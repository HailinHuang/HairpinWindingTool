"""Unit tests for the shared top-level Auto transposition policy."""
import unittest
from fractions import Fraction
from types import SimpleNamespace

import automatic_transposition as auto_tp


class AutomaticTranspositionTests(unittest.TestCase):
    def test_weld_side_contract_preserves_physical_edges_and_uniform_direction(self):
        layout = SimpleNamespace(inlet_from_weld_side=0, phase_shift_list=[0, 0])
        reference = [[1, [(0, 0, 0), (3, 1, 1), (6, 0, 2), (9, 1, 3)]]]
        equivalent = [[2, [(9, 1, 0), (6, 0, 1), (3, 1, 2), (0, 0, 3)]]]
        changed = [[1, [(0, 0, 0), (4, 1, 1), (6, 0, 2), (9, 1, 3)]]]
        conflicting = [[1, [(0, 0, 0), (3, 1, 1), (9, 0, 2), (6, 1, 3)]]]

        self.assertTrue(auto_tp.weld_side_contract(reference, reference, 12, layout)['valid'])
        self.assertTrue(auto_tp.weld_side_contract(reference, equivalent, 12, layout)['valid'])
        self.assertFalse(auto_tp.weld_side_contract(reference, changed, 12, layout)['preserved'])
        result = auto_tp.weld_side_contract(conflicting, conflicting, 12, layout)
        self.assertFalse(result['uniform'])
        self.assertFalse(result['valid'])
    def test_objectives_default_and_rank_independent_metrics(self):
        self.assertEqual(auto_tp.DEFAULT_AUTO_CONFIGURE_OBJECTIVE, 'min_pin_types')
        self.assertEqual(auto_tp.AUTO_CONFIGURE_OBJECTIVES['min_average_pin_length'],
                         '3. Shortest normalized average pin length')
        metrics = [dict(transposition_count=1, pin_type_count=4,
                        average_pin_length_normalized=3.0, average_pin_length_mm=80),
                   dict(transposition_count=3, pin_type_count=2,
                        average_pin_length_normalized=2.0, average_pin_length_mm=90),
                   dict(transposition_count=5, pin_type_count=3,
                        average_pin_length_normalized=1.0, average_pin_length_mm=100)]
        for objective, expected in zip(auto_tp.AUTO_CONFIGURE_OBJECTIVES, (0, 1, 2)):
            self.assertEqual(min(range(3), key=lambda i: auto_tp.objective_score(metrics[i], objective)),
                             expected)

    def test_length_roundoff_does_not_defeat_manufacturing_tie_breaks(self):
        simpler = dict(transposition_count=12, pin_type_count=6,
                       average_pin_length_normalized=4.10613157984454)
        noisy = dict(transposition_count=180, pin_type_count=9,
                     average_pin_length_normalized=4.10613157984443)
        self.assertLess(auto_tp.objective_score(simpler, 'min_average_pin_length'),
                        auto_tp.objective_score(noisy, 'min_average_pin_length'))

    def test_metrics_use_insertion_shapes_all_branches_and_weighted_length(self):
        winding = SimpleNamespace(q=2, num_slots=24, num_poles=4, num_layers=2)
        layout = SimpleNamespace(inlet_from_weld_side=1, phase_shift_list=[0, 0])
        baseline = [[1, [(0, 0), (6, 1), (12, 0), (18, 1)]]]
        paths = [[1, [(0, 0), (5, 1), (12, 0), (18, 1)]],
                 [2, [(1, 0), (7, 1)]]]
        reference = baseline + [[2, [(1, 0), (7, 1)]]]
        metrics = auto_tp.implementation_metrics(paths, reference, winding, layout,
            pin_length_evaluator=lambda a, b, span, wa, wb: 100 + 10*span)
        self.assertEqual(metrics['pin_count'], 3)
        self.assertEqual(metrics['pin_type_count'], 2)
        self.assertEqual(metrics['transposition_count'], 2)
        self.assertAlmostEqual(metrics['average_pin_length_mm'], (150+160+160)/3)
        self.assertEqual(metrics['length_basis'], 'custom_pin_length_model_mm')
        pole_pitch = winding.num_slots/winding.num_poles
        expected = ((2 + ((5/pole_pitch)**2 + 1)**0.5 + 7/(2*pole_pitch))
                    + (2 + ((6/pole_pitch)**2 + 1)**0.5 + 7/(2*pole_pitch))
                    + (2 + ((6/pole_pitch)**2 + 1)**0.5))/3
        self.assertAlmostEqual(metrics['average_pin_length_normalized'], expected)
        self.assertEqual(metrics['normalized_length_basis'],
                         'slot_and_layer_span_geometry_per_pole_pitch')

    def test_length_adapter_reuses_existing_model_and_adds_both_active_legs(self):
        from unittest.mock import patch
        winding = SimpleNamespace()
        stator = SimpleNamespace(StackLength=100)
        inslot, ew = SimpleNamespace(), SimpleNamespace()
        with patch('end_winding_calc.calculate_end_winding_length',
                   return_value=[0, 0, 0, 25, 0, 35, 60, 0]) as existing:
            evaluator = auto_tp.make_pin_length_evaluator(winding, stator, inslot, ew)
            self.assertEqual(evaluator(0, 1, 6, 5, 7), 260)
            self.assertEqual(evaluator(0, 1, 6, 5, 7), 260)
            existing.assert_called_once_with(0, 1, 6, 5, 7, winding, stator, inslot, ew)
            self.assertEqual(evaluator.length_basis, 'existing_end_winding_model_mm')

    def test_length_objective_requires_normalized_length_evidence(self):
        metrics = dict(transposition_count=0, pin_type_count=2,
                       average_pin_length_mm=200,
                       average_pin_length_normalized=None)
        with self.assertRaisesRegex(ValueError, 'length'):
            auto_tp.objective_score(metrics, 'min_average_pin_length')
        with self.assertRaisesRegex(ValueError, 'objective'):
            auto_tp.objective_score(metrics, 'unknown')

    def test_connect_ends_includes_closure_pin_and_changed_edge(self):
        winding = SimpleNamespace(q=2, num_slots=24, num_poles=4, num_layers=2)
        layout = SimpleNamespace(inlet_from_weld_side=0, phase_shift_list=[0, 0],
                                 in_out_connection=1)
        reference = [[1, [(0, 0), (6, 1)]]]
        paths = [[1, [(0, 0), (7, 1)]]]
        metrics = auto_tp.implementation_metrics(paths, reference, winding, layout,
            pin_length_evaluator=lambda a, b, span, wa, wb: 200+10*span)
        self.assertEqual(metrics['pin_count'], 1)
        self.assertEqual(metrics['pin_type_count'], 1)
        self.assertEqual(metrics['transposition_count'], 2)
        self.assertEqual(metrics['average_pin_length_mm'], 270)
        expected = 2 + ((7/6)**2 + 1)**0.5 + 14/12
        self.assertAlmostEqual(metrics['average_pin_length_normalized'], expected)

    def test_normalized_length_uses_each_pins_adjacent_weld_spans(self):
        winding = SimpleNamespace(q=2, num_slots=24, num_poles=4, num_layers=2)
        layout = SimpleNamespace(inlet_from_weld_side=1, phase_shift_list=[0, 0])
        paths = [[1, [(0, 0), (6, 1), (8, 0), (14, 1), (20, 0), (0, 1)]]]
        metrics = auto_tp.implementation_metrics(paths, paths, winding, layout)
        pole_pitch = 6
        expected = (
            (2 + (1 + 1)**0.5 + 2/(2*pole_pitch))
            + (2 + (1 + 1)**0.5 + (2+6)/(2*pole_pitch))
            + (2 + ((4/pole_pitch)**2 + 1)**0.5 + 6/(2*pole_pitch))
        ) / 3
        self.assertAlmostEqual(metrics['average_pin_length_normalized'], expected)

    def test_geometry_recipes_cover_offsets_and_all_edge_intervals(self):
        recipes = list(auto_tp.configuration_recipes('BWP', 6, 12, 48))
        regular = {tuple(r.get(k, 0) % 6 for k in ('uni_tp', 'jltp', 'pltp_ll'))
                   for r in recipes if r['tp_type'] == 'Regular'}
        from itertools import product
        self.assertEqual(regular, set(product(range(6), repeat=3)) - {(0, 0, 0)})
        self.assertEqual({r['tp_interval'] for r in recipes if r['tp_type'] == 'Interval'},
                         set(range(1, 48)))
        self.assertEqual({r['tp_times'] for r in recipes if r['tp_type'] == 'Times'},
                         set(range(1, 48)))
        self.assertTrue(all(not r.get('pltp_fl', 0) for r in recipes))

    def test_legacy_names_normalize_to_auto(self):
        self.assertEqual(auto_tp.normalize_tp_type("Optimize"), "Auto")
        self.assertEqual(auto_tp.normalize_tp_type("Auto balance"), "Auto")
        self.assertEqual(auto_tp.normalize_tp_type("Interval"), "Interval")

    def test_balanced_plan_uses_one_shared_payload(self):
        payload = auto_tp.uwp_balanced_settings({"cycle_advance": 2})
        self.assertEqual(payload, {"tp_interval": 0, "tp_times": 0, "uni_tp": 2,
                                   "pltp_fl": 0, "pltp_ll": 0, "jltp": 1})
        self.assertTrue(auto_tp.balanced_configuration_matches(
            SimpleNamespace(tp_type="Auto", jld=1, **payload), payload))

    def test_auto_rule_keeps_existing_bwp_and_fractional_decisions(self):
        rule = auto_tp.select_automatic_rule("BWP", 2, 4, 2, 2)
        self.assertEqual((rule.effective_type, rule.values["tp_times"]), ("Times", 1))
        fractional = auto_tp.select_automatic_rule("UWP", Fraction(3, 2), 8, 3, 1)
        self.assertEqual((fractional.effective_type, fractional.values),
                         ("Regular", auto_tp.zero_values()))


if __name__ == "__main__":
    unittest.main()
