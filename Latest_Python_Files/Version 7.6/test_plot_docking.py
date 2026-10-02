"""Compact actions and non-destructive plot docking."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QApplication, QComboBox, QDialog, QLabel, QLineEdit
from main_pyqt6 import WindingApp


class PlotDockingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.w = WindingApp()
        fields = self.w.input_fields
        fields['winding_input_mode'].setCurrentText('Slots and poles')
        fields['num_slots'].setText('48')
        fields['ab'].setText('2')
        fields['pattern_name'].setText('BWP')
        self.w._resolve_slot_inputs()
        self.w.resize(1366, 768)
        self.w.show()
        self.app.processEvents()

    def tearDown(self):
        import matplotlib.pyplot as plt
        self.w.close()
        plt.close("all")

    def test_actions_are_uniform_and_toggle_moves_into_dependent_panel_when_collapsed(self):
        w = self.w
        self.assertLessEqual(w.import_config_button.height(), 32)
        buttons = [w.init_calc_button, w.import_config_button, w.export_config_button, w.save_layout_button,
                   w.export_branch_sheet_button, w.model_3d_button,
                   w.config_jmag_button]
        self.assertEqual({button.width() for button in buttons}, {w.action_button_width})
        self.assertIs(w.action_layout.itemAtPosition(0, 0).widget(), w.actions_toggle)
        self.assertIs(w.action_layout.itemAtPosition(1, 0).widget(), w.save_layout_button)
        self.assertIs(w.actions_toggle.parentWidget(), w.action_container)
        self.assertLess(w.actions_toggle.width(), w.action_button_width)
        height = w.canvas.height()
        w.actions_toggle.click()
        self.app.processEvents()
        self.assertTrue(w.actions_toggle.isVisible())
        self.assertIs(w.actions_toggle.parentWidget(), w.result_containers["parameters"])
        self.assertEqual(w.actions_toggle.text(), "▸")
        self.assertEqual(w.actions_toggle.width(), 24)
        self.assertEqual(
            w.actions_toggle.geometry().left(),
            w.result_collapse_buttons["parameters"].geometry().left(),
        )
        self.assertGreaterEqual(
            w.actions_toggle.geometry().bottom(),
            w.result_containers["parameters"].height() - 6,
        )
        self.assertFalse(w.import_config_button.isVisible())
        self.assertEqual(w.action_container.height(), 0)
        self.assertFalse(w.action_container.isVisible())
        self.assertGreater(w.canvas.height(), height)
        w.resize(1920, 1080)
        self.app.processEvents()
        self.assertGreaterEqual(
            w.actions_toggle.geometry().bottom(),
            w.result_containers["parameters"].height() - 6,
        )
        w.actions_toggle.click()
        self.assertTrue(w.import_config_button.isVisible())
        self.assertIs(w.actions_toggle.parentWidget(), w.action_container)
        self.assertEqual(w.actions_toggle.text(), "Actions ▾")
        self.assertTrue(w.action_container.isVisible())

    def test_workflow_is_a_two_by_two_grid_with_one_primary_plot_action(self):
        w = self.w
        self.assertIs(w.workflow_layout.itemAtPosition(0, 0).widget(), w.analyze_button)
        self.assertIs(w.workflow_layout.itemAtPosition(0, 1).widget(), w.layout_analyze_button)
        self.assertIs(w.workflow_layout.itemAtPosition(1, 0).widget(), w.phase_plot_button)
        self.assertIs(w.workflow_layout.itemAtPosition(1, 1).widget(), w.plot_button)
        self.assertTrue(w.plot_button.property("primaryAction"))
        self.assertTrue(w.phase_plot_button.property("secondaryAction"))
        self.assertFalse(bool(w.actions_toggle.property("actionToggle")))

    def test_plot_toolbar_tracks_view_and_moves_with_detached_canvas(self):
        w = self.w
        self.assertFalse(w.plot_fit_button.isEnabled())
        self.assertFalse(w.phase_view_controls.isVisible())
        w.preview_phase_division()
        self.assertEqual(w.plot_view_title.text(), "Phase Division")
        self.assertTrue(w.plot_fit_button.isEnabled())
        self.assertTrue(w.phase_view_controls.isVisible())
        w.plot_window_button.click()
        self.app.processEvents()
        self.assertIs(w.plot_toolbar.parentWidget(), w.plot_window)
        self.assertIs(w.plot_stack.parentWidget(), w.plot_window)
        self.assertTrue(w.phase_view_controls.isVisible())
        w.plot_window.close()
        self.app.processEvents()
        self.assertIs(w.plot_toolbar.parentWidget(), w.figure_container)
        w.plot_layout()
        self.assertEqual(w.plot_view_title.text(), "Plot Layout")
        self.assertFalse(w.phase_view_controls.isVisible())

    def test_result_panels_default_collapsed_summarize_and_restore_after_popout(self):
        w = self.w
        self.assertEqual(w.left_info_splitter.orientation(), Qt.Orientation.Horizontal)
        self.assertEqual(w.left_info_splitter.count(), 2)
        self.assertAlmostEqual(w.left_info_splitter.sizes()[0], w.left_info_splitter.sizes()[1], delta=20)
        for key, panel in w.result_panels.items():
            with self.subTest(panel=key):
                self.assertFalse(panel.isVisible())
                panel.setPlainText(f"{w.result_titles[key]}:\nFirst useful line\nSecond line")
                self.app.processEvents()
                summary = w.result_summary_labels[key]
                self.assertEqual(summary.text(), "First useful line")
                self.assertEqual(summary.toolTip(), "First useful line")
                w.result_collapse_buttons[key].click()
                self.assertTrue(panel.isVisible())
                self.assertFalse(summary.isVisible())
                w.result_collapse_buttons[key].click()
                self.assertFalse(panel.isVisible())
                w.result_window_buttons[key].click()
                self.app.processEvents()
                self.assertTrue(panel.isVisible())
                w.result_windows[key].close()
                self.app.processEvents()
                self.assertFalse(panel.isVisible())
                self.assertTrue(summary.isVisible())

    def test_detach_redock_keeps_canvas_and_phase_data(self):
        w = self.w
        w.preview_phase_division()
        data, canvas, stack = w.phase_preview, w.canvas, w.plot_stack
        with patch.object(w, "extract_parameters", side_effect=AssertionError("Must not regenerate")):
            w.plot_window_button.click()
            self.app.processEvents()
            self.assertTrue(w.plot_window.isVisible())
            self.assertIs(w.plot_stack.parentWidget(), w.plot_window)
            w.phase_view_selector.setCurrentText("Unwrapped")
            self.assertIs(w.phase_preview, data)
            with patch("main_pyqt6.os.makedirs"), patch.object(w.figure, "savefig") as save:
                w.save_layout_as_figure()
                save.assert_called_once()
            w.plot_window.close()
            self.app.processEvents()
            self.assertIs(w.plot_stack, stack)
            self.assertIs(w.canvas, canvas)
            self.assertIs(w.plot_stack.parentWidget(), w.figure_container)
            self.assertFalse(w.plot_window.isVisible())
            self.assertEqual(w.current_view_type, "phase")

    def test_detached_voltage_context_and_owner_close(self):
        w = self.w
        w.plot_window_button.click()
        w.tabs.setCurrentIndex(9)
        self.assertIs(w.plot_stack.currentWidget(), w.vd_plot_scroll_area)
        w.tabs.setCurrentIndex(0)
        self.assertIs(w.plot_stack.currentWidget(), w.canvas)
        w.plot_window.embed_button.click()
        self.assertFalse(w.plot_window.isVisible())

    def test_wheel_zoom_is_cursor_centered_for_primary_and_vd_plots(self):
        w = self.w
        w.preview_phase_division()
        for canvas, axes in ((w.canvas, w.ax), (w.vd_canvas, w.vd_ax)):
            axes.set_xlim(-10, 10)
            axes.set_ylim(-4, 6)
            event = SimpleNamespace(inaxes=axes, xdata=2.0, ydata=1.0, button="up", canvas=canvas)
            w._zoom_plot_event(event)
            self.assertLess(axes.get_xlim()[1] - axes.get_xlim()[0], 20)
            self.assertLess(axes.get_ylim()[1] - axes.get_ylim()[0], 10)
            self.assertAlmostEqual((2.0 - axes.get_xlim()[0]) / (axes.get_xlim()[1] - axes.get_xlim()[0]), .6)
            self.assertAlmostEqual((1.0 - axes.get_ylim()[0]) / (axes.get_ylim()[1] - axes.get_ylim()[0]), .5)
            w._zoom_plot_event(SimpleNamespace(inaxes=axes, xdata=2.0, ydata=1.0, button="down", canvas=canvas))
            self.assertAlmostEqual(axes.get_xlim()[1] - axes.get_xlim()[0], 20)
            self.assertAlmostEqual(axes.get_ylim()[1] - axes.get_ylim()[0], 10)

    def test_wheel_zoom_scales_grid_labels_but_keeps_title_and_right_legend_fixed(self):
        w = self.w
        w.phase_view_selector.setCurrentText("Circular")
        w.winding_view_selector.setCurrentText("Circular")
        w.preview_phase_division()
        slot_label = next(text for text in w.ax.texts if text.get_text() == "1")
        sign_label = next(text for text in w.ax.texts if text.get_text() == "+")
        legend_label = w.ax.get_legend().get_texts()[0]
        slot_size, legend_size = slot_label.get_fontsize(), legend_label.get_fontsize()
        sign_size, title_size = sign_label.get_fontsize(), w.ax.title.get_fontsize()
        w._zoom_plot_event(SimpleNamespace(inaxes=w.ax, xdata=0.0, ydata=0.0,
                                            button="up", canvas=w.canvas))
        self.assertGreater(slot_label.get_fontsize(), slot_size)
        self.assertGreater(sign_label.get_fontsize(), sign_size)
        self.assertAlmostEqual(legend_label.get_fontsize(), legend_size)
        self.assertAlmostEqual(w.ax.title.get_fontsize(), title_size)
        w._zoom_plot_event(SimpleNamespace(inaxes=w.ax, xdata=0.0, ydata=0.0,
                                            button="down", canvas=w.canvas))
        self.assertAlmostEqual(slot_label.get_fontsize(), slot_size)
        self.assertAlmostEqual(sign_label.get_fontsize(), sign_size)
        self.assertAlmostEqual(legend_label.get_fontsize(), legend_size)
        self.assertAlmostEqual(w.ax.title.get_fontsize(), title_size)

    def test_phase_fit_restores_view_without_recreating_artists(self):
        w = self.w
        w.preview_phase_division()
        canonical = (w.ax.get_xlim(), w.ax.get_ylim())
        artists = tuple(w.ax.get_children())
        data = w.phase_preview
        w._zoom_plot_event(SimpleNamespace(inaxes=w.ax, xdata=0.0, ydata=0.0,
                                          button="up", canvas=w.canvas))
        self.assertNotEqual(w.ax.get_xlim(), canonical[0])
        with patch.object(w, "_render_phase_preview") as render:
            w.phase_fit_button.click()
            render.assert_not_called()
        self.assertEqual(tuple(w.ax.get_children()), artists)
        self.assertIs(w.phase_preview, data)
        for actual, expected in zip((*w.ax.get_xlim(), *w.ax.get_ylim()),
                                    (*canonical[0], *canonical[1])):
            self.assertAlmostEqual(actual, expected)

    def test_plot_layout_fit_restores_view_without_recomputing_geometry(self):
        w = self.w
        w.plot_layout()
        w.canvas.draw()
        canonical = (w.ax.get_xlim(), w.ax.get_ylim())
        artists = tuple(w.ax.get_children())
        w._zoom_plot_event(SimpleNamespace(inaxes=w.ax, xdata=0.0, ydata=0.0,
                                          button="up", canvas=w.canvas))
        self.assertNotEqual(w.ax.get_xlim(), canonical[0])
        with patch.object(w, "plot_layout") as plot, patch.object(w, "extract_parameters") as extract:
            w.plot_fit_button.click()
            plot.assert_not_called()
            extract.assert_not_called()
        self.assertEqual(tuple(w.ax.get_children()), artists)
        for actual, expected in zip((*w.ax.get_xlim(), *w.ax.get_ylim()),
                                    (*canonical[0], *canonical[1])):
            self.assertAlmostEqual(actual, expected)

    def test_phase_resize_reapplies_view_without_recreating_artists(self):
        w = self.w
        w.preview_phase_division()
        artists = tuple(w.ax.get_children())
        data = w.phase_preview
        with patch.object(w, "_render_phase_preview") as render, \
                patch.object(w.canvas, "draw_idle") as draw:
            w._on_plot_resize(SimpleNamespace(canvas=w.canvas))
            render.assert_not_called()
            draw.assert_called()
        self.assertEqual(tuple(w.ax.get_children()), artists)
        self.assertIs(w.phase_preview, data)

    def test_repeated_plot_layout_reuses_unchanged_artists(self):
        w = self.w
        w.plot_layout()
        artists = tuple(id(artist) for artist in w.ax.get_children())
        with patch("main_pyqt6.dfig.draw_winding_scheme_ax",
                   side_effect=AssertionError("Must reuse the current plot")), \
             patch("main_pyqt6.dfig.draw_circular_winding_layout",
                   side_effect=AssertionError("Must reuse the current plot")):
            w.plot_layout()
        self.assertEqual(tuple(id(artist) for artist in w.ax.get_children()), artists)

    def test_repeated_plot_layout_uses_saved_calculation(self):
        w = self.w
        w.plot_layout()
        generation = w.calculation_state.generation
        with patch.object(w, "extract_parameters",
                          side_effect=AssertionError("Must use saved calculation")) as extract:
            w.plot_layout()
        extract.assert_not_called()
        self.assertEqual(w.calculation_state.generation, generation)
        self.assertIn("Reused unchanged winding layout plot.", w.message_log.toPlainText())

    def test_plot_layout_recalculates_after_input_change(self):
        w = self.w
        w.plot_layout()
        generation = w.calculation_state.generation
        field = w.input_fields["num_layers"]
        blocked = field.blockSignals(True)
        field.setText("4" if field.text() != "4" else "6")
        field.blockSignals(blocked)
        with patch.object(w, "extract_parameters", wraps=w.extract_parameters) as extract:
            w.plot_layout()
        extract.assert_called_once_with(candidate_only=False)
        self.assertGreater(w.calculation_state.generation, generation)

    def test_q4_bwp_auto_repeated_plot_skips_recipe_search(self):
        w = self.w
        w._apply_config_payload({"inputs": {
            "winding_input_mode": "q and poles", "q": "4",
            "num_poles": "8", "num_layers": "6", "num_phases": "3",
            "ab": "4", "pattern_name": "BWP", "q_divider": "4",
            "pp_divider": "1", "p2_divider": "1", "tp_type": "Auto",
            "inlet_from_weld_side": 0, "radial_shift": 0,
            "phase_shift_pattern": "None", "phase_shift": "0", "PSL": "1",
        }})
        w.plot_layout()
        generation = w.calculation_state.generation
        with patch("main_pyqt6.gw.get_auto_configured_layout",
                   side_effect=AssertionError("Must not repeat recipe search")) as search:
            w.plot_layout()
        search.assert_not_called()
        self.assertEqual(w.calculation_state.generation, generation)

    def test_phase_fit_grid_restores_full_grid_and_cond_phase_summary(self):
        w = self.w
        w.preview_phase_division()
        counts = w.phase_preview["summary"]["counts"]
        self.assertEqual(len(set(counts)), 1)
        self.assertEqual(w.phase_cond_phase_label.text(), f"Cond/Phase: {counts[0]}")
        initial_width = w.ax.get_xlim()[1] - w.ax.get_xlim()[0]
        w._zoom_plot_event(SimpleNamespace(inaxes=w.ax, xdata=0.0, ydata=0.0,
                                            button="up", canvas=w.canvas))
        self.assertLess(w.ax.get_xlim()[1] - w.ax.get_xlim()[0], initial_width)
        w.phase_fit_button.click()
        self.assertAlmostEqual(w.ax.get_xlim()[1] - w.ax.get_xlim()[0], initial_width)

    def test_phase_count_summary_preserves_unequal_phase_counts(self):
        self.assertEqual(WindingApp._format_phase_counts((96, 96, 96)), "Cond/Phase: 96")
        self.assertEqual(WindingApp._format_phase_counts((95, 96, 97)),
                         "Cond/Phase: A 95  B 96  C 97")

    def test_result_windows_detach_original_panels_and_restore_on_close_or_reject(self):
        w = self.w
        panels = {"parameters": w.dependent_params_display, "layout": w.layout_display}
        self.assertEqual(set(w.result_window_buttons), set(panels))
        for key, panel in panels.items():
            with self.subTest(panel=key):
                parent = panel.parentWidget()
                panel.setPlainText(f"Preserved {key} result\nSecond line")
                contents = panel.toPlainText()
                for dismiss in ("close", "reject"):
                    w.result_window_buttons[key].click()
                    self.app.processEvents()
                    dialog = w.result_windows[key]
                    self.assertIsInstance(dialog, QDialog)
                    self.assertTrue(dialog.isVisible())
                    self.assertTrue(dialog.isWindow())
                    self.assertIs(panel.window(), dialog)
                    self.assertIsNot(panel.parentWidget(), parent)
                    original_size = dialog.size()
                    dialog.resize(original_size.width() + 100, original_size.height() + 80)
                    self.app.processEvents()
                    self.assertGreater(dialog.width(), original_size.width())
                    self.assertGreater(dialog.height(), original_size.height())
                    self.assertEqual(panel.toPlainText(), contents)
                    getattr(dialog, dismiss)()
                    self.app.processEvents()
                    self.assertFalse(dialog.isVisible())
                    self.assertIs(panel.parentWidget(), parent)
                    self.assertEqual(panel.toPlainText(), contents)
        self.assertEqual(set(w.result_windows), set(panels))

    def test_result_windows_are_independent_and_close_with_owner(self):
        w = self.w
        for key in ("parameters", "layout"):
            w.result_window_buttons[key].click()
        self.app.processEvents()
        parameters, layout = (w.result_windows[key] for key in ("parameters", "layout"))
        self.assertIsNot(parameters, layout)
        self.assertTrue(parameters.isVisible())
        self.assertTrue(layout.isVisible())
        parameters.close()
        self.app.processEvents()
        self.assertTrue(layout.isVisible())
        w.result_window_buttons["parameters"].click()
        w.close()
        self.app.processEvents()
        self.assertTrue(all(not dialog.isVisible() for dialog in w.result_windows.values()))

    def test_embedded_plot_uses_a_light_neutral_workspace_in_both_themes(self):
        w = self.w
        self.assertEqual(w.figure.get_facecolor()[:3], (246 / 255, 247 / 255, 249 / 255))
        self.assertEqual(w.ax.patch.get_alpha(), 0.0)
        w.input_fields["ui_theme"].setCurrentText("Dark")
        w.apply_settings(silent=True)
        self.assertEqual(w.figure.get_facecolor()[:3], (246 / 255, 247 / 255, 249 / 255))
        w.plot_layout()
        self.assertEqual(w.ax.patch.get_alpha(), 0.0)

    def test_grid_plots_use_full_width_for_center_legends_without_square_boxing(self):
        w = self.w
        w.phase_view_selector.setCurrentText("Circular")
        w.winding_view_selector.setCurrentText("Circular")
        w.plot_layout()
        winding_box = w.ax.get_position()
        self.assertGreater(winding_box.width, .95)
        self.assertGreater(winding_box.height, .95)
        self.assertEqual(w.ax.get_adjustable(), "datalim")
        w.preview_phase_division()
        phase_box = w.ax.get_position()
        self.assertGreater(phase_box.width, .86)
        self.assertLess(phase_box.width, .92)
        self.assertGreater(phase_box.height, .7)
        self.assertEqual(w.ax.get_adjustable(), "datalim")
        self.assertEqual(w.ax.get_legend()._ncols, 1)
        w.update_voltage_difference_view()
        voltage_box = w.vd_ax.get_position()
        self.assertGreater(voltage_box.width, .75)
        self.assertEqual(w.vd_ax.get_aspect(), "auto")
        w.plot_winding_function_and_table()
        self.assertEqual(w.ax_wf1.get_aspect(), "auto")

    def test_grid_legend_positions_keep_center_and_protect_right_hand_grid(self):
        w = self.w
        w.phase_view_selector.setCurrentText("Circular")
        w.winding_view_selector.setCurrentText("Circular")
        expected_positions = {
            "center": (w.ax.transData, 10, (0.0, 0.0), False),
            "upper right": (w.ax.transAxes, 2, (1.02, 1.0), True),
            "lower right": (w.ax.transAxes, 3, (1.02, 0.0), True),
            "right": (w.ax.transAxes, 6, (1.02, 0.5), True),
        }
        for position, (transform, loc, anchor, outside) in expected_positions.items():
            with self.subTest(position=position):
                w.input_fields["legend_position"].setCurrentText(position)
                w.plot_layout()
                legend = w.ax.get_legend()
                self.assertIs(legend.get_bbox_to_anchor()._transform, transform)
                self.assertEqual(legend._loc, loc)
                expected = transform.transform(anchor)
                actual = legend.get_bbox_to_anchor().bounds[:2]
                self.assertAlmostEqual(actual[0], expected[0])
                self.assertAlmostEqual(actual[1], expected[1])
                self.assertLess(w.ax.get_position().width, .85) if outside else self.assertGreater(w.ax.get_position().width, .95)
        w.preview_phase_division()
        phase_legend = w.ax.get_legend()
        self.assertIs(phase_legend.get_bbox_to_anchor()._transform, w.ax.transAxes)
        before = phase_legend.get_bbox_to_anchor().bounds[:2]
        w._zoom_plot_event(SimpleNamespace(inaxes=w.ax, xdata=0.0, ydata=0.0,
                                            button="up", canvas=w.canvas))
        w.canvas.draw()
        after = phase_legend.get_bbox_to_anchor().bounds[:2]
        self.assertEqual(before, after)

    def test_layout_tab_uses_two_parameter_columns_and_five_pattern_columns(self):
        w = self.w
        grid = w.layout_params_grid
        self.assertEqual(grid.itemAtPosition(0, 0).widget().text(), "Pattern:")
        self.assertEqual(grid.itemAtPosition(0, 2).widget().text(), "Shift mode:")
        self.assertEqual(grid.itemAtPosition(1, 0).widget().text(), "Weld inlet:")
        self.assertEqual(grid.itemAtPosition(1, 2).widget().text(), "CHW shift:")
        self.assertIsNotNone(w.config_inlet_positions_button)
        self.assertEqual(w.pattern_buttons_layout.columnCount(), 5)
        self.assertEqual(w.pattern_buttons_layout.count(), 10)
        w.tabs.setCurrentIndex(4)
        self.app.processEvents()
        self.assertEqual(w.tabs.currentWidget().horizontalScrollBar().maximum(), 0)
        w.plot_window_button.click()
        w.plot_window.reject()
        self.assertFalse(w.plot_window.isVisible())
        w.plot_window_button.click()
        w.close()
        self.assertFalse(w.plot_window.isVisible())

    def test_winding_pattern_selector_matches_q_input_right_edge(self):
        w = self.w
        pattern = w.layout_pattern_selector
        q_input = w.input_fields["q"]
        divider_row = w.divider_row_container
        pattern_right = pattern.mapToGlobal(QPoint(pattern.width(), 0)).x()
        q_right = q_input.mapToGlobal(QPoint(q_input.width(), 0)).x()
        divider_right = divider_row.mapToGlobal(QPoint(divider_row.width(), 0)).x()
        self.assertEqual(pattern.width(), q_input.width())
        self.assertEqual(pattern_right, q_right)
        self.assertEqual(divider_right, q_right)

    def test_winding_input_mode_and_default_columns_are_compact(self):
        w = self.w
        self.assertEqual(w.input_fields["winding_input_mode"].width(), 150)
        self.assertEqual(w.compact_parameter_grids["Winding"].horizontalSpacing(), 8)

    def test_parameter_tabs_use_shared_compact_two_column_geometry(self):
        w = self.w
        for name in ("Stator", "Inslot", "End Winding"):
            grid = w.compact_parameter_grids[name]
            self.assertEqual(grid.contentsMargins().left(), 16)
            self.assertEqual(grid.contentsMargins().top(), 14)
            self.assertGreaterEqual(grid.columnCount(), 4)
            self.assertGreater(grid.itemAtPosition(0, 2).widget().text().__len__(), 0)
        self.assertEqual(w.tabs.widget(1).widget().layout(), w.compact_parameter_grids["Stator"])

    def test_parameter_tabs_share_label_and_input_typography(self):
        w = self.w
        label_sizes = set()
        input_sizes = set()
        for index in range(8):
            page = w.tabs.widget(index).widget()
            label_sizes.update(round(label.font().pointSizeF(), 2)
                               for label in page.findChildren(QLabel))
            fields = [*page.findChildren(QComboBox)]
            fields.extend(field for field in page.findChildren(QLineEdit)
                          if not isinstance(field.parentWidget(), QComboBox))
            input_sizes.update(round(field.font().pointSizeF(), 2) for field in fields)
        self.assertEqual(label_sizes, {10.0})
        self.assertEqual(input_sizes, {11.0})

    def test_figure_and_plot_config_fit_the_standard_panel_width(self):
        w = self.w
        for index, name in ((6, "Figure"), (7, "Plot Config")):
            w.tabs.setCurrentIndex(index)
            self.app.processEvents()
            self.assertEqual(w.tabs.currentWidget().horizontalScrollBar().maximum(), 0)
            grid = w.compact_parameter_grids[name]
            self.assertEqual(grid.contentsMargins().left(), 16)
            self.assertEqual(grid.contentsMargins().top(), 14)
        self.assertTrue(w.plot_button.property("primaryAction"))

    def test_same_layer_route_is_available_in_collapsed_figure_advanced_settings(self):
        w = self.w
        w.tabs.setCurrentIndex(6)
        self.app.processEvents()
        self.assertFalse(w.figure_advanced_content.isVisible())
        self.assertEqual(w.input_fields["same_layer_route_style"].currentText(), "Radial-center arc")
        w.figure_advanced_toggle.click()
        self.assertTrue(w.figure_advanced_content.isVisible())

    def test_winding_factor_has_its_own_detachable_canvas_and_tabs_keep_resize_choice(self):
        w = self.w
        self.assertLessEqual(w.wf_plot_button.maximumWidth(), 240)
        self.assertIs(w.wf_detach_button.parentWidget(), w.tabs.widget(8).widget())
        self.assertEqual(w.wf_detach_button.height(), w.wf_plot_button.height())
        canvas = w.canvas_wf
        w.wf_detach_button.click()
        self.app.processEvents()
        self.assertTrue(w.wf_plot_window.isVisible())
        self.assertIs(canvas.parentWidget(), w.wf_plot_window)
        w.wf_plot_window.close()
        self.app.processEvents()
        self.assertIs(canvas.parentWidget(), w.wf_plot_container)

        w.tabs.setCurrentIndex(0)
        w.left_splitter.setSizes([430, 270])
        expected = w.left_splitter.sizes()
        w._remember_left_splitter_sizes()
        w.tabs.setCurrentIndex(1)
        self.assertEqual(w._left_splitter_normal_sizes, expected)
        self.assertGreater(w.left_splitter.sizes()[1], 0)

    def test_checkboxes_keep_an_outlined_box_when_checked(self):
        style = self.w.styleSheet()
        self.assertIn("QCheckBox::indicator:checked", style)
        self.assertIn("border: 1px solid", style)
        checkmark = Path(__file__).with_name("assets") / "checkmark.svg"
        self.assertTrue(checkmark.is_file())

    def test_transposition_parameters_are_arranged_in_two_columns(self):
        w = self.w
        self.assertEqual([w.tp_type_field.itemText(i) for i in range(w.tp_type_field.count())],
                         ['Auto', 'Regular', 'Times', 'Interval'])
        self.assertEqual(w.tp_type_field.currentText(), "Auto")
        grid = w.tp_params_grid
        self.assertEqual(grid.itemAtPosition(0, 0).widget().text(), "Intervals of T.P.:")
        self.assertEqual(grid.itemAtPosition(0, 3).widget().text(), "Times of T.P.:")
        self.assertEqual(grid.itemAtPosition(1, 0).widget().text(), "Uniform T.P.:")
        self.assertEqual(grid.itemAtPosition(1, 3).widget().text(), "First-layer T.P.:")
        self.assertEqual(grid.itemAtPosition(2, 0).widget().text(), "Last-layer T.P.:")
        self.assertEqual(grid.itemAtPosition(2, 3).widget().text(), "Jump-layer T.P.:")

        w.tp_type_field.setCurrentText("Interval")
        self.assertFalse(w.tp_fields["tp_interval"].isReadOnly())
        self.assertTrue(w.tp_fields["tp_times"].isReadOnly())


if __name__ == "__main__":
    unittest.main()
