"""Business callback regression checks after the classic layout restoration."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import zipfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtWidgets import QApplication, QPushButton
from PyQt6.QtGui import QCloseEvent
from main_pyqt6 import WindingApp


class ClassicBusinessRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = WindingApp()
        fields = self.window.input_fields
        fields['winding_input_mode'].setCurrentText('Slots and poles')
        fields['num_slots'].setText('48')
        fields['ab'].setText('2')
        fields['pattern_name'].setText('BWP')
        self.window._resolve_slot_inputs()

    def tearDown(self):
        import matplotlib.pyplot as plt
        plt.close('all')
        self.window.close()

    def test_fractional_config_file_roundtrip_preserves_slots(self):
        w = self.window
        w.input_fields['num_slots'].setText('36')
        w.input_fields['num_poles'].setText('8')
        w.input_fields['q'].setText('1.5')
        w.input_fields['radii_gap'].setText('0.35')
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'config.json')
            with patch.object(w, '_default_config_path', return_value=path), \
                    patch('main_pyqt6.QFileDialog.getSaveFileName', return_value=(path, '')):
                w.export_config()
            saved = json.loads(Path(path).read_text(encoding='utf-8'))
            self.assertEqual(saved['app_version'], '7.6')
            self.assertEqual(saved['inputs']['num_slots'], '36')
            w.input_fields['num_slots'].setText('48')
            w.input_fields['radii_gap'].setText('0.20')
            with patch.object(w, '_config_directory', return_value=directory), \
                    patch('main_pyqt6.QFileDialog.getOpenFileName', return_value=(path, '')):
                w.import_config()
            self.assertEqual(w.input_fields['num_slots'].text(), '36')
            self.assertEqual(w.input_fields['radii_gap'].text(), '0.35')
            self.assertEqual(float(w._resolve_slot_inputs()[0]), 1.5)

    def test_copied_config_examples_import(self):
        examples = sorted(Path(__file__).with_name('configs').glob('*.json'))
        self.assertTrue(examples)
        for path in examples:
            with self.subTest(config=path.name):
                payload = json.loads(path.read_text(encoding='utf-8'))
                self.window._apply_config_payload(payload)
                self.assertEqual(self.window._build_config_payload()['app_version'], '7.6')

    def test_branch_export_writes_real_workbook(self):
        w = self.window
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'branches.xlsx')
            with patch.object(w, '_default_branch_workbook_path', return_value=path), \
                    patch('main_pyqt6.QFileDialog.getSaveFileName', return_value=(path, '')):
                w.export_branch_connection_sheets()
            self.assertTrue(Path(path).is_file(), w.message_log.toPlainText())
            with zipfile.ZipFile(path) as workbook:
                self.assertIsNone(workbook.testzip())
                self.assertIn('xl/workbook.xml', workbook.namelist())
                sheets = [name for name in workbook.namelist()
                          if name.startswith('xl/worksheets/sheet')]
                self.assertGreater(len(sheets), 1)
                self.assertIn(b'<row', workbook.read(sheets[0]))
                parameter_sheet = workbook.read(sheets[0])
                self.assertIn(b'app_version', parameter_sheet)
                self.assertIn(b'7.6', parameter_sheet)

    def test_legacy_and_fraction_input_configs_use_exact_slot_count(self):
        w = self.window
        for q, slots in [('1.5', '36'), ('5/2', '60'), ('7/2', '84')]:
            with self.subTest(q=q):
                w._apply_config_payload({'inputs': {'q': q, 'num_poles': '8', 'num_phases': '3'}})
                self.assertEqual(w.input_fields['winding_input_mode'].currentText(), 'q and poles')
                self.assertEqual(w.input_fields['num_slots'].text(), slots)
                self.assertTrue(w.input_fields['num_slots'].isReadOnly())
                w.preview_phase_division()
                self.assertEqual(w.current_view_type, 'phase')

    def test_figure_apply_uses_current_route_gap(self):
        w = self.window
        w.input_fields['radii_gap'].setText('0.35')
        buttons = [button for button in w.findChildren(QPushButton)
                   if button.text() == 'Apply Figure Settings']
        self.assertEqual(len(buttons), 1)
        buttons[0].click()
        self.assertEqual(w.current_view_type, 'winding')
        self.assertEqual(w.Line_Para.radii_gap, .35)
        self.assertTrue(w.ax.patches)

    def test_winding_factor_and_voltage_difference_default_callbacks(self):
        w = self.window
        w.plot_winding_function_and_table()
        self.assertTrue(hasattr(w, 'winding_func'), w.message_log.toPlainText())
        self.assertTrue(w.ax_wf1.lines or w.ax_wf1.patches)
        original_extract = w.extract_parameters
        with patch.object(w, 'extract_parameters', wraps=original_extract) as tracked_extract:
            result = w.update_voltage_difference_view()
        self.assertEqual(tracked_extract.call_count, 1)
        self.assertIsNotNone(result, w.message_log.toPlainText())
        self.assertIn('Max voltage difference', w.vd_result_display.toPlainText())
        for attribute in (
            'vd_same_slot_value',
            'vd_adjacent_slot_same_layer_value',
            'vd_adjacent_slot_adjacent_layer_value',
        ):
            self.assertNotEqual(getattr(w, attribute).text(), '—')
        self.assertIs(w.plot_stack.currentWidget(), w.vd_plot_scroll_area)

    def test_winding_function_refreshes_after_input_change(self):
        w = self.window
        w.plot_winding_function_and_table()
        w.input_fields['num_slots'].setText('72')
        w.plot_winding_function_and_table()
        self.assertEqual(w.Winding_Para.num_slots, 72)

    def test_vd_optimization_does_not_apply_stale_result(self):
        w = self.window
        w._vd_optimize_input_signature = w._vd_optimize_source_signature()
        original = list(w.volt_diff_inlet_adjustments_all)
        w.input_fields['num_slots'].setText('72')
        result = SimpleNamespace(best_adjustments=[3], phase_a_template=[3], score=(1,))
        w._handle_vd_optimize_finished(result)
        self.assertEqual(w.volt_diff_inlet_adjustments_all, original)
        self.assertIn('discarded', w.message_log.toPlainText().lower())

    def test_vd_optimization_preserves_pending_branch_edit(self):
        w = self.window
        w.update_voltage_difference_view()
        self.assertTrue(w.vd_adjustment_inputs)
        w._vd_optimize_input_signature = w._vd_optimize_source_signature()
        original = list(w.volt_diff_inlet_adjustments_all)
        edit = w.vd_adjustment_inputs[0][1]
        edit.setText('7')
        result = SimpleNamespace(best_adjustments=[3], phase_a_template=[3], score=(1,))
        w._handle_vd_optimize_finished(result)
        self.assertEqual(edit.text(), '7')
        self.assertEqual(w.volt_diff_inlet_adjustments_all, original)

    def test_close_waits_for_running_vd_optimization(self):
        w = self.window
        w.vd_optimize_thread = SimpleNamespace(isRunning=lambda: True)
        event = QCloseEvent()
        w.closeEvent(event)
        self.assertFalse(event.isAccepted())
        w.vd_optimize_thread = None


if __name__ == '__main__':
    unittest.main()
