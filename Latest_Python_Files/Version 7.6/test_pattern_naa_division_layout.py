"""Focused checks for the Version 7.6 Pattern route status page."""

import unittest
from unittest.mock import patch
import json
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

import get_winding_pattern as gw
from pattern_rule_workbench import _base_inputs


ROOT = Path(__file__).resolve().parent


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get('id'):
            self.ids.add(values['id'])
        if tag == 'a' and values.get('href'):
            self.hrefs.append(values['href'])


class StatusProvenanceTests(unittest.TestCase):
    def setUp(self):
        import refresh_pattern_naa_division_layout as refresh

        self.refresh = refresh
        self.inventory = json.loads((ROOT / 'pattern_route_inventory.json').read_text(
            encoding='utf-8'))
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source_root = Path(self.temp.name)
        for name in refresh.SOURCE_FILES:
            (self.source_root / name).write_bytes((name + '\noriginal\n').encode())

    def test_source_hash_is_stable_across_git_line_endings(self):
        with patch.object(self.refresh, 'ROOT', self.source_root):
            expected = self.refresh.source_hash()
            for name in self.refresh.SOURCE_FILES:
                path = self.source_root / name
                path.write_bytes(path.read_bytes().replace(b'\n', b'\r\n'))
            self.assertEqual(self.refresh.source_hash(), expected)

    def test_source_hash_includes_phase_topology(self):
        with patch.object(self.refresh, 'ROOT', self.source_root):
            before = self.refresh.source_hash()
            (self.source_root / 'phase_topology.py').write_bytes(b'changed\n')
            self.assertNotEqual(self.refresh.source_hash(), before)

    def test_generated_navigation_stays_with_repository_resources(self):
        links = Links()
        links.feed(self.refresh.render_page(self.inventory))
        for href in links.hrefs:
            if href.startswith('#'):
                self.assertIn(href[1:], links.ids)
                continue
            path = (ROOT / unquote(href.split('#', 1)[0])).resolve()
            with self.subTest(href=href):
                self.assertTrue(path.is_relative_to(ROOT))
                self.assertTrue(path.is_file())
        document = self.refresh.render_status_document(self.inventory)
        self.assertNotIn('../Version 7.5/', document)

    def test_refresh_rejects_source_drift_before_writing_resources(self):
        refresh = self.refresh
        outputs = {name: self.source_root / name for name in ('data', 'page', 'status')}
        for path in outputs.values():
            path.write_text('previous resource', encoding='utf-8')

        def drift(*args, **kwargs):
            (self.source_root / 'phase_topology.py').write_bytes(b'changed\n')
            return self.inventory

        with (patch.object(refresh, 'ROOT', self.source_root),
              patch.object(refresh, 'DATA', outputs['data']),
              patch.object(refresh, 'PAGE', outputs['page']),
              patch.object(refresh, 'STATUS', outputs['status']),
              patch.object(refresh, 'scan_inventory', side_effect=drift),
              patch.object(refresh, 'feature_probes', return_value=[]),
              patch.object(sys, 'argv', ['refresh'])):
            self.inventory['source_sha256'] = refresh.source_hash()
            self.inventory['source_hashes'] = refresh.source_hashes()
            with self.assertRaisesRegex(ValueError, 'source changed'):
                refresh.main()
        for path in outputs.values():
            self.assertEqual(path.read_text(encoding='utf-8'), 'previous resource')

    def test_check_rejects_resources_from_a_different_generation(self):
        refresh = self.refresh
        outputs = {name: self.source_root / name for name in ('data', 'page', 'status')}
        with (patch.object(refresh, 'ROOT', self.source_root),
              patch.object(refresh, 'DATA', outputs['data']),
              patch.object(refresh, 'PAGE', outputs['page']),
              patch.object(refresh, 'STATUS', outputs['status']),
              patch.object(sys, 'argv', ['refresh', '--check'])):
            inventory = refresh.scan_inventory([], probe_generation=False)
            inventory['feature_probes'] = []
            outputs['data'].write_text(json.dumps(inventory), encoding='utf-8')
            page = refresh.render_page(inventory)
            status = refresh.render_status_document(inventory)
            for target, content in (('page', page), ('status', status)):
                with self.subTest(resource=target):
                    outputs['page'].write_text(page, encoding='utf-8')
                    outputs['status'].write_text(status, encoding='utf-8')
                    outputs[target].write_text(content.replace(
                        inventory['generated_at_utc'], 'another generation'),
                        encoding='utf-8')
                    with self.assertRaisesRegex(ValueError, 'content differs'):
                        refresh.main()


class PatternNaaDivisionLayoutTests(unittest.TestCase):
    def test_tlp_q_pp_p2_parent_slice_status_probes(self):
        from refresh_pattern_naa_division_layout import feature_probes

        tlp = next(item for item in feature_probes()
                   if item['pattern'] == 'TLP')['probes']
        for name in (
                'Q+PP+P2 parent slices: saved q=2 draft',
                'Q+PP+P2 parent slices: adjacent lanes q=4',
                'Q+PP+P2 parent slices: adjacent lanes q=6',
                'Q+PP+P2 parent slices: D=3 extension',
                'Q+PP+P2 parent slices: six-phase lift',
                'Q+PP+P2 parent slices: nine-phase lift'):
            with self.subTest(name=name):
                sample = tlp[name]
                self.assertEqual(sample['preflight']['admission'], 'supported')
                self.assertEqual(sample['preflight']['rule_id'],
                                 'tlp_q_pp_p2_parent_slices')
                self.assertIn(sample['production']['status'],
                              ('Validated', 'retained-not-strong'))
                self.assertTrue(sample['production']['layout_retained'])
                self.assertEqual(sample['production']['identity_status'], 'valid')

        source_failure = tlp['Q+PP+P2 parent slices: D=4 source boundary']
        self.assertEqual(source_failure['preflight']['admission'],
                         'unsupported-yet')
        self.assertNotIn('production', source_failure)
        local_layers = tlp['Q+PP+P2 parent slices: short local-layer array']
        self.assertEqual(local_layers['preflight']['admission'],
                         'unsupported-yet')
        self.assertEqual(local_layers['preflight']['rule_id'],
                         'tlp_q_pp_p2_local_layers_unsupported')
        self.assertNotIn('production', local_layers)
        for name in (
                'Q+PP+P2 parent slices: phase-shift boundary',
                'Q+PP+P2 parent slices: transposition boundary'):
            with self.subTest(name=name):
                # Current shift/manual-TP admission permits an attempt, not certification.
                self.assertEqual(tlp[name]['preflight']['status'], 'enabled')
                self.assertEqual(tlp[name]['preflight']['admission'], 'supported')
                self.assertEqual(tlp[name]['preflight']['rule_id'],
                                 'tlp_q_pp_p2_parent_slices')
                self.assertNotIn('production', tlp[name])

    def test_tlp_q_only_pair_probes_show_formula_and_matrix_delta(self):
        from refresh_pattern_naa_division_layout import (
            feature_probes, scan_geometries, scan_inventory)

        tlp = next(item for item in feature_probes()
                   if item['pattern'] == 'TLP')['probes']
        positive_names = (
            'Q-only adjacent P2 pair: matrix q=Q=2, L=2, m=3',
            'Q-only adjacent P2 pair: matrix q=Q=2, pp=4',
            'Q-only adjacent P2 pair: matrix q=Q=2, pp=2',
            'Q-only adjacent P2 pair: matrix native m=7',
            'Q-only adjacent P2 pair: matrix q=Q=4',
            'Q-only adjacent P2 pair: matrix native m=5',
            'Q-only adjacent P2 pair: full-Q q=8 range sample',
            'Q-only adjacent P2 pair: full-Q odd-pp sample',
            'Q-only adjacent P2 pair: four q lanes, odd pp',
            'Q-only adjacent P2 pair: two-layer q=4 boundary',
            'Q-only adjacent P2 pair: TSP interior-gcd contrast',
            'Q-only adjacent P2 pair: proper-Q q=4 boundary',
            'Q-only adjacent P2 pair: proper-Q q=6 boundary',
            'Q-only proper-Q cohort join: reviewed q=4 draft',
            'Q-only proper-Q cohort join: retained EMF asymmetry',
        )
        for name in positive_names:
            with self.subTest(name=name):
                sample = tlp[name]
                self.assertEqual(sample['preflight']['admission'], 'supported')
                self.assertEqual(sample['preflight']['rule_id'],
                                 'tlp_q_only_pair_join')
                self.assertIn(sample['production']['status'],
                              ('Validated', 'retained-not-strong'))
                self.assertTrue(sample['production']['layout_retained'])
                self.assertEqual(sample['production']['identity_status'], 'valid')

        expected_boundaries = {
            'Q-only adjacent P2 pair: odd-Q boundary': 'rejected',
            'Q-only adjacent P2 pair: retained odd-Q rejection': 'rejected',
            'Q-only adjacent P2 pair: pp=1 boundary': 'unsupported-yet',
            'Q-only adjacent P2 pair: phase-array boundary': 'unsupported-yet',
        }
        for name, admission in expected_boundaries.items():
            with self.subTest(name=name):
                sample = tlp[name]
                self.assertEqual(sample['preflight']['admission'], admission)
                self.assertNotIn('production', sample)

        for name in (
                'Q-only adjacent P2 pair: transposition boundary',
                'Q-only adjacent P2 pair: phase-shift boundary'):
            with self.subTest(name=name):
                self.assertEqual(tlp[name]['preflight']['status'], 'enabled')
                self.assertEqual(tlp[name]['preflight']['admission'], 'supported')
                self.assertEqual(tlp[name]['preflight']['rule_id'],
                                 'tlp_q_only_pair_join')
                self.assertNotIn('production', tlp[name])
        wrong_inlet = tlp['Q-only adjacent P2 pair: wrong-inlet boundary']
        self.assertEqual(wrong_inlet['preflight']['status'], 'disabled')
        self.assertNotIn('production', wrong_inlet)

        inventory = scan_inventory(
            scan_geometries(), probe_generation=False)
        cell = next(item for item in inventory['cells']
                    if item['pattern'] == 'TLP'
                    and item['formula'] == 'q_only')
        self.assertEqual(cell['counts'], {'supported': 8, 'rejected': 1})
        asymmetric = tlp['Q-only proper-Q cohort join: retained EMF asymmetry']
        self.assertEqual(asymmetric['production']['status'], 'retained-not-strong')

    def test_tlp_full_q_even_divider_probes_show_formula_and_boundaries(self):
        from refresh_pattern_naa_division_layout import feature_probes

        tlp = next(item for item in feature_probes()
                   if item['pattern'] == 'TLP')['probes']
        positive_names = (
            'PP-only even-divider Q=1 baseline',
            'PP-only even-divider full-Q direct q=2',
            'PP-only even-divider full-Q direct q=3',
            'PP-only even-divider full-Q direct q=4',
            'PP-only even-divider full-Q direct q=6',
            'PP-only even-divider full-Q array m=6',
            'PP-only even-divider full-Q array m=9',
            'PP-only even-divider full-Q array m=12',
        )
        for name in positive_names:
            with self.subTest(name=name):
                sample = tlp[name]
                self.assertEqual(sample['preflight']['admission'], 'supported')
                self.assertIn(sample['production']['status'],
                              ('Validated', 'retained-not-strong'))
                self.assertTrue(sample['production']['layout_retained'])
                self.assertEqual(sample['production']['identity_status'], 'valid')

        for name in (
                'PP-only even-divider proper-Q boundary',
                'PP-only even-divider odd local-D boundary',
                'PP-only even-divider short local-layer boundary'):
            with self.subTest(name=name):
                sample = tlp[name]
                self.assertEqual(sample['preflight']['admission'],
                                 'unsupported-yet')
                self.assertNotIn('production', sample)

    def test_every_cell_reports_the_public_resolver_decision(self):
        from refresh_pattern_naa_division_layout import scan_inventory

        inventory = scan_inventory([(2, 2, 4, 3)], probe_generation=False)
        self.assertEqual(len(inventory['cells']), 80)
        self.assertEqual(sum(sum(cell['counts'].values())
                             for cell in inventory['cells']), 80)
        for cell in inventory['cells']:
            self.assertEqual(sum(cell['counts'].values()), 1)
            sample = next(iter(cell['examples'].values()))
            winding, tp, layout = _base_inputs(
                sample['pattern'], sample['q'], 2 * sample['pp'],
                sample['layers'], sample['naa'],
                tuple(sample['dividers']), sample['phases'])
            decision = gw.resolve_pattern_route(
                sample['pattern'], winding, winding.branch_dividers,
                tp, layout)
            self.assertEqual(sample['preflight'], {
                'status': decision.status,
                'admission': decision.admission,
                'rule_id': decision.rule_id,
                'reason': decision.reason,
                'is_default': decision.is_default,
                'required_inlet': decision.required_inlet,
                'pin_profile': list(decision.pin_profile),
            })
            self.assertNotIn('production', sample)

    def test_public_generation_keeps_retained_emf_asymmetry_separate(self):
        from refresh_pattern_naa_division_layout import evaluate_case

        case = evaluate_case('SSP', 2, 4, 4, 3, (1, 1, 2),
                             probe_generation=True)
        self.assertEqual(case['preflight']['status'], 'enabled')
        self.assertEqual(case['production']['status'],
                         'retained-not-strong')
        self.assertTrue(case['production']['layout_retained'])
        self.assertIn('parallel_emf_mismatch',
                      case['production']['errors'])

    def test_disabled_route_is_not_promoted_by_factor_arithmetic(self):
        from refresh_pattern_naa_division_layout import evaluate_case

        case = evaluate_case('BWP', 2, 2, 4, 3, (1, 1, 2),
                             probe_generation=True)
        self.assertEqual(case['preflight']['status'], 'disabled')
        self.assertEqual(case['preflight']['admission'], 'rejected')
        self.assertNotIn('production', case)

    def test_zpp_indexed_translation_feature_probes_show_formula_boundary(self):
        from refresh_pattern_naa_division_layout import feature_probes

        zpp = next(item for item in feature_probes()
                   if item['pattern'] == 'ZPP')['probes']
        positive = zpp['PP-only indexed translation: coprime sample']
        expanded = zpp[
            'PP-only indexed translation: expanded direct boundary (a=2)']
        composite = zpp[
            'PP-only indexed translation: composite direct stride (a=5)']

        self.assertEqual(positive['preflight']['admission'], 'supported')
        self.assertEqual(positive['preflight']['rule_id'],
                         'zpp_pp_only_indexed_translation')
        self.assertEqual(positive['production']['status'], 'Validated')
        for sample in (expanded, composite):
            with self.subTest(sample=sample['q'], pp=sample['pp']):
                self.assertEqual(sample['preflight']['admission'], 'supported')
                self.assertEqual(sample['preflight']['rule_id'],
                                 'zpp_pp_only_indexed_translation')
                self.assertEqual(sample['production']['status'], 'Validated')
                self.assertEqual(sample['production']['identity_status'],
                                 'valid')

        arrayed = zpp[
            'PP-only indexed translation: legacy arrayed local-q sample '
            '(a=1; 12 global two-boundary edges)']
        self.assertEqual(arrayed['preflight']['admission'], 'supported')
        self.assertEqual(arrayed['preflight']['rule_id'],
                         'zpp_pp_only_indexed_translation')
        self.assertEqual(arrayed['production']['status'],
                         'retained-not-strong')
        self.assertTrue(arrayed['production']['layout_retained'])
        self.assertEqual(arrayed['production']['identity_status'], 'valid')
        self.assertIn('multi_phase_emf_mismatch',
                      arrayed['production']['errors'])

        array_stride = zpp[
            'PP-only indexed translation: array stride >1 boundary']
        self.assertEqual(array_stride['preflight']['status'], 'disabled')
        self.assertEqual(array_stride['preflight']['admission'],
                         'unsupported-yet')
        self.assertEqual(array_stride['preflight']['rule_id'],
                         'zpp_array_stride_unvalidated')
        self.assertNotIn('production', array_stride)

    def test_zpp_odd_integer_q_p2_probes_show_rejection_and_controls(self):
        inventory = json.loads((ROOT / 'pattern_route_inventory.json').read_text(
            encoding='utf-8'))
        probes = next(item for item in inventory['feature_probes']
                      if item['pattern'] == 'ZPP')['probes']
        for q_divider in (1, 3):
            for pp_divider in (1, 2):
                sample = probes[
                    f'P2=2 odd integer q: Q={q_divider}, D={pp_divider}']
                with self.subTest(Q=q_divider, D=pp_divider):
                    self.assertEqual(sample['preflight']['status'], 'disabled')
                    self.assertEqual(sample['preflight']['admission'], 'rejected')
                    self.assertEqual(sample['preflight']['rule_id'],
                                     'zpp_factor_rejected')
                    expected = ('q and p2 share same route'
                                if q_divider > 1 and pp_divider == 1
                                else 'odd positive integer effective q')
                    self.assertIn(expected, sample['preflight']['reason'])

        shared = probes['Q+P2 shared-route exclusion (even q)']['preflight']
        self.assertEqual(shared['admission'], 'rejected')
        self.assertEqual(shared['reason'], 'q and p2 share same route')

        even_q = probes['P2=2 even-q control']['preflight']
        self.assertNotEqual(even_q['rule_id'], 'zpp_factor_rejected')
        fractional = probes['P2=2 fractional-q control']['preflight']
        self.assertNotEqual(fractional['rule_id'], 'zpp_factor_rejected')
        arrayed = probes['P2=2 phase-set local odd-q control']['preflight']
        self.assertEqual(arrayed['rule_id'], 'phase_set_route_mismatch')
        self.assertIn('odd positive integer effective q', arrayed['reason'])

    @patch('refresh_pattern_naa_division_layout.PATTERNS', ('TSP',))
    def test_tsp_identity_feature_probes_show_new_and_preserved_boundaries(self):
        from refresh_pattern_naa_division_layout import feature_probes

        tsp = next(item for item in feature_probes()
                   if item['pattern'] == 'TSP')['probes']
        positive = tsp['PP-only full-q identity transfer sample']
        fallback = tsp['PP-only D=2 complete-pass closure']

        self.assertEqual(positive['preflight']['admission'], 'supported')
        self.assertEqual(positive['preflight']['rule_id'],
                         'tsp_pp_only_q_p2_identity')
        self.assertEqual(positive['production']['status'],
                         'retained-not-strong')
        self.assertTrue(positive['production']['layout_retained'])
        self.assertEqual(fallback['preflight']['admission'], 'supported')
        self.assertEqual(fallback['preflight']['rule_id'], 'tsp_spiral_pass_partition')
        self.assertEqual(fallback['production']['identity_status'], 'valid')

    @patch('refresh_pattern_naa_division_layout.PATTERNS', ('TSP',))
    def test_tsp_pp_p2_feature_probes_show_formula_and_residue_boundaries(self):
        from refresh_pattern_naa_division_layout import feature_probes

        tsp = next(item for item in feature_probes()
                   if item['pattern'] == 'TSP')['probes']
        positives = (
            tsp['PP+P2 fixed-lane saved sketch sample'],
            tsp['PP+P2 fixed-lane repeated PP sample'],
            tsp['PP+P2 fixed-lane phase-set array sample (m=6)'],
            tsp['PP+P2 fixed-lane phase-set array sample (m=9)'],
        )
        for sample in positives:
            with self.subTest(q=sample['q'], pp=sample['pp'],
                              phases=sample['phases']):
                self.assertEqual(sample['preflight']['admission'], 'supported')
                self.assertEqual(sample['preflight']['rule_id'],
                                 'tsp_pp_p2_sector')
                self.assertEqual(sample['production']['status'],
                                 'retained-not-strong')
                self.assertTrue(sample['production']['layout_retained'])
                self.assertEqual(sample['production']['identity_status'],
                                 'valid')

        for name in (
                'PP+P2 fixed-lane q-lane residue collision',
                'PP+P2 fixed-lane local-q array boundary'):
            with self.subTest(name=name):
                sample = tsp[name]
                self.assertEqual(sample['preflight']['admission'],
                                 'supported')
                self.assertEqual(sample['preflight']['rule_id'], 'tsp_spiral_pass_partition')
                self.assertEqual(sample['production']['identity_status'], 'valid')

        short = tsp['PP+P2 fixed-lane L=2 collision']
        self.assertEqual(short['preflight']['admission'], 'rejected')
        self.assertIn('4 conductors per branch', short['preflight']['reason'])
        self.assertNotIn('production', short)

    @patch('refresh_pattern_naa_division_layout.PATTERNS', ('TSP',))
    def test_tsp_q_only_pair_feature_probes_show_formula_and_matrix_delta(self):
        from refresh_pattern_naa_division_layout import (
            feature_probes, scan_geometries, scan_inventory)

        tsp = next(item for item in feature_probes()
                   if item['pattern'] == 'TSP')['probes']
        positive_names = (
            'Q-only adjacent P2 pair: full-Q finite m=3',
            'Q-only adjacent P2 pair: proper-Q m=3',
            'Q-only adjacent P2 pair: three proper-Q lane sweeps',
            'Q-only adjacent P2 pair: native m=5',
            'Q-only adjacent P2 pair: finite m=7',
            'Q-only adjacent P2 pair: six-phase array',
            'Q-only adjacent P2 pair: nine-phase array',
            'Q-only adjacent P2 pair: twelve-phase array',
        )
        for name in positive_names:
            with self.subTest(name=name):
                sample = tsp[name]
                self.assertEqual(sample['preflight']['admission'], 'supported')
                self.assertEqual(sample['preflight']['rule_id'],
                                 'tsp_q_only_pair_join')
                self.assertIn(sample['production']['status'],
                              ('Validated', 'retained-not-strong'))
                self.assertTrue(sample['production']['layout_retained'])
                self.assertEqual(sample['production']['identity_status'], 'valid')

        expected_boundaries = {
            'Q-only adjacent P2 pair: interior-gcd boundary': 'supported',
            'Q-only adjacent P2 pair: odd-Q boundary': 'rejected',
            'Q-only adjacent P2 pair: pp=1 boundary': 'supported',
            'Q-only adjacent P2 pair: two-layer boundary': 'supported',
            'Q-only adjacent P2 pair: odd local-layer array boundary': 'rejected',
        }
        for name, admission in expected_boundaries.items():
            with self.subTest(name=name):
                sample = tsp[name]
                self.assertEqual(sample['preflight']['admission'], admission)
                if admission == 'supported':
                    self.assertEqual(sample['preflight']['rule_id'], 'tsp_spiral_pass_partition')
                    self.assertEqual(sample['production']['identity_status'], 'valid')
                else:
                    self.assertNotIn('production', sample)

        inventory = scan_inventory(
            scan_geometries(), probe_generation=False)
        cell = next(item for item in inventory['cells']
                    if item['pattern'] == 'TSP'
                    and item['formula'] == 'q_only')
        self.assertEqual(cell['counts'], {
            'supported': 8, 'rejected': 1})

    @patch('refresh_pattern_naa_division_layout.PATTERNS', ('TSP',))
    def test_tsp_manual_closure_probes_generate_and_keep_scope_boundaries(self):
        from refresh_pattern_naa_division_layout import feature_probes
        probes = feature_probes()[0]['probes']
        closed = [sample for name, sample in probes.items()
                  if name.startswith('Complete-pass closure:') and 'boundary' not in name]
        self.assertEqual(len(closed), 10)
        for sample in closed:
            self.assertEqual(sample['preflight']['admission'], 'supported')
            self.assertEqual(sample['preflight']['rule_id'], 'tsp_spiral_pass_partition')
            self.assertEqual(sample['production']['identity_status'], 'valid')
            self.assertTrue(sample['production']['layout_retained'])
        short = probes['Complete-pass closure: one-pass boundary']
        self.assertEqual(short['preflight']['admission'], 'rejected')
        self.assertIn('4 conductors per branch', short['preflight']['reason'])
        self.assertNotIn('production', short)
        fractional = probes['Complete-pass closure: fractional global-q array boundary']
        self.assertEqual(fractional['preflight']['admission'], 'unsupported-yet')
        self.assertNotIn('production', fractional)

    def test_slp_proper_q_pp_p2_probes_show_formula_and_boundaries(self):
        from refresh_pattern_naa_division_layout import feature_probes

        slp = next(item for item in feature_probes()
                   if item['pattern'] == 'SLP')['probes']
        positive_names = (
            'Proper-Q+PP+P2 parent regroup: scan delta sample',
            'Proper-Q+PP+P2 parent regroup: odd q-lane group',
            'Proper-Q+PP+P2 parent regroup: Q=3 scan delta',
            'Proper-Q+PP+P2 parent regroup: six-phase array',
            'Proper-Q+PP+P2 parent regroup: nine-phase array',
        )
        for name in positive_names:
            with self.subTest(name=name):
                sample = slp[name]
                self.assertEqual(sample['preflight']['admission'], 'supported')
                self.assertEqual(sample['preflight']['rule_id'],
                                 'slp_q_pp_p2_parent_cut')
                self.assertIn(sample['production']['status'],
                              ('Validated', 'retained-not-strong'))
                self.assertTrue(sample['production']['layout_retained'])
                self.assertEqual(sample['production']['identity_status'], 'valid')

        odd_sector = slp['Proper-Q+PP+P2 odd sector boundary']
        self.assertEqual(odd_sector['preflight']['admission'],
                         'unsupported-yet')
        self.assertNotIn('production', odd_sector)
        nondivisor = slp['Proper-Q+PP+P2 nondivisor D boundary']
        self.assertEqual(nondivisor['preflight']['admission'],
                         'unsupported-yet')
        self.assertNotIn('production', nondivisor)

    def test_cp_q1_parent_slice_probes_show_source_and_array_boundaries(self):
        from refresh_pattern_naa_division_layout import feature_probes

        cp = next(item for item in feature_probes()
                  if item['pattern'] == 'CP')['probes']
        direct = cp['Q=1 PP-only direct parent-slice sample']
        self.assertEqual(direct['preflight']['admission'], 'supported')
        self.assertEqual(direct['preflight']['rule_id'],
                         'cp_q_pp_full_parent_slices')
        self.assertEqual(direct['production']['status'], 'Validated')
        self.assertEqual(direct['production']['identity_status'], 'valid')

        arrayed = cp['Q=1 PP-only arrayed local-q control']
        self.assertEqual(arrayed['preflight']['admission'], 'supported')
        self.assertEqual(arrayed['preflight']['rule_id'],
                         'cp_q_pp_full_parent_slices')
        self.assertEqual(arrayed['production']['status'],
                         'retained-not-strong')
        self.assertTrue(arrayed['production']['layout_retained'])
        self.assertEqual(arrayed['production']['identity_status'], 'valid')
        self.assertIn('multi_phase_emf_mismatch',
                      arrayed['production']['errors'])

        source_failure = cp['Q=1 PP-only L=8 direct source failure']
        self.assertEqual(source_failure['preflight']['admission'], 'rejected')
        self.assertEqual(source_failure['preflight']['rule_id'],
                         'cp_q_pp_full_parent_slices')
        self.assertIn('duplicate', source_failure['preflight']['reason'])
        self.assertIn('misses', source_failure['preflight']['reason'])
        self.assertNotIn('production', source_failure)

    def test_cp_array_layer_probes_show_global_and_local_boundaries(self):
        from refresh_pattern_naa_division_layout import feature_probes

        cp = next(item for item in feature_probes()
                  if item['pattern'] == 'CP')['probes']
        expected_routes = {
            'Array global Nlayer=12, local six-layer Q+PP slice':
                'cp_q_pp_full_parent_slices',
            'Array global Nlayer=12, local six-layer PP sector':
                'cp_pp_sector_slices',
            'Array global Nlayer=12, local six-layer Q+PP D=6':
                'cp_q_pp_full_parent_slices',
        }
        for name, route in expected_routes.items():
            with self.subTest(name=name):
                sample = cp[name]
                self.assertEqual(sample['preflight']['status'], 'enabled')
                self.assertEqual(sample['production']['status'],
                                 'retained-not-strong')
                self.assertTrue(sample['production']['layout_retained'])
                self.assertEqual(sample['production']['route_rule_id'], route)
                self.assertEqual(sample['production']['identity_status'],
                                 'valid')

        global_boundary = cp['Array global Nlayer=10 rejection']
        self.assertEqual(global_boundary['preflight']['status'], 'disabled')
        self.assertIn('divisible by 4', global_boundary['preflight']['reason'])
        local_boundary = cp['Array odd local-layer rejection']
        self.assertEqual(local_boundary['preflight']['status'], 'disabled')
        self.assertIn('positive even local layer count',
                      local_boundary['preflight']['reason'])

    def test_cp_q_pp_p2_parent_slice_probes_show_formula_and_domain(self):
        from refresh_pattern_naa_division_layout import feature_probes

        cp = next(item for item in feature_probes()
                  if item['pattern'] == 'CP')['probes']
        positive_names = (
            'Q+PP+P2 parent slices: proper Q, D=2',
            'Q+PP+P2 parent slices: odd D=3',
            'Q+PP+P2 parent slices: full D=4',
            'Q+PP+P2 parent slices: six-phase L=12',
        )
        for name in positive_names:
            with self.subTest(name=name):
                sample = cp[name]
                self.assertEqual(sample['preflight']['admission'], 'supported')
                self.assertEqual(sample['preflight']['rule_id'],
                                 'cp_q_pp_p2_parent_slices')
                self.assertIn(sample['production']['status'],
                              ('Validated', 'retained-not-strong'))
                self.assertTrue(sample['production']['layout_retained'])
                self.assertEqual(sample['production']['identity_status'],
                                 'valid')

        default = cp['Q+PP+P2 default remains Default']
        self.assertTrue(default['preflight']['is_default'])
        self.assertEqual(default['preflight']['rule_id'], 'cp_default')
        self.assertIn(default['production']['status'],
                      ('Default', 'retained-not-strong'))

        for name in (
                'Q+PP+P2 nondivisor Q boundary',
                'Q+PP+P2 nondivisor D boundary'):
            with self.subTest(name=name):
                sample = cp[name]
                self.assertEqual(sample['preflight']['admission'],
                                 'unsupported-yet')
                self.assertNotIn('production', sample)

    def test_saved_page_covers_patterns_and_links_to_archived_evidence(self):
        page = (ROOT / 'pattern_naa_division_layout.html').read_text(
            encoding='utf-8')
        links = Links()
        links.feed(page)
        self.assertEqual(len([anchor for anchor in links.ids
                              if anchor.startswith('pattern-')]), 10)
        self.assertIn('V7.5 historical research', page)
        self.assertIn('preflight enabled', page)
        self.assertIn('retained-not-strong', page)
        self.assertIn('Candidate', page)
        self.assertIn('Validated', page)
        self.assertIn(
            'PP-only indexed translation: expanded direct boundary (a=2)',
            page)
        self.assertIn(
            'PP-only indexed translation: array stride &gt;1 boundary', page)
        self.assertIn('P2=2 odd integer q: Q=3, D=2', page)
        self.assertIn('odd positive integer effective q', page)
        self.assertIn('12 global two-boundary edges', page)
        self.assertIn('Q=1 PP-only direct parent-slice sample', page)
        self.assertIn('PP-only even-divider full-Q array m=12', page)
        self.assertIn('Q-only adjacent P2 pair: full-Q finite m=3', page)
        self.assertIn('Q-only adjacent P2 pair: twelve-phase array', page)
        self.assertIn('80 Pattern', page)
        self.assertIn('href="pattern_guide.html"', page)
        self.assertIn('href="pattern_naa_division_layout.html"',
                      (ROOT / 'pattern_guide.html').read_text(encoding='utf-8'))
        referenced_pages = {}
        for href in links.hrefs:
            target, _, fragment = href.partition('#')
            if not target:
                self.assertIn(fragment, links.ids, href)
            else:
                path = (ROOT / unquote(target))
                self.assertTrue(path.is_file(), href)
                if fragment and path.suffix == '.html':
                    if path not in referenced_pages:
                        referenced = Links()
                        referenced.feed(path.read_text(encoding='utf-8'))
                        referenced_pages[path] = referenced.ids
                    self.assertIn(fragment, referenced_pages[path], href)


if __name__ == '__main__':
    unittest.main()
