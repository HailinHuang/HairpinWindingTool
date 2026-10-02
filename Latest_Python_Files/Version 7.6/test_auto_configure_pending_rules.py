"""Focused contracts for formula-wide Auto Configure candidates."""
import unittest
from types import SimpleNamespace

import automatic_transposition as auto_tp
import get_winding_pattern as gw
from pattern_rule_workbench import _base_inputs


class AutoConfigurePendingRuleTests(unittest.TestCase):
    def test_fixed_path_formulas_do_not_silently_ignore_transposition(self):
        for factors in ((1, 4, 2), (1, 2, 1)):
            with self.subTest(factors=factors):
                naa = factors[0] * factors[1] * factors[2]
                winding, tp, layout = _base_inputs('TSP', 2, 8, 4, naa, factors)
                tp.uni_tp = 1
                for recipe in (False, True):
                    if recipe:
                        tp.auto_configuration_rule = 'tsp_geometry_recipe'
                        tp._auto_configuration_token = gw._AUTO_CONFIGURATION_TOKEN
                    with self.assertRaisesRegex(ValueError, 'no transposition implementation'):
                        gw.get_winding_layout('TSP', tp, winding, layout)

    def test_manual_transposition_matches_generated_recipe_for_every_pattern(self):
        cases = (
            ('BWP', 2, (2, 1, 1), 'uni_tp', 1),
            ('UWP', 2, (1, 1, 2), 'jltp', 1),
            ('SSP', 2, (2, 1, 1), 'uni_tp', 1),
            ('TSP', 2, (1, 1, 2), 'tp_times', 3),
            ('SLP', 2, (2, 1, 1), 'uni_tp', 1),
            ('ZLP', 2, (1, 2, 1), 'tp_interval', 2),
            ('CP', 4, (2, 1, 2), 'tp_times', 1),
            ('ZPP', 2, (2, 1, 1), 'tp_times', 1),
            ('TLP', 2, (1, 1, 2), 'uni_tp', 1),
            ('LPP', 4, (1, 4, 1), 'tp_times', 3),
        )
        self.assertEqual({case[0] for case in cases}, set(gw.PATTERN_REGISTRY))
        for pattern, naa, factors, field, value in cases:
            with self.subTest(pattern=pattern, field=field):
                winding, tp, layout = _base_inputs(
                    pattern, 2, 8, 4, naa, factors)
                _, baseline = gw.get_winding_layout(pattern, tp, winding, layout)
                setattr(tp, field, value)
                tp.tp_type = {'tp_times': 'Times', 'tp_interval': 'Interval'}.get(
                    field, 'Regular')
                recipe = SimpleNamespace(**vars(tp))
                recipe.auto_configuration_rule = pattern.lower() + '_geometry_recipe'
                recipe._auto_configuration_token = gw._AUTO_CONFIGURATION_TOKEN
                _, expected = gw.get_winding_layout(pattern, recipe, winding, layout)
                starts, actual = gw.get_winding_layout(pattern, tp, winding, layout)
                self.assertEqual(actual, expected)
                self.assertNotEqual(actual, baseline)
                self.assertEqual(starts, [path[0] for _, path in actual])
                coordinates = [tuple(node[:2]) for _, path in actual for node in path]
                self.assertEqual(len(set(coordinates)), winding.num_slots * winding.num_layers)
                self.assertEqual({len(path) for _, path in actual}, {
                    winding.num_poles * winding.num_layers * winding.q // naa})

    def test_recipes_cover_every_start_index_and_nonwave_regular_fields(self):
        wave = list(auto_tp.configuration_recipes('BWP', 4, 8, 12))
        self.assertEqual(
            {row.get('tp_start_index', 0) for row in wave
             if row['tp_type'] == 'Interval' and row['tp_interval'] == 3},
            {0, 1, 2},
        )
        q2 = list(auto_tp.configuration_recipes('BWP', 2, 8, 12))
        self.assertEqual(
            {row.get('tp_start_index', 0) for row in q2
             if row['tp_type'] == 'Interval' and row['tp_interval'] == 5},
            {0, 1, 2, 3, 4},
        )
        nonwave = list(auto_tp.configuration_recipes('SSP', 4, 8, 12))
        regular = {
            tuple(row.get(field, 0) % 4
                  for field in ('uni_tp', 'jltp', 'pltp_ll', 'pltp_fl'))
            for row in nonwave if row['tp_type'] == 'Regular'
        }
        self.assertIn((0, 0, 1, 0), regular)
        self.assertIn((0, 0, 0, 1), regular)

    def test_bwp_regular_offsets_precede_interval_and_times_recipes(self):
        recipes = list(auto_tp.configuration_recipes(
            'BWP', 4, 8, 12, include_start_indices=False))
        first_non_regular = next(
            index for index, row in enumerate(recipes)
            if row['tp_type'] != 'Regular')
        self.assertTrue(all(row['tp_type'] == 'Regular'
                            for row in recipes[:first_non_regular]))
        first_multi = next(
            index for index, row in enumerate(recipes[:first_non_regular])
            if sum(bool(row.get(field, 0)) for field in
                   ('uni_tp', 'pltp_ll', 'jltp')) > 1)
        single_field_order = []
        for row in recipes[:first_multi]:
            active = [field for field in
                      ('uni_tp', 'pltp_ll', 'pltp_fl', 'jltp')
                      if row.get(field, 0)]
            self.assertEqual(len(active), 1)
            single_field_order.append(active[0])
        field_runs = []
        for field in single_field_order:
            if not field_runs or field_runs[-1] != field:
                field_runs.append(field)
        self.assertEqual(field_runs, ['uni_tp', 'pltp_ll', 'jltp'])

    def test_bwp_formula_miss_continues_full_search(self):
        winding, tp, layout = _base_inputs('BWP', 4, 8, 4, 2, (2, 1, 1))
        _, paths = gw.get_auto_configured_layout(
            'BWP', tp, winding, layout, objective='min_pin_types')
        report = paths.auto_configuration
        self.assertEqual(report['status'], 'strong symmetry layout')
        self.assertEqual(report['effective_parameters']['tp_type'], 'Regular')
        self.assertEqual(report['minimum_pin_types_formula'],
                         'N_L + 1 (manuscript v3, BWP insertion-side, Table IV)')
        self.assertEqual(report['minimum_pin_types_target'], 5)
        self.assertGreater(report['metrics']['pin_type_count'], 5)
        self.assertFalse(report['pin_type_formula_stop_applied'])
        self.assertFalse(report['fast_path_applied'])
        self.assertTrue(report['search_complete'])
        self.assertEqual(report['optimality_scope'],
                         'best_in_evaluated_recipe_domain')
        self.assertGreater(report['attempts'], 100)

    def test_bwp_stops_immediately_when_manuscript_minimum_is_reached(self):
        winding, tp, layout = _base_inputs('BWP', 2, 8, 6, 2, (2, 1, 1))
        _, paths = gw.get_auto_configured_layout(
            'BWP', tp, winding, layout, objective='min_pin_types')
        report = paths.auto_configuration
        self.assertEqual(report['status'], 'strong symmetry layout')
        self.assertEqual(report['minimum_pin_types_target'], 7)
        self.assertEqual(report['metrics']['pin_type_count'], 7)
        self.assertTrue(report['minimum_pin_types_reached'])
        self.assertTrue(report['pin_type_formula_stop_applied'])
        self.assertTrue(report['fast_path_applied'])
        self.assertFalse(report['search_complete'])
        self.assertEqual(report['optimality_scope'],
                         'manuscript_v3_bwp_insertion_side_min_pin_types')
        self.assertLessEqual(report['attempts'], 3)
        selected = next(row for row in report['implementations']
                        if row['implementation_id'] == report['implementation_id'])
        self.assertEqual(selected['effective_parameters']['pltp_ll'], 1)
        _, replay = gw.replay_auto_configuration('BWP', selected, winding, layout)
        self.assertEqual(replay.layout_status, paths.layout_status)

    def test_bwp_formula_recipes_precede_selected_interval_input(self):
        winding, tp, layout = _base_inputs('BWP', 2, 8, 6, 2, (2, 1, 1))
        tp.tp_type = 'Interval'
        tp.tp_interval = 1
        _, paths = gw.get_auto_configured_layout(
            'BWP', tp, winding, layout, objective='min_pin_types')
        report = paths.auto_configuration
        self.assertTrue(report['pin_type_formula_stop_applied'])
        self.assertEqual(report['effective_parameters']['pltp_ll'], 1)
        self.assertNotIn(
            'selected_input',
            {row['rule_id'] for row in report['implementations']})

    def test_bwp_fast_rule_is_limited_to_verified_objective_and_domain(self):
        winding, tp, layout = _base_inputs('BWP', 4, 8, 4, 2, (2, 1, 1))
        _, transposition_paths = gw.get_auto_configured_layout(
            'BWP', tp, winding, layout, objective='min_transpositions')
        self.assertFalse(
            transposition_paths.auto_configuration['fast_path_applied'])

        for q, poles, layers, phases, shifts, expected in (
                (4, 8, 4, 3, [0, 0, 0, 0], True),
                (1, 8, 4, 3, [0, 0, 0, 0], False),
                (7, 8, 4, 3, [0, 0, 0, 0], False),
                (4, 14, 4, 3, [0, 0, 0, 0], False),
                (4, 8, 8, 3, [0] * 8, False),
                (4, 8, 4, 5, [0, 0, 0, 0], False),
                (4, 8, 4, 3, [0, 0, 1, 0], False)):
            case_winding, case_tp, case_layout = _base_inputs(
                'BWP', q, poles, layers, 2, (2, 1, 1), phases=phases)
            case_layout.phase_shift_list = shifts
            self.assertEqual(gw._bwp_fast_rule_domain_verified(
                case_winding, case_layout, 'min_pin_types'), expected,
                (q, poles, layers, phases, shifts))

        winding, tp, layout = _base_inputs('BWP', 2, 8, 6, 2, (2, 1, 1))
        layout.inlet_from_weld_side = 1
        _, paths = gw.get_auto_configured_layout(
            'BWP', tp, winding, layout, objective='min_pin_types')
        self.assertFalse(paths.auto_configuration['fast_path_applied'])
        self.assertTrue(paths.auto_configuration['search_complete'])

    def test_bwp_rule_miss_falls_back_to_full_search_and_pending_retention(self):
        winding, tp, layout = _base_inputs('BWP', 4, 8, 4, 4, (2, 2, 1))
        _, paths = gw.get_auto_configured_layout('BWP', tp, winding, layout)
        report = paths.auto_configuration
        self.assertEqual(report['status'], 'auto configure pending')
        self.assertFalse(report['fast_path_applied'])
        self.assertTrue(report['search_complete'])
        self.assertEqual(report['optimality_scope'],
                         'best_in_evaluated_recipe_domain')
        self.assertGreater(report['attempts'], 100)

    def test_every_implementation_exports_replay_contract(self):
        winding, tp, layout = _base_inputs('BWP', 4, 8, 4, 2, (2, 1, 1))
        _, paths = gw.get_auto_configured_layout('BWP', tp, winding, layout)
        report = paths.auto_configuration
        self.assertIn('effective_start_schedule', report)
        self.assertIsNone(report['effective_start_schedule'])
        for row in report['implementations']:
            self.assertIn('rule_id', row)
            self.assertIn('effective_start_schedule', row)
            replay_tp = SimpleNamespace(**row['effective_parameters'])
            _, replay = gw.get_winding_layout('BWP', replay_tp, winding, layout)
            identity = tuple((branch, tuple(tuple(node[:2]) for node in path))
                             for branch, path in replay)
            self.assertEqual(identity, row['physical_paths'])

    def test_start_index_search_keeps_late_electrically_valid_origin(self):
        winding, tp, layout = _base_inputs('BWP', 2, 8, 4, 2, (2, 1, 1))
        identities = []
        validity = []
        for start_index in range(3):
            candidate = SimpleNamespace(**vars(tp))
            candidate.tp_type = 'Interval'
            candidate.tp_interval = 3
            candidate.tp_start_index = start_index
            _, paths = gw.get_winding_layout('BWP', candidate, winding, layout)
            validity.append(paths.layout_report['electrically_valid'])
            identities.append(tuple(tuple(node[:2]) for _, path in paths for node in path))
        self.assertEqual(validity, [False, False, True])
        self.assertEqual(len(set(identities)), 3)

    def test_pending_records_search_dimensions_without_changing_admission(self):
        winding, tp, layout = _base_inputs('SSP', 4, 8, 4, 2, (2, 1, 1))
        _, paths = gw.get_auto_configured_layout('SSP', tp, winding, layout)
        report = paths.auto_configuration
        self.assertEqual(report['status'], 'auto configure pending')
        self.assertTrue(report['searched_rule_ids'])
        self.assertIn('unsearched_dimensions', report)
        self.assertEqual(gw.selected_integer_divider_route('SSP', winding),
                         gw.selected_integer_divider_route('SSP', winding))

    def test_nonwave_manual_route_and_verified_auto_replay_agree(self):
        winding, tp, layout = _base_inputs('TSP', 2, 8, 4, 4, (2, 2, 1))
        manual = SimpleNamespace(**vars(tp))
        manual.uni_tp = 1
        _, manual_paths = gw.get_winding_layout('TSP', manual, winding, layout)
        manual.auto_configuration_rule = 'tsp_geometry_recipe'
        _, labelled_paths = gw.get_winding_layout('TSP', manual, winding, layout)
        self.assertEqual(manual_paths, labelled_paths)
        with self.assertRaisesRegex(ValueError, 'complete exported'):
            gw.replay_auto_configuration('TSP', vars(manual), winding, layout)
        _, configured = gw.get_auto_configured_layout('TSP', tp, winding, layout)
        implementation = next(
            row for row in configured.auto_configuration['implementations']
            if row['rule_id'] == 'tsp_geometry_recipe')
        _, replay = gw.replay_auto_configuration(
            'TSP', implementation, winding, layout)
        self.assertTrue(replay.layout_report['electrically_valid'])
        forged = dict(implementation, implementation_id='0' * 64)
        with self.assertRaisesRegex(ValueError, 'was not emitted'):
            gw.replay_auto_configuration('TSP', forged, winding, layout)
        self_consistent = dict(implementation)
        self_consistent['effective_parameters'] = dict(
            implementation['effective_parameters'], tp_start_index=999)
        with self.assertRaisesRegex(ValueError, 'was not emitted'):
            gw.replay_auto_configuration(
                'TSP', self_consistent, winding, layout)


if __name__ == '__main__':
    unittest.main()
