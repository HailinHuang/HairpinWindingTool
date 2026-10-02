"""Active-length partial inductance for a generated winding layout.

The model treats every in-slot conductor as a finite, straight, parallel
segment in a homogeneous medium.  It intentionally excludes end windings,
slot/tooth boundary effects, saturation, and frequency-dependent current
redistribution.  Branch matrices preserve the signed conductor directions;
phase matrices assume equal current sharing among parallel branches.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


MU_0 = 4.0e-7 * math.pi


@dataclass(frozen=True)
class InductanceResult:
    """Calculated branch and equal-sharing phase inductance matrices."""

    branch_ids: tuple[int, ...]
    branch_phases: tuple[int, ...]
    branch_matrix_h: np.ndarray
    branch_coupling_matrix: np.ndarray
    phase_ids: tuple[int, ...]
    phase_matrix_h: np.ndarray
    phase_coupling_matrix: np.ndarray
    conductor_count: int
    active_length_m: float
    conductor_gmr_m: float
    relative_permeability: float


def normalize_inductance_matrix(inductance_matrix):
    """Return signed coupling ratios with every self-inductance set to one.

    Each entry is ``k_ij = L_ij / sqrt(L_ii * L_jj)``.  This definition stays
    symmetric when the two self-inductances differ and preserves the mutual
    inductance sign from the reference current directions.
    """
    matrix = np.asarray(inductance_matrix, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("Inductance matrix must be square.")
    if np.any(~np.isfinite(matrix)):
        raise ValueError("Inductance matrix entries must be finite.")
    self_inductance = np.diag(matrix)
    if np.any(self_inductance <= 0.0):
        raise ValueError("Self-inductances must be positive for normalization.")
    denominator = np.sqrt(np.outer(self_inductance, self_inductance))
    normalized = matrix / denominator
    np.fill_diagonal(normalized, 1.0)
    return normalized


def finite_parallel_partial_inductance(
        length_m: float,
        separation_m: float,
        relative_permeability: float = 1.0) -> float:
    """Return the partial inductance of two aligned finite parallel segments."""
    length_m = float(length_m)
    separation_m = float(separation_m)
    relative_permeability = float(relative_permeability)
    if length_m <= 0.0:
        raise ValueError("Active length must be positive.")
    if separation_m <= 0.0:
        raise ValueError("Conductor separation or GMR must be positive.")
    if relative_permeability <= 0.0:
        raise ValueError("Relative permeability must be positive.")
    geometry = (length_m * math.asinh(length_m / separation_m)
                - math.hypot(length_m, separation_m) + separation_m)
    return MU_0 * relative_permeability / (2.0 * math.pi) * geometry


def rectangular_conductor_gmr(width_m: float, height_m: float) -> float:
    """Return the exact rectangular-section GMD used as the self GMR.

    This geometric mean distance assumes uniform current density over the
    rectangular cross-section.  It is symmetric in width and height.
    """
    width_m = float(width_m)
    height_m = float(height_m)
    if (not math.isfinite(width_m) or not math.isfinite(height_m)
            or width_m <= 0.0 or height_m <= 0.0):
        raise ValueError("Conductor width and height must be positive and finite.")

    short_side = min(width_m, height_m)
    long_side = max(width_m, height_m)
    ratio = short_side / long_side
    ratio_squared = ratio * ratio
    log_one_plus_ratio_squared = math.log1p(ratio_squared)
    if ratio < 1.0e-8:
        log_over_ratio_squared = 1.0 - ratio_squared / 2.0
        atan_over_ratio = 1.0 - ratio_squared / 3.0
    else:
        log_over_ratio_squared = log_one_plus_ratio_squared / ratio_squared
        atan_over_ratio = math.atan(ratio) / ratio

    log_gmd_over_long_side = (
        0.5 * log_one_plus_ratio_squared
        - ratio_squared / 12.0
        * (log_one_plus_ratio_squared - 2.0 * math.log(ratio))
        - log_over_ratio_squared / 12.0
        + (2.0 * ratio / 3.0)
        * (math.pi / 2.0 - math.atan(ratio))
        + (2.0 / 3.0) * atan_over_ratio
        - 25.0 / 12.0
    )
    return long_side * math.exp(log_gmd_over_long_side)


def aggregate_phase_matrix(
        branch_matrix_h,
        branch_phases,
        *,
        expected_phase_ids=None,
        expected_branches_per_phase=None):
    """Aggregate a branch matrix assuming equal current in parallel branches."""
    matrix = np.asarray(branch_matrix_h, dtype=float)
    phases = tuple(int(value) for value in branch_phases)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("Branch inductance matrix must be square.")
    if matrix.shape[0] != len(phases):
        raise ValueError("Branch phase count does not match the branch matrix.")
    phase_ids = tuple(sorted(set(phases)))
    if not phase_ids:
        raise ValueError("At least one branch phase is required.")
    if expected_phase_ids is not None:
        expected = tuple(sorted(int(phase) for phase in expected_phase_ids))
        if phase_ids != expected:
            raise ValueError(
                f"Expected branch phases {expected} but the layout contains {phase_ids}.")
    if expected_branches_per_phase is not None:
        expected_count = int(expected_branches_per_phase)
        if expected_count <= 0:
            raise ValueError("Expected branches per phase must be positive.")
        bad_counts = {
            phase: phases.count(phase)
            for phase in phase_ids
            if phases.count(phase) != expected_count
        }
        if bad_counts:
            raise ValueError(
                f"Expected {expected_count} branches per phase; actual counts: "
                f"{bad_counts}.")
    sharing = np.zeros((len(phases), len(phase_ids)), dtype=float)
    for column, phase in enumerate(phase_ids):
        indices = [index for index, value in enumerate(phases) if value == phase]
        sharing[indices, column] = 1.0 / len(indices)
    phase_matrix = sharing.T @ matrix @ sharing
    return phase_ids, (phase_matrix + phase_matrix.T) * 0.5


def _validate_and_prepare_conductors(
        cond_info, phase_records, num_slots, layer_radii_mm):
    if isinstance(num_slots, bool) or int(num_slots) != num_slots or num_slots <= 0:
        raise ValueError("Number of slots must be a positive integer.")
    num_slots = int(num_slots)
    radii = np.asarray(layer_radii_mm, dtype=float)
    if radii.ndim != 1 or not len(radii) or np.any(~np.isfinite(radii)) or np.any(radii <= 0.0):
        raise ValueError("Every layer radius must be positive and finite.")

    sign_by_position = {}
    phase_by_position = {}
    for slot, layer, phase, sign in phase_records:
        position = int(slot), int(layer)
        if position in sign_by_position:
            raise ValueError(f"Duplicate phase record at slot/layer {position}.")
        if int(sign) not in (-1, 1):
            raise ValueError("Every conductor direction must be +1 or -1.")
        sign_by_position[position] = int(sign)
        phase_by_position[position] = int(phase)

    records = []
    occupied = set()
    for row in cond_info:
        if len(row) < 4:
            raise ValueError("Conductor records must include slot, layer, phase, and branch.")
        slot, layer, phase, branch = map(int, row[:4])
        position = slot, layer
        if branch <= 0:
            raise ValueError("Every conductor must have an assigned branch.")
        if position in occupied:
            raise ValueError(f"Duplicate conductor occupancy at slot/layer {position}.")
        if not 0 <= slot < num_slots or not 0 <= layer < len(radii):
            raise ValueError(f"Conductor position {position} is outside the winding geometry.")
        if position not in sign_by_position:
            raise ValueError(f"No signed phase record exists at slot/layer {position}.")
        if phase_by_position[position] != phase:
            raise ValueError(f"Phase mismatch at slot/layer {position}.")
        occupied.add(position)
        records.append((slot, layer, phase, branch, sign_by_position[position]))
    if not records:
        raise ValueError("The current layout has no conductors.")
    return records, radii


def calculate_active_inductance(
        cond_info,
        phase_records,
        *,
        num_slots,
        layer_radii_mm,
        active_length_mm,
        conductor_width_mm,
        conductor_height_mm,
        relative_permeability=1.0,
        expected_branch_count=None,
        expected_phase_ids=None,
        expected_branches_per_phase=None,
        max_conductors=2500,
        block_size=256):
    """Calculate signed branch and equal-sharing phase inductance matrices.

    The exact geometric mean distance of the rectangular cross-section is used
    as the conductor's self GMR, assuming uniform current density.
    """
    records, radii_mm = _validate_and_prepare_conductors(
        cond_info, phase_records, num_slots, layer_radii_mm)
    conductor_count = len(records)
    if conductor_count > int(max_conductors):
        raise ValueError(
            f"Inductance calculation is limited to {int(max_conductors)} conductors; "
            f"the current layout has {conductor_count}.")

    active_length_m = float(active_length_mm) / 1000.0
    width_m = float(conductor_width_mm) / 1000.0
    height_m = float(conductor_height_mm) / 1000.0
    relative_permeability = float(relative_permeability)
    if active_length_m <= 0.0:
        raise ValueError("Active length must be positive.")
    if width_m <= 0.0 or height_m <= 0.0:
        raise ValueError("Conductor width and height must be positive.")
    if relative_permeability <= 0.0:
        raise ValueError("Relative permeability must be positive.")
    conductor_gmr_m = rectangular_conductor_gmr(width_m, height_m)

    branch_ids = tuple(sorted({record[3] for record in records}))
    if (expected_branch_count is not None
            and len(branch_ids) != int(expected_branch_count)):
        raise ValueError(
            f"Expected {int(expected_branch_count)} branches but the layout contains "
            f"{len(branch_ids)}.")
    branch_index = {branch: index for index, branch in enumerate(branch_ids)}
    phases_by_branch = {}
    for _slot, _layer, phase, branch, _sign in records:
        phases_by_branch.setdefault(branch, set()).add(phase)
    if any(len(phases) != 1 for phases in phases_by_branch.values()):
        raise ValueError("Each branch must belong to exactly one phase.")
    branch_phases = tuple(next(iter(phases_by_branch[branch])) for branch in branch_ids)

    angles = np.asarray([2.0 * math.pi * record[0] / int(num_slots)
                         for record in records])
    radial_m = np.asarray([radii_mm[record[1]] / 1000.0 for record in records])
    positions = np.column_stack((radial_m * np.cos(angles),
                                 radial_m * np.sin(angles)))
    incidence = np.zeros((conductor_count, len(branch_ids)), dtype=float)
    for row_index, record in enumerate(records):
        incidence[row_index, branch_index[record[3]]] = record[4]
    signed_totals = incidence.sum(axis=0)
    if np.any(signed_totals != 0.0):
        unbalanced = [branch_ids[index] for index, total in enumerate(signed_totals)
                      if total != 0.0]
        raise ValueError(
            "Every branch must have balanced positive and negative active sides; "
            f"unbalanced branches: {unbalanced}.")

    branch_matrix = np.zeros((len(branch_ids), len(branch_ids)), dtype=float)
    scale = MU_0 * relative_permeability / (2.0 * math.pi)
    all_indices = np.arange(conductor_count)
    block_size = max(1, int(block_size))
    for start in range(0, conductor_count, block_size):
        stop = min(start + block_size, conductor_count)
        delta = positions[start:stop, None, :] - positions[None, :, :]
        distance = np.sqrt(np.sum(delta * delta, axis=2))
        local_indices = np.arange(start, stop)
        distance[np.arange(stop - start), local_indices] = conductor_gmr_m
        duplicate_mask = ((distance <= 0.0)
                          & (local_indices[:, None] != all_indices[None, :]))
        if np.any(duplicate_mask):
            raise ValueError("Distinct conductors cannot occupy the same physical position.")
        geometry = (active_length_m * np.arcsinh(active_length_m / distance)
                    - np.hypot(active_length_m, distance) + distance)
        partial = scale * geometry
        branch_matrix += incidence[start:stop].T @ partial @ incidence
    branch_matrix = (branch_matrix + branch_matrix.T) * 0.5
    if np.any(~np.isfinite(branch_matrix)) or np.any(np.diag(branch_matrix) <= 0.0):
        raise ValueError("The active-length branch inductance matrix is not physically usable.")
    diagonal_limit = np.sqrt(np.outer(np.diag(branch_matrix), np.diag(branch_matrix)))
    if np.any(np.abs(branch_matrix) > diagonal_limit * (1.0 + 1.0e-10)):
        raise ValueError("Mutual inductance exceeds the passive coupling bound.")

    phase_ids, phase_matrix = aggregate_phase_matrix(
        branch_matrix,
        branch_phases,
        expected_phase_ids=expected_phase_ids,
        expected_branches_per_phase=expected_branches_per_phase,
    )
    return InductanceResult(
        branch_ids=branch_ids,
        branch_phases=branch_phases,
        branch_matrix_h=branch_matrix,
        branch_coupling_matrix=normalize_inductance_matrix(branch_matrix),
        phase_ids=phase_ids,
        phase_matrix_h=phase_matrix,
        phase_coupling_matrix=normalize_inductance_matrix(phase_matrix),
        conductor_count=conductor_count,
        active_length_m=active_length_m,
        conductor_gmr_m=conductor_gmr_m,
        relative_permeability=relative_permeability,
    )
