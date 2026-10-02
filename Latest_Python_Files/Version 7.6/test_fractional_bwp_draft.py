"""The exported workbench draft is an oracle for the fractional BWP route."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

import get_winding_pattern as gw


class FractionalBwpDraftTests(unittest.TestCase):
    def test_odd_phase_fractional_single_branch_uses_phase_map(self):
        from phase_topology import phase_map

        tp = SimpleNamespace(tp_type='Regular', tp_interval=0, tp_times=0,
                             uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1)
        for phases in (3, 5, 7):
            for pattern in ('BWP', 'UWP'):
                with self.subTest(phases=phases, pattern=pattern):
                    q, poles, layers = 1.5, 4, 2
                    winding = SimpleNamespace(q=q, num_slots=int(q * poles * phases),
                                              num_poles=poles, num_phases=phases,
                                              num_layers=layers, ab=1)
                    layout = SimpleNamespace(phase_shift_list=[0] * layers,
                                             radial_shift=0, inlet_from_weld_side=0)
                    _, database = gw._fractional_wave_single_branch(
                        pattern, tp, winding, layout)
                    self.assertEqual(len(database), phases)
                    records = phase_map(winding.num_slots, poles, layers, phases=phases)
                    lookup = {(slot, layer): phase for slot, layer, phase, _ in records}
                    self.assertEqual([lookup[path[0][:2]] for _, path in database],
                                     list(range(phases)))
                    report = gw.fractional_uwp_candidate_report(database, winding, layout)
                    self.assertTrue(report['layout_retained'], report['errors'])

    def test_odd_phase_uwp_p2_uses_parameterized_sector(self):
        tp = SimpleNamespace(tp_type='Regular', tp_interval=0, tp_times=0,
                             uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1)
        for phases in (3, 5, 7):
            with self.subTest(phases=phases):
                q, poles, layers = 1.5, 4, 2
                winding = SimpleNamespace(q=q, num_slots=int(q * poles * phases),
                                          num_poles=poles, num_phases=phases,
                                          num_layers=layers, ab=int(2 * q),
                                          branch_dividers=(q, 1, 2))
                layout = SimpleNamespace(phase_shift_list=[0] * layers,
                                         radial_shift=0, inlet_from_weld_side=0)
                self.assertTrue(gw.supports_half_integer_uwp_p2('UWP', winding,
                                                                 winding.branch_dividers))
                _, database = gw._fractional_uwp_2q(tp, winding, layout)
                self.assertEqual(len(database), phases * winding.ab)
                report = gw.fractional_uwp_candidate_report(database, winding, layout)
                self.assertTrue(report['layout_retained'], report['errors'])

    def test_factor_bwp_return_uses_full_circle_pitch(self):
        tp = SimpleNamespace(tp_type='Regular', tp_interval=0, tp_times=0,
                             uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1)
        layout = SimpleNamespace(phase_shift_list=[0] * 6, radial_shift=0,
                                 inlet_from_weld_side=0)
        winding = SimpleNamespace(q=1.5, num_slots=36, num_poles=8,
                                  num_phases=3, num_layers=6, ab=2)
        _, database = gw.get_winding_layout('BWP', tp, winding, layout)
        first, second = (database[index][1] for index in (0, 1))
        self.assertEqual([(slot + 1, layer + 1) for slot, layer, _ in first[:13]],
                         [(1, 1), (5, 2), (10, 1), (14, 2),
                          (19, 3), (23, 4), (28, 3), (32, 4),
                          (1, 5), (5, 6), (10, 5), (14, 6), (10, 6)])
        self.assertEqual((first[14][:2], first[15][:2]), ((0, 5), (32, 4)))
        self.assertEqual((second[14][:2], second[15][:2]), ((18, 5), (14, 4)))

    def test_factor_bwp_all_ordinary_edges_keep_main_pitch_after_array(self):
        tp = SimpleNamespace(tp_type='Regular', tp_interval=0, tp_times=0,
                             uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1)
        for q in (1.5, 2.5, 3.5):
            for pp in (2, 4, 6):
                for naa in (factor for factor in range(2, pp + 1)
                            if pp % factor == 0):
                    with self.subTest(q=q, pp=pp, naa=naa):
                        slots = int(6 * q * pp)
                        winding = SimpleNamespace(
                            q=q, num_slots=slots, num_poles=2 * pp,
                            num_phases=3, num_layers=6, ab=naa)
                        layout = SimpleNamespace(phase_shift_list=[0] * 6,
                                                 radial_shift=0,
                                                 inlet_from_weld_side=0)
                        _, database = gw.get_winding_layout('BWP', tp, winding, layout)
                        pitches = {int(3 * q), int(3 * q + 0.5)}
                        for _, path in database:
                            for edge_index, (source, target) in enumerate(
                                    zip(path, path[1:])):
                                if source[1] == target[1]:
                                    continue
                                forward = (target[0] - source[0]) % slots
                                signed = (forward if forward <= slots / 2
                                          else forward - slots)
                                self.assertIn(abs(signed), pitches,
                                              (q, pp, naa, edge_index, source, target))

    def test_factor_branches_wave_across_sectors_before_next_layer_pair(self):
        tp = SimpleNamespace(tp_type='Regular', tp_interval=0, tp_times=0,
                             uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1)
        layout = SimpleNamespace(phase_shift_list=[0] * 6, radial_shift=0,
                                 inlet_from_weld_side=0)
        for pattern in ('BWP', 'UWP'):
            for naa in (2, 4):
                with self.subTest(pattern=pattern, naa=naa):
                    winding = SimpleNamespace(q=1.5, num_slots=36,
                                              num_poles=8, num_phases=3,
                                              num_layers=6, ab=naa)
                    _, database = gw.get_winding_layout(pattern, tp, winding, layout)
                    branch = database[0][1]
                    nodes_per_pair = winding.num_poles // naa
                    self.assertEqual(branch[nodes_per_pair][0], 36 // naa)
                    self.assertEqual(branch[nodes_per_pair][1],
                                     2 if pattern == 'BWP' else 1)
                    self.assertEqual([database[index][1][0][0]
                                      for index in range(naa)],
                                     [index * 36 // naa for index in range(naa)])

    def test_all_positive_half_integer_q_single_branch_starts_in_fuller_pole(self):
        from phase_topology import phase_map

        tp = SimpleNamespace(tp_type='Regular', tp_interval=0, tp_times=0,
                             uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1)
        for q in (0.5, 1.5, 2.5, 3.5, 4.5, 10.5):
            for poles in (4, 8):
                for layers in (2, 6):
                    with self.subTest(q=q, poles=poles, layers=layers):
                        slots = int(q * poles * 3)
                        winding = SimpleNamespace(q=q, num_slots=slots,
                                                  num_poles=poles, num_phases=3,
                                                  num_layers=layers, ab=1)
                        layout = SimpleNamespace(phase_shift_list=[0] * layers,
                                                 radial_shift=0,
                                                 inlet_from_weld_side=0)
                        starts, database = gw.get_winding_layout(
                            'BWP', tp, winding, layout)
                        self.assertEqual(len(starts), 3)
                        self.assertEqual(len(database), 3)
                        records = phase_map(slots, poles, layers)
                        for phase, start in enumerate(starts):
                            start_pole = poles * start[0] // slots
                            counts = {}
                            for slot, layer, record_phase, _sign in records:
                                if layer == 0 and record_phase == phase:
                                    pole = poles * slot // slots
                                    counts[pole] = counts.get(pole, 0) + 1
                            self.assertEqual(counts[start_pole], max(counts.values()))
                        report = gw.fractional_uwp_candidate_report(
                            database, winding, layout)
                        self.assertTrue(report['topology_valid'], report['errors'])
                        self.assertTrue(report['electrically_valid'], report['errors'])
                        short_pitch = int(3 * q)
                        pass_length = poles * layers // 2
                        for path_id, path in database:
                            for pass_index in range(1, int(2 * q)):
                                before = path[pass_index * pass_length - 1]
                                after = path[pass_index * pass_length]
                                self.assertEqual(before[1], after[1])
                                self.assertEqual((after[0] - before[0]) % slots,
                                                 (-short_pitch) % slots)

    def test_exported_phase_a_route_and_three_phase_validation(self):
        draft = json.loads(Path(__file__).with_name('pattern_process_draft.json').read_text())
        winding = SimpleNamespace(q=1.5, num_slots=36, num_poles=8,
                                  num_phases=3, num_layers=6, ab=1)
        tp = SimpleNamespace(tp_type='Regular', tp_interval=0, tp_times=0,
                             uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1)
        layout = SimpleNamespace(phase_shift_list=[0] * 6, radial_shift=0,
                                 inlet_from_weld_side=0)
        starts, database = gw.get_winding_layout('BWP', tp, winding, layout)
        actual = [(slot + 1, layer + 1) for slot, layer, _ in database[0][1]]
        expected = [(node['slot'], node['layer']) for node in draft['path']]
        self.assertEqual(actual, expected)
        self.assertEqual(len(starts), 3)
        report = gw.fractional_uwp_candidate_report(database, winding, layout)
        self.assertTrue(report['topology_valid'], report['errors'])
        self.assertTrue(report['electrically_valid'], report['errors'])
        edges = [edge for edge in report['sector_array']['special_edges']
                 if edge['branch_id'] == 1]
        self.assertEqual(len(edges), 8)
        self.assertEqual({edge['side'] for edge in edges}, {'insert'})
        self.assertEqual([edge['kind'] for edge in edges].count('jumper'), 2)
        self.assertEqual([edge['kind'] for edge in edges].count('first_last_layer'), 6)

    def test_base_support_follows_pole_pair_divisors(self):
        self.assertTrue(gw.evaluate_base_pattern_support('BWP', 1.5, 8, 1, 6)[0])
        self.assertTrue(gw.evaluate_base_pattern_support('BWP', 0.5, 8, 1, 6)[0])
        self.assertTrue(gw.evaluate_base_pattern_support('BWP', 4.5, 8, 1, 6)[0])
        self.assertTrue(gw.evaluate_base_pattern_support('BWP', 4.5, 8, 2, 6)[0])
        self.assertTrue(gw.evaluate_base_pattern_support('BWP', 1.5, 8, 2, 6)[0])
        self.assertTrue(gw.evaluate_base_pattern_support('BWP', 1.5, 8, 4, 6)[0])
        self.assertFalse(gw.evaluate_base_pattern_support('BWP', 1.5, 8, 3, 6)[0])
        self.assertFalse(gw.evaluate_base_pattern_support('UWP', 2.5, 8, 3, 6)[0])

    def test_existing_uwp_two_q_route_takes_priority_over_sector_array(self):
        winding = SimpleNamespace(q=1.5, num_slots=54, num_poles=12,
                                  num_phases=3, num_layers=6, ab=3)
        tp = SimpleNamespace(tp_type='Regular', tp_interval=0, tp_times=0,
                             uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1)
        layout = SimpleNamespace(phase_shift_list=[0] * 6, radial_shift=0,
                                 inlet_from_weld_side=0)
        _, database = gw.get_winding_layout('UWP', tp, winding, layout)
        self.assertFalse(hasattr(database, 'sector_array_report'))

    def test_single_branch_rejects_shifted_zero_fundamental(self):
        winding = SimpleNamespace(q=0.5, num_slots=12, num_poles=8,
                                  num_phases=3, num_layers=6, ab=1)
        tp = SimpleNamespace(tp_type='Regular', tp_interval=0, tp_times=0,
                             uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1)
        layout = SimpleNamespace(phase_shift_list=[0, 1, -1, 2, -2, 3],
                                 radial_shift=0, inlet_from_weld_side=0)
        with self.assertRaisesRegex(ValueError, 'zero_fundamental'):
            gw.get_winding_layout('BWP', tp, winding, layout)

    def test_even_poles_and_layers_matrix(self):
        for poles in (4, 8):
            for layers in (4, 6, 8):
                with self.subTest(poles=poles, layers=layers):
                    supported, reason = gw.evaluate_base_pattern_support(
                        'BWP', 1.5, poles, 1, layers)
                    self.assertTrue(supported, reason)

    def test_q_one_point_five_sector_arrays_cover_each_phase(self):
        for pp in (2, 4, 6):
            for naa in (divisor for divisor in range(2, pp + 1) if pp % divisor == 0):
                for layers in (4, 6, 8):
                    with self.subTest(pp=pp, naa=naa, layers=layers):
                        slots = 9 * pp
                        winding = SimpleNamespace(q=1.5, num_slots=slots,
                                                  num_poles=2 * pp, num_phases=3,
                                                  num_layers=layers, ab=naa)
                        tp = SimpleNamespace(tp_type='Regular', tp_interval=0,
                                             tp_times=0, uni_tp=0, pltp_fl=0,
                                             pltp_ll=0, jltp=0, jld=1)
                        layout = SimpleNamespace(phase_shift_list=[0] * layers,
                                                 radial_shift=0, inlet_from_weld_side=0)
                        _, database = gw.get_winding_layout('BWP', tp, winding, layout)
                        self.assertEqual(len(database), 3 * naa)
                        width = slots // naa
                        segment_length = 2 * pp // naa
                        offsets = database.sector_array_report['segment_offsets']
                        for phase in range(3):
                            first = database[phase * naa][1]
                            self.assertGreater(len({slot // width for slot, _, _ in first}), 1)
                            for branch_index in range(naa):
                                path = database[phase * naa + branch_index][1]
                                for index, ((base_slot, base_layer, _),
                                            (slot, layer, _)) in enumerate(zip(first, path)):
                                    self.assertEqual((slot, layer),
                                                     ((base_slot + branch_index * width) % slots,
                                                      base_layer))
                                    self.assertEqual(slot // width,
                                                     (first[index][0] // width
                                                      + branch_index) % naa)
                                self.assertEqual(path[0][0],
                                                 (first[0][0] + branch_index * width) % slots)
                        self.assertEqual(len(offsets), len(first) // segment_length)
                        report = gw.fractional_uwp_candidate_report(
                            database, winding, layout)
                        self.assertTrue(report['topology_valid'], report['errors'])
                        self.assertTrue(report['electrically_valid'], report['errors'])

    def test_q_two_point_five_and_three_point_five_sector_arrays(self):
        for q in (2.5, 3.5):
            for pp in (2, 4, 6):
                for naa in (divisor for divisor in range(1, pp + 1)
                            if pp % divisor == 0):
                    for layers in (4, 6, 8):
                        with self.subTest(q=q, pp=pp, naa=naa, layers=layers):
                            slots = int(6 * q * pp)
                            winding = SimpleNamespace(
                                q=q, num_slots=slots, num_poles=2 * pp,
                                num_phases=3, num_layers=layers, ab=naa)
                            tp = SimpleNamespace(tp_type='Regular', tp_interval=0,
                                                 tp_times=0, uni_tp=0, pltp_fl=0,
                                                 pltp_ll=0, jltp=0, jld=1)
                            layout = SimpleNamespace(phase_shift_list=[0] * layers,
                                                     radial_shift=0,
                                                     inlet_from_weld_side=0)
                            _, database = gw.get_winding_layout('BWP', tp, winding, layout)
                            self.assertEqual(len(database), 3 * naa)
                            width = slots // naa
                            for phase in range(3):
                                first = database[phase * naa][1]
                                for branch_index in range(naa):
                                    path = database[phase * naa + branch_index][1]
                                    self.assertEqual(
                                        [(slot, layer) for slot, layer, _ in path],
                                        [((slot + branch_index * width) % slots, layer)
                                         for slot, layer, _ in first])
                                    if naa > 1:
                                        self.assertGreater(len({slot // width for slot, _, _ in path}), 1)
                            report = gw.fractional_uwp_candidate_report(
                                database, winding, layout)
                            self.assertTrue(report['topology_valid'], report['errors'])
                            self.assertTrue(report['electrically_valid'], report['errors'])

    def test_uwp_has_distinct_forward_sector_rule(self):
        for q in (1.5, 2.5, 3.5):
            for pp in (2, 4, 6):
                for naa in (divisor for divisor in range(1, pp + 1)
                            if pp % divisor == 0):
                    # UWP Naa=2q retains its established generator.
                    if naa == int(2 * q):
                        continue
                    for layers in (4, 6, 8):
                        with self.subTest(q=q, pp=pp, naa=naa, layers=layers):
                            winding = SimpleNamespace(
                                q=q, num_slots=int(6 * q * pp),
                                num_poles=2 * pp, num_phases=3,
                                num_layers=layers, ab=naa)
                            tp = SimpleNamespace(tp_type='Regular', tp_interval=0,
                                                 tp_times=0, uni_tp=0,
                                                 pltp_fl=0, pltp_ll=0,
                                                 jltp=0, jld=1)
                            layout = SimpleNamespace(
                                phase_shift_list=[0] * layers,
                                radial_shift=0, inlet_from_weld_side=0)
                            _, uwp = gw.get_winding_layout('UWP', tp, winding, layout)
                            _, bwp = gw.get_winding_layout('BWP', tp, winding, layout)
                            self.assertNotEqual([node[:2] for node in uwp[0][1]],
                                                [node[:2] for node in bwp[0][1]])
                            report = gw.fractional_uwp_candidate_report(
                                uwp, winding, layout)
                            self.assertTrue(report['topology_valid'], report['errors'])
                            self.assertTrue(report['electrically_valid'], report['errors'])

    def test_factor_wave_special_edges_keep_short_pitch(self):
        tp = SimpleNamespace(tp_type='Regular', tp_interval=0, tp_times=0,
                             uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1)
        for pattern in ('BWP', 'UWP'):
            for q in (1.5, 2.5, 3.5):
                for pp in (2, 4, 6):
                    for naa in (divisor for divisor in range(2, pp + 1)
                                if pp % divisor == 0):
                        if pattern == 'UWP' and naa == int(2 * q):
                            continue
                        for layers in (4, 6, 8):
                            with self.subTest(pattern=pattern, q=q, pp=pp,
                                              naa=naa, layers=layers):
                                winding = SimpleNamespace(
                                    q=q, num_slots=int(6 * q * pp),
                                    num_poles=2 * pp, num_phases=3,
                                    num_layers=layers, ab=naa)
                                layout = SimpleNamespace(
                                    phase_shift_list=[0] * layers,
                                    radial_shift=0, inlet_from_weld_side=0)
                                _, database = gw.get_winding_layout(
                                    pattern, tp, winding, layout)
                                longest_pitch = int(3 * q + 0.5)
                                for edge in database.sector_array_report['special_edges']:
                                    self.assertLessEqual(
                                        abs(edge['grid_shortest_pitch']),
                                        longest_pitch)
                                    self.assertEqual(edge['grid_shortest_pitch'],
                                                     edge['default_signed_pitch'])

    def test_sector_shifts_apply_after_default_array(self):
        shifts = (0, 1, -1, 2, -2, 0)
        tp = SimpleNamespace(tp_type='Regular', tp_interval=0, tp_times=0,
                             uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1)
        for pattern in ('BWP', 'UWP'):
            for q in (1.5, 2.5, 3.5):
                for pp, naa in ((2, 2), (4, 4), (6, 2), (6, 3), (6, 6)):
                    if pattern == 'UWP' and naa == int(2 * q):
                        continue
                    with self.subTest(pattern=pattern, q=q, pp=pp, naa=naa):
                        slots = int(6 * q * pp)
                        winding = SimpleNamespace(q=q, num_slots=slots,
                                                  num_poles=2 * pp,
                                                  num_phases=3, num_layers=6,
                                                  ab=naa)
                        zero = SimpleNamespace(phase_shift_list=[0] * 6,
                                               radial_shift=0,
                                               inlet_from_weld_side=0)
                        shifted = SimpleNamespace(phase_shift_list=list(shifts),
                                                  radial_shift=0,
                                                  inlet_from_weld_side=0)
                        _, baseline = gw.get_winding_layout(pattern, tp, winding, zero)
                        _, actual = gw.get_winding_layout(pattern, tp, winding, shifted)
                        for (_, before), (_, after) in zip(baseline, actual):
                            self.assertEqual([(s + shifts[l]) % slots for s, l, _ in before],
                                             [s for s, _, _ in after])
                        report = gw.fractional_uwp_candidate_report(
                            actual, winding, shifted)
                        self.assertTrue(report['topology_valid'], report['errors'])
                        self.assertTrue(report['electrically_valid'], report['errors'])
                        self.assertTrue(report['sector_array']['shifted_boundary_crossings'])

    def test_uwp_special_pitch_is_forward_and_unsupported_swaps_reject(self):
        winding = SimpleNamespace(q=1.5, num_slots=18, num_poles=4,
                                  num_phases=3, num_layers=4, ab=2)
        tp = SimpleNamespace(tp_type='Regular', tp_interval=0, tp_times=0,
                             uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1)
        layout = SimpleNamespace(phase_shift_list=[0] * 4, radial_shift=0,
                                 inlet_from_weld_side=0)
        _, database = gw.get_winding_layout('UWP', tp, winding, layout)
        first = database.sector_array_report['special_edges'][0]
        self.assertEqual(first['default_signed_pitch'], 5)
        self.assertEqual(first['grid_shortest_pitch'], 5)
        _, bwp = gw.get_winding_layout('BWP', tp, winding, layout)
        self.assertEqual(bwp.sector_array_report['special_edges'][0]
                         ['default_signed_pitch'], 5)
        for field in ('radial_shift', 'inlet_from_weld_side'):
            setattr(layout, field, 1)
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, 'does not support'):
                    gw.get_winding_layout('UWP', tp, winding, layout)
            setattr(layout, field, 0)
