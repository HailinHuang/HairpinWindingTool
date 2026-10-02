"""UI persistence and full-calculation integration for Auto objectives."""
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest

import get_winding_pattern as gw
import calculation_cache
from main_pyqt6 import WindingApp


class AutoConfigureStrategyUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = WindingApp()

    def tearDown(self):
        import matplotlib.pyplot as plt
        plt.close("all")
        self.window.close()

    def small_case(self):
        self.window._apply_config_payload({"inputs": {
            "winding_input_mode": "q and poles", "q": "1",
            "num_poles": "4", "num_layers": "4", "num_phases": "3",
            "ab": "1", "pattern_name": "BWP", "tp_type": "Auto",
            "inlet_from_weld_side": 1, "radial_shift": 0,
            "phase_shift_pattern": "None", "phase_shift": "0", "PSL": "1",
        }})

    def test_default_choices_and_manual_editability(self):
        w = self.window
        selector = w.input_fields["auto_configure_objective"]
        self.assertEqual([selector.itemData(i) for i in range(selector.count())],
                         ["min_transpositions", "min_pin_types", "min_average_pin_length"])
        self.assertEqual(selector.currentData(), "min_pin_types")
        self.assertTrue(selector.isEnabled())
        self.assertTrue(all(field.isReadOnly() for field in w.tp_fields.values()))
        w.tp_type_field.setCurrentText("Interval")
        self.assertFalse(selector.isEnabled())
        self.assertFalse(w.tp_fields["tp_interval"].isReadOnly())
        w.tp_type_field.setCurrentText("Auto")
        self.assertTrue(selector.isEnabled())
        self.assertTrue(all(field.isReadOnly() for field in w.tp_fields.values()))

    def test_apply_button_keeps_auto_and_highlights_effective_parameters(self):
        self.small_case()
        w = self.window
        w.inlet_index_adjustments_phase_a = [1]
        w.volt_diff_inlet_adjustments_all = [1, 0, 0]

        w.auto_configure_apply_button.click()

        self.assertEqual(w.tp_type_field.currentText(), "Auto")
        self.assertFalse(any(w.inlet_index_adjustments_phase_a))
        self.assertFalse(any(w.volt_diff_inlet_adjustments_all))
        self.assertIn("Auto Configure applied", w.message_log.toPlainText())
        effective_type = w._auto_effective_tp_type
        active = {
            "Regular": {"uni_tp", "pltp_fl", "pltp_ll", "jltp"},
            "Times": {"tp_times"},
            "Interval": {"tp_interval"},
        }[effective_type]
        for key, field in w.tp_fields.items():
            self.assertTrue(field.isReadOnly())
            if key in active:
                self.assertIn("background-color: white", field.styleSheet())
            else:
                self.assertIn("background-color: lightgray", field.styleSheet())

    def test_auto_materialization_preserves_offsets_for_dependent_tools(self):
        self.small_case()
        w = self.window
        w.inlet_index_adjustments_phase_a = [1]

        self.assertTrue(w.apply_auto_configuration(preserve_inlet_adjustments=True))

        self.assertNotEqual(w.tp_type_field.currentText(), "Auto")
        self.assertEqual(w.inlet_index_adjustments_phase_a, [1])
        w.extract_parameters()

    def test_stable_id_roundtrip_legacy_default_and_signature(self):
        w = self.window
        selector = w.input_fields["auto_configure_objective"]
        original = w._calculation_input_signature()
        original_preview = w._manual_preview_signature()
        original_inductance = w._inductance_source_key()
        selector.setCurrentIndex(selector.findData("min_average_pin_length"))
        self.assertNotEqual(original, w._calculation_input_signature())
        self.assertNotEqual(original_preview, w._manual_preview_signature())
        self.assertNotEqual(original_inductance, w._inductance_source_key())
        payload = w._build_config_payload()
        self.assertEqual(payload["inputs"]["auto_configure_objective"],
                         "min_average_pin_length")
        selector.setCurrentIndex(0)
        w._apply_config_payload(payload)
        self.assertEqual(selector.currentData(), "min_average_pin_length")
        del payload["inputs"]["auto_configure_objective"]
        w._apply_config_payload(payload)
        self.assertEqual(selector.currentData(), "min_pin_types")

    def test_full_calculation_uses_selected_objective_and_effective_parameters(self):
        self.small_case()
        w = self.window
        selector = w.input_fields["auto_configure_objective"]
        selector.setCurrentIndex(selector.findData("min_average_pin_length"))
        seen = {}

        def resolve(pattern, tp, winding, layout, **kwargs):
            seen.update(kwargs)
            self.assertEqual(tp.tp_type, "Regular")
            self.assertTrue(all(getattr(tp, key) == 0 for key in w.tp_fields))
            self.assertIn("PoleN", tp.pole_group_tp)
            starts, database = gw.get_winding_layout(pattern, tp, winding, layout)
            effective = tp._asdict()
            effective.update(tp_type="Interval", tp_interval=7)
            database.auto_configuration = dict(
                completed=True, status="strong symmetry layout",
                objective=kwargs["objective"], effective_parameters=effective,
                metrics={"pin_type_count": 2, "transposition_count": 0,
                         "average_pin_length_normalized": 2.75,
                         "average_pin_length_mm": 300.0}, attempts=1)
            return starts, database

        with patch("main_pyqt6.gw.get_auto_configured_layout", side_effect=resolve) as resolver:
            w.extract_parameters()
            self.assertEqual(resolver.call_count, 1)
        self.assertEqual(seen["objective"], "min_average_pin_length")
        self.assertTrue(callable(seen["pin_length_evaluator"]))
        self.assertEqual(w.TP_info.tp_type, "Interval")
        self.assertEqual(w.TP_info.tp_interval, 7)
        self.assertEqual(w.tp_fields["tp_interval"].text(), "7")
        self.assertEqual(w.tp_type_field.currentText(), "Auto")
        self.assertTrue(w.tp_fields["tp_interval"].isReadOnly())
        self.assertIn("Normalized average pin length: 2.750",
                      w.auto_configuration_notice.text())

    def test_manual_mode_does_not_call_auto_resolver(self):
        self.small_case()
        w = self.window
        w.tp_type_field.setCurrentText("Regular")
        with patch("main_pyqt6.gw.get_auto_configured_layout") as resolver:
            w.extract_parameters()
        resolver.assert_not_called()
        self.assertEqual(w.TP_info.tp_type, "Regular")

    def test_negative_selected_jump_does_not_reverse_next_auto_reference(self):
        self.small_case()
        w = self.window
        w.auto_configure_objective_field.setCurrentIndex(2)
        seeds = []

        def resolve(pattern, tp, winding, layout, **kwargs):
            seeds.append(tp)
            starts, database = gw.get_winding_layout(pattern, tp, winding, layout)
            effective = tp._asdict()
            effective.update(jltp=-1, jld=1)
            database.auto_configuration = dict(
                completed=True, status="strong symmetry layout",
                objective=kwargs["objective"], effective_parameters=effective)
            return starts, database

        with patch("main_pyqt6.gw.get_auto_configured_layout", side_effect=resolve):
            w.extract_parameters()
            self.assertEqual(w.tp_fields["jltp"].text(), "-1")
            w.auto_configure_objective_field.setCurrentIndex(0)
            with patch("main_pyqt6.gw.resolve_pattern_route", wraps=gw.resolve_pattern_route) as route:
                w._validate_divider_route(check_only=True)
            admission_seed = route.call_args.args[3]
            w.extract_parameters()
        self.assertEqual([seed.jld for seed in seeds], [1, 1])
        self.assertEqual(admission_seed.jld, 1)
        self.assertTrue(all(seed.jltp == 0 for seed in seeds))
        w.tp_type_field.setCurrentText("Regular")
        w.extract_parameters()
        self.assertEqual((w.TP_info.jltp, w.TP_info.jld), (1, -1))

    def test_auto_rejects_inlet_adjustments_before_metric_selection(self):
        self.small_case()
        w = self.window
        w.inlet_index_adjustments_phase_a = [1]
        with patch("main_pyqt6.gw.get_auto_configured_layout") as resolver:
            with self.assertRaisesRegex(ValueError, "inlet adjustments"):
                w.extract_parameters()
        resolver.assert_not_called()

    def test_real_small_auto_calculation_attaches_selected_objective(self):
        self.small_case()
        w = self.window
        w.extract_parameters()
        result = w.base_db_conductor_id.auto_configuration
        self.assertEqual(result["objective"], "min_pin_types")
        self.assertEqual(w.TP_info.tp_type, result["effective_parameters"]["tp_type"])
        self.assertEqual(w._last_calculation_signature, w._calculation_input_signature())
        QTest.qWait(200)
        self.assertNotIn("Pending calculation", w.auto_configuration_notice.text())

    def test_auto_admission_validates_neutral_seed_not_provisional_fields(self):
        self.small_case()
        w = self.window
        for field in w.tp_fields.values():
            field.blockSignals(True)
            field.setText("123")
            field.blockSignals(False)
        w._auto_effective_tp_type = "Interval"
        with patch("main_pyqt6.gw.resolve_pattern_route", wraps=gw.resolve_pattern_route) as resolver:
            w._validate_divider_route(check_only=True)
        tp = resolver.call_args.args[3]
        self.assertEqual(tp.tp_type, "Regular")
        self.assertTrue(all(getattr(tp, key) == 0 for key in w.tp_fields))

    def test_real_objective_switches_recalculate_bwp_and_uwp(self):
        self.small_case()
        w = self.window
        for pattern, poles in (("BWP", 4), ("BWP", 8), ("UWP", 4)):
            w._apply_config_payload({"inputs": {
                "q": "2", "num_poles": str(poles), "num_layers": "4",
                "ab": "4" if pattern == "UWP" else "2",
                "pattern_name": pattern, "tp_type": "Auto",
                "inlet_from_weld_side": int(pattern == "BWP"),
                "q_divider": "2", "pp_divider": "1",
                "p2_divider": "2" if pattern == "UWP" else "1",
            }})
            selector = w.input_fields["auto_configure_objective"]
            for objective in ("min_transpositions", "min_pin_types", "min_average_pin_length"):
                with self.subTest(pattern=pattern, poles=poles, objective=objective):
                    selector.setCurrentIndex(selector.findData(objective))
                    w.extract_parameters()
                    report = w.base_db_conductor_id.auto_configuration
                    self.assertEqual(report["objective"], objective)
                    self.assertEqual(w.TP_info.tp_type, report["effective_parameters"]["tp_type"])
                    self.assertIn("Finite recipe search", w.auto_configuration_notice.text())
                    if report.get("fast_path_applied"):
                        self.assertIn("BWP insertion-side pin-type target N_L+1 reached",
                                      w.auto_configuration_notice.text())
                        self.assertIn("The pin-type minimum is met",
                                      w.auto_configuration_notice.text())

    def test_auto_result_survives_config_refresh_and_cached_calculation(self):
        w = self.window
        w._apply_config_payload({"inputs": {
            "q": "4", "num_poles": "8", "num_layers": "4", "ab": "2",
            "pattern_name": "BWP", "tp_type": "Auto", "q_divider": "2",
            "pp_divider": "1", "p2_divider": "1", "inlet_from_weld_side": 1,
        }})
        w.extract_parameters()
        fields = {key: field.text() for key, field in w.tp_fields.items()}
        w._refresh_divider_status()
        w.update_transp_type("Auto")
        QTest.qWait(200)
        self.assertNotIn("Pending calculation", w.auto_configuration_notice.text())
        self.assertEqual(fields, {key: field.text() for key, field in w.tp_fields.items()})
        self.assertEqual(w._last_calculation_signature, w._calculation_input_signature())
        w.tp_type_field.setCurrentText("Interval")
        w.tp_type_field.setCurrentText("Auto")
        self.assertTrue(w.auto_configure_objective_field.isEnabled())
        self.assertTrue(all(field.isReadOnly() for field in w.tp_fields.values()))
        self.assertNotIn("Manual", w.auto_configuration_notice.text())

    def test_q4_bwp_auto_result_survives_new_window_without_search(self):
        inputs = {
            "winding_input_mode": "q and poles", "q": "4", "num_poles": "8",
            "num_layers": "6", "num_phases": "3", "ab": "4",
            "pattern_name": "BWP", "q_divider": "4", "pp_divider": "1",
            "p2_divider": "1", "tp_type": "Auto",
            "inlet_from_weld_side": 0, "radial_shift": 0,
            "phase_shift_pattern": "None", "phase_shift": "0", "PSL": "1",
        }
        with tempfile.TemporaryDirectory() as folder, patch.dict(
                os.environ, {"HAIRPIN_CALC_CACHE_PATH": os.path.join(folder, "results.sqlite3")},
                clear=False):
            self.window._apply_config_payload({"inputs": inputs})
            original = self.window.calculation_state
            self.assertTrue(os.path.isfile(os.path.join(folder, "results.sqlite3")))
            reopened = WindingApp()
            try:
                with patch("main_pyqt6.gw.get_auto_configured_layout",
                           side_effect=AssertionError("Must restore saved Auto result")) as search:
                    reopened._apply_config_payload({"inputs": inputs})
                    reopened.plot_layout()
                search.assert_not_called()
                self.assertEqual(reopened.calculation_state.values["db_conductor_id"],
                                 original.values["db_conductor_id"])
                self.assertEqual(reopened.base_db_conductor_id.auto_configuration["metrics"],
                                 self.window.base_db_conductor_id.auto_configuration["metrics"])
                self.assertEqual(reopened.current_view_type, "winding")
                theme = reopened.input_fields["ui_theme"]
                theme.setCurrentText("Dark" if theme.currentText() != "Dark" else "Light")
                with patch("main_pyqt6.gw.get_auto_configured_layout",
                           side_effect=AssertionError("Plot style must reuse Auto result")):
                    reopened.extract_parameters()
            finally:
                reopened.close()

    def test_persistent_result_uses_changed_inputs_and_damaged_entry_falls_back(self):
        inputs = {
            "winding_input_mode": "q and poles", "q": "1", "num_poles": "4",
            "num_layers": "4", "num_phases": "3", "ab": "1",
            "pattern_name": "BWP", "tp_type": "Auto",
            "inlet_from_weld_side": 1, "radial_shift": 0,
            "phase_shift_pattern": "None", "phase_shift": "0", "PSL": "1",
        }
        with tempfile.TemporaryDirectory() as folder, patch.dict(
                os.environ, {"HAIRPIN_CALC_CACHE_PATH": os.path.join(folder, "results.sqlite3")},
                clear=False):
            self.window._apply_config_payload({"inputs": inputs})
            original_signature = self.window.calculation_state.signature
            changed = WindingApp()
            try:
                with patch("main_pyqt6.gw.get_auto_configured_layout",
                           wraps=gw.get_auto_configured_layout) as search:
                    changed._apply_config_payload({"inputs": {**inputs, "num_layers": "6"}})
                self.assertGreater(search.call_count, 0)
                self.assertNotEqual(changed.calculation_state.signature, original_signature)
            finally:
                changed.close()
            with closing(sqlite3.connect(os.environ["HAIRPIN_CALC_CACHE_PATH"])) as connection, connection:
                connection.execute("UPDATE calculations SET payload = ? WHERE cache_key = ?",
                                   (b"damaged", calculation_cache._key(original_signature)))
            self.assertIsNone(calculation_cache.load(original_signature))


if __name__ == "__main__":
    unittest.main()
