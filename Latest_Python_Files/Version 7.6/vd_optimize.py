# -*- coding: utf-8 -*-
"""
Created on Mon Jun 24 10:15:37 2024

@author: ezzhh5
"""
import os
os.environ.setdefault("MPLCONFIGDIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".matplotlib"))
import numpy as np
import matplotlib.pyplot as plt
import cond_info_operation as co
import itertools
import sys
import time
from collections import OrderedDict
from dataclasses import dataclass
# from matplotlib.patches import FancyArrowPatch

DEFAULT_TIME_BUDGET_SEC = 15.0
EXACT_CANDIDATE_LIMIT = 100000
DEFAULT_BEAM_WIDTH = 48
MAX_BEAM_WIDTH = 96
MAX_ESTIMATED_SECONDS = 1.0e12
BRANCH_BOUND_CANDIDATE_LIMIT = 1000000

ALGORITHM_CHOICES = [
    ("auto", "Auto (recommended)"),
    ("exact", "Exact"),
    ("branch_bound", "Branch-and-Bound Exact"),
    ("beam_polish", "Beam + Polish"),
    ("coordinate", "Coordinate"),
]


def normalized_signed_adjustment(shift, count):
    if count <= 0:
        return 0
    shift = int(shift) % count
    if shift > count / 2:
        shift -= count
    return shift


def phase_a_template_rows(branch_phase_rows):
    return sorted(
        [row for row in branch_phase_rows if int(row.get("phase_index", -1)) == 0],
        key=lambda row: int(row.get("phase_branch_index", 0)),
    )


def phase_a_template_to_all_adjustments(branch_phase_rows, branch_count, phase_a_adjustments):
    if not branch_phase_rows:
        return []
    template = {
        index + 1: int(value)
        for index, value in enumerate(phase_a_adjustments)
    }
    values = [0] * int(branch_count)
    for row in branch_phase_rows:
        branch_index = int(row["branch_index"])
        phase_branch_index = int(row["phase_branch_index"])
        if 0 <= branch_index < len(values):
            values[branch_index] = template.get(phase_branch_index, 0)
    return values


def phase_a_template_candidate_values(db_conductor_id, phase_a_rows, force_even=False):
    candidate_values = []
    for row in phase_a_rows:
        branch_index = int(row["branch_index"])
        conductors = db_conductor_id[branch_index][1]
        values = []
        for shift in range(len(conductors)):
            if force_even and shift % 2 != 0:
                continue
            value = normalized_signed_adjustment(shift, len(conductors))
            if value not in values:
                values.append(value)
        candidate_values.append(values)
    return candidate_values


def normalize_algorithm_id(value):
    text = str(value or "").strip().lower()
    text = text.replace("_", " ").replace("-", " ")
    if text.startswith("auto"):
        return "auto"
    if text.startswith("exact"):
        return "exact"
    if "branch" in text or "bound" in text:
        return "branch_bound"
    if "beam" in text:
        return "beam_polish"
    if "coord" in text:
        return "coordinate"
    return "auto"


def algorithm_label(algorithm_id):
    algorithm_id = normalize_algorithm_id(algorithm_id)
    return dict(ALGORITHM_CHOICES).get(algorithm_id, "Auto (recommended)")


def phase_angle_rad(phase_index, num_phases=3):
    phase_index = int(phase_index)
    num_phases = max(int(num_phases or 3), 1)
    return -2.0 * np.pi * (phase_index % num_phases) / num_phases


def phase_cos_delta(phase_a, phase_b, num_phases=3):
    return float(np.cos(phase_angle_rad(phase_a, num_phases) - phase_angle_rad(phase_b, num_phases)))


def phase_voltage_difference_from_indices(index_a, index_b, cos_delta, voltage_drop, index_span):
    voltage_drop = abs(float(voltage_drop))
    index_span = max(float(index_span), 1e-9)
    mag_a = voltage_drop * np.asarray(index_a, dtype=np.float64) / index_span
    mag_b = voltage_drop * np.asarray(index_b, dtype=np.float64) / index_span
    square = mag_a * mag_a + mag_b * mag_b - 2.0 * mag_a * mag_b * np.asarray(cos_delta, dtype=np.float64)
    return np.sqrt(np.maximum(square, 0.0))


def voltage_to_equivalent_index(voltage_diff, voltage_drop, index_span):
    voltage_drop = abs(float(voltage_drop))
    if voltage_drop <= 1e-12:
        return 0.0
    return float(voltage_diff) * max(float(index_span), 1e-9) / voltage_drop


def phase_voltage_formula_help_text():
    return (
        "Phase-shift voltage formula:\n"
        "- For conductor i, U_i = abs(Vdrop) * index_i / index_span.\n"
        "- Three-phase angles are theta_A = 0, theta_B = -2*pi/3, theta_C = +2*pi/3.\n"
        "- Adjacent-layer voltage is VD_ij = |U_i*exp(j*theta_i) - U_j*exp(j*theta_j)|.\n"
        "- Expanded: VD_ij = sqrt(U_i^2 + U_j^2 - 2*U_i*U_j*cos(theta_i - theta_j)).\n"
        "- Same phase reduces to abs(Vdrop) * abs(index_i - index_j) / index_span.\n"
        "- Cross phase at 120 deg uses cos(120 deg) = -0.5, so VD_ij = sqrt(U_i^2 + U_j^2 + U_i*U_j).\n"
        "The reported index value is an equivalent index difference: VD_ij * index_span / abs(Vdrop)."
    )


def algorithm_help_text():
    """Return developer-facing guidance for VD inlet optimization algorithms.

    This text is intentionally kept in the optimization module rather than in
    the main GUI.  The GUI should show only the selected algorithm and estimated
    runtime; detailed guidance belongs here with the implementation.
    """
    return (
        "VD optimization algorithm guide:\n"
        "- Auto (recommended): uses the 15 s interaction budget to choose an algorithm for the current config. "
        "It runs Exact only when the candidate product and measured score time are small enough; otherwise it "
        "uses Beam + Polish, and falls back to Coordinate for very large estimated cases.\n"
        "- Exact: exhaustive Phase A template search. It guarantees the minimum for the constrained mirrored "
        "Phase A/B/C template, but cost grows as conductors_per_branch ** Naa. Use it for Naa=2 or other small "
        "candidate spaces.\n"
        "- Branch-and-Bound Exact: exact recursive search with conservative pruning from partial adjacent-layer "
        "max voltage lower bounds. It is useful when exhaustive search is too large but the current incumbent makes "
        "many branches provably worse.\n"
        "- Beam + Polish: keeps the best partial Phase A templates at each branch dimension, then refines the "
        "best candidates with coordinate descent. This is the preferred high-Naa algorithm because it avoids "
        "the full Cartesian product while still checking multiple global directions.\n"
        "- Coordinate: multi-seed coordinate descent. It is the fastest approximate mode and is useful for very "
        "large configs or quick checks, but it is more local than Beam + Polish.\n"
        "All algorithms optimize the same precomputed adjacent-layer voltage score and mirror the Phase A branch "
        "template to the other phases by phase-branch index. Stochastic/metaheuristic methods such as GA, "
        "simulated annealing, Bayesian optimisation, and CMA-ES are intentionally not implemented here because "
        "the search space is deterministic, structured, and cheap enough to benefit more from vectorized scoring, "
        "caching, deterministic beam search, and exact pruning.\n\n"
        + phase_voltage_formula_help_text()
    )


@dataclass
class VDMatrixResult:
    voltage_matrix: list
    equivalent_index_matrix: list
    max_voltage: float
    max_equivalent_index: float
    pair_count: int = 0
    cross_phase_pair_count: int = 0


@dataclass
class VDAdjacentSlotResult:
    """Maximum phase-aware voltage difference across neighbouring slots.

    The comparison is made layer-to-layer at the same radial layer.  Each
    physical slot boundary, including the last-to-first boundary, is included
    exactly once.
    """
    max_voltage: float
    max_equivalent_index: float
    pair_count: int = 0
    cross_phase_pair_count: int = 0


@dataclass
class VDOptimizationResult:
    best_adjustments: list
    phase_a_template: list
    score: tuple
    elapsed_sec: float
    estimated_sec: float
    is_exact: bool
    algorithm_id: str
    stopped_reason: str
    evaluations: int = 0


def compute_voltage_difference_matrix(cond_info, num_slots, num_layers, voltage_drop, index_span, num_phases=3):
    num_slots = int(num_slots)
    num_layers = int(num_layers)
    rows = max(0, num_layers - 1)
    cols = max(0, num_slots)
    voltage_matrix = [[0.0 for _slot in range(cols)] for _row in range(rows)]
    equivalent_index_matrix = [[0.0 for _slot in range(cols)] for _row in range(rows)]
    by_slot_layer = {}
    for cond in cond_info:
        if len(cond) < 5:
            continue
        slot = int(cond[0])
        layer = int(cond[1])
        phase = int(cond[2])
        index = float(cond[4])
        if slot < 0 or slot >= cols or layer < 0 or layer >= num_layers:
            continue
        by_slot_layer.setdefault((slot, layer), []).append((phase, index))

    pair_count = 0
    cross_phase_pair_count = 0
    for slot in range(cols):
        for layer in range(rows):
            lower_cells = by_slot_layer.get((slot, layer), [])
            upper_cells = by_slot_layer.get((slot, layer + 1), [])
            if not lower_cells or not upper_cells:
                continue
            for phase_a, index_a in lower_cells:
                for phase_b, index_b in upper_cells:
                    pair_count += 1
                    if phase_a != phase_b:
                        cross_phase_pair_count += 1
                    voltage_diff = phase_voltage_difference_from_indices(
                        index_a,
                        index_b,
                        phase_cos_delta(phase_a, phase_b, num_phases),
                        voltage_drop,
                        index_span,
                    )
                    voltage_diff = float(voltage_diff)
                    equivalent_index = voltage_to_equivalent_index(voltage_diff, voltage_drop, index_span)
                    if voltage_diff >= voltage_matrix[layer][slot]:
                        voltage_matrix[layer][slot] = voltage_diff
                        equivalent_index_matrix[layer][slot] = equivalent_index

    max_voltage = max([max(row) for row in voltage_matrix], default=0.0)
    max_equivalent_index = max([max(row) for row in equivalent_index_matrix], default=0.0)
    return VDMatrixResult(
        voltage_matrix,
        equivalent_index_matrix,
        float(max_voltage),
        float(max_equivalent_index),
        pair_count,
        cross_phase_pair_count,
    )


def compute_adjacent_slot_voltage_difference(
    cond_info, num_slots, num_layers, voltage_drop, index_span, num_phases=3,
):
    """Return the worst voltage difference between same-layer adjacent slots."""
    num_slots = int(num_slots)
    num_layers = int(num_layers)
    by_slot_layer = {}
    for cond in cond_info:
        if len(cond) < 5:
            continue
        slot, layer, phase, index = int(cond[0]), int(cond[1]), int(cond[2]), float(cond[4])
        if 0 <= slot < num_slots and 0 <= layer < num_layers:
            by_slot_layer.setdefault((slot, layer), []).append((phase, index))

    if num_slots < 2:
        return VDAdjacentSlotResult(0.0, 0.0)
    slot_pairs = [(slot, slot + 1) for slot in range(num_slots - 1)]
    if num_slots > 2:
        slot_pairs.append((num_slots - 1, 0))

    max_voltage = 0.0
    max_equivalent_index = 0.0
    pair_count = 0
    cross_phase_pair_count = 0
    for slot_a, slot_b in slot_pairs:
        for layer in range(num_layers):
            left = by_slot_layer.get((slot_a, layer), [])
            right = by_slot_layer.get((slot_b, layer), [])
            for phase_a, index_a in left:
                for phase_b, index_b in right:
                    pair_count += 1
                    if phase_a != phase_b:
                        cross_phase_pair_count += 1
                    voltage_diff = float(phase_voltage_difference_from_indices(
                        index_a,
                        index_b,
                        phase_cos_delta(phase_a, phase_b, num_phases),
                        voltage_drop,
                        index_span,
                    ))
                    if voltage_diff >= max_voltage:
                        max_voltage = voltage_diff
                        max_equivalent_index = voltage_to_equivalent_index(
                            voltage_diff, voltage_drop, index_span)
    return VDAdjacentSlotResult(
        float(max_voltage), float(max_equivalent_index), pair_count, cross_phase_pair_count)


def compute_adjacent_slot_interlayer_voltage_difference(
    cond_info, num_slots, num_layers, voltage_drop, index_span, num_phases=3,
):
    """Return the worst voltage difference across diagonal slot/layer neighbours.

    Each adjacent-slot boundary is visited once; both diagonal directions across
    every adjacent layer pair are evaluated.
    """
    num_slots = int(num_slots)
    num_layers = int(num_layers)
    by_slot_layer = {}
    for cond in cond_info:
        if len(cond) < 5:
            continue
        slot, layer, phase, index = int(cond[0]), int(cond[1]), int(cond[2]), float(cond[4])
        if 0 <= slot < num_slots and 0 <= layer < num_layers:
            by_slot_layer.setdefault((slot, layer), []).append((phase, index))

    if num_slots < 2 or num_layers < 2:
        return VDAdjacentSlotResult(0.0, 0.0)
    slot_pairs = [(slot, slot + 1) for slot in range(num_slots - 1)]
    if num_slots > 2:
        slot_pairs.append((num_slots - 1, 0))

    max_voltage = 0.0
    max_equivalent_index = 0.0
    pair_count = 0
    cross_phase_pair_count = 0
    for slot_a, slot_b in slot_pairs:
        for layer in range(num_layers - 1):
            diagonal_pairs = (
                (by_slot_layer.get((slot_a, layer), []), by_slot_layer.get((slot_b, layer + 1), [])),
                (by_slot_layer.get((slot_a, layer + 1), []), by_slot_layer.get((slot_b, layer), [])),
            )
            for left, right in diagonal_pairs:
                for phase_a, index_a in left:
                    for phase_b, index_b in right:
                        pair_count += 1
                        if phase_a != phase_b:
                            cross_phase_pair_count += 1
                        voltage_diff = float(phase_voltage_difference_from_indices(
                            index_a,
                            index_b,
                            phase_cos_delta(phase_a, phase_b, num_phases),
                            voltage_drop,
                            index_span,
                        ))
                        if voltage_diff >= max_voltage:
                            max_voltage = voltage_diff
                            max_equivalent_index = voltage_to_equivalent_index(
                                voltage_diff, voltage_drop, index_span)
    return VDAdjacentSlotResult(
        float(max_voltage), float(max_equivalent_index), pair_count, cross_phase_pair_count)


class VDOptimizationProblem:
    def __init__(
        self,
        base_cond_info,
        base_db_conductor_id,
        branch_phase_rows,
        num_slots,
        num_layers,
        voltage_drop,
        index_span,
        force_even=False,
        num_phases=3,
    ):
        self.base_cond_info = list(base_cond_info)
        self.base_db_conductor_id = [
            [branch_id, list(conductors)]
            for branch_id, conductors in base_db_conductor_id
        ]
        self.branch_phase_rows = list(branch_phase_rows)
        self.num_slots = int(num_slots)
        self.num_layers = int(num_layers)
        self.voltage_drop = abs(float(voltage_drop))
        self.index_span = max(float(index_span), 1e-9)
        self.force_even = bool(force_even)
        self.num_phases = max(int(num_phases or 3), 1)
        self.branch_count = len(self.base_db_conductor_id)
        self.branch_lengths = [
            len(conductors)
            for _branch_id, conductors in self.base_db_conductor_id
        ]
        self.phase_a_rows = phase_a_template_rows(self.branch_phase_rows)
        if not self.phase_a_rows:
            raise ValueError("No Phase A branches found for Volt Diff optimization.")
        self.candidate_values = phase_a_template_candidate_values(
            self.base_db_conductor_id,
            self.phase_a_rows,
            self.force_even,
        )
        self.ordered_candidate_values = [
            sorted(values, key=lambda value: (abs(value), value))
            for values in self.candidate_values
        ]
        self._template_size = len(self.candidate_values)
        self._branch_to_template_index = self._build_branch_to_template_index()
        self._pair_data = self._build_adjacent_layer_pair_data()
        self._build_pair_arrays()
        self._score_cache = OrderedDict()
        self._score_cache_max_size = 200000
        self._score_cache_hits = 0
        self._score_cache_misses = 0
        self._score_seconds = None
        self._dimension_influence = self._build_dimension_influence()
        self._dimension_order = sorted(
            range(self.template_size),
            key=lambda dim: (-self._dimension_influence[dim], dim),
        )

    @property
    def template_size(self):
        return self._template_size

    @property
    def pair_count(self):
        return len(self._pair_data)

    @property
    def candidate_product(self):
        product = 1
        for values in self.candidate_values:
            product *= max(1, len(values))
        return product

    def _build_adjacent_layer_pair_data(self):
        by_conductor = {}
        by_slot_layer = {}
        for branch_index, (_branch_id, conductors) in enumerate(self.base_db_conductor_id):
            branch_length = len(conductors)
            for base_index, conductor in enumerate(conductors):
                if len(conductor) < 2:
                    continue
                slot = int(conductor[0])
                layer = int(conductor[1])
                phasor = conductor[2] if len(conductor) > 2 else None
                assignment = (branch_index, base_index, branch_length)
                by_conductor[(slot, layer, phasor)] = assignment
                by_slot_layer.setdefault((slot, layer), []).append(assignment)

        cell_assignments = {}
        for cond in self.base_cond_info:
            if len(cond) < 5:
                continue
            slot = int(cond[0])
            layer = int(cond[1])
            phase = int(cond[2])
            phasor = cond[5] if len(cond) > 5 else None
            assignment = by_conductor.get((slot, layer, phasor))
            if assignment is None:
                fallback = by_slot_layer.get((slot, layer), [])
                assignment = fallback[0] if fallback else None
            if assignment is not None:
                item = (phase,) + assignment
                cells = cell_assignments.setdefault((slot, layer), [])
                if item not in cells:
                    cells.append(item)

        pair_data = []
        for slot in range(self.num_slots):
            for layer in range(max(0, self.num_layers - 1)):
                lower_cells = cell_assignments.get((slot, layer), [])
                upper_cells = cell_assignments.get((slot, layer + 1), [])
                if not lower_cells or not upper_cells:
                    continue
                for lower in lower_cells:
                    for upper in upper_cells:
                        phase_a, branch_a, base_index_a, branch_length_a = lower
                        phase_b, branch_b, base_index_b, branch_length_b = upper
                        pair_data.append((
                            branch_a,
                            base_index_a,
                            branch_length_a,
                            phase_a,
                            branch_b,
                            base_index_b,
                            branch_length_b,
                            phase_b,
                        ))
        return pair_data

    def _build_branch_to_template_index(self):
        mapping = [-1] * self.branch_count
        for row in self.branch_phase_rows:
            branch_index = int(row.get("branch_index", -1))
            template_index = int(row.get("phase_branch_index", 0)) - 1
            if 0 <= branch_index < self.branch_count and 0 <= template_index < self.template_size:
                mapping[branch_index] = template_index
        return mapping

    def _build_pair_arrays(self):
        if not self._pair_data:
            empty = np.array([], dtype=np.int64)
            self._pair_branch_a = empty
            self._pair_base_index_a = empty
            self._pair_branch_length_a = empty
            self._pair_phase_a = empty
            self._pair_branch_b = empty
            self._pair_base_index_b = empty
            self._pair_branch_length_b = empty
            self._pair_phase_b = empty
            self._pair_template_a = empty
            self._pair_template_b = empty
            self._pair_cos_delta = np.array([], dtype=np.float64)
            return

        data = np.asarray(self._pair_data, dtype=np.int64)
        self._pair_branch_a = data[:, 0]
        self._pair_base_index_a = data[:, 1]
        self._pair_branch_length_a = data[:, 2]
        self._pair_phase_a = data[:, 3]
        self._pair_branch_b = data[:, 4]
        self._pair_base_index_b = data[:, 5]
        self._pair_branch_length_b = data[:, 6]
        self._pair_phase_b = data[:, 7]
        branch_to_template = np.asarray(self._branch_to_template_index, dtype=np.int64)
        self._pair_template_a = branch_to_template[self._pair_branch_a]
        self._pair_template_b = branch_to_template[self._pair_branch_b]
        self._pair_cos_delta = np.asarray([
            phase_cos_delta(phase_a, phase_b, self.num_phases)
            for phase_a, phase_b in zip(self._pair_phase_a, self._pair_phase_b)
        ], dtype=np.float64)

    def _build_dimension_influence(self):
        influence = [0] * self.template_size
        for template_index in list(self._pair_template_a) + list(self._pair_template_b):
            template_index = int(template_index)
            if 0 <= template_index < self.template_size:
                influence[template_index] += 1
        return influence

    def default_template(self):
        template = []
        for values in self.ordered_candidate_values:
            template.append(values[0] if values else 0)
        return template

    def coerce_template(self, template):
        values = list(template or [])
        coerced = []
        for index, candidates in enumerate(self.candidate_values):
            raw_value = int(values[index]) if index < len(values) else 0
            if raw_value in candidates:
                coerced.append(raw_value)
            else:
                coerced.append(min(candidates, key=lambda value: (abs(value - raw_value), abs(value), value)))
        return coerced

    def template_from_all_adjustments(self, all_adjustments):
        adjustments = list(all_adjustments or [])
        template = []
        for row in self.phase_a_rows:
            branch_index = int(row["branch_index"])
            template.append(adjustments[branch_index] if branch_index < len(adjustments) else 0)
        return self.coerce_template(template)

    def template_to_all_adjustments(self, phase_a_template):
        template = self.coerce_template(phase_a_template)
        values = [0] * self.branch_count
        for branch_index, template_index in enumerate(self._branch_to_template_index):
            if 0 <= template_index < len(template):
                values[branch_index] = int(template[template_index])
        return values

    def score_template(self, phase_a_template):
        return self.score_template_cached(phase_a_template)

    def score_template_cached(self, phase_a_template):
        key = tuple(int(value) for value in self.coerce_template(phase_a_template))
        cached = self._score_cache.get(key)
        if cached is not None:
            self._score_cache_hits += 1
            self._score_cache.move_to_end(key)
            return cached
        self._score_cache_misses += 1
        score = self.score_all_adjustments_fast(self.template_to_all_adjustments(key))
        self._score_cache[key] = score
        if len(self._score_cache) > self._score_cache_max_size:
            self._score_cache.popitem(last=False)
        return score

    def clear_score_cache(self):
        self._score_cache.clear()
        self._score_cache_hits = 0
        self._score_cache_misses = 0

    def cache_info(self):
        return {
            "size": len(self._score_cache),
            "hits": self._score_cache_hits,
            "misses": self._score_cache_misses,
        }

    def score_all_adjustments(self, adjustments):
        return self.score_all_adjustments_fast(adjustments)

    def score_all_adjustments_fast(self, adjustments):
        if self.pair_count <= 0:
            return 0.0, 0
        adjustments_array = np.zeros(self.branch_count, dtype=np.int64)
        adjustments = list(adjustments or [])
        if len(adjustments) < self.branch_count:
            adjustments = adjustments + [0] * (self.branch_count - len(adjustments))
        if adjustments:
            adjustments_array[: self.branch_count] = np.asarray(adjustments[: self.branch_count], dtype=np.int64)
        index_a = np.mod(
            self._pair_base_index_a - adjustments_array[self._pair_branch_a],
            self._pair_branch_length_a,
        )
        index_b = np.mod(
            self._pair_base_index_b - adjustments_array[self._pair_branch_b],
            self._pair_branch_length_b,
        )
        voltage_diffs = phase_voltage_difference_from_indices(
            index_a,
            index_b,
            self._pair_cos_delta,
            self.voltage_drop,
            self.index_span,
        )
        max_voltage = float(np.max(voltage_diffs)) if len(voltage_diffs) else 0.0
        return max_voltage, voltage_to_equivalent_index(max_voltage, self.voltage_drop, self.index_span)

    def score_all_adjustments_slow(self, adjustments):
        adjustments = list(adjustments or [])
        if len(adjustments) < self.branch_count:
            adjustments = adjustments + [0] * (self.branch_count - len(adjustments))
        max_voltage = 0.0
        for (
            branch_a,
            base_index_a,
            branch_length_a,
            phase_a,
            branch_b,
            base_index_b,
            branch_length_b,
            phase_b,
        ) in self._pair_data:
            if branch_length_a <= 0 or branch_length_b <= 0:
                continue
            index_a = (base_index_a - int(adjustments[branch_a])) % branch_length_a
            index_b = (base_index_b - int(adjustments[branch_b])) % branch_length_b
            voltage_diff = phase_voltage_difference_from_indices(
                index_a,
                index_b,
                phase_cos_delta(phase_a, phase_b, self.num_phases),
                self.voltage_drop,
                self.index_span,
            )
            voltage_diff = float(voltage_diff)
            if voltage_diff > max_voltage:
                max_voltage = voltage_diff
        return max_voltage, voltage_to_equivalent_index(max_voltage, self.voltage_drop, self.index_span)

    def score_key(self, phase_a_template, score=None):
        score = score if score is not None else self.score_template(phase_a_template)
        template = list(phase_a_template)
        return (
            score[0],
            score[1],
            sum(abs(value) for value in template),
            template,
        )

    def _benchmark_score_seconds(self):
        if self._score_seconds is not None:
            return self._score_seconds
        sample_count = max(8, min(96, self.candidate_product if self.candidate_product > 0 else 8))
        templates = []
        default_template = self.default_template()
        templates.append(default_template)
        for sample_index in range(sample_count - 1):
            template = []
            for dim, values in enumerate(self.candidate_values):
                template.append(values[(sample_index + dim) % len(values)])
            templates.append(template)
        start = time.perf_counter()
        for template in templates:
            self.score_all_adjustments_fast(self.template_to_all_adjustments(template))
        elapsed = time.perf_counter() - start
        self._score_seconds = max(elapsed / len(templates), 1e-7)
        return self._score_seconds

    def estimate_runtime(self, algorithm_id="auto", time_budget_sec=DEFAULT_TIME_BUDGET_SEC):
        algorithm_id = normalize_algorithm_id(algorithm_id)
        score_seconds = self._benchmark_score_seconds()
        exact_evals = self.candidate_product
        exact_sec = min(MAX_ESTIMATED_SECONDS, float(min(exact_evals, 10**12)) * score_seconds)

        def with_problem_fields(estimate):
            estimate["candidate_product"] = self.candidate_product
            estimate["template_size"] = self.template_size
            estimate["pair_count"] = self.pair_count
            return estimate

        def coordinate_estimate(seed_count=8, passes=4):
            evals = seed_count * (1 + passes * sum(len(values) for values in self.candidate_values))
            return evals, evals * score_seconds

        def beam_estimate(beam_width=DEFAULT_BEAM_WIDTH, polish_seed_count=10, passes=3):
            live = 1
            beam_evals = 0
            for values in self.candidate_values:
                beam_evals += live * len(values)
                live = min(beam_width, live * len(values))
            polish_evals = polish_seed_count * (1 + passes * sum(len(values) for values in self.candidate_values))
            evals = beam_evals + polish_evals
            return evals, evals * score_seconds

        def branch_bound_estimate():
            rough_evals = min(exact_evals, max(1, exact_evals // 4))
            seconds = min(MAX_ESTIMATED_SECONDS, float(min(rough_evals, 10**12)) * score_seconds)
            return rough_evals, seconds

        if algorithm_id == "exact":
            return with_problem_fields({
                "algorithm_id": "exact",
                "estimated_sec": exact_sec,
                "estimated_evaluations": exact_evals,
                "is_exact": True,
            })
        if algorithm_id == "branch_bound":
            evals, seconds = branch_bound_estimate()
            return with_problem_fields({
                "algorithm_id": "branch_bound",
                "estimated_sec": seconds,
                "estimated_evaluations": evals,
                "is_exact": True,
            })
        if algorithm_id == "coordinate":
            evals, seconds = coordinate_estimate()
            return with_problem_fields({
                "algorithm_id": "coordinate",
                "estimated_sec": seconds,
                "estimated_evaluations": evals,
                "is_exact": False,
            })
        if algorithm_id == "beam_polish":
            beam_width = self.recommended_beam_width(time_budget_sec)
            evals, seconds = beam_estimate(beam_width)
            return with_problem_fields({
                "algorithm_id": "beam_polish",
                "estimated_sec": seconds,
                "estimated_evaluations": evals,
                "beam_width": beam_width,
                "is_exact": False,
            })

        if self.candidate_product <= EXACT_CANDIDATE_LIMIT and exact_sec <= time_budget_sec:
            estimate = self.estimate_runtime("exact", time_budget_sec)
            estimate["selected_by_auto"] = True
            return estimate

        if self.candidate_product <= BRANCH_BOUND_CANDIDATE_LIMIT:
            bb_evals, bb_sec = branch_bound_estimate()
            if bb_sec <= max(time_budget_sec * 1.25, 1.0):
                return with_problem_fields({
                    "algorithm_id": "branch_bound",
                    "estimated_sec": bb_sec,
                    "estimated_evaluations": bb_evals,
                    "is_exact": True,
                    "selected_by_auto": True,
                })

        beam_width = self.recommended_beam_width(time_budget_sec)
        beam_evals, beam_sec = beam_estimate(beam_width)
        if beam_width >= 4 and beam_sec <= max(time_budget_sec * 1.25, 1.0):
            return with_problem_fields({
                "algorithm_id": "beam_polish",
                "estimated_sec": beam_sec,
                "estimated_evaluations": beam_evals,
                "beam_width": beam_width,
                "is_exact": False,
                "selected_by_auto": True,
            })
        coord_evals, coord_sec = coordinate_estimate()
        return with_problem_fields({
            "algorithm_id": "coordinate",
            "estimated_sec": coord_sec,
            "estimated_evaluations": coord_evals,
            "is_exact": False,
            "selected_by_auto": True,
        })

    def recommended_beam_width(self, time_budget_sec=DEFAULT_TIME_BUDGET_SEC):
        score_seconds = self._benchmark_score_seconds()
        sum_values = max(1, sum(len(values) for values in self.candidate_values))
        if score_seconds <= 0:
            return DEFAULT_BEAM_WIDTH
        rough_width = int((time_budget_sec / score_seconds) / max(sum_values, 1))
        return max(4, min(MAX_BEAM_WIDTH, DEFAULT_BEAM_WIDTH, rough_width))


def _result_from_template(problem, template, score, start_time, estimated_sec, algorithm_id, is_exact, stopped_reason, evaluations):
    return VDOptimizationResult(
        best_adjustments=problem.template_to_all_adjustments(template),
        phase_a_template=list(template),
        score=score,
        elapsed_sec=time.perf_counter() - start_time,
        estimated_sec=float(estimated_sec),
        is_exact=bool(is_exact),
        algorithm_id=algorithm_id,
        stopped_reason=stopped_reason,
        evaluations=int(evaluations),
    )


def _seed_templates(problem, initial_adjustments=None):
    seeds = []
    default_template = problem.default_template()
    seeds.append(default_template)
    if initial_adjustments is not None:
        seeds.append(problem.template_from_all_adjustments(initial_adjustments))
    if problem.template_size:
        seeds.append([values[len(values) // 2] for values in problem.ordered_candidate_values])
        seeds.append([values[-1] for values in problem.ordered_candidate_values])
    unique = []
    seen = set()
    for seed in seeds:
        seed = tuple(problem.coerce_template(seed))
        if seed not in seen:
            seen.add(seed)
            unique.append(list(seed))
    return unique


def _optimize_coordinate(problem, initial_adjustments=None, seed_templates=None, time_budget_sec=DEFAULT_TIME_BUDGET_SEC, max_passes=4):
    start = time.perf_counter()
    deadline = start + max(float(time_budget_sec), 0.1)
    estimate = problem.estimate_runtime("coordinate", time_budget_sec)
    seeds = list(seed_templates or []) + _seed_templates(problem, initial_adjustments)
    best_template = None
    best_score = None
    best_key = None
    evaluations = 0
    stopped_reason = "completed"

    for seed in seeds:
        template = problem.coerce_template(seed)
        score = problem.score_template(template)
        evaluations += 1
        key = problem.score_key(template, score)
        if best_key is None or key < best_key:
            best_template = list(template)
            best_score = score
            best_key = key

        for _pass_index in range(max_passes):
            improved = False
            for dim in problem._dimension_order:
                values = problem.ordered_candidate_values[dim]
                if time.perf_counter() > deadline:
                    stopped_reason = "time budget reached"
                    return _result_from_template(
                        problem,
                        best_template,
                        best_score,
                        start,
                        estimate["estimated_sec"],
                        "coordinate",
                        False,
                        stopped_reason,
                        evaluations,
                    )
                current_value = template[dim]
                local_best_value = current_value
                local_best_score = score
                local_best_key = problem.score_key(template, score)
                for value in values:
                    if value == current_value:
                        continue
                    template[dim] = value
                    candidate_score = problem.score_template(template)
                    evaluations += 1
                    candidate_key = problem.score_key(template, candidate_score)
                    if candidate_key < local_best_key:
                        local_best_value = value
                        local_best_score = candidate_score
                        local_best_key = candidate_key
                template[dim] = local_best_value
                score = local_best_score
                if local_best_value != current_value:
                    improved = True
                if local_best_key < best_key:
                    best_template = list(template)
                    best_score = score
                    best_key = local_best_key
            if not improved:
                break

    return _result_from_template(
        problem,
        best_template,
        best_score,
        start,
        estimate["estimated_sec"],
        "coordinate",
        False,
        stopped_reason,
        evaluations,
    )


def _optimize_exact(problem, time_budget_sec=DEFAULT_TIME_BUDGET_SEC):
    start = time.perf_counter()
    estimate = problem.estimate_runtime("exact", time_budget_sec)
    best_template = None
    best_score = None
    best_key = None
    evaluations = 0
    for phase_a_template in itertools.product(*problem.candidate_values):
        template = list(phase_a_template)
        score = problem.score_template(template)
        evaluations += 1
        score_key = problem.score_key(template, score)
        if best_key is None or score_key < best_key:
            best_template = template
            best_score = score
            best_key = score_key
    return _result_from_template(
        problem,
        best_template,
        best_score,
        start,
        estimate["estimated_sec"],
        "exact",
        True,
        "completed",
        evaluations,
    )


def _partial_max_voltage(problem, assignment):
    max_voltage = 0.0
    for pair_index in range(problem.pair_count):
        dim_a = int(problem._pair_template_a[pair_index])
        dim_b = int(problem._pair_template_b[pair_index])
        if dim_a >= 0:
            adj_a = assignment[dim_a]
            if adj_a is None:
                continue
        else:
            adj_a = 0
        if dim_b >= 0:
            adj_b = assignment[dim_b]
            if adj_b is None:
                continue
        else:
            adj_b = 0
        index_a = (
            int(problem._pair_base_index_a[pair_index]) - int(adj_a)
        ) % int(problem._pair_branch_length_a[pair_index])
        index_b = (
            int(problem._pair_base_index_b[pair_index]) - int(adj_b)
        ) % int(problem._pair_branch_length_b[pair_index])
        voltage_diff = phase_voltage_difference_from_indices(
            index_a,
            index_b,
            float(problem._pair_cos_delta[pair_index]),
            problem.voltage_drop,
            problem.index_span,
        )
        voltage_diff = float(voltage_diff)
        if voltage_diff > max_voltage:
            max_voltage = voltage_diff
    return max_voltage


def _optimize_branch_bound(problem, initial_adjustments=None, time_budget_sec=DEFAULT_TIME_BUDGET_SEC):
    start = time.perf_counter()
    estimate = problem.estimate_runtime("branch_bound", time_budget_sec)
    deadline = start + max(float(time_budget_sec), 0.1)
    if problem.template_size <= 0:
        template = []
        score = problem.score_template(template)
        return _result_from_template(problem, template, score, start, estimate["estimated_sec"], "branch_bound", True, "completed", 1)

    incumbent_budget = min(1.0, max(0.1, float(time_budget_sec) * 0.10))
    incumbent = _optimize_coordinate(
        problem,
        initial_adjustments=initial_adjustments,
        time_budget_sec=incumbent_budget,
        max_passes=2,
    )
    best_template = list(incumbent.phase_a_template)
    best_score = incumbent.score
    best_key = problem.score_key(best_template, best_score)
    best_max_voltage = float(best_score[0])
    best_abs_sum = sum(abs(value) for value in best_template)
    evaluations = incumbent.evaluations
    assignment = [None] * problem.template_size
    dimension_order = list(problem._dimension_order)
    stopped_reason = "completed"

    def search(depth, partial_abs_sum):
        nonlocal best_template, best_score, best_key, best_max_voltage, best_abs_sum, evaluations, stopped_reason
        evaluations += 1
        if time.perf_counter() > deadline:
            stopped_reason = "time budget reached"
            return
        current_max_voltage = _partial_max_voltage(problem, assignment)
        if current_max_voltage > best_max_voltage + 1e-12:
            return
        if abs(current_max_voltage - best_max_voltage) <= 1e-12 and partial_abs_sum > best_abs_sum:
            return
        if depth >= len(dimension_order):
            template = [int(value) if value is not None else 0 for value in assignment]
            score = problem.score_template(template)
            key = problem.score_key(template, score)
            if key < best_key:
                best_template = list(template)
                best_score = score
                best_key = key
                best_max_voltage = float(score[0])
                best_abs_sum = sum(abs(value) for value in template)
            return

        dim = dimension_order[depth]
        for value in problem.ordered_candidate_values[dim]:
            assignment[dim] = int(value)
            search(depth + 1, partial_abs_sum + abs(int(value)))
            assignment[dim] = None
            if stopped_reason != "completed":
                return

    search(0, 0)
    return _result_from_template(
        problem,
        best_template,
        best_score,
        start,
        estimate["estimated_sec"],
        "branch_bound",
        stopped_reason == "completed",
        stopped_reason,
        evaluations,
    )


def _optimize_beam_polish(
    problem,
    initial_adjustments=None,
    time_budget_sec=DEFAULT_TIME_BUDGET_SEC,
    beam_width=None,
    polish_seed_count=12,
    max_polish_passes=3,
):
    start = time.perf_counter()
    estimate = problem.estimate_runtime("beam_polish", time_budget_sec)
    beam_width = int(beam_width if beam_width is not None else estimate.get("beam_width", DEFAULT_BEAM_WIDTH))
    deadline = start + max(float(time_budget_sec), 0.1)
    partials = [()]
    evaluations = 0
    stopped_reason = "completed"
    dimension_order = list(problem._dimension_order)
    base_template = problem.default_template()

    for depth, dim in enumerate(dimension_order):
        values = problem.ordered_candidate_values[dim]
        scored = []
        seen_partials = set()
        for partial in partials:
            for value in values:
                if time.perf_counter() > deadline:
                    stopped_reason = "time budget reached"
                    break
                next_partial = partial + (int(value),)
                if next_partial in seen_partials:
                    continue
                seen_partials.add(next_partial)
                full_template = list(base_template)
                for partial_index, partial_value in enumerate(partial):
                    full_template[dimension_order[partial_index]] = partial_value
                full_template[dim] = value
                score = problem.score_template(full_template)
                evaluations += 1
                scored.append((problem.score_key(full_template, score), next_partial))
            if stopped_reason != "completed":
                break
        if not scored:
            break
        scored.sort(key=lambda item: item[0])
        partials = [partial for _key, partial in scored[:beam_width]]
        if stopped_reason != "completed":
            break

    seed_templates = []
    for partial in partials:
        template = list(base_template)
        for partial_index, value in enumerate(partial):
            template[dimension_order[partial_index]] = value
        seed_templates.append(template)
    seed_templates = seed_templates[: min(polish_seed_count, len(seed_templates))]

    remaining = max(0.1, deadline - time.perf_counter())
    polished = _optimize_coordinate(
        problem,
        initial_adjustments=initial_adjustments,
        seed_templates=seed_templates,
        time_budget_sec=remaining,
        max_passes=max_polish_passes,
    )
    polished.algorithm_id = "beam_polish"
    polished.estimated_sec = float(estimate["estimated_sec"])
    polished.elapsed_sec = time.perf_counter() - start
    polished.evaluations += evaluations
    polished.stopped_reason = stopped_reason if stopped_reason != "completed" else polished.stopped_reason
    polished.is_exact = False
    return polished


def optimize(problem, algorithm_id="auto", time_budget_sec=DEFAULT_TIME_BUDGET_SEC, initial_adjustments=None):
    algorithm_id = normalize_algorithm_id(algorithm_id)
    estimate = problem.estimate_runtime(algorithm_id, time_budget_sec)
    selected_algorithm = estimate["algorithm_id"]
    if selected_algorithm == "exact":
        return _optimize_exact(problem, time_budget_sec)
    if selected_algorithm == "branch_bound":
        return _optimize_branch_bound(problem, initial_adjustments, time_budget_sec=time_budget_sec)
    if selected_algorithm == "coordinate":
        return _optimize_coordinate(problem, initial_adjustments, time_budget_sec=time_budget_sec)
    return _optimize_beam_polish(problem, initial_adjustments, time_budget_sec=time_budget_sec)


def format_estimate(estimate, requested_algorithm="auto"):
    selected = estimate.get("algorithm_id", "auto")
    mode = "exact" if estimate.get("is_exact") else "approx"
    requested = normalize_algorithm_id(requested_algorithm)
    prefix = f"{algorithm_label(selected)}: " if requested == "auto" else ""
    seconds = float(estimate.get("estimated_sec", 0.0))
    if seconds < 0.01:
        seconds_text = "<0.01 s"
    elif seconds < 60:
        seconds_text = f"{seconds:.2f} s"
    else:
        minutes = seconds / 60
        seconds_text = f"{minutes:.1f} min"
    extras = []
    if "beam_width" in estimate:
        extras.append(f"beam {estimate['beam_width']}")
    extras.append(mode)
    return f"{prefix}{seconds_text}, " + ", ".join(extras)


def optimize_phase_a_template(db_conductor_id, branch_phase_rows, score_fn, force_even=False):
    phase_a_rows = phase_a_template_rows(branch_phase_rows)
    if not phase_a_rows:
        raise ValueError("No Phase A branches found for Volt Diff optimization.")

    candidate_values = phase_a_template_candidate_values(db_conductor_id, phase_a_rows, force_even)
    best_phase_a_adjustments = None
    best_all_adjustments = None
    best_score = None
    best_key = None

    for phase_a_adjustments in itertools.product(*candidate_values):
        all_adjustments = phase_a_template_to_all_adjustments(
            branch_phase_rows,
            len(db_conductor_id),
            phase_a_adjustments,
        )
        score = score_fn(all_adjustments)
        score_key = (
            score[0],
            score[1],
            sum(abs(value) for value in phase_a_adjustments),
            list(phase_a_adjustments),
        )
        if best_key is None or score_key < best_key:
            best_phase_a_adjustments = list(phase_a_adjustments)
            best_all_adjustments = all_adjustments
            best_score = score
            best_key = score_key

    return best_all_adjustments, best_phase_a_adjustments, best_score


def _make_synthetic_problem(num_slots=8, num_layers=3, num_phases=3, ab=2, force_even=False):
    branch_count = num_phases * ab
    db_conductor_id = [[index + 1, []] for index in range(branch_count)]
    base_cond_info = []
    for phase in range(num_phases):
        for slot in range(num_slots):
            for layer in range(num_layers):
                branch_in_phase = (slot + layer) % ab
                branch_index = phase * ab + branch_in_phase
                phasor = phase
                conductor = (slot, layer, phasor)
                db_conductor_id[branch_index][1].append(conductor)
                base_cond_info.append((slot, layer, phase, -1, -1, phasor, 0))
    branch_phase_rows = []
    for phase in range(num_phases):
        for branch_in_phase in range(ab):
            branch_index = phase * ab + branch_in_phase
            branch_phase_rows.append({
                "branch_index": branch_index,
                "branch_id": branch_index + 1,
                "phase_index": phase,
                "phase_branch_index": branch_in_phase + 1,
            })
    max_index = max((len(branch[1]) for branch in db_conductor_id), default=1)
    return VDOptimizationProblem(
        base_cond_info,
        db_conductor_id,
        branch_phase_rows,
        num_slots,
        num_layers,
        voltage_drop=400.0,
        index_span=max(float(max_index - 1), 1.0),
        force_even=force_even,
    )


def _distinct_templates(problem, count):
    templates = [problem.default_template()]
    for sample_index in range(max(0, count - 1)):
        template = []
        for dim, values in enumerate(problem.candidate_values):
            template.append(values[(sample_index + dim) % len(values)])
        templates.append(problem.coerce_template(template))
    unique = []
    seen = set()
    for template in templates:
        key = tuple(template)
        if key not in seen:
            seen.add(key)
            unique.append(template)
    return unique


def _assert_self_checks():
    cases = [
        ("normal", _make_synthetic_problem(8, 3, 3, 2, False)),
        ("no_pairs", _make_synthetic_problem(8, 1, 3, 2, False)),
        ("one_phase_a_branch", _make_synthetic_problem(7, 3, 3, 1, False)),
        ("uneven_lengths", _make_synthetic_problem(7, 4, 3, 2, False)),
        ("force_even", _make_synthetic_problem(8, 3, 3, 2, True)),
    ]
    for name, problem in cases:
        for template in _distinct_templates(problem, 20):
            all_adjustments = problem.template_to_all_adjustments(template)
            slow = problem.score_all_adjustments_slow(all_adjustments)
            fast = problem.score_all_adjustments_fast(all_adjustments)
            if slow != fast:
                raise AssertionError(f"{name}: fast scorer mismatch {slow} != {fast}")

        exact = _optimize_exact(problem, time_budget_sec=10.0)
        branch_bound = _optimize_branch_bound(problem, time_budget_sec=10.0)
        if branch_bound.is_exact and exact.score != branch_bound.score:
            raise AssertionError(f"{name}: exact mismatch {exact.score} != {branch_bound.score}")
        if branch_bound.is_exact and exact.phase_a_template != branch_bound.phase_a_template:
            raise AssertionError(f"{name}: exact template mismatch {exact.phase_a_template} != {branch_bound.phase_a_template}")

        zero_score = problem.score_template(problem.default_template())
        coordinate = _optimize_coordinate(problem, time_budget_sec=5.0)
        beam = _optimize_beam_polish(problem, time_budget_sec=5.0)
        if coordinate.score > zero_score:
            raise AssertionError(f"{name}: coordinate worsened {coordinate.score} > {zero_score}")
        if beam.score > zero_score:
            raise AssertionError(f"{name}: beam worsened {beam.score} > {zero_score}")
        auto = optimize(problem, algorithm_id="auto", time_budget_sec=5.0)
        if not isinstance(auto, VDOptimizationResult):
            raise AssertionError(f"{name}: auto did not return VDOptimizationResult")

        shorter_initial = [0] * max(0, problem.branch_count - 1)
        optimize(problem, algorithm_id="coordinate", time_budget_sec=1.0, initial_adjustments=shorter_initial)


def run_self_benchmark():
    print("VD optimize self benchmark")
    _assert_self_checks()
    print("correctness: passed")

    problem = _make_synthetic_problem(10, 4, 3, 2, False)
    templates = _distinct_templates(problem, 200)
    all_adjustments = [problem.template_to_all_adjustments(template) for template in templates]

    start = time.perf_counter()
    for adjustments in all_adjustments:
        problem.score_all_adjustments_slow(adjustments)
    slow_seconds = (time.perf_counter() - start) / max(1, len(all_adjustments))

    start = time.perf_counter()
    for adjustments in all_adjustments:
        problem.score_all_adjustments_fast(adjustments)
    fast_seconds = (time.perf_counter() - start) / max(1, len(all_adjustments))

    problem.clear_score_cache()
    start = time.perf_counter()
    exact = _optimize_exact(problem, time_budget_sec=30.0)
    exact_seconds = time.perf_counter() - start

    problem.clear_score_cache()
    start = time.perf_counter()
    branch_bound = _optimize_branch_bound(problem, time_budget_sec=30.0)
    branch_seconds = time.perf_counter() - start

    problem.clear_score_cache()
    start = time.perf_counter()
    beam = _optimize_beam_polish(problem, time_budget_sec=15.0)
    beam_seconds = time.perf_counter() - start

    problem.clear_score_cache()
    start = time.perf_counter()
    coordinate = _optimize_coordinate(problem, time_budget_sec=15.0)
    coordinate_seconds = time.perf_counter() - start

    if branch_bound.is_exact and branch_bound.score != exact.score:
        raise AssertionError("benchmark: branch_bound exact score differs from exhaustive exact")

    print(f"scorer slow/reference: {slow_seconds * 1000:.4f} ms/eval")
    print(f"scorer fast/vectorized: {fast_seconds * 1000:.4f} ms/eval")
    print(f"exact exhaustive: {exact_seconds:.4f} s, score={exact.score}, evals={exact.evaluations}")
    print(f"branch-and-bound: {branch_seconds:.4f} s, score={branch_bound.score}, evals={branch_bound.evaluations}, exact={branch_bound.is_exact}")
    print(f"beam+polish: {beam_seconds:.4f} s, score={beam.score}, evals={beam.evaluations}")
    print(f"coordinate: {coordinate_seconds:.4f} s, score={coordinate.score}, evals={coordinate.evaluations}")
    print(f"cache info: {problem.cache_info()}")


def draw_arrow_line(start, end, color='red', linewidth=1.5, linestyle = '-'):
    # Draw the line
    plt.plot([start[0], end[0]], [start[1], end[1]], color=color, linewidth=linewidth, linestyle=linestyle)

    
def analyze_interlayer_diffs(conductors):
    index_diffs = {}  # To store data, key as (slot_index, 'LxLy'), value as maximum difference
    n = len(conductors)
    for i in range(n):
        for j in range(i + 1, n):
            cond1 = conductors[i]
            cond2 = conductors[j]
            if cond1[0] == cond2[0] and abs(cond1[1] - cond2[1]) == 1:
                key = (cond1[0], cond1[1])
                diff = abs(cond1[4] - cond2[4])
                if key in index_diffs:
                    index_diffs[key] = max(index_diffs[key], diff)
                else:
                    index_diffs[key] = diff
    return index_diffs

def adjust_branch_order(conductors, order_shift, num_cond_per_branch):
    adjusted_conductors = []
    for cond in conductors:
        adjusted_cond = list(cond)  # Create a mutable copy of the tuple
        adjusted_cond[4] = (adjusted_cond[4] + order_shift) % num_cond_per_branch
        adjusted_conductors.append(tuple(adjusted_cond))
    return adjusted_conductors

def find_optimal_shift(Cond_info):
    num_cond_per_branch = max([cond[4] for cond in Cond_info]) + 1
    all_phases = set([cond[2] for cond in Cond_info])
    min_max_diff = float('inf')
    optimal_shift = 0

    for order_shift in range(num_cond_per_branch):
        all_diffs = {}
        for phase in all_phases:
            phase_conds = co.find_phase_conductors(phase, Cond_info)
            adjusted_conds = adjust_branch_order(phase_conds, order_shift, num_cond_per_branch)
            phase_diffs = analyze_interlayer_diffs(adjusted_conds)

            for key, diff in phase_diffs.items():
                if key in all_diffs:
                    all_diffs[key] = max(all_diffs[key], diff)
                else:
                    all_diffs[key] = diff

        current_max_diff = max(all_diffs.values()) if all_diffs else 0
        if current_max_diff < min_max_diff:
            min_max_diff = current_max_diff
            optimal_shift = order_shift

    return optimal_shift, min_max_diff

def prepare_data(all_diffs,Winding_Para):
    # 初始化矩阵，行数为层间索引数，列数为槽数
    # 层间索引由 L1L2, L2L3, L3L4 形式给出，假设层数为4，则有3个层间索引
    matrix = np.zeros((Winding_Para.num_layers - 1, Winding_Para.num_slots))
    # 处理所有键值对
    for key, values in all_diffs.items():
        slot, layer0 = key
        # 对于每个层间组合，在对应的槽位填入最大差值
        matrix[layer0, int(slot)] = values if values else 0
    return matrix

def plot_cond_index_difference_map(Cond_info, max_branch_order, Winding_Para):
    all_diffs = {}
    for phase in range(Winding_Para.num_phases):
        phase_conds = co.find_phase_conductors(phase, Cond_info)
        phase_diffs = analyze_interlayer_diffs(phase_conds)
        for key, diffs in phase_diffs.items():
            if key in all_diffs:
                all_diffs[key].extend(diffs)
            else:
                all_diffs[key] = diffs
    matrix = prepare_data(all_diffs,Winding_Para)
    fig_weight = int(Winding_Para.num_slots / 3)
    fig_height = int(Winding_Para.num_layers / 2)
    plt.figure(figsize=(fig_weight, fig_height), dpi=200)  # 增加dpi参数可以提高图形的分辨率
    im = plt.imshow(matrix, cmap='plasma', aspect='auto', vmin=0, vmax=max_branch_order + 1)
    plt.colorbar(im, label='Index Difference')
    plt.title('Index Differences per Slot and Layer Combination')
    plt.xlabel('Slot')
    plt.ylabel('InterLayer Index')
    plt.xticks(np.arange(0, Winding_Para.num_slots, 6), [f'{i+1}' for i in range(0, Winding_Para.num_slots, 6)])
    plt.yticks(np.arange(Winding_Para.num_layers - 1), [f'L{i+1}L{i+2}' for i in range(Winding_Para.num_layers - 1)])
    for (j, i), label in np.ndenumerate(matrix):
        plt.text(i, j, int(label), ha='center', va='center', color='white', fontsize=9)
    plt.show()
    
def update_cond_info_with_optimal_shift(Cond_info, optimal_shift):
    num_cond_per_branch = max([cond[4] for cond in Cond_info]) + 1
    Cond_info_new = []
    for cond in Cond_info:
        # Destructure the tuple for clarity
        slot, layer, phase, branch, branch_order = cond[0],cond[1],cond[2],cond[3],cond[4]
        # Calculate the new branch order and wrap it using modulo operation
        new_branch_order = (branch_order + optimal_shift) % num_cond_per_branch
        # Create a new tuple with the updated branch order and add it to the new list
        Cond_info_new.append((slot, layer, phase, branch, new_branch_order))
    return Cond_info_new

def plot_cond_index_map(Cond_info,Winding_Para):
    all_diffs = {}
    for phase in range(Winding_Para.num_phases):
        phase_conds = co.find_phase_conductors(phase, Cond_info)
        phase_diffs = analyze_interlayer_diffs(phase_conds)
        for key, diffs in phase_diffs.items():
            if key in all_diffs:
                all_diffs[key].extend(diffs)
            else:
                all_diffs[key] = diffs
    data_matrix = np.zeros((Winding_Para.num_layers, Winding_Para.num_slots)) * np.nan
    branch_matrix = np.full((Winding_Para.num_layers, Winding_Para.num_slots), np.nan)
    # Fill the dat to matrix 
    for cond in Cond_info:
        slot_index,layer_index, phase_index, branch_index, cond_index = cond[0],cond[1],cond[2],cond[3],cond[4]
        if phase_index in [0,1,2]:
            data_matrix[layer_index, slot_index] = cond_index
            branch_matrix[layer_index, slot_index] = branch_index
    # plot the heat map
    fig_weight = int(Winding_Para.num_slots / 4)
    fig_height = int(Winding_Para.num_layers / 2)
    plt.figure(figsize=(fig_weight, fig_height), dpi=200)  # 增加dpi参数可以提高图形的分辨率
    im = plt.imshow(branch_matrix, cmap='viridis', aspect='auto')
    # cbar = plt.colorbar(im)
    # cbar.set_label('Branch Index', fontsize=9)
    # cbar.ax.tick_params(labelsize=9)  # Set the fontsize for the colorbar ticks
    plt.title('Cond Index and Connection',fontsize=9)
    plt.xlabel('Slot Index')
    plt.ylabel('Layer Index')
    plt.xticks(np.arange(0, Winding_Para.num_slots, 6), [f'{i+1}' for i in range(0, Winding_Para.num_slots, 6)],fontsize=8)
    plt.yticks(range(Winding_Para.num_layers), [f'Layer {i+1}' for i in range(Winding_Para.num_layers)],fontsize=8)
    # Add cond_index as text in each cell
    for (j, i), label in np.ndenumerate(data_matrix):
        if not np.isnan(label):
            plt.text(i, j, int(label+1), ha='center', va='center', color='white', fontsize=8)
    draw_line_in_cond_index_map(Cond_info,data_matrix,Winding_Para)
    plt.show()
    
def draw_line_in_cond_index_map(Cond_info,data_matrix,Winding_Para):   
    # Find the coordinates for all cond_index within branch index 0
    branch_0_coords = []
    for cond in Cond_info:
        slot_index, layer_index, phase_index, branch_index, cond_index = cond[0], cond[1], cond[2], cond[3], cond[4]
        if branch_index == 0:
            branch_0_coords.append((slot_index, layer_index))

    # Sort the coordinates by cond_index (assume cond_index represents the order)
    branch_0_coords.sort(key=lambda x: data_matrix[x[1], x[0]])  ###slot_index, layer_index
    print (branch_0_coords)
    start = branch_0_coords[0]
    if start[1] == Winding_Para.num_layers-1:
        inlet_length = -0.8
    elif start[1] == 0:
        inlet_length = 0.8
    else: 
        inlet_length = 0.8 + start[1]
    inlet_start = [start[0],start[1]-inlet_length]
    inlet_end = [start[0],start[1]]
    draw_arrow_line(inlet_start, inlet_end, color='blue', linewidth=2)
    
    end = branch_0_coords[-1]
    if end[1] == Winding_Para.num_layers-1:
        outlet_length = -0.8
    elif end[1] == 0:
        outlet_length = 0.8
    else:
        outlet_length = 0.8 + end[1]
    inlet_start = [end[0],end[1]-outlet_length]
    inlet_end = [end[0],end[1]]
    draw_arrow_line(inlet_start, inlet_end, color='green', linewidth=2)
    # Draw lines connecting the conductors in branch 0 in order
    for i in range(len(branch_0_coords) - 1):
        start = list(branch_0_coords[i])
        end = list(branch_0_coords[i + 1])
        ratio_layer_end = min(abs(start[0]+0.5-Winding_Para.num_slots),start[0]+0.5)
        ratio_layer_start = min(abs(end[0]+0.5-Winding_Para.num_slots),end[0]+0.5)
        
        if i % 2 == 0:
            color = 'black'
            linestyle = '--'
            linewidth = 1 
        else:
            color = 'red'
            linestyle = '-'
            linewidth = 1.5
        if abs(end[0] - start[0]) > Winding_Para.num_slots / 2:
            if end[0] > start[0]:
                slot_shift = start[0] - end[0] + Winding_Para.num_slots
                mid_layer = ratio_layer_start/slot_shift * start[1] + ratio_layer_end/slot_shift * end[1]
                mid_end = [Winding_Para.num_slots-0.5, mid_layer]
                mid_start = [-0.5, mid_layer]
                draw_arrow_line(end, mid_end, color=color, linewidth=linewidth, linestyle=linestyle)
                draw_arrow_line(mid_start, start, color=color, linewidth=linewidth, linestyle=linestyle)
            else:
                slot_shift = - start[0] + end[0] + Winding_Para.num_slots
                mid_layer = ratio_layer_start/slot_shift * start[1] + ratio_layer_end/slot_shift * end[1]
                mid_end = [Winding_Para.num_slots-0.5, mid_layer]
                mid_start = [-0.5, mid_layer]
                draw_arrow_line(mid_start, end, color=color, linewidth=linewidth, linestyle=linestyle)
                draw_arrow_line(start, mid_end, color=color, linewidth=linewidth, linestyle=linestyle)
        else:
            draw_arrow_line(start, end, color=color, linewidth=linewidth, linestyle=linestyle)
            
def plot_optimized_cond_index_difference_map(Cond_info,Winding_Para): 
    num_cond_per_branch = max([cond[4] for cond in Cond_info]) + 1
    # Assuming you know num_cond_per_branch or calculate it
    optimal_shift, min_max_diff = find_optimal_shift(Cond_info)
    print(f"The optimal order shift is {optimal_shift} with a minimized mid (max_index_difference) of {min_max_diff}")
    # Use the optimal shift to update the Cond_info
    Cond_info_new = update_cond_info_with_optimal_shift(Cond_info, optimal_shift)
    plot_cond_index_map(Cond_info_new,Winding_Para)
    plot_cond_index_difference_map(Cond_info, num_cond_per_branch, Winding_Para)
    plot_cond_index_difference_map(Cond_info_new, num_cond_per_branch, Winding_Para)


if __name__ == "__main__":
    if "--benchmark" in sys.argv or len(sys.argv) == 1:
        run_self_benchmark()
