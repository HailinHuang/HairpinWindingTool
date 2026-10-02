"""Standalone, exploratory workbench for sketching multiple independent Pattern branches.

Run with ``python pattern_rule_workbench.py`` from the Version 7.6 directory.
Ordinary steps follow the Pattern's public Regular reference path. Unsupported
formulas use the smallest generatable default Naa; ZPP explores one q-lane at a
time and proposes a formula-derived lane transition when ordinary steps run out.
Advance pauses before special edges and crosses them on the next click. CP and
ZPP also pause every four conductors as review checkpoints.
Exported PNG and JSON are process drafts, never approved winding
layouts.
"""

from dataclasses import dataclass
from copy import deepcopy
import cmath
import colorsys
from datetime import datetime
from fractions import Fraction
from functools import lru_cache
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace

from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QFormLayout, QGroupBox, QHeaderView,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
    QScrollArea, QSpinBox, QSplitter, QStyle, QTableWidget, QTableWidgetItem,
    QTabWidget, QVBoxLayout, QWidget,
)
from PyQt6.QtCore import Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT
from matplotlib.figure import Figure
import numpy as np

from phase_topology import (
    phase_map, shifted_connection_slot, supports_phase_count,
    supports_phase_layer_allocation, three_phase_set_count, winding_q,
)
import get_winding_pattern as gw
import draw_figure as dfig


SPECIAL_KINDS = ("jumper", "turnaround", "first_last_layer",
                 "layer_pair_transfer", "branch_join", "lane_transition", "custom")
PATTERNS = ("BWP", "UWP", "SSP", "SLP", "ZLP", "CP", "ZPP",
            "TSP", "TLP", "LPP")
MAX_PHASE_COUNT = 999  # Match the slot-grid control's practical input ceiling.
# Shared by reference-edge classification, Advance checkpoints and the Special
# Connections tab. Rules describe the Workbench base reference, not manufacturing.
_SAME_LAYER = dict(kind='turnaround', predicate='same_layer',
                   description='Same-layer boundary return')
_WAVE_JUMP = dict(kind='jumper', predicate='wave_jump',
                  description='Nonordinary wave pitch or layer span')
_TOP_BOTTOM = dict(kind='first_last_layer', predicate='top_bottom',
                   description='First/last-layer return (two layers: insertion return)')
_NEXT_LAYER_PAIR = dict(
    kind='layer_pair_transfer', predicate='next_layer_pair',
    description='Weld-side transfer after the completed loop block',
    endpoint_rule='Upper layer to lower layer of the next pair; exact reference endpoint')
_CP_ADVANCE_CHECKPOINT = dict(
    kind='checkpoint', predicate='conductor_interval', interval=4,
    description='Pause after every 4 CP draft-path conductors; keep reference edges ordinary',
    endpoint_rule='Stop after 4, 8, ... placed conductors; retain the next generated endpoint and side')
_ZPP_ADVANCE_CHECKPOINT = dict(
    kind='checkpoint', predicate='conductor_interval', interval=4,
    description='Pause after every 4 ZPP draft-path conductors; keep reference edges ordinary',
    endpoint_rule='Stop after 4, 8, ... placed conductors; retain the next generated endpoint and side')
_ZPP_LANE_TRANSITION = dict(
    kind='lane_transition', predicate='lane_transition',
    description='After the current q-lane has no legal ordinary step, move to an adjacent lane',
    endpoint_rule=('For direction d, use Δslot=d*(m*q)+d; insertion stays in-layer, '
                   'weld stays within its adjacent layer pair'))
PATTERN_SPECIAL_RULES = {
    'BWP': (_SAME_LAYER, _WAVE_JUMP), 'UWP': (_WAVE_JUMP,),
    'SSP': (_SAME_LAYER,), 'SLP': (_SAME_LAYER,), 'ZLP': (_SAME_LAYER,),
    'TSP': (_TOP_BOTTOM,), 'TLP': (_TOP_BOTTOM,),
    'CP': (_CP_ADVANCE_CHECKPOINT,),
    'ZPP': (_ZPP_ADVANCE_CHECKPOINT, _ZPP_LANE_TRANSITION),
    'LPP': (_NEXT_LAYER_PAIR,),
}
MANUAL_DRAFT_DIR = Path(__file__).resolve().parent / "pattern_rule_drafts"
ROUTE_NOTE_LOG = MANUAL_DRAFT_DIR / "route_notes.jsonl"
PATTERN_DEVELOPMENT_REFERENCE = (
    Path(__file__).resolve().parent / "PATTERN_DEFINITIONS_AND_CONSTRAINTS.md")


def phase_label(index: int) -> str:
    """Return a stable human label without limiting the model to three phases."""
    return chr(ord("A") + index) if 0 <= index < 26 else f"P{index + 1}"


def saved_phase_index(value, fallback=0) -> int:
    """Read both legacy A/B/C labels and the symbolic phase index."""
    if isinstance(value, int):
        return value
    text = str(value or "").strip().upper()
    if len(text) == 1 and "A" <= text <= "Z":
        return ord(text) - ord("A")
    if text.startswith("P") and text[1:].isdigit():
        return int(text[1:]) - 1
    return fallback


@dataclass(frozen=True)
class DividerRouteRecord:
    pattern: str
    q: Fraction
    pp: int
    layers: int
    slots: int
    naa: int
    dividers: tuple
    route_name: str
    status: str
    reason: str
    phases: int = 3


def _divisors(value: int) -> list[int]:
    return [candidate for candidate in range(1, value + 1)
            if value % candidate == 0]


def _factor_json(value):
    value = Fraction(value)
    return int(value) if value.denominator == 1 else str(value)


def _factor_tuple(values):
    result = []
    for value in values:
        factor = Fraction(str(value))
        result.append(int(factor) if factor.denominator == 1 else factor)
    return tuple(result)


def formula_route_name(dividers):
    """Name the Naa factor composition independently of production dispatch."""
    names = [name for name, value in zip(("q", "pp", "p2"), dividers)
             if Fraction(value) != 1]
    if not names:
        return "no_divider"
    if len(names) == 1:
        return names[0] + "_only"
    return "_and_".join(names)


FORMULA_SUPPORT_SUMMARY = """General divider identity

pp = poles / 2
pp-divisors = all positive integer factors of pp
pp-divider is any positive integer factor of pp
Naa = q-divider * pp-divider * P2

The tuple is (q-divider, pp-divider, P2). P2 is 1 or 2. A factor tuple is only
a decomposition; each Pattern must still admit and validate its own connection
construction.

Divider-type formulas

- No divider: (1, 1, 1), Naa = 1.
- q-divider only: (q-divider, 1, 1), Naa = q-divider.
- pp-divider only: (1, pp-divider, 1), Naa = pp-divider.
- P2 only: (1, 1, 2), Naa = 2.
- Mixed q + pp-divider: (q-divider, pp-divider, 1),
  Naa = q-divider * pp-divider.
- Mixed q + P2: (q-divider, 1, 2), Naa = 2 * q-divider.
- Mixed pp-divider + P2: (1, pp-divider, 2), Naa = 2 * pp-divider.
- Mixed q + pp-divider + P2: (q-divider, pp-divider, 2),
  Naa = 2 * q-divider * pp-divider.

P2 domain formulas

- Integer q, unit q-divider: Naa = 2 * 1 * pp-divider.
- Integer q, proper q-divider: Naa = 2 * q-divider * pp-divider, where
  1 < q-divider < q and q-divider divides q.
  Current general production support: UWP. Other Patterns use narrower routes.
- Integer q, full q-divider: Naa = 2 * q * pp-divider. Support is Pattern-specific.
- Positive half-integer q: this catalog retains its existing (q, pp-divider, 2)
  and (q, 2, 1) candidates. The production resolver decides their admission;
  unequal parallel EMF is reported separately as not strong symmetry.

Pattern-specific exclusions

For `m=3k`, the production resolver generates each equal-layer three-phase
set independently; phase-count and layer conditions below apply to that local
three-phase construction.

- BWP does not support P2-divider=2. Its catalog rows remain visible as rejected.
- ZLP rejects every tuple with Q-divider greater than 1, including mixed
  Q/PP/P2 formulas.
- CP rejects the no-divider (1,1,1) tuple.
- SSP P2-only (1,1,2) uses a distinct reflected q-lane cohort for even integer q,
  even local layers, pp>=2 and the supported local phase domain. Auto must verify strong counts and electrical
  validity before Validated; mixed SSP P2 formulas remain excluded.
- TSP, TLP, CP and ZPP q-and-pp with pp-divider=2 use a common second-sector
  deployment of their (Q,1,2) reference. Q>1 divides integer q, 2 divides pp,
  and each generated set satisfies its phase/layer conditions. Reference/deployed coverage and each
  Pattern's pin identity determine Enabled, Disabled or Candidate. TSP/TLP
  pp-divider alternatives without a registered construction remain unsupported-yet.
- TLP `(2,D,2)` splits each publicly generated `(1,D,2)` parent into two
  complete-pass paths. For even integer q, D>1 dividing pp, 2D<=pp and even
  local layers >=4, each outer-layer positive sector receives two distinct
  inlet q-lanes. Adjacent lanes are allowed when the complete path passes
  independent checks; the saved manual draft alone is not production evidence.
- TLP `(Q,1,1)` joins `g=2q/Q` consecutive full-q `(q,1,2)` parents within
  each outer-layer cohort. Even Q divides integer q, pp>=2, even L>=2 and
  one native phase set are required. Q>2 neutral groups retain unequal
  parallel complex EMF as not strong symmetry; two-layer overlap stays visible.
  Preflight and manual completion do not establish public generation.
- TSP `(1,D,2)` uses the fixed-lane two-inlet formula only when `q|D|pp` and
  every local q lane covers every pole-pair residue exactly once. Phase-set
  arrays apply that check locally and then validate the mapped global paths;
  passing public layouts with EMF-only mismatch remain `not strong symmetry layout`.
- TSP, TLP and CP reverse pole travel with the second cohort's layer traversal.
  TLP welds do not transpose and must share one direction per Layer_Pair after
  normalization from the lower-numbered to the higher-numbered layer.
  ZPP retains welding-direction audit findings. LPP admits only its full-PP
  source; catalog admission alone does not verify a generated case.

Catalog status

Default = the Pattern's automatic factor route passed production generation.
Validated = a selected non-default route passed production generation.
Manual drafts cannot confer either status. Strong symmetry is reported separately.
Loading a production route uses its generated paths and effective parameters;
manual exports remain non-certified.
not strong symmetry layout = retained layout with a count-divisibility proof.
identity unverified = route generated, but ordered Pattern identity is outside
  the recognizer's current layer domain; inspect its per-set confidence.
Candidate = a drawable identity/pin-role result isolated from production.
rejected = explicit rule exclusion or generation failure; see the route reason.
unsupported-yet = no production admission rule; it is not an impossibility claim.

See PATTERN_DIVIDER_FORMULA_SUPPORT.md for the complete Pattern matrix.
"""


def load_pattern_development_reference():
    """Load the maintained developer reference instead of copying its rules."""
    try:
        return PATTERN_DEVELOPMENT_REFERENCE.read_text(encoding="utf-8")
    except OSError as exc:
        return (f"Pattern developer reference is unavailable:\n{exc}\n\n"
                f"Expected file: {PATTERN_DEVELOPMENT_REFERENCE}")


def _base_inputs(pattern, q, poles, layers, naa, dividers=None, phases=3):
    from types import SimpleNamespace
    slots = int(Fraction(q) * poles * phases)
    winding = SimpleNamespace(q=int(q) if Fraction(q).denominator == 1 else Fraction(q),
                              num_slots=slots, num_poles=poles, num_phases=phases,
                              num_layers=layers, ab=naa)
    if dividers is not None:
        winding.branch_dividers = tuple(dividers)
    transposition = SimpleNamespace(tp_type="Regular", tp_interval=0, tp_times=0,
                                    uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1)
    layout = SimpleNamespace(phase_shift_list=[0] * layers, radial_shift=0,
                             inlet_from_weld_side=int(
                                 gw.pattern_requires_weld_side_inlet(pattern)))
    return winding, transposition, layout


def _probe_route(pattern, q, poles, layers, naa, dividers, phases=3,
                 pending_only_search=False):
    winding, transposition, layout = _base_inputs(
        pattern, q, poles, layers, naa, dividers, phases)
    try:
        if pending_only_search and Fraction(q).denominator == 1:
            _, baseline = gw.get_winding_layout(
                pattern, transposition, winding, layout, allow_candidate=True)
            records = gw.phase_map(
                winding.num_slots, winding.num_poles, winding.num_layers,
                layout.phase_shift_list, winding.num_phases)
            assessment = gw.auto_tp.assess_strong_symmetry(
                baseline, records, winding.num_slots,
                winding.num_poles, winding.ab)
            if assessment['hard_no']:
                return True, ('not strong symmetry layout: '
                              + assessment['reason'])
            if (assessment['strong']
                    and baseline.layout_report['electrically_valid']):
                return True, ('strong symmetry layout: '
                              + assessment['reason'])
        _, database = gw.get_auto_configured_layout(
            pattern, transposition, winding, layout, allow_candidate=True)
    except (ValueError, TypeError, IndexError, ZeroDivisionError) as exc:
        return False, str(exc)
    identity = database.layout_report.get('pattern_identity', {})
    if identity.get('status') == 'unverified':
        reason = 'identity unverified: ' + identity.get('reason', '')
        if hasattr(database, 'auto_configuration'):
            auto = database.auto_configuration
            reason += (f" Auto status: {auto['status']}: "
                       f"{auto['assessment']['reason']}.")
        elif getattr(database, 'layout_status', '') == 'not strong symmetry layout':
            reason += '; layout status: not strong symmetry layout'
        return True, reason
    if hasattr(database,'auto_configuration'):
        auto = database.auto_configuration
        return True, auto['status'] + ': ' + auto['assessment']['reason'] + (
            ' Auto parameters: ' + str(auto['parameters']) if auto['parameters'] else '')
    if getattr(database, 'layout_status', '') == 'not strong symmetry layout':
        return True, 'not strong symmetry layout: ' + ', '.join(database.layout_report['errors'])
    return True, "Complete base layout passed the current generator validators."


def _probe_slp_selected_route(q, poles, layers, naa, dividers, phases):
    """Classify a selected SLP route from its production base layout."""
    winding, transposition, layout = _base_inputs(
        "SLP", q, poles, layers, naa, dividers, phases)
    try:
        _, database = gw.get_winding_layout(
            "SLP", transposition, winding, layout)
    except (ValueError, TypeError, IndexError, ZeroDivisionError) as exc:
        return False, str(exc)
    report = database.layout_report
    if (not report.get("layout_retained")
            or report.get("pattern_identity", {}).get("status") != "valid"):
        return False, "SLP production layout failed retention or Pattern identity."
    reason = "Production base layout passed the current generator validators."
    if not report.get("electrically_valid"):
        reason += " Electrical result: not strong symmetry layout."
    return True, reason


def _probe_tsp_pp_p2_sector(q, poles, layers, naa, dividers, phases):
    """Classify TSP sector/pass formulas from their public Regular layout."""
    winding, transposition, layout = _base_inputs(
        'TSP', q, poles, layers, naa, dividers, phases)
    try:
        _, database = gw.get_winding_layout(
            'TSP', transposition, winding, layout)
    except (ValueError, TypeError, IndexError, ZeroDivisionError) as exc:
        return False, str(exc)
    report = database.layout_report
    if (not report.get('layout_retained')
            or report.get('pattern_identity', {}).get('status') != 'valid'):
        return False, 'TSP production layout failed retention or identity.'
    if not report.get('electrically_valid'):
        return True, ('not strong symmetry layout: '
                      + ', '.join(report.get('errors', ())))
    return True, 'Production TSP layout passed the current validators.'


@lru_cache(maxsize=256)
def build_divider_route_catalog(q_text: str, pp: int, layers: int,
                                phases: int = 3, pending_only_search=False):
    """Return the current production classification for one machine geometry."""
    if not supports_phase_count(phases):
        raise ValueError(
            "Supported phase counts are odd integers >= 3 or multiples of three.")
    if not supports_phase_layer_allocation(phases, layers):
        set_count = three_phase_set_count(phases)
        raise ValueError(
            f"{phases} phases require layers divisible by {set_count} "
            "to allocate equal three-phase winding sets.")
    q = Fraction(q_text)
    poles = 2 * pp
    slots = q * poles * phases
    if q <= 0 or slots.denominator != 1:
        raise ValueError("q and pp must produce an integer slot count.")
    if q.denominator not in (1, 2):
        raise ValueError("Catalog q must be an integer or positive half-integer.")
    if q.denominator == 1:
        configurations = tuple(
            (q_divider * pp_divider * p2_divider,
             (q_divider, pp_divider, p2_divider))
            for q_divider in _divisors(int(q))
            for pp_divider in _divisors(pp)
            for p2_divider in (1, 2))
    else:
        # Keep the current fractional catalog scope; one resolver judges every row.
        configurations = tuple(
            (int(2 * q * pp_divider), (q, pp_divider, 2))
            for pp_divider in _divisors(pp))
        if pp % 2 == 0:
            configurations += ((int(2 * q), (q, 2, 1)),)
    records = []
    for pattern in PATTERNS:
        for naa, dividers in configurations:
            winding, transposition, layout = _base_inputs(
                pattern, q, poles, layers, naa, dividers, phases)
            decision = gw.resolve_pattern_route(
                pattern, winding, dividers, transposition, layout)
            if decision.admission == 'Candidate':
                status, reason = 'Candidate', decision.reason
            elif decision.admission in ('rejected', 'unsupported-yet'):
                status, reason = decision.admission, decision.reason
            elif decision.admission == 'supported':
                if pattern == 'SLP' and not decision.is_default:
                    ok, reason = _probe_slp_selected_route(
                        q, poles, layers, naa, dividers, phases)
                elif (pattern == 'TSP'
                      and decision.route_name in (
                          'tsp_pp_p2_sector', 'tsp_spiral_pass_partition')):
                    ok, reason = _probe_tsp_pp_p2_sector(
                        q, poles, layers, naa, dividers, phases)
                else:
                    ok, reason = _probe_route(
                        pattern, q, poles, layers, naa, dividers, phases,
                        pending_only_search)
                status = ('Default' if decision.is_default else 'Validated') if ok else 'rejected'
                if not ok and decision.is_default:
                    reason = 'Default route rejected for this case: ' + reason
                if ok and reason.startswith('not strong symmetry layout'):
                    status = 'not strong symmetry layout'
                elif ok and reason.startswith('identity unverified'):
                    status = 'identity unverified'
            else:
                raise ValueError(f"Unknown production route admission: {decision.admission}")
            records.append(DividerRouteRecord(
                pattern, q, pp, layers, int(slots), naa, tuple(dividers),
                formula_route_name(dividers), status, reason, phases))
    return tuple(records)


def _reference_edge_kind(pattern, layer_delta, signed_pitch, layers, main_pitches,
                         side='insert', start_layer=None):
    """Identify only the explicit transitions defined as special by a Pattern."""
    matches = {
        'same_layer': layer_delta == 0,
        'top_bottom': abs(layer_delta) == layers - 1
                      and (layers > 2 or side == 'insert'),
        'wave_jump': abs(layer_delta) != 1 or abs(signed_pitch) not in main_pitches,
        'next_layer_pair': (side == 'weld' and start_layer is not None
                            and start_layer % 2 == 1
                            and layer_delta == 1 and start_layer + 1 < layers),
    }
    for rule in PATTERN_SPECIAL_RULES[pattern]:
        if rule['predicate'] in ('conductor_interval', 'lane_transition'):
            # Checkpoints and formula transitions are not copied reference edges.
            continue
        if matches[rule['predicate']]:
            return rule['kind']
    return "ordinary"


def _advance_checkpoint_interval(pattern):
    """Return the Workbench pause interval registered for this Pattern, if any."""
    return next((rule['interval'] for rule in PATTERN_SPECIAL_RULES[pattern]
                 if rule.get('predicate') == 'conductor_interval'), None)


def _database_reference_paths(database):
    """Return slot/layer paths from a public Regular layout."""
    return [(branch, [tuple(conductor[:2]) for conductor in path])
            for branch, path in database]


def _zpp_zero_extra_transposition_paths(paths, q, phases, slots, phase_lookup):
    """Replace ZPP same-layer lane changes with the parameterized regular pitch."""
    q_fraction = Fraction(q)
    if q_fraction.denominator != 1 or q_fraction <= 0:
        return paths, {'available': False,
                       'reason': 'The ZPP lane reference requires positive integer q.'}
    if phases != 3:
        return paths, {'available': False,
                       'reason': 'The lane coordinate formula is verified for one three-phase set.'}

    q_value = int(q_fraction)
    tau = phases * q_value
    transformed = []
    all_positions = []
    for branch, path in paths:
        if not path:
            return paths, {'available': False, 'reason': 'A public ZPP branch is empty.'}
        first_record = phase_lookup.get(path[0])
        if first_record is None:
            return paths, {'available': False,
                           'reason': 'A public ZPP inlet is outside the phase map.'}
        lane = path[0][0] % q_value
        output = [path[0]]
        for start, end in zip(path, path[1:]):
            start_record = phase_lookup.get(start)
            end_record = phase_lookup.get(end)
            if (start_record is None or end_record is None
                    or start_record[0] != end_record[0]
                    or start_record[1] != -end_record[1]):
                return paths, {'available': False,
                               'reason': 'The public ZPP reference fails phase or polarity checks.'}
            delta = (end[0] - start[0]) % slots
            signed_pitch = delta if delta <= slots // 2 else delta - slots
            if start[1] == end[1]:
                if signed_pitch == 0:
                    return paths, {'available': False,
                                   'reason': 'A same-layer reference edge has zero pitch.'}
                signed_pitch = (1 if signed_pitch > 0 else -1) * tau
            target = ((output[-1][0] + signed_pitch) % slots, end[1])
            target_record = phase_lookup.get(target)
            if (target_record is None or target_record[0] != start_record[0]
                    or target_record[1] != -start_record[1]):
                return paths, {'available': False,
                               'reason': 'The q-lane pitch does not preserve phase and polarity.'}
            if target in output:
                return paths, {'available': False,
                               'reason': 'The q-lane pitch repeats a conductor in its branch.'}
            if target[0] % q_value != lane:
                return paths, {'available': False,
                               'reason': 'A public layer-change edge leaves its q-lane.'}
            output.append(target)
        transformed.append((branch, output))
        all_positions.extend(output)

    if len(all_positions) != len(set(all_positions)):
        return paths, {'available': False,
                       'reason': 'The q-lane references overlap conductor positions.'}
    return transformed, {
        'available': True,
        'q': q_value,
        'phases': phases,
        'tau': tau,
        'lane_rule': 'lane=(slot-layer_shift) mod q',
        'transition_rule': 'delta_slot=direction*(m*q)+lane_delta',
        'branch_lanes': [path[0][0] % q_value for _branch, path in transformed
                         if path and phase_lookup[path[0]][0] == 0],
    }


def extract_reference_constraints(pattern, q, poles, layers, naa, phases=3,
                                  dividers=None, database=None,
                                  zero_extra_transposition=True):
    """Extract the selected Pattern's edge vocabulary and ordered transitions."""
    reference_mode = 'selected'
    selected_error = ''
    try:
        winding, transposition, layout = _base_inputs(
            pattern, q, poles, layers, naa, dividers, phases)
        if database is None:
            _, database = gw.get_winding_layout(
                pattern, transposition, winding, layout, allow_candidate=True)
        if (pattern == 'LPP' and database.layout_report.get(
                'pattern_identity', {}).get('status') != 'valid'):
            raise ValueError('Selected LPP path reverses weld travel; use a valid default reference.')
    except (ValueError, TypeError, IndexError, ZeroDivisionError) as exc:
        selected_error = str(exc)
        reference_mode = 'default_series'
        q_fraction = Fraction(q)
        if q_fraction.denominator == 1:
            candidates = sorted({a*b*c for a in gw.divisors(int(q))
                                 for b in gw.divisors(poles//2) for c in (1, 2)})
        elif q_fraction.denominator == 2:
            candidates = [int(2*q_fraction)]
        else:
            candidates = []
        for reference_naa in candidates:
            try:
                winding, transposition, layout = _base_inputs(
                    pattern, q, poles, layers, reference_naa, phases=phases)
                _, database = gw.get_winding_layout(
                    pattern, transposition, winding, layout,
                    allow_candidate=(pattern != 'LPP'))
                break
            except (ValueError, TypeError, IndexError, ZeroDivisionError):
                continue
        else:
            return {"available": False, "reason":
                    f"Selected formula: {selected_error} No generatable default {pattern} reference.",
                    "edges": [], "reference_mode": reference_mode}
    lookup = {(slot, layer): (phase, sign)
              for slot, layer, phase, sign in phase_map(
                  winding.num_slots, poles, layers, (0,) * layers, phases)}
    reference_paths = _database_reference_paths(database)
    lane_walk = None
    if pattern == 'ZPP' and zero_extra_transposition:
        reference_paths, lane_walk = _zpp_zero_extra_transposition_paths(
            reference_paths, q, phases, winding.num_slots, lookup)
        if reference_mode == 'default_series':
            reference_mode = 'default_lane_walk'
    elif pattern == 'ZPP':
        lane_walk = {'available': False,
                     'reason': 'The direct public Regular paths were requested without lane transformation.'}
    edges = set()
    transitions = []
    pitch = phases * Fraction(q)
    main_pitches = {math.floor(pitch), math.ceil(pitch)}
    first_side = "insert" if layout.inlet_from_weld_side else "weld"
    for _, path in reference_paths:
        for index, (start, end) in enumerate(zip(path, path[1:])):
            start_key, end_key = tuple(start[:2]), tuple(end[:2])
            delta = (end_key[0] - start_key[0]) % winding.num_slots
            pitch = delta if delta <= winding.num_slots // 2 else delta - winding.num_slots
            side = first_side if index % 2 == 0 else (
                "insert" if first_side == "weld" else "weld")
            layer_delta = end_key[1] - start_key[1]
            kind = _reference_edge_kind(
                pattern, layer_delta, pitch, layers, main_pitches, side,
                start_key[1])
            transitions.append({
                "start": list(start_key), "end": list(end_key), "side": side,
                "kind": kind,
                "note": ('LPP reference next layer pair weld transfer'
                         if kind == 'layer_pair_transfer' else
                         f"{pattern} reference {kind.replace('_', ' ')}"),
            })
            edges.add((side, layer_delta, pitch,
                       lookup.get(start_key, (None, 0))[1] ==
                       -lookup.get(end_key, (None, 0))[1], kind))
    starts = {str(phase): list(next(path[0][:2] for _, path in reference_paths
              if lookup[tuple(path[0][:2])][0] == phase)) for phase in range(phases)}
    if reference_mode in ('default_series', 'default_lane_walk'):
        for phase in range(phases):
            paths = [path for _, path in reference_paths
                     if lookup[tuple(path[0][:2])][0] == phase]
            if not paths:
                continue
            starts[str(phase)] = list(paths[0][0][:2])
            joins = (zip(paths, paths[1:])
                     if reference_mode == 'default_series' and pattern != 'ZPP'
                     else ())
            for path, following in joins:
                # An even conductor count preserves the following branch's
                # original edge side after inserting the series connection.
                if len(path) % 2:
                    return {'available': False, 'edges': [], 'reason':
                            'Default series reference has incompatible branch edge parity.'}
                transitions.append(dict(start=list(path[-1][:2]),
                    end=list(following[0][:2]),
                    side='insert' if first_side == 'weld' else 'weld',
                    kind='branch_join', note=f'{pattern} default branch outlet to next inlet'))
    reference_dividers = (tuple(gw.classify_branch_mode(
        winding.ab, int(q), poles, pattern)[1:4]) if Fraction(q).denominator == 1
        else (Fraction(q), 1, 2))
    if reference_mode == 'selected' and dividers is not None:
        reference_dividers = dividers
    source = ('smallest generatable default (q-lane reference)'
              if reference_mode == 'default_lane_walk' else
              'smallest generatable default (series)'
              if reference_mode == 'default_series' else 'selected')
    if lane_walk is not None:
        lane_walk.update({
            'source_dividers': [_factor_json(value) for value in reference_dividers],
            'target_dividers': (None if dividers is None else
                                [_factor_json(value) for value in dividers]),
            'reference_mode': reference_mode,
        })
    return {"available": True,
            "reason": f"Extracted from the public Regular {source} Pattern layout.",
            "reference_mode": reference_mode, "reference_naa": winding.ab,
            "reference_dividers": [_factor_json(v) for v in reference_dividers],
            "selected_dividers": (None if dividers is None else
                                  [_factor_json(v) for v in dividers]),
            "reference_starts": starts, "first_side": first_side,
            "reference_branch_starts": {str(phase): [list(path[0][:2]) for _, path in reference_paths
                if lookup[tuple(path[0][:2])][0] == phase] for phase in range(phases)},
            "selected_error": selected_error,
            "transitions": transitions,
            **({'lane_walk': lane_walk} if lane_walk is not None else {}),
            "edges": [dict(side=side, layer_delta=layer_delta,
                           signed_pitch=pitch, direction_ok=direction_ok,
                           kind=kind)
                      for side, layer_delta, pitch, direction_ok, kind
                      in sorted(edges)]}


def generate_route_drafts(record: DividerRouteRecord,
                          zero_extra_transposition=True):
    """Load public Regular paths as exploratory Pattern references."""
    winding, transposition, layout = _base_inputs(
        record.pattern, record.q, record.pp * 2, record.layers,
        record.naa, record.dividers, record.phases)
    _, database = gw.get_winding_layout(
        record.pattern, transposition, winding, layout, allow_candidate=True)
    shifts = (0,) * record.layers
    phase_lookup = {(slot, layer): (phase, sign)
                    for slot, layer, phase, sign in phase_map(
                        record.slots, record.pp * 2, record.layers, shifts,
                        record.phases)}
    constraints = extract_reference_constraints(
        record.pattern, record.q, record.pp * 2, record.layers, record.naa,
        record.phases, record.dividers, database=database,
        zero_extra_transposition=zero_extra_transposition)
    reference_paths = _database_reference_paths(database)
    if (record.pattern == 'ZPP' and zero_extra_transposition
            and constraints.get('lane_walk', {}).get('available')):
        reference_paths, _ = _zpp_zero_extra_transposition_paths(
            reference_paths, record.q, record.phases, record.slots, phase_lookup)
    first_side = "insert" if layout.inlet_from_weld_side else "weld"
    drafts = []
    transition_kinds = {
        (tuple(edge['start']), tuple(edge['end']), edge['side']): edge
        for edge in constraints.get('transitions', [])}
    for _, path in reference_paths:
        if not path or phase_lookup.get(path[0], (-1, 0))[0] != 0:
            continue
        draft = PatternDraft(
            record.slots, record.pp * 2, record.layers, phase=0,
            start=path[0], first_side=first_side, shifts=shifts,
            naa=record.naa, pattern=record.pattern, source_route=record,
            reference_constraints=constraints, num_phases=record.phases)
        draft.path = path
        draft.steps = []
        for index, (start, end) in enumerate(zip(path, path[1:])):
            delta = (end[0] - start[0]) % record.slots
            pitch = delta if delta <= record.slots // 2 else delta - record.slots
            side = first_side if index % 2 == 0 else (
                "insert" if first_side == "weld" else "weld")
            edge = transition_kinds.get((start, end, side), {})
            kind = edge.get('kind', 'ordinary')
            draft.steps.append(DraftStep(
                start, end, side, "regular" if kind == 'ordinary' else kind, pitch,
                1 if pitch >= 0 else -1,
                phase_lookup.get(start, (-1, 0))[1] ==
                -phase_lookup.get(end, (-1, 0))[1],
                edge.get('note', 'Public Regular Pattern reference edge')))
        if draft.steps:
            draft.wave_direction = draft.steps[0].wave_direction
        drafts.append(draft)
    if len(drafts) != record.naa:
        raise ValueError(
            f"Generated {len(drafts)} Phase A branches; expected Naa={record.naa}.")
    return drafts


def load_saved_route_drafts(path, record):
    """Restore a saved manual configure package for continued editing."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    drafts = []
    for branch_data in data.get("branches", []):
        path_data = branch_data.get("path", [])
        if not path_data:
            continue
        conductor_path = [(int(item["slot"]) - 1, int(item["layer"]) - 1)
                          for item in path_data]
        phase = saved_phase_index(
            branch_data.get("phase_index", branch_data.get("phase", "A")))
        shifts = tuple(branch_data.get("layer_shifts", [0] * record.layers))
        draft = PatternDraft(
            record.slots, record.pp * 2, record.layers, phase=phase,
            start=conductor_path[0],
            first_side=branch_data.get("first_connection_side", "weld"),
            shifts=shifts, naa=record.naa, pattern=record.pattern,
            source_route=record,
            reference_constraints=branch_data.get(
                "reference_constraints", {"available": False, "edges": []}),
            num_phases=record.phases)
        draft.path = conductor_path
        draft.steps = []
        for step_data in branch_data.get("steps", []):
            start = (int(step_data["from"]["slot"]) - 1,
                     int(step_data["from"]["layer"]) - 1)
            end = (int(step_data["to"]["slot"]) - 1,
                   int(step_data["to"]["layer"]) - 1)
            draft.steps.append(DraftStep(
                start, end, step_data["side"], step_data["kind"],
                int(step_data["signed_pitch"]),
                int(step_data.get("wave_direction", 1)),
                bool(step_data.get("direction_ok", True)),
                step_data.get("note", "")))
        draft.wave_direction = int(branch_data.get("current_wave_direction", 1))
        draft.notes = branch_data.get("designer_notes", "")
        draft.saved_active_branch = int(data.get("active_branch", 1)) - 1
        draft.manual_edit_dirty = bool(data.get("manual_edit_dirty"))
        draft.saved_transform_report = data.get("manual_transform")
        drafts.append(draft)
    if not drafts:
        raise ValueError("Saved manual configure contains no branch path.")
    return drafts


class DividerRouteCatalog(QWidget):
    """On-demand view of production route admission for one geometry."""

    def __init__(self, open_callback):
        super().__init__()
        self.open_callback = open_callback
        self.records = ()
        self.saved_routes = self._load_saved_routes(MANUAL_DRAFT_DIR)
        self.note_log_path = ROUTE_NOTE_LOG
        self.route_notes = self._load_route_notes(self.note_log_path)
        self.status_widgets = {}
        layout = QVBoxLayout(self)
        form = QHBoxLayout()
        self.q_box = QLineEdit("2")
        self.pp_box = QSpinBox(); self.pp_box.setRange(1, 50); self.pp_box.setValue(4)
        self.layers_box = QSpinBox(); self.layers_box.setRange(2, 50); self.layers_box.setValue(4)
        self.phases_box = QSpinBox(); self.phases_box.setRange(3, MAX_PHASE_COUNT)
        self.phases_box.setSingleStep(1); self.phases_box.setValue(3)
        self.refresh_button = QPushButton("Refresh Routes")
        self.refresh_button.clicked.connect(self.refresh)
        for label, widget in (("q", self.q_box), ("Pole pairs", self.pp_box),
                              ("Layers", self.layers_box),
                              ("Phases", self.phases_box)):
            form.addWidget(QLabel(label)); form.addWidget(widget)
        form.addWidget(self.refresh_button); form.addStretch()
        layout.addLayout(form)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ("Pattern", "q", "pp", "Naa",
             "(q-divider, pp-divider, P2)", "Route", "Open", "Status"))
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.doubleClicked.connect(self.open_selected)
        layout.addWidget(self.table, 1)
        actions = QHBoxLayout()
        self.hint = QLabel("Open any route; validated/default routes include complete paths.")
        self.open_button = QPushButton("Open Selected Route")
        self.open_button.clicked.connect(self.open_selected)
        actions.addWidget(self.hint, 1); actions.addWidget(self.open_button)
        layout.addLayout(actions)
        self.refresh()

    @staticmethod
    def _route_key(record):
        return (record.pattern, str(record.q), record.pp, record.layers,
                record.naa, tuple(record.dividers), record.phases)

    @staticmethod
    def _note_key(data):
        return (data["pattern"], str(data["q"]), int(data["pp"]),
                int(data["layers"]), int(data["naa"]),
                _factor_tuple(data["dividers"]), int(data.get("phases", 3)))

    @classmethod
    def _load_route_notes(cls, path):
        notes = {}
        path = Path(path)
        if not path.is_file():
            return notes
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return notes
        for line in lines:
            try:
                entry = json.loads(line)
                notes[cls._note_key(entry)] = str(entry.get("note", ""))
            except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                continue
        return notes

    def _record_route_note(self, record, note):
        note = str(note)
        key = self._route_key(record)
        self.route_notes[key] = note
        entry = {
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "pattern": record.pattern, "q": str(record.q), "pp": record.pp,
            "layers": record.layers, "naa": record.naa,
            "phases": record.phases,
            "dividers": [_factor_json(value) for value in record.dividers],
            "route_name": record.route_name,
            "status": record.status, "note": note,
        }
        self.note_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.note_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _status_widget(self, record, text, tooltip):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 1, 4, 1)
        layout.setSpacing(8)
        label = QLabel(text)
        label_font = label.font()
        label_font.setBold(True)
        label.setFont(label_font)
        label.setToolTip(tooltip)
        label.setMinimumWidth(190)
        reason_button = None
        if record.status == "rejected" and record.reason:
            reason_button = QPushButton(self._reason_summary(record.reason))
            reason_button.setObjectName("routeReasonButton")
            reason_button.setToolTip("Click to view the complete rejection reason.")
            reason_button.setStyleSheet(
                "QPushButton { color: #8a3b12; border: 0; text-align: left; "
                "padding: 2px 4px; } QPushButton:hover { color: #c14f16; "
                "text-decoration: underline; }")
            reason_button.clicked.connect(
                lambda _checked=False, reason=record.reason:
                QMessageBox.information(self, "Rejected route reason", reason))
        note_edit = QLineEdit(self.route_notes.get(self._route_key(record), ""))
        note_edit.setPlaceholderText("Add route note for Codex...")
        note_edit.setToolTip("Written immediately to pattern_rule_drafts/route_notes.jsonl")
        note_edit.textEdited.connect(
            lambda value, selected=record: self._record_route_note(selected, value))
        layout.addWidget(label)
        if reason_button is not None:
            layout.addWidget(reason_button)
        layout.addWidget(note_edit, 1)
        self.status_widgets[self._route_key(record)] = (label, note_edit)
        return container

    @staticmethod
    def _reason_summary(reason, limit=42):
        """Return a compact reason while retaining the full text on click."""
        summary = " ".join(str(reason).split())
        if len(summary) <= limit:
            return summary
        return summary[:limit - 1].rstrip() + "…"

    def _set_status_text(self, record, text, tooltip):
        key = self._route_key(record)
        pair = self.status_widgets.get(key)
        if pair is not None:
            pair[0].setText(text)
            pair[0].setToolTip(tooltip)

    @classmethod
    def _load_saved_routes(cls, folder):
        saved = {}
        if not folder.is_dir():
            return saved
        paths = sorted(folder.glob("*.json"), key=lambda item: item.stat().st_mtime)
        for path in paths:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                route = data.get("source_route")
                if data.get("save_kind") != "manual_configure" or not route:
                    continue
                key = (route["pattern"], str(route["q"]), int(route["pp"]),
                       int(route["layers"]), int(route["naa"]),
                       _factor_tuple(route["dividers"]),
                       int(route.get("phases", 3)))
                checks = data.get("completion_checks", {})
                complete = bool(
                    data.get("all_branch_counts_reached")
                    and checks.get("unique_conductor_occupancy"))
                dirty = bool(data.get("manual_edit_dirty"))
                state = "configured" if dirty and complete else "draft" if dirty else "checkpoint"
                saved[key] = (path, state)
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
                continue
        return saved

    @staticmethod
    def _saved_label(state):
        return {"configured": "Manual configured",
                "draft": "Manual draft saved",
                "checkpoint": "Production checkpoint saved"}[state]

    @staticmethod
    def _display_status(record):
        if (record.status in ("Default", "Validated")
                and "not strong symmetry layout" in record.reason):
            return f"{record.status} · not strong symmetry layout"
        return record.status

    def mark_saved(self, record, path, state):
        key = self._route_key(record)
        self.saved_routes[key] = (Path(path), state)
        for row, candidate in enumerate(self.records):
            if self._route_key(candidate) == key:
                item = self.table.item(row, 7)
                label = self._saved_label(state)
                status_text = (self._display_status(candidate)
                               if candidate.status in ("Default", "Validated",
                                                       "not strong symmetry layout")
                               else f"{label} · {candidate.status}")
                item.setData(Qt.ItemDataRole.UserRole, status_text)
                item.setToolTip(f"Saved manual configure: {path}\n{candidate.reason}")
                self._set_status_text(
                    candidate, status_text, item.toolTip())

    def refresh(self):
        try:
            self.records = build_divider_route_catalog(
                self.q_box.text().strip(), self.pp_box.value(),
                self.layers_box.value(), self.phases_box.value())
        except (ValueError, ZeroDivisionError) as exc:
            self.hint.setText(str(exc)); return
        self.table.setRowCount(len(self.records))
        self.status_widgets.clear()
        for row, record in enumerate(self.records):
            values = (record.pattern, str(record.q), str(record.pp), str(record.naa),
                      str(record.dividers), record.route_name)
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(record.reason)
                self.table.setItem(row, column, item)
            open_button = QPushButton("Open")
            open_button.setToolTip(f"Open {record.status} route in the editor")
            open_button.clicked.connect(
                lambda _checked=False, selected=record: self.open_callback(selected))
            self.table.setCellWidget(row, 6, open_button)
            status_text = self._display_status(record)
            status_item = QTableWidgetItem("")
            saved_entry = self.saved_routes.get(self._route_key(record))
            if saved_entry is not None:
                saved_path, state = saved_entry
                label = self._saved_label(state)
                status_text = (self._display_status(record)
                               if record.status in ("Default", "Validated",
                                                    "not strong symmetry layout")
                               else f"{label} · {record.status}")
                status_item.setToolTip(
                    f"Saved manual configure: {saved_path}\n{record.reason}")
            else:
                status_item.setToolTip(record.reason)
            status_item.setData(Qt.ItemDataRole.UserRole, status_text)
            self.table.setItem(row, 7, status_item)
            self.table.setCellWidget(
                row, 7, self._status_widget(
                    record, status_text, status_item.toolTip()))
            self.table.setRowHeight(row, 34)
        self.table.resizeColumnsToContents()
        self.hint.setText(
            f"{len(self.records)} routes classified for m={self.phases_box.value()} "
            "from current production code."
            if self.records else
            "No divider routes are available for these inputs.")

    def open_selected(self, *_args):
        row = self.table.currentRow()
        if row < 0:
            return
        record = self.records[row]
        self.open_callback(record)


class WorkbenchDetachedPlot(QDialog):
    """Temporary host that returns the existing workbench canvas when closed."""

    def __init__(self, owner):
        super().__init__(owner, Qt.WindowType.Window)
        self.owner = owner
        self.setWindowTitle("Pattern Rule Workbench — Detached Plot")
        self.resize(1200, 800)
        self.setMinimumSize(700, 450)
        self.content_layout = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addStretch()
        embed_button = QPushButton("Embed Plot")
        embed_button.clicked.connect(owner.embed_plot)
        header.addWidget(embed_button)
        self.content_layout.addLayout(header)

    def closeEvent(self, event):
        self.owner.embed_plot()
        event.accept()

    def reject(self):
        self.owner.embed_plot()


@dataclass(frozen=True)
class DraftStep:
    start: tuple[int, int]
    end: tuple[int, int]
    side: str
    kind: str
    pitch: int
    wave_direction: int
    direction_ok: bool
    note: str = ""


class PatternDraft:
    """One explicit branch path; no Pattern generator or electrical approval."""

    def __init__(self, slots: int, poles: int, layers: int, phase: int = 0,
                 start: tuple[int, int] = (0, 0), first_side: str = "weld",
                 shifts: tuple[int, ...] | None = None, naa: int = 1,
                 pattern: str = "BWP", source_route=None,
                 reference_constraints=None, num_phases: int = 3):
        if not supports_phase_count(num_phases):
            raise ValueError(
                "Supported phase counts are odd integers >= 3 or multiples of three.")
        self.q: Fraction = winding_q(slots, poles, num_phases)
        if layers < 2 or layers % 2:
            raise ValueError("An even layer count of at least two is required.")
        if type(phase) is not int or not 0 <= phase < num_phases:
            raise ValueError("Select a phase within the configured phase count.")
        if first_side not in ("weld", "insert"):
            raise ValueError("First connection side must be weld or insert.")
        if pattern not in PATTERNS:
            raise ValueError("Unknown Pattern draft type.")
        self.slots, self.poles, self.layers = slots, poles, layers
        self.num_phases = num_phases
        self.phase, self.first_side = phase, first_side
        self.shifts = tuple([0] * layers if shifts is None else shifts)
        self.records = phase_map(slots, poles, layers, self.shifts, num_phases)
        self.lookup = {(slot, layer): (record_phase, sign)
                       for slot, layer, record_phase, sign in self.records}
        self.phase_conductor_count = sum(p == phase for p, _ in self.lookup.values())
        if type(naa) is not int or naa <= 0 or self.phase_conductor_count % naa:
            raise ValueError("Naa must divide the phase conductor count.")
        self.naa = naa
        self.pattern = pattern
        self.source_route = source_route
        self.reference_constraints = reference_constraints or {
            "available": False, "reason": "No reference layout was supplied.", "edges": []}
        self.target_branch_count = self.phase_conductor_count // naa
        if start not in self.lookup or self.lookup[start][0] != phase:
            raise ValueError("Start conductor must belong to the selected phase.")
        self.path: list[tuple[int, int]] = [start]
        self.steps: list[DraftStep] = []
        self.wave_direction = 1
        self.notes = ""
        self.blocked: set[tuple[int, int]] = set()
        self._advance_pause = None

    @property
    def current(self) -> tuple[int, int]:
        return self.path[-1]

    @property
    def next_side(self) -> str:
        if len(self.steps) % 2 == 0:
            return self.first_side
        return "insert" if self.first_side == "weld" else "weld"

    @property
    def main_pitches(self) -> tuple[int, ...]:
        pitch = self.num_phases * self.q
        return tuple(sorted({math.floor(pitch), math.ceil(pitch)}))

    def available_conductors(self) -> list[tuple[int, int]]:
        used = set(self.path) | self.blocked
        return sorted(key for key, (phase, _) in self.lookup.items()
                      if phase == self.phase and key not in used)

    def _reference_transition(self):
        """Return the selected Pattern transition for the current conductor."""
        slot, layer = self.current
        base_slot = (slot - self.shifts[layer]) % self.slots
        reference_direction = self.reference_constraints.get('travel_direction', 1)
        if (self.reference_constraints.get('transitions')
                and self.wave_direction != reference_direction):
            # Reverse the remaining reference about the current unshifted slot.
            # Keep the existing path and other branches' shared reference intact.
            self.reference_constraints = deepcopy(self.reference_constraints)
            for edge in self.reference_constraints['transitions']:
                for endpoint in ('start', 'end'):
                    s, l = edge[endpoint]
                    edge[endpoint] = [(2*base_slot-s) % self.slots, l]
            for edge in self.reference_constraints.get('edges', []):
                edge['signed_pitch'] = -edge['signed_pitch']
            for start in self.reference_constraints.get('reference_starts', {}).values():
                start[0] = (2*base_slot-start[0]) % self.slots
            for starts in self.reference_constraints.get('reference_branch_starts', {}).values():
                for start in starts:
                    start[0] = (2*base_slot-start[0]) % self.slots
            self.reference_constraints['travel_direction'] = self.wave_direction
            self._advance_pause = None
        matches = [edge for edge in self.reference_constraints.get(
            "transitions", [])
            if tuple(edge["start"]) == (base_slot, layer)
            and edge["side"] == self.next_side]
        if len(matches) != 1:
            return None
        edge = matches[0]
        end_slot, end_layer = edge["end"]
        target = ((end_slot + self.shifts[end_layer]) % self.slots, end_layer)
        return edge, target

    def suggested_special_transition(self):
        """Describe the next explicit edge from the selected Pattern, if any."""
        if self._zpp_lane_walk_enabled():
            if self._zpp_regular_candidates():
                return None
            return self._suggest_zpp_lane_transition()
        matched = self._reference_transition()
        if matched is None:
            return None
        edge, target = matched
        if edge.get("kind", "ordinary") == "ordinary":
            return None
        if target in set(self.path) | self.blocked:
            return None
        if (self.reference_constraints.get('unaligned_start')
                and (target not in self.lookup
                     or self.lookup[target][0] != self.phase
                     or self.lookup[target][1] != -self.lookup[self.current][1]
                     or not self._preserves_unaligned_weld_direction(target))):
            return None
        return {"target": target, "kind": edge["kind"],
                "note": edge.get("note", "")}

    def _preserves_unaligned_weld_direction(self, target):
        if (not self.reference_constraints.get('unaligned_start')
                or self.next_side != 'weld'):
            return True
        value = _weld_direction(self.current, target, self.slots)
        if value is None:
            return True
        pair, direction = value
        expected = {
            tuple(item['pair']): item['direction']
            for item in self.reference_constraints.get(
                'existing_weld_directions', [])}
        for step in self.steps:
            if step.side != 'weld':
                continue
            prior = _weld_direction(step.start, step.end, self.slots)
            if prior is not None:
                prior_pair, prior_direction = prior
                if (prior_pair in expected
                        and expected[prior_pair] != prior_direction):
                    return False
                expected[prior_pair] = prior_direction
        return pair not in expected or expected[pair] == direction

    def _zpp_lane_walk_enabled(self):
        lane_walk = self.reference_constraints.get('lane_walk', {})
        return (self.pattern == 'ZPP' and lane_walk.get('available') is True
                and type(lane_walk.get('q')) is int
                and lane_walk['q'] > 0
                and type(lane_walk.get('tau')) is int
                and lane_walk['tau'] > 0)

    def _zpp_lane_index(self, key):
        lane_walk = self.reference_constraints['lane_walk']
        unshifted_slot = (key[0] - self.shifts[key[1]]) % self.slots
        return unshifted_slot % lane_walk['q']

    def _zpp_target_is_legal(self, target):
        used = set(self.path) | self.blocked
        return (target not in used and target in self.lookup
                and self.lookup[target][0] == self.phase
                and self.lookup[target][1] == -self.lookup[self.current][1]
                and self._preserves_unaligned_weld_direction(target))

    def _zpp_regular_candidates(self):
        """Follow the reference edge order, then re-anchor within the same q-lane."""
        if len(self.path) >= self.target_branch_count:
            return []
        lane = self._zpp_lane_index(self.current)
        matched = self._reference_transition()
        if matched is not None:
            edge, target = matched
            if edge.get('kind', 'ordinary') != 'ordinary':
                return []
            if (self._zpp_target_is_legal(target)
                    and self._zpp_lane_index(target) == lane):
                return [target]

        candidates = []
        slot, layer = self.current
        for edge in self.reference_constraints.get('edges', []):
            if (edge['side'] != self.next_side
                    or not edge.get('direction_ok', True)
                    or edge.get('kind', 'ordinary') != 'ordinary'):
                continue
            next_layer = layer + edge['layer_delta']
            if not 0 <= next_layer < self.layers:
                continue
            if self.next_side == 'insert':
                if next_layer != layer:
                    continue
            elif (abs(next_layer - layer) != 1
                  or next_layer // 2 != layer // 2):
                continue
            target = (shifted_connection_slot(
                edge['signed_pitch'], slot, layer, next_layer,
                self.shifts, self.slots), next_layer)
            if (self._zpp_target_is_legal(target)
                    and self._zpp_lane_index(target) == lane):
                candidates.append(target)
        return sorted(set(candidates))

    def _suggest_zpp_lane_transition(self):
        lane_walk = self.reference_constraints['lane_walk']
        q_value = lane_walk['q']
        direction = 1 if self.wave_direction >= 0 else -1
        lane = self._zpp_lane_index(self.current)
        next_lane = (lane + direction) % q_value
        if next_lane == lane:
            return None
        layer = self.current[1]
        next_layer = (layer if self.next_side == 'insert'
                      else layer + (1 if layer % 2 == 0 else -1))
        if not 0 <= next_layer < self.layers:
            return None
        lane_delta = direction
        signed_pitch = direction * lane_walk['tau'] + lane_delta
        target = (shifted_connection_slot(
            signed_pitch, self.current[0], layer, next_layer,
            self.shifts, self.slots), next_layer)
        if (self._zpp_lane_index(target) != next_lane
                or not self._zpp_target_is_legal(target)):
            return None
        source = tuple(lane_walk.get('source_dividers') or ())
        target_dividers = tuple(lane_walk.get('target_dividers') or ())
        note = (f"ZPP lane transition: Δslot=direction*(m*q)+lane_delta; "
                f"direction={direction}, m={lane_walk['phases']}, "
                f"q={q_value}, tau={lane_walk['tau']}, lane {lane}->{next_lane}; "
                f"reference {source} to target {target_dividers}.")
        return {'target': target, 'kind': 'lane_transition', 'note': note}

    def regular_candidates(self) -> list[tuple[int, int]]:
        """Follow the current Pattern's ordered route before using legacy fallback."""
        if len(self.path) >= self.target_branch_count:
            return []
        if self.pattern == 'ZPP' and self.reference_constraints.get(
                'reference_mode') == 'default_lane_walk':
            return (self._zpp_regular_candidates()
                    if self._zpp_lane_walk_enabled() else [])
        matched = self._reference_transition()
        if matched is not None:
            edge, target = matched
            if edge.get("kind", "ordinary") != "ordinary":
                if (not self.reference_constraints.get('unaligned_start')
                        or self.suggested_special_transition() is not None):
                    return []
            else:
                used = set(self.path) | self.blocked
                if (target not in used and target in self.lookup
                        and self.lookup[target][0] == self.phase
                        and self.lookup[target][1] == -self.lookup[self.current][1]
                        and self._preserves_unaligned_weld_direction(target)):
                    return [target]
                if not self.reference_constraints.get('unaligned_start'):
                    return []
        if (self.reference_constraints.get('reference_mode') == 'default_series'
                or self.reference_constraints.get('start_alignment')) and not \
                self.reference_constraints.get('unaligned_start'):
            return []
        reference_edges = [edge for edge in self.reference_constraints.get("edges", [])
                           if edge["side"] == self.next_side
                           and edge.get("direction_ok", True)
                           and edge.get("kind", "ordinary") == "ordinary"]
        if reference_edges:
            used = set(self.path) | self.blocked
            candidates = []
            slot, layer = self.current
            for edge in reference_edges:
                reference_pitch = edge["signed_pitch"]
                if (reference_pitch == 0
                        or (reference_pitch > 0) != (self.wave_direction > 0)):
                    continue
                next_layer = layer + edge["layer_delta"]
                if not 0 <= next_layer < self.layers:
                    continue
                if self.pattern == "UWP":
                    # Reference layouts contain jumpers too. Only ordinary
                    # wave edges within the current layer pair may auto-advance.
                    paired_layer = layer + 1 if layer % 2 == 0 else layer - 1
                    if (next_layer != paired_layer
                            or abs(reference_pitch) not in self.main_pitches):
                        continue
                target = (shifted_connection_slot(
                    reference_pitch, slot, layer, next_layer,
                    self.shifts, self.slots), next_layer)
                if (target not in used and target in self.lookup
                        and self.lookup[target][0] == self.phase
                        and self.lookup[target][1] == -self.lookup[self.current][1]
                        and self._preserves_unaligned_weld_direction(target)):
                    candidates.append(target)
            return sorted(set(candidates))
        if self.pattern not in ("BWP", "UWP"):
            return []
        slot, layer = self.current
        next_layer = layer + 1 if layer % 2 == 0 else layer - 1
        if next_layer >= self.layers:
            return []
        used = set(self.path) | self.blocked
        sign = self.lookup[self.current][1]
        candidates = []
        for pitch in self.main_pitches:
            target = (shifted_connection_slot(
                self.wave_direction * pitch, slot, layer, next_layer,
                self.shifts, self.slots), next_layer)
            if (target not in used and self.lookup[target] == (self.phase, -sign)):
                candidates.append(target)
        return candidates

    def _append(self, target: tuple[int, int], kind: str, note: str = "") -> None:
        if len(self.path) >= self.target_branch_count:
            raise ValueError("The target conductor count for this branch is reached.")
        if target not in self.lookup:
            raise ValueError("Target slot/layer is outside the grid.")
        if target in self.path or target in self.blocked:
            raise ValueError("Target conductor is already used by a branch.")
        if self.lookup[target][0] != self.phase:
            raise ValueError("Target conductor is outside the selected phase.")
        start = self.current
        if not self._preserves_unaligned_weld_direction(target):
            raise ValueError(
                "This exploratory weld reverses travel in an occupied layer pair.")
        delta = (target[0] - start[0]) % self.slots
        pitch = delta if delta <= self.slots // 2 else delta - self.slots
        self.steps.append(DraftStep(start, target, self.next_side, kind, pitch,
                                    self.wave_direction,
                                    self.lookup[target][1] == -self.lookup[start][1],
                                    note.strip()))
        self.path.append(target)
        self._advance_pause = None

    def add_regular(self, target: tuple[int, int]) -> None:
        if target not in self.regular_candidates():
            raise ValueError("Target is not an available ordinary Pattern step.")
        self._append(target, "regular")

    def advance_until_special(self) -> int:
        """Add one pending special edge, or ordinary edges to the next pause point."""
        added = 0
        self._advance_pause = None
        if len(self.path) >= self.target_branch_count:
            return added
        pending = self.suggested_special_transition()
        if pending is not None:
            self.add_special(pending['target'], pending['kind'], pending['note'])
            return 1
        interval = _advance_checkpoint_interval(self.pattern)
        checkpoint_reached = False
        while candidates := self.regular_candidates():
            self.add_regular(candidates[0])
            added += 1
            if (interval and len(self.path) < self.target_branch_count
                    and len(self.path) % interval == 0):
                checkpoint_reached = True
                break
        pending = self.suggested_special_transition()
        if pending is not None:
            self._advance_pause = {
                'kind': 'special', 'conductors': len(self.path),
                'current': self.current, 'target': pending['target']}
        elif checkpoint_reached:
            self._advance_pause = {
                'kind': 'checkpoint', 'conductors': len(self.path),
                'current': self.current}
        return added

    def add_special(self, target: tuple[int, int], kind: str,
                    note: str = "") -> None:
        if kind not in SPECIAL_KINDS:
            raise ValueError("Unknown special connection type.")
        self._append(target, kind, note)

    def undo(self) -> None:
        self._advance_pause = None
        if self.steps:
            self.steps.pop()
            self.path.pop()

    @staticmethod
    def _position(key: tuple[int, int]) -> dict[str, int]:
        return {"slot": key[0] + 1, "layer": key[1] + 1}

    def to_dict(self) -> dict:
        warnings = []
        if len(self.path) != self.target_branch_count:
            warnings.append("partial_branch")
        if self.reference_constraints.get('unaligned_start'):
            warnings.append("reference_inlet_not_aligned")
        if any(not step.direction_ok for step in self.steps):
            warnings.append("direction_sequence_mismatch")
        return {
            "tool": "Pattern Rule Workbench",
            "status": ("exploratory_complete_branch" if not warnings
                       else "exploratory_partial_branch"),
            "certified": False, "pattern_family": "wave",
            "pattern": self.pattern, "slots": self.slots,
            "poles": self.poles, "layers": self.layers, "q": str(self.q),
            "num_phases": self.num_phases,
            "phase": phase_label(self.phase), "phase_index": self.phase,
            "layer_shifts": list(self.shifts),
            "naa": self.naa, "target_branch_conductor_count": self.target_branch_count,
            "source_route": (None if self.source_route is None else {
                "pattern": self.source_route.pattern,
                "q": str(self.source_route.q), "pp": self.source_route.pp,
                "layers": self.source_route.layers, "slots": self.source_route.slots,
                "phases": self.source_route.phases,
                "naa": self.source_route.naa,
                "dividers": [_factor_json(value)
                             for value in self.source_route.dividers],
                "route_name": self.source_route.route_name,
                "status": self.source_route.status,
                "reason": self.source_route.reason,
            }),
            "reference_constraints": self.reference_constraints,
            "main_pitches": list(self.main_pitches),
            "first_connection_side": self.first_side,
            "current_wave_direction": self.wave_direction,
            "phase_conductor_count": self.phase_conductor_count,
            "used_conductor_count": len(self.path),
            "remaining_branch_conductor_count": self.target_branch_count - len(self.path),
            "path": [self._position(key) for key in self.path],
            "steps": [dict({"from": self._position(step.start),
                            "to": self._position(step.end), "side": step.side,
                            "kind": step.kind, "signed_pitch": step.pitch,
                            "wave_direction": step.wave_direction,
                            "direction_ok": step.direction_ok, "note": step.note})
                      for step in self.steps],
            "warnings": warnings, "designer_notes": self.notes,
        }


def _weld_direction(start, end, slots):
    """Physical left/right direction, normalized from the lower to higher layer."""
    if start[1] == end[1]:
        return None
    pitch = (end[0]-start[0]) % slots
    if 2*pitch == slots:
        raise ValueError('Weld travel is ambiguous at half a circumference.')
    if pitch > slots//2:
        pitch -= slots
    if pitch == 0:
        return None
    return (tuple(sorted((start[1], end[1]))),
            (1 if pitch > 0 else -1)*(1 if end[1] > start[1] else -1))


def _aligned_reference(source, branch, existing, check_occupancy=True):
    """Anchor an ordered reference to a new inlet without changing physical weld travel."""
    constraints = source.reference_constraints
    anchors = constraints.get('reference_branch_starts', {}).get(str(branch.phase), [])
    if not anchors:
        return constraints, source.wave_direction
    existing_directions = {}
    for other in existing:
        for step in other.steps:
            if step.side == 'weld' and (value := _weld_direction(step.start, step.end, branch.slots)):
                pair, direction = value
                if pair in existing_directions and existing_directions[pair] != direction:
                    raise ValueError('Existing branches have conflicting weld travel in one layer pair.')
                existing_directions[pair] = direction
    start = branch.path[0]
    unshifted_start = ((start[0]-branch.shifts[start[1]]) % branch.slots, start[1])
    reasons = []
    for anchor_slot, anchor_layer in anchors:
        if start[1] == anchor_layer:
            reflect = False
        elif start[1] == branch.layers-1-anchor_layer:
            reflect = True
        else:
            continue
        direction = -1 if reflect else 1
        def transform(node):
            return [(unshifted_start[0]+direction*(node[0]-anchor_slot)) % branch.slots,
                    branch.layers-1-node[1] if reflect else node[1]]
        aligned = deepcopy(constraints)
        for edge in aligned['transitions']:
            edge['start'], edge['end'] = transform(edge['start']), transform(edge['end'])
        aligned['start_alignment'] = dict(anchor=[anchor_slot, anchor_layer],
                                           inlet=list(unshifted_start), reflected=reflect)
        transitions = {(tuple(edge['start']), edge['side']): edge for edge in aligned['transitions']}
        current, side = unshifted_start, branch.first_side
        occupied = set(branch.blocked) | {start}
        directions = dict(existing_directions)
        try:
            for _ in range(branch.target_branch_count-1):
                edge = transitions.get((current, side))
                if edge is None:
                    raise ValueError('Reference ends before the target branch conductor count.')
                target = tuple(edge['end'])
                physical_start = ((current[0]+branch.shifts[current[1]]) % branch.slots, current[1])
                physical_end = ((target[0]+branch.shifts[target[1]]) % branch.slots, target[1])
                if check_occupancy and physical_end in occupied:
                    raise ValueError('Aligned reference overlaps an occupied conductor.')
                if (branch.lookup[physical_end][0] != branch.phase
                        or branch.lookup[physical_end][1] != -branch.lookup[physical_start][1]):
                    raise ValueError('Aligned reference does not preserve phase and signed direction.')
                if side == 'weld' and (value := _weld_direction(physical_start, physical_end, branch.slots)):
                    pair, weld_direction = value
                    if pair in directions and directions[pair] != weld_direction:
                        raise ValueError('Aligned reference reverses weld travel in an existing layer pair.')
                    directions[pair] = weld_direction
                occupied.add(physical_end)
                current, side = target, 'insert' if side == 'weld' else 'weld'
        except ValueError as exc:
            reasons.append(str(exc))
            continue
        aligned['travel_direction'] = direction * constraints.get('travel_direction', 1)
        return aligned, aligned['travel_direction']
    raise ValueError('Cannot align the Pattern reference to this inlet: '
                     + (reasons[0] if reasons else 'No compatible reference inlet layer.'))


class BranchDraftSet:
    """Independent same-phase branches with shared conductor occupancy."""

    def __init__(self, first: PatternDraft):
        self.branches = [first]
        self.active_index = 0

    @property
    def active(self):
        return self.branches[self.active_index]

    def select(self, index):
        if not 0 <= index < len(self.branches):
            raise ValueError("Unknown branch.")
        self.active_index = index
        for i, branch in enumerate(self.branches):
            branch.blocked = {key for j, other in enumerate(self.branches)
                              if i != j for key in other.path}
        return self.active

    def undo_active(self):
        """Undo a connection, or remove the latest branch if it has only an inlet."""
        if self.active.steps:
            self.active.undo()
            self.select(self.active_index)
            return False
        if self.active_index == len(self.branches) - 1 and self.active_index > 0:
            self.branches.pop()
            self.select(len(self.branches) - 1)
            return True
        return False

    def _new_branch(self, start, check_reference_occupancy=True,
                    allow_unaligned=False):
        source = self.branches[-1]
        if any(len(b.path) != b.target_branch_count for b in self.branches):
            raise ValueError("Please complete every existing branch first.")
        if len(self.branches) >= source.naa:
            raise ValueError("All Naa branches have already been created.")
        used = {key for branch in self.branches for key in branch.path}
        if start in used:
            raise ValueError("Start conductor is already used by a branch.")
        branch = PatternDraft(source.slots, source.poles, source.layers,
                              source.phase, start, source.first_side,
                              source.shifts, source.naa, source.pattern,
                              source.source_route, source.reference_constraints,
                              source.num_phases)
        branch.blocked = used
        if source.reference_constraints.get('available'):
            try:
                branch.reference_constraints, branch.wave_direction = _aligned_reference(
                    self.branches[0], branch, self.branches,
                    check_reference_occupancy)
            except ValueError as exc:
                zpp_manual_layer_start = (
                    branch.pattern == 'ZPP'
                    and str(exc).endswith('No compatible reference inlet layer.'))
                if (not allow_unaligned
                        or (not zpp_manual_layer_start
                            and 'does not preserve phase and signed direction.'
                            not in str(exc))):
                    raise
                directions = {}
                for other in self.branches:
                    for step in other.steps:
                        if step.side != 'weld':
                            continue
                        value = _weld_direction(step.start, step.end, source.slots)
                        if value is not None:
                            pair, direction = value
                            directions[pair] = direction
                branch.reference_constraints = deepcopy(source.reference_constraints)
                branch.reference_constraints['unaligned_start'] = {
                    'inlet': list(start), 'reason': str(exc)}
                branch.reference_constraints['existing_weld_directions'] = [
                    {'pair': list(pair), 'direction': direction}
                    for pair, direction in sorted(directions.items())]
                branch.notes = (
                    'The default reference could not be aligned to this manual '
                    'inlet. Continue as an exploratory path using '
                    'Pattern-matched ordinary edges and explicit special connections.')
        return branch

    def _commit(self, branch):
        self.branches.append(branch)
        return self.select(len(self.branches) - 1)

    def start_next(self, start):
        # A manual click places only the inlet.  Occupancy of later reference
        # endpoints is checked when those conductors are actually added.
        return self._commit(self._new_branch(
            start, check_reference_occupancy=False, allow_unaligned=True))

    def start_next_auto(self, preferred=None):
        """Commit the nearest unused inlet whose full reference can be aligned."""
        source = self.branches[-1]
        used = {key for branch in self.branches for key in branch.path}
        available = [key for key, (phase, _sign) in source.lookup.items()
                     if phase == source.phase and key not in used]
        if preferred is not None:
            preferred = tuple(preferred)
            def distance(key):
                slot_distance = min((key[0]-preferred[0]) % source.slots,
                                    (preferred[0]-key[0]) % source.slots)
                return (slot_distance + abs(key[1]-preferred[1]),
                        abs(key[1]-preferred[1]), slot_distance, key)
            available.sort(key=distance)
        else:
            available.sort()
        reasons = []
        for start in available:
            try:
                return self._commit(self._new_branch(start))
            except ValueError as exc:
                reasons.append(str(exc))
        detail = reasons[0] if reasons else "No unused conductor remains in the selected phase."
        raise ValueError("No compatible start conductor is available for the next branch: " + detail)

    def rotate_next(self, offset):
        if type(offset) is not int:
            raise ValueError("Slot offset must be an integer.")
        source = self.branches[-1]
        shifted = lambda key: ((key[0] + offset) % source.slots, key[1])
        branch = self._new_branch(shifted(source.path[0]))
        for step in source.steps:
            branch.wave_direction = step.wave_direction
            if step.kind == "regular":
                branch.add_regular(shifted(step.end))
            else:
                branch.add_special(shifted(step.end), step.kind, step.note)
        branch.wave_direction = source.wave_direction
        branch.notes = source.notes
        return self._commit(branch)


def transform_completed_branches(branch_set, shifts, tp_type="Regular",
                                 tp_interval=0, tp_times=0,
                                 source_shifts=None):
    """Return a transformed manual candidate without mutating its source.

    Layer shifts use the canonical phase-map translation. Times/Interval use
    insertion-side cuts only: Times selects exactly the requested count, while
    Interval filters its edge-index schedule. Each cut applies a workbench-only
    cumulative one-slot step in the recorded wave direction.
    This heuristic is not the generator's q-dependent phasor transposition and
    is never production certification.
    """
    branches = branch_set.branches
    if not branches or any(len(branch.path) != branch.target_branch_count
                           for branch in branches):
        raise ValueError("Every current branch must be completed before transformation.")
    first = branches[0]
    try:
        new_shifts = tuple(shifts)
        valid_shifts = (len(new_shifts) == first.layers
                        and all(type(value) is int for value in new_shifts))
    except TypeError:
        valid_shifts = False
    if not valid_shifts:
        raise ValueError("Provide one integer phase shift per layer.")
    old_shifts = tuple(first.shifts if source_shifts is None else source_shifts)
    if (len(old_shifts) != first.layers
            or any(type(value) is not int for value in old_shifts)):
        raise ValueError("Provide one integer source phase shift per layer.")
    if tp_type not in ("Regular", "Times", "Interval"):
        raise ValueError("Transposition type must be Regular, Times, or Interval.")
    edge_count = len(first.steps)
    insertion_edges = [index + 1 for index in range(edge_count)
                       if all(branch.steps[index].side == 'insert'
                              for branch in branches)]
    if tp_type == "Interval":
        if type(tp_interval) is not int or tp_interval <= 0:
            raise ValueError("Transposition interval must be greater than 0.")
        interval = tp_interval
    elif tp_type == "Times":
        if type(tp_times) is not int or tp_times <= 0:
            raise ValueError("Transposition times must be greater than 0.")
        if tp_times > len(insertion_edges):
            raise ValueError("Transposition times exceed the available insertion connections.")
        interval = None
    else:
        interval = None
    selected = ([] if interval is None else
                [index + 1 for index in range(edge_count)
                 if index % interval == interval - 1
                 and all(branch.steps[index].side == 'insert'
                         for branch in branches)])
    if tp_type == "Times":
        selected = [insertion_edges[(i * len(insertion_edges)) // (tp_times + 1)]
                    for i in range(1, tp_times + 1)]

    transformed = []
    for source in branches:
        cumulative = 0
        path = [((source.path[0][0]
                  + new_shifts[source.path[0][1]]
                  - old_shifts[source.path[0][1]]) % source.slots,
                 source.path[0][1])]
        for index, (target, step) in enumerate(zip(source.path[1:], source.steps), 1):
            if index in selected:
                cumulative += step.wave_direction
            path.append(((target[0] + new_shifts[target[1]]
                          - old_shifts[target[1]] + cumulative) % source.slots,
                         target[1]))
        draft = PatternDraft(
            source.slots, source.poles, source.layers, source.phase, path[0],
            source.first_side, new_shifts, source.naa, source.pattern,
            source.source_route, source.reference_constraints,
            source.num_phases)
        draft.path = path
        draft.steps = []
        for old_step, start, end in zip(source.steps, path, path[1:]):
            delta = (end[0] - start[0]) % source.slots
            pitch = delta if delta <= source.slots // 2 else delta - source.slots
            start_meta = draft.lookup.get(start)
            end_meta = draft.lookup.get(end)
            direction_ok = bool(start_meta and end_meta
                                and end_meta[1] == -start_meta[1])
            draft.steps.append(DraftStep(
                start, end, old_step.side, old_step.kind, pitch,
                old_step.wave_direction, direction_ok, old_step.note))
        draft.wave_direction = source.wave_direction
        draft.notes = source.notes
        transformed.append(draft)

    result = BranchDraftSet(transformed[0])
    result.branches = transformed
    result.select(min(branch_set.active_index, len(transformed) - 1))
    occupied = [key for branch in transformed for key in branch.path]
    phase_ok = all(branch.lookup.get(key, (-1, 0))[0] == branch.phase
                   for branch in transformed for key in branch.path)
    direction_ok = all(step.direction_ok for branch in transformed
                       for step in branch.steps)
    unique = len(occupied) == len(set(occupied))
    emf_values = []
    for branch in transformed:
        if not all(key in branch.lookup for key in branch.path):
            continue
        emf_values.append(sum(
            branch.lookup[key][1]
            * cmath.exp(1j * math.pi * branch.poles * key[0] / branch.slots)
            for key in branch.path))
    emf_complete = len(transformed) == first.naa and len(emf_values) == first.naa
    emf_scale = max((abs(value) for value in emf_values), default=0.0)
    emf_nonzero = emf_complete and emf_scale > 1e-12
    emf_equal = bool(emf_nonzero and all(
        abs(value - emf_values[0]) / emf_scale <= 1e-8
        for value in emf_values))
    report = {
        "status": ("phase_shift_candidate" if tp_type == "Regular" else
                   "exploratory_transposition_candidate"),
        "certified": False,
        "phase_shifts": list(new_shifts),
        "transposition": {"type": tp_type, "interval": tp_interval,
                          "times": tp_times,
                          "semantics": "manual_cumulative_slot_step_candidate"},
        "transposition_edges": selected,
        "unique_conductor_occupancy": unique,
        "phase_membership_valid": phase_ok,
        "direction_sequence_valid": direction_ok,
        "topology_candidate_valid": unique and phase_ok and direction_ok,
        "pattern_edges_validated": False,
        "parallel_emf_checked": emf_complete,
        "parallel_emf_nonzero": emf_nonzero,
        "parallel_emf_equal": emf_equal,
        "parallel_emf_diagnostic_passed": emf_equal,
        "branch_emf": [[value.real, value.imag] for value in emf_values],
        "parallel_emf_validated": False,
    }
    for branch in transformed:
        branch.transform_report = report
    return result, report


class PatternRuleWorkbench(QWidget):
    """A manual connection sketchpad that never touches production layout state."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pattern Rule Workbench — exploratory drafts")
        self.resize(1450, 850)
        self._draft_pending = False
        self._manual_edit_dirty = False
        self._transform_baseline = None
        self.transform_report = None
        self.source_route = None
        self._start_select_mode = False
        self._updating_start_position = False
        self.manual_draft_dir = MANUAL_DRAFT_DIR
        self._build_ui()
        self._new_draft()

    def _replace_branch_one_start(self, target, message):
        """Replace Branch 1's start while preserving other completed branches."""
        source = self.branch_set.branches[0]
        if target not in source.lookup or source.lookup[target][0] != source.phase:
            raise ValueError("Start conductor must belong to the selected phase.")
        occupied_by_other = {
            key for branch in self.branch_set.branches[1:] for key in branch.path}
        if target in occupied_by_other:
            raise ValueError("Start conductor is already used by another branch.")
        replacement = PatternDraft(
            source.slots, source.poles, source.layers, source.phase, target,
            source.first_side, source.shifts, source.naa, source.pattern,
            source.source_route, source.reference_constraints, source.num_phases)
        replacement.notes = source.notes
        self.branch_set.branches[0] = replacement
        self.branch_set.select(0)
        self.draft = replacement
        self._manual_edit_dirty = True
        self._draft_pending = False
        self._start_select_mode = False
        self._updating_start_position = True
        try:
            self.start_slot_box.setValue(target[0] + 1)
            self.start_layer_box.setValue(target[1] + 1)
        finally:
            self._updating_start_position = False
        self._update(message)

    def _start_position_changed(self):
        """Apply edited Branch 1 start fields after the user finishes editing."""
        if (self._updating_start_position or not hasattr(self, "draft")
                or self._draft_pending):
            return
        target = (self.start_slot_box.value() - 1,
                  self.start_layer_box.value() - 1)
        try:
            self._replace_branch_one_start(target,
                                           "Branch 1 start conductor updated.")
        except ValueError as exc:
            self.status.setText(str(exc))

    def _reset_cond1(self):
        """Reset Branch 1 to its first available phase conductor and arm plot selection."""
        if not hasattr(self, "draft"):
            return
        available = [key for key, (phase, _sign) in self.draft.lookup.items()
                     if phase == self.draft.phase and key not in {
                         used for branch in self.branch_set.branches[1:]
                         for used in branch.path}]
        if not available:
            self.status.setText("No unused conductor is available for Branch 1.")
            return
        try:
            self._replace_branch_one_start(min(available),
                                           "Branch 1 reset. Click a conductor center to choose its start.")
        except ValueError as exc:
            self.status.setText(str(exc))
            return
        self._start_select_mode = True
        self.status.setText(
            "Branch 1 reset. Click a conductor center in the selected phase to choose its start.")

    def _spin(self, minimum: int, maximum: int, value: int) -> QSpinBox:
        box = QSpinBox()
        box.setRange(minimum, maximum)
        box.setValue(value)
        return box

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        banner = QLabel(
            "Route inspection and exploratory drafts — no production-rule changes, "
            "engineering approval, or production export")
        banner.setStyleSheet("background:#fff3bf;color:#5c4400;padding:9px;font-weight:600;")
        root.addWidget(banner)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.catalog = DividerRouteCatalog(self.open_route)
        self.tabs.addTab(self.catalog, "Divider Route Catalog")
        editor = QWidget()
        self.editor_page = editor
        editor_layout = QVBoxLayout(editor)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        editor_layout.addWidget(splitter, 1)
        self.tabs.addTab(editor, "Pattern Rule Editor")
        rules_page = QWidget()
        rules_layout = QVBoxLayout(rules_page)
        rule_scope = QLabel(
            "Base-reference rules. Ordinary body pins remain ordinary, including CP cross-layer "
            "and ZPP/LPP same-layer pins. Default-branch series joins pause for other Patterns. "
            "ZPP stays in its current q-lane while an ordinary step is available; its formula-derived "
            "lane transition pauses separately and adds one edge on the next click. "
            "CP and ZPP also pause after each 4 conductors as review checkpoints.")
        rule_scope.setWordWrap(True)
        rules_layout.addWidget(rule_scope)
        self.special_rules_table = QTableWidget(0, 4)
        self.special_rules_table.setHorizontalHeaderLabels(
            ('Pattern', 'Rule / pause kind', 'Base-reference boundary', 'Endpoint / side'))
        self.special_rules_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for pattern in PATTERNS:
            rules = PATTERN_SPECIAL_RULES[pattern] or (
                dict(kind='ordinary', description='No additional body special rule; retain reference body pins'),)
            joins = (() if pattern == 'ZPP' else
                     (dict(kind='branch_join',
                           description='Default branch outlet to next same-phase inlet'),))
            for rule in (*rules, *joins):
                row = self.special_rules_table.rowCount()
                self.special_rules_table.insertRow(row)
                for col, value in enumerate((pattern, rule['kind'], rule['description'],
                                              rule.get('endpoint_rule',
                                                  'Exact ordered reference endpoint and edge side'))):
                    self.special_rules_table.setItem(row, col, QTableWidgetItem(value))
        self.special_rules_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.special_rules_table.horizontalHeader().setStretchLastSection(True)
        rules_layout.addWidget(self.special_rules_table)
        self.tabs.addTab(rules_page, 'Special Connections')

        controls = QWidget()
        control_layout = QVBoxLayout(controls)
        control_layout.setSpacing(10)
        dimensions = QGroupBox("1  Grid and starting conductor")
        form = QFormLayout(dimensions)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        self.slots_box = self._spin(3, 999, 36)
        self.poles_box = self._spin(2, 100, 8)
        self.layers_box = self._spin(2, 50, 6)
        self.naa_box = self._spin(1, 100, 1)
        self.phases_box = self._spin(3, MAX_PHASE_COUNT, 3)
        self.phases_box.setSingleStep(1)
        self.pattern_box = QComboBox()
        self.pattern_box.addItems(PATTERNS)
        self.phase_box = QComboBox()
        self.phase_box.addItems(
            tuple(f"Phase {phase_label(index)}" for index in range(3)))
        self.start_slot_box = self._spin(1, 999, 1)
        self.start_layer_box = self._spin(1, 50, 1)
        self.shifts_box = QLineEdit()
        self.shifts_box.setPlaceholderText("Blank = zero shift on every layer")
        self.side_box = QComboBox()
        self.side_box.addItems(("weld", "insert"))
        self.route_label = QLabel("Manual draft — no catalog route selected")
        self.route_label.setWordWrap(True)
        for label, widget in (("Slots", self.slots_box), ("Poles", self.poles_box),
                              ("Layers", self.layers_box), ("Naa", self.naa_box),
                              ("Phases", self.phases_box),
                              ("Pattern draft", self.pattern_box),
                              ("Phase", self.phase_box),
                              ("Start slot", self.start_slot_box),
                              ("Start layer", self.start_layer_box),
                              ("Layer shifts", self.shifts_box),
                              ("First edge side", self.side_box)):
            form.addRow(label, widget)
        form.addRow("Source route", self.route_label)
        self.production_path_button = QPushButton("Reload Public Regular Path")
        self.production_path_button.setMaximumWidth(220)
        self.production_path_button.setEnabled(False)
        self.production_path_button.clicked.connect(self._reload_production_path)
        form.addRow("", self.production_path_button)
        new_button = QPushButton("New Draft / Reset")
        new_button.setMaximumWidth(220)
        new_button.clicked.connect(self._new_draft)
        draft_actions = QHBoxLayout()
        draft_actions.addWidget(new_button)
        self.reset_cond1_button = QPushButton("Reset Cond 1")
        self.reset_cond1_button.setToolTip(
            "Reset Branch 1 and then click a conductor center in the plot to choose its start.")
        self.reset_cond1_button.clicked.connect(self._reset_cond1)
        draft_actions.addWidget(self.reset_cond1_button)
        draft_actions.addStretch()
        form.addRow(draft_actions)
        control_layout.addWidget(dimensions)

        branches = QGroupBox("Branches — independent paths")
        branch_form = QFormLayout(branches)
        branch_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        self.branch_box = QComboBox()
        self.branch_box.currentIndexChanged.connect(self._select_branch)
        branch_form.addRow("Edit branch", self.branch_box)
        self.branch_hint = QLabel()
        self.branch_hint.setWordWrap(True)
        branch_form.addRow(self.branch_hint)
        self.next_slot_box = self._spin(1, 999, 1)
        self.next_layer_box = self._spin(1, 50, 1)
        self.next_slot_box.setToolTip("Exact slot for the next branch inlet.")
        self.next_layer_box.setToolTip("Exact layer for the next branch inlet.")
        branch_form.addRow("Next start slot", self.next_slot_box)
        branch_form.addRow("Next start layer", self.next_layer_box)
        self.next_branch_button = QPushButton("Start Next Branch")
        self.next_branch_button.setMaximumWidth(220)
        self.next_branch_button.clicked.connect(self._start_next_branch)
        branch_form.addRow(self.next_branch_button)
        self.offset_box = self._spin(-999, 999, 1)
        self.offset_box.setToolTip("Signed slot offset from the last branch; wraps around Slots.")
        branch_form.addRow("Array slot offset", self.offset_box)
        self.array_button = QPushButton("Array Last Branch → Next")
        self.array_button.setMaximumWidth(220)
        self.array_button.clicked.connect(self._array_next_branch)
        branch_form.addRow(self.array_button)
        control_layout.addWidget(branches)

        transforms = QGroupBox("Phase shift and transposition candidate")
        transform_form = QFormLayout(transforms)
        transform_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        self.transform_shift_type = QComboBox()
        self.transform_shift_type.addItems(("None", "Normal", "Increment"))
        self.transform_shift = self._spin(-999, 999, 0)
        self.transform_psl = self._spin(0, 50, 1)
        self.transform_tp_type = QComboBox()
        self.transform_tp_type.addItems(("Regular", "Times", "Interval"))
        self.transform_tp_interval = self._spin(0, 999, 0)
        self.transform_tp_times = self._spin(0, 999, 0)
        self.transform_check = QLabel(
            "Complete the current manual branches to preview a candidate.")
        self.transform_check.setWordWrap(True)
        for label, widget in (
                ("Phase shift pattern", self.transform_shift_type),
                ("Slot shift", self.transform_shift),
                ("Layers per section (PSL)", self.transform_psl),
                ("Transposition type", self.transform_tp_type),
                ("T.P. interval", self.transform_tp_interval),
                ("T.P. times", self.transform_tp_times)):
            transform_form.addRow(label, widget)
        self.transform_apply_button = QPushButton("Apply / Refresh Candidate")
        self.transform_apply_button.setMaximumWidth(220)
        self.transform_apply_button.clicked.connect(self._apply_transform_candidate)
        self.transform_revert_button = QPushButton("Revert Candidate")
        self.transform_revert_button.setMaximumWidth(220)
        self.transform_revert_button.clicked.connect(self._revert_transform_candidate)
        transform_form.addRow(self.transform_apply_button)
        transform_form.addRow(self.transform_revert_button)
        transform_form.addRow(self.transform_check)
        control_layout.addWidget(transforms)

        ordinary = QGroupBox("2  Pattern-guided ordinary steps")
        ordinary_layout = QFormLayout(ordinary)
        ordinary_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        self.direction_box = QComboBox()
        self.direction_box.addItems(("Forward (+)", "Reverse (−)"))
        self.direction_box.currentIndexChanged.connect(self._refresh_candidates)
        self.candidate_box = QComboBox()
        ordinary_layout.addRow("Fallback direction", self.direction_box)
        ordinary_layout.addRow("Legal next conductor", self.candidate_box)
        self.ordinary_actions = QHBoxLayout()
        self.step_button = QPushButton("Add One Step")
        self.step_button.clicked.connect(self._add_regular)
        self.undo_button = QPushButton("Undo Step")
        self.undo_button.clicked.connect(self._undo)
        self.auto_button = QPushButton("Advance to Special")
        self.auto_button.clicked.connect(self._advance)
        self.ordinary_actions.addWidget(self.step_button)
        self.ordinary_actions.addWidget(self.undo_button)
        self.ordinary_actions.addWidget(self.auto_button)
        ordinary_layout.addRow(self.ordinary_actions)
        control_layout.addWidget(ordinary)

        special = QGroupBox("3  Explicit special connection")
        special_layout = QFormLayout(special)
        special_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        self.kind_box = QComboBox()
        for label, code in (("Jumper / layer jump", "jumper"),
                            ("Turnaround", "turnaround"),
                            ("First / last layer", "first_last_layer"),
                            ("Default branch join", "branch_join"),
                            ("Adjacent q-lane transition", "lane_transition"),
                            ("Other / custom", "custom")):
            self.kind_box.addItem(label, code)
        self.target_slot_box = self._spin(1, 999, 1)
        self.target_layer_box = self._spin(1, 50, 3)
        self.edge_note_box = QLineEdit()
        self.edge_note_box.setPlaceholderText("Why is this edge needed?")
        special_layout.addRow("Connection kind", self.kind_box)
        special_layout.addRow("Target slot", self.target_slot_box)
        special_layout.addRow("Target layer", self.target_layer_box)
        special_layout.addRow("Step note", self.edge_note_box)
        self.special_button = QPushButton("Add Special Edge")
        self.special_button.clicked.connect(self._add_special)
        special_layout.addRow(self.special_button)
        control_layout.addWidget(special)

        notes_box = QGroupBox("4  Explain your intended rule")
        notes_layout = QVBoxLayout(notes_box)
        self.notes_box = QPlainTextEdit()
        self.notes_box.setPlaceholderText("Describe jumper, turnaround, first/last-layer, or branch-group rules here.")
        self.notes_box.setMinimumHeight(95)
        notes_layout.addWidget(self.notes_box)
        control_layout.addWidget(notes_box)
        log_box = QGroupBox("Connection log")
        log_layout = QVBoxLayout(log_box)
        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(110)
        log_layout.addWidget(self.log_box)
        control_layout.addWidget(log_box)
        self.help_button = QPushButton("Help")
        self.help_button.clicked.connect(self._show_help)
        self.export_button = QPushButton("Export Rule Package")
        self.export_button.clicked.connect(self._export_dialog)
        self.save_button = QPushButton("Save Manual Configure")
        self.save_button.clicked.connect(self._save_manual_configure_clicked)
        self.copy_prompt_button = QPushButton("Copy Codex Prompt")
        self.copy_prompt_button.clicked.connect(self._copy_codex_prompt)
        control_layout.addStretch()
        compact_inputs = (
            self.slots_box, self.poles_box, self.layers_box, self.naa_box,
            self.phases_box,
            self.pattern_box, self.phase_box, self.start_slot_box,
            self.start_layer_box, self.shifts_box, self.side_box,
            self.branch_box, self.next_slot_box, self.next_layer_box,
            self.offset_box, self.direction_box, self.candidate_box,
            self.transform_shift_type, self.transform_shift,
            self.transform_psl, self.transform_tp_type,
            self.transform_tp_interval, self.transform_tp_times,
            self.kind_box, self.target_slot_box, self.target_layer_box,
            self.edge_note_box,
        )
        for widget in compact_inputs:
            widget.setMinimumWidth(135)
            widget.setMaximumWidth(205)
        self.controls_scroll = QScrollArea()
        self.controls_scroll.setWidgetResizable(True)
        self.controls_scroll.setWidget(controls)
        self.controls_scroll.setMinimumWidth(350)
        self.controls_scroll.setMaximumWidth(405)
        splitter.addWidget(self.controls_scroll)

        plot_panel = QWidget()
        self.plot_layout = QVBoxLayout(plot_panel)
        plot_actions = QHBoxLayout()
        plot_actions.addStretch()
        icon_actions = (
            (self.help_button, QStyle.StandardPixmap.SP_DialogHelpButton, "Help"),
            (self.save_button, QStyle.StandardPixmap.SP_DialogSaveButton,
             "Save Manual Configure"),
            (self.export_button, QStyle.StandardPixmap.SP_DriveHDIcon,
             "Export Rule Package"),
            (self.copy_prompt_button, QStyle.StandardPixmap.SP_FileDialogNewFolder,
             "Copy Codex Prompt"),
        )
        for button, icon, tooltip in icon_actions:
            button.setText("")
            button.setIcon(self.style().standardIcon(icon))
            button.setToolTip(tooltip)
            button.setAccessibleName(tooltip)
            button.setFixedSize(38, 32)
            plot_actions.addWidget(button)
        self.detach_button = QPushButton("Detach Plot")
        self.detach_button.clicked.connect(self.toggle_plot_window)
        self.detach_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarMaxButton))
        self.detach_button.setToolTip("Detach Plot")
        self.detach_button.setAccessibleName("Detach Plot")
        plot_actions.addWidget(self.detach_button)
        self.plot_layout.addLayout(plot_actions)
        self.figure = Figure(figsize=(13, 7.5), facecolor="#f7f8fa")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumSize(700, 450)
        self.canvas.setToolTip(
            "Click a conductor center to connect it. Legal wave targets add an ordinary "
            "step; other available conductors use the selected special connection kind.")
        self.canvas.mpl_connect("button_press_event", self._on_plot_click)
        self.plot_toolbar = NavigationToolbar2QT(self.canvas, plot_panel)
        self.plot_layout.addWidget(self.plot_toolbar)
        self.plot_layout.addWidget(self.canvas, 1)
        self.plot_placeholder = QLabel(
            "Plot is open in a separate window. Select Embed Plot to return it.")
        self.plot_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.plot_placeholder.hide()
        self.plot_layout.addWidget(self.plot_placeholder, 1)
        self.plot_window = None
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.plot_layout.addWidget(self.status)
        splitter.addWidget(plot_panel)
        splitter.setSizes([380, 1070])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        for widget in (self.slots_box, self.poles_box, self.layers_box,
                       self.naa_box):
            widget.valueChanged.connect(self._mark_pending)
        self.start_slot_box.editingFinished.connect(self._start_position_changed)
        self.start_layer_box.editingFinished.connect(self._start_position_changed)
        self.phases_box.valueChanged.connect(self._phase_count_changed)
        for widget in (self.phase_box, self.side_box, self.pattern_box):
            widget.currentIndexChanged.connect(self._mark_pending)
        self.shifts_box.textChanged.connect(self._mark_pending)
        self.notes_box.textChanged.connect(self._mark_manual_edit)
        self.transform_shift_type.currentTextChanged.connect(
            self._transform_parameters_changed)
        self.transform_tp_type.currentTextChanged.connect(
            self._transform_parameters_changed)
        for widget in (self.transform_shift, self.transform_psl,
                       self.transform_tp_interval, self.transform_tp_times):
            widget.valueChanged.connect(self._transform_parameters_changed)

    def _mark_manual_edit(self):
        if hasattr(self, "draft") and not self._draft_pending:
            self._manual_edit_dirty = True

    def _phase_count_changed(self, phases):
        current = min(self.phase_box.currentIndex(), max(0, phases - 1))
        self.phase_box.blockSignals(True)
        self.phase_box.clear()
        self.phase_box.addItems(
            tuple(f"Phase {phase_label(index)}" for index in range(phases)))
        self.phase_box.setCurrentIndex(current)
        self.phase_box.blockSignals(False)
        self._mark_pending()

    def _transform_parameters_changed(self, *_):
        if self._transform_baseline is not None:
            self._apply_transform_candidate()

    def _transform_shifts(self):
        from types import SimpleNamespace
        winding = SimpleNamespace(num_layers=self.draft.layers)
        return tuple(gw.get_phase_shift_list(
            winding, self.transform_shift_type.currentText(),
            self.transform_shift.value(), self.transform_psl.value(),
            log=lambda message: None))

    def _apply_transform_candidate(self):
        if not hasattr(self, "branch_set") or self._draft_pending:
            return
        baseline = self._transform_baseline or self.branch_set
        try:
            transformed, report = transform_completed_branches(
                baseline, self._transform_shifts(),
                self.transform_tp_type.currentText(),
                self.transform_tp_interval.value(),
                self.transform_tp_times.value())
        except (ValueError, TypeError) as exc:
            if self._transform_baseline is not None:
                self.branch_set = self._transform_baseline
                self.draft = self.branch_set.select(
                    min(self.branch_set.active_index,
                        len(self.branch_set.branches) - 1))
                self._transform_baseline = None
                self.transform_report = None
                self.notes_box.setReadOnly(False)
                self._update("Invalid transform settings; restored the completed baseline.")
            self.transform_check.setText(f"Candidate rejected: {exc}")
            return
        if self._transform_baseline is None:
            self._transform_baseline = self.branch_set
        self.branch_set = transformed
        self.draft = transformed.active
        self.transform_report = report
        self._manual_edit_dirty = True
        self.notes_box.setReadOnly(True)
        checks = (
            f"occupancy={'pass' if report['unique_conductor_occupancy'] else 'FAIL'}, "
            f"phase={'pass' if report['phase_membership_valid'] else 'FAIL'}, "
            f"direction={'pass' if report['direction_sequence_valid'] else 'FAIL'}, "
            f"parallel EMF={('pass' if report['parallel_emf_equal'] else 'FAIL') if report['parallel_emf_checked'] else 'not checked'}")
        self.transform_check.setText(
            f"{report['status']}: {checks}. Pattern-specific edges remain unvalidated.")
        self._update("Phase-shift/transposition candidate refreshed.")

    def _revert_transform_candidate(self):
        if self._transform_baseline is None:
            return
        self.branch_set = self._transform_baseline
        self.draft = self.branch_set.select(
            min(self.branch_set.active_index, len(self.branch_set.branches) - 1))
        self._transform_baseline = None
        self.transform_report = None
        self.notes_box.setReadOnly(False)
        self.transform_check.setText("Candidate reverted to the completed manual connections.")
        self._update("Transform candidate reverted.")

    def toggle_plot_window(self):
        if self.plot_window is not None and self.plot_window.isVisible():
            self.embed_plot()
            return
        if self.plot_window is None:
            self.plot_window = WorkbenchDetachedPlot(self)
        self.plot_window.content_layout.addWidget(self.plot_toolbar)
        self.plot_window.content_layout.addWidget(self.canvas, 1)
        self.plot_placeholder.show()
        self.detach_button.setText("Embed Plot")
        self.plot_window.show()
        self.plot_window.raise_()

    def embed_plot(self):
        if self.plot_window is None:
            return
        self.plot_layout.insertWidget(1, self.plot_toolbar)
        self.plot_layout.insertWidget(2, self.canvas, 1)
        self.plot_placeholder.hide()
        self.plot_window.hide()
        self.detach_button.setText("Detach Plot")

    @staticmethod
    def _linestyle_for_side(side):
        return "--" if side == "weld" else "-"

    def open_route(self, record: DividerRouteRecord) -> None:
        """Open a catalog route with its public Regular exploratory reference."""
        self.source_route = record
        self.production_path_button.setEnabled(
            record.status in ("Default", "Validated", "Candidate",
                              "not strong symmetry layout", "identity unverified"))
        self.route_label.setText(
            f"{record.status}: {record.pattern} · q={record.q} · pp={record.pp} · "
            f"Naa={record.naa} · (q-divider, pp-divider, P2)={record.dividers}"
            + (f"\nReject reason: {record.reason}" if record.status == 'rejected' else
               f"\nConfigure: {record.reason}"))
        values = ((self.slots_box, record.slots), (self.poles_box, record.pp * 2),
                  (self.layers_box, record.layers), (self.naa_box, record.naa),
                  (self.phases_box, record.phases))
        for widget, value in values:
            widget.blockSignals(True); widget.setValue(value); widget.blockSignals(False)
        self._phase_count_changed(record.phases)
        self.pattern_box.blockSignals(True)
        self.pattern_box.setCurrentText(record.pattern)
        self.pattern_box.blockSignals(False)
        self.shifts_box.blockSignals(True); self.shifts_box.clear(); self.shifts_box.blockSignals(False)
        self._new_draft()
        saved_entry = self.catalog.saved_routes.get(self.catalog._route_key(record))
        if saved_entry is not None:
            saved_path, state = saved_entry
            try:
                drafts = load_saved_route_drafts(saved_path, record)
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                self.status.setText(f"Could not restore saved manual configure: {exc}")
            else:
                self.branch_set = BranchDraftSet(drafts[0])
                self.branch_set.branches = drafts
                active_index = min(max(drafts[0].saved_active_branch, 0), len(drafts) - 1)
                self.draft = self.branch_set.select(active_index)
                self._manual_edit_dirty = drafts[0].manual_edit_dirty
                self.transform_report = drafts[0].saved_transform_report
                self._transform_baseline = None
                self.phase_box.blockSignals(True)
                self.phase_box.setCurrentIndex(self.draft.phase)
                self.phase_box.blockSignals(False)
                self.side_box.blockSignals(True)
                self.side_box.setCurrentText(self.draft.first_side)
                self.side_box.blockSignals(False)
                self.shifts_box.blockSignals(True)
                self.shifts_box.setText(",".join(map(str, self.draft.shifts)))
                self.shifts_box.blockSignals(False)
                self.notes_box.blockSignals(True)
                self.notes_box.setPlainText(self.draft.notes)
                self.notes_box.blockSignals(False)
                for widget, value in ((self.start_slot_box, self.draft.path[0][0] + 1),
                                      (self.start_layer_box, self.draft.path[0][1] + 1)):
                    widget.blockSignals(True); widget.setValue(value); widget.blockSignals(False)
                self.direction_box.blockSignals(True)
                self.direction_box.setCurrentIndex(0 if self.draft.wave_direction == 1 else 1)
                self.direction_box.blockSignals(False)
                self._update(
                    f"Restored latest saved {self.catalog._saved_label(state).lower()}: "
                    f"{saved_path.name}.")
                if self.transform_report is not None:
                    self.notes_box.setReadOnly(True)
                    self.transform_check.setText(
                        "Restored an opaque manual transform candidate. Its report is "
                        "preserved; no pre-transform baseline is available to revert.")
        elif record.status in ("Default", "Validated", "Candidate",
                                "not strong symmetry layout", "identity unverified"):
            self._load_production_route(record)
        self.tabs.setCurrentWidget(self.editor_page)

    def _load_production_route(self, record, zero_extra_transposition=True):
        try:
            drafts = generate_route_drafts(
                record, zero_extra_transposition=zero_extra_transposition)
        except (ValueError, TypeError, IndexError, ZeroDivisionError) as exc:
            self.status.setText(f"Could not load the public Regular paths: {exc}")
            return
        self.branch_set = BranchDraftSet(drafts[0])
        self.branch_set.branches = drafts
        self.draft = self.branch_set.select(0)
        self._manual_edit_dirty = False
        self._transform_baseline = None
        self.transform_report = None
        for widget, value in ((self.start_slot_box, self.draft.path[0][0] + 1),
                              (self.start_layer_box, self.draft.path[0][1] + 1)):
            widget.blockSignals(True); widget.setValue(value); widget.blockSignals(False)
        self.side_box.blockSignals(True)
        self.side_box.setCurrentText(self.draft.first_side)
        self.side_box.blockSignals(False)
        lane_walk = self.draft.reference_constraints.get('lane_walk', {})
        if zero_extra_transposition and lane_walk.get('available'):
            message = ("Exploratory ZPP zero-extra-transposition lane references loaded; "
                       "catalog admission status is unchanged.")
        elif zero_extra_transposition and lane_walk.get('reason'):
            message = ("Public Regular paths loaded as exploratory references; "
                       f"ZPP lane formula unavailable: {lane_walk['reason']}")
        elif zero_extra_transposition:
            message = ("Public Regular paths loaded as exploratory references; "
                       "catalog admission status is unchanged.")
        else:
            message = "Direct public Regular generator paths reloaded for inspection."
        self._update(message)

    def _reload_production_path(self):
        if (self.source_route is not None
                and self.source_route.status in (
                    "Default", "Validated", "Candidate",
                     "not strong symmetry layout", "identity unverified")):
            self._load_production_route(
                self.source_route, zero_extra_transposition=False)

    def _mark_pending(self) -> None:
        if not hasattr(self, "draft"):
            return
        self._draft_pending = True
        self.next_branch_button.setEnabled(False)
        self.array_button.setEnabled(False)
        self.branch_box.setEnabled(False)
        self.copy_prompt_button.setEnabled(False)
        self.status.setText("Inputs edited. Select New Draft / Reset before continuing or exporting.")
        for button in (self.step_button, self.auto_button, self.special_button,
                       self.undo_button, self.export_button, self.save_button):
            button.setEnabled(False)

    def _new_draft(self) -> None:
        try:
            layers = self.layers_box.value()
            self.start_slot_box.setMaximum(self.slots_box.value())
            self.start_layer_box.setMaximum(layers)
            if self.source_route is not None and (
                    self.source_route.pattern != self.pattern_box.currentText()
                    or self.source_route.slots != self.slots_box.value()
                    or self.source_route.pp * 2 != self.poles_box.value()
                    or self.source_route.layers != layers
                    or self.source_route.naa != self.naa_box.value()
                    or self.source_route.phases != self.phases_box.value()):
                self.source_route = None
                self.route_label.setText("Manual draft — catalog route inputs were changed")
                self.production_path_button.setEnabled(False)
            text = self.shifts_box.text().strip()
            shifts = tuple(int(part.strip()) for part in text.split(",")) if text else (0,) * layers
            constraints = extract_reference_constraints(
                self.pattern_box.currentText(),
                winding_q(self.slots_box.value(), self.poles_box.value(), self.phases_box.value()),
                self.poles_box.value(), layers, self.naa_box.value(), self.phases_box.value(),
                None if self.source_route is None else self.source_route.dividers)
            if constraints.get('reference_mode') in (
                    'default_series', 'default_lane_walk') and constraints.get('available'):
                reference_start = constraints['reference_starts'][str(self.phase_box.currentIndex())]
                self.start_slot_box.setValue((reference_start[0]+shifts[reference_start[1]]) % self.slots_box.value()+1)
                self.start_layer_box.setValue(reference_start[1]+1)
                self.side_box.setCurrentText(constraints['first_side'])
                if self.source_route is None:
                    self.route_label.setText(
                    f"Exploratory target Naa={self.naa_box.value()}; default reference "
                        f"Naa={constraints['reference_naa']}, dividers={constraints['reference_dividers']}")
                else:
                    self.route_label.setText(
                        f"Selected route Naa={self.source_route.naa}, "
                        f"dividers={self.source_route.dividers}; default reference "
                        f"Naa={constraints['reference_naa']}, "
                        f"dividers={constraints['reference_dividers']}")
            self.draft = PatternDraft(
                self.slots_box.value(), self.poles_box.value(), layers,
                phase=self.phase_box.currentIndex(),
                start=(self.start_slot_box.value() - 1,
                       self.start_layer_box.value() - 1),
                first_side=self.side_box.currentText(), shifts=shifts,
                naa=self.naa_box.value(), pattern=self.pattern_box.currentText(),
                source_route=self.source_route,
                reference_constraints=constraints,
                num_phases=self.phases_box.value())
        except (ValueError, TypeError) as exc:
            QMessageBox.warning(self, "Invalid draft parameters", str(exc))
            return
        self._draft_pending = False
        self._manual_edit_dirty = False
        self._transform_baseline = None
        self.transform_report = None
        self.branch_set = BranchDraftSet(self.draft)
        self.branch_box.setEnabled(True)
        self.next_slot_box.setMaximum(self.draft.slots)
        self.next_layer_box.setMaximum(self.draft.layers)
        for button in (self.step_button, self.auto_button, self.special_button,
                       self.undo_button, self.export_button, self.save_button):
            button.setEnabled(True)
        self.target_slot_box.setMaximum(self.draft.slots)
        self.target_layer_box.setMaximum(self.draft.layers)
        self.direction_box.setCurrentIndex(0)
        self.notes_box.clear()
        lane_walk = constraints.get('lane_walk')
        if (self.draft.pattern == 'ZPP' and lane_walk is not None
                and not lane_walk.get('available')):
            message = ("New draft. ZPP q-lane transitions are unavailable: "
                       f"{lane_walk.get('reason', 'formula domain not established.')}")
        elif self.draft.pattern == 'ZPP' and lane_walk and lane_walk.get('available'):
            message = ("New exploratory ZPP q-lane draft. Advance follows ordinary "
                       "steps in-lane and pauses before each formula transition.")
        elif not constraints.get('available'):
            message = ("New draft without a Pattern reference: "
                       f"{constraints.get('reason', 'no generatable reference.')}")
        else:
            message = "New draft. Click a conductor center or use the step controls."
        self._update(message)

    def _select_branch(self, index):
        if index < 0 or self._draft_pending:
            return
        self.draft.notes = self.notes_box.toPlainText().strip()
        self.draft = self.branch_set.select(index)
        self.direction_box.blockSignals(True)
        self.direction_box.setCurrentIndex(0 if self.draft.wave_direction == 1 else 1)
        self.direction_box.blockSignals(False)
        self.notes_box.blockSignals(True)
        self.notes_box.setPlainText(self.draft.notes)
        self.notes_box.blockSignals(False)
        self._update("Selected branch for editing.")

    def _create_next_branch(self, offset=None, start=None):
        if self._draft_pending:
            return
        self.draft.notes = self.notes_box.toPlainText().strip()
        try:
            if start is not None:
                branch = self.branch_set.start_next(start)
            elif offset is None:
                preferred = (self.next_slot_box.value() - 1,
                             self.next_layer_box.value() - 1)
                branch = self.branch_set.start_next(preferred)
            else:
                branch = self.branch_set.rotate_next(offset)
        except ValueError as exc:
            self.status.setText(str(exc))
            self.branch_hint.setText(str(exc))
            return
        self._manual_edit_dirty = True
        self.next_slot_box.setValue(branch.path[0][0] + 1)
        self.next_layer_box.setValue(branch.path[0][1] + 1)
        self._select_branch(self.branch_set.active_index)
        branch_name = f"Branch {self.branch_set.active_index + 1}"
        position = f"S{branch.path[0][0] + 1}/L{branch.path[0][1] + 1}"
        if branch.reference_constraints.get('unaligned_start'):
            message = (f"{branch_name} started at {position}. Exact reference alignment "
                       "was unavailable; continue with the Pattern-matched exploratory "
                       "steps and record special connections manually.")
        elif offset is None:
            message = f"{branch_name} started at the requested conductor {position}."
        else:
            message = f"{branch_name} start placed by array at {position}."
        self._update(message)

    def _start_next_branch(self):
        self._create_next_branch()

    def _array_next_branch(self):
        self._create_next_branch(offset=self.offset_box.value())

    def _refresh_candidates(self) -> None:
        if not hasattr(self, "draft"):
            return
        self.draft.wave_direction = 1 if self.direction_box.currentIndex() == 0 else -1
        self.candidate_box.clear()
        for target in self.draft.regular_candidates():
            delta = (target[0] - self.draft.current[0]) % self.draft.slots
            pitch = delta if delta <= self.draft.slots // 2 else delta - self.draft.slots
            base_delta = (target[0] - self.draft.current[0]
                          - self.draft.shifts[target[1]]
                          + self.draft.shifts[self.draft.current[1]]) % self.draft.slots
            base_pitch = (base_delta if base_delta <= self.draft.slots // 2
                          else base_delta - self.draft.slots)
            self.candidate_box.addItem(
                f"S{target[0] + 1}/L{target[1] + 1} · {base_pitch:+d} → {pitch:+d}",
                target)
            self.candidate_box.setItemData(
                self.candidate_box.count() - 1,
                f"Default signed pitch {base_pitch:+d}; physical pitch {pitch:+d}",
                Qt.ItemDataRole.ToolTipRole)

    def _add_regular(self) -> None:
        target = self.candidate_box.currentData()
        if target is None:
            self._update("No ordinary option remains. Choose a special edge or reverse direction.")
            return
        try:
            self.draft.add_regular(tuple(target))
        except ValueError as exc:
            QMessageBox.warning(self, "Step rejected", str(exc))
            return
        self._manual_edit_dirty = True
        self._update(f"{self.draft.pattern} ordinary step added.")

    def _advance(self) -> None:
        count = self.draft.advance_until_special()
        if count:
            self._manual_edit_dirty = True
        self._suggest_special_target()
        suggestion = self.draft.suggested_special_transition()
        pause = self.draft._advance_pause
        message = ("Target branch conductor count reached."
                   if len(self.draft.path) == self.draft.target_branch_count else
                   f"Paused before {suggestion['kind']}; click Advance again to connect only this edge."
                   if suggestion else
                   f"{self.draft.pattern} review checkpoint after {pause['conductors']} conductors; click Advance again to continue."
                   if pause and pause['kind'] == 'checkpoint' else
                   "Special connection added. Click Advance again to reach the next special connection."
                   if count == 1 and self.draft.steps[-1].kind != 'regular' else
                   self.draft.reference_constraints.get('reason', 'No reference available.')
                   if not self.draft.reference_constraints.get('available') else
                   "Reference exhausted or next endpoint unavailable; check occupancy and edge side.")
        self._update(
            f"Added {count} {self.draft.pattern} reference steps. {message}")

    def _suggest_special_target(self) -> None:
        suggestion = self.draft.suggested_special_transition()
        if suggestion is not None:
            target = suggestion["target"]
            self.target_slot_box.setValue(target[0] + 1)
            self.target_layer_box.setValue(target[1] + 1)
            index = self.kind_box.findData(suggestion["kind"])
            if index >= 0:
                self.kind_box.setCurrentIndex(index)
            self.edge_note_box.setText(suggestion["note"])
            return
        pair = self.draft.current[1] // 2
        preferred_layer = min((pair + 1) * 2, self.draft.layers - 1)
        available = self.draft.available_conductors()
        options = [key for key in available if key[1] == preferred_layer]
        if options:
            target = min(options, key=lambda key:
                         min((key[0] - self.draft.current[0]) % self.draft.slots,
                             (self.draft.current[0] - key[0]) % self.draft.slots))
            self.target_slot_box.setValue(target[0] + 1)
            self.target_layer_box.setValue(target[1] + 1)

    def _add_special(self) -> None:
        try:
            self.draft.add_special(
                (self.target_slot_box.value() - 1,
                 self.target_layer_box.value() - 1),
                self.kind_box.currentData(), self.edge_note_box.text())
        except ValueError as exc:
            QMessageBox.warning(self, "Special edge rejected", str(exc))
            return
        self._manual_edit_dirty = True
        self.edge_note_box.clear()
        self._update("Special edge added. Review its geometry and continue the draft.")

    def _on_plot_click(self, event) -> None:
        if (event.button != 1 or event.inaxes not in self.figure.axes
                or event.xdata is None or event.ydata is None):
            return
        if self._draft_pending:
            self.status.setText("Inputs edited. Select New Draft / Reset before adding a connection.")
            return
        slot = round(event.xdata) - 1
        layer = round(event.ydata) - 1
        if (abs(event.xdata - (slot + 1)) > 0.45
                or abs(event.ydata - (layer + 1)) > 0.45):
            self.status.setText(
                "Click nearer to a conductor center to select or start a branch.")
            return
        target = (slot, layer)
        if self._start_select_mode:
            try:
                self._replace_branch_one_start(
                    target, "Branch 1 start conductor selected from plot.")
            except ValueError as exc:
                self.status.setText(str(exc))
            return
        if (len(self.draft.path) == self.draft.target_branch_count
                and len(self.branch_set.branches) < self.draft.naa):
            self._create_next_branch(start=target)
            return
        if target not in self.draft.available_conductors():
            self.status.setText(
                "Select an unused conductor in the current phase and branch.")
            return
        try:
            if target in self.draft.regular_candidates():
                self.draft.add_regular(target)
                message = "Ordinary wave step added from plot."
            else:
                self.draft.add_special(target, self.kind_box.currentData(),
                                       self.edge_note_box.text())
                self.edge_note_box.clear()
                message = "Special edge added from plot."
        except ValueError as exc:
            self.status.setText(str(exc))
            return
        self._manual_edit_dirty = True
        self.target_slot_box.setValue(slot + 1)
        self.target_layer_box.setValue(layer + 1)
        self._update(message)

    def _undo(self) -> None:
        removed_start = self.branch_set.undo_active()
        if removed_start:
            self.draft = self.branch_set.active
            self.direction_box.blockSignals(True)
            self.direction_box.setCurrentIndex(0 if self.draft.wave_direction == 1 else 1)
            self.direction_box.blockSignals(False)
            self.notes_box.blockSignals(True)
            self.notes_box.setPlainText(self.draft.notes)
            self.notes_box.blockSignals(False)
        self._manual_edit_dirty = True
        self._update("Branch start removed. Select a new start conductor."
                     if removed_start else "Last step removed.")

    def _show_help(self) -> None:
        QMessageBox.information(
            self, "Pattern Rule Workbench Help",
            "This workbench records exploratory branch drafts only. It does not "
            "generate production patterns, approve EMF, or export production layouts.\n\n"
            "1  Grid and starting conductor\n"
            "Set the machine inputs, phase, first conductor, and first edge side. "
            "Use New Draft / Reset after editing these values.\n\n"
            "Branches\n"
            "Each branch has Phase Cond / Naa conductors. Once counts are reached, "
            "click the next unused start conductor or use Start Next Branch. "
            "Array Last Branch copies the last branch by a signed slot offset with "
            "ring wraparound. Occupied or wrong-phase targets are rejected. "
            "Choose Edit branch to return to a previous path. Weld-side edges are dashed, "
            "insert-side edges are solid, and "
            "colors identify branches. Count completion does not certify EMF.\n\n"
            "Phase shift and transposition candidate\n"
            "After the current branches are complete, enter the standard phase-shift "
            "pattern and Times/Interval parameters, then apply the candidate. Further "
            "parameter changes refresh from the same completed baseline, so transforms "
            "do not accumulate. Revert restores the baseline. The check reports occupancy, "
            "shifted phase membership, direction, and a parallel-EMF diagnostic when all "
            "Naa branches exist. This diagnostic is not independent engineering validation; "
            "Pattern edges remain an unvalidated candidate gate.\n\n"
            "2  Pattern-guided ordinary steps\n"
            "The legal target comes from the currently selected Pattern's existing "
            "reference route. Undo Step removes the most recent connection. Advance "
            "to Special follows that Pattern until its next explicit special edge. "
            "Click again to connect only the pending special edge. A further click advances "
            "ordinary steps to the next special connection. Unsupported "
            "formulas use the same Pattern's smallest generatable default Naa, with "
            "its branches connected in series. The target Naa remains unchanged. "
            "Later branch inlets align the reference and check physical welding direction. "
            "A manual ZPP inlet on a layer without a reference anchor remains an "
            "unaligned exploratory start; subsequent connections still require review. "
            "See Special Connections for the shared per-Pattern rules.\n\n"
            "3  Explicit special connection\n"
            "Use this section for a jumper, turnaround, first/last-layer edge, or "
            "another deliberate connection. Choose its target and record a short reason.\n\n"
            "Plot interaction\n"
            "Click an unused conductor center in the selected phase to add a connection. "
            "Legal ordinary targets use the selected Pattern; other available targets "
            "use the selected special connection kind and step note.\n\n"
            "4  Explain your intended rule\n"
            "Record the intended routing rule or any engineering question for later review.\n\n"
            "Connection log and export\n"
            "The log lists the committed path. The plot's upper-right icons provide "
            "Help, Save Manual Configure, Export Rule Package, Copy Codex Prompt, and "
            "Detach Plot. Detaching moves the same live canvas and Embed Plot returns it. "
            "Export saves the visible diagram and replayable exploratory metadata.")

    @staticmethod
    def _wrapped_connection_segments(
            start: tuple[float, float], end: tuple[float, float],
            slots: int) -> tuple[tuple[tuple[float, float], tuple[float, float]],
                                tuple[tuple[float, float], tuple[float, float]]]:
        """Split a seam-crossing line while preserving its entry angle on both sides."""
        x1, y1 = start
        x2, y2 = end
        boundary = slots + 0.5 if x2 < x1 else 0.5
        opposite = 0.5 if x2 < x1 else slots + 0.5
        first_width = abs(boundary - x1)
        second_width = abs(x2 - opposite)
        seam_fraction = first_width / (first_width + second_width)
        seam_y = y1 + (y2 - y1) * seam_fraction
        return ((x1, boundary), (y1, seam_y)), ((opposite, x2), (seam_y, y2))

    @staticmethod
    def _same_layer_connection_points(
            start: tuple[float, float], end: tuple[float, float],
            slots: int, lane: float) -> list[tuple[float, float]]:
        """Use the main renderer's periodic 90-degree same-layer route."""
        return dfig.build_unwrapped_same_layer_path(start, end, slots, lane)

    @staticmethod
    def _split_wrapped_polyline(points, slots):
        """Use the main renderer's periodic seam splitting."""
        return dfig._split_unwrapped_path(points, slots)

    @staticmethod
    def _same_layer_route_lanes(drafts):
        """Assign shared lanes from visible overlap on the unwrapped grid."""
        if not drafts:
            return {}
        first = drafts[0]
        branches = []
        for branch_id, draft in enumerate(drafts, 1):
            conductors = [
                (slot, layer, draft.lookup[(slot, layer)][1])
                for slot, layer in draft.path
            ]
            branches.append((branch_id, conductors))
        winding = SimpleNamespace(
            num_slots=first.slots, num_layers=first.layers)
        return dfig.build_unwrapped_same_layer_route_lanes(
            branches, winding, close_loop=False,
            boundary_only=False)

    def _update(self, message: str) -> None:
        self.branch_set.select(self.branch_set.active_index)
        self.branch_box.blockSignals(True)
        self.branch_box.clear()
        for i, branch in enumerate(self.branch_set.branches, 1):
            self.branch_box.addItem(f"Branch {i}: {len(branch.path)}/{branch.target_branch_count} cond")
        self.branch_box.setCurrentIndex(self.branch_set.active_index)
        self.branch_box.blockSignals(False)
        ready = all(len(b.path) == b.target_branch_count for b in self.branch_set.branches)
        more = len(self.branch_set.branches) < self.draft.naa
        occupied = [key for branch in self.branch_set.branches for key in branch.path]
        handoff_ready = (ready and not more and not self._draft_pending
                         and len(occupied) == len(set(occupied)))
        self.copy_prompt_button.setEnabled(handoff_ready)
        self.transform_apply_button.setEnabled(ready and not self._draft_pending)
        self.transform_revert_button.setEnabled(self._transform_baseline is not None)
        candidate_active = self.transform_report is not None
        self.next_branch_button.setEnabled(
            ready and more and not self._draft_pending and not candidate_active)
        self.array_button.setEnabled(
            ready and more and not self._draft_pending and not candidate_active)
        self.undo_button.setEnabled(
            (bool(self.draft.steps) or
             (self.branch_set.active_index == len(self.branch_set.branches) - 1
              and self.branch_set.active_index > 0))
            and not self._draft_pending and not candidate_active)
        self.branch_hint.setText(
            "Count reached. Click the next start conductor, or array the last branch."
            if ready and more else "All Naa branches reached their conductor counts."
            if ready else "Complete the current branches to start the next one.")
        complete = len(self.draft.path) == self.draft.target_branch_count
        for button in (self.step_button, self.auto_button, self.special_button):
            button.setEnabled(not complete and not self._draft_pending)
        self._refresh_candidates()
        self._draw()
        remaining = self.draft.target_branch_count - len(self.draft.path)
        warning = (" Direction mismatch on a proposed special edge."
                   if any(not step.direction_ok for step in self.draft.steps) else "")
        self.status.setText(
            f"{self.branch_hint.text()} {message}  Branch {self.branch_set.active_index + 1}: {len(self.draft.path)}/{self.draft.target_branch_count} "
            f"conductors (Phase {phase_label(self.draft.phase)}, Naa={self.draft.naa}); "
            f"{remaining} remain in this branch. "
            f"Next side: {self.draft.next_side}.{warning}")
        self.log_box.setPlainText("\n".join(
            f"{index:02d}  S{step.start[0] + 1}/L{step.start[1] + 1} → "
            f"S{step.end[0] + 1}/L{step.end[1] + 1}  "
            f"{step.side}  {step.kind}  pitch {step.pitch:+d}"
            + (f"  — {step.note}" if step.note else "")
            for index, step in enumerate(self.draft.steps, 1)))

    def _draw(self) -> None:
        draft = self.draft
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor("#f7f8fa")
        colors = np.zeros((draft.layers, draft.slots, 3))
        palette = tuple(
            colorsys.hsv_to_rgb(index / draft.num_phases, 0.16, 0.98)
            for index in range(draft.num_phases))
        for slot, layer, phase, _ in draft.records:
            colors[layer, slot] = palette[phase]
        ax.imshow(colors, extent=(0.5, draft.slots + 0.5,
                                  draft.layers + 0.5, 0.5), aspect="auto", alpha=0.82)
        for x in range(1, draft.slots + 1):
            ax.axvline(x + 0.5, color="#c3cad4", linewidth=0.38, zorder=1)
        for y in range(1, draft.layers + 1):
            ax.axhline(y + 0.5, color="#aeb8c6", linewidth=0.65, zorder=1)
        for slot, layer, phase, sign in draft.records:
            if phase == draft.phase:
                ax.text(slot + 1, layer + 1, "+" if sign > 0 else "−",
                        ha="center", va="center", fontsize=7, color="#58677b")
        branch_colors = ("#155eef", "#a020b0", "#008765", "#c46b00")
        same_layer_lanes = self._same_layer_route_lanes(
            self.branch_set.branches)
        for branch_number, draft in enumerate(self.branch_set.branches, 1):
            branch_color = branch_colors[(branch_number - 1) % len(branch_colors)]
            label_stride = max(1, math.ceil(max(1, len(draft.steps)) / 32))
            for index, step in enumerate(draft.steps, 1):
                x1, y1 = step.start[0] + 1, step.start[1] + 1
                x2, y2 = step.end[0] + 1, step.end[1] + 1
                color = branch_color
                style = self._linestyle_for_side(step.side)
                if y1 == y2:
                    route_lane = same_layer_lanes.get(
                        (branch_number, index - 1), dfig.SameLayerRouteLane(0, 1))
                    offset = dfig.unwrapped_same_layer_lane_offset(
                        route_lane.rank, route_lane.count)
                    lane_sign = dfig.unwrapped_same_layer_lane_sign(
                        step.start[1], draft.layers)
                    lane = y1 + lane_sign * offset
                    points = self._same_layer_connection_points(
                        (x1, y1), (x2, y2), draft.slots, lane)
                    pieces = self._split_wrapped_polyline(points, draft.slots)
                    for piece in pieces:
                        ax.plot(*zip(*piece), linestyle=style, color=color,
                                linewidth=1.75, alpha=0.92, zorder=3)
                    arrow_tail, arrow_head = dfig.unwrapped_path_arrow_segment(pieces)
                    ax.annotate("", xy=arrow_head, xytext=arrow_tail,
                                arrowprops={"arrowstyle": "->", "color": color,
                                            "lw": 1.75, "linestyle": style,
                                            "alpha": 0.92}, zorder=4)
                elif abs(x2 - x1) > draft.slots / 2:
                    first, second = self._wrapped_connection_segments(
                        (x1, y1), (x2, y2), draft.slots)
                    ax.plot(first[0], first[1],
                            linestyle=style, color=color, linewidth=1.75,
                            alpha=0.92, zorder=3)
                    ax.plot(second[0], second[1],
                            linestyle=style, color=color, linewidth=1.75,
                            alpha=0.92, zorder=3)
                    arrow_x = second[0][0] + 0.72 * (second[0][1] - second[0][0])
                    arrow_y = second[1][0] + 0.72 * (second[1][1] - second[1][0])
                    ax.annotate(
                        "", xy=(second[0][1], second[1][1]),
                        xytext=(arrow_x, arrow_y),
                        arrowprops={"arrowstyle": "->", "color": color,
                                    "lw": 1.75, "linestyle": style,
                                    "alpha": 0.92}, zorder=4)
                else:
                    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                                arrowprops={"arrowstyle": "->", "color": color,
                                            "lw": 1.75, "linestyle": style,
                                            "alpha": 0.92})
                if step.kind not in ("regular", "production"):
                    label = step.kind.replace("_", " ")
                    label_x = x2 if abs(x2 - x1) > draft.slots / 2 else (x1 + x2) / 2
                    ax.text(label_x, (y1 + y2) / 2 - 0.28, label,
                            fontsize=7, color=branch_color, ha="center",
                            bbox={"facecolor": "white", "alpha": 0.85,
                                  "edgecolor": "none", "pad": 1})
                if draft is self.draft and index % label_stride == 0:
                    ax.text(x2, y2 - 0.26, str(index + 1), ha="center", va="center",
                            fontsize=7, color=branch_color, fontweight="bold")
            start = draft.path[0]
            ax.scatter([start[0] + 1], [start[1] + 1], s=90,
                       color=branch_color, zorder=5, label=f"Branch {branch_number}")
            ax.scatter([draft.current[0] + 1], [draft.current[1] + 1], s=100,
                       facecolors="none", edgecolors=branch_color, linewidths=2, zorder=6)
        draft = self.draft
        dividers = (draft.source_route.dividers if draft.source_route is not None
                    else draft.reference_constraints.get("selected_dividers"))
        divider_label = (str(tuple(dividers)) if dividers is not None
                         else "unspecified")
        ax.legend(loc="upper right", fontsize=8, framealpha=0.92, ncols=2)
        ax.set(xlim=(0.5, draft.slots + 0.5),
               ylim=(draft.layers + 0.5, 0.5), xlabel="Slot", ylabel="Layer",
               title=(f"Exploratory {draft.pattern} · Target (q-divider, pp-divider, p2-divider)={divider_label} · Naa={draft.naa}\n"
                      f"Phase {phase_label(draft.phase)} · Branch {self.branch_set.active_index + 1}/{draft.naa} · "
                      f"q={draft.q} · {len(draft.path)}/{draft.target_branch_count} conductors"))
        tick_step = max(1, math.ceil(draft.slots / 48))
        ax.set_xticks(range(1, draft.slots + 1, tick_step))
        ax.set_yticks(range(1, draft.layers + 1))
        ax.tick_params(axis="x", labelsize=8)
        ax.tick_params(axis="y", labelsize=9)
        self.figure.subplots_adjust(left=0.065, right=0.985, top=0.86, bottom=0.11)
        self.canvas.draw_idle()

    def _package_data(self):
        complete = (len(self.branch_set.branches) == self.draft.naa
                    and all(len(b.path) == b.target_branch_count
                            for b in self.branch_set.branches))
        occupied = [key for branch in self.branch_set.branches for key in branch.path]
        data = self.draft.to_dict()
        data.update({
            "schema_version": 3,
            "certified": False,
            "manual_edit_dirty": self._manual_edit_dirty,
            "active_branch": self.branch_set.active_index + 1,
            "branches": [branch.to_dict() for branch in self.branch_set.branches],
            "created_branch_count": len(self.branch_set.branches),
            "all_branch_counts_reached": complete,
            "completion_checks": {
                "all_naa_branches_created": len(self.branch_set.branches) == self.draft.naa,
                "all_branch_quotas_reached": complete,
                "unique_conductor_occupancy": len(occupied) == len(set(occupied)),
                "inputs_current": not self._draft_pending,
                "engineering_validated": False,
            },
        })
        if self.transform_report is not None:
            data["manual_transform"] = self.transform_report
        if self.source_route is not None:
            data["route_note"] = self.catalog.route_notes.get(
                self.catalog._route_key(self.source_route), "")
        return data

    def _codex_prompt(self, json_name="the saved schema-v3 JSON rule package"):
        route = self.draft.source_route
        identity = (f"{route.pattern} q={route.q}, pp={route.pp}, layers={route.layers}, "
                    f"Naa={route.naa}, dividers={route.dividers}"
                    if route else
                    f"{self.draft.pattern} q={self.draft.q}, poles={self.draft.poles}, "
                    f"layers={self.draft.layers}, Naa={self.draft.naa}")
        package_location = str(json_name)
        return f"""# Codex handoff: generalize a Pattern divider rule

Work in `Latest_Python_Files/Version 7.6`. Load the schema-v3 rule package directly from this saved path (no manual attachment is needed):

`{package_location}`

Treat it as an exploratory, non-certified designer specification for {identity}.

Infer one general construction from all supplied branch paths and annotated special edges. Do not hard-code the current q, pp, Naa, slot count, branch ids, or individual conductor coordinates. Reject the proposal if it cannot be expressed as a general Pattern/divider rule.

Review the package `route_note` and the append-only `pattern_rule_drafts/route_notes.jsonl` log for designer decisions and rejection reasons. Treat the latest note for this exact route identity as current.

The current project already centralizes production admission in `selected_integer_divider_route()` and applies generated-layout and Pattern-identity checks after dispatch. Reuse an existing general constructor when its rule matches; otherwise add the smallest guarded construction. Do not duplicate admission logic in the UI or Workbench.

Before admitting the route, independently validate exact conductor coverage, equal branch counts, phase membership, the full ordered circumferential and radial connection directions and sides, and N-to-S terminal orientation when P2=2. Record pitch as construction data, never as a Pattern identity or route-admission whitelist. Compute and report every branch's complex EMF, but do not use EMF asymmetry alone to reject a layout or restrict the construction domain.

For an EMF-asymmetric retained layout, distinguish a proved signed-category/count-divisibility obstruction (`not strong symmetry layout`, hard no) from an unresolved configuration (`auto configure pending`). A bounded search failure is pending, not proof of impossibility. Keep these diagnostics separate from Pattern admission and candidate engineering approval.

Add focused acceptance, rejection, retention-status, and existing-route regression coverage. Keep the support matrix, rejection registry, Pattern Rule Workbench, and changelog synchronized. Preserve every current default and alternative route. The saved package is candidate evidence, not engineering approval.
"""

    def _copy_codex_prompt(self):
        if not self.copy_prompt_button.isEnabled():
            self.status.setText("Complete all Naa branches before copying the Codex handoff.")
            return
        try:
            json_path = self.save_manual_configure().resolve()
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Copy Codex Prompt failed", str(exc))
            return
        QApplication.clipboard().setText(self._codex_prompt(json_path))
        self.status.setText(
            f"Codex prompt copied; current layout saved and non-certified: {json_path.name}")

    def export_draft(self, json_path: Path, save_kind="rule_package") -> Path:
        """Save the exact visible draft and its replayable connection metadata."""
        if self._draft_pending:
            raise ValueError("Apply edited inputs with New Draft / Reset before export.")
        json_path = Path(json_path).with_suffix(".json")
        png_path = json_path.with_suffix(".png")
        self.draft.notes = self.notes_box.toPlainText().strip()
        self.figure.savefig(png_path, dpi=180, facecolor="white")
        data = self._package_data()
        data["save_kind"] = save_kind
        data["image_file"] = png_path.name
        data["handoff_file"] = json_path.with_suffix(".md").name
        json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                             encoding="utf-8")
        json_path.with_suffix(".md").write_text(
            self._codex_prompt(json_path.resolve()), encoding="utf-8")
        return png_path

    def save_manual_configure(self):
        """Save a predictably named local checkpoint without changing production rules."""
        if self._draft_pending:
            raise ValueError("Apply edited inputs with New Draft / Reset before saving.")
        self.manual_draft_dir.mkdir(parents=True, exist_ok=True)
        route = self.source_route
        dividers = route.dividers if route is not None else (1, self.draft.naa, 1)
        divider_names = tuple(str(value).replace("/", "over")
                              for value in dividers)
        q_name = str(self.draft.q).replace("/", "over")
        shifts_name = "-".join(map(str, self.draft.shifts))
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        stem = (f"{self.draft.pattern}_q-{q_name}_pp-{self.draft.poles // 2}_"
                f"L-{self.draft.layers}_Naa-{self.draft.naa}_"
                f"Q-{divider_names[0]}_PP-{divider_names[1]}_P2-{divider_names[2]}_"
                f"Ph-{phase_label(self.draft.phase)}_Side-{self.draft.first_side}_"
                f"Shifts-{shifts_name}_{timestamp}")
        json_path = self.manual_draft_dir / f"{stem}.json"
        self.export_draft(json_path, save_kind="manual_configure")
        if route is not None:
            checks = self._package_data()["completion_checks"]
            complete = bool(
                checks["all_naa_branches_created"]
                and checks["all_branch_quotas_reached"]
                and checks["unique_conductor_occupancy"])
            state = ("configured" if self._manual_edit_dirty and complete
                     else "draft" if self._manual_edit_dirty else "checkpoint")
            self.catalog.mark_saved(route, json_path, state)
        self.status.setText(
            f"Manual configure saved as {json_path.name}. Production rules are unchanged.")
        return json_path

    def _save_manual_configure_clicked(self):
        try:
            self.save_manual_configure()
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Save manual configure failed", str(exc))

    def _export_dialog(self) -> None:
        name, _ = QFileDialog.getSaveFileName(
            self, "Export pattern process draft", "pattern_process_draft.json",
            "JSON draft (*.json)")
        if name:
            try:
                image = self.export_draft(Path(name))
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, "Export failed", str(exc))
                return
            self._update(
                f"Exported {image.name}, {image.with_suffix('.json').name}, and "
                f"{image.with_suffix('.md').name}.")


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = PatternRuleWorkbench()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
