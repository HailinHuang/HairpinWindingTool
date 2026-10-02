"""Public-entry regressions for the confirmed ordered identity policy."""

import unittest
from copy import deepcopy
from fractions import Fraction
from types import SimpleNamespace

import get_winding_pattern as gw
from layout_analysis import analyze_pattern_identity
from pattern_rule_workbench import _base_inputs


class OrderedIdentityIntegrationTests(unittest.TestCase):
    def test_compatible_signatures_preserve_full_ordered_check_evidence(self):
        winding, tp, layout = _base_inputs('SSP', 2, 4, 4, 2)
        _, database = gw.get_winding_layout('SSP', tp, winding, layout)
        report = database.layout_report['pattern_identity']
        self.assertEqual(report['status'], 'valid', report['reason'])
        self.assertTrue(report['matching_profiles'])
        self.assertEqual(report['identity_confidence'], 'full')

    def test_two_layer_overlap_is_not_incomplete_evidence(self):
        winding = SimpleNamespace(q=1, num_phases=3, num_slots=6,
                                  num_layers=2, ab=1)
        layout = SimpleNamespace(inlet_from_weld_side=1,
                                 phase_shift_list=[0, 0])
        report = analyze_pattern_identity(
            'TLP', [[1, [(0, 0), (3, 1)]]], winding, layout)
        self.assertEqual(report['status'], 'valid', report['reason'])
        self.assertTrue(report['degeneracy'])
        self.assertEqual(report['identity_confidence'], 'full')
        short_pitch = analyze_pattern_identity(
            'TLP', [[1, [(0, 0), (1, 1)]]], winding, layout)
        self.assertEqual(short_pitch['status'], 'valid')
        self.assertEqual(short_pitch['identity_confidence'], 'full')

    def test_public_entry_reports_ordered_identity_for_all_ten_patterns(self):
        for pattern in ('BWP', 'UWP', 'SSP', 'TSP', 'SLP', 'TLP',
                        'ZLP', 'ZPP', 'CP', 'LPP'):
            with self.subTest(pattern=pattern):
                poles = 8 if pattern == 'ZLP' else 4
                winding, tp, layout = _base_inputs(pattern, 2, poles, 4, 2)
                winding.branch_dividers = tuple(gw.classify_branch_mode(
                    2, 2, poles, pattern)[1:4])
                if pattern == 'ZLP':
                    winding.branch_dividers = (1, 1, 2)
                _, database = gw.get_winding_layout(pattern, tp, winding, layout)
                report = database.layout_report['pattern_identity']
                self.assertEqual(report['status'], 'valid', report['reason'])
                ordered = report['ordered_identity']
                self.assertEqual(ordered['qualification'], 'bounded-integer-even-layer')
                self.assertEqual(len(report['branch_identity']), len(database))

    def test_tsp_short_branch_without_cross_layer_pin_is_accepted(self):
        winding = SimpleNamespace(q=Fraction(2), num_phases=3,
                                  num_slots=24, num_layers=4, ab=1)
        layout = SimpleNamespace(inlet_from_weld_side=0,
                                 phase_shift_list=[0] * 4)
        database = [[1, [(0, 0), (6, 1), (12, 2), (18, 3)]]]
        report = analyze_pattern_identity('TSP', database, winding, layout)
        self.assertEqual(report['status'], 'valid', report['reason'])
        self.assertNotIn('CLWP', report['missing_pin_types'])
        self.assertEqual(report['ordered_identity']['qualification'],
                         'bounded-integer-even-layer')
        bad = deepcopy(database)
        bad[0][1][2] = (12, 0)
        report = analyze_pattern_identity('TSP', bad, winding, layout)
        self.assertEqual(report['status'], 'candidate', report['reason'])

    def test_uwp_explicit_series_weld_remains_a_valid_public_route(self):
        winding, tp, layout = _base_inputs('UWP', 4, 4, 4, 2, (2, 1, 1))
        _, database = gw.get_winding_layout('UWP', tp, winding, layout)
        report = database.layout_report['pattern_identity']
        self.assertEqual(report['status'], 'valid', report['reason'])
        self.assertTrue(database.series_connections)
        broken = deepcopy(database)
        broken.series_connections = []
        report = analyze_pattern_identity('UWP', broken, winding, layout)
        self.assertEqual(report['status'], 'candidate')

    def test_html_policy_refresh_is_idempotent_and_has_all_ten_contracts(self):
        from refresh_pattern_naa_division_layout import refresh_identity_policy
        from pattern_identity import PATTERN_CONTRACTS

        page = ('<a href="#connection-units">Units</a>'
                '<section class="panel" id="connection-units"></section>')
        result = refresh_identity_policy(page)
        self.assertEqual(refresh_identity_policy(result), result)
        self.assertEqual(result.count('id="ordered-identity"'), 1)
        for pattern in PATTERN_CONTRACTS:
            self.assertIn(f'<th scope="row">{pattern}</th>', result)
        self.assertIn('Short branches allowed', result)
        self.assertIn('Degenerate overlap allowed', result)


if __name__ == '__main__':
    unittest.main()
