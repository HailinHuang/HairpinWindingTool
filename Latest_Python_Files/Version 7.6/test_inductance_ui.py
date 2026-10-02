"""Inductance-tab integration checks."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from types import SimpleNamespace

import numpy as np
from PyQt6.QtWidgets import QApplication

import inductance_calculation as ic
from main_pyqt6 import WindingApp


class InductanceTabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = WindingApp()
        fields = self.window.input_fields
        fields["winding_input_mode"].setCurrentText("Slots and poles")
        fields["num_slots"].setText("48")
        fields["num_poles"].setText("8")
        fields["num_layers"].setText("6")
        fields["num_phases"].setText("3")
        fields["ab"].setText("2")
        fields["pattern_name"].setText("BWP")
        self.window._resolve_slot_inputs()

    def tearDown(self):
        import matplotlib.pyplot as plt
        self.window.close()
        plt.close("all")

    def test_tab_exposes_bounded_model_inputs_and_config_roundtrip_fields(self):
        labels = [self.window.tabs.tabText(index)
                  for index in range(self.window.tabs.count())]
        self.assertIn("Inductance", labels)
        self.assertEqual(self.window.input_fields["inductance_mu_r"].text(), "1.0")
        self.assertNotIn("inductance_gmr_factor", self.window.input_fields)
        self.assertTrue(self.window.inductance_gmr_display.isReadOnly())

        payload = self.window._build_config_payload()

        self.assertEqual(payload["inputs"]["inductance_mu_r"], "1.0")
        self.assertNotIn("inductance_gmr_factor", payload["inputs"])

        legacy_payload = dict(payload)
        legacy_payload["inputs"] = dict(payload["inputs"])
        legacy_payload["inputs"]["inductance_gmr_factor"] = "0.9"
        legacy_payload["inputs"].pop("inductance_mu_r")
        self.window.input_fields["inductance_mu_r"].setText("9")
        self.window._apply_config_payload(legacy_payload)
        self.assertEqual(self.window.input_fields["inductance_mu_r"].text(), "1.0")
        self.assertNotIn("inductance_gmr_factor", self.window.input_fields)

        index = labels.index("Inductance")
        self.window.tabs.setCurrentIndex(index)
        self.app.processEvents()
        self.assertFalse(self.window.workflow_container.isVisible())
        self.assertFalse(self.window.left_info_splitter.isVisible())
        self.assertFalse(self.window.figure_container.isVisible())

    def test_calculation_populates_phase_and_branch_matrices_for_current_layout(self):
        self.window.calculate_inductance()

        self.assertEqual(self.window.inductance_phase_table.rowCount(), 3)
        self.assertEqual(self.window.inductance_phase_table.columnCount(), 3)
        self.assertEqual(self.window.inductance_phase_normalized_table.rowCount(), 3)
        self.assertEqual(self.window.inductance_branch_table.rowCount(), 6)
        self.assertEqual(self.window.inductance_branch_table.columnCount(), 6)
        self.assertEqual(self.window.inductance_branch_normalized_table.rowCount(), 6)
        self.assertEqual(self.window.inductance_matrix_tabs.count(), 4)
        for table in (
                self.window.inductance_phase_normalized_table,
                self.window.inductance_branch_normalized_table):
            for index in range(table.rowCount()):
                self.assertAlmostEqual(float(table.item(index, index).text()), 1.0)
        self.assertIn("Active-length partial inductance", self.window.inductance_summary.toPlainText())
        self.assertIn("Equal current sharing", self.window.inductance_summary.toPlainText())
        self.assertIn("kij = Mij / sqrt(Lii Ljj)", self.window.inductance_summary.toPlainText())
        inslot = self.window.calculation_state.values["Inslot_Para"]
        self.assertAlmostEqual(
            self.window.inductance_result.conductor_gmr_m,
            ic.rectangular_conductor_gmr(
                inslot.Cond_Width / 1000,
                inslot.Cond_Height / 1000),
            places=15,
        )
        self.assertEqual(
            self.window.inductance_gmr_display.text(),
            f"{self.window.inductance_result.conductor_gmr_m * 1000.0:.6g}")
        self.assertIn("excludes end winding", self.window.inductance_model_note.text().lower())
        self.assertTrue(hasattr(self.window, "inductance_result"))
        self.assertTrue(self.window.inductance_matrix_popout_button.isEnabled())

    def test_branch_matrix_labels_use_phase_local_numbers(self):
        result = SimpleNamespace(
            branch_ids=[10, 11, 20, 21, 30],
            branch_phases=[0, 0, 1, 1, 2],
        )

        self.assertEqual(
            self.window._inductance_branch_labels(result),
            ["A-1", "A-2", "B-1", "B-2", "C-1"],
        )

    def test_current_matrix_can_pop_out_and_embed_without_copying_table(self):
        self.window.calculate_inductance()
        tab_index = next(
            index for index in range(self.window.inductance_matrix_tabs.count())
            if self.window.inductance_matrix_tabs.tabText(index)
            == "Branch normalized (k)")
        self.window.inductance_matrix_tabs.setCurrentIndex(tab_index)
        table = self.window.inductance_branch_normalized_table
        page = self.window.inductance_matrix_tabs.widget(tab_index)

        self.window.toggle_inductance_matrix_window()
        self.app.processEvents()

        self.assertIs(table.window(), self.window.inductance_matrix_window)
        self.assertTrue(self.window.inductance_matrix_window.isVisible())
        self.assertEqual(
            self.window.inductance_matrix_popout_button.text(), "Embed Matrix")

        self.window.embed_inductance_matrix()
        self.app.processEvents()

        self.assertIs(table.parentWidget(), page)
        self.assertFalse(self.window.inductance_matrix_window.isVisible())
        self.assertEqual(
            self.window.inductance_matrix_popout_button.text(), "Pop Out Matrix")

    def test_stale_input_embeds_and_clears_detached_matrix(self):
        self.window.calculate_inductance()
        self.window.inductance_matrix_tabs.setCurrentIndex(0)
        self.window.toggle_inductance_matrix_window()
        self.app.processEvents()

        self.window.input_fields["stack_length"].setText("999")
        self.app.processEvents()

        self.assertFalse(self.window.inductance_matrix_window.isVisible())
        self.assertEqual(self.window.inductance_phase_table.rowCount(), 0)
        self.assertFalse(self.window.inductance_matrix_popout_button.isEnabled())
        self.assertEqual(self.window.inductance_gmr_display.text(), "—")

    def test_conductor_dimension_input_updates_derived_gmr(self):
        self.window.calculate_inductance()
        original_gmr = self.window.inductance_result.conductor_gmr_m
        original_insulation = float(self.window.input_fields["d_Ins"].text())

        self.window.input_fields["d_Ins"].setText(str(original_insulation + 0.1))
        self.assertEqual(self.window.inductance_gmr_display.text(), "—")
        self.window.calculate_inductance()

        self.assertLess(self.window.inductance_result.conductor_gmr_m, original_gmr)
        self.assertEqual(
            self.window.inductance_gmr_display.text(),
            f"{self.window.inductance_result.conductor_gmr_m * 1000.0:.6g}")

    def test_invalid_model_input_clears_stale_result(self):
        self.window.calculate_inductance()
        self.assertGreater(self.window.inductance_phase_table.rowCount(), 0)

        self.window.input_fields["inductance_mu_r"].setText("0")
        self.window.calculate_inductance()

        self.assertEqual(self.window.inductance_phase_table.rowCount(), 0)
        self.assertEqual(self.window.inductance_branch_table.rowCount(), 0)
        self.assertFalse(hasattr(self.window, "inductance_result"))
        self.assertIn("unavailable", self.window.inductance_summary.toPlainText().lower())

    def test_input_edit_immediately_invalidates_published_matrix(self):
        self.window.calculate_inductance()
        self.assertTrue(hasattr(self.window, "inductance_result"))

        self.window.input_fields["stack_length"].setText("999")

        self.assertFalse(hasattr(self.window, "inductance_result"))
        self.assertEqual(self.window.inductance_phase_table.rowCount(), 0)
        self.assertEqual(self.window.inductance_branch_table.rowCount(), 0)
        self.assertIn("stale", self.window.inductance_summary.toPlainText().lower())

    def test_visual_only_edit_keeps_physical_matrix_current(self):
        self.window.calculate_inductance()
        result = self.window.inductance_result

        self.window.input_fields["linewidth"].setText("3.0")

        self.assertIs(self.window.inductance_result, result)
        self.assertEqual(self.window.inductance_phase_table.rowCount(), 3)

    def test_model_input_change_reuses_layout_but_recalculates_matrix(self):
        self.window.calculate_inductance()
        generation = self.window.calculation_state.generation
        first_phase_matrix = self.window.inductance_result.phase_matrix_h.copy()
        first_phase_coupling = (
            self.window.inductance_result.phase_coupling_matrix.copy())

        self.window.input_fields["inductance_mu_r"].setText("2.0")
        self.window.calculate_inductance()

        self.assertEqual(self.window.calculation_state.generation, generation)
        self.assertAlmostEqual(
            self.window.inductance_result.phase_matrix_h[0, 0],
            2.0 * first_phase_matrix[0, 0],
        )
        np.testing.assert_allclose(
            self.window.inductance_result.phase_coupling_matrix,
            first_phase_coupling,
        )


if __name__ == "__main__":
    unittest.main()
