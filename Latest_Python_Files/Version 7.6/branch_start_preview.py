"""Isolated branch-inlet candidates; never promote or mutate production state."""
from collections import Counter, defaultdict
from copy import deepcopy
from fractions import Fraction
from math import gcd
from types import SimpleNamespace

import get_winding_pattern as gw
import phase_topology


def _copy_parameters(value):
    values = value._asdict() if hasattr(value, '_asdict') else vars(value)
    return SimpleNamespace(**deepcopy(values))


def _path_error(path, phase, records):
    keys = [tuple(c[:2]) for c in path]
    if not keys or len(set(keys)) != len(keys):
        return 'The candidate contains duplicate or missing conductors.'
    if any(key not in records for key in keys):
        return 'The candidate references an unavailable slot/layer.'
    metadata = [records[key] for key in keys]
    if any(p != phase for p, _ in metadata):
        return 'The candidate crosses phase assignments.'
    if any(sign != metadata[0][1] * (-1)**i for i, (_, sign) in enumerate(metadata)):
        return 'The candidate does not alternate conductor directions.'
    return ''


def _fractional_branch_members(plan, rows, slots, poles):
    """Partition mapped conductors by the candidate pole/category quotas."""
    pole_groups = plan['pole_groups']
    position_count = plan['position_divider']
    region_to_group = {region: index for index, group in enumerate(pole_groups)
                       for region in group}
    buckets = defaultdict(list)
    lookup = {(row[0], row[1]): row for row in rows}
    for row in rows:
        group = region_to_group[poles * row[0] // slots]
        category = phase_topology._division_category(row, slots, poles, plan['symmetry'])
        buckets[group, category].append(row[:2])

    members = defaultdict(list)
    counts = Counter()
    reserved = set()
    for start in plan['default_start_conductors']:
        position = start['slot'], start['layer']
        row = lookup[position]
        group, part = start['pole_group'], start['position_group']
        category = phase_topology._division_category(row, slots, poles, plan['symmetry'])
        if (group, category) not in buckets or position in reserved:
            raise ValueError('A planned branch start has no unique mapped position.')
        members[start['phase'], group, part].append(position)
        counts[group, part, category] += 1
        reserved.add(position)

    for (group, category), positions in sorted(buckets.items()):
        quota = plan['category_quotas'][category]
        if len(positions) != quota * position_count:
            raise ValueError('The phase map does not match the planned branch quotas.')
        for position in sorted(positions):
            if position in reserved:
                continue
            part = min(range(position_count), key=lambda i: (counts[group, i, category], i))
            if counts[group, part, category] >= quota:
                raise ValueError('A planned branch category has no remaining capacity.')
            members[category[0], group, part].append(position)
            counts[group, part, category] += 1
    assigned = [position for group_members in members.values() for position in group_members]
    if len(assigned) != len(set(assigned)) or set(assigned) != set(lookup):
        raise ValueError('The candidate branch partition does not cover the phase map.')
    for (group, category) in buckets:
        if any(counts[group, part, category] != plan['category_quotas'][category]
               for part in range(position_count)):
            raise ValueError('Candidate branches have unequal category counts.')
    return members


def evaluate_division_rule(pattern, slots, poles, layers, naa, shifts,
                           division_rule=None, phases=3):
    """Evaluate one candidate partition under strong, then weak symmetry."""
    pole_groups = None
    if division_rule is not None:
        pole_groups, positions = division_rule
        if (isinstance(pole_groups, bool) or isinstance(positions, bool)
                or not isinstance(pole_groups, int) or not isinstance(positions, int)
                or pole_groups <= 0 or positions <= 0 or pole_groups * positions != naa):
            raise ValueError('Pole groups × position branches must equal Naa.')
    plan = phase_topology.classify_fractional_branch_plan(
        slots, poles, layers, naa, pattern, shifts=shifts,
        prefer_position_division=division_rule is None, pole_divider=pole_groups,
        phases=phases)
    if plan['status'] != 'candidate':
        plan = phase_topology.classify_fractional_branch_plan(
            slots, poles, layers, naa, pattern, symmetry='weak', shifts=shifts,
            prefer_position_division=division_rule is None, pole_divider=pole_groups,
            phases=phases)
    return plan


def proposed_division_rule(q, poles, naa):
    """Prefer the largest pole-region factor shared by poles and Naa."""
    q = Fraction(str(q))
    if q > 0 and q.denominator != 1 and poles > 0 and naa > 0:
        pole_groups = gcd(poles, naa)
        return pole_groups, naa // pole_groups
    return None


def preferred_division_plan(pattern, slots, poles, layers, naa, shifts, phases=3):
    """Validate the factor preference; retain the planner's other candidates."""
    q = Fraction(slots, poles * phases)
    proposed = proposed_division_rule(q, poles, naa)
    if proposed is not None:
        plan = evaluate_division_rule(pattern, slots, poles, layers, naa, shifts,
                                      proposed, phases=phases)
        if plan['status'] == 'candidate':
            return plan
    return evaluate_division_rule(pattern, slots, poles, layers, naa, shifts,
                                  phases=phases)


def build_preview_context(pattern, winding, layout, transposition, records,
                          division_rule=None):
    """Generate an independent integer baseline or fractional division candidate.

    Coordinates are zero-based; branch IDs match the integer generator or
    the candidate planner's one-based phase order.
    Per-phase ``number`` is one-based. Returned paths/records are immutable tuples;
    each call owns its parameter copies. CHW is rejected because phase-only maps
    intentionally do not include its local conductor swaps.
    """
    w, lp, tp = map(_copy_parameters, (winding, layout, transposition))
    rows = tuple(tuple(row) for row in records)
    context = dict(status='unavailable', reason='', branches=(), records=rows,
                   production_ready=False, _winding=w, _layout=lp)
    try:
        q = Fraction(str(w.q))
        if q <= 0 or w.ab <= 0:
            raise ValueError('Positive q and branch count are required.')
        if q != Fraction(w.num_slots, w.num_poles * w.num_phases):
            raise ValueError('q does not match the slot, pole and phase counts.')
        lookup = {(s, l): (p, sign) for s, l, p, sign in rows}
        if len(lookup) != len(rows):
            raise ValueError('The phase map contains duplicate conductors.')
        if getattr(lp, 'radial_shift', 0):
            raise ValueError('CHW conductor swaps are not represented in the Phase Division map; disable CHW for branch previews.')
        if q.denominator != 1 or division_rule is not None:
            if set(rows) != set(phase_topology.phase_map(
                    w.num_slots, w.num_poles, w.num_layers, lp.phase_shift_list,
                    w.num_phases)):
                raise ValueError('The phase map differs from the fractional division inputs.')
            if division_rule is None and q.denominator != 1:
                plan = preferred_division_plan(
                    pattern, w.num_slots, w.num_poles, w.num_layers, w.ab,
                    lp.phase_shift_list, w.num_phases)
            else:
                plan = evaluate_division_rule(
                    pattern, w.num_slots, w.num_poles, w.num_layers, w.ab,
                    lp.phase_shift_list, division_rule, w.num_phases)
            if plan['status'] != 'candidate':
                raise ValueError(plan['reason'])
            assigned = _fractional_branch_members(plan, rows, w.num_slots, w.num_poles)
            branches = []
            for start in plan['default_start_conductors']:
                group, part = start['pole_group'], start['position_group']
                branch_number = start['branch'] + 1
                branches.append(dict(id=start['phase'] * w.ab + branch_number,
                                     phase=start['phase'], number=branch_number,
                                     path=(), members=tuple(sorted(assigned[start['phase'], group, part])),
                                     start=(start['slot'], start['layer'])))
            context.update(status='division_candidate', branches=tuple(branches),
                           reason=(f"{plan['symmetry'].capitalize()} symmetry candidate membership only; "
                                   'connections are not generated.'),
                           division_plan=plan)
            return context
        w.q = int(q)
        _, database = gw.get_winding_layout(pattern, tp, w, lp)
        branches, phase_counts, occupied = [], Counter(), []
        for branch_id, conductors in database:
            path = tuple(tuple(c) for c in conductors)
            if not path or path[0][:2] not in lookup:
                raise ValueError('The generated branch has no mapped start conductor.')
            phase = lookup[path[0][:2]][0]
            reason = _path_error(path, phase, lookup)
            if reason:
                raise ValueError(reason)
            phase_counts[phase] += 1
            branches.append(dict(id=branch_id, phase=phase, number=phase_counts[phase],
                                 path=path, start=path[0][:2]))
            occupied.extend(c[:2] for c in path)
        expected_length = len(rows) / (w.ab * w.num_phases)
        if (len(occupied) != len(set(occupied)) or set(occupied) != set(lookup)
                or any(phase_counts[p] != w.ab for p in range(w.num_phases))
                or any(len(b['path']) != expected_length for b in branches)):
            raise ValueError('The generated branch set does not cover the phase map exactly once with equal branch lengths.')
        context.update(status='candidate', branches=tuple(branches),
                       reason='Existing integer branch paths; preview only, without production changes.')
    except (ValueError, TypeError, IndexError, ZeroDivisionError, AttributeError) as exc:
        context['reason'] = str(exc)
    return context


def preview_branch_start(context, branch_id, slot, layer):
    """Preview a member, rotating and validating integer paths when available."""
    result = dict(status='rejected', reason='', branch_id=branch_id, phase=None,
                  start=(slot, layer), path=(), offset=0, closed=False, production_ready=False)
    branch = next((b for b in context['branches'] if b['id'] == branch_id), None)
    if branch is None:
        result['reason'] = 'No preview branch is available.'
        return result
    result['phase'] = branch['phase']
    lookup = {(s, l): (p, sign) for s, l, p, sign in context['records']}
    if (slot, layer) not in lookup or lookup[(slot, layer)][0] != branch['phase']:
        result['reason'] = 'Select a conductor belonging to the selected phase.'
        return result
    if context['status'] == 'division_candidate':
        if (slot, layer) not in branch['members']:
            result['reason'] = 'Select a conductor within this candidate branch.'
            return result
        result.update(status='branch_preview', reason=context['reason'])
        return result
    path = branch['path']
    index = next((i for i, conductor in enumerate(path) if conductor[:2] == (slot, layer)), None)
    if index is None:
        result['reason'] = 'Select a conductor within this branch; arbitrary rerouting is not implemented.'
        return result
    rotated = path[index:] + path[:index]
    reason = _path_error(rotated, branch['phase'], lookup)
    if not reason and index:
        try:
            gw.find_single_connection_between(path[-1], path[0], context['_winding'], context['_layout'])
        except (ValueError, IndexError, TypeError) as exc:
            reason = f'The required old-outlet to old-inlet connection is unavailable: {exc}'
    closed = bool(getattr(context['_layout'], 'in_out_connection', False))
    if not reason and closed:
        if lookup[rotated[-1][:2]][1] == lookup[rotated[0][:2]][1]:
            reason = 'The closing connection does not alternate conductor directions.'
        else:
            try:
                gw.find_single_connection_between(rotated[-1], rotated[0], context['_winding'], context['_layout'])
            except (ValueError, IndexError, TypeError) as exc:
                reason = f'The candidate outlet-to-inlet closing connection is unavailable: {exc}'
    if reason:
        result['reason'] = reason
        return result
    result.update(status='candidate', reason='Complete branch candidate; not applied to production.',
                  path=rotated, offset=index, closed=closed)
    return result
