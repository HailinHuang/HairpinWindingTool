"""Receipt guard tests use only temporary files and standard-library fakes."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from half_integer_q_source_receipt import SourceWindow, run_probe


def digest(value):
    return hashlib.sha256(value).hexdigest()


class SourceWindowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.probe = self.root / 'probe.py'
        self.marker = self.root / 'imported'
        self.probe.write_text(
            "from pathlib import Path\nfrom types import SimpleNamespace\n"
            f"Path({str(self.marker)!r}).write_text('yes')\n"
            "def _hash_paths(*args): return {'original': 'data'}\n"
            "def resolver(): return 12\n"
            "gw = SimpleNamespace(resolve_pattern_route=resolver, "
            "get_winding_layout=resolver)\n"
            "def main():\n"
            "    assert _hash_paths({}) == {'original': 'data'}\n"
            "    assert gw.resolve_pattern_route() == 12\n"
            "    assert gw.get_winding_layout() == 12\n",
            encoding='utf-8')
        self.source = self.root / 'source.py'
        self.source.write_text('original', encoding='utf-8')
        self.refresh()

    def refresh(self):
        paths = {'probe': str(self.probe), 'source': str(self.source)}
        hashes = {key: digest(Path(path).read_bytes()) for key, path in paths.items()}
        self.manifest = self.root / 'inputs.json'
        data = {'scope': 'test_scope', 'source_paths': paths,
                'source_hashes': hashes, 'probes': {'fake': str(self.probe)}}
        self.manifest.write_text(json.dumps(data), encoding='utf-8')
        self.receipt = self.root / 'release.json'
        receipt = dict(data, status='released', snapshot_id='test_snapshot',
                       released_by='test owner', source_count=len(paths),
                       source_closure_sha256=digest(json.dumps(
                           hashes, sort_keys=True, separators=(',', ':')).encode()))
        self.receipt.write_text(json.dumps(receipt), encoding='utf-8')
        self.manifest_hash = digest(self.manifest.read_bytes())
        self.receipt_hash = digest(self.receipt.read_bytes())

    def window(self, scope='test_scope', probe='fake'):
        return SourceWindow(self.manifest, self.manifest_hash, self.receipt,
                            self.receipt_hash, scope, probe)

    def test_legitimate_outputs_and_audit_data(self):
        window = self.window()
        output = self.root / 'binding.json'
        self.assertEqual(run_probe(window, [], output), 0)
        self.assertTrue(self.marker.exists())
        report = json.loads(output.read_text())
        self.assertEqual(report['status'], 'verified')
        self.assertEqual(report['guarded_calls'],
                         {'resolve_pattern_route': 1, 'get_winding_layout': 1})
        window.check()

    def test_reject_before_import(self):
        for scope, probe in [('wrong', 'fake'), ('test_scope', 'wrong')]:
            with self.subTest(scope=scope, probe=probe), self.assertRaises(RuntimeError):
                self.window(scope, probe)
        self.source.write_text('changed')
        with self.assertRaises(RuntimeError):
            run_probe(self.window(), [], self.root / 'binding.json')
        self.assertFalse(self.marker.exists())

    def test_missing_input(self):
        self.source.unlink()
        with self.assertRaises(RuntimeError):
            self.window()

    def test_missing_receipt(self):
        self.receipt.unlink()
        with self.assertRaises(RuntimeError):
            self.window()

    def test_pinned_manifest_and_receipt(self):
        for path in (self.manifest, self.receipt):
            with self.subTest(path=path):
                old = path.read_bytes()
                path.write_bytes(old + b' ')
                with self.assertRaises(RuntimeError):
                    self.window()
                path.write_bytes(old)

    def test_full_map_must_match(self):
        receipt = json.loads(self.receipt.read_text())
        receipt['source_paths'].pop('source')
        self.receipt.write_text(json.dumps(receipt))
        self.receipt_hash = digest(self.receipt.read_bytes())
        with self.assertRaises(RuntimeError):
            self.window()

    def test_mid_call_source_and_receipt_drift(self):
        for target in (self.source, self.receipt):
            with self.subTest(target=target):
                old = target.read_bytes()
                window = self.window()
                wrapped = window.guard(lambda: target.write_bytes(old + b' '))
                with self.assertRaises(RuntimeError):
                    wrapped()
                target.write_bytes(old)

    def test_pre_call_guard_stops_function(self):
        window = self.window()
        called = []
        function = window.guard(lambda: called.append(True))
        self.source.write_text('changed')
        with self.assertRaises(RuntimeError):
            function()
        self.assertEqual(called, [])

    def test_deferred_module_loader_installs_guards(self):
        text = self.probe.read_text().replace(
            'gw = SimpleNamespace(resolve_pattern_route=resolver, get_winding_layout=resolver)',
            'gw = None\ndef _load_project_modules():\n'
            '    global gw\n'
            '    gw = SimpleNamespace(resolve_pattern_route=resolver, get_winding_layout=resolver)')
        text = text.replace('def main():\n', 'def main():\n    _load_project_modules()\n')
        self.probe.write_text(text)
        self.refresh()
        self.assertEqual(run_probe(self.window(), [], self.root / 'binding.json'), 0)


if __name__ == '__main__':
    unittest.main()
