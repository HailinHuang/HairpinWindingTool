"""Public TLP cohort joins checked against reviewed paths and analytic EMF."""

from collections import Counter
from copy import deepcopy
from fractions import Fraction
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


class RationalSlpHalfBeltTranslationTests(unittest.TestCase):
    @staticmethod
    def inputs(q=Fraction(4, 3), m=5, poles=6, layers=4, factors=None):
        winding, tp, layout = _inputs(
            'SLP', q, poles // 2, layers, m,
            factors if factors is not None else (q, poles // 2, 2))
        layout.inlet_from_weld_side = 1
        return winding, tp, layout

    def test_public_parameter_family_preserves_actual_connection_sides(self):
        from explicit_connections import compile_edges
        for a, b, m, P in ((4, 3, 5, 6), (4, 3, 5, 12), (6, 5, 3, 10),
                           (6, 5, 13, 10), (8, 5, 3, 10), (8, 3, 5, 6),
                           (8, 7, 11, 14), (10, 7, 11, 28), (14, 3, 5, 6),
                           (16, 15, 23, 30)):
            with self.subTest(a=a, b=b, phases=m, poles=P):
                q = Fraction(a, b)
                winding, tp, layout = self.inputs(q, m, P)
                decision = gw.resolve_pattern_route('SLP', winding, configuration=tp, layout=layout)
                self.assertEqual(decision.admission, 'supported')
                self.assertEqual(decision.route_name, 'slp_rational_half_belt_translation')
                self.assertEqual(decision.required_inlet, 'weld')
                _, database = gw.get_winding_layout('SLP', tp, winding, layout)
                S, tau, H = winding.num_slots, m*q, int(q*Fraction(2*m-1, 2))
                positions = [tuple(n[:2]) for _, path in database for n in path]
                self.assertEqual(len(positions), 4*S)
                self.assertEqual(set(positions), {(s, l) for s in range(S) for l in range(4)})
                phases, returns = Counter(), 0
                for _, path in database:
                    self.assertEqual(len(path), 4)
                    phase, emf = None, 0j
                    for i, (s, l, *_rest) in enumerate(path):
                        n = (s+math.ceil(tau)*(l % 2)) // q
                        phase = int(n % m) if phase is None else phase
                        self.assertEqual(int(n % m), phase)
                        sign = (-1)**int(n+l % 2)
                        self.assertEqual(sign, (-1)**i)
                        emf += sign*cmath.exp(1j*math.pi*s/float(tau))
                    phases[phase] += 1
                    self.assertAlmostEqual(abs(emf), 4*math.cos(math.pi/(4*m)), places=9)
                    steps = []
                    for left, right in zip(path, path[1:]):
                        ds = (right[0]-left[0]) % S
                        steps.append(ds if 2*ds < S else ds-S)
                    edges = compile_edges(path, S, [0]*4, steps, first_side='insert')
                    self.assertEqual([e.side for e in edges], ['insert', 'weld', 'insert'])
                    for e in edges:
                        self.assertEqual(abs(e.signed_pitch), H)
                        self.assertLessEqual(abs((e.start[0]+e.signed_pitch)//tau-e.start[0]//tau), 1)
                        dl = e.end[1]-e.start[1]
                        if e.side == 'weld':
                            self.assertEqual(abs(dl), 1)
                            self.assertEqual(e.signed_pitch*dl, H if min(e.start[1], e.end[1]) == 2 else -H)
                        elif dl == 0:
                            self.assertIn(e.start[1], (0, 3))
                            returns += 1
                self.assertGreater(returns, 0)
                self.assertEqual(phases, Counter({p: int(q*P) for p in range(m)}))
                report = database.layout_report
                self.assertTrue(report['layout_retained'])
                self.assertEqual(report['pattern_identity']['status'], 'valid')
                self.assertEqual(report['layout_status'], 'not strong symmetry layout')
                self.assertFalse(set(report['errors']) - gw.EMF_ASYMMETRY_ERRORS)

    def test_unproved_layers_geometry_and_dividers_remain_unsupported(self):
        for q, m, P, L, factors in ((Fraction(4, 3), 5, 6, 6, None),
                                    (Fraction(5, 3), 5, 6, 4, None),
                                    (Fraction(6, 5), 7, 10, 4, None),
                                    (Fraction(4, 3), 5, 6, 4, (Fraction(4, 3), 3, 1))):
            with self.subTest(q=q, phases=m, layers=L, factors=factors):
                winding, tp, layout = self.inputs(q, m, P, L, factors)
                self.assertEqual(gw.resolve_pattern_route(
                    'SLP', winding, configuration=tp, layout=layout).admission, 'unsupported-yet')
                with self.assertRaises(ValueError):
                    gw.get_winding_layout('SLP', tp, winding, layout)

    def test_wrong_inlet_cannot_move_same_layer_returns_to_weld_side(self):
        winding, tp, layout = self.inputs()
        layout.inlet_from_weld_side = 0
        decision = gw.resolve_pattern_route('SLP', winding, configuration=tp, layout=layout)
        self.assertEqual(decision.rule_id, 'invalid_configuration')
        with self.assertRaises(ValueError):
            gw.get_winding_layout('SLP', tp, winding, layout)

    def test_same_layer_weld_corruption_is_rejected_despite_unique_coverage(self):
        winding, tp, layout = self.inputs()
        original = gw._slp_rational_half_belt_translation_from_formula

        def corrupt(*args):
            starts, database = original(*args)
            first = next(p for _, p in database if p[0][:2] == (0, 2))
            second = next(p for _, p in database if p[0][:2] == (0, 1))
            first[2], second[0] = second[0], first[2]
            self.assertEqual(first[1][1], first[2][1])
            self.assertEqual(len({n[:2] for _, p in database for n in p}), 160)
            return [p[0] for _, p in database], database

        with patch.object(gw, '_slp_rational_half_belt_translation_from_formula', side_effect=corrupt):
            with self.assertRaisesRegex(ValueError, 'SLP boundary return|weld.*adjacent'):
                gw.get_winding_layout('SLP', tp, winding, layout)

    def test_phase_only_shifts_preserve_certified_identity(self):
        winding, tp, layout = self.inputs()
        layout.phase_shift_list = [0, 1, 0, 1]
        _, database = gw.get_winding_layout('SLP', tp, winding, layout)
        self.assertEqual(len({n[:2] for _, p in database for n in p}), 160)
        self.assertTrue(all(abs(p[i+1][1]-p[i][1]) == 1
                            for _, p in database for i in range(1, len(p)-1, 2)))
        self.assertTrue(database.layout_report['layout_retained'])
        self.assertEqual(database.layout_report['pattern_identity']['status'], 'valid')
        self.assertEqual(database.layout_report['post_connection_shift']['connection_validation'], 'before shift')

    @patch('pattern_rule_workbench.PATTERNS', ('SLP',))
    def test_workbench_uses_public_paths_with_only_adjacent_welds(self):
        from pattern_rule_workbench import build_divider_route_catalog, generate_route_drafts
        record = next(r for r in build_divider_route_catalog('4/3', 3, 4, phases=5)
                      if r.dividers == (Fraction(4, 3), 3, 2))
        self.assertEqual(record.status, 'Validated')
        self.assertIn('not strong symmetry layout', record.reason)
        drafts = generate_route_drafts(record)
        self.assertEqual(len(drafts), 8)
        for draft in drafts:
            self.assertEqual(draft.first_side, 'insert')
            self.assertTrue(all(abs(s.end[1]-s.start[1]) == 1 for s in draft.steps if s.side == 'weld'))


class RationalTlpHalfBeltTranslationTests(unittest.TestCase):
    """Independent canonical belts, coverage, travel and phasor expectations."""

    @staticmethod
    def inputs(q, m=5, poles=6, layers=4, factors=None):
        winding, tp, layout = _inputs(
            'TLP', q, poles // 2, layers, m,
            factors if factors is not None else (q, poles // 2, 2))
        layout.inlet_from_weld_side = 1
        return winding, tp, layout

    def test_public_formula_family_has_complete_uniform_welds(self):
        cases = ((4, 3, 5, 6, 4), (4, 3, 5, 12, 8),
                 (6, 5, 3, 10, 4), (6, 5, 13, 10, 6),
                 (8, 5, 3, 10, 8), (8, 3, 5, 6, 6),
                 (8, 7, 11, 14, 4), (10, 7, 11, 28, 6),
                 (14, 3, 5, 6, 4))
        for a, b, m, P, L in cases:
            with self.subTest(a=a, b=b, phases=m, poles=P, layers=L):
                q = Fraction(a, b)
                winding, tp, layout = self.inputs(q, m, P, L)
                decision = gw.resolve_pattern_route(
                    'TLP', winding, winding.branch_dividers, tp, layout)
                self.assertEqual(decision.admission, 'supported')
                self.assertEqual(decision.route_name, 'tlp_rational_half_belt_translation')
                self.assertEqual(decision.required_inlet, 'weld')
                _, database = gw.get_winding_layout('TLP', tp, winding, layout)
                S, tau = winding.num_slots, m * q
                H, c = int(q * Fraction(2 * m - 1, 2)), math.ceil(tau)
                positions = [tuple(node[:2]) for _, path in database for node in path]
                self.assertEqual(len(positions), S * L)
                self.assertEqual(len(set(positions)), S * L)
                self.assertEqual(set(positions), {(s, l) for s in range(S) for l in range(L)})
                phase_counts = Counter()
                for _, path in database:
                    self.assertEqual(len(path), L)
                    self.assertEqual({node[1] for node in path}, set(range(L)))
                    phase, emf = None, 0j
                    for index, (slot, layer, *_rest) in enumerate(path):
                        belt = (slot + c * (layer % 2)) // q
                        node_phase = int(belt % m)
                        sign = (-1) ** int(belt + layer % 2)
                        phase = node_phase if phase is None else phase
                        self.assertEqual(node_phase, phase)
                        self.assertEqual(sign, (-1) ** index)
                        emf += sign * cmath.exp(1j * math.pi * slot / float(tau))
                    phase_counts[phase] += 1
                    self.assertAlmostEqual(abs(emf), L * math.cos(math.pi / (4 * m)), places=9)
                    for index, (left, right) in enumerate(zip(path, path[1:])):
                        ds = (right[0] - left[0]) % S
                        ds = ds if 2 * ds < S else ds - S
                        self.assertEqual(abs(ds), H)
                        self.assertLessEqual(abs((left[0] + ds) // tau - left[0] // tau), 1)
                        if index % 2:
                            self.assertEqual(abs(right[1] - left[1]), 1)
                            self.assertLess(ds * (right[1] - left[1]), 0)
                self.assertEqual(phase_counts, Counter({phase: int(q * P) for phase in range(m)}))
                report = database.layout_report
                self.assertTrue(report['layout_retained'])
                self.assertEqual(report['pattern_identity']['status'], 'valid')
                self.assertFalse(set(report['errors']) - gw.EMF_ASYMMETRY_ERRORS)
                self.assertEqual(report['layout_status'], 'not strong symmetry layout')

    def test_outside_formula_domain_remains_unsupported(self):
        for q, m, P, L in ((Fraction(5, 3), 5, 6, 4),
                           (Fraction(6, 5), 7, 10, 4),
                           (Fraction(2, 3), 5, 6, 4),
                           (Fraction(4, 3), 5, 6, 2)):
            with self.subTest(q=q, phases=m, layers=L):
                winding, tp, layout = self.inputs(q, m, P, L)
                decision = gw.resolve_pattern_route('TLP', winding, configuration=tp, layout=layout)
                self.assertEqual(decision.admission, 'unsupported-yet')
                with self.assertRaises(ValueError):
                    gw.get_winding_layout('TLP', tp, winding, layout)

    def test_fractional_divider_products_are_not_truncated(self):
        winding, tp, layout = self.inputs(Fraction(4, 3), factors=(Fraction(4, 3), 1, 2))
        decision = gw.resolve_pattern_route('TLP', winding, configuration=tp, layout=layout)
        self.assertEqual(decision.admission, 'rejected')
        self.assertEqual(decision.rule_id, 'divider_product_mismatch')

    def test_max_split_does_not_inherit_integer_tlp_factor_exclusion(self):
        q = Fraction(4, 3)
        self.assertFalse(gw.pattern_rejects_divider_tuple('TLP', (q, 3, 2), q, 3))
        self.assertTrue(gw.pattern_rejects_divider_tuple('TLP', (4, 3, 2), 4, 3))

    def test_fixed_formula_rejects_changed_configuration(self):
        for field, value in (('inlet', 0), ('uni_tp', 1), ('adjustment', 1)):
            with self.subTest(field=field):
                winding, tp, layout = self.inputs(Fraction(4, 3))
                if field == 'inlet':
                    layout.inlet_from_weld_side = value
                elif field == 'adjustment':
                    layout.inlet_index_adjustments_phase_a = [value]
                else:
                    setattr(tp, field, value)
                decision = gw.resolve_pattern_route('TLP', winding, configuration=tp, layout=layout)
                self.assertEqual(decision.admission, 'rejected')
                self.assertEqual(decision.rule_id, 'invalid_configuration')
                with self.assertRaises(ValueError):
                    gw.get_winding_layout('TLP', tp, winding, layout)

    def test_phase_only_shifts_preserve_established_identity_contract(self):
        winding, tp, layout = self.inputs(Fraction(4, 3))
        layout.phase_shift_list = [0, 1, 0, 1]
        decision = gw.resolve_pattern_route('TLP', winding, configuration=tp, layout=layout)
        self.assertEqual(decision.admission, 'supported')
        _, database = gw.get_winding_layout('TLP', tp, winding, layout)
        positions = [tuple(node[:2]) for _, path in database for node in path]
        self.assertEqual(len(set(positions)), winding.num_slots * winding.num_layers)
        self.assertTrue(all(abs(p[i+1][1]-p[i][1]) == 1
                            for _, p in database for i in range(1, len(p)-1, 2)))
        self.assertTrue(database.layout_report['layout_retained'])
        self.assertEqual(database.layout_report['pattern_identity']['status'], 'valid')
        self.assertEqual(database.layout_report['post_connection_shift']['connection_validation'], 'before shift')

    def test_public_generation_rejects_changed_weld_pitch(self):
        winding, tp, layout = self.inputs(Fraction(4, 3))
        original = gw._tlp_rational_half_belt_translation_from_formula

        def corrupt(*args):
            starts, database = original(*args)
            # Swap complete odd-layer lanes in two phase-A branches. Coverage,
            # phase and alternating polarity survive; their pitch becomes 7.
            first, second = database[0][1], database[1][1]
            odd_slots = [next(node[0] for node in path if node[1] % 2) for path in (first, second)]
            for path, target in zip((first, second), reversed(odd_slots)):
                path[:] = [(target if layer % 2 else slot, layer, lane)
                           for slot, layer, lane in path]
            first.sort(key=lambda node: node[1])
            second[:] = sorted(second, key=lambda node: (node[1] != 0, -node[1]))
            # Orient the new lap walks so the existing uniform-direction rule
            # also passes. Only the required common pitch is now violated.
            gw.validate_tlp_welds(database, winding, layout)
            return [path[0] for _, path in database], database

        with patch.object(gw, '_tlp_rational_half_belt_translation_from_formula', side_effect=corrupt):
            with self.assertRaisesRegex(ValueError, 'weld pitch'):
                gw.get_winding_layout('TLP', tp, winding, layout)

    def test_public_generation_rejects_phase_swap_with_legal_welds(self):
        winding, tp, layout = self.inputs(Fraction(4, 3))
        original = gw._tlp_rational_half_belt_translation_from_formula

        def corrupt(*args):
            starts, database = original(*args)
            first = next(path for _, path in database if path[0][:2] == (1, 0))
            second = next(path for _, path in database if path[0][:2] == (3, 0))
            first[1:3], second[1:3] = second[1:3], first[1:3]
            # Coverage, branch lengths, weld direction and pitch survive.
            # The swapped middle pair belongs to a different phase.
            gw.validate_tlp_welds(database, winding, layout)
            return starts, database

        with patch.object(gw, '_tlp_rational_half_belt_translation_from_formula', side_effect=corrupt):
            with self.assertRaisesRegex(ValueError, 'mixed_phase_branch'):
                gw.get_winding_layout('TLP', tp, winding, layout)

    @patch('pattern_rule_workbench.PATTERNS', ('TLP',))
    def test_workbench_uses_weld_inlet_and_successful_public_generation(self):
        from pattern_rule_workbench import build_divider_route_catalog
        records = build_divider_route_catalog('4/3', 3, 4, phases=5)
        record = next(item for item in records if item.dividers == (Fraction(4, 3), 3, 2))
        self.assertEqual(record.status, 'Validated')
        self.assertIn('not strong symmetry layout', record.reason)
        self.assertEqual(records[0].naa, 8)


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

    def test_odd_nondivisor_and_short_native_source_stay_closed(self):
        cases = ((6, 3, 2, 4, 3), (8, 6, 2, 4, 3), (4, 2, 1, 4, 3))
        for q, Q, pp, L, m in cases:
            with self.subTest(q=q, Q=Q, pp=pp, layers=L, phases=m):
                winding, tp, layout = _inputs('TLP', q, pp, L, m, (Q, 1, 1))
                self.assertFalse(gw.supports_integer_tlp_q_only_pair_join(winding, (Q, 1, 1)))
                decision = gw.resolve_pattern_route('TLP', winding, winding.branch_dividers, tp, layout)
                self.assertNotEqual(decision.admission, 'supported')
                with self.assertRaises(ValueError):
                    gw.get_winding_layout('TLP', tp, winding, layout)

    def assert_array_formula(self, database, winding, Q):
        """Derive every mapped parent node and phase/EMF without route helpers."""
        q, m, L = winding.q, winding.num_phases, winding.num_layers
        k, pp, S = m // 3, winding.num_poles // 2, winding.num_slots
        local_q = k * q
        self.assertEqual(local_q, int(local_q))
        qs, Ls, tau = int(local_q), L // k, m * q
        g, width = 2 * qs // Q, pp * Ls
        positions = [tuple(node[:2]) for _, path in database for node in path]
        self.assertEqual(len(positions), len(set(positions)))
        self.assertEqual(set(positions), {(s, l) for s in range(S) for l in range(L)})
        phase_counts, cohort_counts, cohort_lanes = Counter(), Counter(), {}
        for _, path in database:
            self.assertEqual(len(path), g * width)
            j, outer = divmod(path[0][1], Ls)
            phi = ((path[0][0] - 2 * q * j) % S // qs) % 3
            phase_counts[3 * j + phi] += 1
            cohort_counts[3 * j + phi, outer] += 1
            direction = 1 if outer == 0 else -1
            first_lane = path[0][2]
            lanes = list(range(first_lane, first_lane + g))
            cohort_lanes.setdefault((3 * j + phi, outer), []).extend(lanes)
            anchor = phi * qs
            if phi % 2:
                anchor += tau if direction == 1 else (2 * pp - 1) * tau
            actual = 0j
            for index, node in enumerate(path):
                parent_index, within_parent = divmod(index, width)
                lap, within = divmod(within_parent, Ls)
                lane = first_lane + parent_index
                expected_slot = (anchor + lane + direction * tau *
                                 (2 * lap + within % 2) + 2 * q * j) % S
                self.assertEqual(tuple(node), (expected_slot,
                    j * Ls + outer + direction * within, lane))
                local_slot = (node[0] - 2 * q * j) % S
                belt = local_slot // qs
                self.assertEqual(belt % 3, phi)
                self.assertEqual((-1) ** belt, (-1) ** index)
                actual += (-1) ** belt * cmath.exp(1j * math.pi * node[0] / tau)
                if index + 1 < len(path):
                    end = path[index + 1]
                    step = (end[0] - node[0]) % S
                    step = step if 2 * step < S else step - S
                    crossings = abs((local_slot + step) // tau - local_slot // tau)
                    self.assertEqual(crossings, 1)
                    seam = (index + 1) % width == 0
                    outer_return = (index + 1) % Ls == 0
                    self.assertEqual(step, direction * tau + 1 if seam else
                                     direction * tau if outer_return else
                                     direction * tau * (-1) ** within)
            expected = width * cmath.exp(2j * math.pi * j / m) * cmath.exp(
                4j * math.pi * phi / 3) * sum(cmath.exp(1j * math.pi * lane / tau)
                                            for lane in lanes)
            magnitude = width * math.sin(math.pi / (3 * Q)) / math.sin(math.pi / (2 * tau))
            self.assertLess(abs(actual - expected) / magnitude, 1e-10)
            self.assertAlmostEqual(abs(actual) / magnitude, 1, places=10)
        self.assertEqual(phase_counts, Counter({p: Q for p in range(m)}))
        self.assertEqual(cohort_counts, Counter({(p, l): Q // 2 for p in range(m)
                                               for l in (0, Ls - 1)}))
        for lanes in cohort_lanes.values():
            self.assertEqual(lanes, list(range(qs)))
        report = database.layout_report
        self.assertEqual(report['pattern_route']['admission'], 'supported')
        self.assertTrue(report['layout_retained'])
        self.assertEqual(report['pattern_identity']['status'], 'valid')
        self.assertFalse(report['electrically_valid'])
        self.assertEqual(set(report['errors']), {'multi_phase_emf_mismatch'} |
                         ({'parallel_emf_mismatch'} if Q > 2 else set()))
        self.assertEqual(report['layout_status'], 'not strong symmetry layout')

    def test_phase_array_admits_rotated_tau_plus_one_seam(self):
        winding, tp, layout = _inputs('TLP', 4, 2, 12, 9, (2, 1, 1))
        decision = gw.resolve_pattern_route('TLP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.admission, 'supported', decision.reason)
        _, database = gw.get_winding_layout('TLP', tp, winding, layout)
        self.assert_array_formula(database, winding, 2)
        start, end = database[10][1][31:33]
        self.assertEqual((start[0], end[0]), (143, 36))
        step, tau, offset = 37, 36, 8
        self.assertEqual(abs((start[0] + step) // tau - start[0] // tau), 2)
        local_start = (start[0] - offset) % winding.num_slots
        self.assertEqual(abs((local_start + step) // tau - local_start // tau), 1)

    def test_phase_array_public_matrix_matches_independent_formula(self):
        pairs = [(q, Q) for q in (4, 6, 8, 10, 12)
                 for Q in range(2, q, 2) if q % Q == 0]
        for k in (2, 3, 4):
            for q, Q in pairs:
                for pp, Ls in ((2, 2), (3, 4)):
                    with self.subTest(q=q, Q=Q, pp=pp, local_layers=Ls, sets=k):
                        winding, tp, layout = _inputs('TLP', q, pp, k * Ls, 3 * k, (Q, 1, 1))
                        _, database = gw.get_winding_layout('TLP', tp, winding, layout)
                        self.assert_array_formula(database, winding, Q)

    def test_phase_array_uses_local_q_and_parameterized_set_count(self):
        for q, Q, pp, Ls, k in ((1, 2, 2, 2, 2), (3, 2, 2, 4, 2),
                               (2, 6, 2, 4, 3), (2, 2, 2, 2, 5), (1, 2, 3, 4, 6)):
            with self.subTest(q=q, Q=Q, sets=k):
                winding, tp, layout = _inputs('TLP', q, pp, k * Ls, 3 * k, (Q, 1, 1))
                _, database = gw.get_winding_layout('TLP', tp, winding, layout)
                self.assert_array_formula(database, winding, Q)

    def test_phase_array_keeps_local_domain_and_fractional_geometry_boundaries(self):
        for q, Q, pp, L, m in ((6, 3, 2, 8, 6), (4, 6, 2, 8, 6),
                               (4, 2, 1, 8, 6), (4, 2, 2, 6, 6),
                               (4, 2, 2, 8, 9), (1, 2, 2, 12, 9),
                               ('1/2', 2, 2, 4, 6)):
            with self.subTest(q=q, Q=Q, pp=pp, layers=L, phases=m):
                winding, tp, layout = _inputs('TLP', q, pp, L, m, (Q, 1, 1))
                decision = gw.resolve_pattern_route('TLP', winding, winding.branch_dividers, tp, layout)
                self.assertNotEqual(decision.admission, 'supported')
                with self.assertRaises(ValueError):
                    gw.get_winding_layout('TLP', tp, winding, layout)

    def test_half_integer_phase_array_public_cohort_formula(self):
        cases = [(h, 2, pp, Ls, 4) for h in (1, 3, 5, 7)
                 for pp, Ls in ((2, 2), (3, 4))]
        cases += [(1, 2, 2, 2, 8), (3, 2, 2, 2, 8),
                  (3, 4, 2, 4, 8), (3, 12, 3, 4, 8), (1, 2, 3, 4, 12)]
        for h, Q, pp, Ls, k in cases:
            with self.subTest(h=h, Q=Q, pp=pp, local_layers=Ls, sets=k):
                winding, tp, layout = _inputs(
                    'TLP', Fraction(h, 2), pp, k * Ls, 3 * k, (Q, 1, 1))
                decision = gw.resolve_pattern_route('TLP', winding, winding.branch_dividers, tp, layout)
                self.assertEqual(decision.admission, 'supported', decision.reason)
                _, database = gw.get_winding_layout('TLP', tp, winding, layout)
                self.assert_array_formula(database, winding, Q)

    def test_half_integer_cohort_boundaries_and_public_seam_rejection(self):
        for k in (2, 3, 6):
            with self.subTest(sets=k):
                winding, tp, layout = _inputs(
                    'TLP', Fraction(1, 2), 2, 4 * k, 3 * k, (2, 1, 1))
                decision = gw.resolve_pattern_route('TLP', winding, winding.branch_dividers, tp, layout)
                self.assertNotEqual(decision.admission, 'supported')
                with self.assertRaises(ValueError):
                    gw.get_winding_layout('TLP', tp, winding, layout)
        winding, tp, layout = _inputs('TLP', Fraction(3, 2), 2, 16, 12, (2, 1, 1))
        self.assertEqual(gw.resolve_pattern_route(
            'TLP', winding, winding.branch_dividers, tp, layout).admission, 'supported')
        original = gw._array_three_phase_winding_sets

        def corrupt(*args, **kwargs):
            starts, database = original(*args, **kwargs)
            path, width = database[0][1], 2 * 4
            path[width], path[2 * width] = path[2 * width], path[width]
            return starts, database

        with patch.object(gw, '_array_three_phase_winding_sets', side_effect=corrupt):
            with self.assertRaisesRegex(ValueError, 'tau plus or minus one'):
                gw.get_winding_layout('TLP', tp, winding, layout)
        layout.inlet_from_weld_side = 1
        self.assertEqual(gw.resolve_pattern_route(
            'TLP', winding, winding.branch_dividers, tp, layout).admission, 'rejected')

    @patch('pattern_rule_workbench.PATTERNS', ('TLP',))
    def test_half_integer_cohort_catalog_and_post_connection_shifts(self):
        from pattern_rule_workbench import build_divider_route_catalog

        records = build_divider_route_catalog('1/2', 2, 16, phases=12)
        matching = [record for record in records if record.dividers == (2, 1, 1)]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].status, 'Validated')
        self.assertIn('not strong symmetry layout', matching[0].reason)
        self.assertIn('multi_phase_emf_mismatch', matching[0].reason)
        winding, tp, layout = _inputs('TLP', Fraction(3, 2), 2, 16, 12, (2, 1, 1))
        layout.phase_shift_list = [index % 2 for index in range(16)]
        layout.radial_shift = 1
        _, database = gw.get_winding_layout('TLP', tp, winding, layout)
        self.assertTrue(database.layout_report['layout_retained'])
        self.assertEqual(database.layout_report['pattern_identity']['status'], 'valid')
        positions = [tuple(node[:2]) for _, path in database for node in path]
        self.assertEqual(set(positions), {(s, l) for s in range(winding.num_slots)
                                          for l in range(winding.num_layers)})
        self.assertEqual(len(positions), len(set(positions)))

    def test_phase_array_public_generation_rejects_corrupt_seam(self):
        winding, tp, layout = _inputs('TLP', 4, 2, 12, 9, (2, 1, 1))
        self.assertEqual(gw.resolve_pattern_route(
            'TLP', winding, winding.branch_dividers, tp, layout).admission, 'supported')
        original = gw._array_three_phase_winding_sets

        def corrupt(*args, **kwargs):
            starts, database = original(*args, **kwargs)
            path, width = database[10][1], 2 * 4
            path[width], path[2 * width] = path[2 * width], path[width]
            return starts, database

        with patch.object(gw, '_array_three_phase_winding_sets', side_effect=corrupt):
            with self.assertRaisesRegex(ValueError, 'tau plus or minus one'):
                gw.get_winding_layout('TLP', tp, winding, layout)

    def test_phase_array_post_connection_shifts_keep_identity_and_occupancy(self):
        for m, L in ((6, 8), (9, 12)):
            with self.subTest(phases=m):
                winding, tp, layout = _inputs('TLP', 4, 2, L, m, (2, 1, 1))
                layout.phase_shift_list = [index % 2 for index in range(L)]
                layout.radial_shift = 1
                _, database = gw.get_winding_layout('TLP', tp, winding, layout)
                report = database.layout_report
                self.assertTrue(report['layout_retained'])
                self.assertEqual(report['pattern_identity']['status'], 'valid')
                self.assertEqual(report['pattern_route']['admission'], 'supported')
                positions = [tuple(node[:2]) for _, path in database for node in path]
                self.assertEqual(len(positions), len(set(positions)))
                self.assertEqual(len(positions), winding.num_slots * winding.num_layers)

    @patch('pattern_rule_workbench.PATTERNS', ('TLP',))
    def test_phase_array_workbench_uses_public_generation_and_retention_status(self):
        from pattern_rule_workbench import build_divider_route_catalog

        for m, L in ((6, 8), (9, 12), (12, 16)):
            with self.subTest(phases=m):
                records = build_divider_route_catalog('4', 2, L, phases=m)
                record = next(r for r in records if r.dividers == (2, 1, 1))
                self.assertEqual(record.status, 'Validated')
                self.assertTrue(record.reason.startswith('auto configure pending'))
                self.assertIn('layout status: not strong symmetry layout', record.reason)
                self.assertIn('multi_phase_emf_mismatch', record.reason)

    @patch('pattern_rule_workbench.PATTERNS', ('TLP',))
    def test_phase_array_workbench_enumerates_local_q_divisors(self):
        from pattern_rule_workbench import build_divider_route_catalog

        records = build_divider_route_catalog('1', 2, 4, phases=6)
        matching = [r for r in records if r.dividers == (2, 1, 1)]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].status, 'Validated')
        self.assertIn('layout status: not strong symmetry layout', matching[0].reason)
        self.assertIn('multi_phase_emf_mismatch', matching[0].reason)

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


class TlpQppQParentSliceTests(unittest.TestCase):
    def assert_public_q_parent_cut(self, q, pp, layers, phases, Q, D,
                                   shifts=None):
        """Check public children against complete public Q-only parents."""
        winding, tp, layout = _inputs(
            'TLP', q, pp, layers, phases, (Q, D, 1))
        if shifts is not None:
            layout.phase_shift_list = list(shifts)
        reference = deepcopy(winding)
        reference.ab, reference.branch_dividers = Q, (Q, 1, 1)
        _, parents = gw.get_winding_layout('TLP', tp, reference, layout)

        sets = phases // 3 if phases > 3 and phases % 3 == 0 else 1
        local_q, local_layers = q * sets, layers // sets
        local_phases = 3 if sets > 1 else phases
        width = 2 * (local_q // Q) * (pp // D) * local_layers
        expected = []
        for _, path in parents:
            self.assertEqual(len(path), D * width)
            expected.extend(path[index * width:(index + 1) * width]
                            for index in range(D))

        decision = gw.resolve_pattern_route(
            'TLP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.status, 'enabled', decision.reason)
        self.assertEqual(decision.route_name, 'tlp_q_pp_q_parent_slices')
        starts, database = gw.get_winding_layout('TLP', tp, winding, layout)
        self.assertEqual([path for _, path in database], expected)
        self.assertEqual(starts, [path[0] for _, path in database])
        positions = [tuple(node[:2]) for _, path in database for node in path]
        self.assertEqual(len(positions), len(set(positions)))
        self.assertEqual(set(positions), {
            (slot, layer) for slot in range(winding.num_slots)
            for layer in range(layers)})

        counts, weld_directions = Counter(), {}
        phase_shifts = layout.phase_shift_list
        tau = local_phases * local_q
        for branch_id, path in database:
            self.assertEqual(len(path), width)
            set_index = path[0][1] // local_layers if sets > 1 else 0
            slot_offset = 2 * q * set_index if sets > 1 else 0
            local = [((slot - slot_offset - phase_shifts[layer])
                      % winding.num_slots, layer - set_index * local_layers)
                     for slot, layer, *_ in path]
            phase = local[0][0] // local_q % local_phases
            counts[set_index * local_phases + phase] += 1
            self.assertTrue(all(slot // local_q % local_phases == phase
                                for slot, _ in local))
            self.assertEqual([(-1) ** (slot // local_q) for slot, _ in local],
                             [(-1) ** index for index in range(width)])
            self.assertEqual((-1) ** (local[0][0] // local_q), 1)
            self.assertEqual((-1) ** (local[-1][0] // local_q), -1)
            self.assertGreaterEqual(width // local_layers, 2)
            layer_order = (list(range(local_layers)) if local[0][1] == 0
                           else list(range(local_layers - 1, -1, -1)))
            for offset in range(0, width, local_layers):
                self.assertEqual([layer for _, layer in
                                  local[offset:offset + local_layers]],
                                 layer_order)
            for index, (left, right) in enumerate(zip(local, local[1:])):
                ds = (right[0] - left[0]) % winding.num_slots
                ds = ds if 2 * ds < winding.num_slots else ds - winding.num_slots
                self.assertNotEqual(ds, 0)
                self.assertLessEqual(
                    abs((left[0] + ds) // tau - left[0] // tau), 1)
                dl = right[1] - left[1]
                if (index + 1) % local_layers == 0:
                    self.assertEqual(index % 2, 1)
                    self.assertEqual(abs(dl), local_layers - 1)
                else:
                    self.assertEqual(dl, 1 if layer_order[0] == 0 else -1)
                if index % 2 == 0:
                    self.assertEqual(abs(dl), 1)
                    self.assertEqual(abs(ds), tau)
                    pair = (set_index, tuple(sorted((left[1], right[1]))))
                    weld_directions.setdefault(pair, set()).add(
                        1 if ds * dl > 0 else -1)
            recorded = getattr(database, 'signed_travel', {}).get(branch_id)
            if recorded is not None:
                self.assertEqual(len(recorded), width - 1)
                for step, (left, right) in zip(recorded, zip(path, path[1:])):
                    self.assertEqual((left[0] + step) % winding.num_slots,
                                     right[0])
        self.assertEqual(counts, Counter({phase: Q * D
                                         for phase in range(phases)}))
        self.assertTrue(all(len(values) == 1
                            for values in weld_directions.values()))
        report = database.layout_report
        self.assertTrue(report['layout_retained'])
        self.assertEqual(report['pattern_identity']['status'], 'valid')
        self.assertFalse(set(report['errors']) - gw.EMF_ASYMMETRY_ERRORS)
        return winding, tp, layout, database

    def test_native_public_routes_cut_complete_q_only_parents(self):
        for case in ((4, 4, 4, 3, 2, 4), (6, 6, 4, 5, 2, 3)):
            with self.subTest(case=case):
                self.assert_public_q_parent_cut(*case)

    def test_phase_array_reuses_its_two_layer_local_q_only_parents(self):
        self.assert_public_q_parent_cut(4, 4, 4, 6, 2, 4)

    def test_phase_only_shifts_commute_with_the_parent_partition(self):
        _, _, _, database = self.assert_public_q_parent_cut(
            4, 4, 4, 3, 2, 4, shifts=(0, 1, -2, 7))
        self.assertEqual(database.layout_report['post_connection_shift']
                         ['connection_validation'], 'before shift')

    def test_full_global_q_array_parent_cuts_keep_successful_mapper_priority(self):
        cases = ((2, 6, 12, 6, 2, 3), (4, 4, 4, 6, 4, 4))
        for case in cases:
            with self.subTest(case=case):
                shifts = tuple(layer % 2 for layer in range(case[2]))
                self.assert_public_q_parent_cut(*case, shifts=shifts)

        # The established valid mapping (4,8,1) -> (8,4,1) still takes priority.
        winding, tp, layout = _inputs('TLP', 4, 8, 8, 6, (4, 8, 1))
        decision = gw.resolve_pattern_route(
            'TLP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.status, 'enabled', decision.reason)
        self.assertEqual(decision.route_name, 'tlp_pp_only_even')
        _, database = gw.get_winding_layout('TLP', tp, winding, layout)
        self.assertEqual({item['route_name'] for item in
                          database.phase_set_array['routes']},
                         {'tlp_pp_only_even'})
        self.assertTrue(database.layout_report['layout_retained'])

    def test_array_parent_slices_require_complete_unambiguous_signed_evidence(self):
        winding, tp, layout, baseline = self.assert_public_q_parent_cut(
            2, 6, 12, 6, 2, 3)
        self.assertEqual({item['route_name'] for item in
                          baseline.phase_set_array['routes']},
                         {'tlp_q_pp_q_parent_slices'})
        self.assertEqual(set(baseline.signed_travel),
                         {branch_id for branch_id, _ in baseline})
        for branch_id, path in baseline:
            steps = baseline.signed_travel[branch_id]
            self.assertEqual(len(steps), len(path) - 1)
            for step, (left, right) in zip(steps, zip(path, path[1:])):
                self.assertIs(type(step), int)
                self.assertEqual((left[0] + step) % winding.num_slots,
                                 right[0])

        dispatch = gw._dispatch_winding_pattern
        for corruption in ('none', 'missing_branch', 'extra_branch', 'extra_turn'):
            with self.subTest(corruption=corruption):
                corrupted = []

                def corrupt_after_dispatch(pattern, config, current, selected_layout,
                                           **kwargs):
                    starts, database = dispatch(
                        pattern, config, current, selected_layout, **kwargs)
                    if (pattern == 'TLP' and current.num_phases == 6
                            and current.branch_dividers == (2, 3, 1)):
                        self.assertEqual(set(database.signed_travel),
                                         {bid for bid, _ in database})
                        travel = dict(database.signed_travel)
                        branch_id = database[0][0]
                        if corruption == 'none':
                            travel = None
                        elif corruption == 'missing_branch':
                            travel.pop(branch_id)
                        elif corruption == 'extra_branch':
                            travel[max(travel) + 1] = travel[branch_id]
                        else:
                            steps = travel[branch_id]
                            travel[branch_id] = (
                                steps[0] + current.num_slots, *steps[1:])
                        database.signed_travel = travel
                        corrupted.append(branch_id)
                    return starts, database

                with patch.object(gw, '_dispatch_winding_pattern',
                                  side_effect=corrupt_after_dispatch):
                    with self.assertRaises(ValueError):
                        gw.get_winding_layout('TLP', tp, winding, layout)
                self.assertEqual(len(corrupted), 1)

    def test_unit_q_uses_even_gcd_parent_instead_of_odd_naa_reference(self):
        winding, tp, layout = _inputs('TLP', 4, 4, 4, 3, (1, 1, 1))
        with self.assertRaisesRegex(ValueError, 'current grammar requires even Naa'):
            gw.get_winding_layout('TLP', tp, winding, layout)
        winding.ab, winding.branch_dividers = 4, (1, 4, 1)
        decision = gw.resolve_pattern_route(
            'TLP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.admission, 'supported')
        self.assertEqual(decision.route_name, 'tlp_even_gcd_parent_slices')
        parent = deepcopy(winding)
        parent.ab, parent.branch_dividers = 4, (4, 1, 1)
        _, source = gw.get_winding_layout('TLP', tp, parent, layout)
        _, database = gw.get_winding_layout('TLP', tp, winding, layout)
        self.assertEqual([path for _, path in database], [path for _, path in source])
        self.assertTrue(database.layout_report['layout_retained'])

    def test_existing_d_two_and_full_q_even_cut_routes_keep_precedence(self):
        for Q, D, route in ((4, 2, 'tlp_q_pp_two'),
                            (4, 4, 'tlp_pp_only_even')):
            with self.subTest(dividers=(Q, D, 1)):
                winding, tp, layout = _inputs('TLP', 4, 4, 4, 3, (Q, D, 1))
                decision = gw.resolve_pattern_route(
                    'TLP', winding, winding.branch_dividers, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                self.assertEqual(decision.route_name, route)


class TlpEvenGcdParentSliceTests(unittest.TestCase):
    def assert_parent_partition(self, q, pp, layers, phases, factors, shifts=None,
                                route='tlp_even_gcd_parent_slices'):
        winding, tp, layout = _inputs('TLP', q, pp, layers, phases, factors)
        if shifts is not None:
            layout.phase_shift_list = list(shifts)
        sets = phases // 3 if phases > 3 and phases % 3 == 0 else 1
        local_q, local_layers = q * sets, layers // sets
        naa = math.prod(factors)
        parent_count = math.gcd(local_q, naa)
        parts = naa // parent_count
        width = 2 * local_q * pp * local_layers // naa
        parent = deepcopy(winding)
        parent.ab = parent_count
        parent.branch_dividers = (parent_count, 1, 1)
        _, source = gw.get_winding_layout('TLP', tp, parent, layout)
        expected = [path[index * width:(index + 1) * width]
                    for _, path in source for index in range(parts)]
        if factors[2] == 2:
            signs = {(s, l): sign for s, l, _, sign in gw.phase_map(
                winding.num_slots, winding.num_poles, layers,
                layout.phase_shift_list, phases)}
            expected = [path if signs[tuple(path[0][:2])] == 1
                        else path[::-1] for path in expected]
        decision = gw.resolve_pattern_route('TLP', winding, factors, tp, layout)
        self.assertEqual(decision.route_name, route, decision.reason)
        _, database = gw.get_winding_layout('TLP', tp, winding, layout)
        if route == 'tlp_even_gcd_parent_slices':
            self.assertEqual([path for _, path in database], expected)
        else:
            self.assertCountEqual([path for _, path in database], expected)
        positions = [tuple(node[:2]) for _, path in database for node in path]
        self.assertEqual(Counter(positions), Counter({(s, l): 1
                         for s in range(winding.num_slots) for l in range(layers)}))
        self.assertEqual({len(path) for _, path in database}, {width})
        self.assertGreaterEqual(width, 2 * local_layers)
        self.assertEqual(set(database.signed_travel), {bid for bid, _ in database})
        for bid, path in database:
            self.assertEqual(len(database.signed_travel[bid]), width - 1)
            for step, (left, right) in zip(database.signed_travel[bid], zip(path, path[1:])):
                self.assertEqual((left[0] + step) % winding.num_slots, right[0])
        self.assertTrue(database.layout_report['layout_retained'])
        self.assertEqual(database.layout_report['pattern_identity']['status'], 'valid')
        return winding, tp, layout, database

    def test_odd_selected_q_uses_an_even_gcd_parent(self):
        self.assert_parent_partition(6, 6, 4, 5, (3, 6, 1))

    def test_equal_naa_reinterpretation_and_p2_cuts(self):
        self.assert_parent_partition(6, 6, 4, 5, (3, 2, 1))
        self.assert_parent_partition(4, 4, 4, 3, (4, 2, 2))
        self.assert_parent_partition(4, 4, 4, 3, (2, 1, 2))

    def test_failed_old_sector_deployment_uses_complete_gcd_mother_cuts(self):
        # D=4's old rotated sector deployment duplicates and misses positions.
        # The configured Q-only mother is complete; cuts add no target edges.
        self.assert_parent_partition(2, 8, 4, 3, (1, 4, 2))
        self.assert_parent_partition(2, 8, 4, 3, (2, 4, 2),
                                     route='tlp_q_pp_p2_parent_slices')

    def test_local_two_layers_and_full_global_q_array_mapping(self):
        self.assert_parent_partition(3, 6, 4, 6, (3, 6, 1))
        self.assert_parent_partition(1, 2, 4, 6, (1, 2, 1), shifts=(0, 1, -2, 7))

    def test_odd_local_q_and_illegal_sector_product_are_not_promoted(self):
        for q, pp, factors in ((3, 6, (3, 2, 1)), (4, 4, (4, 4, 2))):
            winding, _, _ = _inputs('TLP', q, pp, 4, 3, factors)
            self.assertFalse(gw.supports_tlp_even_gcd_parent_slices(winding, factors))

    def test_odd_q_fallback_cuts_the_two_branch_public_p2_mother(self):
        for q, pp, layers, factors in ((3, 6, 4, (1, 6, 1)),
                                      (5, 6, 4, (5, 3, 2)),
                                      (3, 6, 2, (1, 2, 1))):
            with self.subTest(q=q, pp=pp, layers=layers, factors=factors):
                w, tp, layout = _inputs('TLP', q, pp, layers, 5, factors)
                parent = deepcopy(w)
                parent.ab, parent.branch_dividers = 2, (1, 1, 2)
                _, source = gw.get_winding_layout('TLP', tp, parent, layout)
                width = 2 * q * pp * layers // math.prod(factors)
                phase_by_position = {(s, l): phase for s, l, phase, _ in gw.phase_map(
                    w.num_slots, w.num_poles, layers, layout.phase_shift_list, 5)}
                expected = [path[i:i + width] for phase in range(5)
                            for _, path in source
                            if phase_by_position[tuple(path[0][:2])] == phase
                            for i in range(0, len(path), width)]
                if factors[2] == 2:
                    signs = {(s, l): sign for s, l, _, sign in gw.phase_map(
                        w.num_slots, w.num_poles, layers, layout.phase_shift_list, 5)}
                    expected = [path if signs[tuple(path[0][:2])] == 1
                                else path[::-1] for path in expected]
                d = gw.resolve_pattern_route('TLP', w, factors, tp, layout)
                self.assertEqual(d.route_name, 'tlp_p2_parent_slices', d.reason)
                _, database = gw.get_winding_layout('TLP', tp, w, layout)
                self.assertEqual([path for _, path in database], expected)
                self.assertTrue(database.layout_report['layout_retained'])
                self.assertEqual(database.layout_report['pattern_identity']['status'], 'valid')

    def test_odd_composite_local_q_second_sector_uses_the_complete_p2_mother(self):
        w, tp, layout = _inputs('TLP', 3, 4, 6, 9, (3, 2, 1))
        d = gw.resolve_pattern_route('TLP', w, w.branch_dividers, tp, layout)
        self.assertEqual(d.route_name, 'tlp_p2_parent_slices', d.reason)
        _, database = gw.get_winding_layout('TLP', tp, w, layout)
        self.assertEqual(Counter(tuple(n[:2]) for _, path in database for n in path),
                         Counter({(s, l): 1 for s in range(w.num_slots) for l in range(6)}))
        self.assertTrue(database.layout_report['layout_retained'])
        self.assertEqual(database.layout_report['pattern_identity']['status'], 'valid')

    def test_full_global_q_odd_local_array_keeps_the_p2_parent_mapping(self):
        cases = ((q, pp, layers, D) for q in (3, 5) for layers in (6, 12)
                 for pp, D in ((4, 4), (6, 6), (8, 4), (8, 8)))
        for q, pp, layers, D in cases:
            with self.subTest(q=q, pp=pp, layers=layers, D=D):
                factors = (q, D, 1)
                w, tp, layout = _inputs('TLP', q, pp, layers, 9, factors)
                parent = deepcopy(w)
                parent.ab, parent.branch_dividers = 2, (1, 1, 2)
                _, source = gw.get_winding_layout('TLP', tp, parent, layout)
                width = 2*q*pp*layers//math.prod(factors)
                expected = [path[i:i+width] for _, path in source
                            for i in range(0, len(path), width)]
                d = gw.resolve_pattern_route('TLP', w, factors, tp, layout)
                self.assertEqual(d.status, 'enabled', d.reason)
                _, database = gw.get_winding_layout('TLP', tp, w, layout)
                self.assertCountEqual([path for _, path in database], expected)
                self.assertEqual(Counter(tuple(n[:2]) for _, path in database for n in path),
                                 Counter({(s, l): 1 for s in range(w.num_slots)
                                          for l in range(layers)}))
                self.assertTrue(database.layout_report['layout_retained'])
                self.assertEqual(database.layout_report['pattern_identity']['status'], 'valid')

    def test_parent_failure_and_malformed_signed_record_are_propagated(self):
        w, tp, layout = _inputs('TLP', 6, 6, 4, 5, (3, 6, 1))
        public = gw.get_winding_layout
        for corruption in ('failed_parent', 'none_steps'):
            def corrupt(pattern, config, current, selected_layout, **kwargs):
                if current.branch_dividers == (6, 1, 1):
                    if corruption == 'failed_parent':
                        raise ValueError('configured parent witness fails')
                    starts, source = public(pattern, config, current, selected_layout, **kwargs)
                    source.signed_travel = {
                        bid: tuple(gw.circular_travel_steps(a[0], b[0], current.num_slots)[0]
                                   for a, b in zip(path, path[1:]))
                        for bid, path in source}
                    source.signed_travel[source[0][0]] = None
                    return starts, source
                return public(pattern, config, current, selected_layout, **kwargs)
            with self.subTest(corruption=corruption), patch.object(
                    gw, 'get_winding_layout', side_effect=corrupt):
                with self.assertRaisesRegex(ValueError, 'parent witness fails|wrong length'):
                    gw._q_pp_q_parent_slices_from_reference('TLP', tp, w, layout)


class TspSingleCompletePassTests(unittest.TestCase):
    def test_proper_q_second_sector_uses_complete_passes_instead_of_incomplete_raw_parent(self):
        w, tp, layout = _inputs('TSP', 4, 4, 4, 3, (2, 2, 1))
        parent = deepcopy(w)
        parent.branch_dividers = (2, 1, 2)
        starts, raw = gw.pattern_TSP(tp, parent, layout)
        with self.assertRaisesRegex(ValueError, 'conductors|occupancy|complete|covers|positions'):
            gw._validate_generated_layout_consistency('TSP', starts, raw, parent)
        d = gw.resolve_pattern_route('TSP', w, w.branch_dividers, tp, layout)
        self.assertEqual(d.route_name, 'tsp_spiral_pass_partition', d.reason)
        _, database = gw.get_winding_layout('TSP', tp, w, layout)
        self.assertEqual(Counter(tuple(n[:2]) for _, path in database for n in path),
                         Counter({(s, l): 1 for s in range(w.num_slots) for l in range(4)}))
        self.assertTrue(database.layout_report['layout_retained'])
        self.assertEqual(database.layout_report['pattern_identity']['status'], 'valid')

    def test_eight_node_single_pass_keeps_grammar_and_full_occupancy(self):
        w, tp, layout = _inputs('TSP', 2, 3, 8, 5, (2, 3, 2))
        decision = gw.resolve_pattern_route('TSP', w, w.branch_dividers, tp, layout)
        self.assertEqual(decision.admission, 'supported', decision.reason)
        _, database = gw.get_winding_layout('TSP', tp, w, layout)
        positions = [tuple(node[:2]) for _, path in database for node in path]
        self.assertEqual(Counter(positions), Counter({(s, l): 1
                         for s in range(w.num_slots) for l in range(8)}))
        self.assertEqual({len(path) for _, path in database}, {8})
        signs = {(s, l): (phase, sign) for s, l, phase, sign in gw.phase_map(
            w.num_slots, w.num_poles, 8, layout.phase_shift_list, 5)}
        for bid, path in database:
            self.assertIn([node[1] for node in path],
                          [list(range(8)), list(reversed(range(8)))])
            phase = signs[tuple(path[0][:2])][0]
            self.assertEqual([signs[tuple(node[:2])] for node in path],
                             [(phase, (-1)**i) for i in range(8)])
            self.assertEqual(set(abs(ds) for ds in database.signed_travel[bid]), {10})
        self.assertTrue(database.layout_report['layout_retained'])
        self.assertEqual(database.layout_report['pattern_identity']['status'], 'valid')


class CpGcdQuartetParentSliceTests(unittest.TestCase):
    def test_configured_mother_failure_is_propagated_without_neutral_retry(self):
        w, tp, layout = _inputs('CP', 2, 2, 8, 5, (2, 1, 2))
        tp.uni_tp = 1
        layout.phase_shift_list = [0, 1, -2, 7, 2, 0, 1, -1]
        calls = []

        def fail(pattern, config, current, selected_layout, **kwargs):
            calls.append((pattern, config.uni_tp, current.branch_dividers,
                          selected_layout.phase_shift_list))
            raise ValueError('configured CP mother witness fails')

        with patch.object(gw, 'get_winding_layout', side_effect=fail):
            with self.assertRaisesRegex(ValueError, 'configured CP mother witness fails'):
                gw._cp_polarity_pool_parent_slices_from_reference(tp, w, layout)
        self.assertEqual(calls, [('CP', 1, (1, 1, 2), [0, 1, 2, 0])])

    def test_mother_signed_corruption_and_nonuniform_weld_pitch_are_rejected(self):
        w, tp, layout = _inputs('CP', 2, 2, 4, 5, (1, 2, 1))
        public = gw.get_winding_layout
        for corruption in ('none', 'none_steps', 'short', 'extra_turn', 'pitch'):
            def corrupt(pattern, config, current, selected_layout, **kwargs):
                starts, source = public(pattern, config, current, selected_layout, **kwargs)
                self.assertEqual(current.branch_dividers, (1, 1, 2))
                bid = source[0][0]
                if corruption == 'none':
                    source.signed_travel = None
                elif corruption == 'none_steps':
                    source.signed_travel[bid] = None
                elif corruption == 'short':
                    source.signed_travel[bid] = source.signed_travel[bid][:-1]
                elif corruption == 'extra_turn':
                    steps = source.signed_travel[bid]
                    source.signed_travel[bid] = (steps[0] + current.num_slots, *steps[1:])
                else:
                    before = Counter(tuple(n[:2]) for _, path in source for n in path)
                    for _, path in source:
                        for i, node in enumerate(path):
                            if node[1] == 1 and node[0] in (10, 11):
                                path[i] = (21 - node[0], *node[1:])
                    self.assertEqual(Counter(tuple(n[:2]) for _, path in source for n in path), before)
                    source.signed_travel = {
                        branch_id: tuple(gw.circular_travel_steps(a[0], b[0], current.num_slots)[0]
                                         for a, b in zip(path, path[1:]))
                        for branch_id, path in source}
                return starts, source
            with self.subTest(corruption=corruption), patch.object(
                    gw, 'get_winding_layout', side_effect=corrupt):
                with self.assertRaisesRegex(ValueError, 'signed|pitch'):
                    gw._cp_polarity_pool_parent_slices_from_reference(tp, w, layout)

    def test_weld_inlet_and_unsupported_inlet_adjustment_are_rejected(self):
        for adjustment, weld in ((0, 1), (1, 0)):
            w, tp, layout = _inputs('CP', 2, 2, 8, 5, (2, 1, 2))
            layout.inlet_from_weld_side = weld
            layout.inlet_index_adjustments_phase_a = [adjustment]
            with self.subTest(adjustment=adjustment, weld=weld):
                d = gw.resolve_pattern_route('CP', w, w.branch_dividers, tp, layout)
                self.assertEqual(d.admission, 'rejected', d.reason)

    def test_two_layer_transfer_rejects_nonsequence_signed_values(self):
        w, tp, layout = _inputs('CP', 2, 2, 2, 3, (1, 2, 1))
        public = gw.get_winding_layout
        starts, baseline = public('TLP', tp, w, layout)
        def corrupt(pattern, config, current, selected_layout, **kwargs):
            source = deepcopy(baseline)
            source.signed_travel[source[0][0]] = None
            return starts, source
        with patch.object(gw, 'get_winding_layout', side_effect=corrupt):
            with self.assertRaisesRegex(ValueError, 'complete mother signed evidence'):
                gw._cp_two_layer_from_tlp_reference(tp, w, layout)

    def test_pp_two_reuses_a_public_p2_mother_without_new_edges(self):
        for q in (1, 2, 3):
            w, tp, layout = _inputs('CP', q, 2, 4, 5, (1, 2, 1))
            parent = deepcopy(w)
            parent.branch_dividers = (1, 1, 2)
            _, source = gw.get_winding_layout('CP', tp, parent, layout)
            d = gw.resolve_pattern_route('CP', w, w.branch_dividers, tp, layout)
            self.assertEqual(d.route_name, 'cp_gcd_quartet_parent_slices', d.reason)
            _, database = gw.get_winding_layout('CP', tp, w, layout)
            self.assertCountEqual([path for _, path in database], [path for _, path in source])
            self.assertTrue(database.layout_report['layout_retained'])

    def test_four_layer_mother_lifts_into_each_independent_quartet(self):
        for q, pp, layers, factors in ((2, 2, 8, (2, 1, 2)),
                                      (3, 3, 12, (1, 3, 2))):
            w, tp, layout = _inputs('CP', q, pp, layers, 5, factors)
            parent = deepcopy(w)
            parent.ab, parent.branch_dividers, parent.num_layers = 2, (1, 1, 2), 4
            parent_layout = deepcopy(layout)
            parent_layout.phase_shift_list = [0] * 4
            _, source = gw.get_winding_layout('CP', tp, parent, parent_layout)
            H = layers // 2
            expected = []
            for r in range(H // 2):
                layer_map = (2*r, 2*r+1, H+2*r, H+2*r+1)
                expected.extend([[(s, layer_map[l], lane) for s, l, lane in path]
                                 for _, path in source])
            d = gw.resolve_pattern_route('CP', w, factors, tp, layout)
            self.assertEqual(d.route_name, 'cp_gcd_quartet_parent_slices', d.reason)
            _, database = gw.get_winding_layout('CP', tp, w, layout)
            self.assertCountEqual([path for _, path in database], expected)
            positions = [tuple(node[:2]) for _, path in database for node in path]
            self.assertEqual(Counter(positions), Counter({(s, l): 1
                             for s in range(w.num_slots) for l in range(layers)}))
            self.assertTrue(database.layout_report['layout_retained'])
            self.assertEqual(database.layout_report['pattern_identity']['status'], 'valid')

    def test_polarity_pool_exclusion_is_a_parameter_rule(self):
        for q, pp, layers, factors in ((2, 3, 4, (1, 3, 1)),
                                      (1, 2, 8, (1, 1, 2)),
                                      (2, 2, 12, (2, 1, 2))):
            w, tp, layout = _inputs('CP', q, pp, layers, 3, factors)
            d = gw.resolve_pattern_route('CP', w, factors, tp, layout)
            self.assertEqual(d.rule_id, 'cp_polarity_pool_rejected')
            self.assertEqual(d.admission, 'rejected')
            with self.assertRaisesRegex(ValueError, 'polarity pool'):
                gw.get_winding_layout('CP', tp, w, layout)

    def test_arrays_include_local_two_and_six_layer_constructions(self):
        for q, pp, layers, phases, factors, route in (
                (1, 2, 4, 6, (1, 2, 1), 'cp_two_layer_tlp_transfer'),
                (1, 2, 4, 6, (1, 2, 2), 'cp'),
                (1, 6, 12, 6, (1, 6, 1), 'cp_q_pp_full_parent_slices')):
            with self.subTest(q=q, pp=pp, L=layers, m=phases, factors=factors):
                w, tp, layout = _inputs('CP', q, pp, layers, phases, factors)
                d = gw.resolve_pattern_route('CP', w, factors, tp, layout)
                self.assertEqual(d.route_name, route, d.reason)
                _, database = gw.get_winding_layout('CP', tp, w, layout)
                positions = [tuple(node[:2]) for _, path in database for node in path]
                self.assertEqual(Counter(positions), Counter({(s, l): 1
                                 for s in range(w.num_slots) for l in range(layers)}))
                self.assertTrue(database.layout_report['layout_retained'])
                self.assertEqual(database.layout_report['pattern_identity']['status'], 'valid')


class SlpP2BeltPassPartitionTests(unittest.TestCase):
    def test_array_shifts_manual_input_and_successful_legacy_priority(self):
        for q, pp, layers, phases, factors in (
                (2, 6, 4, 6, (1, 2, 2)), (6, 7, 4, 5, (2, 1, 2))):
            w, tp, layout = _inputs('SLP', q, pp, layers, phases, factors)
            layout.phase_shift_list = [0, 1, -2, 7]
            if phases == 5:
                tp.uni_tp = 1
            _, database = gw.get_winding_layout('SLP', tp, w, layout)
            self.assertTrue(database.layout_report['layout_retained'])
            self.assertEqual(database.layout_report['pattern_identity']['status'], 'valid')
            self.assertEqual(database.layout_report['post_connection_shift']
                             ['connection_validation'], 'before shift')
        w, tp, layout = _inputs('SLP', 2, 4, 4, 3, (1, 1, 2))
        _, legacy = gw._slp_p2_from_reference(tp, w, layout)
        _, current = gw.get_winding_layout('SLP', tp, w, layout)
        self.assertEqual([path for _, path in current], [path for _, path in legacy])
        self.assertEqual(current.layout_report['pattern_route']['route_name'], 'slp_p2_from_reference')

    def test_weld_inlet_keeps_same_layer_edges_on_the_insertion_side(self):
        for q, pp, L, m, factors, manual in (
                (4, 4, 4, 3, (1, 1, 2), 0),
                (4, 4, 4, 3, (1, 1, 2), 1),
                (2, 4, 4, 6, (1, 1, 2), 0),
                (4, 4, 6, 5, (2, 4, 2), 0),
                (6, 7, 4, 5, (2, 1, 2), 1)):
            with self.subTest(q=q, pp=pp, L=L, m=m, manual=manual):
                w, tp, layout = _inputs('SLP', q, pp, L, m, factors)
                tp.uni_tp = manual
                layout.inlet_from_weld_side = 1
                _, database = gw.get_winding_layout('SLP', tp, w, layout)
                positions = [tuple(n[:2]) for _, path in database for n in path]
                self.assertEqual(Counter(positions), Counter({(s, l): 1
                                 for s in range(w.num_slots) for l in range(L)}))
                for local, winding, selected_layout in gw._three_phase_set_views(
                        database, w, layout) if m % 3 == 0 and m > 3 else ((database, w, layout),):
                    parent = deepcopy(winding)
                    parent.ab, parent.branch_dividers = parent.q, (parent.q, 1, 1)
                    source_layout = deepcopy(selected_layout)
                    source_layout.inlet_from_weld_side = 0
                    _, source = gw.get_winding_layout('SLP', tp, parent, source_layout)
                    mother_welds = Counter(frozenset((tuple(a[:2]), tuple(b[:2])))
                        for _, path in source for i, (a, b) in enumerate(zip(path, path[1:]))
                        if i % 2 == 0)
                    actual_welds = Counter(frozenset((tuple(a[:2]), tuple(b[:2])))
                        for _, path in local for i, (a, b) in enumerate(zip(path, path[1:]))
                        if i % 2 == 1)
                    self.assertFalse(actual_welds - mother_welds)
                    self.assertEqual(sum(mother_welds.values())-sum(actual_welds.values()),
                                     winding.ab*winding.num_phases)
                    for bid, path in local:
                        for i, (a, b) in enumerate(zip(path, path[1:])):
                            if i % 2 == 1:
                                self.assertEqual(abs(b[1]-a[1]), 1)
                                self.assertEqual(abs(local.signed_travel[bid][i]), winding.q*winding.num_phases)
                            elif a[1] == b[1]:
                                self.assertIn(a[1], (0, winding.num_layers-1))
                self.assertTrue(database.layout_report['layout_retained'])
                self.assertEqual(database.layout_report['pattern_identity']['status'], 'valid')

    def test_whole_branch_rotation_is_not_a_legal_weld_inlet_construction(self):
        w, tp, layout = _inputs('SLP', 4, 4, 4, 3, (1, 1, 2))
        _, baseline = gw.get_winding_layout('SLP', tp, w, layout)
        rotated = deepcopy(baseline)
        for bid, path in rotated:
            closing = gw.circular_travel_steps(path[-1][0], path[0][0], w.num_slots)[0]
            rotated.signed_travel[bid] = (*rotated.signed_travel[bid][1:], closing)
            path[:] = path[1:]+path[:1]
        layout.inlet_from_weld_side = 1
        identity = analyze_ordered_pattern('SLP', rotated, w, layout)
        self.assertEqual(identity['ordered_status'], 'candidate')
        self.assertIn('multiple pole regions', str(identity['branch_reports']))

    def test_configured_mother_failure_and_explicit_signed_corruption_are_rejected(self):
        w, tp, layout = _inputs('SLP', 4, 4, 4, 3, (1, 1, 2))
        parent = deepcopy(w)
        parent.ab, parent.branch_dividers = 4, (4, 1, 1)
        _, source = gw.get_winding_layout('SLP', tp, parent, layout)
        for weld in (0, 1):
            layout.inlet_from_weld_side = weld
            with self.subTest(weld=weld), patch.object(gw, 'get_winding_layout',
                    side_effect=ValueError('configured SLP mother witness fails')) as mocked:
                with self.assertRaisesRegex(ValueError, 'configured SLP mother witness fails'):
                    gw._slp_p2_belt_pass_partition_from_reference(tp, w, layout)
                self.assertEqual(mocked.call_count, 1)
            for corruption in ('none', 'none_steps', 'short', 'extra_turn'):
                corrupted = deepcopy(source)
                corrupted.signed_travel = {bid: tuple(gw.circular_travel_steps(a[0], b[0], w.num_slots)[0]
                    for a, b in zip(path, path[1:])) for bid, path in source}
                bid = source[0][0]
                if corruption == 'none':
                    corrupted.signed_travel = None
                elif corruption == 'none_steps':
                    corrupted.signed_travel[bid] = None
                elif corruption == 'short':
                    corrupted.signed_travel[bid] = corrupted.signed_travel[bid][:-1]
                else:
                    steps = corrupted.signed_travel[bid]
                    corrupted.signed_travel[bid] = (steps[0]+w.num_slots, *steps[1:])
                with self.subTest(weld=weld, corruption=corruption), patch.object(
                        gw, 'get_winding_layout', return_value=([], corrupted)):
                    with self.assertRaisesRegex(ValueError, 'signed'):
                        gw._slp_p2_belt_pass_partition_from_reference(tp, w, layout)

    def test_new_even_and_odd_sector_routes_preserve_every_actual_mother_weld(self):
        for q, pp, layers, phases, factors in (
                (4, 4, 4, 3, (1, 1, 2)), (6, 6, 4, 5, (2, 6, 2)),
                (4, 4, 6, 5, (2, 4, 2)),
                (6, 7, 4, 5, (2, 1, 2)), (1, 4, 4, 3, (1, 1, 2)),
                (4, 6, 2, 3, (1, 2, 2))):
            with self.subTest(q=q, pp=pp, L=layers, m=phases, factors=factors):
                w, tp, layout = _inputs('SLP', q, pp, layers, phases, factors)
                parent = deepcopy(w)
                parent.ab, parent.branch_dividers = q, (q, 1, 1)
                _, source = gw.get_winding_layout('SLP', tp, parent, layout)
                # Ordinary L-pass orientation can reverse; unordered physical
                # weld endpoints must remain exactly the public mother's.
                mother_welds = Counter(frozenset((tuple(a[:2]), tuple(b[:2])))
                    for _, path in source for i, (a, b) in enumerate(zip(path, path[1:]))
                    if i % 2 == 0)
                d = gw.resolve_pattern_route('SLP', w, factors, tp, layout)
                self.assertEqual(d.route_name, 'slp_p2_belt_pass_partition', d.reason)
                _, database = gw.get_winding_layout('SLP', tp, w, layout)
                self.assertEqual(Counter(frozenset((tuple(a[:2]), tuple(b[:2])))
                    for _, path in database for i, (a, b) in enumerate(zip(path, path[1:]))
                    if i % 2 == 0), mother_welds)
                positions = [tuple(n[:2]) for _, path in database for n in path]
                self.assertEqual(Counter(positions), Counter({(s, l): 1
                                 for s in range(w.num_slots) for l in range(layers)}))
                self.assertEqual({len(path) for _, path in database},
                                 {q // factors[0] * (pp // factors[1]) * layers})
                self.assertTrue(database.layout_report['layout_retained'])
                self.assertEqual(database.layout_report['pattern_identity']['status'], 'valid')


class SlpProperQOnlyP2RegroupTests(unittest.TestCase):
    def assert_public_full_q_p2_regroup(self, q, pp, layers, phases, Q,
                                      shifts=None):
        """Check sector-major children against strict public full-Q parents."""
        winding, tp, layout = _inputs('SLP', q, pp, layers, phases, (Q, 1, 2))
        if shifts is not None:
            layout.phase_shift_list = list(shifts)
        sets = phases // 3 if phases > 3 and phases % 3 == 0 else 1
        local_q, local_layers = q * sets, layers // sets
        local_phases = 3 if sets > 1 else phases
        lanes_per_child = local_q // Q
        width = lanes_per_child * pp * local_layers
        block_width = 2 * local_layers
        expected, source_welds = [], Counter()
        for set_index in range(sets):
            parent_winding, parent_tp, parent_layout = _inputs(
                'SLP', local_q, pp, local_layers, local_phases,
                (local_q, 1, 2))
            parent_layout.phase_shift_list = list(layout.phase_shift_list[
                set_index * local_layers:(set_index + 1) * local_layers])
            _, parents = gw.get_winding_layout(
                'SLP', parent_tp, parent_winding, parent_layout)
            self.assertEqual(len(parents), 2 * local_q * local_phases)
            slot_offset = 2 * q * set_index if sets > 1 else 0

            def to_global(node):
                return ((node[0] + slot_offset) % winding.num_slots,
                        node[1] + set_index * local_layers, *node[2:])

            for _, path in parents:
                self.assertEqual(len(path), pp * local_layers)
                source_welds.update(
                    (to_global(left)[:2], to_global(right)[:2])
                    for index, (left, right) in enumerate(zip(path, path[1:]))
                    if index % 2 == 0)
            for phase_start in range(0, len(parents), 2 * local_q):
                for cohort in range(2):
                    first = phase_start + cohort * local_q
                    cohort_parents = parents[first:first + local_q]
                    for lane, (_, path) in enumerate(cohort_parents):
                        self.assertEqual({node[2] for node in path}, {lane})
                    for group in range(Q):
                        lanes = list(range(group * lanes_per_child,
                                           (group + 1) * lanes_per_child))
                        child = []
                        for block in range(pp // 2):
                            for lane in lanes if block % 2 == 0 else reversed(lanes):
                                source = cohort_parents[lane][1]
                                child.extend(source[block * block_width:
                                                    (block + 1) * block_width])
                        expected.append([to_global(node) for node in child])

        decision = gw.resolve_pattern_route(
            'SLP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.status, 'enabled', decision.reason)
        self.assertEqual(decision.route_name, 'slp_q_pp_p2_parent_cut')
        self.assertEqual(decision.required_inlet, 'insert')
        starts, database = gw.get_winding_layout('SLP', tp, winding, layout)
        self.assertEqual([path for _, path in database], expected)
        self.assertEqual(starts, [path[0] for _, path in database])
        self.assertEqual(len(database), 2 * Q * phases)
        positions = [tuple(node[:2]) for _, path in database for node in path]
        self.assertEqual(len(positions), len(set(positions)))
        self.assertEqual(set(positions), {
            (slot, layer) for slot in range(winding.num_slots)
            for layer in range(layers)})

        counts, child_welds, weld_directions = Counter(), Counter(), {}
        tau = local_q * local_phases
        for branch_id, path in database:
            self.assertEqual(len(path), width)
            set_index = path[0][1] // local_layers if sets > 1 else 0
            slot_offset = 2 * q * set_index if sets > 1 else 0
            local = [((slot - slot_offset - layout.phase_shift_list[layer])
                      % winding.num_slots, layer - set_index * local_layers)
                     for slot, layer, *_ in path]
            phase = local[0][0] // local_q % local_phases
            counts[set_index * local_phases + phase] += 1
            self.assertTrue(all(slot // local_q % local_phases == phase
                                for slot, _ in local))
            self.assertEqual([(-1) ** (slot // local_q) for slot, _ in local],
                             [(-1) ** index for index in range(width)])
            self.assertEqual((-1) ** (local[0][0] // local_q), 1)
            self.assertEqual((-1) ** (local[-1][0] // local_q), -1)
            lane_counts = Counter(node[2] for node in path)
            self.assertEqual(len(lane_counts), lanes_per_child)
            self.assertEqual(set(lane_counts.values()), {pp * local_layers})
            cohort_start = min(lane_counts) // lanes_per_child * lanes_per_child
            self.assertEqual(set(lane_counts), set(range(
                cohort_start, cohort_start + lanes_per_child)))
            for offset in range(0, width, local_layers):
                order = (list(range(local_layers)) if local[offset][1] == 0
                         else list(range(local_layers - 1, -1, -1)))
                self.assertEqual([layer for _, layer in
                                  local[offset:offset + local_layers]], order)
            previous_ds, previous_dl = None, None
            for index, (left, right) in enumerate(zip(local, local[1:])):
                ds = (right[0] - left[0]) % winding.num_slots
                ds = ds if 2 * ds < winding.num_slots else ds - winding.num_slots
                dl = right[1] - left[1]
                self.assertNotEqual(ds, 0)
                self.assertLessEqual(
                    abs((left[0] + ds) // tau - left[0] // tau), 1)
                if (index + 1) % local_layers == 0:
                    self.assertEqual(index % 2, 1)  # Boundary returns are I.
                    self.assertEqual(dl, 0)
                    self.assertIn(left[1], (0, local_layers - 1))
                    previous_ds, previous_dl = None, None
                else:
                    self.assertEqual(abs(dl), 1)
                    if previous_ds is not None:
                        self.assertEqual(dl, previous_dl)
                        self.assertLess(ds * previous_ds, 0)
                    previous_ds, previous_dl = ds, dl
                if index % 2 == 0:  # Insert-side terminals give first edge W.
                    self.assertEqual(abs(dl), 1)
                    self.assertEqual(abs(ds), tau)
                    pair = (set_index, tuple(sorted((left[1], right[1]))))
                    weld_directions.setdefault(pair, set()).add(
                        1 if ds * dl > 0 else -1)
                    child_welds[(tuple(path[index][:2]),
                                 tuple(path[index + 1][:2]))] += 1
            recorded = getattr(database, 'signed_travel', {}).get(branch_id)
            if recorded is not None:
                self.assertEqual(len(recorded), width - 1)
                for step, (left, right) in zip(recorded, zip(path, path[1:])):
                    self.assertEqual((left[0] + step) % winding.num_slots,
                                     right[0])
        self.assertEqual(child_welds, source_welds)
        self.assertEqual(counts, Counter({phase: 2 * Q for phase in range(phases)}))
        self.assertTrue(all(len(values) == 1
                            for values in weld_directions.values()))
        report = database.layout_report
        self.assertTrue(report['layout_retained'])
        self.assertEqual(report['pattern_identity']['status'], 'valid')
        self.assertFalse(set(report['errors']) - gw.EMF_ASYMMETRY_ERRORS)
        return winding, tp, layout, database

    def test_native_proper_q_p2_reuses_complete_full_q_parent_blocks(self):
        for case in ((4, 4, 4, 3, 2), (6, 2, 4, 5, 2), (6, 2, 4, 5, 3)):
            with self.subTest(case=case):
                self.assert_public_full_q_p2_regroup(*case)

    def test_phase_array_uses_its_two_layer_local_full_q_parents(self):
        self.assert_public_full_q_p2_regroup(4, 4, 4, 6, 2)

    def test_phase_only_shifts_commute_with_complete_block_regroup(self):
        _, _, _, database = self.assert_public_full_q_p2_regroup(
            4, 4, 4, 3, 2, shifts=(0, 1, -2, 7))
        self.assertEqual(database.layout_report['post_connection_shift']
                         ['connection_validation'], 'before shift')

    def test_odd_pass_parent_boundary_and_existing_p2_routes_are_preserved(self):
        winding, tp, layout = _inputs('SLP', 4, 3, 4, 3, (2, 1, 2))
        decision = gw.resolve_pattern_route(
            'SLP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.route_name, 'slp_p2_belt_pass_partition')
        self.assertFalse(gw.supports_slp_q_pp_p2_parent_cut(winding, (2, 1, 2)))
        _, database = gw.get_winding_layout('SLP', tp, winding, layout)
        self.assertTrue(database.layout_report['layout_retained'])
        self.assertEqual(database.layout_report['pattern_identity']['status'], 'valid')
        winding.ab, winding.branch_dividers = 8, (4, 1, 2)
        _, database = gw.get_winding_layout('SLP', tp, winding, layout)
        self.assertTrue(database.layout_report['layout_retained'])
        self.assertEqual(database.layout_report['pattern_route']['route_name'],
                         'slp_p2_belt_pass_partition')

        for factors, route in (((4, 1, 2), 'slp_full_q_p2'),
                               ((2, 2, 2), 'slp_q_pp_p2_parent_cut')):
            with self.subTest(factors=factors):
                winding, tp, layout = _inputs('SLP', 4, 4, 4, 3, factors)
                decision = gw.resolve_pattern_route(
                    'SLP', winding, factors, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                self.assertEqual(decision.route_name, route)
                _, database = gw.get_winding_layout('SLP', tp, winding, layout)
                self.assertTrue(database.layout_report['layout_retained'])


class ZppActualLaneEndpointGcdPartitionTests(unittest.TestCase):
    def actual_lane_oracle(self, q, pp, layers, phases, factors, shifts):
        """Permute actual endpoint lanes, then cut gcd-derived cohorts."""
        Q, D, P2 = factors
        sets = phases // 3 if phases > 3 and phases % 3 == 0 else 1
        local_q, local_layers = q * sets, layers // sets
        local_phases = 3 if sets > 1 else phases
        A = Q * D * P2
        g = math.gcd(local_q, A)
        lanes_per_cohort, cuts = local_q // g, A // g
        width = 2 * local_q * pp * local_layers // A
        slots, tau = 2 * q * pp * phases, local_q * local_phases
        self.assertEqual(2 * local_q * pp * local_layers % A, 0)
        self.assertEqual(width % 2, 0)
        expected = []
        for set_index in range(sets):
            winding, tp, layout = _inputs(
                'ZPP', local_q, pp, local_layers, local_phases,
                (local_q, 1, 1))
            _, parents = gw.get_winding_layout('ZPP', tp, winding, layout)
            by_phase = {phase: [] for phase in range(local_phases)}
            for _, path in parents:
                self.assertEqual(len(path), 2 * pp * local_layers)
                by_phase[path[0][0] // local_q % local_phases].append(path)
            for source_paths in by_phase.values():
                self.assertEqual(len(source_paths), local_q)
                cohorts = [[] for _ in range(g)]
                for pair in range(local_layers // 2):
                    segments = [path[pair * 4 * pp:(pair + 1) * 4 * pp]
                                for path in source_paths]
                    starts = {path[0][0] % local_q: path for path in segments}
                    ends = {path[-1][0] % local_q: path[-1]
                            for path in segments}
                    self.assertEqual(set(starts), set(range(local_q)))
                    self.assertEqual(set(ends), set(range(local_q)))
                    self.assertEqual({path[0][1] for path in segments}, {2 * pair})
                    self.assertEqual({path[-1][1] for path in segments},
                                     {2 * pair + 1})
                    start_bases = {(path[0][0] - path[0][0] % local_q) % slots
                                   for path in segments}
                    end_bases = {(node[0] - node[0] % local_q - tau) % slots
                                 for node in ends.values()}
                    self.assertEqual(len(start_bases), 1)
                    self.assertEqual(start_bases, end_bases)
                    for cohort in range(g):
                        lanes = list(range(cohort * lanes_per_cohort,
                                           (cohort + 1) * lanes_per_cohort))
                        for index, lane in enumerate(lanes):
                            next_lane = lanes[(index + 1) % lanes_per_cohort]
                            cohorts[cohort].extend(starts[lane][:-1])
                            cohorts[cohort].append(ends[next_lane])
                source_positions = Counter(tuple(node[:2])
                                           for path in source_paths for node in path)
                self.assertEqual(Counter(tuple(node[:2])
                                         for path in cohorts for node in path),
                                 source_positions)
                for cohort in cohorts:
                    self.assertEqual(len(cohort), cuts * width)
                    for cut in range(cuts):
                        child = list(cohort[cut * width:(cut + 1) * width])
                        if P2 == 2 and (-1) ** (child[0][0] // local_q) < 0:
                            child.reverse()
                        global_path = []
                        for slot, layer, *rest in child:
                            global_layer = layer + set_index * local_layers
                            offset = 2 * q * set_index if sets > 1 else 0
                            global_path.append(((slot + offset + shifts[global_layer])
                                                % slots, global_layer, *rest))
                        expected.append(global_path)
        return expected

    def assert_zpp_geometry(self, paths, q, pp, layers, phases, factors, shifts):
        Q, D, P2 = factors
        A = Q * D * P2
        sets = phases // 3 if phases > 3 and phases % 3 == 0 else 1
        local_q, local_layers = q * sets, layers // sets
        local_phases = 3 if sets > 1 else phases
        slots, tau = 2 * q * pp * phases, local_q * local_phases
        width = 2 * q * pp * layers // A
        self.assertEqual(len(paths), A * phases)
        positions = [tuple(node[:2]) for path in paths for node in path]
        self.assertEqual(len(positions), len(set(positions)))
        self.assertEqual(set(positions), {(slot, layer) for slot in range(slots)
                                         for layer in range(layers)})
        counts, weld_directions = Counter(), {}
        for path in paths:
            self.assertEqual(len(path), width)
            set_index = path[0][1] // local_layers if sets > 1 else 0
            self.assertTrue(all(node[1] // local_layers == set_index for node in path))
            offset = 2 * q * set_index if sets > 1 else 0
            local = [((slot - offset - shifts[layer]) % slots,
                      layer - set_index * local_layers)
                     for slot, layer, *_ in path]
            phase = local[0][0] // local_q % local_phases
            counts[set_index * local_phases + phase] += 1
            self.assertEqual({slot // local_q % local_phases for slot, _ in local},
                             {phase})
            signs = [(-1) ** (slot // local_q) for slot, _ in local]
            self.assertEqual(signs, [signs[0] * (-1) ** index
                                     for index in range(width)])
            if P2 == 2:
                self.assertEqual((signs[0], signs[-1]), (1, -1))
            insert_directions = set()
            for index, (left, right) in enumerate(zip(local, local[1:])):
                ds = (right[0] - left[0]) % slots
                ds = ds if 2 * ds < slots else ds - slots
                dl = right[1] - left[1]
                self.assertNotEqual(ds, 0)
                self.assertLess(abs(ds), slots / 2)
                self.assertLessEqual(abs((left[0] + ds) // tau - left[0] // tau), 1)
                if index % 2 == 0:  # Weld-side terminals give first edge I.
                    self.assertEqual(dl, 0)
                    insert_directions.add(1 if ds > 0 else -1)
                else:
                    self.assertEqual(abs(dl), 1)
                    self.assertEqual(abs(ds), tau)
                    pair = tuple(sorted((path[index][1], path[index + 1][1])))
                    weld_directions.setdefault(pair, set()).add(
                        1 if ds * dl > 0 else -1)
            self.assertEqual(len(insert_directions), 1)
        self.assertEqual(counts, Counter({phase: A for phase in range(phases)}))
        self.assertTrue(all(len(values) == 1 for values in weld_directions.values()))

    def assert_public_actual_lane_partition(self, q, pp, layers, phases, factors,
                                            shifts=None):
        shifts = list(shifts) if shifts is not None else [0] * layers
        expected = self.actual_lane_oracle(q, pp, layers, phases, factors, shifts)
        self.assert_zpp_geometry(expected, q, pp, layers, phases, factors, shifts)
        winding, tp, layout = _inputs('ZPP', q, pp, layers, phases, factors)
        layout.phase_shift_list = shifts
        decision = gw.resolve_pattern_route('ZPP', winding, factors, tp, layout)
        self.assertEqual(decision.status, 'enabled', decision.reason)
        self.assertEqual(decision.route_name, 'zpp_actual_lane_endpoint_gcd_partition')
        self.assertEqual(decision.required_inlet, 'weld')
        starts, database = gw.get_winding_layout('ZPP', tp, winding, layout)
        self.assertEqual([path for _, path in database], expected)
        self.assertEqual(starts, [path[0] for path in expected])
        self.assert_zpp_geometry([path for _, path in database], q, pp, layers,
                                 phases, factors, shifts)
        recorded = getattr(database, 'signed_travel', None)
        if recorded is not None:
            self.assertEqual(set(recorded), {branch_id for branch_id, _ in database})
            for branch_id, path in database:
                self.assertEqual(len(recorded[branch_id]), len(path) - 1)
                for step, (left, right) in zip(recorded[branch_id], zip(path, path[1:])):
                    self.assertIs(type(step), int)
                    self.assertEqual((left[0] + step) % winding.num_slots, right[0])
        report = database.layout_report
        self.assertTrue(report['layout_retained'])
        self.assertEqual(report['pattern_identity']['status'], 'valid')
        self.assertFalse(set(report['errors']) - gw.EMF_ASYMMETRY_ERRORS)
        return database

    def test_actual_end_lane_lookup_handles_terminal_lane_shift(self):
        self.assertNotEqual(2 * 3 % 4, 0)
        database = self.assert_public_actual_lane_partition(4, 3, 4, 3, (2, 1, 1))
        self.assertEqual([tuple(node[:2]) for node in database[0][1][10:13]],
                         [(1, 1), (13, 1), (1, 0)])

    def test_coprime_gcd_cohort_is_partitioned_into_equal_branches(self):
        self.assertEqual(math.gcd(5, 3), 1)
        for case in ((5, 3, 6, 7, (1, 3, 1)),
                     (4, 4, 4, 3, (2, 2, 1))):
            with self.subTest(case=case):
                self.assert_public_actual_lane_partition(*case)

    def test_p2_short_children_all_run_from_n_to_s(self):
        database = self.assert_public_actual_lane_partition(2, 4, 4, 3, (2, 2, 2))
        self.assertEqual({len(path) for _, path in database}, {8})

    def test_phase_array_lifts_two_layer_local_candidates(self):
        for case in ((2, 3, 4, 6, (2, 1, 1)),
                     (2, 6, 8, 6, (1, 3, 1))):
            with self.subTest(case=case):
                self.assert_public_actual_lane_partition(*case)

    def test_phase_only_shifts_commute_with_endpoint_permutation_and_cuts(self):
        database = self.assert_public_actual_lane_partition(
            4, 3, 4, 3, (2, 1, 1), shifts=(0, 1, -2, 7))
        self.assertEqual(database.layout_report['post_connection_shift']
                         ['connection_validation'], 'before shift')

    def test_selected_domain_upper_bounds_and_minimum_child_width(self):
        for case in ((6, 8, 12, 13, (2, 8, 2)),
                     (6, 8, 8, 12, (24, 8, 2))):
            with self.subTest(case=case):
                self.assert_public_actual_lane_partition(*case)

    def test_configured_parent_signed_evidence_rejects_corruption_without_short_arc_fallback(self):
        winding, tp, layout = _inputs('ZPP', 4, 3, 4, 3, (2, 1, 1))
        parent_winding, parent_tp, parent_layout = _inputs(
            'ZPP', 4, 3, 4, 3, (4, 1, 1))
        _, parents = gw.get_winding_layout('ZPP', parent_tp, parent_winding, parent_layout)
        travel = {}
        for branch_id, path in parents:
            steps = []
            for left, right in zip(path, path[1:]):
                ds = (right[0] - left[0]) % winding.num_slots
                ds = ds if 2 * ds < winding.num_slots else ds - winding.num_slots
                self.assertLess(2 * abs(ds), winding.num_slots)
                self.assertNotEqual(ds, 0)
                steps.append(ds)
            travel[branch_id] = tuple(steps)
        expected = self.actual_lane_oracle(4, 3, 4, 3, (2, 1, 1), [0] * 4)

        for corruption in ('absent', 'complete', 'none', 'missing_branch',
                           'extra_branch', 'none_steps', 'short_steps',
                           'long_steps', 'extra_turn'):
            with self.subTest(parent_evidence=corruption):
                source = gw._CandidateBranches(deepcopy(list(parents)))
                branch_id = source[0][0]
                if corruption != 'absent':
                    source.signed_travel = dict(travel)
                    if corruption == 'none':
                        source.signed_travel = None
                    elif corruption == 'missing_branch':
                        source.signed_travel.pop(branch_id)
                    elif corruption == 'extra_branch':
                        source.signed_travel[max(travel) + 1] = travel[branch_id]
                    elif corruption == 'none_steps':
                        source.signed_travel[branch_id] = None
                    elif corruption == 'short_steps':
                        source.signed_travel[branch_id] = travel[branch_id][:-1]
                    elif corruption == 'long_steps':
                        source.signed_travel[branch_id] = (*travel[branch_id], 1)
                    elif corruption == 'extra_turn':
                        steps = travel[branch_id]
                        source.signed_travel[branch_id] = (
                            steps[0] + winding.num_slots, *steps[1:])
                else:
                    self.assertFalse(hasattr(source, 'signed_travel'))

                def injected_configured_parent(pattern, config, current, selected_layout):
                    self.assertEqual(pattern, 'ZPP')
                    self.assertIs(config, tp)
                    self.assertIs(selected_layout, layout)
                    self.assertEqual(current.branch_dividers, (4, 1, 1))
                    return [path[0] for _, path in source], source

                # Inject only the actual public parent; execute the target helper
                # and its formula and validators without replacements.
                with patch.object(gw, 'get_winding_layout',
                                  side_effect=injected_configured_parent) as fetch:
                    if corruption in ('absent', 'complete'):
                        starts, database = gw._zpp_actual_lane_endpoint_partition_from_reference(
                            tp, winding, layout)
                        self.assertEqual([path for _, path in database], expected)
                        self.assertEqual(starts, [path[0] for path in expected])
                        self.assertEqual(set(database.signed_travel),
                                         {bid for bid, _ in database})
                    else:
                        with self.assertRaises(ValueError):
                            gw._zpp_actual_lane_endpoint_partition_from_reference(
                                tp, winding, layout)
                    fetch.assert_called_once()

    def test_global_signed_metadata_precedes_array_projection_and_actual_weld_pitch_is_required(self):
        winding, tp, layout = _inputs('ZPP', 2, 6, 8, 6, (1, 3, 1))
        decision = gw.resolve_pattern_route('ZPP', winding, winding.branch_dividers, tp, layout)
        _, baseline = gw.get_winding_layout('ZPP', tp, winding, layout)
        self.assertEqual({item['route_name'] for item in baseline.phase_set_array['routes']},
                         {'zpp_actual_lane_endpoint_gcd_partition'})
        self.assertEqual(set(baseline.signed_travel), {bid for bid, _ in baseline})
        gw._validate_route_connections('ZPP', decision, baseline, winding, layout)
        for corruption in ('absent', 'none', 'missing_branch', 'extra_branch', 'none_steps'):
            with self.subTest(global_evidence=corruption):
                database = deepcopy(baseline)
                branch_id = database[0][0]
                if corruption == 'absent':
                    del database.signed_travel
                elif corruption == 'none':
                    database.signed_travel = None
                elif corruption == 'missing_branch':
                    database.signed_travel.pop(branch_id)
                elif corruption == 'extra_branch':
                    database.signed_travel[max(database.signed_travel) + 1] = (
                        database.signed_travel[branch_id])
                else:
                    database.signed_travel[branch_id] = None
                with patch.object(gw, '_three_phase_set_views',
                                  wraps=gw._three_phase_set_views) as project:
                    with self.assertRaises(ValueError):
                        gw._validate_route_connections('ZPP', decision, database, winding, layout)
                    project.assert_not_called()

        winding, tp, layout = _inputs('ZPP', 4, 3, 4, 3, (2, 1, 1))
        _, database = gw.get_winding_layout('ZPP', tp, winding, layout)
        before = Counter(tuple(node[:2]) for _, path in database for node in path)
        left, right = database[0][1], database[1][1]
        self.assertEqual(left[2][1], right[2][1])
        self.assertEqual(left[2][0] // 4, right[2][0] // 4)
        left[2], right[2] = right[2], left[2]
        self.assertEqual(Counter(tuple(node[:2]) for _, path in database for node in path), before)
        for branch_id, path in database:
            steps = []
            for start, end in zip(path, path[1:]):
                ds = (end[0] - start[0]) % winding.num_slots
                steps.append(ds if 2 * ds < winding.num_slots else ds - winding.num_slots)
            database.signed_travel[branch_id] = tuple(steps)
        tau = winding.num_phases * winding.q
        self.assertEqual(abs(left[2][1] - left[1][1]), 1)
        self.assertNotEqual(abs(database.signed_travel[database[0][0]][1]), tau)
        # Coverage, phase/sign and signed one-region travel remain valid;
        # the endpoint-route weld-pitch check must reject the physical swap.
        gw.validate_selected_zpp(database, winding, layout)
        with self.assertRaisesRegex(ValueError, 'welds of pitch tau'):
            gw.validate_zpp_actual_lane_endpoint_partition(database, winding, layout)

    def test_existing_routes_exclusions_and_configured_parent_failure_are_preserved(self):
        for q, pp, layers, phases, factors, reason in (
                (4, 4, 4, 3, (2, 1, 2), 'q and p2 share same route'),
                (3, 4, 4, 3, (1, 2, 2), 'odd positive integer effective q'),
                (1, 4, 6, 9, (1, 2, 2), 'odd positive integer effective q')):
            with self.subTest(excluded=(q, pp, layers, phases, factors)):
                winding, tp, layout = _inputs('ZPP', q, pp, layers, phases, factors)
                decision = gw.resolve_pattern_route('ZPP', winding, factors, tp, layout)
                self.assertEqual(decision.status, 'disabled')
                self.assertIn(reason, decision.reason)
                with self.assertRaises(ValueError):
                    gw.get_winding_layout('ZPP', tp, winding, layout)
        for q, pp, factors, route in ((4, 3, (4, 1, 1), None),
                                      (2, 4, (1, 2, 1), 'zpp_pp_only_half_turn')):
            with self.subTest(existing=(q, pp, factors)):
                winding, tp, layout = _inputs('ZPP', q, pp, 4, 3, factors)
                decision = gw.resolve_pattern_route('ZPP', winding, factors, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                self.assertEqual(decision.route_name, route)
                _, database = gw.get_winding_layout('ZPP', tp, winding, layout)
                self.assertTrue(database.layout_report['layout_retained'])

        half, half_tp, half_layout = _inputs('ZPP', Fraction(3, 2), 6, 8, 6, (1, 3, 1))
        half_decision = gw.resolve_pattern_route('ZPP', half, (1, 3, 1), half_tp, half_layout)
        self.assertEqual(half_decision.route_name, 'zpp_pp_only_indexed_translation')
        _, half_database = gw.get_winding_layout('ZPP', half_tp, half, half_layout)
        self.assertTrue(half_database.layout_report['layout_retained'])

        q, pp, layers = 4, 3, 4
        parent_width = 2 * pp * layers
        target_width = 2 * q * pp * layers // 2
        self.assertLessEqual(parent_width, target_width - 1)
        for factors in ((q, 1, 1), (2, 1, 1)):
            with self.subTest(configured_parent=factors):
                winding, tp, layout = _inputs('ZPP', q, pp, layers, 3, factors)
                tp.tp_type, tp.tp_times = 'Times', parent_width
                with self.assertRaisesRegex(ValueError, f'tp_times <= {parent_width - 1}'):
                    gw.get_winding_layout('ZPP', tp, winding, layout)
                self.assertEqual(tp.tp_times, parent_width)


class UwpAdjacentWeldExclusionTests(unittest.TestCase):
    def test_workbench_rejected_series_requests_never_enter_auto_probe(self):
        import pattern_rule_workbench as workbench
        workbench.build_divider_route_catalog.cache_clear()
        with (patch.object(workbench, 'PATTERNS', ('UWP',)),
              patch.object(workbench, '_probe_route', return_value=(
                  False, 'Generation deliberately omitted in this rejection check.')) as probe):
            rows = workbench.build_divider_route_catalog('4', 4, 4)
        for row in rows:
            if row.dividers[1:] == (1, 1):
                self.assertEqual(row.status, 'rejected')
                self.assertIn('same as BWP' if row.dividers[0] == 4
                              else 'same-layer', row.reason)
        self.assertTrue(probe.called)
        self.assertTrue(all(call.args[5][1:] != (1, 1)
                            for call in probe.call_args_list))
        workbench.build_divider_route_catalog.cache_clear()

    def test_local_factor_reason_and_implicit_p2_choice_remain_distinct(self):
        for q, pp, layers, phases, factors, reason in (
                (1, 2, 2, 3, (1, 1, 1), 'same-layer'),
                (1, 2, 4, 3, (1, 1, 1), 'same-layer'),
                (2, 3, 6, 9, (3, 1, 1), 'same-layer'),
                (Fraction(3, 2), 2, 4, 6, (1, 1, 1), 'same-layer'),
                (2, 3, 6, 9, (6, 1, 1), 'same as BWP'),
                (4, 4, 4, 3, (2, 2, 2), 'product must be 1 or 2')):
            with self.subTest(q=q, m=phases, factors=factors):
                w, tp, layout = _inputs('UWP', q, pp, layers, phases, factors)
                d = gw.resolve_pattern_route('UWP', w, configuration=tp, layout=layout)
                self.assertEqual(d.admission, 'rejected', d.reason)
                self.assertIn(reason, d.reason)
        w, tp, layout = _inputs('UWP', 4, 4, 4, 3, (2, 1, 1))
        self.assertEqual(gw.resolve_pattern_route('UWP', w).admission, 'rejected')
        w.branch_dividers = None
        d = gw.resolve_pattern_route('UWP', w, configuration=tp, layout=layout)
        self.assertEqual(d.dividers, (1, 1, 2))
        self.assertEqual(d.admission, 'supported', d.reason)
        _, db = gw.get_winding_layout('UWP', tp, w, layout)
        self.assertTrue(db.layout_report['layout_retained'])

    def test_no_divider_boundary_requests_are_owner_rejected_before_dispatch(self):
        # These are the five geometry corners containing the earlier six
        # failed/Candidate requests (some q=1 factor corners coincide).
        for q, pp, layers, phases in ((1, 2, 12, 13), (6, 8, 12, 13),
                                      (6, 8, 8, 12), (1, 7, 12, 6),
                                      (1, 3, 12, 9)):
            for implicit in (False, True):
                with self.subTest(q=q, pp=pp, layers=layers, m=phases, implicit=implicit):
                    w, tp, layout = _inputs('UWP', q, pp, layers, phases, (1, 1, 1))
                    if implicit:
                        w.branch_dividers = None
                    decision = gw.resolve_pattern_route('UWP', w, configuration=tp, layout=layout)
                    self.assertEqual(decision.status, 'disabled', decision.reason)
                    self.assertEqual(decision.admission, 'rejected', decision.reason)
                    self.assertIn('same-layer', decision.reason)
                    with patch.object(gw, '_dispatch_winding_pattern') as dispatch:
                        with self.assertRaises(gw.PatternConfigurationError):
                            gw.get_winding_layout('UWP', tp, w, layout, allow_candidate=True)
                        dispatch.assert_not_called()

    def test_proper_q_series_family_is_rejected_for_manual_and_shifted_inputs(self):
        for q, pp, layers, phases, Q in ((4, 4, 4, 3, 2), (6, 3, 6, 5, 3),
                                         (2, 4, 4, 6, 2), (6, 8, 8, 12, 12)):
            for mode in ('Regular', 'Times', 'Interval'):
                with self.subTest(q=q, m=phases, Q=Q, mode=mode):
                    w, tp, layout = _inputs('UWP', q, pp, layers, phases, (Q, 1, 1))
                    tp.tp_type = mode
                    tp.tp_times = tp.tp_interval = 1 if mode != 'Regular' else 0
                    tp.uni_tp = 1
                    layout.phase_shift_list = [1]*layers
                    d = gw.resolve_pattern_route('UWP', w, configuration=tp, layout=layout)
                    self.assertEqual(d.admission, 'rejected', d.reason)
                    self.assertIsNone(gw.selected_integer_divider_route('UWP', w))
                    with self.assertRaises(gw.PatternConfigurationError):
                        gw.get_winding_layout('UWP', tp, w, layout)

    def test_adjacent_p2_and_pp_routes_keep_public_coverage_and_identity(self):
        for q, pp, layers, phases, factors in (
                (1, 2, 4, 5, (1, 1, 2)), (4, 4, 6, 3, (1, 1, 2)),
                (6, 3, 4, 5, (3, 1, 2)), (2, 4, 4, 6, (2, 2, 1))):
            with self.subTest(q=q, pp=pp, m=phases, factors=factors):
                w, tp, layout = _inputs('UWP', q, pp, layers, phases, factors)
                _, db = gw.get_winding_layout('UWP', tp, w, layout)
                self.assertEqual(Counter(tuple(n[:2]) for _, path in db for n in path),
                                 Counter({(s, l): 1 for s in range(w.num_slots)
                                          for l in range(layers)}))
                self.assertFalse(getattr(db, 'series_connections', ()))
                self.assertTrue(db.layout_report['layout_retained'])
                self.assertEqual(db.layout_report['pattern_identity']['status'], 'valid')


if __name__ == '__main__':
    unittest.main()
