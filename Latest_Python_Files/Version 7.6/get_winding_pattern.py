# -*- coding: utf-8 -*-
"""
Created on Fri Jun 21 15:14:54 2024

@author: ezzhh5
"""
import pandas as pd
from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
from fractions import Fraction
from functools import lru_cache
from math import gcd
from types import SimpleNamespace
from phase_topology import (
    phase_map, shifted_connection_slot, supports_phase_count,
    supports_phase_layer_allocation, three_phase_set_count,
    build_winding_phase_topology,
    phase_division_feasibility, legacy_cond_info,
)
from pattern_identity import circular_travel_steps, pole_region_crossings
from explicit_connections import validate_branches, EMF_ASYMMETRY_ERRORS
from pattern_route_contract import (
    PatternRouteRule, PatternRouteDecision, PATTERN_ROUTE_RULES,
    PATTERN_DEFAULT_PIN_PROFILES, SLP_ROTATED_WELD_ROUTES,
)
from divider_connection_formulas import (
    DividerConnectionFormula, apply_route_formula, phase_set_local_dividers,
    cp_four_pass_weave, cp_parent_half_translation,
    spiral_q_pp_parent_cut, slp_q_pp_single_sector_weld_rotation,
    slp_q_pp_p2_lane_regroup, tsp_pp_p2_sector_branches,
    tsp_pp_p2_sector_residues_are_complete, tsp_q_lane_sweep_completion,
    tsp_spiral_pass_partition, tsp_spiral_pass_partition_dimensions,
    zpp_indexed_sector_stride,
)
from half_integer_q_connection_formulas import (
    build_bwp_half_integer_base_path,
    build_uwp_half_integer_p2_definition,
    transfer_uwp_half_integer_q_pp,
)
import automatic_transposition as auto_tp

_AUTO_CONFIGURATION_TOKEN = object()


# ---------------------------------------------------------------------------
# Pattern registry and public naming API
# ---------------------------------------------------------------------------
#
# Version 7.3 uses short document abbreviations as the only canonical pattern
# code. Legacy ids are accepted only as aliases for loading old inputs.

PATTERN_REGISTRY = {
    "BWP": {
        "label": "BWP",
        "full_name": "Bi-dir. Wave Pattern (BWP)",
        "code": "BWP",
        "order": 1,
        "implemented": True,
        "aliases": ["1", "wave_01", "bi-dir. wave pattern (bwp)", "bi-dir wave pattern", "bi directional wave pattern"],
    },
    "UWP": {
        "label": "UWP",
        "full_name": "Uni-dir. Wave Pattern (UWP)",
        "code": "UWP",
        "order": 2,
        "implemented": True,
        "aliases": ["2", "wave_02", "uni-dir. wave pattern (uwp)", "uni-dir wave pattern", "uni directional wave pattern"],
    },
    "SSP": {
        "label": "SSP",
        "full_name": "SL Spiral Pattern (SSP)",
        "code": "SSP",
        "order": 3,
        "implemented": True,
        "aliases": ["3", "q_03", "slsp", "sl spiral pattern (ssp)", "sl spiral pattern"],
    },
    "TSP": {
        "label": "TSP",
        "full_name": "TB Spiral Pattern (TSP)",
        "code": "TSP",
        "order": 4,
        "implemented": True,
        "aliases": ["5", "q_05", "tbsp", "tb spiral pattern (tsp)", "tb spiral pattern"],
    },
    "SLP": {
        "label": "SLP",
        "full_name": "SL Lap Pattern (SLP)",
        "code": "SLP",
        "order": 5,
        "implemented": True,
        "aliases": ["4", "q_04", "sllp", "sl lap pattern (slp)", "sl lap pattern"],
    },
    "ZLP": {
        "label": "ZLP",
        "full_name": "Z Lap Pattern (ZLP)",
        "code": "ZLP",
        "order": 6,
        "implemented": True,
        "aliases": ["6", "q_06", "z lap pattern (zlp)", "z lap pattern", "z-lap pattern"],
    },
    "CP": {
        "label": "CP",
        "full_name": "Cross-Layer Pattern (CP)",
        "code": "CP",
        "order": 7,
        "implemented": True,
        "aliases": ["7", "c_07", "cross-layer pattern (cp)", "cross layer pattern (cp)", "cross-layer pattern", "cross layer pattern"],
    },
    "ZPP": {
        "label": "ZPP",
        "full_name": "Z Parallel Pattern (ZPP)",
        "code": "ZPP",
        "order": 8,
        "implemented": True,
        "requires_weld_side_inlet": True,
        "aliases": ["8", "p_08", "z parallel pattern (zpp)", "z parallel pattern", "z-parallel pattern"],
    },
    "TLP": {
        "label": "TLP",
        "full_name": "TB Lap pattern (TLP)",
        "code": "TLP",
        "order": 9,
        "implemented": True,
        "aliases": ["9", "tb lap pattern (tlp)", "tb lap pattern", "top-bottom lap pattern", "top bottom lap pattern"],
    },
    "LPP": {
        "label": "LPP",
        "full_name": "Loop Parallel Pattern (LPP)",
        "code": "LPP",
        "order": 10,
        "implemented": True,
        "requires_weld_side_inlet": True,
        "aliases": ["10", "loop parallel pattern (lpp)", "loop parallel pattern"],
    },
}

EXTRA_PATTERN_IDS = {"manual"}


def _pattern_alias_key(value):
    return " ".join(str(value).strip().lower().replace("_", " ").split())


PATTERN_ALIASES = {}
for _pattern_id, _meta in PATTERN_REGISTRY.items():
    for _alias in (
        _pattern_id,
        _meta["label"],
        _meta["full_name"],
        _meta.get("code"),
        *_meta["aliases"],
    ):
        if _alias:
            PATTERN_ALIASES[_pattern_alias_key(_alias)] = _pattern_id


def normalize_pattern_name(pattern_name, allow_extra=True):
    """Return canonical abbreviation code for old ids, numbers, abbreviations, or full names."""
    if isinstance(pattern_name, int):
        pattern_name = str(pattern_name)
    key = _pattern_alias_key(pattern_name)
    if key in PATTERN_ALIASES:
        return PATTERN_ALIASES[key]
    extra_key = str(pattern_name).strip().lower()
    if allow_extra and extra_key in EXTRA_PATTERN_IDS:
        return extra_key
    raise PatternConfigurationError(
        "unsupported_pattern",
        f"Unsupported winding pattern '{pattern_name}'.",
    )


def get_pattern_label(pattern_name):
    """Return the short public pattern label, for example BWP or ZLP."""
    try:
        pattern_id = normalize_pattern_name(pattern_name)
    except Exception:
        pattern_id = str(pattern_name)
    return PATTERN_REGISTRY.get(pattern_id, {}).get("label", str(pattern_name))


def get_pattern_full_name(pattern_name):
    """Return the Word-document pattern name while accepting all aliases."""
    pattern_id = normalize_pattern_name(pattern_name, allow_extra=False)
    return PATTERN_REGISTRY[pattern_id]["full_name"]


def get_pattern_code(pattern_name):
    """Return the canonical abbreviation used by the registry and dispatch."""
    pattern_id = normalize_pattern_name(pattern_name, allow_extra=True)
    if pattern_id in EXTRA_PATTERN_IDS:
        return pattern_id
    return PATTERN_REGISTRY[pattern_id].get("code")


def is_pattern_implemented(pattern_name):
    pattern_id = normalize_pattern_name(pattern_name, allow_extra=False)
    return bool(PATTERN_REGISTRY[pattern_id].get("implemented", True))

def pattern_requires_weld_side_inlet(pattern_name):
    pattern_id = normalize_pattern_name(pattern_name, allow_extra=False)
    return bool(PATTERN_REGISTRY[pattern_id].get("requires_weld_side_inlet", False))


def get_available_patterns(include_unimplemented=False):
    """Return selectable pattern abbreviations; hidden unfinished patterns are opt-in."""
    ordered = sorted(PATTERN_REGISTRY.values(), key=lambda meta: meta.get("order", 999))
    return [
        meta["label"]
        for meta in ordered
        if include_unimplemented or meta.get("implemented", True)
    ]


class PatternConfigurationError(ValueError):
    """Raised when a winding pattern cannot support the requested parameters."""

    def __init__(self, category, message, pattern_name=None):
        self.category = category
        self.pattern_name = pattern_name
        prefix = f"[{category}] "
        if pattern_name:
            prefix += f"{get_pattern_label(pattern_name)}: "
        super().__init__(prefix + message)


def _raise_pattern_error(category, message, pattern_name):
    raise PatternConfigurationError(category, message, pattern_name)


def can_phase_division(slots, poles, m):
    """Compatibility wrapper for phase-count feasibility without layer data."""
    result = phase_division_feasibility(slots, poles, None, m)
    q_fraction = ((result.q.numerator, result.q.denominator)
                  if result.q is not None else (0, 1))
    return result.feasible, q_fraction, result.repeating_pole_unit


def get_cond_info_df(Connection):
    connections_data = []
    for c in Connection:
        if len(c) == 3:  # check if c is a sublist
            if isinstance(c[0], str):
                direction = c[0]
            else:
                direction = 'F' if c[0] == 1 else 'B'
            ltp = c[1]
            connections_data.append({'num_cond': 2, 'direction': direction, 'ltp': ltp, 'ptp': c[2]})
        elif isinstance(c, int):  # if c is a single integer
            connections_data.append(c)
    connections_df = pd.DataFrame(connections_data)
    return (connections_df)

def get_seq_connection(start_conductor_id, num_cond, Winding_Para, Layout_Para, direction, ltp, ptp='none', CW=1):
    q = Winding_Para.q
    num_phases = Winding_Para.num_phases
    num_layers = Winding_Para.num_layers
    num_slots = Winding_Para.num_slots
    phase_shift_list = getattr(Layout_Para, "phase_shift_list", None)
    if phase_shift_list is None:
        phase_shift_list = get_phase_shift_list(
            Winding_Para,
            getattr(Layout_Para, "phase_shift_pattern", "Normal"),
            getattr(Layout_Para, "phase_shift", 1),
            getattr(Layout_Para, "PSL", 1),
        )
    
    if isinstance(q,int):
        num_phasor = q
    else:
        num_phasor = int(q*num_phases*2)
    group_conductors_id = []
    start_slot, start_layer, start_phasor = start_conductor_id
                 
    for i in range(num_cond):
        group_conductors_id.append(start_conductor_id)
        if direction == 'F' or direction == 1:
            jump_signal = 1
        elif direction == 'B' or direction == -1:
            jump_signal = -1
        
        regular_tp = int(q*num_phases) ### this without signal
        slot_jump = jump_signal * regular_tp
        if ptp == 'none' or ptp == 0: #### uniform is the short pitch int(q*num_phases)
            end_phasor = (start_phasor + jump_signal*regular_tp) % num_phasor
            # Update start_phasor for the next iteration
            start_phasor = end_phasor
        elif ptp != 'none' and isinstance(ptp, int) == True:
            regular_tp += ptp  ### this without signal
            end_phasor = (start_phasor + jump_signal*regular_tp) % num_phasor
            if isinstance(q, int):
                jump_tp = end_phasor - start_phasor
                slot_jump += jump_tp 
            else:
                slot_jump += jump_signal * ptp
            # Update start_phasor for the next iteration
            start_phasor = end_phasor
        end_slot = (start_slot + slot_jump) % num_slots
        if ltp == 'wave':
            end_layer = start_layer + 1 if start_layer % 2 == 0 else start_layer - 1
        elif ltp == 'parallel':
            end_layer = start_layer
        elif ltp == 'jumper':
            end_layer = start_layer - 1 if start_layer % 2 == 0 else start_layer + 1
        else:
            end_layer = start_layer + ltp
        
        ##### modify the conductor ID according to the phase shift list
        end_slot = shifted_connection_slot(slot_jump, start_slot, start_layer, end_layer, phase_shift_list, num_slots)
        
        if Layout_Para.radial_shift == 1:  ##### modify the conductor ID according to the radial shift region
            rsr_start_slot = 0
            rsr_end_slot = num_phases * q
            if end_layer in range(1, num_layers - 1) and end_slot in range(rsr_start_slot, rsr_end_slot):
                if end_layer % 2 == 1:
                    end_layer = (end_layer+1) % num_layers
                elif end_layer % 2 == 0 and end_layer != 0:
                    end_layer -= 1 
        # Update start_slot and start_layer for the next iteration
        start_slot, start_layer = end_slot, end_layer
        start_conductor_id = (start_slot, start_layer,start_phasor)
    return start_conductor_id,group_conductors_id

def get_next_conductor_id(start_conductor_id, Winding_Para, Layout_Para, direction, ltp, ptp='none'):
    q = Winding_Para.q
    num_phases = Winding_Para.num_phases
    num_layers = Winding_Para.num_layers
    num_slots = Winding_Para.num_slots
    phase_shift_list = Layout_Para.phase_shift_list
    
    if isinstance(q,int):
        num_phasor = q
    else:
        num_phasor = int(q*num_phases*2)
    start_slot, start_layer, start_phasor = start_conductor_id
    if direction == 1:
        jump_signal = 1
    elif direction == -1:
        jump_signal = -1
    regular_tp = int(q*num_phases) ### this without signal
    slot_jump = jump_signal * regular_tp
    if ptp == 0: #### uniform is the short pitch int(q*num_phases)
        end_phasor = (start_phasor + jump_signal*regular_tp) % num_phasor
        # Update start_phasor for the next iteration
        start_phasor = end_phasor
    elif ptp != 'none' and isinstance(ptp, int) == True:
        regular_tp += ptp  ### this without signal
        end_phasor = (start_phasor + jump_signal*regular_tp) % num_phasor
        if isinstance(q, int):
            jump_tp = end_phasor - start_phasor
            slot_jump += jump_tp 
        else:
            slot_jump += jump_signal * ptp
        # Update start_phasor for the next iteration
        start_phasor = end_phasor
    end_slot = (start_slot + slot_jump) % num_slots
    end_layer = start_layer + ltp
    
    ##### modify the conductor ID according to the phase shift list
    end_slot = shifted_connection_slot(slot_jump, start_slot, start_layer, end_layer, phase_shift_list, num_slots)
    
    if Layout_Para.radial_shift == 1:  ##### modify the conductor ID according to the radial shift region
        rsr_start_slot = 0
        rsr_end_slot = num_phases * q
        if end_layer in range(1, num_layers - 1) and end_slot in range(rsr_start_slot, rsr_end_slot):
            if end_layer % 2 == 1:
                end_layer = (end_layer+1) % num_layers
            elif end_layer % 2 == 0 and end_layer != 0:
                end_layer -= 1 
    # Update start_slot and start_layer for the next iteration
    end_conductor_id = (end_slot,end_layer,end_phasor)
    return end_conductor_id

def TP_modi(TP_info,Connection, *, preserve_offsets=False):
    if TP_info.tp_type == 'Times' or TP_info.tp_type == 'Interval':
        Update_Connection = []
        tp_start_index = getattr(TP_info, 'tp_start_index', 0)
        if TP_info.tp_type == 'Times':
            if TP_info.tp_times <= 0:
                raise ValueError("Times transposition requires tp_times > 0.")
            tp_interval = int((len(Connection)+1)/(TP_info.tp_times+1))
        if TP_info.tp_type == 'Interval':
            tp_interval = TP_info.tp_interval
        if tp_interval <= 0:
            raise ValueError("Transposition interval must be greater than 0.")
        for i in range(len(Connection)):
            direction, layer_change, phasor_change = Connection[i]
            if (i % tp_interval) == (tp_interval - 1- tp_start_index):
                Update_Connection.append([direction, layer_change, 1])
            else:
                Update_Connection.append([
                    direction, layer_change,
                    phasor_change if preserve_offsets else 0])
        Connection = Update_Connection

    return Connection

def Inlet_modi(Layout_Para,Connection,start_conn,start_conductor_ids,Winding_Para):
    import get_winding_pattern as gw
    if Layout_Para.inlet_from_weld_side == 1:
        direction = start_conn[0]
        ltp = start_conn[1]
        ptp = start_conn[2] if len(start_conn) > 2 else 'none'
        num_cond = 2
        for index, start_conductor_id in enumerate(start_conductor_ids):
            startid,groupid = gw.get_seq_connection(start_conductor_id, num_cond, Winding_Para, Layout_Para, direction, ltp, ptp=ptp, CW=1)
            start_conductor_ids[index] = groupid[1]  # Update 
    return (start_conductor_ids)

def _candidate_ptp_values(Winding_Para):
    limit = max(int(getattr(Winding_Para, "num_slots", 0)), int(getattr(Winding_Para, "q", 1)) * getattr(Winding_Para, "num_phases", 3) * 2)
    values = list(range(-limit, limit + 1))
    return sorted(values, key=lambda value: (abs(value), value))

def find_single_connection_between(start_conductor_id, target_conductor_id, Winding_Para, Layout_Para):
    """Find one connection vector that maps start_conductor_id to target_conductor_id."""
    layer_change = target_conductor_id[1] - start_conductor_id[1]
    for direction in (1, -1):
        for ptp in _candidate_ptp_values(Winding_Para):
            try:
                end_conductor_id = get_next_conductor_id(
                    start_conductor_id,
                    Winding_Para,
                    Layout_Para,
                    direction,
                    layer_change,
                    ptp,
                )
            except (IndexError, TypeError, ValueError):
                continue
            if end_conductor_id == target_conductor_id:
                return [direction, layer_change, ptp]
    raise ValueError(f"Cannot connect {start_conductor_id} to {target_conductor_id} with a single generated connection.")

def shift_inlet_to_weld_side(Connection, start_conductor_ids, Winding_Para, Layout_Para):
    """Move the branch start to the first weld-side conductor while preserving conductor coverage."""
    if getattr(Layout_Para, "inlet_from_weld_side", 0) != 1:
        return Connection, start_conductor_ids
    if not Connection:
        return Connection, start_conductor_ids

    source_connection = [list(conn) for conn in Connection]
    first_connection = source_connection[0]
    old_start_conductor_id = start_conductor_ids[0]
    old_end_conductor_id, _ = get_branch_connections(old_start_conductor_id, source_connection, Winding_Para, Layout_Para)
    end_to_old_start = find_single_connection_between(
        old_end_conductor_id,
        old_start_conductor_id,
        Winding_Para,
        Layout_Para,
    )
    shifted_connection = source_connection[1:] + [end_to_old_start]
    shifted_start_ids = Inlet_modi(Layout_Para, shifted_connection, first_connection, start_conductor_ids, Winding_Para)
    return shifted_connection, shifted_start_ids

def shift_inlet_to_weld_side_or_rotate_later(Connection, start_conductor_ids, Winding_Para, Layout_Para):
    try:
        shifted_connection, shifted_start_ids = shift_inlet_to_weld_side(
            Connection,
            start_conductor_ids,
            Winding_Para,
            Layout_Para,
        )
        return shifted_connection, shifted_start_ids, False
    except ValueError:
        return Connection, start_conductor_ids, True

def rotate_db_conductor_ids_to_weld_inlet(db_conductor_id):
    """Rotate generated conductor sequences when a pattern cannot express the closing step as one connection vector."""
    rotated_start_ids = []
    rotated_db = []
    for branch_number, conductors in db_conductor_id:
        if len(conductors) > 1:
            rotated_conductors = conductors[1:] + conductors[:1]
        else:
            rotated_conductors = conductors
        rotated_start_ids.append(rotated_conductors[0])
        rotated_db.append([branch_number, rotated_conductors])
    return rotated_start_ids, rotated_db

def reverse_connection(conn_list):
    #### This is to allow the end connection that can connect two branches to form one
    reversed_conn = []
    for a, b, c in reversed(conn_list):
        new_a = -a
        new_b = -b
        new_c = c
        reversed_conn.append([new_a, new_b, new_c])
    return reversed_conn

def divisors(n: int):
    """Return all positive divisors of n."""
    divs = {1}
    for i in range(2, int(n ** 0.5) + 1):
        if n % i == 0:
            divs.add(i)
            divs.add(n // i)
    divs.add(n)
    return sorted(divs)


# ---------------------------------------------------------------------------
# Branch decomposition
# ---------------------------------------------------------------------------

def classify_branch_mode(ab: int, q: int, poles: int, pattern='BWP'):
    if Fraction(str(q)).denominator != 1:
        raise ValueError('Fractional-q branch decomposition is not implemented; phase division is available separately.')
    """
    Classify how the number of parallel branches (ab) is formed
    from factors of q (slots per pole per phase),
    pp (pole-pairs), and p2 (the extra factor 2 from pp to poles).

    Pattern names in this function are the Version 7.3 public abbreviations
    from the Word pattern list:
      BWP: Bi-dir. Wave Pattern
      UWP: Uni-dir. Wave Pattern
      SSP: SL Spiral Pattern
      TSP: TB Spiral Pattern
      SLP: SL Lap Pattern
      ZLP: Z Lap Pattern
      CP:  Cross-Layer Pattern
      ZPP: Z Parallel Pattern
      TLP: TB Lap pattern, the top-bottom lap-family counterpart of TSP
      LPP: Loop Parallel Pattern, the loop-family counterpart of ZPP

    Branch-factor extraction priority:
      BWP, SSP, SLP, ZPP: q -> pp -> p2
      UWP:                p2 -> pp -> q
      TSP, TLP, CP:       p2 -> q -> pp
      ZLP:                pp -> p2 -> q
      LPP:                pp -> p2, with no q divider
    
    This function decomposes:
        ab = q_divider * pp_divider * p2_divider

    Parameters
    ----------
    ab : int
        Number of parallel branches.
    q : int
        Slots per pole per phase.
    poles : int
        Total number of poles.

    Returns
    -------
    mode_name : str
        One of: 'q_only', 'pp_only', 'p2_only', 'q_and_pp',
                 'q_and_p2', 'pp_and_p2', 'q_pp_p2', or 'unsupported'.
    q_divider : int
        Portion of ab contributed by q factors.
    pp_divider : int
        Portion of ab contributed by pole-pair factors.
    p2_divider : int
        Portion of ab contributed by the extra 2 (poles vs pole-pairs).
    """

    pattern = normalize_pattern_name(pattern, allow_extra=False)
    if not is_pattern_implemented(pattern):
        _raise_pattern_error(
            "pattern_not_implemented",
            "this Word pattern has no branch-decomposition rule because no generation algorithm is implemented yet.",
            pattern,
        )

    extraction_priority_by_pattern = {
        "BWP": ("q", "pp", "p2"),
        "UWP": ("p2", "pp", "q"),
        "SSP": ("q", "pp", "p2"),
        "TSP": ("p2", "q", "pp"),
        "SLP": ("q", "pp", "p2"),
        "ZLP": ("pp", "p2", "q"),
        "CP": ("p2", "q", "pp"),
        "ZPP": ("q", "pp", "p2"),
        "TLP": ("p2", "q", "pp"),
        "LPP": ("pp", "p2"),
    }
    if pattern not in extraction_priority_by_pattern:
        _raise_pattern_error(
            "unsupported_pattern",
            f"'{pattern}' is not one of the implemented pattern abbreviations.",
            pattern,
        )
    pp = poles // 2

    # --- Precompute factors ---
    q_factors = divisors(q)
    pp_factors = divisors(pp)
    all_ab_list = sorted({
        qf * ppf * p2f
        for qf in q_factors
        for ppf in pp_factors
        for p2f in (1, 2)
    })

    extract_order = extraction_priority_by_pattern[pattern]

    # Track remaining and dividers
    remaining = ab
    q_divider = 1
    pp_divider = 1
    p2_divider = 1

    # Use local copies so we don't conceptually "overdraw" factor powers
    q_left = q
    pp_left = pp

    def extract_q():
        nonlocal remaining, q_divider, q_left
        # skip 1; factors list should be ascending
        for f in q_factors[1:]:
            while remaining % f == 0 and q_left % f == 0:
                q_divider *= f
                remaining //= f
                q_left //= f

    def extract_pp():
        nonlocal remaining, pp_divider, pp_left
        for f in pp_factors[1:]:
            while remaining % f == 0 and pp_left % f == 0:
                pp_divider *= f
                remaining //= f
                pp_left //= f

    def extract_p2():
        nonlocal remaining, p2_divider
        if remaining % 2 == 0:
            p2_divider = 2
            remaining //= 2

    # Execute in chosen priority
    for key in extract_order:
        if key == 'q':
            extract_q()
        elif key == 'pp':
            extract_pp()
        elif key == 'p2':
            extract_p2()

    if remaining != 1:
        return "unsupported", q_divider, pp_divider, p2_divider, all_ab_list

    has_q = q_divider > 1
    has_pp = pp_divider > 1
    has_p2 = p2_divider > 1

    if has_q and not has_pp and not has_p2:
        mode_name = "q_only"
    elif not has_q and has_pp and not has_p2:
        mode_name = "pp_only"
    elif not has_q and not has_pp and has_p2:
        mode_name = "p2_only"
    elif has_q and has_pp and not has_p2:
        mode_name = "q_and_pp"
    elif has_q and has_p2 and not has_pp:
        mode_name = "q_and_p2"
    elif not has_q and has_pp and has_p2:
        mode_name = "pp_and_p2"
    elif has_q and has_pp and has_p2:
        mode_name = "q_pp_p2"
    else:
        mode_name = "q_only" if ab == 1 else "unsupported"

    return mode_name, q_divider, pp_divider, p2_divider, all_ab_list


def supports_integer_pp_only(pattern, q, poles, layers, phases, ab):
    """Recognize PP-only routes with a construction and validation rule."""
    if (type(q) is not int or q <= 0 or poles <= 0 or poles % 2
            or layers <= 0 or not supports_phase_count(phases) or ab <= 1
            or (poles // 2) % ab):
        return False
    if pattern == 'SSP':
        return True
    if pattern == 'SLP':
        return True
    if pattern == 'UWP' and layers >= 2 and layers % 2 == 0:
        pp = poles // 2
        factor_route = (ab == 2 or (ab % 2 == 0 and pp // ab >= 2)
                        or (q == 1 and pp % 2 == 0 and ab == pp))
        return factor_route
    return False


def _validate_selected_electrical(label, database, winding, layout):
    """Apply the same independent electrical check to every selected route."""
    records = phase_map(winding.num_slots, winding.num_poles,
                        winding.num_layers, layout.phase_shift_list,
                        winding.num_phases)
    report = validate_branches([branch[1] for branch in database], records,
                               winding.num_slots, winding.num_poles,
                               winding.ab, winding.num_phases)
    if not report['layout_retained']:
        raise ValueError(f'{label} branches fail electrical validation: '
                         + ', '.join(report['errors']))


def orient_p2_branches_n_to_s(database, winding, layout):
    """Orient every P2 branch from its N-pole inlet to its S-pole outlet.

    The shifted phase map is the single pole-region oracle, so N/S membership
    follows q, phase count, and each layer's phase shift. Reversing the stored
    conductor path is the model operation: downstream start IDs, conductor
    indices, drawings, and exports must all observe the same terminal direction.
    """
    pole_sign = {
        (slot, layer): sign
        for slot, layer, _phase, sign in phase_map(
            winding.num_slots, winding.num_poles, winding.num_layers,
            layout.phase_shift_list, winding.num_phases)
    }
    recorded = getattr(database, 'signed_travel', None)
    travel = dict(recorded) if isinstance(recorded, Mapping) else None

    for branch_id, path in database:
        if not path:
            raise ValueError(f'P2 branch {branch_id} has no conductors.')
        inlet_sign = pole_sign[path[0][:2]]
        outlet_sign = pole_sign[path[-1][:2]]
        if (inlet_sign, outlet_sign) == (-1, 1):
            path.reverse()
            if travel is not None:
                steps = travel[branch_id]
                if len(steps) != len(path) - 1:
                    raise ValueError('P2 signed travel has incomplete branch evidence.')
                travel[branch_id] = tuple(-step for step in reversed(steps))
            inlet_sign, outlet_sign = 1, -1
        if (inlet_sign, outlet_sign) != (1, -1):
            raise ValueError(
                f'P2 branch {branch_id} terminals do not span an N-to-S pole pair.')
    if travel is not None:
        database.signed_travel = travel
    return [path[0] for _branch_id, path in database], database


def uses_p2_divider(pattern, winding):
    """Return whether the explicit or derived decomposition uses P2=2."""
    selected = getattr(winding, 'branch_dividers', None)
    try:
        if selected is not None and len(selected) == 3:
            return Fraction(str(selected[2])) == 2
    except (TypeError, ValueError, ZeroDivisionError):
        return False
    if Fraction(str(winding.q)).denominator != 1:
        return False
    return classify_branch_mode(
        winding.ab, winding.q, winding.num_poles, pattern)[3] == 2


def validate_pp_only_spiral(pattern, database, winding, layout, topology=None):
    """Check phase retention and spiral connection roles without pitch limits."""
    topology = topology or _phase_topology_for_winding(winding, layout)
    if topology.phase_model == 'arrayed_three_phase_sets':
        for local_database, local_winding, local_layout in _three_phase_set_views(
                database, winding, layout, topology):
            validate_pp_only_spiral(
                pattern, local_database, local_winding, local_layout)
        return
    _validate_selected_electrical(f'{pattern} PP-only', database, winding, layout)
    insert_parity = 0 if layout.inlet_from_weld_side else 1
    odd_layer_group = winding.num_layers % 2 == 1
    for _, path in database:
        for index, (start, end) in enumerate(zip(path, path[1:])):
            layer_step = end[1] - start[1]
            boundary_return = (layer_step == 0
                               and (odd_layer_group or index % 2 == insert_parity)
                               and start[1] in (0, winding.num_layers - 1))
            if not (abs(layer_step) == 1 or boundary_return):
                raise ValueError(f'{pattern} PP-only branch has an invalid edge.')


def _connection_travel_steps(database, branch_id, index, start, end,
                             slots, shifts=None):
    """Use complete constructor evidence, or infer the shortest circular arc."""
    recorded = getattr(database, 'signed_travel', None)
    if recorded is not None:
        steps = recorded.get(branch_id) if isinstance(recorded, Mapping) else None
        if (not isinstance(steps, (tuple, list)) or len(steps) <= index
                or type(steps[index]) is not int or not steps[index]
                or (steps[index] - end[0] + start[0]) % slots):
            raise ValueError('Signed travel evidence does not match its edge.')
        step = steps[index]
        if shifts is not None:
            step -= shifts[end[1]] - shifts[start[1]]
        return (step,)
    start_slot, end_slot = start[0], end[0]
    if shifts is not None:
        start_slot -= shifts[start[1]]
        end_slot -= shifts[end[1]]
    return circular_travel_steps(start_slot, end_slot, slots)


def _slp_factor_edge_error(path, winding, layout, database=None, branch_id=None):
    """Check the physical SLP pass/return grammar, independent of draft labels."""
    slots = winding.num_slots
    previous_signs = None
    previous_layer_step = None
    first_weld = not bool(layout.inlet_from_weld_side)
    for index, (start, end) in enumerate(zip(path, path[1:])):
        steps = _connection_travel_steps(database, branch_id, index,
                                         start, end, slots)
        signs = {1 if step > 0 else -1 for step in steps if step}
        layer_step = end[1] - start[1]
        weld = first_weld == (index % 2 == 0)
        if layer_step == 0:
            if (weld and winding.num_layers % 2 == 0
                    or start[1] not in (0, winding.num_layers - 1)
                    or not signs):
                return 'SLP boundary return has the wrong side, layer, or direction.'
            previous_signs = previous_layer_step = None
        elif (abs(layer_step) != 1 or not signs
              or (previous_layer_step is not None
                  and (layer_step != previous_layer_step
                       or not signs.intersection(
                           {-sign for sign in previous_signs})))):
            return 'SLP ordinary lap pass changes layer or circumferential direction order.'
        else:
            previous_signs = (signs if previous_signs is None else
                              signs.intersection({-sign for sign in previous_signs}))
            previous_layer_step = layer_step
    return None


def validate_slp_factor_route(database, winding, layout):
    """Validate retained SLP factor paths and uniform physical weld travel."""
    _validate_selected_electrical('SLP factor route', database, winding, layout)
    weld_directions = {}
    first_weld = not bool(layout.inlet_from_weld_side)
    for branch_id, path in database:
        error = _slp_factor_edge_error(path, winding, layout,
                                       database, branch_id)
        if error:
            raise ValueError(error)
        for index, (start, end) in enumerate(zip(path, path[1:])):
            if first_weld != (index % 2 == 0):
                continue
            layer_step = end[1] - start[1]
            if abs(layer_step) != 1:
                continue
            steps = _connection_travel_steps(database, branch_id, index,
                                             start, end, winding.num_slots)
            pair = min(start[1], end[1]) // 2
            choices = {(1 if step * layer_step > 0 else -1) for step in steps}
            shared = choices & weld_directions.get(pair, {-1, 1})
            if not shared:
                raise ValueError('SLP welds reverse travel within one layer pair.')
            weld_directions[pair] = shared


def validate_slp_q_pp_p2_parent_cut(database, winding, layout):
    """Validate the proper-Q lane cohorts produced by the SLP P2 cut."""
    validate_slp_factor_route(database, winding, layout)
    q_divider, pp_divider, p2_divider = branch_dividers_for_pattern(
        'SLP', winding)
    if p2_divider != 2:
        raise ValueError('SLP Q+PP parent-cut validation requires P2=2.')
    lanes_per_child = winding.q // q_divider
    passes_per_lane = (winding.num_poles // 2) // pp_divider
    expected_lane_count = passes_per_lane * winding.num_layers
    for branch_id, path in database:
        lane_counts = Counter(node[2] for node in path)
        if (len(lane_counts) != lanes_per_child
                or set(lane_counts.values()) != {expected_lane_count}):
            raise ValueError(
                f'SLP branch {branch_id} does not contain the derived Q-lane cohort.')
        first_lane = min(lane_counts)
        cohort_start = (first_lane // lanes_per_child) * lanes_per_child
        if set(lane_counts) != set(range(
                cohort_start, cohort_start + lanes_per_child)):
            raise ValueError(
                f'SLP branch {branch_id} uses non-contiguous q lanes.')


def _uwp_pp_branch_direction(winding, index):
    """The second PP=2 cohort travels backward from its bottom N inlet."""
    factors = getattr(winding, 'branch_dividers', ()) or ()
    opposite = (len(factors) == 3 and tuple(factors[1:]) == (2, 1)
                and (factors[0] == 1 or uses_uwp_complementary_q_pp(winding)))
    return -1 if opposite and index % winding.ab >= winding.ab//2 else 1


def validate_pp_only_uwp(database, winding, layout, label='UWP PP-only'):
    for index, (branch_id, path) in enumerate(database):
        direction = _uwp_pp_branch_direction(winding, index)
        if any(not any(step * direction > 0 for step in _connection_travel_steps(
                   database, branch_id, edge_index, start, end, winding.num_slots))
               for edge_index, (start, end) in enumerate(zip(path, path[1:]))):
            raise ValueError(f'{label} branch has an invalid forward edge.')
    _validate_selected_electrical(label, database, winding, layout)


def validate_uwp_proper_q_factor(database, winding, layout, braided):
    """Validate a selected proper q factor against wave travel and retention."""
    _validate_selected_electrical('UWP selected Q factor', database, winding, layout)
    for branch_id, path in database:
        for index, (start, end) in enumerate(zip(path, path[1:])):
            if not any(step > 0 for step in _connection_travel_steps(
                    database, branch_id, index, start, end, winding.num_slots)):
                raise ValueError('UWP selected Q factor has an invalid forward edge.')


def supports_uwp_proper_q_factor(winding, factors):
    """Admit proper-Q sectors and the PP=2 q/P2 reference deployment."""
    if pattern_rejects_divider_tuple('UWP', factors):
        return False
    q_divider, pp_divider, p2_divider = factors
    q, poles, layers, ab = (winding.q, winding.num_poles,
                            winding.num_layers, winding.ab)
    # Reference deployment partitions q lanes, not pole sectors by Naa.
    if (type(q) is int and q > 1 and 1 < q_divider <= q
            and q % q_divider == 0 and (pp_divider, p2_divider) == (2,1)
            and ab == 2*q_divider and poles > 0 and poles % 4 == 0
            and layers >= 2 and layers % 2 == 0
            and _supported_phase_domain(winding)):
        return True
    return (type(q) is int and q > 2 and 1 < q_divider < q
            and q % q_divider == 0 and pp_divider > 0
            and p2_divider in (1, 2)
            and q_divider * pp_divider * p2_divider == ab
            and poles > 0 and poles % 2 == 0
            and (poles // 2) % pp_divider == 0
            and poles % ab == 0 and poles // ab >= 2
            and (poles // ab) % 2 == 0
            and layers >= 2 and layers % 2 == 0
            and _supported_phase_domain(winding))


def preferred_uwp_q_dividers(q, poles, layers, phases, ab):
    """Find a selectable Q-factor route for the base UWP preview."""
    if type(q) is not int or q <= 2:
        return None
    winding = SimpleNamespace(q=q, num_poles=poles, num_layers=layers,
                              num_phases=phases, ab=ab)
    for q_factor in range(2, q):
        if q % q_factor:
            continue
        for p2_factor in (2, 1):
            if ab % (q_factor * p2_factor):
                continue
            factors = (q_factor, ab // (q_factor * p2_factor), p2_factor)
            if (supports_uwp_proper_q_factor(winding, factors)
                    or supports_uwp_balanced_q_factor(winding, factors)):
                return factors
    return None


def pattern_rejects_divider_tuple(pattern, factors, q=None, pp=None, layers=None):
    """Return whether a Pattern explicitly excludes an otherwise enumerable tuple."""
    try:
        normalized = normalize_pattern_name(pattern, allow_extra=True)
        selected = tuple(Fraction(str(value)) for value in factors)
    except (TypeError, ValueError, ZeroDivisionError):
        return False
    if len(selected) != 3:
        return False
    if normalized == 'BWP' and selected[2] == 2:
        return True
    if normalized == 'SSP' and selected[2] == 2:
        if selected != (1, 1, 2):
            return True
        if q is not None:
            q_value = Fraction(str(q))
            return q_value.denominator == 1 and q_value.numerator % 2 == 1
    if normalized == 'ZPP' and selected[2] == 2 and q is not None:
        q_value = Fraction(str(q))
        return (q_value.denominator == 1 and q_value.numerator > 0
                and q_value.numerator % 2 == 1)
    if normalized == 'ZLP' and selected[0] > 1:
        return True
    if normalized == 'CP' and selected == (1, 1, 1):
        return True
    if (normalized == 'TSP' and q is not None and pp is not None
            and layers is not None):
        q_value = Fraction(str(q))
        if (q_value.denominator == 1 and q_value > 0
                and Fraction(str(pp)) > 0 and Fraction(str(layers)) > 0
                and all(value > 0 for value in selected)):
            branch_length = (2 * q_value * Fraction(str(pp))
                             * Fraction(str(layers))
                             / (selected[0] * selected[1] * selected[2]))
            if branch_length < 8:
                return True
    if (normalized == 'TLP' and pp is not None
            and selected[1] * selected[2] > Fraction(str(pp))):
        return True
    if normalized == 'UWP':
        return (selected[1] * selected[2] > 2
                or (q is not None and selected == (q, 1, 1)
                    and selected[0] > 1))
    if normalized == 'LPP':
        return (selected[0] != 1 or selected[2] != 1
                or pp is None or selected[1] != Fraction(str(pp)))
    return False


def supports_slp_p2_from_reference(winding, factors):
    """Admit the even-layer SLP P2-only reference split by its factors."""
    return (factors == (1, 1, 2)
            and type(winding.q) is int and winding.q > 0
            and winding.ab == 2 and winding.num_poles > 0
            and winding.num_poles % 2 == 0
            and winding.num_layers >= 2 and winding.num_layers % 2 == 0
            and _supported_phase_domain(winding))


def supports_slp_full_q_p2(winding, factors):
    """Recognize full-Q P2 branches made from even lap-pass sectors."""
    if (type(winding.q) is not int or winding.q <= 1
            or len(factors) != 3 or factors[0] != winding.q
            or factors[2] != 2 or factors[1] <= 0
            or winding.num_poles <= 0 or winding.num_poles % 2
            or (winding.num_poles // 2) % factors[1]
            or winding.ab != 2 * winding.q * factors[1]
            or winding.num_layers < 2 or winding.num_layers % 2
            or not _supported_phase_domain(winding)):
        return False
    return ((winding.num_poles // 2) // factors[1]) % 2 == 0


def supports_slp_q_pp_p2_parent_cut(winding, factors):
    """Recognize proper-Q+PP P2 paths cut from the public full-Q parent."""
    if (type(winding.q) is not int or winding.q <= 1
            or len(factors) != 3
            or any(type(value) is not int for value in factors)):
        return False
    q_divider, pp_divider, p2_divider = factors
    if (not 1 < q_divider < winding.q
            or winding.q % q_divider
            or pp_divider <= 1 or p2_divider != 2
            or winding.num_poles <= 0 or winding.num_poles % 2):
        return False
    pp = winding.num_poles // 2
    return (pp % pp_divider == 0
            and (pp // pp_divider) % 2 == 0
            and winding.ab == 2 * q_divider * pp_divider
            and winding.num_layers >= 2 and winding.num_layers % 2 == 0
            and _supported_phase_domain(winding))


def supports_slp_pair_lane_p2(winding, factors):
    """Recognize a two-pass branch joining paired q lanes in one pole sector."""
    return (type(winding.q) is int and winding.q > 0
            and len(factors) == 3 and factors[0] > 0
            and winding.q == 2 * factors[0]
            and winding.num_poles > 0 and winding.num_poles % 2 == 0
            and factors[1] == winding.num_poles // 2
            and factors[2] == 2
            and winding.ab == 2 * factors[0] * factors[1]
            and winding.num_layers >= 2 and winding.num_layers % 2 == 0
            and _supported_phase_domain(winding))


def supports_slp_pp_p2_sector(winding, factors):
    """Group an even number of complete pole-pair sectors by PP and P2."""
    return (type(winding.q) is int and winding.q > 0
            and len(factors) == 3 and factors[0] == 1
            and factors[1] > 1 and factors[2] == 2
            and winding.num_poles > 0 and winding.num_poles % 2 == 0
            and (winding.num_poles // 2) % factors[1] == 0
            and ((winding.num_poles // 2) // factors[1]) % 2 == 0
            and winding.ab == 2 * factors[1]
            and winding.num_layers >= 2 and winding.num_layers % 2 == 0
            and _supported_phase_domain(winding))


def divider_exclusion_reason(pattern, factors=None, q=None, pp=None, layers=None):
    normalized = normalize_pattern_name(pattern, allow_extra=True)
    if normalized == 'UWP':
        if q is not None and factors is not None and tuple(factors) == (q,1,1) and q > 1:
            return ('UWP q-only with q-divider=q is the same as BWP q-only '
                    'with q-divider=q; use the BWP route.')
        return ('UWP pp-divider and P2-divider share the same splitting allowance; '
                'their product must be 1 or 2.')
    if normalized == 'BWP':
        return 'BWP does not support P2-divider=2.'
    if normalized == 'SSP':
        if factors is not None and tuple(factors) == (1, 1, 2) and q is not None:
            q_value = Fraction(str(q))
            if q_value.denominator == 1 and q_value.numerator % 2 == 1:
                return ('SSP (1,1,2) reflected construction requires two equal '
                        'q-lane cohorts; odd integer q cannot be divided into '
                        'those cohorts. This rejects the registered construction '
                        'for this geometry, not every possible physical layout.')
        return ('SSP mixed P2-divider formulas remain excluded; only the '
                'distinct reflected P2-only (1,1,2) construction is registered. '
                'Use an admitted P2-only, q-only or q-and-pp route.')
    if normalized == 'ZPP':
        if (factors is not None and len(factors) == 3 and factors[2] == 2
                and q is not None):
            q_value = Fraction(str(q))
            if (q_value.denominator == 1 and q_value.numerator > 0
                    and q_value.numerator % 2 == 1):
                return ('ZPP P2=2 requires q=2*Q; an odd positive integer '
                        'effective q has no integer Q. This rejects the '
                        'registered construction for this geometry, not every '
                        'possible physical layout.')
        return f'{normalized} explicitly excludes this divider tuple.'
    if normalized == 'ZLP':
        return 'ZLP does not support Q-divider greater than 1.'
    if normalized == 'CP':
        return 'CP does not allow the no-divider (1,1,1) route.'
    if normalized == 'TSP' and factors is not None and None not in (q, pp, layers):
        branch_length = (2 * Fraction(str(q)) * Fraction(str(pp))
                         * Fraction(str(layers))
                         / (Fraction(str(factors[0]))
                            * Fraction(str(factors[1]))
                            * Fraction(str(factors[2]))))
        return (f'TSP feature is lost with {branch_length} conductors per '
                'branch; Regular TSP requires at least 8.')
    if normalized == 'TLP':
        return (f'TLP requires pp-divider x P2-divider <= pp={pp}; '
                'the two dividers share the available pole-pair division.')
    if normalized == 'LPP':
        return (f'LPP admits only (1, pp, 1) with the full pole-pair count '
                f'pp={pp}. Observed lower-PP paths reverse weld travel; '
                'all other factors are outside the confirmed LPP construction.')
    return f'{normalized} explicitly excludes this divider tuple.'


def branch_dividers_for_pattern(pattern, winding):
    if pattern == 'CP':
        reason = _cp_layer_admission_reason(winding)
        if reason:
            raise ValueError(reason)
    result = classify_branch_mode(winding.ab, winding.q, winding.num_poles, pattern)
    default = result[1:4]
    selected = getattr(winding, 'branch_dividers', None)
    candidate = default if selected is None else tuple(selected)
    pp = winding.num_poles // 2
    if pattern_rejects_divider_tuple(
            pattern, candidate, winding.q, pp, winding.num_layers):
        raise ValueError(divider_exclusion_reason(
            pattern, candidate, winding.q, pp, winding.num_layers))
    if candidate == default:
        return default
    # Constructors need the arithmetic dispatch route only. Calling the public
    # resolver here would recurse through its structural dry-run.
    if _selected_integer_divider_route(pattern, winding) is not None:
        return tuple(map(int, selected))
    raise ValueError(f'Unsupported {pattern} branch divider combination.')


def _integer_divider_tuple(selected):
    try:
        values = tuple(map(int, selected))
        if len(values) != 3 or tuple(selected) != values:
            return None
    except (TypeError, ValueError):
        return None
    return values


def supports_q_pp_two_reference(pattern, winding, factors):
    """Registered deployment domain; source and transformed paths are validated."""
    if f'{pattern.lower()}_q_pp_two' not in PATTERN_ROUTE_RULES:
        return False
    return (factors[0] > 1 and factors[1:] == (2, 1)
            and winding.q % factors[0] == 0
            and winding.num_poles > 0 and winding.num_poles % 4 == 0
            and winding.ab == 2 * factors[0]
            and winding.num_layers >= 2 and winding.num_layers % 2 == 0
            and (pattern != 'CP' or not _cp_layer_admission_reason(winding))
            and _supported_phase_domain(winding))


def supports_integer_tsp_pp_only_q_p2_identity(winding, factors):
    """Admit full-q TSP PP-only identity transfer from its q/P2 parent."""
    values = _integer_divider_tuple(factors)
    q = getattr(winding, 'q', None)
    phases = getattr(winding, 'num_phases', None)
    layers = getattr(winding, 'num_layers', None)
    poles = getattr(winding, 'num_poles', None)
    if (values is None or type(q) is not int or q < 2
            or values != (1, 2 * q, 1)
            or getattr(winding, 'ab', None) != 2 * q
            or type(poles) is not int or poles <= 0 or poles % 2
            or (poles // 2) % (2 * q)
            or type(layers) is not int or layers < 2 or layers % 2
            or type(phases) is not int or phases < 3 or phases % 2 == 0
            or not _supported_phase_domain(winding)):
        return False
    return not pattern_rejects_divider_tuple(
        'TSP', values, q, poles // 2)


def supports_integer_tsp_q_only_pair_join(winding, factors):
    """Admit TSP adjacent P2 pairing at the one-region seam boundary."""
    values = _integer_divider_tuple(factors)
    q = getattr(winding, 'q', None)
    poles = getattr(winding, 'num_poles', None)
    layers = getattr(winding, 'num_layers', None)
    phases = getattr(winding, 'num_phases', None)
    if (values is None or len(values) != 3
            or type(q) is not int or q <= 0
            or type(poles) is not int or poles <= 0 or poles % 2
            or type(layers) is not int or layers <= 0
            or type(phases) is not int
            or not _supported_phase_domain(winding)
            or not supports_phase_layer_allocation(phases, layers)):
        return False

    q_divider, pp_divider, p2_divider = values
    q_divider_sets = three_phase_set_count(phases)
    local_layers = layers // q_divider_sets
    local_q = q * q_divider_sets
    pole_pairs = poles // 2
    if (q_divider <= 1 or q_divider % 2 or q % q_divider
            or pp_divider != 1 or p2_divider != 1
            or getattr(winding, 'ab', None) != q_divider
            or getattr(winding, 'num_slots', None)
            != phases * q * poles
            or local_q % q_divider
            or pole_pairs <= 1
            or local_layers < 4 or local_layers % 2):
        return False

    seam_factor = gcd(local_layers // 2, pole_pairs)
    if seam_factor not in (1, pole_pairs):
        return False
    return not pattern_rejects_divider_tuple(
        'TSP', values, q, pole_pairs)


def supports_integer_tsp_pp_p2_sector(winding, factors):
    """Admit direct-phase TSP sector inlets when every fixed lane tiles PP."""
    values = _integer_divider_tuple(factors)
    q = getattr(winding, 'q', None)
    poles = getattr(winding, 'num_poles', None)
    layers = getattr(winding, 'num_layers', None)
    phases = getattr(winding, 'num_phases', None)
    if (values is None or type(q) is not int or q <= 0
            or type(poles) is not int or poles <= 0 or poles % 2
            or type(layers) is not int or layers < 2 or layers % 2
            or type(phases) is not int or phases < 3 or phases % 2 == 0
            or (phases > 3 and phases % 3 == 0)
            or not _supported_phase_domain(winding)):
        return False
    q_divider, pp_divider, p2_divider = values
    pp = poles // 2
    if (q_divider != 1 or pp_divider <= 1 or p2_divider != 2
            or getattr(winding, 'ab', None) != 2 * pp_divider
            or pp % pp_divider
            or getattr(winding, 'num_slots', None)
            != 2 * pp * phases * q):
        return False
    if pattern_rejects_divider_tuple('TSP', values, q, pp):
        return False
    return tsp_pp_p2_sector_residues_are_complete(
        q, pp, values, layers)


def supports_integer_tsp_spiral_pass_partition(winding, factors):
    """Admit complete TSP pass partitions in one native phase set."""
    values = _integer_divider_tuple(factors)
    q = getattr(winding, 'q', None)
    poles = getattr(winding, 'num_poles', None)
    layers = getattr(winding, 'num_layers', None)
    phases = getattr(winding, 'num_phases', None)
    if (values is None or type(q) is not int
            or type(poles) is not int or poles <= 0 or poles % 2
            or type(phases) is not int or phases < 3 or phases % 2 == 0
            or three_phase_set_count(phases) != 1
            or getattr(winding, 'ab', None) != values[0] * values[1] * values[2]
            or getattr(winding, 'num_slots', None) != phases * q * poles):
        return False
    try:
        tsp_spiral_pass_partition_dimensions(q, poles // 2, values, layers)
    except ValueError:
        return False
    return True


def supports_tlp_q_pp_two(winding, factors):
    """Compatibility entry for the TLP deployment domain."""
    return supports_q_pp_two_reference('TLP', winding, factors)


def supports_integer_tlp_q_only_pair_join(winding, factors):
    """Admit full-Q TLP adjacent P2 pairing at the one-region seam boundary."""
    values = _integer_divider_tuple(factors)
    q = getattr(winding, 'q', None)
    poles = getattr(winding, 'num_poles', None)
    layers = getattr(winding, 'num_layers', None)
    phases = getattr(winding, 'num_phases', None)
    if (values is None or type(q) is not int or q < 2 or q % 2
            or type(poles) is not int or poles < 4 or poles % 2
            or type(layers) is not int or layers < 2 or layers % 2
            or type(phases) is not int or not _supported_phase_domain(winding)
            or three_phase_set_count(phases) != 1
            or values != (q, 1, 1)
            or getattr(winding, 'ab', None) != q
            or getattr(winding, 'num_slots', None) != phases * q * poles
            or (poles // 2) < 2):
        return False
    return not pattern_rejects_divider_tuple(
        'TLP', values, q, poles // 2)


def supports_tlp_pp_only_two(winding, factors):
    """Admit the approved D=2 TLP deployment from its raw P2 reference."""
    values = _integer_divider_tuple(factors)
    return bool(
        values == (1, 2, 1)
        and type(winding.q) is int and winding.q > 0
        and winding.ab == 2
        and winding.num_poles > 0 and winding.num_poles % 4 == 0
        and winding.num_layers >= 4 and winding.num_layers % 2 == 0
        and _supported_phase_domain(winding))


def supports_tlp_pp_only_even(winding, factors):
    """Cut a Q-matched D=2 parent at complete TLP pass boundaries."""
    values = _integer_divider_tuple(factors)
    if values is None:
        return False
    q_divider, divider, p2 = values
    q = getattr(winding, 'q', None)
    legacy_q_parent = (q_divider == 1 and type(q) is int and 0 < q <= 2)
    full_q_parent = (type(q) is int and q > 1 and q_divider == q)
    return bool(
        p2 == 1 and divider > 2 and divider % 2 == 0
        and (legacy_q_parent or full_q_parent)
        and winding.ab == q_divider * divider and winding.num_poles > 0
        and winding.num_poles % 4 == 0
        and (winding.num_poles // 2) % divider == 0
        and winding.num_layers >= 4 and winding.num_layers % 2 == 0
        and _supported_phase_domain(winding))


def supports_tlp_pp_p2_short_unit(winding, factors):
    """Split the public P2 parent into whole TLP units and deploy PP copies."""
    values = _integer_divider_tuple(factors)
    if values is None:
        return False
    q_divider, divider, p2 = values
    pp = winding.num_poles // 2
    return bool(
        q_divider == 1 and p2 == 2 and divider > 1
        and type(winding.q) is int and winding.q > 0
        and winding.num_poles > 0 and winding.num_poles % 2 == 0
        and pp % divider == 0 and 2 * divider <= pp
        and winding.ab == 2 * divider
        and winding.num_layers >= 4 and winding.num_layers % 2 == 0
        and _supported_phase_domain(winding))


def supports_tlp_q_pp_p2_parent_slices(winding, factors):
    """Recognize complete-pass Q slices of a public TLP PP+P2 parent."""
    values = _integer_divider_tuple(factors)
    if values is None:
        return False
    q_divider, divider, p2 = values
    q = getattr(winding, 'q', None)
    poles = getattr(winding, 'num_poles', None)
    layers = getattr(winding, 'num_layers', None)
    if (type(q) is not int or q < 2 or type(poles) is not int
            or poles < 4 or poles % 2 or type(layers) is not int
            or layers < 4 or layers % 2 or q_divider < 1 or divider < 1):
        return False
    pp = poles // 2
    passes_per_child = (q // q_divider) * (pp // divider)
    return bool(
        q_divider == 2 and divider > 1 and p2 == 2
        and q % q_divider == 0 and pp % divider == 0
        and 2 * divider <= pp and passes_per_child >= 2
        and winding.ab == q_divider * divider * p2
        and _supported_phase_domain(winding))


def supports_uwp_short_p2_weld(winding, factors):
    """Two-leg P2 wave pins expose both terminals on the weld side."""
    values = _integer_divider_tuple(factors)
    return bool(
        values is not None and type(winding.q) is int and winding.q > 0
        and values == (winding.q, 1, 2)
        and winding.ab == 2 * winding.q
        and winding.num_poles == 2 and winding.num_layers == 2
        and _supported_phase_domain(winding))


def _deploy_second_pole_region(database, winding, layout, *, reflect_pole_travel=False):
    """Move the second raw pole cohort to sector two, preserving edge parity.

    A bare slot translation overlaps the first cohort. Reflecting its layer
    traversal supplies the complementary occupancy. Routes that must preserve
    geometric weld direction also reflect pole travel while retaining q lanes.
    """
    slots, q, layers = winding.num_slots, winding.q, winding.num_layers
    tau = winding.num_phases * q
    shifts = layout.phase_shift_list
    lookup = {(s, l): (phase, sign) for s, l, phase, sign in phase_map(
        slots, winding.num_poles, layers, shifts, winding.num_phases)}
    cohorts, rotations, counts = [], {}, {}
    for _, path in database:
        slot, layer = path[0][:2]
        pole = ((slot - shifts[layer]) % slots) // tau
        if pole not in (0, 1):
            raise ValueError('q/P2 reference inlets must lie in its first two pole regions.')
        phase, sign = lookup[(slot, layer)]
        cohorts.append((phase, pole))
        counts[(phase, pole)] = counts.get((phase, pole), 0) + 1
        if pole == 0:
            rotations[phase] = tau if sign < 0 else 0
    divider = int(winding.branch_dividers[0])
    if any(counts.get((phase, pole), 0) != divider
           for phase in range(winding.num_phases) for pole in (0, 1)):
        raise ValueError('q/P2 reference requires Q branches per phase in each pole region.')
    result = _CandidateBranches()
    for (branch_id, path), (phase, pole) in zip(database, cohorts):
        rotation = rotations[phase] + (slots//2-tau if pole else 0)
        deployed = [((s-shifts[l]+rotation) % slots,
                     layers-1-l if pole else l, pos) for s, l, pos in path]
        if pole and reflect_pole_travel:
            anchor = deployed[0][0] - deployed[0][0] % q
            deployed = [((2*anchor-(s-s%q)+s%q) % slots, l, pos)
                        for s, l, pos in deployed]
        deployed = [((s+shifts[l]) % slots, l, pos) for s, l, pos in deployed]
        result.append([branch_id, deployed])
    if any(lookup[path[0][:2]][1] != 1 or lookup[path[-1][:2]][1] != -1
           for _, path in result):
        raise ValueError('q-and-pp second-sector deployment requires N-to-S terminals.')
    result.sector_deployment_report = dict(
        source_dividers=(divider, 1, 2), target_dividers=(divider, 2, 1),
        second_cohort_rotation=slots//2-tau,
        second_cohort_layer_mapping='L-1-layer',
        reflected_pole_travel=reflect_pole_travel,
        source_starts=[tuple(path[0]) for _, path in database],
        starts=[tuple(path[0]) for _, path in result])
    return [path[0] for _, path in result], result


def _q_pp_two_from_reference(pattern, tp, winding, layout):
    reference = SimpleNamespace(**{name: getattr(winding, name) for name in
        ('q', 'num_slots', 'num_poles', 'num_phases', 'num_layers', 'ab')})
    reference.branch_dividers = (int(winding.branch_dividers[0]), 1, 2)
    source_decision = resolve_pattern_route(
        pattern, reference, reference.branch_dividers, tp, layout)
    if source_decision.status == 'disabled':
        raise ValueError('q/P2 reference unavailable: ' + source_decision.reason)
    starts, source = _dispatch_winding_pattern(pattern, tp, reference, layout)
    _validate_generated_layout_consistency(pattern, starts, source, reference)
    starts, database = _deploy_second_pole_region(
        source, winding, layout, reflect_pole_travel=pattern in ('TSP', 'TLP', 'CP'))
    _validate_generated_layout_consistency(pattern, starts, database, winding)
    _validate_selected_electrical(pattern + ' second-sector deployment', database, winding, layout)
    if pattern == 'TLP':
        validate_tlp_welds(database, winding, layout)
    if pattern == 'TLP' and tuple(winding.branch_dividers) == (1, 2, 1):
        validate_tlp_pp_only_two_returns(database, winding)
    return starts, database


def _tsp_pp_only_q_p2_identity_from_reference(tp, winding, layout):
    """Reuse the validated full-q TSP q/P2 paths without changing their order."""
    q = int(winding.q)
    if not supports_integer_tsp_pp_only_q_p2_identity(
            winding, winding.branch_dividers):
        raise ValueError(
            'TSP PP-only identity transfer is outside its full-q source domain.')
    reference = SimpleNamespace(**{name: getattr(winding, name) for name in
        ('q', 'num_slots', 'num_poles', 'num_phases', 'num_layers')})
    reference.ab = 2 * q
    reference.branch_dividers = (q, 1, 2)
    _, source = get_winding_layout('TSP', tp, reference, layout)
    pieces = apply_route_formula(
        'tsp_pp_only_q_p2_identity', source,
        tuple(winding.branch_dividers))
    database = _CandidateBranches([
        [branch_id, piece.path]
        for branch_id, piece in enumerate(pieces, start=1)
    ])
    _validate_selected_electrical(
        'TSP PP-only identity transfer', database, winding, layout)
    return [path[0] for _, path in database], database


def _tsp_q_only_pair_join_from_reference(tp, winding, layout):
    """Complete a TSP (Q,1,2) parent and join adjacent same-phase branches."""
    factors = _integer_divider_tuple(
        getattr(winding, 'branch_dividers', None))
    if not supports_integer_tsp_q_only_pair_join(winding, factors):
        raise ValueError('TSP Q-only adjacent pairing is outside its formula domain.')

    Q = factors[0]
    q = int(winding.q)
    reference = SimpleNamespace(
        q=q, num_slots=winding.num_slots, num_poles=winding.num_poles,
        num_phases=winding.num_phases, num_layers=winding.num_layers,
        ab=2 * Q, branch_dividers=(Q, 1, 2))
    if Q == q:
        _, source = get_winding_layout('TSP', tp, reference, layout)
    else:
        _raw_starts, raw_source = pattern_TSP(tp, reference, layout)
        source_phase_sign = {
            (slot, layer): (phase, sign)
            for slot, layer, phase, sign in phase_map(
                reference.num_slots, reference.num_poles,
                reference.num_layers, layout.phase_shift_list,
                reference.num_phases)
        }
        swept = tsp_q_lane_sweep_completion(
            raw_source, q=q, q_divider=Q,
            num_slots=reference.num_slots,
            phase_signs=source_phase_sign)
        source = _CandidateBranches([
            [index + 1, item.path]
            for index, item in enumerate(swept)
        ])
        _validate_generated_layout_consistency(
            'TSP', [path[0] for _, path in source], source, reference)

    source_paths = [path for _branch_id, path in source]
    source_records = phase_map(
        reference.num_slots, reference.num_poles, reference.num_layers,
        layout.phase_shift_list, reference.num_phases)
    source_phase_sign = {
        (slot, layer): (phase, sign)
        for slot, layer, phase, sign in source_records
    }
    source_report = validate_branches(
        source_paths, source_records, reference.num_slots,
        reference.num_poles, reference.ab, reference.num_phases)
    source_errors = (set(source_report['errors'])
                     - EMF_ASYMMETRY_ERRORS)
    if not source_report['layout_retained'] or source_errors:
        raise ValueError(
            'TSP Q-only P2 parent fails source validation: '
            + ', '.join(sorted(source_errors or set(source_report['errors']))))
    from layout_analysis import analyze_pattern_identity
    source_identity = analyze_pattern_identity(
        'TSP', source, reference, layout)
    if source_identity['status'] != 'valid':
        raise ValueError(
            'TSP Q-only P2 parent identity: ' + source_identity['reason'])

    groups = {phase: [] for phase in range(reference.num_phases)}
    for source_id, path in source:
        if not path:
            raise ValueError('TSP Q-only P2 source contains an empty branch.')
        start_phase, start_sign = source_phase_sign[tuple(path[0][:2])]
        end_phase, end_sign = source_phase_sign[tuple(path[-1][:2])]
        if start_sign != 1 or end_sign != -1 or start_phase != end_phase:
            raise ValueError(
                f'TSP Q-only P2 source branch {source_id} must run N to S.')
        if any(source_phase_sign[tuple(node[:2])][0] != start_phase
               for node in path):
            raise ValueError(
                f'TSP Q-only P2 source branch {source_id} changes phase.')
        if any(node[2] != (
                node[0] - layout.phase_shift_list[node[1]]) % q
               for node in path):
            raise ValueError(
                f'TSP Q-only P2 source branch {source_id} has invalid q coordinates.')
        groups[start_phase].append((source_id, path))

    database = _CandidateBranches()
    for phase in range(reference.num_phases):
        parents = groups[phase]
        if len(parents) != 2 * Q:
            raise ValueError(
                f'TSP Q-only source phase {phase + 1} has {len(parents)} '
                f'branches; expected {2 * Q}.')
        joined = apply_route_formula(
            'tsp_q_only_pair_join', parents, factors)
        for branch in joined:
            database.append([len(database) + 1, branch.path])

    return [path[0] for _, path in database], database


def _tlp_q_only_pair_join_from_reference(tp, winding, layout):
    """Join adjacent full-Q TLP P2 parents in generated phase order."""
    factors = _integer_divider_tuple(
        getattr(winding, 'branch_dividers', None))
    if not supports_integer_tlp_q_only_pair_join(winding, factors):
        raise ValueError('TLP Q-only adjacent pairing is outside its formula domain.')

    Q = factors[0]
    q = int(winding.q)
    pp = int(winding.num_poles) // 2
    layers = int(winding.num_layers)
    phases = int(winding.num_phases)
    reference = SimpleNamespace(
        q=q, num_slots=winding.num_slots, num_poles=winding.num_poles,
        num_phases=phases, num_layers=layers, ab=2 * Q,
        branch_dividers=(Q, 1, 2))
    _, source = get_winding_layout('TLP', tp, reference, layout)
    parent_length = pp * layers

    source_records = phase_map(
        reference.num_slots, reference.num_poles, layers,
        layout.phase_shift_list, phases)
    source_phase_sign = {
        (slot, layer): (phase, sign)
        for slot, layer, phase, sign in source_records
    }
    source_report = validate_branches(
        [path for _branch_id, path in source], source_records,
        reference.num_slots, reference.num_poles, reference.ab, phases)
    source_errors = set(source_report['errors']) - EMF_ASYMMETRY_ERRORS
    if not source_report['layout_retained'] or source_errors:
        raise ValueError(
            'TLP Q-only P2 parent fails source validation: '
            + ', '.join(sorted(source_errors or set(source_report['errors']))))
    source_identity = _analyze_pattern_identity_for_sets(
        'TLP', source, reference, layout)
    if source_identity['status'] != 'valid':
        raise ValueError(
            'TLP Q-only P2 parent identity: ' + source_identity['reason'])

    groups = {phase: [] for phase in range(phases)}
    for source_id, path in source:
        if len(path) != parent_length:
            raise ValueError(
                f'TLP Q-only P2 parent {source_id} has the wrong branch length.')
        start_phase, start_sign = source_phase_sign[tuple(path[0][:2])]
        end_phase, end_sign = source_phase_sign[tuple(path[-1][:2])]
        if (start_sign != 1 or end_sign != -1
                or start_phase != end_phase
                or any(source_phase_sign[tuple(node[:2])][0] != start_phase
                       for node in path)):
            raise ValueError(
                f'TLP Q-only P2 parent {source_id} must run N-to-S in one phase.')
        lane = path[0][2]
        if (any(node[2] != lane for node in path)
                or any(node[2] != (
                    node[0] - layout.phase_shift_list[node[1]]) % q
                       for node in path)):
            raise ValueError(
                f'TLP Q-only P2 parent {source_id} changes its q-lane identity.')
        groups[start_phase].append((source_id, path))

    database = _CandidateBranches()
    for phase in range(phases):
        parents = groups[phase]
        if len(parents) != 2 * Q:
            raise ValueError(
                f'TLP Q-only source phase {phase + 1} has {len(parents)} '
                f'branches; expected {2 * Q}.')
        starts_by_layer = Counter(path[0][1] for _branch_id, path in parents)
        expected_cohorts = Counter({0: Q, layers - 1: Q})
        if starts_by_layer != expected_cohorts:
            raise ValueError(
                f'TLP Q-only source phase {phase + 1} does not form two '
                f'{Q}-branch end-layer cohorts.')
        for layer in (0, layers - 1):
            lanes = [path[0][2] for _branch_id, path in parents
                     if path[0][1] == layer]
            if sorted(lanes) != list(range(Q)):
                raise ValueError(
                    f'TLP Q-only source phase {phase + 1} does not partition '
                    f'q lanes in layer cohort {layer}.')

        for branch in apply_route_formula(
                'tlp_q_only_pair_join', parents, factors):
            database.append([len(database) + 1, branch.path])

    starts = [path[0] for _branch_id, path in database]
    return starts, database


def _tsp_pp_p2_sector_from_formula(winding):
    """Build TSP PP+P2 branches from the registered fixed-lane formula."""
    factors = _integer_divider_tuple(
        getattr(winding, 'branch_dividers', None))
    if not supports_integer_tsp_pp_p2_sector(winding, factors):
        raise ValueError(
            'TSP PP+P2 fixed-lane sectors are outside the validated formula domain.')
    formula_branches = tsp_pp_p2_sector_branches(
        int(winding.q), int(winding.num_poles) // 2, factors,
        int(winding.num_layers), int(winding.num_phases))
    database = _CandidateBranches()
    signed_travel = {}
    pole_region_width = int(winding.q) * int(winding.num_phases)
    for formula_branch in formula_branches:
        branch_id = len(database) + 1
        path = list(formula_branch.path)
        database.append([branch_id, path])
        signed_travel[branch_id] = (
            formula_branch.direction * pole_region_width,
        ) * max(len(path) - 1, 0)
    database.signed_travel = signed_travel
    return [path[0] for _branch_id, path in database], database


def _tsp_spiral_pass_partition_from_formula(winding):
    """Materialize the registered orbit/lane partition and signed edge travel."""
    factors = _integer_divider_tuple(branch_dividers_for_pattern('TSP', winding))
    if not supports_integer_tsp_spiral_pass_partition(winding, factors):
        raise ValueError('TSP spiral pass partition is outside its formula domain.')
    pieces = tsp_spiral_pass_partition(
        winding.q, winding.num_poles // 2, factors,
        winding.num_layers, winding.num_phases)
    database = _CandidateBranches([
        [index, list(piece.path)] for index, piece in enumerate(pieces, 1)])
    database.signed_travel = {
        index: piece.signed_travel for index, piece in enumerate(pieces, 1)}
    return [path[0] for _, path in database], database


def _tlp_pp_only_even_from_reference(tp, winding, layout):
    """Partition a public Q-matched D=2 TLP parent at complete lap passes."""
    q_divider, divider, _p2 = _integer_divider_tuple(
        winding.branch_dividers)
    reference = SimpleNamespace(**{name: getattr(winding, name) for name in
        ('q', 'num_slots', 'num_poles', 'num_phases', 'num_layers')})
    reference.ab = 2 * q_divider
    reference.branch_dividers = (q_divider, 2, 1)
    decision = resolve_pattern_route(
        'TLP', reference, reference.branch_dividers, tp, layout)
    if decision.status != 'enabled':
        raise ValueError('TLP D=2 parent unavailable: ' + decision.reason)
    _, parent = get_winding_layout('TLP', tp, reference, layout)
    pieces = apply_route_formula(
        'tlp_pp_only_even', parent, tuple(winding.branch_dividers))
    _validate_tlp_pp_partition_lineage(
        parent, pieces, winding, layout, q_divider)
    database = _CandidateBranches()
    for piece in pieces:
        path = piece.path
        width = len(path)
        if width % winding.num_layers or width < 2 * winding.num_layers:
            raise ValueError('TLP cut must retain two complete lap passes.')
        database.append([len(database) + 1, path])
    starts = [path[0] for _, path in database]
    _validate_generated_layout_consistency('TLP', starts, database, winding)
    _validate_selected_electrical('TLP even PP cut', database, winding, layout)
    validate_tlp_welds(database, winding, layout)
    validate_tlp_pp_only_two_returns(database, winding)
    return starts, database


def _validate_tlp_pp_partition_lineage(parent, pieces, winding, layout,
                                       source_q_divider):
    """Verify cuts retain the public parent's phase, lane, sector and pass order."""
    divider = int(winding.branch_dividers[1])
    parts = divider // 2
    layers = int(winding.num_layers)
    q = int(winding.q)
    phases = int(winding.num_phases)
    slots = int(winding.num_slots)
    tau = q * phases
    shifts = tuple(layout.phase_shift_list)
    phase_lookup = {
        (slot, layer): phase
        for slot, layer, phase, _sign in phase_map(
            slots, winding.num_poles, layers, shifts, phases)
    }

    def path_signature(path):
        signature = []
        for slot, layer, position in path:
            shifted_slot = (slot - shifts[layer]) % slots
            phase = phase_lookup[(slot, layer)]
            lane = (shifted_slot % tau) // phases
            region = shifted_slot // tau
            signature.append((phase, lane, region, layer, position))
        return signature

    parents_by_id = {branch_id: path for branch_id, path in parent}
    if len(parents_by_id) != len(parent) or len(pieces) != len(parent) * parts:
        raise ValueError('TLP PP cut changed the public parent branch inventory.')
    if any(len(path) % layers for _branch_id, path in parent):
        raise ValueError('TLP PP parent does not contain complete layer passes.')
    expected_order = [
        (branch_id, part_index)
        for branch_id, _path in parent
        for part_index in range(parts)
    ]
    actual_order = [
        (piece.source_ids[0] if len(piece.source_ids) == 1 else None,
         piece.part_index)
        for piece in pieces
    ]
    if actual_order != expected_order:
        raise ValueError('TLP PP cut changed source-major parent order.')

    children_by_parent = {branch_id: [] for branch_id in parents_by_id}
    for piece in pieces:
        if len(piece.source_ids) != 1 or piece.source_ids[0] not in parents_by_id:
            raise ValueError('TLP PP cut changed source branch identity.')
        children_by_parent[piece.source_ids[0]].append(piece)

    for branch_id, parent_path in parent:
        children = children_by_parent[branch_id]
        if [child.part_index for child in children] != list(range(parts)):
            raise ValueError('TLP PP cut changed source-major pass order.')
        parent_tags = path_signature(parent_path)
        if source_q_divider == q:
            if (len({tag[0] for tag in parent_tags}) != 1
                    or len({tag[1] for tag in parent_tags}) != 1):
                raise ValueError(
                    'Full-Q TLP parent changes phase or q-lane within a branch.')
        width = len(parent_path) // parts
        if width % layers:
            raise ValueError('TLP PP cuts must end at complete layer-pass boundaries.')
        for child in children:
            start = child.part_index * width
            end = start + width
            expected_path = parent_path[start:end]
            if child.path != expected_path:
                raise ValueError('TLP PP cut reordered a parent path segment.')
            if path_signature(child.path) != parent_tags[start:end]:
                raise ValueError(
                    'TLP PP cut changed its inherited pole-sector sequence.')
            if source_q_divider == q:
                child_tags = path_signature(child.path)
                if (len({tag[0] for tag in child_tags}) != 1
                        or len({tag[1] for tag in child_tags}) != 1):
                    raise ValueError(
                        'TLP PP child changed its parent phase or q-lane.')


def _tlp_pp_p2_short_unit_from_reference(tp, winding, layout):
    """Cut complete P2 lap units and deploy phase-preserving sector copies."""
    divider = int(winding.branch_dividers[1])
    reference = SimpleNamespace(**{name: getattr(winding, name) for name in
        ('q', 'num_slots', 'num_poles', 'num_phases', 'num_layers')})
    reference.ab = 2
    reference.branch_dividers = (1, 1, 2)
    _, source = get_winding_layout('TLP', tp, reference, layout)
    slots, layers = winding.num_slots, winding.num_layers
    if slots % divider:
        raise ValueError('TLP PP+P2 sector rotation requires integral slots per divider.')
    units = []
    source_travel = getattr(source, 'signed_travel', None)
    child_travel = {}
    unit_pieces = apply_route_formula(
        'tlp_pp_p2_short_unit', source, tuple(winding.branch_dividers))
    for piece in unit_pieces:
        parent_id = piece.source_ids[0]
        index = piece.part_index
        path = piece.path
        width = len(path)
        if width < layers or width % layers:
            raise ValueError('TLP PP+P2 cut must preserve complete layer passes.')
        units.append((parent_id, index, path))
        if isinstance(source_travel, Mapping) and parent_id in source_travel:
            child_travel[len(units)] = tuple(source_travel[parent_id][
                index * width:index * width + width - 1])
    from layout_analysis import analyze_pattern_identity
    signs = {(slot, layer): sign for slot, layer, _, sign in phase_map(
        slots, winding.num_poles, layers, layout.phase_shift_list,
        winding.num_phases)}
    failures = []
    # A source sector may already be in the intended position. In either
    # placement, each parent must supply distinct PP sectors in its cohort.
    for rotations in (tuple(index * (slots // divider)
                            for index in range(divider)),
                      (0,) * divider):
        database = _CandidateBranches([
            [branch_id, [((slot + rotations[index]) % slots, layer, phasor)
                         for slot, layer, phasor in unit]]
            for branch_id, (_, index, unit) in enumerate(units, start=1)
        ])
        if len(child_travel) == len(units):
            database.signed_travel = child_travel
        starts = [path[0] for _, path in database]
        try:
            sectors_by_parent = {}
            tau = winding.num_phases * winding.q
            for (parent_id, _, _), (_, path) in zip(units, database):
                slot, layer, _ = path[0]
                physical_slot = (slot - layout.phase_shift_list[layer]) % slots
                sector = int(physical_slot // tau) // 2
                sectors_by_parent.setdefault(parent_id, []).append(sector)
            pp = winding.num_poles // 2
            for sectors in sectors_by_parent.values():
                expected = {(sectors[0] + k * (pp // divider)) % pp
                            for k in range(divider)}
                if len(set(sectors)) != divider or set(sectors) != expected:
                    raise ValueError('TLP PP+P2 children must occupy distinct '
                                     'PP sectors of their parent cohort.')
            _validate_generated_layout_consistency('TLP', starts, database, winding)
            if any((signs[path[0][:2]], signs[path[-1][:2]]) != (1, -1)
                   for _, path in database):
                raise ValueError('TLP PP+P2 short units must start N and end S.')
            identity = analyze_pattern_identity('TLP', database, winding, layout)
            if identity['status'] != 'valid':
                raise ValueError('TLP PP+P2 ordered identity: ' + identity['reason'])
            _validate_selected_electrical('TLP PP+P2 short-unit deployment',
                                          database, winding, layout)
            validate_tlp_welds(database, winding, layout)
        except ValueError as exc:
            failures.append(str(exc))
            continue
        database.sector_deployment_report = dict(
            source_dividers=(1, 1, 2), target_dividers=(1, divider, 2),
            child_rotations=rotations,
            inlet_sectors_by_parent=sectors_by_parent)
        return starts, database
    raise ValueError('TLP PP+P2 short-unit deployment has no legal sector '
                     'placement: ' + '; '.join(failures))


def _tlp_q_pp_p2_parent_slices_from_reference(tp, winding, layout):
    """Partition a public PP+P2 parent without changing any child edge."""
    q_divider, divider, p2 = tuple(winding.branch_dividers)
    source_winding = SimpleNamespace(**{name: getattr(winding, name) for name in
        ('q', 'num_slots', 'num_poles', 'num_phases', 'num_layers')})
    source_winding.ab = divider * p2
    source_winding.branch_dividers = (1, divider, p2)
    _, source = get_winding_layout('TLP', tp, source_winding, layout)
    pieces = apply_route_formula(
        'tlp_q_pp_p2_parent_slices', source,
        tuple(winding.branch_dividers))
    layers = winding.num_layers
    expected_width = layers * (winding.q // q_divider) * (
        (winding.num_poles // 2) // divider)
    branches = []
    child_travel = {}
    source_travel = getattr(source, 'signed_travel', None)
    for child_id, piece in enumerate(pieces, start=1):
        path = piece.path
        if len(path) != expected_width or len(path) % layers:
            raise ValueError('TLP Q+PP+P2 slices must contain complete layer passes.')
        branches.append([child_id, path])
        parent_id = piece.source_ids[0]
        if isinstance(source_travel, Mapping) and parent_id in source_travel:
            offset = piece.part_index * expected_width
            child_travel[child_id] = tuple(source_travel[parent_id][
                offset:offset + expected_width - 1])
    database = _CandidateBranches(branches)
    if len(child_travel) == len(branches):
        database.signed_travel = child_travel
    starts = [path[0] for _, path in database]

    slots = winding.num_slots
    q = winding.q
    pp = winding.num_poles // 2
    tau = winding.num_phases * q
    records = phase_map(slots, winding.num_poles, layers,
                        layout.phase_shift_list, winding.num_phases)
    phase_sign = {(slot, layer): (phase, sign)
                  for slot, layer, phase, sign in records}
    north_regions = {}
    for slot, layer, phase, sign in records:
        if sign == 1 and layer in (0, layers - 1):
            physical_slot = (slot - layout.phase_shift_list[layer]) % slots
            north_regions.setdefault((phase, layer), set()).add(
                physical_slot // tau)
    north_region_ranks = {
        key: {region: rank for rank, region in enumerate(sorted(regions))}
        for key, regions in north_regions.items()
    }
    cohorts = {}
    for branch_id, path in database:
        inlet = path[0][:2]
        outlet = path[-1][:2]
        phase, sign = phase_sign[inlet]
        end_phase, end_sign = phase_sign[outlet]
        if (sign, end_sign) != (1, -1) or phase != end_phase:
            raise ValueError(
                f'TLP Q+PP+P2 branch {branch_id} must remain N-to-S in one phase.')
        slot, layer = inlet
        if layer not in (0, layers - 1):
            raise ValueError('TLP Q+PP+P2 inlets require an outer layer.')
        physical_slot = (slot - layout.phase_shift_list[layer]) % slots
        pole_region = physical_slot // tau
        try:
            sector = north_region_ranks[(phase, layer)][pole_region]
        except KeyError as exc:
            raise ValueError(
                'TLP Q+PP+P2 inlet is outside a phase-positive pole region.') from exc
        lane = physical_slot % q
        cohorts.setdefault((phase, layer), {}).setdefault(sector, []).append(lane)
    uniformly_spaced_lanes = True
    for phase in range(winding.num_phases):
        for layer in (0, layers - 1):
            sector_lanes = cohorts.get((phase, layer), {})
            if len(sector_lanes) != divider:
                raise ValueError('TLP Q+PP+P2 inlet PP sector count is wrong.')
            sectors = set(sector_lanes)
            first = next(iter(sectors))
            expected_sectors = {(first + j * (pp // divider)) % pp
                                for j in range(divider)}
            if sectors != expected_sectors:
                raise ValueError('TLP Q+PP+P2 inlet PP sectors are not uniform.')
            for lanes in sector_lanes.values():
                if len(lanes) != q_divider or len(set(lanes)) != q_divider:
                    raise ValueError('TLP Q+PP+P2 inlet q-lanes are not distinct.')
                expected_lanes = {(lanes[0] + j * (q // q_divider)) % q
                                  for j in range(q_divider)}
                if set(lanes) != expected_lanes:
                    uniformly_spaced_lanes = False

    _validate_generated_layout_consistency('TLP', starts, database, winding)
    from layout_analysis import analyze_pattern_identity
    identity = analyze_pattern_identity('TLP', database, winding, layout)
    if identity['status'] != 'valid':
        raise ValueError('TLP Q+PP+P2 ordered identity: ' + identity['reason'])
    validate_tlp_welds(database, winding, layout)
    _validate_selected_electrical('TLP Q+PP+P2 parent slices',
                                  database, winding, layout)
    database.parent_slice_report = dict(
        source_dividers=(1, divider, p2),
        target_dividers=(q_divider, divider, p2),
        child_width=expected_width,
        uniformly_spaced_lanes=uniformly_spaced_lanes,
        source_parts=tuple((piece.source_ids, piece.part_index)
                           for piece in pieces),
        inlet_cohorts=cohorts)
    return starts, database


def _uwp_short_p2_weld(winding, layout):
    """Pair every phase/q-lane N conductor with its diametric S conductor."""
    q, m = winding.q, winding.num_phases
    tau = m * q
    records = phase_map(winding.num_slots, 2, 2,
                        layout.phase_shift_list, m)
    north = {}
    for slot, layer, phase, sign in records:
        if layer == 0 and sign == 1:
            key = (phase, slot % q)
            if key in north:
                raise ValueError('UWP short P2 has duplicate N-lane origins.')
            north[key] = slot
    database = _CandidateBranches()
    for phase in range(m):
        for start_layer in (0, 1):
            for lane in range(q):
                key = (phase, lane)
                if key not in north:
                    raise ValueError('UWP short P2 is missing an N-lane origin.')
                n_slot = north[key]
                s_slot = (n_slot + tau) % winding.num_slots
                database.append([len(database) + 1,
                                 [(n_slot, start_layer, lane),
                                  (s_slot, 1 - start_layer, lane)]])
    starts = [path[0] for _, path in database]
    _validate_generated_layout_consistency('UWP', starts, database, winding)
    _validate_selected_electrical('UWP short P2 weld pin',
                                  database, winding, layout)
    return starts, database


def validate_tlp_welds(database, winding, layout):
    """TLP welds retain one geometric direction per layer pair."""
    slots = winding.num_slots
    shifts = layout.phase_shift_list
    weld_parity = 1 if layout.inlet_from_weld_side else 0
    directions = {}
    for branch_id, path in database:
        for index in range(weld_parity, len(path)-1, 2):
            a, b = path[index:index+2]
            steps = _connection_travel_steps(database, branch_id, index,
                                             a, b, slots, shifts)
            if not any(steps) or abs(b[1]-a[1]) != 1:
                raise ValueError('TLP welding-side transposition is not allowed.')
            pair = tuple(sorted((a[1], b[1])))
            choices = {(1 if step * (b[1] - a[1]) > 0 else -1)
                       for step in steps if step}
            shared = choices & directions.get(pair, {-1, 1})
            if not shared:
                raise ValueError('TLP welding travel conflicts within a layer pair.')
            directions[pair] = shared


def validate_tlp_pp_only_two_returns(database, winding):
    """Keep first/last-layer returns forward relative to layer traversal."""
    returns = []
    for branch_id, path in database:
        for edge_index, (left, right) in enumerate(zip(path, path[1:])):
            layer_delta = right[1] - left[1]
            if edge_index % 2 == 1 and abs(layer_delta) == winding.num_layers - 1:
                pitches = _connection_travel_steps(
                    database, branch_id, edge_index, left, right,
                    winding.num_slots)
                # A tail-layer inlet reverses both layer and pole travel.
                returns.append(tuple(pitch if layer_delta < 0 else -pitch
                                     for pitch in pitches))
    if not returns:
        raise ValueError('TLP PP-only D=2 requires first/last-layer insertion returns.')
    if any(not any(pitch > 0 for pitch in choices) for choices in returns):
        raise ValueError(
            'TLP PP-only D=2 has a reversed first/last-layer return.')


def supports_ssp_reflected_p2(winding, factors):
    """Two equal q-lane cohorts; the second starts at the last layer."""
    return (tuple(factors) == (1, 1, 2)
            and type(winding.q) is int and winding.q > 0 and winding.q % 2 == 0
            and winding.ab == 2 and winding.num_poles >= 4
            and winding.num_poles % 2 == 0
            and winding.num_layers >= 2 and winding.num_layers % 2 == 0
            and _supported_phase_domain(winding))


def supports_spiral_q_pp_parent_cut(pattern, winding, factors):
    """Admit whole PP-parent pass cuts with a complete Q-lane partition."""
    values = _integer_divider_tuple(factors)
    if (pattern not in ('SSP', 'SLP') or values is None
            or type(winding.q) is not int or winding.q < 2):
        return False
    Q, D, P2 = values
    pp = winding.num_poles // 2
    return bool(
        1 < Q < winding.q and winding.q % Q == 0
        and D > 1 and pp > 0 and winding.num_poles == 2 * pp
        and pp % D == 0 and P2 == 1 and winding.ab == Q * D
        and winding.num_layers >= 2
        and _supported_phase_domain(winding))


def supports_slp_q_pp_single_sector_weld(winding, factors):
    """Check the SLP Q+PP domain whose one-conductor weld seam is derived."""
    values = _integer_divider_tuple(factors)
    if (values is None or type(winding.num_layers) is not int
            or winding.num_layers < 2 or winding.num_layers % 2):
        return False
    pp = winding.num_poles // 2
    return (values[1] == pp
            and supports_spiral_q_pp_parent_cut('SLP', winding, values))


def _spiral_q_pp_from_pp_parent(pattern, tp, winding, layout):
    """Regroup whole PP-parent pass units into disjoint Q-lane children."""
    Q, D, _ = _integer_divider_tuple(winding.branch_dividers)
    fields = (vars(winding) if hasattr(winding, '__dict__')
              else winding._asdict())
    reference = SimpleNamespace(**fields)
    reference.ab = D
    reference.branch_dividers = (1, D, 1)
    _, parent = get_winding_layout(pattern, tp, reference, layout)
    pp = winding.num_poles // 2
    database = _CandidateBranches()
    for _, source_path in parent:
        try:
            children = spiral_q_pp_parent_cut(
                source_path, q_divider=Q, pp_divider=D, q=winding.q,
                pp=pp, layer_count=winding.num_layers,
                block_order='lane_major' if pattern == 'SSP'
                else 'sector_major')
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        for path in children:
            if len(path) != len(source_path) // Q:
                raise ValueError('Spiral Q child has the wrong q-lane cohort.')
            database.append([len(database) + 1, path])
    starts = [path[0] for _, path in database]
    _validate_generated_layout_consistency(pattern, starts, database, winding)
    records = phase_map(winding.num_slots, winding.num_poles,
                        winding.num_layers, layout.phase_shift_list,
                        winding.num_phases)
    electrical = validate_branches(
        [path for _, path in database], records, winding.num_slots,
        winding.num_poles, winding.ab, winding.num_phases)
    if not electrical['layout_retained']:
        raise ValueError('Spiral Q+PP cut fails complete-path retention.')
    if any(abs(complex(*voltage)) < 1e-12
           for values in electrical['branch_emf'].values()
           for voltage in values):
        raise ValueError('Spiral Q+PP cut has a zero branch fundamental.')
    return starts, database


def _slp_q_pp_parent_cut_weld_from_reference(tp, winding, layout):
    """Rotate admitted single-sector Q+PP children and record every edge step."""
    factors = _integer_divider_tuple(winding.branch_dividers)
    if not supports_slp_q_pp_single_sector_weld(winding, factors):
        raise ValueError(
            'SLP Q+PP weld rotation requires one complete PP sector per child.')
    source_layout = (layout._replace(inlet_from_weld_side=0)
                     if hasattr(layout, '_replace') else
                     SimpleNamespace(**{**vars(layout),
                                        'inlet_from_weld_side': 0}))
    _, insert_database = _spiral_q_pp_from_pp_parent(
        'SLP', tp, winding, source_layout)
    children, closing_step = slp_q_pp_single_sector_weld_rotation(
        insert_database, dividers=factors, q=winding.q,
        pp=winding.num_poles // 2, phase_count=winding.num_phases,
        num_slots=winding.num_slots)

    database = _CandidateBranches()
    signed_travel = {}
    pole_region_width = winding.num_phases * winding.q
    for child in children:
        branch_id = child.source_ids[0]
        path = child.path
        steps = []
        for index, (start, end) in enumerate(zip(path, path[1:])):
            vector = find_single_connection_between(
                start, end, winding, source_layout)
            step = (vector[0] * pole_region_width
                    + end[2] - start[2])
            if (start[0] + step) % winding.num_slots != end[0]:
                raise ValueError(
                    f'SLP branch {branch_id} connector travel does not match its endpoints.')
            if index == len(path) - 2 and step != closing_step:
                raise ValueError(
                    f'SLP branch {branch_id} weld seam disagrees with the derived one-sector step.')
            steps.append(step)
        database.append([branch_id, path])
        signed_travel[branch_id] = tuple(steps)
    database.signed_travel = signed_travel
    return [path[0] for _, path in database], database


def _ssp_reflected_p2(tp, winding, layout):
    """Reflect the second q-only cohort in layer and pole travel, keeping q lanes."""
    reference = SimpleNamespace(**vars(winding))
    reference.branch_dividers = (2, 1, 1)
    _, source = pattern_SSP(tp, reference, layout)
    slots, q, layers = winding.num_slots, winding.q, winding.num_layers
    shifts = layout.phase_shift_list
    database = _CandidateBranches()
    for branch_id, path in source:
        inlet = path[0][0] - shifts[path[0][1]]
        if inlet % q >= q // 2:
            anchor = inlet - inlet % q
            reflected = []
            for slot, layer, position in path:
                unshifted = slot - shifts[layer]
                belt, lane = divmod(unshifted, q)
                target_layer = layers-1-layer
                target_slot = (2*anchor-belt*q+lane+shifts[target_layer]) % slots
                reflected.append((target_slot, target_layer, position))
            path = reflected
        database.append([branch_id, path])
    # Auto may change insertion returns; welds still follow the layer-pair direction.
    for _, path in database:
        for a, b in zip(path[::2], path[1::2]):
            low, high = sorted((a, b), key=lambda node: node[1])
            low_slot = (low[0] - shifts[low[1]]) % slots
            high_slot = (high[0] - shifts[high[1]]) % slots
            if (high[1] - low[1] != 1
                    or not any(step > 0 for step in circular_travel_steps(
                        low_slot, high_slot, slots))):
                raise ValueError('SSP reflected P2 requires uniform forward welds per layer pair.')
    return [path[0] for _, path in database], database


def supports_zlp_p2_mirrored(winding, factors):
    """P2 splits an oriented ZLP phase path into layer-mirrored halves."""
    return (tuple(factors) == (1, 1, 2)
            and type(winding.q) is int and winding.q > 0
            and winding.ab == 2 and winding.num_poles > 0
            and winding.num_poles % 2 == 0
            and winding.num_layers >= 2 and winding.num_layers % 2 == 0
            and _supported_phase_domain(winding))


def supports_zlp_pp_p2_source_cut(winding, factors):
    """Divide each complete P2 branch into whole PP-sector children."""
    values = _integer_divider_tuple(factors)
    if (values is None or type(winding.q) is not int or winding.q < 1
            or winding.num_poles <= 0 or winding.num_poles % 2):
        return False
    Q, D, P2 = values
    pp = winding.num_poles // 2
    # Keep existing classifier-default ZLP layouts on their original route.
    if values == tuple(classify_branch_mode(
            winding.ab, winding.q, winding.num_poles, 'ZLP')[1:4]):
        return False
    return bool(Q == 1 and D > 1 and P2 == 2
                and pp > 0 and winding.num_poles == 2 * pp
                and pp % D == 0 and winding.ab == 2 * D
                and winding.num_layers >= 2 and winding.num_layers % 2 == 0
                and _supported_phase_domain(winding))


def _zlp_pp_p2_from_p2_parent(tp, winding, layout):
    """Cut validated ZLP P2 paths at equal complete-sector boundaries."""
    fields = (vars(winding) if hasattr(winding, '__dict__')
              else winding._asdict())
    reference = SimpleNamespace(**fields)
    reference.ab = 2
    reference.branch_dividers = (1, 1, 2)
    _, parent = get_winding_layout('ZLP', tp, reference, layout)
    pieces = apply_route_formula(
        'zlp_pp_p2_source_cut', parent, tuple(winding.branch_dividers))
    database = _CandidateBranches()
    for piece in pieces:
        width = len(piece.path)
        if width % 2:
            raise ValueError('ZLP PP child breaks an insertion/weld pair.')
        database.append([len(database) + 1, piece.path])
    starts = [path[0] for _, path in database]
    _validate_generated_layout_consistency('ZLP', starts, database, winding)
    records = phase_map(winding.num_slots, winding.num_poles,
                        winding.num_layers, layout.phase_shift_list,
                        winding.num_phases)
    electrical = validate_branches(
        [path for _, path in database], records, winding.num_slots,
        winding.num_poles, winding.ab, winding.num_phases)
    if not electrical['layout_retained']:
        raise ValueError('ZLP PP+P2 cut fails complete-path retention.')
    if any(abs(complex(*voltage)) < 1e-12
           for values in electrical['branch_emf'].values()
           for voltage in values):
        raise ValueError('ZLP PP+P2 cut has a zero branch fundamental.')
    return starts, database


def _zlp_p2_from_reference(tp, winding, layout):
    """Mirror each phase's N-to-S reference half across slot and layer axes."""
    reference = SimpleNamespace(
        q=winding.q, num_slots=winding.num_slots,
        num_poles=winding.num_poles, num_phases=winding.num_phases,
        num_layers=winding.num_layers, ab=1, branch_dividers=(1, 1, 1))
    _, source = pattern_ZLP(tp, reference, layout)
    shifts = layout.phase_shift_list
    slots, layers, q = winding.num_slots, winding.num_layers, winding.q
    pole_map = {(slot, layer): (phase, sign)
                for slot, layer, phase, sign in phase_map(
                    slots, winding.num_poles, layers, shifts,
                    winding.num_phases)}
    phase_paths = {}
    for _, path in source:
        phase = pole_map[path[0][:2]][0]
        if phase in phase_paths:
            raise ValueError(f'ZLP P2 reference has multiple phase {phase} paths.')
        phase_paths[phase] = path
    if len(phase_paths) != winding.num_phases:
        raise ValueError('ZLP P2 reference does not cover every phase.')

    database = _CandidateBranches()
    for phase in range(winding.num_phases):
        path = list(phase_paths[phase])
        if pole_map[path[0][:2]][1] != 1:
            path.reverse()
        if len(path) % 2:
            raise ValueError('ZLP P2 reference cannot be split into equal branches.')
        first = path[:len(path) // 2]
        # Reflect the first half onto the other conductor positions of this
        # phase. Each layer pair beyond the first advances the mirror axis by
        # one full m-phase q belt; this reduces to the prior axis at m=3.
        axis = ((winding.num_phases * (layers - 2) + 1) * q - 1
                + 2 * q * phase) % slots
        second = []
        for slot, layer, _position in first:
            target_layer = layers - 1 - layer
            unshifted = (slot - shifts[layer]) % slots
            target_slot = (axis - unshifted + shifts[target_layer]) % slots
            second.append((target_slot, target_layer,
                           (target_slot - shifts[target_layer]) % q))
        for branch in (first, second):
            database.append([len(database) + 1, branch])
    return [path[0] for _, path in database], database


def _selected_integer_divider_route(pattern, winding):
    """Name an admitted non-default factor route; generation still validates it."""
    selected = getattr(winding, 'branch_dividers', None)
    if selected is None or Fraction(str(winding.q)).denominator != 1:
        return None
    if (pattern == 'CP'
            and _cp_layer_admission_reason(winding)):
        return None
    factors = _integer_divider_tuple(selected)
    if factors is None:
        return None
    if pattern_rejects_divider_tuple(
            pattern, factors, winding.q, winding.num_poles // 2):
        return None
    if pattern == 'SSP' and supports_ssp_reflected_p2(winding, factors):
        return 'ssp_p2_reflected'
    if pattern == 'SLP' and supports_slp_p2_from_reference(winding, factors):
        return 'slp_p2_from_reference'
    if pattern == 'SLP' and supports_slp_full_q_p2(winding, factors):
        return 'slp_full_q_p2'
    if pattern == 'SLP' and supports_slp_q_pp_p2_parent_cut(
            winding, factors):
        return 'slp_q_pp_p2_parent_cut'
    if pattern == 'SLP' and supports_slp_pair_lane_p2(winding, factors):
        return 'slp_pair_lane_p2'
    if pattern == 'SLP' and supports_slp_pp_p2_sector(winding, factors):
        return 'slp_pp_p2_sector'
    if pattern == 'ZLP' and supports_zlp_p2_mirrored(winding, factors):
        return 'zlp_p2_mirrored'
    if pattern == 'ZLP' and supports_zlp_pp_p2_source_cut(winding, factors):
        return 'zlp_pp_p2_source_cut'
    if pattern == 'TLP' and supports_integer_tlp_q_only_pair_join(
            winding, factors):
        return 'tlp_q_only_pair_join'
    if pattern == 'TLP' and supports_tlp_pp_only_two(winding, factors):
        return 'tlp_pp_only_two'
    if pattern == 'TLP' and supports_tlp_pp_only_even(winding, factors):
        return 'tlp_pp_only_even'
    if pattern == 'TLP' and supports_tlp_pp_p2_short_unit(winding, factors):
        return 'tlp_pp_p2_short_unit'
    if pattern == 'TLP' and supports_tlp_q_pp_p2_parent_slices(
            winding, factors):
        return 'tlp_q_pp_p2_parent_slices'
    if pattern == 'TSP' and supports_integer_tsp_pp_only_q_p2_identity(
            winding, factors):
        return 'tsp_pp_only_q_p2_identity'
    if pattern == 'TSP' and supports_integer_tsp_q_only_pair_join(
            winding, factors):
        return 'tsp_q_only_pair_join'
    if pattern == 'TSP' and supports_integer_tsp_pp_p2_sector(
            winding, factors):
        return 'tsp_pp_p2_sector'
    if pattern == 'UWP' and supports_uwp_short_p2_weld(winding, factors):
        return 'uwp_short_p2_weld'
    if supports_q_pp_two_reference(pattern, winding, factors):
        # Existing ZPP Q*P2=q routes retain their established construction.
        if not (pattern == 'ZPP' and factors[0] == winding.q):
            return f'{pattern.lower()}_q_pp_two'
    if (pattern == 'UWP' and factors[1:] == (1,1)
            and 1 < factors[0] < winding.q and winding.q % factors[0] == 0
            and winding.ab == factors[0]
            and winding.num_poles > 0 and winding.num_poles % 2 == 0
            and winding.num_layers >= 2 and winding.num_layers % 2 == 0
            and _supported_phase_domain(winding)):
        return 'uwp_q_only_series'
    if pattern == 'CP' and supports_integer_cp_pp_four_pass_weave(
            winding, factors):
        return 'cp_pp_four_pass_weave'
    if pattern == 'CP' and supports_integer_cp_q_only_pair_join(winding, factors):
        return 'cp_q_only_pair_join'
    if pattern == 'CP' and supports_integer_cp_q_pp_full_parent_slices(
            winding, factors):
        return 'cp_q_pp_full_parent_slices'
    if pattern == 'CP' and supports_integer_cp_q_pp_p2_parent_slices(
            winding, factors):
        return 'cp_q_pp_p2_parent_slices'
    if pattern == 'CP' and supports_integer_cp_pp_parent_half_translation(
            winding, factors):
        return 'cp_pp_parent_half_translation'
    if pattern == 'CP' and supports_integer_cp_pp_sector_slices(
            winding, factors):
        return 'cp_pp_sector_slices'
    if (pattern == 'ZPP'
            and supports_integer_zpp_pp_only_centered_entry_translation(
                winding, factors)):
        return 'zpp_pp_only_centered_entry_translation'
    if pattern == 'ZPP' and supports_integer_zpp_pp_only_indexed_translation(
            winding, factors):
        return ('zpp_pp_only_half_turn' if factors[1] == 2 else
                'zpp_pp_only_indexed_translation')
    is_default = factors == classify_branch_mode(
        winding.ab, winding.q, winding.num_poles, pattern)[1:4]
    if (pattern == 'TSP' and (not is_default or factors[1] > 1)
            and supports_integer_tsp_spiral_pass_partition(winding, factors)):
        return 'tsp_spiral_pass_partition'
    if is_default and not (pattern == 'UWP'
                           and supports_uwp_balanced_q_factor(winding, factors)):
        return None
    if supports_spiral_q_pp_parent_cut(pattern, winding, factors):
        return f'{pattern.lower()}_q_pp_parent_cut'
    if (pattern == 'BWP' and 1 < factors[0] < winding.q
            and winding.q % factors[0] == 0 and factors[1] > 1 and factors[2] == 1
            and winding.num_poles > 0 and winding.num_poles % 2 == 0
            and (winding.num_poles//2) % factors[1] == 0
            and winding.ab == factors[0]*factors[1]
            and winding.num_layers >= 2 and winding.num_layers % 2 == 0
            and _supported_phase_domain(winding)):
        return 'bwp_q_pp'
    if (factors == (1, winding.ab, 1) and winding.ab > 1
            and (winding.num_poles // 2) % winding.ab == 0):
        if pattern == 'BWP':
            return 'bwp_pp'
        if supports_integer_pp_only(pattern, winding.q, winding.num_poles,
                                    winding.num_layers, winding.num_phases,
                                    winding.ab):
            return 'pp_only'
    if pattern == 'CP' and supports_integer_cp_pp_p2(winding, factors):
        return 'cp'
    if pattern == 'ZPP' and supports_integer_zpp_factors(winding, factors):
        return 'zpp'
    if pattern == 'ZLP' and supports_integer_zlp_factors(winding, factors):
        return 'zlp'
    if pattern == 'UWP' and supports_uwp_balanced_q_factor(winding, factors):
        return 'uwp_balanced_q'
    if pattern == 'UWP' and supports_uwp_proper_q_factor(winding, factors):
        return ('uwp_q_factor_p2' if factors[2] == 2
                else 'uwp_q_factor_pp')
    return None


def _supported_phase_domain(winding):
    return supports_phase_count(getattr(winding, 'num_phases', 0))


def _effective_tp_type(tp_info, winding=None):
    """Resolve a neutral Auto display value before capability checks."""
    tp_type = getattr(tp_info, 'tp_type', 'Regular') if tp_info is not None else 'Regular'
    if auto_tp.is_auto_type(tp_type):
        fields = ('tp_interval', 'tp_times', 'uni_tp', 'pltp_fl', 'pltp_ll', 'jltp')
        modulus = int(getattr(winding, 'q', 0) or 0)
        def is_zero(field):
            value = getattr(tp_info, field, 0)
            if field in ('uni_tp', 'pltp_fl', 'pltp_ll', 'jltp') and modulus:
                return int(value) % modulus == 0
            return value == 0
        if all(is_zero(field) for field in fields):
            return 'Regular'
    return tp_type


def _normalized_tp_info(tp_info, winding=None):
    """Return an effective TP payload; neutral Auto is Regular, not a route."""
    effective = _effective_tp_type(tp_info, winding)
    if tp_info is None or effective == getattr(tp_info, 'tp_type', 'Regular'):
        return tp_info
    values = {field: getattr(tp_info, field, 0)
              for field in auto_tp.TP_FIELD_NAMES}
    values.update(
        tp_type=effective,
        jld=getattr(tp_info, 'jld', 1),
        pole_group_tp=getattr(tp_info, 'pole_group_tp', {}),
        tp_start_index=getattr(tp_info, 'tp_start_index', 0))
    return SimpleNamespace(**values)


def _configuration_preflight(pattern, tp_info, winding, layout):
    """Reject invalid or inapplicable UI payloads before construction."""
    if tp_info is None or layout is None:
        return None
    effective = _effective_tp_type(tp_info, winding)
    if effective not in ('Regular', 'Times', 'Interval'):
        return 'Auto does not resolve to a supported effective TP payload.'
    try:
        branch_conductors = int(
            winding.num_poles * winding.num_layers * winding.q / winding.ab)
    except (TypeError, ValueError, ZeroDivisionError):
        return 'Cannot derive the number of usable branch connection positions.'
    usable_edges = max(branch_conductors - 1, 0)
    if effective == 'Times':
        times = getattr(tp_info, 'tp_times', 0)
        if type(times) is not int or not 1 <= times <= usable_edges:
            return (f'Times requires 1 <= tp_times <= {usable_edges} for '
                    'the available branch edges.')
    if effective == 'Interval':
        interval = getattr(tp_info, 'tp_interval', 0)
        if type(interval) is not int or not 1 <= interval <= usable_edges:
            return (f'Interval requires 1 <= tp_interval <= {usable_edges}; '
                    'larger values have no usable transposition position.')
    for field in auto_tp.TP_FIELD_NAMES:
        if type(getattr(tp_info, field, 0)) is not int:
            return f'{field} must be an integer.'
    pole_group_tp = getattr(tp_info, 'pole_group_tp', {}) or {}
    if pattern not in ('UWP',) and any(
            spec.get('tp_type', 'Regular') != 'Regular'
            or any(int(spec.get(field, 0)) % int(winding.q) != 0
                   for field in ('uni_tp', 'pltp_fl', 'pltp_ll', 'jltp'))
            or any(spec.get(field, 0) != 0
                   for field in ('tp_interval', 'tp_times'))
            for spec in pole_group_tp.values()):
        return f'{pattern} does not implement independent PoleN/PoleS TP payloads.'
    shifts = tuple(getattr(layout, 'phase_shift_list', ()))
    if len(shifts) != winding.num_layers:
        return 'phase_shift_list length must equal the number of layers.'
    if any(type(shift) is not int for shift in shifts):
        return 'Every layer phase shift must be an integer slot offset.'
    adjustments = tuple(getattr(
        layout, 'inlet_index_adjustments_phase_a', ()) or ())
    if len(adjustments) > winding.ab or any(type(value) is not int
                                            for value in adjustments):
        return 'Inlet adjustments must be integer indices for at most Naa branches.'
    return None


def _transposition_is_neutral(tp_info, winding):
    if tp_info is None:
        return True
    effective = _effective_tp_type(tp_info, winding)
    if effective != 'Regular':
        return False
    modulus = int(winding.q)
    offset_fields = ('uni_tp', 'pltp_fl', 'pltp_ll', 'jltp')
    if any(int(getattr(tp_info, field, 0)) % modulus for field in offset_fields):
        return False
    if any(getattr(tp_info, field, 0) for field in ('tp_interval', 'tp_times')):
        return False
    if any(spec.get('tp_type', 'Regular') != 'Regular'
           or any(int(spec.get(field, 0)) % modulus for field in offset_fields)
           or any(spec.get(field, 0) for field in ('tp_interval', 'tp_times'))
           for spec in (getattr(tp_info, 'pole_group_tp', {}) or {}).values()):
        return False
    return True


def _configuration_is_neutral(tp_info, layout, weld_side, winding):
    if tp_info is None or layout is None:
        return True
    if not _transposition_is_neutral(tp_info, winding):
        return False
    shifts = tuple(getattr(layout, 'phase_shift_list', ()))
    if any(int(shift) % winding.num_slots for shift in shifts):
        return False
    branch_length = max(int(
        winding.num_poles * winding.num_layers * winding.q / winding.ab), 1)
    adjustments = tuple(getattr(
        layout, 'inlet_index_adjustments_phase_a', ()) or ())
    normalized = SimpleNamespace(
        tp_type='Regular',
        pole_group_tp={name: {
            'tp_type': 'Regular', 'tp_interval': 0, 'tp_times': 0,
            'uni_tp': 0, 'pltp_fl': 0, 'pltp_ll': 0, 'jltp': 0}
            for name in (getattr(tp_info, 'pole_group_tp', {}) or {})},
        tp_interval=0, tp_times=0, uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0)
    neutral_layout = SimpleNamespace(
        phase_shift_pattern='None', phase_shift_list=[0] * winding.num_layers,
        radial_shift=getattr(layout, 'radial_shift', 0),
        inlet_from_weld_side=getattr(layout, 'inlet_from_weld_side', 0),
        inlet_index_adjustments_phase_a=[
            value % branch_length for value in adjustments])
    return pp_only_configuration_is_unshifted(
        normalized, neutral_layout, weld_side=weld_side)


def _layout_configuration_is_neutral(layout, weld_side, winding):
    """Check layout restrictions without blocking manual transposition fields.

    The constructors consume TP settings and the public output validators check
    their result. Manual input does not require an Auto recipe's private token.
    """
    neutral_tp = SimpleNamespace(tp_type='Regular')
    return _configuration_is_neutral(neutral_tp, layout, weld_side, winding)


def _post_connection_shift_requested(layout, winding):
    if layout is None or getattr(winding, 'num_slots', 0) <= 0:
        return False
    shifts = getattr(layout, 'phase_shift_list', None)
    return (shifts is not None and len(shifts) == winding.num_layers
            and all(type(value) is int for value in shifts)
            and (bool(getattr(layout, 'radial_shift', 0))
                 or any(value % winding.num_slots for value in shifts)))


def _without_post_connection_shifts(layout, winding):
    values = dict(layout._asdict() if hasattr(layout, '_asdict') else vars(layout))
    values.update(phase_shift_pattern='None', phase_shift=0, PSL=0,
                  phase_shift_list=[0] * winding.num_layers, radial_shift=0)
    return SimpleNamespace(**values)


def _bwp_q_pp_configuration_failure(tp_info, layout, winding):
    """Check a BWP Q+PP request against its generated edges and body pins."""
    if tp_info is None or layout is None:
        return None
    shifts = tuple(getattr(layout, 'phase_shift_list', ()))
    if (len(shifts) != winding.num_layers
            or any(type(shift) is not int for shift in shifts)):
        return 'BWP Q+PP requires one integer slot shift per layer.'
    if (getattr(layout, 'radial_shift', 0)
            or any(getattr(layout, 'inlet_index_adjustments_phase_a', ()) or ())):
        return 'BWP Q+PP does not support radial shift or inlet adjustment.'
    try:
        starts, database = pattern_BWP(tp_info, winding, layout)
        _validate_generated_layout_consistency('BWP', starts, database, winding)
        validate_selected_bwp_pp(database, winding, layout)
        from layout_analysis import analyze_pattern_identity
        identity = analyze_pattern_identity('BWP', database, winding, layout)
        if identity['status'] != 'valid':
            return 'BWP Q+PP body pin types: ' + identity['reason']
    except (ValueError, TypeError, IndexError, ZeroDivisionError) as exc:
        return f'BWP Q+PP configuration cannot form valid connections: {exc}'
    return None


def _phase_topology_for_winding(winding, layout=None):
    """Build one canonical topology from a winding and its layer shifts."""
    shifts = getattr(layout, 'phase_shift_list', None) if layout is not None else None
    return build_winding_phase_topology(winding, shifts)


def _is_tlp_full_q_even_array_request(winding, factors):
    values = _integer_divider_tuple(factors)
    q = getattr(winding, 'q', None)
    return bool(
        values is not None and type(q) is int and q > 1
        and values[0] == q and values[1] > 2 and values[2] == 1)


def _tlp_full_q_even_array_local_dividers(winding, factors, set_count):
    """Map full-Q TLP factors into a layer-assigned three-phase set."""
    if not _is_tlp_full_q_even_array_request(winding, factors):
        return None
    try:
        local = phase_set_local_dividers(tuple(factors), set_count)
    except ValueError:
        return None
    local_divider = local[1]
    pp = int(winding.num_poles) // 2
    if (local_divider < 4 or local_divider % 2
            or pp % int(factors[1]) or pp % local_divider
            or int(winding.num_layers) % set_count):
        return None
    local_layers = int(winding.num_layers) // set_count
    if local_layers < 4 or local_layers % 2:
        return None
    return local


def _phase_array_local_inputs(winding, layout, phase_set_spec, factors,
                              pattern=None):
    """Build one locally indexed 3-phase set from its canonical set spec."""
    if len(phase_set_spec.phases) != 3:
        raise ValueError('Pattern constructors require a three-phase local set.')
    source_winding = (vars(winding) if hasattr(winding, '__dict__')
                      else winding._asdict())
    local_winding = dict(source_winding)
    local_factors = tuple(factors)
    set_count = three_phase_set_count(winding.num_phases)
    if (pattern == 'TLP' and set_count > 1
            and _is_tlp_full_q_even_array_request(winding, factors)):
        local_factors = _tlp_full_q_even_array_local_dividers(
            winding, factors, set_count)
        if local_factors is None:
            raise ValueError(
                'TLP full-Q PP factors have no validated local phase-set mapping.')
    local_winding.update(
        q=(int(phase_set_spec.local_q)
           if phase_set_spec.local_q.denominator == 1
           else phase_set_spec.local_q),
        num_slots=phase_set_spec.local_slots, num_phases=3,
        num_layers=phase_set_spec.layer_count,
        branch_dividers=local_factors)
    if pattern == 'CP':
        local_winding['_cp_array_global_layers'] = winding.num_layers

    source_layout = (vars(layout) if hasattr(layout, '__dict__')
                     else layout._asdict() if layout is not None else {})
    local_layout = dict(source_layout)
    shifts = getattr(layout, 'phase_shift_list', None)
    if shifts is not None:
        if len(shifts) != winding.num_layers:
            raise ValueError('One integer slot shift is required per layer.')
        local_layout['phase_shift_list'] = list(
            shifts[phase_set_spec.layer_start:
                   phase_set_spec.layer_start + phase_set_spec.layer_count])
    else:
        local_layout['phase_shift_list'] = [0] * phase_set_spec.layer_count
    return SimpleNamespace(**local_winding), SimpleNamespace(**local_layout)


def _phase_array_local_route_decisions(pattern, winding, factors,
                                       configuration, layout, outer_decision,
                                       topology=None):
    """Resolve the selected divider factors in every local 3-phase set."""
    topology = topology or _phase_topology_for_winding(winding, layout)
    if topology.phase_model != 'arrayed_three_phase_sets':
        return (), 'This winding is not an array of independent three-phase sets.'
    decisions = []
    for phase_set_spec in topology.phase_sets:
        try:
            local_winding, local_layout = _phase_array_local_inputs(
                winding, layout, phase_set_spec, factors, pattern)
        except (TypeError, ValueError, ZeroDivisionError) as exc:
            return (), f'Phase set {phase_set_spec.set_index + 1}: {exc}'
        try:
            local_topology = _phase_topology_for_winding(local_winding, local_layout)
        except (TypeError, ValueError, ZeroDivisionError) as exc:
            return (), (f'Phase set {phase_set_spec.set_index + 1} has an '
                        f'invalid phase topology: {exc}')
        local_factors = factors
        if (pattern == 'TLP'
                and _is_tlp_full_q_even_array_request(winding, factors)):
            local_factors = local_winding.branch_dividers
        local = resolve_pattern_route(
            pattern, local_winding, local_factors, configuration, local_layout,
            topology=local_topology)
        if local.status not in ('enabled', 'candidate'):
            return (), (f'Phase set {phase_set_spec.set_index + 1} rejects the selected '
                        f'construction: {local.reason}')
        decisions.append(local)
    return tuple(decisions), None


def _resolve_phase_array_route(pattern, winding, factors, configuration,
                               layout, outer_decision, topology=None):
    """Admit an array only when all local constructors and the full array pass."""
    topology = topology or _phase_topology_for_winding(winding, layout)
    pp = winding.num_poles // 2
    q = Fraction(str(winding.q))
    if (pattern == 'TLP' and len(factors) == 3
            and factors[0] == 2 and factors[1] > 1 and factors[2] == 2
            and q.denominator == 1 and q.numerator >= 2
            and q.numerator % 2 == 0 and pp % factors[1] == 0
            and 2 * factors[1] <= pp
            and any(spec.layer_count < 4 or spec.layer_count % 2
                    for spec in topology.phase_sets)):
        return PatternRouteDecision(
            'disabled', 'tlp_q_pp_p2_local_layers_unsupported',
            'The current TLP (2,D,2) parent-slice constructor requires at '
            'least four even layers in each local three-phase set. Short '
            'local sets remain a construction boundary, not a physical '
            'impossibility result.', pattern, tuple(factors),
            admission='unsupported-yet')
    local_decisions, failure = _phase_array_local_route_decisions(
        pattern, winding, factors, configuration, layout, outer_decision,
        topology)
    if failure:
        return PatternRouteDecision(
            'disabled', 'phase_set_route_mismatch', failure, pattern,
            tuple(factors), outer_decision.route_name,
            outer_decision.pin_profile, outer_decision.required_inlet,
            outer_decision.effective_configuration, outer_decision.is_default)

    route_names = {item.route_name for item in local_decisions}
    route_name = (next(iter(route_names)) if len(route_names) == 1
                  else 'three_phase_set_array')
    q = Fraction(str(winding.q))
    if (pattern == 'TSP' and q.denominator != 1
            and 'tsp_spiral_pass_partition' in route_names):
        return PatternRouteDecision(
            'disabled', 'tsp_pass_partition_integer_scope',
            'TSP spiral pass partition is registered for integer global q; '
            'fractional-global-q phase arrays remain unsupported-yet for this family.',
            pattern, tuple(factors), admission='unsupported-yet')
    q_value = int(q) if q.denominator == 1 else q
    status, reason = _cached_neutral_non_wave_preflight(
        pattern, q_value, int(winding.num_poles),
        int(winding.num_phases), int(winding.num_layers), int(winding.ab),
        tuple(factors), outer_decision.required_inlet == 'weld', route_name)
    if status == 'disabled':
        return PatternRouteDecision(
            'disabled', 'phase_set_array_structural_failure', reason, pattern,
            tuple(factors), outer_decision.route_name,
            outer_decision.pin_profile, outer_decision.required_inlet,
            outer_decision.effective_configuration, outer_decision.is_default)
    candidate = (status == 'candidate'
                 or any(item.status == 'candidate' for item in local_decisions))
    rule_ids = {item.rule_id for item in local_decisions}
    rule_id = (next(iter(rule_ids)) if len(rule_ids) == 1
               else 'multiphase_three_phase_array')
    set_count = len(local_decisions)
    return PatternRouteDecision(
        'candidate' if candidate else 'enabled', rule_id,
        f'All {set_count} layer-assigned three-phase sets preserve the selected '
        f'route and pass local construction checks. {reason}', pattern,
        tuple(factors), route_name, outer_decision.pin_profile,
        outer_decision.required_inlet, outer_decision.effective_configuration,
        outer_decision.is_default)


def resolve_pattern_route(pattern, winding, dividers=None, configuration=None,
                          layout=None, topology=None):
    """Classify one Pattern/divider/configuration request before generation.

    The resolver owns admission. Arithmetic factorization alone never enables a
    route: an explicit constructor, edge oracle, pin profile, and configuration
    capability must all be present.
    """
    pattern = normalize_pattern_name(pattern, allow_extra=False)
    if _post_connection_shift_requested(layout, winding):
        layout = _without_post_connection_shifts(layout, winding)
        topology = None
    try:
        topology = topology or _phase_topology_for_winding(winding, layout)
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        phases = getattr(winding, 'num_phases', 0)
        if not supports_phase_count(phases):
            topology_rule = 'unsupported_phase_count'
        elif (three_phase_set_count(phases) > 1
              and not supports_phase_layer_allocation(
                  phases, getattr(winding, 'num_layers', 0))):
            topology_rule = 'unsupported_phase_layer_allocation'
        else:
            topology_rule = 'phase_division_infeasible'
        return PatternRouteDecision(
            'disabled', topology_rule, str(exc), pattern,
            _integer_divider_tuple(dividers if dividers is not None else
                                   getattr(winding, 'branch_dividers', None)))
    phases = topology.phases
    layers = topology.layers
    set_count = topology.set_count
    selected = (getattr(winding, 'branch_dividers', None)
                if dividers is None else dividers)
    if pattern == 'CP':
        layer_reason = _cp_layer_admission_reason(winding)
        if layer_reason:
            return PatternRouteDecision(
                'disabled', 'cp_layer_multiple_of_four', layer_reason,
                pattern, _integer_divider_tuple(selected))
    fractional_decision = _half_integer_route_decision(
        pattern, winding, selected, configuration, layout)
    if fractional_decision is not None:
        if set_count > 1:
            if fractional_decision.status in ('enabled', 'candidate'):
                return _resolve_phase_array_route(
                    pattern, winding,
                    fractional_decision.dividers or selected,
                    configuration, layout, fractional_decision, topology)
            # A half-integer global q can become an ordinary integer-q route
            # inside each 3-phase set. Let the local public resolver decide
            # that construction when the selected tuple is integral.
            local_factors = _integer_divider_tuple(
                selected if selected is not None else fractional_decision.dividers)
            if local_factors is None:
                return fractional_decision
            selected = local_factors
        else:
            return fractional_decision
    if selected is None:
        try:
            selected = classify_branch_mode(
                winding.ab, winding.q, winding.num_poles, pattern)[1:4]
        except (TypeError, ValueError, ZeroDivisionError) as exc:
            return PatternRouteDecision(
                'disabled', 'invalid_dividers', str(exc), pattern, None)
    factors = _integer_divider_tuple(selected)
    if factors is None:
        return PatternRouteDecision(
            'disabled', 'invalid_dividers',
            'Q, PP and P2 dividers must be three positive integers.',
            pattern, None)
    if any(value <= 0 for value in factors):
        return PatternRouteDecision(
            'disabled', 'invalid_dividers',
            'Q, PP and P2 dividers must be positive integers.',
            pattern, factors)
    if factors[0] * factors[1] * factors[2] != winding.ab:
        return PatternRouteDecision(
            'disabled', 'divider_product_mismatch',
            'Q x PP x P2 must equal Naa.', pattern, factors)

    pp = winding.num_poles // 2
    if (pattern == 'TSP' and pattern_rejects_divider_tuple(
            pattern, factors, winding.q, pp, winding.num_layers)):
        return PatternRouteDecision(
            'disabled', 'tsp_branch_length_rejected',
            divider_exclusion_reason(
                pattern, factors, winding.q, pp, winding.num_layers),
            pattern, factors)

    if set_count > 1:
        if (pattern == 'TLP'
                and _is_tlp_full_q_even_array_request(winding, factors)
                and _tlp_full_q_even_array_local_dividers(
                    winding, factors, set_count) is None):
            return PatternRouteDecision(
                'disabled', 'tlp_pp_only_even_array_unsupported',
                'The full-Q TLP divider triple must map to an even local PP '
                'divider of at least four and at least four local layers.',
                pattern, factors, admission='unsupported-yet')
        if (pattern == 'TSP' and factors[0] == 1
                and factors[1] > 1 and factors[2] == 2):
            for spec in topology.phase_sets:
                try:
                    local_winding, _local_layout = _phase_array_local_inputs(
                        winding, layout, spec, factors, pattern)
                except (TypeError, ValueError, ZeroDivisionError) as exc:
                    return PatternRouteDecision(
                        'disabled', 'tsp_pp_p2_sector_local_domain_unsupported',
                        f'Phase set {spec.set_index + 1}: {exc}', pattern,
                        factors, admission='unsupported-yet')
                if not (supports_integer_tsp_pp_p2_sector(local_winding, factors)
                        or supports_integer_tsp_spiral_pass_partition(
                            local_winding, factors)):
                    return PatternRouteDecision(
                        'disabled', 'tsp_pp_p2_sector_local_domain_unsupported',
                        'TSP PP+P2 fixed-lane formula is unsupported-yet for '
                        f'phase set {spec.set_index + 1}: each local q lane must '
                        'cover every pole pair exactly once for the selected D '
                        'and layer count.', pattern, factors,
                        admission='unsupported-yet')
        if (pattern == 'ZPP' and factors[0] == 1
                and factors[1] > 1 and factors[2] == 1):
            q_value = Fraction(str(winding.q))
            pp = winding.num_poles // 2
            divider = factors[1]
            if (q_value.denominator == 1 and pp > 0 and pp % divider == 0
                    and zpp_indexed_sector_stride(
                        divider, pp // divider) > 1):
                return PatternRouteDecision(
                    'disabled', 'zpp_array_stride_unvalidated',
                    'Variable-stride ZPP is not admitted for arrayed phase sets '
                    'until mapped global signed edges pass the one-pole-region check.',
                    pattern, factors, admission='unsupported-yet')
        try:
            q = Fraction(str(winding.q))
            default_factors = (tuple(classify_branch_mode(
                winding.ab, q.numerator, winding.num_poles, pattern)[1:4])
                if q.denominator == 1 else None)
        except (TypeError, ValueError, ZeroDivisionError) as exc:
            return PatternRouteDecision(
                'disabled', 'invalid_dividers', str(exc), pattern, factors)
        global_default = (factors == default_factors if default_factors is not None
                          else bool(fractional_decision and
                                    fractional_decision.is_default))
        rule_id = f'{pattern.lower()}_three_phase_set_array'
        pin_profile = PATTERN_DEFAULT_PIN_PROFILES.get(pattern, ())
        required_inlet = ('weld' if pattern_requires_weld_side_inlet(pattern)
                          else 'insert')
        if (pattern == 'SLP' and layout is not None
                and getattr(layout, 'inlet_from_weld_side', False)):
            required_inlet = 'weld'
        outer_decision = PatternRouteDecision(
            'enabled', rule_id, 'Checking each local three-phase construction.',
            pattern, factors, None, pin_profile, required_inlet,
            _effective_tp_type(configuration, winding), global_default)
        return _resolve_phase_array_route(
            pattern, winding, factors, configuration, layout, outer_decision,
            topology)

    pp = winding.num_poles // 2
    if pattern_rejects_divider_tuple(pattern, factors, getattr(winding, 'q', None), pp):
        rule_id = ({'LPP': 'lpp_factor_rejected'}.get(
                        pattern, f'{pattern.lower()}_factor_rejected'))
        return PatternRouteDecision(
            'disabled', rule_id,
            divider_exclusion_reason(pattern, factors, getattr(winding, 'q', None), pp),
            pattern, factors)

    configuration_error = (None if pattern in ('BWP', 'UWP') else
                           _configuration_preflight(
                               pattern, configuration, winding, layout))
    if configuration_error:
        return PatternRouteDecision(
            'disabled', 'invalid_configuration', configuration_error,
            pattern, factors,
            effective_configuration=_effective_tp_type(configuration, winding))

    try:
        default = tuple(classify_branch_mode(
            winding.ab, winding.q, winding.num_poles, pattern)[1:4])
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        return PatternRouteDecision(
            'disabled', 'invalid_dividers', str(exc), pattern, factors)
    route_values = {name: getattr(winding, name) for name in
                    ('q', 'num_poles', 'num_phases', 'num_layers', 'ab')}
    route_values['num_slots'] = getattr(
        winding, 'num_slots',
        int(winding.q * winding.num_poles * winding.num_phases))
    cp_array_global_layers = getattr(
        winding, '_cp_array_global_layers', None)
    if cp_array_global_layers is not None:
        route_values['_cp_array_global_layers'] = cp_array_global_layers
    route_winding = SimpleNamespace(**route_values, branch_dividers=factors)
    route_name = _selected_integer_divider_route(pattern, route_winding)
    if (pattern == 'UWP' and route_name in ('pp_only', 'uwp_q_factor_pp')
            and configuration is not None and layout is not None):
        try:
            validate_uwp_pp_settings(configuration, winding, layout)
        except (ValueError, TypeError) as exc:
            return PatternRouteDecision(
                'disabled', 'invalid_configuration', str(exc),
                pattern, factors, route_name=route_name)
    if (route_name == 'uwp_short_p2_weld' and
            configuration is not None and layout is not None and
            not _configuration_is_neutral(
                configuration, layout, weld_side=True, winding=winding)):
        return PatternRouteDecision(
            'disabled', 'invalid_configuration',
            'UWP short P2 requires neutral Regular and a weld-side inlet.',
            pattern, factors, route_name=route_name)
    is_default = factors == default and route_name is None

    rule = None
    if route_name and (route_name.endswith('_q_pp_two')
                       or route_name in ('tlp_pp_only_two', 'tlp_pp_only_even',
                                         'tlp_pp_p2_short_unit',
                                         'tlp_q_pp_p2_parent_slices',
                                         'tlp_q_only_pair_join',
                                         'tsp_pp_only_q_p2_identity',
                                         'tsp_q_only_pair_join',
                                         'tsp_pp_p2_sector',
                                         'tsp_spiral_pass_partition',
                                         'uwp_short_p2_weld',
                                         'ssp_q_pp_parent_cut',
                                         'slp_q_pp_parent_cut',
                                         'ssp_p2_reflected',
                                         'slp_p2_from_reference', 'slp_full_q_p2',
                                         'slp_q_pp_p2_parent_cut',
                                         'slp_pair_lane_p2', 'slp_pp_p2_sector',
                                         'zlp_p2_mirrored',
                                         'zlp_pp_p2_source_cut')):
        rule = PATTERN_ROUTE_RULES[route_name]
    elif pattern in ('SSP', 'SLP') and route_name == 'pp_only':
        rule = PATTERN_ROUTE_RULES[f'{pattern.lower()}_pp_only']
    elif pattern == 'ZLP' and route_name == 'zlp':
        rule = PATTERN_ROUTE_RULES['zlp_q_pp']
    elif pattern == 'ZPP' and route_name == 'zpp':
        rule = PATTERN_ROUTE_RULES['zpp_q_pp_p2']
    elif pattern == 'ZPP' and route_name in (
            'zpp_pp_only_centered_entry_translation',
            'zpp_pp_only_half_turn',
            'zpp_pp_only_indexed_translation'):
        rule = PATTERN_ROUTE_RULES[route_name]
    elif pattern == 'CP' and route_name == 'cp':
        rule = PATTERN_ROUTE_RULES['cp_pp_p2']
    elif pattern == 'CP' and route_name == 'cp_pp_four_pass_weave':
        rule = PATTERN_ROUTE_RULES['cp_pp_four_pass_weave']
    elif pattern == 'CP' and route_name == 'cp_q_only_pair_join':
        rule = PATTERN_ROUTE_RULES['cp_q_only_pair_join']
    elif pattern == 'CP' and route_name == 'cp_q_pp_full_parent_slices':
        rule = PATTERN_ROUTE_RULES['cp_q_pp_full_parent_slices']
    elif pattern == 'CP' and route_name == 'cp_q_pp_p2_parent_slices':
        rule = PATTERN_ROUTE_RULES['cp_q_pp_p2_parent_slices']
    elif pattern == 'CP' and route_name == 'cp_pp_parent_half_translation':
        rule = PATTERN_ROUTE_RULES['cp_pp_parent_half_translation']
    elif pattern == 'CP' and route_name == 'cp_pp_sector_slices':
        rule = PATTERN_ROUTE_RULES['cp_pp_sector_slices']
    elif pattern == 'LPP' and is_default and factors[0] == factors[2] == 1:
        rule = PATTERN_ROUTE_RULES['lpp_pp_default']

    # TSP/TLP have no generic PP constructor, including arithmetic defaults.
    # Only an explicitly registered selected route can supply that construction.
    if rule is None and route_name is None and (
            not is_default or (pattern in ('TSP', 'TLP') and factors[1] > 1)
            or (pattern == 'SSP' and factors[2] == 2)):
        return PatternRouteDecision(
            'disabled', f'{pattern.lower()}_route_unsupported',
            f'{pattern} has no validated construction for divider tuple {factors}.',
            pattern, factors, admission='unsupported-yet')

    if rule is None:
        pin_profile = PATTERN_DEFAULT_PIN_PROFILES.get(pattern, ())
        required_inlet = ('weld' if pattern_requires_weld_side_inlet(pattern)
                          else 'insert')
        rule_id = f'{pattern.lower()}_default' if is_default else route_name
    else:
        pin_profile = rule.pin_profile
        required_inlet = rule.required_inlet
        rule_id = rule.rule_id
    slp_q_pp_weld_supported = (
        pattern == 'SLP' and route_name == 'slp_q_pp_parent_cut'
        and supports_slp_q_pp_single_sector_weld(winding, factors))
    if (pattern == 'SLP' and (
            is_default or route_name in SLP_ROTATED_WELD_ROUTES
            or slp_q_pp_weld_supported)
            and layout is not None and layout.inlet_from_weld_side):
        required_inlet = 'weld'

    non_wave = pattern not in ('BWP', 'UWP')
    auto_rule = getattr(configuration, 'auto_configuration_rule', None)
    auto_configuration = (
        getattr(configuration, '_auto_configuration_token', None)
        is _AUTO_CONFIGURATION_TOKEN
        and auto_rule == f'{pattern.lower()}_geometry_recipe')
    configuration_limited = (
        route_name == 'bwp_q_pp'
        or (route_name not in ('zlp_p2_mirrored',
                               'zlp_pp_p2_source_cut') and non_wave and (
            route_name is not None
            or pattern in ('SSP', 'SLP', 'ZLP', 'ZPP', 'CP', 'LPP'))))
    slp_pp_validated_after_generation = (
        pattern == 'SLP' and route_name == 'pp_only')
    bwp_configuration_failure = (
        _bwp_q_pp_configuration_failure(configuration, layout, winding)
        if route_name == 'bwp_q_pp' else None)
    configuration_ok = (
        bwp_configuration_failure is None
        if route_name == 'bwp_q_pp' else _configuration_is_neutral(
            configuration, layout, weld_side=(required_inlet == 'weld'),
            winding=winding))
    manual_layout_ok = _layout_configuration_is_neutral(
        layout, weld_side=(required_inlet == 'weld'), winding=winding)
    if (route_name in ('tsp_pp_p2_sector', 'tsp_spiral_pass_partition')
            and not _transposition_is_neutral(configuration, winding)):
        # These formulas have no TP argument. Do not silently return the
        # unchanged reference for either manual input or an Auto recipe.
        return PatternRouteDecision(
            'disabled', rule_id,
            f'{route_name} has no transposition implementation; the requested '
            'settings cannot be applied to this fixed-path formula.',
            pattern, factors, route_name, pin_profile, required_inlet,
            _effective_tp_type(configuration, winding), is_default)
    if (configuration_limited and not slp_pp_validated_after_generation
            and not auto_configuration
            and not (manual_layout_ok if non_wave else configuration_ok)):
        return PatternRouteDecision(
            'disabled', rule_id,
            bwp_configuration_failure or
            ('This production route requires no inlet adjustment and its required '
             f'{required_inlet}-side inlet.'),
            pattern, factors, route_name, pin_profile, required_inlet,
            _effective_tp_type(configuration, winding), is_default)

    if (route_name == 'zlp_pp_p2_source_cut'
            and configuration is not None and layout is not None
            and not configuration_ok):
        # The source cut permits some nonneutral settings, but only when the
        # actual shifted/configured P2 parent and every resulting child pass.
        try:
            _, candidate = _zlp_pp_p2_from_p2_parent(
                configuration, winding, layout)
            validate_selected_zlp(candidate, winding, layout)
        except (ValueError, TypeError, IndexError, KeyError) as exc:
            return PatternRouteDecision(
                'disabled', 'zlp_pp_p2_configuration_failed', str(exc),
                pattern, factors, route_name, pin_profile, required_inlet,
                _effective_tp_type(configuration, winding), is_default)

    if set_count > 1:
        outer_decision = PatternRouteDecision(
            'enabled', rule_id,
            f'{rule_id} is being checked in each local three-phase set.',
            pattern, factors, route_name, pin_profile, required_inlet,
            _effective_tp_type(configuration, winding), is_default)
        return _resolve_phase_array_route(
            pattern, winding, factors, configuration, layout, outer_decision,
            topology)

    if non_wave:
        if route_name in ('pp_only', 'zpp'):
            structure_status, structure_reason = (
                'enabled', 'The registered symbolic route has complete target-domain coverage.')
        elif route_name == 'zlp' and int(winding.num_layers) % 2 == 0:
            if factors[0] * factors[1] == winding.num_poles:
                structure_status, structure_reason = (
                    'disabled',
                    'Known structural branch-length failure: Q x PP equals the '
                    'full pole count, so the current pair-cycle constructs only '
                    'half of the required branch conductors.')
            else:
                structure_status, structure_reason = (
                    'enabled', 'The ZLP pair-cycle branch-length identity is satisfied.')
        else:
            structure_status, structure_reason = _cached_neutral_non_wave_preflight(
                pattern, int(winding.q), int(winding.num_poles),
                int(winding.num_phases), int(winding.num_layers), int(winding.ab),
                tuple(factors), required_inlet == 'weld', route_name,
                getattr(winding, '_cp_array_global_layers', None))
        if structure_status != 'enabled':
            return PatternRouteDecision(
                structure_status, rule_id, structure_reason,
                pattern, factors, route_name, pin_profile, required_inlet,
                _effective_tp_type(configuration, winding), is_default,
                admission=('unsupported-yet' if
                           route_name == 'tlp_q_pp_p2_parent_slices' else None))

    return PatternRouteDecision(
        'enabled', rule_id,
        f'{rule_id} satisfies the symbolic construction and pin-profile contract.',
        pattern, factors, route_name, pin_profile, required_inlet,
        _effective_tp_type(configuration, winding), is_default)


def selected_integer_divider_route(pattern, winding):
    """Compatibility wrapper returning the historical generator route name."""
    # Default and unsupported tuples have no legacy selected-route name. Avoid
    # running the production structural oracle when callers only need that fact.
    if _selected_integer_divider_route(pattern, winding) is None:
        return None
    decision = resolve_pattern_route(pattern, winding)
    return decision.route_name if decision.status == 'enabled' else None


def supports_uwp_balanced_q_factor(winding, factors):
    """Admit proper/full-Q, P2=2 UWP under the PP/P2 exclusion.

    PP partitions each full-pole sweep into rotating even-pole arcs.  This is
    one factor rule; it does not whitelist q, pole, PP, or Naa values.
    """
    if pattern_rejects_divider_tuple('UWP', factors):
        return False
    q, poles = winding.q, winding.num_poles
    values = _integer_divider_tuple(factors)
    if values is None:
        return False
    divider, pp, p2 = values
    if not (type(q) is int and q > 0
            and 1 < divider <= q
            and q % divider == 0
            and pp > 0 and p2 == 2 and winding.ab == 2 * divider * pp
            and poles > 0 and poles % 2 == 0
            and (poles // 2) % pp == 0
            and _supported_phase_domain(winding)
            and winding.num_layers >= 2 and winding.num_layers % 2 == 0):
        return False
    plan = _uwp_balanced_q_pp_plan(winding, values)
    return plan is not None


def _uwp_balanced_q_pp_plan(winding, factors=None):
    """Prefer a balanced plan; retain an occupancy-safe unbalanced fallback."""
    divider, pp, _ = factors or _integer_divider_tuple(winding.branch_dividers)
    q, poles, layers = winding.q, winding.num_poles, winding.num_layers
    width = q // divider
    arc_poles = poles // pp
    path_count = (layers // 2) * width * arc_poles
    fallback = dict(q_divider=divider, pp_divider=pp, width=width,
                    arc_poles=arc_poles, cycle_advance=0, local_advance=0)
    if path_count % q:
        return fallback

    # Equal q-position occupancy is an optimization, not an admission gate.
    expected = path_count // q
    cycles = (layers // 2) * width
    for cycle_advance in range(q):
        for local_advance in range(q):
            occupied = set()
            valid = True
            for start_pole in (0, 1):
                for group in range(divider):
                    for pp_branch in range(pp):
                        positions = []
                        keys = []
                        for cycle in range(cycles):
                            pair, lane = divmod(cycle, width)
                            arc_start = ((pp_branch + cycle) % pp) * arc_poles
                            for local_step in range(arc_poles):
                                step = arc_start + local_step
                                position = (group * width + lane
                                            + cycle * cycle_advance
                                            + (local_step // 2) * local_advance) % q
                                positions.append(position)
                                keys.append(((start_pole + step) % poles,
                                             2 * pair + step % 2, position))
                        if (Counter(positions) != dict.fromkeys(range(q), expected)
                                or occupied.intersection(keys)):
                            valid = False
                            break
                        occupied.update(keys)
                    if not valid:
                        break
                if not valid:
                    break
            if valid and len(occupied) == q * poles * layers:
                return dict(q_divider=divider, pp_divider=pp, width=width,
                            arc_poles=arc_poles,
                            cycle_advance=cycle_advance,
                            local_advance=local_advance)
    return fallback


def uwp_balanced_q_settings(winding):
    """Expose the derived per-edge q-position advance in the TP controls."""
    return auto_tp.uwp_balanced_settings(_uwp_balanced_q_pp_plan(winding))


def uwp_balanced_phase_a_start_slots(winding):
    """Return the one-based starts produced by the generic Q/PP/P2 plan."""
    plan = _uwp_balanced_q_pp_plan(winding)
    if plan is None:
        return []
    q, poles, phases = winding.q, winding.num_poles, winding.num_phases
    starts = []
    for start_pole in (0, 1):
        for group in range(plan['q_divider']):
            for pp_branch in range(plan['pp_divider']):
                pole = pp_branch * plan['arc_poles']
                starts.append(((start_pole + pole) * phases * q
                               + group * plan['width']) % (phases * q * poles) + 1)
    return starts


def validate_uwp_balanced_configuration(tp, winding, layout):
    expected = uwp_balanced_q_settings(winding)
    if not auto_tp.balanced_configuration_matches(tp, expected):
        raise ValueError('UWP balanced divider requires its automatic transposition settings.')
    neutral_tp = SimpleNamespace(tp_type='Regular',
                                pole_group_tp=getattr(tp, 'pole_group_tp', {}))
    if (not pp_only_configuration_is_unshifted(neutral_tp, layout)
            or len(layout.phase_shift_list) != winding.num_layers):
        raise ValueError('UWP balanced divider requires unshifted layers, automatic starts, '
                         'no additional pole-group transposition and the insert-side inlet.')


def _uwp_balanced_q_factor(tp, winding, layout):
    """Build proper-Q/P2 UWP branches for every admitted PP factor."""
    validate_uwp_balanced_configuration(tp, winding, layout)
    q, poles, layers = winding.q, winding.num_poles, winding.num_layers
    phases = winding.num_phases
    if winding.num_slots != phases * q * poles:
        raise ValueError('UWP balanced divider slots do not match q and poles.')
    divider, pp, _ = map(int, winding.branch_dividers)
    plan = _uwp_balanced_q_pp_plan(winding, (divider, pp, 2))
    if plan is None:
        raise ValueError('UWP balanced divider cannot distribute q positions equally.')
    width, pitch = plan['width'], phases * q
    arc_poles = plan['arc_poles']
    # Regular zero settings retain each branch's q-position group. Only an
    # explicitly selected Auto payload enables the searched permutation.
    automatic = auto_tp.is_auto_type(getattr(tp, 'tp_type', 'Regular'))
    cycle_advance = plan['cycle_advance'] if automatic else 0
    local_advance = plan['local_advance'] if automatic else 0
    database = _CandidateBranches()
    travel = {}
    for phase in range(phases):
        for start_pole in (0, 1):
            for group in range(divider):
                for pp_branch in range(pp):
                    path = []
                    for cycle in range((layers // 2) * width):
                        pair, lane = divmod(cycle, width)
                        arc_start = ((pp_branch + cycle) % pp) * arc_poles
                        for local_step in range(arc_poles):
                            step = arc_start + local_step
                            position = (group * width + lane
                                        + cycle * cycle_advance
                                        + (local_step // 2) * local_advance) % q
                            slot = ((start_pole + step) * pitch
                                    + phase * q + position) % winding.num_slots
                            path.append((slot, 2 * pair + step % 2, position))
                    branch_id = len(database) + 1
                    steps = tuple(pitch + target[2] - source[2]
                                  for source, target in zip(path, path[1:]))
                    if any(step <= 0 or
                           (source[0] + step - target[0]) % winding.num_slots
                           for step, source, target in zip(
                               steps, path, path[1:])):
                        raise ValueError('UWP balanced travel misses its endpoint.')
                    database.append([branch_id, path])
                    travel[branch_id] = steps
    database.signed_travel = travel
    validate_uwp_balanced_paths(database, winding, layout)
    return [branch[1][0] for branch in database], database


def validate_uwp_balanced_paths(database, winding, layout):
    _validate_selected_electrical('UWP automatic balanced divider', database, winding, layout)
    q = winding.q
    for branch_index, (branch_id, path) in enumerate(database):
        direction = _uwp_pp_branch_direction(winding, branch_index)
        for index, (source, target) in enumerate(zip(path, path[1:])):
            if index % 2 == 0 and source[0] % q != target[0] % q:
                raise ValueError('UWP transposition must preserve weld-side q positions.')
            if (abs(target[1] - source[1]) != 1
                    or not any(step * direction > 0 for step in
                               _connection_travel_steps(
                                   database, branch_id, index, source, target,
                                   winding.num_slots))):
                raise ValueError('UWP balanced divider has an invalid forward edge.')


def validate_selected_bwp_pp(database, winding, layout):
    _validate_selected_electrical('BWP selected PP', database, winding, layout)
    for _, path in database:
        for start, end in zip(path, path[1:]):
            layer_step = end[1] - start[1]
            if not (abs(layer_step) == 1 or
                    (layer_step == 0 and start[1] in (0, winding.num_layers - 1))):
                raise ValueError('BWP selected PP branch has an invalid wave edge.')


def _cp_layer_admission_reason(layer_context):
    """Check CP's global layer rule and, for arrays, local pairability."""
    local_layers = getattr(layer_context, 'num_layers', layer_context)
    global_layers = getattr(
        layer_context, '_cp_array_global_layers', None)
    if global_layers is not None:
        global_reason = _cp_layer_admission_reason(global_layers)
        if global_reason:
            return global_reason
        try:
            if local_layers > 0 and local_layers % 2 == 0:
                return None
        except (TypeError, ValueError):
            pass
        return 'CP phase-set construction requires a positive even local layer count.'
    try:
        if local_layers > 0 and local_layers % 4 == 0:
            return None
    except (TypeError, ValueError):
        pass
    return 'CP requires a positive layer count divisible by 4.'


def supports_integer_cp_pp_p2(winding, selected):
    """Admit CP's existing PP/P2 generator path for checked output only."""
    factors = _integer_divider_tuple(selected)
    if factors is None:
        return False
    q_divider, pp_divider, p2_divider = factors
    return (float(winding.q).is_integer() and winding.q > 0
            and winding.num_poles > 0 and winding.num_poles % 2 == 0
            and not _cp_layer_admission_reason(winding)
            and _supported_phase_domain(winding)
            and q_divider == 1
            and pp_divider > 1 and p2_divider == 2
            and (winding.num_poles // 2) % pp_divider == 0
            and winding.ab == pp_divider * p2_divider)


def supports_integer_cp_pp_four_pass_weave(winding, selected):
    """Recognize the four-pass CP PP weave from its parent-path geometry."""
    factors = _integer_divider_tuple(selected)
    if factors is None:
        return False
    Q, D, P2 = factors
    if not isinstance(winding.q, int) or isinstance(winding.q, bool):
        return False
    pole_pairs = winding.num_poles // 2
    parent_passes = winding.q * pole_pairs
    return (winding.q > 0
            and winding.num_poles > 0 and winding.num_poles % 2 == 0
            and not _cp_layer_admission_reason(winding)
            and _supported_phase_domain(winding)
            and Q == 1 and D == 2 and P2 == 1
            and pole_pairs % D == 0
            and parent_passes == 4 * D
            and winding.ab == D)


def supports_integer_cp_q_pp_full_parent_slices(winding, selected):
    """Recognize CP Q+PP and PP-only cuts from public P2 parents."""
    factors = _integer_divider_tuple(selected)
    if factors is None:
        return False
    Q, D, P2 = factors
    q = getattr(winding, 'q', None)
    poles = getattr(winding, 'num_poles', 0)
    pole_pairs = poles // 2 if poles > 0 and poles % 2 == 0 else 0
    return (type(q) is int and q > 0
            and poles > 0 and poles % 2 == 0
            and not _cp_layer_admission_reason(winding)
            and _supported_phase_domain(winding)
            and ((Q > 1 and q > 1 and q % Q == 0
                  and D >= 4 and D % 2 == 0)
                 or (Q == 1 and D >= 4 and D % 2 == 0
                     and (q % 2 == 1 or D % 4 == 2)))
            and pole_pairs % D == 0
            and P2 == 1 and winding.ab == Q * D)


def supports_integer_cp_q_pp_p2_parent_slices(winding, selected):
    """Recognize non-default CP Q+PP+P2 cuts from same-geometry parents."""
    factors = _integer_divider_tuple(selected)
    if factors is None:
        return False
    Q, D, P2 = factors
    q = getattr(winding, 'q', None)
    poles = getattr(winding, 'num_poles', 0)
    pole_pairs = poles // 2 if poles > 0 and poles % 2 == 0 else 0
    if not (type(q) is int and q > 0
            and poles > 0 and poles % 2 == 0
            and not _cp_layer_admission_reason(winding)
            and _supported_phase_domain(winding)
            and Q > 1 and q % Q == 0
            and D > 1 and pole_pairs % D == 0
            and P2 == 2 and winding.ab == Q * D * P2):
        return False
    try:
        default = tuple(classify_branch_mode(
            winding.ab, q, poles, 'CP')[1:4])
    except (TypeError, ValueError, ZeroDivisionError):
        return False
    return factors != default


def supports_integer_cp_pp_parent_half_translation(winding, selected):
    """Recognize the even-q CP four-sector translation from a P2 parent."""
    factors = _integer_divider_tuple(selected)
    if factors is None:
        return False
    Q, D, P2 = factors
    q = getattr(winding, 'q', None)
    poles = getattr(winding, 'num_poles', 0)
    pole_pairs = poles // 2 if poles > 0 and poles % 2 == 0 else 0
    return (type(q) is int and q > 1 and q % 2 == 0
            and poles > 0 and poles % 2 == 0
            and not _cp_layer_admission_reason(winding)
            and _supported_phase_domain(winding)
            and Q == 1 and D == 4 and P2 == 1
            and pole_pairs >= D and pole_pairs % D == 0
            and winding.ab == D)


def supports_integer_cp_pp_sector_slices(winding, selected):
    """Recognize PP sectors cut from a public four-sector CP layout."""
    factors = _integer_divider_tuple(selected)
    if factors is None:
        return False
    Q, D, P2 = factors
    q = getattr(winding, 'q', None)
    poles = getattr(winding, 'num_poles', 0)
    pole_pairs = poles // 2 if poles > 0 and poles % 2 == 0 else 0
    return (type(q) is int and q > 1 and q % 2 == 0
            and poles > 0 and poles % 2 == 0
            and not _cp_layer_admission_reason(winding)
            and _supported_phase_domain(winding)
            and Q == 1 and D > 4 and D % 4 == 0 and P2 == 1
            and pole_pairs % D == 0 and winding.ab == D)


def supports_integer_cp_q_only_pair_join(winding, selected):
    """Use adjacent per-phase P2 parents for a CP Q-only target."""
    factors = _integer_divider_tuple(selected)
    if factors is None:
        return False
    Q, pp_divider, p2_divider = factors
    return (type(winding.q) is int and winding.q > 0
            and Q > 1 and winding.q % Q == 0
            and pp_divider == p2_divider == 1
            and winding.ab == Q
            and winding.num_poles > 0 and winding.num_poles % 2 == 0
            and not _cp_layer_admission_reason(winding)
            and _supported_phase_domain(winding))


def supports_integer_zpp_factors(winding, selected):
    """ZPP path length requires Q times P2 to equal q."""
    factors = _integer_divider_tuple(selected)
    if factors is None:
        return False
    q_divider, pp_divider, p2_divider = factors
    return (float(winding.q).is_integer() and winding.q > 0
            and winding.num_poles > 0 and winding.num_poles % 2 == 0
            and winding.num_layers > 0 and winding.num_layers % 2 == 0
            and _supported_phase_domain(winding)
            and q_divider > 0
            and pp_divider > 0 and p2_divider in (1, 2)
            and q_divider * p2_divider == winding.q
            and (winding.num_poles // 2) % pp_divider == 0
            and winding.ab == q_divider * pp_divider * p2_divider)


def supports_integer_zpp_pp_only_indexed_translation(winding, selected):
    """Admit indexed ZPP Q-parent deployment when its sector classes permute."""
    factors = _integer_divider_tuple(selected)
    if factors is None:
        return False
    q_divider, pp_divider, p2_divider = factors
    if (type(winding.q) is not int or winding.q <= 0
            or winding.num_poles <= 0 or winding.num_poles % 2
            or winding.num_layers <= 0 or winding.num_layers % 2
            or not _supported_phase_domain(winding)
            or q_divider != 1 or pp_divider <= 1 or p2_divider != 1
            or winding.q != pp_divider or winding.ab != pp_divider):
        return False

    pole_pairs = winding.num_poles // 2
    if pole_pairs % pp_divider:
        return False
    repetitions = pole_pairs // pp_divider
    try:
        zpp_indexed_sector_stride(pp_divider, repetitions)
    except ValueError:
        return False

    # Equal Naa fixes the source as (D,1,1); ZPP's Q*P2=q rule then
    # requires D=q. Let the public parent rule own all source factor gates.
    parent = SimpleNamespace(
        q=winding.q, num_poles=winding.num_poles,
        num_layers=winding.num_layers, num_phases=winding.num_phases,
        ab=pp_divider)
    return supports_integer_zpp_factors(
        parent, (pp_divider, 1, 1))


def supports_integer_zpp_pp_only_centered_entry_translation(winding, selected):
    """Admit PP-only ZPP routes derived from a public integer-q parent."""
    factors = _integer_divider_tuple(selected)
    if factors is None:
        return False
    q_divider, pp_divider, p2_divider = factors
    q = getattr(winding, 'q', None)
    if (type(q) is not int or q <= 0
            or q_divider != 1 or pp_divider <= q or p2_divider != 1
            or pp_divider % q
            or getattr(winding, 'ab', None) != pp_divider
            or getattr(winding, 'num_poles', 0) <= 0
            or winding.num_poles % 2
            or getattr(winding, 'num_layers', 0) <= 0
            or winding.num_layers % 2
            or not _supported_phase_domain(winding)):
        return False

    pole_pairs = winding.num_poles // 2
    if pole_pairs % pp_divider:
        return False
    num_slots = getattr(
        winding, 'num_slots',
        int(winding.q * winding.num_poles * winding.num_phases))
    if num_slots <= 0 or num_slots % pp_divider:
        return False
    try:
        zpp_indexed_sector_stride(
            pp_divider, pole_pairs // pp_divider)
    except ValueError:
        return False

    # The input parent is generated through the existing public (q,1,1) rule.
    parent = SimpleNamespace(
        q=q, num_poles=winding.num_poles,
        num_layers=winding.num_layers,
        num_phases=winding.num_phases, ab=q)
    return supports_integer_zpp_factors(parent, (q, 1, 1))


def supports_integer_zpp_pp_only_half_turn(winding, selected):
    """Compatibility predicate for the D=2 indexed translation route."""
    return (_integer_divider_tuple(selected) == (1, 2, 1)
            and supports_integer_zpp_pp_only_indexed_translation(
                winding, selected))


def _zpp_pp_only_indexed_translation_from_q_parent(tp, winding, layout):
    """Translate each ordered ZPP q-parent by its indexed PP sector."""
    from pattern_identity import circular_travel_steps

    factors = _integer_divider_tuple(winding.branch_dividers)
    if not supports_integer_zpp_pp_only_indexed_translation(
            winding, winding.branch_dividers):
        raise ValueError(
            'ZPP PP-only indexed translation is outside its source-derived domain.')
    divider = factors[1]
    repetitions = (winding.num_poles // 2) // divider
    sector_stride = zpp_indexed_sector_stride(divider, repetitions)
    reference = SimpleNamespace(**{name: getattr(winding, name) for name in
        ('q', 'num_slots', 'num_poles', 'num_phases', 'num_layers')})
    reference.ab = divider
    reference.branch_dividers = (divider, 1, 1)
    _, source = get_winding_layout('ZPP', tp, reference, layout)
    phase_by_position = {
        (slot, layer): phase for slot, layer, phase, _sign in phase_map(
            winding.num_slots, winding.num_poles, winding.num_layers,
            layout.phase_shift_list, winding.num_phases)}
    source_branches = list(source)
    group_keys = []
    for branch_id, path in source_branches:
        if not path:
            raise ValueError('ZPP q-divider reference contains an empty branch.')
        group_keys.append(phase_by_position[path[0][:2]])
    formula_route = (
        'zpp_pp_only_half_turn' if divider == 2 else
        'zpp_pp_only_indexed_translation')
    children = apply_route_formula(
        formula_route, source_branches, winding.branch_dividers,
        num_slots=winding.num_slots, group_keys=group_keys,
        group_order=tuple(range(winding.num_phases)),
        sector_stride=sector_stride, sector_repetitions=repetitions)

    database = _CandidateBranches()
    source_by_id = dict(source_branches)
    source_travel = getattr(source, 'signed_travel', {})
    deployed_travel = {}

    def source_steps(source_id, path):
        if source_id in source_travel:
            steps = tuple(source_travel[source_id])
            if len(steps) != len(path) - 1:
                raise ValueError('ZPP q-parent has incomplete signed-travel evidence.')
        else:
            steps = tuple(
                (choices[0] if len(choices) == 1 else None)
                for start, end in zip(path, path[1:])
                for choices in (circular_travel_steps(
                    start[0], end[0], winding.num_slots),))
            if any(step is None for step in steps):
                raise ValueError('ZPP q-parent contains an ambiguous half-circle edge.')
        if any((start[0] + step) % winding.num_slots != end[0]
               for start, end, step in zip(path, path[1:], steps)):
            raise ValueError('ZPP q-parent signed travel does not match its endpoints.')
        return steps

    for child in children:
        source_id = child.source_ids[0]
        path = source_by_id[source_id]
        new_id = len(database) + 1
        database.append([new_id, child.path])
        deployed_travel[new_id] = source_steps(source_id, path)
    database.signed_travel = deployed_travel
    deployment = dict(
        source_dividers=(divider, 1, 1),
        target_dividers=tuple(winding.branch_dividers),
        slot_translation_per_branch=tuple(
            ((index * sector_stride) % divider)
            * winding.num_slots // divider
            for index in range(divider)),
        sector_index_multiplier=sector_stride,
        source_starts=[tuple(path[0]) for _, path in source],
        starts=[tuple(path[0]) for _, path in database])
    database.indexed_sector_deployment = deployment
    if divider == 2:
        database.half_turn_deployment = dict(
            source_dividers=(2, 1, 1), target_dividers=(1, 2, 1),
            slot_translation=winding.num_slots // 2,
            source_starts=deployment['source_starts'],
            starts=deployment['starts'])
    return [path[0] for _, path in database], database


def _zpp_pp_only_centered_entry_from_q_parent(tp, winding, layout):
    """Deploy centered windows from each public ZPP q-parent into PP sectors."""
    factors = _integer_divider_tuple(winding.branch_dividers)
    if not supports_integer_zpp_pp_only_centered_entry_translation(
            winding, factors):
        raise ValueError(
            'ZPP centered-entry translation is outside its source-derived domain.')

    q = int(winding.q)
    divider = factors[1]
    pole_pairs = winding.num_poles // 2
    repetitions = pole_pairs // divider
    stride = zpp_indexed_sector_stride(divider, repetitions)
    reference = SimpleNamespace(**{
        name: getattr(winding, name) for name in
        ('q', 'num_slots', 'num_poles', 'num_phases', 'num_layers')})
    reference.ab = q
    reference.branch_dividers = (q, 1, 1)
    _, source = get_winding_layout('ZPP', tp, reference, layout)
    source_branches = list(source)
    phase_by_position = {
        (slot, layer): phase for slot, layer, phase, _sign in phase_map(
            winding.num_slots, winding.num_poles, winding.num_layers,
            layout.phase_shift_list, winding.num_phases)
    }
    group_keys = []
    for _branch_id, path in source_branches:
        if not path:
            raise ValueError('ZPP q-divider reference contains an empty branch.')
        try:
            group_keys.append(phase_by_position[path[0][:2]])
        except KeyError as exc:
            raise ValueError(
                'ZPP q-divider reference starts outside the phase map.') from exc

    children = DividerConnectionFormula(
        'zpp_centered_entry_translation', (q, 1, 1),
        tuple(winding.branch_dividers)).apply(
            source_branches, num_slots=winding.num_slots,
            pp=pole_pairs, group_keys=group_keys,
            group_order=tuple(range(winding.num_phases)))

    source_by_id = dict(source_branches)
    source_travel = getattr(source, 'signed_travel', {})

    def parent_steps(branch_id, path):
        if isinstance(source_travel, Mapping) and branch_id in source_travel:
            steps = tuple(source_travel[branch_id])
            if len(steps) != len(path) - 1:
                raise ValueError(
                    'ZPP q-parent has incomplete signed-travel evidence.')
        else:
            derived = []
            for start, end in zip(path, path[1:]):
                choices = circular_travel_steps(
                    start[0], end[0], winding.num_slots)
                if len(choices) != 1:
                    raise ValueError(
                        'ZPP q-parent contains an ambiguous half-circle edge.')
                derived.append(choices[0])
            steps = tuple(derived)
        if any((start[0] + step) % winding.num_slots != end[0]
               for start, end, step in zip(path, path[1:], steps)):
            raise ValueError(
                'ZPP q-parent signed travel does not match its endpoints.')
        return steps

    database = _CandidateBranches()
    deployed_travel = {}
    window_records = []
    for child in children:
        source_id = child.source_ids[0]
        parent_path = source_by_id[source_id]
        window_start = (len(parent_path) - len(child.path)) // 2
        window = parent_path[window_start:window_start + len(child.path)]
        if len(window) != len(child.path):
            raise ValueError('ZPP centered-entry formula returned an incomplete window.')
        slot_offset = (child.path[0][0] - window[0][0]) % winding.num_slots
        if any(
                (original[0] + slot_offset) % winding.num_slots != deployed[0]
                or original[1:] != deployed[1:]
                for original, deployed in zip(window, child.path)):
            raise ValueError(
                'ZPP centered-entry formula changed parent path identity.')

        new_id = len(database) + 1
        database.append([new_id, child.path])
        steps = parent_steps(source_id, parent_path)
        deployed_travel[new_id] = steps[
            window_start:window_start + len(child.path) - 1]
        window_records.append({
            'branch_id': new_id,
            'source_branch_id': source_id,
            'part_index': child.part_index,
            'window_start': window_start,
            'window_length': len(child.path),
            'slot_offset': slot_offset,
        })

    database.signed_travel = deployed_travel
    database.centered_entry_deployment = {
        'source_dividers': (q, 1, 1),
        'target_dividers': tuple(winding.branch_dividers),
        'parts_per_parent': divider // q,
        'sector_stride': stride,
        'sector_width': winding.num_slots // divider,
        'windows': window_records,
    }
    return [path[0] for _, path in database], database


def _zpp_pp_only_half_turn_from_q_parent(tp, winding, layout):
    """Preserve the D=2 constructor entry point for existing callers."""
    return _zpp_pp_only_indexed_translation_from_q_parent(
        tp, winding, layout)


def supports_integer_zlp_factors(winding, selected):
    """Report current ZLP support after explicit divider exclusions."""
    factors = _integer_divider_tuple(selected)
    if factors is None or pattern_rejects_divider_tuple('ZLP', factors, winding.q):
        return False
    q_divider, pp_divider, p2_divider = factors
    return (float(winding.q).is_integer() and winding.q > 0
            and winding.num_poles > 0 and winding.num_poles % 2 == 0
            and winding.num_layers > 1
            and _supported_phase_domain(winding)
            and q_divider > 1 and winding.q % q_divider == 0
            and pp_divider > 0 and (winding.num_poles // 2) % pp_divider == 0
            and p2_divider == 1 and winding.ab == q_divider * pp_divider
            and (winding.num_layers % 2 == 0 or q_divider == winding.q))


def validate_selected_zlp(database, winding, layout):
    _validate_selected_electrical('ZLP selected', database, winding, layout)
    for _, path in database:
        for start, end in zip(path, path[1:]):
            layer_step = end[1] - start[1]
            if abs(layer_step) > 1:
                raise ValueError('ZLP selected branch has an invalid lap edge.')


def validate_selected_zpp(database, winding, layout):
    from pattern_identity import circular_travel_steps, pole_region_crossings

    _validate_selected_electrical('ZPP selected', database, winding, layout)
    pole_pitch = winding.num_phases * winding.q
    recorded_travel = getattr(database, 'signed_travel', {})
    selected_dividers = _integer_divider_tuple(
        getattr(winding, 'branch_dividers', None))
    require_signed_travel = (
        selected_dividers is not None
        and selected_dividers[0] == 1
        and selected_dividers[1] > 1
        and selected_dividers[2] == 1)
    if require_signed_travel and any(
            branch_id not in recorded_travel
            or len(recorded_travel[branch_id]) != len(path) - 1
            for branch_id, path in database):
        raise ValueError('ZPP PP-only branches require complete signed-travel evidence.')
    for branch_id, path in database:
        travel = recorded_travel.get(branch_id)
        for edge_index, (start, end) in enumerate(zip(path, path[1:])):
            layer_step = end[1] - start[1]
            if abs(layer_step) > 1:
                raise ValueError('ZPP selected branch has an invalid Z edge.')
            steps = ((travel[edge_index],) if travel is not None else
                     circular_travel_steps(start[0], end[0], winding.num_slots))
            if travel is not None and (
                    type(travel[edge_index]) is not int
                    or (start[0] + travel[edge_index]) % winding.num_slots
                    != end[0]):
                raise ValueError(
                    'ZPP selected signed-travel evidence does not match its endpoints.')
            if (not steps or any(pole_region_crossings(
                    int(start[0]), step, pole_pitch) > 1 for step in steps)):
                raise ValueError(
                    'ZPP selected connection crosses multiple pole regions.')


def validate_selected_cp(database, winding, layout, *, require_signed_travel=False):
    _validate_selected_electrical('CP selected', database, winding, layout)
    if require_signed_travel:
        from pattern_identity import pole_region_crossings

        recorded = getattr(database, 'signed_travel', None)
        expected_ids = {branch_id for branch_id, _path in database}
        if (not isinstance(recorded, Mapping)
                or set(recorded) != expected_ids):
            raise ValueError(
                'CP parent-slice branches require complete signed-travel evidence.')
        pole_pitch = winding.num_phases * winding.q
        for branch_id, path in database:
            steps = recorded[branch_id]
            if len(steps) != len(path) - 1:
                raise ValueError(
                    'CP parent-slice signed-travel evidence has the wrong length.')
            for (start, end), step in zip(zip(path, path[1:]), steps):
                if (type(step) is not int or not step
                        or (start[0] + step) % winding.num_slots != end[0]):
                    raise ValueError(
                        'CP parent-slice signed travel does not match its edge.')
                if pole_region_crossings(
                        int(start[0]), step, pole_pitch) > 1:
                    raise ValueError(
                        'CP parent-slice signed connection crosses multiple pole regions.')
    cross_layers = winding.num_layers // 2
    for _, path in database:
        for start, end in zip(path, path[1:]):
            layer_step = end[1] - start[1]
            if abs(layer_step) not in (1, cross_layers):
                raise ValueError('CP selected branch has an invalid cross-layer edge.')


def _three_phase_set_views(database, winding, layout, topology=None):
    """Return arrayed 3-phase branches in topology-owned local coordinates."""
    topology = topology or _phase_topology_for_winding(winding, layout)
    if topology.phase_model != 'arrayed_three_phase_sets':
        return [(database, winding, layout)]
    shifts = tuple(getattr(layout, 'phase_shift_list', (0,) * winding.num_layers))
    if len(shifts) != winding.num_layers:
        raise ValueError('One integer slot shift is required per layer.')
    winding_fields = (vars(winding) if hasattr(winding, '__dict__')
                      else winding._asdict())
    layout_fields = (vars(layout) if hasattr(layout, '__dict__')
                     else layout._asdict())
    grouped = [[] for _ in range(topology.set_count)]
    for branch_id, path in database:
        if not path:
            raise ValueError('A three-phase-set branch cannot be empty.')
        group = topology.record_at(*path[0][:2]).set_index
        grouped[group].append((branch_id, path))

    views = []
    for spec, branches in zip(topology.phase_sets, grouped):
        local_winding = dict(winding_fields)
        local_winding.update(
            q=(int(spec.local_q) if spec.local_q.denominator == 1
               else spec.local_q),
            num_slots=spec.local_slots, num_phases=3,
            num_layers=spec.layer_count)
        local_layout = dict(layout_fields)
        local_layout['phase_shift_list'] = list(
            shifts[spec.layer_start:spec.layer_start + spec.layer_count])
        local_database = _CandidateBranches()
        local_travel = getattr(database, 'signed_travel', None)
        travel = {}
        for old_id, path in branches:
            local_path = []
            for node in path:
                local_slot, local_layer = spec.to_local(node[0], node[1])
                local_path.append((local_slot, local_layer, *node[2:]))
            new_id = len(local_database) + 1
            local_database.append([new_id, local_path])
            if isinstance(local_travel, Mapping) and old_id in local_travel:
                travel[new_id] = tuple(local_travel[old_id])
        if travel and len(travel) == len(local_database):
            local_database.signed_travel = travel
        views.append((local_database, SimpleNamespace(**local_winding),
                      SimpleNamespace(**local_layout)))
    return views


def _analyze_pattern_identity_for_sets(pattern, database, winding, layout,
                                      topology=None):
    """Analyze one 3-phase identity per independent electrical set."""
    from layout_analysis import (analyze_pattern_identity,
                                 _validated_post_shift_identity)

    prior_identity = _validated_post_shift_identity(
        pattern, database, winding, layout)
    if prior_identity is not None:
        return prior_identity

    views = _three_phase_set_views(database, winding, layout, topology)
    identities = [analyze_pattern_identity(
        pattern, local_database, local_winding, local_layout)
        for local_database, local_winding, local_layout in views]
    if len(identities) == 1:
        return identities[0]
    combined = dict(identities[0])
    ordered_qualifications = [identity.get('ordered_identity', {}).get(
        'qualification') for identity in identities]
    statuses = [
        ('unverified' if qualification == 'unsupported-domain'
         else identity.get('status'))
        for identity, qualification in zip(identities, ordered_qualifications)]
    if any(status == 'candidate' for status in statuses):
        combined['status'] = 'candidate'
    elif any(status == 'unverified' for status in statuses):
        combined['status'] = 'unverified'
    else:
        combined['status'] = 'valid'
    summaries = []
    for index, (identity, status, qualification) in enumerate(
            zip(identities, statuses, ordered_qualifications), start=1):
        ordered = identity.get('ordered_identity', {})
        reason = identity.get('reason', '')
        if status == 'unverified':
            reason = ('Ordered identity is outside the current recognizer '
                      'domain; legacy checks only. ' + reason)
        summaries.append({
            'set': index,
            'status': status,
            'identity_confidence': identity.get('identity_confidence'),
            'identity_basis': identity.get('identity_basis'),
            'ordered_qualification': qualification,
            'reason': reason,
            'pin_types': identity.get('pin_types', {}),
            'topology_issues': identity.get('topology_issues', ()),
        })
    combined['phase_sets'] = summaries
    if combined['status'] != 'valid':
        combined['reason'] = '; '.join(
            f"set {item['set']}: {item['reason']}"
            for item in summaries if item['status'] != 'valid')
    return combined


def validate_tsp_pp_p2_sector(database, winding, layout):
    """Validate the fixed-lane TSP PP+P2 formula against generated branches."""
    factors = _integer_divider_tuple(
        getattr(winding, 'branch_dividers', None))
    if not supports_integer_tsp_pp_p2_sector(winding, factors):
        raise ValueError('TSP PP+P2 sector factors are outside the formula domain.')
    expected = tsp_pp_p2_sector_branches(
        int(winding.q), int(winding.num_poles) // 2, factors,
        int(winding.num_layers), int(winding.num_phases))
    actual = list(database)
    if len(actual) != len(expected):
        raise ValueError('TSP PP+P2 sector branch count differs from the formula.')

    phase_sign = {
        (slot, layer): (phase, sign)
        for slot, layer, phase, sign in phase_map(
            winding.num_slots, winding.num_poles, winding.num_layers,
            layout.phase_shift_list, winding.num_phases)
    }

    # Independently recover each inlet's pole-pair rank and q-lane from the
    # canonical phase map. This checks the sector assignment without reusing
    # the branch formula that generated the expected paths below.
    q = int(winding.q)
    pp = int(winding.num_poles) // 2
    divider = factors[1]
    outer_layers = (0, winding.num_layers - 1)
    origins_by_lane = {}
    for (slot, layer), (phase, sign) in phase_sign.items():
        if layer not in outer_layers or sign != 1:
            continue
        lane = slot % q
        origins_by_lane.setdefault((phase, layer, lane), []).append(slot)

    origin_rank = {}
    for phase in range(winding.num_phases):
        for layer in outer_layers:
            for lane in range(q):
                origins = sorted(origins_by_lane.get(
                    (phase, layer, lane), ()))
                if len(origins) != pp:
                    raise ValueError(
                        'TSP PP+P2 phase-map N-sign lane does not contain '
                        'one origin per pole pair.')
                for rank, slot in enumerate(origins):
                    origin_rank[(phase, layer, lane, slot)] = rank

    observed_inlets = {}
    for branch_id, path in actual:
        if not path:
            raise ValueError(
                f'TSP PP+P2 branch {branch_id} has no inlet conductor.')
        slot, layer = path[0][:2]
        phase, sign = phase_sign.get((slot, layer), (None, None))
        lane = slot % q
        key = (phase, layer, lane, slot)
        if (phase is None or layer not in outer_layers or sign != 1
                or key not in origin_rank):
            raise ValueError(
                f'TSP PP+P2 branch {branch_id} inlet is not a phase-map '
                'N-sign outer-layer origin.')
        observed_inlets.setdefault((phase, layer), Counter())[
            (origin_rank[key], lane)] += 1

    expected_inlets = Counter({
        (region * pp // divider, (region * q) // divider): 1
        for region in range(divider)
    })
    for phase in range(winding.num_phases):
        for layer in outer_layers:
            if observed_inlets.get((phase, layer), Counter()) != expected_inlets:
                raise ValueError(
                    f'TSP PP+P2 phase {phase} layer {layer} does not cover '
                    'the required region/lane inlet partition.')

    recorded_travel = getattr(database, 'signed_travel', None)
    if not isinstance(recorded_travel, Mapping):
        raise ValueError('TSP PP+P2 sectors require signed edge travel evidence.')
    region_width = winding.q * winding.num_phases
    starts_by_phase_layer = Counter()
    for (branch_id, path), formula_branch in zip(actual, expected):
        observed = tuple(tuple(node[:3]) for node in path)
        if observed != formula_branch.path:
            raise ValueError(
                f'TSP PP+P2 branch {branch_id} differs from its formula path.')
        start_phase, start_sign = phase_sign[path[0][:2]]
        end_phase, end_sign = phase_sign[path[-1][:2]]
        if start_sign != 1 or end_sign != -1 or start_phase != end_phase:
            raise ValueError(
                f'TSP PP+P2 branch {branch_id} does not run from N to S '
                'within one phase.')
        if any(phase_sign[node[:2]][0] != start_phase for node in path):
            raise ValueError(
                f'TSP PP+P2 branch {branch_id} changes phase along its path.')
        starts_by_phase_layer[(start_phase, path[0][1])] += 1

        signed_step = formula_branch.direction * region_width
        travel = recorded_travel.get(branch_id)
        expected_travel = (signed_step,) * max(len(path) - 1, 0)
        if tuple(travel or ()) != expected_travel:
            raise ValueError(
                f'TSP PP+P2 branch {branch_id} has inconsistent signed travel.')
        for edge_index, (left, right) in enumerate(zip(path, path[1:])):
            if ((right[0] - left[0]) % winding.num_slots
                    != signed_step % winding.num_slots):
                raise ValueError(
                    f'TSP PP+P2 branch {branch_id} edge {edge_index} '
                    'does not preserve the formula pitch.')
            if pole_region_crossings(
                    left[0], signed_step, region_width) > 1:
                raise ValueError(
                    f'TSP PP+P2 branch {branch_id} edge {edge_index} '
                    'crosses more than one pole region.')

    expected_layer_counts = {
        (phase, layer): factors[1]
        for phase in range(winding.num_phases)
        for layer in {0, winding.num_layers - 1}
    }
    if starts_by_phase_layer != Counter(expected_layer_counts):
        raise ValueError(
            'TSP PP+P2 requires D first-layer and D last-layer inlets '
            'for every phase.')

    identity = _analyze_pattern_identity_for_sets(
        'TSP', database, winding, layout)
    if identity['status'] != 'valid':
        raise ValueError('TSP PP+P2 ordered identity: ' + identity['reason'])
    _validate_selected_electrical(
        'TSP PP+P2 sector inlets', database, winding, layout)


def validate_tsp_spiral_pass_partition(database, winding, layout):
    """Check actual complete passes, uniform welds and physical return travel."""
    factors = _integer_divider_tuple(winding.branch_dividers)
    if not supports_integer_tsp_spiral_pass_partition(winding, factors):
        raise ValueError('TSP spiral pass partition is outside its formula domain.')
    q, layers, phases = winding.q, winding.num_layers, winding.num_phases
    tau = q * phases
    width = winding.num_slots * layers // (phases * winding.ab)
    if len(database) != phases * winding.ab:
        raise ValueError('TSP pass partition has an incorrect branch count.')
    recorded = getattr(database, 'signed_travel', {})
    phase_sign = {(s, l): (ph, sign) for s, l, ph, sign in phase_map(
        winding.num_slots, winding.num_poles, layers,
        layout.phase_shift_list, phases)}
    for branch_id, path in database:
        if len(path) != width or len(path) < 2 * layers or len(path) % layers:
            raise ValueError('TSP branch must contain at least two complete spiral passes.')
        direction = 1 if path[0][1] == 0 else -1
        expected_layers = (tuple(range(layers)) if direction > 0
                           else tuple(reversed(range(layers))))
        travel = recorded.get(branch_id, ())
        if len(travel) != len(path) - 1:
            raise ValueError('TSP pass partition requires signed travel for every edge.')
        phase = phase_sign[path[0][:2]][0]
        for offset in range(0, len(path), layers):
            block = path[offset:offset + layers]
            if tuple(node[1] for node in block) != expected_layers:
                raise ValueError('TSP spiral pass changed its monotone layer traversal.')
            if len({node[2] for node in block}) != 1:
                raise ValueError('TSP body changed q lane inside a spiral pass.')
        for index, node in enumerate(path):
            if (phase_sign[node[:2]] != (phase, (-1) ** index)
                    or node[2] != node[0] % q):
                raise ValueError('TSP pass partition changed phase, polarity or q lane.')
        for index, (left, right) in enumerate(zip(path, path[1:])):
            step = travel[index]
            if (type(step) is not int
                    or (left[0] + step) % winding.num_slots != right[0]
                    or pole_region_crossings(left[0], step, tau) > 1):
                raise ValueError('TSP signed travel must cross at most one pole region.')
            if (index + 1) % layers:
                if step != direction * tau:
                    raise ValueError('TSP ordinary body/weld direction changed.')
            else:
                lane_delta = right[2] - left[2]
                if (step - lane_delta not in (-tau, tau)
                        or abs(right[1] - left[1]) != layers - 1):
                    raise ValueError('TSP return must join outer layers across one pole region.')
    _validate_selected_electrical('TSP spiral pass partition', database, winding, layout)


def validate_tsp_q_only_pair_join(database, winding, layout):
    """Check the TSP q-only source halves and their parameterized return seam."""
    from layout_analysis import signed_circular_distance

    factors = _integer_divider_tuple(
        getattr(winding, 'branch_dividers', None))
    if not supports_integer_tsp_q_only_pair_join(winding, factors):
        raise ValueError('TSP Q-only pairing is outside the formula domain.')

    q = int(winding.q)
    Q = factors[0]
    pp = int(winding.num_poles) // 2
    layers = int(winding.num_layers)
    phases = int(winding.num_phases)
    tau = phases * q
    g = gcd(layers // 2, pp)
    seam_multiplier = min(2 * g - 1, 2 * pp - 2 * g + 1)
    parent_length = pp * layers * q // Q
    expected_branch_count = Q * phases
    if len(database) != expected_branch_count:
        raise ValueError(
            f'TSP Q-only pairing produced {len(database)} branches; '
            f'expected {expected_branch_count}.')

    phase_sign = {
        (slot, layer): (phase, sign)
        for slot, layer, phase, sign in phase_map(
            winding.num_slots, winding.num_poles, layers,
            layout.phase_shift_list, phases)
    }
    counts_by_phase = Counter()
    for branch_id, path in database:
        if len(path) != 2 * parent_length:
            raise ValueError(
                f'TSP Q-only branch {branch_id} has the wrong joined length.')
        if any(node[2] != (
                node[0] - layout.phase_shift_list[node[1]]) % q
               for node in path):
            raise ValueError(
                f'TSP Q-only branch {branch_id} has invalid q coordinates.')

        halves = (path[:parent_length], path[parent_length:])
        half_phases = []
        for half in halves:
            start_phase, start_sign = phase_sign[tuple(half[0][:2])]
            end_phase, end_sign = phase_sign[tuple(half[-1][:2])]
            if (start_sign != 1 or end_sign != -1
                    or start_phase != end_phase
                    or any(phase_sign[tuple(node[:2])][0] != start_phase
                           for node in half)):
                raise ValueError(
                    f'TSP Q-only branch {branch_id} has a parent half that '
                    'does not run N-to-S within one phase.')
            half_phases.append(start_phase)
        if half_phases[0] != half_phases[1]:
            raise ValueError(
                f'TSP Q-only branch {branch_id} joins different phases.')

        outlet = path[parent_length - 1]
        inlet = path[parent_length]
        outlet_phase, outlet_sign = phase_sign[tuple(outlet[:2])]
        inlet_phase, inlet_sign = phase_sign[tuple(inlet[:2])]
        if (outlet_phase != inlet_phase or outlet_sign != -1
                or inlet_sign != 1
                or abs(inlet[1] - outlet[1]) != layers - 1):
            raise ValueError(
                f'TSP Q-only branch {branch_id} does not form a top-bottom '
                'N-to-S parent return seam.')

        shift = layout.phase_shift_list
        outlet_slot = outlet[0] - shift[outlet[1]]
        inlet_slot = inlet[0] - shift[inlet[1]]
        pitch = signed_circular_distance(
            winding.num_slots, inlet_slot, outlet_slot)
        expected_pitches = {
            seam_multiplier * tau - 1,
            seam_multiplier * tau + 1,
        }
        if abs(pitch) not in expected_pitches:
            raise ValueError(
                f'TSP Q-only branch {branch_id} seam pitch does not match '
                'the gcd-derived return formula.')
        possible_steps = circular_travel_steps(
            outlet_slot % winding.num_slots,
            inlet_slot % winding.num_slots, winding.num_slots)
        if (not possible_steps or min(
                pole_region_crossings(outlet_slot, step, tau)
                for step in possible_steps) > 1):
            raise ValueError(
                f'TSP Q-only branch {branch_id} seam crosses multiple '
                'pole regions.')
        counts_by_phase[half_phases[0]] += 1

    expected_counts = Counter({phase: Q for phase in range(phases)})
    if counts_by_phase != expected_counts:
        raise ValueError(
            'TSP Q-only pairing must produce Q joined branches per phase.')


def validate_tlp_q_only_pair_join(database, winding, layout):
    """Check full-Q source pairing and the TLP insertion-return formula."""
    from layout_analysis import signed_circular_distance

    factors = _integer_divider_tuple(
        getattr(winding, 'branch_dividers', None))
    if not supports_integer_tlp_q_only_pair_join(winding, factors):
        raise ValueError('TLP Q-only pairing is outside the formula domain.')

    Q = factors[0]
    q = int(winding.q)
    pp = int(winding.num_poles) // 2
    layers = int(winding.num_layers)
    phases = int(winding.num_phases)
    tau = phases * q
    parent_length = pp * layers
    if len(database) != Q * phases:
        raise ValueError(
            f'TLP Q-only pairing produced {len(database)} branches; '
            f'expected {Q * phases}.')

    phase_sign = {
        (slot, layer): (phase, sign)
        for slot, layer, phase, sign in phase_map(
            winding.num_slots, winding.num_poles, layers,
            layout.phase_shift_list, phases)
    }
    branches_by_phase = Counter()
    starts_by_phase_layer = Counter()
    lanes_by_phase_layer = {
        (phase, layer): []
        for phase in range(phases) for layer in (0, layers - 1)
    }
    for branch_id, path in database:
        if len(path) != 2 * parent_length:
            raise ValueError(
                f'TLP Q-only branch {branch_id} has the wrong joined length.')
        if any(node[2] != (
                node[0] - layout.phase_shift_list[node[1]]) % q
               for node in path):
            raise ValueError(
                f'TLP Q-only branch {branch_id} has invalid q coordinates.')

        halves = (path[:parent_length], path[parent_length:])
        half_phase_lanes = []
        for half in halves:
            start_phase, start_sign = phase_sign[tuple(half[0][:2])]
            end_phase, end_sign = phase_sign[tuple(half[-1][:2])]
            if (start_sign != 1 or end_sign != -1
                    or start_phase != end_phase
                    or any(phase_sign[tuple(node[:2])][0] != start_phase
                           for node in half)):
                raise ValueError(
                    f'TLP Q-only branch {branch_id} has a parent half that '
                    'does not run N-to-S within one phase.')
            lane = half[0][2]
            half_phase_lanes.append((start_phase, lane, half[0][1]))

        first_phase, first_lane, first_layer = half_phase_lanes[0]
        second_phase, second_lane, second_layer = half_phase_lanes[1]
        if first_phase != second_phase:
            raise ValueError(
                f'TLP Q-only branch {branch_id} joins different phases.')
        if (first_layer != second_layer
                or first_layer not in (0, layers - 1)):
            raise ValueError(
                f'TLP Q-only branch {branch_id} crosses the two source cohorts.')

        outlet = halves[0][-1]
        inlet = halves[1][0]
        outlet_phase, outlet_sign = phase_sign[tuple(outlet[:2])]
        inlet_phase, inlet_sign = phase_sign[tuple(inlet[:2])]
        if (outlet_phase != inlet_phase or outlet_phase != first_phase
                or outlet_sign != -1 or inlet_sign != 1
                or abs(inlet[1] - outlet[1]) != layers - 1):
            raise ValueError(
                f'TLP Q-only branch {branch_id} does not form a top-bottom '
                'N-to-S parent return seam.')

        shifts = layout.phase_shift_list
        outlet_slot = outlet[0] - shifts[outlet[1]]
        inlet_slot = inlet[0] - shifts[inlet[1]]
        pitch = signed_circular_distance(
            winding.num_slots, inlet_slot, outlet_slot)
        if abs(pitch) not in (tau - 1, tau + 1):
            raise ValueError(
                f'TLP Q-only branch {branch_id} seam pitch is not tau plus '
                'or minus one.')
        oriented_pitch = pitch if inlet[1] < outlet[1] else -pitch
        if oriented_pitch not in (tau - 1, tau + 1):
            raise ValueError(
                f'TLP Q-only branch {branch_id} special return opposes layer '
                'traversal.')
        possible_steps = circular_travel_steps(
            outlet_slot % winding.num_slots,
            inlet_slot % winding.num_slots, winding.num_slots)
        if (not possible_steps or any(
                pole_region_crossings(outlet_slot, step, tau) > 1
                for step in possible_steps)):
            raise ValueError(
                f'TLP Q-only branch {branch_id} seam crosses multiple pole '
                'regions.')
        lane_delta = (second_lane - first_lane) % Q
        if min(lane_delta, Q - lane_delta) != 1:
            raise ValueError(
                f'TLP Q-only branch {branch_id} does not join adjacent q lanes.')
        if any(node[2] != lane for half, (_phase, lane, _layer)
               in zip(halves, half_phase_lanes) for node in half):
            raise ValueError(
                f'TLP Q-only branch {branch_id} changes q lane within a '
                'parent half.')

        branches_by_phase[first_phase] += 1
        starts_by_phase_layer[(first_phase, first_layer)] += 1
        lanes_by_phase_layer[(first_phase, first_layer)].extend(
            (first_lane, second_lane))

    if branches_by_phase != Counter({phase: Q for phase in range(phases)}):
        raise ValueError(
            'TLP Q-only pairing must produce Q joined branches per phase.')
    expected_layer_counts = Counter({
        (phase, layer): Q // 2
        for phase in range(phases) for layer in (0, layers - 1)
    })
    if starts_by_phase_layer != expected_layer_counts:
        raise ValueError(
            'TLP Q-only pairing must retain Q/2 starts in each end-layer '
            'cohort per phase.')
    for phase in range(phases):
        for layer in (0, layers - 1):
            if sorted(lanes_by_phase_layer[(phase, layer)]) != list(range(Q)):
                raise ValueError(
                    'TLP Q-only pairs must partition every q lane once per '
                    'phase and end-layer cohort.')

    validate_tlp_welds(database, winding, layout)


def _validate_route_connections(pattern, decision, database, winding, layout,
                                topology=None):
    """Apply each registered route's connection checks to actual generated paths."""
    set_routes = getattr(database, 'phase_set_array', {}).get('routes', ())
    for set_index, (local_database, local_winding, local_layout) in enumerate(
            _three_phase_set_views(database, winding, layout, topology)):
        route = (set_routes[set_index].get('route_name')
                 if set_index < len(set_routes) else decision.route_name)
        if pattern == 'TSP' and route == 'tsp_q_only_pair_join':
            validate_tsp_q_only_pair_join(
                local_database, local_winding, local_layout)
        if pattern == 'TSP' and route == 'tsp_pp_p2_sector':
            validate_tsp_pp_p2_sector(
                local_database, local_winding, local_layout)
        if pattern == 'TSP' and route == 'tsp_spiral_pass_partition':
            validate_tsp_spiral_pass_partition(
                local_database, local_winding, local_layout)
        if pattern == 'TLP' and route == 'tlp_q_only_pair_join':
            validate_tlp_q_only_pair_join(
                local_database, local_winding, local_layout)
        if route in ('bwp_pp', 'bwp_q_pp'):
            validate_selected_bwp_pp(
                local_database, local_winding, local_layout)
        if pattern == 'CP' and route in (None, 'cp', 'cp_q_pp_two',
                                         'cp_pp_four_pass_weave',
                                         'cp_q_only_pair_join',
                                         'cp_q_pp_p2_parent_slices'):
            validate_selected_cp(
                local_database, local_winding, local_layout,
                require_signed_travel=(
                    route == 'cp_q_pp_p2_parent_slices'))
        if pattern == 'ZPP' and route in (
                None, 'zpp', 'zpp_q_pp_two', 'zpp_pp_only_half_turn',
                'zpp_pp_only_indexed_translation',
                'zpp_pp_only_centered_entry_translation'):
            validate_selected_zpp(local_database, local_winding, local_layout)
        if pattern == 'ZLP' and route in (None, 'zlp', 'zlp_p2_mirrored',
                                       'zlp_pp_p2_source_cut'):
            validate_selected_zlp(local_database, local_winding, local_layout)
        if pattern == 'SLP' and (
                route in ('slp_q_pp_parent_cut', 'slp_p2_from_reference',
                          'slp_full_q_p2', 'slp_q_pp_p2_parent_cut',
                          'slp_pair_lane_p2', 'slp_pp_p2_sector')
                or (set_routes and route in (None, 'pp_only'))):
            if route == 'slp_q_pp_p2_parent_cut':
                validate_slp_q_pp_p2_parent_cut(
                    local_database, local_winding, local_layout)
            else:
                validate_slp_factor_route(
                    local_database, local_winding, local_layout)
        if pattern in ('SSP', 'SLP') and route in (
                None, 'pp_only', 'ssp_p2_reflected',
                'ssp_q_pp_parent_cut', 'slp_q_pp_parent_cut'):
            validate_pp_only_spiral(
                pattern, local_database, local_winding, local_layout)


@lru_cache(maxsize=4096)
def _cached_neutral_non_wave_preflight(pattern, q, poles, phases, layers, naa,
                                       factors, weld_side, route_name,
                                       cp_array_global_layers=None):
    """Dry-construct a neutral route so UI admission matches production.

    This is a geometry-keyed structural oracle, not a parameter whitelist.  It
    executes the registered constructor without publishing a calculation, then
    applies the same coverage, edge, electrical-retention, and identity gates
    as the production path.
    """
    slots = q * poles * phases
    if Fraction(str(slots)).denominator == 1:
        slots = int(slots)
    winding = SimpleNamespace(
        q=q, num_slots=slots, num_poles=poles,
        num_phases=phases, num_layers=layers, ab=naa,
        branch_dividers=tuple(factors))
    if cp_array_global_layers is not None:
        winding._cp_array_global_layers = cp_array_global_layers
    tp_info = SimpleNamespace(
        tp_type='Regular', tp_interval=0, tp_times=0, uni_tp=0,
        pltp_fl=0, pltp_ll=0, jltp=0, jld=1, pole_group_tp={})
    layout = SimpleNamespace(
        phase_shift_pattern='None', phase_shift_list=[0] * layers,
        radial_shift=0, inlet_from_weld_side=int(weld_side),
        inlet_index_adjustments_phase_a=[])
    decision = PatternRouteDecision(
        'enabled', route_name or f'{pattern.lower()}_default',
        'Neutral structural probe.', pattern, tuple(factors),
        route_name=route_name, is_default=route_name is None)
    try:
        starts, database = _dispatch_winding_pattern(
            pattern, tp_info, winding, layout, route_decision=decision)
        if database is None:
            return 'disabled', f'{pattern} constructor returned no layout.'
        _validate_generated_layout_consistency(
            pattern, starts, database, winding)
        _validate_route_connections(pattern, decision, database, winding, layout)
        identity = _analyze_pattern_identity_for_sets(
            pattern, database, winding, layout)
        if identity['status'] == 'candidate':
            return ('candidate',
                    'Workbench-only Pattern identity candidate: '
                    + identity['reason'])
    except (PatternConfigurationError, ValueError, TypeError, IndexError,
            ZeroDivisionError) as exc:
        return 'disabled', f'Known structural construction failure: {exc}'
    return 'enabled', 'Neutral construction passes coverage, edge, and identity gates.'


def pp_only_configuration_is_unshifted(tp_info, layout, weld_side=False):
    return (getattr(tp_info, 'tp_type', 'Regular') == 'Regular'
            and all(getattr(tp_info, key, 0) == 0 for key in
                    ('tp_interval', 'tp_times', 'uni_tp', 'pltp_fl', 'pltp_ll', 'jltp'))
            and all(spec.get('tp_type', 'Regular') == 'Regular'
                    and all(spec.get(key, 0) == 0 for key in
                            ('tp_interval', 'tp_times', 'uni_tp', 'pltp_fl',
                             'pltp_ll', 'jltp'))
                    for spec in getattr(tp_info, 'pole_group_tp', {}).values())
            and getattr(layout, 'phase_shift_pattern', 'None') == 'None'
            and not getattr(layout, 'radial_shift', 0)
            and bool(getattr(layout, 'inlet_from_weld_side', 0)) == weld_side
            and all(shift == 0 for shift in getattr(layout, 'phase_shift_list', ()))
            and not any(getattr(layout, 'inlet_index_adjustments_phase_a', ())))



# ---------------------------------------------------------------------------
# Pattern algorithms
# ---------------------------------------------------------------------------
#
# Each algorithm function is named with the canonical Word abbreviation.
# Public callers and internal dispatch both use the same BWP/UWP/... names.

def pattern_BWP(TP_info,Winding_Para,Layout_Para):
    
    mode_name, q_divider, pp_divider, p2_divider, all_ab_list = classify_branch_mode(Winding_Para.ab, Winding_Para.q, Winding_Para.num_poles, 'BWP')
    q_divider, pp_divider, p2_divider = branch_dividers_for_pattern('BWP', Winding_Para)
    # print (mode_name, q_divider, pp_divider, p2_divider,all_ab_list)
    
    ###1. Follow the pole divider pattern. 
    pp_per_branch = Winding_Para.num_poles // pp_divider ### pole regions per branch  
    num_phasors = Winding_Para.q*Winding_Para.num_phases ### Phasors per pole

    ##########Define the Start conductor IDs based on the parallel branches
    start_layer = 0 
    start_phasor = 0
    start_conductor_ids = []
    ### If Winding_Para.ab is the multiples of q, then we should determin the start cond ids
    if isinstance(Winding_Para.q,int):  ### If q is int
        phasor_range = Winding_Para.q*Winding_Para.num_phases
        for k in range(p2_divider):
            for n in range(pp_divider):
                start_conductor_ids += [(i+n*pp_per_branch*num_phasors+k*num_phasors, start_layer, start_phasor+(i) % (Winding_Para.q)) for i in range(phasor_range)]
        # print('start_conductor_ids',start_conductor_ids)

    ##### After the correct defination of SCI We can then Define the Connections 
    Connection = []
    db_conductor_id = []
    d_ini = 1  #### Initial winding direction 
    num_layer_pattern = int(Winding_Para.num_layers/2)  ### Layer patterns 
    # ####Assume welding side are identical
    pltp_fl = TP_info.pltp_fl ## parallel layer trans position-first_layer
    pltp_ll = TP_info.pltp_ll  ## parallel layer trans position-last_layer
    ultp = TP_info.uni_tp  ## uniform layer trans position
    jltp = TP_info.jltp  ## uniform layer jump trans position
    
    num_poles_pattern_repeat = int(Winding_Para.num_poles/2/pp_divider)-1
 
    for i in range(num_layer_pattern):
        uni_conn = [d_ini,1,0]
        uniform_connection = [uni_conn]
        uniform_layer_connection = [uni_conn,[d_ini,-1,ultp]]
        jump_layer_connection = [[d_ini,1,jltp]]  
        Connection += uniform_layer_connection * num_poles_pattern_repeat + uniform_connection + jump_layer_connection
    Connection.pop()
    parallel_layer_connection = [[d_ini,0,pltp_ll]]
    Connection += parallel_layer_connection
    
    if p2_divider == 1:  ##### if p2_divider == 1 do the end layer connection
        for i in range(num_layer_pattern):
            uni_conn = [-d_ini,-1,0]
            uniform_connection = [uni_conn]
            uniform_layer_connection = [uni_conn,[-d_ini,1,ultp]]
            jump_layer_connection = [[-d_ini,-1,jltp]]  
            #parallel_layer_connection = [[1,0,pltp]]
            Connection += uniform_layer_connection * num_poles_pattern_repeat + uniform_connection + jump_layer_connection
    Connection.pop()
    
    if q_divider != Winding_Para.q: ### if q_divider != q, means the series connection between different wire sets is needed.
        q_per_branch = Winding_Para.q//q_divider
        new_start_conductor_ids = []  ### A new_start_conductor_is needed, two or more wire path need to be combined to form a new branch.
        for i in range(int(len(start_conductor_ids)/q_per_branch)):    
            k = int(i * q_per_branch)  ### k is the interval index where the new start cond id located 
            new_start_conductor_ids.append(start_conductor_ids[k]) ### so we rearrange the sci (start cond id) based on k
        # print('start_conductor_ids',start_conductor_ids)
        # print ('Len_Connection',len(Connection))
        start_conductor_id = start_conductor_ids[0]
        start_conductor_ids = new_start_conductor_ids  ## Update start cond ids 
        New_Connection = []
        occupied_phasors = []
        left_phasors = list(range(q_per_branch))
        for n in range(q_per_branch-1):  ## loop to create the full connection for each of the small groups
            segment = Connection
            New_Connection += segment
            # print('start_conductor_id'+str(n),start_conductor_id)
            occupied_phasors.append(start_conductor_id[2]) 
            left_phasors = left_phasors = [p for p in left_phasors if p not in occupied_phasors]
            end_conductor_id,group_cond_ids = get_branch_connections(start_conductor_id,segment,Winding_Para,Layout_Para)
            # print('end_conductor_id'+str(n),end_conductor_id)
            phasor_change = None
            for shift in range(q_per_branch):
                candidate = (end_conductor_id[2] + shift) % q_per_branch
                if candidate in left_phasors:
                    phasor_change = shift
                    break
            if phasor_change is None:
                raise ValueError(f"No valid phasor found for end_conductor_id {end_conductor_id[2]}")
            start_conductor_id,group_cond_ids = get_branch_connections(end_conductor_id,[[-d_ini,0,-phasor_change]],Winding_Para,Layout_Para)
            New_Connection += [[-d_ini,0,-phasor_change]]
        New_Connection += Connection
        Connection = New_Connection
    
    rotate_sequence_for_weld_inlet = False
    if Layout_Para.inlet_from_weld_side == 1:
        Connection, start_conductor_ids, rotate_sequence_for_weld_inlet = shift_inlet_to_weld_side_or_rotate_later(
            Connection,
            start_conductor_ids,
            Winding_Para,
            Layout_Para,
        )
        
    Connection = TP_modi(TP_info,Connection)
    db_conductor_id = get_db_cond_id_from_connection(start_conductor_ids,Connection,Winding_Para, Layout_Para)
    if rotate_sequence_for_weld_inlet:
        start_conductor_ids, db_conductor_id = rotate_db_conductor_ids_to_weld_inlet(db_conductor_id)
    return start_conductor_ids, db_conductor_id

def is_half_integer_uwp_2q(pattern_name, winding):
    """Accept any positive half-integer q with UWP and Naa=2q."""
    q = Fraction(str(winding.q))
    return (normalize_pattern_name(pattern_name, allow_extra=True) == 'UWP'
            and q > 0 and q.denominator == 2 and winding.ab == 2 * q)


def is_half_integer_uwp_p2_factorization(pattern_name, winding, factors):
    """Match the registered UWP half-q P2 parent `(q, 1, 2)` exactly."""
    q = Fraction(str(winding.q))
    try:
        selected = tuple(Fraction(str(value)) for value in factors)
    except (TypeError, ValueError, ZeroDivisionError):
        return False
    if len(selected) != 3:
        return False
    q_divider, pp_divider, p2_divider = selected
    poles = getattr(winding, 'num_poles', 0)
    return (normalize_pattern_name(pattern_name, allow_extra=True) == 'UWP'
            and q > 0 and q.denominator == 2 and q_divider == q
            and pp_divider == 1 and p2_divider == 2
            and winding.ab == 2 * q
            and type(poles) is int and poles > 0 and poles % 2 == 0)


def supports_half_integer_uwp_p2(pattern_name, winding, factors):
    """Admit the registered positive half-integer UWP `(q, 1, 2)` parent."""
    q = Fraction(str(winding.q))
    return (not pattern_rejects_divider_tuple(pattern_name, factors)
            and is_half_integer_uwp_p2_factorization(
                pattern_name, winding, factors)
            and _supported_phase_domain(winding)
            and winding.num_layers > 0 and winding.num_layers % 2 == 0
            and getattr(winding, 'num_slots', q * winding.num_poles * winding.num_phases)
            == q * winding.num_poles * winding.num_phases)


def _half_integer_default_dividers(pattern, winding, q):
    """Name an existing fractional construction when no tuple was selected."""
    if pattern == 'UWP' and winding.ab == 2 * q:
        return q, 1, 2
    pp = winding.num_poles // 2
    if (pattern in ('BWP', 'UWP') and type(winding.ab) is int
            and winding.ab > 0 and pp % winding.ab == 0):
        return 1, winding.ab, 1
    return None


def _half_integer_configuration_failure(rule, configuration, layout, winding):
    if configuration is None or layout is None:
        return None
    if rule.configuration_capability != 'fractional_wave':
        return None
    if getattr(layout, 'radial_shift', 0):
        return 'This half-integer wave route does not support radial conductor swaps (CHW shift).'
    if getattr(layout, 'inlet_from_weld_side', 0):
        return 'This half-integer wave route does not support a weld-side inlet.'
    if (rule.route_name.endswith('_sector_array')
            and any(getattr(layout, 'inlet_index_adjustments_phase_a', ()) or ())):
        return 'Global wave array does not support inlet adjustments.'
    shifts = tuple(getattr(layout, 'phase_shift_list', ()))
    if len(shifts) != winding.num_layers or any(type(value) is not int for value in shifts):
        return 'Half-integer wave route requires one integer slot shift per layer.'
    return None


def _half_integer_uwp_transfer_source(pattern, winding, factors):
    """Find a P2 source for relocating a full-wave split to the PP factor.

    The available source has two inlet cohorts. Its P2 constructor and the
    UWP PP/P2 splitting rule jointly bound this transfer to a binary split.
    """
    q = Fraction(str(winding.q))
    if pattern != 'UWP' or factors[0] != q or factors[2] != 1:
        return None
    source = (q, 1, factors[1])
    return source if supports_half_integer_uwp_p2(pattern, winding, source) else None


def _half_integer_route_decision(pattern, winding, factors, configuration=None,
                                 layout=None):
    """Classify every positive half-integer tuple by factors and construction."""
    q = Fraction(str(winding.q))
    if q.denominator != 2:
        return None
    implicit = factors is None
    if implicit:
        factors = _half_integer_default_dividers(pattern, winding, q)
        if factors is None:
            return PatternRouteDecision(
                'disabled', 'fractional_route_unsupported',
                'No registered default half-integer construction matches this Pattern and Naa.',
                pattern, None, admission='unsupported-yet')
    try:
        selected = (None if factors is None else
                    tuple(Fraction(str(value)) for value in factors))
    except (TypeError, ValueError, ZeroDivisionError):
        selected = None
    if selected is None or len(selected) != 3 or any(value <= 0 for value in selected):
        return PatternRouteDecision(
            'disabled', 'invalid_dividers',
            'Half-integer q requires three positive Q, PP and P2 dividers.',
            pattern, selected)
    if selected[0] * selected[1] * selected[2] != winding.ab:
        return PatternRouteDecision(
            'disabled', 'divider_product_mismatch',
            'Q x PP x P2 must equal Naa.', pattern, selected)
    pp = winding.num_poles // 2
    if (selected[0] not in (1, q) or selected[1].denominator != 1
            or selected[2] not in (1, 2) or pp <= 0
            or pp % selected[1]):
        return PatternRouteDecision(
            'disabled', 'invalid_dividers',
            'Half-integer Q must be 1 or q; PP must divide pole pairs; P2 must be 1 or 2.',
            pattern, selected)
    sector_default = (
        implicit and selected[0] == selected[2] == 1
        and selected[1] == winding.ab
        and is_fractional_sector_array_candidate(pattern, winding))
    # The legacy implicit array divides a whole-wave sector, whereas an
    # explicit UWP PP divider requests the ordinary PP/P2 split contract.
    if not sector_default and pattern_rejects_divider_tuple(pattern, selected, q, pp):
        return PatternRouteDecision(
            'disabled', f'{pattern.lower()}_factor_rejected',
            divider_exclusion_reason(pattern, selected, q, pp),
            pattern, selected)
    if (q <= 0 or winding.num_poles <= 0 or winding.num_poles % 2
            or not _supported_phase_domain(winding)
            or winding.num_layers <= 0 or winding.num_layers % 2
            or getattr(winding, 'num_slots', q * winding.num_poles * winding.num_phases)
            != q * winding.num_poles * winding.num_phases):
        return PatternRouteDecision(
            'disabled', 'fractional_geometry_invalid',
            'Half-integer routes require positive q, even poles/layers, odd m>=3 and exact slots.',
            pattern, selected)

    route_name = None
    transfer_source = _half_integer_uwp_transfer_source(
        pattern, winding, selected)
    if transfer_source is not None:
        if q <= 1:
            reason = ('The reference has no second inlet cohort to transfer; '
                      'q-and-pp would only alias q-and-P2.')
        else:
            reason = None
        if reason:
            return PatternRouteDecision(
                'disabled', 'uwp_half_integer_q_pp', reason, pattern, selected)
        route_name = 'uwp_half_integer_q_pp'
    elif pattern == 'UWP' and selected[0] == q and selected[2] == 2:
        if supports_half_integer_uwp_p2(pattern, winding, selected):
            route_name = 'uwp_half_integer_p2'
    elif (pattern in ('BWP', 'UWP') and selected == (1, winding.ab, 1)
          and is_fractional_sector_array_candidate(pattern, winding)):
        route_name = f'{pattern.lower()}_fractional_sector_array'
    if route_name is None:
        return PatternRouteDecision(
            'disabled', 'fractional_route_unsupported',
            'No registered half-integer construction matches this Pattern and divider tuple.',
            pattern, selected, admission='unsupported-yet')

    rule = PATTERN_ROUTE_RULES[route_name]
    configuration_error = _half_integer_configuration_failure(
        rule, configuration, layout, winding)
    if configuration_error:
        return PatternRouteDecision(
            'disabled', 'invalid_configuration', configuration_error,
            pattern, selected, route_name=route_name,
            pin_profile=rule.pin_profile, required_inlet=rule.required_inlet,
            effective_configuration=_effective_tp_type(configuration, winding),
            is_default=implicit)
    return PatternRouteDecision(
        'enabled', rule.rule_id,
        'Registered half-integer construction; generated connections determine the case result.',
        pattern, selected, route_name=route_name,
        pin_profile=rule.pin_profile, required_inlet=rule.required_inlet,
        effective_configuration=_effective_tp_type(configuration, winding),
        is_default=implicit)


def half_integer_q_pp_route_decision(pattern, winding, factors):
    """Compatibility view of the unified half-integer route classifier."""
    q = Fraction(str(winding.q))
    try:
        selected = tuple(Fraction(str(value)) for value in factors)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    if (q.denominator != 2 or len(selected) != 3
            or selected[0] != q or selected[2] != 1):
        return None
    return _half_integer_route_decision(
        normalize_pattern_name(pattern, allow_extra=True), winding, selected)


def supports_half_integer_uwp_q_pp(pattern, winding, factors):
    decision = half_integer_q_pp_route_decision(pattern, winding, factors)
    return decision is not None and decision.status == 'enabled'


def _fractional_uwp_q_pp(tp, winding, layout):
    """Rotate the reversed S-inlet cohort by whole two-pole slot periods.

    Half-q has unequal integer cohort sizes; no fractional-slot translation or
    equal-Q-per-cohort assumption is made. Whole waves preserve occupancy.
    """
    q = Fraction(str(winding.q))
    target = tuple(Fraction(str(value)) for value in winding.branch_dividers)
    source = _half_integer_uwp_transfer_source('UWP', winding, target)
    if source is None:
        raise ValueError('No P2 source can supply this UWP full-wave transfer.')
    reference = deepcopy(winding)
    reference.branch_dividers = source
    _, database = _fractional_uwp_2q(tp, reference, layout)
    records = phase_map(
        winding.num_slots, winding.num_poles, winding.num_layers,
        layout.phase_shift_list, winding.num_phases)
    pole_signs = {(slot, layer): sign
                  for slot, layer, _phase, sign in records}
    source_branches = [(branch_id, tuple(path))
                       for branch_id, path in database]
    _, database = orient_p2_branches_n_to_s(database, reference, layout)
    transfer = transfer_uwp_half_integer_q_pp(
        source_branches,
        database,
        q=q,
        source_dividers=source,
        target_dividers=target,
        num_slots=winding.num_slots,
        num_poles=winding.num_poles,
        num_phases=winding.num_phases,
        num_layers=winding.num_layers,
        phase_shift_list=layout.phase_shift_list,
        pole_sign_by_position=pole_signs,
    )
    database[:] = [
        [branch_id, list(path)] for branch_id, path in transfer.branches
    ]
    starts = [path[0] for _, path in database]
    _validate_generated_layout_consistency('UWP', starts, database, winding)
    report = fractional_uwp_candidate_report(database, winding, layout)
    if not report['layout_retained']:
        raise ValueError('Half-q transfer validation failed: ' + ', '.join(report['errors']))
    database.sector_deployment_report = dict(
        source_dividers=source, target_dividers=target,
        two_pole_slot_period=transfer.two_pole_slot_period,
        branch_rotations=list(transfer.branch_rotations),
        second_cohort_layer_mapping='reverse source S-to-N paths')
    return starts, database


def is_fractional_bwp_single_branch(pattern_name, winding):
    """Single-sector BWP candidate for any positive half-integer q."""
    q = Fraction(str(winding.q))
    return (normalize_pattern_name(pattern_name, allow_extra=True) == 'BWP'
            and q > 0 and q.denominator == 2
            and winding.ab == 1)


def is_fractional_sector_array_candidate(pattern_name, winding):
    """A BWP/UWP global-wave candidate is available when Naa divides pole pairs."""
    q = Fraction(str(winding.q))
    poles = getattr(winding, 'num_poles', 0)
    ab = winding.ab
    pattern = normalize_pattern_name(pattern_name, allow_extra=True)
    supported_q = q > 0 and q.denominator == 2
    return (pattern in ('BWP', 'UWP') and supported_q
            and not (pattern == 'UWP' and ab == 2 * q)
            and type(poles) is int
            and poles > 0 and poles % 2 == 0 and type(ab) is int
            and ab > 0 and (poles // 2) % ab == 0)


def _fractional_sector_array(pattern, tp, winding, layout, route_decision=None):
    """Interleave sector wave segments into globally travelling branches."""
    slots, poles, layers, ab = (winding.num_slots, winding.num_poles,
                                winding.num_layers, winding.ab)
    if (getattr(layout, 'radial_shift', 0)
            or getattr(layout, 'inlet_from_weld_side', 0)
            or any(getattr(layout, 'inlet_index_adjustments_phase_a', ()))):
        raise ValueError('Global wave array does not support radial swap, weld-side inlet, or inlet adjustments.')
    if slots != Fraction(str(winding.q)) * poles * winding.num_phases:
        raise ValueError('Global wave array slots do not match q, poles and phases.')
    width = slots // ab
    sector_winding = SimpleNamespace(q=winding.q, num_slots=width,
                                     num_poles=poles // ab,
                                     num_phases=winding.num_phases,
                                     num_layers=layers, ab=1)
    sector_layout = SimpleNamespace(phase_shift_list=[0] * layers,
                                    radial_shift=0, inlet_from_weld_side=0)
    generator = (_fractional_bwp_single_branch if pattern == 'BWP'
                 else _fractional_uwp_single_branch)
    _, module = generator(tp, sector_winding, sector_layout)
    selected_route = (route_decision.route_name if route_decision is not None else
                      selected_integer_divider_route(pattern, winding)
                      if pattern == 'UWP' else None)
    if selected_route == 'uwp_q_factor_p2':
        # Two adjacent q starts traverse each layer pair in opposite order.
        # Each lane contains two passes through the two-pole sector.
        lane_width = 2 * sector_winding.num_poles
        pair_width = winding.q * lane_width
        for branch in module:
            path = branch[1]
            branch[1] = [node
                         for lane in range(winding.q)
                         for pair in (range(layers // 2) if lane % 2 == 0
                                      else range(layers // 2 - 1, -1, -1))
                         for node in path[pair * pair_width + lane * lane_width:
                                          pair * pair_width + (lane + 1) * lane_width]]
    forward_pitch_limit = int(3 * Fraction(str(winding.q)) + Fraction(1, 2))
    if selected_route in ('uwp_q_factor_pp', 'uwp_q_factor_p2'):
        forward_pitch_limit = 3 * winding.q + 1
    if any(not 0 <= slot < width for _, path in module
           for slot, _, _ in path):
        raise ValueError('Wave segment leaves its local slot interval.')
    shifts = layout.phase_shift_list
    if len(shifts) != layers:
        raise ValueError('Global wave array requires one integer shift per layer.')
    if any(type(shift) is not int for shift in shifts):
        raise ValueError('Global wave array phase shifts must be integer slots.')
    nodes_per_segment = sector_winding.num_poles
    segment_count = len(module[0][1]) // nodes_per_segment
    database = _CandidateBranches()
    crossings = []
    special_edges = []
    phase_offsets = []
    for _, module_path in module:
        segment_offsets = [0]
        default_slots = [module_path[0][0]]
        for node_index in range(1, len(module_path)):
            source = module_path[node_index - 1]
            target = module_path[node_index]
            segment_index = (node_index - 1) // nodes_per_segment
            if node_index % nodes_per_segment and (pattern == 'BWP'
                                                   or Fraction(str(winding.q)).denominator == 1):
                forward = (pattern == 'UWP' or
                           (segment_index // (layers // 2)) % 2 == 0)
                pitch = ((target[0] - source[0]) % width if forward
                         else -((source[0] - target[0]) % width))
                default_slots.append((default_slots[-1] + pitch) % slots)
                continue
            if node_index % nodes_per_segment:
                default_slots.append(target[0] + segment_offsets[-1] * width)
                continue
            source_slot = default_slots[-1]
            def circular_pitch(offset):
                forward = (target[0] + offset * width - source_slot) % slots
                return forward if forward <= slots / 2 else forward - slots
            turnaround = (pattern == 'BWP'
                          and (segment_index + 1) % (layers // 2) == 0)
            direction = (1 if pattern == 'UWP'
                         or (segment_index // (layers // 2)) % 2 == 0 else -1)
            options = range(ab)
            if not turnaround:
                directed = [offset for offset in options
                            if circular_pitch(offset) * direction > 0
                             and abs(circular_pitch(offset)) <= forward_pitch_limit]
                if directed:
                    options = directed
            segment_offsets.append(min(options,
                                       key=lambda offset: (abs(circular_pitch(offset)),
                                                           offset)))
            default_slots.append(target[0] + segment_offsets[-1] * width)
        if len(segment_offsets) != segment_count:
            raise ValueError('Global wave array has an incomplete segment sweep.')
        phase_offsets.append(segment_offsets)
        for branch_sector in range(ab):
            path = []
            for node_index, (_, layer, phasor) in enumerate(module_path):
                default = (default_slots[node_index] + branch_sector * width) % slots
                actual = (default + shifts[layer]) % slots
                if actual // width != default // width:
                    crossings.append((len(database) + 1, default,
                                      actual, layer))
                path.append((actual, layer, phasor))
            branch_id = len(database) + 1
            for edge_index in range(len(module_path) - 1):
                if (edge_index + 1) % sector_winding.num_poles:
                    continue
                source = module_path[edge_index]
                target = module_path[edge_index + 1]
                segment_index = edge_index // nodes_per_segment
                default_source = (default_slots[edge_index]
                                  + branch_sector * width) % slots
                default_target = (default_slots[edge_index + 1]
                                  + branch_sector * width) % slots
                grid_forward = (path[edge_index + 1][0]
                                - path[edge_index][0]) % slots
                grid_shortest = (grid_forward if grid_forward <= slots / 2
                                 else grid_forward - slots)
                default_forward = (default_target - default_source) % slots
                signed_pitch = (default_forward if default_forward <= slots / 2
                                else default_forward - slots)
                if pattern == 'BWP':
                    jumper = segment_index < layers // 2 - 1
                else:
                    jumper = (segment_index + 1) % int(2 * Fraction(str(winding.q))) == 0
                special_edges.append(dict(
                    branch_id=branch_id,
                    kind='jumper' if jumper else 'first_last_layer',
                    side='insert',
                    from_default=(default_source, source[1]),
                    to_default=(default_target, target[1]),
                    default_signed_pitch=signed_pitch,
                    shifted_signed_pitch=(signed_pitch + shifts[target[1]]
                                          - shifts[source[1]]),
                    grid_shortest_pitch=grid_shortest))
            database.append([branch_id, path])
    report = fractional_uwp_candidate_report(database, winding, layout)
    emf_only = EMF_ASYMMETRY_ERRORS
    if not report['topology_valid'] or set(report['errors']) - emf_only:
        raise ValueError('Global wave array fails connection validation: '
                         + ', '.join(report['errors']))
    database.sector_array_report = dict(sector_slots=width, sectors=ab,
                                        segment_offsets=phase_offsets[0],
                                        phase_segment_offsets=phase_offsets,
                                        shifted_boundary_crossings=crossings,
                                        special_edges=special_edges)
    database.transposition_report = {'groups': {}, 'exchanges': [], 'search': {}}
    return [branch[1][0] for branch in database], database


def _fractional_wave_single_branch(pattern, tp, winding, layout):
    """Generate an inspected BWP reversal or distinct forward-only UWP module."""
    slots, poles, layers = winding.num_slots, winding.num_poles, winding.num_layers
    q = Fraction(str(winding.q))
    phases = winding.num_phases
    period = 2 * phases * q
    supported_q = (q > 0 and (q.denominator == 2 if pattern == 'BWP'
                            else q.denominator in (1, 2)))
    if (not _supported_phase_domain(winding) or poles < 2 or poles % 2 or layers < 2
            or layers % 2 or not supported_q
            or slots != period * poles // 2):
        raise ValueError('Fractional wave module requires a supported half-integer q, '
                         'odd m>=3, even poles/layers and matching slots.')
    if (tp.tp_type != 'Regular' or any(getattr(tp, key, 0) for key in
            ('tp_interval', 'tp_times', 'uni_tp', 'pltp_fl', 'pltp_ll', 'jltp'))):
        raise ValueError('Fractional wave module does not support transposition.')
    if any(spec.get('tp_type', 'Regular') != 'Regular' or any(
            spec.get(key, 0) for key in
            ('tp_interval', 'tp_times', 'uni_tp', 'pltp_fl', 'pltp_ll', 'jltp'))
            for spec in getattr(tp, 'pole_group_tp', {}).values()):
        raise ValueError('Fractional wave module does not support pole-group transposition.')
    if getattr(layout, 'radial_shift', 0) or getattr(layout, 'inlet_from_weld_side', 0):
        raise ValueError('Fractional wave module does not support radial swap or weld-side inlet.')
    shifts = layout.phase_shift_list
    if len(shifts) != layers:
        raise ValueError('Fractional wave module requires one phase shift per layer.')
    if any(type(shift) is not int for shift in shifts):
        raise ValueError('Fractional wave module phase shifts must be integer slots.')
    if pattern == 'BWP':
        definition = build_bwp_half_integer_base_path(
            q,
            num_slots=slots,
            num_poles=poles,
            num_phases=phases,
            num_layers=layers,
        )
        base = list(definition.positions)
        segment_directions = list(definition.segment_directions)
        period = definition.two_pole_slot_period
        short_pitch = definition.short_pitch
        long_pitch = definition.long_pitch
    else:
        base = []
        segment_directions = []
        period = int(period)
        short_pitch = period // 2
        long_pitch = period - short_pitch
        passes = int(2 * q)
        pairs = range(layers // 2)
        for pair in pairs:
            for pass_index in range(passes):
                forward_lane = pass_index % 2 == 0
                segment_directions.append(True)
                seed = pass_index // 2
                for index in range(poles):
                    pitch = short_pitch if forward_lane else long_pitch
                    slot = (seed + (index // 2) * period
                            + (index % 2) * pitch) % slots
                    layer = 2 * pair + (index % 2 if forward_lane else 1 - index % 2)
                    base.append((slot, layer))
    if len(base) != poles * len(segment_directions):
        raise ValueError('Fractional wave module has an incomplete sweep.')
    for edge_index, (source, target) in enumerate(zip(base, base[1:])):
        if (edge_index + 1) % poles == 0:
            continue
        forward = segment_directions[edge_index // poles]
        signed = ((target[0] - source[0]) % slots if forward
                  else -((source[0] - target[0]) % slots))
        if abs(signed) not in (short_pitch, long_pitch) or abs(target[1] - source[1]) != 1:
            raise ValueError('Fractional wave module violates an ordinary wave edge.')
    database = _CandidateBranches()
    for branch_id in range(1, phases + 1):
        # Each two-belt step advances the phase label by two modulo odd m.
        rotation = int(2 * q * (((branch_id - 1) * ((phases + 1) // 2)) % phases))
        path = [((slot + rotation + shifts[layer]) % slots, layer, slot % period)
                for slot, layer in base]
        database.append([branch_id, path])
    report = fractional_uwp_candidate_report(database, winding, layout)
    if not report['layout_retained']:
        raise ValueError(f'Fractional {pattern} module fails validation: '
                         + ', '.join(report['errors']))
    database.transposition_report = {'groups': {}, 'exchanges': [], 'search': {}}
    return [branch[1][0] for branch in database], database


def _fractional_bwp_single_branch(tp, winding, layout):
    return _fractional_wave_single_branch('BWP', tp, winding, layout)


def _fractional_uwp_single_branch(tp, winding, layout):
    return _fractional_wave_single_branch('UWP', tp, winding, layout)


def fractional_uwp_candidate_report(database, winding, layout):
    records = phase_map(winding.num_slots, winding.num_poles,
                        winding.num_layers, layout.phase_shift_list,
                        winding.num_phases)
    report = validate_branches([branch[1] for branch in database], records,
                               winding.num_slots, winding.num_poles, winding.ab,
                               winding.num_phases)
    if hasattr(database, 'transposition_report'):
        report['transposition'] = database.transposition_report
    if hasattr(database, 'sector_array_report'):
        report['sector_array'] = database.sector_array_report
    if hasattr(database, 'series_connections'):
        report['series_connections'] = database.series_connections
    if hasattr(database, 'phase_set_array'):
        report['phase_set_array'] = database.phase_set_array
    return report


class _CandidateBranches(list):
    """Keep candidate diagnostics with the paths, outside production state."""


def _fractional_group_settings(tp):
    names = ('PoleN', 'PoleS')
    keys = ('tp_interval', 'tp_times', 'uni_tp', 'pltp_fl', 'pltp_ll', 'jltp')
    active_keys = {
        'Regular': {'uni_tp', 'pltp_fl', 'pltp_ll', 'jltp'},
        'Times': {'tp_times'},
        'Interval': {'tp_interval'},
        'Optimize': set(),
    }
    raw = getattr(tp, 'pole_group_tp', {}) or {}
    settings = {}
    for name in names:
        source = raw.get(name, {})
        kind = source.get('tp_type', 'Regular')
        if kind not in ('Regular', 'Times', 'Interval', 'Optimize'):
            raise ValueError(f'Invalid {name} transposition type: {kind}.')
        try:
            values = {key: int(source.get(key, 0)) if key in active_keys[kind]
                      else 0 for key in keys}
        except (TypeError, ValueError) as exc:
            raise ValueError(f'Invalid {name} transposition parameter.') from exc
        settings[name] = dict(tp_type=kind, **values)
    return settings


def _fractional_start_pole_groups(paths, winding, records):
    """Group each phase's branch starts by their signed first-layer pole."""
    lookup = {(slot, layer): (phase, sign)
              for slot, layer, phase, sign in records}
    groups = {name: {phase: [] for phase in range(winding.num_phases)}
              for name in ('PoleN', 'PoleS')}
    for phase in range(winding.num_phases):
        for branch in range(phase * winding.ab, (phase + 1) * winding.ab):
            start_phase, sign = lookup[paths[branch][0][:2]]
            if start_phase != phase:
                raise ValueError('Fractional UWP branch start has the wrong phase.')
            groups['PoleN' if sign > 0 else 'PoleS'][phase].append(branch)
    return groups


def _fractional_swap_candidates(paths, winding, records, group, shifts):
    """Find insertion-side cuts where two same-group branch tails can cross."""
    from itertools import combinations
    slots = winding.num_slots
    pitch = 3 * Fraction(str(winding.q))
    low = pitch.numerator // pitch.denominator
    high = -(-pitch.numerator // pitch.denominator)
    lookup = {(slot, layer): (phase, sign)
              for slot, layer, phase, sign in records}
    group_members = _fractional_start_pole_groups(paths, winding, records)[group]

    def valid_insertion_edge(path, original, edge):
        start, end = path[edge], path[edge + 1]
        old_start, old_end = original[edge], original[edge + 1]
        shift = shifts[end[1]] - shifts[start[1]]
        base_pitch = (old_end[0] - old_start[0]) % slots
        new_pitch = (end[0] - start[0]) % slots
        return (edge % 2 == 1
                and (base_pitch - shift) % slots in (low, high)
                and 0 < new_pitch < slots // 2
                and abs(new_pitch - base_pitch) <= 1
                and end[1] - start[1] == old_end[1] - old_start[1])

    candidates = []
    for phase in range(winding.num_phases):
        for first, second in combinations(group_members[phase], 2):
            for left in range(0, len(paths[first]) - 2, 2):
                cut = left + 2
                first_tail = paths[first][cut:]
                second_tail = paths[second][cut:]
                if len(first_tail) != len(second_tail):
                    continue
                if any(a[1] != b[1] or lookup[a[:2]] != lookup[b[:2]]
                       for a, b in zip(first_tail, second_tail)):
                    continue
                first_path = paths[first][:cut] + second_tail
                second_path = paths[second][:cut] + first_tail
                edge = cut - 1
                if (valid_insertion_edge(first_path, paths[first], edge)
                        and valid_insertion_edge(second_path, paths[second], edge)):
                    candidates.append((first, second, left, left))
    return candidates


def _apply_fractional_group_tp(database, winding, layout, settings):
    """Apply a bounded candidate exchange; reject partial or invalid routes."""
    records = phase_map(winding.num_slots, winding.num_poles,
                        winding.num_layers, layout.phase_shift_list,
                        winding.num_phases)
    paths = [branch[1][:] for branch in database]
    original_paths = [path[:] for path in paths]
    start_groups = _fractional_start_pole_groups(original_paths, winding, records)
    details = {'groups': settings, 'exchanges': [], 'search': {},
               'pitch_rule': ('pair crossover within one slot of base wave pitch; '
                              'Uniform +1 cyclic return within group width minus one slots'),
               'interval_basis': 'insertion-side edge position'}
    changed_edges = []
    def signed_pitch(start, end):
        pitch = (end[0] - start[0]) % winding.num_slots
        return pitch if pitch <= winding.num_slots // 2 else pitch - winding.num_slots

    used_pairs = set()
    lookup = {(slot, layer): (phase, sign)
              for slot, layer, phase, sign in records}

    def apply_tail_rotation(group, members, left, max_pitch_change=1):
        """Rotate intact downstream weld-pair sequences at one insert cut."""
        cut = left + 2
        if len(members) < 2 or len(set(members)) != len(members):
            raise ValueError(f'{group} needs distinct branches for transposition.')
        if any((branch, left) in used_pairs for branch in members):
            raise ValueError(f'{group} transposition positions conflict.')
        tails = [paths[branch][cut:] for branch in members]
        if not tails[0] or any(len(tail) != len(tails[0]) for tail in tails):
            raise ValueError(f'{group} has an invalid insertion-side cut.')

        edge_rows = []
        for offset, branch in enumerate(members):
            donor_tail = tails[(offset + 1) % len(members)]
            if any(a[1] != b[1] or lookup[a[:2]] != lookup[b[:2]]
                   for a, b in zip(tails[offset], donor_tail)):
                raise ValueError(f'{group} cyclic tails differ in phase or layer.')
            start = paths[branch][cut - 1]
            old_end, new_end = tails[offset][0], donor_tail[0]
            base_pitch = signed_pitch(start, old_end)
            new_pitch = signed_pitch(start, new_end)
            if (abs(new_pitch - base_pitch) > max_pitch_change
                    or new_pitch <= 0 or new_pitch >= winding.num_slots // 2
                    or new_end[1] != old_end[1]):
                raise ValueError(
                    f'{group} has an invalid insertion-side crossover at '
                    f'position {left // 2 + 1}.')
            edge_rows.append({
                'branch': branch + 1, 'edge': cut,
                'side': 'insert', 'from': start[:2], 'to': new_end[:2],
                'signed_pitch': new_pitch, 'base_pitch': base_pitch,
            })
        if (len(members) > 2 and
                sum(abs(row['signed_pitch'] - row['base_pitch']) > 1
                    for row in edge_rows) > 1):
            raise ValueError(f'{group} has more than one wide cyclic return.')

        for offset, branch in enumerate(members):
            paths[branch][cut:] = tails[(offset + 1) % len(members)]
            used_pairs.add((branch, left))
        changed_edges.extend(edge_rows)
        details['exchanges'].append({
            'group': group, 'branches': [branch + 1 for branch in members],
            'insert_position': left // 2 + 1,
            'indices': [left] * len(members),
            'group_step': 1,
            'scope': ('tail_after_insert' if len(members) == 2
                      else 'cyclic_tail_rotation'),
            'conductors': [tail[0][:2] for tail in tails],
            'weld_pairs': [[conductor[:2] for conductor in tail[:2]]
                           for tail in tails],
        })

    for group in ('PoleN', 'PoleS'):
        spec = settings[group]
        kind = spec['tp_type']
        active_regular = [key for key in ('uni_tp', 'pltp_fl', 'pltp_ll', 'jltp')
                          if spec[key]]
        if kind == 'Regular' and not active_regular:
            continue
        if all(len(branches) < 2 for branches in start_groups[group].values()):
            raise ValueError(f'{group} has fewer than two branches per phase; '
                             'transposition is unavailable.')
        if kind == 'Regular' and 'uni_tp' in active_regular:
            if spec['uni_tp'] != 1:
                raise ValueError(f'{group} Uniform accepts only 0 or 1.')
            if len(active_regular) > 1:
                raise ValueError(f'{group} Uniform cannot be combined with other Regular offsets.')
            insert_positions = len(original_paths[0]) // 2 - 1
            if insert_positions <= 0:
                raise ValueError(f'{group} has no insertion-side positions for Uniform.')
            for position in range(insert_positions):
                for phase in range(winding.num_phases):
                    members = start_groups[group][phase]
                    if len(members) < 2:
                        raise ValueError(f'{group} has fewer than two branches in phase {phase}.')
                    apply_tail_rotation(group, members, 2 * position,
                                        max_pitch_change=len(members) - 1)
            continue
        eligible = _fractional_swap_candidates(
            original_paths, winding, records, group, layout.phase_shift_list)
        by_position = {}
        for candidate in eligible:
            position = candidate[2] // 2
            phase = candidate[0] // winding.ab
            by_position.setdefault(position, {}).setdefault(phase, []).append(candidate)
        positions = sorted(position for position, phase_candidates in
                           by_position.items()
                           if len(phase_candidates) == winding.num_phases)
        def candidates_at(position):
            return [by_position[position][phase][0]
                    for phase in sorted(by_position[position])]
        if kind == 'Regular':
            selected = []
            for key in active_regular:
                value = spec[key]
                layer = 0 if key == 'pltp_fl' else winding.num_layers - 2 if key == 'pltp_ll' else None
                matches = []
                for candidate in eligible:
                    first, second, left, right = candidate
                    source = original_paths[first][left]
                    target = original_paths[second][right]
                    delta = (target[0] - source[0]) % winding.num_slots
                    if delta > winding.num_slots // 2:
                        delta -= winding.num_slots
                    if delta != value or (layer is not None and source[1] != layer):
                        continue
                    if key == 'jltp' and not (
                            left + 2 < len(original_paths[first])
                            and original_paths[first][left + 2][1]
                            - original_paths[first][left + 1][1]
                            == (1 if value > 0 else -1)):
                        continue
                    matches.append(candidate)
                if not matches:
                    raise ValueError(f'{group} transposition has no eligible {key} position.')
                selected.append(matches[0])
        elif kind == 'Times':
            count = spec['tp_times']
            if count <= 0 or count > len(positions):
                raise ValueError(f'{group} transposition Times exceeds eligible positions.')
            selected = [candidate for i in range(count)
                        for candidate in candidates_at(
                            positions[(i + 1) * len(positions) // (count + 1)])]
        elif kind == 'Interval':
            interval = spec['tp_interval']
            if interval <= 0:
                raise ValueError(f'{group} transposition Interval must be positive.')
            selected = [candidate for position in positions
                        if (position + 1) % interval == 0
                        for candidate in candidates_at(position)]
            if not selected:
                raise ValueError(f'{group} transposition has no eligible Interval position.')
        else:
            if not eligible:
                raise ValueError(f'{group} transposition Optimize has no eligible positions.')
            limit = min(len(eligible), 200)
            scored = []
            for candidate in eligible[:limit]:
                trial = [path[:] for path in paths]
                a, b, i, j = candidate
                trial[a][i + 2:], trial[b][j + 2:] = (
                    trial[b][j + 2:], trial[a][i + 2:])
                score_report = validate_branches(trial, records, winding.num_slots,
                                                 winding.num_poles, winding.ab)
                emf = score_report['branch_emf']
                spread = sum(max(abs(complex(*v) - sum(complex(*x) for x in values)/len(values))
                                 for v in values) for values in emf.values())
                scored.append((spread, candidate))
            best_score, best_candidate = min(scored)
            selected = [best_candidate]
            details['search'][group] = {'eligible': len(eligible),
                                        'insertion_positions': len(positions), 'checked': limit,
                                        'best_emf_spread': best_score,
                                        'stop_reason': 'limit' if len(eligible) > limit else 'exhausted'}
        if len(set(selected)) != len(selected):
            raise ValueError(f'{group} transposition selects the same position twice.')
        selected.sort(key=lambda candidate: candidate[2])
        for candidate in selected:
            a, b, i, j = candidate
            if i != j:
                raise ValueError(f'{group} exchange cuts must share one insertion position.')
            apply_tail_rotation(group, (a, b), i)
    def weld_connections(branches):
        return Counter(tuple(tuple(conductor[:2]) for conductor in path[index:index + 2])
                       for path in branches for index in range(0, len(path) - 1, 2))

    if weld_connections(paths) != weld_connections(original_paths):
        raise ValueError('Grouped transposition changed a weld-side connection.')
    details['weld_connections_preserved'] = True
    def physical_insert_edges(branches):
        return Counter((tuple(path[index][:2]), tuple(path[index + 1][:2]))
                       for path in branches
                       for index in range(1, len(path) - 1, 2))

    added_edges = physical_insert_edges(paths) - physical_insert_edges(original_paths)
    reported_edges = Counter((tuple(edge['from']), tuple(edge['to']))
                             for edge in changed_edges)
    if added_edges != reported_edges:
        raise ValueError('Grouped transposition report does not match physical insertion edges.')
    details['edges'] = changed_edges
    result = _CandidateBranches([[index + 1, path] for index, path in enumerate(paths)])
    report = fractional_uwp_candidate_report(result, winding, layout)
    if not report['layout_retained']:
        raise ValueError('Grouped transposition fails phase or connection validation: '
                         + ', '.join(report['errors']))
    result.transposition_report = details
    return result


def assess_fractional_uwp_pair_swap(starts, database, winding, layout):
    """Screen a same-cut tail swap of the first neighboring pair per phase.

    All other branch paths remain unchanged. The EMF test below applies only
    to that topology; it does not reject more general UWP transpositions.
    """
    result = {'status': 'rejected', 'reason_code': 'unsupported_domain',
              'reason': 'Pair-only swap requires a half-integer UWP candidate.',
              'pair_indices': []}
    if (not is_half_integer_uwp_2q('UWP', winding)
            or not _supported_phase_domain(winding) or winding.ab < 3):
        return result
    records = phase_map(winding.num_slots, winding.num_poles,
                        winding.num_layers, layout.phase_shift_list,
                        winding.num_phases)
    lookup = {(slot, layer): (phase, sign)
              for slot, layer, phase, sign in records}
    pairs = []
    for phase in range(winding.num_phases):
        indices = range(phase * winding.ab, (phase + 1) * winding.ab)
        adjacent = [(first, second) for first in indices for second in indices
                    if first < second
                    and lookup[starts[first][:2]] == lookup[starts[second][:2]]
                    and lookup[starts[first][:2]][0] == phase
                    and (starts[second][0] - starts[first][0]) % winding.num_slots == 1]
        if not adjacent:
            result.update(reason_code='nonadjacent_starts',
                          reason='No same-sign neighboring branch starts exist in every phase.')
            return result
        # Starts are phase-then-slot ordered; take the first neighboring pair.
        pairs.append(adjacent[0])
    result['pair_indices'] = pairs
    report = validate_branches([branch[1] for branch in database], records,
                               winding.num_slots, winding.num_poles, winding.ab,
                               winding.num_phases)
    if not report['layout_retained']:
        result.update(reason_code='invalid_base',
                      reason='The base UWP candidate fails topology or phase checks.')
        return result
    result.update(status='unverified', reason_code='route_unverified',
                  reason='EMF asymmetry does not exclude this swap; wave-pitch '
                         'crossovers and the complete route remain unverified.',
                  layout_report=report)
    return result


def _fractional_uwp_2q(TP_info, winding, layout):
    """Build half-integer UWP P2 branches in each selected pole-pair sector."""
    q = Fraction(str(winding.q))
    if (not _supported_phase_domain(winding) or winding.num_layers % 2
             or winding.num_slots != q * winding.num_poles * winding.num_phases):
        raise ValueError('Half-integer UWP requires odd m>=3, even layers, and matching slots.')
    settings = _fractional_group_settings(TP_info)
    if (not hasattr(TP_info, 'pole_group_tp') and
            (TP_info.tp_type != 'Regular'
            or any(getattr(TP_info, key, 0) for key in
                   ('uni_tp', 'pltp_fl', 'pltp_ll', 'jltp'))
            or getattr(TP_info, 'jld', 1) != 1)):
        raise ValueError('Half-integer UWP candidate requires no transposition.')
    if getattr(layout, 'radial_shift', 0):
        raise ValueError('Half-integer UWP candidate does not support radial conductor swaps.')
    if getattr(layout, 'inlet_from_weld_side', 0):
        raise ValueError('Half-integer UWP candidate starts on the first layer; disable weld-side inlet.')

    shifts = layout.phase_shift_list
    records = phase_map(winding.num_slots, winding.num_poles,
                        winding.num_layers, shifts, winding.num_phases)
    phases = {(slot, layer): phase for slot, layer, phase, _ in records}
    factors = getattr(winding, 'branch_dividers', (q, 1, 2))
    definition = build_uwp_half_integer_p2_definition(
        q,
        dividers=factors,
        num_slots=winding.num_slots,
        num_poles=winding.num_poles,
        num_phases=winding.num_phases,
        num_layers=winding.num_layers,
        phase_shift_list=shifts,
        phase_by_position=phases,
    )
    starts = list(definition.starts)
    connections = [list(step) for step in definition.connections]
    database = get_db_cond_id_from_connection(starts, connections, winding, layout)
    report = fractional_uwp_candidate_report(database, winding, layout)
    if not report['layout_retained']:
        raise ValueError('Half-integer UWP candidate fails conductor or phase validation: '
                         + ', '.join(report['errors']))
    if any(spec['tp_type'] != 'Regular' or any(spec[key] for key in
           ('uni_tp', 'pltp_fl', 'pltp_ll', 'jltp'))
           for spec in settings.values()):
        database = _apply_fractional_group_tp(database, winding, layout, settings)
    else:
        database = _CandidateBranches(database)
        database.transposition_report = {'groups': settings, 'exchanges': [], 'search': {}}
    starts = [branch[1][0] for branch in database]
    return starts, database


def supports_uwp_complementary_waves(winding):
    """Two complementary full-circle branches for every positive integer q."""
    return (winding.ab == 2 and type(winding.q) is int and winding.q > 0
            and winding.num_layers >= 2 and winding.num_layers % 2 == 0)


def uses_uwp_complementary_q_pp(winding):
    """Use the q/P2 reference for admitted proper/full-Q, PP=2, P2=1."""
    factors = _integer_divider_tuple(getattr(winding, 'branch_dividers', ()))
    return (factors is not None and factors[1:] == (2, 1)
            and selected_integer_divider_route('UWP', winding) == 'uwp_q_factor_pp')


def validate_uwp_pp_settings(tp, winding, layout):
    """Validate configurable Regular wave permutations before construction."""
    if getattr(tp, 'tp_type', 'Regular') != 'Regular':
        raise ValueError('UWP PP-only currently requires Regular transposition.')
    if getattr(tp, 'jld', 1) != 1:
        raise ValueError('UWP PP-only requires forward jumper direction.')
    for key in ('tp_interval', 'tp_times', 'pltp_fl', 'pltp_ll'):
        if getattr(tp, key, 0):
            raise ValueError(f'UWP PP-only does not implement {key}.')
    shifts = layout.phase_shift_list
    if len(shifts) != winding.num_layers or any(type(s) is not int for s in shifts):
        raise ValueError('UWP PP-only requires one integer shift per layer.')
    if (getattr(layout, 'radial_shift', 0) or getattr(layout, 'inlet_from_weld_side', 0)
            or any(getattr(layout, 'inlet_index_adjustments_phase_a', ()))):
        raise ValueError('UWP PP-only requires automatic insert-side starts and no radial swap.')
    settings = {key: getattr(tp, key, 0) for key in ('uni_tp', 'jltp')}
    groups = getattr(tp, 'pole_group_tp', {}) or {}
    if set(groups) - {'PoleN', 'PoleS'}:
        raise ValueError('Pole-group names must be PoleN or PoleS.')
    for name, spec in groups.items():
        if spec.get('tp_type', 'Regular') != 'Regular' or any(
                spec.get(k, 0) for k in ('tp_interval','tp_times','pltp_fl','pltp_ll')):
            raise ValueError('UWP PP-only pole groups support Regular Uniform and Jump only.')
    if (any(type(v) is not int for v in settings.values())
            or any(type(spec.get(k,0)) is not int for spec in groups.values() for k in settings)):
        raise ValueError('Transposition offsets must be integers.')
    return settings


def _uwp_complementary_waves(winding, layout):
    """Each pair contains q complete waves; the second branch descends pairs."""
    q, poles, layers = winding.q, winding.num_poles, winding.num_layers
    phases = winding.num_phases
    slots, pitch = winding.num_slots, phases*q
    database = []
    # (m+1)*phase is even and congruent to phase modulo odd m: one N belt
    # per phase, without a three-phase start table.
    for phase in range(phases):
        phase_offset = ((phases + 1) * phase % (2 * phases)) * q
        for descending in (False, True):
            path = []
            for pair_index in range(layers//2):
                pair = layers//2-1-pair_index if descending else pair_index
                for wave in range(q):
                    # Snake through q positions: pair boundaries retain the last
                    # lane, so their pitch is m*q regardless of the size of q.
                    lane = q-1-wave if pair_index % 2 else wave
                    for pole in range(poles):
                        slot = (phase_offset + (slots//2 if descending else 0)
                                + lane + (-pole if descending else pole)*pitch) % slots
                        layer = 2*pair + (1-pole%2 if descending else pole%2)
                        path.append((slot, layer, slot % q))
            database.append([len(database)+1, path])
    validate_pp_only_uwp(database, winding, layout)
    if any(abs(b[1]-a[1]) != 1 for _, path in database
           for a,b in zip(path,path[1:])):
        raise ValueError('UWP complementary waves require adjacent-layer edges.')
    return [path[0] for _, path in database], database


def _configured_uwp_pp(tp, winding, layout):
    """Apply q-position transposition and layer shifts to any admitted PP base."""
    settings = validate_uwp_pp_settings(tp, winding, layout)
    base_winding = SimpleNamespace(**vars(winding)) if hasattr(winding, '__dict__') else SimpleNamespace(**winding._asdict())
    base_winding._uwp_pp_base = True
    base_layout = SimpleNamespace(phase_shift_list=[0]*winding.num_layers,
                                  radial_shift=0, inlet_from_weld_side=0)
    neutral = SimpleNamespace(tp_type='Regular', tp_interval=0, tp_times=0,
                              uni_tp=0, jltp=0, pltp_fl=0, pltp_ll=0, jld=1)
    _, database = pattern_UWP(neutral, base_winding, base_layout)
    original = deepcopy(database)
    q, slots = winding.q, winding.num_slots
    groups = getattr(tp, 'pole_group_tp', {}) or {}
    records = {(s,l):(phase,sign) for s,l,phase,sign in phase_map(
        slots,winding.num_poles,winding.num_layers,base_layout.phase_shift_list,
        winding.num_phases)}
    used_groups = set()
    for branch_index, ((_,path), (_,base)) in enumerate(zip(database, original)):
        direction = _uwp_pp_branch_direction(winding, branch_index)
        group = 'PoleN' if records[base[0][:2]][1] == 1 else 'PoleS'
        used_groups.add(group)
        spec = groups.get(group,{})
        uniform = settings['uni_tp'] + spec.get('uni_tp',0)
        jump = settings['jltp'] + spec.get('jltp',0)
        pair_offset = 0
        uniform_steps = 0
        for index,(slot,layer,phasor) in enumerate(base):
            if index and index % 2 == 0:
                previous = base[index-1]
                if previous[1]//2 != layer//2:
                    pair_offset += jump
                    uniform_steps = 0
                elif ((index-1) % 2 == 1 and abs(previous[1]-layer) == 1
                      and (direction*(slot-previous[0])) % slots == winding.num_phases*q):
                    uniform_steps += 1
                elif (index-1) % 2 == 1:
                    # Preserve the declared next-wave start; Uniform schedules
                    # the same permutation in each wave, not accumulated drift.
                    uniform_steps = 0
            offset = direction * (pair_offset + uniform_steps*uniform)
            position = (slot % q + offset) % q
            path[index] = (slot-slot%q+position,layer,phasor-slot%q+position)
    for name,spec in groups.items():
        if name not in used_groups and any(spec.get(k,0) for k in settings):
            raise ValueError(f'UWP PP-only has no {name} inlet branches to transpose.')
    def weld_pairs(branches):
        return {frozenset((a[:2], b[:2])) for _, path in branches
                for a, b in zip(path[::2], path[1::2])}
    if weld_pairs(database) != weld_pairs(original):
        raise ValueError('UWP transposition changed a weld-side connection.')
    # Check the declared wave contract before shifting the phase map.
    if uses_uwp_complementary_q_pp(winding):
        validate_uwp_balanced_paths(database, winding, base_layout)
    else:
        validate_pp_only_uwp(database, winding, base_layout)
    shifts = layout.phase_shift_list
    for branch_index, (_,path) in enumerate(database):
        direction = _uwp_pp_branch_direction(winding, branch_index)
        for a,b in zip(path,path[1:]):
            forward = (direction*(b[0]-a[0])) % slots + direction*(shifts[b[1]]-shifts[a[1]])
            if not 0 < forward < slots:
                raise ValueError('UWP layer shifts reverse or overrun a forward wave edge.')
        for i,(slot,layer,position) in enumerate(path):
            path[i] = ((slot+shifts[layer])%slots,layer,position)
    _validate_selected_electrical('Configured UWP PP-only', database, winding, layout)
    if uses_uwp_complementary_q_pp(winding):
        inlet_signs = {(s,l): sign for s,l,phase,sign in phase_map(
            slots,winding.num_poles,winding.num_layers,shifts,winding.num_phases)}
        if any(inlet_signs[path[0][:2]] != 1 for _,path in database):
            raise ValueError('UWP q-and-pp requires N-pole inlets after configuration.')
    return [path[0] for _,path in database], database


def _uwp_q_only_series(tp, winding, layout):
    """Join corresponding oriented q/P2 branches using one same-layer weld."""
    reference = SimpleNamespace(**vars(winding)) if hasattr(winding, '__dict__') else SimpleNamespace(**winding._asdict())
    divider = winding.branch_dividers[0]
    reference.ab = 2*divider
    reference.branch_dividers = (divider,1,2)
    _, source = get_winding_layout('UWP',tp,reference,layout)
    database = _CandidateBranches()
    bridges = []
    source_by_id = {branch_id: path for branch_id, path in source}
    ordered_parents = []
    for phase in range(winding.num_phases):
        for group in range(divider):
            first_id = source[phase*2*divider+group][0]
            second_id = source[phase*2*divider+divider+group][0]
            ordered_parents.extend((
                (first_id, source_by_id[first_id]),
                (second_id, source_by_id[second_id]),
            ))

    joined_groups = apply_route_formula(
        'uwp_q_only_series', ordered_parents,
        tuple(winding.branch_dividers))
    for joined in joined_groups:
        first_id, second_id = joined.source_ids
        first, second = source_by_id[first_id], source_by_id[second_id]
        if first[-1][1] != second[0][1]:
            raise ValueError('UWP q-only series bridge must connect the same layer.')
        branch_id = len(database)+1
        bridges.append(dict(branch_id=branch_id, edge_index=len(first)-1,
                            start=first[-1][:2], end=second[0][:2],
                            kind='same_layer_series', side='weld'))
        database.append([branch_id, joined.path])
    database.series_connections = bridges
    _validate_selected_electrical('UWP q-only series',database,winding,layout)
    return [path[0] for _,path in database],database


def pattern_UWP(TP_info,Winding_Para,Layout_Para):
    # Dedicated UWP routes return early; the legacy BWP fallback is checked below.
    mode_name, q_divider, pp_divider, p2_divider, all_ab_list = classify_branch_mode(Winding_Para.ab, Winding_Para.q, Winding_Para.num_poles, 'UWP')
    used_bwp_fallback = False
    selected_route = selected_integer_divider_route('UWP', Winding_Para)
    if selected_route == 'uwp_q_only_series':
        return _uwp_q_only_series(TP_info,Winding_Para,Layout_Para)
    complementary_q_pp = uses_uwp_complementary_q_pp(Winding_Para)
    if (selected_route == 'pp_only' or complementary_q_pp) and not getattr(Winding_Para, '_uwp_pp_base', False):
        return _configured_uwp_pp(TP_info, Winding_Para, Layout_Para)
    if complementary_q_pp:
        # Reuse q/P2's q/Q full-circle waves and derived balanced permutation.
        # Only the construction input is mapped; the actual route remains P2=1,
        # so its terminal handling must not inherit P2 post-processing.
        reference = SimpleNamespace(**vars(Winding_Para)) if hasattr(Winding_Para, '__dict__') else SimpleNamespace(**Winding_Para._asdict())
        reference.branch_dividers = (Winding_Para.branch_dividers[0], 1, 2)
        _, database = _uwp_balanced_q_factor(TP_info, reference, Layout_Para)
        _, database = _deploy_second_pole_region(
            database, Winding_Para, Layout_Para, reflect_pole_travel=True)
        validate_uwp_balanced_paths(database, Winding_Para, Layout_Para)
        return [path[0] for _,path in database], database
    if selected_route == 'pp_only' and supports_uwp_complementary_waves(Winding_Para):
        return _uwp_complementary_waves(Winding_Para, Layout_Para)
    if selected_route == 'uwp_balanced_q':
        return _uwp_balanced_q_factor(TP_info, Winding_Para, Layout_Para)
    if selected_route in ('uwp_q_factor_pp', 'uwp_q_factor_p2'):
        starts, database = _fractional_sector_array(
            'UWP', TP_info, Winding_Para, Layout_Para)
        validate_uwp_proper_q_factor(
            database, Winding_Para, Layout_Para,
            braided=selected_route == 'uwp_q_factor_p2')
        return starts, database
    if (getattr(Winding_Para, 'branch_dividers', None) is not None
            and tuple(Winding_Para.branch_dividers) !=
            (q_divider, pp_divider, p2_divider)
            and branch_dividers_for_pattern('UWP', Winding_Para)
            == (1, Winding_Para.ab, 1)):
        # Reuse the full-circle wave segments; the standard two-branch route
        # cannot represent a pole-pair split.
        starts, database = _fractional_sector_array(
            'UWP', TP_info, Winding_Para, Layout_Para)
        validate_pp_only_uwp(database, Winding_Para, Layout_Para)
        return starts, database
    if TP_info.tp_type in ('Times', 'Interval'):
        # Disabled Regular controls must not leak into the scaffold that the
        # scheduled transposition modifies. Keep mandatory series transitions.
        TP_info = deepcopy(TP_info)
        values = dict(uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0)
        if hasattr(TP_info, '_replace'):
            TP_info = TP_info._replace(**values)
        else:
            for field, value in values.items():
                setattr(TP_info, field, value)
    # print (mode_name, q_divider, pp_divider, p2_divider,all_ab_list)
    
    ###1. Follow the pole divider pattern. 
    pp_per_branch = Winding_Para.num_poles // pp_divider ### pole regions per branch  
    num_phasors = Winding_Para.q*Winding_Para.num_phases ### Phasors per pole
    
    ##########Define the Start conductor IDs based on the parallel branches
    start_layer = 0 
    start_phasor = 0
    start_conductor_ids = []
    ### If Winding_Para.ab is the multiples of q, then we should determin the start cond ids
    if isinstance(Winding_Para.q,int):  ### If q is int
        phasor_range = Winding_Para.q*Winding_Para.num_phases
        for k in range(p2_divider):
            for n in range(pp_divider):
                start_conductor_ids += [(i+n*pp_per_branch*num_phasors+k*num_phasors, start_layer, start_phasor+(i) % (Winding_Para.q)) for i in range(phasor_range)]
    # print('start_conductor_ids',start_conductor_ids)
                
    ##### Define the Connections
    Connection = []
    d_ini = 1
    pltp_fl = TP_info.pltp_fl ## parallel layer trans position-first_layer
    pltp_ll = TP_info.pltp_ll  ## parallel layer trans position-last_layer
    ultp = TP_info.uni_tp  ## uniform layer trans position
    jltp = TP_info.jltp  ## uniform layer jump trans position
    jld = TP_info.jld ## jump layer direction
    
    ### Define the connection only works under ab == 1 or 2
    if Winding_Para.ab == int(2*Winding_Para.q) and Winding_Para.q != 1:
        num_layer_pattern = int(Winding_Para.num_layers/2)
        num_poles_pattern_repeat = int(Winding_Para.num_poles/2/pp_divider)-1
        for i in range(num_layer_pattern):
            uni_conn = [d_ini,1,0]
            uniform_connection = [uni_conn]
            uniform_layer_connection = [uni_conn,[d_ini,-1,ultp]]
            jump_layer_connection = [[jld,1,jltp]] ######### jump layer direction can be -1 or 1
            Connection += uniform_layer_connection * num_poles_pattern_repeat + uniform_connection + jump_layer_connection
        Connection.pop()
        
    elif Winding_Para.ab == 2 or Winding_Para.ab == 1:
        start_conductor_ids = [(i*Winding_Para.q,0,0) for i in range(Winding_Para.num_phases*2)]
        if Winding_Para.ab == 2 and p2_divider == 2:
            # Anchor both cohorts to the same phase-local N belt. The common
            # P2 orientation reverses the second cohort to last-layer entry.
            n_inlets = {}
            for slot, layer, phase, sign in phase_map(
                    Winding_Para.num_slots, Winding_Para.num_poles,
                    Winding_Para.num_layers, Layout_Para.phase_shift_list,
                    Winding_Para.num_phases):
                if layer == 0 and sign == 1:
                    n_inlets.setdefault(phase, slot)
            start_conductor_ids = [
                ((n_inlets[phase] + cohort * num_phasors) % Winding_Para.num_slots, 0, 0)
                for cohort in range(2) for phase in range(Winding_Para.num_phases)]
        num_layer_pattern = int(Winding_Para.num_layers/2)
        # ####Assume welding side are identical
        num_poles_pattern_repeat = int(Winding_Para.num_poles/2)-1
        
        for i in range(num_layer_pattern):
            uni_conn = [d_ini,1,0]
            uniform_connection = [uni_conn]
            uniform_layer_connection = [uni_conn,[d_ini,-1,ultp]]
            # Each q-wave must advance one lane. Cancel the Uniform offsets
            # accumulated within this wave before entering the next one.
            trans_layer_connection = [[
                d_ini, -1, -1 - num_poles_pattern_repeat * ultp]]
            jump_layer_connection = [[jld,1,jltp]]  
            # Connection += uniform_layer_connection * num_poles_pattern_repeat + uniform_connection + jump_layer_connection
            for j in range(Winding_Para.q):
                Connection += uniform_layer_connection * (num_poles_pattern_repeat)+ uniform_connection + trans_layer_connection
            Connection.pop()
            Connection += jump_layer_connection
        Connection.pop()
        
        if Winding_Para.ab == 1: ### if p2_divider == 1 which means the series connection between different wire sets is needed. 
            new_start_conductor_ids = []  ### A new_start_conductor_is needed, two or more wire path need to be combined to form a new branch.
            for i in range(Winding_Para.num_phases):    
                new_start_conductor_ids.append(start_conductor_ids[i]) ### so we rearrange the sci (start cond id) based on k

            start_conductor_id = start_conductor_ids[0]
            end_conductor_id1,group_cond_ids = get_branch_connections(start_conductor_id,Connection,Winding_Para,Layout_Para)
            end_conductor_id2,group_cond_ids = get_branch_connections(start_conductor_ids[Winding_Para.num_phases],Connection,Winding_Para,Layout_Para)
            
            # print('end_conductor_id2=',end_conductor_id)
            end_conn = [[d_ini,end_conductor_id2[1]-end_conductor_id1[1],end_conductor_id2[2]-end_conductor_id1[2]]]
            
            start_conductor_ids = new_start_conductor_ids  ## Update start cond ids 
            
            reverse_conn = reverse_connection(Connection)
            Connection += end_conn + reverse_conn
            # print('Connection',Connection)
            
    else:  # Legacy BWP-derived construction; validate UWP type before returning.
        used_bwp_fallback = True
        
        mode_name, q_divider, pp_divider, p2_divider, all_ab_list = classify_branch_mode(Winding_Para.ab, Winding_Para.q, Winding_Para.num_poles, 'BWP')
        # print (mode_name, q_divider, pp_divider, p2_divider,all_ab_list)
        
        ###1. Follow the pole divider pattern. 
        pp_per_branch = Winding_Para.num_poles // pp_divider ### pole regions per branch  
        num_phasors = Winding_Para.q*Winding_Para.num_phases ### Phasors per pole

        ##########Define the Start conductor IDs based on the parallel branches
        start_layer = 0 
        start_phasor = 0
        start_conductor_ids = []
        ### If Winding_Para.ab is the multiples of q, then we should determin the start cond ids
        if isinstance(Winding_Para.q,int):  ### If q is int
            phasor_range = Winding_Para.q*Winding_Para.num_phases
            for k in range(p2_divider):
                for n in range(pp_divider):
                    start_conductor_ids += [(i+n*pp_per_branch*num_phasors+k*num_phasors, start_layer, start_phasor+(i) % (Winding_Para.q)) for i in range(phasor_range)]
                    
        ##### After the correct defination of SCI We can then Define the Connections 
        Connection = []
        db_conductor_id = []
        d_ini = 1  #### Initial winding direction 
        num_layer_pattern = int(Winding_Para.num_layers/2)  ### Layer patterns 
        # ####Assume welding side are identical
        pltp_fl = TP_info.pltp_fl ## parallel layer trans position-first_layer
        pltp_ll = TP_info.pltp_ll  ## parallel layer trans position-last_layer
        ultp = TP_info.uni_tp  ## uniform layer trans position
        jltp = TP_info.jltp  ## uniform layer jump trans position
        
        num_poles_pattern_repeat = int(Winding_Para.num_poles/2/pp_divider)-1
     
        for i in range(num_layer_pattern):
            uni_conn = [d_ini,1,0]
            uniform_connection = [uni_conn]
            uniform_layer_connection = [uni_conn,[d_ini,-1,ultp]]
            jump_layer_connection = [[d_ini,1,jltp]]  
            Connection += uniform_layer_connection * num_poles_pattern_repeat + uniform_connection + jump_layer_connection
        Connection.pop()
        parallel_layer_connection = [[d_ini,0,pltp_ll]]
        Connection += parallel_layer_connection
        
        if p2_divider == 1:  ##### if p2_divider == 1 do the end layer connection
            for i in range(num_layer_pattern):
                uni_conn = [-d_ini,-1,0]
                uniform_connection = [uni_conn]
                uniform_layer_connection = [uni_conn,[-d_ini,1,ultp]]
                jump_layer_connection = [[-d_ini,-1,jltp]]  
                #parallel_layer_connection = [[1,0,pltp]]
                Connection += uniform_layer_connection * num_poles_pattern_repeat + uniform_connection + jump_layer_connection
        Connection.pop()
        
        if q_divider != Winding_Para.q: ### if q_divider != q, means the series connection between different wire sets is needed. 
            q_per_branch = Winding_Para.q//q_divider
            new_start_conductor_ids = []  ### A new_start_conductor_is needed, two or more wire path need to be combined to form a new branch.
            for i in range(int(len(start_conductor_ids)/q_per_branch)):    
                k = int(i * q_per_branch)  ### k is the interval index where the new start cond id located 
                new_start_conductor_ids.append(start_conductor_ids[k]) ### so we rearrange the sci (start cond id) based on k
            # print('start_conductor_ids',start_conductor_ids)
            # print ('Len_Connection',len(Connection))
            start_conductor_id = start_conductor_ids[0]
            start_conductor_ids = new_start_conductor_ids  ## Update start cond ids 
            New_Connection = []
            occupied_phasors = []
            left_phasors = list(range(q_per_branch))
            for n in range(q_per_branch-1):  ## loop to create the full connection for each of the small groups
                New_Connection += Connection
                # print('start_conductor_id'+str(n),start_conductor_id)
                occupied_phasors.append(start_conductor_id[2]) 
                left_phasors = left_phasors = [p for p in left_phasors if p not in occupied_phasors]
                end_conductor_id,group_cond_ids = get_branch_connections(start_conductor_id,Connection,Winding_Para,Layout_Para)
                # print('end_conductor_id'+str(n),end_conductor_id)
                phasor_change = None
                for shift in range(q_per_branch):
                    candidate = (end_conductor_id[2] + shift) % q_per_branch
                    if candidate in left_phasors:
                        phasor_change = shift
                        break
                if phasor_change is None:
                    raise ValueError(f"No valid phasor found for end_conductor_id {end_conductor_id[2]}")
                start_conductor_id,group_cond_ids = get_branch_connections(end_conductor_id,[[-d_ini,0,-phasor_change]],Winding_Para,Layout_Para)
                New_Connection += [[-d_ini,0,-phasor_change]]
            New_Connection += Connection
            Connection = New_Connection
        
    rotate_sequence_for_weld_inlet = False
    if Layout_Para.inlet_from_weld_side == 1:
        Connection, start_conductor_ids, rotate_sequence_for_weld_inlet = shift_inlet_to_weld_side_or_rotate_later(
            Connection,
            start_conductor_ids,
            Winding_Para,
            Layout_Para,
        )
        

    # UWP's q-wave series transitions are part of the winding scaffold, not
    # optional Regular offsets. Times/Interval must retain unselected ones.
    Connection = TP_modi(TP_info, Connection, preserve_offsets=True)
    len_conn = len(Connection)
    # print('len_conn = ', len_conn)
    num_cond_in_branch = int(Winding_Para.num_poles * Winding_Para.num_layers * Winding_Para.q / Winding_Para.ab)
    if len_conn != num_cond_in_branch-1:
        pass  # Checked by _validate_generated_layout_consistency after dispatch.

    db_conductor_id = get_db_cond_id_from_connection(start_conductor_ids,Connection,Winding_Para, Layout_Para)
    if rotate_sequence_for_weld_inlet:
        start_conductor_ids, db_conductor_id = rotate_db_conductor_ids_to_weld_inlet(db_conductor_id)
    if used_bwp_fallback:
        validate_pp_only_uwp(db_conductor_id, Winding_Para, Layout_Para,
                             label='UWP BWP fallback')
    if ((q_divider, pp_divider, p2_divider) == (1, 1, 2)
            and not rotate_sequence_for_weld_inlet
            and Fraction(str(Winding_Para.q)).denominator == 1):
        # Preserve the constructor's directed travel across a long circular
        # arc. Endpoint-only shortest-arc inference can reverse its meaning.
        travel = {}
        slots = Winding_Para.num_slots
        shifts = Layout_Para.phase_shift_list
        for branch_id, path in db_conductor_id:
            if len(path) != len(Connection) + 1:
                raise ValueError('UWP P2 source has incomplete connections.')
            steps = []
            for conn, start, end in zip(Connection, path, path[1:]):
                direction, layer_step, _ptp = conn
                logical_end_layer = start[1] + layer_step
                step = (direction * int(Winding_Para.q * Winding_Para.num_phases)
                        + end[2] - start[2]
                        + shifts[logical_end_layer] - shifts[start[1]])
                if (not step or (start[0] + step - end[0]) % slots):
                    raise ValueError('UWP P2 signed travel misses its endpoint.')
                steps.append(int(step))
            travel[branch_id] = tuple(steps)
        db_conductor_id = _CandidateBranches(db_conductor_id)
        db_conductor_id.signed_travel = travel
    
    return start_conductor_ids, db_conductor_id

def pattern_SSP(TP_info,Winding_Para,Layout_Para):
    mode_name, q_divider, pp_divider, p2_divider, all_ab_list = classify_branch_mode(Winding_Para.ab, Winding_Para.q, Winding_Para.num_poles, 'SSP')
    q_divider, pp_divider, p2_divider = branch_dividers_for_pattern('SSP', Winding_Para)
    # print (mode_name, q_divider, pp_divider, p2_divider,all_ab_list)
    
    ###1. Follow the pole divider pattern. 
    pp_per_branch = Winding_Para.num_poles // pp_divider ### pole regions per branch  
    num_phasors = Winding_Para.q*Winding_Para.num_phases ### Phasors per pole
    
    ##########Define the Start conductor IDs based on the parallel branches
    start_layer = 0 
    start_phasor = 0
    start_conductor_ids = []
    ### If Winding_Para.ab is the multiples of q, then we should determin the start cond ids
    if isinstance(Winding_Para.q,int):  ### If q is int
        phasor_range = Winding_Para.q*Winding_Para.num_phases
        for k in range(p2_divider):
            for n in range(pp_divider):
                start_conductor_ids += [(i+n*pp_per_branch*num_phasors+k*num_phasors, start_layer, start_phasor+(i) % (Winding_Para.q)) for i in range(phasor_range)]
    # print('start_conductor_ids',start_conductor_ids)
    
    ##### After the correct defination of SCI We can then Define the Connections 
    Connection = []
    db_conductor_id = []
    d_ini = 1  #### Initial winding direction 
    num_layer_pattern = int(Winding_Para.num_layers/2)  ### Layer patterns 
    num_pp_pattern = int(Winding_Para.num_poles/2/pp_divider)
    
    # ####Assume welding side are identical
    pltp_fl = TP_info.pltp_fl ## parallel layer trans position-first_layer
    pltp_ll = TP_info.pltp_ll  ## parallel layer trans position-last_layer
    ultp = TP_info.uni_tp  ## uniform layer trans position
    jltp = TP_info.jltp  ## uniform layer jump trans position

    if Winding_Para.num_layers % 2 == 0: ## even layer condition
        num_layer_pattern_repeat = num_layer_pattern-1 
        # print('num_layer_pattern_repeat',num_layer_pattern_repeat)
        # print('num_layer_pattern',num_layer_pattern)
        for i in range(num_pp_pattern):
            uni_conn = [d_ini,1,0]  #### Welding side uni connection
            uniform_connection = [uni_conn]
            uni_layer_connection = [uni_conn,[d_ini,1,ultp]]
            parallel_layer_connection = [[d_ini,0,pltp_ll]]  
            Connection += uni_layer_connection * num_layer_pattern_repeat + uniform_connection +  parallel_layer_connection
            #### Finish the forward winding to the bottom layer
            if p2_divider < 2:  ### need to do the reverse winding to the first layer if p2_divider < 2
                uni_conn = [-d_ini,-1,0] #### Welding side uni connection
                uniform_connection = [uni_conn]
                uni_layer_connection = [uni_conn,[-d_ini,-1,ultp]]
                parallel_layer_connection = [[d_ini,0,pltp_fl]]
                Connection += uni_layer_connection * num_layer_pattern_repeat + uniform_connection +  parallel_layer_connection
        
   
    if Winding_Para.num_layers % 2 == 1:  #### If odd layers
        num_layer_pattern_repeat = int(Winding_Para.num_layers/2)
        for i in range(num_pp_pattern):
            uni_conn = [d_ini,1,0]  #### Welding side uni connection
            uniform_connection = [uni_conn]
            uni_layer_connection = [uni_conn,[d_ini,1,ultp]]
            parallel_layer_connection = [[d_ini,0,pltp_ll]]  
            Connection += uni_layer_connection * num_layer_pattern_repeat + parallel_layer_connection 
            if p2_divider < 2:
                uni_conn = [-d_ini,-1,0] #### Welding side uni connection
                uniform_connection = [uni_conn]
                uni_layer_connection = [uni_conn,[-d_ini,-1,ultp]]
                parallel_layer_connection = [[d_ini,0,pltp_fl]]
                Connection += uni_layer_connection * num_layer_pattern_repeat + parallel_layer_connection
                
    Connection.pop()          
    
    if q_divider != Winding_Para.q: ### if q_divider != q, means the series connection between different wire sets is needed. 
        q_per_branch = Winding_Para.q//q_divider
        new_start_conductor_ids = []  ### A new_start_conductor_is needed, two or more wire path need to be combined to form a new branch.
        for i in range(int(len(start_conductor_ids)/q_per_branch)):    
            k = int(i * q_per_branch)  ### k is the interval index where the new start cond id located 
            new_start_conductor_ids.append(start_conductor_ids[k]) ### so we rearrange the sci (start cond id) based on k
        # print('start_conductor_ids',new_start_conductor_ids)
        # print ('Len_Connection',len(Connection))
        start_conductor_id = start_conductor_ids[0]
        start_conductor_ids = new_start_conductor_ids  ## Update start cond ids 
        New_Connection = []
        occupied_phasors = []
        left_phasors = list(range(q_per_branch))
        for n in range(q_per_branch-1):  ## loop to create the full connection for each of the small groups
            New_Connection += Connection
            # print('start_conductor_id'+str(n),start_conductor_id)
            occupied_phasors.append(start_conductor_id[2]) 
            left_phasors = left_phasors = [p for p in left_phasors if p not in occupied_phasors]
            # print('left_phasors',left_phasors)
            end_conductor_id,group_cond_ids = get_branch_connections(start_conductor_id,Connection,Winding_Para,Layout_Para)
            # print('end_conductor_id'+str(n),end_conductor_id)
            phasor_change = None
            for shift in range(q_per_branch):
                candidate = (end_conductor_id[2] + shift) % q_per_branch
                if candidate in left_phasors:
                    phasor_change = shift
                    break
            if phasor_change is None:
                raise ValueError(f"No valid phasor found for end_conductor_id {end_conductor_id[2]}")
            start_conductor_id,group_cond_ids = get_branch_connections(end_conductor_id,[[-d_ini,0,-phasor_change]],Winding_Para,Layout_Para)
            New_Connection += [[d_ini,0,phasor_change]]
        New_Connection += Connection
        Connection = New_Connection

    
    rotate_sequence_for_weld_inlet = False
    if Layout_Para.inlet_from_weld_side == 1:
        Connection, start_conductor_ids, rotate_sequence_for_weld_inlet = shift_inlet_to_weld_side_or_rotate_later(
            Connection,
            start_conductor_ids,
            Winding_Para,
            Layout_Para,
        )
        
    Connection = TP_modi(TP_info,Connection)
    len_conn = len(Connection)
    num_cond_in_branch = int(Winding_Para.num_poles * Winding_Para.num_layers * Winding_Para.q / Winding_Para.ab)
    if len_conn != num_cond_in_branch-1:
        pass  # Checked by _validate_generated_layout_consistency after dispatch.
        
    db_conductor_id = get_db_cond_id_from_connection(start_conductor_ids,Connection,Winding_Para, Layout_Para)
    if rotate_sequence_for_weld_inlet:
        start_conductor_ids, db_conductor_id = rotate_db_conductor_ids_to_weld_inlet(db_conductor_id)
    
    return (start_conductor_ids, db_conductor_id)
    
def pattern_SLP(TP_info,Winding_Para,Layout_Para):
    mode_name, q_divider, pp_divider, p2_divider, all_ab_list = classify_branch_mode(Winding_Para.ab, Winding_Para.q, Winding_Para.num_poles, 'SLP')
    q_divider, pp_divider, p2_divider = branch_dividers_for_pattern('SLP', Winding_Para)
    # print (mode_name, q_divider, pp_divider, p2_divider,all_ab_list)
    
    ###1. Follow the pole divider pattern. 
    pp_per_branch = Winding_Para.num_poles // pp_divider ### pole regions per branch  
    num_phasors = Winding_Para.q*Winding_Para.num_phases ### Phasors per pole
    
    ##########Define the Start conductor IDs based on the parallel branches
    start_layer = 0 
    start_phasor = 0
    start_conductor_ids = []
    ### If Winding_Para.ab is the multiples of q, then we should determin the start cond ids
    if isinstance(Winding_Para.q,int):  ### If q is int
        phasor_range = Winding_Para.q*Winding_Para.num_phases
        for k in range(p2_divider):
            for n in range(pp_divider):
                start_conductor_ids += [(i+n*pp_per_branch*num_phasors+k*num_phasors, start_layer, start_phasor+(i) % (Winding_Para.q)) for i in range(phasor_range)]
    # print('start_conductor_ids',start_conductor_ids)
                
    ##### After the correct defination of SCI We can then Define the Connections 
    Connection = []
    db_conductor_id = []
    d_ini = 1  #### Initial winding direction 
    num_layer_pattern = int(Winding_Para.num_layers/2)  ### Layer patterns 
    num_pp_pattern = int(Winding_Para.num_poles/2/pp_divider)
    
    # ####Assume welding side are identical
    pltp_fl = TP_info.pltp_fl ## parallel layer trans position-first_layer
    pltp_ll = TP_info.pltp_ll  ## parallel layer trans position-last_layer
    ultp = TP_info.uni_tp  ## uniform layer trans position
    jltp = TP_info.jltp  ## uniform layer jump trans position
    num_layer_pattern_repeat = (num_layer_pattern if Winding_Para.num_layers % 2
                                else num_layer_pattern - 1)
    
    for i in range(num_pp_pattern):
        uni_conn = [d_ini,1,0]  #### Welding side uni connection
        uniform_connection = [uni_conn]
        uni_layer_connection = [uni_conn,[-d_ini,1,ultp]]
        parallel_layer_connection = [[-d_ini,0,pltp_ll]]  
        if Winding_Para.num_layers % 2 == 0:
            Connection += uni_layer_connection * num_layer_pattern_repeat + uniform_connection  + parallel_layer_connection
        if Winding_Para.num_layers % 2 == 1:
            parallel_layer_connection = [[d_ini,0,pltp_ll]] 
            Connection += uni_layer_connection * num_layer_pattern_repeat + parallel_layer_connection
        #### Finish the forward winding to the bottom layer
        
        if p2_divider < 2: ### need to do the reverse winding to the first layer if p2_divider < 2
            uni_conn = [-d_ini,-1,0] #### Welding side uni connection
            uniform_connection = [uni_conn]
            uni_layer_connection = [uni_conn,[d_ini,-1,ultp]]
            parallel_layer_connection = [[-d_ini,0,pltp_fl]]
            if Winding_Para.num_layers % 2 == 0:
                Connection += uni_layer_connection * num_layer_pattern_repeat + uniform_connection +  parallel_layer_connection
            if Winding_Para.num_layers % 2 == 1:
                parallel_layer_connection = [[d_ini,0,pltp_fl]]
                Connection += uni_layer_connection * num_layer_pattern_repeat  + parallel_layer_connection
    
    Connection.pop()     #### Important!!! 
    
    if q_divider != Winding_Para.q: ### if q_divider != q, means the series connection between different wire sets is needed. 
        q_per_branch = Winding_Para.q//q_divider
        new_start_conductor_ids = []  ### A new_start_conductor_is needed, two or more wire path need to be combined to form a new branch.
        for i in range(int(len(start_conductor_ids)/q_per_branch)):    
            k = int(i * q_per_branch)  ### k is the interval index where the new start cond id located 
            new_start_conductor_ids.append(start_conductor_ids[k]) ### so we rearrange the sci (start cond id) based on k
        # print('start_conductor_ids',new_start_conductor_ids)
        # print ('Len_Connection',len(Connection))
        start_conductor_id = start_conductor_ids[0]
        start_conductor_ids = new_start_conductor_ids  ## Update start cond ids 
        New_Connection = []
        occupied_phasors = []
        left_phasors = list(range(q_per_branch))
        for n in range(q_per_branch-1):  ## loop to create the full connection for each of the small groups
            New_Connection += Connection
            # print('start_conductor_id'+str(n),start_conductor_id)
            occupied_phasors.append(start_conductor_id[2]) 
            left_phasors = left_phasors = [p for p in left_phasors if p not in occupied_phasors]
            # print('left_phasors',left_phasors)
            end_conductor_id,group_cond_ids = get_branch_connections(start_conductor_id,Connection,Winding_Para,Layout_Para)
            # print('end_conductor_id'+str(n),end_conductor_id)
            phasor_change = None
            for shift in range(q_per_branch):
                candidate = (end_conductor_id[2] + shift) % q_per_branch
                if candidate in left_phasors:
                    phasor_change = shift
                    break
            if phasor_change is None:
                raise ValueError(f"No valid phasor found for end_conductor_id {end_conductor_id[2]}")
            start_conductor_id,group_cond_ids = get_branch_connections(end_conductor_id,[[-d_ini,0,-phasor_change]],Winding_Para,Layout_Para)
            New_Connection += [[d_ini,0,phasor_change]]
        New_Connection += Connection
        Connection = New_Connection
        
    rotate_sequence_for_weld_inlet = False
    if Layout_Para.inlet_from_weld_side == 1:
        Connection, start_conductor_ids, rotate_sequence_for_weld_inlet = shift_inlet_to_weld_side_or_rotate_later(
            Connection,
            start_conductor_ids,
            Winding_Para,
            Layout_Para,
        )
    
    
    Connection = TP_modi(TP_info,Connection)
    len_conn = len(Connection)
    num_cond_in_branch = int(Winding_Para.num_poles * Winding_Para.num_layers * Winding_Para.q / Winding_Para.ab)
    if len_conn != num_cond_in_branch-1:
        pass  # Checked by _validate_generated_layout_consistency after dispatch.
    
    db_conductor_id = get_db_cond_id_from_connection(start_conductor_ids,Connection,Winding_Para, Layout_Para)
    if rotate_sequence_for_weld_inlet:
        start_conductor_ids, db_conductor_id = rotate_db_conductor_ids_to_weld_inlet(db_conductor_id)
    
    return (start_conductor_ids, db_conductor_id)


def _slp_pp_p2_sector_from_reference(TP_info, Winding_Para, Layout_Para):
    """Join complete sector paths in the SLP lap order for each branch."""
    source_values = (vars(Winding_Para) if hasattr(Winding_Para, '__dict__')
                     else Winding_Para._asdict())
    source_winding = SimpleNamespace(**deepcopy(source_values))
    source_winding.ab = 1
    source_winding.branch_dividers = (1, 1, 1)
    _, source_database = pattern_SLP(TP_info, source_winding, Layout_Para)
    slots = Winding_Para.num_slots
    layers = Winding_Para.num_layers
    q = Winding_Para.q
    pole_pairs = Winding_Para.num_poles // 2
    pp_divider = branch_dividers_for_pattern('SLP', Winding_Para)[1]
    sectors_per_branch = pole_pairs // pp_divider // 2
    if (sectors_per_branch < 1 or
            pole_pairs % (2 * pp_divider)):
        raise ValueError('SLP PP+P2 requires an even sector count per branch.')
    tau = Winding_Para.num_phases * q
    sector_order = (*range(0, pole_pairs, 2),
                    *range(pole_pairs - 1, 0, -2))
    database = []
    for _, source_path in source_database:
        sector_paths = []
        passes = [source_path[index:index + layers]
                  for index in range(0, len(source_path), layers)]
        if len(passes) != 2 * pole_pairs * q:
            raise ValueError('SLP reference cannot separate complete lap passes.')
        by_start = {(part[0][0], part[0][1]): part for part in passes}
        anchor = source_path[0][0]
        for sector in sector_order:
            sector_anchor = (anchor - 2 * sector * tau) % slots
            ordered_passes = []
            for lane in range(q):
                layer = 0 if lane % 2 == 0 else layers - 1
                key = ((sector_anchor + lane) % slots, layer)
                if key not in by_start:
                    raise ValueError('SLP reference is missing a sector lap pass.')
                ordered_passes.append(by_start[key])
            for lane in range(q - 1, -1, -1):
                layer = layers - 1 if lane % 2 == 0 else 0
                key = ((sector_anchor + lane) % slots, layer)
                if key not in by_start:
                    raise ValueError('SLP reference is missing a sector return pass.')
                ordered_passes.append(by_start[key])
            if sector % 2:
                ordered_passes.reverse()
            ordered = [node for part in ordered_passes for node in part]
            sector_paths.append(ordered)
        for first in range(0, len(sector_paths), sectors_per_branch):
            path = [node for sector_path in sector_paths[
                first:first + sectors_per_branch] for node in sector_path]
            database.append([len(database) + 1, path])
    return [path[0] for _, path in database], database


def _slp_pair_lane_p2_from_reference(TP_info, Winding_Para, Layout_Para):
    """Join complementary lap passes from each pair of q lanes.

    The selected full pp-divider leaves two passes per branch.  A forward
    pass from one lane joins a return pass in its paired lane; the remaining
    passes form the opposite boundary-layer cohort. Their same-layer joins
    must travel in the lap-return direction, without a numeric pitch gate.
    """
    source_values = (vars(Winding_Para) if hasattr(Winding_Para, '__dict__')
                     else Winding_Para._asdict())
    source_winding = SimpleNamespace(**deepcopy(source_values))
    source_winding.ab = 1
    source_winding.branch_dividers = (1, 1, 1)
    _, source_database = pattern_SLP(TP_info, source_winding, Layout_Para)
    records = {(slot, layer): (phase, sign)
               for slot, layer, phase, sign in phase_map(
                   Winding_Para.num_slots, Winding_Para.num_poles,
                   Winding_Para.num_layers, Layout_Para.phase_shift_list,
                   Winding_Para.num_phases)}
    slots = Winding_Para.num_slots
    layers = Winding_Para.num_layers
    pp = Winding_Para.num_poles // 2
    q = Winding_Para.q
    database = []

    def join(first, second):
        if (first[-1][1] != second[0][1]
                or not any(step < 0 for step in circular_travel_steps(
                    first[-1][0], second[0][0], slots))):
            return None
        raw = first + second
        for path in (raw, list(reversed(raw))):
            first_phase, first_sign = records[path[0][:2]]
            last_phase, last_sign = records[path[-1][:2]]
            if (first_phase == last_phase and (first_sign, last_sign) == (1, -1)
                    and not _slp_factor_edge_error(path, Winding_Para, Layout_Para)
                    and all(records[node[:2]][1] == (-1) ** index
                            for index, node in enumerate(path))):
                return path
        return None

    for _, source_path in source_database:
        lane_length = 2 * pp * layers
        if len(source_path) != q * lane_length:
            raise ValueError('SLP reference cannot separate paired q lanes.')
        cohorts = ([], [])
        for pair_index in range(q // 2):
            first_lane = source_path[
                2 * pair_index * lane_length:(2 * pair_index + 1) * lane_length]
            second_lane = source_path[
                (2 * pair_index + 1) * lane_length:(2 * pair_index + 2) * lane_length]
            first_passes = [first_lane[i:i + layers]
                            for i in range(0, lane_length, layers)]
            second_passes = [second_lane[i:i + layers]
                             for i in range(0, lane_length, layers)]
            for cohort, initial, matching in (
                    (0, first_passes[::2], second_passes[1::2]),
                    (1, first_passes[1::2], second_passes[::2])):
                available = list(matching)
                for first in initial:
                    candidates = [(index, joined)
                                  for index, second in enumerate(available)
                                  if (joined := join(first, second)) is not None]
                    if len(candidates) != 1:
                        raise ValueError('SLP paired lanes lack a unique legal return.')
                    index, path = candidates[0]
                    available.pop(index)
                    cohorts[cohort].append(path)
                if available:
                    raise ValueError('SLP paired-lane return leaves unused passes.')
        for cohort, paths in enumerate(cohorts):
            origin = min(path[0][0] for path in paths)
            paths.sort(key=lambda path: ((path[0][0] - origin) % slots
                                         if cohort == 0 else
                                         (origin - path[0][0]) % slots))
            for path in paths:
                database.append([len(database) + 1, path])
    return [path[0] for _, path in database], database


def _slp_full_q_p2_from_reference(TP_info, Winding_Para, Layout_Para):
    """Partition each q lane into alternating forward/reflected pole sectors."""
    source_values = (vars(Winding_Para) if hasattr(Winding_Para, '__dict__')
                     else Winding_Para._asdict())
    source_winding = SimpleNamespace(**deepcopy(source_values))
    source_winding.ab = 1
    source_winding.branch_dividers = (1, 1, 1)
    _, source_database = pattern_SLP(TP_info, source_winding, Layout_Para)
    phases = {(slot, layer): (phase, sign)
              for slot, layer, phase, sign in phase_map(
                  Winding_Para.num_slots, Winding_Para.num_poles,
                  Winding_Para.num_layers, Layout_Para.phase_shift_list,
                  Winding_Para.num_phases)}
    q = Winding_Para.q
    layers = Winding_Para.num_layers
    pp = Winding_Para.num_poles // 2
    divider = branch_dividers_for_pattern('SLP', Winding_Para)[1]
    passes_per_branch = pp // divider
    groups_per_lane = 2 * divider
    database = []
    for _, source_path in source_database:
        lane_length = 2 * pp * layers
        if len(source_path) != q * lane_length:
            raise ValueError('SLP reference cannot separate complete q lanes.')
        lane_groups = []
        for lane in range(q):
            lane_path = source_path[lane * lane_length:(lane + 1) * lane_length]
            passes = [lane_path[index:index + layers]
                      for index in range(0, lane_length, layers)]
            candidates = []
            for rotation in range(len(passes)):
                rotated = passes[rotation:] + passes[:rotation]
                groups = []
                for group_index in range(groups_per_lane):
                    section = rotated[
                        group_index * passes_per_branch:
                        (group_index + 1) * passes_per_branch]
                    if group_index % 2:
                        section = list(reversed(section))
                    raw = [node for part in section for node in part]
                    options = (raw, list(reversed(raw)))
                    valid = []
                    for reversed_path, path in enumerate(options):
                        first_phase, first_sign = phases[path[0][:2]]
                        last_phase, last_sign = phases[path[-1][:2]]
                        if ((first_phase, first_sign) != (last_phase, 1)
                                or last_sign != -1
                                or _slp_factor_edge_error(
                                    path, Winding_Para, Layout_Para)):
                            continue
                        signs = [phases[node[:2]][1] for node in path]
                        if all(sign == (-1) ** index
                               for index, sign in enumerate(signs)):
                            valid.append((reversed_path, path))
                    if not valid:
                        break
                    groups.append(min(valid, key=lambda item: item[0])[1])
                if len(groups) == groups_per_lane:
                    candidates.append((groups[0][0][0], rotation, groups))
            if not candidates:
                raise ValueError('SLP full-Q lane has no legal P2 sector partition.')
            lane_groups.append(min(candidates, key=lambda item: item[:2])[2])
        for group_index in (*range(0, groups_per_lane, 2),
                            *range(groups_per_lane - 1, 0, -2)):
            for groups in lane_groups:
                database.append([len(database) + 1, groups[group_index]])
    return [path[0] for _, path in database], database


def _slp_q_pp_p2_parent_cut_from_full_q(TP_info, Winding_Para, Layout_Para):
    """Build proper-Q P2 children from a public full-Q P2 parent."""
    source_values = (vars(Winding_Para) if hasattr(Winding_Para, '__dict__')
                     else Winding_Para._asdict())
    source_winding = SimpleNamespace(**deepcopy(source_values))
    source_winding.ab = 2 * Winding_Para.q
    source_winding.branch_dividers = (Winding_Para.q, 1, 2)
    _, source = get_winding_layout(
        'SLP', TP_info, source_winding, Layout_Para)
    children = slp_q_pp_p2_lane_regroup(
        source, dividers=branch_dividers_for_pattern('SLP', Winding_Para),
        q=Winding_Para.q, pp=Winding_Para.num_poles // 2,
        layer_count=Winding_Para.num_layers)
    database = _CandidateBranches()
    for child in children:
        database.append([len(database) + 1, child.path])
    starts = [path[0] for _, path in database]
    validate_slp_q_pp_p2_parent_cut(database, Winding_Para, Layout_Para)
    return starts, database


def _slp_p2_from_reference(TP_info, Winding_Para, Layout_Para):
    """Split each no-divider SLP phase path and rotate whole lap passes.

    A P2-only branch takes half of its phase's ordered reference passes.  A
    cyclic pass rotation moves the inlet to an N region without changing any
    conductor or the alternating weld/insert edge parity.  The second half
    prefers a last-layer inlet, as in the completed manual construction.
    """
    source_values = (vars(Winding_Para) if hasattr(Winding_Para, '__dict__')
                     else Winding_Para._asdict())
    source_winding = SimpleNamespace(**deepcopy(source_values))
    source_winding.ab = 1
    source_winding.branch_dividers = (1, 1, 1)
    _, source_database = pattern_SLP(TP_info, source_winding, Layout_Para)
    pole_sign = {(slot, layer): (phase, sign)
                 for slot, layer, phase, sign in phase_map(
                     Winding_Para.num_slots, Winding_Para.num_poles,
                     Winding_Para.num_layers, Layout_Para.phase_shift_list,
                     Winding_Para.num_phases)}
    layers = Winding_Para.num_layers
    database = []
    for _, source_path in source_database:
        if len(source_path) % (2 * layers):
            raise ValueError('SLP reference cannot split into two complete lap-pass groups.')
        branch_length = len(source_path) // 2
        for half in range(2):
            chunk = source_path[half * branch_length:(half + 1) * branch_length]
            passes = [chunk[index:index + layers]
                      for index in range(0, len(chunk), layers)]
            candidates = []
            for rotation in range(len(passes)):
                ordered = passes[rotation:] + passes[:rotation]
                rotated = [node for part in ordered for node in part]
                for reversed_path in (False, True):
                    path = list(reversed(rotated)) if reversed_path else rotated
                    inlet_phase, inlet_sign = pole_sign[path[0][:2]]
                    outlet_phase, outlet_sign = pole_sign[path[-1][:2]]
                    if (inlet_phase != outlet_phase
                            or (inlet_sign, outlet_sign) != (1, -1)
                            or _slp_factor_edge_error(path, Winding_Para, Layout_Para)):
                        continue
                    signs = [pole_sign[node[:2]][1] for node in path]
                    if any(sign != (-1) ** index for index, sign in enumerate(signs)):
                        continue
                    preferred_layer = 0 if half == 0 else layers - 1
                    candidates.append((reversed_path,
                                       path[0][1] != preferred_layer,
                                       path[0][0], rotation, path))
            if not candidates:
                raise ValueError('SLP P2 reference half has no legal N-to-S pass rotation.')
            path = min(candidates, key=lambda item: item[:4])[4]
            database.append([len(database) + 1, path])
    return [path[0] for _, path in database], database


def _slp_pp_from_reference(TP_info, Winding_Para, Layout_Para):
    """Split an SLP reference into circumferential PP-divider copies.

    The no-divider SLP supplies one complete phase path made of pole-pair
    blocks.  Branch zero keeps equally spaced pole-pair sectors, alternates the
    q-lane order between sectors, and every later branch is an exact rotation
    by ``slots / pp_divider``.  This is the factor rule; no q, pole, layer, or
    branch identifier is special-cased.
    """
    q_divider, pp_divider, p2_divider = branch_dividers_for_pattern(
        'SLP', Winding_Para)
    if q_divider != 1 or pp_divider <= 1 or p2_divider != 1:
        raise ValueError('SLP learned PP construction requires (1, pp-divider, 1).')

    source_values = (vars(Winding_Para) if hasattr(Winding_Para, '__dict__')
                     else Winding_Para._asdict())
    source_winding = SimpleNamespace(**deepcopy(source_values))
    source_winding.ab = 1
    source_winding.branch_dividers = (1, 1, 1)
    _, source_database = pattern_SLP(
        TP_info, source_winding, Layout_Para)

    q = int(Winding_Para.q)
    slots = int(Winding_Para.num_slots)
    layers = int(Winding_Para.num_layers)
    pole_pairs = int(Winding_Para.num_poles) // 2
    pole_pitch = int(Winding_Para.num_phases) * q
    sectors_per_branch = pole_pairs // pp_divider
    branch_shift = slots // pp_divider
    block_size = 2 * layers
    base_phase_paths = []

    for _source_id, source_path in source_database:
        if len(source_path) % block_size:
            raise ValueError('SLP reference cannot be divided into pole-pair blocks.')
        blocks = [source_path[index:index + block_size]
                  for index in range(0, len(source_path), block_size)]
        blocks_by_start = {
            (block[0][0], block[0][1]): block
            for block in blocks
        }
        start_slot, start_layer = source_path[0][:2]
        base_path = []
        for sector in range(sectors_per_branch):
            anchor = (start_slot - 2 * sector * pole_pitch) % slots
            lanes = (range(q) if sector % 2 == 0
                     else range(q - 1, -1, -1))
            for lane in lanes:
                key = ((anchor + lane) % slots, start_layer)
                if key not in blocks_by_start:
                    raise ValueError(
                        'SLP reference is missing a required pole-pair block.')
                base_path.extend(blocks_by_start[key])
        base_phase_paths.append(base_path)

    database = []
    for branch_index in range(pp_divider):
        offset = branch_index * branch_shift
        for base_path in base_phase_paths:
            path = [((node[0] + offset) % slots, node[1], *node[2:])
                    for node in base_path]
            database.append([len(database) + 1, path])
    return [path[0] for _, path in database], database


def pattern_TSP(TP_info,Winding_Para,Layout_Para):
    pltp_ll = TP_info.pltp_ll  ## parallel layer transposition, used for top-bottom layer
    p2_divider = 2
    mode_name, q_divider, pp_divider,p2_divider, all_ab_list = classify_branch_mode(Winding_Para.ab, Winding_Para.q, Winding_Para.num_poles, 'TSP')
    # print (mode_name, q_divider, pp_divider,p2_divider, all_ab_list)
    if  pp_divider > 1:
        _raise_pattern_error(
            "pattern_specific_infeasible",
            "TSP does not support pole-pair division for the selected number of parallel branches.",
            "TSP",
        )
    ###1. Follow the pole divider pattern. 
    pp_per_branch = Winding_Para.num_poles // pp_divider ### pole regions per branch  
    num_phasors = Winding_Para.q*Winding_Para.num_phases ### Phasors per pole
    
    ##########Define the Start conductor IDs based on the parallel branches
    start_layer = 0 
    start_phasor = 0
    start_conductor_ids = []
    ### If Winding_Para.ab is the multiples of q, then we should determin the start cond ids
    if isinstance(Winding_Para.q,int):  ### If q is int
        phasor_range = q_divider*Winding_Para.num_phases
        phasor_interval = int(Winding_Para.q/q_divider)
        for k in range(p2_divider):
            for n in range(pp_divider):
                start_conductor_ids += [(phasor_interval*i+n*pp_per_branch*num_phasors+k*num_phasors, start_layer, start_phasor+(phasor_interval*i) % (Winding_Para.q)) for i in range(phasor_range)]
    
    # if Winding_Para.ab == 2:
    #     start_conductor_ids = [(i*Winding_Para.q,0,0) for i in range(Winding_Para.num_phases*2)]
        
    num_layers = Winding_Para.num_layers
    num_cond_in_branch = int(Winding_Para.num_poles * Winding_Para.num_layers * Winding_Para.q / Winding_Para.ab) ### Check how many conductors per branch 
    num_pattern = int(num_cond_in_branch / num_layers)  ### num_patterns is how many sprial patterns needed for one branch. the end pole_region_index is calculated as:
    
    Connection = []
    num_wireset = int(pp_divider * p2_divider)
 
    # ---- Define the Connections scaffold ----
    
    ####Assume welding side are identical
    ultp = TP_info.uni_tp  ## uniform layer trans position
    
    pole_count = 0
    cond_count = 0
    phasor_change = 0 if q_divider == 1 else pltp_ll
    pole_taken = [n*i for i in range(p2_divider)]
    
    # How many times we repeat the uniform layer connection pattern per pole
    if Winding_Para.num_layers % 2 == 0:
        num_layer_pattern_repeat = int(Winding_Para.num_layers/2)-1 
    else:
        num_layer_pattern_repeat = int(Winding_Para.num_layers/2)

    ##### Generate the connections
    d_slot = 1
    d_layer = 1 
    
    for i in range(num_pattern):
        # Repeating intra-pole connections (uniform welding-side connections)
        uni_conn = [d_slot, d_layer, 0]             # Welding side, no phasor change
        uniform_connection = [uni_conn]             # Uniform weld connection
        uni_layer_connection = [uni_conn, [d_slot, d_layer, ultp]]

        Connection += uni_layer_connection * num_layer_pattern_repeat
        if Winding_Para.num_layers % 2 == 0:
            Connection += uniform_connection
        
        # We just added (num_layers - 1) "internal" transitions and we are now at the bottom layer 
        pole_count += num_layers - 1
        cond_count += num_layers - 1
        
        if cond_count < num_cond_in_branch - 1:  ### If branch not finished yet, topbottom connection would be needed
            current_pole_regions = [(i + pole_count) % Winding_Para.num_poles for i in range(num_wireset)]
            next_pole_regions = [(i + pole_count + 1) % Winding_Para.num_poles for i in range(num_wireset)]
            last_pole_regions = [(i + pole_count - 1) % Winding_Para.num_poles for i in range(num_wireset)]
            next_pole_feasible = 1
            last_pole_feasible = 1
            for region in next_pole_regions:
                if region in pole_taken:
                    next_pole_feasible = 0
            for region in last_pole_regions:
                if region in pole_taken:
                    last_pole_feasible = 0
            if next_pole_feasible == 1 and last_pole_feasible == 1:  ### Both feasible
                d_fec = TP_info.jld 
            elif next_pole_feasible == 1 and last_pole_feasible == 0: ### Next region feasible
                d_fec = 1 
            elif next_pole_feasible == 0 and last_pole_feasible == 1: ### Last region feasible
                d_fec = -1 
            else:
                break
            pole_count += d_fec
            pole_taken += [region+d_fec for region in current_pole_regions]
            jump_layer = -num_layers+1
            first_end_connection = [[d_fec,jump_layer,phasor_change]] 
            phasor_change = 0 if q_divider == 1 else pltp_ll
            Connection += first_end_connection
  
    Total_Connection = Connection
    
    if Winding_Para.ab == 2: 
        for k in range(Winding_Para.q-1):
            d_fec = TP_info.jld
            phasor_change = 1 if Winding_Para.q % 2 ==0 else -1
            jump_layer = -num_layers+1
            first_end_connection = [[d_fec,jump_layer,phasor_change]]
            Total_Connection += first_end_connection
            Total_Connection += Total_Connection
            Total_Connection.pop()
            
          
    if Layout_Para.inlet_from_weld_side == 1:
        Total_Connection, start_conductor_ids = shift_inlet_to_weld_side(
            Total_Connection,
            start_conductor_ids,
            Winding_Para,
            Layout_Para,
        )
        
    Total_Connection = TP_modi(TP_info,Total_Connection)
    

    db_conductor_id = get_db_cond_id_from_connection(start_conductor_ids,Total_Connection,Winding_Para, Layout_Para)
    
    return (start_conductor_ids, db_conductor_id)           


def pattern_ZLP(TP_info,Winding_Para,Layout_Para):
    #### ZLP is the Z-shape lap pattern, mainly using adjacent-layer lap pins.
    mode_name, q_divider, pp_divider, p2_divider, all_ab_list = classify_branch_mode(Winding_Para.ab, Winding_Para.q, Winding_Para.num_poles, 'ZLP')
    q_divider, pp_divider, p2_divider = branch_dividers_for_pattern('ZLP', Winding_Para)
    # print (mode_name, q_divider, pp_divider, p2_divider,all_ab_list)
    
    ###1. Follow the pole divider pattern. 
    pp_per_branch = Winding_Para.num_poles // pp_divider ### pole regions per branch  
    num_phasors = Winding_Para.q*Winding_Para.num_phases ### Phasors per pole
    
    ##########Define the Start conductor IDs based on the parallel branches
    start_layer = 0 
    start_phasor = 0
    start_conductor_ids = []
    ### If Winding_Para.ab is the multiples of q, then we should determin the start cond ids
    if isinstance(Winding_Para.q,int):  ### If q is int
        phasor_range = q_divider*Winding_Para.num_phases
        phasor_interval = int(Winding_Para.q/q_divider)
        for k in range(p2_divider):
            for n in range(pp_divider):
                start_conductor_ids += [(phasor_interval*i+n*pp_per_branch*num_phasors+k*num_phasors, start_layer, start_phasor+(phasor_interval*i) % (Winding_Para.q)) for i in range(phasor_range)]
    # print(start_conductor_ids)
    ##### After the correct defination of SCI We can then Define the Connections 
    Connection = []
    db_conductor_id = []
    d_ini = 1  #### Initial winding direction 
    num_layer_pattern = int(Winding_Para.num_layers/2)  ### Layer patterns 
    num_pp_pattern = int(Winding_Para.num_poles/2/pp_divider)
    num_q_pattern = int(Winding_Para.q/q_divider)
    # ####Assume welding side are identical
    pltp_fl = TP_info.pltp_fl ## parallel layer trans position-first_layer
    pltp_ll = TP_info.pltp_ll  ## parallel layer trans position-last_layer
    ultp = 1  ## uniform layer trans position should be 1 for continuous phasor change 
    jltp = TP_info.jltp  ## uniform layer jump trans position
    cross_layers = Winding_Para.num_layers - 1
    cltp = 1
    if Winding_Para.num_layers % 2 == 0: ## even layer condition
        num_layer_pattern_repeat = num_layer_pattern-1 

        for k in range(num_pp_pattern):
            parallel_layer_connection = [[d_ini,0,0]]
            for i in range(num_layer_pattern):
                uni_conn = [d_ini,1,0]  #### Welding side uni connection
                uniform_connection = [uni_conn]
                uni_layer_connection = [uni_conn,[-d_ini,-1,ultp]]
                jump_layer_connection = [[d_ini,1,ultp]]
                Connection += uni_layer_connection * (num_q_pattern-1) + uniform_connection + jump_layer_connection
            if Winding_Para.ab != int(Winding_Para.num_poles):
                Connection.pop()
                Connection += parallel_layer_connection
                
                for i in range(num_layer_pattern):
                    uni_conn = [-d_ini,-1,0]  #### Welding side uni connection
                    uniform_connection = [uni_conn]
                    uni_layer_connection = [uni_conn,[d_ini,1,ultp]]
                    jump_layer_connection = [[-d_ini,-1,ultp]]
                    Connection += uni_layer_connection * (num_q_pattern-1) + uniform_connection + jump_layer_connection
                    
                Connection.pop()
                Connection += parallel_layer_connection
            
    if Winding_Para.num_layers % 2 == 1:  #### If odd layers
        num_layer_pattern_repeat = int(Winding_Para.num_layers/2)
        for i in range(num_pp_pattern):
            uni_conn = [d_ini,1,0]  #### Welding side uni connection
            uniform_connection = [uni_conn]
            uni_layer_connection = [uni_conn,[d_ini,1,ultp]]
            parallel_layer_connection = [[d_ini,0,pltp_ll]]  
            Connection += uni_layer_connection * num_layer_pattern_repeat + parallel_layer_connection 
            if p2_divider < 2:
                uni_conn = [-d_ini,-1,0] #### Welding side uni connection
                uniform_connection = [uni_conn]
                uni_layer_connection = [uni_conn,[-d_ini,-1,ultp]]
                parallel_layer_connection = [[d_ini,0,pltp_fl]]
                Connection += uni_layer_connection * num_layer_pattern_repeat + parallel_layer_connection
                
    Connection.pop()          
    
    rotate_sequence_for_weld_inlet = False
    if Layout_Para.inlet_from_weld_side == 1:
        try:
            Connection, start_conductor_ids = shift_inlet_to_weld_side(
                Connection,
                start_conductor_ids,
                Winding_Para,
                Layout_Para,
            )
        except ValueError:
            rotate_sequence_for_weld_inlet = True
        
    Connection = TP_modi(TP_info,Connection)
    len_conn = len(Connection)
    num_cond_in_branch = int(Winding_Para.num_poles * Winding_Para.num_layers * Winding_Para.q / Winding_Para.ab)
    if len_conn != num_cond_in_branch-1:
        pass  # Checked by _validate_generated_layout_consistency after dispatch.
        
    db_conductor_id = get_db_cond_id_from_connection(start_conductor_ids,Connection,Winding_Para, Layout_Para)
    if rotate_sequence_for_weld_inlet:
        start_conductor_ids, db_conductor_id = rotate_db_conductor_ids_to_weld_inlet(db_conductor_id)
    
    return (start_conductor_ids, db_conductor_id)

def _cp_reference_winding(winding, naa, dividers, *, signed_travel=False):
    """Build a CP source with the same global-layer context as its target."""
    reference = SimpleNamespace(
        q=winding.q, num_slots=winding.num_slots,
        num_poles=winding.num_poles, num_phases=winding.num_phases,
        num_layers=winding.num_layers, ab=naa,
        branch_dividers=tuple(dividers))
    global_layers = getattr(winding, '_cp_array_global_layers', None)
    if global_layers is not None:
        reference._cp_array_global_layers = global_layers
    if signed_travel:
        reference._capture_cp_constructor_travel = True
    return reference


def _cp_pp_four_pass_weave_from_p2_parent(tp_info, winding, layout):
    """Apply the reviewed L-sized four-pass weave to adjacent P2 parents."""
    D = int(winding.branch_dividers[1])
    if not supports_integer_cp_pp_four_pass_weave(
            winding, winding.branch_dividers):
        raise ValueError('CP PP four-pass weave is outside its structural domain.')
    parent = _cp_reference_winding(
        winding, 2 * D, (1, D, 2))
    _, source = get_winding_layout('CP', tp_info, parent, layout)
    records = phase_map(winding.num_slots, winding.num_poles,
                        winding.num_layers, layout.phase_shift_list,
                        winding.num_phases)
    phase_sign = {(slot, layer): (phase, sign)
                  for slot, layer, phase, sign in records}
    groups = {}
    for source_id, (_, path) in enumerate(source):
        phase = phase_sign[tuple(path[0][:2])][0]
        groups.setdefault(phase, []).append((source_id, path))
    if not groups:
        raise ValueError(
            'CP PP four-pass weave requires four generated parent branches '
            'per phase, each containing four Nlayer-sized passes.')

    selected_paths = []
    for phase in sorted(groups):
        try:
            selected_paths.extend(cp_four_pass_weave(
                groups[phase], winding.num_layers))
        except ValueError as exc:
            raise ValueError(
                'CP PP four-pass weave requires four generated parent branches '
                'per phase, each containing four Nlayer-sized passes.') from exc
    database = [[index + 1, path]
                for index, path in enumerate(selected_paths)]
    return [path[0] for path in selected_paths], database


def _cp_q_only_pair_join_from_p2_parent(tp_info, winding, layout):
    """Pair adjacent same-phase CP (Q,1,2) parents in their generated order."""
    from pattern_identity import circular_travel_steps, pole_region_crossings

    factors = _integer_divider_tuple(
        getattr(winding, 'branch_dividers', None))
    if not supports_integer_cp_q_only_pair_join(winding, factors):
        raise ValueError(
            'CP Q-only adjacent-pair factors are outside the registered route.')
    Q = factors[0]
    reference = _cp_reference_winding(
        winding, 2 * Q, (Q, 1, 2))
    _, source = get_winding_layout('CP', tp_info, reference, layout)
    phase_sign = {(slot, layer): (phase, sign)
                  for slot, layer, phase, sign in phase_map(
                      winding.num_slots, winding.num_poles,
                      winding.num_layers, layout.phase_shift_list,
                      winding.num_phases)}
    groups = {phase: [] for phase in range(winding.num_phases)}
    for source_id, (_, path) in enumerate(source):
        if not path:
            raise ValueError('CP Q-only source contains an empty parent branch.')
        phase = phase_sign[tuple(path[0][:2])][0]
        groups[phase].append((source_id, path))

    database = _CandidateBranches()
    pole_pitch = winding.num_phases * winding.q
    for phase in range(winding.num_phases):
        group = groups[phase]
        if len(group) != 2 * Q:
            raise ValueError(
                f'CP Q-only source phase {phase + 1} has {len(group)} branches; '
                f'expected {2 * Q}.')
        source_paths = {source_id: path for source_id, path in group}
        joined_groups = apply_route_formula(
            'cp_q_only_pair_join', group, factors)
        for joined in joined_groups:
            left_id, right_id = joined.source_ids
            left_path, right_path = source_paths[left_id], source_paths[right_id]
            for source_id, path in ((left_id, left_path),
                                    (right_id, right_path)):
                if any(phase_sign[tuple(node[:2])][0] != phase
                       for node in path):
                    raise ValueError(
                        'CP Q-only adjacent parents must remain in one phase.')
                if (phase_sign[tuple(path[0][:2])][1] != 1
                        or phase_sign[tuple(path[-1][:2])][1] != -1):
                    raise ValueError(
                        f'CP Q-only source branch {source_id + 1} must run N to S.')
            outlet, inlet = left_path[-1], right_path[0]
            if (phase_sign[tuple(outlet[:2])][1]
                    == phase_sign[tuple(inlet[:2])][1]
                    or abs(inlet[1] - outlet[1]) != winding.num_layers // 2):
                raise ValueError(
                    'CP Q-only adjacent parents do not form an ordered CLWP insertion.')
            steps = circular_travel_steps(
                outlet[0], inlet[0], winding.num_slots)
            crossings = tuple(pole_region_crossings(
                outlet[0], step, pole_pitch) for step in steps)
            if not steps or min(crossings) > 1:
                raise ValueError(
                    'CP Q-only adjacent-parent insertion crosses multiple pole regions.')
            branch_id = len(database) + 1
            database.append([branch_id, joined.path])

    validate_selected_cp(database, winding, layout)
    return [path[0] for _, path in database], database


def _cp_q_pp_full_parent_slices_from_p2_parent(tp_info, winding, layout):
    """Split same-phase full-Q CP P2 parents into equal target branches."""
    factors = _integer_divider_tuple(
        getattr(winding, 'branch_dividers', None))
    if not supports_integer_cp_q_pp_full_parent_slices(winding, factors):
        raise ValueError(
            'CP full-Q/full-PP parent slicing is outside its structural domain.')
    Q, D, _P2 = factors
    parent = _cp_reference_winding(
        winding, 2 * Q, (Q, 1, 2))
    _, source = get_winding_layout('CP', tp_info, parent, layout)
    phase_by_position = {
        (slot, layer): phase for slot, layer, phase, _sign in phase_map(
            winding.num_slots, winding.num_poles, winding.num_layers,
            layout.phase_shift_list, winding.num_phases)}
    groups = {phase: [] for phase in range(winding.num_phases)}
    for source_id, (_, path) in enumerate(source):
        if not path:
            raise ValueError('CP full-Q P2 reference contains an empty branch.')
        phase = phase_by_position[tuple(path[0][:2])]
        groups[phase].append((source_id, path))

    target_branch_count = winding.num_phases * winding.ab
    total_positions = winding.num_slots * winding.num_layers
    if target_branch_count <= 0 or total_positions % target_branch_count:
        raise ValueError(
            'CP full-Q/full-PP target branch length is not an integer.')
    target_length = total_positions // target_branch_count
    database = _CandidateBranches()
    for phase in range(winding.num_phases):
        group = groups[phase]
        if len(group) != 2 * Q:
            raise ValueError(
                f'CP full-Q P2 source phase {phase + 1} has {len(group)} '
                f'branches; expected {2 * Q}.')
        pieces = apply_route_formula(
            'cp_q_pp_full_parent_slices', group, factors)
        if len(pieces) != D * Q or any(
                len(piece.path) != target_length for piece in pieces):
            raise ValueError(
                'CP full-Q P2 parents do not partition into the expected '
                'equal target branches.')
        for piece in pieces:
            database.append([len(database) + 1, piece.path])

    validate_selected_cp(database, winding, layout)
    return [path[0] for _, path in database], database


def _cp_q_pp_p2_parent_slices_from_p2_parent(tp_info, winding, layout):
    """Split public CP (Q,1,P2) parents into D equal target branches."""
    factors = _integer_divider_tuple(
        getattr(winding, 'branch_dividers', None))
    if not supports_integer_cp_q_pp_p2_parent_slices(winding, factors):
        raise ValueError(
            'CP Q+PP+P2 parent slicing is outside its structural domain.')
    Q, D, P2 = factors
    parent = _cp_reference_winding(
        winding, Q * P2, (Q, 1, P2), signed_travel=True)
    _, source = get_winding_layout('CP', tp_info, parent, layout)
    source_travel = getattr(source, 'signed_travel', None)
    source_ids = {branch_id for branch_id, _path in source}
    if (not isinstance(source_travel, Mapping)
            or set(source_travel) != source_ids):
        raise ValueError(
            'CP Q+PP+P2 source requires complete constructor signed-travel evidence.')
    phase_by_position = {
        (slot, layer): phase for slot, layer, phase, _sign in phase_map(
            winding.num_slots, winding.num_poles, winding.num_layers,
            layout.phase_shift_list, winding.num_phases)}
    groups = {phase: [] for phase in range(winding.num_phases)}
    for source_id, path in source:
        if not path:
            raise ValueError('CP Q+PP+P2 source contains an empty branch.')
        phase = phase_by_position[tuple(path[0][:2])]
        groups[phase].append((source_id, path))

    target_branch_count = winding.num_phases * winding.ab
    total_positions = winding.num_slots * winding.num_layers
    if target_branch_count <= 0 or total_positions % target_branch_count:
        raise ValueError(
            'CP Q+PP+P2 target branch length is not an integer.')
    target_length = total_positions // target_branch_count
    database = _CandidateBranches()
    signed_travel = {}
    for phase in range(winding.num_phases):
        group = groups[phase]
        if len(group) != Q * P2:
            raise ValueError(
                f'CP Q+PP+P2 source phase {phase + 1} has {len(group)} '
                f'branches; expected {Q * P2}.')
        pieces = apply_route_formula(
            'cp_q_pp_p2_parent_slices', group, factors)
        if len(pieces) != Q * D * P2 or any(
                len(piece.path) != target_length for piece in pieces):
            raise ValueError(
                'CP Q+PP+P2 parents do not partition into the expected '
                'equal target branches.')
        for piece in pieces:
            branch_id = len(database) + 1
            parent_id = piece.source_ids[0]
            width = len(piece.path)
            first_edge = piece.part_index * width
            parent_steps = source_travel[parent_id]
            piece_steps = tuple(parent_steps[
                first_edge:first_edge + width - 1])
            if len(piece_steps) != width - 1:
                raise ValueError(
                    'CP Q+PP+P2 source travel cannot be partitioned with its parent path.')
            database.append([branch_id, piece.path])
            signed_travel[branch_id] = piece_steps

    database.signed_travel = signed_travel
    validate_selected_cp(
        database, winding, layout, require_signed_travel=True)
    return [path[0] for _, path in database], database


def _cp_pp_parent_half_translation(tp_info, winding, layout):
    """Build CP (1,4,1) from translated second halves of public P2 parents."""
    factors = _integer_divider_tuple(
        getattr(winding, 'branch_dividers', None))
    if not supports_integer_cp_pp_parent_half_translation(winding, factors):
        raise ValueError(
            'CP four-sector parent translation is outside its structural domain.')
    Q, D, _P2 = factors
    if (Q, D) != (1, 4):
        raise ValueError('CP parent half translation requires divider (1,4,1).')
    parent = _cp_reference_winding(
        winding, 2, (1, 1, 2))
    _, source = get_winding_layout('CP', tp_info, parent, layout)
    phase_by_position = {
        (slot, layer): phase for slot, layer, phase, _sign in phase_map(
            winding.num_slots, winding.num_poles, winding.num_layers,
            layout.phase_shift_list, winding.num_phases)}
    parents_by_phase = {phase: [] for phase in range(winding.num_phases)}
    for source_id, path in source:
        if len(path) < 2:
            raise ValueError('CP P2 reference contains a short parent branch.')
        phase = phase_by_position[tuple(path[0][:2])]
        parents_by_phase[phase].append((source_id, path))

    numerator = winding.num_slots * winding.num_layers
    denominator = 4 * winding.num_phases
    if numerator % denominator:
        raise ValueError('CP four-sector target path length is not an integer.')
    half_length = numerator // denominator
    tau = winding.num_phases * winding.q
    database = _CandidateBranches()
    source_ids = []
    inlet_offsets = []
    for phase in range(winding.num_phases):
        matching_parents = [
            (source_id, path) for source_id, path in parents_by_phase[phase]
            if circular_travel_steps(
                path[0][0], path[1][0], winding.num_slots) == (tau,)]
        if len(matching_parents) != 1:
            raise ValueError(
                f'CP P2 source phase {phase + 1} has '
                f'{len(matching_parents)} parents with first signed step '
                f'+{tau}; expected one.')
        source_id, parent_path = matching_parents[0]
        if len(parent_path) != 2 * half_length:
            raise ValueError(
                f'CP P2 source branch {source_id + 1} has '
                f'{len(parent_path)} conductors; expected '
                f'{2 * half_length} for two equal halves.')
        half = parent_path[half_length:2 * half_length]
        translated_paths, offsets = cp_parent_half_translation(
            half, num_slots=winding.num_slots, pole_pitch=tau)
        for translated_path, offset in zip(translated_paths, offsets):
            branch_id = len(database) + 1
            database.append([branch_id, translated_path])
            source_ids.append(source_id)
            inlet_offsets.append(offset)

    database.cp_parent_half_translation = {
        'source_dividers': (1, 1, 2),
        'target_dividers': (1, 4, 1),
        'source_branch_ids': tuple(source_ids),
        'slot_offsets': tuple(inlet_offsets),
    }
    validate_selected_cp(database, winding, layout)
    return [path[0] for _, path in database], database


def _cp_pp_sector_slices(tp_info, winding, layout):
    """Cut each validated four-sector branch into equal PP-sector paths."""
    factors = _integer_divider_tuple(
        getattr(winding, 'branch_dividers', None))
    if not supports_integer_cp_pp_sector_slices(winding, factors):
        raise ValueError('CP PP sector slicing is outside its structural domain.')
    D = factors[1]
    parent = _cp_reference_winding(
        winding, 4, (1, 4, 1))
    _, source = get_winding_layout('CP', tp_info, parent, layout)
    target_length = (2 * winding.q * (winding.num_poles // 2)
                     * winding.num_layers // D)
    pieces = apply_route_formula(
        'cp_pp_sector_slices', source, factors)
    database = _CandidateBranches()
    for piece in pieces:
        if len(piece.path) != target_length:
            raise ValueError('CP four-sector source cannot be cut into equal PP paths.')
        database.append([len(database) + 1, piece.path])
    if len(database) != winding.num_phases * D:
        raise ValueError('CP PP sector slicing produced the wrong branch count.')
    validate_selected_cp(database, winding, layout)
    return [path[0] for _, path in database], database


def _cp_connection_signed_slot_step(connection, start, end, winding, layout):
    """Resolve one CP edge from its generated connection vector, preserving direction."""
    direction, layer_step, ptp = connection
    q = winding.q
    if (type(q) is not int or q <= 0 or direction not in (-1, 1)
            or type(layer_step) is not int):
        raise ValueError('CP signed travel requires integer connection inputs.')

    next_conductor = get_next_conductor_id(
        start, winding, layout, direction, layer_step, ptp)
    if tuple(next_conductor) != tuple(end):
        raise ValueError('CP connection vector does not map to its generated edge.')

    regular_pitch = q * winding.num_phases
    if ptp == 'none':
        slot_jump = direction * regular_pitch
    elif type(ptp) is int:
        end_phasor = (start[2] + direction * (regular_pitch + ptp)) % q
        slot_jump = direction * regular_pitch + end_phasor - start[2]
    else:
        raise ValueError('CP signed travel requires an integer pitch adjustment.')

    shifts = getattr(layout, 'phase_shift_list', None)
    if shifts is None:
        shifts = [0] * winding.num_layers
    step = (slot_jump + shifts[end[1]] - shifts[start[1]])
    if not step or (start[0] + step) % winding.num_slots != end[0]:
        raise ValueError('CP directed slot travel does not match its generated edge.')
    return int(step)


def _attach_cp_constructor_signed_travel(database, connections, winding, layout):
    """Attach exact CP connection-vector travel when paths retain constructor order."""
    if (type(getattr(winding, 'q', None)) is not int
            or getattr(layout, 'radial_shift', 0)):
        return database
    if any(len(path) != len(connections) + 1 for _, path in database):
        return database

    travel = {}
    try:
        for branch_id, path in database:
            travel[branch_id] = tuple(
                _cp_connection_signed_slot_step(
                    connection, start, end, winding, layout)
                for connection, start, end in zip(
                    connections, path, path[1:]))
    except (IndexError, TypeError, ValueError, ZeroDivisionError):
        return database
    database = _CandidateBranches(database)
    database.signed_travel = travel
    return database


def pattern_CP(TP_info,Winding_Para,Layout_Para):
    #### CP is the cross-layer pattern.
    mode_name, q_divider, pp_divider, p2_divider, all_ab_list = classify_branch_mode(Winding_Para.ab, Winding_Para.q, Winding_Para.num_poles, 'CP')
    q_divider, pp_divider, p2_divider = branch_dividers_for_pattern('CP', Winding_Para)
    # print (mode_name, q_divider, pp_divider, p2_divider,all_ab_list)
    
    ###1. Follow the pole divider pattern. 
    pp_per_branch = Winding_Para.num_poles // pp_divider ### pole regions per branch  
    num_phasors = Winding_Para.q*Winding_Para.num_phases ### Phasors per pole
    
    ##########Define the Start conductor IDs based on the parallel branches
    start_layer = 0 
    start_phasor = 0
    start_conductor_ids = []
    ### If Winding_Para.ab is the multiples of q, then we should determin the start cond ids
    if isinstance(Winding_Para.q,int):  ### If q is int
        phasor_range = q_divider*Winding_Para.num_phases
        phasor_interval = int(Winding_Para.q/q_divider)
        for k in range(p2_divider):
            for n in range(pp_divider):
                start_conductor_ids += [(phasor_interval*i+n*pp_per_branch*num_phasors+k*num_phasors, start_layer, start_phasor+(phasor_interval*i) % (Winding_Para.q)) for i in range(phasor_range)]
                # start_conductor_ids += [(phasor_interval*i+n*pp_per_branch*num_phasors, k*2+start_layer, start_phasor+(phasor_interval*i) % (Winding_Para.q)) for i in range(phasor_range)]

    ##### After the correct defination of SCI We can then Define the Connections 
    Connection = []
    db_conductor_id = []
    d_ini = 1  #### Initial winding direction 
    num_layer_pattern = int(Winding_Para.num_layers * Winding_Para.num_poles / 2 / pp_divider / 2)  ### Layer patterns 
    num_q_pattern = int(Winding_Para.q/q_divider)
    
    # ####Assume welding side are identical
    ultp = 0  ## uniform layer trans position should be 1 for continuous phasor change 
    cross_layers = int(Winding_Para.num_layers/2)
    cltp = 1
    
    if Winding_Para.num_layers % 2 == 0: ## even layer condition
        half_layers = int(Winding_Para.num_layers/2) 
        layer_record = 0 
        for i in range(num_layer_pattern * num_q_pattern):
            if (i+1) % num_layer_pattern == 0:
                ultp = 1
            else:
                ultp = 0
            weld_layer_jump = 1 if layer_record < Winding_Para.num_layers - 1 else -1
            uni_conn = [d_ini,weld_layer_jump,0]  #### Welding side uni connection
            if (layer_record+weld_layer_jump) < half_layers:
                insert_connection = [d_ini,cross_layers,ultp]
                layer_record = layer_record + cross_layers + weld_layer_jump 
            else:
                insert_connection = [-d_ini,-cross_layers,ultp]
                layer_record = layer_record - cross_layers + weld_layer_jump
            layer_connection = [uni_conn,insert_connection]
            Connection += layer_connection
        Connection.pop()

            
    if Winding_Para.num_layers % 2 == 1:
        _raise_pattern_error("pattern_specific_infeasible", "CP requires an even layer count.", "CP")
        half_layers = int(Winding_Para.num_layers/2) 
        layer_record = 0 
        for i in range(num_layer_pattern * num_q_pattern):
        # for i in range(10):
            if (i+1) % num_layer_pattern == 0:
                ultp = 1
            else:
                ultp = 0
            weld_layer_jump = 1 if layer_record < Winding_Para.num_layers - 1 else -1
            uni_conn = [d_ini,weld_layer_jump,0]  #### Welding side uni connection
            if (layer_record+weld_layer_jump) < half_layers:
                insert_connection = [d_ini,cross_layers,ultp]
                layer_record = layer_record + cross_layers + weld_layer_jump 
            else:
                insert_connection = [-d_ini,-cross_layers,ultp]
                layer_record = layer_record - cross_layers + weld_layer_jump
                
            layer_connection = [uni_conn,insert_connection]
            Connection += layer_connection
            
        Connection.pop()

                       
    
    rotate_sequence_for_weld_inlet = False
    if Layout_Para.inlet_from_weld_side == 1:
        Connection, start_conductor_ids, rotate_sequence_for_weld_inlet = shift_inlet_to_weld_side_or_rotate_later(
            Connection,
            start_conductor_ids,
            Winding_Para,
            Layout_Para,
        )
        
    Connection = TP_modi(TP_info,Connection)
    len_conn = len(Connection)
    num_cond_in_branch = int(Winding_Para.num_poles * Winding_Para.num_layers * Winding_Para.q / Winding_Para.ab)
    if len_conn != num_cond_in_branch-1:
        pass  # Checked by _validate_generated_layout_consistency after dispatch.
        
    db_conductor_id = get_db_cond_id_from_connection(start_conductor_ids,Connection,Winding_Para, Layout_Para)
    if rotate_sequence_for_weld_inlet:
        start_conductor_ids, db_conductor_id = rotate_db_conductor_ids_to_weld_inlet(db_conductor_id)
    elif getattr(Winding_Para, '_capture_cp_constructor_travel', False):
        db_conductor_id = _attach_cp_constructor_signed_travel(
            db_conductor_id, Connection, Winding_Para, Layout_Para)
    
    return (start_conductor_ids, db_conductor_id)

def pattern_ZPP(TP_info,Winding_Para,Layout_Para):
    #### ZPP is the Z-shape parallel pattern, mainly using parallel-layer pins.
    mode_name, q_divider, pp_divider, p2_divider, all_ab_list = classify_branch_mode(Winding_Para.ab, Winding_Para.q, Winding_Para.num_poles, 'ZPP')
    q_divider, pp_divider, p2_divider = branch_dividers_for_pattern('ZPP', Winding_Para)
    # print (mode_name, q_divider, pp_divider, p2_divider,all_ab_list)
    
    ###1. Follow the pole divider pattern. 
    pp_per_branch = Winding_Para.num_poles // pp_divider ### pole regions per branch  
    num_phasors = Winding_Para.q*Winding_Para.num_phases ### Phasors per pole
    
    ##########Define the Start conductor IDs based on the parallel branches
    start_layer = 0 
    start_phasor = 0
    start_conductor_ids = []
    ### If Winding_Para.ab is the multiples of q, then we should determin the start cond ids
    if isinstance(Winding_Para.q,int):  ### If q is int
        phasor_range = q_divider*Winding_Para.num_phases
        phasor_interval = int(Winding_Para.q/q_divider)
        for k in range(p2_divider):
            for n in range(pp_divider):
                start_conductor_ids += [(phasor_interval*i+n*pp_per_branch*num_phasors+k*num_phasors, start_layer, start_phasor+(phasor_interval*i) % (Winding_Para.q)) for i in range(phasor_range)]

    ##### After the correct defination of SCI We can then Define the Connections 
    Connection = []
    db_conductor_id = []
    d_ini = 1  #### Initial winding direction 
    num_layer_pattern = int(Winding_Para.num_layers / 2 )  ### Layer patterns 
    num_q_pattern = int(Winding_Para.q/q_divider)
    num_pp_pattern = int(Winding_Para.num_poles / 2 / pp_divider)
    # ####Assume welding side are identical
    ultp = 1  ## uniform layer trans position should be 1 for continuous phasor change 
    if Layout_Para.inlet_from_weld_side == 0:
        _raise_pattern_error("pattern_specific_infeasible", "ZPP requires inlet_from_weld_side=1.", "ZPP")
        
    if Winding_Para.num_layers % 2 == 0: ## even layer condition

        for n in range(num_layer_pattern):
            
            for i in range(num_pp_pattern * 2):
                weld_conn = [d_ini,1,0] if i % 2 == 0 else  [-d_ini,-1,0]
                layer_connection = [[d_ini,0,1],weld_conn]  #### Welding side uni connection
                Connection += layer_connection
            Connection.pop()
            weld_conn = [-d_ini,1,0]
            Connection += [weld_conn]
        Connection.pop()
            

    Connection = TP_modi(TP_info,Connection)
    len_conn = len(Connection)
    num_cond_in_branch = int(Winding_Para.num_poles * Winding_Para.num_layers * Winding_Para.q / Winding_Para.ab)
    if len_conn != num_cond_in_branch-1:
        pass  # Checked by _validate_generated_layout_consistency after dispatch.
        
    db_conductor_id = get_db_cond_id_from_connection(start_conductor_ids,Connection,Winding_Para, Layout_Para)
    
    return (start_conductor_ids, db_conductor_id)


def pattern_TLP(TP_info,Winding_Para,Layout_Para):
    #### TLP is the top-bottom lap pattern, combining TSP pole tracking with lap-style layer steps.
    mode_name, q_divider, pp_divider, p2_divider, all_ab_list = classify_branch_mode(Winding_Para.ab, Winding_Para.q, Winding_Para.num_poles, 'TLP')
    if pp_divider > 1:
        _raise_pattern_error(
            "pattern_specific_infeasible",
            "TLP does not support pole-pair division for the selected number of parallel branches.",
            "TLP",
        )

    pp_per_branch = Winding_Para.num_poles // pp_divider
    num_phasors = Winding_Para.q * Winding_Para.num_phases

    start_layer = 0
    start_phasor = 0
    start_conductor_ids = []
    if isinstance(Winding_Para.q, int):
        phasor_range = q_divider * Winding_Para.num_phases
        phasor_interval = int(Winding_Para.q / q_divider)
        for k in range(p2_divider):
            for n in range(pp_divider):
                start_conductor_ids += [
                    (
                        phasor_interval * i + n * pp_per_branch * num_phasors + k * num_phasors,
                        start_layer,
                        start_phasor + (phasor_interval * i) % Winding_Para.q,
                    )
                    for i in range(phasor_range)
                ]

    num_layers = Winding_Para.num_layers
    num_cond_in_branch = int(Winding_Para.num_poles * num_layers * Winding_Para.q / Winding_Para.ab)
    num_pattern = int(num_cond_in_branch / num_layers)
    num_wireset = int(pp_divider * p2_divider)

    Connection = []
    pole_count = 0
    cond_count = 0
    phasor_change = 0 if q_divider == 1 else TP_info.pltp_ll
    pole_taken = list(range(p2_divider))

    for i in range(num_pattern):
        for layer_index in range(num_layers - 1):
            slot_direction = 1 if layer_index % 2 == 0 else -1
            layer_phasor_change = 0 if layer_index % 2 == 0 else TP_info.uni_tp
            Connection.append([slot_direction, 1, layer_phasor_change])
            # Lap steps alternate direction. Track their signed displacement,
            # not the number of steps used by the spiral construction.
            pole_count += slot_direction

        cond_count += num_layers - 1

        if cond_count < num_cond_in_branch - 1:
            current_pole_regions = [(i + pole_count) % Winding_Para.num_poles for i in range(num_wireset)]
            next_pole_regions = [(i + pole_count + 1) % Winding_Para.num_poles for i in range(num_wireset)]
            last_pole_regions = [(i + pole_count - 1) % Winding_Para.num_poles for i in range(num_wireset)]
            next_pole_feasible = all(region not in pole_taken for region in next_pole_regions)
            last_pole_feasible = all(region not in pole_taken for region in last_pole_regions)
            if next_pole_feasible and last_pole_feasible:
                d_fec = TP_info.jld
            elif next_pole_feasible:
                d_fec = 1
            elif last_pole_feasible:
                d_fec = -1
            else:
                break

            pole_count += d_fec
            pole_taken += [region + d_fec for region in current_pole_regions]
            Connection.append([d_fec, -num_layers + 1, phasor_change])
            phasor_change = 0 if q_divider == 1 else TP_info.pltp_ll

    Total_Connection = Connection.copy()

    if Winding_Para.ab == 2:
        for k in range(Winding_Para.q - 1):
            phasor_change = 1 if Winding_Para.q % 2 == 0 else -1
            Total_Connection += [[TP_info.jld, -num_layers + 1, phasor_change]]
            Total_Connection += Connection

    if Layout_Para.inlet_from_weld_side == 1:
        Total_Connection, start_conductor_ids = shift_inlet_to_weld_side(
            Total_Connection,
            start_conductor_ids,
            Winding_Para,
            Layout_Para,
        )

    Total_Connection = TP_modi(TP_info, Total_Connection)
    db_conductor_id = get_db_cond_id_from_connection(start_conductor_ids, Total_Connection, Winding_Para, Layout_Para)

    validate_tlp_welds(db_conductor_id, Winding_Para, Layout_Para)
    return (start_conductor_ids, db_conductor_id)


def pattern_LPP(TP_info,Winding_Para,Layout_Para):
    #### LPP is the loop parallel pattern. It uses pole-pair division first and does not split branches by q.
    mode_name, q_divider, pp_divider, p2_divider, all_ab_list = classify_branch_mode(Winding_Para.ab, Winding_Para.q, Winding_Para.num_poles, 'LPP')

    if Layout_Para.inlet_from_weld_side == 0:
        _raise_pattern_error("pattern_specific_infeasible", "LPP requires inlet_from_weld_side=1.", "LPP")
    pp = Winding_Para.num_poles // 2
    selected = getattr(Winding_Para, 'branch_dividers', None)
    active_dividers = ((q_divider, pp_divider, p2_divider)
                       if selected is None else tuple(selected))
    if active_dividers != (1, pp, 1):
        _raise_pattern_error(
            "pattern_specific_infeasible",
            divider_exclusion_reason(
                'LPP', active_dividers, Winding_Para.q, pp),
            "LPP",
        )

    pp_per_branch = Winding_Para.num_poles // pp_divider
    num_phasors = Winding_Para.q * Winding_Para.num_phases

    start_layer = 0
    start_phasor = 0
    start_conductor_ids = []
    if isinstance(Winding_Para.q, int):
        phasor_range = q_divider * Winding_Para.num_phases
        phasor_interval = int(Winding_Para.q / q_divider)
        for k in range(p2_divider):
            for n in range(pp_divider):
                start_conductor_ids += [
                    (
                        phasor_interval * i + n * pp_per_branch * num_phasors + k * num_phasors,
                        start_layer,
                        start_phasor + (phasor_interval * i) % Winding_Para.q,
                    )
                    for i in range(phasor_range)
                ]

    Connection = []
    num_layer_pairs = int(Winding_Para.num_layers / 2)
    num_pp_pattern = int(Winding_Para.num_poles / 2 / pp_divider)
    parallel_ptp = 1 - Winding_Para.q

    for layer_pair_index in range(num_layer_pairs):
        for pole_pair_index in range(num_pp_pattern):
            for q_index in range(Winding_Para.q):
                Connection += [
                    [1, 0, -1],   # Long/short parallel pin into the paired pole region.
                    [1, 1, 0],              # Insertion-side connection.
                    [-1, 0, 0],  # Reverse parallel pin back to the previous pole region.
                ]
                if q_index != Winding_Para.q - 1:
                    Connection += [[-1, -1, 0]]
            if pole_pair_index != num_pp_pattern - 1:
                Connection += [[1, -1, parallel_ptp]]
        if layer_pair_index != num_layer_pairs - 1:
            Connection += [[-1, 1, parallel_ptp]]

    Connection = TP_modi(TP_info, Connection)
    db_conductor_id = get_db_cond_id_from_connection(start_conductor_ids, Connection, Winding_Para, Layout_Para)

    return (start_conductor_ids, db_conductor_id)


# ---------------------------------------------------------------------------
# Validation, dispatch, and public layout API
# ---------------------------------------------------------------------------

def _validate_basic_winding_parameters(pattern_name, Winding_Para):
    q_val = Winding_Para.q
    p_val = Winding_Para.num_poles
    ab_val = Winding_Para.ab
    num_layers = Winding_Para.num_layers
    num_phases = Winding_Para.num_phases

    if q_val <= 0:
        _raise_pattern_error("invalid_parameter", "q must be greater than 0.", pattern_name)
    if p_val <= 0 or p_val % 2 != 0:
        _raise_pattern_error("invalid_parameter", "number of poles must be a positive even number.", pattern_name)
    if num_layers <= 0:
        _raise_pattern_error("invalid_parameter", "number of layers must be greater than 0.", pattern_name)
    if num_phases <= 0:
        _raise_pattern_error("invalid_parameter", "number of phases must be greater than 0.", pattern_name)
    if ab_val <= 0:
        _raise_pattern_error("invalid_parameter", "number of parallel branches must be greater than 0.", pattern_name)


def _validate_branch_decomposition(pattern_name, Winding_Para,
                                   configuration=None, layout=None,
                                   topology=None):
    if pattern_name not in PATTERN_REGISTRY:
        return
    if not PATTERN_REGISTRY[pattern_name].get("implemented", True):
        _raise_pattern_error(
            "pattern_not_implemented",
            "this pattern is named in the document, but no generation algorithm is implemented yet.",
            pattern_name,
        )

    selected = getattr(Winding_Para, 'branch_dividers', None)
    topology = topology or _phase_topology_for_winding(Winding_Para, layout)
    if topology.phase_model == 'arrayed_three_phase_sets':
        decision = resolve_pattern_route(
            pattern_name, Winding_Para, selected, configuration, layout,
            topology=topology)
        if decision.status == 'disabled':
            category = ('unsupported_branch_decomposition'
                        if decision.admission == 'unsupported-yet' else
                        'pattern_specific_infeasible')
            _raise_pattern_error(category, decision.reason, pattern_name)
        return decision

    if pattern_name == 'CP':
        layer_reason = _cp_layer_admission_reason(Winding_Para)
        if layer_reason:
            _raise_pattern_error(
                'pattern_specific_infeasible', layer_reason, pattern_name)

    if Fraction(str(Winding_Para.q)).denominator == 2:
        decision = resolve_pattern_route(
            pattern_name, Winding_Para, selected, configuration, layout,
            topology=topology)
        if decision.status == 'disabled':
            category = ('unsupported_branch_decomposition'
                        if decision.admission == 'unsupported-yet' else
                        'pattern_specific_infeasible')
            _raise_pattern_error(category, decision.reason, pattern_name)
        return decision
    pp = Winding_Para.num_poles // 2
    if (selected is not None
            and pattern_rejects_divider_tuple(
                pattern_name, selected, Winding_Para.q, pp)):
        _raise_pattern_error(
            "pattern_specific_infeasible",
            divider_exclusion_reason(pattern_name, selected, Winding_Para.q, pp),
            pattern_name,
        )

    q_val = Winding_Para.q
    p_val = Winding_Para.num_poles
    ab_val = Winding_Para.ab
    if not float(q_val).is_integer():
        _raise_pattern_error(
            "invalid_parameter",
            "built-in pattern generation requires integer q.",
            pattern_name,
        )
    q_val = int(q_val)
    mode_name, q_divider, pp_divider, p2_divider, all_ab_list = classify_branch_mode(ab_val, q_val, p_val, pattern_name)
    active_dividers = ((q_divider, pp_divider, p2_divider)
                       if selected is None else tuple(selected))
    if pattern_rejects_divider_tuple(
            pattern_name, active_dividers, Winding_Para.q, pp):
        _raise_pattern_error(
            "pattern_specific_infeasible",
            divider_exclusion_reason(pattern_name, active_dividers, Winding_Para.q, pp),
            pattern_name,
        )
    if (q_val * p_val) % ab_val != 0 or ab_val not in all_ab_list:
        supported = ", ".join(str(v) for v in all_ab_list)
        _raise_pattern_error(
            "unsupported_branch_decomposition",
            f"ab={ab_val} cannot be decomposed for q={q_val} and poles={p_val}. Supported branch counts: {supported}.",
            pattern_name,
        )
    if pattern_name in ('TSP', 'TLP') and active_dividers[1] > 1:
        decision = resolve_pattern_route(
            pattern_name, Winding_Para, active_dividers,
            topology=topology)
        if decision.rule_id == f'{pattern_name.lower()}_route_unsupported':
            _raise_pattern_error(
                'unsupported_branch_decomposition', decision.reason, pattern_name)
    if selected is not None and tuple(selected) != (q_divider, pp_divider, p2_divider):
        branch_dividers_for_pattern(pattern_name, Winding_Para)
    if pattern_name == "LPP" and (q_divider != 1 or p2_divider != 1):
        _raise_pattern_error(
            "pattern_specific_infeasible",
            "LPP currently supports pole-pair division only; q divider and p2 divider are not used.",
            pattern_name,
        )


def _validate_pattern_specific_configuration(pattern_name, Winding_Para,
                                            Layout_Para, topology=None):
    if pattern_name not in PATTERN_REGISTRY:
        return

    topology = topology or _phase_topology_for_winding(Winding_Para, Layout_Para)
    layers = (topology.phase_sets[0].layer_count
              if topology.phase_model == 'arrayed_three_phase_sets'
              else topology.layers)

    if pattern_name == "CP":
        layer_reason = _cp_layer_admission_reason(Winding_Para)
        if layer_reason:
            _raise_pattern_error(
                "pattern_specific_infeasible", layer_reason, pattern_name)

    if pattern_name in ("ZPP", "TLP", "LPP") and layers % 2 != 0:
        _raise_pattern_error(
            "pattern_specific_infeasible",
            f"{get_pattern_label(pattern_name)} requires an even layer count.",
            pattern_name,
        )

    if pattern_requires_weld_side_inlet(pattern_name) and getattr(Layout_Para, "inlet_from_weld_side", 0) != 1:
        _raise_pattern_error(
            "pattern_specific_infeasible",
            f"{get_pattern_label(pattern_name)} requires inlet_from_weld_side=1 so the inlet starts from the weld side.",
            pattern_name,
        )


def _validate_generated_layout_consistency(pattern_name, start_conductor_ids, db_conductor_id, Winding_Para):
    if pattern_name not in PATTERN_REGISTRY:
        return

    expected_float = Winding_Para.num_poles * Winding_Para.num_layers * Winding_Para.q / Winding_Para.ab
    if abs(expected_float - round(expected_float)) > 1e-9:
        _raise_pattern_error(
            "phase_division_infeasible",
            "slot/layer conductors cannot be divided evenly across phases and branches.",
            pattern_name,
        )
    expected_count = int(round(expected_float))
    expected_groups = Winding_Para.ab * Winding_Para.num_phases

    if len(start_conductor_ids) != expected_groups:
        _raise_pattern_error(
            "generated_layout_sequence",
            f"generated {len(start_conductor_ids)} start conductors; expected {expected_groups} phase branch groups.",
            pattern_name,
        )
    if len(db_conductor_id) != expected_groups:
        _raise_pattern_error(
            "generated_layout_sequence",
            f"generated {len(db_conductor_id)} branch groups; expected {expected_groups}.",
            pattern_name,
        )

    total_references = 0
    conductor_keys = []
    expected_total_conductors = int(Winding_Para.num_slots * Winding_Para.num_layers)

    for branch_index, branch_info in enumerate(db_conductor_id, start=1):
        if not isinstance(branch_info, (list, tuple)) or len(branch_info) < 2:
            _raise_pattern_error(
                "generated_layout_sequence",
                f"branch group {branch_index} has an unsupported structure.",
                pattern_name,
            )
        conductors = branch_info[1]
        actual_count = len(conductors)
        if actual_count != expected_count:
            branch_id = branch_info[0]
            _raise_pattern_error(
                "generated_layout_sequence",
                f"branch {branch_id} has {actual_count} conductors; expected {expected_count}.",
                pattern_name,
            )
        total_references += actual_count
        for cond_index, conductor_id in enumerate(conductors, start=1):
            if not isinstance(conductor_id, (list, tuple)) or len(conductor_id) < 2:
                _raise_pattern_error(
                    "generated_layout_sequence",
                    f"branch {branch_info[0]} conductor {cond_index} has an unsupported id.",
                    pattern_name,
                )
            slot, layer = conductor_id[0], conductor_id[1]
            if not isinstance(slot, int) or not isinstance(layer, int):
                _raise_pattern_error(
                    "generated_layout_sequence",
                    f"branch {branch_info[0]} conductor {cond_index} has non-integer slot/layer id {conductor_id}.",
                    pattern_name,
                )
            if slot < 0 or slot >= Winding_Para.num_slots or layer < 0 or layer >= Winding_Para.num_layers:
                _raise_pattern_error(
                    "generated_layout_sequence",
                    f"branch {branch_info[0]} conductor {cond_index} references invalid slot/layer {conductor_id}.",
                    pattern_name,
                )
            conductor_keys.append((slot, layer))

    if total_references != expected_total_conductors:
        _raise_pattern_error(
            "generated_layout_sequence",
            f"generated {total_references} conductor references; expected {expected_total_conductors}.",
            pattern_name,
        )

    unique_count = len(set(conductor_keys))
    if unique_count != expected_total_conductors:
        duplicate_count = total_references - unique_count
        missing_count = expected_total_conductors - unique_count
        _raise_pattern_error(
            "generated_layout_sequence",
            f"layout has {duplicate_count} duplicate slot/layer references and misses {missing_count} conductors.",
            pattern_name,
        )


def _dispatch_winding_pattern(pattern_name, TP_info, Winding_Para, Layout_Para,
                              *, route_decision=None, topology=None):
    topology = topology or _phase_topology_for_winding(Winding_Para, Layout_Para)
    if topology.phase_model == 'arrayed_three_phase_sets':
        return _array_three_phase_winding_sets(
            pattern_name, TP_info, Winding_Para, Layout_Para,
            topology.set_count, route_decision=route_decision,
            topology=topology)

    if route_decision is not None:
        route = route_decision.route_name
        if Fraction(str(Winding_Para.q)).denominator == 2:
            if route == 'uwp_half_integer_q_pp':
                return _fractional_uwp_q_pp(TP_info, Winding_Para, Layout_Para)
            if route == 'uwp_half_integer_p2':
                return _fractional_uwp_2q(TP_info, Winding_Para, Layout_Para)
            if route in ('bwp_fractional_sector_array',
                         'uwp_fractional_sector_array'):
                return _fractional_sector_array(
                    pattern_name, TP_info, Winding_Para, Layout_Para,
                    route_decision=route_decision)
            raise ValueError('No constructor matches the resolved half-integer route.')
    else:
        if supports_half_integer_uwp_q_pp(
                pattern_name, Winding_Para, getattr(Winding_Para, 'branch_dividers', ())):
            return _fractional_uwp_q_pp(TP_info, Winding_Para, Layout_Para)
        route = _selected_integer_divider_route(pattern_name, Winding_Para)
    if pattern_name == 'CP' and route == 'cp_pp_four_pass_weave':
        return _cp_pp_four_pass_weave_from_p2_parent(
            TP_info, Winding_Para, Layout_Para)
    if pattern_name == 'CP' and route == 'cp_q_only_pair_join':
        return _cp_q_only_pair_join_from_p2_parent(
            TP_info, Winding_Para, Layout_Para)
    if pattern_name == 'CP' and route == 'cp_q_pp_full_parent_slices':
        return _cp_q_pp_full_parent_slices_from_p2_parent(
            TP_info, Winding_Para, Layout_Para)
    if pattern_name == 'CP' and route == 'cp_q_pp_p2_parent_slices':
        return _cp_q_pp_p2_parent_slices_from_p2_parent(
            TP_info, Winding_Para, Layout_Para)
    if pattern_name == 'CP' and route == 'cp_pp_parent_half_translation':
        return _cp_pp_parent_half_translation(
            TP_info, Winding_Para, Layout_Para)
    if pattern_name == 'CP' and route == 'cp_pp_sector_slices':
        return _cp_pp_sector_slices(
            TP_info, Winding_Para, Layout_Para)
    if pattern_name == 'TSP' and route == 'tsp_pp_only_q_p2_identity':
        return _tsp_pp_only_q_p2_identity_from_reference(
            TP_info, Winding_Para, Layout_Para)
    if pattern_name == 'TSP' and route == 'tsp_q_only_pair_join':
        return _tsp_q_only_pair_join_from_reference(
            TP_info, Winding_Para, Layout_Para)
    if pattern_name == 'TLP' and route == 'tlp_q_only_pair_join':
        return _tlp_q_only_pair_join_from_reference(
            TP_info, Winding_Para, Layout_Para)
    if pattern_name == 'TSP' and route == 'tsp_pp_p2_sector':
        return _tsp_pp_p2_sector_from_formula(Winding_Para)
    if pattern_name == 'TSP' and route == 'tsp_spiral_pass_partition':
        return _tsp_spiral_pass_partition_from_formula(Winding_Para)
    if pattern_name == 'ZPP' and route in (
            'zpp_pp_only_half_turn',
            'zpp_pp_only_indexed_translation'):
        return _zpp_pp_only_indexed_translation_from_q_parent(
            TP_info, Winding_Para, Layout_Para)
    if (pattern_name == 'ZPP'
            and route == 'zpp_pp_only_centered_entry_translation'):
        return _zpp_pp_only_centered_entry_from_q_parent(
            TP_info, Winding_Para, Layout_Para)
    if pattern_name == 'SLP' and route == 'pp_only':
        return _slp_pp_from_reference(TP_info, Winding_Para, Layout_Para)
    if pattern_name == 'SLP' and route == 'slp_q_pp_p2_parent_cut':
        return _slp_q_pp_p2_parent_cut_from_full_q(
            TP_info, Winding_Para, Layout_Para)
    slp_rotated_weld_constructors = {
        'slp_p2_from_reference': _slp_p2_from_reference,
        'slp_pair_lane_p2': _slp_pair_lane_p2_from_reference,
        'slp_pp_p2_sector': _slp_pp_p2_sector_from_reference,
    }
    if pattern_name == 'SLP' and route in slp_rotated_weld_constructors:
        constructor = slp_rotated_weld_constructors[route]
        if Layout_Para.inlet_from_weld_side:
            source_layout = (Layout_Para._replace(inlet_from_weld_side=0)
                             if hasattr(Layout_Para, '_replace') else
                             SimpleNamespace(**{**vars(Layout_Para),
                                                'inlet_from_weld_side': 0}))
            _, insert_database = constructor(
                TP_info, Winding_Para, source_layout)
            # Reopen each intact branch on its other terminal side. The new
            # closing edge is checked by the SLP validators below.
            rotated = [[branch_id, path[1:] + path[:1]]
                       for branch_id, path in insert_database]
            return orient_p2_branches_n_to_s(
                rotated, Winding_Para, Layout_Para)
        return constructor(TP_info, Winding_Para, Layout_Para)
    if route == 'slp_full_q_p2':
        return _slp_full_q_p2_from_reference(TP_info, Winding_Para, Layout_Para)
    if route == 'ssp_p2_reflected':
        return _ssp_reflected_p2(TP_info, Winding_Para, Layout_Para)
    if route == 'zlp_p2_mirrored':
        return _zlp_p2_from_reference(TP_info, Winding_Para, Layout_Para)
    if route == 'zlp_pp_p2_source_cut':
        return _zlp_pp_p2_from_p2_parent(
            TP_info, Winding_Para, Layout_Para)
    if route == 'tlp_pp_only_even':
        return _tlp_pp_only_even_from_reference(
            TP_info, Winding_Para, Layout_Para)
    if route == 'tlp_pp_p2_short_unit':
        return _tlp_pp_p2_short_unit_from_reference(
            TP_info, Winding_Para, Layout_Para)
    if route == 'tlp_q_pp_p2_parent_slices':
        return _tlp_q_pp_p2_parent_slices_from_reference(
            TP_info, Winding_Para, Layout_Para)
    if route == 'uwp_short_p2_weld':
        return _uwp_short_p2_weld(Winding_Para, Layout_Para)
    if (pattern_name == 'SLP' and route == 'slp_q_pp_parent_cut'
            and Layout_Para.inlet_from_weld_side):
        return _slp_q_pp_parent_cut_weld_from_reference(
            TP_info, Winding_Para, Layout_Para)
    if route in ('ssp_q_pp_parent_cut', 'slp_q_pp_parent_cut'):
        return _spiral_q_pp_from_pp_parent(
            pattern_name, TP_info, Winding_Para, Layout_Para)
    if route and (route.endswith('_q_pp_two')
                  or route == 'tlp_pp_only_two'):
        return _q_pp_two_from_reference(
            pattern_name, TP_info, Winding_Para, Layout_Para)
    if pattern_name == 'manual':
        import manual_layout
        app = manual_layout.SlotGame()
        app.num_poles = Winding_Para.num_poles
        app.num_layers = Winding_Para.num_layers
        app.naa = Winding_Para.ab
        app.q = Winding_Para.q
        app.m = Winding_Para.num_phases
        app.phase_shift = getattr(Layout_Para, "phase_shift", 0)
        app.psl = getattr(Layout_Para, "PSL", 1)
        app.set_defaults()
        app.mainloop()
        start_conductor_ids, db_conductor_id, cond_info = app.get_result()
        return start_conductor_ids, db_conductor_id

    if supports_half_integer_uwp_p2(
            pattern_name, Winding_Para,
            getattr(Winding_Para, 'branch_dividers', ())):
        pp_divider = int(Fraction(str(Winding_Para.branch_dividers[1])))
        return _fractional_uwp_2q(TP_info, Winding_Para, Layout_Para)
    if is_half_integer_uwp_2q(pattern_name, Winding_Para):
        return _fractional_uwp_2q(TP_info, Winding_Para, Layout_Para)
    if is_fractional_sector_array_candidate(pattern_name, Winding_Para):
        return _fractional_sector_array(
            pattern_name, TP_info, Winding_Para, Layout_Para)
    if is_fractional_bwp_single_branch(pattern_name, Winding_Para):
        return _fractional_bwp_single_branch(TP_info, Winding_Para, Layout_Para)

    dispatch = {
        'BWP': pattern_BWP,
        'UWP': pattern_UWP,
        'SSP': pattern_SSP,
        'TSP': pattern_TSP,
        'SLP': pattern_SLP,
        'ZLP': pattern_ZLP,
        'CP': pattern_CP,
        'ZPP': pattern_ZPP,
        'TLP': pattern_TLP,
        'LPP': pattern_LPP,
    }
    pattern_code = get_pattern_code(pattern_name)
    if pattern_code not in dispatch:
        _raise_pattern_error("unsupported_pattern", f"Unsupported winding pattern '{pattern_name}'.", pattern_name)
    return dispatch[pattern_code](TP_info, Winding_Para, Layout_Para)


def _array_three_phase_winding_sets(pattern_name, TP_info, winding, layout,
                                    set_count, route_decision=None,
                                    topology=None):
    """Generate each layer-assigned three-phase set, then array it by angle."""
    topology = topology or _phase_topology_for_winding(winding, layout)
    if topology.phase_model != 'arrayed_three_phase_sets':
        raise ValueError('Winding is not an array of three-phase sets.')
    if topology.set_count != set_count:
        raise ValueError('Requested phase-set count differs from the topology.')
    phases = topology.phases

    if route_decision is None:
        route_decision = resolve_pattern_route(
            pattern_name, winding, getattr(winding, 'branch_dividers', None),
            TP_info, layout, topology=topology)
        if route_decision.status not in ('enabled', 'candidate'):
            raise ValueError(route_decision.reason)
    array_factors = (route_decision.dividers
                     or getattr(winding, 'branch_dividers', ()) or ())
    local_decisions, failure = _phase_array_local_route_decisions(
        pattern_name, winding, array_factors,
        TP_info, layout, route_decision, topology)
    if failure:
        raise ValueError(failure)
    database = _CandidateBranches()
    starts = []
    signed_travel = {}

    for spec, local_decision in zip(topology.phase_sets, local_decisions):
        local_winding, local_layout = _phase_array_local_inputs(
            winding, layout, spec, array_factors, pattern_name)
        local_starts, local_database = _dispatch_winding_pattern(
            pattern_name, TP_info, local_winding, local_layout,
            route_decision=local_decision)
        if local_database is None:
            raise ValueError(
                f'{pattern_name} returned no layout for three-phase set '
                f'{spec.set_index + 1}.')

        local_travel = getattr(local_database, 'signed_travel', None)
        for _branch_id, path in local_database:
            rotated = []
            for node in path:
                slot, layer = spec.to_global(node[0], node[1])
                rotated.append((slot, layer, *node[2:]))
            branch_id = len(database) + 1
            database.append([branch_id, rotated])
            starts.append(rotated[0])
            if isinstance(local_travel, Mapping):
                signed_travel[branch_id] = tuple(
                    local_travel.get(_branch_id, ()))

    if signed_travel and len(signed_travel) == len(database):
        database.signed_travel = signed_travel
    database.phase_set_array = {
        'set_count': topology.set_count,
        'set_layers': topology.phase_sets[0].layer_count,
        'electrical_step_degrees': float(
            topology.phase_sets[1].electrical_offset_degrees
            if len(topology.phase_sets) > 1 else 0),
        'slot_offsets': tuple(spec.slot_offset for spec in topology.phase_sets),
        'routes': tuple({
            'set': spec.set_index + 1,
            'rule_id': decision.rule_id,
            'route_name': decision.route_name,
            'status': decision.status,
            'reason': decision.reason,
        } for spec, decision in zip(topology.phase_sets, local_decisions)),
    }
    return starts, database


def _bwp_fast_rule_domain_verified(winding, layout, objective):
    """Return whether formula-based BWP stopping is in the audited domain."""
    if objective != 'min_pin_types':
        return False
    q = Fraction(str(winding.q))
    return (
        q.denominator == 1 and 2 <= q <= 6
        and 1 <= int(winding.num_poles) // 2 <= 6
        and int(winding.num_layers) in (2, 4, 6)
        and int(winding.num_phases) == 3
        and not bool(getattr(layout, 'inlet_from_weld_side', 0))
        and tuple(getattr(layout, 'phase_shift_list', ()))
        == (0,) * int(winding.num_layers)
    )


def _bwp_insertion_side_min_pin_types_target(winding, layout, objective):
    """Manuscript v3 Table IV gives the insertion-side BWP target N_L + 1."""
    if not _bwp_fast_rule_domain_verified(winding, layout, objective):
        return None
    return int(winding.num_layers) + 1


def get_auto_configured_layout(pattern, tp, winding, layout,
                               allow_candidate=False, objective=None,
                               pin_length_evaluator=None,
                               _force_full_search_for_validation=False):
    """Rank every validated recipe by objective; keep honest retention states.

    The implementation list is replayable, and each objective has its own winner.
    Minima apply to the evaluated recipe domain, not every physical winding.
    `_force_full_search_for_validation` bypasses BWP rule-first termination for
    same-case differential audits; normal UI and catalog callers leave it false.
    """
    from hashlib import sha256
    from itertools import chain
    objective = auto_tp.normalize_objective(objective)
    pattern = normalize_pattern_name(pattern, allow_extra=True)
    bwp_pin_type_target = (
        _bwp_insertion_side_min_pin_types_target(winding, layout, objective)
        if pattern == 'BWP' and not _force_full_search_for_validation else None)

    def tp_values(value):
        values = dict(tp_type=getattr(value, 'tp_type', 'Regular'),
                      **{key: getattr(value, key, 0) for key in auto_tp.TP_FIELD_NAMES},
                      jld=getattr(value, 'jld', 1),
                      tp_start_index=getattr(value, 'tp_start_index', 0),
                      pole_group_tp=deepcopy(getattr(value, 'pole_group_tp', {})))
        rule = getattr(value, 'auto_configuration_rule', None)
        if rule:
            values['auto_configuration_rule'] = rule
        return values

    reference_tp = SimpleNamespace(**tp_values(tp))
    reference_tp.tp_type = 'Regular'
    reference_tp.auto_configuration_rule = None
    for key in auto_tp.TP_FIELD_NAMES:
        setattr(reference_tp, key, 0)
    starts, database = get_winding_layout(
        pattern, reference_tp, winding, layout, allow_candidate=allow_candidate)
    reference = database
    records = phase_map(winding.num_slots,winding.num_poles,winding.num_layers,
                        layout.phase_shift_list,winding.num_phases)
    def assess(paths):
        return auto_tp.assess_strong_symmetry(paths,records,winding.num_slots,
                                             winding.num_poles,winding.ab)
    assessment = assess(database)
    neutral_strong = assessment['strong']
    attempts = 0
    chosen = None
    implementations, winners, seen = [], {}, set()
    weld_rule_rejections = 0
    searched_rule_ids = set()
    fast_path_applied = False
    pin_type_formula_stop_applied = False
    slots = winding.num_slots
    phase_lookup = {(s, layer): phase for s, layer, phase, _ in records}

    def start_regions(paths):
        return [(branch_id, phase_lookup[p[0][:2]],
                 ((p[0][0]-layout.phase_shift_list[p[0][1]]) % slots)
                 *winding.num_poles//slots, p[0][1]) for branch_id, p in paths]

    initial_regions = start_regions(reference)

    def reached_bwp_pin_type_target():
        return (bwp_pin_type_target is not None
                and any(row['metrics']['pin_type_count'] == bwp_pin_type_target
                        for row in implementations))

    def consider(candidate_starts, paths, trial, parameters, changed, rule_id):
        nonlocal weld_rule_rejections
        weld_contract = auto_tp.weld_side_contract(
            reference, paths, winding.num_slots, layout)
        if not weld_contract['valid']:
            weld_rule_rejections += 1
            return False
        if not (trial['strong'] and paths.layout_report['electrically_valid']
                and start_regions(paths) == initial_regions):
            return False
        physical = tuple((branch, tuple(tuple(n[:2]) for n in path)) for branch, path in paths)
        identity = sha256(repr(physical).encode('ascii')).hexdigest()
        if identity in seen:
            return False
        seen.add(identity)
        metrics = auto_tp.implementation_metrics(
            paths, reference, winding, layout, pin_length_evaluator)
        implementation = dict(
            implementation_id=identity,
            effective_parameters=parameters,
            effective_start_schedule=None,
            rule_id=rule_id,
            physical_paths=physical,
            metrics=metrics,
            weld_side_contract=weld_contract,
        )
        implementations.append(implementation)
        for target in auto_tp.AUTO_CONFIGURE_OBJECTIVES:
            try:
                score = auto_tp.objective_score(metrics, target)
            except ValueError:
                continue
            if target not in winners or score < winners[target][0]:
                winners[target] = (score, candidate_starts, paths, trial, changed, implementation)
        return True

    searched_rule_ids.add('neutral_reference')
    consider(starts, database, assessment, tp_values(reference_tp), None,
             'neutral_reference')
    if reached_bwp_pin_type_target():
        fast_path_applied = True
        pin_type_formula_stop_applied = True
    # Search even an already strong baseline: it may not minimize pin types/length.
    candidates = iter(())
    if not assessment['hard_no'] and not fast_path_applied:
        recipe_candidates = auto_tp.configuration_recipes(
            pattern, winding.q, winding.num_poles, len(database[0][1]),
            include_start_indices=not neutral_strong)
        if pattern == 'BWP':
            # Keep BWP's general offset recipes ahead of Interval/Times and
            # any currently selected TP, which may itself be an Interval.
            candidates = chain(recipe_candidates, [tp_values(tp)])
        else:
            candidates = chain([tp_values(tp)], recipe_candidates)
        if (pattern == 'UWP' and Fraction(str(winding.q)).denominator == 1
                and selected_integer_divider_route(pattern, winding) == 'uwp_balanced_q'):
            candidates = chain([dict(tp_type='Auto', **uwp_balanced_q_settings(winding))],
                               candidates)
    tried_parameters = {repr(tp_values(reference_tp))}
    for values in candidates:
        values = dict(values)
        rule_id = values.pop('_rule_id', 'selected_input')
        values.pop('_rule_stage', None)
        searched_rule_ids.add(rule_id)
        candidate = SimpleNamespace(**tp_values(reference_tp))
        if rule_id.endswith('_geometry_recipe'):
            candidate.auto_configuration_rule = rule_id
            candidate._auto_configuration_token = _AUTO_CONFIGURATION_TOKEN
        for key,value in values.items():
            setattr(candidate,key,value)
        parameters = tp_values(candidate)
        key = repr(parameters)
        if key in tried_parameters:
            continue
        tried_parameters.add(key)
        attempts += 1
        try:
            candidate_starts,paths = get_winding_layout(
                pattern, candidate, winding, layout,
                allow_candidate=allow_candidate)
            trial = assess(paths)
        except (ValueError,IndexError,TypeError):
            continue
        rule_hit = consider(candidate_starts, paths, trial, parameters, values, rule_id)
        if rule_hit and reached_bwp_pin_type_target():
            fast_path_applied = True
            pin_type_formula_stop_applied = True
            break
    selected = winners.get(objective)
    if selected is not None:
        _, starts, database, assessment, chosen, implementation = selected
        effective_parameters = implementation['effective_parameters']
        metrics = implementation['metrics']
    else:
        effective_parameters = tp_values(reference_tp)
        metrics = auto_tp.implementation_metrics(
            database, reference, winding, layout, pin_length_evaluator)
    status = ('strong symmetry layout' if assessment['strong'] and database.layout_report['electrically_valid'] else
              'not strong symmetry layout' if assessment['hard_no'] else
              'auto configure pending')
    database.auto_configuration = dict(status=status, assessment=assessment,
        parameters=chosen, attempts=attempts,
        completed=status == 'strong symmetry layout',
        objective=objective, metrics=metrics,
        objective_policy_version=1, reference_parameters=tp_values(reference_tp),
        weld_rule_version=1, weld_rule_rejections=weld_rule_rejections,
        weld_rule=('Physical weld-edge multiset unchanged from the neutral reference; '
                   'one phase-shift-corrected direction per cross-layer pair.'),
        implementation_id=selected[-1]['implementation_id'] if selected else None,
        implementations=implementations, evaluated_implementation_count=len(implementations),
        objectives={target: (dict(available=True, **winners[target][-1]) if target in winners
                            else dict(available=False, reason=(metrics['length_unavailable_reason']
                                if target == 'min_average_pin_length' else status)))
                    for target in auto_tp.AUTO_CONFIGURE_OBJECTIVES},
        search_complete=not fast_path_applied,
        fast_path_applied=fast_path_applied,
        fast_path_rule=('manuscript_v3_bwp_insertion_side_min_pin_types_formula'
                        if fast_path_applied else None),
        fast_path_domain=(
            'min_pin_types; integer q=2..6; pole pairs=1..6; layers in {2,4,6}; '
            'three phases; insertion-side inlet; zero layer shifts'
            if bwp_pin_type_target is not None else None),
        minimum_pin_types_formula=(
            'N_L + 1 (manuscript v3, BWP insertion-side, Table IV)'
            if bwp_pin_type_target is not None else None),
        minimum_pin_types_target=bwp_pin_type_target,
        minimum_pin_types_reached=reached_bwp_pin_type_target(),
        pin_type_formula_stop_applied=pin_type_formula_stop_applied,
        optimality_scope=(
            'manuscript_v3_bwp_insertion_side_min_pin_types' if fast_path_applied
            else 'best_in_evaluated_recipe_domain'),
        effective_parameters=effective_parameters,
        effective_start_schedule=None,
        searched_rule_ids=sorted(searched_rule_ids),
        unsearched_dimensions=[
            'independent per-branch start relocation',
            'independent pole-group schedules unless emitted by an admitted route',
        ],
        starts=[tuple(p[0][:2]) for _,p in database],
        scope=(('BWP insertion-side Auto stops when a candidate passes all '
                'existing validations and reaches the manuscript v3 pin-type '
                'target N_L + 1. Later recipes were not evaluated. The pin-type '
                'minimum is reached; transposition tie-breaks and other objectives '
                'are only ranked over evaluated candidates. '
                if fast_path_applied else '')
               + 'Geometry-derived common TP recipes for integer BWP/UWP and bounded '
               'Pattern-specific recipes for other routes. Interval/Times start '
               + ('indices were fully enumerated because the neutral layout was unresolved. '
                  if not neutral_strong else
                  'indices used the canonical origin because the neutral layout was already strong. ')
               + 'Starts remain in their original pole region and layer. Independent '
                 'per-branch starts and unemitted pole-group schedules are not exhausted.'))
    database.layout_report['auto_configuration'] = database.auto_configuration
    return starts,database


def replay_auto_configuration(pattern, implementation, winding, layout,
                              allow_candidate=False):
    """Replay and verify one complete implementation exported by Auto."""
    from hashlib import sha256
    pattern = normalize_pattern_name(pattern, allow_extra=True)
    required = {'implementation_id', 'effective_parameters', 'physical_paths',
                'rule_id', 'effective_start_schedule'}
    if not isinstance(implementation, dict) or not required <= implementation.keys():
        raise ValueError('Replay requires a complete exported Auto implementation.')
    if implementation['effective_start_schedule'] is not None:
        raise ValueError('This Auto version does not admit independent start schedules.')
    parameters = deepcopy(dict(implementation['effective_parameters']))
    rule = parameters.get('auto_configuration_rule')
    if (implementation['rule_id'].endswith('_geometry_recipe')
            and rule != implementation['rule_id']):
        raise ValueError('Exported Auto rule metadata is inconsistent.')
    if rule is not None and rule != f'{pattern.lower()}_geometry_recipe':
        raise ValueError('Auto configuration rule does not match the selected Pattern.')
    if rule:
        neutral = SimpleNamespace(
            tp_type='Regular', tp_interval=0, tp_times=0, uni_tp=0,
            pltp_fl=0, pltp_ll=0, jltp=0, jld=parameters.get('jld', 1),
            tp_start_index=0, pole_group_tp={})
        _searched_starts, searched = get_auto_configured_layout(
            pattern, neutral, winding, layout,
            allow_candidate=allow_candidate)
        emitted = searched.auto_configuration['implementations']
        if not any(
                item['implementation_id'] == implementation['implementation_id']
                and item['effective_parameters'] == parameters
                and item['rule_id'] == implementation['rule_id']
                and item['physical_paths'] == implementation['physical_paths']
                for item in emitted):
            raise ValueError(
                'Auto implementation was not emitted by the validated '
                'geometry search.')
    candidate = SimpleNamespace(**parameters)
    if rule:
        candidate._auto_configuration_token = _AUTO_CONFIGURATION_TOKEN
    neutral = SimpleNamespace(**parameters)
    neutral.tp_type = 'Regular'
    neutral.auto_configuration_rule = None
    neutral.__dict__.pop('_auto_configuration_token', None)
    for key in auto_tp.TP_FIELD_NAMES:
        setattr(neutral, key, 0)
    _, reference = get_winding_layout(
        pattern, neutral, winding, layout, allow_candidate=allow_candidate)
    starts, paths = get_winding_layout(
        pattern, candidate, winding, layout, allow_candidate=allow_candidate)
    weld_contract = auto_tp.weld_side_contract(
        reference, paths, winding.num_slots, layout)
    if not weld_contract['valid']:
        raise ValueError('Auto replay violates the weld-side uniform contract.')
    physical = tuple((branch, tuple(tuple(node[:2]) for node in path))
                     for branch, path in paths)
    expected = tuple((int(branch), tuple(tuple(node[:2]) for node in path))
                     for branch, path in implementation['physical_paths'])
    identity = sha256(repr(physical).encode('ascii')).hexdigest()
    if physical != expected or identity != implementation['implementation_id']:
        raise ValueError('Auto replay paths do not match the exported implementation.')
    records = phase_map(winding.num_slots, winding.num_poles, winding.num_layers,
                        layout.phase_shift_list, winding.num_phases)
    assessment = auto_tp.assess_strong_symmetry(
        paths, records, winding.num_slots, winding.num_poles, winding.ab)
    if not assessment['strong'] or not paths.layout_report['electrically_valid']:
        raise ValueError('Auto replay no longer passes strong and electrical gates.')
    return starts, paths


def _apply_post_connection_shifts(pattern, starts, database, winding, layout):
    """Relocate completed connections without reclassifying their topology."""
    slots = winding.num_slots
    shifts = layout.phase_shift_list
    set_count = three_phase_set_count(winding.num_phases)
    local_layers = winding.num_layers // set_count
    radial_limit = winding.num_phases * winding.q
    base_phase = {(slot, layer): (phase, sign) for slot, layer, phase, sign
                  in phase_map(slots, winding.num_poles, winding.num_layers,
                               [0] * winding.num_layers, winding.num_phases)}
    shifted_phase = {(slot, layer): (phase, sign) for slot, layer, phase, sign
                     in phase_map(slots, winding.num_poles, winding.num_layers,
                                  shifts, winding.num_phases)}

    def relocate(node):
        slot, layer = node[:2]
        local_layer = layer % local_layers
        if (layout.radial_shift and slot < radial_limit
                and 0 < local_layer < local_layers - 1):
            other_layer = layer + (1 if local_layer % 2 else -1)
            if base_phase[slot, layer] == base_phase[slot, other_layer]:
                layer = other_layer
        result = ((slot + shifts[layer]) % slots, layer, *node[2:])
        if base_phase[slot, node[1]] != shifted_phase[result[:2]]:
            raise ValueError('Post-connection shift changed a conductor phase or pole sign.')
        return result

    base_report = database.layout_report
    recorded_travel = getattr(database, 'signed_travel', None)
    new_travel = {} if recorded_travel is not None else None
    for branch_id, path in database:
        relocated = [relocate(node) for node in path]
        if new_travel is not None and branch_id in recorded_travel:
            steps = recorded_travel[branch_id]
            new_travel[branch_id] = tuple(
                step + shifts[relocated[index + 1][1]]
                - shifts[relocated[index][1]]
                for index, step in enumerate(steps))
        path[:] = relocated
    if new_travel is not None:
        database.signed_travel = new_travel
    if hasattr(database, 'series_connections'):
        database.series_connections = [dict(
            bridge, start=relocate(bridge['start']),
            end=relocate(bridge['end']))
            for bridge in database.series_connections]
    if hasattr(database, 'transposition_report'):
        details = deepcopy(database.transposition_report)
        for edge in details.get('edges', ()):
            original_from, original_to = edge['from'], edge['to']
            edge['from'], edge['to'] = (relocate(original_from),
                                        relocate(original_to))
            edge['canonical_signed_pitch'] = edge['signed_pitch']
            edge['signed_pitch'] += (shifts[edge['to'][1]]
                                     - shifts[edge['from'][1]])
            edge['base_pitch_reference'] = 'before shift'
        for exchange in details.get('exchanges', ()):
            exchange['conductors'] = [relocate(node)
                                      for node in exchange['conductors']]
            exchange['weld_pairs'] = [[relocate(node) for node in pair]
                                      for pair in exchange['weld_pairs']]
        details['coordinate_reference'] = 'after shift'
        database.transposition_report = details
    for attribute in ('sector_deployment_report', 'indexed_sector_deployment',
                      'half_turn_deployment'):
        if hasattr(database, attribute):
            deployment = deepcopy(getattr(database, attribute))
            for key in ('source_starts', 'starts'):
                if key in deployment:
                    deployment[key] = [relocate(node) for node in deployment[key]]
            setattr(database, attribute, deployment)

    shifted_starts = [path[0] for _branch_id, path in database]
    _validate_generated_layout_consistency(pattern, shifted_starts, database, winding)
    report = fractional_uwp_candidate_report(database, winding, layout)
    if not report['layout_retained']:
        kind = ('electrical' if set(report['errors']) == {'zero_fundamental'}
                else 'conductor or phase')
        raise ValueError(f'Post-connection shift failed {kind} validation: '
                         + ', '.join(report['errors']))
    for key in ('pattern_identity', 'pattern_route'):
        if key in base_report:
            report[key] = base_report[key]
    if hasattr(database, 'sector_deployment_report'):
        report['sector_deployment'] = database.sector_deployment_report
    report['post_connection_shift'] = {
        'phase_shift_list': tuple(shifts),
        'radial_shift': bool(layout.radial_shift),
        'connection_validation': 'before shift',
    }
    database.layout_report = report
    database.layout_status = report['layout_status']
    database._post_shift_identity_snapshot = tuple(
        (branch_id, tuple(tuple(node) for node in path))
        for branch_id, path in database)
    from layout_analysis import _post_shift_identity_context
    database._post_shift_identity_context = _post_shift_identity_context(
        winding, layout)
    return shifted_starts, database


def get_winding_layout(pattern_name,TP_info,Winding_Para,Layout_Para,
                       allow_candidate=False):
    pattern_name = normalize_pattern_name(pattern_name, allow_extra=True)
    _validate_basic_winding_parameters(pattern_name, Winding_Para)
    if (pattern_name in PATTERN_REGISTRY
            and _post_connection_shift_requested(Layout_Para, Winding_Para)):
        neutral_layout = _without_post_connection_shifts(Layout_Para, Winding_Para)
        starts, database = get_winding_layout(
            pattern_name, TP_info, Winding_Para, neutral_layout,
            allow_candidate=allow_candidate)
        return _apply_post_connection_shifts(
            pattern_name, starts, database, Winding_Para, Layout_Para)
    topology = None
    if pattern_name in PATTERN_REGISTRY:
        try:
            topology = _phase_topology_for_winding(Winding_Para, Layout_Para)
        except (TypeError, ValueError, ZeroDivisionError) as exc:
            phases = getattr(Winding_Para, 'num_phases', 0)
            if not supports_phase_count(phases):
                category = 'unsupported_phase_count'
            elif (three_phase_set_count(phases) > 1
                  and not supports_phase_layer_allocation(
                      phases, getattr(Winding_Para, 'num_layers', 0))):
                category = 'unsupported_phase_layer_allocation'
            else:
                category = 'phase_division_infeasible'
            _raise_pattern_error(category, str(exc), pattern_name)
    pre_decision = _validate_branch_decomposition(
        pattern_name, Winding_Para, TP_info, Layout_Para, topology)
    _validate_pattern_specific_configuration(
        pattern_name, Winding_Para, Layout_Para, topology)
    if pre_decision is not None:
        route_decision = pre_decision
    elif (pattern_name == 'manual'
            or Fraction(str(Winding_Para.q)).denominator != 1):
        route_decision = PatternRouteDecision(
            'enabled', f'{pattern_name}_legacy',
            'Legacy manual or fractional candidate route.', pattern_name,
            None, route_name=None)
    else:
        route_decision = resolve_pattern_route(
            pattern_name, Winding_Para,
            getattr(Winding_Para, 'branch_dividers', None), TP_info, Layout_Para,
            topology=topology)
    if route_decision.status == 'disabled':
        _raise_pattern_error(
            'pattern_specific_infeasible', route_decision.reason, pattern_name)
    selected_route = route_decision.route_name
    if (auto_tp.is_auto_type(getattr(TP_info, 'tp_type', 'Regular'))
            and _effective_tp_type(TP_info, Winding_Para) != 'Regular'
            and selected_route != 'uwp_balanced_q'):
        _raise_pattern_error('invalid_transposition',
                             'Auto requires a supported automatic transposition route.', pattern_name)
    TP_info = _normalized_tp_info(TP_info, Winding_Para)
    configurable_uwp_pp = (pattern_name == 'UWP' and (
        selected_route == 'pp_only' or uses_uwp_complementary_q_pp(Winding_Para)))
    auto_configuration_recipe = (
        getattr(TP_info, '_auto_configuration_token', None)
        is _AUTO_CONFIGURATION_TOKEN
        and getattr(TP_info, 'auto_configuration_rule', None)
        == f'{pattern_name.lower()}_geometry_recipe')
    fractional_route = Fraction(str(Winding_Para.q)).denominator == 2
    if fractional_route:
        selected_configuration_ok = True
    elif selected_route == 'bwp_q_pp':
        selected_configuration_ok = (
            _bwp_q_pp_configuration_failure(
                TP_info, Layout_Para, Winding_Para) is None)
    elif selected_route == 'uwp_short_p2_weld':
        selected_configuration_ok = _configuration_is_neutral(
            TP_info, Layout_Para, weld_side=True, winding=Winding_Para)
    elif pattern_name not in ('BWP', 'UWP'):
        selected_configuration_ok = _layout_configuration_is_neutral(
            Layout_Para,
            weld_side=(bool(Layout_Para.inlet_from_weld_side)
                       if pattern_name == 'SLP'
                       and route_decision.required_inlet == 'weld'
                       else pattern_requires_weld_side_inlet(pattern_name)),
            winding=Winding_Para)
    else:
        selected_configuration_ok = pp_only_configuration_is_unshifted(
            TP_info, Layout_Para, weld_side=(selected_route == 'zpp'))
    if (not fractional_route and not auto_configuration_recipe and not configurable_uwp_pp
            and not (pattern_name == 'SLP' and selected_route == 'pp_only')
            and selected_route not in (None, 'bwp_pp', 'uwp_balanced_q',
                                       'zlp_p2_mirrored',
                                       'zlp_pp_p2_source_cut',
                                       'uwp_half_integer_q_pp')
            and not selected_configuration_ok):
        _raise_pattern_error(
            'pattern_specific_infeasible',
            'This selected divider route requires supported shifts and the required inlet side.',
            pattern_name)

    try:
        result = _dispatch_winding_pattern(
            pattern_name, TP_info, Winding_Para, Layout_Para,
            route_decision=route_decision, topology=topology)
        if result is None:
            _raise_pattern_error(
                "pattern_specific_infeasible",
                "the selected pattern returned no layout for these parameters.",
                pattern_name,
            )
        start_conductor_ids, db_conductor_id = result
        _validate_generated_layout_consistency(pattern_name, start_conductor_ids, db_conductor_id, Winding_Para)
        _validate_route_connections(
            pattern_name, route_decision, db_conductor_id,
            Winding_Para, Layout_Para, topology)
        # Defaults and selected routes share the same Pattern identity gate.
        if uses_p2_divider(pattern_name, Winding_Para):
            start_conductor_ids, db_conductor_id = orient_p2_branches_n_to_s(
                db_conductor_id, Winding_Para, Layout_Para)
        report = fractional_uwp_candidate_report(db_conductor_id, Winding_Para, Layout_Para)
        if not isinstance(db_conductor_id, _CandidateBranches):
            db_conductor_id = _CandidateBranches(db_conductor_id)
        ordered_identity_domain = (
            Fraction(str(Winding_Para.q)).denominator in (1, 2)
            and Winding_Para.num_layers >= 2
            and Winding_Para.num_layers % 2 == 0
            and supports_phase_count(Winding_Para.num_phases))
        if (ordered_identity_domain or selected_route == 'bwp_q_pp' or pattern_name in
                ('SSP', 'SLP', 'TSP', 'TLP', 'ZLP', 'ZPP', 'CP', 'LPP')):
            identity = _analyze_pattern_identity_for_sets(
                pattern_name, db_conductor_id, Winding_Para, Layout_Para,
                topology)
            if identity['status'] == 'candidate' and not allow_candidate:
                _raise_pattern_error(
                    'pattern_identity_candidate',
                    'Generated layout is isolated as Candidate: ' + identity['reason'],
                    pattern_name)
            report['pattern_identity'] = identity
        report['pattern_route'] = {
            'rule_id': route_decision.rule_id,
            'status': route_decision.status,
            'admission': route_decision.admission,
            'reason': route_decision.reason,
            'dividers': route_decision.dividers,
            'route_name': route_decision.route_name,
            'pin_profile': route_decision.pin_profile,
            'required_inlet': route_decision.required_inlet,
        }
        if hasattr(db_conductor_id, 'sector_deployment_report'):
            report['sector_deployment'] = dict(
                db_conductor_id.sector_deployment_report,
                starts=[tuple(path[0]) for _, path in db_conductor_id])
        db_conductor_id.layout_report = report
        db_conductor_id.layout_status = report['layout_status']
        return start_conductor_ids, db_conductor_id
    except PatternConfigurationError:
        raise
    except ValueError as exc:
        if "transposition" in str(exc).lower():
            raise PatternConfigurationError("invalid_transposition", str(exc), pattern_name) from exc
        raise PatternConfigurationError("generated_layout_sequence", str(exc), pattern_name) from exc


    except IndexError as exc:
        raise PatternConfigurationError(
            "generated_layout_sequence",
            "generated conductor sequence references an unavailable slot/layer. Try a different branch count, pole count, layer count, or pattern.",
            pattern_name,
        ) from exc
    except ZeroDivisionError as exc:
        raise PatternConfigurationError(
            "invalid_parameter",
            "parameter combination caused division by zero during layout generation.",
            pattern_name,
        ) from exc
    except UnboundLocalError as exc:
        raise PatternConfigurationError(
            "generated_layout_sequence",
            "the selected parameters left part of the layout sequence undefined.",
            pattern_name,
        ) from exc
    except TypeError as exc:
        if "NoneType" in str(exc):
            raise PatternConfigurationError(
                "pattern_specific_infeasible",
                "the selected pattern did not produce a complete layout for these parameters.",
                pattern_name,
            ) from exc
        raise PatternConfigurationError("generated_layout_sequence", str(exc), pattern_name) from exc


def evaluate_base_pattern_support(pattern_name, q, poles, naa, layers, phases=3):
    """Probe a Pattern using only its base winding dimensions.

    Regular/no transposition, unshifted layers and each Pattern's required
    inlet side form a reproducible baseline. Other layout settings may change
    whether the eventual drawing succeeds.
    """
    try:
        pattern = normalize_pattern_name(pattern_name, allow_extra=False)
        q = Fraction(str(q))
        if any(value <= 0 or type(value) is not int
               for value in (poles, naa, layers, phases)):
            raise ValueError('q, poles, Naa, layers and phases must be positive.')
        slots = q * poles * phases
        if q <= 0 or slots.denominator != 1 or poles % 2:
            raise ValueError('q must give an integer slot count with positive even poles.')
        if slots * layers > 20000:
            return False, 'Base Pattern preview exceeds the interactive size limit.'
        candidate_winding = SimpleNamespace(q=q, ab=naa)
        if (q.denominator != 1
                and not is_half_integer_uwp_2q(pattern, candidate_winding)
                and not is_fractional_bwp_single_branch(pattern, candidate_winding)
                and not is_fractional_sector_array_candidate(
                    pattern, SimpleNamespace(q=q, ab=naa, num_poles=poles))):
            return False, ('fractional-q Pattern selection currently supports only '
                           'half-integer UWP with Naa=2q or supported half-integer '
                           'BWP sector candidates.')
        winding = SimpleNamespace(q=int(q) if q.denominator == 1 else q,
                                   num_slots=int(slots), num_poles=poles,
                                   num_phases=phases, num_layers=layers, ab=naa)
        required_uwp_dividers = (preferred_uwp_q_dividers(
            winding.q, poles, layers, phases, naa) if pattern == 'UWP' else None)
        if required_uwp_dividers is not None:
            winding.branch_dividers = required_uwp_dividers
        elif q.denominator == 1:
            winding.branch_dividers = branch_dividers_for_pattern(pattern, winding)
        transposition = SimpleNamespace(tp_type='Regular', tp_interval=0,
                                        tp_times=0, uni_tp=0, pltp_fl=0,
                                        pltp_ll=0, jltp=0, jld=1)
        layout = SimpleNamespace(phase_shift_list=[0] * layers, radial_shift=0,
                                 inlet_from_weld_side=int(
                                     pattern_requires_weld_side_inlet(pattern)))
        starts, database = get_winding_layout(pattern, transposition, winding, layout)
    except (ValueError, TypeError, IndexError, ZeroDivisionError) as exc:
        return False, str(exc)
    if q.denominator != 1:
        if (is_fractional_bwp_single_branch(pattern, winding)
                or is_fractional_sector_array_candidate(pattern, winding)):
            return True, f'{pattern} sector candidate available for inspection; no transposition or radial swap.'
        swap = assess_fractional_uwp_pair_swap(
            starts, database, winding, layout)
        return True, ('Candidate layout available; parallel EMF needs separate '
                      'review. ' + swap['reason'])
    if required_uwp_dividers is not None:
        if selected_integer_divider_route(pattern, winding) == 'uwp_balanced_q':
            return True, ('UWP automatic balance requires selected dividers (Q, PP, P2)='
                          f'{required_uwp_dividers}; transposition and branch starts are derived automatically.')
        return True, ('UWP base layout requires selected dividers (Q, PP, P2)='
                      f'{required_uwp_dividers}, regular connections and no shifts.')
    return True, ('Base layout available; transposition, shifts, inlet and other '
                  'layout settings may still affect generation.')

def get_db_cond_id_from_connection(start_conductor_ids,Connection,Winding_Para, Layout_Para): 
    n_branch = 1
    db_conductor_id = []
    for start_conductor_id in start_conductor_ids:
        slot,layer,phasor = start_conductor_id
        end_conductor_id,group_conductors_id = get_branch_connections(start_conductor_id, Connection, Winding_Para, Layout_Para)
        db_conductor_id.append([n_branch,group_conductors_id])
        n_branch += 1
    return db_conductor_id

def get_phaseA_winding_layout(pattern_name,TP_info,Winding_Para,Layout_Para):
    pattern_name = normalize_pattern_name(pattern_name, allow_extra=True)
    start_conductor_ids, db_conductor_id = get_winding_layout(pattern_name,TP_info,Winding_Para,Layout_Para)
    try:
        topology = _phase_topology_for_winding(Winding_Para, Layout_Para)
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        _raise_pattern_error(
            "phase_division_infeasible",
            f"phase topology is invalid for the selected slots, poles, phases, and layers: {exc}",
            pattern_name,
        )
    phase_A_conductor_id = []
    try:
        for i in range(len(start_conductor_ids)):
            cond = start_conductor_ids[i]
            slot,layer,phasor = cond
            phase = topology.phase_of(slot, layer)
            if phase == 0:  ####if branch belongs to phase A
                phase_A_conductor_id.append(db_conductor_id[i])
    except IndexError as exc:
        raise PatternConfigurationError(
            "generated_layout_sequence",
            "generated phase-A sequence references an unavailable slot/layer.",
            pattern_name,
        ) from exc
    return  phase_A_conductor_id

def get_branch_connections(start_conductor_id,Connection,Winding_Para,Layout_Para):
    group_cond_ids = []
    group_cond_ids.append(start_conductor_id)
    for conn in Connection:
        direction = conn[0]
        ltp = conn[1]
        ptp = conn[2]
        start_slot,start_layer,start_phasor = start_conductor_id
        end_conductor_id = get_next_conductor_id(start_conductor_id, Winding_Para, Layout_Para, direction, ltp, ptp)
        group_cond_ids.append(end_conductor_id)
        start_conductor_id = end_conductor_id
    return start_conductor_id,group_cond_ids
    
def get_phase_shift_list(Winding_Para,phase_shift_pattern,phase_shift,PSL,log=print):
    if PSL < 0 or int(PSL) != PSL or int(phase_shift) != phase_shift:
        raise ValueError('PSL must be nonnegative and slot shift must be an integer.')
    if phase_shift_pattern not in ('None', 'Normal', 'Increment'):
        raise ValueError('Unknown phase shift pattern.')
    num_layers = Winding_Para.num_layers
    phase_shift_list = [0] * num_layers   # default
    if phase_shift_pattern == 'Normal' and PSL != 0:
        if phase_shift == 0:
            log("⚠️ Warning: phase_shift = 0, please set phase_shift value.")
        pattern = [0] * PSL + [phase_shift] * PSL
        full_patterns = num_layers // len(pattern)  # how many full repeats
        remainder = num_layers % len(pattern)       # leftover layers
        if remainder != 0:
            log(f"⚠️ Warning: num_layers={num_layers} is not a multiple of {len(pattern)} (2*PSL). "
                  f"Will truncate the pattern for the last {remainder} layers.")
        # Build the final list
        phase_shift_list = pattern * full_patterns + pattern[:remainder]
    # -------- increment pattern --------
    elif phase_shift_pattern == 'Increment' and PSL != 0:
        if phase_shift == 0:
            log("⚠️ Warning: phase_shift = 0, please set phase_shift value.")
        phase_shift_list = []
        remainder = num_layers % PSL
        if remainder != 0:
            log(f"⚠️ Warning: num_layers={num_layers} is not a multiple of PSL={PSL}. "
                  f"Last group will be truncated.")
        for layer in range(num_layers):
            phase_shift_list.append(phase_shift*(layer // PSL))
    return phase_shift_list

def Winding_Phase_division(Winding_Para,Layout_Para,log=print):  ####[slot,layer,phase,branch,kd,kc]
    num_slots = Winding_Para.num_slots
    num_phases = Winding_Para.num_phases
    num_layers = Winding_Para.num_layers
    num_poles = Winding_Para.num_poles
    phase_shift_list = Layout_Para.phase_shift_list
    result = phase_division_feasibility(
        num_slots, num_poles, num_layers, num_phases, phase_shift_list)
    if not result.feasible:
        log("⚠️ Warning: Phase division is not feasible for the supplied topology.")
        log(f"  Slots: {num_slots}, Poles: {num_poles}, Phases: {num_phases}, "
            f"Layers: {num_layers}")
        if result.q is not None:
            log(f"  q (slots per pole per phase) = "
                f"{result.q.numerator}/{result.q.denominator}: {result.reason}")
        else:
            log(f"  {result.reason}")
        return None
    try:
        return legacy_cond_info(result.topology)
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        log(f"⚠️ Warning: Legacy conductor adapter failed: {exc}")
        return None


#### After the winding division, the winding factor can be calculated, since we already know how many conductors per slot we have for each slot, this information are collected in the Cond_info. structure of the Cond_info: (slot, layer, phase_index, 0, 0, 0, pole_index). Each conductor has its own MMF. or we can pair the positive and negative conductors. 


