"""Shared policy for the top-level automatic transposition mode.

The module contains no Qt widgets or winding dispatch.  It keeps Auto UI,
config compatibility, and derived UWP settings on one testable boundary.
"""
from dataclasses import dataclass
from fractions import Fraction
from collections import Counter, defaultdict
from math import gcd, isfinite, sqrt
from itertools import combinations, product
from functools import lru_cache


def strong_symmetry_count_rule(records, slots, poles, naa):
    """Geometry-only necessary condition, independent of any generated branch."""
    if any(type(value) is not int or value <= 0 for value in (slots,poles,naa)):
        raise ValueError('Positive integer slots, poles and Naa are required.')
    if not records or len({(s,l) for s,l,phase,sign in records}) != len(records):
        raise ValueError('A nonempty phase map with unique positions is required.')
    if any(not 0 <= s < slots or l < 0 or phase < 0 or sign not in (-1,1)
           for s,l,phase,sign in records):
        raise ValueError('Invalid phase-map position, phase or sign.')
    if len(records) != slots*(1+max(l for s,l,phase,sign in records)):
        raise ValueError('The count proof requires the complete slot-layer phase map.')
    totals = Counter((phase,l,(poles*s+(slots if sign < 0 else 0))%(2*slots))
                     for s,l,phase,sign in records)
    common = 0
    for count in totals.values():
        common = gcd(common,count)
    proof = [{'phase':phase,'layer':layer,'signed_angle_key':key,
              'total':count,'naa':naa,'remainder':count%naa}
             for (phase,layer,key),count in sorted(totals.items()) if count%naa]
    return dict(hard_no=bool(proof), proof=proof, category_count_gcd=common,
                counts=totals, quotas=None if proof else
                {key:count//naa for key,count in totals.items()})


AUTO_TYPE = "Auto"
LEGACY_AUTO_TYPES = frozenset((AUTO_TYPE, "Optimize", "Auto balance"))
TP_FIELD_NAMES = ("tp_interval", "tp_times", "uni_tp", "pltp_fl", "pltp_ll", "jltp")

AUTO_CONFIGURE_OBJECTIVES = {
    'min_transpositions': '1. Minimum transpositions',
    'min_pin_types': '2. Minimum pin types',
    'min_average_pin_length': '3. Shortest normalized average pin length',
}
DEFAULT_AUTO_CONFIGURE_OBJECTIVE = 'min_pin_types'


def normalize_objective(objective=None):
    objective = objective or DEFAULT_AUTO_CONFIGURE_OBJECTIVE
    if objective not in AUTO_CONFIGURE_OBJECTIVES:
        raise ValueError(f'Unknown Auto Configure objective: {objective}.')
    return objective


def objective_score(metrics, objective=None):
    """Independent lexicographic objectives; deterministic enumeration breaks ties.

    Count objectives never depend on geometry being available in a caller.
    This keeps default catalog and main-window decisions identical.
    """
    objective = normalize_objective(objective)
    transpositions = metrics['transposition_count']
    types = metrics['pin_type_count']
    if objective == 'min_transpositions':
        return transpositions, types
    if objective == 'min_pin_types':
        return types, transpositions
    length = metrics['average_pin_length_normalized']
    if length is None or not isfinite(length) or length <= 0:
        raise ValueError('Normalized average pin length requires valid geometry and body pins.')
    # Equivalent weighted sums can differ by floating-point noise.
    # Rounding is only a deterministic ranking tie rule, not an accuracy claim.
    return round(length, 9), types, transpositions


def make_pin_length_evaluator(winding, stator, inslot, end_winding):
    """Bind the existing estimated end-winding model, including two active legs.

    Custom length models can implement this same five-argument callable.
    No slot-span proxy is silently substituted for physical millimetres.
    """
    import end_winding_calc
    stack_length = float(stator.StackLength)
    if not isfinite(stack_length) or stack_length <= 0:
        raise ValueError('Pin length requires a positive finite stack length.')

    @lru_cache(maxsize=4096)
    def estimate(layer_a, layer_b, span, weld_a, weld_b):
        lengths = end_winding_calc.calculate_end_winding_length(
            layer_a, layer_b, span, weld_a, weld_b,
            winding, stator, inslot, end_winding)
        value = 2*stack_length + float(lengths[6])
        if not isfinite(value) or value <= 0:
            raise ValueError('The end-winding model returned an invalid pin length.')
        return value

    estimate.length_basis = 'existing_end_winding_model_mm'
    return estimate


def implementation_metrics(database, reference, winding, layout,
                           pin_length_evaluator=None):
    """Measure all phases using physical insertion pins and ordered edge changes.

    A transposition event is an edge whose phase-shift-corrected signed pitch
    or layer pair differs from the same branch/index in the neutral reference.
    Both insertion and weld edges count, including necessary cyclic returns.
    This is a reproducible connection-event count, not the number of nonzero
    TP controls or a manufacturing operation-time estimate.
    """
    slots = winding.num_slots
    shifts = layout.phase_shift_list
    first_pin_parity = 0 if getattr(layout, 'inlet_from_weld_side', 0) else 1
    pin_shapes = Counter()
    normalized_pins = []
    weld_totals, weld_counts = Counter(), Counter()
    transpositions = 0
    baseline = {branch_id: path for branch_id, path in reference}

    def edge_key(a, b):
        delta = ((b[0]-shifts[b[1]]) - (a[0]-shifts[a[1]])) % slots
        signed = delta if delta <= slots/2 else delta-slots
        return a[1], b[1], signed

    for branch_id, path in database:
        base = baseline[branch_id]
        if len(path) != len(base):
            raise ValueError('Implementation metrics require matching reference branch lengths.')
        edges = list(zip(path, path[1:]))
        closed = bool(getattr(layout, 'in_out_connection', 0) and len(path) > 1)
        if closed:
            edges.append((path[-1], path[0]))
        edge_spans = []
        for edge_a, edge_b in edges:
            edge_span = abs(edge_b[0]-edge_a[0]) % slots
            edge_spans.append(min(edge_span, slots-edge_span))
        for index, (a, b) in enumerate(edges):
            transpositions += edge_key(a, b) != edge_key(base[index], base[(index+1) % len(base)])
            layer_a, layer_b = sorted((a[1], b[1]))
            span = abs(b[0]-a[0]) % slots
            span = min(span, slots-span)
            if index % 2 == first_pin_parity:
                pin_shapes[(layer_a, layer_b, span)] += 1
                previous = ((index-1) % len(edges) if closed else index-1)
                following = ((index+1) % len(edges) if closed else index+1)
                weld_a = (edge_spans[previous] if 0 <= previous < len(edges)
                          and previous % 2 != first_pin_parity else 0)
                weld_b = (edge_spans[following] if 0 <= following < len(edges)
                          and following % 2 != first_pin_parity else 0)
                normalized_pins.append(
                    (layer_a, layer_b, span, weld_a, weld_b))
            else:
                for layer in (layer_a, layer_b):
                    weld_totals[layer] += span
                    weld_counts[layer] += 1
    weld_spans = [weld_totals[layer]/weld_counts[layer] if weld_counts[layer] else 0
                  for layer in range(winding.num_layers)]
    pin_count = sum(pin_shapes.values())
    normalized_average = None
    if pin_count:
        pole_pitch = slots/winding.num_poles
        layer_denominator = max(winding.num_layers-1, 1)
        normalized_total = 0.0
        for a, b, span, weld_a, weld_b in normalized_pins:
            normalized_length = (
                2
                + sqrt((span/pole_pitch)**2
                       + (abs(b-a)/layer_denominator)**2)
                + (weld_a+weld_b)/(2*pole_pitch)
            )
            normalized_total += normalized_length
        normalized_average = normalized_total/pin_count
    average = None
    reason = 'Physical stator, conductor and end-winding geometry is required.'
    if pin_length_evaluator is not None and pin_count:
        try:
            total = 0.0
            for (a, b, span), count in pin_shapes.items():
                length = float(pin_length_evaluator(a, b, span, weld_spans[a], weld_spans[b]))
                if not isfinite(length) or length <= 0:
                    raise ValueError('Invalid estimated pin length.')
                total += count*length
            average = total/pin_count
            reason = ''
        except (ValueError, ArithmeticError) as exc:
            reason = str(exc)
    elif not pin_count:
        reason = 'No insertion-side body pins exist in these open branch paths.'
    return dict(transposition_count=transpositions, pin_type_count=len(pin_shapes),
                pin_count=pin_count,
                pin_shapes=[dict(layers=[a, b], slot_span=span, count=count)
                            for (a, b, span), count in sorted(pin_shapes.items())],
                average_pin_length_mm=average,
                average_pin_length_normalized=normalized_average,
                normalized_length_basis='slot_and_layer_span_geometry_per_pole_pitch',
                length_basis=(getattr(pin_length_evaluator, 'length_basis',
                                      'custom_pin_length_model_mm')
                              if average is not None else None),
                length_unavailable_reason=reason,
                transposition_basis='changed_ordered_connections_from_neutral_reference')


def weld_side_contract(reference, candidate, slots, layout):
    """Require Auto to leave physical welds unchanged and direction-uniform.

    Physical edges are branch-agnostic because insertion-side tail exchange may
    move a preserved weld to another branch.  A Counter retains repeated edges;
    lower-to-higher layer travel makes direction independent of path reversal.
    """
    if type(slots) is not int or slots <= 0:
        raise ValueError('Weld-side validation requires a positive slot count.')
    shifts = tuple(getattr(layout, 'phase_shift_list', ()))
    weld_parity = int(bool(getattr(layout, 'inlet_from_weld_side', 0)))

    def inspect(database):
        edges = Counter()
        directions = defaultdict(set)
        for _, path in database:
            for index in range(weld_parity, len(path) - 1, 2):
                a, b = path[index:index + 2]
                a_key, b_key = tuple(a[:2]), tuple(b[:2])
                edges[frozenset((a_key, b_key))] += 1
                if a[1] == b[1]:
                    continue
                low, high = (a, b) if a[1] < b[1] else (b, a)
                pitch = ((high[0] - shifts[high[1]])
                         - (low[0] - shifts[low[1]])) % slots
                if pitch > slots / 2:
                    pitch -= slots
                direction = (pitch > 0) - (pitch < 0)
                directions[tuple(sorted((a[1], b[1])))].add(direction)
        conflicts = {pair: sorted(values) for pair, values in directions.items()
                     if len(values) != 1 or 0 in values}
        return edges, conflicts

    reference_edges, reference_conflicts = inspect(reference)
    candidate_edges, candidate_conflicts = inspect(candidate)
    preserved = candidate_edges == reference_edges
    uniform = not candidate_conflicts
    return dict(valid=preserved and uniform, preserved=preserved, uniform=uniform,
                reference_uniform=not reference_conflicts,
                reference_conflicts=reference_conflicts,
                candidate_conflicts=candidate_conflicts)


def configuration_recipes(pattern, q, poles, branch_conductors,
                          include_start_indices=True):
    """Yield deterministic TP recipes; wave domains follow geometry, not examples.

    Integer wave offsets act modulo q. Enumerate joint residues as well as
    single offsets, and every usable Times/Interval value. This exhausts this
    common-TP family only, not arbitrary starts or independent pole groups.
    Other Patterns retain their existing bounded recipe policy.
    """
    seen = set()

    def unique(recipe):
        key = tuple(sorted(recipe.items()))
        if key not in seen:
            seen.add(key)
            return True
        return False

    rule_prefix = pattern.lower() + '_geometry_recipe'
    fast_bwp_wave = pattern == 'BWP' and Fraction(q).denominator == 1
    if fast_bwp_wave:
        fields = ('uni_tp', 'pltp_ll', 'jltp')
        for field in fields:
            offsets = ([1, -1, *range(2, int(Fraction(q)))]
                       if field in ('uni_tp', 'jltp')
                       else range(1, int(Fraction(q))))
            for offset in offsets:
                recipe = dict(tp_type='Regular', _rule_id=rule_prefix,
                              _rule_stage='bwp_single_field',
                              **{field: offset})
                if unique(recipe):
                    yield recipe
    else:
        for offset in (1, -1):
            for field in ('uni_tp', 'jltp'):
                recipe = dict(tp_type='Regular', _rule_id=rule_prefix,
                              **{field: offset})
                if unique(recipe):
                    yield recipe
    q = Fraction(q)
    wave = pattern in ('BWP', 'UWP') and q.denominator == 1
    if fast_bwp_wave:
        fields = ('uni_tp', 'pltp_ll', 'jltp')
        residues = range(1, int(q))
        for count in range(2, len(fields) + 1):
            for active in combinations(fields, count):
                for offsets in product(residues, repeat=count):
                    recipe = dict(tp_type='Regular', _rule_id=rule_prefix,
                                  _rule_stage='bwp_combined_field',
                                  **dict(zip(active, offsets)))
                    if unique(recipe):
                        yield recipe
        intervals = range(1, branch_conductors)
        for interval in intervals:
            for start_index in range(interval if include_start_indices else 1):
                recipe = dict(tp_type='Interval', tp_interval=interval,
                              tp_start_index=start_index, _rule_id=rule_prefix)
                if unique(recipe):
                    yield recipe
        for count in range(1, branch_conductors):
            derived_interval = max(branch_conductors // (count + 1), 1)
            for start_index in range(derived_interval if include_start_indices else 1):
                recipe = dict(tp_type='Times', tp_times=count,
                              tp_start_index=start_index, _rule_id=rule_prefix)
                if unique(recipe):
                    yield recipe
        return
    intervals = (range(1, branch_conductors) if wave else
                 [n for n in range(1, poles + 1) if poles % n == 0][:8])
    for interval in intervals:
        for start_index in range(interval if include_start_indices else 1):
            recipe = dict(tp_type='Interval', tp_interval=interval,
                          tp_start_index=start_index, _rule_id=rule_prefix)
            if unique(recipe):
                yield recipe
    times = range(1, branch_conductors if wave else min(int(q), 4) + 1)
    for count in times:
        derived_interval = max(branch_conductors // (count + 1), 1)
        for start_index in range(derived_interval if include_start_indices else 1):
            recipe = dict(tp_type='Times', tp_times=count,
                          tp_start_index=start_index, _rule_id=rule_prefix)
            if unique(recipe):
                yield recipe
    if not wave:
        residues = range(1, max(int(q), 1))
        fields = ('uni_tp', 'jltp', 'pltp_ll', 'pltp_fl')
        for field in fields:
            for offset in residues:
                recipe = dict(tp_type='Regular', _rule_id=rule_prefix,
                              **{field: offset})
                if unique(recipe):
                    yield recipe
        # Cover the two coupled schedule families used by existing constructors
        # without claiming an exhaustive four-field Cartesian search.
        for active in (('uni_tp', 'jltp'), ('pltp_fl', 'pltp_ll')):
            for offsets in product(residues, repeat=2):
                recipe = dict(tp_type='Regular', _rule_id=rule_prefix,
                              **dict(zip(active, offsets)))
                if unique(recipe):
                    yield recipe
        return
    # BWP's first-layer field is unused by its constructor. UWP wave routes
    # consume Uniform/Jump; the public route guards reject inapplicable fields.
    fields = (('uni_tp', 'jltp', 'pltp_ll') if pattern == 'BWP' else
              ('uni_tp', 'jltp', 'pltp_ll', 'pltp_fl'))
    residues = range(1, int(q))
    for count in range(1, len(fields) + 1):
        for active in combinations(fields, count):
            for offsets in product(residues, repeat=count):
                recipe = dict(tp_type='Regular', _rule_id=rule_prefix,
                              **dict(zip(active, offsets)))
                if unique(recipe):
                    yield recipe


def assess_strong_symmetry(database, records, slots, poles, naa):
    """Separate actual signed layer quotas from an invariant impossibility proof."""
    categories = {(s,l):(phase,l,(poles*s+(slots if sign < 0 else 0))%(2*slots))
                  for s,l,phase,sign in records}
    rule = strong_symmetry_count_rule(records,slots,poles,naa)
    totals = rule['counts']
    by_phase = defaultdict(list)
    for _,path in database:
        counts = Counter(categories[tuple(node[:2])] for node in path)
        phases = {key[0] for key in counts}
        if len(phases) != 1:
            return dict(strong=False, hard_no=False, reason='Invalid phase path; not a symmetry proof.')
        by_phase[next(iter(phases))].append(counts)
    strong = (len(by_phase) == len({key[0] for key in totals})
              and all(len(group)==naa and all(c==group[0] for c in group)
                      for group in by_phase.values()))
    proof = rule['proof']
    return dict(strong=strong, hard_no=rule['hard_no'], proof=proof,
                category_count_gcd=rule['category_count_gcd'],
                reason=('Equal signed layer-position counts verified.' if strong else
                        'A signed layer-position total is not divisible by Naa.' if proof else
                        'No count obstruction; a constructive configuration is still required.'))


@dataclass(frozen=True)
class AutomaticRule:
    effective_type: str
    values: dict
    message: str
    error: str | None = None


def normalize_tp_type(value, default="Regular"):
    """Convert persisted legacy automatic names to the single Auto mode."""
    value = str(value or default)
    return AUTO_TYPE if value in LEGACY_AUTO_TYPES else value


def is_auto_type(value):
    return normalize_tp_type(value) == AUTO_TYPE


def zero_values():
    return {name: 0 for name in TP_FIELD_NAMES}


def uwp_balanced_settings(plan):
    """Translate a UWP q-position plan into the shared TP field payload."""
    if plan is None:
        raise ValueError("UWP balanced divider has no equal-q transposition plan.")
    values = zero_values()
    values.update(uni_tp=plan["cycle_advance"], jltp=1)
    return values


def balanced_configuration_matches(tp, expected):
    """Allow neutral Regular input or the exact derived Auto payload."""
    values = {key: getattr(tp, key, 0) for key in expected}
    mode = normalize_tp_type(getattr(tp, "tp_type", "Regular"))
    return (getattr(tp, "jld", 1) == 1
            and ((mode == "Regular" and not any(values.values()))
                 or (mode == AUTO_TYPE and values == expected)))


def select_automatic_rule(pattern, q, poles, ab, q_divider):
    """Return the former Optimize decision as an explicit, pure Auto policy."""
    q = Fraction(q)
    values = zero_values()
    if q.denominator != 1:
        return AutomaticRule("Regular", values,
                             f"Half-integer {pattern} candidate: no transposition selected.")
    q = int(q)
    if pattern == "BWP" and q == ab and q_divider == q:
        values["tp_times"] = 1
        return AutomaticRule("Times", values,
                             "Transposition auto-optimized: Type=Times, Times=1")
    if pattern == "BWP" and 2 * q == ab and q_divider == q:
        if poles % 4:
            return AutomaticRule("Regular", values, "",
                                 "Error: For BWP with 2q=ab, number of poles (p) must be a multiple of 4.")
        values["tp_interval"] = poles // 4
        return AutomaticRule("Interval", values,
                             f"Transposition auto-optimized: Type=Interval, Interval={poles // 4}")
    if pattern == "UWP" and ab == 2:
        return AutomaticRule("Regular", values,
                             "Transposition auto-optimized: Type=Regular, All related parameters set to 0")
    if pattern == "UWP" and ab == 2 * q:
        values["tp_interval"] = 1
        return AutomaticRule("Interval", values,
                             "Transposition auto-optimized: Type=Interval, Interval=1")
    if pattern in ("SSP", "SLP") and ab in (q, 2 * q, poles):
        values["pltp_ll"] = 1
        return AutomaticRule("Regular", values,
                             "Transposition auto-optimized: Type=Regular, pltp_ll = 1")
    return None
