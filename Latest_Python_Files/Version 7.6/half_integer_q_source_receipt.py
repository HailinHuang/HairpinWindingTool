"""Run an audited probe under an externally pinned, immutable source receipt.

Each CLI invocation runs one probe in a fresh interpreter. The manifest is an
independently reviewed input allowlist; generated reports are not source inputs.
This launcher does not change route admission or the probe's engineering gates.
"""
from __future__ import annotations

import argparse
from functools import wraps
from hashlib import sha256
import json
from pathlib import Path
import runpy
import sys


def _digest(data):
    return sha256(data).hexdigest()


def _read(path):
    try:
        return Path(path).read_bytes()
    except OSError as error:
        raise RuntimeError(f'Missing or unreadable input: {path}') from error


class SourceWindow:
    def __init__(self, manifest, manifest_sha, receipt, receipt_sha, scope, probe):
        self.manifest_path = Path(manifest).resolve()
        self.receipt_path = Path(receipt).resolve()
        self.manifest_sha = manifest_sha
        self.receipt_sha = receipt_sha
        manifest_bytes = _read(self.manifest_path)
        receipt_bytes = _read(self.receipt_path)
        if (_digest(manifest_bytes) != manifest_sha
                or _digest(receipt_bytes) != receipt_sha):
            raise RuntimeError('Pinned manifest or receipt hash mismatch.')
        self.manifest = json.loads(manifest_bytes)
        self.receipt = json.loads(receipt_bytes)
        if (self.manifest.get('scope') != scope
                or self.receipt.get('scope') != scope
                or self.receipt.get('status') != 'released'
                or not self.receipt.get('snapshot_id')
                or not self.receipt.get('released_by')):
            raise RuntimeError('Receipt release identity or exact scope mismatch.')
        if probe not in self.manifest.get('probes', {}):
            raise RuntimeError('Probe is outside the reviewed allowlist.')
        self.probe = Path(self.manifest['probes'][probe]).resolve()
        self.paths = self.manifest.get('source_paths', {})
        self.hashes = self.manifest.get('source_hashes', {})
        closure = _digest(json.dumps(self.hashes, sort_keys=True,
                                     separators=(',', ':')).encode())
        if (not self.paths or set(self.paths) != set(self.hashes)
                or self.receipt.get('source_paths') != self.paths
                or self.receipt.get('source_hashes') != self.hashes
                or self.receipt.get('source_count') != len(self.paths)
                or self.receipt.get('source_closure_sha256') != closure
                or self.probe not in {Path(p).resolve() for p in self.paths.values()}):
            raise RuntimeError('Complete source path/hash map or closure mismatch.')
        self.check_count = 0
        self.guarded_calls = {'resolve_pattern_route': 0, 'get_winding_layout': 0}
        self.check()

    def check(self):
        if (_digest(_read(self.manifest_path)) != self.manifest_sha
                or _digest(_read(self.receipt_path)) != self.receipt_sha):
            raise RuntimeError('Manifest or receipt changed during the source window.')
        for name, path in self.paths.items():
            if _digest(_read(path)) != self.hashes[name]:
                raise RuntimeError(f'Frozen source changed: {name} ({path})')
        self.check_count += 1

    def guard(self, function, call_name=None):
        @wraps(function)
        def guarded(*args, **kwargs):
            self.check()
            if call_name:
                self.guarded_calls[call_name] += 1
            try:
                return function(*args, **kwargs)
            finally:
                self.check()
        return guarded


def run_probe(window, arguments, output):
    output = Path(output).resolve()
    frozen = {Path(p).resolve() for p in window.paths.values()}
    frozen.update((window.manifest_path, window.receipt_path))
    if output in frozen or output.exists():
        raise RuntimeError('Binding output must be new and outside frozen inputs.')
    original_argv, original_path = sys.argv, sys.path[:]
    restores = []
    installed = set()

    def install_calls(namespace):
        module = namespace.get('gw')
        if module is None or id(module) in installed:
            return
        for name in window.guarded_calls:
            function = getattr(module, name)
            restores.append((module, name, function))
            setattr(module, name, window.guard(function, name))
        installed.add(id(module))

    status, exit_code, error_text = 'failed', 1, None
    try:
        window.check()
        sys.path.insert(0, str(window.probe.parent))
        namespace = runpy.run_path(str(window.probe), run_name='receipt_bound_probe')
        window.check()
        main = namespace['main']
        globals_ = main.__globals__
        globals_['_hash_paths'] = window.guard(globals_['_hash_paths'])
        install_calls(globals_)
        loader = globals_.get('_load_project_modules')
        if loader:
            @wraps(loader)
            def guarded_loader(*args, **kwargs):
                value = window.guard(loader)(*args, **kwargs)
                install_calls(globals_)
                return value
            globals_['_load_project_modules'] = guarded_loader
        sys.argv = [str(window.probe), *arguments]
        try:
            main()
            exit_code = 0
        except SystemExit as error:
            exit_code = error.code if isinstance(error.code, int) else (0 if error.code is None else 1)
        window.check()
        status = 'verified' if exit_code == 0 else 'probe_failed'
    except BaseException as error:
        error_text = f'{type(error).__name__}: {error}'
        raise
    finally:
        for module, name, function in reversed(restores):
            setattr(module, name, function)
        sys.argv, sys.path[:] = original_argv, original_path
        report = {
            'status': status, 'probe_exit_code': exit_code, 'error': error_text,
            'probe': str(window.probe), 'arguments': arguments,
            'manifest_path': str(window.manifest_path), 'manifest_sha256': window.manifest_sha,
            'receipt_path': str(window.receipt_path), 'receipt_sha256': window.receipt_sha,
            'scope': window.receipt['scope'], 'snapshot_id': window.receipt['snapshot_id'],
            'source_closure_sha256': window.receipt['source_closure_sha256'],
            'source_count': len(window.paths), 'check_count': window.check_count,
            'guarded_calls': window.guarded_calls,
        }
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        if json.loads(output.read_text(encoding='utf-8')) != report:
            raise RuntimeError('External receipt binding readback mismatch.')
    return exit_code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'manifest-sha', 'receipt', 'receipt-sha', 'scope', 'probe', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    window = SourceWindow(args.manifest, args.manifest_sha, args.receipt,
                          args.receipt_sha, args.scope, args.probe)
    arguments = args.arguments[1:] if args.arguments[:1] == ['--'] else args.arguments
    raise SystemExit(run_probe(window, arguments, args.output))


if __name__ == '__main__':
    main()
