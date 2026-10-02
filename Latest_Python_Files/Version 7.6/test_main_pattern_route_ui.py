"""Focused main-window checks for production Pattern route decisions."""

import os
import unittest
from fractions import Fraction
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

import get_winding_pattern as gw
from main_pyqt6 import WindingApp


class MainPatternRouteUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = WindingApp()

    def tearDown(self):
        import matplotlib.pyplot as plt
        plt.close(self.window.figure)
        self.window.close()

    def _set_geometry(self, pattern, q, poles, layers, naa):
        fields = self.window.input_fields
        fields["winding_input_mode"].setCurrentText("q and poles")
        fields["q"].setText(str(q))
        fields["num_poles"].setText(str(poles))
        fields["num_layers"].setText(str(layers))
        fields["num_phases"].setText("3")
        fields["pattern_name"].setText(pattern)
        fields["ab"].setText(str(naa))
        self.window._sync_dividers_from_inputs()

    def test_half_integer_selected_routes_return_production_decisions(self):
        cases = (
            ("UWP", Fraction(3, 2), 8, 6, 3, (Fraction(3, 2), 1, 2),
             "uwp_half_integer_p2"),
            ("BWP", Fraction(5, 2), 12, 6, 3, (1, 3, 1),
             "bwp_fractional_sector_array"),
        )
        for pattern, q, poles, layers, naa, factors, route in cases:
            with self.subTest(pattern=pattern, q=q, factors=factors):
                self._set_geometry(pattern, q, poles, layers, naa)
                self.assertEqual(self.window._selected_dividers(), factors)
                decision = self.window._validate_divider_route(check_only=True)
                self.assertIsNotNone(decision)
                self.assertEqual(decision.status, "enabled", decision.reason)
                self.assertEqual(decision.route_name, route)

    def test_cp_q1_pp_only_parent_slice_uses_production_route(self):
        self._set_geometry("CP", 1, 12, 4, 6)
        self.window.q_divider_box.setCurrentText("1")
        self.window.pp_divider_box.setCurrentText("6")
        self.window.p2_divider_box.setCurrentText("1")

        factors = self.window._selected_dividers()
        self.assertEqual(factors, (1, 6, 1))
        decision = self.window._validate_divider_route(check_only=True)
        self.assertEqual(decision.status, "enabled", decision.reason)
        self.assertEqual(
            decision.route_name, "cp_q_pp_full_parent_slices")

    def test_production_enabled_tuple_is_not_rejected_for_another_preference(self):
        self._set_geometry("UWP", 4, 8, 4, 4)
        self.window.q_divider_box.setCurrentText("1")
        self.window.pp_divider_box.setCurrentText("2")
        self.window.p2_divider_box.setCurrentText("2")
        selected = self.window._selected_dividers()
        decision = gw.PatternRouteDecision(
            "enabled", "selected_uwp", "The selected route is admitted.",
            "UWP", selected)
        with (patch.object(self.window, "_sync_uwp_balanced_defaults"),
              patch.object(self.window, "_default_dividers", return_value=selected),
              patch.object(self.window, "_validate_divider_route", return_value=decision),
              patch.object(gw, "preferred_uwp_q_dividers", return_value=(2, 1, 2))):
            self.window._refresh_divider_status()
        self.assertNotIn("disabled", self.window.divider_status.text().lower())
        self.assertIn("enabled", self.window.divider_status.text().lower())

    def test_divider_option_uses_production_rejection_reason(self):
        self._set_geometry("BWP", 2, 8, 6, 2)
        self.window.q_divider_box.setCurrentText("1")
        self.window.pp_divider_box.setCurrentText("2")
        self.window.p2_divider_box.setCurrentText("1")
        self.assertEqual(self.window._selected_dividers(), (1, 2, 1))
        item = self.window.p2_divider_box.model().item(
            self.window.p2_divider_box.findText("2"))
        self.assertFalse(item.isEnabled())
        self.assertIn("BWP", item.toolTip())
        self.assertIn("P2", item.toolTip())

    def test_feasible_uwp_p2_option_remains_enabled(self):
        self._set_geometry("UWP", 4, 8, 4, 2)
        item = self.window.p2_divider_box.model().item(
            self.window.p2_divider_box.findText("2"))
        self.assertTrue(item.isEnabled(), item.toolTip())
        self.assertEqual(self.window._validate_divider_route(check_only=True).status,
                         "enabled")

    def test_fractional_option_guidance_uses_route_configuration_reasons(self):
        self._set_geometry("BWP", Fraction(5, 2), 12, 6, 3)
        self.window._refresh_weld_inlet_availability()
        self.window._refresh_route_option_availability()
        self.assertFalse(self.window.input_fields["inlet_from_weld_side"].isEnabled())
        self.assertIn(
            "This half-integer wave route does not support a weld-side inlet.",
            self.window.input_fields["inlet_from_weld_side"].toolTip())
        self.assertFalse(self.window._option_help_buttons[
            "inlet_from_weld_side"].isHidden())
        self.assertTrue(self.window.input_fields["radial_shift"].isEnabled())
        self.assertTrue(self.window._option_help_buttons["radial_shift"].isHidden())
        self.window.input_fields["radial_shift"].setChecked(True)
        decision = self.window._validate_divider_route(check_only=True)
        self.assertIsNotNone(decision)
        self.assertEqual(decision.status, "enabled", decision.reason)

    def test_required_weld_inlet_remains_fixed_on(self):
        self._set_geometry("ZPP", 4, 8, 4, 4)
        self.window.q_divider_box.setCurrentText("2")
        self.window.pp_divider_box.setCurrentText("2")
        self.window.p2_divider_box.setCurrentText("1")
        self.window._refresh_weld_inlet_availability()
        field = self.window.input_fields["inlet_from_weld_side"]
        self.assertFalse(field.isEnabled())
        self.assertTrue(field.isChecked())
        self.assertIn("weld", field.toolTip().lower())


if __name__ == "__main__":
    unittest.main()
