"""Public TLP cohort joins checked against reviewed paths and analytic EMF."""

from collections import Counter
from copy import deepcopy
import cmath
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch

import get_winding_pattern as gw
from divider_connection_formulas import DividerConnectionFormula
from pattern_identity import analyze_ordered_pattern
from refresh_pattern_naa_division_layout import _inputs


REVIEWED_DRAFT = (Path(__file__).parent / 'pattern_rule_drafts' /
    'TLP_q-4_pp-2_L-4_Naa-2_Q-2_PP-1_P2-1_Ph-A_Side-weld_Shifts-0-0-0-0_20261002-reviewed.json')
# Frozen pre-promotion owner-review snapshot. Its notes and local image/handoff
# references describe that review; exact paths are the oracle, never certification.


class TlpProperQRouteTests(unittest.TestCase):
    def assert_neutral_formula(self, database, winding, Q):
        """Use integer belts and phasor sums independently of phase_map."""
        q, m, L = winding.q, winding.num_phases, winding.num_layers
        pp, S = winding.num_poles // 2, winding.num_slots
        g, width, tau = 2 * q // Q, pp * L, m * q
        positions = [tuple(node[:2]) for _, path in database for node in path]
        self.assertEqual(set(positions), {(s, l) for s in range(S) for l in range(L)})
        self.assertEqual(len(positions), len(set(positions)))
        phase_counts, cohort_counts = Counter(), Counter()
        cohort_lanes = {}
        for _, path in database:
            self.assertEqual(len(path), g * width)
            phase = (path[0][0] // q) % m
            phase_counts[phase] += 1
            start_layer = path[0][1]
            cohort_counts[phase, start_layer] += 1
            lanes = []
            for offset in range(0, len(path), width):
                parent = path[offset:offset + width]
                lane = parent[0][2]; lanes.append(lane)
                self.assertEqual({node[2] for node in parent}, {lane})
                self.assertEqual(parent[0][1], start_layer)
                self.assertEqual((-1) ** (parent[0][0] // q), 1)
                self.assertEqual((-1) ** (parent[-1][0] // q), -1)
            self.assertEqual(lanes, list(range(lanes[0], lanes[0] + g)))
            cohort_lanes.setdefault((phase, start_layer), []).extend(lanes)
            for index, (start, end) in enumerate(zip(path, path[1:])):
                self.assertEqual((start[0] // q) % m, phase)
                self.assertEqual((end[0] // q) % m, phase)
                self.assertEqual((-1) ** (start[0] // q), -(-1) ** (end[0] // q))
                delta = (end[0] - start[0]) % S
                delta = delta if 2 * delta < S else delta - S
                self.assertLessEqual(abs((start[0] + delta) // tau - start[0] // tau), 1)
                if (index + 1) % width == 0:
                    self.assertEqual(index % 2, 1)
                    self.assertEqual(abs(end[1] - start[1]), L - 1)
                    self.assertIn(abs(delta), (tau - 1, tau + 1))
                elif (index + 1) % L == 0:
                    self.assertEqual(abs(end[1] - start[1]), L - 1)
                else:
                    self.assertEqual(end[1] - start[1], 1 if start_layer == 0 else -1)
            actual = sum((-1) ** (slot // q) * cmath.exp(1j * math.pi * slot / tau)
                         for slot, *_ in path)
            expected = pp * L * cmath.exp(1j * math.pi * phase * (1 + 1 / m)) * sum(
                cmath.exp(1j * math.pi * lane / tau) for lane in lanes)
            self.assertLess(abs(actual - expected), 1e-8)
            magnitude = pp * L * math.sin(math.pi / (m * Q)) / math.sin(math.pi / (2 * m * q))
            self.assertAlmostEqual(abs(actual), magnitude, places=8)
        self.assertEqual(phase_counts, Counter({phase: Q for phase in range(m)}))
        self.assertEqual(cohort_counts, Counter({(phase, layer): Q // 2
                                               for phase in range(m) for layer in (0, L - 1)}))
        for lanes in cohort_lanes.values():
            self.assertEqual(sorted(lanes), list(range(q)))
        report = database.layout_report
        self.assertTrue(report['layout_retained'])
        self.assertEqual(report['pattern_identity']['status'], 'valid')
        self.assertFalse(set(report['errors']) - gw.EMF_ASYMMETRY_ERRORS)
        self.assertEqual(report['electrically_valid'], Q == 2)
        if Q > 2:
            self.assertIn('parallel_emf_mismatch', report['errors'])

    def test_public_paths_match_owner_reviewed_manual_draft(self):
        saved = json.loads(REVIEWED_DRAFT.read_text(encoding='utf-8'))
        winding, tp, layout = _inputs('TLP', 4, 2, 4, 3, (2, 1, 1))
        decision = gw.resolve_pattern_route('TLP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.admission, 'supported')
        self.assertEqual(decision.rule_id, 'tlp_q_only_pair_join')
        _, database = gw.get_winding_layout('TLP', tp, winding, layout)
        expected = [[(item['slot'] - 1, item['layer'] - 1) for item in branch['path']]
                    for branch in saved['branches']]
        self.assertEqual([[tuple(node[:2]) for node in path] for _, path in database[:2]], expected)
        self.assertFalse(saved['certified'])
        self.assertFalse(saved['completion_checks']['engineering_validated'])
        self.assert_neutral_formula(database, winding, 2)

    def test_public_proper_q_matrix_matches_independent_formula(self):
        pairs = [(q, Q) for q in (4, 6, 8, 10, 12)
                 for Q in range(2, q, 2) if q % Q == 0]
        for q, Q in pairs:
            for pp, L, m in ((2, 2, 3), (3, 4, 3), (4, 6, 5), (6, 8, 7)):
                with self.subTest(q=q, Q=Q, pp=pp, layers=L, phases=m):
                    winding, tp, layout = _inputs('TLP', q, pp, L, m, (Q, 1, 1))
                    _, database = gw.get_winding_layout('TLP', tp, winding, layout)
                    self.assert_neutral_formula(database, winding, Q)

    def test_formula_extends_beyond_review_examples_without_tuple_rules(self):
        for q, Q, pp, L, m in ((14, 2, 5, 4, 3), (16, 8, 3, 6, 5)):
            with self.subTest(q=q, Q=Q):
                winding, tp, layout = _inputs('TLP', q, pp, L, m, (Q, 1, 1))
                _, database = gw.get_winding_layout('TLP', tp, winding, layout)
                self.assert_neutral_formula(database, winding, Q)

    def test_existing_join_formula_uses_actual_full_q_source_count(self):
        parents = [(index, [(index, 0, index)]) for index in range(8)]
        joined = DividerConnectionFormula('join', (4, 1, 2), (2, 1, 1)).apply(parents)
        self.assertEqual([branch.source_ids for branch in joined], [(0, 1, 2, 3), (4, 5, 6, 7)])

    def test_later_seams_and_mixed_cohorts_are_rejected(self):
        winding, tp, layout = _inputs('TLP', 8, 2, 4, 3, (2, 1, 1))
        _, database = gw.get_winding_layout('TLP', tp, winding, layout)
        width = 2 * 4
        reordered = deepcopy(database)
        path = reordered[0][1]
        path[-2 * width:] = path[-width:] + path[-2 * width:-width]
        with self.assertRaisesRegex(ValueError, 'tau plus or minus one'):
            gw.validate_tlp_q_only_pair_join(reordered, winding, layout)
        mixed = deepcopy(database)
        first, second = mixed[0][1], mixed[1][1]
        first[-width:], second[-width:] = second[-width:], first[-width:]
        with self.assertRaisesRegex(ValueError, 'source cohorts'):
            gw.validate_tlp_q_only_pair_join(mixed, winding, layout)

    def test_two_layers_keep_structural_overlap_qualification(self):
        winding, tp, layout = _inputs('TLP', 8, 2, 2, 3, (4, 1, 1))
        _, database = gw.get_winding_layout('TLP', tp, winding, layout)
        identity = analyze_ordered_pattern('TLP', database, winding, layout)
        self.assertEqual(identity['ordered_status'], 'valid')
        self.assertIn('degenerate-two-layer', identity['degeneracy'])

    def test_nonzero_post_connection_shifts_keep_route_and_occupancy(self):
        winding, tp, layout = _inputs('TLP', 4, 2, 4, 3, (2, 1, 1))
        layout.phase_shift_list = [0, 1, 0, 1]
        layout.radial_shift = 1
        decision = gw.resolve_pattern_route('TLP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.admission, 'supported')
        _, database = gw.get_winding_layout('TLP', tp, winding, layout)
        report = database.layout_report
        self.assertTrue(report['layout_retained'])
        self.assertFalse(set(report['errors']) - gw.EMF_ASYMMETRY_ERRORS)
        positions = [tuple(node[:2]) for _, path in database for node in path]
        self.assertEqual(len(positions), len(set(positions)))
        self.assertEqual(len(positions), winding.num_slots * winding.num_layers)

    def test_odd_nondivisor_short_source_and_phase_arrays_stay_closed(self):
        cases = ((6, 3, 2, 4, 3), (8, 6, 2, 4, 3), (4, 2, 1, 4, 3),
                 (4, 2, 2, 8, 6), (4, 2, 2, 12, 9))
        for q, Q, pp, L, m in cases:
            with self.subTest(q=q, Q=Q, pp=pp, layers=L, phases=m):
                winding, tp, layout = _inputs('TLP', q, pp, L, m, (Q, 1, 1))
                self.assertFalse(gw.supports_integer_tlp_q_only_pair_join(winding, (Q, 1, 1)))
                decision = gw.resolve_pattern_route('TLP', winding, winding.branch_dividers, tp, layout)
                self.assertNotEqual(decision.admission, 'supported')
                with self.assertRaises(ValueError):
                    gw.get_winding_layout('TLP', tp, winding, layout)

    @patch('pattern_rule_workbench.PATTERNS', ('TLP', 'ZPP'))
    def test_workbench_consumes_public_route_results_and_zpp_exclusion(self):
        from pattern_rule_workbench import build_divider_route_catalog

        for q, pp, Q, expected in ((4, 2, 2, 'Validated'),
                                   (8, 3, 4, 'not strong symmetry layout')):
            with self.subTest(q=q, Q=Q):
                records = build_divider_route_catalog(str(q), pp, 4)
                route = next(record for record in records
                             if record.pattern == 'TLP' and record.dividers == (Q, 1, 1))
                self.assertEqual(route.status, expected)
        records = build_divider_route_catalog('4', 4, 4)
        excluded = next(record for record in records
                        if record.pattern == 'ZPP' and record.dividers == (2, 1, 2))
        self.assertEqual(excluded.status, 'rejected')
        self.assertEqual(excluded.reason, 'q and p2 share same route')


if __name__ == '__main__':
    unittest.main()
