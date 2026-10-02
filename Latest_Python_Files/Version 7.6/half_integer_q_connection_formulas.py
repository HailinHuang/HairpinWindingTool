"""Exact Pattern connection formulas whose domain is positive half-integer q.

The formula layer owns UWP paths/transfers, the BWP half-integer base wave,
and candidate-only TLP, TSP and ZLP families. Route admission and production
generation remain outside this module; these candidates are not registered
with either one.
"""

from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping, Sequence
from types import SimpleNamespace

from phase_topology import default_phase_map, supports_phase_count
from pattern_identity import (
    analyze_ordered_pattern, circular_travel_steps, pole_region_crossings,
)


DividerTuple = tuple[Fraction, Fraction, Fraction]
ConnectionNode = tuple[int, ...]
Branch = tuple[int, Sequence[ConnectionNode]]


class HalfIntegerQFormulaError(ValueError):
    """The selected parameters do not fit a registered half-integer formula."""


@dataclass(frozen=True)
class HalfIntegerUWPFormulaBinding:
    """Exact source and target divider identity for one UWP formula."""

    route_name: str
    source_dividers: DividerTuple
    target_dividers: DividerTuple
    source_naa: int
    target_naa: int
    construction: str


@dataclass(frozen=True)
class HalfIntegerUWPConnectionDefinition:
    """Start conductors and ordered UWP steps derived from a half-q geometry."""

    starts: tuple[ConnectionNode, ...]
    connections: tuple[tuple[int, int, int], ...]
    slots_per_two_poles: int
    slots_per_pole_region: Fraction


@dataclass(frozen=True)
class HalfIntegerUWPTransferResult:
    """Translated branches and the whole-wave rotations used by the formula."""

    branches: tuple[tuple[int, tuple[ConnectionNode, ...]], ...]
    branch_rotations: tuple[int, ...]
    two_pole_slot_period: int
    slots_per_pole_region: Fraction


@dataclass(frozen=True)
class HalfIntegerBWPBasePathDefinition:
    """BWP positions and pass orientations before phase and slot shifts."""

    positions: tuple[tuple[int, int], ...]
    segment_directions: tuple[bool, ...]
    two_pole_slot_period: int
    short_pitch: int
    long_pitch: int
    passes_per_branch: int


@dataclass(frozen=True)
class TLPShortBranchCandidateDefinition:
    """Immutable q=1/2 TLP short branches, without a top-bottom return."""

    q: Fraction
    dividers: DividerTuple
    num_slots: int
    num_poles: int
    num_phases: int
    num_layers: int
    phase_shift_list: tuple[int, ...]
    inlet_side: str
    naa: int
    branch_length: int
    branches: tuple[tuple[int, int, tuple[ConnectionNode, ...]], ...]
    signed_travel: tuple[tuple[int, tuple[int, ...]], ...]


@dataclass(frozen=True)
class ZLPHalfIntegerRankLaneCandidateDefinition:
    """Candidate-only ZLP rank-lane branches for q=3/2 odd phases."""

    q: Fraction
    dividers: DividerTuple
    num_slots: int
    num_poles: int
    num_phases: int
    num_layers: int
    phase_shift_list: tuple[int, ...]
    inlet_side: str
    naa: int
    branch_length: int
    lane_rank_offsets: tuple[tuple[int, int, int], ...]
    rank_schedule: tuple[tuple[int, int], ...]
    orientation_by_phase: tuple[tuple[int, str], ...]
    branches: tuple[tuple[int, int, tuple[ConnectionNode, ...]], ...]
    signed_travel: tuple[tuple[int, tuple[int, ...]], ...]
    compatible_patterns: tuple[str, ...]
    identity_qualification: str
    status: str


@dataclass(frozen=True)
class TSPHalfIntegerQ1_2LaneCandidateDefinition:
    """Candidate-only TSP lane paths for q=1/2 and non-arrayed odd phases."""

    q: Fraction
    dividers: DividerTuple
    num_slots: int
    num_poles: int
    num_phases: int
    num_layers: int
    phase_shift_list: tuple[int, ...]
    inlet_side: str
    naa: int
    branch_length: int
    lane_rank_plans: tuple[
        tuple[int, int, tuple[int, ...], tuple[int, ...]], ...]
    branches: tuple[tuple[int, int, tuple[ConnectionNode, ...]], ...]
    signed_travel: tuple[tuple[int, tuple[int, ...]], ...]
    compatible_patterns: tuple[str, ...]
    identity_qualification: str
    status: str


class _CandidateBranchDatabase(list):
    """Small identity-check adapter for candidate connection rows."""

    def __init__(self, branches, signed_travel):
        super().__init__(branches)
        self.signed_travel = signed_travel


def _validated_tlp_phase_map(
    phase_by_position: Mapping[tuple[int, int], tuple[int, int]],
    *,
    num_slots: int,
    num_poles: int,
    num_layers: int,
    num_phases: int,
) -> dict[tuple[int, int], tuple[int, int]]:
    if not isinstance(phase_by_position, Mapping):
        raise HalfIntegerQFormulaError(
            "Provide a complete coordinate-to-phase/polarity mapping.")
    expected_phase_map = {
        (slot, layer): (phase, polarity)
        for slot, layer, phase, polarity in
        default_phase_map(num_slots, num_poles, num_layers, num_phases)
    }
    supplied_phase_map: dict[tuple[int, int], tuple[int, int]] = {}
    for position, assignment in phase_by_position.items():
        if (not isinstance(position, tuple) or len(position) != 2
                or any(type(value) is not int for value in position)):
            raise HalfIntegerQFormulaError(
                "Phase-map coordinates must be integer (slot, layer) tuples.")
        if (not isinstance(assignment, Sequence)
                or isinstance(assignment, (str, bytes))
                or len(assignment) != 2
                or any(type(value) is not int for value in assignment)):
            raise HalfIntegerQFormulaError(
                "Each phase-map value must be an integer (phase, polarity) pair.")
        supplied_phase_map[position] = (assignment[0], assignment[1])
    if supplied_phase_map != expected_phase_map:
        raise HalfIntegerQFormulaError(
            "The supplied map must exactly match the complete zero-shift phase map.")
    return supplied_phase_map


def _validated_tsp_phase_map(
    phase_by_position: Mapping[tuple[int, int], tuple[int, int]],
    *,
    num_slots: int,
    num_poles: int,
    num_layers: int,
    num_phases: int,
) -> dict[tuple[int, int], tuple[int, int]]:
    if not isinstance(phase_by_position, Mapping):
        raise HalfIntegerQFormulaError(
            "Provide a complete coordinate-to-phase/polarity mapping.")
    expected = {
        (slot, layer): (phase, polarity)
        for slot, layer, phase, polarity in
        default_phase_map(num_slots, num_poles, num_layers, num_phases)
    }
    supplied = {}
    for position, assignment in phase_by_position.items():
        if (not isinstance(position, tuple) or len(position) != 2
                or any(type(value) is not int for value in position)):
            raise HalfIntegerQFormulaError(
                "Phase-map coordinates must be integer (slot, layer) tuples.")
        if (not isinstance(assignment, Sequence)
                or isinstance(assignment, (str, bytes))
                or len(assignment) != 2
                or any(type(value) is not int for value in assignment)):
            raise HalfIntegerQFormulaError(
                "Each phase-map value must be an integer (phase, polarity) pair.")
        supplied[position] = (assignment[0], assignment[1])
    if supplied != expected:
        raise HalfIntegerQFormulaError(
            "The TSP candidate requires the complete canonical zero-shift phase map.")
    return supplied


def _tsp_q1_2_lane_rank_plan(
    phase: int, branch_ordinal: int, num_layers: int,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Return one parameterized phase-major TSP schedule for q=1/2."""
    pair_count = num_layers // 2
    top_first_pairs = (pair_count - 1, *range(pair_count - 1))

    def pair_visit_flip(visit: int) -> int:
        return max(visit - 1, 0) % 2

    layers = []
    ranks = []
    if phase == 0:
        for visit, pair in enumerate(top_first_pairs):
            rank = branch_ordinal ^ pair_visit_flip(visit)
            layers.extend((2 * pair, 2 * pair + 1))
            ranks.extend((rank, rank))
    elif phase % 2:
        for visit, pair in enumerate(top_first_pairs):
            odd_layer_rank = branch_ordinal ^ pair_visit_flip(visit)
            layers.extend((2 * pair, 2 * pair + 1))
            ranks.extend((1 - odd_layer_rank, odd_layer_rank))
    elif branch_ordinal == 0:
        for pair in range(pair_count):
            rank = pair % 2
            layers.extend((2 * pair, 2 * pair + 1))
            ranks.extend((rank, rank))
    else:
        for pair in top_first_pairs:
            rank = 1 - (pair % 2)
            layers.extend((2 * pair, 2 * pair + 1))
            ranks.extend((rank, rank))
    return tuple(layers), tuple(ranks)


def _validated_zlp_phase_map(
    phase_by_position: Mapping[tuple[int, int], tuple[int, int]],
    *,
    num_slots: int,
    num_poles: int,
    num_layers: int,
    num_phases: int,
) -> dict[tuple[int, int], tuple[int, int]]:
    if not isinstance(phase_by_position, Mapping):
        raise HalfIntegerQFormulaError(
            "Provide a complete coordinate-to-phase/polarity mapping.")
    expected = {
        (slot, layer): (phase, polarity)
        for slot, layer, phase, polarity in
        default_phase_map(num_slots, num_poles, num_layers, num_phases)
    }
    supplied = {}
    for position, assignment in phase_by_position.items():
        if (not isinstance(position, tuple) or len(position) != 2
                or any(type(value) is not int for value in position)):
            raise HalfIntegerQFormulaError(
                "Phase-map coordinates must be integer (slot, layer) tuples.")
        if (not isinstance(assignment, Sequence)
                or isinstance(assignment, (str, bytes))
                or len(assignment) != 2
                or any(type(value) is not int for value in assignment)):
            raise HalfIntegerQFormulaError(
                "Each phase-map value must be an integer (phase, polarity) pair.")
        supplied[position] = (assignment[0], assignment[1])
    if supplied != expected:
        raise HalfIntegerQFormulaError(
            "The ZLP candidate requires the complete canonical zero-shift phase map.")
    return supplied


def _zlp_q3_2_rank_schedule(num_layers: int) -> tuple[tuple[int, int], ...]:
    lane_count = 3
    lane_modulus = 2 * lane_count
    first_half = []
    for pair in range(num_layers // 2):
        base = pair * lane_count
        for lane in range(lane_count - 1):
            first_half.extend((
                (2 * pair, (base + lane) % lane_modulus),
                (2 * pair + 1, (base + lane + 1) % lane_modulus),
            ))
    for layer in range(num_layers - 1, -1, -1):
        pair = layer // 2
        rank = ((pair + 1) * lane_count - 1 if layer % 2 == 0
                else (pair + 1) * lane_count) % lane_modulus
        first_half.append((layer, rank))
    return tuple(first_half + [
        (layer, (rank + lane_count) % lane_modulus)
        for layer, rank in first_half
    ])


def _zlp_q3_2_lane_rank_offsets(
    supplied_phase_map: Mapping[tuple[int, int], tuple[int, int]],
    num_layers: int,
    num_phases: int,
) -> tuple[tuple[int, int, int], ...]:
    lane_count = 3
    lane_modulus = 2 * lane_count
    ordered_slots = {}
    for phase in range(num_phases):
        for layer in range(num_layers):
            slots = sorted(
                slot for (slot, mapped_layer), (mapped_phase, _sign)
                in supplied_phase_map.items()
                if mapped_layer == layer and mapped_phase == phase)
            if len(slots) != lane_modulus:
                raise HalfIntegerQFormulaError(
                    "Each phase and layer must contain exactly six ZLP lane positions.")
            ordered_slots[(phase, layer)] = slots

    offsets = []
    for layer in range(num_layers):
        reference = tuple(
            supplied_phase_map[(slot, layer)][1]
            for slot in ordered_slots[(0, layer)])
        for phase in range(num_phases):
            profile = tuple(
                supplied_phase_map[(slot, layer)][1]
                for slot in ordered_slots[(phase, layer)])
            matches = [offset for offset in range(lane_modulus)
                       if tuple(profile[(rank + offset) % lane_modulus]
                                for rank in range(lane_modulus)) == reference]
            if not matches:
                raise HalfIntegerQFormulaError(
                    "A phase lane has no cyclic polarity alignment to phase zero.")
            minimum_offset = min(matches)
            formula_offset = (phase % 2) * (1 + layer % 2)
            if minimum_offset != formula_offset:
                raise HalfIntegerQFormulaError(
                    "The canonical phase lane offset does not match the "
                    "q=3/2 odd-phase rank formula.")
            offsets.append((phase, layer, minimum_offset))
    return tuple(offsets)


def _zlp_q3_2_exact_steps(
    path: Sequence[ConnectionNode], *, num_slots: int,
    pole_region_width: Fraction,
) -> tuple[int, ...]:
    steps = []
    for source, target in zip(path, path[1:]):
        options = tuple(step for step in circular_travel_steps(
            source[0], target[0], num_slots) if step)
        legal = tuple(
            step for step in options
            if pole_region_crossings(source[0], step, pole_region_width) <= 1)
        if len(legal) != 1:
            raise HalfIntegerQFormulaError(
                "Every ZLP candidate edge must have one shortest legal signed step.")
        steps.append(legal[0])
    return tuple(steps)


def _build_tlp_short_branch_paths(
    supplied_phase_map: Mapping[tuple[int, int], tuple[int, int]],
    *,
    num_slots: int,
    num_phases: int,
    num_layers: int,
    naa: int,
    branch_length: int,
    slot_step: int,
) -> tuple[
    tuple[tuple[int, int, tuple[ConnectionNode, ...]], ...],
    tuple[tuple[int, tuple[int, ...]], ...],
]:
    starts_by_phase: list[list[int]] = [[] for _ in range(num_phases)]
    positions_by_phase: list[set[tuple[int, int]]] = [
        set() for _ in range(num_phases)]
    for (slot, layer), (phase, _polarity) in supplied_phase_map.items():
        positions_by_phase[phase].add((slot, layer))
        if layer == 0:
            starts_by_phase[phase].append(slot)

    branches = []
    signed_travel = []
    produced_positions = []
    produced_by_phase: list[set[tuple[int, int]]] = [
        set() for _ in range(num_phases)]
    for phase, phase_starts in enumerate(starts_by_phase):
        phase_starts.sort()
        if len(phase_starts) != naa:
            raise HalfIntegerQFormulaError(
                "Each phase must have Naa distinct layer-zero starts.")
        for start_slot in phase_starts:
            branch_id = len(branches) + 1
            path = tuple(
                ((start_slot + slot_step * (layer % 2)) % num_slots, layer)
                for layer in range(num_layers)
            )
            steps = tuple(
                slot_step if edge_index % 2 == 0 else -slot_step
                for edge_index in range(num_layers - 1)
            )
            if len(path) != branch_length or len(steps) != branch_length - 1:
                raise HalfIntegerQFormulaError(
                    "The TLP short-branch formula produced an incorrect path length.")

            for node_index, (slot, layer) in enumerate(path):
                mapped_phase, polarity = supplied_phase_map[(slot, layer)]
                expected_polarity = 1 if node_index % 2 == 0 else -1
                if mapped_phase != phase or polarity != expected_polarity:
                    raise HalfIntegerQFormulaError(
                        "A candidate branch must stay in phase and alternate polarity.")
            for edge_index, (first, second) in enumerate(zip(path, path[1:])):
                first_slot, first_layer = first
                second_slot, second_layer = second
                step = steps[edge_index]
                if (second_layer != first_layer + 1
                        or (second_slot - first_slot) % num_slots != step % num_slots):
                    raise HalfIntegerQFormulaError(
                        "A candidate edge does not match its signed adjacent-layer step.")

            branches.append((branch_id, phase, path))
            signed_travel.append((branch_id, steps))
            produced_positions.extend(path)
            produced_by_phase[phase].update(path)

    if (len(branches) != num_phases * naa
            or len(produced_positions) != num_slots * num_layers
            or len(set(produced_positions)) != len(produced_positions)
            or produced_by_phase != positions_by_phase):
        raise HalfIntegerQFormulaError(
            "The candidate branches must uniquely cover every phase-map position.")
    return tuple(branches), tuple(signed_travel)


def build_tlp_half_integer_short_branch_candidate(
    q,
    *,
    dividers,
    num_poles: int,
    num_phases: int,
    num_layers: int,
    phase_shift_list: Sequence[int],
    phase_by_position: Mapping[tuple[int, int], tuple[int, int]],
    inlet_side: str,
) -> TLPShortBranchCandidateDefinition:
    """Build TLP's isolated q=1/2, (1,2,1) short-branch candidate.

    The candidate domain is q=1/2, four poles, three phases, and an even
    layer count L >= 4. Exact arithmetic derives S=q*poles*m=6 slots,
    Naa=Q*D*P2=2 branches per phase, and q*poles*L/Naa=L conductors per
    branch. Starts are ordered by phase and then increasing layer-zero slot.

    ``phase_by_position`` must be the complete canonical zero-shift phase map
    for this geometry. ``phase_shift_list`` is independently required to be
    all zero. The builder does not inspect or validate the caller's Regular/
    neutral transposition configuration. It also does not add the TLP
    top-bottom return required by the existing production route, register
    production admission, or compute/filter by EMF.
    """
    q = _positive_half_integer_q(q)
    if q != Fraction(1, 2):
        raise HalfIntegerQFormulaError(
            "The TLP short-branch candidate currently requires q=1/2.")

    selected_dividers = _divider_tuple(dividers)
    required_dividers = (Fraction(1), Fraction(2), Fraction(1))
    if selected_dividers != required_dividers:
        raise HalfIntegerQFormulaError(
            "The TLP short-branch candidate requires divider tuple (1,2,1).")

    for name, value in (
        ("pole count", num_poles),
        ("phase count", num_phases),
        ("layer count", num_layers),
    ):
        if type(value) is not int or value <= 0:
            raise HalfIntegerQFormulaError(
                f"{name.capitalize()} must be a positive integer.")
    if num_poles != 4 or num_phases != 3:
        raise HalfIntegerQFormulaError(
            "The TLP short-branch candidate requires four poles and three phases.")
    if num_layers < 4 or num_layers % 2:
        raise HalfIntegerQFormulaError(
            "The TLP short-branch candidate requires an even layer count L >= 4.")
    if type(inlet_side) is not str or inlet_side != "insert":
        raise HalfIntegerQFormulaError(
            "The TLP short-branch candidate requires an insert-side inlet.")

    if (not isinstance(phase_shift_list, Sequence)
            or isinstance(phase_shift_list, (str, bytes))
            or len(phase_shift_list) != num_layers
            or any(type(shift) is not int for shift in phase_shift_list)):
        raise HalfIntegerQFormulaError(
            "Provide one integer phase shift for each layer.")
    shifts = tuple(phase_shift_list)
    if any(shifts):
        raise HalfIntegerQFormulaError(
            "The TLP short-branch candidate requires zero phase shifts.")

    slots_exact = q * num_poles * num_phases
    if slots_exact.denominator != 1:
        raise HalfIntegerQFormulaError(
            "q, poles and phases must produce an integer slot count.")
    num_slots = int(slots_exact)
    naa = _integer_naa(selected_dividers)
    branch_length_exact = q * num_poles * num_layers / naa
    if (naa != 2 or branch_length_exact.denominator != 1
            or branch_length_exact != num_layers):
        raise HalfIntegerQFormulaError(
            "The divider identity must produce two branches per phase of length L.")
    branch_length = int(branch_length_exact)

    supplied_phase_map = _validated_tlp_phase_map(
        phase_by_position, num_slots=num_slots, num_poles=num_poles,
        num_layers=num_layers, num_phases=num_phases)
    branches, signed_travel = _build_tlp_short_branch_paths(
        supplied_phase_map, num_slots=num_slots, num_phases=num_phases,
        num_layers=num_layers, naa=naa, branch_length=branch_length,
        slot_step=1)

    return TLPShortBranchCandidateDefinition(
        q=q,
        dividers=selected_dividers,
        num_slots=num_slots,
        num_poles=num_poles,
        num_phases=num_phases,
        num_layers=num_layers,
        phase_shift_list=shifts,
        inlet_side=inlet_side,
        naa=naa,
        branch_length=branch_length,
        branches=branches,
        signed_travel=signed_travel,
    )


def build_tlp_half_integer_odd_phase_short_branch_candidate(
    q,
    *,
    dividers,
    num_poles: int,
    num_phases: int,
    num_layers: int,
    phase_shift_list: Sequence[int],
    phase_by_position: Mapping[tuple[int, int], tuple[int, int]],
    inlet_side: str,
) -> TLPShortBranchCandidateDefinition:
    """Build the candidate TLP short branch for non-arrayed odd phase counts.

    The domain is q=1/2, four poles, odd ``m=num_phases >= 5`` with
    ``m % 3 != 0``, divider tuple (1,2,1), and even ``L=num_layers >= 4``.
    Exact arithmetic gives ``S=2m``, ``Naa=2``, and branch length ``L``.
    Each phase has two positive layer-zero starts. With
    ``delta=(m-1)/2``, a branch follows
    ``slot_j=(s+delta*(j % 2)) % (2*m)`` and ``layer_j=j``; signed travel
    alternates ``+delta, -delta``. The displacement is strictly less than
    the pole-region width ``tau=m/2``.

    This remains an isolated short-branch Candidate: it adds no top-bottom
    return, production admission, or EMF calculation/filter. ``m=3`` remains
    owned by ``build_tlp_half_integer_short_branch_candidate``; multiples of
    three above three use the arrayed phase-set model and are outside this
    odd-phase family.
    """
    q = _positive_half_integer_q(q)
    if q != Fraction(1, 2):
        raise HalfIntegerQFormulaError(
            "The TLP odd-phase candidate currently requires q=1/2.")

    selected_dividers = _divider_tuple(dividers)
    required_dividers = (Fraction(1), Fraction(2), Fraction(1))
    if selected_dividers != required_dividers:
        raise HalfIntegerQFormulaError(
            "The TLP odd-phase candidate requires divider tuple (1,2,1).")

    for name, value in (
        ("pole count", num_poles),
        ("phase count", num_phases),
        ("layer count", num_layers),
    ):
        if type(value) is not int or value <= 0:
            raise HalfIntegerQFormulaError(
                f"{name.capitalize()} must be a positive integer.")
    if num_poles != 4:
        raise HalfIntegerQFormulaError(
            "The TLP odd-phase candidate requires four poles.")
    if (not supports_phase_count(num_phases) or num_phases < 5
            or num_phases % 2 == 0 or num_phases % 3 == 0):
        raise HalfIntegerQFormulaError(
            "The TLP odd-phase candidate requires odd m>=5 outside the arrayed three-phase model.")
    if num_layers < 4 or num_layers % 2:
        raise HalfIntegerQFormulaError(
            "The TLP odd-phase candidate requires an even layer count L >= 4.")
    if type(inlet_side) is not str or inlet_side != "insert":
        raise HalfIntegerQFormulaError(
            "The TLP odd-phase candidate requires an insert-side inlet.")

    if (not isinstance(phase_shift_list, Sequence)
            or isinstance(phase_shift_list, (str, bytes))
            or len(phase_shift_list) != num_layers
            or any(type(shift) is not int for shift in phase_shift_list)):
        raise HalfIntegerQFormulaError(
            "Provide one integer phase shift for each layer.")
    shifts = tuple(phase_shift_list)
    if any(shifts):
        raise HalfIntegerQFormulaError(
            "The TLP odd-phase candidate requires zero phase shifts.")

    slots_exact = q * num_poles * num_phases
    if slots_exact.denominator != 1:
        raise HalfIntegerQFormulaError(
            "q, poles and phases must produce an integer slot count.")
    num_slots = int(slots_exact)
    naa = _integer_naa(selected_dividers)
    branch_length_exact = q * num_poles * num_layers / naa
    if naa != 2 or branch_length_exact != num_layers:
        raise HalfIntegerQFormulaError(
            "The divider identity must produce two branches per phase of length L.")
    branch_length = int(branch_length_exact)

    slot_step_exact = Fraction(num_phases - 1, 2)
    pole_region_width = q * num_phases
    if (slot_step_exact.denominator != 1
            or slot_step_exact >= pole_region_width):
        raise HalfIntegerQFormulaError(
            "The odd-phase slot step must be integral and shorter than one pole region.")
    slot_step = int(slot_step_exact)

    supplied_phase_map = _validated_tlp_phase_map(
        phase_by_position, num_slots=num_slots, num_poles=num_poles,
        num_layers=num_layers, num_phases=num_phases)
    branches, signed_travel = _build_tlp_short_branch_paths(
        supplied_phase_map, num_slots=num_slots, num_phases=num_phases,
        num_layers=num_layers, naa=naa, branch_length=branch_length,
        slot_step=slot_step)

    return TLPShortBranchCandidateDefinition(
        q=q,
        dividers=selected_dividers,
        num_slots=num_slots,
        num_poles=num_poles,
        num_phases=num_phases,
        num_layers=num_layers,
        phase_shift_list=shifts,
        inlet_side=inlet_side,
        naa=naa,
        branch_length=branch_length,
        branches=branches,
        signed_travel=signed_travel,
    )


def build_zlp_half_integer_q3_2_rank_lane_candidate(
    q,
    *,
    dividers,
    num_poles: int,
    num_phases: int,
    num_layers: int,
    phase_shift_list: Sequence[int],
    phase_by_position: Mapping[tuple[int, int], tuple[int, int]],
    inlet_side: str,
    reverse_phases: Sequence[int] = (),
) -> ZLPHalfIntegerRankLaneCandidateDefinition:
    """Build ZLP's q=3/2 rank-lane candidate for non-arrayed odd phases.

    The candidate attempt domain is q=3/2, four poles, m=3 or odd m>=5 not
    divisible by 3, divider tuple (1,1,1), zero shifts, insert-side inlet,
    and even L>=4. Here h=2q=3, each phase/layer has 2h=6 positions, Naa=1,
    and branch length q*poles*L/Naa=6L=2hL. The formula deliberately targets
    the non-arrayed odd-phase topology; each constructed result is still
    checked against the supplied canonical phase map and ordered identity.

    For each layer pair p, the first half emits the lane ranks
    (2p,3p+j),(2p+1,3p+j+1) for j=0,1, then sweeps layers L-1..0 with
    rank 3(p+1)-1 on even layer 2p and 3(p+1) on odd layer 2p+1, modulo 6.
    The second half repeats that schedule with every rank advanced by h=3.
    The canonical phase map determines the minimum cyclic polarity alignment
    for each phase/layer; it is checked against the formula offset
    ``delta[k,l]=(k mod 2)*(1+(l mod 2))``. This lane frame is derived from
    phase-map polarity, not from EMF symmetry.

    ``reverse_phases`` selects reversed branch orientations when the resulting
    complete layout still passes the ordered ZLP identity check. The function
    checks exact signed shortest steps, phase coverage, polarity alternation,
    and ordered ZLP identity. It does not calculate or gate on EMF and does not
    register production route admission or generation.
    """
    q = _positive_half_integer_q(q)
    if q != Fraction(3, 2):
        raise HalfIntegerQFormulaError(
            "The ZLP rank-lane candidate currently requires q=3/2.")

    selected_dividers = _divider_tuple(dividers)
    required_dividers = (Fraction(1), Fraction(1), Fraction(1))
    if selected_dividers != required_dividers:
        raise HalfIntegerQFormulaError(
            "The ZLP rank-lane candidate requires divider tuple (1,1,1).")

    for name, value in (
        ("pole count", num_poles),
        ("phase count", num_phases),
        ("layer count", num_layers),
    ):
        if type(value) is not int or value <= 0:
            raise HalfIntegerQFormulaError(
                f"{name.capitalize()} must be a positive integer.")
    valid_phase_domain = (
        num_phases == 3
        or (num_phases >= 5 and num_phases % 2 == 1
            and num_phases % 3 != 0)
    )
    if (num_poles != 4 or not valid_phase_domain
            or not supports_phase_count(num_phases)):
        raise HalfIntegerQFormulaError(
            "The ZLP rank-lane candidate requires four poles and three phases "
            "or an odd non-arrayed phase count m>=5.")
    if num_layers < 4 or num_layers % 2:
        raise HalfIntegerQFormulaError(
            "The ZLP rank-lane candidate requires even L >= 4.")
    if type(inlet_side) is not str or inlet_side != "insert":
        raise HalfIntegerQFormulaError(
            "The ZLP rank-lane candidate requires an insert-side inlet.")

    if (not isinstance(phase_shift_list, Sequence)
            or isinstance(phase_shift_list, (str, bytes))
            or len(phase_shift_list) != num_layers
            or any(type(shift) is not int for shift in phase_shift_list)):
        raise HalfIntegerQFormulaError(
            "Provide one integer phase shift for each layer.")
    shifts = tuple(phase_shift_list)
    if any(shifts):
        raise HalfIntegerQFormulaError(
            "The ZLP rank-lane candidate requires zero phase shifts.")

    if (not isinstance(reverse_phases, Sequence)
            or isinstance(reverse_phases, (str, bytes))
            or any(type(phase) is not int or not 0 <= phase < num_phases
                   for phase in reverse_phases)
            or len(set(reverse_phases)) != len(reverse_phases)):
        raise HalfIntegerQFormulaError(
            "reverse_phases must contain unique phase indices from "
            f"0 to {num_phases - 1}.")

    slots_exact = q * num_poles * num_phases
    if slots_exact.denominator != 1:
        raise HalfIntegerQFormulaError(
            "q, poles and phases must produce an integer slot count.")
    num_slots = int(slots_exact)
    naa = _integer_naa(selected_dividers)
    branch_length_exact = q * num_poles * num_layers / naa
    if naa != 1 or branch_length_exact != 6 * num_layers:
        raise HalfIntegerQFormulaError(
            "The divider identity must produce one 6L-conductor branch per phase.")
    branch_length = int(branch_length_exact)

    supplied_phase_map = _validated_zlp_phase_map(
        phase_by_position, num_slots=num_slots, num_poles=num_poles,
        num_layers=num_layers, num_phases=num_phases)
    lane_rank_offsets = _zlp_q3_2_lane_rank_offsets(
        supplied_phase_map, num_layers, num_phases)
    offsets = {
        (phase, layer): offset
        for phase, layer, offset in lane_rank_offsets
    }
    lane_slots = {}
    for phase in range(num_phases):
        for layer in range(num_layers):
            lane_slots[(phase, layer)] = sorted(
                slot for (slot, mapped_layer), (mapped_phase, _sign)
                in supplied_phase_map.items()
                if mapped_layer == layer and mapped_phase == phase)

    rank_schedule = _zlp_q3_2_rank_schedule(num_layers)
    if len(rank_schedule) != branch_length:
        raise HalfIntegerQFormulaError(
            "The ZLP rank schedule does not match the 6L branch length.")

    positions_by_phase = {phase: set() for phase in range(num_phases)}
    for (slot, layer), (phase, _sign) in supplied_phase_map.items():
        positions_by_phase[phase].add((slot, layer))
    branches = []
    signed_travel = []
    occupied = []
    for phase in range(num_phases):
        path = tuple(
            (lane_slots[(phase, layer)][
                (rank + offsets[(phase, layer)]) % 6], layer)
            for layer, rank in rank_schedule)
        orientation = "forward"
        if phase in reverse_phases:
            path = tuple(reversed(path))
            orientation = "reverse"
        if len(path) != branch_length or len(set(path)) != branch_length:
            raise HalfIntegerQFormulaError(
                "A ZLP candidate branch must cover distinct positions of length 6L.")
        if set(path) != positions_by_phase[phase]:
            raise HalfIntegerQFormulaError(
                "A ZLP candidate branch must cover every position in its phase.")
        if any(supplied_phase_map[node][0] != phase for node in path):
            raise HalfIntegerQFormulaError(
                "A ZLP candidate branch must remain within its phase.")
        if any(supplied_phase_map[left][1] != -supplied_phase_map[right][1]
               for left, right in zip(path, path[1:])):
            raise HalfIntegerQFormulaError(
                "A ZLP candidate branch must alternate phase polarity.")

        steps = _zlp_q3_2_exact_steps(
            path, num_slots=num_slots,
            pole_region_width=q * num_phases)
        branch_id = len(branches) + 1
        branches.append((branch_id, phase, path))
        signed_travel.append((branch_id, steps))
        occupied.extend(path)

    if len(occupied) != num_slots * num_layers or len(set(occupied)) != len(occupied):
        raise HalfIntegerQFormulaError(
            "The ZLP candidate branches must uniquely cover the full layout.")

    winding = SimpleNamespace(
        q=q, num_slots=num_slots, num_poles=num_poles,
        num_phases=num_phases, num_layers=num_layers, ab=naa)
    layout = SimpleNamespace(
        phase_shift_list=shifts, inlet_from_weld_side=0)
    database = _CandidateBranchDatabase(
        [(branch_id, path) for branch_id, _phase, path in branches],
        dict(signed_travel))
    ordered_identity = analyze_ordered_pattern(
        "ZLP", database, winding, layout)
    compatible_patterns = tuple(ordered_identity["compatible_patterns"])
    if (ordered_identity["ordered_status"] != "valid"
            or compatible_patterns != ("ZLP",)):
        raise HalfIntegerQFormulaError(
            "The generated candidate must pass the unique ordered ZLP identity check.")

    return ZLPHalfIntegerRankLaneCandidateDefinition(
        q=q,
        dividers=selected_dividers,
        num_slots=num_slots,
        num_poles=num_poles,
        num_phases=num_phases,
        num_layers=num_layers,
        phase_shift_list=shifts,
        inlet_side=inlet_side,
        naa=naa,
        branch_length=branch_length,
        lane_rank_offsets=lane_rank_offsets,
        rank_schedule=rank_schedule,
        orientation_by_phase=tuple(
            (phase, "reverse" if phase in reverse_phases else "forward")
            for phase in range(num_phases)),
        branches=tuple(branches),
        signed_travel=tuple(signed_travel),
        compatible_patterns=compatible_patterns,
        identity_qualification=ordered_identity["qualification"],
        status="candidate",
    )


def build_tsp_half_integer_q1_2_lane_candidate(
    q,
    *,
    dividers,
    num_poles: int,
    num_phases: int,
    num_layers: int,
    phase_shift_list: Sequence[int],
    phase_by_position: Mapping[tuple[int, int], tuple[int, int]],
    inlet_side: str,
) -> TSPHalfIntegerQ1_2LaneCandidateDefinition:
    """Build candidate-only q=1/2 TSP lane paths for odd phase counts.

    The domain is four poles, even ``L>=4``, ``(Q,D,P2)=(1,1,2)``, zero phase
    shifts, and insert-side inlet. The phase count is three or odd ``m>=5``
    not divisible by three. With ``m`` phases, ``S=q*poles*m=2m``,
    ``tau=q*m=m/2``, ``Naa=2``, and each branch has
    ``q*poles*L/Naa=L`` conductors.

    Each phase/layer has two sorted lane ranks. With ``n=L/2`` layer pairs,
    phase 0 and odd phases use pair order ``(n-1,0,...,n-2)``; even phases
    ``k>=2`` use ascending pair order for branch 0 and that top-first order
    for branch 1. Rank choices follow the branch, phase parity, and pair-visit
    formulas in ``_tsp_q1_2_lane_rank_plan``. This reduces exactly to the
    existing four-layer schedules when ``n=2``.

    The builder checks exact signed edges, full per-phase coverage, N-to-S
    endpoints, and unique ordered TSP identity. It returns Candidate status
    only; it does not connect route admission/public generation or
    calculate/filter by EMF.
    """
    q = _positive_half_integer_q(q)
    if q != Fraction(1, 2):
        raise HalfIntegerQFormulaError(
            "The TSP lane candidate currently requires q=1/2.")

    selected_dividers = _divider_tuple(dividers)
    required_dividers = (
        Fraction(1), Fraction(1), Fraction(2))
    if selected_dividers != required_dividers:
        raise HalfIntegerQFormulaError(
            "The TSP lane candidate requires divider tuple (1,1,2).")

    for name, value in (
        ("pole count", num_poles),
        ("phase count", num_phases),
        ("layer count", num_layers),
    ):
        if type(value) is not int or value <= 0:
            raise HalfIntegerQFormulaError(
                f"{name.capitalize()} must be a positive integer.")
    valid_phase_domain = (
        num_phases == 3
        or (num_phases >= 5 and num_phases % 2 == 1
            and num_phases % 3 != 0)
    )
    if (num_poles != 4 or not valid_phase_domain
            or not supports_phase_count(num_phases)):
        raise HalfIntegerQFormulaError(
            "The TSP lane candidate requires four poles and three phases or "
            "an odd non-arrayed phase count.")
    if num_layers < 4 or num_layers % 2:
        raise HalfIntegerQFormulaError(
            "The TSP lane candidate requires even L >= 4.")
    if type(inlet_side) is not str or inlet_side != "insert":
        raise HalfIntegerQFormulaError(
            "The TSP lane candidate requires an insert-side inlet.")

    if (not isinstance(phase_shift_list, Sequence)
            or isinstance(phase_shift_list, (str, bytes))
            or len(phase_shift_list) != num_layers
            or any(type(shift) is not int for shift in phase_shift_list)):
        raise HalfIntegerQFormulaError(
            "Provide one integer phase shift for each layer.")
    shifts = tuple(phase_shift_list)
    if any(shifts):
        raise HalfIntegerQFormulaError(
            "The TSP lane candidate requires zero phase shifts.")

    slots_exact = q * num_poles * num_phases
    if slots_exact.denominator != 1:
        raise HalfIntegerQFormulaError(
            "q, poles and phases must produce an integer slot count.")
    num_slots = int(slots_exact)
    naa = _integer_naa(selected_dividers)
    branch_length_exact = q * num_poles * num_layers / naa
    if (naa != 2 or branch_length_exact != num_layers
            or branch_length_exact.denominator != 1):
        raise HalfIntegerQFormulaError(
            "The TSP lane divider identity must produce two L-conductor "
            "branches per phase.")
    branch_length = int(branch_length_exact)

    supplied_phase_map = _validated_tsp_phase_map(
        phase_by_position, num_slots=num_slots, num_poles=num_poles,
        num_layers=num_layers, num_phases=num_phases)
    lane_slots = {}
    positions_by_phase = {phase: set() for phase in range(num_phases)}
    for (slot, layer), (phase, _sign) in supplied_phase_map.items():
        positions_by_phase[phase].add((slot, layer))
    for phase in range(num_phases):
        for layer in range(num_layers):
            slots = tuple(sorted(
                slot for (slot, mapped_layer), (mapped_phase, _sign)
                in supplied_phase_map.items()
                if mapped_phase == phase and mapped_layer == layer))
            if len(slots) != 2:
                raise HalfIntegerQFormulaError(
                    "Each TSP phase/layer must contain exactly two lane positions.")
            lane_slots[(phase, layer)] = slots

    branches = []
    signed_travel = []
    lane_rank_plans = []
    produced_positions = []
    produced_by_phase = {phase: set() for phase in range(num_phases)}
    weld_directions = {pair: set() for pair in range(num_layers // 2)}
    d = (num_phases - 1) // 2
    u = (num_phases + 1) // 2
    pole_region_width = q * num_phases
    for phase in range(num_phases):
        for branch_ordinal in range(2):
            layer_schedule, lane_ranks = _tsp_q1_2_lane_rank_plan(
                phase, branch_ordinal, num_layers)
            path = tuple(
                (lane_slots[(phase, layer)][rank], layer)
                for layer, rank in zip(layer_schedule, lane_ranks)
            )
            if len(path) != branch_length or len(set(path)) != branch_length:
                raise HalfIntegerQFormulaError(
                    "A TSP lane branch must contain L distinct conductors.")
            if set(path).difference(positions_by_phase[phase]):
                raise HalfIntegerQFormulaError(
                    "A TSP lane branch leaves its phase-map phase.")
            polarities = tuple(supplied_phase_map[node][1] for node in path)
            expected_polarities = tuple(
                1 if edge_index % 2 == 0 else -1
                for edge_index in range(branch_length))
            if (polarities != expected_polarities
                    or any(supplied_phase_map[node][0] != phase for node in path)):
                raise HalfIntegerQFormulaError(
                    "TSP lane branches must stay phase-pure and alternate "
                    "N-to-S polarity.")

            steps = []
            for edge_index, (start, end) in enumerate(zip(path, path[1:])):
                choices = circular_travel_steps(
                    start[0], end[0], num_slots)
                if len(choices) != 1:
                    raise HalfIntegerQFormulaError(
                        "Each TSP lane edge must have a unique shortest signed step.")
                step = choices[0]
                if (start[0] + step - end[0]) % num_slots:
                    raise HalfIntegerQFormulaError(
                        "A TSP lane signed step does not reach its endpoint.")
                if pole_region_crossings(
                        start[0], step, pole_region_width) > 1:
                    raise HalfIntegerQFormulaError(
                        "A TSP lane edge crosses more than one exact pole region.")
                steps.append(step)
                if edge_index % 2 == 0:
                    layer_step = end[1] - start[1]
                    pair = min(start[1], end[1]) // 2
                    if (abs(layer_step) != 1
                            or start[1] // 2 != end[1] // 2
                            or pair not in weld_directions):
                        raise HalfIntegerQFormulaError(
                            "A TSP lane weld must stay within an adjacent layer pair.")
                    direction = (1 if step > 0 else -1) * (
                        1 if layer_step > 0 else -1)
                    weld_directions[pair].add(direction)
            pair_count = num_layers // 2
            if phase >= 2 and phase % 2 == 0 and branch_ordinal == 0:
                expected_steps_list = [d]
                for _pair in range(pair_count - 1):
                    expected_steps_list.extend((u, d))
            else:
                if phase >= 2 and phase % 2 == 0:
                    return_step = u if pair_count % 2 == 0 else -d
                else:
                    return_step = -d
                expected_steps_list = [d, return_step]
                for lower_pair in range(pair_count - 1):
                    expected_steps_list.append(d)
                    if lower_pair < pair_count - 2:
                        expected_steps_list.append(u)
            expected_steps = tuple(expected_steps_list)
            if tuple(steps) != expected_steps:
                raise HalfIntegerQFormulaError(
                    "The phase lane steps do not match the exact q=1/2 rule.")

            branch_id = phase * 2 + branch_ordinal + 1
            branches.append((branch_id, phase, path))
            signed_travel.append((branch_id, tuple(steps)))
            lane_rank_plans.append((
                branch_id, phase, layer_schedule, lane_ranks))
            produced_positions.extend(path)
            produced_by_phase[phase].update(path)

    if any(directions != {1} for directions in weld_directions.values()):
        raise HalfIntegerQFormulaError(
            "TSP lower-to-higher weld travel must be positive in each layer pair.")
    if (len(branches) != num_phases * naa
            or len(produced_positions) != num_slots * num_layers
            or len(set(produced_positions)) != len(produced_positions)
            or produced_by_phase != positions_by_phase):
        raise HalfIntegerQFormulaError(
            "The TSP lane branches must uniquely cover every phase-map position.")

    winding = SimpleNamespace(
        q=q, num_slots=num_slots, num_poles=num_poles,
        num_phases=num_phases, num_layers=num_layers, ab=naa)
    layout = SimpleNamespace(
        phase_shift_list=shifts, inlet_from_weld_side=0)
    database = _CandidateBranchDatabase(
        [(branch_id, path) for branch_id, _phase, path in branches],
        dict(signed_travel))
    ordered_identity = analyze_ordered_pattern(
        "TSP", database, winding, layout)
    compatible_patterns = tuple(ordered_identity["compatible_patterns"])
    if (ordered_identity["ordered_status"] != "valid"
            or compatible_patterns != ("TSP",)):
        raise HalfIntegerQFormulaError(
            "The generated candidate must pass the unique ordered TSP identity check.")

    return TSPHalfIntegerQ1_2LaneCandidateDefinition(
        q=q,
        dividers=selected_dividers,
        num_slots=num_slots,
        num_poles=num_poles,
        num_phases=num_phases,
        num_layers=num_layers,
        phase_shift_list=shifts,
        inlet_side=inlet_side,
        naa=naa,
        branch_length=branch_length,
        lane_rank_plans=tuple(lane_rank_plans),
        branches=tuple(branches),
        signed_travel=tuple(signed_travel),
        compatible_patterns=compatible_patterns,
        identity_qualification=ordered_identity["qualification"],
        status="candidate",
    )


def build_bwp_half_integer_base_path(
    q,
    *,
    num_slots: int,
    num_poles: int,
    num_phases: int,
    num_layers: int,
) -> HalfIntegerBWPBasePathDefinition:
    """Derive BWP's alternating half-q passes before phase-specific rotation.

    Each pass traverses every layer pair. Its circumferential travel alternates
    by pass, the layer-pair order reverses on reverse passes, and the next pass
    seed retreats by the short half-wave pitch. Phase rotation, per-layer
    shifts, phasor tags, and generated-layout validation remain with the caller.
    """
    q = _positive_half_integer_q(q)
    for name, value in (
        ("slot count", num_slots),
        ("pole count", num_poles),
        ("phase count", num_phases),
        ("layer count", num_layers),
    ):
        if type(value) is not int or value <= 0:
            raise HalfIntegerQFormulaError(
                f"{name.capitalize()} must be a positive integer.")
    if num_poles < 2 or num_poles % 2:
        raise HalfIntegerQFormulaError("BWP requires an even pole count.")
    if num_layers < 2 or num_layers % 2:
        raise HalfIntegerQFormulaError("BWP requires an even layer count.")
    if not supports_phase_count(num_phases):
        raise HalfIntegerQFormulaError(
            "BWP requires a currently supported phase count.")

    slots_from_q = q * num_poles * num_phases
    if slots_from_q.denominator != 1 or slots_from_q != num_slots:
        raise HalfIntegerQFormulaError(
            "q, poles and phases must produce the exact slot count.")

    period = 2 * num_phases * q
    passes = 2 * q
    if period.denominator != 1 or passes.denominator != 1:
        raise HalfIntegerQFormulaError(
            "BWP half-integer q must produce integral wave periods and passes.")
    period = int(period)
    passes = int(passes)
    short_pitch = period // 2
    long_pitch = period - short_pitch
    pairs = range(num_layers // 2)
    seed = 0
    positions = []
    segment_directions = []
    for pass_index in range(passes):
        forward = pass_index % 2 == 0
        ordered_pairs = pairs if forward else reversed(pairs)
        for pair in ordered_pairs:
            segment_directions.append(forward)
            for index in range(num_poles):
                offset = ((index // 2) * period
                          + (index % 2) * short_pitch)
                slot = (seed + (offset if forward else -offset)) % num_slots
                layer = 2 * pair + (
                    index % 2 if forward else 1 - index % 2)
                positions.append((slot, layer))
        seed = (positions[-1][0] - short_pitch) % num_slots

    if len(positions) != num_poles * len(segment_directions):
        raise HalfIntegerQFormulaError(
            "Fractional BWP wave module has an incomplete sweep.")
    return HalfIntegerBWPBasePathDefinition(
        positions=tuple(positions),
        segment_directions=tuple(segment_directions),
        two_pole_slot_period=period,
        short_pitch=short_pitch,
        long_pitch=long_pitch,
        passes_per_branch=passes,
    )


def resolve_uwp_half_integer_formula(
    route_name: str,
    q,
    target_dividers,
    *,
    pole_pairs: int | None = None,
) -> HalfIntegerUWPFormulaBinding:
    """Bind one registered UWP formula without widening route admission.

    The base construction is `(q, 1, 2)`. Its existing transfer target is
    `(q, 2, 1)`. For both, `Naa = Q * D * P2 = 2*q`; the factor 2 is the
    denominator-clearing factor for positive half-integer q. The existing
    explicit split condition `D*P2 in {1, 2}` excludes `(q, D, 2)` for D>1.
    """
    q = _positive_half_integer_q(q)
    selected = _divider_tuple(target_dividers)

    if route_name == "uwp_half_integer_p2":
        source = target = (q, Fraction(1), Fraction(2))
        construction = "full-wave P2 parent"
    elif route_name == "uwp_half_integer_q_pp":
        # For positive half-integers, q > 1 is equivalent to floor(q) > 0;
        # q=1/2 has no second inlet cohort to transfer.
        if q <= 1:
            raise HalfIntegerQFormulaError(
                "The q-and-pp transfer requires a nonempty second inlet cohort.")
        source = (q, Fraction(1), Fraction(2))
        target = (q, Fraction(2), Fraction(1))
        construction = "reverse and translate the second inlet cohort"
    else:
        raise HalfIntegerQFormulaError(
            f"No half-integer UWP formula is registered for {route_name!r}.")

    if selected != target:
        raise HalfIntegerQFormulaError(
            f"{route_name} requires target dividers {target}.")

    source_naa = _integer_naa(source)
    target_naa = _integer_naa(target)
    if source_naa != target_naa:
        raise HalfIntegerQFormulaError(
            "This half-integer parent transformation must preserve Naa.")
    if target[1] * target[2] not in (1, 2):
        raise HalfIntegerQFormulaError(
            "The explicit UWP split requires pp-divider * P2 in {1, 2}.")
    if pole_pairs is not None:
        if type(pole_pairs) is not int or pole_pairs <= 0:
            raise HalfIntegerQFormulaError("Pole-pair count must be a positive integer.")
        pp_divider = target[1]
        if pp_divider.denominator != 1 or pole_pairs % int(pp_divider):
            raise HalfIntegerQFormulaError(
                "The pp-divider must be an integer factor of the pole-pair count.")

    return HalfIntegerUWPFormulaBinding(
        route_name=route_name,
        source_dividers=source,
        target_dividers=target,
        source_naa=source_naa,
        target_naa=target_naa,
        construction=construction,
    )


def build_uwp_half_integer_p2_definition(
    q,
    *,
    dividers,
    num_slots: int,
    num_poles: int,
    num_phases: int,
    num_layers: int,
    phase_shift_list: Sequence[int],
    phase_by_position: Mapping[tuple[int, int], int],
) -> HalfIntegerUWPConnectionDefinition:
    """Derive the UWP P2 parent's ordered start and connection formula.

    The two-pole wave period is `2*q*num_phases` slots, so each ordinary step
    uses its floor/ceiling half-pitches. UWP's alternating layer-pair steps
    follow the existing UWP connection identity; the first pole pair is
    represented by a separate final pair, hence the `pole_pairs_per_sector - 1`
    repeat count. Phase sorting and sector offsets come from the geometry.
    """
    q = _positive_half_integer_q(q)
    binding = resolve_uwp_half_integer_formula(
        "uwp_half_integer_p2", q, dividers)
    geometry = _validate_geometry(
        q, binding.target_dividers,
        num_slots=num_slots,
        num_poles=num_poles,
        num_phases=num_phases,
        num_layers=num_layers,
        phase_shift_list=phase_shift_list,
    )

    if not isinstance(phase_by_position, Mapping):
        raise HalfIntegerQFormulaError("A shifted phase map is required for start ordering.")

    period = geometry["slots_per_two_poles"]
    slots_per_sector = geometry["slots_per_sector"]
    pp_divider = int(binding.target_dividers[1])
    shift0 = phase_shift_list[0]
    starts_with_phase = []
    for sector in range(pp_divider):
        for slot_in_period in range(period):
            unshifted_slot = sector * slots_per_sector + slot_in_period
            slot = (unshifted_slot + shift0) % num_slots
            position = (slot, 0)
            if position not in phase_by_position:
                raise HalfIntegerQFormulaError(
                    f"The shifted phase map has no start record for {position}.")
            start = (slot, 0, unshifted_slot)
            starts_with_phase.append((phase_by_position[position], unshifted_slot, start))

    starts = tuple(row[2] for row in sorted(starts_with_phase, key=lambda row: (row[0], row[1])))
    expected_starts = binding.target_naa * num_phases
    if len(starts) != expected_starts:
        raise HalfIntegerQFormulaError(
            "The half-integer P2 starts do not match the integer Naa branch count.")

    alternating_pair = ((1, 1, 0), (1, -1, 1))
    pole_pairs_per_sector = geometry["poles_per_sector"] // 2
    layer_pair = (
        alternating_pair * (pole_pairs_per_sector - 1)
        + ((1, 1, 0), (1, 1, 1))
    )
    ordered_connections = layer_pair * (num_layers // 2)
    connections = tuple(ordered_connections[:-1])

    # The one-pole region width is phase_count*q, retained as an exact Fraction
    # for the signed pole-boundary checks performed by the public validator.
    return HalfIntegerUWPConnectionDefinition(
        starts=starts,
        connections=connections,
        slots_per_two_poles=period,
        slots_per_pole_region=Fraction(num_phases) * q,
    )


def transfer_uwp_half_integer_q_pp(
    source_branches: Sequence[Branch],
    north_to_south_branches: Sequence[Branch],
    *,
    q,
    source_dividers,
    target_dividers,
    num_slots: int,
    num_poles: int,
    num_phases: int,
    num_layers: int,
    phase_shift_list: Sequence[int],
    pole_sign_by_position: Mapping[tuple[int, int], int],
) -> HalfIntegerUWPTransferResult:
    """Move reversed S-inlet parent waves by complete two-pole periods.

    The source and oriented branch lists preserve their generated order. The
    caller obtains the latter with the shifted-map N-to-S helper, which also
    updates terminal-facing metadata. This formula owns the half-integer cohort
    selection, exact whole-wave translation, and order-preserving edge checks.
    """
    q = _positive_half_integer_q(q)
    binding = resolve_uwp_half_integer_formula(
        "uwp_half_integer_q_pp", q, target_dividers,
        pole_pairs=(num_poles // 2 if type(num_poles) is int else None),
    )
    if _divider_tuple(source_dividers) != binding.source_dividers:
        raise HalfIntegerQFormulaError(
            "The q-and-pp formula requires the public (q, 1, 2) parent.")
    geometry = _validate_geometry(
        q, binding.target_dividers,
        num_slots=num_slots,
        num_poles=num_poles,
        num_phases=num_phases,
        num_layers=num_layers,
        phase_shift_list=phase_shift_list,
    )
    if not isinstance(pole_sign_by_position, Mapping):
        raise HalfIntegerQFormulaError("A shifted pole-sign map is required.")
    if len(source_branches) != len(north_to_south_branches):
        raise HalfIntegerQFormulaError("Source and oriented parent counts differ.")
    if len(source_branches) != binding.target_naa * num_phases:
        raise HalfIntegerQFormulaError("The parent count does not match the target Naa.")
    source_ids = tuple(branch_id for branch_id, _path in source_branches)
    target_ids = tuple(branch_id for branch_id, _path in north_to_south_branches)
    if len(set(source_ids)) != len(source_ids) or source_ids != target_ids:
        raise HalfIntegerQFormulaError(
            "Source and oriented parents must preserve unique branch identity and order.")

    period = geometry["slots_per_two_poles"]
    slots_per_region = geometry["slots_per_pole_region"]
    rotations = []
    transformed = []
    saw_second_cohort = False
    for source, oriented in zip(source_branches, north_to_south_branches):
        source_id, source_path = source
        branch_id, path = oriented
        if source_id != branch_id:
            raise HalfIntegerQFormulaError("Parent branch order or identity changed.")
        if not source_path or not path:
            raise HalfIntegerQFormulaError("A half-integer parent branch is empty.")
        if any(len(node) < 2 for node in (*source_path, *path)):
            raise HalfIntegerQFormulaError("Branch nodes require slot and layer coordinates.")

        source_start = tuple(source_path[0][:2])
        source_end = tuple(source_path[-1][:2])
        try:
            source_inlet_sign = pole_sign_by_position[source_start]
            source_outlet_sign = pole_sign_by_position[source_end]
        except KeyError as exc:
            raise HalfIntegerQFormulaError(
                "The shifted pole map is missing a source terminal.") from exc
        if (source_inlet_sign, source_outlet_sign) not in ((1, -1), (-1, 1)):
            raise HalfIntegerQFormulaError(
                "Each P2 parent must span one N-to-S or S-to-N pole pair.")
        move_second = source_inlet_sign < 0
        saw_second_cohort = saw_second_cohort or move_second
        expected_orientation = (
            tuple(tuple(node) for node in source_path)
            if not move_second
            else tuple(tuple(node) for node in reversed(source_path))
        )
        if tuple(tuple(node) for node in path) != expected_orientation:
            raise HalfIntegerQFormulaError(
                "P2 orientation must preserve generated order or reverse the full path.")

        try:
            oriented_start_sign = pole_sign_by_position[tuple(path[0][:2])]
            oriented_end_sign = pole_sign_by_position[tuple(path[-1][:2])]
        except KeyError as exc:
            raise HalfIntegerQFormulaError(
                "The shifted pole map is missing an oriented terminal.") from exc
        if (oriented_start_sign, oriented_end_sign) != (1, -1):
            raise HalfIntegerQFormulaError(
                "Transferred branches must be oriented from N inlet to S outlet.")

        source_positions = {tuple(node[:2]) for node in source_path}
        if source_positions != {tuple(node[:2]) for node in path}:
            raise HalfIntegerQFormulaError(
                "N-to-S orientation changed parent conductor membership.")

        first_slot, first_layer = path[0][:2]
        if not (0 <= first_layer < num_layers):
            raise HalfIntegerQFormulaError("A branch starts outside the layer range.")
        inlet = (first_slot - phase_shift_list[first_layer]) % num_slots
        # Keep the established integer slot-grid convention for the opposite
        # half-circumference offset; period alignment is derived from q.
        delta = num_slots // 2 + inlet % period - inlet if move_second else 0
        rotations.append(delta)

        shifted_path = tuple(
            ((node[0] + delta) % num_slots, *node[1:]) for node in path
        )
        if {tuple(node[:2]) for node in shifted_path} != source_positions:
            raise HalfIntegerQFormulaError(
                "Whole-wave translation changed parent conductor membership.")
        _validate_wave_edges(
            shifted_path, num_slots, num_layers, period, phase_shift_list)
        transformed.append((branch_id, shifted_path))

    if not saw_second_cohort:
        raise HalfIntegerQFormulaError(
            "The source has no second inlet cohort to transfer.")

    return HalfIntegerUWPTransferResult(
        branches=tuple(transformed),
        branch_rotations=tuple(rotations),
        two_pole_slot_period=period,
        slots_per_pole_region=slots_per_region,
    )


def _validate_geometry(
    q: Fraction,
    dividers: DividerTuple,
    *,
    num_slots: int,
    num_poles: int,
    num_phases: int,
    num_layers: int,
    phase_shift_list: Sequence[int],
) -> dict[str, int | Fraction]:
    for name, value in (
        ("slot count", num_slots),
        ("pole count", num_poles),
        ("phase count", num_phases),
        ("layer count", num_layers),
    ):
        if type(value) is not int or value <= 0:
            raise HalfIntegerQFormulaError(f"{name.capitalize()} must be a positive integer.")
    if num_poles % 2:
        raise HalfIntegerQFormulaError("Half-integer UWP requires an even pole count.")
    if num_layers % 2:
        raise HalfIntegerQFormulaError("Half-integer UWP requires an even layer count.")
    if not supports_phase_count(num_phases):
        raise HalfIntegerQFormulaError(
            "Half-integer UWP requires a currently supported phase count.")
    if not isinstance(phase_shift_list, Sequence) or len(phase_shift_list) != num_layers:
        raise HalfIntegerQFormulaError(
            "Half-integer UWP requires one integer phase shift per layer.")
    if any(type(shift) is not int for shift in phase_shift_list):
        raise HalfIntegerQFormulaError("Phase shifts must be integer slot offsets.")

    slots_from_q = q * num_poles * num_phases
    if slots_from_q.denominator != 1 or slots_from_q != num_slots:
        raise HalfIntegerQFormulaError(
            "q, poles and phases must produce the exact slot count.")

    pp_divider = dividers[1]
    if pp_divider.denominator != 1:
        raise HalfIntegerQFormulaError("The pp-divider must be an integer factor.")
    pp_divider = int(pp_divider)
    pole_pairs = num_poles // 2
    if pole_pairs % pp_divider:
        raise HalfIntegerQFormulaError(
            "The pp-divider must divide the pole-pair count.")
    if num_poles % pp_divider or num_slots % pp_divider:
        raise HalfIntegerQFormulaError("The sector counts must be integral.")

    period = 2 * q * num_phases
    if period.denominator != 1 or period <= 0:
        raise HalfIntegerQFormulaError(
            "The two-pole slot period must be a positive integer.")
    if num_slots // int(period) != num_poles // 2:
        raise HalfIntegerQFormulaError(
            "The slot count must contain an exact integer number of two-pole periods.")
    poles_per_sector = num_poles // pp_divider
    if poles_per_sector < 2 or poles_per_sector % 2:
        raise HalfIntegerQFormulaError(
            "Each pp-divider sector must contain a positive whole pole pair.")

    return {
        "slots_per_sector": num_slots // pp_divider,
        "poles_per_sector": poles_per_sector,
        "slots_per_two_poles": int(period),
        "slots_per_pole_region": q * num_phases,
    }


def _validate_wave_edges(
    path: Sequence[ConnectionNode],
    num_slots: int,
    num_layers: int,
    period: int,
    phase_shift_list: Sequence[int],
) -> None:
    if len(path) < 2:
        raise HalfIntegerQFormulaError("A transferred wave must contain a connection edge.")
    allowed_pitches = {period // 2, (period + 1) // 2}
    directions = set()
    for first, second in zip(path, path[1:]):
        first_slot, first_layer = first[:2]
        second_slot, second_layer = second[:2]
        if not (0 <= first_layer < num_layers and 0 <= second_layer < num_layers):
            raise HalfIntegerQFormulaError("A wave edge leaves the layer range.")
        if abs(second_layer - first_layer) != 1:
            raise HalfIntegerQFormulaError(
                "A half-integer UWP wave edge must join adjacent layers.")
        delta = (
            second_slot - phase_shift_list[second_layer]
            - first_slot + phase_shift_list[first_layer]
        ) % num_slots
        signed = delta if delta <= num_slots // 2 else delta - num_slots
        if abs(signed) not in allowed_pitches:
            raise HalfIntegerQFormulaError(
                "A half-integer UWP wave edge has an unsupported signed pitch.")
        directions.add(1 if signed > 0 else -1)
    if len(directions) != 1:
        raise HalfIntegerQFormulaError(
            "A half-integer UWP branch reverses its wave travel.")


def _positive_half_integer_q(value) -> Fraction:
    q = _fraction(value, "q")
    if q <= 0 or q.denominator != 2:
        raise HalfIntegerQFormulaError("q must be a positive half-integer.")
    return q


def _divider_tuple(values) -> DividerTuple:
    if not isinstance(values, Sequence) or len(values) != 3:
        raise HalfIntegerQFormulaError(
            "Divider identity requires (q-divider, pp-divider, P2).")
    factors = tuple(_fraction(value, "divider") for value in values)
    if any(value <= 0 for value in factors):
        raise HalfIntegerQFormulaError("Divider factors must be positive.")
    return factors  # type: ignore[return-value]


def _integer_naa(dividers: DividerTuple) -> int:
    naa = dividers[0] * dividers[1] * dividers[2]
    if naa <= 0 or naa.denominator != 1:
        raise HalfIntegerQFormulaError(
            "The divider product Naa=Q*D*P2 must be a positive integer.")
    return int(naa)


def _fraction(value, label: str) -> Fraction:
    if isinstance(value, bool):
        raise HalfIntegerQFormulaError(f"{label.capitalize()} cannot be boolean.")
    try:
        return Fraction(str(value))
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        raise HalfIntegerQFormulaError(f"{label.capitalize()} must be an exact rational.") from exc
