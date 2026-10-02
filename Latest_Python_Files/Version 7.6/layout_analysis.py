# -*- coding: utf-8 -*-
"""
Created on Mon Jun 24 09:33:48 2024

@author: ezzhh5
"""
import csv_operation as csvo
import end_winding_calc as ewc
from collections import Counter
import phase_topology


def _phase_label(index):
    return chr(ord('A') + index) if 0 <= index < 26 else f'P{index + 1}'


def cal_slot_position(num_slots, slot1, slot2, position):
    """
    Calculate the slot number at a given position between two slots on a circular slot system.
    
    :param num_slots: Total number of slots.
    :param slot1: First slot number.
    :param slot2: Second slot number.
    :param position: Position between slot1 and slot2 (0 to 1, where 0 is slot1 and 1 is slot2).
    :return: Calculated slot number at the given position.
    """
    # Ensure slot1 is less than slot2 for consistent calculations
    if slot1 > slot2:
        slot1, slot2 = slot2, slot1
    # Calculate direct distance and circular distance
    direct_distance = slot2 - slot1
    circular_distance = num_slots - direct_distance

    # Determine if we should go clockwise or counterclockwise
    if direct_distance <= circular_distance:
        target_slot = slot1 + position * direct_distance
    else:
        target_slot = slot1 - position * circular_distance
        if target_slot < 0:
            target_slot += num_slots
    return round(target_slot % num_slots,2)

def abs_circular_distance(num_slots, slot1, slot2):
    """
    Calculate the distance between two slots in a circular slot system.
    
    :param num_slots: Total number of slots.
    :param slot1: First slot number.
    :param slot2: Second slot number.
    :return: The minimum distance between the two slots.
    """
    # Calculate direct distance
    direct_distance = abs(slot1 - slot2)
    # Calculate circular distance
    circular_distance = num_slots - direct_distance
    # Return the minimum of the two distances
    return min(direct_distance, circular_distance)

def signed_circular_distance(num_slots, slot1, slot2):
    """
    Calculate the signed distance between two slots in a circular slot system.
    
    :param num_slots: Total number of slots.
    :param slot1: First slot number.
    :param slot2: Second slot number.
    :return: The signed distance between slot1 and slot2.
             Positive value indicates the distance from slot2 to slot1 clockwise, 
             Negative value indicates the distance from slot2 to slot1 counterclockwise.
    """
    # Calculate clockwise distance
    clockwise_distance = (slot1 - slot2) % num_slots
    
    # Calculate counterclockwise distance
    counterclockwise_distance = (slot2 - slot1) % num_slots
    
    # Choose the direction based on the actual shorter distance
    if clockwise_distance <= counterclockwise_distance:
        return clockwise_distance
    else:
        return -counterclockwise_distance


def _pattern_pin_family(Layout_Para):
    pattern = str(getattr(Layout_Para, "pattern_name", "")).strip().upper()
    if pattern in ("SLP", "ZLP", "TLP"):
        return "lap"
    if pattern in ("ZPP", "LPP"):
        return "parallel"
    return "wave"


def get_pin_type_abbr(pin_shape, Layout_Para=None):
    layer_a, layer_b, _slot_span = pin_shape
    layer_span = abs(layer_b - layer_a)
    family = _pattern_pin_family(Layout_Para)

    if layer_span == 0:
        return "SLPP"
    if layer_span == 1:
        if family == "lap":
            return "ALLP"
        if family == "parallel":
            return "ALPP"
        return "ALWP"
    if family == "lap":
        return "CLLP"
    return "CLWP"


PATTERN_BODY_PIN_PROFILES = {
    "BWP": frozenset(("ALWP", "SLPP")),
    "UWP": frozenset(("ALWP",)),
    "SSP": frozenset(("ALWP", "SLPP")),
    "SLP": frozenset(("ALLP", "SLPP")),
    "TSP": frozenset(("ALWP", "CLWP")),
    "TLP": frozenset(("ALLP", "CLLP")),
    "ZLP": frozenset(("ALLP", "SLPP")),
    "ZPP": frozenset(("SLPP",)),
    "CP": frozenset(("CLWP",)),
    "LPP": frozenset(("SLPP",)),
}

# Legacy-domain evidence hints. The integer/even-layer ordered recognizer does
# not require an optional return Pin to occur in a divider child.
PATTERN_REQUIRED_BODY_PIN_TYPES = {
    "BWP": frozenset(("ALWP",)),
    "UWP": frozenset(("ALWP",)),
    "SSP": frozenset(("ALWP",)),
    "SLP": frozenset(("ALLP",)),
    "TSP": frozenset(("ALWP", "CLWP")),
    "TLP": frozenset(("ALLP",)),
    "ZLP": frozenset(("ALLP",)),
    "ZPP": frozenset(("SLPP",)),
    "CP": frozenset(("CLWP",)),
    "LPP": frozenset(("SLPP",)),
}


def _insertion_pin_type(pattern, layer_step, num_layers):
    """Classify an observed insertion edge without relabeling its layer span."""
    span = abs(layer_step)
    if span == 0:
        return "SLPP"
    if pattern == "CP" and span == num_layers // 2:
        return "CLWP"
    if span == 1:
        if pattern in ("SLP", "ZLP", "TLP"):
            return "ALLP"
        if pattern in ("ZPP", "LPP"):
            return "ALPP"
        return "ALWP"
    return "CLLP" if pattern == "TLP" else "CLWP"


def _analyze_pin_inventory(pattern, database, winding, layout):
    """Derive body pin inventory from actual insertion edges.

    Stored conductor paths alternate insertion and weld edges.  The starting
    side and each odd inlet-index adjustment determine that parity.  Terminal
    I-pins are reported separately and never counted as body pin types.
    """
    pattern = str(pattern).strip().upper()
    expected = PATTERN_BODY_PIN_PROFILES.get(pattern, frozenset())
    pin_types = Counter()
    insertion_edges = []
    weld_edges = []
    adjustments = tuple(getattr(
        layout, "inlet_index_adjustments_phase_a", ()) or ())
    branches_per_phase = max(int(getattr(winding, "ab", 1)), 1)
    base_insert_parity = (0 if getattr(layout, "inlet_from_weld_side", 0)
                          else 1)

    for branch_index, (_branch_id, path) in enumerate(database):
        phase_branch = branch_index % branches_per_phase
        adjustment = (adjustments[phase_branch]
                      if phase_branch < len(adjustments) else 0)
        insert_parity = (1 - base_insert_parity
                         if int(adjustment) % 2 else base_insert_parity)
        for edge_index, (start, end) in enumerate(zip(path, path[1:])):
            slot_step = signed_circular_distance(
                winding.num_slots, end[0], start[0])
            layer_step = end[1] - start[1]
            edge = {
                "branch": branch_index + 1,
                "edge_index": edge_index,
                "start_layer": start[1],
                "end_layer": end[1],
                "slot_step": slot_step,
                "layer_step": layer_step,
            }
            if pattern == "ZLP":
                shifts = layout.phase_shift_list
                edge["unshifted_slot_step"] = signed_circular_distance(
                    winding.num_slots,
                    end[0] - shifts[end[1]],
                    start[0] - shifts[start[1]])
            if edge_index % 2 == insert_parity:
                pin_type = _insertion_pin_type(
                    pattern, layer_step, winding.num_layers)
                pin_types[pin_type] += 1
                edge["pin_type"] = pin_type
                insertion_edges.append(edge)
            else:
                weld_edges.append(edge)

    actual = frozenset(pin_types)
    tau = int(winding.num_phases * winding.q)
    paired_pitch = (winding.num_phases - 1) * winding.q + 1
    has_pair_local_zigzag = any(
        abs(edge.get("unshifted_slot_step", edge["slot_step"])) == paired_pitch
        and abs(edge["layer_step"]) == 1
        for edge in insertion_edges)
    has_signed_lap_pass = bool(insertion_edges) and all(
        not edge["layer_step"]
        or edge["slot_step"] == -edge["layer_step"] * tau
        for edge in insertion_edges)
    layer_directions = {}
    for edge in insertion_edges:
        if edge["slot_step"]:
            direction = 1 if edge["slot_step"] > 0 else -1
            layer_directions.setdefault(edge["start_layer"], set()).add(direction)

    def layer_pairs_are(opposite):
        for first_layer in range(0, winding.num_layers, 2):
            first = layer_directions.get(first_layer, set())
            second = layer_directions.get(first_layer + 1, set())
            if not first or not second:
                return False
            relations = {a != b for a in first for b in second}
            if relations != {opposite}:
                return False
        return True

    lpp_opposite_pairs = layer_pairs_are(True)
    zpp_same_pairs = layer_pairs_are(False)
    topology_issues = []
    if pattern == "SSP" and any(
            edge["layer_step"] and
            edge["slot_step"] != edge["layer_step"] * tau
            for edge in insertion_edges):
        topology_issues.append("spiral pass direction changed")
    if pattern == "SLP" and any(
            edge["layer_step"] and
            edge["slot_step"] != -edge["layer_step"] * tau
            for edge in insertion_edges):
        topology_issues.append("lap pass direction changed")
    if pattern == "TLP":
        # Divider children may contain a complete lap pass without its
        # long-parent return. Check every remaining ordered connection.
        if any(abs(edge["layer_step"]) not in (1, winding.num_layers - 1)
               for edge in insertion_edges):
            topology_issues.append("lap insertion has an invalid layer span")
        if any(abs(edge["layer_step"]) == 1 and
               not (edge["slot_step"] == -edge["layer_step"] * tau or
                    (winding.num_slots == 2 * tau and
                     abs(edge["slot_step"]) == tau))
               for edge in insertion_edges):
            topology_issues.append("lap pass direction changed")
        if any(abs(edge["layer_step"]) != 1 or
               abs(edge["slot_step"]) != tau for edge in weld_edges):
            topology_issues.append("lap weld connection changed")
    if pattern == "TSP" and not any(
            abs(edge["layer_step"]) == winding.num_layers - 1
            for edge in insertion_edges):
        topology_issues.append("top-bottom return span is missing")
    if pattern == "ZLP":
        if not has_pair_local_zigzag:
            topology_issues.append("pair-local zigzag edge is missing")
    if pattern == "CP" and any(
            abs(edge["layer_step"]) != winding.num_layers // 2
            for edge in insertion_edges):
        topology_issues.append("body insertion no longer spans L/2")
    if pattern in ("ZPP", "LPP") and any(
            edge["layer_step"] != 0 for edge in insertion_edges):
        topology_issues.append("parallel body gained a cross-layer insertion")
    if pattern == "LPP":
        if not lpp_opposite_pairs:
            topology_issues.append("layer-pair loops lost opposite directions")
    unexpected = tuple(sorted(actual - expected))
    required = PATTERN_REQUIRED_BODY_PIN_TYPES.get(pattern, expected)
    missing = tuple(sorted(required - actual))
    matching_profiles = []
    if actual == PATTERN_BODY_PIN_PROFILES["ZLP"]:
        if pattern != "ZLP" and has_pair_local_zigzag:
            matching_profiles.append("ZLP")
        if pattern != "SLP" and has_signed_lap_pass:
            matching_profiles.append("SLP")
    if actual == PATTERN_BODY_PIN_PROFILES["ZPP"]:
        if pattern != "LPP" and lpp_opposite_pairs:
            matching_profiles.append("LPP")
        if pattern != "ZPP" and zpp_same_pairs:
            matching_profiles.append("ZPP")
    matching_profiles = tuple(sorted(matching_profiles))
    degenerate_two_layer_profile = (
        winding.num_layers == 2 and actual == frozenset(("SLPP",)))
    legacy_odd_layer_profile = winding.num_layers % 2 == 1
    status = ("candidate"
              if unexpected or ((matching_profiles or missing or topology_issues)
                                and not degenerate_two_layer_profile
                                and not legacy_odd_layer_profile)
              else "valid")
    terminal_i_pins = (0 if getattr(layout, "inlet_from_weld_side", 0)
                       else 2 * len(database))
    reasons = []
    if unexpected:
        reasons.append("unexpected body pin types: " + ", ".join(unexpected))
    if missing:
        reasons.append("missing required body pin types: " + ", ".join(missing))
    if topology_issues:
        reasons.append("; ".join(topology_issues))
    if matching_profiles:
        reasons.append("pin inventory also matches: " + ", ".join(matching_profiles))
    return {
        "status": status,
        "pattern": pattern,
        "pin_types": dict(sorted(pin_types.items())),
        "expected_pin_types": tuple(sorted(expected)),
        "unexpected_pin_types": unexpected,
        "missing_pin_types": missing,
        "topology_issues": tuple(topology_issues),
        "terminal_i_pins": terminal_i_pins,
        "matching_profiles": matching_profiles,
        "identity_confidence": ("degenerate-two-layer"
                                if degenerate_two_layer_profile else
                                "legacy-odd-layer"
                                if legacy_odd_layer_profile else "full"),
        "insertion_edges": insertion_edges,
        "weld_edges": weld_edges,
        "reason": "; ".join(reasons) if reasons else
                  "Observed body pin inventory matches the Pattern contract.",
    }


def _post_shift_identity_context(winding, layout):
    winding_values = tuple(getattr(winding, key, None) for key in (
        'q', 'num_slots', 'num_poles', 'num_layers', 'num_phases', 'ab'))
    return (winding_values,
            tuple(getattr(winding, 'branch_dividers', ()) or ()),
            getattr(layout, 'inlet_from_weld_side', 0),
            tuple(getattr(layout, 'inlet_index_adjustments_phase_a', ()) or ()),
            getattr(layout, 'in_out_connection', 0))


def _validated_post_shift_identity(pattern, database, winding, layout):
    generated = getattr(database, 'layout_report', {})
    if not isinstance(generated, dict):
        return None
    relocation = generated.get('post_connection_shift')
    prior_identity = generated.get('pattern_identity')
    snapshot = getattr(database, '_post_shift_identity_snapshot', None)
    if (relocation and prior_identity and prior_identity['pattern'] == pattern
            and snapshot is not None
            and snapshot == tuple(
                (branch_id, tuple(tuple(node) for node in path))
                for branch_id, path in database)
            and getattr(database, '_post_shift_identity_context', None)
            == _post_shift_identity_context(winding, layout)
            and tuple(layout.phase_shift_list) == relocation['phase_shift_list']
            and bool(layout.radial_shift) == relocation['radial_shift']):
        return dict(prior_identity)
    return None


def analyze_pattern_identity(pattern, database, winding, layout):
    """Check ordered branches; retain pin roles as descriptive diagnostics.

    Short branches need not exhibit every return of their parent construction.
    Structural overlap in a degenerate case is not an identity rejection.
    Qualified legacy domains retain their existing checks until explicitly
    extended; they are not certified by the integer/even-layer recognizer.
    """
    from pattern_identity import analyze_ordered_pattern

    prior_identity = _validated_post_shift_identity(
        pattern, database, winding, layout)
    if prior_identity is not None:
        return prior_identity

    report = _analyze_pin_inventory(pattern, database, winding, layout)
    ordered = analyze_ordered_pattern(pattern, database, winding, layout)
    report['ordered_identity'] = ordered
    report['identity_basis'] = 'ordered layer traversal and connection sequence'
    if ordered['qualification'] == 'unsupported-domain':
        report['identity_basis'] = 'qualified legacy checks; ordered domain not evaluated'
        return report

    report['absent_body_pin_types'] = report['missing_pin_types']
    report['missing_pin_types'] = ()
    report['status'] = ordered['ordered_status']
    report['topology_issues'] = ordered['errors']
    report['compatible_patterns'] = ordered['compatible_patterns']
    report['matching_profiles'] = tuple(
        code for code in ordered['compatible_patterns'] if code != report['pattern'])
    report['branch_identity'] = ordered['branch_reports']
    report['degeneracy'] = ordered['degeneracy']
    # Existing evidence binders use "full" to mean a completed passing check.
    # Overlap concerns distinguishability, not whether every edge was checked.
    report['identity_confidence'] = (
        'full' if ordered['ordered_status'] == 'valid' else 'incomplete-ordered-check')
    report['identity_distinguishability'] = (
        'compatible-signatures' if ordered['degeneracy'] else 'single-observed-signature')
    report['reason'] = ('; '.join(ordered['errors']) if ordered['errors'] else
                        'Every branch preserves the ordered Pattern construction; '
                        'optional missing returns and degenerate overlap are allowed.')
    return report


def analyze_database(database, Winding_Para, Layout_Para, odd=True):
    num_slots = Winding_Para.num_slots
    num_layers = Winding_Para.num_layers
    results = []
    all_pin_shapes = {}  # Store all branch pin shapes with counts
    all_pin_shape_types = {}
    all_weld_shapes = {} # Store all branch weld shapes with counts
    total_slot_distance_all = 0
    conductor_count_all = 0
    # inlet_from_weld_side and per-branch inlet index adjustments rotate the
    # branch start, so insertion-side pin parity follows those shifts.
    base_pin_side_mod = 0 if getattr(Layout_Para, "inlet_from_weld_side", 0) == 1 else 1
    phase_a_adjustments = list(getattr(Layout_Para, "inlet_index_adjustments_phase_a", []))
    
    for phase_a_index, branch_info in enumerate(database[:Winding_Para.ab]): 
        n_branch, group_conductors_id = branch_info
        adjustment = phase_a_adjustments[phase_a_index] if phase_a_index < len(phase_a_adjustments) else 0
        pin_side_mod = 1 - base_pin_side_mod if int(adjustment) % 2 != 0 else base_pin_side_mod
        pin_shapes = {}
        weld_shapes = {}
        total_slot_distance = 0
        conductor_count = 0
        
        # Calculate the connection between the last and the first conductor if required
        if Layout_Para.in_out_connection == 1:
            i = len(group_conductors_id) - 1  # Last conductor index
            a, b = sorted([group_conductors_id[i][1], group_conductors_id[0][1]])
            y = abs(group_conductors_id[i][0] - group_conductors_id[0][0]) % num_slots
            y = min(y, num_slots - y)
            if i % 2 == pin_side_mod:
                pin_key = (a, b, y)
                pin_shapes[pin_key] = pin_shapes.get(pin_key, 0) + 1
            total_slot_distance += y
            conductor_count += 1
        else:
            conductor_count += 1

        for i in range(len(group_conductors_id) - 1):
            a, b = sorted([group_conductors_id[i][1], group_conductors_id[i+1][1]])
            y = abs(group_conductors_id[i][0] - group_conductors_id[i+1][0]) % num_slots
            y = min(y, num_slots - y)
            if i % 2 == pin_side_mod:
                pin_key = (a, b, y)
                pin_shapes[pin_key] = pin_shapes.get(pin_key, 0) + 1
            else:
                weld_key = (a, b, y)
                weld_shapes[weld_key] = weld_shapes.get(weld_key,0) + 1
            total_slot_distance += y
            conductor_count += 1

        num_pin_shapes = len(pin_shapes)
        num_weld_shapes = len(weld_shapes)

        conductor_info = []
        for phasor_layer in set([(c[2], c[1]) for c in group_conductors_id]):
            num_conductor = len([c for c in group_conductors_id if c[2] == phasor_layer[0] and c[1] == phasor_layer[1]])
            conductor_info.append((phasor_layer[0], phasor_layer[1], num_conductor))

        for pin_shape, count in pin_shapes.items():
            all_pin_shapes[pin_shape] = all_pin_shapes.get(pin_shape, 0) + count
            all_pin_shape_types[pin_shape] = get_pin_type_abbr(pin_shape, Layout_Para)
        
        for weld_shape, count in weld_shapes.items():
            all_weld_shapes[weld_shape] = all_weld_shapes.get(weld_shape, 0) + count
        
        layer_weld_y_sum = [0] * num_layers
        layer_weld_count = [0] * num_layers
        
        for (a, b, y), count in all_weld_shapes.items():
            for layer in [a, b]:  # Consider both ends
                if 0 <= layer < num_layers:
                    layer_weld_y_sum[layer] += y * count
                    layer_weld_count[layer] += count
        
        # Average span per layer
        span_weld_list = []
        for i in range(num_layers):
            if layer_weld_count[i] > 0:
                avg_y = round(layer_weld_y_sum[i] / layer_weld_count[i], 3)
            else:
                avg_y = 0
            span_weld_list.append(avg_y) 
            
        total_slot_distance_all += total_slot_distance
        conductor_count_all += conductor_count
        average_slot_distance = round(total_slot_distance_all / conductor_count_all, 4) if conductor_count > 0 else 0

        # --- New code: Calculate and store positions of conductors ---
        branch_positions = {(conductor[0], conductor[1]) for conductor in group_conductors_id}

        results.append({
            'n_branch': n_branch, 
            'num_pin_shapes': num_pin_shapes, 
            'num_weld_shapes': num_weld_shapes,
            'conductor_info': conductor_info, 
            'pin_shapes': pin_shapes, 
            'pin_shape_types': {
                pin_shape: get_pin_type_abbr(pin_shape, Layout_Para)
                for pin_shape in pin_shapes
            },
            'weld_shapes': weld_shapes, 
            'average_slot_distance': average_slot_distance, 
            'total_slot_distance': total_slot_distance,
            'total_conductors': conductor_count,
            'positions': branch_positions  # New key for overlapping check
        })

    average_slot_distance_all = round(total_slot_distance_all / conductor_count_all, 4) if conductor_count_all > 0 else 0
    results.append({
        'n_branch': 'All', 
        'num_pin_shapes': len(all_pin_shapes), 
        'num_weld_shapes':len(all_weld_shapes),
        'conductor_info': [], 
        'pin_shapes': all_pin_shapes, 
        'pin_shape_types': all_pin_shape_types,
        'weld_shapes': all_weld_shapes, 
        'average_slot_distance': average_slot_distance_all, 
        'total_slot_distance': total_slot_distance_all,
        'total_conductors': conductor_count_all,
        'weld_span_list':span_weld_list
    })

    return results

def check_overlapping_positions(results):
    """
    Given the results (a list of dictionaries—each for one branch with a 'positions' key),
    check for overlapping conductor positions between branches.
    Two branches are said to overlap if they contain a (slot, layer) position in common.
    Returns a dictionary with keys as tuple pairs (branch1, branch2) and values as the overlapping positions.
    """
    branch_positions = {}
    for result in results:
        if result['n_branch'] != 'All':
            # Get the positions saved in each branch result
            branch_positions[result['n_branch']] = result.get('positions', set())
    overlaps = {}
    branch_keys = list(branch_positions.keys())
    for i in range(len(branch_keys)):
        for j in range(i + 1, len(branch_keys)):
            common = branch_positions[branch_keys[i]].intersection(branch_positions[branch_keys[j]])
            if common:
                overlaps[(branch_keys[i], branch_keys[j])] = common
    return overlaps

def check_symmetry(results):
    conductor_infos = [set(tuple(info) for info in result['conductor_info']) for result in results if result["n_branch"] != "All"]
    return all(info == conductor_infos[0] for info in conductor_infos)

def print_analysis_results(results):
    for result in results:
        if result["n_branch"] == "All":
            print(f'Number of total different pin shapes: {result["num_pin_shapes"]}')
            print(f'Span_weld_list:{result["weld_span_list"]}')
            continue  # Skip the overall summary here
        print(f'For branch number {result["n_branch"]}:')
        print(f'\tNumber of different pin shapes: {result["num_pin_shapes"]}')
        print("\tPin shapes:")
        sorted_pin_shapes = sorted(list(result['pin_shapes']), key=lambda x: x[0])
        for pin_shape in sorted_pin_shapes:
            pin_type = result.get('pin_shape_types', {}).get(pin_shape, get_pin_type_abbr(pin_shape))
            print(f'\t{pin_type}  Layer {pin_shape[0]}, Layer {pin_shape[1]}, y: {pin_shape[2]}')
        print("\tWeld shapes:")
        sorted_weld_shapes = sorted(list(result['weld_shapes']), key=lambda x: x[0])
        for weld_shape in sorted_weld_shapes:
            print(f'\tLayer {weld_shape[0]}, Layer {weld_shape[1]}, y: {weld_shape[2]}')
            
        print(f'\tAverage slot distance: {result["average_slot_distance"]}')
        print(f'\tTotal slot distance: {result["total_slot_distance"]}')
        
        sorted_conductor_info = sorted(result['conductor_info'], key=lambda x: (x[0], x[1]))
        print("\tConductor information:")
        for conductor_info in sorted_conductor_info:
            print(f'\t\tPhasor: {conductor_info[0]}, Layer: {conductor_info[1]}, Number of conductors: {conductor_info[2]}')
        print()

    if check_symmetry(results):
        print("This winding pattern features strong symmetry.")
    else:
        print("This winding pattern is not symmetric.")

    # --- Overlap check between branches ---
    overlaps = check_overlapping_positions(results)
    if overlaps:
        print("Overlapping positions found between branches:")
        for branch_pair, positions in overlaps.items():
            print(f"\tBetween branches {branch_pair[0]} and {branch_pair[1]}: positions {positions}")
    else:
        print("No overlapping positions found between branches.")
        
        
def format_analysis_results(results):
    output = []
    
    for result in results:
        # Only process Phase A (skip branches)
        if result['n_branch'] == 'All':
            output.append('Overall Results for Phase A:')

            output.append(f'Number of different pin shapes: {result["num_pin_shapes"]}')
            output.append("Pin shapes:")

            sorted_pin_shapes = sorted(list(result['pin_shapes'].items()), key=lambda x: x[0])
            for pin_shape, count in sorted_pin_shapes:
                pin_type = result.get('pin_shape_types', {}).get(pin_shape, get_pin_type_abbr(pin_shape))
                output.append(f'\t{pin_type}  Layer {pin_shape[0]}, Layer {pin_shape[1]}, y: {pin_shape[2]}, num: {count}')

            # output.append(f'Average slot distance of pins: {result["average_slot_distance"]}')
            # output.append(f'Total slot distance of conds: {result["total_slot_distance"]}')
            # output.append(f'Total conductors of phase: {result["total_conductors"]}')
            
            sorted_conductor_info = sorted(result['conductor_info'], key=lambda x: (x[0], x[1]))
            if result['conductor_info']:
                output.append("\tConductor information:")

            for conductor_info in sorted_conductor_info:
                output.append(f'\t\tPhasor: {conductor_info[0]}, Layer: {conductor_info[1]}, Number of conductors: {conductor_info[2]}')

            output.append("")  # Blank line for spacing

    # Symmetry check
    if check_symmetry(results):
        output.append("This winding pattern features strong symmetry.")
    else:
        output.append("This winding pattern is not symmetric.")

    return "\n".join(output)  # Convert list to a formatted string


def format_fractional_candidate_analysis(database, winding, layout, report,
                                         all_branch_adjustments=None, pattern='UWP'):
    """Describe candidate pin shapes and exact branch position populations."""
    slots, poles, branches = winding.num_slots, winding.num_poles, winding.ab
    position_count, remainder = divmod(2 * slots, poles)
    if remainder:
        raise ValueError("Candidate position numbering requires an integer two-pole slot period.")
    records = phase_topology.phase_map(slots, poles, winding.num_layers,
                                       layout.phase_shift_list)
    positions = {(slot, layer): (phase, layer,
                 (poles * slot + (slots if sign == -1 else 0)) % (2 * slots),
                 slot % position_count + 1)
                 for slot, layer, phase, sign in records}
    lines = [f"{pattern} half-integer q candidate layout only. Production use is not approved.",
             f"Position IDs: P1-P{position_count} follow the physical slots in each two-pole period; L is the 1-based layer.",
             "Omitted position counts are zero."]
    phase_data = []
    for phase in range(winding.num_phases):
        phase_branches = database[phase * branches:(phase + 1) * branches]
        adjustments = (all_branch_adjustments[phase * branches:(phase + 1) * branches]
                       if all_branch_adjustments is not None else
                       layout.inlet_index_adjustments_phase_a if phase == 0 else ())
        phase_layout = layout._replace(inlet_index_adjustments_phase_a=tuple(adjustments))
        overall = analyze_database(phase_branches, winding, phase_layout)[-1]
        phase_data.append((phase_branches, overall))
    common_pin_shapes = all(
        (overall['pin_shapes'], overall['pin_shape_types']) ==
        (phase_data[0][1]['pin_shapes'], phase_data[0][1]['pin_shape_types'])
        for _, overall in phase_data[1:])
    for phase, (phase_branches, overall) in enumerate(phase_data):
        if phase == 0 or not common_pin_shapes:
            lines.extend(["", f"Overall Results for Phase {_phase_label(phase)}:",
                          f"Number of different pin shapes: {overall['num_pin_shapes']}",
                          "Pin shapes:"])
            for shape, count in sorted(overall['pin_shapes'].items()):
                pin_type = overall['pin_shape_types'][shape]
                lines.append(f"\t{pin_type}  Layer {shape[0]}, Layer {shape[1]}, "
                             f"y: {shape[2]}, num: {count}")
        else:
            lines.extend(["", f"Phase {_phase_label(phase)}:"])
        signed_occupied = [Counter((positions[tuple(conductor[:2])][1],
                                    positions[tuple(conductor[:2])][2])
                                   for conductor in conductors)
                           for _, conductors in phase_branches]
        occupied = [Counter((positions[tuple(conductor[:2])][1],
                             positions[tuple(conductor[:2])][3])
                            for conductor in conductors)
                    for _, conductors in phase_branches]
        strong = all(counts == signed_occupied[0] for counts in signed_occupied[1:])
        lines.append("This winding pattern features strong symmetry." if strong else
                     "This winding pattern does not feature strong symmetry.")
        if not strong:
            lines.append("Position occupancy by branch:")
            for index, counts in enumerate(occupied, 1):
                detail = "; ".join(
                    f"L{layer + 1}P{position}: {count} conds"
                    for (layer, position), count in sorted(counts.items()))
                lines.append(f"\tBranch {index}: {detail}")
        lines.append(f"Phase {_phase_label(phase)} branch complex EMF:")
        for index, (real, imag) in enumerate(report['branch_emf'][str(phase)], 1):
            lines.append(f"\tBranch {index}: {real:.6g}{imag:+.6g}j")
    lines.extend(["", "Electrical checks: " +
                  ", ".join(report['errors'] or ["no mismatch detected"])])
    return "\n".join(lines)


def print_db_conductor(db_conductor_id,Winding_Para,one_branch):
    num_slots = Winding_Para.num_slots
    for branch in db_conductor_id:
        branch_number = branch[0]
        conductors = branch[1]
        if one_branch == 0 or branch_number == 1:
            print(f"Branch Number: {branch_number}")
            print("=========================================================================")
            print("|  Slot   |  Layer  |  Phasor  | Slot Pitch | Layer Jump |Phasor Trans|")
            print("=========================================================================")      
            # 初始化前一个导体的数据
            prev_slot, prev_layer, prev_phasor = conductors[0]
            print(f"|  {prev_slot+1:^5}  |  {prev_layer+1:^5}  |  {prev_phasor+1:^6}  |            |            |            |")
            for conductor in conductors[1:]:
                slot_pitch = conductor[0] - prev_slot
                if slot_pitch > num_slots/2:
                    slot_pitch -= num_slots
                elif slot_pitch < -num_slots/2:
                    slot_pitch += num_slots        
                layer_jump = conductor[1] - prev_layer
                phasor_trans = conductor[2] - prev_phasor
                print(f"|  {conductor[0]+1:^5}  |  {conductor[1]+1:^5}  |  {conductor[2]+1:^6}  |  {slot_pitch:^8}  |  {layer_jump:^8}  |  {phasor_trans:^8}  |")
                # 更新前一个导体的数据
                prev_slot, prev_layer, prev_phasor = conductor
            print("=========================================================================\n")
      
        
      
def output_3D_pin_info(db_conductor_id,Winding_Para,Layout_Para,Stator_Para,Inslot_Para,EW_info,path):
    #### This is to output the pin info for matlab code to understand the layout of the winding;
    #### 
    # results = analyze_database(db_conductor_id, Winding_Para, Layout_Para)
    # weld_span_list = results[-1]["weld_span_list"]
    pin_info_data = []  ##### [pin_No,S_weld1,L_weld1,S_ins1,L_ins1,S_ins2,L_ins2,S_weld2,L_weld2]
    pin_info_data.append(['StackLength','Cond_OD','Cond_ID','num_Layer','Cond_Width','Cond_Height','Cond_radii','L_str','L_weld_str','g_cond_min','R_bend_side','R_bend_height','gcond_weld'])
    Rm_layer,SP_layer,Thetab_layer = ewc.calculate_layer_beta_angle(EW_info, Winding_Para,Stator_Para, Inslot_Para)
    Cond_OD = round(Rm_layer[0] * 2,2)
    Cond_ID = round(Rm_layer[-1] * 2,2)
    Cond_Width = round(Inslot_Para.Cond_Width,3) + round(Inslot_Para.Wire_Coating_Thickness,3) * 2
    Cond_Height = round(Inslot_Para.Cond_Height,3) + round(Inslot_Para.Wire_Coating_Thickness,3) * 2
    Cond_Radi = Inslot_Para.Cond_Radi
    L_str = EW_info.L_str
    L_weld_str = EW_info.L_weld_str
    g_cond_min = EW_info.gcond_min
    Rbend_side = EW_info.Rbend_side_min
    Rbend_height = EW_info.Rbend_height_min
    gcond_weld = EW_info.gcond_weld
    pin_info_data.append([Stator_Para.StackLength,Cond_OD,Cond_ID,Winding_Para.num_layers,Cond_Width,Cond_Height,Cond_Radi, L_str,L_weld_str,g_cond_min,Rbend_side,Rbend_height,gcond_weld])
    branch_number = 0
    for branch in db_conductor_id:
        branch_number += 1
        conductors = branch[1]
        if Layout_Para.inlet_from_weld_side == 0:
            side = 1
        else:
            side = 0
        conductors = branch[1]  #### Get the conductors information 
        pin_No = 1 ### Initialize the pin_no
        pin_info_data.append('')  #### Space between two branch info
        pin_info_data.append(['Phase A','BranchNo',branch_number])
        pin_info_data.append(['Pin_No','S_weld1','L_weld1','S_ins1','L_ins1','S_ins2','L_ins2','S_weld2','L_weld2','S_ins_span','S_weld_span','H_Insert_end','L_Insert_end','H_Weld_end','L1_Weld_end','L2_Weld_end'])
        for i in range(len(conductors)):
            if Layout_Para.inlet_from_weld_side == 0 and i == 0: ### If start with I-pin.
                S_ins2 = conductors[0][0] + 1
                L_ins2 = conductors[0][1] + 1
                S_ins3 = conductors[1][0] + 1
                S_weld2 = cal_slot_position(Winding_Para.num_slots, S_ins2, S_ins3, 0.5)
                L_weld2 = L_ins2
                pin_info_data.append([pin_No,None,None,None,None,S_ins2,L_ins2,S_weld2,L_weld2,None])
                pin_No += 1
                
            if i % 2 == side and i <= len(conductors)-2:  ### For each pin shape 
                S_ins1 = conductors[i][0] + 1
                L_ins1 = conductors[i][1] + 1
                S_ins2 = conductors[i+1][0] + 1
                L_ins2 = conductors[i+1][1] + 1
                if i > 0:
                    S_ins0 = conductors[i-1][0] + 1
                else:
                    S_ins0 = S_ins1 - signed_circular_distance(Winding_Para.num_slots, S_ins2, S_ins1)
                if i + 2 < len(conductors):
                    S_ins3 = conductors[i+2][0] + 1
                else:
                    S_ins3 = S_ins2 + abs(signed_circular_distance(Winding_Para.num_slots, S_ins1, S_ins0))
                S_weld1 = cal_slot_position(Winding_Para.num_slots, S_ins0, S_ins1, 0.5)
                L_weld1 = L_ins1
                S_weld2 = cal_slot_position(Winding_Para.num_slots, S_ins2, S_ins3, 0.5)
                L_weld2 = L_ins2
                S_ins_span = abs_circular_distance(Winding_Para.num_slots, S_ins1, S_ins2)
                S_weld_span = round(2*abs_circular_distance(Winding_Para.num_slots, S_ins1, S_weld1),2)
                
                EW_data = ewc.calculate_end_winding_length(L_ins1-1 ,L_ins2-1,S_ins_span,S_weld_span,S_weld_span,Winding_Para,Stator_Para,Inslot_Para,EW_info)

                EndW_Height_insert = EW_data[2]
                EndW_Length_insert = EW_data[3]
                EndW_Height_weld = EW_data[4]
                EndW_Length_weld = EW_data[5]
                pin_info_data.append([pin_No,S_weld1,L_weld1,S_ins1,L_ins1,S_ins2,L_ins2,S_weld2,L_weld2,S_ins_span,S_weld_span,EndW_Height_insert,EndW_Length_insert,EndW_Height_weld,EndW_Length_weld/2,EndW_Length_weld/2])
                pin_No += 1
                
            if Layout_Para.inlet_from_weld_side == 0 and i == len(conductors)-1: ### If Start with I-pin.
                S_ins0 = conductors[i-1][0] + 1
                S_ins1 = conductors[i][0] + 1
                L_ins1 = conductors[i][1] + 1
                S_ins1 = conductors[i][0] + 1
                S_weld1 = cal_slot_position(Winding_Para.num_slots, S_ins0, S_ins1, 0.5)
                L_weld1 = L_ins1
                pin_info_data.append([pin_No,S_weld1,L_weld1,S_ins1,L_ins1,None,None,None,None,None])
                pin_No += 1
                    
    csvo.output_to_csv(path,pin_info_data)
                        
                    
                
                
                    
            
                
