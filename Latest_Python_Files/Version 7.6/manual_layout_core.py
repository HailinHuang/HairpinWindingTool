# -*- coding: utf-8 -*-
"""Core state and rules for the standalone manual layout tool."""

from __future__ import annotations

import copy
import csv
import json
import math
import os
from collections import namedtuple
from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

os.environ.setdefault("MPLCONFIGDIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".matplotlib"))

import get_winding_pattern as gw


ConductorId = Tuple[int, int, int]
CondInfo = Tuple[int, int, int, int, int, int, int]


@dataclass
class ManualLayoutParams:
    q: float = 2.0
    num_phases: int = 3
    num_poles: int = 4
    num_layers: int = 4
    ab: int = 2
    phase_shift: int = 1
    psl: int = 1
    phase_shift_pattern: str = "Normal"
    radial_shift: int = 0
    inlet_from_weld_side: int = 0
    full_symmetry: bool = False
    first_last_connection: bool = True
    pattern_name: str = "Manual"
    tp_type: str = "Regular"
    tp_times: int = 0
    tp_interval: int = 0
    uni_tp: int = 0
    pltp_fl: int = 0
    pltp_ll: int = 0
    jltp: int = 0
    jld: int = 1
    output_path: str = "manual_layout_output"


class ManualLayoutCore:
    def __init__(self, params: Optional[ManualLayoutParams] = None, log=None):
        self.params = params or ManualLayoutParams()
        self.log = log or (lambda message: None)
        self.reset_state()

    @property
    def num_slots(self) -> int:
        return int(round(self.params.q * self.params.num_phases * self.params.num_poles))

    @property
    def q_count(self) -> int:
        return max(1, int(math.ceil(self.params.q)))

    @property
    def group_size(self) -> int:
        return int(self.num_slots * self.params.num_layers / self.params.ab / self.params.num_phases)

    def reset_state(self):
        self.slots = np.zeros((self.params.num_layers, max(self.num_slots, 1)), dtype=int)
        self.cond_info: List[CondInfo] = []
        self.cond_index: Dict[Tuple[int, int], int] = {}
        self.current_number = 1
        self.current_position: Optional[Tuple[int, int]] = None
        self.branch_index = 0
        self.remaining_in_branch = 0
        self.positions: List[Tuple[int, int]] = []
        self.history = []
        self.branch_info: List[Dict[str, Dict[str, int]]] = []
        self.remains: List[int] = []
        self.winding_para = None

    def validate_params(self):
        p = self.params
        if p.num_phases <= 0 or p.num_poles <= 0 or p.num_layers <= 0 or p.ab <= 0:
            raise ValueError("phases, poles, layers, and branches must be positive.")
        if p.q <= 0:
            raise ValueError("q must be positive.")
        raw_slots = p.q * p.num_phases * p.num_poles
        if abs(raw_slots - round(raw_slots)) > 1e-9:
            raise ValueError("q * phases * poles must produce an integer slot count.")
        if not (float(p.q).is_integer() or float(2 * p.q).is_integer()):
            raise ValueError("v1 supports integer q and half-slot q only.")
        total_per_phase = self.num_slots * p.num_layers / p.num_phases
        if abs(total_per_phase / p.ab - round(total_per_phase / p.ab)) > 1e-9:
            raise ValueError("slot/layer count is not divisible by phases and branches.")
        if p.full_symmetry and p.num_poles % p.ab != 0:
            raise ValueError("full symmetry requires number of poles divisible by branches.")
        if str(p.pattern_name).strip().lower() == "manual":
            p.pattern_name = "Manual"
        else:
            try:
                pattern_id = gw.normalize_pattern_name(p.pattern_name, allow_extra=False)
                if not gw.is_pattern_implemented(pattern_id):
                    raise ValueError(f"{gw.get_pattern_label(pattern_id)} is listed in the document but is not implemented yet.")
                if pattern_id in ("CP", "ZPP", "TLP", "LPP") and p.num_layers % 2 != 0:
                    raise ValueError(f"{gw.get_pattern_label(pattern_id)} requires an even layer count.")
                if pattern_id in ("ZPP", "LPP") and not p.inlet_from_weld_side:
                    raise ValueError(f"{gw.get_pattern_label(pattern_id)} requires inlet_from_weld_side=1.")
                p.pattern_name = gw.get_pattern_label(pattern_id)
            except ValueError as exc:
                raise ValueError(str(exc)) from exc
        if p.tp_type not in ["Regular", "Times", "Interval", "Optimize"]:
            raise ValueError("unsupported transposition type.")

    def start(self):
        self.validate_params()
        p = self.params
        self.reset_state()
        WindingPara = namedtuple("WindingPara", ["q", "num_poles", "num_layers", "num_phases", "num_slots", "ab"])
        q_value = int(p.q) if float(p.q).is_integer() else p.q
        self.winding_para = WindingPara(q_value, p.num_poles, p.num_layers, p.num_phases, self.num_slots, p.ab)
        self.slots = np.zeros((p.num_layers, self.num_slots), dtype=int)
        self.remaining_in_branch = self.group_size
        self.remains = [self.group_size for _ in range(p.ab)]
        self.branch_info = [
            {f"P{phasor + 1} L{layer + 1}": {"count": 0, "left": max(0, int(p.num_poles / p.ab))}
             for phasor in range(self.q_count) for layer in range(p.num_layers)}
            for _ in range(p.ab)
        ]
        self.cond_info = self._initial_cond_info()
        self._rebuild_cond_index()
        self.log(f"Started manual layout: {self.num_slots} slots, {p.num_layers} layers.")

    def _layout_para(self, pattern_name: Optional[str] = None):
        p = self.params
        phase_shift_list = gw.get_phase_shift_list(
            self.winding_para,
            p.phase_shift_pattern,
            p.phase_shift,
            p.psl,
            log=self.log,
        )
        LayoutPara = namedtuple(
            "LayoutPara",
            ["inlet_from_weld_side", "phase_shift_pattern", "phase_shift", "PSL",
             "radial_shift", "Single_Phase_Draw", "CW",
             "in_out_connection", "pattern_name", "phase_shift_list"],
        )
        return LayoutPara(
            p.inlet_from_weld_side,
            p.phase_shift_pattern,
            p.phase_shift,
            p.psl,
            p.radial_shift,
            1,
            0,
            1 if p.first_last_connection else 0,
            pattern_name or p.pattern_name,
            phase_shift_list,
        )

    def _initial_cond_info(self) -> List[CondInfo]:
        cond_info = gw.Winding_Phase_division(self.winding_para, self._layout_para("Manual"), log=self.log)
        if not cond_info:
            raise ValueError("phase division failed for the selected parameters.")
        return [(int(s), int(l), int(ph), -1, -1, 0, int(po)) for s, l, ph, _b, _ci, _pa, po in cond_info]

    def _rebuild_cond_index(self):
        self.cond_index = {(slot, layer): i for i, (slot, layer, *_rest) in enumerate(self.cond_info)}

    def phase_at(self, slot: int, layer: int) -> int:
        idx = self.cond_index.get((slot, layer))
        if idx is None:
            return -1
        return self.cond_info[idx][2]

    def pole_at(self, slot: int, layer: int) -> int:
        idx = self.cond_index.get((slot, layer))
        if idx is None:
            return -1
        return self.cond_info[idx][6]

    def phase_slots(self, layer: int, pole: int, phase: int) -> List[int]:
        slots = [
            slot for slot, cond_layer, cond_phase, _branch, _index, _phasor, cond_pole in self.cond_info
            if cond_layer == layer and cond_phase == phase and cond_pole == pole
        ]
        return sorted(slots)

    def phasor_rank(self, slot: int, layer: int) -> int:
        phase = self.phase_at(slot, layer)
        pole = self.pole_at(slot, layer)
        candidates = self.phase_slots(layer, pole, phase)
        if slot in candidates:
            return candidates.index(slot)
        return 0

    def display_phasor(self, slot: int, layer: int) -> int:
        return self.phasor_rank(slot, layer)

    def branch_status_rows(self):
        return [
            {"branch": i + 1, "left": self.remains[i] if i < len(self.remains) else self.group_size}
            for i in range(self.params.ab)
        ]

    def branch_detail_rows(self):
        rows = []
        for branch_idx, branch in enumerate(self.branch_info):
            for key, value in branch.items():
                rows.append({
                    "branch": branch_idx + 1,
                    "position": key,
                    "count": value.get("count", 0),
                    "left": value.get("left", 0),
                })
        return rows

    def position_branch_info(self, layer: int, slot: int):
        idx = self.cond_index.get((slot, layer))
        if idx is None:
            return None
        _slot, _layer, _phase, branch, cond_index, phasor, _pole = self.cond_info[idx]
        if branch < 0 or cond_index < 0:
            return None
        return {
            "branch": branch % self.params.ab,
            "branch_label": branch % self.params.ab + 1,
            "cond_index": cond_index,
            "phasor": phasor,
        }

    def symmetry_report(self, branch_index: Optional[int] = None):
        if not self.branch_info:
            return "No branch information available."
        branch_indices = [branch_index] if branch_index is not None else list(range(len(self.branch_info)))
        reports = []
        for idx in branch_indices:
            if idx < 0 or idx >= len(self.branch_info):
                continue
            branch = self.branch_info[idx]
            target = self.group_size / max(len(branch), 1)
            deltas = []
            for key in sorted(branch):
                count = branch[key].get("count", 0)
                diff = count - target
                if abs(diff) > 1e-9:
                    if float(diff).is_integer():
                        diff_text = f"{int(diff):+d}"
                    else:
                        diff_text = f"{diff:+.2f}"
                    deltas.append(f"{key.replace(' ', '')} {diff_text}")
            if deltas:
                reports.append(f"Branch {idx + 1}: " + " ".join(deltas))
            else:
                reports.append(f"Branch {idx + 1}: strong symmetry")
        if not reports:
            return "No branch information available."
        if all("strong symmetry" in report for report in reports):
            return "Strong symmetry: " + "; ".join(reports)
        return "Symmetry mismatch: " + "; ".join(reports)

    def can_place(self, layer: int, slot: int, enforce_rules: bool = True) -> Tuple[bool, str]:
        if self.winding_para is None:
            return False, "Start the layout first."
        if not (0 <= layer < self.params.num_layers and 0 <= slot < self.num_slots):
            return False, "Position is outside the grid."
        if self.slots[layer][slot] != 0:
            return False, "Position already filled."
        if self.phase_at(slot, layer) != 0:
            return False, "Manual placement is restricted to phase A positions."
        if enforce_rules and self.current_position is not None:
            valid_positions = self.get_valid_positions(self.current_position)
            if (layer, slot) not in valid_positions:
                return False, "Position does not satisfy current winding rules."
        return True, ""

    def place(self, layer: int, slot: int, enforce_rules: bool = True, report_symmetry: bool = True):
        ok, reason = self.can_place(layer, slot, enforce_rules=enforce_rules)
        if not ok:
            raise ValueError(reason)
        self.history.append(self._snapshot())
        cond_index = self.current_number - 1
        self.positions.append((layer, slot))
        self.slots[layer][slot] = self.current_number
        self.current_position = (layer, slot)
        self._update_cond_info(slot, layer, self.branch_index, cond_index)
        self._update_branch_info(layer, slot, undo=False)
        self.current_number += 1
        self.remaining_in_branch -= 1
        if 0 <= self.branch_index < len(self.remains):
            self.remains[self.branch_index] = self.remaining_in_branch
        completed_branch = self.branch_index if self.remaining_in_branch == 0 else None
        if completed_branch is not None and report_symmetry:
            self.log(self.symmetry_report(completed_branch))
        if self.remaining_in_branch == 0 and self.branch_index < self.params.ab - 1:
            self.branch_index += 1
            self.remaining_in_branch = self.group_size
            self.current_number = 1
        return self.analysis()

    def undo(self):
        if not self.history:
            return False
        self._restore(self.history.pop())
        return True

    def clear(self):
        params = copy.deepcopy(self.params)
        self.params = params
        self.start()

    def _snapshot(self):
        return {
            "slots": self.slots.copy(),
            "cond_info": copy.deepcopy(self.cond_info),
            "current_number": self.current_number,
            "current_position": self.current_position,
            "branch_index": self.branch_index,
            "remaining_in_branch": self.remaining_in_branch,
            "positions": copy.deepcopy(self.positions),
            "branch_info": copy.deepcopy(self.branch_info),
            "remains": copy.deepcopy(self.remains),
        }

    def _restore(self, snapshot):
        self.slots = snapshot["slots"].copy()
        self.cond_info = copy.deepcopy(snapshot["cond_info"])
        self.current_number = snapshot["current_number"]
        self.current_position = snapshot["current_position"]
        self.branch_index = snapshot["branch_index"]
        self.remaining_in_branch = snapshot["remaining_in_branch"]
        self.positions = copy.deepcopy(snapshot["positions"])
        self.branch_info = copy.deepcopy(snapshot["branch_info"])
        self.remains = copy.deepcopy(snapshot["remains"])
        self._rebuild_cond_index()

    def _update_cond_info(self, slot: int, layer: int, branch_id: int, cond_index: int):
        phase = self.phase_at(slot, layer)
        pole = self.pole_at(slot, layer)
        phasor = self.phasor_rank(slot, layer)
        if phase != 0:
            raise ValueError("Only phase A positions can seed a manual conductor.")
        for phase_index in range(self.params.num_phases):
            slots = self.phase_slots(layer, pole, phase_index)
            if not slots:
                continue
            target_slot = slots[min(phasor, len(slots) - 1)]
            idx = self.cond_index[(target_slot, layer)]
            old = self.cond_info[idx]
            global_branch = branch_id + self.params.ab * phase_index
            self.cond_info[idx] = (old[0], old[1], old[2], global_branch, cond_index, phasor, old[6])

    def get_db_conductor_id(self) -> List[List[object]]:
        branches: Dict[int, List[Tuple[int, ConductorId]]] = {}
        for slot, layer, phase, branch, cond_index, phasor, _pole in self.cond_info:
            if branch < 0:
                continue
            branches.setdefault(branch, []).append((cond_index, (slot, layer, phasor)))
        result = []
        for output_branch_id, raw_branch_id in enumerate(sorted(branches), start=1):
            ordered = [cond for _idx, cond in sorted(branches[raw_branch_id], key=lambda item: item[0])]
            result.append([output_branch_id, ordered])
        return result

    def export_csv(self, folder: Optional[str] = None):
        folder = folder or self.params.output_path
        os.makedirs(folder, exist_ok=True)
        for branch_id, conductors in self.get_db_conductor_id():
            matrix = [["" for _ in range(self.num_slots + 1)] for _ in range(self.params.num_layers + 1)]
            for slot in range(1, self.num_slots + 1):
                matrix[0][slot] = str(slot)
            for layer in range(1, self.params.num_layers + 1):
                matrix[layer][0] = str(layer)
            for idx, (slot, layer, _phasor) in enumerate(conductors):
                matrix[layer + 1][slot + 1] = str(idx + 1)
            file_path = os.path.join(folder, f"branch{branch_id}.csv")
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(matrix)
        return folder

    def save_session(self, path: str):
        payload = {
            "params": asdict(self.params),
            "slots": self.slots.tolist(),
            "cond_info": [list(row) for row in self.cond_info],
            "current_number": self.current_number,
            "current_position": self.current_position,
            "branch_index": self.branch_index,
            "remaining_in_branch": self.remaining_in_branch,
            "positions": [list(p) for p in self.positions],
            "branch_info": self.branch_info,
            "remains": self.remains,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def load_session(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        self.params = ManualLayoutParams(**payload["params"])
        self.validate_params()
        self.slots = np.array(payload["slots"], dtype=int)
        self.cond_info = [tuple(map(int, row)) for row in payload["cond_info"]]
        self.current_number = int(payload["current_number"])
        current_position = payload.get("current_position")
        self.current_position = tuple(current_position) if current_position else None
        self.branch_index = int(payload["branch_index"])
        self.remaining_in_branch = int(payload["remaining_in_branch"])
        self.positions = [tuple(p) for p in payload.get("positions", [])]
        self.branch_info = payload.get("branch_info", [])
        self.remains = [int(v) for v in payload.get("remains", [])]
        WindingPara = namedtuple("WindingPara", ["q", "num_poles", "num_layers", "num_phases", "num_slots", "ab"])
        q_value = int(self.params.q) if float(self.params.q).is_integer() else self.params.q
        self.winding_para = WindingPara(q_value, self.params.num_poles, self.params.num_layers, self.params.num_phases, self.num_slots, self.params.ab)
        self.history = []
        self._rebuild_cond_index()

    def analysis(self):
        return self.analyze_database(self.get_db_conductor_id())

    def analyze_database(self, database: Iterable[List[object]]):
        results = []
        all_pin_shapes = {}
        total_slot_distance_all = 0
        conductor_count_all = 0
        for branch_info in database:
            n_branch, group_conductors_id = branch_info
            pin_shapes = {}
            total_slot_distance = 0
            conductor_count = 0
            if not group_conductors_id:
                continue
            pairs = [(group_conductors_id[i], group_conductors_id[i + 1], i) for i in range(len(group_conductors_id) - 1)]
            if self.params.first_last_connection and len(group_conductors_id) > 1:
                pairs.append((group_conductors_id[-1], group_conductors_id[0], len(group_conductors_id) - 1))
            for start, end, i in pairs:
                a, b = sorted([start[1], end[1]])
                y = abs(start[0] - end[0]) % self.num_slots
                y = min(y, self.num_slots - y)
                side = int(1 - self.params.inlet_from_weld_side)
                if i % 2 == side:
                    pin_key = (a, b, y)
                    pin_shapes[pin_key] = pin_shapes.get(pin_key, 0) + 1
                    all_pin_shapes[pin_key] = all_pin_shapes.get(pin_key, 0) + 1
                total_slot_distance += y
                conductor_count += 1
            conductor_info = []
            for phasor_layer in sorted(set((c[2], c[1]) for c in group_conductors_id)):
                num_conductor = len([c for c in group_conductors_id if c[2] == phasor_layer[0] and c[1] == phasor_layer[1]])
                conductor_info.append((phasor_layer[0], phasor_layer[1], num_conductor))
            total_slot_distance_all += total_slot_distance
            conductor_count_all += conductor_count
            average_slot_distance = round(total_slot_distance / conductor_count, 4) if conductor_count > 0 else 0
            results.append({
                "n_branch": n_branch,
                "num_pin_shapes": len(pin_shapes),
                "conductor_info": conductor_info,
                "pin_shapes": pin_shapes,
                "average_slot_distance": average_slot_distance,
                "total_slot_distance": total_slot_distance,
                "total_conductors": conductor_count,
            })
        average_slot_distance_all = round(total_slot_distance_all / conductor_count_all, 4) if conductor_count_all > 0 else 0
        results.append({
            "n_branch": "All",
            "num_pin_shapes": len(all_pin_shapes),
            "conductor_info": [],
            "pin_shapes": all_pin_shapes,
            "average_slot_distance": average_slot_distance_all,
            "total_slot_distance": total_slot_distance_all,
            "total_conductors": conductor_count_all,
        })
        return results

    def pin_shape_rows(self):
        result = self.analysis()[-1]
        rows = []
        for (layer_1, layer_2, pitch), count in sorted(result["pin_shapes"].items(), key=lambda item: item[0]):
            if layer_1 == layer_2:
                pin_type = "Pall"
            elif abs(layer_1 - layer_2) == 1:
                pin_type = "Adj"
            elif abs(layer_1 - layer_2) == self.params.num_layers - 1:
                pin_type = "FL"
            else:
                pin_type = "Other"
            full_pitch = self.params.num_phases * self.params.q
            if abs(pitch - full_pitch) < 1e-9:
                pitch_type = "Full"
            elif pitch < full_pitch:
                pitch_type = "Short"
            else:
                pitch_type = "Long"
            rows.append({
                "L1": layer_1 + 1,
                "L2": layer_2 + 1,
                "Y": pitch,
                "Type": pin_type,
                "Pitch": pitch_type,
                "Num": count,
            })
        return rows

    def _update_branch_info(self, layer: int, slot: int, undo: bool = False):
        if self.branch_index >= len(self.branch_info):
            return
        phasor_index = self.phasor_rank(slot, layer)
        key = f"P{phasor_index + 1} L{layer + 1}"
        if key not in self.branch_info[self.branch_index]:
            self.branch_info[self.branch_index][key] = {"count": 0, "left": max(0, int(self.params.num_poles / self.params.ab))}
        item = self.branch_info[self.branch_index][key]
        if undo:
            item["count"] = max(0, item["count"] - 1)
            item["left"] += 1
        else:
            item["count"] += 1
            item["left"] = max(0, item["left"] - 1)

    def _manufacturing_valid_layers(self, current_position: Tuple[int, int]):
        current_layer, _slot = current_position
        if self.params.first_last_connection:
            next_layers = [current_layer - 1, current_layer, current_layer + 1]
            return list(dict.fromkeys((layer + self.params.num_layers) % self.params.num_layers for layer in next_layers))
        if current_layer == 0:
            next_layers = [current_layer, current_layer + 1]
        elif current_layer == self.params.num_layers - 1:
            next_layers = [current_layer - 1, current_layer]
        else:
            next_layers = [current_layer - 1, current_layer, current_layer + 1]
        return list(dict.fromkeys(next_layers))

    def _winding_theory_valid_positions(self, current_position: Tuple[int, int]):
        current_layer, slot = current_position
        current_pole = self.pole_at(slot, current_layer)
        valid_layers = self._manufacturing_valid_layers(current_position)
        next_poles = [(current_pole + 1) % self.params.num_poles, (current_pole - 1) % self.params.num_poles]
        positions = []
        for pole in next_poles:
            for layer in valid_layers:
                for candidate_slot in self.phase_slots(layer, pole, 0):
                    positions.append((layer, candidate_slot))
        return list(dict.fromkeys(positions))

    def get_valid_positions(self, current_position: Optional[Tuple[int, int]] = None):
        if self.winding_para is None:
            return []
        if current_position is None or (self.branch_index > 0 and self.current_number == 1):
            positions = [
                (layer, slot)
                for slot, layer, phase, _branch, _index, _phasor, _pole in self.cond_info
                if phase == 0 and self.slots[layer][slot] == 0
            ]
            return positions
        candidates = self._winding_theory_valid_positions(current_position)
        valid = []
        for layer, slot in candidates:
            if self.slots[layer][slot] != 0:
                continue
            if self.params.full_symmetry and self.branch_index < len(self.branch_info):
                key = f"P{self.phasor_rank(slot, layer) + 1} L{layer + 1}"
                if self.branch_info[self.branch_index].get(key, {"left": 1})["left"] <= 0:
                    continue
            valid.append((layer, slot))
        return valid

    def classify_valid_position(self, layer: int, slot: int) -> str:
        if self.slots[layer][slot] != 0:
            return "filled"
        valid_positions = set(self.get_valid_positions(self.current_position))
        if (layer, slot) not in valid_positions:
            return "invalid"
        next_valid = set(self.get_valid_positions((layer, slot)))
        if not next_valid:
            return "dead"
        has_continuation = False
        for next_position in next_valid:
            second_valid = set(self.get_valid_positions(next_position))
            second_valid.discard((layer, slot))
            if second_valid:
                has_continuation = True
                break
        return "valid" if has_continuation else "risk"

    def auto_fill_pattern(self):
        if str(self.params.pattern_name).strip().lower() == "manual":
            raise ValueError("Select a winding pattern before auto filling.")
        self.start()
        p = self.params
        if p.tp_type == "Times" and p.tp_times <= 0:
            raise ValueError("Times transposition requires Transposition times > 0.")
        if p.tp_type == "Interval" and p.tp_interval <= 0:
            raise ValueError("Interval transposition requires Transposition interval > 0.")
        TPInfo = namedtuple("TP_info", ["tp_type", "tp_interval", "tp_times", "uni_tp", "pltp_fl", "pltp_ll", "jltp", "jld", "tp_start_index"])
        tp_type = p.tp_type if p.tp_type in ("Regular", "Times", "Interval") else "Regular"
        tp_info = TPInfo(
            tp_type,
            p.tp_interval,
            p.tp_times,
            p.uni_tp,
            p.pltp_fl,
            p.pltp_ll,
            abs(p.jltp),
            -1 if p.jltp < 0 else p.jld,
            0,
        )
        phase_a = gw.get_phaseA_winding_layout(p.pattern_name, tp_info, self.winding_para, self._layout_para(p.pattern_name))
        filled = 0
        for _branch, conductors in phase_a:
            for slot, layer, _phasor in conductors:
                if layer < self.params.num_layers and slot < self.num_slots and self.slots[layer][slot] == 0:
                    try:
                        self.place(layer, slot, enforce_rules=False, report_symmetry=False)
                        filled += 1
                    except ValueError:
                        continue
        self.log(f"Auto-filled {filled} phase-A conductors from {p.pattern_name}.")
        self.log(self.symmetry_report())
        return filled
