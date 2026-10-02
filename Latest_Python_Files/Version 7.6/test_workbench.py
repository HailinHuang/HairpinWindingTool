"""Classic layout and pattern-independent phase preview regression checks."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication, QScrollArea
from calculation_state import CalculationState
import get_winding_pattern as gw
import cond_info_operation as cio
from explicit_connections import validate_branches
from phase_topology import default_phase_map, phase_map
from main_pyqt6 import WindingApp


class ClassicLayoutTests(unittest.TestCase):
    def test_zpp_layout_shift_plots_after_connection_validation(self):
        w = self.window
        fields = w.input_fields
        fields['winding_input_mode'].setCurrentText('q and poles')
        fields['pattern_name'].setText('ZPP')
        for key, value in dict(q=2, num_poles=8, num_layers=6,
                               num_phases=3, ab=8).items():
            fields[key].setText(str(value))
        w.q_divider_box.setCurrentText('2')
        w.pp_divider_box.setCurrentText('4')
        w.p2_divider_box.setCurrentText('1')
        fields['inlet_from_weld_side'].setChecked(True)
        fields['phase_shift_pattern'].setCurrentText('Normal')
        fields['phase_shift'].setText('1')
        fields['PSL'].setText('1')
        w.plot_layout()
        self.assertEqual(w.current_view_type, 'winding')
        self.assertEqual(w.Layout_Para.phase_shift_list, [0, 1] * 3)
        self.assertTrue(w.base_db_conductor_id.layout_report['layout_retained'])

        w._refresh_route_option_availability()
        self.assertTrue(fields['radial_shift'].isEnabled())
        fields['radial_shift'].setChecked(True)
        w.plot_layout()
        self.assertEqual(w.current_view_type, 'winding')
        self.assertTrue(w.base_db_conductor_id.layout_report['layout_retained'])
        w.analyze_layouts()
        self.assertNotIn('unavailable', w.layout_display.toPlainText().lower())

        w.tp_type_field.setCurrentText('Auto')
        self.assertTrue(w.apply_auto_configuration(keep_auto=True))
        w.plot_layout()
        self.assertEqual(w.current_view_type, 'winding')
        self.assertTrue(w.base_db_conductor_id.layout_report['layout_retained'])

    def test_naa_edit_refreshes_pattern_support_after_bwp_plot(self):
        w = self.window
        fields = w.input_fields
        fields['winding_input_mode'].setCurrentText('q and poles')
        fields['pattern_name'].setText('BWP')
        for key, value in dict(q=2, num_poles=8, num_layers=6,
                               num_phases=3, ab=4).items():
            fields[key].setText(str(value))
        w.q_divider_box.setCurrentText('2')
        w.pp_divider_box.setCurrentText('2')
        w.p2_divider_box.setCurrentText('1')
        w.tp_type_field.setCurrentText('Auto')
        self.assertTrue(w.apply_auto_configuration(keep_auto=True))
        w.plot_layout()
        self.assertEqual(w.current_view_type, 'winding')

        fields['ab'].setText('8')
        fields['ab'].editingFinished.emit()
        w._refresh_pattern_availability()
        self.assertEqual(w._selected_dividers(), (2, 4, 1))
        self.assertEqual(w.current_view_type, 'winding')
        self.assertTrue(w.pattern_buttons['TSP'].isEnabled())
        w.plot_layout()
        self.assertEqual(w.current_view_type, 'winding')

    def test_uwp_times_one_plots_without_duplicate_conductors(self):
        w = self.window
        fields = w.input_fields
        fields['winding_input_mode'].setCurrentText('q and poles')
        fields['pattern_name'].setText('UWP')
        for key, value in dict(q=2, num_poles=8, num_layers=4,
                               num_phases=3, ab=2).items():
            fields[key].setText(str(value))
        w.q_divider_box.setCurrentText('1')
        w.pp_divider_box.setCurrentText('1')
        w.p2_divider_box.setCurrentText('2')
        w.tp_type_field.setCurrentText('Times')
        w.tp_fields['tp_times'].setText('1')
        with patch('main_pyqt6.QMessageBox.warning') as warning:
            w.plot_layout()
        warning.assert_not_called()
        self.assertEqual(w.current_view_type, 'winding')
        paths = w.base_db_conductor_id
        coordinates = [tuple(node[:2]) for _, path in paths for node in path]
        self.assertEqual(len(coordinates), 192)
        self.assertEqual(len(set(coordinates)), 192)
        self.assertEqual(w.TP_info.tp_times, 1)

    def test_plot_parameter_extraction_preserves_manual_selected_route_tp(self):
        w = self.window
        fields = w.input_fields
        fields['winding_input_mode'].setCurrentText('q and poles')
        fields['pattern_name'].setText('SSP')
        for key, value in dict(q=2, num_poles=8, num_layers=6,
                               num_phases=5, ab=2).items():
            fields[key].setText(str(value))
        w.q_divider_box.setCurrentText('1')
        w.pp_divider_box.setCurrentText('2')
        w.p2_divider_box.setCurrentText('1')
        w.tp_type_field.setCurrentText('Times')
        w.tp_fields['tp_times'].setText('1')
        self.assertEqual(w._validate_divider_route().status, 'enabled')
        w.extract_parameters()
        self.assertEqual(w.TP_info.tp_type, 'Times')
        self.assertEqual(w.TP_info.tp_times, 1)
        self.assertEqual(len(w.base_db_conductor_id), 10)
        self.assertTrue(w.base_db_conductor_id.layout_report['layout_retained'])

    def test_uwp_two_branch_default_is_not_falsely_disabled(self):
        w = self.window
        f = w.input_fields
        f['winding_input_mode'].setCurrentText('q and poles')
        f['q'].setText('4')
        f['num_poles'].setText('8')
        f['num_layers'].setText('4')
        f['num_phases'].setText('3')
        f['ab'].setText('2')
        f['pattern_name'].setText('UWP')
        w._refresh_divider_status()
        self.assertEqual(w._validate_divider_route(check_only=True).status, 'enabled')
        self.assertIn('enabled', w.divider_status.text().lower())

    def test_odd_q_ssp_p2_option_is_disabled(self):
        w = self.window
        f = w.input_fields
        f['winding_input_mode'].setCurrentText('q and poles')
        f['q'].setText('3')
        f['num_poles'].setText('4')
        f['num_layers'].setText('4')
        f['num_phases'].setText('3')
        f['ab'].setText('2')
        f['pattern_name'].setText('SSP')
        w._update_half_divider_availability()
        index = w.p2_divider_box.findText('2')
        self.assertGreaterEqual(index, 0)
        self.assertFalse(w.p2_divider_box.model().item(index).isEnabled())

    def test_slp_pp_inlet_adjustment_checks_final_branch_edges(self):
        w = self.window
        fields = w.input_fields
        fields['winding_input_mode'].setCurrentText('q and poles')
        fields['q'].setText('2')
        fields['num_poles'].setText('8')
        fields['num_layers'].setText('6')
        fields['num_phases'].setText('3')
        fields['ab'].setText('2')
        fields['pattern_name'].setText('SLP')
        w._resolve_slot_inputs()
        w._refresh_pattern_availability()
        w.q_divider_box.setCurrentText('1')
        w.pp_divider_box.setCurrentText('2')
        w.p2_divider_box.setCurrentText('1')
        w.tp_type_field.setCurrentText('Times')
        w.tp_fields['tp_times'].setText('1')
        w.inlet_index_adjustments_phase_a = [2, 0]

        with self.assertRaisesRegex(ValueError, 'invalid edge'):
            w.extract_parameters()

    def test_tlp_q_and_pp_two_ui_generation_and_config_roundtrip(self):
        w = self.window
        f = w.input_fields
        f['winding_input_mode'].setCurrentText('q and poles')
        f['q'].setText('2')
        f['num_poles'].setText('8')
        f['num_layers'].setText('4')
        f['pattern_name'].setText('TLP')
        f['ab'].setText('4')
        w.q_divider_box.setCurrentText('2')
        w.pp_divider_box.setCurrentText('2')
        w.p2_divider_box.setCurrentText('1')
        self.assertIn('eligible', w.divider_status.text().lower(),
                      w.divider_status.toolTip())
        w.extract_parameters()
        self.assertEqual(w.Winding_Para.branch_dividers, (2, 2, 1))
        self.assertEqual(w.base_db_conductor_id.layout_report[
            'pattern_route']['rule_id'], 'tlp_q_pp_two')
        before = list(w.base_db_conductor_id)
        payload = w._build_config_payload()
        w._apply_config_payload(payload)
        w.extract_parameters()
        self.assertEqual(list(w.base_db_conductor_id), before)

    def test_shared_q_and_pp_second_sector_routes_are_available_in_ui(self):
        w = self.window
        f = w.input_fields
        f['winding_input_mode'].setCurrentText('q and poles')
        f['num_poles'].setText('8')
        f['num_phases'].setText('3')
        for pattern, q, layers, q_divider, weld_side in (
                ('TSP', 2, 4, 2, False),
                ('TLP', 2, 4, 2, False),
                ('ZPP', 4, 4, 2, True)):
            with self.subTest(pattern=pattern):
                f['pattern_name'].setText(pattern)
                f['q'].setText(str(q))
                f['num_layers'].setText(str(layers))
                f['ab'].setText(str(2*q_divider))
                f['inlet_from_weld_side'].setChecked(weld_side)
                w.q_divider_box.setCurrentText('1')
                w.pp_divider_box.setCurrentText('1')
                w.q_divider_box.setCurrentText(str(q_divider))
                w.pp_divider_box.setCurrentText('2')
                w.p2_divider_box.setCurrentText('1')
                self.assertIn('eligible', w.divider_status.text().lower(),
                              w.divider_status.toolTip())
                w.extract_parameters()
                report = w.base_db_conductor_id.layout_report
                self.assertEqual(
                    report['pattern_route']['rule_id'],
                    f'{pattern.lower()}_q_pp_two')
                self.assertIn('sector_deployment', report)
                self.assertEqual(
                    report['pattern_identity']['status'], 'valid')

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = WindingApp()
        self.window.resize(1366, 768)
        self.window.show()
        self.app.processEvents()
        if self._testMethodName != 'test_startup_defaults_to_half_integer_uwp_development_case':
            # Existing connection tests exercise the former integer-q fixture.
            fields = self.window.input_fields
            fields['winding_input_mode'].setCurrentText('Slots and poles')
            fields['num_slots'].setText('48')
            fields['num_poles'].setText('8')
            fields['ab'].setText('2')
            fields['pattern_name'].setText('BWP')
            self.window._resolve_slot_inputs()
            self.window._refresh_pattern_availability()
            self.app.processEvents()

    def tearDown(self):
        import matplotlib.pyplot as plt
        plt.close(self.window.figure)
        self.window.close()

    def test_startup_defaults_to_half_integer_uwp_development_case(self):
        w = self.window
        self.assertEqual(w.input_fields['winding_input_mode'].currentText(),
                         'q and poles')
        self.assertEqual(w.input_fields['q'].text(), '1.5')
        self.assertEqual(w.input_fields['num_slots'].text(), '36')
        self.assertEqual(w.input_fields['num_poles'].text(), '8')
        self.assertEqual(w.input_fields['ab'].text(), '3')
        self.assertEqual(w.input_fields['pattern_name'].text(), 'UWP')
        self.assertFalse(w.input_fields['inlet_from_weld_side'].isChecked())
        self.assertFalse(w.input_fields['q'].isReadOnly())
        self.assertTrue(w.input_fields['num_slots'].isReadOnly())
        self.assertEqual(w.input_fields['tp_type'].currentText(), 'Auto')

    def test_uwp_sample_divider_automatically_balances_transposition_and_starts(self):
        w = self.window
        f = w.input_fields
        f['winding_input_mode'].setCurrentText('q and poles')
        f['pattern_name'].setText('UWP')
        f['q'].setText('4')
        f['num_poles'].setText('4')
        f['num_layers'].setText('6')
        f['ab'].setText('4')
        w.q_divider_box.setCurrentText('2')
        w.pp_divider_box.setCurrentText('1')
        w.p2_divider_box.setCurrentText('2')
        self.assertEqual(f['tp_type'].currentText(), 'Auto')
        self.assertEqual(f['uni_tp'].text(), '0')
        self.assertEqual(f['jltp'].text(), '1')
        self.assertIn('cycle=0, local=1', w.uwp_balance_notice.text())
        self.assertIn('1, 3, 13, 15', w.uwp_balance_notice.text())
        w.extract_parameters()
        paths = [branch[1] for branch in w.db_conductor_id]
        report = validate_branches(paths, default_phase_map(48, 4, 6), 48, 4, 4)
        self.assertTrue(report['electrically_valid'], report)
        self.assertEqual([p[0][:2] for p in paths[:4]],
                         [(0, 0), (2, 0), (0, 5), (2, 5)])
        w.plot_layout()
        self.assertEqual(w.current_view_type, 'winding', w.message_log.toPlainText())
        self.assertFalse(w._winding_candidate)
        payload = w._build_config_payload()
        f['num_poles'].setText('8')
        w._refresh_divider_status()
        self.assertEqual(f['tp_type'].currentText(), 'Auto')
        self.assertEqual(f['uni_tp'].text(), '0')
        w._apply_config_payload(payload)
        self.assertEqual(f['tp_type'].currentText(), 'Auto')
        self.assertEqual(f['uni_tp'].text(), '0')
        w.extract_parameters()
        self.assertEqual(w.db_conductor_id, w.base_db_conductor_id)
        other = w._build_config_payload()
        other['inputs'].update(q_divider='1', pp_divider='2', p2_divider='2',
                               tp_type='Regular', uni_tp='3', jltp='0')
        w._apply_config_payload(other)
        self.assertEqual(f['uni_tp'].text(), '3')
        w._apply_config_payload(payload)
        w.update_transp_type('Auto')
        self.assertEqual(f['tp_type'].currentText(), 'Auto')
        f['num_poles'].setText('8')
        w._refresh_divider_status()
        self.assertEqual(f['tp_type'].currentText(), 'Auto')

    def test_legacy_automatic_transposition_names_import_as_auto(self):
        w = self.window
        for legacy in ('Optimize', 'Auto balance'):
            with self.subTest(legacy=legacy):
                w._apply_config_payload({'inputs': {'tp_type': legacy}})
                self.assertEqual(w.input_fields['tp_type'].currentText(), 'Auto')
                self.assertEqual(w._build_config_payload()['inputs']['tp_type'], 'Auto')

    def test_uwp_proper_q_p2_auto_route_covers_all_pp_choices(self):
        w = self.window
        f = w.input_fields
        f['winding_input_mode'].setCurrentText('q and poles')
        f['pattern_name'].setText('UWP')
        f['q'].setText('4')
        f['num_layers'].setText('6')
        for poles, pp in ((6, 1), (6, 3), (8, 1), (8, 2), (8, 4)):
            with self.subTest(poles=poles, pp=pp):
                f['num_poles'].setText(str(poles))
                f['ab'].setText(str(4*pp))
                w.q_divider_box.setCurrentText('2')
                w.pp_divider_box.setCurrentText(str(pp))
                w.p2_divider_box.setCurrentText('2')
                w._refresh_divider_status()
                self.assertIn('eligible', w.divider_status.text().lower(),
                              w.divider_status.toolTip())
                self.assertEqual(f['tp_type'].currentText(), 'Auto')
                self.assertIn(f'PP={pp}', w.uwp_balance_notice.text())
                w.extract_parameters()
                report = validate_branches(
                    [branch[1] for branch in w.db_conductor_id],
                    default_phase_map(12*poles, poles, 6),
                    12*poles, poles, 4*pp)
                self.assertTrue(report['electrically_valid'], report)

    def test_uwp_q6_q8_auto_route_supports_odd_phase_counts(self):
        w = self.window
        f = w.input_fields
        f['winding_input_mode'].setCurrentText('q and poles')
        f['pattern_name'].setText('UWP')
        f['num_layers'].setText('6')
        for phases, q, q_divider, poles, pp in (
                (5, 6, 3, 8, 4), (5, 8, 2, 6, 3), (7, 6, 2, 4, 2)):
            with self.subTest(m=phases, q=q, Q=q_divider, poles=poles, pp=pp):
                f['num_phases'].setText(str(phases))
                f['q'].setText(str(q))
                f['num_poles'].setText(str(poles))
                f['ab'].setText(str(2*q_divider*pp))
                w._refresh_divider_from_inputs()
                w.q_divider_box.setCurrentText(str(q_divider))
                w.pp_divider_box.setCurrentText(str(pp))
                w.p2_divider_box.setCurrentText('2')
                w._refresh_divider_status()
                self.assertIn('eligible', w.divider_status.text().lower(),
                              w.divider_status.toolTip())
                self.assertEqual(f['tp_type'].currentText(), 'Auto')
                w.extract_parameters()
                slots = phases*q*poles
                report = validate_branches(
                    [branch[1] for branch in w.db_conductor_id],
                    default_phase_map(slots, poles, 6, phases),
                    slots, poles, 2*q_divider*pp, phases)
                self.assertTrue(report['electrically_valid'], report)

    def test_divider_options_and_exact_naa_linkage(self):
        w = self.window
        self.assertEqual(w.current_layout_pattern_hint.text(),
                         'Current Layout pattern: BWP')
        w.input_fields['pattern_name'].setText('UWP')
        self.assertEqual(w.current_layout_pattern_hint.text(),
                         'Current Layout pattern: UWP')
        w.input_fields['winding_input_mode'].setCurrentText('q and poles')
        w.input_fields['q'].setText('4')
        w.input_fields['ab'].setText('1')
        w._refresh_divider_from_inputs()
        self.assertEqual([w.q_divider_box.itemText(i) for i in range(w.q_divider_box.count())],
                         ['1', '2', '4'])
        self.assertEqual([w.pp_divider_box.itemText(i) for i in range(w.pp_divider_box.count())],
                         ['1', '2', '4'])
        self.assertEqual([w.p2_divider_box.itemText(i) for i in range(w.p2_divider_box.count())],
                         ['1', '2'])
        w.q_divider_box.setCurrentText('2')
        w.pp_divider_box.setCurrentText('2')
        self.assertEqual(w.input_fields['ab'].text(), '4')

        w.input_fields['q'].setText('9/2')
        w.input_fields['ab'].setText('1')
        w._refresh_divider_from_inputs()
        self.assertEqual([w.q_divider_box.itemText(i) for i in range(w.q_divider_box.count())],
                         ['1', '1.5', '4.5'])
        self.assertFalse(w.q_divider_box.model().item(1).isEnabled())
        w.p2_divider_box.setCurrentText('2')
        self.assertTrue(w.q_divider_box.model().item(1).isEnabled())
        w.q_divider_box.setCurrentText('1.5')
        self.assertEqual(w.input_fields['ab'].text(), '3')
        self.assertIn('not supported', w.divider_status.text().lower())

    def test_bwp_pp_only_divider_generates_distinct_branches(self):
        w = self.window
        w.input_fields['winding_input_mode'].setCurrentText('q and poles')
        w.input_fields['q'].setText('2')
        w.input_fields['ab'].setText('2')
        w.input_fields['pattern_name'].setText('BWP')
        w._refresh_divider_from_inputs()
        self.assertEqual(w._selected_dividers(), (2, 1, 1))
        w.q_divider_box.setCurrentText('1')
        w.pp_divider_box.setCurrentText('2')
        self.assertEqual(w.input_fields['ab'].text(), '2')
        self.assertIn('eligible', w.divider_status.text().lower())
        w.input_fields['num_layers'].setText('6')
        w.extract_parameters()
        self.assertEqual(w.Winding_Para.branch_dividers, (1, 2, 1))
        self.assertEqual(len(w.base_db_conductor_id), 6)
        self.assertEqual({len(branch[1]) for branch in w.base_db_conductor_id}, {48})
        report = validate_branches([branch[1] for branch in w.base_db_conductor_id],
                                   default_phase_map(48, 8, 6), 48, 8, 2)
        self.assertTrue(report['electrically_valid'], report['errors'])
        w.input_fields['ab'].setText('2')
        w.input_fields['ab'].editingFinished.emit()
        self.assertEqual(w._selected_dividers(), (2, 1, 1))
        w.input_fields['pattern_name'].setText('UWP')
        self.assertEqual(w._selected_dividers(), (1, 1, 2))

    def test_bwp_p2_divider_is_explicitly_unsupported(self):
        w = self.window
        f = w.input_fields
        f['winding_input_mode'].setCurrentText('q and poles')
        f['pattern_name'].setText('BWP')
        f['q'].setText('1')
        f['num_poles'].setText('4')
        f['num_layers'].setText('4')
        f['ab'].setText('2')
        w.q_divider_box.setCurrentText('1')
        w.pp_divider_box.setCurrentText('1')
        w.p2_divider_box.setCurrentText('2')
        self.assertIn('not supported', w.divider_status.text().lower())
        self.assertIn('BWP does not support P2-divider=2',
                      w.divider_status.toolTip())
        self.assertFalse(w.p2_divider_box.model().item(
            w.p2_divider_box.findText('2')).isEnabled())
        with self.assertRaisesRegex(ValueError,
                                    'BWP does not support P2-divider=2'):
            w._validate_divider_route()
        w.pp_divider_box.setCurrentText('2')
        w.p2_divider_box.setCurrentText('1')
        self.assertIn('enabled', w.divider_status.text().lower())
        w.extract_parameters()
        self.assertEqual(w.Winding_Para.branch_dividers, (1, 2, 1))

    def test_non_wave_selected_route_uses_effective_auto_payload(self):
        w = self.window
        f = w.input_fields
        f['winding_input_mode'].setCurrentText('q and poles')
        f['pattern_name'].setText('SSP')
        f['q'].setText('2')
        f['num_poles'].setText('8')
        f['num_layers'].setText('6')
        f['num_phases'].setText('5')
        f['ab'].setText('2')
        w.q_divider_box.setCurrentText('1')
        w.pp_divider_box.setCurrentText('2')
        w.p2_divider_box.setCurrentText('1')
        w.tp_type_field.setCurrentText('Auto')
        w._auto_effective_tp_type = 'Regular'

        w._validate_divider_route()
        w._refresh_divider_status()

        self.assertNotIn('not supported', w.divider_status.text().lower())
        self.assertIn('enabled', w.divider_status.text().lower())

    def test_bwp_pp_only_q4_edges_and_electrical_balance(self):
        w = self.window
        f = w.input_fields
        f['winding_input_mode'].setCurrentText('q and poles')
        f['pattern_name'].setText('BWP')
        f['q'].setText('4')
        f['num_poles'].setText('8')
        f['num_layers'].setText('6')
        f['ab'].setText('2')
        w.q_divider_box.setCurrentText('1')
        w.pp_divider_box.setCurrentText('2')
        w.p2_divider_box.setCurrentText('1')
        self.assertIn('eligible', w.divider_status.text().lower())
        w.extract_parameters()
        paths = [branch[1] for branch in w.base_db_conductor_id]
        report = validate_branches(paths, default_phase_map(96, 8, 6),
                                   96, 8, 2)
        self.assertTrue(report['electrically_valid'], report['errors'])
        self.assertTrue(all(
            (abs(end[1] - start[1]) == 1
             and abs(((end[0] - start[0] + 48) % 96) - 48) == 12)
            or (end[1] == start[1]
                and abs(((end[0] - start[0] + 48) % 96) - 48) in (11, 12))
            for path in paths for start, end in zip(path, path[1:])))

    def test_selected_integer_divider_route_classifies_existing_domains(self):
        cases = (
            ('BWP', 2, 8, 6, 2, (1, 2, 1), 'bwp_pp'),
            ('BWP', 1, 4, 4, 2, (1, 1, 2), None),
            ('UWP', 2, 8, 6, 2, (1, 2, 1), 'pp_only'),
            ('SSP', 2, 8, 6, 2, (1, 2, 1), 'pp_only'),
            ('SLP', 2, 8, 6, 2, (1, 2, 1), 'pp_only'),
            ('ZLP', 2, 4, 4, 2, (2, 1, 1), None),
            ('CP', 2, 8, 6, 4, (2, 2, 1), None),
            ('ZPP', 2, 8, 6, 4, (1, 2, 2), 'zpp'),
            ('TSP', 2, 8, 6, 2, (1, 2, 1), None),
            ('TLP', 2, 8, 6, 2, (1, 2, 1), None),
            ('LPP', 2, 8, 6, 2, (2, 1, 1), None),
        )
        for pattern, q, poles, layers, ab, selected, expected in cases:
            with self.subTest(pattern=pattern, selected=selected):
                winding = SimpleNamespace(q=q, num_poles=poles,
                                          num_layers=layers, num_phases=3,
                                          ab=ab, branch_dividers=selected)
                self.assertEqual(gw.selected_integer_divider_route(
                    pattern, winding), expected)
                default = gw.classify_branch_mode(ab, q, poles, pattern)[1:4]
                winding.branch_dividers = default
                self.assertIsNone(gw.selected_integer_divider_route(
                    pattern, winding))

    def test_priority_patterns_use_selected_pp_only_branches(self):
        w = self.window
        w.input_fields['winding_input_mode'].setCurrentText('q and poles')
        w.input_fields['q'].setText('2')
        w.input_fields['num_layers'].setText('6')
        for pattern, default in (('UWP', (1, 1, 2)),
                                 ('SSP', (2, 1, 1)),
                                 ('SLP', (2, 1, 1))):
            with self.subTest(pattern=pattern):
                w.input_fields['pattern_name'].setText(pattern)
                w.input_fields['ab'].setText('2')
                w._refresh_divider_from_inputs()
                self.assertEqual(w._selected_dividers(), default)
                w.extract_parameters()
                default_paths = [branch[1] for branch in w.base_db_conductor_id]
                w.q_divider_box.setCurrentText('1')
                w.pp_divider_box.setCurrentText('2')
                w.p2_divider_box.setCurrentText('1')
                self.assertIn('eligible', w.divider_status.text().lower())
                w.extract_parameters()
                self.assertEqual(w.Winding_Para.branch_dividers, (1, 2, 1))
                branches = [branch[1] for branch in w.base_db_conductor_id]
                self.assertNotEqual(branches, default_paths)
                report = validate_branches(branches, default_phase_map(48, 8, 6),
                                           48, 8, 2)
                self.assertTrue(report['electrically_valid'], report['errors'])
                with self.assertRaisesRegex(gw.PatternConfigurationError,
                                            'without shifts'):
                    gw.get_winding_layout(
                        pattern, w.TP_info, w.Winding_Para,
                        w.Layout_Para._replace(phase_shift_pattern='Normal'))
                for branch in branches:
                    edges = [((((end[0] - start[0] + 24) % 48) - 24),
                              end[1] - start[1])
                             for start, end in zip(branch, branch[1:])]
                    if pattern == 'UWP':
                        self.assertTrue(all(pitch in (5, 6, 7) for pitch, _ in edges))
                        self.assertEqual(set(edges),
                                         {(5, 2), (6, -1), (6, 0), (6, 1), (7, 0)})
                        continue
                    self.assertEqual(edges.count((7, 0)), 1)
                    ordinary = [edge for edge in edges if edge != (7, 0)]
                    self.assertTrue(all(abs(pitch) == 6 and abs(layer_delta) <= 1
                                        for pitch, layer_delta in ordinary))
                    if pattern == 'SSP':
                        self.assertTrue(all(pitch == 6 for pitch, layer_delta in ordinary
                                            if layer_delta == 1))
                        self.assertTrue(all(pitch == -6 for pitch, layer_delta in ordinary
                                            if layer_delta == -1))
                    else:
                        self.assertEqual([pitch for pitch, _ in edges[:5]],
                                         [6, -6, 6, -6, 6])
                payload = w._build_config_payload()
                w._apply_config_payload(payload)
                self.assertEqual(w._selected_dividers(), (1, 2, 1))
                self.assertIn('eligible', w.divider_status.text().lower())
                w.input_fields['phase_shift_pattern'].setCurrentText('Normal')
                self.assertIn('not supported', w.divider_status.text().lower())
                w.input_fields['phase_shift_pattern'].setCurrentText('None')
                self.assertIn('eligible', w.divider_status.text().lower())

    def test_priority_pp_only_route_rejects_unchecked_parameters(self):
        w = self.window
        w.input_fields['winding_input_mode'].setCurrentText('q and poles')
        w.input_fields['num_layers'].setText('6')
        w.input_fields['pattern_name'].setText('UWP')
        w.input_fields['ab'].setText('2')
        w.q_divider_box.setCurrentText('1')
        w.pp_divider_box.setCurrentText('2')
        w.p2_divider_box.setCurrentText('1')
        w.tp_fields['pltp_ll'].setText('1')
        self.assertIn('not supported', w.divider_status.text().lower())
        with self.assertRaisesRegex(ValueError, 'Unsupported SSP'):
            gw.branch_dividers_for_pattern(
                'SSP', SimpleNamespace(q=2, num_poles=8, num_layers=6,
                                       num_phases=3, ab=3,
                                       branch_dividers=(1, 3, 1)))

    def test_spiral_pp_only_factor_range_and_odd_layers(self):
        w = self.window
        f = w.input_fields
        f['winding_input_mode'].setCurrentText('q and poles')
        f['q'].setText('4')
        f['num_poles'].setText('16')
        f['num_layers'].setText('8')
        f['ab'].setText('4')
        for pattern in ('SSP', 'SLP'):
            with self.subTest(pattern=pattern):
                f['pattern_name'].setText(pattern)
                w.q_divider_box.setCurrentText('1')
                w.pp_divider_box.setCurrentText('4')
                w.p2_divider_box.setCurrentText('1')
                self.assertIn('eligible', w.divider_status.text().lower())
                w.extract_parameters()
                report = validate_branches(
                    [branch[1] for branch in w.base_db_conductor_id],
                    default_phase_map(192, 16, 8), 192, 16, 4)
                self.assertTrue(report['electrically_valid'], report['errors'])
        f['num_layers'].setText('7')
        f['pattern_name'].setText('SLP')
        w.q_divider_box.setCurrentText('1')
        w.pp_divider_box.setCurrentText('4')
        w.p2_divider_box.setCurrentText('1')
        self.assertIn('eligible', w.divider_status.text().lower())
        w.extract_parameters()
        paths = [branch[1] for branch in w.base_db_conductor_id]
        report = validate_branches(paths, default_phase_map(192, 16, 7),
                                   192, 16, 4)
        self.assertTrue(report['electrically_valid'], report['errors'])

    def test_slp_odd_layer_lap_route_at_small_layer_counts(self):
        w = self.window
        f = w.input_fields
        f['winding_input_mode'].setCurrentText('q and poles')
        f['pattern_name'].setText('SLP')
        for q, poles, layers, ab in ((1, 8, 3, 2), (2, 8, 3, 2),
                                     (2, 8, 5, 4)):
            with self.subTest(q=q, layers=layers, ab=ab):
                f['q'].setText(str(q))
                f['num_poles'].setText(str(poles))
                f['num_layers'].setText(str(layers))
                f['ab'].setText(str(ab))
                w.q_divider_box.setCurrentText('1')
                w.pp_divider_box.setCurrentText(str(ab))
                w.p2_divider_box.setCurrentText('1')
                self.assertNotIn('not supported', w.divider_status.text().lower())
                w.extract_parameters()
                paths = [branch[1] for branch in w.base_db_conductor_id]
                slots = 3 * q * poles
                report = validate_branches(
                    paths, default_phase_map(slots, poles, layers),
                    slots, poles, ab)
                self.assertTrue(report['electrically_valid'], report['errors'])
                if q == 2:
                    gw.validate_pp_only_spiral(
                        'SLP', w.base_db_conductor_id,
                        w.Winding_Para, w.Layout_Para)

    def test_uwp_pp_only_multi_factor_full_circle_route(self):
        w = self.window
        f = w.input_fields
        f['winding_input_mode'].setCurrentText('q and poles')
        f['pattern_name'].setText('UWP')
        f['q'].setText('4')
        f['num_poles'].setText('16')
        f['num_layers'].setText('2')
        f['ab'].setText('2')
        w.q_divider_box.setCurrentText('1')
        w.pp_divider_box.setCurrentText('2')
        w.p2_divider_box.setCurrentText('1')
        self.assertIn('eligible', w.divider_status.text().lower())
        w.extract_parameters()
        branches = [branch[1] for branch in w.base_db_conductor_id]
        report = validate_branches(branches, default_phase_map(192, 16, 2),
                                   192, 16, 2)
        self.assertTrue(report['electrically_valid'], report['errors'])
        self.assertEqual(len(branches), 6)
        self.assertTrue(all(((end[0] - start[0]) % 192) in (11, 12, 13)
                            for branch in branches
                            for start, end in zip(branch, branch[1:])))

    def test_uwp_q1_q2_multilayer_pp_factor_range(self):
        w = self.window
        f = w.input_fields
        f['winding_input_mode'].setCurrentText('q and poles')
        f['pattern_name'].setText('UWP')
        for q, poles, layers, ab in ((1, 12, 8, 6), (2, 16, 8, 4),
                                     (2, 24, 12, 4)):
            with self.subTest(q=q, poles=poles, layers=layers, ab=ab):
                f['q'].setText(str(q))
                f['num_poles'].setText(str(poles))
                f['num_layers'].setText(str(layers))
                f['ab'].setText(str(ab))
                w.q_divider_box.setCurrentText('1')
                w.pp_divider_box.setCurrentText(str(ab))
                w.p2_divider_box.setCurrentText('1')
                self.assertIn('eligible', w.divider_status.text().lower())
                w.extract_parameters()
                paths = [branch[1] for branch in w.base_db_conductor_id]
                slots = q * poles * 3
                report = validate_branches(
                    paths, default_phase_map(slots, poles, layers),
                    slots, poles, ab)
                self.assertTrue(report['electrically_valid'], report['errors'])
                self.assertTrue(all((end[0] - start[0]) % slots in
                                    (3*q-1, 3*q, 3*q+1)
                                    for path in paths
                                    for start, end in zip(path, path[1:])))
        f['q'].setText('3')
        f['num_poles'].setText('16')
        f['num_layers'].setText('8')
        f['ab'].setText('4')
        w.q_divider_box.setCurrentText('1')
        w.pp_divider_box.setCurrentText('4')
        w.p2_divider_box.setCurrentText('1')
        self.assertIn('eligible', w.divider_status.text().lower())
        with self.assertRaisesRegex(ValueError, 'invalid forward edge'):
            w.extract_parameters()

    def test_uwp_even_non_power_two_pp_factors(self):
        w = self.window
        f = w.input_fields
        f['winding_input_mode'].setCurrentText('q and poles')
        f['pattern_name'].setText('UWP')
        for q, poles, layers, ab in ((2, 24, 6, 6), (4, 40, 2, 10)):
            with self.subTest(q=q, poles=poles, layers=layers, ab=ab):
                f['q'].setText(str(q))
                f['num_poles'].setText(str(poles))
                f['num_layers'].setText(str(layers))
                f['ab'].setText(str(ab))
                w.q_divider_box.setCurrentText('1')
                w.pp_divider_box.setCurrentText(str(ab))
                w.p2_divider_box.setCurrentText('1')
                self.assertIn('eligible', w.divider_status.text().lower())
                w.extract_parameters()
                paths = [branch[1] for branch in w.base_db_conductor_id]
                slots = q * poles * 3
                report = validate_branches(
                    paths, default_phase_map(slots, poles, layers),
                    slots, poles, ab)
                self.assertTrue(report['electrically_valid'], report['errors'])
                self.assertTrue(all((end[0] - start[0]) % slots in
                                    (3*q-1, 3*q, 3*q+1)
                                    for path in paths
                                    for start, end in zip(path, path[1:])))
        f['q'].setText('2')
        f['num_poles'].setText('12')
        f['num_layers'].setText('2')
        f['ab'].setText('6')
        w.q_divider_box.setCurrentText('1')
        w.pp_divider_box.setCurrentText('6')
        w.p2_divider_box.setCurrentText('1')
        self.assertIn('not supported', w.divider_status.text().lower())

    def test_uwp_q2_full_q_selection_has_no_special_route(self):
        w = self.window
        f = w.input_fields
        f['winding_input_mode'].setCurrentText('q and poles')
        f['pattern_name'].setText('UWP')
        f['q'].setText('2')
        f['num_poles'].setText('8')
        f['num_layers'].setText('6')
        f['ab'].setText('4')
        w.q_divider_box.setCurrentText('2')
        w.pp_divider_box.setCurrentText('2')
        w.p2_divider_box.setCurrentText('1')
        self.assertIn('not supported', w.divider_status.text().lower())
        with self.assertRaisesRegex(ValueError, 'divider combination'):
            w._validate_divider_route()

    def test_uwp_bwp_fallback_rejects_reverse_wave_edges(self):
        w = self.window
        f = w.input_fields
        f['winding_input_mode'].setCurrentText('q and poles')
        f['pattern_name'].setText('UWP')
        f['q'].setText('4')
        f['num_poles'].setText('8')
        f['num_layers'].setText('6')
        f['ab'].setText('4')
        self.assertEqual(w._selected_dividers(), (1, 2, 2))
        w._refresh_pattern_availability()
        self.assertTrue(w.pattern_buttons['UWP'].isEnabled())
        self.assertIn('(2, 1, 2)', w.pattern_buttons['UWP'].toolTip())
        w._refresh_divider_status()
        self.assertIn('not supported', w.divider_status.text().lower())
        self.assertIn('(2, 1, 2)', w.divider_status.toolTip())
        self.assertTrue(gw.evaluate_base_pattern_support('BWP', 4, 8, 4, 6)[0])
        with self.assertRaisesRegex(ValueError, 'UWP.*forward edge'):
            w.extract_parameters()
        self.assertTrue(gw.evaluate_base_pattern_support('UWP', 1, 4, 4, 6)[0])

    def test_uwp_q4_q_and_p2_uses_general_wave_route(self):
        w = self.window
        f = w.input_fields
        f['winding_input_mode'].setCurrentText('q and poles')
        f['pattern_name'].setText('UWP')
        f['q'].setText('4')
        f['num_poles'].setText('8')
        f['num_layers'].setText('6')
        f['ab'].setText('4')
        w.q_divider_box.setCurrentText('2')
        w.pp_divider_box.setCurrentText('1')
        w.p2_divider_box.setCurrentText('2')
        self.assertIn('eligible', w.divider_status.text().lower())
        w._refresh_pattern_availability()
        self.assertTrue(w.pattern_buttons['UWP'].isEnabled())
        w.extract_parameters()
        paths = [branch[1] for branch in w.base_db_conductor_id]
        self.assertEqual(len(paths), 12)
        self.assertTrue(all(len(path) == 48 for path in paths))
        self.assertEqual(gw.selected_integer_divider_route('UWP', w.Winding_Para),
                         'uwp_q_factor_p2')
        report = validate_branches(paths, default_phase_map(96, 8, 6),
                                   96, 8, 4)
        self.assertTrue(report['electrically_valid'], report['errors'])
        bwp_winding = SimpleNamespace(q=4, num_slots=96, num_poles=8,
                                      num_layers=6, num_phases=3, ab=4)
        _, bwp_database = gw.get_winding_layout(
            'BWP', w.TP_info, bwp_winding, w.Layout_Para)
        self.assertNotEqual(paths, [branch[1] for branch in bwp_database])
        self.assertTrue(all((end[0] - start[0]) % 96 in (12, 13)
                            for path in paths
                            for start, end in zip(path, path[1:])))
        near_case = SimpleNamespace(q=4, num_slots=96, num_poles=8, num_layers=4,
                                    num_phases=3, ab=4,
                                    branch_dividers=(2, 1, 2))
        self.assertEqual(gw.selected_integer_divider_route('UWP', near_case),
                         'uwp_q_factor_p2')
        _, near_database = gw.get_winding_layout(
            'UWP', w.TP_info, near_case,
            SimpleNamespace(phase_shift_list=[0]*4, radial_shift=0,
                            inlet_from_weld_side=0,
                            inlet_index_adjustments_phase_a=[]))
        self.assertTrue(validate_branches(
            [branch[1] for branch in near_database],
            default_phase_map(96, 8, 4), 96, 8, 4)['electrically_valid'])
        shifted = SimpleNamespace(phase_shift_list=[1, 0, 0, 0, 0, 0],
                                  radial_shift=0, inlet_from_weld_side=0)
        with self.assertRaisesRegex(ValueError, 'without shifts'):
            gw.get_winding_layout('UWP', w.TP_info, w.Winding_Para, shifted)
        w.plot_layout()
        self.assertEqual(w.current_view_type, 'winding',
                         w.message_log.toPlainText())

    def test_uwp_proper_q_factors_across_slot_pole_counts(self):
        w = self.window
        f = w.input_fields
        f['winding_input_mode'].setCurrentText('q and poles')
        f['pattern_name'].setText('UWP')
        f['num_layers'].setText('6')
        for q, poles, factors in ((6, 8, (2, 2, 1)),
                                  (6, 12, (3, 1, 2)),
                                  (8, 16, (4, 1, 2)),
                                  (9, 12, (3, 2, 1))):
            with self.subTest(q=q, poles=poles, factors=factors):
                f['q'].setText(str(q))
                f['num_poles'].setText(str(poles))
                naa = factors[0] * factors[1] * factors[2]
                f['ab'].setText(str(naa))
                w.q_divider_box.setCurrentText(str(factors[0]))
                w.pp_divider_box.setCurrentText(str(factors[1]))
                w.p2_divider_box.setCurrentText(str(factors[2]))
                w._refresh_pattern_availability()
                self.assertTrue(w.pattern_buttons['UWP'].isEnabled())
                w.extract_parameters()
                paths = [branch[1] for branch in w.base_db_conductor_id]
                report = validate_branches(
                    paths, default_phase_map(q*poles*3, poles, 6),
                    q*poles*3, poles, naa)
                self.assertTrue(report['electrically_valid'], report['errors'])
                self.assertEqual(len(paths), 3*naa)
        rejected = SimpleNamespace(q=6, num_poles=12, num_layers=6,
                                   num_phases=3, ab=6,
                                   branch_dividers=(6, 1, 1))
        self.assertIsNone(gw.selected_integer_divider_route('UWP', rejected))
        rejected.num_poles = 6
        rejected.ab = 2
        rejected.branch_dividers = (2, 1, 1)
        self.assertIsNone(gw.selected_integer_divider_route('UWP', rejected))

    def test_uwp_every_proper_q_factor_regular_sector_matrix(self):
        tp = SimpleNamespace(tp_type='Regular', tp_interval=0, tp_times=0,
                             uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1)
        for q in (4, 6, 8, 9, 10, 12):
            for q_factor in range(2, q):
                if q % q_factor:
                    continue
                for p2_factor in (1, 2):
                    naa = q_factor * p2_factor
                    poles = 2 * naa
                    for layers in (2, 6):
                        with self.subTest(q=q, Q=q_factor, P2=p2_factor,
                                          layers=layers):
                            winding = SimpleNamespace(
                                q=q, num_slots=3*q*poles, num_poles=poles,
                                num_layers=layers, num_phases=3, ab=naa,
                                branch_dividers=(q_factor, 1, p2_factor))
                            layout = SimpleNamespace(
                                phase_shift_list=[0]*layers, radial_shift=0,
                                inlet_from_weld_side=0,
                                inlet_index_adjustments_phase_a=[])
                            _, database = gw.get_winding_layout(
                                'UWP', tp, winding, layout)
                            report = validate_branches(
                                [branch[1] for branch in database],
                                default_phase_map(winding.num_slots, poles, layers),
                                winding.num_slots, poles, naa)
                            self.assertTrue(report['electrically_valid'],
                                            report['errors'])

    def test_all_supported_p2_patterns_orient_and_index_branches_n_to_s(self):
        tp = SimpleNamespace(
            tp_type='Regular', tp_interval=0, tp_times=0, uni_tp=0,
            pltp_fl=0, pltp_ll=0, jltp=0, jld=1,
            pole_group_tp={})
        for pattern, q, dividers, weld_side, layers, ab in (
                ('CP', 2, (1, 1, 2), 0, 4, 2),
                ('ZPP', 2, (1, 2, 2), 1, 6, 4),
                ('UWP', 4, (2, 1, 2), 0, 6, 4)):
            with self.subTest(pattern=pattern):
                winding = SimpleNamespace(
                    q=q, num_slots=3 * q * 8, num_poles=8, num_layers=layers,
                    num_phases=3, ab=ab, branch_dividers=dividers)
                layout = SimpleNamespace(
                    phase_shift_list=[0] * winding.num_layers, radial_shift=0,
                    phase_shift_pattern='None', inlet_from_weld_side=weld_side,
                    inlet_index_adjustments_phase_a=[])
                starts, database = gw.get_winding_layout(
                    pattern, tp, winding, layout)
                pole_sign = {
                    (slot, layer): sign
                    for slot, layer, _phase, sign in phase_map(
                        winding.num_slots, winding.num_poles,
                        winding.num_layers, layout.phase_shift_list,
                        winding.num_phases)
                }

                self.assertEqual(starts, [path[0] for _branch, path in database])
                self.assertTrue(all(pole_sign[path[0][:2]] == 1
                                    for _branch, path in database))
                self.assertTrue(all(pole_sign[path[-1][:2]] == -1
                                    for _branch, path in database))
                cond_info = gw.Winding_Phase_division(
                    winding, layout, log=lambda _msg: None)
                cond_info = cio.update_cond_info_with_branch_data(
                    cond_info, database)
                self.assertEqual(
                    cio.get_start_cond_ids_with_cond_info(cond_info), starts)
                for branch_id, path in database:
                    self.assertEqual(
                        cio.get_cond_ids_with_cond_info(cond_info, branch_id), path)

    def test_half_integer_q_p2_branches_follow_shifted_phase_pole_regions(self):
        winding = SimpleNamespace(
            q=1.5, num_slots=36, num_poles=8, num_layers=6,
            num_phases=3, ab=3, branch_dividers=(1.5, 1, 2))
        tp = SimpleNamespace(
            tp_type='Regular', tp_interval=0, tp_times=0, uni_tp=0,
            pltp_fl=0, pltp_ll=0, jltp=0, jld=1,
            pole_group_tp={})
        for shifts in ([0] * 6, [0, 0, 1, 1, 0, 0]):
            with self.subTest(shifts=shifts):
                layout = SimpleNamespace(
                    phase_shift_list=shifts, radial_shift=0,
                    phase_shift_pattern='None', inlet_from_weld_side=0,
                    inlet_index_adjustments_phase_a=[])
                starts, database = gw.get_winding_layout(
                    'UWP', tp, winding, layout)
                pole_sign = {
                    (slot, layer): sign
                    for slot, layer, _phase, sign in phase_map(
                        winding.num_slots, winding.num_poles,
                        winding.num_layers, shifts, winding.num_phases)
                }
                self.assertTrue(gw.uses_p2_divider('UWP', winding))
                self.assertEqual(starts,
                                 [path[0] for _branch, path in database])
                self.assertTrue(all(
                    pole_sign[path[0][:2]] == 1
                    and pole_sign[path[-1][:2]] == -1
                    for _branch, path in database))
                report = validate_branches(
                    [path for _branch, path in database],
                    phase_map(winding.num_slots, winding.num_poles,
                              winding.num_layers, shifts,
                              winding.num_phases),
                    winding.num_slots, winding.num_poles, winding.ab,
                    winding.num_phases)
                self.assertTrue(report['topology_valid'], report['errors'])
                self.assertTrue(all(
                    error == 'parallel_emf_mismatch'
                    for error in report['errors']), report['errors'])

    def test_half_integer_q_pp_p2_factor_uses_general_product_rule(self):
        winding = SimpleNamespace(
            q=1.5, num_slots=54, num_poles=12, num_layers=6,
            num_phases=3, ab=6, branch_dividers=(1.5, 2, 2))
        tp = SimpleNamespace(
            tp_type='Regular', tp_interval=0, tp_times=0, uni_tp=0,
            pltp_fl=0, pltp_ll=0, jltp=0, jld=1,
            pole_group_tp={})
        for shifts in ([0] * 6, [0, 0, 1, 1, 0, 0]):
            with self.subTest(shifts=shifts):
                layout = SimpleNamespace(
                    phase_shift_list=shifts, radial_shift=0,
                    phase_shift_pattern='None', inlet_from_weld_side=0,
                    inlet_index_adjustments_phase_a=[])
                starts, database = gw.get_winding_layout(
                    'UWP', tp, winding, layout)
                records = phase_map(
                    winding.num_slots, winding.num_poles,
                    winding.num_layers, shifts, winding.num_phases)
                pole_sign = {(slot, layer): sign
                             for slot, layer, _phase, sign in records}
                self.assertTrue(gw.supports_half_integer_uwp_p2(
                    'UWP', winding, winding.branch_dividers))
                self.assertEqual(len(database), winding.ab * winding.num_phases)
                self.assertEqual(starts,
                                 [path[0] for _branch, path in database])
                self.assertTrue(all(
                    pole_sign[path[0][:2]] == 1
                    and pole_sign[path[-1][:2]] == -1
                    for _branch, path in database))
                report = validate_branches(
                    [path for _branch, path in database], records,
                    winding.num_slots, winding.num_poles, winding.ab,
                    winding.num_phases)
                self.assertTrue(report['topology_valid'], report['errors'])
                self.assertEqual(report['errors'], ['parallel_emf_mismatch'])

    def test_cp_four_layer_default_p2_route_remains_available(self):
        w = self.window
        f = w.input_fields
        f['winding_input_mode'].setCurrentText('q and poles')
        f['pattern_name'].setText('CP')
        f['q'].setText('2')
        f['num_poles'].setText('8')
        f['num_layers'].setText('4')
        f['ab'].setText('2')
        w.q_divider_box.setCurrentText('1')
        w.pp_divider_box.setCurrentText('1')
        w.p2_divider_box.setCurrentText('2')
        w._refresh_divider_status()
        self.assertIn('enabled', w.divider_status.text().lower())
        decision = w._validate_divider_route(check_only=True)
        self.assertEqual((decision.status, decision.rule_id),
                         ('enabled', 'cp_default'))
        w.extract_parameters()
        self.assertEqual(w.Winding_Para.branch_dividers, (1, 1, 2))
        report = w.base_db_conductor_id.layout_report
        self.assertEqual(report['pattern_route']['rule_id'], 'cp_default')
        self.assertTrue(report['layout_retained'], report)
        branches = [branch[1] for branch in w.base_db_conductor_id]
        self.assertEqual(len(branches), 6)
        self.assertTrue(all(
            abs(end[1] - start[1]) in {1, 2}
            for branch in branches for start, end in zip(branch, branch[1:])))

    def test_cp_six_layer_route_is_disabled_and_rejected(self):
        w = self.window
        f = w.input_fields
        f['winding_input_mode'].setCurrentText('q and poles')
        f['pattern_name'].setText('CP')
        f['q'].setText('2')
        f['num_poles'].setText('8')
        f['num_layers'].setText('6')
        f['ab'].setText('4')
        w.q_divider_box.setCurrentText('1')
        w.pp_divider_box.setCurrentText('1')
        w.q_divider_box.setCurrentText('2')
        w.pp_divider_box.setCurrentText('2')
        w.p2_divider_box.setCurrentText('1')
        w._update_half_divider_availability()

        p2_index = w.p2_divider_box.findText('1')
        self.assertGreaterEqual(p2_index, 0)
        self.assertFalse(w.p2_divider_box.model().item(p2_index).isEnabled())
        w._refresh_divider_status()
        self.assertIn('disabled', w.divider_status.text().lower())
        self.assertIn('divisible by 4', w.divider_status.toolTip())
        with self.assertRaisesRegex(ValueError, 'divisible by 4'):
            w._validate_divider_route()

    def test_cp_selected_pp_p2_rejects_duplicate_conductors(self):
        w = self.window
        f = w.input_fields
        f['winding_input_mode'].setCurrentText('q and poles')
        f['pattern_name'].setText('CP')
        f['q'].setText('4')
        f['num_poles'].setText('16')
        f['num_layers'].setText('8')
        f['ab'].setText('8')
        w.q_divider_box.setCurrentText('1')
        w.pp_divider_box.setCurrentText('4')
        w.p2_divider_box.setCurrentText('2')
        self.assertIn('not supported', w.divider_status.text().lower())
        with self.assertRaisesRegex(ValueError, 'duplicate slot/layer references'):
            w._validate_divider_route()

    def test_zpp_selected_q_p2_factors_preserve_z_edges(self):
        w = self.window
        f = w.input_fields
        f['winding_input_mode'].setCurrentText('q and poles')
        f['pattern_name'].setText('ZPP')
        f['q'].setText('2')
        f['num_poles'].setText('8')
        f['num_layers'].setText('6')
        f['ab'].setText('4')
        f['inlet_from_weld_side'].setChecked(True)
        w.q_divider_box.setCurrentText('1')
        w.pp_divider_box.setCurrentText('2')
        w.p2_divider_box.setCurrentText('2')
        self.assertIn('eligible', w.divider_status.text().lower())
        w.extract_parameters()
        self.assertEqual(w.Winding_Para.branch_dividers, (1, 2, 2))
        paths = [branch[1] for branch in w.base_db_conductor_id]
        report = validate_branches(paths, default_phase_map(48, 8, 6),
                                   48, 8, 4)
        self.assertTrue(report['electrically_valid'], report['errors'])
        self.assertTrue(all(
            ((abs(((end[0] - start[0] + 24) % 48) - 24) in (5, 7)
              and end[1] == start[1])
             or (abs(((end[0] - start[0] + 24) % 48) - 24) == 6
                 and abs(end[1] - start[1]) == 1))
            for path in paths for start, end in zip(path, path[1:])))
        f['inlet_from_weld_side'].setChecked(False)
        self.assertIn('not supported', w.divider_status.text().lower())

    def test_zpp_selected_q_p2_factor_product_guard(self):
        w = self.window
        f = w.input_fields
        f['winding_input_mode'].setCurrentText('q and poles')
        f['pattern_name'].setText('ZPP')
        f['q'].setText('4')
        f['num_poles'].setText('16')
        f['num_layers'].setText('8')
        f['ab'].setText('8')
        f['inlet_from_weld_side'].setChecked(True)
        w.q_divider_box.setCurrentText('2')
        w.pp_divider_box.setCurrentText('2')
        w.p2_divider_box.setCurrentText('2')
        self.assertIn('eligible', w.divider_status.text().lower())
        w.extract_parameters()
        self.assertEqual(w.Winding_Para.branch_dividers, (2, 2, 2))
        paths = [branch[1] for branch in w.base_db_conductor_id]
        report = validate_branches(paths, default_phase_map(192, 16, 8),
                                   192, 16, 8)
        self.assertTrue(report['electrically_valid'], report['errors'])
        self.assertFalse(gw.supports_integer_zpp_factors(
            w.Winding_Para, (1, 4, 2)))
        self.assertFalse(gw.supports_integer_zpp_factors(
            w.Winding_Para, (2.5, 2, 2)))

    def test_zpp_selected_factors_retain_parallel_emf_mismatch(self):
        w = self.window
        f = w.input_fields
        f['winding_input_mode'].setCurrentText('q and poles')
        f['pattern_name'].setText('ZPP')
        f['q'].setText('4')
        f['num_poles'].setText('4')
        f['num_layers'].setText('2')
        f['ab'].setText('8')
        f['inlet_from_weld_side'].setChecked(True)
        w.q_divider_box.setCurrentText('2')
        w.pp_divider_box.setCurrentText('2')
        w.p2_divider_box.setCurrentText('2')
        self.assertIn('eligible', w.divider_status.text().lower())
        w.extract_parameters()
        self.assertEqual(w.base_db_conductor_id.layout_status,
                         'not strong symmetry layout')
        self.assertTrue(w.base_db_conductor_id.layout_report['layout_retained'])
        self.assertIn('parallel_emf_mismatch',
                      w.base_db_conductor_id.layout_report['errors'])

    def test_zpp_selected_q6_edges_and_direct_shift_guard(self):
        w = self.window
        f = w.input_fields
        f['winding_input_mode'].setCurrentText('q and poles')
        f['pattern_name'].setText('ZPP')
        f['q'].setText('6')
        f['num_poles'].setText('8')
        f['num_layers'].setText('6')
        f['ab'].setText('12')
        f['inlet_from_weld_side'].setChecked(True)
        w.q_divider_box.setCurrentText('3')
        w.pp_divider_box.setCurrentText('2')
        w.p2_divider_box.setCurrentText('2')
        self.assertIn('eligible', w.divider_status.text().lower())
        w.extract_parameters()
        paths = [branch[1] for branch in w.base_db_conductor_id]
        report = validate_branches(paths, default_phase_map(144, 8, 6),
                                   144, 8, 12)
        self.assertTrue(report['electrically_valid'], report['errors'])
        self.assertTrue(all(
            (abs(((end[0] - start[0] + 72) % 144) - 72),
             abs(end[1] - start[1])) in {(13, 0), (19, 0), (18, 1)}
            for path in paths for start, end in zip(path, path[1:])))
        with self.assertRaisesRegex(gw.PatternConfigurationError,
                                    'without shifts'):
            gw.get_winding_layout(
                'ZPP', w.TP_info, w.Winding_Para,
                w.Layout_Para._replace(phase_shift_pattern='Normal'))

    def test_zlp_q_divider_and_cp_no_divider_show_rejection(self):
        w = self.window
        fields = w.input_fields
        fields['winding_input_mode'].setCurrentText('q and poles')
        cases = (
            ('ZLP', 2, 8, 4, (2, 1, 1), 'ZLP does not support Q-divider greater than 1.'),
            ('ZLP', 2, 8, 4, (2, 2, 1), 'ZLP does not support Q-divider greater than 1.'),
            ('ZLP', 3, 12, 6, (3, 1, 1), 'ZLP does not support Q-divider greater than 1.'),
            ('CP', 2, 8, 4, (1, 1, 1), 'CP does not allow the no-divider (1,1,1) route.'),
        )
        for pattern, q, poles, layers, factors, reason in cases:
            with self.subTest(pattern=pattern, q=q, factors=factors):
                fields['pattern_name'].setText(pattern)
                fields['q'].setText(str(q))
                fields['num_poles'].setText(str(poles))
                fields['num_layers'].setText(str(layers))
                fields['ab'].setText(str(factors[0] * factors[1] * factors[2]))
                w.q_divider_box.setCurrentText(str(factors[0]))
                w.pp_divider_box.setCurrentText(str(factors[1]))
                w.p2_divider_box.setCurrentText(str(factors[2]))
                self.assertEqual(w._selected_dividers(), factors)
                self.assertIn('not supported', w.divider_status.text().lower())
                self.assertIn(reason, w.divider_status.toolTip())
                with self.assertRaisesRegex(ValueError, reason[:3]):
                    w._validate_divider_route()

    def test_zlp_paired_edge_rejects_opposite_layer_direction(self):
        winding = SimpleNamespace(q=3, num_slots=36, num_poles=4,
                                  num_layers=6, num_phases=3, ab=3)
        layout = SimpleNamespace(phase_shift_list=[0]*6)
        with patch.object(gw, 'validate_branches',
                          return_value={'electrically_valid': True,
                                        'errors': []}):
            with self.assertRaisesRegex(ValueError, 'invalid lap edge'):
                gw.validate_selected_zlp(
                    [(None, [(0, 1), (7, 0)])], winding, layout)

    def test_zlp_q2_paired_edge_rejects_opposite_layer_direction(self):
        winding = SimpleNamespace(q=2, num_slots=48, num_poles=8,
                                  num_layers=3, num_phases=3, ab=8)
        layout = SimpleNamespace(phase_shift_list=[0]*3)
        with patch.object(gw, 'validate_branches',
                          return_value={'electrically_valid': True,
                                        'errors': []}):
            with self.assertRaisesRegex(ValueError, 'invalid lap edge'):
                gw.validate_selected_zlp(
                    [(None, [(0, 1), (5, 0)])], winding, layout)

    def test_divider_config_roundtrip_and_legacy_fallback(self):
        w = self.window
        w.input_fields['winding_input_mode'].setCurrentText('q and poles')
        w.input_fields['q'].setText('1.5')
        w.input_fields['pattern_name'].setText('UWP')
        w.input_fields['ab'].setText('3')
        w._refresh_divider_from_inputs()
        payload = w._build_config_payload()
        self.assertEqual(tuple(payload['inputs'][key] for key in
                               ('q_divider', 'pp_divider', 'p2_divider')),
                         ('1.5', '1', '2'))
        w.input_fields['ab'].setText('2')
        w._apply_config_payload(payload)
        self.assertEqual(w._selected_dividers(), (1.5, 1, 2))
        self.assertEqual(w.input_fields['ab'].text(), '3')

        bad = {'inputs': dict(payload['inputs'], ab='4')}
        with self.assertRaisesRegex(ValueError, 'divider.*product'):
            w._apply_config_payload(bad)
        self.assertEqual(w.input_fields['ab'].text(), '3')

        w._apply_config_payload({'inputs': {'q': '3/2', 'num_poles': '8',
                                             'ab': '2', 'pattern_name': 'BWP'}})
        self.assertEqual(w._selected_dividers(), (1, 2, 1))

    def test_navigation_preserves_all_pages_and_plot_context(self):
        w = self.window
        self.assertFalse(hasattr(w, 'navigation'))
        self.assertEqual(w.tabs.count(), 11)
        for index in range(w.tabs.count()):
            w.tabs.setCurrentIndex(index)
            self.app.processEvents()
            self.assertIsInstance(w.tabs.widget(index), QScrollArea)
        volt_diff_index = next(index for index in range(w.tabs.count())
                               if w.tabs.tabText(index) == 'Volt Diff')
        w.tabs.setCurrentIndex(volt_diff_index)
        self.assertIs(w.plot_stack.currentWidget(), w.vd_plot_scroll_area)
        w.tabs.setCurrentIndex(6)
        self.assertIs(w.plot_stack.currentWidget(), w.canvas)
        self.assertFalse(w.bottom_splitter.isHidden())
        self.assertEqual(w.upper_splitter.count(), 2)

    def test_preview_does_not_call_patterns_and_views_share_data(self):
        w = self.window
        w.phase_view_selector.setCurrentText("Circular")
        w.input_fields['num_slots'].setText('36')
        w.input_fields['ab'].setText('invalid but irrelevant')
        with patch.object(w, 'extract_parameters', side_effect=AssertionError('Pattern path called')):
            w.phase_plot_button.click()
            self.assertEqual(w.current_view_type, 'phase')
            data = w.phase_preview
            self.assertEqual(len(data['records']), 216)
            self.assertTrue(w.ax.patches)
            circular_ids = [item.get_gid() for item in w.ax.patches]
            w.phase_view_selector.setCurrentText('Unwrapped')
            self.assertIs(w.phase_preview, data)
            self.assertEqual(len(w.ax.patches), 216)
            self.assertEqual(circular_ids, [item.get_gid() for item in w.ax.patches])
            self.assertIn('Mapping complete: True', w.layout_display.toPlainText())
            with patch('main_pyqt6.os.makedirs'), patch.object(w.figure, 'savefig') as save:
                w.save_layout_as_figure()
                save.assert_called_once()

    def test_calculation_results_keeps_brief_parameter_and_layout_summaries(self):
        w = self.window
        w.analyze_parameters()
        parameter_summary = w.result_display.toPlainText()
        self.assertIn('Parameters', parameter_summary)
        self.assertIn('Conductor:', parameter_summary)
        self.assertNotIn('K_bend_side', parameter_summary)
        w.analyze_layouts()
        combined_summary = w.result_display.toPlainText()
        self.assertIn(parameter_summary, combined_summary)
        self.assertIn('Layout Analysis', combined_summary)
        self.assertIn('Number of different pin shapes:', combined_summary)
        self.assertIn('This winding pattern', combined_summary)
        self.assertNotIn('Pin shapes:', combined_summary)

    def test_dependent_parameters_supports_half_integer_uwp_candidate(self):
        w = self.window
        w.input_fields['winding_input_mode'].setCurrentText('q and poles')
        w.input_fields['q'].setText('3/2')
        w.input_fields['num_poles'].setText('8')
        w.input_fields['ab'].setText('3')
        w.input_fields['pattern_name'].setText('UWP')
        w.analyze_parameters()
        details = w.dependent_params_display.toPlainText()
        self.assertNotIn('Invalid input', details)
        self.assertIn('Number of Slots: 36', details)
        self.assertIn('q: 3/2', details)
        self.assertIn('Slots: 36', w.result_display.toPlainText())

    def test_dependent_parameters_supports_other_rational_q_with_integer_slots(self):
        w = self.window
        w.input_fields['winding_input_mode'].setCurrentText('q and poles')
        w.input_fields['q'].setText('2/3')
        w.input_fields['num_poles'].setText('8')
        w.input_fields['ab'].setText('2')
        w.input_fields['pattern_name'].setText('UWP')
        w.analyze_parameters()
        details = w.dependent_params_display.toPlainText()
        self.assertNotIn('Invalid input', details)
        self.assertIn('q: 2/3', details)
        self.assertIn('Number of Slots: 16', details)

    def test_clockwise_is_visual_only_and_shift_applies_once(self):
        w = self.window
        w.input_fields['num_slots'].setText('60')
        w.input_fields['phase_shift_pattern'].setCurrentText('Normal')
        w.input_fields['phase_shift'].setText('-1')
        w.input_fields['PSL'].setText('1')
        w.preview_phase_division()
        first = w.phase_preview
        w.input_fields['CW'].setChecked(not w.input_fields['CW'].isChecked())
        w.preview_phase_division()
        self.assertEqual(w.phase_preview['records'], first['records'])
        self.assertEqual(w.phase_preview['summary'], first['summary'])
        self.assertNotEqual(w.phase_preview['clockwise'], first['clockwise'])

    def test_unbalanced_arithmetic_valid_case_can_be_inspected(self):
        w = self.window
        w.input_fields['num_slots'].setText('6')
        w.input_fields['num_poles'].setText('6')
        w.preview_phase_division()
        self.assertEqual(w.current_view_type, 'phase')
        self.assertIn('WARNING', w.layout_display.toPlainText())
        self.assertIn('Mapping complete: True', w.layout_display.toPlainText())

    def test_invalid_preview_clears_old_result(self):
        w = self.window
        w.preview_phase_division()
        w.input_fields['num_slots'].setText('0')
        w.preview_phase_division()
        self.assertIsNone(w.phase_preview)
        self.assertEqual(w.current_view_type, 'empty')
        self.assertFalse(w.ax.patches)
        self.assertIn('failed', w.layout_display.toPlainText())

    def test_draw_uses_existing_parameters(self):
        self.window.input_fields['radii_gap'].setText('0.35')
        self.window.plot_layout()
        self.assertEqual(self.window.Line_Para.radii_gap, 0.35)
        self.assertTrue(self.window.ax.patches)
        self.assertEqual(self.window.current_view_type, 'winding')

    def test_winding_view_switch_uses_plotted_snapshot_and_exports_current_view(self):
        w = self.window
        self.assertFalse(w.winding_view_selector.isEnabled())
        self.assertEqual(w.winding_view_selector.currentText(), 'Unwrapped')
        w.plot_layout()
        w.winding_view_selector.setCurrentText('Circular')
        state = w.calculation_state
        conductors = w.cond_info.copy()
        w.input_fields['num_slots'].setText('96')
        with patch.object(w, 'extract_parameters', side_effect=AssertionError('Recomputed')):
            w.winding_view_selector.setCurrentText('Unwrapped')
            self.assertEqual(w.current_view_type, 'winding')
            self.assertEqual(w.ax.get_xlabel(), 'Slot')
            self.assertIs(w.calculation_state, state)
            __import__('numpy').testing.assert_array_equal(w.cond_info, conductors)
            limits = (w.ax.get_xlim(), w.ax.get_ylim())
            w.ax.set_xlim(3, 9)
            w.fit_plot_view()
            self.assertEqual((w.ax.get_xlim(), w.ax.get_ylim()), limits)
            with patch('main_pyqt6.os.makedirs'), patch.object(w.figure, 'savefig') as save:
                w.save_layout_as_figure()
                self.assertIn('Unwrapped', str(save.call_args))
                self.assertIn('S48P', str(save.call_args))
            w.winding_view_selector.setCurrentText('Circular')
            self.assertEqual(w.current_view_type, 'winding')
        self.assertEqual(w.input_fields['num_slots'].text(), '96')

    def test_winding_render_failure_disables_save_and_can_recover(self):
        w = self.window
        w.plot_layout()
        w.winding_view_selector.setCurrentText('Circular')
        with patch('main_pyqt6.dfig.draw_unwrapped_winding_layout', side_effect=ValueError('injected')):
            w.winding_view_selector.setCurrentText('Unwrapped')
        self.assertEqual(w.current_view_type, 'empty')
        with patch.object(w.figure, 'savefig') as save:
            w.save_layout_as_figure()
            save.assert_not_called()
        w.plot_layout()
        self.assertEqual(w.current_view_type, 'winding')

    def test_winding_view_keeps_snapshot_after_analysis_and_context_changes(self):
        from types import SimpleNamespace
        w = self.window
        w.plot_layout()
        w.input_fields['num_slots'].setText('96')
        w.extract_parameters()
        state = w.calculation_state
        with patch.object(w, 'extract_parameters', side_effect=AssertionError('Recomputed')), \
                patch('main_pyqt6.gw.Winding_Phase_division', side_effect=AssertionError('Remapped')):
            w.winding_view_selector.setCurrentText('Unwrapped')
            self.assertEqual(len(w.ax.get_xticks()), 48)
            self.assertIs(w.calculation_state, state)
            limits = w.ax.get_xlim()
            w._zoom_plot_event(SimpleNamespace(inaxes=w.ax, xdata=24, ydata=3, button='up'))
            self.assertLess(w.ax.get_xlim()[1] - w.ax.get_xlim()[0], limits[1] - limits[0])
            w.fit_plot_view()
            self.assertEqual(w.ax.get_xlim(), limits)
            w.toggle_plot_window()
            self.app.processEvents()
            self.assertIs(w.winding_view_controls.parentWidget(), w.plot_toolbar)
            self.assertIs(w.plot_toolbar.parentWidget(), w.plot_window)
            w.plot_window.close()
            self.app.processEvents()
            self.assertIs(w.plot_toolbar.parentWidget(), w.figure_container)
            w.tabs.setCurrentIndex(9)
            self.assertFalse(w.winding_view_controls.isVisible())
            w.tabs.setCurrentIndex(0)
            self.assertTrue(w.winding_view_controls.isVisible())
        w.preview_phase_division()
        self.assertEqual(w.phase_view_selector.currentText(), 'Unwrapped')
        self.assertFalse(w.winding_view_controls.isVisible())
        w.plot_layout()
        self.assertEqual(w.winding_view_selector.currentText(), 'Unwrapped')
        self.assertEqual(len(w.ax.get_xticks()), 96)

    def test_specific_branch_filter_uses_snapshot_without_recalculation(self):
        w = self.window
        w.plot_layout()
        state = w.calculation_state
        with patch.object(w, 'extract_parameters', side_effect=AssertionError('Recomputed')):
            w.winding_branch_selector.setCurrentIndex(w.winding_branch_selector.findData(3))
            self.assertEqual({e['branch'] for e in w.ax._winding_edges}, {3})
            self.assertEqual({e['branch'] for e in w.ax._winding_terminals}, {3})
            self.assertIs(w.calculation_state, state)
            with patch('main_pyqt6.os.makedirs'), patch.object(w.figure, 'savefig') as save:
                w.save_layout_as_figure()
                self.assertIn('Branch3', str(save.call_args))

    def test_winding_branch_selector_labels_each_branch_with_its_phase(self):
        w = self.window
        w.plot_layout()
        branch_phase = {}
        for row in w._winding_plot_data['cond_info']:
            branch = int(row[3])
            if branch > 0:
                branch_phase.setdefault(branch, set()).add(int(row[2]))
        local_number = {}
        for phase in sorted({next(iter(phases)) for phases in branch_phase.values()
                             if len(phases) == 1}):
            for number, branch in enumerate(sorted(
                    branch for branch, phases in branch_phase.items()
                    if phases == {phase}), start=1):
                local_number[branch] = number
        self.assertEqual(
            [(w.winding_phase_selector.itemText(index), w.winding_phase_selector.itemData(index))
             for index in range(w.winding_phase_selector.count())],
            [('All', None), ('Phase A', 0), ('Phase B', 1), ('Phase C', 2)])
        for index in range(1, w.winding_branch_selector.count()):
            branch = w.winding_branch_selector.itemData(index)
            phases = branch_phase[branch]
            self.assertEqual(len(phases), 1)
            phase = "ABC"[phases.pop()]
            self.assertEqual(w.winding_branch_selector.itemText(index),
                             f"{phase}: Branch {local_number[branch]}")

    def test_phase_selector_filters_the_snapshot_to_all_branches_of_that_phase(self):
        w = self.window
        w.plot_layout()
        state = w.calculation_state
        phase = 1
        phase_branches = {
            int(row[3]) for row in w._winding_plot_data['cond_info']
            if int(row[2]) == phase and int(row[3]) > 0
        }
        with patch.object(w, 'extract_parameters', side_effect=AssertionError('Recomputed')):
            w.winding_phase_selector.setCurrentIndex(
                w.winding_phase_selector.findData(phase))
            self.assertEqual({edge['branch'] for edge in w.ax._winding_edges}, phase_branches)
            self.assertEqual({terminal['branch'] for terminal in w.ax._winding_terminals}, phase_branches)
            self.assertIs(w.calculation_state, state)
            with patch('main_pyqt6.os.makedirs'), patch.object(w.figure, 'savefig') as save:
                w.save_layout_as_figure()
                self.assertIn('PhaseB', str(save.call_args))

    def test_manual_start_preview_is_complete_and_does_not_publish_calculation(self):
        w = self.window
        w.plot_layout()
        state = w.calculation_state
        w.preview_phase_division()
        with patch.object(w, 'extract_parameters', side_effect=AssertionError('Production extraction')):
            w.phase_start_mode.setChecked(True)
            self.assertEqual(w._manual_start_context['status'], 'candidate')
            branch = w._manual_start_context['branches'][0]
            w._select_manual_start(*branch['path'][2][:2])
            result = w._manual_start_results[branch['id']]
            self.assertEqual(result['status'], 'candidate')
            self.assertEqual(len(result['path']), len(branch['path']))
            self.assertEqual(result['start'], branch['path'][2][:2])
            self.assertTrue(any((line.get_gid() or '').startswith('manual-preview-') for line in w.ax.lines))
            self.assertIs(w.calculation_state, state)
            w.phase_view_selector.setCurrentText('Circular')
            self.assertIs(w._manual_start_results[branch['id']], result)
            w._reset_manual_starts()
            self.assertFalse(w._manual_start_results)

    def test_manual_start_click_switches_to_position_owner(self):
        from matplotlib.backend_bases import MouseEvent

        w = self.window
        w.preview_phase_division()
        w.phase_start_mode.setChecked(True)
        branches = w._manual_start_context['branches']
        first = branches[0]
        same_phase = next(b for b in branches if b['phase'] == first['phase'] and b['id'] != first['id'])
        other_phase = next(b for b in branches if b['phase'] != first['phase'])

        for target in (same_phase, other_phase):
            w.phase_start_branch.setCurrentIndex(w.phase_start_branch.findData(first['id']))
            slot, layer = target['path'][0][:2]
            w.canvas.draw()
            x, y = w.ax.transData.transform((slot + 1, layer + 1))
            w.canvas.callbacks.process(
                'button_press_event', MouseEvent('button_press_event', w.canvas, x, y, button=1))
            self.assertEqual(w.phase_start_branch.currentData(), target['id'])
            self.assertEqual(w._manual_start_results[target['id']]['start'], (slot, layer))
            self.assertEqual(w._manual_start_results[target['id']]['status'], 'candidate')
            self.assertNotIn(first['id'], w._manual_start_results)

    def test_fractional_manual_branch_preview_does_not_generate_connections(self):
        from matplotlib.backend_bases import MouseEvent

        w = self.window
        w.input_fields['num_slots'].setText('36')
        w.preview_phase_division()
        with patch('main_pyqt6.gw.get_winding_layout', side_effect=AssertionError('Fractional dispatch')):
            w.phase_start_mode.setChecked(True)
            self.assertEqual(w._manual_start_context['status'], 'division_candidate')
            first = w._manual_start_context['branches'][0]
            start = first['start']
            w._select_manual_start(*start)
            self.assertEqual(w._manual_start_results[1]['status'], 'branch_preview')
            self.assertFalse(any((line.get_gid() or '').startswith('manual-preview-') for line in w.ax.lines))
            w.phase_start_branch.setCurrentIndex(1)
            w._select_manual_start(*start)
            self.assertEqual(w.phase_start_branch.currentData(), first['id'])
            second = w._manual_start_context['branches'][1]
            w.canvas.draw()
            x, y = w.ax.transData.transform((second['start'][0] + 1, second['start'][1] + 1))
            w.canvas.callbacks.process(
                'button_press_event', MouseEvent('button_press_event', w.canvas, x, y, button=1))
            self.assertEqual(w.phase_start_branch.currentData(), second['id'])
            selectable = next(c for c in w.ax.collections if c.get_gid() == 'manual-selectable')
            self.assertEqual(len(selectable.get_offsets()), len(second['members']))
            def cell(position):
                gid = f'slot={position[0]+1};layer={position[1]+1};'
                return next(p for p in w.ax.patches if p.get_gid().startswith(gid))
            self.assertGreater(cell(second['start']).get_alpha(), cell(first['start']).get_alpha())
            other = next(b for b in w._manual_start_context['branches'] if b['phase'] == 1)
            w._select_manual_start(*other['start'])
            self.assertEqual(w.phase_start_branch.currentData(), other['id'])
            self.assertEqual(w._manual_start_results[other['id']]['status'], 'branch_preview')
            self.assertFalse(hasattr(w, 'calculation_state'))

    def test_branch_division_uses_same_supported_phase_setting_as_preview(self):
        w = self.window
        for phases in (3, 5, 6, 7, 9, 12):
            with self.subTest(phases=phases):
                layers = (2 * (phases // 3)
                          if phases > 3 and phases % 3 == 0 else 6)
                w.input_fields['num_phases'].setText(str(phases))
                w.input_fields['num_slots'].setText(str(12 * phases))
                w.input_fields['num_layers'].setText(str(layers))
                w.preview_phase_division()
                self.assertEqual(w.phase_preview['phases'], phases)
                if phases > 3 and phases % 3 == 0:
                    summary = w.phase_preview['summary']
                    self.assertTrue(summary['balanced'], summary)
                    self.assertEqual(len(summary['sets']), phases // 3)
                    self.assertIn('Balance by three-phase winding sets: PASS',
                                  w.phase_preview['report'])
                    self.assertIn(f'Set {phases // 3} ',
                                  w.phase_preview['report'])
                w.open_branch_division()
                self.assertTrue(w.branch_division_dialog.isVisible())
                w.branch_division_dialog.preview_button.click()
                self.assertEqual(w._manual_start_context['status'], 'division_candidate')
                self.assertEqual(len(w._manual_start_context['branches']), phases * 2)
                self.assertEqual(w.phase_start_branch.count(), phases * 2)
                self.assertIn(f'Phase {w._phase_label(phases - 1)}',
                              w.phase_start_branch.itemText(phases * 2 - 1))
                report = w._format_uwp_candidate_analysis(
                    {'errors': [], 'branch_emf': {phases - 1: [(1.0, 0.0)]}},
                    drawn=False)
                self.assertIn(f'Phase {w._phase_label(phases - 1)} branch EMF',
                              report)

    def test_branch_division_workbench_selects_rule_without_production_changes(self):
        w = self.window
        w.input_fields['num_slots'].setText('36')
        w.preview_phase_division()
        original_pattern = w.input_fields['pattern_name'].text()
        with patch('main_pyqt6.gw.get_winding_layout', side_effect=AssertionError('Production dispatch')):
            w.branch_division_button.click()
            dialog = w.branch_division_dialog
            self.assertTrue(dialog.isVisible())
            self.assertEqual((dialog.pole_groups.value(), dialog.position_branches.value()), (2, 1))
            self.assertEqual(dialog.table.rowCount(), len(dialog.patterns) * 2)
            dialog.table.cellClicked.emit(0, 0)
            self.assertEqual((dialog.pole_groups.value(), dialog.position_branches.value()), (1, 2))
            dialog.pole_groups.setValue(1)
            self.assertEqual(dialog.position_branches.value(), 2)
            dialog.preview_button.click()
            self.assertEqual(w._manual_start_context['status'], 'division_candidate')
            self.assertEqual((w._manual_start_context['division_plan']['pole_divider'],
                              w._manual_start_context['division_plan']['position_divider']), (1, 2))
            dialog.pole_groups.setValue(2)
            dialog.preview_button.click()
            self.assertEqual((w._manual_start_context['division_plan']['pole_divider'],
                              w._manual_start_context['division_plan']['position_divider']), (2, 1))
            dialog.pattern.setCurrentText('SSP')
            dialog.preview_button.click()
            self.assertEqual(w._manual_start_context['division_plan']['pattern'], 'SSP')
            dialog.pattern.setCurrentText('BWP')
            dialog.mark_preferred_button.click()
            self.assertEqual(dialog.preferred_rules[dialog.pattern.currentText()], (2, 1))
            self.assertEqual(w.input_fields['pattern_name'].text(), original_pattern)
            dialog.close()
            w.branch_division_button.click()
            self.assertEqual(w.branch_division_dialog.preferred_rules['BWP'], (2, 1))
            w.branch_division_dialog.pattern.setCurrentText('LPP')
            w.branch_division_dialog.pole_groups.setValue(1)
            self.assertFalse(w.branch_division_dialog.preview_button.isEnabled())
            w.branch_division_dialog.pole_groups.setValue(3)
            self.assertFalse(w.branch_division_dialog.preview_button.isEnabled())
            self.assertEqual(w.input_fields['pattern_name'].text(), original_pattern)
            w.branch_division_dialog.close()

    def test_branch_division_rule_stales_with_phase_inputs(self):
        w = self.window
        w.input_fields['num_slots'].setText('36')
        w.preview_phase_division()
        w.branch_division_button.click()
        dialog = w.branch_division_dialog
        self.assertTrue(dialog.preview_button.isEnabled())
        w.input_fields['num_slots'].setText('48')
        self.app.processEvents()
        self.assertFalse(dialog.isVisible())
        self.assertIsNone(w.branch_division_dialog)
        w.branch_division_button.click()
        self.assertIsNone(w.branch_division_dialog)
        self.assertIn('Inputs changed', w.phase_start_status.text())

    def test_branch_division_rejects_invalid_naa_without_closing_phase_plot(self):
        w = self.window
        w.input_fields['num_slots'].setText('36')
        w.input_fields['ab'].setText('invalid')
        w.preview_phase_division()
        self.assertEqual(w.current_view_type, 'phase')
        w.branch_division_button.click()
        self.assertIsNone(w.branch_division_dialog)
        self.assertIn('Naa must be a positive integer', w.phase_start_status.text())

    def test_branch_division_six_branches_starts_with_two_by_three(self):
        w = self.window
        w.input_fields['num_slots'].setText('36')
        w.input_fields['ab'].setText('6')
        w.preview_phase_division()
        w.branch_division_button.click()
        dialog = w.branch_division_dialog
        self.assertEqual((dialog.pole_groups.value(), dialog.position_branches.value()), (2, 3))
        self.assertIn('Weak candidate', dialog.table.item(dialog.patterns.index('BWP'), 2).text())
        dialog.preview_button.click()
        self.assertEqual(len(w._manual_start_context['branches']), 18)
        self.assertEqual({len(b['members']) for b in w._manual_start_context['branches']}, {12})
        dialog.close()

    def test_two_point_five_q_workbench_starts_with_two_half_ring_regions(self):
        w = self.window
        w.input_fields['num_slots'].setText('60')
        w.input_fields['ab'].setText('2')
        w.preview_phase_division()
        w.phase_start_mode.setChecked(True)
        self.assertEqual(w._manual_start_context['status'], 'division_candidate')
        self.assertEqual(w._manual_start_context['division_plan']['pole_divider'], 2)
        w.branch_division_button.click()
        dialog = w.branch_division_dialog
        self.assertEqual((dialog.pole_groups.value(), dialog.position_branches.value()),
                         (2, 1))
        dialog.close()

    def test_half_integer_uwp_2q_plots_candidate_without_publishing_calculation(self):
        w = self.window
        w.plot_layout()
        self.assertTrue(hasattr(w, 'calculation_state'))

        w.input_fields['num_poles'].setText('8')
        w.input_fields['num_layers'].setText('6')
        w.input_fields['pattern_name'].setText('UWP')
        w.input_fields['tp_type'].setText('Regular')
        for slots, naa in ((36, 3), (60, 5)):
            with self.subTest(slots=slots):
                w.input_fields['num_slots'].setText(str(slots))
                w.input_fields['ab'].setText(str(naa))
                self.assertEqual(w._selected_dividers(),
                                 (slots / 24, 1, 2))
                self.assertIn('available', w.divider_status.text().lower())
                w.plot_layout()
                self.assertEqual(w.current_view_type, 'winding',
                                 w.message_log.toPlainText())
                self.assertTrue(w._winding_candidate)
                self.assertIsNotNone(w._winding_plot_data)
                self.assertFalse(hasattr(w, 'calculation_state'))
                self.assertIn('candidate', w.layout_display.toPlainText().lower())
                self.assertIn('parallel_emf_mismatch',
                              w.layout_display.toPlainText())
                self.assertIn(
                    'This winding pattern does not feature strong symmetry.',
                    w.layout_display.toPlainText())
                self.assertIn('Candidate', w.plot_view_title.text())
        w.input_fields['num_slots'].setText('48')
        w.input_fields['ab'].setText('2')
        w.plot_layout()
        self.assertEqual(w.current_view_type, 'winding', w.message_log.toPlainText())
        self.assertFalse(w._winding_candidate)
        self.assertTrue(hasattr(w, 'calculation_state'))

    def test_fractional_bwp_draft_plots_as_isolated_candidate(self):
        w = self.window
        w.input_fields['num_slots'].setText('36')
        w.input_fields['num_poles'].setText('8')
        w.input_fields['num_layers'].setText('6')
        w.input_fields['ab'].setText('1')
        w.input_fields['pattern_name'].setText('BWP')
        w.plot_layout()
        self.assertEqual(w.current_view_type, 'winding', w.message_log.toPlainText())
        self.assertTrue(w._winding_candidate)
        self.assertIn('BWP', w.layout_display.toPlainText())
        self.assertFalse(hasattr(w, 'calculation_state'))

    def test_fractional_sector_arrays_plot_as_candidates(self):
        w = self.window
        for pattern, slots, poles, naa in (('BWP', 90, 12, 3),
                                           ('UWP', 84, 8, 4)):
            with self.subTest(pattern=pattern):
                w.input_fields['num_slots'].setText(str(slots))
                w.input_fields['num_poles'].setText(str(poles))
                w.input_fields['num_layers'].setText('6')
                w.input_fields['ab'].setText(str(naa))
                w.input_fields['pattern_name'].setText(pattern)
                w.plot_layout()
                self.assertEqual(w.current_view_type, 'winding',
                                 w.message_log.toPlainText())
                self.assertTrue(w._winding_candidate)
                self.assertIn(pattern, w.layout_display.toPlainText())
                self.assertIn('Global wave array:', w.layout_display.toPlainText())
                self.assertIn('Special edges:', w.layout_display.toPlainText())
                self.assertIn('sector_array', w._winding_plot_data['candidate_report'])
                self.assertFalse(hasattr(w, 'calculation_state'))
                w.analyze_layouts()
                self.assertIn('Global wave array:', w.layout_display.toPlainText())
                self.assertIn('default pitch', w.layout_display.toPlainText())
                self.assertFalse(hasattr(w, 'calculation_state'))

    def test_q_two_point_five_bwp_single_branch_replots_as_candidate(self):
        w = self.window
        w.plot_layout()
        self.assertTrue(hasattr(w, 'calculation_state'))
        fields = w.input_fields
        fields['winding_input_mode'].setCurrentText('q and poles')
        fields['q'].setText('2.5')
        fields['num_poles'].setText('8')
        fields['num_layers'].setText('6')
        fields['ab'].setText('1')
        fields['pattern_name'].setText('BWP')
        w.analyze_layouts()
        self.assertIn('BWP half-integer q candidate',
                      w.layout_display.toPlainText())
        self.assertFalse(hasattr(w, 'calculation_state'))
        for _ in range(2):
            w.plot_layout()
            self.assertEqual(w.current_view_type, 'winding',
                             w.message_log.toPlainText())
            self.assertTrue(w._winding_candidate)
            self.assertEqual(fields['num_slots'].text(), '60')
            self.assertFalse(hasattr(w, 'calculation_state'))
        with patch('main_pyqt6.os.makedirs'), patch.object(w.figure, 'savefig') as save:
            w.save_layout_as_figure()
            self.assertIn('_BWPCandidate_', save.call_args.args[0])

    def test_half_integer_uwp_layout_analysis_reports_candidate_without_publishing(self):
        w = self.window
        w.plot_layout()
        self.assertTrue(hasattr(w, 'calculation_state'))
        plot_data = w._winding_plot_data
        w.input_fields['num_poles'].setText('8')
        w.input_fields['num_layers'].setText('6')
        w.input_fields['num_slots'].setText('36')
        w.input_fields['ab'].setText('3')
        w.input_fields['pattern_name'].setText('UWP')
        w.analyze_layouts()
        summary = w.layout_display.toPlainText()
        self.assertIn('candidate', summary.lower())
        self.assertIn('Overall Results for Phase A:', summary)
        self.assertNotIn('Overall Results for Phase B:', summary)
        self.assertNotIn('Overall Results for Phase C:', summary)
        for phase in 'ABC':
            self.assertIn(f'Phase {phase} branch complex EMF:', summary)
        self.assertIn('Number of different pin shapes:', summary)
        self.assertIn('ALWP  Layer', summary)
        self.assertIn('Position occupancy by branch:', summary)
        self.assertIn('Branch 1:', summary)
        self.assertIn('P1-P9', summary)
        self.assertIn('Branch 1: L1P1: 4 conds; L2P5: 4 conds; '
                      'L3P1: 4 conds; L4P5: 4 conds', summary)
        self.assertIn('This winding pattern does not feature strong symmetry.', summary)
        self.assertIn('parallel_emf_mismatch', summary)
        self.assertNotIn('Layout analysis failed', summary)
        self.assertEqual(w.current_view_type, 'winding')
        self.assertFalse(hasattr(w, 'calculation_state'))
        self.assertIs(w._winding_plot_data, plot_data)

    def test_unsupported_fractional_layout_analysis_shows_specific_reason(self):
        w = self.window
        w.input_fields['winding_input_mode'].setCurrentText('q and poles')
        w.input_fields['q'].setText('7/3')
        w.input_fields['num_poles'].setText('6')
        w.input_fields['ab'].setText('2')
        w.input_fields['pattern_name'].setText('UWP')
        w.analyze_layouts()
        summary = w.layout_display.toPlainText()
        self.assertIn('Fractional-q connection generation is not supported', summary)
        self.assertNotIn('Reference:', summary)

    def test_single_branch_uwp_candidate_reports_strong_without_occupancy(self):
        w = self.window
        w.input_fields['num_poles'].setText('8')
        w.input_fields['num_slots'].setText('12')
        w.input_fields['ab'].setText('1')
        w.input_fields['pattern_name'].setText('UWP')
        w.analyze_layouts()
        summary = w.layout_display.toPlainText()
        self.assertEqual(summary.count('This winding pattern features strong symmetry.'), 3)
        self.assertNotIn('Position occupancy by branch:', summary)
        self.assertEqual(summary.count('Branch 1:'), 3)

    def test_candidate_pin_shapes_follow_odd_all_branch_inlet_rotation(self):
        import layout_analysis as la
        w = self.window
        w.input_fields['num_poles'].setText('8')
        w.input_fields['num_slots'].setText('36')
        w.input_fields['num_layers'].setText('6')
        w.input_fields['ab'].setText('3')
        w.input_fields['pattern_name'].setText('UWP')
        w.volt_diff_inlet_adjustments_all = [1] + [0] * 8
        state = w.extract_parameters(candidate_only=True).values
        args = (state['db_conductor_id'], state['Winding_Para'],
                state['Layout_Para'], state['candidate_report'])
        expected = la.format_fractional_candidate_analysis(
            *args, state['all_branch_adjustments'])
        self.assertNotEqual(expected, la.format_fractional_candidate_analysis(*args))
        w.analyze_layouts()
        self.assertTrue(w.layout_display.toPlainText().startswith(expected))
        self.assertIn('Overall Results for Phase B:', expected)
        self.assertIn('Overall Results for Phase C:', expected)

    def test_candidate_analysis_preserves_existing_winding_plot_and_export(self):
        w = self.window
        w.plot_layout()
        self.assertEqual(w.current_view_type, 'winding')
        w.input_fields['num_poles'].setText('8')
        w.input_fields['num_layers'].setText('6')
        w.input_fields['num_slots'].setText('36')
        w.input_fields['ab'].setText('3')
        w.input_fields['pattern_name'].setText('UWP')
        w.analyze_layouts()
        self.assertEqual(w.current_view_type, 'winding')
        self.assertIsNotNone(w._winding_plot_data)
        with patch.object(w.figure, 'savefig') as save:
            w.save_layout_as_figure()
        self.assertTrue(save.called)
        self.assertNotIn('Phase_', save.call_args.args[0])

    def test_fraction_text_allows_uwp_pattern_selection_for_2q_candidate(self):
        w = self.window
        w.input_fields['winding_input_mode'].setCurrentText('q and poles')
        w.input_fields['num_poles'].setText('8')
        for q, slots, naa in (('1/2', 12, 1), ('3/2', 36, 3),
                              ('9/2', 108, 9)):
            with self.subTest(q=q):
                w.input_fields['q'].setText(q)
                w.input_fields['ab'].setText(str(naa))
                w.set_pattern_with_validation('UWP')
                self.assertEqual(w.input_fields['pattern_name'].text(), 'UWP')
                self.assertEqual(w.input_fields['num_slots'].text(), str(slots))
                self.assertNotIn('Invalid pattern or winding input',
                                 w.message_log.toPlainText())
                w.plot_layout()
                self.assertEqual(w.current_view_type, 'winding',
                                 w.message_log.toPlainText())
                self.assertTrue(w._winding_candidate)
        w.set_pattern_with_validation('BWP')
        self.assertEqual(w.input_fields['pattern_name'].text(), 'UWP')
        self.assertIn('supports only half-integer UWP',
                      w.message_log.toPlainText())

    def test_half_integer_uwp_optimizer_keeps_no_transposition(self):
        w = self.window
        w.input_fields['winding_input_mode'].setCurrentText('q and poles')
        w.input_fields['q'].setText('3/2')
        w.input_fields['num_poles'].setText('8')
        w.input_fields['ab'].setText('3')
        w.set_pattern_with_validation('UWP')
        w.update_transp_type('Interval')
        w.input_fields['tp_interval'].setText('1')
        w.config_optimise_pattern()
        self.assertEqual(w.input_fields['tp_type'].text(), 'Regular')
        self.assertTrue(all(w.input_fields[key].text() == '0' for key in
                            ('tp_interval', 'tp_times', 'uni_tp', 'pltp_fl',
                             'pltp_ll', 'jltp')))
        w.plot_layout()
        self.assertEqual(w.current_view_type, 'winding', w.message_log.toPlainText())

    def test_pattern_buttons_disable_generated_integer_failures_and_refresh(self):
        from PyQt6.QtTest import QTest

        w = self.window
        self.assertTrue(w.pattern_buttons['TSP'].isEnabled())
        w.input_fields['ab'].setText('1')
        QTest.qWait(180)
        self.assertFalse(w.pattern_buttons['TSP'].isEnabled())
        self.assertIn('branch', w.pattern_buttons['TSP'].toolTip().lower())
        selected = w.input_fields['pattern_name'].text()
        w.pattern_buttons['TSP'].click()
        self.assertEqual(w.input_fields['pattern_name'].text(), selected)
        w.input_fields['ab'].setText('2')
        QTest.qWait(180)
        self.assertTrue(w.pattern_buttons['TSP'].isEnabled())
        w.input_fields['ab'].setText('4')
        QTest.qWait(180)
        self.assertFalse(w.pattern_buttons['UWP'].isEnabled())
        self.assertNotIn('(2, 2, 1)', w.pattern_buttons['UWP'].toolTip())
        w.input_fields['pattern_name'].setText('UWP')
        self.assertTrue(w.input_fields['pattern_name'].property('patternUnavailable'))
        w.input_fields['ab'].setText('2')
        QTest.qWait(180)
        self.assertFalse(w.input_fields['pattern_name'].property('patternUnavailable'))
        w.input_fields['ab'].setText('4')
        QTest.qWait(180)
        w.set_pattern_with_validation('UWP')
        self.assertEqual(w.input_fields['pattern_name'].text(), 'UWP')

    def test_pattern_buttons_fractional_candidate_and_invalid_input(self):
        from PyQt6.QtTest import QTest

        w = self.window
        w.input_fields['winding_input_mode'].setCurrentText('q and poles')
        w.input_fields['q'].setText('3/2')
        w.input_fields['ab'].setText('3')
        QTest.qWait(180)
        self.assertTrue(w.pattern_buttons['UWP'].isEnabled())
        self.assertFalse(w.pattern_buttons['BWP'].isEnabled())
        w.input_fields['ab'].setText('bad')
        QTest.qWait(180)
        self.assertTrue(all(not button.isEnabled()
                            for button in w.pattern_buttons.values()))

    def test_half_integer_uwp_disables_weld_inlet_with_guidance(self):
        from PyQt6.QtCore import Qt
        from PyQt6.QtTest import QTest

        w = self.window
        fields = w.input_fields
        weld_inlet = fields['inlet_from_weld_side']
        self.assertTrue(weld_inlet.isEnabled())
        weld_inlet.setChecked(True)

        fields['winding_input_mode'].setCurrentText('q and poles')
        fields['q'].setText('3/2')
        fields['num_poles'].setText('8')
        fields['ab'].setText('3')
        w.set_pattern_with_validation('UWP')
        QTest.qWait(180)

        self.assertFalse(weld_inlet.isEnabled())
        self.assertFalse(weld_inlet.isChecked())
        self.assertIn('do not click', weld_inlet.toolTip().lower())
        self.assertIn('do not click', w.weld_inlet_label.toolTip().lower())
        self.assertIn('turned off', w.message_log.toPlainText().lower())
        QTest.mouseClick(weld_inlet, Qt.MouseButton.LeftButton)
        self.assertFalse(weld_inlet.isChecked())

        fields['ab'].setText('6')
        QTest.qWait(180)
        self.assertFalse(weld_inlet.isEnabled())

        fields['q'].setText('2')
        fields['ab'].setText('2')
        QTest.qWait(180)
        self.assertTrue(weld_inlet.isEnabled())
        self.assertEqual(w.weld_inlet_label.text(), 'Weld inlet:')
        self.assertEqual(w.weld_inlet_label.toolTip(), '')

        w._apply_config_payload({'inputs': {
            'winding_input_mode': 'q and poles', 'q': '3/2',
            'num_poles': '8', 'num_phases': '3', 'num_layers': '6',
            'ab': '3', 'pattern_name': 'UWP',
            'inlet_from_weld_side': '1',
        }})
        self.assertFalse(weld_inlet.isEnabled())
        self.assertFalse(weld_inlet.isChecked())

    def test_half_integer_uwp_unverified_swap_options_are_gray(self):
        from PyQt6.QtTest import QTest

        w = self.window
        w.input_fields['winding_input_mode'].setCurrentText('q and poles')
        w.input_fields['q'].setText('3/2')
        w.input_fields['ab'].setText('3')
        w.set_pattern_with_validation('UWP')
        QTest.qWait(180)
        model = w.tp_type_field.model()
        self.assertTrue(model.item(0).isEnabled())
        for index in range(1, 4):
            self.assertFalse(model.item(index).isEnabled())
            self.assertIn('Advanced', model.item(index).toolTip())
        self.assertTrue(w.pole_group_advanced_toggle.isEnabled())
        self.assertIn('Open Advanced', w.fractional_tp_notice.text())
        self.assertFalse(w.fractional_advanced_row.isHidden())
        self.assertEqual(w.pole_group_advanced_toggle.text(), 'Advanced')
        self.assertTrue(w.pattern_buttons['UWP'].isEnabled())
        w.input_fields['q'].setText('5/2')
        w.input_fields['ab'].setText('5')
        QTest.qWait(180)
        self.assertTrue(w.pattern_buttons['UWP'].isEnabled())
        self.assertTrue(all(not model.item(index).isEnabled()
                            for index in range(1, 4)))
        w.input_fields['q'].setText('2')
        w.input_fields['ab'].setText('2')
        QTest.qWait(180)
        self.assertTrue(all(model.item(index).isEnabled()
                            for index in range(4)))
        self.assertFalse(w.fractional_tp_notice.isVisible())
        self.assertTrue(w.fractional_advanced_row.isHidden())

    def test_fractional_group_transposition_ui_config_and_candidate(self):
        w = self.window
        w.input_fields['winding_input_mode'].setCurrentText('q and poles')
        w.input_fields['q'].setText('3/2')
        w.input_fields['num_poles'].setText('8')
        w.input_fields['ab'].setText('3')
        w.set_pattern_with_validation('UWP')
        w.pole_group_advanced_toggle.setChecked(True)
        w.input_fields['pole_n_tp_type'].setCurrentText('Times')
        w.input_fields['pole_n_tp_times'].setText('1')
        w.input_fields['pole_s_tp_type'].setCurrentText('Interval')
        w.input_fields['pole_s_tp_interval'].setText('1')
        payload = w._build_config_payload()
        self.assertEqual(payload['inputs']['pole_n_tp_times'], '1')
        self.assertEqual(payload['inputs']['pole_s_tp_type'], 'Interval')
        w.input_fields['pole_n_tp_times'].setText('0')
        w._apply_config_payload(payload)
        self.assertEqual(w.input_fields['pole_n_tp_times'].text(), '1')
        self.assertEqual(w.input_fields['pole_s_tp_type'].currentText(), 'Interval')
        w.plot_layout()
        self.assertIn('PoleS has fewer than two branches per phase',
                      w.message_log.toPlainText())
        w.input_fields['pole_s_tp_type'].setCurrentText('Regular')
        w.input_fields['pole_s_tp_interval'].setText('0')
        w.plot_layout()
        self.assertEqual(w.current_view_type, 'winding', w.message_log.toPlainText())
        self.assertTrue(w._winding_candidate)
        self.assertIn('PoleN/PoleS transposition candidate',
                      w.layout_display.toPlainText())
        self.assertFalse(hasattr(w, 'calculation_state'))
        w._apply_config_payload({'inputs': {'q': '3/2', 'num_poles': '8',
                                             'ab': '3', 'pattern_name': 'UWP'}})
        self.assertEqual(w.input_fields['pole_n_tp_type'].currentText(), 'Regular')
        self.assertEqual(w.input_fields['pole_n_tp_times'].text(), '0')
        self.assertEqual(w.input_fields['pole_s_tp_type'].currentText(), 'Regular')
        self.assertEqual(w.input_fields['pole_s_tp_interval'].text(), '0')

    def test_pole_group_advanced_panel_reports_phase_relative_branches_and_ranges(self):
        w = self.window
        w.input_fields['winding_input_mode'].setCurrentText('q and poles')
        w.input_fields['q'].setText('3/2')
        w.input_fields['num_poles'].setText('8')
        w.input_fields['num_layers'].setText('6')
        w.input_fields['ab'].setText('3')
        w.set_pattern_with_validation('UWP')
        w._refresh_fractional_uwp_transposition_options(w._pattern_base_inputs())

        self.assertFalse(w.pole_group_advanced_content.isVisible())
        self.assertEqual(w.pole_group_advanced_toggle.text(), 'Advanced')
        self.assertFalse(w.pole_group_advanced_toggle.isChecked())
        self.assertEqual(w.pole_group_cond_labels['pole_n'].text(), '2 branches')
        self.assertEqual(w.pole_group_cond_labels['pole_s'].text(), '1 branch')
        self.assertIn('phase-relative first pole',
                      w.pole_group_cond_labels['pole_n'].toolTip())
        self.assertIn('phase-relative second pole',
                      w.pole_group_cond_labels['pole_s'].toolTip())
        self.assertIn('Times 1-11', w.pole_group_tp_hints['pole_n'].text())
        self.assertIn('every insertion-side',
                      w.input_fields['pole_n_uni_tp'].toolTip())
        w.input_fields['pole_n_tp_type'].setCurrentText('Times')
        self.assertIn('not applied',
                      w.input_fields['pole_n_uni_tp'].toolTip())
        w.input_fields['pole_n_tp_type'].setCurrentText('Regular')
        self.assertIn('No pair for transposition',
                      w.pole_group_tp_hints['pole_s'].text())
        self.assertIn('Use Regular with all offsets 0',
                      w.pole_group_tp_hints['pole_s'].text())
        south_type = w.input_fields['pole_s_tp_type']
        self.assertFalse(south_type.model().item(1).isEnabled())
        self.assertFalse(south_type.model().item(2).isEnabled())
        self.assertFalse(south_type.model().item(3).isEnabled())
        self.assertTrue(w.input_fields['pole_s_uni_tp'].validator() is not None)

        w.input_fields['q'].setText('5/2')
        w.input_fields['ab'].setText('5')
        w._refresh_fractional_uwp_transposition_options(w._pattern_base_inputs())
        self.assertEqual(w.pole_group_cond_labels['pole_n'].text(), '3 branches')
        self.assertEqual(w.pole_group_cond_labels['pole_s'].text(), '2 branches')
        self.assertTrue(south_type.model().item(1).isEnabled())
        self.assertIsNone(w.input_fields['pole_s_uni_tp'].validator())

        w.tabs.setCurrentIndex(5)
        self.app.processEvents()
        w.pole_group_advanced_toggle.click()
        self.assertTrue(w.pole_group_advanced_content.isVisible())
        self.assertTrue(w.pole_group_advanced_toggle.isChecked())
        w.pole_group_advanced_toggle.click()
        self.assertFalse(w.pole_group_advanced_content.isVisible())
        self.assertFalse(w.pole_group_advanced_toggle.isChecked())

    def test_noninteger_transposition_notice_explains_unsupported_domain(self):
        w = self.window
        w.input_fields['winding_input_mode'].setCurrentText('q and poles')
        w.input_fields['q'].setText('2/3')
        w.input_fields['num_poles'].setText('8')
        w.input_fields['ab'].setText('2')
        w.input_fields['pattern_name'].setText('UWP')
        w._refresh_fractional_uwp_transposition_options(w._pattern_base_inputs())
        self.assertIn('Open Advanced', w.fractional_tp_notice.text())
        self.assertIn('requires half-integer q', w.fractional_tp_notice.text())
        self.assertFalse(w.pole_group_advanced_toggle.isEnabled())

    def test_pole_group_guidance_recomputes_after_layer_and_chw_shifts(self):
        from PyQt6.QtTest import QTest

        w = self.window
        w.input_fields['winding_input_mode'].setCurrentText('q and poles')
        w.input_fields['q'].setText('3/2')
        w.input_fields['num_poles'].setText('8')
        w.input_fields['num_layers'].setText('6')
        w.input_fields['ab'].setText('3')
        w.set_pattern_with_validation('UWP')
        w._refresh_fractional_uwp_transposition_options(w._pattern_base_inputs())
        baseline_signatures = set(w._pole_group_tp_adjacency_cache)

        w.input_fields['phase_shift_pattern'].setCurrentText('Normal')
        w.input_fields['phase_shift'].setText('1')
        QTest.qWait(200)
        self.assertTrue(set(w._pole_group_tp_adjacency_cache) - baseline_signatures)
        self.assertEqual(w.pole_group_cond_labels['pole_n'].text(), '2 branches')

        w.input_fields['radial_shift'].setChecked(True)
        QTest.qWait(200)
        self.assertEqual(w.pole_group_cond_labels['pole_n'].text(), '-- branches')
        self.assertIn('does not support radial conductor swaps',
                      w.pole_group_tp_hints['pole_n'].text())
        self.assertFalse(w.input_fields['pole_n_tp_type'].model().item(1).isEnabled())

    def test_pole_group_advanced_rows_align_with_different_hint_lengths(self):
        from PyQt6.QtCore import QPoint

        w = self.window
        w.resize(1920, 1080)
        w.upper_splitter.setSizes([1100, 820])
        w.input_fields['winding_input_mode'].setCurrentText('q and poles')
        w.input_fields['q'].setText('3/2')
        w.input_fields['num_poles'].setText('8')
        w.input_fields['num_layers'].setText('6')
        w.input_fields['ab'].setText('3')
        w.set_pattern_with_validation('UWP')
        w.tabs.setCurrentIndex(5)
        w.pole_group_advanced_toggle.click()
        self.app.processEvents()

        for left_width in (700, 1100):
            w.upper_splitter.setSizes([left_width, 1920 - left_width])
            self.app.processEvents()
            for suffix in ('tp_type', 'tp_interval', 'tp_times', 'uni_tp',
                           'pltp_fl', 'pltp_ll', 'jltp'):
                north = w.input_fields[f'pole_n_{suffix}']
                south = w.input_fields[f'pole_s_{suffix}']
                north_y = north.mapTo(w.pole_group_advanced_content, QPoint()).y()
                south_y = south.mapTo(w.pole_group_advanced_content, QPoint()).y()
                self.assertEqual(north_y, south_y, (left_width, suffix))

    def test_uniform_availability_does_not_depend_on_pair_candidates(self):
        from unittest.mock import patch
        import main_pyqt6

        w = self.window
        w.input_fields['winding_input_mode'].setCurrentText('q and poles')
        w.input_fields['q'].setText('3/2')
        w.input_fields['num_poles'].setText('8')
        w.input_fields['num_layers'].setText('6')
        w.input_fields['ab'].setText('3')
        w.set_pattern_with_validation('UWP')
        w._pole_group_tp_adjacency_cache = {}
        with patch.object(main_pyqt6.gw, '_fractional_swap_candidates',
                          return_value=[]):
            w._refresh_pole_group_tp_adjacency(w._pattern_base_inputs(), True)

        self.assertFalse(w.input_fields['pole_n_tp_type'].model().item(1).isEnabled())
        self.assertIsNotNone(w.input_fields['pole_n_tp_times'].validator())
        self.assertIsNone(w.input_fields['pole_n_uni_tp'].validator())
        self.assertIn('Uniform 1', w.pole_group_tp_hints['pole_n'].text())
        self.assertIsNotNone(w.input_fields['pole_s_uni_tp'].validator())

    def test_uniform_ui_rejects_layout_without_insert_cuts(self):
        w = self.window
        w.input_fields['winding_input_mode'].setCurrentText('q and poles')
        w.input_fields['q'].setText('3/2')
        w.input_fields['num_poles'].setText('2')
        w.input_fields['num_layers'].setText('2')
        w.input_fields['ab'].setText('3')
        w.set_pattern_with_validation('UWP')
        w._refresh_fractional_uwp_transposition_options(w._pattern_base_inputs())

        self.assertEqual(w.pole_group_cond_labels['pole_n'].text(), '2 branches')
        self.assertIsNotNone(w.input_fields['pole_n_uni_tp'].validator())
        self.assertIn('No insertion-side positions',
                      w.pole_group_tp_hints['pole_n'].text())

    def test_inactive_uniform_value_is_saved_but_not_executed(self):
        w = self.window
        w.input_fields['winding_input_mode'].setCurrentText('q and poles')
        w.input_fields['q'].setText('3/2')
        w.input_fields['num_poles'].setText('8')
        w.input_fields['num_layers'].setText('6')
        w.input_fields['ab'].setText('3')
        w.set_pattern_with_validation('UWP')
        w.input_fields['pole_n_uni_tp'].setText('1')
        w.input_fields['pole_n_tp_type'].setCurrentText('Times')
        w.input_fields['pole_n_tp_times'].setText('1')

        self.assertEqual(w._build_config_payload()['inputs']['pole_n_uni_tp'], '1')
        state = w.extract_parameters(candidate_only=True)
        effective = state.values['candidate_report']['transposition']['groups']['PoleN']
        self.assertEqual(effective['tp_type'], 'Times')
        self.assertEqual(effective['uni_tp'], 0)
        self.assertEqual(len(state.values['candidate_report']['transposition']['exchanges']), 3)

    def test_grouped_transposition_rejects_inlet_rotation(self):
        w = self.window
        w.input_fields['winding_input_mode'].setCurrentText('q and poles')
        w.input_fields['q'].setText('3/2')
        w.input_fields['num_poles'].setText('8')
        w.input_fields['ab'].setText('3')
        w.set_pattern_with_validation('UWP')
        w.input_fields['pole_n_tp_type'].setCurrentText('Times')
        w.input_fields['pole_n_tp_times'].setText('1')
        w.volt_diff_inlet_adjustments_all = [1] + [0] * 8
        with self.assertRaisesRegex(ValueError, 'do not support inlet adjustments'):
            w.extract_parameters(candidate_only=True)

    def test_manual_start_mouse_picking_in_both_views_and_stale_clearing(self):
        import math
        from matplotlib.backend_bases import MouseEvent
        w = self.window
        for clockwise in (False, True):
            w.input_fields['CW'].setChecked(clockwise)
            w.preview_phase_division()
            w.phase_start_mode.setChecked(True)
            branch = w._manual_start_context['branches'][0]
            slot, layer = branch['path'][0][:2]
            for view in ('Unwrapped', 'Circular'):
                w.phase_view_selector.setCurrentText(view)
                w._reset_manual_starts()
                self.assertFalse(w._manual_start_results)
                w.canvas.draw()
                if view == 'Unwrapped':
                    center = slot+1, layer+1
                else:
                    angle = (-1 if clockwise else 1) * 2*math.pi*slot/w.phase_preview['slots']
                    radius = 1-(layer+0.5)*0.52/w.phase_preview['layers']
                    center = radius*math.cos(angle), radius*math.sin(angle)
                x,y = w.ax.transData.transform(center)
                event = MouseEvent('button_press_event', w.canvas, x, y, button=1)
                w.canvas.callbacks.process('button_press_event', event)
                self.assertEqual(w._manual_start_results[branch['id']]['start'], (slot, layer))
        w.input_fields['ab'].setText('1')
        self.assertFalse(w.phase_start_mode.isChecked())
        self.assertFalse(w._manual_start_results)
        self.assertIsNone(w._manual_start_context)
        self.assertFalse(any((line.get_gid() or '').startswith('manual-preview-') for line in w.ax.lines))

    def test_failed_extraction_restores_the_last_complete_calculation_state(self):
        w = self.window
        w.extract_parameters()
        state_names = (
            'Winding_Para', 'Stator_Para', 'Inslot_Para', 'Layout_Para',
            'Line_Para', 'Fig_Para', 'TP_info', 'base_start_conductor_ids',
            'base_db_conductor_id', 'base_cond_info', 'db_conductor_id',
            'start_conductor_ids', 'phase_A_conductor_id', 'cond_info', 'results',
        )
        before = {name: getattr(w, name) for name in state_names}
        w.input_fields['num_layers'].setText('8')

        with patch('main_pyqt6.gw.get_winding_layout', side_effect=RuntimeError('injected failure')):
            with self.assertRaisesRegex(RuntimeError, 'injected failure'):
                w.extract_parameters()

        self.assertEqual({name: getattr(w, name) for name in state_names}, before)
        self.assertEqual(w.input_fields['num_layers'].text(), '8')

    def test_unchanged_inputs_reuse_calculation_and_changed_inputs_recompute(self):
        w = self.window
        original_layout = __import__('main_pyqt6').gw.get_winding_layout
        with patch('main_pyqt6.gw.get_winding_layout', wraps=original_layout) as generate:
            w.extract_parameters()
            first_results = w.results
            w.extract_parameters()
            self.assertEqual(generate.call_count, 1)
            self.assertIs(w.results, first_results)

            w.input_fields['num_layers'].setText('8')
            w.extract_parameters()
            self.assertEqual(generate.call_count, 2)
            self.assertEqual(w.Winding_Para.num_layers, 8)

    def test_successful_extraction_publishes_one_coherent_state_bundle(self):
        w = self.window
        w.extract_parameters()
        state = w.calculation_state
        self.assertIsInstance(state, CalculationState)
        self.assertIs(state.values['Winding_Para'], w.Winding_Para)
        self.assertIs(state.values['db_conductor_id'], w.db_conductor_id)
        self.assertIs(state.values['results'], w.results)
        self.assertEqual(state.signature, w._last_calculation_signature)
        self.assertGreaterEqual(state.generation, 1)
        with self.assertRaises(TypeError):
            state.values['results'] = None


class SlpFactorRouteTests(unittest.TestCase):
    """Check selected SLP constructions through the public layout entry point."""

    def _saved_phase_a(self, name):
        package = Path(__file__).parent / "pattern_rule_drafts" / name
        saved = json.loads(package.read_text(encoding="utf-8"))
        return [[(node["slot"] - 1, node["layer"] - 1)
                 for node in branch["path"]] for branch in saved["branches"]]

    def _assert_manual_route(self, factors, name, expected_emf_mismatch):
        from pattern_rule_workbench import _base_inputs

        expected = self._saved_phase_a(name)
        naa = factors[0] * factors[1] * factors[2]
        winding, tp, layout = _base_inputs("SLP", 2, 8, 4, naa, factors)
        starts, database = gw.get_winding_layout("SLP", tp, winding, layout)
        records = phase_map(48, 8, 4)
        phase_lookup = {(slot, layer): phase
                        for slot, layer, phase, _ in records}
        phase_a = [path for _, path in database
                   if phase_lookup[path[0][:2]] == 0]
        self.assertEqual([[tuple(node[:2]) for node in path] for path in phase_a],
                         expected)
        self.assertEqual(starts, [path[0] for _, path in database])
        report = validate_branches([path for _, path in database],
                                   records, 48, 8, naa)
        self.assertTrue(report["layout_retained"], report["errors"])
        self.assertEqual("parallel_emf_mismatch" in report["errors"],
                         expected_emf_mismatch)

    def test_manual_p2_only_paths_are_generated_and_retained(self):
        self._assert_manual_route(
            (1, 1, 2),
            "SLP_q-2_pp-4_L-4_Naa-2_Q-1_PP-1_P2-2_Ph-A_Side-weld_"
            "Shifts-0-0-0-0_20260923-171108-051958.json", True)

    def test_manual_full_q_p2_paths_are_generated_and_retained(self):
        for factors, name in (
                ((2, 1, 2),
                 "SLP_q-2_pp-4_L-4_Naa-4_Q-2_PP-1_P2-2_Ph-A_Side-weld_"
                 "Shifts-0-0-0-0_20260922-225156-377603.json"),
                ((2, 2, 2),
                 "SLP_q-2_pp-4_L-4_Naa-8_Q-2_PP-2_P2-2_Ph-A_Side-weld_"
                 "Shifts-0-0-0-0_20260922-223714-810649.json")):
            with self.subTest(factors=factors):
                self._assert_manual_route(factors, name, True)

    def test_manual_full_pp_p2_paths_are_generated(self):
        self._assert_manual_route(
            (1, 4, 2),
            "SLP_q-2_pp-4_L-4_Naa-8_Q-1_PP-4_P2-2_Ph-A_Side-weld_"
            "Shifts-0-0-0-0_20260922-221549-303114.json", False)

    def test_p2_factor_routes_extend_beyond_the_saved_geometry(self):
        from pattern_rule_workbench import _base_inputs

        for factors, rule_id in (
                ((1, 1, 2), 'slp_p2_from_reference'),
                ((4, 1, 2), 'slp_full_q_p2'),
                ((2, 4, 2), 'slp_pair_lane_p2')):
            with self.subTest(factors=factors):
                naa = factors[0] * factors[1] * factors[2]
                winding, tp, layout = _base_inputs(
                    'SLP', 4, 8, 6, naa, factors, phases=5)
                starts, database = gw.get_winding_layout(
                    'SLP', tp, winding, layout)
                self.assertEqual(database.layout_report['pattern_route']['rule_id'],
                                 rule_id)
                records = phase_map(160, 8, 6, phases=5)
                report = validate_branches(
                    [path for _, path in database], records, 160, 8, naa, 5)
                self.assertTrue(report['layout_retained'], report['errors'])
                signs = {(slot, layer): sign
                         for slot, layer, _phase, sign in records}
                self.assertTrue(all(signs[path[0][:2]] == 1
                                    and signs[path[-1][:2]] == -1
                                    for _, path in database))
                self.assertEqual(starts, [path[0] for _, path in database])

    def test_manual_pp_p2_paths_are_generated_and_retained(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs('SLP', 2, 8, 4, 4, (1, 2, 2))
        decision = gw.resolve_pattern_route(
            'SLP', winding, (1, 2, 2), tp, layout)
        self.assertEqual(decision.status, 'enabled', decision.reason)
        self._assert_manual_route(
            (1, 2, 2),
            'SLP_q-2_pp-4_L-4_Naa-4_Q-1_PP-2_P2-2_Ph-A_Side-weld_'
            'Shifts-0-0-0-0_20260923-175737-766554.json', False)

    def test_pp_p2_sector_route_covers_factor_domain(self):
        from pattern_rule_workbench import _base_inputs

        for phases in (3, 5, 7):
            for q in range(2, 7):
                for pole_pairs in (4, 6, 8, 10):
                    divider = pole_pairs // 2
                    factors = (1, divider, 2)
                    for layers in (2, 4, 6):
                        with self.subTest(m=phases, q=q, pp=pole_pairs,
                                          layers=layers):
                            winding, tp, layout = _base_inputs(
                                'SLP', q, 2 * pole_pairs, layers,
                                2 * divider, factors, phases)
                            decision = gw.resolve_pattern_route(
                                'SLP', winding, factors, tp, layout)
                            self.assertEqual(decision.status, 'enabled',
                                             decision.reason)
                            _, database = gw.get_winding_layout(
                                'SLP', tp, winding, layout)
                            occupied = [tuple(node[:2]) for _, path in database
                                        for node in path]
                            self.assertEqual(len(occupied), len(set(occupied)))
                            self.assertEqual(len(occupied),
                                             winding.num_slots * layers)
                            self.assertEqual({len(path) for _, path in database},
                                             {2 * q * layers})
                            self.assertTrue(database.layout_report['electrically_valid'])
                            self.assertEqual(
                                database.layout_report['pattern_identity']['status'],
                                'valid')

    def test_pp_p2_sector_preserves_ordered_lap_identity(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'SLP', 1, 8, 4, 4, (1, 2, 2))
        decision = gw.resolve_pattern_route(
            'SLP', winding, (1, 2, 2), tp, layout)
        self.assertEqual(decision.status, 'enabled')
        _, database = gw.get_winding_layout('SLP', tp, winding, layout)
        identity = database.layout_report['pattern_identity']
        self.assertEqual(identity['status'], 'valid', identity['reason'])
        self.assertIn('SLP', identity['ordered_identity']['compatible_patterns'])
        self.assertTrue(all(branch['status'] == 'valid'
                            for branch in identity['branch_identity']))


if __name__ == '__main__':
    unittest.main()
