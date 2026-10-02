"""Exact slot-sector assignment and independent electrical diagnostics.

Count-based branch symmetry does not establish connected windings or manufacturability.
"""
from fractions import Fraction
from numbers import Integral
from collections import Counter
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping
import cmath
import math


FRACTIONAL_PATTERN_POLICIES = {
    'BWP': {'family': 'wave'},
    'UWP': {'family': 'wave', 'special_modes': True},
    'SSP': {'family': 'spiral_lap'},
    'SLP': {'family': 'spiral_lap'},
    'ZPP': {'family': 'spiral_lap', 'requires_even_layers': True},
    'ZLP': {'family': 'pole_lap'},
    'LPP': {'family': 'pole_lap', 'position_division': False,
            'requires_even_layers': True},
    'CP': {'family': 'cross_layer', 'requires_even_layers': True},
    'TSP': {'family': 'top_bottom', 'max_pole_divider': 2},
    'TLP': {'family': 'top_bottom', 'max_pole_divider': 2,
            'requires_even_layers': True},
}


@dataclass(frozen=True)
class PhaseRecord:
    """One conductor's immutable electrical and phase-set identity."""

    slot: int
    layer: int
    phase: int
    sign: int
    pole_region: int
    set_index: int
    local_phase: int
    local_slot: int
    local_layer: int


@dataclass(frozen=True)
class PhaseSetSpec:
    """One phase model's local view and reversible global coordinate transform."""

    set_index: int
    phases: tuple[int, ...]
    layer_start: int
    layer_count: int
    slot_offset: int
    electrical_offset_degrees: Fraction
    local_q: Fraction
    local_slots: int
    total_slots: int

    def to_local(self, slot, layer):
        return ((int(slot) - self.slot_offset) % self.total_slots,
                int(layer) - self.layer_start)

    def to_global(self, slot, layer):
        return ((int(slot) + self.slot_offset) % self.total_slots,
                int(layer) + self.layer_start)

    def local_phase(self, global_phase):
        try:
            return self.phases.index(int(global_phase))
        except ValueError as exc:
            raise ValueError('Phase does not belong to this phase set.') from exc

    def global_phase(self, local_phase):
        try:
            return self.phases[int(local_phase)]
        except (IndexError, TypeError) as exc:
            raise ValueError('Local phase is outside this phase set.') from exc


@dataclass(frozen=True)
class PhaseTopology:
    """Canonical conductor phase assignment and phase-set coordinate system."""

    slots: int
    poles: int
    layers: int
    phases: int
    q: Fraction
    phase_model: str
    set_count: int
    records: tuple[PhaseRecord, ...]
    phase_sets: tuple[PhaseSetSpec, ...]
    _by_coordinate: Mapping[tuple[int, int], PhaseRecord] = field(
        repr=False, compare=False)

    def record_at(self, slot, layer):
        try:
            return self._by_coordinate[(int(slot), int(layer))]
        except KeyError as exc:
            raise ValueError('No conductor exists at this slot/layer coordinate.') from exc

    def phase_of(self, slot, layer):
        return self.record_at(slot, layer).phase

    def sign_of(self, slot, layer):
        return self.record_at(slot, layer).sign

    def pole_region_of(self, slot, layer):
        return self.record_at(slot, layer).pole_region

    def phase_view(self, phase_index):
        phase_index = int(phase_index)
        if not 0 <= phase_index < self.phases:
            raise ValueError('Phase index is outside this topology.')
        return tuple(record for record in self.records
                     if record.phase == phase_index)


@dataclass(frozen=True)
class PhaseDivisionResult:
    """Phase feasibility summary, with an optional generated topology."""

    feasible: bool
    q: Fraction | None
    reason: str | None
    phase_model: str | None
    set_count: int
    repeating_pole_unit: int | None
    topology: PhaseTopology | None = None


def parse_q(value):
    q = Fraction(str(value).strip())
    if q <= 0:
        raise ValueError('q must be positive.')
    return q


def winding_q(slots, poles, phases=3):
    if any(isinstance(n, bool) or not isinstance(n, Integral) or n <= 0
           for n in (slots, poles, phases)):
        raise ValueError('Slots, poles and phases must be positive integers.')
    if slots <= 0 or slots % phases or poles <= 0 or poles % 2:
        raise ValueError('Slots must be a positive multiple of phases; poles must be positive and even.')
    return Fraction(slots, poles * phases)


def supports_phase_count(phases):
    """Keep existing odd-phase routes and admit every multiple of three."""
    return (not isinstance(phases, bool) and isinstance(phases, Integral)
            and phases >= 3 and (phases % 2 == 1 or phases % 3 == 0))


def three_phase_set_count(phases):
    """Return the number of three-phase sets represented by ``phases``."""
    return phases // 3 if supports_phase_count(phases) and phases % 3 == 0 else 1


def supports_phase_layer_allocation(phases, layers):
    """Require equal layer groups for circumferentially arrayed 3-phase sets."""
    if (not supports_phase_count(phases) or isinstance(layers, bool)
            or not isinstance(layers, Integral) or layers <= 0):
        return False
    return layers % three_phase_set_count(phases) == 0


def _default_phase_records(slots, poles, layers, phases=3):
    """Return slot/layer/phase/sign records for supported phase counts.

    Positive shift moves a layer toward increasing slot indices. Odd layers
    use the existing fractional-slot upper-integer pole-pitch displacement,
    with polarity reversal. Multiples of three use equal layer groups, each
    carrying the existing three-phase belt sequence. Consecutive sets rotate
    by one ``360 / phases`` electrical-angle step around the stator.
    """
    if not supports_phase_count(phases):
        raise ValueError(
            'Phase count must be an odd integer of at least three or a multiple of three.')
    if isinstance(layers, bool) or not isinstance(layers, Integral) or layers <= 0:
        raise ValueError('Layers must be a positive integer.')
    if not supports_phase_layer_allocation(phases, layers):
        sets = three_phase_set_count(phases)
        raise ValueError(
            f'{phases} phases require layers divisible by {sets} '
            'to allocate equal three-phase winding sets.')
    q = winding_q(slots, poles, phases)
    records = []
    fractional = q.denominator != 1
    set_count = three_phase_set_count(phases)
    set_layers = layers // set_count
    set_q = q * set_count
    for slot in range(slots):
        for layer in range(layers):
            if phases % 3 == 0:
                set_index = layer // set_layers
                slot_offset = 2 * q * set_index
                if slot_offset.denominator != 1:
                    raise ValueError(
                        'Three-phase set rotation 360/phases must map to an '
                        'integer slot offset.')
                offset = math.ceil(3 * set_q) if set_q.denominator != 1 and layer % 2 else 0
                belt = (Fraction(slot - int(slot_offset) + offset) / set_q).__floor__()
                phase = 3 * set_index + belt % 3
                sign = (-1) ** belt
            else:
                offset = math.ceil(phases * q) if fractional and layer % 2 else 0
                belt = (Fraction(slot + offset) / q).__floor__()
                phase = belt % phases
                pole_sector = belt // phases
                sign = (-1) ** (phase + pole_sector)
            if set_q.denominator != 1 and layer % 2 and phases % 3 == 0:
                sign *= -1
            elif fractional and layer % 2 and phases % 3 != 0:
                sign *= -1
            records.append((slot, layer, phase, sign))
    return tuple(records)


def apply_layer_shifts(default_records, slots, layers, shifts):
    """Translate immutable default positions once; never shift a cached result."""
    shifts = tuple(shifts)
    try:
        valid = len(shifts) == layers and all(not isinstance(s, bool) and int(s) == s for s in shifts)
    except (ValueError, TypeError, OverflowError):
        valid = False
    if not valid:
        raise ValueError('One integer slot shift is required per layer.')
    return [((slot + int(shifts[layer])) % slots, layer, phase, sign)
            for slot, layer, phase, sign in default_records]


def shifted_connection_slot(default_delta, start_slot, start_layer, end_layer, shifts, slots):
    """Start is already shifted. Add only the relative layer shift to the edge."""
    return (start_slot + default_delta + shifts[end_layer] - shifts[start_layer]) % slots


def _phase_map_records(slots, poles, layers, shifts=None, phases=3):
    return apply_layer_shifts(_default_phase_records(slots, poles, layers, phases), slots, layers,
                              [0] * layers if shifts is None else shifts)


def build_phase_topology(slots, poles, layers, phases=3, shifts=None):
    """Build the canonical immutable phase and phase-set map for a winding.

    Odd phase counts use one native polyphase view. Multiples of three above
    three use equal layer-assigned, circumferentially arrayed 3-phase sets.
    Pattern connection rules are deliberately outside this object.
    """
    if not supports_phase_count(phases):
        raise ValueError(
            'Phase count must be an odd integer of at least three or a multiple of three.')
    q = winding_q(slots, poles, phases)
    raw_records = _default_phase_records(slots, poles, layers, phases)
    mapped_records = apply_layer_shifts(
        raw_records, slots, layers,
        [0] * layers if shifts is None else shifts)

    set_count = three_phase_set_count(phases)
    arrayed = phases > 3 and phases % 3 == 0
    phase_model = ('arrayed_three_phase_sets' if arrayed
                   else 'symmetric_polyphase')
    set_layers = layers // set_count
    local_q = q * set_count if arrayed else q
    phase_sets = []
    for set_index in range(set_count):
        slot_offset = 2 * q * set_index if arrayed else Fraction(0)
        if slot_offset.denominator != 1:
            raise ValueError(
                'Three-phase set rotation 360/phases must map to an integer slot offset.')
        phase_indices = (tuple(range(3 * set_index, 3 * (set_index + 1)))
                         if arrayed else tuple(range(phases)))
        phase_sets.append(PhaseSetSpec(
            set_index=set_index,
            phases=phase_indices,
            layer_start=set_index * set_layers,
            layer_count=set_layers,
            slot_offset=int(slot_offset),
            electrical_offset_degrees=Fraction(360 * set_index, phases)
            if arrayed else Fraction(0),
            local_q=local_q,
            local_slots=slots,
            total_slots=slots,
        ))

    records = []
    for slot, layer, phase, sign in mapped_records:
        set_index = phase // 3 if arrayed else 0
        spec = phase_sets[set_index]
        local_slot, local_layer = spec.to_local(slot, layer)
        records.append(PhaseRecord(
            slot=int(slot), layer=int(layer), phase=int(phase), sign=int(sign),
            pole_region=min(poles - 1, poles * int(slot) // slots),
            set_index=set_index,
            local_phase=spec.local_phase(phase),
            local_slot=local_slot,
            local_layer=local_layer,
        ))

    by_coordinate = {(record.slot, record.layer): record for record in records}
    if (len(records) != slots * layers
            or len(by_coordinate) != slots * layers):
        raise ValueError('Phase topology must assign every conductor exactly once.')
    return PhaseTopology(
        slots=int(slots), poles=int(poles), layers=int(layers),
        phases=int(phases), q=q, phase_model=phase_model,
        set_count=set_count, records=tuple(records),
        phase_sets=tuple(phase_sets),
        _by_coordinate=MappingProxyType(by_coordinate),
    )


def build_winding_phase_topology(winding, shifts=None):
    """Build a topology from the application's winding parameter object."""
    phases = getattr(winding, 'num_phases', None)
    poles = getattr(winding, 'num_poles', None)
    layers = getattr(winding, 'num_layers', None)
    slots = getattr(winding, 'num_slots', None)
    if slots is None:
        q_value = getattr(winding, 'q', None)
        if not all(value is not None for value in (q_value, poles, phases)):
            raise ValueError('Winding parameters do not define an integer slot count.')
        inferred_slots = parse_q(q_value) * poles * phases
        if inferred_slots.denominator != 1:
            raise ValueError('Winding q does not resolve to an integer slot count.')
        slots = inferred_slots.numerator
    return build_phase_topology(slots, poles, layers, phases, shifts)


def default_phase_map(slots, poles, layers, phases=3):
    """Compatibility tuple view of the canonical default phase topology."""
    topology = build_phase_topology(slots, poles, layers, phases)
    return tuple((record.slot, record.layer, record.phase, record.sign)
                 for record in topology.records)


def phase_map(slots, poles, layers, shifts=None, phases=3):
    """Compatibility tuple view of the canonical shifted phase topology."""
    topology = build_phase_topology(slots, poles, layers, phases, shifts)
    return [(record.slot, record.layer, record.phase, record.sign)
            for record in topology.records]


def _phase_count_preflight(slots, poles, phases):
    """Check phase-count arithmetic without inventing a layer allocation."""
    try:
        q = winding_q(slots, poles, phases)
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        return False, None, None, str(exc)
    if not supports_phase_count(phases):
        return (False, q, None,
                'Phase count must be an odd integer of at least three or a multiple of three.')
    if phases > 3 and phases % 3 == 0:
        local_q = q * three_phase_set_count(phases)
        if (2 * q).denominator != 1:
            return (False, q, local_q.denominator,
                    'Three-phase set rotation 360/phases must map to an integer slot offset.')
        return True, q, local_q.denominator, None
    if q.denominator > 1 and math.gcd(q.denominator, phases) != 1:
        return (False, q, None,
                'Fractional q denominator must be coprime with the phase count.')
    return True, q, q.denominator if q.denominator > 1 else 1, None


def phase_division_feasibility(slots, poles, layers, phases=3, shifts=None):
    """Evaluate phase feasibility using the requested real layer allocation."""
    feasible, q, pole_unit, reason = _phase_count_preflight(slots, poles, phases)
    model = ('arrayed_three_phase_sets'
             if supports_phase_count(phases) and phases > 3 and phases % 3 == 0
             else 'symmetric_polyphase')
    set_count = three_phase_set_count(phases) if supports_phase_count(phases) else 0
    if not feasible:
        return PhaseDivisionResult(
            False, q, reason, model, set_count, pole_unit, None)
    if layers is None:
        return PhaseDivisionResult(
            True, q, None, model, set_count, pole_unit, None)
    try:
        topology = build_phase_topology(slots, poles, layers, phases, shifts)
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        return PhaseDivisionResult(
            False, q, str(exc), model, set_count, None, None)
    return PhaseDivisionResult(
        True, topology.q, None, topology.phase_model, topology.set_count,
        pole_unit, topology)


def legacy_cond_info(topology):
    """Adapt canonical phase records to the legacy seven-column Cond_info."""
    if not isinstance(topology, PhaseTopology):
        raise TypeError('legacy_cond_info requires a PhaseTopology.')
    counts = [0] * topology.phases
    conductors_per_pole_phase = Fraction(
        topology.slots * topology.layers,
        topology.poles * topology.phases)
    legacy_counts_per_pole_phase = int(conductors_per_pole_phase)
    result = []
    for record in topology.records:
        if topology.phase_model == 'arrayed_three_phase_sets':
            pole_index = counts[record.phase] // conductors_per_pole_phase
            if (pole_index + record.phase) % 2 != (record.sign < 0):
                pole_index += 1
        else:
            if legacy_counts_per_pole_phase <= 0:
                raise ZeroDivisionError(
                    'Legacy Cond_info cannot encode fewer than one conductor per pole and phase.')
            pole_index = counts[record.phase] // legacy_counts_per_pole_phase
        counts[record.phase] += 1
        result.append((record.slot, record.layer, record.phase,
                       0, 0, 0, int(pole_index)))
    return result


def _symmetry_rule(counts, name):
    """Build equal-share rules from nonempty, positive category counts.

    Equal integer shares exist iff Naa divides every category count, hence
    iff it divides their GCD. Missing categories have no allocation to split.
    """
    maximum = math.gcd(*counts.values())
    factors = set()
    for value in range(1, math.isqrt(maximum) + 1):
        if maximum % value == 0:
            factors.update((value, maximum // value))
    allowed = sorted(factors)
    return {'rule': name, 'max_naa': maximum, 'allowed_naa': allowed,
            'counts': dict(sorted(counts.items())),
            'quotas': {naa: {key: count // naa for key, count in sorted(counts.items())}
                       for naa in allowed}}


def _default_start_conductors(records, slots, poles, layers, naa,
                              preferred_layer, phases):
    """Choose boundary-layer starts, distributing across pole regions first."""
    starts = []
    for phase in range(phases):
        if phases % 3 == 0:
            set_count = three_phase_set_count(phases)
            set_layers = layers // set_count
            set_index = phase // 3
            first_layer = set_index * set_layers
            target_layer = (first_layer if preferred_layer == 'first' else
                            first_layer + set_layers - 1)
        else:
            target_layer = 0 if preferred_layer == 'first' else layers - 1
        by_pole = {}
        for slot, layer, record_phase, sign in records:
            if record_phase != phase or layer != target_layer:
                continue
            pole_region = poles * slot // slots
            angle_key = (poles * slot + (slots if sign == -1 else 0)) % (2 * slots)
            by_pole.setdefault(pole_region, []).append(
                (angle_key, slot, sign, pole_region))
        for candidates in by_pole.values():
            candidates.sort()
        ordered = []
        depth = 0
        while len(ordered) < naa:
            added = False
            for pole_region in sorted(by_pole):
                candidates = by_pole[pole_region]
                if depth < len(candidates):
                    ordered.append(candidates[depth])
                    added = True
                    if len(ordered) == naa:
                        break
            if not added:
                raise ValueError('Not enough boundary-layer conductors for the requested Naa.')
            depth += 1
        for branch, (angle_key, slot, sign, pole_region) in enumerate(ordered):
            starts.append({'phase': phase, 'branch': branch, 'slot': slot,
                           'layer': target_layer, 'sign': sign,
                           'signed_angle_key': angle_key,
                           'pole_region': pole_region})
    return starts


def symmetry_branch_rules(slots, poles, layers, shifts=None, phases=3):
    """Return exact strong/weak equal-share Naa rules for supported maps.

    Supports any positive rational q that produces an integer slot count and
    populates every assigned phase/layer category, with positive even layer counts.
    Shifts follow phase_map: one integer slot translation per layer, default zero.
    No connection-pattern dispatch or search is performed.

    Each result contains rule, max_naa, allowed_naa, counts and quotas[naa].
    Strong count/ quota keys are (phase, layer, signed_angle_key); weak keys
    are (phase, layer). Phase, layer and slot indices are zero-based. The
    angle key denotes key*pi/slots modulo 2*pi, with polarity folded in.
    Quotas give conductors per category PER BRANCH, not totals per phase.

    Strong guarantees identical signed fundamental contributions within each
    phase. Weak guarantees only equal layer populations. Neither asserts
    nonzero EMF, phase balance, connectivity or manufacturability;
    electrical_summary remains a separate diagnostic. Results describe all
    and only the Naa satisfying each count rule, not all EMF-equal partitions.
    """
    winding_q(slots, poles, phases)
    if (isinstance(layers, bool) or not isinstance(layers, Integral)
            or layers <= 0 or layers % 2):
        raise ValueError('Symmetry branch rules require a positive even layer count.')
    records = phase_map(slots, poles, layers, shifts, phases)
    strong = Counter()
    weak = Counter()
    for slot, layer, phase, sign in records:
        angle_key = (poles * slot + (slots if sign == -1 else 0)) % (2 * slots)
        strong[phase, layer, angle_key] += 1
        weak[phase, layer] += 1
    for phase in range(phases):
        if phases % 3 == 0:
            set_layers = layers // three_phase_set_count(phases)
            phase_layers = range((phase // 3) * set_layers,
                                 (phase // 3 + 1) * set_layers)
        else:
            phase_layers = range(layers)
        if any((phase, layer) not in weak for layer in phase_layers):
            raise ValueError(
                'Symmetry branch rules require conductors in every assigned '
                'phase and layer.')
    result = {'strong': _symmetry_rule(strong, 'strong'),
              'weak': _symmetry_rule(weak, 'weak')}
    for mode, rule in result.items():
        rule['default_start_conductors'] = {
            naa: _default_start_conductors(
                records, slots, poles, layers, naa, 'first', phases)
            for naa in rule['allowed_naa']
        }
    return result


def default_start_conductors(slots, poles, layers, naa, symmetry='strong',
                             shifts=None, preferred_layer='first', phases=3):
    """Return deterministic start candidates for one feasible symmetry rule.

    Starts use the first or last layer and exhaust distinct pole regions before
    taking another position from a pole region. Returned dictionaries are
    candidate metadata for future fractional-q connection construction; they
    are not legacy ``(slot, layer, phasor)`` connection IDs.
    """
    if isinstance(naa, bool) or not isinstance(naa, Integral) or naa <= 0:
        raise ValueError('Naa must be a positive integer.')
    if symmetry not in ('strong', 'weak'):
        raise ValueError("Symmetry must be 'strong' or 'weak'.")
    if preferred_layer not in ('first', 'last'):
        raise ValueError("Preferred layer must be 'first' or 'last'.")
    shifts = None if shifts is None else tuple(shifts)
    rules = symmetry_branch_rules(slots, poles, layers, shifts, phases)
    if naa not in rules[symmetry]['allowed_naa']:
        allowed = ', '.join(map(str, rules[symmetry]['allowed_naa']))
        raise ValueError(f'Naa={naa} is not allowed by {symmetry} symmetry; '
                         f'allowed values: {allowed}.')
    records = phase_map(slots, poles, layers, shifts, phases)
    return _default_start_conductors(
        records, slots, poles, layers, naa, preferred_layer, phases)


def _division_category(record, slots, poles, symmetry):
    slot, layer, phase, sign = record
    if symmetry == 'weak':
        return phase, layer
    angle_key = (poles * slot + (slots if sign == -1 else 0)) % (2 * slots)
    return phase, layer, angle_key


def _pole_groups(records, slots, poles, naa, symmetry, pole_divider):
    """Find one cyclic contiguous pole partition with equal category histograms."""
    position_divider = naa // pole_divider
    group_size = poles // pole_divider
    for origin in range(group_size):
        groups = [tuple((origin + group * group_size + offset) % poles
                        for offset in range(group_size))
                  for group in range(pole_divider)]
        region_to_group = {region: group_index
                           for group_index, group in enumerate(groups)
                           for region in group}
        histograms = [Counter() for _ in groups]
        for record in records:
            pole_region = poles * record[0] // slots
            histograms[region_to_group[pole_region]][
                _division_category(record, slots, poles, symmetry)] += 1
        if (all(histogram == histograms[0] for histogram in histograms[1:])
                and all(count % position_divider == 0
                        for count in histograms[0].values())):
            return origin, groups, histograms
    return None


def _plan_start_conductors(records, slots, poles, layers, naa, groups,
                           preferred_layer, phases):
    """Choose one start per branch, exhausting pole groups before positions."""
    pole_divider = len(groups)
    position_divider = naa // pole_divider
    region_to_group = {region: group_index
                       for group_index, group in enumerate(groups)
                       for region in group}
    starts = []
    for phase in range(phases):
        if phases % 3 == 0:
            set_layers = layers // three_phase_set_count(phases)
            first_layer = (phase // 3) * set_layers
            target_layer = (first_layer if preferred_layer == 'first' else
                            first_layer + set_layers - 1)
        else:
            target_layer = 0 if preferred_layer == 'first' else layers - 1
        selected_by_group = []
        for group_index, group in enumerate(groups):
            by_region = {}
            for slot, layer, record_phase, sign in records:
                pole_region = poles * slot // slots
                if (record_phase != phase or layer != target_layer
                        or pole_region not in group):
                    continue
                angle_key = (poles * slot + (slots if sign == -1 else 0)) % (2 * slots)
                by_region.setdefault(pole_region, []).append(
                    (angle_key, slot, sign, pole_region))
            for candidates in by_region.values():
                candidates.sort()
            selected = []
            depth = 0
            while len(selected) < position_divider:
                added = False
                for pole_region in sorted(by_region):
                    candidates = by_region[pole_region]
                    if depth < len(candidates):
                        selected.append(candidates[depth])
                        added = True
                        if len(selected) == position_divider:
                            break
                if not added:
                    raise ValueError(
                        'Not enough boundary-layer conductors for the division plan.')
                depth += 1
            selected_by_group.append(selected)
        for position_group in range(position_divider):
            for pole_group in range(pole_divider):
                angle_key, slot, sign, pole_region = selected_by_group[pole_group][position_group]
                branch = position_group * pole_divider + pole_group
                starts.append({'phase': phase, 'branch': branch, 'slot': slot,
                               'layer': target_layer, 'sign': sign,
                               'signed_angle_key': angle_key,
                               'pole_region': pole_region,
                               'pole_group': pole_group,
                               'position_group': position_group})
    return starts


def _division_mode(pattern, naa, pole_divider, position_divider):
    if pattern == 'UWP':
        if naa == 1:
            return 'uwp_single'
        if naa == 2:
            return 'uwp_dual'
        if pole_divider == 2 and position_divider > 1:
            return 'uwp_half_cycle_position'
    if pattern in ('TSP', 'TLP') and pole_divider == 2:
        return ('half_cycle' if position_divider == 1
                else 'half_cycle_and_position')
    if pole_divider == 1 and position_divider == 1:
        return 'none'
    if pole_divider == 1:
        return 'position_only'
    if position_divider == 1:
        return 'pole_only'
    return 'pole_and_position'


def classify_fractional_branch_plan(slots, poles, layers, naa, pattern,
                                    symmetry='strong', shifts=None,
                                    preferred_layer='first',
                                    prefer_position_division=False,
                                    pole_divider=None, phases=3):
    """Return an Naa division candidate without generating paths.

    This API supports integer and fractional q for comparison, but does not
    replace the legacy integer-q classifier or authorize Pattern dispatch.
    Candidate means only that the requested count partition and starts exist.
    The default is pole-first; position preference is for exploratory previews.
    """
    if not isinstance(pattern, str) or pattern.strip().upper() not in FRACTIONAL_PATTERN_POLICIES:
        raise ValueError('Unknown Pattern for fractional branch planning.')
    pattern = pattern.strip().upper()
    if symmetry not in ('strong', 'weak'):
        raise ValueError("Symmetry must be 'strong' or 'weak'.")
    if isinstance(naa, bool) or not isinstance(naa, Integral) or naa <= 0:
        raise ValueError('Naa must be a positive integer.')
    if preferred_layer not in ('first', 'last'):
        raise ValueError("Preferred layer must be 'first' or 'last'.")
    shifts = None if shifts is None else tuple(shifts)
    rules = symmetry_branch_rules(slots, poles, layers, shifts, phases)
    rule = rules[symmetry]
    base = {'pattern': pattern, 'naa': naa, 'symmetry': symmetry,
            'status': 'rejected', 'reason': '', 'pole_divider': None,
            'position_divider': None, 'pole_groups': [], 'pole_origin': None,
            'division_mode': None, 'category_counts': rule['counts'],
            'category_quotas': {}, 'pole_group_category_counts': [],
            'default_start_conductors': [], 'production_ready': False,
            'connection_capability': 'division_candidate_only',
            'policy': dict(FRACTIONAL_PATTERN_POLICIES[pattern])}
    if naa not in rule['allowed_naa']:
        base['reason'] = (f'Naa={naa} is not allowed by {symmetry} symmetry; '
                          f"allowed values: {', '.join(map(str, rule['allowed_naa']))}.")
        return base

    if pole_divider is not None and (isinstance(pole_divider, bool)
                                    or not isinstance(pole_divider, Integral)
                                    or pole_divider <= 0 or naa % pole_divider
                                    or poles % pole_divider):
        base['reason'] = 'Pole groups must be a positive divisor of both Naa and pole count.'
        return base

    records = phase_map(slots, poles, layers, shifts, phases)
    policy = FRACTIONAL_PATTERN_POLICIES[pattern]
    candidates = [divider for divider in range(1, min(naa, poles) + 1)
                  if naa % divider == 0 and poles % divider == 0]
    if 'max_pole_divider' in policy:
        candidates = [divider for divider in candidates
                      if divider <= policy['max_pole_divider']]
    if pole_divider is not None:
        candidates = [divider for divider in candidates if divider == pole_divider]
    selected = None
    for pole_divider in sorted(candidates, reverse=not prefer_position_division):
        if (prefer_position_division and not policy.get('position_division', True)
                and naa // pole_divider != 1):
            continue
        result = _pole_groups(
            records, slots, poles, naa, symmetry, pole_divider)
        if result is not None:
            selected = pole_divider, result
            break
    if selected is None:
        base['reason'] = 'No branch partition satisfies the selected symmetry rule.'
        return base

    pole_divider, (origin, groups, histograms) = selected
    position_divider = naa // pole_divider
    if not policy.get('position_division', True) and position_divider != 1:
        base.update({'pole_divider': pole_divider,
                     'position_divider': position_divider,
                     'pole_groups': groups, 'pole_origin': origin,
                     'reason': f'{pattern} does not support position division.'})
        return base

    starts = _plan_start_conductors(
        records, slots, poles, layers, naa, groups, preferred_layer, phases)
    base.update({
        'status': 'candidate',
        'reason': ('Division counts and starts are valid; connection topology '
                   'and manufacturability are not evaluated.'),
        'pole_divider': pole_divider,
        'position_divider': position_divider,
        'pole_groups': groups,
        'pole_origin': origin,
        'division_mode': _division_mode(
            pattern, naa, pole_divider, position_divider),
        'category_quotas': rule['quotas'][naa],
        'pole_group_category_counts': [dict(sorted(h.items())) for h in histograms],
        'default_start_conductors': starts,
    })
    return base


def electrical_summary(records, slots, poles, phases=3):
    sums = [0j] * phases
    counts = [0] * phases
    for slot, layer, phase, sign in records:
        sums[phase] += sign * cmath.exp(1j * math.pi * poles * slot / slots)
        counts[phase] += 1

    def sequence_error(vectors):
        scale = max(map(abs, vectors), default=0)
        # Either phase sequence is valid; compare complex vectors, not counts alone.
        sequences = (step for step in range(1, len(vectors))
                     if math.gcd(step, len(vectors)) == 1)
        errors = [max(abs(vectors[k] - vectors[0] * cmath.exp(
            step * 2j * math.pi * k / len(vectors)))
            for k in range(len(vectors))) / scale
            if scale > 1e-12 else float('inf') for step in sequences]
        return min(errors, default=float('inf'))

    if phases > 3 and phases % 3 == 0:
        groups = []
        for group in range(phases // 3):
            start = 3 * group
            vectors = sums[start:start + 3]
            error = sequence_error(vectors)
            groups.append({
                'set': group + 1,
                'phase_indices': tuple(range(start, start + 3)),
                'counts': tuple(counts[start:start + 3]),
                'emf': tuple(vectors),
                'balanced': error < 1e-8,
                'relative_error': error,
                'array_offset_degrees': 360 * group / phases,
            })
        reference = groups[0]['emf'][0] if groups else 0j
        reference_magnitude = abs(reference)
        for group in groups:
            vector = group['emf'][0]
            magnitude_error = (
                abs(abs(vector) - reference_magnitude) / reference_magnitude
                if reference_magnitude > 1e-12 else float('inf'))
            if reference_magnitude > 1e-12 and abs(vector) > 1e-12:
                observed = math.degrees(cmath.phase(vector / reference)) % 360
                expected = group['array_offset_degrees'] % 360
                angle_error = (observed - expected + 180) % 360 - 180
            else:
                observed = float('nan')
                angle_error = float('inf')
            group.update(
                observed_array_offset_degrees=observed,
                array_offset_error_degrees=angle_error,
                relative_emf_magnitude_error=magnitude_error,
                array_aligned=(abs(angle_error) < 1e-8
                               and magnitude_error < 1e-8),
            )
        worst_error = max((group['relative_error'] for group in groups),
                          default=float('inf'))
        array_aligned = all(group['array_aligned'] for group in groups)
        return {'counts': counts, 'emf': sums,
                'balanced': (all(group['balanced'] for group in groups)
                             and array_aligned),
                'relative_error': worst_error,
                'balance_model': 'independent_three_phase_sets',
                'array_aligned': array_aligned,
                'sets': groups}

    error = sequence_error(sums)
    return {'counts': counts, 'emf': sums, 'balanced': error < 1e-8,
            'relative_error': error, 'balance_model': 'symmetric_polyphase',
            'sets': []}
