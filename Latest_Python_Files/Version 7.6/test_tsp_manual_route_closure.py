"""Independent acceptance checks for the regular TSP manual-route family."""
from collections import Counter
from copy import deepcopy
from fractions import Fraction
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import get_winding_pattern as gw
from explicit_connections import EMF_ASYMMETRY_ERRORS
from phase_topology import phase_map
from pattern_rule_workbench import (
    DividerRouteCatalog, _base_inputs, build_divider_route_catalog)


MANUAL_FACTORS = ((1, 2, 1), (2, 1, 1), (1, 2, 2),
                  (2, 2, 2), (2, 4, 1))


class TspManualRouteClosureTests(unittest.TestCase):
    def test_regular_tsp_rejects_every_branch_shorter_than_eight_conductors(self):
        for q, pp, layers, factors, phases in (
                (2, 4, 4, (2, 4, 2), 3),
                (2, 4, 4, (2, 4, 2), 6),
                (2, 4, 2, (2, 2, 1), 5),
                (3, 6, 2, (1, 6, 2), 7),
                (2, 4, 4, (2, 2, 1), 3)):
            naa = factors[0] * factors[1] * factors[2]
            branch_length = 2 * q * pp * layers // naa
            with self.subTest(q=q, pp=pp, layers=layers, factors=factors):
                winding, tp, layout = _base_inputs(
                    'TSP', q, 2 * pp, layers, naa, factors, phases)
                decision = gw.resolve_pattern_route(
                    'TSP', winding, factors, tp, layout)
                if branch_length < 8:
                    self.assertEqual(decision.admission, 'rejected')
                    self.assertIn(str(branch_length), decision.reason)
                    self.assertIn('8', decision.reason)
                else:
                    self.assertEqual(decision.admission, 'supported', decision.reason)

    def test_every_enumerated_integer_tsp_tuple_uses_eight_conductor_floor(self):
        for q in range(1, 7):
            for pp in range(1, 9):
                for layers in (2, 4, 6, 8):
                    for q_divider in range(1, q + 1):
                        if q % q_divider:
                            continue
                        for pp_divider in range(1, pp + 1):
                            if pp % pp_divider:
                                continue
                            for p2_divider in (1, 2):
                                factors = (q_divider, pp_divider, p2_divider)
                                naa = q_divider * pp_divider * p2_divider
                                branch_length = Fraction(2 * q * pp * layers, naa)
                                self.assertEqual(
                                    gw.pattern_rejects_divider_tuple(
                                        'TSP', factors, q, pp, layers),
                                    branch_length < 8,
                                    (q, pp, layers, factors))

    def assert_public_layout(self, q, pp, layers, phases, factors):
        naa = factors[0] * factors[1] * factors[2]
        winding, tp, layout = _base_inputs(
            'TSP', q, 2 * pp, layers, naa, factors, phases)
        decision = gw.resolve_pattern_route(
            'TSP', winding, factors, tp, layout)
        self.assertEqual(decision.admission, 'supported', decision.reason)
        starts, database = gw.get_winding_layout('TSP', tp, winding, layout)
        report = database.layout_report
        self.assertTrue(report['layout_retained'])
        self.assertEqual(report['pattern_identity']['status'], 'valid')
        self.assertFalse(set(report['errors']) - EMF_ASYMMETRY_ERRORS,
                         report['errors'])
        self.assertEqual(starts, [path[0] for _, path in database])
        self.assertEqual(len(database), naa * phases)
        self.assertEqual({len(path) for _, path in database},
                         {2 * q * pp * layers // naa})
        occupancy = Counter(node[:2] for _, path in database for node in path)
        self.assertEqual(occupancy, Counter({
            (slot, layer): 1 for slot in range(winding.num_slots)
            for layer in range(layers)}))
        signs = {(s, l): (ph, sign) for s, l, ph, sign in phase_map(
            winding.num_slots, 2 * pp, layers, [0] * layers, phases)}
        counts = Counter()
        for _, path in database:
            phase, sign = signs[path[0][:2]]
            self.assertEqual(sign, 1)
            self.assertEqual(signs[path[-1][:2]], (phase, -1))
            self.assertEqual({signs[n[:2]][0] for n in path}, {phase})
            self.assertTrue(all(signs[n[:2]][1] == (-1) ** i
                                for i, n in enumerate(path)))
            counts[phase] += 1
        self.assertEqual(counts, Counter({phase: naa for phase in range(phases)}))
        return winding, layout, database

    def test_all_five_saved_unsupported_routes_generate_publicly(self):
        for factors in MANUAL_FACTORS:
            with self.subTest(factors=factors):
                self.assert_public_layout(2, 4, 4, 3, factors)

    def test_native_odd_phases_and_layer_assigned_arrays(self):
        for phases, layers in ((5, 4), (7, 6), (6, 8), (9, 12), (12, 16)):
            for factors in MANUAL_FACTORS:
                with self.subTest(phases=phases, layers=layers, factors=factors):
                    self.assert_public_layout(2, 4, layers, phases, factors)

    def test_parameterized_proper_q_and_two_layer_cases(self):
        cases = ((4, 6, 2, 3, (2, 3, 2)),
                 (6, 8, 6, 5, (2, 4, 2)),
                 (3, 6, 8, 7, (1, 2, 1)),
                 (6, 9, 4, 3, (2, 3, 1)),
                 (1, 6, 4, 3, (1, 2, 1)))
        for case in cases:
            with self.subTest(case=case):
                self.assert_public_layout(*case)

    def test_existing_supported_constructor_precedence_is_preserved(self):
        for factors, expected in (
                ((1, 1, 2), 'tsp_default'),
                ((2, 1, 2), 'tsp_default'),
                ((2, 2, 1), 'tsp_q_pp_two'),
                ((1, 4, 1), 'tsp_pp_only_q_p2_identity'),
                ((1, 4, 2), 'tsp_pp_p2_sector')):
            winding, tp, layout = _base_inputs(
                'TSP', 2, 8, 4, factors[0] * factors[1] * factors[2], factors)
            decision = gw.resolve_pattern_route('TSP', winding, factors, tp, layout)
            self.assertEqual(decision.rule_id, expected)

    def test_new_constructor_requires_two_passes_and_regular_configuration(self):
        for q, pp, layers, factors in (
                (2, 4, 4, (2, 4, 2)), (1, 2, 2, (1, 2, 2)),
                (2, 4, 3, (1, 2, 1))):
            winding, tp, layout = _base_inputs(
                'TSP', q, 2 * pp, layers,
                factors[0] * factors[1] * factors[2], factors)
            self.assertFalse(gw.supports_integer_tsp_spiral_pass_partition(
                winding, factors))
        winding, tp, layout = _base_inputs('TSP', 2, 8, 4, 2, (1, 2, 1))
        for field, value in (('uni_tp', 1), ('jltp', 1)):
            changed = deepcopy(tp)
            setattr(changed, field, value)
            self.assertEqual(gw.resolve_pattern_route(
                'TSP', winding, winding.branch_dividers, changed, layout).admission,
                'rejected')
        layout.phase_shift_list[1] = 1
        self.assertEqual(gw.resolve_pattern_route(
            'TSP', winding, winding.branch_dividers, tp, layout).admission, 'rejected')

    def test_validator_detects_wrong_travel_and_broken_body(self):
        winding, layout, database = self.assert_public_layout(2, 4, 4, 3, (1, 2, 1))
        bad = deepcopy(database)
        branch_id = bad[0][0]
        travel = list(bad.signed_travel[branch_id])
        travel[3] += winding.num_slots
        bad.signed_travel[branch_id] = tuple(travel)
        with self.assertRaisesRegex(ValueError, 'pole.region|signed travel'):
            gw.validate_tsp_spiral_pass_partition(bad, winding, layout)
        bad = deepcopy(database)
        bad[0][1][1], bad[0][1][2] = bad[0][1][2], bad[0][1][1]
        with self.assertRaisesRegex(ValueError, 'spiral pass|body|phase'):
            gw.validate_tsp_spiral_pass_partition(bad, winding, layout)

    def test_integer_scope_does_not_expand_fractional_global_q_arrays(self):
        for q in (Fraction(1, 2), Fraction(3, 2)):
            winding, tp, layout = _base_inputs('TSP', q, 8, 8, 2, (1, 2, 1), 6)
            decision = gw.resolve_pattern_route('TSP', winding, (1, 2, 1), tp, layout)
            self.assertEqual(decision.admission, 'unsupported-yet')
            self.assertIn('integer global q', decision.reason)
            with self.assertRaises(gw.PatternConfigurationError):
                gw.get_winding_layout('TSP', tp, winding, layout)

    def test_workbench_closes_five_rows_from_public_generation(self):
        build_divider_route_catalog.cache_clear()
        with patch('pattern_rule_workbench.PATTERNS', ('TSP',)):
            records = build_divider_route_catalog('2', 4, 4)
        try:
            rows = {row.dividers: row for row in records}
            for factors in MANUAL_FACTORS:
                self.assertIn(rows[factors].status,
                              ('Validated', 'not strong symmetry layout'),
                              rows[factors].reason)
        finally:
            build_divider_route_catalog.cache_clear()

    def test_saved_four_tsp_routes_display_production_symmetry_status(self):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        build_divider_route_catalog.cache_clear()
        with patch('pattern_rule_workbench.PATTERNS', ('TSP',)):
            catalog = DividerRouteCatalog(lambda _record: None)
            try:
                factors_list = ((1, 2, 2), (1, 4, 2),
                                (2, 2, 2), (2, 4, 1))
                rows = {row.dividers: row for row in catalog.records}
                for factors in factors_list:
                    record = rows[factors]
                    self.assertEqual(record.status, 'not strong symmetry layout')
                    catalog.saved_routes[catalog._route_key(record)] = (
                        Path('saved-manual-route.json'), 'configured')
                catalog.refresh()
                for factors in factors_list:
                    record = rows[factors]
                    key = catalog._route_key(record)
                    row = catalog.records.index(record)
                    item = catalog.table.item(row, 7)
                    self.assertEqual(
                        catalog.status_widgets[key][0].text(),
                        'not strong symmetry layout')
                    self.assertEqual(item.data(Qt.ItemDataRole.UserRole),
                                     'not strong symmetry layout')
                    self.assertIn('Saved manual configure', item.toolTip())
                    catalog.mark_saved(record, Path('saved-manual-route.json'),
                                       'configured')
                    self.assertEqual(
                        catalog.status_widgets[key][0].text(),
                        'not strong symmetry layout')
            finally:
                catalog.close()
                build_divider_route_catalog.cache_clear()


if __name__ == '__main__':
    unittest.main()
