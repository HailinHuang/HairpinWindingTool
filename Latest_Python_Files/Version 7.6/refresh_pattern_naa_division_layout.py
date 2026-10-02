"""Build a bounded V7.6 Pattern route view from public production decisions.

The finite scan describes requests, not a general admission rule. Only a
successful public generation probe can receive a generated-layout label.
"""

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from fractions import Fraction
from html import escape
from pathlib import Path
from types import SimpleNamespace

import get_winding_pattern as gw
from pattern_identity import PATTERN_CONTRACTS


ROOT = Path(__file__).resolve().parent
PAGE = ROOT / 'pattern_naa_division_layout.html'
DATA = ROOT / 'pattern_route_inventory.json'
STATUS = ROOT / 'INTEGER_Q_DIVIDER_SUPPORT_STATUS.md'
PATTERNS = tuple(PATTERN_CONTRACTS)
FORMULAS = (
    ('no_divider', 'None'), ('q_only', 'Q'), ('pp_only', 'PP'),
    ('p2_only', 'P2'), ('q_and_pp', 'Q+PP'), ('q_and_p2', 'Q+P2'),
    ('pp_and_p2', 'PP+P2'), ('q_and_pp_and_p2', 'Q+PP+P2'),
)
ADMISSIONS = ('supported', 'Candidate', 'rejected', 'unsupported-yet')


def divisors(value):
    return (item for item in range(1, value + 1) if value % item == 0)


def formula_name(factors):
    active = [name for name, value in zip(('q', 'pp', 'p2'), factors)
              if value != 1]
    return '_and_'.join(active) if len(active) > 1 else (
        active[0] + '_only' if active else 'no_divider')


def scan_geometries():
    """A small fixed request sample, with all eight factor types represented."""
    return [(2, 2, 2, 3), (2, 4, 4, 3), (2, 2, 4, 3), (2, 2, 6, 7),
            (4, 4, 4, 3), (6, 6, 4, 5)]


def source_hash():
    digest = hashlib.sha256()
    for name in ('get_winding_pattern.py', 'pattern_route_contract.py',
                 'divider_connection_formulas.py',
                 'half_integer_q_connection_formulas.py',
                 'pattern_identity.py', 'explicit_connections.py',
                 'refresh_pattern_naa_division_layout.py'):
        digest.update((ROOT / name).read_bytes())
    return digest.hexdigest()


def _inputs(pattern, q, pp, layers, phases, factors):
    q = Fraction(str(q))
    q = int(q) if q.denominator == 1 else q
    naa = factors[0] * factors[1] * factors[2]
    winding = SimpleNamespace(
        q=q, num_slots=int(q * 2 * pp * phases), num_poles=2 * pp,
        num_phases=phases, num_layers=layers, ab=int(naa),
        branch_dividers=tuple(factors))
    tp = SimpleNamespace(
        tp_type='Regular', tp_interval=0, tp_times=0, uni_tp=0,
        pltp_fl=0, pltp_ll=0, jltp=0, jld=1)
    layout = SimpleNamespace(
        phase_shift_list=[0] * layers, radial_shift=0,
        inlet_from_weld_side=int(gw.pattern_requires_weld_side_inlet(pattern)))
    return winding, tp, layout


def evaluate_case(pattern, q, pp, layers, phases, factors,
                  *, probe_generation=False, setting='Regular'):
    """Return exact resolver fields and, when requested, one public path result."""
    winding, tp, layout = _inputs(pattern, q, pp, layers, phases, factors)
    neutral = gw.resolve_pattern_route(pattern, winding, factors)
    layout.inlet_from_weld_side = int(neutral.required_inlet == 'weld')
    if setting == 'Shift':
        layout.phase_shift_list = [index % 2 for index in range(layers)]
    elif setting == 'Times=1':
        tp.tp_type, tp.tp_times = 'Times', 1
    elif setting == 'Interval=1':
        tp.tp_type, tp.tp_interval = 'Interval', 1
    elif setting == 'Opposite inlet':
        layout.inlet_from_weld_side = 1 - layout.inlet_from_weld_side
    elif setting != 'Regular':
        raise ValueError('Unknown configuration probe: ' + setting)
    decision = gw.resolve_pattern_route(
        pattern, winding, factors, tp, layout)
    result = {
        'pattern': pattern, 'q': str(q) if isinstance(q, Fraction) else q,
        'pp': pp, 'layers': layers, 'phases': phases,
        'naa': winding.ab,
        'dividers': [str(value) if isinstance(value, Fraction) else value
                     for value in factors],
        'setting': setting,
        'inlet': 'weld' if layout.inlet_from_weld_side else 'insert',
        'preflight': {
            'status': decision.status, 'admission': decision.admission,
            'rule_id': decision.rule_id, 'reason': decision.reason,
            'is_default': decision.is_default,
            'required_inlet': decision.required_inlet,
            'pin_profile': list(decision.pin_profile),
        },
    }
    if not probe_generation or decision.status == 'disabled':
        return result
    try:
        _, paths = gw.get_winding_layout(
            pattern, tp, winding, layout, allow_candidate=True)
    except (ValueError, TypeError, IndexError, ZeroDivisionError) as exc:
        result['production'] = {
            'status': 'rejected', 'reason': str(exc),
            'layout_retained': False, 'errors': [str(exc)],
        }
        return result
    report = paths.layout_report
    identity = report.get('pattern_identity') or {}
    if not report['layout_retained']:
        status = 'rejected'
        reason = ', '.join(report['errors']) or 'Public layout validation failed.'
    elif decision.status == 'candidate' or identity.get('status') != 'valid':
        status = 'Candidate'
        reason = identity.get('reason') or decision.reason
    elif not report['electrically_valid']:
        status = 'retained-not-strong'
        reason = ', '.join(report['errors'])
    else:
        status = 'Default' if decision.is_default else 'Validated'
        reason = 'Public layout generated; coverage, identity and electrical checks passed.'
    result['production'] = {
        'status': status, 'reason': reason,
        'layout_retained': bool(report['layout_retained']),
        'electrically_valid': bool(report['electrically_valid']),
        'identity_status': identity.get('status', 'unreported'),
        'errors': list(report['errors']),
        'route_rule_id': (report.get('pattern_route') or {}).get('rule_id'),
    }
    return result


def scan_inventory(geometries, *, probe_generation=True):
    """Count preflight admissions in exactly 80 Pattern × formula cells."""
    geometries = list(geometries)
    cells = {(pattern, formula): {
        'pattern': pattern, 'formula': formula, 'counts': Counter(),
        'examples': {},
    } for pattern in PATTERNS for formula, _ in FORMULAS}
    for q, pp, layers, phases in geometries:
        for pattern in PATTERNS:
            for Q in divisors(q):
                for D in divisors(pp):
                    for P2 in (1, 2):
                        factors = (Q, D, P2)
                        item = evaluate_case(
                            pattern, q, pp, layers, phases, factors)
                        cell = cells[pattern, formula_name(factors)]
                        admission = item['preflight']['admission']
                        cell['counts'][admission] += 1
                        cell['examples'].setdefault(admission, item)
    if probe_generation:
        for cell in cells.values():
            for admission in ('supported', 'Candidate'):
                sample = cell['examples'].get(admission)
                if sample:
                    cell['examples'][admission] = evaluate_case(
                        sample['pattern'], sample['q'], sample['pp'],
                        sample['layers'], sample['phases'],
                        tuple(sample['dividers']), probe_generation=True)
    return {
        'schema': 1,
        'version': '7.6',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(
            timespec='seconds'),
        'source_sha256': source_hash(),
        'geometries': [list(row) for row in geometries],
        'scope': ('Listed integer-q geometries, neutral Regular at the '
                  'route-required inlet. Counts are tuple/geometry requests, '
                  'not verified production layouts. This finite sample does '
                  'not determine support outside its listed parameters.'),
        'cells': [
            {**cell, 'counts': dict(cell['counts'])}
            for cell in cells.values()
        ],
    }


def feature_probes():
    """Small, explicit requests; never interpret them as Pattern-wide support."""
    rows = []
    for pattern in PATTERNS:
        factors = tuple(gw.classify_branch_mode(2, 2, 4, pattern)[1:4])
        probes = {}
        for setting in ('Regular', 'Shift', 'Times=1', 'Interval=1',
                        'Opposite inlet'):
            probes[setting] = evaluate_case(
                pattern, 2, 2, 4, 3, factors,
                setting=setting)
        probes['Odd layers'] = evaluate_case(
            pattern, 2, 2, 3, 3, factors)
        if pattern == 'SLP':
            probes['Proper-Q+PP+P2 parent regroup: scan delta sample'] = evaluate_case(
                'SLP', 4, 4, 4, 3, (2, 2, 2), probe_generation=True)
            probes['Proper-Q+PP+P2 parent regroup: odd q-lane group'] = evaluate_case(
                'SLP', 6, 6, 4, 5, (2, 3, 2), probe_generation=True)
            probes['Proper-Q+PP+P2 parent regroup: Q=3 scan delta'] = evaluate_case(
                'SLP', 6, 6, 4, 5, (3, 3, 2), probe_generation=True)
            probes['Proper-Q+PP+P2 parent regroup: six-phase array'] = evaluate_case(
                'SLP', 8, 8, 4, 6, (2, 4, 2), probe_generation=True)
            probes['Proper-Q+PP+P2 parent regroup: nine-phase array'] = evaluate_case(
                'SLP', 8, 8, 6, 9, (2, 4, 2), probe_generation=True)
            probes['Proper-Q+PP+P2 odd sector boundary'] = evaluate_case(
                'SLP', 8, 8, 4, 3, (2, 8, 2))
            probes['Proper-Q+PP+P2 nondivisor D boundary'] = evaluate_case(
                'SLP', 6, 6, 4, 5, (2, 4, 2))
        if pattern == 'CP':
            probes['PP-only four-pass sketch'] = evaluate_case(
                'CP', 2, 4, 4, 3, (1, 2, 1), probe_generation=True)
            probes['PP-only even-divider parent slices'] = evaluate_case(
                'CP', 2, 6, 4, 3, (1, 6, 1), probe_generation=True)
            probes['PP-only even-divider L=8 source failure'] = evaluate_case(
                'CP', 2, 6, 8, 3, (1, 6, 1), probe_generation=True)
            probes['Q=1 PP-only direct parent-slice sample'] = evaluate_case(
                'CP', 1, 6, 4, 3, (1, 6, 1), probe_generation=True)
            probes['Odd-q PP-only D=4 parent-slice sample (q=1)'] = evaluate_case(
                'CP', 1, 4, 4, 3, (1, 4, 1), probe_generation=True)
            probes['Odd-q PP-only D=4 parent-slice sample (q=3)'] = evaluate_case(
                'CP', 3, 4, 4, 3, (1, 4, 1), probe_generation=True)
            probes['Odd-q PP-only D=4 L=8 source failure (q=3)'] = evaluate_case(
                'CP', 3, 4, 8, 3, (1, 4, 1), probe_generation=True)
            probes['Q=1 PP-only arrayed local-q control'] = evaluate_case(
                'CP', 1, 6, 8, 6, (1, 6, 1), probe_generation=True)
            probes['Array global Nlayer=12, local six-layer Q+PP slice'] = evaluate_case(
                'CP', 2, 8, 12, 6, (2, 4, 1), probe_generation=True)
            probes['Array global Nlayer=12, local six-layer PP sector'] = evaluate_case(
                'CP', 1, 8, 12, 6, (1, 8, 1), probe_generation=True)
            probes['Array global Nlayer=12, local six-layer Q+PP D=6'] = evaluate_case(
                'CP', 2, 12, 12, 6, (2, 6, 1), probe_generation=True)
            probes['Q+PP+P2 parent slices: proper Q, D=2'] = evaluate_case(
                'CP', 4, 4, 4, 3, (2, 2, 2), probe_generation=True)
            probes['Q+PP+P2 parent slices: odd D=3'] = evaluate_case(
                'CP', 6, 6, 4, 5, (2, 3, 2), probe_generation=True)
            probes['Q+PP+P2 parent slices: full D=4'] = evaluate_case(
                'CP', 4, 4, 4, 3, (2, 4, 2), probe_generation=True)
            probes['Q+PP+P2 parent slices: six-phase L=12'] = evaluate_case(
                'CP', 4, 8, 12, 6, (2, 2, 2), probe_generation=True)
            probes['Q+PP+P2 default remains Default'] = evaluate_case(
                'CP', 6, 6, 4, 5, (2, 2, 2), probe_generation=True)
            probes['Q+PP+P2 nondivisor Q boundary'] = evaluate_case(
                'CP', 6, 6, 4, 5, (4, 2, 2))
            probes['Q+PP+P2 nondivisor D boundary'] = evaluate_case(
                'CP', 4, 6, 4, 3, (2, 4, 2))
            probes['Array global Nlayer=10 rejection'] = evaluate_case(
                'CP', 2, 8, 10, 6, (2, 4, 1), probe_generation=True)
            probes['Array odd local-layer rejection'] = evaluate_case(
                'CP', 2, 8, 12, 12, (2, 4, 1), probe_generation=True)
            probes['Q=1 PP-only L=8 direct source failure'] = evaluate_case(
                'CP', 1, 6, 8, 3, (1, 6, 1), probe_generation=True)
        if pattern == 'TSP':
            probes['PP-only full-q identity transfer sample'] = evaluate_case(
                'TSP', 2, 4, 4, 3, (1, 4, 1), probe_generation=True)
            probes['PP-only D=2 complete-pass closure'] = evaluate_case(
                'TSP', 2, 4, 4, 3, (1, 2, 1), probe_generation=True)
            probes['Q-only adjacent P2 pair: full-Q finite m=3'] = evaluate_case(
                'TSP', 2, 2, 4, 3, (2, 1, 1), probe_generation=True)
            probes['Q-only adjacent P2 pair: proper-Q m=3'] = evaluate_case(
                'TSP', 4, 3, 4, 3, (2, 1, 1), probe_generation=True)
            probes['Q-only adjacent P2 pair: three proper-Q lane sweeps'] = evaluate_case(
                'TSP', 6, 3, 4, 3, (2, 1, 1), probe_generation=True)
            probes['Q-only adjacent P2 pair: native m=5'] = evaluate_case(
                'TSP', 2, 2, 4, 5, (2, 1, 1), probe_generation=True)
            probes['Q-only adjacent P2 pair: finite m=7'] = evaluate_case(
                'TSP', 2, 2, 6, 7, (2, 1, 1), probe_generation=True)
            probes['Q-only adjacent P2 pair: six-phase array'] = evaluate_case(
                'TSP', 2, 2, 8, 6, (2, 1, 1), probe_generation=True)
            probes['Q-only adjacent P2 pair: nine-phase array'] = evaluate_case(
                'TSP', 2, 2, 12, 9, (2, 1, 1), probe_generation=True)
            probes['Q-only adjacent P2 pair: twelve-phase array'] = evaluate_case(
                'TSP', 2, 2, 16, 12, (2, 1, 1), probe_generation=True)
            probes['Q-only adjacent P2 pair: interior-gcd boundary'] = evaluate_case(
                'TSP', 2, 4, 4, 3, (2, 1, 1), probe_generation=True)
            probes['Q-only adjacent P2 pair: odd-Q boundary'] = evaluate_case(
                'TSP', 6, 2, 4, 3, (3, 1, 1))
            probes['Q-only adjacent P2 pair: pp=1 boundary'] = evaluate_case(
                'TSP', 2, 1, 4, 3, (2, 1, 1), probe_generation=True)
            probes['Q-only adjacent P2 pair: two-layer boundary'] = evaluate_case(
                'TSP', 2, 2, 2, 3, (2, 1, 1), probe_generation=True)
            probes['Q-only adjacent P2 pair: odd local-layer array boundary'] = evaluate_case(
                'TSP', 2, 2, 12, 12, (2, 1, 1))
            probes['PP+P2 fixed-lane saved sketch sample'] = evaluate_case(
                'TSP', 2, 4, 4, 3, (1, 4, 2), probe_generation=True)
            probes['PP+P2 fixed-lane repeated PP sample'] = evaluate_case(
                'TSP', 2, 12, 4, 3, (1, 4, 2), probe_generation=True)
            probes['PP+P2 fixed-lane phase-set array sample (m=6)'] = evaluate_case(
                'TSP', 2, 4, 4, 6, (1, 4, 2), probe_generation=True)
            probes['PP+P2 fixed-lane phase-set array sample (m=9)'] = evaluate_case(
                'TSP', 2, 6, 6, 9, (1, 6, 2), probe_generation=True)
            probes['PP+P2 fixed-lane q-lane residue collision'] = evaluate_case(
                'TSP', 2, 4, 4, 3, (1, 2, 2), probe_generation=True)
            probes['PP+P2 fixed-lane L=2 collision'] = evaluate_case(
                'TSP', 2, 4, 2, 3, (1, 4, 2), probe_generation=True)
            probes['PP+P2 fixed-lane local-q array boundary'] = evaluate_case(
                'TSP', 2, 4, 6, 9, (1, 4, 2), probe_generation=True)
            for factors in ((1, 2, 1), (2, 1, 1), (1, 2, 2), (2, 2, 2), (2, 4, 1)):
                probes[f'Complete-pass closure: saved factors {factors}'] = evaluate_case(
                    'TSP', 2, 4, 4, 3, factors, probe_generation=True)
            for phases, layers in ((5, 4), (7, 6), (6, 8), (9, 12), (12, 16)):
                probes[f'Complete-pass closure: m={phases}'] = evaluate_case(
                    'TSP', 2, 4, layers, phases, (2, 2, 2), probe_generation=True)
            probes['Complete-pass closure: one-pass boundary'] = evaluate_case(
                'TSP', 2, 4, 4, 3, (2, 4, 2))
            probes['Complete-pass closure: fractional global-q array boundary'] = evaluate_case(
                'TSP', Fraction(1, 2), 4, 8, 6, (1, 2, 1))
        if pattern == 'TLP':
            probes['Q-only adjacent P2 pair: matrix q=Q=2, L=2, m=3'] = evaluate_case(
                'TLP', 2, 2, 2, 3, (2, 1, 1), probe_generation=True)
            probes['Q-only adjacent P2 pair: matrix q=Q=2, pp=4'] = evaluate_case(
                'TLP', 2, 4, 4, 3, (2, 1, 1), probe_generation=True)
            probes['Q-only adjacent P2 pair: matrix q=Q=2, pp=2'] = evaluate_case(
                'TLP', 2, 2, 4, 3, (2, 1, 1), probe_generation=True)
            probes['Q-only adjacent P2 pair: matrix native m=7'] = evaluate_case(
                'TLP', 2, 2, 6, 7, (2, 1, 1), probe_generation=True)
            probes['Q-only adjacent P2 pair: matrix q=Q=4'] = evaluate_case(
                'TLP', 4, 4, 4, 3, (4, 1, 1), probe_generation=True)
            probes['Q-only adjacent P2 pair: matrix native m=5'] = evaluate_case(
                'TLP', 6, 6, 4, 5, (6, 1, 1), probe_generation=True)
            probes['Q-only adjacent P2 pair: full-Q q=8 range sample'] = evaluate_case(
                'TLP', 8, 5, 4, 3, (8, 1, 1), probe_generation=True)
            probes['Q-only adjacent P2 pair: full-Q odd-pp sample'] = evaluate_case(
                'TLP', 2, 3, 4, 3, (2, 1, 1), probe_generation=True)
            probes['Q-only adjacent P2 pair: four q lanes, odd pp'] = evaluate_case(
                'TLP', 4, 3, 4, 3, (4, 1, 1), probe_generation=True)
            probes['Q-only adjacent P2 pair: two-layer q=4 boundary'] = evaluate_case(
                'TLP', 4, 4, 2, 3, (4, 1, 1), probe_generation=True)
            probes['Q-only adjacent P2 pair: TSP interior-gcd contrast'] = evaluate_case(
                'TLP', 4, 6, 8, 5, (4, 1, 1), probe_generation=True)
            probes['Q-only adjacent P2 pair: proper-Q q=4 boundary'] = evaluate_case(
                'TLP', 4, 4, 4, 3, (2, 1, 1))
            probes['Q-only adjacent P2 pair: proper-Q q=6 boundary'] = evaluate_case(
                'TLP', 6, 6, 4, 5, (2, 1, 1))
            probes['Q-only adjacent P2 pair: odd-Q boundary'] = evaluate_case(
                'TLP', 3, 2, 4, 3, (3, 1, 1))
            probes['Q-only adjacent P2 pair: retained odd-Q rejection'] = evaluate_case(
                'TLP', 6, 6, 4, 5, (3, 1, 1))
            probes['Q-only adjacent P2 pair: pp=1 boundary'] = evaluate_case(
                'TLP', 2, 1, 4, 3, (2, 1, 1))
            probes['Q-only adjacent P2 pair: phase-array boundary'] = evaluate_case(
                'TLP', 2, 2, 4, 6, (2, 1, 1))
            probes['Q-only adjacent P2 pair: transposition boundary'] = evaluate_case(
                'TLP', 2, 2, 4, 3, (2, 1, 1), setting='Times=1')
            probes['Q-only adjacent P2 pair: phase-shift boundary'] = evaluate_case(
                'TLP', 2, 2, 4, 3, (2, 1, 1), setting='Shift')
            probes['Q-only adjacent P2 pair: wrong-inlet boundary'] = evaluate_case(
                'TLP', 2, 2, 4, 3, (2, 1, 1), setting='Opposite inlet')
            probes['Q+PP+P2 parent slices: saved q=2 draft'] = evaluate_case(
                'TLP', 2, 4, 4, 3, (2, 2, 2), probe_generation=True)
            probes['Q+PP+P2 parent slices: adjacent lanes q=4'] = evaluate_case(
                'TLP', 4, 4, 8, 3, (2, 2, 2), probe_generation=True)
            probes['Q+PP+P2 parent slices: adjacent lanes q=6'] = evaluate_case(
                'TLP', 6, 6, 12, 3, (2, 2, 2), probe_generation=True)
            probes['Q+PP+P2 parent slices: D=3 extension'] = evaluate_case(
                'TLP', 2, 6, 4, 3, (2, 3, 2), probe_generation=True)
            probes['Q+PP+P2 parent slices: six-phase lift'] = evaluate_case(
                'TLP', 2, 4, 8, 6, (2, 2, 2), probe_generation=True)
            probes['Q+PP+P2 parent slices: nine-phase lift'] = evaluate_case(
                'TLP', 2, 4, 12, 9, (2, 2, 2), probe_generation=True)
            probes['Q+PP+P2 parent slices: D=4 source boundary'] = evaluate_case(
                'TLP', 2, 8, 4, 3, (2, 4, 2))
            probes['Q+PP+P2 parent slices: short local-layer array'] = evaluate_case(
                'TLP', 2, 4, 8, 12, (2, 2, 2))
            probes['Q+PP+P2 parent slices: phase-shift boundary'] = evaluate_case(
                'TLP', 2, 4, 4, 3, (2, 2, 2), setting='Shift')
            probes['Q+PP+P2 parent slices: transposition boundary'] = evaluate_case(
                'TLP', 2, 4, 4, 3, (2, 2, 2), setting='Times=1')
            probes['PP-only even-divider Q=1 baseline'] = evaluate_case(
                'TLP', 2, 4, 4, 3, (1, 4, 1), probe_generation=True)
            probes['PP-only even-divider full-Q direct q=2'] = evaluate_case(
                'TLP', 2, 4, 4, 3, (2, 4, 1), probe_generation=True)
            probes['PP-only even-divider full-Q direct q=3'] = evaluate_case(
                'TLP', 3, 6, 6, 3, (3, 6, 1), probe_generation=True)
            probes['PP-only even-divider full-Q direct q=4'] = evaluate_case(
                'TLP', 4, 8, 4, 3, (4, 4, 1), probe_generation=True)
            probes['PP-only even-divider full-Q direct q=6'] = evaluate_case(
                'TLP', 6, 6, 6, 3, (6, 6, 1), probe_generation=True)
            for set_count in (2, 3, 4):
                global_divider = 4 * set_count
                probes[
                    'PP-only even-divider full-Q array m={}'.format(
                        3 * set_count)] = evaluate_case(
                            'TLP', 2, global_divider, global_divider,
                            3 * set_count,
                            (2, global_divider, 1), probe_generation=True)
            probes['PP-only even-divider proper-Q boundary'] = evaluate_case(
                'TLP', 4, 8, 4, 3, (2, 4, 1))
            probes['PP-only even-divider odd local-D boundary'] = evaluate_case(
                'TLP', 2, 8, 8, 6, (2, 6, 1))
            probes['PP-only even-divider short local-layer boundary'] = evaluate_case(
                'TLP', 2, 8, 6, 6, (2, 8, 1))
        if pattern == 'ZPP':
            probes['P2=2 odd integer q: Q=1, D=1'] = evaluate_case(
                'ZPP', 3, 4, 4, 3, (1, 1, 2))
            probes['P2=2 odd integer q: Q=1, D=2'] = evaluate_case(
                'ZPP', 3, 4, 4, 3, (1, 2, 2))
            probes['P2=2 odd integer q: Q=3, D=1'] = evaluate_case(
                'ZPP', 3, 4, 4, 3, (3, 1, 2))
            probes['P2=2 odd integer q: Q=3, D=2'] = evaluate_case(
                'ZPP', 3, 4, 4, 3, (3, 2, 2))
            probes['P2=2 even-q control'] = evaluate_case(
                'ZPP', 4, 4, 4, 3, (2, 2, 2))
            probes['P2=2 fractional-q control'] = evaluate_case(
                'ZPP', Fraction(3, 2), 4, 4, 3, (1, 2, 2))
            probes['P2=2 phase-set local odd-q control'] = evaluate_case(
                'ZPP', Fraction(3, 2), 4, 8, 6, (1, 2, 2))
            probes['PP-only half-turn baseline (D=2)'] = evaluate_case(
                'ZPP', 2, 4, 4, 3, (1, 2, 1), probe_generation=True)
            probes['PP-only indexed translation: coprime sample'] = evaluate_case(
                'ZPP', 3, 3, 4, 3, (1, 3, 1), probe_generation=True)
            probes['PP-only indexed translation: expanded direct boundary (a=2)'] = evaluate_case(
                'ZPP', 3, 6, 4, 3, (1, 3, 1), probe_generation=True)
            probes['PP-only indexed translation: composite direct stride (a=5)'] = evaluate_case(
                'ZPP', 6, 12, 4, 3, (1, 6, 1), probe_generation=True)
            probes['PP-only indexed translation: legacy arrayed local-q sample (a=1; 12 global two-boundary edges)'] = evaluate_case(
                'ZPP', 1, 3, 6, 9, (1, 3, 1), probe_generation=True)
            probes['PP-only indexed translation: array stride >1 boundary'] = evaluate_case(
                'ZPP', 1, 6, 6, 9, (1, 3, 1), probe_generation=True)
        rows.append({'pattern': pattern, 'probes': probes})
    return rows


def refresh_identity_policy(page):
    """Keep the existing V7.6 identity integration test source-backed."""
    start = '<!-- ORDERED-IDENTITY:START -->'
    end = '<!-- ORDERED-IDENTITY:END -->'
    rows = ''.join(
        '<tr><th scope="row">' + escape(pattern) + '</th><td>' +
        escape(contract) + '</td></tr>'
        for pattern, contract in PATTERN_CONTRACTS.items())
    block = (start + '\n<section class="panel" id="ordered-identity">'
             '<h2>Ordered Pattern identity</h2>'
             '<p>Check actual connection side, layer travel, signed slot '
             'direction and the shared one-pole-region limit on every edge.</p>'
             '<p><strong>Short branches allowed:</strong> optional returns '
             'may be absent. <strong>Degenerate overlap allowed:</strong> '
             'a short path can match more than one Pattern signature.</p>'
             '<div class="table-wrap"><table><thead><tr><th>Pattern</th>'
             '<th>Core connection</th></tr></thead><tbody>' + rows +
             '</tbody></table></div></section>\n' + end)
    if start in page or end in page:
        if page.count(start) != 1 or page.count(end) != 1:
            raise ValueError('Expected one ordered-identity marker pair.')
        before, tail = page.split(start, 1)
        _, after = tail.split(end, 1)
        return before + block + after
    anchor = '<section class="panel" id="connection-units">'
    if page.count(anchor) != 1:
        raise ValueError('Missing connection-unit anchor.')
    return page.replace(anchor, block + '\n' + anchor, 1)


def _case_details(case):
    decision = case['preflight']
    factors = ', '.join(map(str, case['dividers']))
    lines = [
        '<p><strong>Request:</strong> q={}, pp={}, L={}, m={}; '
        '(Q, PP, P2)=({}); {} inlet.</p>'.format(
            escape(str(case['q'])), case['pp'], case['layers'],
            case['phases'], escape(factors), escape(case['inlet'])),
        '<p><strong>Preflight:</strong> {} / {} · <code>{}</code>. {}</p>'.format(
            escape(decision['status']), escape(decision['admission']),
            escape(decision['rule_id']), escape(decision['reason'])),
    ]
    production = case.get('production')
    if production:
        lines.append(
            '<p><strong>Public generation:</strong> {}. {}</p>'.format(
                escape(production['status']),
                escape(production['reason'])))
    else:
        lines.append('<p><strong>Public generation:</strong> not run '
                     'for this disabled or preflight-only example.</p>')
    return ''.join(lines)


def render_page(inventory):
    """Render only current source decisions and bounded case evidence."""
    cells = {(cell['pattern'], cell['formula']): cell
             for cell in inventory['cells']}
    lines = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<title>Pattern Naa-Division Layout — Version 7.6</title>',
        '<style>',
        ':root{--ink:#1c3041;--muted:#536779;--navy:#193e61;'
        '--line:#d6e1ea;--bg:#f4f7fa;--link:#145d9e}',
        '*{box-sizing:border-box}body{margin:0;background:var(--bg);'
        'color:var(--ink);font:16px/1.5 "Segoe UI",Arial,sans-serif}',
        '.wrap{max-width:1240px;margin:auto;padding:0 24px}',
        'header{background:var(--navy);color:white;padding:28px 0}',
        'h1{margin:0 0 7px}h2{margin:0 0 12px}h3{margin:15px 0 7px}',
        'a{color:var(--link)}header a{color:#d4ebff}',
        'nav{display:flex;flex-wrap:wrap;gap:8px;margin:17px 0}',
        'nav a{background:white;border:1px solid var(--line);'
        'border-radius:6px;padding:6px 10px;text-decoration:none}',
        '.panel{background:white;border:1px solid var(--line);'
        'border-radius:9px;padding:20px;margin:0 0 18px}',
        '.note{background:#edf4fa;border-left:4px solid #6292bd;'
        'padding:9px 12px}.muted{color:var(--muted);font-size:14px}',
        '.table-wrap{overflow-x:auto;border:1px solid var(--line);'
        'border-radius:7px}table{width:100%;border-collapse:collapse}',
        'th,td{text-align:left;vertical-align:top;border-bottom:1px solid '
        'var(--line);padding:8px 10px}thead th{background:#edf3f8}',
        '.inventory{min-width:1050px}.inventory td{min-width:105px}',
        '.badge{display:inline-block;background:#e7f0fa;color:#194e7c;'
        'border-radius:20px;font-size:12px;font-weight:700;'
        'padding:2px 7px;margin:2px 2px 2px 0}',
        '.badge.Candidate{background:#eeeafa;color:#5e4b91}',
        '.badge.rejected{background:#fbeae7;color:#9a3b31}',
        '.badge.unsupported-yet{background:#fff1d8;color:#875700}',
        'details{margin:5px 0}summary{cursor:pointer;color:var(--link)}',
        'details p{margin:6px 0;overflow-wrap:anywhere}',
        'code{font-family:Consolas,monospace;font-size:.91em;'
        'overflow-wrap:anywhere}',
        'footer{padding:0 0 25px;color:var(--muted);font-size:14px}',
        '@media(max-width:650px){.wrap{padding:0 12px}.panel{padding:15px}'
        'body{font-size:15px}}',
        '</style></head><body><header><div class="wrap">',
        '<p>Winding Design Tool · Version 7.6</p>',
        '<h1>Pattern Naa-Division Layout</h1>',
        '<p>A finite status view refreshed from the current V7.6 public '
        'resolver and selected public generation calls.</p>',
        '</div></header><main class="wrap">',
        '<nav aria-label="Page navigation">'
        '<a href="#read-first">Read first</a>'
        '<a href="#route-inventory">80-cell scan</a>'
        '<a href="#ordered-identity">Pattern identity</a>'
        '<a href="#patterns">Per-Pattern probes</a>'
        '<a href="pattern_guide.html">Pattern Guide</a>'
        '</nav>',
        '<section class="panel" id="read-first"><h2>Read the statuses</h2>',
        '<p class="note"><strong>preflight enabled is not Validated.</strong> '
        'Supported means the V7.6 resolver admits this exact request before '
        'generation. Default or Validated appears only on a public-generated '
        'example that passes the retained-layout, Pattern identity and '
        'electrical checks. Candidate remains exploratory. '
        'retained-not-strong keeps a generated path with EMF asymmetry '
        'visible without certifying strong symmetry.</p>',
        '<p>The 80 Pattern × divider-type cells below count resolver '
        'admissions over five listed integer-q geometries. Mixed cells can '
        'contain multiple admissions. A generated example is one case, '
        'not a family-wide result. Configuration probes below show '
        'preflight only.</p>',
        '<p><strong>Sample scope:</strong> ' + escape(inventory['scope']) +
        ' <strong>Generated:</strong> ' +
        escape(inventory['generated_at_utc']) + ' UTC. '
        '<strong>Source SHA-256:</strong> <code>' +
        escape(inventory['source_sha256']) + '</code>.</p>',
        '<p><a href="get_winding_pattern.py">V7.6 public resolver and '
        'generator</a> · <a href="pattern_route_contract.py">decision '
        'contract</a> · <a href="divider_connection_formulas.py">'
        'divider formula layer</a> · '
        '<a href="INTEGER_Q_DIVIDER_SUPPORT_STATUS.md">'
        'finite status summary</a> · <a href="PATTERN_DIVIDER_FORMULA_SUPPORT.md">'
        'support notes</a>.</p>',
        '<p><a href="../Version%207.5/pattern_naa_division_layout.html">'
        'V7.5 historical research</a> and '
        '<a href="../Version%207.5/pattern_naa_review_cards.html">'
        'historical candidate review</a> retain the dated research '
        'evidence. Their counts are not current V7.6 admissions.</p>',
        '<p>Fractional q interfaces remain in the V7.6 resolver. This '
        'integer-q scan does not add fractional cases or promote the '
        'archived candidate evidence.</p></section>',
        '<section class="panel" id="route-inventory">',
        '<h2>Current finite resolver scan</h2>',
        '<p class="muted">Geometries (q, pp, L, m): ' +
        escape(', '.join(map(str, inventory['geometries']))) + '.</p>',
        '<div class="table-wrap"><table class="inventory"><thead><tr>'
        '<th>Pattern</th>' + ''.join(
            '<th>' + escape(label) + '</th>'
            for _, label in FORMULAS) + '</tr></thead><tbody>',
    ]
    for pattern in PATTERNS:
        row = ['<tr><th scope="row"><a href="#pattern-' +
               pattern.lower() + '">' + pattern + '</a></th>']
        for formula, _ in FORMULAS:
            cell = cells[pattern, formula]
            counts = cell['counts']
            badges = ''.join(
                '<span class="badge {}">{} {}</span>'.format(
                    admission, escape(admission), counts[admission])
                for admission in ADMISSIONS if counts.get(admission))
            examples = ''.join(
                '<details><summary>{} example</summary>{}</details>'.format(
                    escape(admission), _case_details(
                        cell['examples'][admission]))
                for admission in ADMISSIONS if admission in cell['examples'])
            row.append('<td id="cell-{}-{}">{}{}</td>'.format(
                pattern.lower(), formula, badges or '—', examples))
        lines.append(''.join(row) + '</tr>')
    lines += [
        '</tbody></table></div>',
        '<p class="muted">Counts refer to preflight requests, including '
        'disabled requests with exact resolver reasons. Open each example '
        'for its parameters, rule ID, reason and any public generation result.'
        '</p></section>',
        '<section class="panel" id="connection-units">'
        '<h2>Connection and divider identity</h2>'
        '<p>Naa = Q × PP × P2. Q divides integer q; PP divides the '
        'pole-pair count; P2 is 1 or 2. Factorization alone does not '
        'admit a route. Actual paths must satisfy the shared connection, '
        'phase, coverage, terminal and Pattern identity checks.</p>'
        '</section>',
        '<section class="panel" id="patterns"><h2>Per-Pattern source '
        'and configuration samples</h2><p class="muted">The expected '
        'body pin roles come from the V7.6 route contract. Conditional '
        'returns may be absent from a short valid branch. Configuration '
        'requests use q=2, pp=2, L=4, m=3 and the automatic Naa=2 '
        'factorization. Odd-layer requests use L=3. Configuration probes '
        'show preflight only; the explicitly listed route sample also '
        'shows public generation.</p></section>',
    ]
    for item in inventory['feature_probes']:
        pattern = item['pattern']
        probes = item['probes']
        profile = ', '.join(gw.PATTERN_DEFAULT_PIN_PROFILES[pattern])
        regular = probes['Regular']
        lines += [
            '<section class="panel" id="pattern-' + pattern.lower() + '">',
            '<h2>' + pattern + '</h2>',
            '<p><strong>Body pins:</strong> ' + escape(profile) +
            ' (expected source roles; actual paths determine presence).'
            '</p>',
            '<p><strong>Core connection:</strong> ' +
            escape(PATTERN_CONTRACTS[pattern]) + '</p>',
            '<p><strong>Divider routes:</strong> see the eight finite '
            'cells in the <a href="#route-inventory">current scan</a>; '
            'their exact reasons come from the V7.6 resolver.</p>',
            '<p><strong>Branch inlet / terminal side:</strong> this '
            'neutral request uses the ' + escape(regular['inlet']) +
            ' side; its resolver requires ' +
            escape(regular['preflight']['required_inlet']) +
            '. Other routes may differ.</p>',
        '<p><strong>Phase shift, transposition, weld-side inlet '
        'and odd layers:</strong> inspect the bounded preflight '
        'requests below. A passing preflight does not certify '
        'the generated connection. Explicit production examples '
        'are reported separately.</p>',
            '<p><strong>Fractional q:</strong> not scanned here; '
            '<a href="../Version%207.5/pattern_naa_division_layout.html'
            '#pattern-' + pattern.lower() + '">V7.5 evidence</a> '
            'remains historical.</p>',
            '<div class="table-wrap"><table><thead><tr><th>Setting or route sample</th>'
            '<th>Preflight</th><th>Rule and reason</th>'
            '<th>Public generation</th></tr></thead><tbody>',
        ]
        for setting, case in probes.items():
            decision = case['preflight']
            production = case.get('production')
            production_text = ('{} · {}'.format(
                production['status'], production['reason'])
                if production else 'not run (preflight only)')
            lines.append(
                '<tr><th scope="row">{}</th><td>{} / {}</td>'
                '<td><code>{}</code>: {}</td><td>{}</td></tr>'.format(
                    escape(setting), escape(decision['status']),
                    escape(decision['admission']),
                    escape(decision['rule_id']),
                    escape(decision['reason']),
                    escape(production_text)))
        lines += ['</tbody></table></div></section>']
    lines += [
        '</main><footer class="wrap">V7.6 finite source view. '
        '<a href="pattern_guide.html">Pattern Guide</a> · '
        '<a href="../Version%207.5/pattern_naa_division_layout.html">'
        'V7.5 historical research</a>.</footer></body></html>',
    ]
    return refresh_identity_policy('\n'.join(lines))


def render_status_document(inventory):
    totals = {pattern: Counter() for pattern in PATTERNS}
    for cell in inventory['cells']:
        totals[cell['pattern']].update(cell['counts'])
    lines = [
        '# Integer-q Pattern Divider Support Status — Version 7.6',
        '',
        'Generated from the V7.6 public resolver on ' +
        inventory['generated_at_utc'] + ' UTC.',
        '',
        'Source SHA-256: ' + inventory['source_sha256'],
        '',
        'Scope: ' + inventory['scope'],
        '',
        'The counts below are preflight tuple/geometry requests. A supported '
        'preflight is not a Validated generated layout. The linked page shows '
        'exact rule IDs, reasons, and bounded public generation examples.',
        '',
        '| Pattern | Supported preflight | Candidate | Rejected | '
        'Unsupported-yet |',
        '| --- | ---: | ---: | ---: | ---: |',
    ]
    for pattern in PATTERNS:
        counter = totals[pattern]
        lines.append('| {} | {} | {} | {} | {} |'.format(
            pattern, *(counter[admission] for admission in ADMISSIONS)))
    lines += [
        '',
        'Default and Validated labels on the page require a passing public '
        'generated example. A retained path with EMF asymmetry is shown '
        'separately as retained-not-strong; Candidate remains exploratory.',
        '',
        'Current view: [V7.6 Pattern Naa-Division Layout]'
        '(pattern_naa_division_layout.html) and '
        '[machine-readable finite scan](pattern_route_inventory.json).',
        '',
        'Historical evidence: [V7.5 integer-q status]'
        '(<../Version 7.5/INTEGER_Q_DIVIDER_SUPPORT_STATUS.md>) and '
        '[V7.5 Naa research]'
        '(<../Version 7.5/pattern_naa_division_layout.html>). '
        'Their dated counts are not current V7.6 admissions.',
        '',
        'Fractional q is outside this finite scan. Its V7.6 public '
        'resolver interface remains available without a new research claim '
        'from this page.',
        '',
    ]
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true',
                        help='Check saved source signatures.')
    args = parser.parse_args()
    if args.check:
        saved = json.loads(DATA.read_text(encoding='utf-8'))
        if saved['source_sha256'] != source_hash():
            raise ValueError('The saved V7.6 status view has stale source code.')
        if saved['source_sha256'] not in PAGE.read_text(encoding='utf-8'):
            raise ValueError('HTML source signature differs from JSON.')
        if saved['source_sha256'] not in STATUS.read_text(encoding='utf-8'):
            raise ValueError('Markdown source signature differs from JSON.')
        print('V7.6 status signatures match.')
        return
    inventory = scan_inventory(scan_geometries())
    inventory['feature_probes'] = feature_probes()
    DATA.write_text(json.dumps(inventory, ensure_ascii=False, indent=2),
                    encoding='utf-8')
    PAGE.write_text(render_page(inventory), encoding='utf-8')
    STATUS.write_text(render_status_document(inventory), encoding='utf-8')
    total = sum(sum(cell['counts'].values()) for cell in inventory['cells'])
    print('Refreshed {} Pattern cells and {} finite requests.'.format(
        len(inventory['cells']), total))


if __name__ == '__main__':
    main()
