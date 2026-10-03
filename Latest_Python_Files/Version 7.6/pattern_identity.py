"""Bounded ordered Pattern recognition from physical conductor paths.

This module does not import constructors or use pin labels as identity evidence.
Compatibility is a structural verdict, separate from phase, coverage and EMF.
Overlapping observed signatures do not establish equivalence of two complete
parameterized families. In particular a short wave slice may also be a spiral.
Slot/layer coordinates are zero based; a third conductor field is ignored.
"""

from numbers import Rational, Real
from math import isfinite
from collections.abc import Mapping
from fractions import Fraction
from phase_topology import supports_phase_count
from pattern_route_contract import rational_half_belt_translation_pitch

PATTERN_CONTRACTS = {
    'BWP': 'Adjacent-layer wave runs keep one slot direction; insertion-side boundary returns separate opposite runs. Welds stay inside layer pairs.',
    'UWP': 'Adjacent-layer wave edges keep one slot direction. Welds stay inside layer pairs; same-layer series welds are rejected.',
    'SSP': 'Ordinary spiral passes move monotonically through adjacent layers with one slot direction; insertion-side same-layer returns occur at boundary layers.',
    'TSP': 'Ordinary spiral passes move monotonically through adjacent layers with one slot direction; insertion-side top-bottom returns restart the layer traversal.',
    'SLP': 'Ordinary lap passes move monotonically through adjacent layers while slot direction alternates; insertion-side same-layer returns occur at boundary layers.',
    'TLP': 'Ordinary lap passes move monotonically through adjacent layers while slot direction alternates; insertion-side top-bottom returns restart the layer traversal.',
    'ZLP': 'Welds traverse a layer pair. Pair-local insertion steps reverse the neighboring weld direction; pair-changing insertions continue it. Same-layer insertion returns occur at boundary layers.',
    'ZPP': 'Same-layer insertion pins retain one slot direction; adjacent-layer welds form successive pair-local Z steps and connect neighboring layer pairs.',
    'CP': 'Insertion pins span half the even layer count between layer groups; adjacent-layer welds retain one slot direction, with insertion travel following the group crossing.',
    'LPP': 'Same-layer insertion pins retain their direction within each layer and have opposite directions across a layer pair; adjacent-layer welds connect loop steps and neighboring pairs.',
}


def circular_travel_steps(start, end, slots):
    step = (end - start) % slots
    # Use the physical shortest circular travel, as in the Unwrapped plot.
    # Only a half-circumference edge has two equally short directions.
    if 2 * step < slots:
        return (step,)
    if 2 * step > slots:
        return (step - slots,)
    return (step, -step)


def pole_region_crossings(start_slot, signed_step, pole_pitch):
    """Count physical pole boundaries along actual, unwrapped slot travel.

    A half-integer q gives a fractional region width. Integer floor division
    by that exact rational width retains both signed direction and slot-zero
    wrapping without rounding a physical boundary to a slot.
    """
    if type(start_slot) is not int or type(signed_step) is not int:
        raise ValueError('Pole-region travel requires integer slot and step.')
    if not isinstance(pole_pitch, Rational) or isinstance(pole_pitch, bool) or pole_pitch <= 0:
        raise ValueError('Pole-region width must be a positive rational number.')
    return abs((start_slot + signed_step) // pole_pitch
               - start_slot // pole_pitch)


def _sign(value):
    return (value > 0) - (value < 0)


def _advance(code, previous, edge, step, layers, orientation):
    """A small nondeterministic grammar; half-circumference choices merge."""
    old_dl, old_sign, run_sign = previous
    dl, side = edge['layer_step'], edge['side']
    start, end = edge['start'][1], edge['end'][1]
    sign = _sign(step)
    boundary = start in (0, layers - 1)
    same_pair = start // 2 == end // 2
    insert = side == 'insert'
    if not sign:
        return None
    if code in ('SSP', 'TSP', 'SLP', 'TLP'):
        is_return = insert and ((code in ('SSP', 'SLP') and dl == 0)
                                or (code in ('TSP', 'TLP') and abs(dl) == layers - 1))
        if is_return:
            if not boundary:
                return None
            if dl and end not in (0, layers - 1):
                return None
            return (None, None, None)
        if abs(dl) != 1:
            return None
        if old_dl is not None and dl != old_dl:
            return None
        if old_sign is not None and sign != old_sign * (-1 if code in ('SLP', 'TLP') else 1):
            return None
        return (dl, sign, None)
    if code in ('BWP', 'UWP'):
        if code == 'BWP' and dl == 0:
            if not insert or not boundary:
                return None
            return (None, None, -run_sign if run_sign else None)
        if abs(dl) != 1 or (not insert and not same_pair):
            return None
        if run_sign is not None and sign != run_sign:
            return None
        return (dl, sign, sign)
    if code == 'ZLP':
        if dl == 0:
            if not insert or not boundary:
                return None
            return (None, None, None)
        if abs(dl) != 1:
            return None
        if not insert:
            if not same_pair:
                return None
            if old_dl is not None and old_sign is not None:
                # A preceding pair-local insertion reverses this weld;
                # a pair change preserves its travel.
                prior_pair_local = old_dl == -dl
                if sign != old_sign * (-1 if prior_pair_local else 1):
                    return None
        else:
            if old_sign is not None and sign != old_sign * (-1 if same_pair else 1):
                return None
        return (dl, sign, None)
    if code == 'CP':
        if insert:
            if abs(dl) != layers // 2 or sign != orientation * _sign(dl):
                return None
        elif abs(dl) != 1 or (run_sign is not None and sign != run_sign):
            return None
        return (dl, sign, run_sign if insert else sign)
    if code in ('ZPP', 'LPP'):
        if insert:
            if dl != 0:
                return None
            expected = orientation if code == 'ZPP' else orientation * (1 if start % 2 == 0 else -1)
            if sign != expected:
                return None
        elif abs(dl) != 1:
            return None
        return (dl, sign, None)
    return None


def _check(code, edges, layers):
    states = {(None, None, None, direction) for direction in (-1, 1)}
    for edge in edges:
        following = set()
        for old_dl, old_sign, run_sign, orientation in states:
            for step in edge['slot_steps']:
                result = _advance(code, (old_dl, old_sign, run_sign), edge,
                                  step, layers, orientation)
                if result is not None:
                    following.add((*result, orientation))
        if not following:
            return (f"edge {edge['edge_index']}: {code} ordered {edge['side']} "
                    f"connection fails (layer step {edge['layer_step']}, "
                    f"slot choices {edge['slot_steps']}).")
        states = following
    pair_directions = {}
    for edge in edges:
        a, b = edge['start'][1], edge['end'][1]
        if edge['side'] != 'weld' or abs(b - a) != 1 or a // 2 != b // 2:
            continue
        choices = {_sign(step) * _sign(b - a)
                   for step in edge['actual_slot_steps']}
        choices &= pair_directions.get(a // 2, {-1, 1})
        if not choices:
            return f"edge {edge['edge_index']}: weld travel reverses inside layer pair {a // 2 + 1}."
        pair_directions[a // 2] = choices
    return None


def analyze_ordered_pattern(pattern, database, winding, layout):
    """Return independent compatibility and per-branch ordered diagnostics.

    Domain qualification never silently certifies an undefined construction.
    A compatible short path need not exhibit every optional return type.
    Historical series metadata cannot authorize a same-layer UWP weld.
    A constructor may provide complete physical signed steps as
    database.signed_travel[branch_id]; otherwise short-arc direction is inferred.
    """
    pattern = str(pattern).upper().strip()
    layers, slots = int(winding.num_layers), int(winding.num_slots)
    q, phases = winding.q, int(winding.num_phases)
    half_integer_q = (isinstance(q, Real) and isfinite(q) and q > 0
                      and int(2 * q) == 2 * q)
    rational_lap = False
    if (pattern in ('TLP', 'SLP') and not half_integer_q and isinstance(q, Real)
            and isfinite(q) and q > 1 and phases >= 3 and slots > 0):
        poles = Fraction(slots, 1) / (Fraction(str(q)) * phases)
        rational_lap = (poles.denominator == 1 and rational_half_belt_translation_pitch(
            q, int(poles), layers, phases, pattern=pattern) is not None)
    pole_pitch = Fraction(str(q)) * phases if half_integer_q or rational_lap else 0
    qualification = ('bounded-integer-even-layer' if half_integer_q and int(q) == q
                     else 'bounded-half-integer-even-layer' if half_integer_q
                     else f'bounded-rational-{pattern.lower()}-half-belt-translation' if rational_lap
                     else 'unsupported-domain')
    errors = []
    if (not (half_integer_q or rational_lap) or layers < 2 or layers % 2
            or not supports_phase_count(phases) or slots <= 0):
        qualification = 'unsupported-domain'
        errors.append(
            'Ordered recognition requires integer/half-integer q or the implemented rational lap half-belt translation domain, even layers, and a supported phase count; arrayed multiphase layouts are checked per three-phase set.')
    shifts = tuple(getattr(layout, 'phase_shift_list', ()) or (0,) * max(layers, 0))
    if len(shifts) != layers:
        errors.append('Phase-shift list does not match layer count.')
    if pattern not in PATTERN_CONTRACTS:
        errors.append('Unknown Pattern code.')
    reports = []
    compatible = set(PATTERN_CONTRACTS)
    adjustments = tuple(getattr(layout, 'inlet_index_adjustments_phase_a', ()) or ())
    ab = max(int(getattr(winding, 'ab', 1)), 1)
    bridges = getattr(database, 'series_connections', ()) or ()
    signed_travel = getattr(database, 'signed_travel', None)
    if signed_travel is not None and not isinstance(signed_travel, Mapping):
        errors.append('Signed travel evidence must map each branch ID to its complete edge sequence.')
    if isinstance(signed_travel, Mapping):
        branch_ids = [branch_id for branch_id, _path in database]
        if len(set(branch_ids)) != len(branch_ids) or set(signed_travel) != set(branch_ids):
            errors.append('Signed travel evidence must cover each unique branch ID exactly once.')
    for number, (branch_id, path) in enumerate(database, 1):
        branch_errors = []
        edges = []
        adjustment = adjustments[(number - 1) % ab] if (number - 1) % ab < len(adjustments) else 0
        insert_parity = (0 if getattr(layout, 'inlet_from_weld_side', 0) else 1) ^ (int(adjustment) % 2)
        nodes = [tuple(node[:2]) for node in path]
        travel = signed_travel.get(branch_id) if isinstance(signed_travel, Mapping) else None
        if signed_travel is not None and (not isinstance(travel, (tuple, list))
                                          or len(travel) != max(len(nodes) - 1, 0)
                                          or any(type(step) is not int or step == 0
                                                 for step in travel)):
            branch_errors.append('Signed travel evidence must specify every edge with a nonzero integer step.')
        if len(nodes) < 2:
            branch_errors.append('Branch needs at least one connection for identity evidence.')
        if any(len(node) != 2 or not all(isinstance(value, Real) and isfinite(value) and int(value) == value for value in node)
               or not 0 <= node[0] < slots or not 0 <= node[1] < layers for node in nodes):
            branch_errors.append('Conductor coordinate is outside the winding domain.')
        if not branch_errors and not errors:
            segment_start = 0
            for index, (start, end) in enumerate(zip(nodes, nodes[1:])):
                if travel is not None and (travel[index] - (end[0] - start[0])) % slots:
                    branch_errors.append(f'edge {index}: signed travel does not reach its endpoint.')
                    break
                side = 'insert' if (index - segment_start) % 2 == insert_parity else 'weld'
                marked = [item for item in bridges if item.get('branch_id') == branch_id and item.get('edge_index') == index]
                valid_bridge = any(item.get('kind') == 'same_layer_series' and item.get('side') == 'weld'
                                   and tuple(item.get('start', ())) == start and tuple(item.get('end', ())) == end
                                   and start[1] == end[1] for item in marked)
                if valid_bridge:
                    side = 'weld'
                    segment_start = index + 1
                    if pattern == 'UWP':
                        branch_errors.append(
                            f'edge {index}: UWP same-layer series welds are rejected; '
                            'welds must join adjacent layers.')
                if marked and not valid_bridge:
                    branch_errors.append(f'edge {index}: series bridge metadata does not match the actual connection.')
                actual_steps = ((travel[index],) if travel is not None else
                                circular_travel_steps(start[0], end[0], slots))
                region_crossings = tuple(
                    pole_region_crossings(int(start[0]), step, pole_pitch)
                    for step in actual_steps)
                if min(region_crossings) > 1:
                    branch_errors.append(
                        f'edge {index}: connection crosses multiple pole regions '
                        f'({start[0] + 1} to {end[0] + 1}; '
                        f'{min(region_crossings)} boundaries).')
                normal_steps = ((travel[index] - shifts[int(end[1])] + shifts[int(start[1])],)
                                if travel is not None else circular_travel_steps(
                                    start[0] - shifts[int(start[1])],
                                    end[0] - shifts[int(end[1])], slots))
                edges.append({'edge_index': index, 'side': side, 'start': start, 'end': end,
                              'layer_step': end[1] - start[1],
                              'actual_slot_steps': actual_steps,
                              'pole_region_crossings': region_crossings,
                              'slot_steps': normal_steps,
                              'series_bridge': valid_bridge})
        failures = {code: _check(code, edges, layers)
                    for code in PATTERN_CONTRACTS} if edges and not errors else {code: 'Unqualified branch geometry.' for code in PATTERN_CONTRACTS}
        matches = {code for code, error in failures.items() if error is None} if not branch_errors else set()
        compatible &= matches
        if pattern in failures and failures[pattern]:
            branch_errors.append(failures[pattern])
        reports.append({'branch': number, 'branch_id': branch_id,
                        'status': 'candidate' if branch_errors or errors else 'valid',
                        'errors': tuple(branch_errors), 'observed_signature': tuple(edges),
                        'compatible_patterns': tuple(sorted(matches)), 'pattern_errors': failures})
        reports[-1]['evidence_qualification'] = (
            'observed-sequence-compatible; insufficient to distinguish families'
            if len(matches) > 1 else 'observed-sequence-contract')
        errors_for_branch = [f'branch {number}: {error}' for error in branch_errors]
        # Preserve scope errors separately so later branches are still checked.
        reports[-1]['qualified_errors'] = tuple(errors_for_branch)
    if not reports:
        errors.append('No branch paths supplied.')
        compatible.clear()
    pair_directions = {}
    for report in reports:
        for edge in report['observed_signature']:
            a, b = edge['start'][1], edge['end'][1]
            if edge['side'] != 'weld' or abs(b - a) != 1 or a // 2 != b // 2:
                continue
            pair = a // 2
            choices = {_sign(step) * _sign(b - a)
                       for step in edge['actual_slot_steps']}
            shared = choices & pair_directions.get(pair, {-1, 1})
            if not shared:
                message = (f"edge {edge['edge_index']}: weld travel reverses "
                           f"across branches inside layer pair {pair + 1}.")
                report['errors'] += (message,)
                report['qualified_errors'] += (f"branch {report['branch']}: {message}",)
                report['status'] = 'candidate'
                compatible.clear()
            else:
                pair_directions[pair] = shared
    errors.extend(error for report in reports for error in report['qualified_errors'])
    degeneracy = []
    if len(compatible) > 1:
        degeneracy.append('observed-path-overlap: ' + ', '.join(sorted(compatible)))
    if layers == 2 and len(compatible) > 1:
        degeneracy.append('degenerate-two-layer')
    return {'ordered_status': 'valid' if not errors and pattern in compatible else 'candidate',
            'branch_reports': tuple(reports), 'compatible_patterns': tuple(sorted(compatible)),
            'degeneracy': tuple(degeneracy), 'errors': tuple(errors), 'qualification': qualification,
            'evidence_qualification': ('observed-path-overlap; not proof of family equivalence'
                                       if len(compatible) > 1 else 'observed-sequence-contract'),
            'observed_signatures': tuple(report['observed_signature'] for report in reports)}
