"""Independent checks of count-based branch symmetry rules."""
import cmath
from collections import Counter, defaultdict
import math
import unittest

from phase_topology import (classify_fractional_branch_plan,
                            default_start_conductors, phase_map,
                            symmetry_branch_rules, _symmetry_rule)


class SymmetryBranchRuleTests(unittest.TestCase):
    def test_reference_cases(self):
        for slots, weak in ((36, [1, 2, 3, 4, 6, 12]),
                            (60, [1, 2, 4, 5, 10, 20]),
                            (84, [1, 2, 4, 7, 14, 28])):
            result = symmetry_branch_rules(slots, 8, 6)
            self.assertEqual(result['strong']['allowed_naa'], [1, 2, 4])
            self.assertEqual(result['weak']['allowed_naa'], weak)
            self.assertEqual(result['strong']['max_naa'], 4)
            self.assertEqual(result['weak']['max_naa'], weak[-1])
            self.assertEqual(set(result['strong']['counts'].values()), {4})
            self.assertNotIn(3, result['strong']['quotas'])

    def test_unequal_category_counts_use_gcd_not_minimum(self):
        result = _symmetry_rule({(0, 0): 6, (0, 1): 4}, 'weak')
        self.assertEqual(result['allowed_naa'], [1, 2])
        self.assertEqual(result['quotas'][2], {(0, 0): 3, (0, 1): 2})
        self.assertEqual(result['quotas'][1], result['counts'])

    @staticmethod
    def angular_buckets(records, slots, poles):
        # Independent trigonometric oracle; do not reuse modular angle keys.
        buckets = defaultdict(list)
        for record in records:
            slot, layer, phase, sign = record
            value = sign * cmath.exp(1j * math.pi * poles * slot / slots)
            key = (phase, layer, round(value.real, 9), round(value.imag, 9))
            buckets[key].append(record)
        return buckets

    def test_matrix_witnesses_and_shift_invariance(self):
        for q in (0.5, 1, 1.5, 2, 2.5, 3, 3.5):
            for poles in (4, 8):
                for layers in (2, 4, 6, 8):
                    slots = int(q * 3 * poles)
                    base = symmetry_branch_rules(slots, poles, layers)
                    shifts = [(-1)**l * (l + slots) for l in range(layers)]
                    result = symmetry_branch_rules(slots, poles, layers, shifts)
                    records = phase_map(slots, poles, layers, shifts)
                    buckets = self.angular_buckets(records, slots, poles)
                    self.assertEqual(sorted(map(len, buckets.values())),
                                     sorted(result['strong']['counts'].values()))
                    self.assertEqual(result['weak']['max_naa'] % result['strong']['max_naa'], 0)
                    for mode in ('strong', 'weak'):
                        rule = result[mode]
                        self.assertEqual(rule['allowed_naa'], base[mode]['allowed_naa'])
                        groups = buckets if mode == 'strong' else defaultdict(list)
                        if mode == 'weak':
                            for record in records:
                                groups[record[2], record[1]].append(record)
                        for naa in rule['allowed_naa']:
                            branches = defaultdict(list)
                            for key, members in groups.items():
                                self.assertEqual(len(members) % naa, 0)
                                for branch in range(naa):
                                    branches[key[0], branch].extend(members[branch::naa])
                            self.assertEqual(Counter(r for b in branches.values() for r in b), Counter(records))
                            for phase in range(3):
                                reference = None
                                for branch in range(naa):
                                    members = branches[phase, branch]
                                    counts = Counter(r[1] for r in members)
                                    self.assertEqual(counts, Counter(r[1] for r in branches[phase, 0]))
                                    emf = sum(d * cmath.exp(1j * math.pi * poles * s / slots)
                                              for s, l, p, d in members)
                                    if mode == 'strong' and reference is not None:
                                        self.assertLess(abs(emf - reference), 1e-8)
                                    reference = emf
                            for key, count in rule['counts'].items():
                                self.assertEqual(rule['quotas'][naa][key] * naa, count)

    def test_weak_does_not_imply_equal_emf(self):
        records = phase_map(36, 8, 6)
        groups = defaultdict(list)
        for record in records:
            if record[2] == 0:
                groups[record[1]].append(record)
        branches = [[], []]
        for members in groups.values():
            members.sort(key=lambda r: (r[3] * math.cos(math.pi * 8 * r[0] / 36)))
            half = len(members) // 2
            branches[0].extend(members[:half])
            branches[1].extend(members[half:])
        self.assertEqual(Counter(r[1] for r in branches[0]), Counter(r[1] for r in branches[1]))
        emf = [sum(d * cmath.exp(1j * math.pi * 8 * s / 36) for s,l,p,d in b) for b in branches]
        self.assertGreater(abs(emf[0] - emf[1]), 1)

    def test_invalid_inputs(self):
        for args in ((0, 8, 6), (36.0, 8, 6), (True, 8, 6),
                     (36, 7, 6), (36, 8, 3), (36, 8, 0),
                     (36, 8, True), (36, 8, 6.0)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                symmetry_branch_rules(*args)
        for shifts in ([0], [0, 0, 0, 0, 0, 0.5]):
            with self.assertRaises(ValueError):
                symmetry_branch_rules(36, 8, 6, shifts)

    def test_general_rational_q_and_default_starts(self):
        expected = {
            (18, 8): ([1, 2], [1, 2, 3, 6]),       # q = 3/4
            (30, 8): ([1, 2], [1, 2, 5, 10]),      # q = 5/4
            (24, 6): ([1, 2, 3, 6], [1, 2, 3, 6]), # q = 4/3
            (30, 6): ([1, 2, 3, 6], [1, 2, 3, 6]), # q = 5/3
        }
        for (slots, poles), (strong, weak) in expected.items():
            with self.subTest(slots=slots, poles=poles):
                result = symmetry_branch_rules(slots, poles, 6)
                self.assertEqual(result['strong']['allowed_naa'], strong)
                self.assertEqual(result['weak']['allowed_naa'], weak)
                for mode in ('strong', 'weak'):
                    for naa in result[mode]['allowed_naa']:
                        starts = default_start_conductors(
                            slots, poles, 6, naa, mode)
                        self.assertEqual(
                            result[mode]['default_start_conductors'][naa], starts)
                        self.assertEqual(len(starts), 3 * naa)
                        self.assertEqual(len({(s['slot'], s['layer']) for s in starts}),
                                         3 * naa)
                        for phase in range(3):
                            phase_starts = [s for s in starts if s['phase'] == phase]
                            self.assertEqual([s['branch'] for s in phase_starts],
                                             list(range(naa)))
                            self.assertTrue(all(s['layer'] == 0 for s in phase_starts))
                            distinct_poles = len({s['pole_region'] for s in phase_starts})
                            available_poles = len({(poles * s) // slots for s, l, p, d
                                                   in phase_map(slots, poles, 6)
                                                   if p == phase and l == 0})
                            self.assertEqual(distinct_poles, min(naa, available_poles))

    def test_last_layer_preference_and_invalid_naa(self):
        starts = default_start_conductors(30, 8, 6, 5, 'weak',
                                          preferred_layer='last')
        self.assertTrue(all(start['layer'] == 5 for start in starts))
        with self.assertRaises(ValueError):
            default_start_conductors(30, 8, 6, 5, 'strong')
        for naa in (0, True, 1.5):
            with self.assertRaises(ValueError):
                default_start_conductors(30, 8, 6, naa, 'weak')
        with self.assertRaises(ValueError):
            default_start_conductors(30, 8, 6, 1, 'other')
        with self.assertRaises(ValueError):
            default_start_conductors(30, 8, 6, 1, 'weak',
                                     preferred_layer='middle')

    def test_missing_phase_map_and_generator_shifts(self):
        for slots, poles in ((3, 6), (6, 12)):
            with self.subTest(slots=slots, poles=poles), self.assertRaisesRegex(
                    ValueError, 'every phase and layer'):
                symmetry_branch_rules(slots, poles, 2)
        shifts = (value for value in [0] * 6)
        starts = default_start_conductors(30, 8, 6, 1, 'strong', shifts)
        self.assertEqual(len(starts), 3)

    def test_fractional_preview_can_prefer_integer_style_position_division(self):
        default = classify_fractional_branch_plan(36, 8, 6, 2, 'BWP')
        position = classify_fractional_branch_plan(
            36, 8, 6, 2, 'BWP', prefer_position_division=True)
        self.assertEqual((default['pole_divider'], default['position_divider']), (2, 1))
        self.assertEqual(position['status'], 'candidate')
        self.assertEqual((position['pole_divider'], position['position_divider']), (1, 2))

    def test_fractional_division_plan_matrix(self):
        patterns = ('BWP', 'UWP', 'SSP', 'SLP', 'TSP',
                    'ZLP', 'CP', 'ZPP', 'TLP', 'LPP')
        for slots, poles in ((18, 8), (30, 8), (24, 6),
                             (30, 6), (36, 8), (48, 8)):
            for layers in (4, 6):
                rules = symmetry_branch_rules(slots, poles, layers)
                for symmetry in ('strong', 'weak'):
                    for naa in rules[symmetry]['allowed_naa']:
                        base = classify_fractional_branch_plan(
                            slots, poles, layers, naa, 'BWP', symmetry)
                        self.assertEqual(base['status'], 'candidate')
                        for pattern in patterns:
                            with self.subTest(slots=slots, poles=poles,
                                              layers=layers, symmetry=symmetry,
                                              naa=naa, pattern=pattern):
                                plan = classify_fractional_branch_plan(
                                    slots, poles, layers, naa, pattern, symmetry)
                                if pattern == 'LPP' and base['position_divider'] != 1:
                                    self.assertEqual(plan['status'], 'rejected')
                                    self.assertIn('position division', plan['reason'])
                                    continue
                                self.assertEqual(plan['status'], 'candidate')
                                self.assertEqual(plan['pole_divider'] *
                                                 plan['position_divider'], naa)
                                if pattern in ('TSP', 'TLP'):
                                    self.assertIn(plan['pole_divider'], (1, 2))
                                covered = [region for group in plan['pole_groups']
                                           for region in group]
                                self.assertEqual(sorted(covered), list(range(poles)))
                                self.assertEqual(len(covered), len(set(covered)))
                                # Independent oracle: rebuild group categories with
                                # trigonometric phasors, not production angle keys.
                                records = phase_map(slots, poles, layers)
                                group_histograms = []
                                for group in plan['pole_groups']:
                                    histogram = Counter()
                                    for slot, layer, phase, sign in records:
                                        if poles * slot // slots not in group:
                                            continue
                                        if symmetry == 'strong':
                                            value = sign * cmath.exp(
                                                1j * math.pi * poles * slot / slots)
                                            key = (phase, layer, round(value.real, 9),
                                                   round(value.imag, 9))
                                        else:
                                            key = (phase, layer)
                                        histogram[key] += 1
                                    group_histograms.append(histogram)
                                self.assertTrue(all(
                                    histogram == group_histograms[0]
                                    for histogram in group_histograms[1:]))
                                self.assertTrue(all(
                                    count % plan['position_divider'] == 0
                                    for count in group_histograms[0].values()))
                                starts = plan['default_start_conductors']
                                self.assertEqual(len(starts), 3 * naa)
                                self.assertEqual(len({(s['slot'], s['layer'])
                                                      for s in starts}), 3 * naa)
                                for phase in range(3):
                                    phase_starts = [s for s in starts
                                                    if s['phase'] == phase]
                                    self.assertEqual([s['branch'] for s in phase_starts],
                                                     list(range(naa)))
                                    self.assertTrue(all(s['layer'] == 0
                                                        for s in phase_starts))
                                    for start in phase_starts:
                                        self.assertIn(start['pole_region'],
                                                      plan['pole_groups'][start['pole_group']])
                                for count in plan['category_counts'].values():
                                    self.assertEqual(count % naa, 0)
                                for key, count in plan['category_counts'].items():
                                    self.assertEqual(plan['category_quotas'][key] * naa,
                                                     count)

    def test_pattern_policy_labels_and_rejections(self):
        lpp = classify_fractional_branch_plan(30, 8, 6, 5, 'LPP', 'weak')
        self.assertEqual(lpp['status'], 'rejected')
        zlp = classify_fractional_branch_plan(30, 8, 6, 5, 'ZLP', 'weak')
        self.assertEqual((zlp['pole_divider'], zlp['position_divider']), (1, 5))
        tsp = classify_fractional_branch_plan(30, 8, 6, 10, 'TSP', 'weak')
        self.assertEqual((tsp['pole_divider'], tsp['position_divider']), (2, 5))
        self.assertEqual(tsp['division_mode'], 'half_cycle_and_position')
        self.assertEqual(classify_fractional_branch_plan(
            30, 8, 6, 1, 'UWP', 'weak')['division_mode'], 'uwp_single')
        self.assertEqual(classify_fractional_branch_plan(
            30, 8, 6, 2, 'UWP', 'weak')['division_mode'], 'uwp_dual')
        self.assertEqual(classify_fractional_branch_plan(
            30, 8, 6, 10, 'UWP', 'weak')['division_mode'],
            'uwp_half_cycle_position')
        rejected = classify_fractional_branch_plan(30, 8, 6, 3, 'BWP', 'strong')
        self.assertEqual(rejected['status'], 'rejected')
        self.assertIn('allowed', rejected['reason'])

    def test_fractional_plan_last_layer_shifts_and_validation(self):
        shifts = (value for value in (0, 1, 2, 3, 4, 5))
        plan = classify_fractional_branch_plan(
            30, 8, 6, 2, 'BWP', 'strong', shifts, 'last')
        self.assertTrue(all(start['layer'] == 5
                            for start in plan['default_start_conductors']))
        for pattern in ('bad', '', None):
            with self.assertRaises(ValueError):
                classify_fractional_branch_plan(30, 8, 6, 1, pattern, 'strong')
        for symmetry in ('other', None):
            with self.assertRaises(ValueError):
                classify_fractional_branch_plan(30, 8, 6, 1, 'BWP', symmetry)

    def test_legacy_integer_q_classifier_is_unchanged(self):
        from get_winding_pattern import classify_branch_mode
        self.assertEqual(classify_branch_mode(4, 2, 8, 'BWP')[:4],
                         ('q_and_pp', 2, 2, 1))
        self.assertEqual(classify_branch_mode(2, 2, 8, 'UWP')[:4],
                         ('p2_only', 1, 1, 2))
        self.assertEqual(classify_branch_mode(4, 2, 8, 'LPP')[:4],
                         ('pp_only', 1, 4, 1))

    def test_half_integer_uwp_2q_has_complete_phase_pure_wave_paths(self):
        from types import SimpleNamespace as NS
        from get_winding_pattern import get_winding_layout
        from explicit_connections import validate_branches

        for q, slots, naa in ((0.5, 12, 1), (1.5, 36, 3),
                              (2.5, 60, 5), (3.5, 84, 7),
                              (4.5, 108, 9), (10.5, 252, 21)):
            with self.subTest(q=q):
                winding = NS(q=q, num_slots=slots, num_poles=8,
                             num_phases=3, num_layers=6, ab=naa)
                layout = NS(phase_shift_list=[0]*6, radial_shift=0,
                            inlet_from_weld_side=0)
                transposition = NS(tp_type='Regular', tp_interval=0, tp_times=0,
                                   uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1)
                starts, branches = get_winding_layout('UWP', transposition,
                                                       winding, layout)
                self.assertEqual(len(starts), 3*naa)
                self.assertTrue(all(layer == 0 and slot < 6*q
                                    for slot, layer, _ in starts))
                paths = [branch[1] for branch in branches]
                self.assertEqual({len(path) for path in paths}, {24})
                records = phase_map(slots, 8, 6)
                report = validate_branches(paths, records, slots, 8, naa)
                self.assertTrue(report['topology_valid'], report['errors'])
                self.assertEqual(report['errors'],
                                 [] if naa == 1 else ['parallel_emf_mismatch'])
                lookup = {(slot, layer): (phase, sign)
                          for slot, layer, phase, sign in records}
                self.assertEqual([lookup[start[:2]][0] for start in starts],
                                 [phase for phase in range(3) for _ in range(naa)])
                for path in paths:
                    self.assertEqual(len({lookup[slot, layer][0]
                                          for slot, layer, _ in path}), 1)
                    self.assertTrue(all(abs((b[0]-a[0]) % slots) in
                                        (math.floor(3*q), math.ceil(3*q))
                                        for a, b in zip(path, path[1:])))

    def test_half_integer_uwp_2q_rejects_transposition_and_other_patterns(self):
        from types import SimpleNamespace as NS
        from get_winding_pattern import get_winding_layout

        winding = NS(q=1.5, num_slots=36, num_poles=8,
                     num_phases=3, num_layers=6, ab=3)
        layout = NS(phase_shift_list=[0]*6, radial_shift=0,
                    inlet_from_weld_side=0)
        transposition = NS(tp_type='Regular', tp_interval=0, tp_times=0,
                           uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1)
        for pattern in ('BWP', 'SSP'):
            with self.subTest(pattern=pattern), self.assertRaises(ValueError):
                get_winding_layout(pattern, transposition, winding, layout)
        transposition.tp_type = 'Interval'
        with self.assertRaisesRegex(ValueError, 'transposition'):
            get_winding_layout('UWP', transposition, winding, layout)
        transposition.tp_type = 'Regular'
        transposition.uni_tp = 1
        with self.assertRaisesRegex(ValueError, 'transposition'):
            get_winding_layout('UWP', transposition, winding, layout)
        transposition.uni_tp = 0
        transposition.tp_interval = 2  # Dormant after switching to Regular.
        get_winding_layout('UWP', transposition, winding, layout)
        transposition.jld = -1
        with self.assertRaisesRegex(ValueError, 'transposition'):
            get_winding_layout('UWP', transposition, winding, layout)

    def test_half_integer_uwp_pair_only_swap_rejects_untouched_emf(self):
        from types import SimpleNamespace as NS
        from get_winding_pattern import (get_winding_layout,
                                         assess_fractional_uwp_pair_swap)
        for q, poles, layers in ((1.5, 4, 4), (1.5, 8, 6),
                                 (2.5, 8, 6), (3.5, 8, 4)):
            with self.subTest(q=q, poles=poles, layers=layers):
                naa = int(2 * q)
                winding = NS(q=q, num_slots=int(3*q*poles),
                             num_poles=poles, num_phases=3,
                             num_layers=layers, ab=naa)
                layout = NS(phase_shift_list=[0]*layers, radial_shift=0,
                            inlet_from_weld_side=0)
                tp = NS(tp_type='Regular', tp_interval=0, tp_times=0,
                        uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1)
                starts, database = get_winding_layout('UWP', tp, winding, layout)
                assessment = assess_fractional_uwp_pair_swap(
                    starts, database, winding, layout)
                self.assertEqual(assessment['status'], 'rejected')
                self.assertEqual(assessment['reason_code'], 'untouched_emf')
                self.assertEqual(len(assessment['pair_indices']), 3)
                self.assertTrue(all(first // naa == second // naa == phase
                                    for phase, (first, second) in
                                    enumerate(assessment['pair_indices'])))
                if q == 1.5:
                    self.assertEqual(assessment['pair_indices'],
                                     [(0, 1), (4, 5), (6, 7)])

    def test_fractional_uwp_group_settings_generate_candidate_report(self):
        from types import SimpleNamespace as NS
        from get_winding_pattern import get_winding_layout, fractional_uwp_candidate_report

        winding = NS(q=1.5, num_slots=36, num_poles=8,
                     num_phases=3, num_layers=6, ab=3)
        layout = NS(phase_shift_list=[0]*6, radial_shift=0,
                    inlet_from_weld_side=0)
        north = dict(tp_type='Times', tp_times=1, tp_interval=0,
                     uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0)
        south = dict(tp_type='Regular', tp_times=0, tp_interval=0,
                     uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0)
        tp = NS(tp_type='Regular', tp_interval=0, tp_times=0,
                uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1,
                pole_group_tp={'PoleN': north, 'PoleS': south})
        starts, branches = get_winding_layout('UWP', tp, winding, layout)
        report = fractional_uwp_candidate_report(branches, winding, layout)
        self.assertIn('transposition', report)
        self.assertEqual(report['transposition']['groups']['PoleN']['tp_type'], 'Times')
        self.assertEqual(report['transposition']['groups']['PoleS']['tp_type'], 'Regular')
        self.assertEqual({row['group'] for row in report['transposition']['exchanges']},
                         {'PoleN'})
        signs = {(slot, layer): sign for slot, layer, _phase, sign in
                 phase_map(36, 8, 6, [0] * 6)}
        for exchange in report['transposition']['exchanges']:
            self.assertTrue(all(signs[starts[branch - 1][:2]] == 1
                                for branch in exchange['branches']))
        self.assertTrue(report['transposition']['edges'])
        self.assertTrue(report['transposition']['weld_connections_preserved'])
        self.assertTrue(all(edge['side'] == 'insert' and edge['edge'] % 2 == 0
                            for edge in report['transposition']['edges']))
        self.assertTrue(all(edge['side'] in ('insert', 'weld') and
                            3 <= edge['signed_pitch'] <= 6 and
                            abs(edge['signed_pitch'] - edge['base_pitch']) <= 1
                            for edge in report['transposition']['edges']))
        self.assertEqual(report['errors'], ['parallel_emf_mismatch'])
        self.assertEqual(len(starts), 9)

    def test_fractional_pole_groups_follow_each_phase_start_polarity(self):
        from types import SimpleNamespace as NS
        from get_winding_pattern import (get_winding_layout,
                                         _fractional_start_pole_groups,
                                         _fractional_swap_candidates)

        for q in (1.5, 2.5, 3.5):
            with self.subTest(q=q):
                naa = int(2 * q)
                slots = int(3 * q * 8)
                winding = NS(q=q, num_slots=slots, num_poles=8,
                             num_phases=3, num_layers=6, ab=naa)
                layout = NS(phase_shift_list=[0] * 6, radial_shift=0,
                            inlet_from_weld_side=0)
                tp = NS(tp_type='Regular', tp_interval=0, tp_times=0,
                        uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1,
                        pole_group_tp={})
                starts, database = get_winding_layout('UWP', tp, winding, layout)
                records = phase_map(slots, 8, 6, [0] * 6)
                signs = {(slot, layer): sign
                         for slot, layer, _phase, sign in records}
                paths = [branch[1][:] for branch in database]
                if q == 1.5:
                    self.assertEqual(
                        _fractional_start_pole_groups(paths, winding, records),
                        {'PoleN': {0: [0, 1], 1: [4, 5], 2: [6, 7]},
                         'PoleS': {0: [2], 1: [3], 2: [8]}})
                for phase in range(3):
                    phase_starts = starts[phase * naa:(phase + 1) * naa]
                    self.assertEqual(sum(signs[start[:2]] == 1
                                         for start in phase_starts), math.ceil(q))
                    self.assertEqual(sum(signs[start[:2]] == -1
                                         for start in phase_starts), math.floor(q))
                for group, expected_sign in (('PoleN', 1), ('PoleS', -1)):
                    candidates = _fractional_swap_candidates(
                        paths, winding, records, group, [0] * 6)
                    for first, second, _left, _right in candidates:
                        self.assertEqual(first // naa, second // naa)
                        self.assertEqual(signs[paths[first][0][:2]], expected_sign)
                        self.assertEqual(signs[paths[second][0][:2]], expected_sign)
                    if q == 1.5 and group == 'PoleS':
                        self.assertEqual(candidates, [])

    def test_fractional_interval_counts_insert_edges_and_preserves_weld_pairs(self):
        from types import SimpleNamespace as NS
        from get_winding_pattern import get_winding_layout

        winding = NS(q=1.5, num_slots=36, num_poles=8,
                     num_phases=3, num_layers=6, ab=3)
        layout = NS(phase_shift_list=[0]*6, radial_shift=0,
                    inlet_from_weld_side=0)
        base_tp = NS(tp_type='Regular', tp_interval=0, tp_times=0,
                     uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1)
        _starts, base = get_winding_layout('UWP', base_tp, winding, layout)
        grouped_tp = NS(**vars(base_tp), pole_group_tp={
            'PoleN': {'tp_type': 'Interval', 'tp_interval': 2}})
        _starts, grouped = get_winding_layout('UWP', grouped_tp, winding, layout)

        def weld_pairs(database):
            return Counter(tuple(tuple(conductor[:2]) for conductor in path[index:index+2])
                           for _branch, path in database
                           for index in range(0, len(path)-1, 2))

        self.assertEqual(weld_pairs(grouped), weld_pairs(base))
        exchanges = grouped.transposition_report['exchanges']
        self.assertEqual(Counter(row['insert_position'] for row in exchanges),
                         Counter({position: 3 for position in (2, 4, 6, 8, 10)}))
        self.assertEqual({(row['branches'][0] - 1) // 3 for row in exchanges},
                         {0, 1, 2})
        self.assertTrue(all(edge['side'] == 'insert'
                            for edge in grouped.transposition_report['edges']))

    def test_fractional_times_one_changes_only_one_insert_boundary_per_phase(self):
        from types import SimpleNamespace as NS
        from get_winding_pattern import get_winding_layout

        winding = NS(q=1.5, num_slots=36, num_poles=8,
                     num_phases=3, num_layers=6, ab=3)
        layout = NS(phase_shift_list=[0] * 6, radial_shift=0,
                    inlet_from_weld_side=0)
        tp = NS(tp_type='Regular', tp_interval=0, tp_times=0,
                uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1,
                pole_group_tp={})
        _starts, base = get_winding_layout('UWP', tp, winding, layout)
        tp.pole_group_tp = {'PoleN': {'tp_type': 'Times', 'tp_times': 1}}
        _starts, changed = get_winding_layout('UWP', tp, winding, layout)

        def physical_insert_edges(database):
            return Counter((tuple(path[edge][:2]), tuple(path[edge + 1][:2]))
                           for _branch, path in database
                           for edge in range(1, len(path) - 1, 2))

        new_edges = physical_insert_edges(changed) - physical_insert_edges(base)
        report = changed.transposition_report
        self.assertEqual(len(report['exchanges']), 3)
        self.assertEqual({item['insert_position'] for item in report['exchanges']}, {6})
        self.assertEqual(sum(new_edges.values()), 6)
        self.assertEqual(len(report['edges']), 6)
        self.assertEqual(Counter((tuple(edge['from']), tuple(edge['to']))
                                 for edge in report['edges']), new_edges)
        for first, second in ((0, 1), (4, 5), (6, 7)):
            self.assertEqual(changed[first][1][-1], base[second][1][-1])
            self.assertEqual(changed[second][1][-1], base[first][1][-1])

    def test_fractional_uniform_one_transposes_at_every_insert_boundary(self):
        from types import SimpleNamespace as NS
        from get_winding_pattern import get_winding_layout

        winding = NS(q=1.5, num_slots=36, num_poles=8,
                     num_phases=3, num_layers=6, ab=3)
        layout = NS(phase_shift_list=[0] * 6, radial_shift=0,
                    inlet_from_weld_side=0)
        tp = NS(tp_type='Regular', tp_interval=0, tp_times=0,
                uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1,
                pole_group_tp={})
        base_starts, base = get_winding_layout('UWP', tp, winding, layout)
        tp.pole_group_tp = {'PoleN': {'tp_type': 'Regular', 'uni_tp': 1}}
        changed_starts, changed = get_winding_layout('UWP', tp, winding, layout)

        positions = len(base[0][1]) // 2 - 1
        self.assertEqual(changed_starts, base_starts)
        self.assertEqual(Counter(item['insert_position'] for item in
                                 changed.transposition_report['exchanges']),
                         Counter({position: 3 for position in
                                  range(1, positions + 1)}))
        self.assertEqual(len(changed.transposition_report['edges']), 6 * positions)
        self.assertTrue(changed.transposition_report['weld_connections_preserved'])

    def test_fractional_uniform_rotates_all_group_branches(self):
        from types import SimpleNamespace as NS
        from get_winding_pattern import (get_winding_layout,
                                         _fractional_start_pole_groups)

        for q in (1.5, 2.5, 3.5):
            winding = NS(q=q, num_slots=int(24 * q), num_poles=8,
                         num_phases=3, num_layers=6, ab=int(2 * q))
            layout = NS(phase_shift_list=[0] * 6, radial_shift=0,
                        inlet_from_weld_side=0)
            tp = NS(tp_type='Regular', tp_interval=0, tp_times=0,
                    uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1,
                    pole_group_tp={})
            _starts, base = get_winding_layout('UWP', tp, winding, layout)
            base_paths = [branch[1] for branch in base]
            groups = _fractional_start_pole_groups(
                base_paths, winding,
                phase_map(winding.num_slots, 8, 6, [0] * 6))
            positions = len(base_paths[0]) // 2 - 1

            for group in ('PoleN', 'PoleS'):
                members = groups[group][0]
                if len(members) < 2:
                    continue
                with self.subTest(q=q, group=group):
                    tp.pole_group_tp = {group: {'tp_type': 'Regular',
                                                'uni_tp': 1}}
                    _starts, changed = get_winding_layout('UWP', tp, winding, layout)
                    changed_paths = [branch[1] for branch in changed]
                    for phase_members in groups[group].values():
                        count = len(phase_members)
                        for offset, branch in enumerate(phase_members):
                            for pair_index in range(positions + 1):
                                donor = phase_members[(offset + pair_index) % count]
                                cut = 2 * pair_index
                                self.assertEqual(changed_paths[branch][cut:cut + 2],
                                                 base_paths[donor][cut:cut + 2])
                    report = changed.transposition_report
                    self.assertEqual(len(report['exchanges']), 3 * positions)
                    self.assertEqual(len(report['edges']),
                                     3 * len(members) * positions)
                    self.assertTrue(all(len(event['branches']) == len(members)
                                        for event in report['exchanges']))
                    self.assertTrue(all(abs(edge['signed_pitch'] - edge['base_pitch'])
                                        <= len(members) - 1 for edge in report['edges']))
                    if len(members) > 2:
                        first_cycle = report['edges'][:len(members)]
                        self.assertEqual(
                            Counter(edge['signed_pitch'] - edge['base_pitch']
                                    for edge in first_cycle),
                            Counter({1: len(members) - 1,
                                     1 - len(members): 1}))

    def test_fractional_uniform_both_groups_preserve_all_physical_edges(self):
        from types import SimpleNamespace as NS
        from get_winding_pattern import get_winding_layout

        for q in (2.5, 3.5):
            with self.subTest(q=q):
                winding = NS(q=q, num_slots=int(24 * q), num_poles=8,
                             num_phases=3, num_layers=6, ab=int(2 * q))
                layout = NS(phase_shift_list=[0] * 6, radial_shift=0,
                            inlet_from_weld_side=0)
                tp = NS(tp_type='Regular', tp_interval=0, tp_times=0,
                        uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1,
                        pole_group_tp={})
                _starts, base = get_winding_layout('UWP', tp, winding, layout)
                tp.pole_group_tp = {
                    'PoleN': {'tp_type': 'Regular', 'uni_tp': 1},
                    'PoleS': {'tp_type': 'Regular', 'uni_tp': 1},
                }
                _starts, changed = get_winding_layout('UWP', tp, winding, layout)

                def physical_edges(database, start):
                    return Counter((tuple(path[index][:2]),
                                    tuple(path[index + 1][:2]))
                                   for _branch, path in database
                                   for index in range(start, len(path) - 1, 2))

                self.assertEqual(physical_edges(changed, 0),
                                 physical_edges(base, 0))
                added = physical_edges(changed, 1) - physical_edges(base, 1)
                reported = Counter((tuple(edge['from']), tuple(edge['to']))
                                   for edge in changed.transposition_report['edges'])
                self.assertEqual(added, reported)
                self.assertEqual(len(changed.transposition_report['exchanges']),
                                 6 * (len(base[0][1]) // 2 - 1))

    def test_fractional_uniform_rejects_invalid_value_or_combination(self):
        from types import SimpleNamespace as NS
        from get_winding_pattern import get_winding_layout

        winding = NS(q=1.5, num_slots=36, num_poles=8,
                     num_phases=3, num_layers=6, ab=3)
        layout = NS(phase_shift_list=[0] * 6, radial_shift=0,
                    inlet_from_weld_side=0)
        for setting, error in (({'uni_tp': 2}, 'accepts only 0 or 1'),
                               ({'uni_tp': 1, 'pltp_fl': 1},
                                'cannot be combined')):
            with self.subTest(setting=setting):
                tp = NS(tp_type='Regular', tp_interval=0, tp_times=0,
                        uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1,
                        pole_group_tp={'PoleN': {'tp_type': 'Regular',
                                                 **setting}})
                with self.assertRaisesRegex(ValueError, error):
                    get_winding_layout('UWP', tp, winding, layout)

    def test_fractional_uniform_rejects_layout_without_insert_cuts(self):
        from types import SimpleNamespace as NS
        from get_winding_pattern import get_winding_layout

        winding = NS(q=1.5, num_slots=9, num_poles=2,
                     num_phases=3, num_layers=2, ab=3)
        layout = NS(phase_shift_list=[0, 0], radial_shift=0,
                    inlet_from_weld_side=0)
        tp = NS(tp_type='Regular', tp_interval=0, tp_times=0,
                uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1,
                pole_group_tp={'PoleN': {'tp_type': 'Regular', 'uni_tp': 1}})
        with self.assertRaisesRegex(ValueError, 'no insertion-side positions'):
            get_winding_layout('UWP', tp, winding, layout)

    def test_fractional_report_omits_inactive_regular_values(self):
        from types import SimpleNamespace as NS
        from get_winding_pattern import get_winding_layout

        winding = NS(q=1.5, num_slots=36, num_poles=8,
                     num_phases=3, num_layers=6, ab=3)
        layout = NS(phase_shift_list=[0] * 6, radial_shift=0,
                    inlet_from_weld_side=0)
        tp = NS(tp_type='Regular', tp_interval=0, tp_times=0,
                uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1,
                pole_group_tp={'PoleN': {'tp_type': 'Times', 'tp_times': 1,
                                         'uni_tp': 1}})
        _starts, stale = get_winding_layout('UWP', tp, winding, layout)
        tp.pole_group_tp['PoleN']['uni_tp'] = 0
        _starts, clean = get_winding_layout('UWP', tp, winding, layout)

        self.assertEqual(stale, clean)
        self.assertEqual(stale.transposition_report['exchanges'],
                         clean.transposition_report['exchanges'])
        self.assertEqual(stale.transposition_report['groups']['PoleN']['uni_tp'], 0)

    def test_fractional_group_tp_rejects_missing_positions(self):
        from types import SimpleNamespace as NS
        from get_winding_pattern import get_winding_layout

        winding = NS(q=0.5, num_slots=12, num_poles=8,
                     num_phases=3, num_layers=6, ab=1)
        layout = NS(phase_shift_list=[0]*6, radial_shift=0,
                    inlet_from_weld_side=0)
        tp = NS(tp_type='Regular', tp_interval=0, tp_times=0,
                uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1,
                pole_group_tp={'PoleN': {'tp_type': 'Times', 'tp_times': 1}})
        with self.assertRaisesRegex(ValueError, 'fewer than two branches'):
            get_winding_layout('UWP', tp, winding, layout)

    def test_fractional_single_branch_pole_s_rejects_transposition(self):
        from types import SimpleNamespace as NS
        from get_winding_pattern import get_winding_layout

        winding = NS(q=1.5, num_slots=36, num_poles=8,
                     num_phases=3, num_layers=6, ab=3)
        layout = NS(phase_shift_list=[0] * 6, radial_shift=0,
                    inlet_from_weld_side=0)
        for setting in ({'tp_type': 'Times', 'tp_times': 1},
                        {'tp_type': 'Interval', 'tp_interval': 1},
                        {'tp_type': 'Optimize'},
                        {'tp_type': 'Regular', 'uni_tp': 1}):
            with self.subTest(setting=setting):
                tp = NS(tp_type='Regular', tp_interval=0, tp_times=0,
                        uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1,
                        pole_group_tp={'PoleS': setting})
                with self.assertRaisesRegex(ValueError,
                                            'PoleS.*fewer than two branches'):
                    get_winding_layout('UWP', tp, winding, layout)

    def test_fractional_group_reverse_jump_rejects_without_legal_edge(self):
        from types import SimpleNamespace as NS
        from get_winding_pattern import get_winding_layout

        winding = NS(q=1.5, num_slots=36, num_poles=8,
                     num_phases=3, num_layers=6, ab=3)
        layout = NS(phase_shift_list=[0]*6, radial_shift=0,
                    inlet_from_weld_side=0)
        tp = NS(tp_type='Regular', tp_interval=0, tp_times=0,
                uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1,
                pole_group_tp={'PoleN': {'tp_type': 'Regular', 'jltp': -1}})
        with self.assertRaisesRegex(ValueError, 'no eligible jltp position'):
            get_winding_layout('UWP', tp, winding, layout)

    def test_fractional_group_tp_optimize_is_bounded_and_keeps_candidate(self):
        from types import SimpleNamespace as NS
        from get_winding_pattern import get_winding_layout, fractional_uwp_candidate_report

        for q in (1.5, 2.5):
            with self.subTest(q=q):
                winding = NS(q=q, num_slots=int(q*24), num_poles=8,
                             num_phases=3, num_layers=6, ab=int(2*q))
                layout = NS(phase_shift_list=[0]*6, radial_shift=0,
                            inlet_from_weld_side=0)
                tp = NS(tp_type='Regular', tp_interval=0, tp_times=0,
                        uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1,
                        pole_group_tp={'PoleN': {'tp_type': 'Optimize'}})
                starts, branches = get_winding_layout('UWP', tp, winding, layout)
                report = fractional_uwp_candidate_report(branches, winding, layout)
                self.assertEqual(len(starts), 3*winding.ab)
                self.assertEqual(len(report['transposition']['exchanges']), 1)
                self.assertLessEqual(report['transposition']['search']['PoleN']['checked'], 200)
                self.assertTrue(report['topology_valid'])
                self.assertEqual(report['errors'], ['parallel_emf_mismatch'])

    def test_fractional_group_preserves_start_polarity_with_layer_shift(self):
        from types import SimpleNamespace as NS
        from get_winding_pattern import get_winding_layout

        winding = NS(q=1.5, num_slots=36, num_poles=8,
                     num_phases=3, num_layers=6, ab=3)
        layout = NS(phase_shift_list=[0, 1, 0, 1, 0, 1], radial_shift=0,
                    inlet_from_weld_side=0)
        tp = NS(tp_type='Regular', tp_interval=0, tp_times=0,
                uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1,
                pole_group_tp={'PoleN': {'tp_type': 'Times', 'tp_times': 1}})
        _starts, branches = get_winding_layout('UWP', tp, winding, layout)
        exchange = branches.transposition_report['exchanges'][0]
        self.assertEqual(exchange['group'], 'PoleN')
        signs = {(slot, layer): sign for slot, layer, _phase, sign in
                 phase_map(36, 8, 6, layout.phase_shift_list)}
        self.assertTrue(all(signs[branches[branch - 1][1][0][:2]] == 1
                            for branch in exchange['branches']))


if __name__ == '__main__':
    unittest.main()
