"""Parameter-derived branch transformations and constructors for divider routes.

This module owns path-composition and route-specific path formulas. Pattern
admission and generated-layout validation remain in ``get_winding_pattern``.
Divider triples are always interpreted as ``(q-divider, pp-divider, P2)``.
"""

from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from math import gcd, prod
from collections import Counter
from typing import Literal, Mapping, Sequence


DividerTuple = tuple[int | Fraction, int | Fraction, int | Fraction]
FormulaOperation = Literal[
    "identity", "partition", "grouped_partition", "join", "indexed_translation",
    "zpp_centered_entry_translation"]
FormulaOrder = Literal["source", "piece"]
EntryTensorKey = tuple[int, int, int, int]


@dataclass(frozen=True)
class DividerFactorRef:
    """Reference and scale one target divider factor in a source binding."""

    target_index: int
    scale: Fraction = Fraction(1, 1)


SourceFactor = int | Fraction | DividerFactorRef | None


class DividerFormulaError(ValueError):
    """Raised when divider factors cannot produce the requested transform."""


def phase_set_local_dividers(
    global_dividers: DividerTuple, set_count: int,
) -> DividerTuple:
    """Scale a global integer route into one equal three-phase set.

    Multiplying Q by the number of sets and dividing D by that same count
    preserves ``Naa = Q * D * P2`` while matching the local q and layer view.
    """
    if (isinstance(set_count, bool) or not isinstance(set_count, int)
            or set_count < 1):
        raise DividerFormulaError(
            "A phase-set divider mapping requires a positive integer set count.")
    if (not isinstance(global_dividers, tuple) or len(global_dividers) != 3
            or any(isinstance(value, bool) or not isinstance(value, int)
                   or value < 1 for value in global_dividers)):
        raise DividerFormulaError(
            "Phase-set divider mapping requires three positive integer factors.")
    q_divider, pp_divider, p2_divider = global_dividers
    if pp_divider % set_count:
        raise DividerFormulaError(
            "The global PP divider must be divisible by the phase-set count.")
    local = (q_divider * set_count, pp_divider // set_count, p2_divider)
    if _naa(local) != _naa(global_dividers):
        raise DividerFormulaError(
            "Phase-set divider mapping must preserve Naa.")
    return local


def zpp_indexed_sector_stride(sector_count: int, repetitions: int) -> int:
    """Return the least stride that permutes ZPP translation and lane classes.

    Translating source branch ``j`` by sector ``a*j`` gives lane classes
    ``c + (2*r*a - 1)*j (mod D)``. The stride must therefore be coprime to
    ``D`` and make the resulting class coefficient coprime to ``D``.
    """
    if (isinstance(sector_count, bool) or not isinstance(sector_count, int)
            or sector_count < 2 or isinstance(repetitions, bool)
            or not isinstance(repetitions, int) or repetitions < 1):
        raise DividerFormulaError(
            "ZPP indexed translation requires D >= 2 and a positive repetition count.")
    for stride in range(1, sector_count):
        if (gcd(stride, sector_count) == 1
                and gcd(sector_count, 2 * repetitions * stride - 1) == 1):
            return stride
    raise DividerFormulaError(
        "No ZPP indexed sector stride satisfies both permutation conditions.")


@dataclass(frozen=True)
class FormulaBranch:
    """A generated child path and the parent path identities it came from."""

    source_ids: tuple[int, ...]
    part_index: int
    path: list


@dataclass(frozen=True)
class ParentEntry:
    """One ordered conductor reference from a parent branch path."""

    branch_id: int
    path_index: int
    key: EntryTensorKey
    node: tuple


def derive_parent_entry_tensor(
    branches: Sequence[tuple[int, Sequence]],
    *,
    key_by_coordinate: Mapping[tuple[int, int], EntryTensorKey],
) -> dict[EntryTensorKey, tuple[ParentEntry, ...]]:
    """Index ordered parent entries by (phase, cohort, PP sector, q group).

    Coordinate-to-key classification is supplied by the caller from its
    Pattern topology. This helper preserves source branch/path order and does
    not infer Pattern support or electrical meaning.
    """
    if not branches:
        raise DividerFormulaError(
            "An inlet tensor requires at least one parent branch.")
    if not isinstance(key_by_coordinate, Mapping):
        raise DividerFormulaError(
            "An inlet tensor requires a coordinate-to-key mapping.")

    for coordinate, key in key_by_coordinate.items():
        if (not isinstance(coordinate, tuple) or len(coordinate) != 2
                or any(type(value) is not int or value < 0
                       for value in coordinate)):
            raise DividerFormulaError(
                "Inlet-tensor coordinates must be non-negative slot/layer pairs.")
        _validate_entry_tensor_key(key)

    tensor = {}
    seen_coordinates = set()
    seen_branch_ids = set()
    for branch_id, source_path in branches:
        if type(branch_id) is not int or branch_id < 0:
            raise DividerFormulaError(
                "Inlet-tensor parent branch IDs must be non-negative integers.")
        if branch_id in seen_branch_ids:
            raise DividerFormulaError(
                "Inlet-tensor parent branch IDs must be unique.")
        seen_branch_ids.add(branch_id)
        if not source_path:
            raise DividerFormulaError(
                f"Inlet-tensor parent branch {branch_id} has an empty path.")
        for path_index, node in enumerate(source_path):
            if (not isinstance(node, Sequence) or isinstance(node, (str, bytes))
                    or len(node) < 2
                    or type(node[0]) is not int or node[0] < 0
                    or type(node[1]) is not int or node[1] < 0):
                raise DividerFormulaError(
                    f"Inlet-tensor parent branch {branch_id} has an invalid conductor coordinate.")
            coordinate = (node[0], node[1])
            if coordinate in seen_coordinates:
                raise DividerFormulaError(
                    f"Inlet-tensor conductor {coordinate} appears more than once.")
            seen_coordinates.add(coordinate)
            try:
                key = key_by_coordinate[coordinate]
            except KeyError as exc:
                raise DividerFormulaError(
                    f"Conductor {coordinate} has no inlet-tensor key.") from exc
            entry = ParentEntry(
                branch_id=branch_id, path_index=path_index,
                key=key, node=tuple(node))
            tensor.setdefault(key, []).append(entry)

    return {key: tuple(entries) for key, entries in tensor.items()}


def walk_parent_entry_tensor(
    tensor: Mapping[EntryTensorKey, Sequence[ParentEntry]],
    keys: Sequence[EntryTensorKey],
    *,
    part_index: int = 0,
    direction: int = 1,
) -> FormulaBranch:
    """Compose tensor cells into one provenance-preserving ordered branch.

    Entries within a cell retain source branch/path order. A negative
    direction reverses the complete walk, including cell order.
    """
    if not isinstance(tensor, Mapping) or not keys:
        raise DividerFormulaError(
            "An ordered inlet walk requires a tensor and at least one cell key.")
    if type(part_index) is not int or part_index < 0:
        raise DividerFormulaError(
            "Ordered inlet-walk part indexes must be non-negative integers.")
    if type(direction) is not int or direction not in (-1, 1):
        raise DividerFormulaError(
            "Ordered inlet-walk direction must be +1 or -1.")

    entries = []
    seen_coordinates = set()
    for key in keys:
        _validate_entry_tensor_key(key)
        try:
            cell = tensor[key]
        except KeyError as exc:
            raise DividerFormulaError(
                f"Inlet-tensor cell {key} does not exist.") from exc
        if not cell:
            raise DividerFormulaError(
                f"Inlet-tensor cell {key} is empty.")
        for entry in cell:
            if not isinstance(entry, ParentEntry) or entry.key != key:
                raise DividerFormulaError(
                    f"Inlet-tensor cell {key} contains an invalid parent entry.")
            coordinate = tuple(entry.node[:2])
            if coordinate in seen_coordinates:
                raise DividerFormulaError(
                    f"Ordered inlet walk repeats conductor {coordinate}.")
            seen_coordinates.add(coordinate)
            entries.append(entry)

    if direction < 0:
        entries.reverse()
    source_ids = tuple(dict.fromkeys(entry.branch_id for entry in entries))
    return FormulaBranch(
        source_ids=source_ids, part_index=part_index,
        path=[entry.node for entry in entries])


def _validate_entry_tensor_key(key) -> None:
    if (not isinstance(key, tuple) or len(key) != 4
            or any(type(value) is not int or value < 0 for value in key)):
        raise DividerFormulaError(
            "Inlet-tensor keys must be non-negative (phase, cohort, PP sector, q group) tuples.")


@dataclass(frozen=True)
class TspPpP2SectorBranch:
    """One TSP branch entering a PP sector from an outer layer."""

    phase_index: int
    region_index: int
    direction: int
    path: tuple[tuple[int, int, int], ...]


@dataclass(frozen=True)
class TspPassPartitionBranch:
    """One contiguous cut of a complete TSP lane/orbit traversal."""

    phase_index: int
    direction: int
    path: tuple[tuple[int, int, int], ...]
    signed_travel: tuple[int, ...]


@dataclass(frozen=True)
class DividerConnectionFormula:
    """Split or join ordered parent paths using the three divider factors."""

    operation: FormulaOperation
    source_dividers: DividerTuple
    target_dividers: DividerTuple
    order: FormulaOrder = "source"

    def apply(
        self,
        branches: Sequence[tuple[int, Sequence]],
        *,
        num_slots: int | None = None,
        pp: int | None = None,
        group_keys: Sequence[object] | None = None,
        group_order: Sequence[object] | None = None,
        sector_stride: int = 1,
        sector_repetitions: int | None = None,
    ) -> list[FormulaBranch]:
        """Apply the divider transform to ordered parent paths.

        ``pp`` is the physical pole-pair count required by the exploratory
        ZPP centered-entry operation; its sector stride is derived from pp.
        """
        parents = [(branch_id, list(path)) for branch_id, path in branches]
        if not parents:
            raise DividerFormulaError("A divider formula requires at least one parent branch.")
        if any(not path for _branch_id, path in parents):
            raise DividerFormulaError("A divider formula cannot transform an empty parent path.")
        source_naa = _naa(self.source_dividers)
        target_naa = _naa(self.target_dividers)

        if self.operation == "indexed_translation":
            return _indexed_sector_translation(
                parents, self.source_dividers, self.target_dividers,
                source_naa, target_naa, num_slots, group_keys, group_order,
                sector_stride, sector_repetitions)

        if self.operation == "zpp_centered_entry_translation":
            return _zpp_centered_entry_translation(
                parents, self.source_dividers, self.target_dividers,
                num_slots, pp, group_keys, group_order)

        if self.operation == "identity":
            if source_naa != target_naa:
                raise DividerFormulaError(
                    "An identity requires source and target to have the same Naa.")
            return [
                FormulaBranch((branch_id,), 0, path)
                for branch_id, path in parents
            ]

        if self.operation == "partition":
            parts = _integer_ratio(target_naa, source_naa)
            if parts <= 1:
                raise DividerFormulaError(
                    "A partition requires the target Naa to exceed the source Naa.")
            return _partition(parents, parts, self.order)

        if self.operation == "grouped_partition":
            parts = _integer_ratio(target_naa, source_naa)
            if parts <= 1:
                raise DividerFormulaError(
                    "A grouped partition requires the target Naa to exceed the source Naa.")
            return _grouped_partition(
                parents, parts, self.order, group_keys, group_order)

        if self.operation == "join":
            parents_per_branch = _integer_ratio(source_naa, target_naa)
            if parents_per_branch <= 1:
                raise DividerFormulaError(
                    "A join requires the source Naa to exceed the target Naa.")
            return _join(parents, parents_per_branch)

        raise DividerFormulaError(f"Unsupported divider formula operation: {self.operation}")


@dataclass(frozen=True)
class RouteFormulaBinding:
    """Route recipe metadata; ``None`` copies the target factor at that axis."""

    operation: FormulaOperation
    source_dividers: tuple[SourceFactor, SourceFactor, SourceFactor]
    order: FormulaOrder = "source"

    def resolve_source_dividers(self, target_dividers: DividerTuple) -> DividerTuple:
        _naa(target_dividers)
        if len(self.source_dividers) != 3:
            raise DividerFormulaError("A route formula requires three source factors.")
        resolved = []
        for index, factor in enumerate(self.source_dividers):
            if isinstance(factor, DividerFactorRef):
                target_index = factor.target_index
                if (isinstance(target_index, bool)
                        or not isinstance(target_index, int)
                        or target_index not in range(3)):
                    raise DividerFormulaError(
                        "A divider-factor reference must name an axis from 0 to 2.")
                scale = factor.scale
                if isinstance(scale, bool) or not isinstance(scale, (int, Fraction)):
                    raise DividerFormulaError(
                        "A divider-factor scale must be an integer or Fraction.")
                value = Fraction(target_dividers[target_index]) * Fraction(scale)
                resolved.append(
                    value.numerator if value.denominator == 1 else value)
            else:
                resolved.append(
                    target_dividers[index] if factor is None else factor)
        return tuple(resolved)


# These bindings describe path transformations only. They do not grant route
# support; the public Pattern resolver and its validators remain authoritative.
ROUTE_FORMULA_BINDINGS = {
    "zpp_pp_only_half_turn": RouteFormulaBinding(
        "indexed_translation", (DividerFactorRef(1), 1, 1), "source"),
    "zpp_pp_only_indexed_translation": RouteFormulaBinding(
        "indexed_translation", (DividerFactorRef(1), 1, 1), "source"),
    "tsp_pp_only_q_p2_identity": RouteFormulaBinding(
        "identity", (DividerFactorRef(1, Fraction(1, 2)), 1, 2), "source"),
    "tlp_pp_only_even": RouteFormulaBinding(
        "partition", (DividerFactorRef(0), 2, 1), "source"),
    "tlp_pp_p2_short_unit": RouteFormulaBinding(
        "partition", (1, 1, 2), "source"),
    "tlp_q_pp_p2_parent_slices": RouteFormulaBinding(
        "partition", (1, None, 2), "source"),
    "zlp_pp_p2_source_cut": RouteFormulaBinding(
        "partition", (1, 1, 2), "source"),
    "zpp_q_pp_p2_parent_slices": RouteFormulaBinding(
        "grouped_partition", (None, 1, None), "piece"),
    "cp_q_pp_full_parent_slices": RouteFormulaBinding(
        "partition", (None, 1, 2), "piece"),
    "cp_q_pp_p2_parent_slices": RouteFormulaBinding(
        "partition", (None, 1, None), "source"),
    "cp_pp_sector_slices": RouteFormulaBinding(
        "partition", (1, 4, 1), "source"),
    "cp_q_only_pair_join": RouteFormulaBinding(
        "join", (None, 1, 2), "source"),
    "tsp_q_only_pair_join": RouteFormulaBinding(
        "join", (None, 1, 2), "source"),
    "tlp_q_only_pair_join": RouteFormulaBinding(
        "join", (None, 1, 2), "source"),
    "uwp_q_only_series": RouteFormulaBinding(
        "join", (None, 1, 2), "source"),
}

ROUTE_FORMULA_FAMILIES = {
    route_id: f"divider_{binding.operation}_{binding.order}"
    for route_id, binding in ROUTE_FORMULA_BINDINGS.items()
}
ROUTE_FORMULA_FAMILIES.update({
    "zpp_pp_only_half_turn": "divider_indexed_sector_translation",
    "zpp_pp_only_indexed_translation": "divider_indexed_sector_translation",
    "zpp_pp_only_centered_entry_translation":
        "divider_zpp_centered_entry_translation",
    "ssp_q_pp_parent_cut": "spiral_q_lane_parent_cut",
    "slp_q_pp_parent_cut": "spiral_q_lane_parent_cut",
    "slp_q_pp_p2_parent_cut": "slp_q_lane_p2_parent_regroup",
    "cp_pp_four_pass_weave": "cp_four_pass_weave",
    "cp_pp_parent_half_translation": "cp_parent_half_translation",
    "tsp_pp_p2_sector": "tsp_fixed_lane_sector_inlets",
    "tsp_spiral_pass_partition": "tsp_gcd_orbit_pass_partition",
})


def tsp_spiral_pass_partition_dimensions(q, pp, dividers, layers):
    """Derive cohort size, lane groups, pole orbits and complete passes/cut."""
    if (not isinstance(dividers, tuple) or len(dividers) != 3
            or any(type(value) is not int
                   for value in (q, pp, layers, *dividers))):
        raise DividerFormulaError('TSP pass partition requires integer dimensions.')
    Q, D, P2 = dividers
    naa = Q * D * P2
    if (min(q, pp, Q, D) < 1 or P2 not in (1, 2)
            or q % Q or pp % D or layers < 2 or layers % 2
            or naa % 2):
        raise DividerFormulaError(
            'TSP pass partition requires Q|q, D|pp, P2 in {1,2}, '
            'even Naa and positive even local layers.')
    cohort_size = naa // 2
    if q * pp % cohort_size or q * pp // cohort_size < 2:
        raise DividerFormulaError(
            'TSP pass partition requires at least two complete local-layer passes '
            'per branch.')
    return (cohort_size, gcd(q, cohort_size), gcd(layers // 2, pp),
            q * pp // cohort_size)


def tsp_spiral_pass_partition(q, pp, dividers, layers, phases):
    """Cover pole-pair gcd orbits, join q lanes, then cut at full passes.

    With a=L/2 and g=gcd(a,pp), pass heads r-d*c+d*t*a cover every
    pole pair once (c=0..g-1, t=0..pp/g-1). The orbit seam uses -d*tau;
    the other returns use d*tau. A lane join changes only its q position.
    The two outer-layer cohorts have opposite physical travel and identical
    weld travel when expressed from the lower to the higher layer.
    """
    cohort_size, groups, orbits, passes = tsp_spiral_pass_partition_dimensions(
        q, pp, dividers, layers)
    if type(phases) is not int or phases < 3 or phases % 2 == 0:
        raise DividerFormulaError('TSP pass partition requires native odd phases.')
    Q, _D, _P2 = dividers
    tau = phases * q
    slots = 2 * pp * tau
    lane_count = q // groups
    cuts = cohort_size // groups
    width = passes * layers
    result = []
    for phase in range(phases):
        origin = q * (phase + phases * (phase % 2))
        for group in range(groups):
            # PP-contributed groups get distinct origins; Q groups are lanes.
            origin_pair = (group // Q) * pp * min(Q, groups) // groups
            for direction in (1, -1):
                path, travel = [], []
                previous_lane = None
                for lane_index in range(lane_count):
                    lane = group * lane_count + lane_index
                    if direction < 0:
                        lane = q - 1 - lane
                    base = origin_pair - direction * lane_index * (orbits - 1)
                    for orbit in range(orbits):
                        for index in range(pp // orbits):
                            pair = (base - direction * orbit
                                    + direction * index * (layers // 2)) % pp
                            start_slot = (origin + 2 * pair * tau + lane) % slots
                            if path:
                                step = (direction * tau if index or not orbit
                                        else -direction * tau)
                                if not orbit and not index:
                                    step += lane - previous_lane
                                travel.append(step)
                            for layer_index in range(layers):
                                layer = (layer_index if direction > 0
                                         else layers - 1 - layer_index)
                                path.append(((start_slot + direction * layer_index * tau)
                                             % slots, layer, lane))
                                if layer_index < layers - 1:
                                    travel.append(direction * tau)
                    previous_lane = lane
                for cut in range(cuts):
                    start = cut * width
                    result.append(TspPassPartitionBranch(
                        phase, direction, tuple(path[start:start + width]),
                        tuple(travel[start:start + width - 1])))
    return tuple(result)


@lru_cache(maxsize=512)
def tsp_pp_p2_sector_lane_residues(
    q: int, pp: int, dividers: DividerTuple, layers: int,
) -> tuple[tuple[int, tuple[int, ...]], ...]:
    """Return pole-pair residues visited by each fixed q lane.

    A residue partition is part of this constructor's domain: every lane must
    visit every pole pair exactly once. The caller can use the returned rows
    to reject collisions before materializing branch paths.
    """
    if (not isinstance(dividers, tuple) or len(dividers) != 3
            or any(type(value) is not int for value in dividers)):
        raise DividerFormulaError(
            "TSP PP+P2 requires three integer divider factors.")
    q_divider, divider, p2_divider = dividers
    values = (q, pp, q_divider, divider, p2_divider, layers)
    if any(type(value) is not int for value in values):
        raise DividerFormulaError(
            "TSP PP+P2 sector factors and layers must be integers.")
    if (q <= 0 or pp <= 0 or q_divider != 1 or divider <= 1
            or p2_divider != 2 or pp % divider or divider % q
            or layers < 2 or layers % 2):
        raise DividerFormulaError(
            "TSP PP+P2 sectors require dividers (1,D,2), q|D|pp, "
            "and a positive even layer count.")

    passes = q * (pp // divider)
    step = layers // 2
    residues = {lane: [] for lane in range(q)}
    for region in range(divider):
        lane = (region * q) // divider
        pole_pair = region * (pp // divider)
        residues[lane].extend(
            (pole_pair + index * step) % pp
            for index in range(passes))
    return tuple((lane, tuple(values)) for lane, values in residues.items())


def tsp_pp_p2_sector_residues_are_complete(
    q: int, pp: int, dividers: DividerTuple, layers: int,
) -> bool:
    """Check that each formula lane covers every pole pair exactly once."""
    try:
        residues = tsp_pp_p2_sector_lane_residues(q, pp, dividers, layers)
    except DividerFormulaError:
        return False
    return all(len(values) == pp and set(values) == set(range(pp))
               for _lane, values in residues)


def tsp_pp_p2_sector_branches(
    q: int, pp: int, dividers: DividerTuple, layers: int, phases: int,
) -> tuple[TspPpP2SectorBranch, ...]:
    """Construct two opposite-travel inlets per positive pole-pair sector.

    The first cohort starts on layer zero and advances with positive signed
    travel. The second starts on the last layer and advances with negative
    signed travel. Both use the same fixed q-lane and pole-region assignment.
    """
    if type(phases) is not int or phases < 1:
        raise DividerFormulaError(
            "TSP PP+P2 sector construction requires a positive phase count.")
    if not isinstance(dividers, tuple) or len(dividers) != 3:
        raise DividerFormulaError(
            "TSP PP+P2 sector construction requires three divider factors.")
    divider = dividers[1]
    if not tsp_pp_p2_sector_residues_are_complete(
            q, pp, dividers, layers):
        raise DividerFormulaError(
            "TSP PP+P2 fixed-lane residues do not partition all pole pairs.")

    pole_region_width = phases * q
    slots = 2 * pp * pole_region_width
    passes = q * (pp // divider)
    branch_length = passes * layers
    branches = []
    for phase in range(phases):
        for region in range(divider):
            pole_pair = region * (pp // divider)
            lane = (region * q) // divider
            start_slot = (
                q * (phase + phases * (2 * pole_pair + phase % 2)) + lane
            ) % slots
            for direction in (1, -1):
                start_layer = 0 if direction > 0 else layers - 1
                path = tuple(
                    ((start_slot + direction * index * pole_region_width) % slots,
                     (start_layer + direction * index) % layers,
                     lane)
                    for index in range(branch_length)
                )
                branches.append(TspPpP2SectorBranch(
                    phase, region, direction, path))
    return tuple(branches)


def apply_route_formula(
    route_id: str,
    branches: Sequence[tuple[int, Sequence]],
    target_dividers: DividerTuple,
    *,
    num_slots: int | None = None,
    pp: int | None = None,
    group_keys: Sequence[object] | None = None,
    group_order: Sequence[object] | None = None,
    sector_stride: int = 1,
    sector_repetitions: int | None = None,
) -> list[FormulaBranch]:
    """Apply a registered route's shared divider-factor path transform."""
    try:
        binding = ROUTE_FORMULA_BINDINGS[route_id]
    except KeyError as exc:
        raise DividerFormulaError(
            f"No shared divider formula is registered for route {route_id!r}.") from exc
    source_dividers = binding.resolve_source_dividers(target_dividers)
    return DividerConnectionFormula(
        operation=binding.operation,
        source_dividers=source_dividers,
        target_dividers=target_dividers,
        order=binding.order,
    ).apply(
        branches, num_slots=num_slots, pp=pp, group_keys=group_keys,
        group_order=group_order, sector_stride=sector_stride,
        sector_repetitions=sector_repetitions)


def _indexed_sector_translation(
    parents,
    source_dividers,
    target_dividers,
    source_naa,
    target_naa,
    num_slots,
    group_keys,
    group_order,
    sector_stride,
    sector_repetitions,
):
    """Translate same-Naa Q-parent branches by their PP-sector index."""
    target_pp = target_dividers[1]
    try:
        target_pp_value = Fraction(target_pp)
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        raise DividerFormulaError(
            "Indexed sector translation requires an integer PP divider.") from exc
    if (target_pp_value.denominator != 1 or target_pp_value <= 1
            or tuple(Fraction(value) for value in source_dividers)
            != (target_pp_value, Fraction(1), Fraction(1))
            or tuple(Fraction(value) for value in target_dividers)
            != (Fraction(1), target_pp_value, Fraction(1))
            or source_naa != target_naa):
        raise DividerFormulaError(
            "Indexed sector translation requires same-Naa (D,1,1) to (1,D,1).")
    sector_count = target_pp_value.numerator
    if (isinstance(sector_stride, bool)
            or not isinstance(sector_stride, int)
            or not 1 <= sector_stride < sector_count
            or gcd(sector_stride, sector_count) != 1):
        raise DividerFormulaError(
            "Indexed sector translation requires a stride coprime to D.")
    if sector_repetitions is not None:
        if (isinstance(sector_repetitions, bool)
                or not isinstance(sector_repetitions, int)
                or sector_repetitions < 1):
            raise DividerFormulaError(
                "Indexed sector repetitions must be a positive integer.")
        expected_stride = zpp_indexed_sector_stride(
            sector_count, sector_repetitions)
        if sector_stride != expected_stride:
            raise DividerFormulaError(
                "Indexed sector stride does not match the factor-derived ZPP stride.")
    if (isinstance(num_slots, bool) or not isinstance(num_slots, int)
            or num_slots <= 0 or num_slots % sector_count):
        raise DividerFormulaError(
            "Indexed sector translation requires a positive slot count divisible by D.")
    if group_keys is None or len(group_keys) != len(parents):
        raise DividerFormulaError(
            "Indexed sector translation requires one phase key per parent.")

    groups = {}
    try:
        for parent, key in zip(parents, group_keys):
            groups.setdefault(key, []).append(parent)
    except TypeError as exc:
        raise DividerFormulaError(
            "Indexed sector translation phase keys must be hashable.") from exc
    order = tuple(groups) if group_order is None else tuple(group_order)
    try:
        if (len(order) != len(set(order)) or set(order) != set(groups)):
            raise DividerFormulaError(
                "Indexed sector translation group order must cover every phase once.")
    except TypeError as exc:
        raise DividerFormulaError(
            "Indexed sector translation phase keys must be hashable.") from exc

    sector_width = num_slots // sector_count
    transformed = []
    for key in order:
        group = groups[key]
        if len(group) != sector_count:
            raise DividerFormulaError(
                "Indexed sector translation requires exactly D parents per phase.")
        for branch_index, (branch_id, path) in enumerate(group):
            sector_index = (branch_index * sector_stride) % sector_count
            offset = sector_index * sector_width
            translated = [
                ((node[0] + offset) % num_slots, *node[1:])
                for node in path
            ]
            transformed.append(FormulaBranch(
                source_ids=(branch_id,), part_index=branch_index,
                path=translated))
    return transformed


def _zpp_centered_entry_translation(
    parents,
    source_dividers,
    target_dividers,
    num_slots,
    pp,
    group_keys,
    group_order,
):
    """Deploy centered Q-parent entry windows into exploratory ZPP sectors.

    For integer ``(Q,1,1) -> (1,D,1)``, each parent's centered window has
    ``len(parent)/(D/Q)`` conductors. The ``D/Q`` windows are deployed in
    piece-major Q-lane order to sectors ``a*j mod D``, where
    ``a=zpp_indexed_sector_stride(D, pp/D)``. This is a path formula only;
    public Pattern admission and generated-layout validation remain separate.
    """
    factors = tuple(source_dividers) + tuple(target_dividers)
    if (len(source_dividers) != 3 or len(target_dividers) != 3
            or any(type(value) is not int or value < 1 for value in factors)):
        raise DividerFormulaError(
            "ZPP centered-entry translation requires positive integer dividers.")
    source_q, source_pp, source_p2 = source_dividers
    target_q, target_pp, target_p2 = target_dividers
    if (source_pp != 1 or source_p2 != 1
            or target_q != 1 or target_p2 != 1
            or source_q <= 0 or target_pp <= source_q):
        raise DividerFormulaError(
            "ZPP centered-entry translation requires (Q,1,1) to (1,D,1) with D>Q.")
    if target_pp % source_q:
        raise DividerFormulaError(
            "ZPP centered-entry translation requires Q|D (Q must divide D).")
    if type(pp) is not int or pp < 1:
        raise DividerFormulaError(
            "ZPP centered-entry translation requires a positive integer pp.")
    if pp % target_pp:
        raise DividerFormulaError(
            "ZPP centered-entry translation requires D|pp (D must divide pp).")
    if (type(num_slots) is not int or num_slots < 1
            or num_slots % target_pp):
        raise DividerFormulaError(
            "ZPP centered-entry translation requires a positive slot count divisible by D.")
    if group_keys is None or len(group_keys) != len(parents):
        raise DividerFormulaError(
            "ZPP centered-entry translation requires one group key per parent.")

    groups = {}
    try:
        for parent, key in zip(parents, group_keys):
            groups.setdefault(key, []).append(parent)
    except TypeError as exc:
        raise DividerFormulaError(
            "ZPP centered-entry translation group keys must be hashable.") from exc
    if len({len(path) for _branch_id, path in parents}) != 1:
        raise DividerFormulaError(
            "ZPP centered-entry translation requires equal parent walk lengths across groups.")
    order = tuple(groups) if group_order is None else tuple(group_order)
    try:
        if len(order) != len(set(order)) or set(order) != set(groups):
            raise DividerFormulaError(
                "ZPP centered-entry translation group order must cover every group once.")
    except TypeError as exc:
        raise DividerFormulaError(
            "ZPP centered-entry translation group keys must be hashable.") from exc

    parts = target_pp // source_q
    stride = zpp_indexed_sector_stride(target_pp, pp // target_pp)
    sector_width = num_slots // target_pp
    transformed = []
    occupied = set()
    for key in order:
        group = groups[key]
        if len(group) != source_q:
            raise DividerFormulaError(
                "ZPP centered-entry translation requires exactly Q parents per group.")
        lengths = {len(path) for _branch_id, path in group}
        if len(lengths) != 1 or next(iter(lengths)) % parts:
            raise DividerFormulaError(
                "ZPP centered-entry translation requires equal, divisible parent walks per group.")
        parent_length = next(iter(lengths))
        entry_length = parent_length // parts
        remainder = parent_length - entry_length
        if remainder % 2:
            raise DividerFormulaError(
                "ZPP centered-entry translation requires a symmetric centered entry window.")
        entry_start = remainder // 2
        for child_index in range(target_pp):
            parent_index = child_index % source_q
            piece_index = child_index // source_q
            branch_id, source_path = group[parent_index]
            entry_window = source_path[entry_start:entry_start + entry_length]
            if len(entry_window) != entry_length:
                raise DividerFormulaError(
                    "ZPP centered-entry translation could not resolve a complete entry window.")
            first_node = entry_window[0]
            if (not isinstance(first_node, Sequence)
                    or isinstance(first_node, (str, bytes))
                    or len(first_node) < 2
                    or type(first_node[0]) is not int
                    or not 0 <= first_node[0] < num_slots):
                raise DividerFormulaError(
                    "ZPP centered-entry translation requires slot/layer conductor nodes.")
            source_sector = first_node[0] // sector_width
            sector_index = (child_index * stride) % target_pp
            offset = ((sector_index - source_sector) % target_pp) * sector_width
            translated = []
            for node in entry_window:
                if (not isinstance(node, Sequence)
                        or isinstance(node, (str, bytes)) or len(node) < 2
                        or type(node[0]) is not int
                        or not 0 <= node[0] < num_slots
                        or type(node[1]) is not int or node[1] < 0):
                    raise DividerFormulaError(
                        "ZPP centered-entry translation requires slot/layer conductor nodes.")
                updated = ((node[0] + offset) % num_slots, *node[1:])
                coordinate = updated[:2]
                if coordinate in occupied:
                    raise DividerFormulaError(
                        f"ZPP centered-entry translation duplicates conductor {coordinate}.")
                occupied.add(coordinate)
                translated.append(updated)
            transformed.append(FormulaBranch(
                source_ids=(branch_id,), part_index=piece_index,
                path=translated))
    return transformed


def cp_four_pass_weave(branches, layer_count: int) -> list[list]:
    """Apply the reviewed CP four-parent weave using layer-sized pass blocks."""
    if len(branches) != 4 or layer_count <= 0:
        raise DividerFormulaError(
            "The CP four-pass weave requires four parents and a positive layer count.")
    paths = [list(path) for _branch_id, path in branches]
    if any(len(path) != 4 * layer_count for path in paths):
        raise DividerFormulaError(
            "Each CP weave parent must contain four complete layer-sized passes.")

    p1, p2, p3, p4 = paths
    lap = layer_count
    first = p1[:2 * lap] + p2 + p1[2 * lap:]
    second = (
        p3[3 * lap:] + p4[2 * lap:] + p3[2 * lap:3 * lap]
        + p4[lap:2 * lap] + p3[:2 * lap] + p4[:lap]
    )
    return [first, second]


def tsp_q_lane_sweep_completion(
    branches: Sequence[tuple[int, Sequence]],
    *,
    q: int,
    q_divider: int,
    num_slots: int,
    phase_signs: Mapping[tuple[int, int], tuple[int, int]],
) -> list[FormulaBranch]:
    """Complete a proper-Q TSP P2 parent by sweeping its missing q lanes.

    Each raw branch is oriented from its positive-polarity inlet, then copied
    through ``q / q_divider`` consecutive q lanes. A sweep advances both the
    physical slot and stored q coordinate by one.
    """
    if (isinstance(q, bool) or not isinstance(q, int) or q <= 0
            or isinstance(q_divider, bool)
            or not isinstance(q_divider, int) or q_divider <= 0
            or q % q_divider
            or isinstance(num_slots, bool)
            or not isinstance(num_slots, int) or num_slots <= 0):
        raise DividerFormulaError(
            "TSP q-lane completion requires positive integer q, Q and slots, "
            "with Q dividing q.")
    if not isinstance(phase_signs, Mapping):
        raise DividerFormulaError(
            "TSP q-lane completion requires a phase-sign map.")

    completed = []
    for branch_id, raw_path in branches:
        path = list(raw_path)
        if not path:
            raise DividerFormulaError(
                "TSP q-lane completion cannot transform an empty parent path.")
        if any(len(node) < 3 for node in path):
            raise DividerFormulaError(
                "TSP q-lane completion requires slot, layer and q coordinates.")
        try:
            _phase, start_sign = phase_signs[(path[0][0], path[0][1])]
        except (KeyError, TypeError, ValueError) as exc:
            raise DividerFormulaError(
                "TSP q-lane completion cannot resolve the parent inlet polarity.") from exc
        if start_sign not in (-1, 1):
            raise DividerFormulaError(
                "TSP q-lane completion requires a signed parent inlet.")
        if start_sign < 0:
            path.reverse()

        swept_path = []
        for lane in range(q // q_divider):
            for node in path:
                if (isinstance(node[0], bool) or not isinstance(node[0], int)
                        or isinstance(node[1], bool)
                        or not isinstance(node[1], int)
                        or isinstance(node[2], bool)
                        or not isinstance(node[2], int)):
                    raise DividerFormulaError(
                        "TSP q-lane completion requires integer conductor coordinates.")
                coordinates = list(node)
                coordinates[0] = (node[0] + lane) % num_slots
                coordinates[2] = (node[2] + lane) % q
                swept_path.append(tuple(coordinates))
        completed.append(FormulaBranch(
            (branch_id,), 0, swept_path))
    return completed


def cp_parent_half_translation(
    half_path: Sequence,
    *,
    num_slots: int,
    pole_pitch: int,
) -> tuple[list[list], tuple[int, ...]]:
    """Translate one CP P2-parent half into four formula-derived paths."""
    if not half_path or num_slots <= 0 or pole_pitch <= 0:
        raise DividerFormulaError(
            "CP parent translation requires a non-empty path and positive geometry.")
    delta = (half_path[-1][0] - half_path[0][0]) % num_slots
    offsets = (
        pole_pitch - delta,
        pole_pitch - 1,
        2 * pole_pitch - delta,
        2 * pole_pitch - 1,
    )
    translated = [
        [((node[0] + offset) % num_slots, *node[1:]) for node in half_path]
        for offset in offsets
    ]
    return translated, tuple(offset % num_slots for offset in offsets)


def spiral_q_pp_parent_cut(
    parent_path: Sequence,
    *,
    q_divider: int,
    pp_divider: int,
    q: int,
    pp: int,
    layer_count: int,
    block_order: Literal["lane_major", "sector_major"],
) -> list[list]:
    """Build Q lane children from an SSP or SLP PP-parent path."""
    if (q_divider <= 0 or pp_divider <= 0 or q <= 0 or pp <= 0
            or layer_count <= 0 or q % q_divider or pp % pp_divider):
        raise DividerFormulaError("Spiral Q+PP factors do not divide the parent geometry.")
    if block_order not in ("lane_major", "sector_major"):
        raise DividerFormulaError(f"Unsupported spiral parent order: {block_order}")

    block_width = 2 * layer_count
    if len(parent_path) % (q_divider * block_width):
        raise DividerFormulaError(
            "Spiral PP parent cannot be partitioned into equal complete Q blocks.")
    blocks = [list(parent_path[index:index + block_width])
              for index in range(0, len(parent_path), block_width)]
    sector_copies = pp // pp_divider
    children = []
    child_lanes = []
    for child_index in range(q_divider):
        if block_order == "lane_major":
            first = child_index * len(blocks) // q_divider
            last = (child_index + 1) * len(blocks) // q_divider
            child_blocks = blocks[first:last]
        else:
            lane_start = child_index * q // q_divider
            lane_stop = (child_index + 1) * q // q_divider
            child_blocks = [
                block for block in blocks
                if lane_start <= block[0][2] < lane_stop
            ]

        lanes = Counter(block[0][2] for block in child_blocks)
        expected_lanes = q // q_divider
        if (len(lanes) != expected_lanes
                or set(lanes.values()) != {sector_copies}):
            raise DividerFormulaError(
                "Spiral Q child has the wrong q-lane cohort or repetition count.")
        child_lanes.append(set(lanes))
        children.append([node for block in child_blocks for node in block])

    if (set.union(*child_lanes) != set(range(q))
            or sum(map(len, child_lanes)) != q):
        raise DividerFormulaError("Spiral Q children do not partition all q lanes.")
    return children


def slp_q_pp_p2_lane_regroup(
    parent_branches: Sequence[tuple[int, Sequence]],
    *,
    dividers: DividerTuple,
    q: int,
    pp: int,
    layer_count: int,
) -> list[FormulaBranch]:
    """Cut full-Q P2 parents by PP and regroup complete q-lane sectors.

    Each full-Q parent belongs to one q lane and one of the two P2 cohorts.
    A target child takes ``q / Q`` lanes and ``pp / D`` passes per lane.
    Those passes are assembled as complete ``2 * layer_count`` pole-pair
    blocks; successive blocks reverse the lane order to preserve SLP's
    sector-major path grammar.
    """
    try:
        factors = tuple(dividers)
    except TypeError as exc:
        raise DividerFormulaError(
            "SLP Q+PP+P2 requires a three-factor divider tuple.") from exc
    if (len(factors) != 3
            or any(type(value) is not int or value <= 0 for value in factors)):
        raise DividerFormulaError(
            "SLP Q+PP+P2 requires three positive integer divider factors.")
    q_divider, pp_divider, p2_divider = factors
    if (type(q) is not int or q <= 1
            or not 1 < q_divider < q or q % q_divider
            or pp_divider <= 1 or type(pp) is not int or pp <= 0
            or pp % pp_divider or p2_divider != 2):
        raise DividerFormulaError(
            "SLP Q+PP+P2 requires proper Q, D|pp, and P2=2.")
    if (type(layer_count) is not int or layer_count < 2
            or layer_count % 2):
        raise DividerFormulaError(
            "SLP Q+PP+P2 requires a positive even layer count.")

    lanes_per_child = q // q_divider
    passes_per_child_lane = pp // pp_divider
    if passes_per_child_lane % 2:
        raise DividerFormulaError(
            "SLP Q+PP+P2 requires an even number of passes per child lane.")
    parents_per_phase = 2 * q
    if len(parent_branches) % parents_per_phase:
        raise DividerFormulaError(
            "SLP full-Q P2 parents must contain two complete q-lane cohorts per phase.")

    block_width = 2 * layer_count
    child_paths = []
    for phase_start in range(0, len(parent_branches), parents_per_phase):
        phase_parents = parent_branches[
            phase_start:phase_start + parents_per_phase]
        for cohort in range(2):
            cohort_parents = phase_parents[cohort * q:(cohort + 1) * q]
            for lane, (branch_id, source_path) in enumerate(cohort_parents):
                if (len(source_path) != pp * layer_count
                        or not source_path
                        or any(len(node) < 3 or node[2] != lane
                               for node in source_path)):
                    raise DividerFormulaError(
                        "SLP full-Q P2 parent order must provide one complete path per q lane.")

        for cohort in range(2):
            cohort_parents = phase_parents[cohort * q:(cohort + 1) * q]
            for pp_sector in range(pp_divider):
                for q_group in range(q_divider):
                    first_lane = q_group * lanes_per_child
                    lane_range = range(
                        first_lane, first_lane + lanes_per_child)
                    source_ids = tuple(
                        cohort_parents[lane][0] for lane in lane_range)
                    path = []
                    for block_index in range(passes_per_child_lane // 2):
                        block_lanes = (lane_range if block_index % 2 == 0
                                       else range(
                                           first_lane + lanes_per_child - 1,
                                           first_lane - 1, -1))
                        for lane in block_lanes:
                            source_path = cohort_parents[lane][1]
                            piece_width = passes_per_child_lane * layer_count
                            piece_start = pp_sector * piece_width
                            block_start = piece_start + block_index * block_width
                            path.extend(source_path[
                                block_start:block_start + block_width])
                    child_index = ((cohort * pp_divider + pp_sector)
                                   * q_divider + q_group)
                    child_paths.append(FormulaBranch(
                        source_ids, child_index, path))

    return child_paths


def slp_q_pp_single_sector_weld_rotation(
    branches: Sequence[tuple[int, Sequence]],
    *,
    dividers: DividerTuple,
    q: int,
    pp: int,
    phase_count: int,
    num_slots: int,
) -> tuple[list[FormulaBranch], int]:
    """Rotate single-sector SLP Q+PP children to their weld inlet.

    The formula applies when the target has one PP-parent sector per child:
    `pp-divider == pp`. The new closing edge advances by
    `phase_count*q - (q/q-divider - 1)` slots.
    """
    try:
        factors = tuple(dividers)
    except TypeError as exc:
        raise DividerFormulaError(
            "SLP weld rotation requires a three-factor divider tuple.") from exc
    if (len(factors) != 3
            or any(type(value) is not int or value <= 0 for value in factors)):
        raise DividerFormulaError(
            "SLP weld rotation requires three positive integer dividers.")
    q_divider, pp_divider, p2_divider = factors
    if (type(q) is not int or q <= 0 or q_divider <= 1
            or q_divider >= q or q % q_divider):
        raise DividerFormulaError(
            "SLP weld rotation requires a proper q-divider of q.")
    if (type(pp) is not int or pp <= 1 or pp_divider != pp
            or p2_divider != 1):
        raise DividerFormulaError(
            "SLP weld rotation requires one PP sector per child and P2=1.")
    if type(phase_count) is not int or phase_count < 3 or phase_count % 2 == 0:
        raise DividerFormulaError(
            "SLP weld rotation requires an odd phase count of at least three.")
    if type(num_slots) is not int or num_slots <= 0:
        raise DividerFormulaError(
            "SLP weld rotation requires a positive integer slot count.")

    pole_region_width = phase_count * q
    closing_step = pole_region_width - (q // q_divider - 1)
    if not 0 < closing_step < pole_region_width:
        raise DividerFormulaError(
            "SLP weld rotation closing step must stay within one pole region.")

    rotated = []
    for branch_id, source_path in branches:
        path = list(source_path)
        if len(path) < 2:
            raise DividerFormulaError(
                f"SLP weld rotation requires a non-empty edge in branch {branch_id}.")
        if (path[-1][0] + closing_step) % num_slots != path[0][0]:
            raise DividerFormulaError(
                f"SLP branch {branch_id} endpoints do not match the derived weld step.")
        rotated.append(FormulaBranch(
            (branch_id,), 0, path[1:] + path[:1]))
    return rotated, closing_step


def _naa(dividers: DividerTuple) -> Fraction:
    if len(dividers) != 3:
        raise DividerFormulaError(
            "Divider formulas require (q-divider, pp-divider, P2).")
    factors = []
    for value in dividers:
        if isinstance(value, bool) or not isinstance(value, (int, Fraction)):
            raise DividerFormulaError("Divider factors must be integers or Fractions.")
        factor = Fraction(value)
        if factor <= 0:
            raise DividerFormulaError("Divider factors must be positive.")
        factors.append(factor)
    return prod(factors, start=Fraction(1))


def _integer_ratio(numerator: Fraction, denominator: Fraction) -> int:
    ratio = numerator / denominator
    if ratio.denominator != 1:
        raise DividerFormulaError(
            f"Divider change {numerator}/{denominator} is not an integer branch ratio.")
    return ratio.numerator


def _partition(parents, parts: int, order: FormulaOrder) -> list[FormulaBranch]:
    if order not in ("source", "piece"):
        raise DividerFormulaError(f"Unsupported partition order: {order}")
    rows_by_parent = []
    for branch_id, path in parents:
        if len(path) % parts:
            raise DividerFormulaError(
                f"Parent branch {branch_id} cannot be split into {parts} equal paths.")
        width = len(path) // parts
        rows_by_parent.append([
            FormulaBranch((branch_id,), part_index,
                          path[part_index * width:(part_index + 1) * width])
            for part_index in range(parts)
        ])
    if order == "source":
        return [row for rows in rows_by_parent for row in rows]
    return [rows[part_index] for part_index in range(parts)
            for rows in rows_by_parent]


def _grouped_partition(
    parents,
    parts: int,
    order: FormulaOrder,
    group_keys,
    group_order,
) -> list[FormulaBranch]:
    """Partition each ordered parent group before moving to the next group."""
    if group_keys is None or len(group_keys) != len(parents):
        raise DividerFormulaError(
            "Grouped partition requires one group key per parent.")
    groups = {}
    try:
        for parent, key in zip(parents, group_keys):
            groups.setdefault(key, []).append(parent)
    except TypeError as exc:
        raise DividerFormulaError(
            "Grouped partition keys must be hashable.") from exc
    ordered_groups = tuple(groups) if group_order is None else tuple(group_order)
    try:
        if (len(ordered_groups) != len(set(ordered_groups))
                or set(ordered_groups) != set(groups)):
            raise DividerFormulaError(
                "Grouped partition order must cover every group exactly once.")
    except TypeError as exc:
        raise DividerFormulaError(
            "Grouped partition keys must be hashable.") from exc
    return [
        child
        for key in ordered_groups
        for child in _partition(groups[key], parts, order)
    ]


def _join(parents, parents_per_branch: int) -> list[FormulaBranch]:
    if len(parents) % parents_per_branch:
        raise DividerFormulaError(
            f"{len(parents)} parent branches cannot be grouped by {parents_per_branch}.")
    joined = []
    for start in range(0, len(parents), parents_per_branch):
        group = parents[start:start + parents_per_branch]
        joined.append(FormulaBranch(
            tuple(branch_id for branch_id, _path in group),
            start // parents_per_branch,
            [node for _branch_id, path in group for node in path],
        ))
    return joined
