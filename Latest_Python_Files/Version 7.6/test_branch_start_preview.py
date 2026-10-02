"""Independent candidate-only branch start behavior."""
import copy
import cmath
import math
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

import branch_start_preview as preview


class BranchStartPreviewTests(unittest.TestCase):
    def test_fractional_division_uses_one_odd_phase_rule(self):
        from phase_topology import phase_map

        for phases in (3, 5, 7, 9):
            with self.subTest(phases=phases):
                slots, poles, layers, naa = 12 * phases, 8, 4, 2
                winding = NS(q=1.5, num_slots=slots, num_poles=poles,
                             num_layers=layers, num_phases=phases, ab=naa)
                layout = NS(phase_shift_list=[0] * layers, radial_shift=0)
                records = phase_map(slots, poles, layers, [0] * layers, phases)
                context = preview.build_preview_context(
                    'BWP', winding, layout, NS(), records)
                self.assertEqual(context['status'], 'division_candidate', context['reason'])
                self.assertEqual(len(context['branches']), phases * naa)
                self.assertEqual({branch['phase'] for branch in context['branches']},
                                 set(range(phases)))
                self.assertEqual(len({point for branch in context['branches']
                                      for point in branch['members']}), slots * layers)

    def test_fractional_default_division_uses_common_factors(self):
        self.assertEqual(preview.proposed_division_rule(2.5, 8, 4), (4, 1))
        self.assertEqual(preview.proposed_division_rule(1.5, 10, 5), (5, 1))
        plan = preview.preferred_division_plan('BWP', 60, 8, 6, 4, [0]*6)
        self.assertEqual(plan['status'], 'candidate', plan['reason'])
        self.assertEqual((plan['pole_divider'], plan['position_divider']), (4, 1))

    def test_fractional_default_falls_back_when_preferred_factor_fails(self):
        failed = {'status': 'unavailable', 'reason': 'preferred factor fails'}
        candidate = {'status': 'candidate', 'pole_divider': 1,
                     'position_divider': 4}
        with patch.object(preview, 'evaluate_division_rule',
                          side_effect=[failed, candidate]) as evaluate:
            self.assertIs(preview.preferred_division_plan(
                'BWP', 60, 8, 6, 4, [0]*6), candidate)
        self.assertEqual(evaluate.call_args_list[0].args[-1], (4, 1))
        self.assertEqual(len(evaluate.call_args_list[1].args), 6)

    def setUp(self):
        self.w = NS(q=1, num_slots=12, num_poles=4, num_layers=1, num_phases=3, ab=1)
        self.layout = NS(phase_shift_list=[0], radial_shift=0)
        self.tp = NS()
        self.paths = [[p+1, [(p+3*i, 0, 0) for i in range(4)]] for p in range(3)]
        self.records = tuple((p+3*i, 0, p, (-1)**i) for p in range(3) for i in range(4))

    def context(self):
        with patch.object(preview.gw, 'get_winding_layout', return_value=([], self.paths)):
            return preview.build_preview_context('BWP', self.w, self.layout, self.tp, self.records)

    def test_selection_rotates_complete_branch_without_mutation(self):
        before = copy.deepcopy((self.paths, vars(self.w), vars(self.layout)))
        context = self.context()
        with patch.object(preview.gw, 'find_single_connection_between', return_value=[1, 0, 0]):
            result = preview.preview_branch_start(context, 1, 6, 0)
        self.assertEqual(result['status'], 'candidate')
        self.assertEqual([c[0] for c in result['path']], [6, 9, 0, 3])
        self.assertEqual(result['offset'], 2)
        self.assertFalse(result['production_ready'])
        self.assertEqual(context['branches'][0]['path'][0][:2], (0, 0))
        self.assertEqual(before, (self.paths, vars(self.w), vars(self.layout)))

    def test_rejects_cross_branch_and_unexpressible_closure(self):
        context = self.context()
        self.assertEqual(preview.preview_branch_start(context, 1, 1, 0)['status'], 'rejected')
        with patch.object(preview.gw, 'find_single_connection_between', side_effect=ValueError('no edge')):
            result = preview.preview_branch_start(context, 1, 3, 0)
        self.assertEqual(result['status'], 'rejected')
        self.assertEqual(result['path'], ())

    def test_rejects_duplicate_or_wrong_direction_paths(self):
        self.paths[0][1][-1] = self.paths[0][1][0]
        self.assertEqual(self.context()['status'], 'unavailable')
        self.setUp()
        self.records = tuple((s, l, p, 1) for s, l, p, _ in self.records)
        self.assertEqual(self.context()['status'], 'unavailable')

    def test_fractional_preview_rejects_inconsistent_q_without_generator(self):
        self.w.q = 0.5
        with patch.object(preview.gw, 'get_winding_layout', side_effect=AssertionError('generator')):
            context = preview.build_preview_context('BWP', self.w, self.layout, self.tp, self.records)
        self.assertEqual(context['status'], 'unavailable')
        self.assertIn('q does not match', context['reason'])

    def test_fractional_initial_branch_members_cover_phase_map(self):
        from phase_topology import phase_map

        winding = NS(q=1.5, num_slots=36, num_poles=8, num_layers=6, num_phases=3, ab=2)
        layout = NS(phase_shift_list=[0]*6, radial_shift=0)
        records = phase_map(36, 8, 6, [0]*6)
        with patch.object(preview.gw, 'get_winding_layout', side_effect=AssertionError('generator')):
            context = preview.build_preview_context('BWP', winding, layout, self.tp, records)
        self.assertEqual(context['status'], 'division_candidate', context['reason'])
        self.assertEqual(len(context['branches']), 6)
        owners = {}
        for branch in context['branches']:
            self.assertEqual(len(branch['members']), 36)
            self.assertIn(branch['start'], branch['members'])
            self.assertFalse(branch['path'])
            for position in branch['members']:
                self.assertNotIn(position, owners)
                owners[position] = branch
                self.assertEqual(next(p for s, l, p, _ in records if (s, l) == position),
                                 branch['phase'])
        self.assertEqual(set(owners), {(s, l) for s, l, _, _ in records})
        self.assertEqual(owners[(0, 0)]['number'], 1)
        self.assertEqual(owners[(18, 0)]['number'], 2)
        self.assertEqual(context['division_plan']['pole_divider'], 2)
        second_start = context['branches'][1]['start']
        self.assertEqual(owners[second_start]['number'], 2)
        signed = {(s, l): sign for s, l, _, sign in records}
        emfs = [sum(signed[slot, layer] * cmath.exp(1j * math.pi * 8 * slot / 36)
                    for slot, layer in branch['members']) for branch in context['branches']]
        for phase in range(3):
            self.assertAlmostEqual(abs(emfs[2*phase] - emfs[2*phase+1]), 0, places=10)
        result = preview.preview_branch_start(context, owners[second_start]['id'], *second_start)
        self.assertEqual(result['status'], 'branch_preview')
        self.assertEqual(result['path'], ())

    def test_fractional_position_split_keeps_starts_and_equal_quotas(self):
        from phase_topology import phase_map

        winding = NS(q=1.25, num_slots=30, num_poles=8, num_layers=6, num_phases=3, ab=5)
        layout = NS(phase_shift_list=[0]*6, radial_shift=0)
        records = phase_map(30, 8, 6, [0]*6)
        context = preview.build_preview_context('BWP', winding, layout, self.tp, records)
        self.assertEqual(context['status'], 'division_candidate', context['reason'])
        self.assertEqual(context['division_plan']['symmetry'], 'weak')
        self.assertEqual(len(context['branches']), 15)
        self.assertEqual({len(b['members']) for b in context['branches']}, {12})
        self.assertEqual(len({point for b in context['branches'] for point in b['members']}),
                         len(records))
        self.assertTrue(all(b['start'] in b['members'] for b in context['branches']))

    def test_fractional_shifted_phase_map_keeps_unique_branch_ownership(self):
        from phase_topology import phase_map

        shifts = [0, 0, 1, 1, 2, 2]
        winding = NS(q=1.5, num_slots=36, num_poles=8, num_layers=6, num_phases=3, ab=2)
        layout = NS(phase_shift_list=shifts, radial_shift=0)
        records = phase_map(36, 8, 6, shifts)
        context = preview.build_preview_context('BWP', winding, layout, self.tp, records)
        self.assertEqual(context['status'], 'division_candidate', context['reason'])
        members = [position for branch in context['branches'] for position in branch['members']]
        self.assertEqual(len(members), len(set(members)))
        self.assertEqual(set(members), {(s, l) for s, l, _, _ in records})

    def test_developer_division_rules_for_one_point_five_q(self):
        from phase_topology import phase_map

        records = phase_map(36, 8, 6, [0]*6)
        for naa, pole_groups, positions, width in ((2, 2, 1, 18),
                                                    (3, 1, 3, 36),
                                                    (4, 4, 1, 9),
                                                    (6, 2, 3, 18)):
            with self.subTest(naa=naa):
                winding = NS(q=1.5, num_slots=36, num_poles=8,
                             num_layers=6, num_phases=3, ab=naa)
                layout = NS(phase_shift_list=[0]*6, radial_shift=0)
                context = preview.build_preview_context(
                    'BWP', winding, layout, self.tp, records,
                    division_rule=(pole_groups, positions))
                self.assertEqual(context['status'], 'division_candidate', context['reason'])
                plan = context['division_plan']
                self.assertEqual((plan['pole_divider'], plan['position_divider']),
                                 (pole_groups, positions))
                self.assertEqual(len(context['branches']), 3*naa)
                for branch in context['branches']:
                    region = (branch['number']-1) % pole_groups
                    self.assertTrue(all(region*width <= slot < (region+1)*width
                                        for slot, _ in branch['members']))
                    self.assertEqual(len(branch['members']), 72//naa)
                self.assertEqual(len({point for branch in context['branches']
                                      for point in branch['members']}), len(records))

    def test_documented_one_point_five_q_rule_is_initial_preview(self):
        from phase_topology import phase_map

        layout = NS(phase_shift_list=[0]*6, radial_shift=0)
        for naa, expected in ((2, (2, 1)), (3, (1, 3)),
                              (4, (4, 1)), (6, (2, 3))):
            with self.subTest(naa=naa):
                winding = NS(q=1.5, num_slots=36, num_poles=8,
                             num_layers=6, num_phases=3, ab=naa)
                context = preview.build_preview_context('BWP', winding, layout, self.tp,
                                                        phase_map(36, 8, 6, [0]*6))
                self.assertEqual(context['status'], 'division_candidate')
                self.assertEqual((context['division_plan']['pole_divider'],
                                  context['division_plan']['position_divider']), expected)

    def test_two_point_five_q_two_branches_use_contiguous_half_ring_regions(self):
        from phase_topology import phase_map

        winding = NS(q=2.5, num_slots=60, num_poles=8,
                     num_layers=6, num_phases=3, ab=2)
        layout = NS(phase_shift_list=[0]*6, radial_shift=0)
        records = phase_map(60, 8, 6, [0]*6)
        context = preview.build_preview_context('BWP', winding, layout, self.tp,
                                                records)
        self.assertEqual(context['status'], 'division_candidate', context['reason'])
        self.assertEqual((context['division_plan']['pole_divider'],
                          context['division_plan']['position_divider']), (2, 1))
        self.assertEqual(len(context['branches']), 6)
        self.assertEqual({len(b['members']) for b in context['branches']}, {60})
        for branch in context['branches']:
            first_slot = 0 if branch['number'] == 1 else 30
            self.assertTrue(all(first_slot <= slot < first_slot + 30
                                for slot, _ in branch['members']))
            self.assertIn(branch['start'], branch['members'])
        self.assertEqual({point for branch in context['branches']
                          for point in branch['members']},
                         {(s, l) for s, l, _, _ in records})

    def test_developer_rule_rejects_wrong_product_without_generator(self):
        from phase_topology import phase_map

        winding = NS(q=1.5, num_slots=36, num_poles=8, num_layers=6, num_phases=3, ab=3)
        layout = NS(phase_shift_list=[0]*6, radial_shift=0)
        with patch.object(preview.gw, 'get_winding_layout', side_effect=AssertionError('generator')):
            context = preview.build_preview_context('BWP', winding, layout, self.tp,
                                                    phase_map(36, 8, 6, [0]*6),
                                                    division_rule=(2, 2))
        self.assertEqual(context['status'], 'unavailable')
        self.assertIn('Naa', context['reason'])

    def test_real_integer_baseline_and_shifted_mapping(self):
        from phase_topology import phase_map
        winding = NS(q=2, num_slots=48, num_poles=8, num_layers=6, num_phases=3, ab=2)
        transposition = NS(tp_type='Regular', pltp_fl=0, pltp_ll=0, jltp=1, jld=1, uni_tp=0)
        for shifts in ([0]*6, [0, 0, 1, 1, 2, 2]):
            with self.subTest(shifts=shifts):
                layout = NS(phase_shift_list=shifts, radial_shift=0, inlet_from_weld_side=1)
                context = preview.build_preview_context('BWP', winding, layout, transposition,
                                                        phase_map(48, 8, 6, shifts))
                self.assertEqual(context['status'], 'candidate', context['reason'])
                self.assertEqual([b['phase'] for b in context['branches']], [0, 0, 1, 1, 2, 2])
                self.assertEqual([len(b['path']) for b in context['branches']], [48]*6)
                branch = context['branches'][0]
                selected = branch['path'][4][:2]
                result = preview.preview_branch_start(context, branch['id'], *selected)
                self.assertEqual(result['status'], 'candidate', result['reason'])
                self.assertEqual(result['path'][0][:2], selected)
                self.assertEqual(set(result['path']), set(branch['path']))

    def test_chw_is_not_silently_mapped_to_phase_only_grid(self):
        self.layout.radial_shift = 1
        with patch.object(preview.gw, 'get_winding_layout', side_effect=AssertionError('generator')):
            context = preview.build_preview_context('BWP', self.w, self.layout, self.tp, self.records)
        self.assertEqual(context['status'], 'unavailable')
        self.assertIn('CHW', context['reason'])

    def test_closed_loop_checks_and_exposes_final_connection(self):
        self.layout.in_out_connection = 1
        context = self.context()
        with patch.object(preview.gw, 'find_single_connection_between', return_value=[1, 0, 0]) as check:
            result = preview.preview_branch_start(context, 1, 0, 0)
        self.assertTrue(result['closed'])
        self.assertEqual(check.call_args.args[:2], ((9, 0, 0), (0, 0, 0)))
        with patch.object(preview.gw, 'find_single_connection_between', side_effect=ValueError('no closure')):
            rejected = preview.preview_branch_start(context, 1, 0, 0)
        self.assertEqual(rejected['status'], 'rejected')
        self.assertEqual(rejected['path'], ())
        self.assertFalse(rejected['closed'])
        with patch.object(preview.gw, 'find_single_connection_between', return_value=[1, 0, 0]) as check:
            rotated = preview.preview_branch_start(context, 1, 6, 0)
        self.assertTrue(rotated['closed'])
        self.assertEqual([call.args[:2] for call in check.call_args_list],
                         [((9, 0, 0), (0, 0, 0)), ((3, 0, 0), (6, 0, 0))])


if __name__ == '__main__':
    unittest.main()
