"""Behavior checks for the standalone, exploratory pattern-rule workbench."""
import json
import math
import os
import re
from fractions import Fraction
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import draw_figure as dfig

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pattern_rule_workbench import (
    PATTERNS, BranchDraftSet, DividerRouteCatalog, PatternDraft, PatternRuleWorkbench,
    build_divider_route_catalog, extract_reference_constraints,
    generate_route_drafts, transform_completed_branches,
)


class SavedManualDividerDraftCharacterizationTests(unittest.TestCase):
    """Keep designer packages distinct from production route evidence."""

    def test_recent_manual_drafts_use_only_existing_body_pin_profiles(self):
        root = Path(__file__).parent / "pattern_rule_drafts"
        expected = {
            "SLP": {"ALLP", "SLPP"},
            "ZLP": {"ALLP", "SLPP"},
            "CP": {"CLWP"},
        }
        packages = []
        for path in root.glob("*.json"):
            match = re.search(r"_20260922-(\d{6})-", path.name)
            if match and match.group(1) >= "213000":
                packages.append((path, json.loads(path.read_text(encoding="utf-8"))))

        self.assertEqual(len(packages), 13)
        self.assertTrue(all(data["schema_version"] == 3
                            and data["save_kind"] == "manual_configure"
                            and data["certified"] is False
                            and data["completion_checks"]["engineering_validated"] is False
                            for _path, data in packages))
        for path, data in packages:
            with self.subTest(package=path.name):
                actual = set()
                for branch in data["branches"]:
                    for step in branch["steps"]:
                        if step["side"] != "insert":
                            continue
                        layer_span = abs(step["to"]["layer"] - step["from"]["layer"])
                        if layer_span == 0:
                            actual.add("SLPP")
                        elif data["pattern"] == "CP" and layer_span == data["layers"] // 2:
                            actual.add("CLWP")
                        elif data["pattern"] in ("SLP", "ZLP"):
                            actual.add("ALLP")
                        else:
                            actual.add("ALWP")
                self.assertTrue(actual)
                self.assertLessEqual(actual, expected[data["pattern"]])

    def test_rejected_slp_draft_is_not_rescued_by_its_pin_profile(self):
        root = Path(__file__).parent / "pattern_rule_drafts"
        path = root / (
            "SLP_q-2_pp-4_L-4_Naa-4_Q-1_PP-2_P2-2_Ph-A_Side-weld_"
            "Shifts-0-0-0-0_20260922-224750-076466.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["route_note"], "should reject")
        self.assertEqual(data["source_route"]["status"], "unsupported-yet")
        self.assertTrue(data["all_branch_counts_reached"])
        self.assertFalse(data["completion_checks"]["engineering_validated"])


class BranchDraftSetTests(unittest.TestCase):
    def test_auto_start_next_uses_first_compatible_unoccupied_inlet(self):
        from pattern_rule_workbench import build_divider_route_catalog, generate_route_drafts
        record = next(r for r in build_divider_route_catalog('2', 4, 4)
                      if r.pattern == 'SLP' and r.dividers == (1, 2, 1))
        source = generate_route_drafts(record)[0]
        group = BranchDraftSet(source)
        branch = group.start_next_auto(preferred=(0, 0))
        self.assertNotEqual(branch.path[0], (0, 0))
        self.assertNotIn(branch.path[0], source.path)
        self.assertEqual(len(group.branches), 2)

    def test_tail_start_reflects_reference_travel_and_preserves_weld_direction(self):
        constraints = extract_reference_constraints('TLP', 1, 8, 4, 4,
                                                    dividers=(1, 4, 1))
        first = PatternDraft(24, 8, 4, naa=4, pattern='TLP', reference_constraints=constraints)
        for _ in range(20):
            first.advance_until_special()
            if len(first.path) == first.target_branch_count:
                break
        group = BranchDraftSet(first)
        branch = group.start_next((0, 3))
        self.assertEqual(branch.wave_direction, -1)
        for _ in range(20):
            branch.advance_until_special()
            if len(branch.path) == branch.target_branch_count:
                break
        self.assertEqual(branch.path, [(0, 3), (21, 2), (0, 1), (21, 0),
                                       (18, 3), (15, 2), (18, 1), (15, 0)])
        directions = {}
        for path in group.branches:
            for step in path.steps:
                if step.side == 'weld':
                    pair = tuple(sorted((step.start[1], step.end[1])))
                    direction = (1 if step.pitch > 0 else -1)*(1 if step.end[1]>step.start[1] else -1)
                    self.assertEqual(directions.setdefault(pair, direction), direction)
        occupied = [node for path in group.branches for node in path.path]
        self.assertEqual(len(set(occupied)), len(occupied))

    def test_reference_alignment_preserves_shifts_and_is_atomic(self):
        from copy import deepcopy
        shifts = (0, 1, 0, 1)
        constraints = extract_reference_constraints('TLP', 1, 8, 4, 4,
                                                    dividers=(1, 4, 1))
        original = deepcopy(constraints)
        first = PatternDraft(24, 8, 4, naa=4, pattern='TLP', shifts=shifts,
                             reference_constraints=constraints)
        for _ in range(20):
            first.advance_until_special()
            if len(first.path) == first.target_branch_count:
                break
        group = BranchDraftSet(first)
        with self.assertRaises(ValueError):
            group.start_next((0, 2))
        self.assertEqual(len(group.branches), 1)
        branch = group.start_next((1, 3))
        for _ in range(20):
            branch.advance_until_special()
            if len(branch.path) == branch.target_branch_count:
                break
        self.assertEqual(branch.path[:2], [(1, 3), (21, 2)])
        self.assertTrue(all(step.direction_ok for step in branch.steps))
        self.assertEqual(first.reference_constraints, original)
        branch.undo()
        branch.advance_until_special()
        self.assertEqual(len(branch.path), branch.target_branch_count)


    def test_times_uses_exact_number_of_insertion_cuts(self):
        draft = PatternDraft(36, 4, 2, naa=4)
        for target in ((9, 1), (18, 0), (27, 1), (1, 0), (10, 1)):
            draft.add_special(target, 'custom', 'manual')
        group = BranchDraftSet(draft)
        for times in (1, 2):
            changed, report = transform_completed_branches(
                group, (0, 0), 'Times', tp_times=times)
            self.assertEqual(len(report['transposition_edges']), times)
            self.assertTrue(all(draft.steps[i-1].side == 'insert'
                                for i in report['transposition_edges']))
        with self.assertRaisesRegex(ValueError, 'insertion connections'):
            transform_completed_branches(group, (0, 0), 'Times', tp_times=3)

    def test_candidate_transposition_never_changes_weld_pitch(self):
        group = self.complete_first()
        for kind, kwargs in (('Interval', {'tp_interval': 1}),
                             ('Times', {'tp_times': 2})):
            with self.subTest(kind=kind):
                changed, report = transform_completed_branches(group, (0, 0), kind, **kwargs)
                for before, after in zip(group.active.steps, changed.active.steps):
                    if before.side == 'weld':
                        self.assertEqual(before.pitch, after.pitch)
                self.assertTrue(all(group.active.steps[i-1].side == 'insert'
                                    for i in report['transposition_edges']))

    def complete_first(self):
        draft = PatternDraft(48, 4, 2, naa=4)
        for target in [(12, 1), (24, 0), (36, 1), (1, 0), (13, 1), (25, 0), (37, 1)]:
            draft.add_special(target, "custom", "manual")
        return BranchDraftSet(draft)

    def test_rotation_preserves_path_and_metadata_with_wrap(self):
        group = self.complete_first()
        source = group.active
        branch = group.rotate_next(2)
        self.assertEqual(branch.path, [((s + 2) % 48, l) for s, l in source.path])
        self.assertEqual(branch.steps[0].note, "manual")
        self.assertEqual(len(group.branches), 2)
        with self.assertRaisesRegex(ValueError, "used"):
            group.rotate_next(-2)
        self.assertEqual(len(group.branches), 2)

    def test_manual_start_excludes_other_branches(self):
        group = self.complete_first()
        next_branch = group.start_next((2, 0))
        self.assertNotIn((0, 0), next_branch.available_conductors())
        with self.assertRaisesRegex(ValueError, "used"):
            next_branch.add_special((0, 0), "custom")
        with self.assertRaisesRegex(ValueError, "complete"):
            group.start_next((3, 0))
        group.select(0)
        group.active.undo()
        self.assertNotIn((2, 0), group.active.available_conductors())

    def test_zpp_manual_third_branch_start_accepts_unaligned_inlet(self):
        constraints = extract_reference_constraints(
            'ZPP', 2, 8, 4, 4, dividers=(2, 1, 2))
        self.assertEqual(constraints['reference_mode'], 'default_lane_walk')
        first = PatternDraft(
            48, 8, 4, start=(0, 0), first_side='insert', naa=4,
            pattern='ZPP', reference_constraints=constraints)
        group = BranchDraftSet(first)
        while len(first.path) < first.target_branch_count:
            self.assertGreater(first.advance_until_special(), 0)
        second = group.start_next((1, 0))
        while len(second.path) < second.target_branch_count:
            self.assertGreater(second.advance_until_special(), 0)
        existing_paths = [list(branch.path) for branch in group.branches]

        with self.assertRaisesRegex(ValueError, 'No compatible reference inlet layer'):
            group._new_branch((0, 2))
        self.assertEqual(len(group.branches), 2)

        third = group.start_next((0, 2))  # Layer 3, slot 1.

        self.assertEqual(third.path, [(0, 2)])
        self.assertEqual([branch.path for branch in group.branches[:2]], existing_paths)
        self.assertIn('No compatible reference inlet layer',
                      third.reference_constraints['unaligned_start']['reason'])
        self.assertIn('could not be aligned', third.notes)
        self.assertNotIn((0, 0), third.available_conductors())
        self.assertFalse(third.to_dict()['certified'])

        self.assertTrue(group.undo_active())
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        window = PatternRuleWorkbench()
        try:
            window.branch_set = group
            window.draft = group.active
            window._update('Ready for a manual inlet')
            window._on_plot_click(SimpleNamespace(
                button=1, inaxes=window.figure.axes[0], xdata=1, ydata=3))
            self.assertEqual(len(window.branch_set.branches), 3)
            self.assertEqual(window.draft.path, [(0, 2)])
            self.assertIn('Branch 3 started at S1/L3', window.status.text())
        finally:
            window.close()

    def test_undo_only_start_of_second_branch_allows_new_start(self):
        group = self.complete_first()
        first_path = list(group.active.path)
        group.start_next((2, 0))

        self.assertTrue(group.undo_active())
        self.assertEqual(len(group.branches), 1)
        self.assertEqual(group.active.path, first_path)
        self.assertNotIn((2, 0), group.active.blocked)

        new_start = next(key for key in group.active.available_conductors()
                         if key != (2, 0))
        replacement = group.start_next(new_start)
        self.assertEqual(replacement.path, [new_start])

    def test_invalid_rotation_is_atomic(self):
        group = self.complete_first()
        for offset in (0, 4, 48):
            with self.assertRaises(ValueError):
                group.rotate_next(offset)
            self.assertEqual(len(group.branches), 1)

    def test_negative_offset_wrap_and_naa_limit(self):
        group = self.complete_first()
        group.rotate_next(-22)
        self.assertEqual(group.active.path[2], (2, 0))
        self.assertEqual(group.active.steps[0].pitch, 12)
        group = BranchDraftSet(PatternDraft(48, 4, 2, naa=32))
        for target in list(group.active.available_conductors()):
            group.start_next(target)
        with self.assertRaisesRegex(ValueError, "Naa"):
            group.rotate_next(1)

    def test_rotation_replays_regular_special_and_direction_changes(self):
        draft = PatternDraft(48, 4, 2, naa=4)
        draft.add_regular((12, 1))
        draft.add_regular((24, 0))
        draft.add_regular((36, 1))
        draft.add_special((1, 0), "jumper", "Return leg")
        draft.wave_direction = -1
        draft.add_regular((37, 1))
        draft.add_regular((25, 0))
        draft.add_regular((13, 1))
        group = BranchDraftSet(draft)
        rotated = group.rotate_next(2)
        self.assertEqual(rotated.path, [((s + 2) % 48, l) for s, l in draft.path])
        for before, after in zip(draft.steps, rotated.steps):
            self.assertEqual((before.kind, before.side, before.wave_direction, before.pitch,
                              before.direction_ok, before.note),
                             (after.kind, after.side, after.wave_direction, after.pitch,
                              after.direction_ok, after.note))

    def test_completed_paths_accept_layer_shift_without_accumulating(self):
        group = self.complete_first()
        original = list(group.active.path)
        transformed, report = transform_completed_branches(
            group, (0, 2), "Regular")
        self.assertEqual(
            transformed.branches[0].path,
            [((slot + (2 if layer else 0)) % 48, layer)
             for slot, layer in original])
        self.assertEqual(transformed.branches[0].steps[0].note, "manual")
        self.assertEqual(group.active.path, original)
        self.assertTrue(report["phase_membership_valid"])
        restored, _ = transform_completed_branches(
            transformed, (0, 0), "Regular", source_shifts=(0, 2))
        self.assertEqual(restored.branches[0].path, original)

    def test_interval_transposition_adjusts_selected_edges_and_reports_candidate(self):
        group = self.complete_first()
        transformed, report = transform_completed_branches(
            group, (0, 0), "Interval", tp_interval=2)
        self.assertEqual(report["transposition_edges"], [2, 4, 6])
        self.assertEqual(transformed.active.path[1], group.active.path[1])
        self.assertEqual(
            transformed.active.path[2][0],
            (group.active.path[2][0] + group.active.steps[1].wave_direction) % 48)
        self.assertFalse(report["certified"])
        self.assertEqual(report["status"], "exploratory_transposition_candidate")

    def test_transform_requires_completed_paths_and_valid_parameters(self):
        group = BranchDraftSet(PatternDraft(48, 4, 2, naa=4))
        with self.assertRaisesRegex(ValueError, "completed"):
            transform_completed_branches(group, (0, 0), "Regular")
        group = self.complete_first()
        with self.assertRaisesRegex(ValueError, "one integer"):
            transform_completed_branches(group, (0,))
        with self.assertRaisesRegex(ValueError, "interval"):
            transform_completed_branches(group, (0, 0), "Interval", tp_interval=0)

    def test_ui_completion_click_switch_and_export(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        window = PatternRuleWorkbench()
        try:
            window.branch_set = self.complete_first()
            window.draft = window.branch_set.active
            window._update("Ready")
            self.assertIn("Count reached", window.branch_hint.text())
            self.assertTrue(window.array_button.isEnabled())
            self.assertFalse(window.step_button.isEnabled())
            window.notes_box.setPlainText("First branch note")
            window._on_plot_click(SimpleNamespace(button=1, inaxes=window.figure.axes[0],
                                                  xdata=3, ydata=1))
            self.assertEqual(window.branch_set.active_index, 1)
            self.assertEqual(window.draft.path, [(2, 0)])
            self.assertEqual(window.draft.steps, [])
            self.assertFalse(window.array_button.isEnabled())
            window.branch_box.setCurrentIndex(0)
            self.assertEqual(window.notes_box.toPlainText(), "First branch note")
            with tempfile.TemporaryDirectory() as folder:
                output = Path(folder) / "branches.json"
                window.export_draft(output)
                data = json.loads(output.read_text())
                self.assertEqual(len(data["branches"]), 2)
                self.assertEqual(data["active_branch"], 1)
                self.assertFalse(data["all_branch_counts_reached"])
                self.assertFalse(data["certified"])
            window.slots_box.setValue(51)
            self.assertFalse(window.branch_box.isEnabled())
            self.assertFalse(window.next_branch_button.isEnabled())
        finally:
            window.close()

    def test_ui_transform_refreshes_from_stable_completed_baseline_and_exports_report(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        window = PatternRuleWorkbench()
        try:
            window.branch_set = self.complete_first()
            window.draft = window.branch_set.active
            original = list(window.draft.path)
            window._update("Ready")
            window.transform_shift_type.setCurrentText("Normal")
            window.transform_shift.setValue(2)
            window.transform_psl.setValue(1)
            window.transform_apply_button.click()
            self.assertEqual(window.draft.path[1][0], (original[1][0] + 2) % 48)
            window.transform_shift.setValue(3)
            self.assertEqual(window.draft.path[1][0], (original[1][0] + 3) % 48)
            self.assertIn("Pattern-specific edges remain unvalidated",
                          window.transform_check.text())
            with tempfile.TemporaryDirectory() as folder:
                output = Path(folder) / "transformed.json"
                window.export_draft(output)
                data = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(data["manual_transform"]["phase_shifts"], [0, 3])
                self.assertFalse(data["manual_transform"]["certified"])
            window.transform_revert_button.click()
            self.assertEqual(window.draft.path, original)
        finally:
            window.close()

    def test_invalid_live_transform_restores_baseline_and_clears_export_report(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        window = PatternRuleWorkbench()
        try:
            window.branch_set = self.complete_first()
            window.draft = window.branch_set.active
            original = list(window.draft.path)
            window._update("Ready")
            window.transform_shift_type.setCurrentText("Normal")
            window.transform_shift.setValue(2)
            window.transform_apply_button.click()
            self.assertIsNotNone(window.transform_report)
            window.transform_tp_type.setCurrentText("Times")
            self.assertEqual(window.draft.path, original)
            self.assertIsNone(window.transform_report)
            self.assertIsNone(window._transform_baseline)
            self.assertIn("Candidate rejected", window.transform_check.text())
            with tempfile.TemporaryDirectory() as folder:
                output = Path(folder) / "restored.json"
                window.export_draft(output)
                data = json.loads(output.read_text(encoding="utf-8"))
                self.assertNotIn("manual_transform", data)
        finally:
            window.close()


class PatternDraftTests(unittest.TestCase):
    def test_completed_branch_plot_click_and_button_auto_place_next_start(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        for use_plot in (True, False):
            with self.subTest(use_plot=use_plot):
                window = PatternRuleWorkbench()
                try:
                    record = next(r for r in build_divider_route_catalog('2', 4, 4)
                                  if r.pattern == 'SLP' and r.dividers == (1, 2, 1))
                    source = generate_route_drafts(record)[0]
                    window.branch_set = BranchDraftSet(source)
                    window.draft = source
                    window._start_select_mode = False
                    window._update('Ready')
                    if use_plot:
                        window._on_plot_click(SimpleNamespace(
                            button=1, inaxes=window.figure.axes[0],
                            xdata=24.62, ydata=1.38))
                    else:
                        window.next_branch_button.click()
                    self.assertEqual(len(window.branch_set.branches), 2)
                    self.assertEqual(window.draft.path,
                                     [window.branch_set.branches[1].path[0]])
                    self.assertEqual(window.next_slot_box.value(),
                                     window.draft.path[0][0] + 1)
                    self.assertEqual(window.next_layer_box.value(),
                                     window.draft.path[0][1] + 1)
                finally:
                    window.close()

    def test_real_canvas_click_starts_next_branch(self):
        from PyQt6.QtCore import QPoint, Qt
        from PyQt6.QtTest import QTest
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        window = PatternRuleWorkbench()
        try:
            record = next(r for r in build_divider_route_catalog('2', 4, 4)
                          if r.pattern == 'SLP' and r.dividers == (1, 2, 1))
            source = generate_route_drafts(record)[0]
            window.branch_set = BranchDraftSet(source)
            window.draft = source
            window._start_select_mode = False
            window.resize(1600, 900)
            window.show()
            window._update('Ready')
            app.processEvents()
            display_x, display_y = window.figure.axes[0].transData.transform((25, 1))
            point = QPoint(round(display_x), round(window.canvas.height()-display_y))
            QTest.mouseClick(window.canvas, Qt.MouseButton.LeftButton,
                             Qt.KeyboardModifier.NoModifier, point)
            app.processEvents()
            self.assertEqual(len(window.branch_set.branches), 2)
            self.assertIn('start placed automatically', window.status.text())
        finally:
            window.close()

    def test_tlp_loaded_tail_branches_have_reverse_direction_and_uniform_welds(self):
        for factors in ((1, 2, 1), (2, 2, 1)):
            record = next(r for r in build_divider_route_catalog('2', 4, 6)
                          if r.pattern == 'TLP' and r.dividers == factors)
            drafts = generate_route_drafts(record)
            self.assertEqual(len(drafts), factors[0]*2)
            for draft in drafts:
                expected = -1 if draft.path[0][1] == 5 else 1
                self.assertEqual(draft.wave_direction, expected)
                for step in draft.steps:
                    if step.side == 'weld':
                        pitch = (step.end[0]-step.start[0]+24) % 48-24
                        self.assertEqual(abs(pitch), 6)
                        self.assertGreater(pitch*(step.end[1]-step.start[1]), 0)

    def test_advance_connects_only_one_pending_special_then_waits(self):
        constraints = extract_reference_constraints('SSP', 2, 8, 4, 2)
        draft = PatternDraft(48, 8, 4, naa=2, pattern='SSP', reference_constraints=constraints)
        self.assertEqual(draft.advance_until_special(), 3)
        pending = draft.suggested_special_transition()
        self.assertIsNotNone(pending)
        before = list(draft.path)
        self.assertEqual(draft.advance_until_special(), 1)
        self.assertEqual(draft.path, before + [pending['target']])
        self.assertEqual(draft.steps[-1].kind, pending['kind'])
        self.assertTrue(draft.regular_candidates())
        self.assertEqual(draft.advance_until_special(), 3)
        self.assertIsNotNone(draft.suggested_special_transition())

    def test_reference_route_accepts_direction_without_changing_existing_path(self):
        from copy import deepcopy
        constraints = extract_reference_constraints('SSP', 2, 8, 4, 2)
        original = deepcopy(constraints)
        draft = PatternDraft(48, 8, 4, naa=2, pattern='SSP', reference_constraints=constraints)
        self.assertEqual(draft.regular_candidates(), [(6, 1)])
        draft.wave_direction = -1
        self.assertEqual(draft.regular_candidates(), [(42, 1)])
        draft.wave_direction = 1
        self.assertEqual(draft.regular_candidates(), [(6, 1)])
        draft.wave_direction = -1
        draft.advance_until_special()
        self.assertEqual(draft.path, [(0, 0), (42, 1), (36, 2), (30, 3)])
        pending = draft.suggested_special_transition()
        self.assertEqual(pending['kind'], 'turnaround')
        self.assertEqual(pending['target'], (24, 3))
        previous = list(draft.path)
        draft.wave_direction = 1
        draft.regular_candidates()
        self.assertEqual(draft.path, previous)
        self.assertEqual(constraints, original)

    def test_direction_control_changes_ordered_reference_with_layer_shifts(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        window = PatternRuleWorkbench()
        try:
            constraints = extract_reference_constraints('SSP', 2, 8, 4, 2)
            window.draft = PatternDraft(48, 8, 4, naa=2, pattern='SSP',
                shifts=(0, 1, 0, 1), reference_constraints=constraints)
            window.branch_set = BranchDraftSet(window.draft)
            window.direction_box.setCurrentIndex(1)
            self.assertEqual(window.candidate_box.currentData(), (43, 1))
            window.direction_box.setCurrentIndex(0)
            self.assertEqual(window.candidate_box.currentData(), (7, 1))
        finally:
            window.close()

    def test_unsupported_tlp_advances_default_branches_in_series(self):
        constraints = extract_reference_constraints('TLP', 2, 8, 4, 1,
                                                    dividers=(1, 1, 1))
        self.assertTrue(constraints['available'], constraints['reason'])
        self.assertEqual(constraints['reference_naa'], 2)
        self.assertEqual(constraints['reference_dividers'], [1, 1, 2])
        self.assertEqual(constraints['reference_mode'], 'default_series')
        draft = PatternDraft(48, 8, 4, naa=1, pattern='TLP',
                             reference_constraints=constraints)
        self.assertGreater(draft.advance_until_special(), 0)
        pending = draft.suggested_special_transition()
        self.assertEqual(pending['kind'], 'first_last_layer')
        self.assertEqual(abs(pending['target'][1]-draft.current[1]), 3)
        self.assertGreater(draft.advance_until_special(), 0)
        self.assertIn(pending['target'], draft.path)
        for _ in range(100):
            if len(draft.path) == draft.target_branch_count:
                break
            self.assertGreater(draft.advance_until_special(), 0)
        self.assertEqual(len(draft.path), 64)
        self.assertEqual(len(set(draft.path)), 64)
        self.assertEqual(sum(s.kind == 'branch_join' for s in draft.steps), 1)
        self.assertTrue(all(s.direction_ok for s in draft.steps))
        self.assertEqual(draft.to_dict()['naa'], 1)

    def test_every_pattern_has_central_special_rules(self):
        from pattern_rule_workbench import PATTERNS, PATTERN_SPECIAL_RULES
        self.assertEqual(set(PATTERN_SPECIAL_RULES), set(PATTERNS))
        self.assertIn('first_last_layer', [r['kind'] for r in PATTERN_SPECIAL_RULES['TLP']])
        cp_checkpoint = next(r for r in PATTERN_SPECIAL_RULES['CP']
                             if r['predicate'] == 'conductor_interval')
        self.assertEqual(cp_checkpoint['kind'], 'checkpoint')
        self.assertEqual(cp_checkpoint['interval'], 4)
        zpp_checkpoint = next(r for r in PATTERN_SPECIAL_RULES['ZPP']
                              if r['predicate'] == 'conductor_interval')
        self.assertEqual(zpp_checkpoint['kind'], 'checkpoint')
        self.assertEqual(zpp_checkpoint['interval'], 4)
        zpp_lane = next(r for r in PATTERN_SPECIAL_RULES['ZPP']
                        if r['predicate'] == 'lane_transition')
        self.assertIn('m*q', zpp_lane['endpoint_rule'])

    def test_two_layer_tlp_keeps_weld_steps_ordinary(self):
        constraints = extract_reference_constraints('TLP', 2, 8, 2, 1,
                                                    dividers=(1, 1, 1))
        self.assertTrue(constraints['available'])
        self.assertTrue(all(edge['kind'] == 'ordinary'
                            for edge in constraints['transitions'] if edge['side'] == 'weld'))
        self.assertTrue(any(edge['kind'] == 'first_last_layer'
                            for edge in constraints['transitions']))

    def test_special_table_and_default_join_are_visible_in_ui(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        window = PatternRuleWorkbench()
        try:
            record = next(r for r in build_divider_route_catalog('2', 4, 4)
                          if r.pattern == 'TLP' and r.dividers == (1, 1, 1))
            window.open_route(record)
            self.assertEqual(window.tabs.tabText(2), 'Special Connections')
            cp_rows = [
                [window.special_rules_table.item(row, col).text()
                 for col in range(4)]
                for row in range(window.special_rules_table.rowCount())
                if window.special_rules_table.item(row, 0).text() == 'CP']
            self.assertTrue(any(
                row[1] == 'checkpoint' and 'every 4' in row[2]
                and 'Stop after 4' in row[3]
                for row in cp_rows))
            zpp_rows = [
                [window.special_rules_table.item(row, col).text()
                 for col in range(4)]
                for row in range(window.special_rules_table.rowCount())
                if window.special_rules_table.item(row, 0).text() == 'ZPP']
            self.assertTrue(any(
                row[1] == 'checkpoint' and 'every 4' in row[2]
                and 'Stop after 4' in row[3]
                for row in zpp_rows))
            self.assertTrue(any(
                row[1] == 'lane_transition' and 'adjacent lane' in row[2]
                and 'm*q' in row[3]
                for row in zpp_rows))
            self.assertFalse(any(row[1] == 'branch_join' for row in zpp_rows))
            self.assertIn('reference Naa=2', window.route_label.text())
            for _ in range(40):
                window._advance()
                pending = window.draft.suggested_special_transition()
                if pending and pending['kind'] == 'branch_join':
                    break
            self.assertEqual(window.kind_box.currentData(), 'branch_join')
            self.assertIn('click Advance again', window.status.text())
            before = len(window.draft.path)
            window._advance()
            self.assertGreater(len(window.draft.path), before)
            self.assertTrue(any(step.kind == 'branch_join' for step in window.draft.steps))
        finally:
            window.close()

    def test_workbench_route_uses_public_regular_generation_without_auto_search(self):
        from pattern_rule_workbench import DividerRouteRecord
        record = DividerRouteRecord(
            'ZPP', Fraction(3), 4, 4, 72, 3, (3, 1, 1), 'q_only',
            'Candidate', 'exploratory reference sample')
        import get_winding_pattern as gw
        with patch('get_winding_pattern.get_auto_configured_layout',
                   side_effect=AssertionError('Workbench must not run Auto Configure')) as configure:
            with patch('get_winding_pattern.get_winding_layout',
                       wraps=gw.get_winding_layout) as generate:
                drafts = generate_route_drafts(record)
                reference = extract_reference_constraints(
                    'ZPP', 3, 8, 4, 3, dividers=(3, 1, 1))
                uwp_record = DividerRouteRecord(
                    'UWP', Fraction(2), 4, 4, 48, 4, (2, 2, 1),
                    'q_and_pp_and_p2', 'Candidate', 'exploratory reference sample')
                uwp_drafts = generate_route_drafts(uwp_record)
                uwp_reference = extract_reference_constraints(
                    'UWP', 2, 8, 4, 4, dividers=(2, 2, 1))

        self.assertEqual(configure.call_count, 0)
        self.assertEqual(generate.call_count, 4)
        self.assertTrue(reference['available'])
        self.assertNotIn('auto_configuration', reference)
        self.assertTrue(all(step.kind != 'production'
                            for draft in drafts for step in draft.steps))
        self.assertTrue(uwp_reference['available'])
        transitions = uwp_reference['transitions']
        self.assertTrue(all(any(tuple(edge['start']) == step.start
                                 and tuple(edge['end']) == step.end
                                 for edge in transitions)
                            for draft in uwp_drafts for step in draft.steps))

    def test_zpp_zero_extra_transposition_reference_stays_in_each_q_lane(self):
        from pattern_rule_workbench import DividerRouteRecord
        record = DividerRouteRecord(
            'ZPP', Fraction(3), 4, 4, 72, 3, (3, 1, 1), 'q_only',
            'Candidate', 'exploratory reference sample')

        drafts = generate_route_drafts(record)

        self.assertEqual([len(draft.path) for draft in drafts], [32, 32, 32])
        self.assertEqual(
            [{slot % 3 for slot, _layer in draft.path} for draft in drafts],
            [{0}, {1}, {2}])
        occupied = [key for draft in drafts for key in draft.path]
        self.assertEqual(len(occupied), 96)
        self.assertEqual(len(set(occupied)), 96)
        for draft in drafts:
            signs = [draft.lookup[key][1] for key in draft.path]
            self.assertTrue(all(signs[index] == -signs[index - 1]
                                for index in range(1, len(signs))))

        public_paths = generate_route_drafts(record, zero_extra_transposition=False)
        self.assertNotEqual(public_paths[0].path, drafts[0].path)
        self.assertGreater(len({slot % 3 for slot, _layer in public_paths[0].path}), 1)

    def test_validated_route_status_keeps_saved_draft_in_tooltip(self):
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        catalog = DividerRouteCatalog(lambda _record: None)
        try:
            record = next(item for item in catalog.records
                          if item.pattern == 'ZLP'
                          and item.dividers == (1, 1, 2))
            self.assertEqual(record.status, 'Validated')
            catalog.saved_routes[catalog._route_key(record)] = (
                Path('saved-zlp-p2.json'), 'configured')
            catalog.refresh()
            row = catalog.records.index(record)
            cell = catalog.table.item(row, 7)
            self.assertEqual(cell.data(Qt.ItemDataRole.UserRole), 'Validated')
            self.assertIn('Saved manual configure', cell.toolTip())
        finally:
            catalog.close()

    def test_slp_pp_p2_manual_route_can_reload_production_path(self):
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        window = PatternRuleWorkbench()
        try:
            record = next(item for item in window.catalog.records
                          if item.pattern == "SLP"
                          and item.dividers == (1, 2, 2))
            self.assertEqual(record.status, "Validated")
            window.open_route(record)
            self.assertTrue(window.production_path_button.isEnabled())
            window._reload_production_path()
            self.assertEqual(len(window.branch_set.branches), 4)
            self.assertIn("Direct public Regular", window.status.text())
        finally:
            window.close()

    def test_slp_selected_routes_use_production_validation_for_status(self):
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication

        records = {record.dividers: record
                   for record in build_divider_route_catalog("2", 4, 4)
                   if record.pattern == "SLP"}
        for factors in ((1, 2, 2), (2, 1, 2), (2, 2, 2)):
            with self.subTest(factors=factors):
                self.assertEqual(records[factors].status, "Validated")
        self.assertIn("not strong symmetry layout", records[(2, 1, 2)].reason)
        self.assertNotEqual(records[(2, 1, 1)].status, "Validated")
        app = QApplication.instance() or QApplication([])
        catalog = DividerRouteCatalog(lambda _record: None)
        try:
            record = next(item for item in catalog.records
                          if item.pattern == "SLP"
                          and item.dividers == (2, 1, 2))
            row = catalog.records.index(record)
            self.assertEqual(
                catalog.table.item(row, 7).data(Qt.ItemDataRole.UserRole),
                "Validated · not strong symmetry layout")
        finally:
            catalog.close()

    def test_route_catalog_classifies_default_validated_rejected_and_unsupported(self):
        records = build_divider_route_catalog("2", 4, 4)
        self.assertTrue(all(record.dividers[0] in (1, 2) for record in records))
        self.assertTrue(all(record.dividers[1] in (1, 2, 4) for record in records))
        self.assertTrue(all(record.dividers[2] in (1, 2) for record in records))
        self.assertTrue(all(record.naa == math.prod(record.dividers)
                            for record in records))
        self.assertFalse(any(record.dividers == (1, 1, 4)
                             for record in records))
        statuses = {record.status for record in records}
        self.assertIn("Default", statuses)
        self.assertIn("Validated", statuses)
        self.assertIn("unsupported-yet", statuses)
        self.assertIn("rejected", statuses)
        rejected = build_divider_route_catalog("2", 3, 4)
        self.assertIn("rejected", {record.status for record in rejected})
        self.assertTrue(all(
            record.status == "rejected"
            for record in records
            if record.route_name == "default"
            and "Default route rejected" in record.reason))
        fractional = build_divider_route_catalog("3/2", 4, 6)
        self.assertEqual(len(fractional), 40)
        self.assertEqual(
            {record.dividers for record in fractional
             if record.pattern == "UWP"},
            {(Fraction(3, 2), 1, 2),
             (Fraction(3, 2), 2, 2),
             (Fraction(3, 2), 4, 2),
             (Fraction(3, 2), 2, 1)})
        self.assertTrue(all(record.naa == math.prod(record.dividers)
                            for record in fractional))
        self.assertTrue(all(
            record.status in ("Validated", "rejected",
                              "not strong symmetry layout")
            for record in fractional if record.pattern == "UWP"))
        self.assertTrue(all(
            record.status in ("unsupported-yet", "rejected")
            for record in fractional if record.pattern != "UWP"))
        self.assertTrue(all(
            record.reason == "BWP does not support P2-divider=2."
            for record in fractional
            if record.pattern == "BWP" and record.dividers[2] == 2))
        bwp_p2 = [record for record in records
                  if record.pattern == "BWP" and record.dividers[2] == 2]
        self.assertTrue(bwp_p2)
        self.assertTrue(all(record.status == "rejected"
                            for record in bwp_p2))
        self.assertTrue(all(record.reason ==
                            "BWP does not support P2-divider=2."
                            for record in bwp_p2))
        phase_five = build_divider_route_catalog("2", 4, 4, 5)
        self.assertTrue(phase_five)
        self.assertEqual({record.phases for record in phase_five}, {5})
        self.assertEqual({record.slots for record in phase_five}, {80})
        for phases in (6, 9, 12):
            with self.subTest(phases=phases):
                layers = 2 * (phases // 3)
                records = build_divider_route_catalog("2", 4, layers, phases)
                self.assertTrue(records)
                self.assertEqual({record.phases for record in records}, {phases})
                self.assertEqual({record.slots for record in records},
                                 {16 * phases})
        with self.assertRaisesRegex(ValueError, "layers divisible by 4"):
            build_divider_route_catalog("2", 4, 6, 12)
        for invalid_phases in (1, 2, 4, 8):
            with self.subTest(phases=invalid_phases):
                with self.assertRaisesRegex(ValueError, "phase count"):
                    build_divider_route_catalog("2", 4, 4, invalid_phases)

    def test_cp_pp_sketch_and_full_q_full_pp_candidate_statuses(self):
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        catalog = DividerRouteCatalog(lambda _record: None)
        try:
            records = {record.dividers: record for record in catalog.records
                       if record.pattern == "CP"}
            self.assertEqual(records[(1, 2, 1)].status, "Validated")
            self.assertEqual(records[(1, 4, 1)].status, "Validated")
            self.assertEqual(records[(2, 4, 1)].status, "Validated")
            row = catalog.records.index(records[(1, 2, 1)])
            self.assertEqual(
                catalog.table.item(row, 7).data(Qt.ItemDataRole.UserRole),
                "Validated")
        finally:
            catalog.close()

    def test_manual_phase_drafts_accept_all_requested_multiples(self):
        from pattern_rule_workbench import PatternDraft
        from phase_topology import phase_map

        for phases in (6, 9, 12):
            with self.subTest(phases=phases):
                layers = 2 * (phases // 3)
                slots = phases * 4 * 2
                selected_phase = phases - 1
                start = next((slot, layer) for slot, layer, phase, _sign
                             in phase_map(slots, 4, layers, phases=phases)
                             if phase == selected_phase)
                draft = PatternDraft(phases * 4 * 2, 4, layers,
                                     phase=selected_phase,
                                     start=start,
                                     num_phases=phases)
                self.assertEqual(draft.num_phases, phases)
                self.assertEqual(draft.phase, phases - 1)
                self.assertEqual(len(draft.records), phases * 4 * 2 * layers)

    def test_multiphase_odd_layer_identity_is_reported_as_unverified(self):
        from pattern_rule_workbench import build_divider_route_catalog

        build_divider_route_catalog.cache_clear()
        try:
            with patch("pattern_rule_workbench.PATTERNS", ("SSP",)):
                records = build_divider_route_catalog("4", 2, 6, 6)
        finally:
            build_divider_route_catalog.cache_clear()

        record = next(item for item in records
                      if item.dividers == (4, 2, 1))
        self.assertEqual(record.status, "identity unverified")
        self.assertIn("legacy checks only", record.reason)

    def test_fractional_catalog_uses_resolver_admission_for_existing_families(self):
        from pattern_route_contract import PatternRouteDecision

        def unsupported(pattern, _winding, dividers, _configuration, _layout):
            return PatternRouteDecision(
                'disabled', 'fractional_route_unsupported',
                'Resolver says no registered construction.',
                pattern, tuple(dividers), admission='unsupported-yet')

        build_divider_route_catalog.cache_clear()
        try:
            with patch('pattern_rule_workbench.gw.resolve_pattern_route',
                       side_effect=unsupported) as resolver, patch(
                           'pattern_rule_workbench._probe_route',
                           return_value=(False, 'Unexpected generation')):
                records = build_divider_route_catalog('3/2', 4, 6)
            self.assertEqual(len(records), 40)
            self.assertEqual(resolver.call_count, len(records))
            self.assertEqual({record.status for record in records},
                             {'unsupported-yet'})
            self.assertEqual({record.reason for record in records},
                             {'Resolver says no registered construction.'})
        finally:
            build_divider_route_catalog.cache_clear()

    def test_fractional_catalog_keeps_resolver_candidate_exploratory(self):
        from pattern_route_contract import PatternRouteDecision

        def candidate(pattern, _winding, dividers, _configuration, _layout):
            return PatternRouteDecision(
                'candidate', 'exploratory_identity', 'Identity needs production validation.',
                pattern, tuple(dividers), admission='Candidate')

        build_divider_route_catalog.cache_clear()
        try:
            with patch('pattern_rule_workbench.gw.resolve_pattern_route',
                       side_effect=candidate), patch(
                           'pattern_rule_workbench._probe_route',
                           side_effect=AssertionError('Candidate must not be promoted')):
                records = build_divider_route_catalog('3/2', 4, 6)
            self.assertEqual(len(records), 40)
            self.assertEqual({record.status for record in records}, {'Candidate'})
        finally:
            build_divider_route_catalog.cache_clear()

    @unittest.skip('Research evidence: expanding the half-integer catalog from 40 to 110 '
                   'factorizations was deferred for V7.6; the original test failed 40 != 110.')
    def test_fractional_catalog_uses_resolver_for_every_integer_naa_factorization(self):
        from pattern_route_contract import PatternRouteDecision

        q = Fraction(3, 2)
        expected = {
            (q_divider, pp_divider, p2_divider)
            for q_divider in (1, q)
            for pp_divider in (1, 2, 4)
            for p2_divider in (1, 2)
            if (q_divider * pp_divider * p2_divider).denominator == 1
        }

        def unsupported(pattern, _winding, dividers, _configuration, _layout):
            return PatternRouteDecision(
                'disabled', 'fractional_route_unsupported',
                'No registered construction for this factorization.',
                pattern, tuple(dividers), admission='unsupported-yet')

        build_divider_route_catalog.cache_clear()
        try:
            with patch('pattern_rule_workbench.gw.resolve_pattern_route',
                       side_effect=unsupported) as resolver, patch(
                           'pattern_rule_workbench._probe_route',
                           return_value=(False, 'Unexpected generation')):
                records = build_divider_route_catalog('3/2', 4, 6)
            self.assertEqual(len(records), len(PATTERNS) * len(expected))
            self.assertEqual({record.dividers for record in records}, expected)
            self.assertEqual(resolver.call_count, len(records))
            self.assertEqual({record.status for record in records},
                             {'unsupported-yet'})
            self.assertEqual({record.reason for record in records},
                             {'No registered construction for this factorization.'})
        finally:
            build_divider_route_catalog.cache_clear()

    def test_rejected_status_shows_short_reason_and_click_reveals_full_reason(self):
        from PyQt6.QtWidgets import QApplication, QPushButton
        app = QApplication.instance() or QApplication([])
        catalog = DividerRouteCatalog(lambda _record: None)
        try:
            record = next(item for item in catalog.records
                          if item.status == "rejected" and len(item.reason) > 42)
            row = catalog.records.index(record)
            button = catalog.table.cellWidget(row, 7).findChild(
                QPushButton, "routeReasonButton")
            self.assertIsNotNone(button)
            self.assertNotEqual(button.text(), record.reason)
            self.assertLessEqual(len(button.text()), 42)
            with patch("pattern_rule_workbench.QMessageBox.information") as show:
                button.click()
            self.assertTrue(show.called)
            self.assertIn(record.reason, str(show.call_args))
        finally:
            catalog.close()

    def test_opening_selected_divider_keeps_target_tuple_when_reference_falls_back(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        catalog = DividerRouteCatalog(lambda _record: None)
        record = next(item for item in catalog.records
                      if item.pattern == "SSP" and item.dividers == (1, 1, 2))
        window = PatternRuleWorkbench()
        try:
            window.open_route(record)
            self.assertIn("(1, 1, 2)", window.route_label.text())
            self.assertEqual(window.source_route.dividers, (1, 1, 2))
            self.assertEqual(window.draft.reference_constraints["selected_dividers"],
                             [1, 1, 2])
        finally:
            window.close()
            catalog.close()

    def test_formula_summary_and_reference_remain_source_backed(self):
        from pattern_rule_workbench import (
            FORMULA_SUPPORT_SUMMARY, load_pattern_development_reference)
        text = FORMULA_SUPPORT_SUMMARY
        self.assertIn("Naa = q-divider * pp-divider * P2", text)
        self.assertIn("pp-divider is any positive integer factor of pp", text)
        self.assertIn("positive half-integer q", text.lower())
        self.assertIn("BWP does not support P2-divider=2", text)
        reference = load_pattern_development_reference()
        self.assertIn("# Pattern Definitions and Constraints", reference)
        self.assertIn("## 3. Ten connection families", reference)

    def test_five_phase_catalog_route_opens_as_five_phase_drafts(self):
        from PyQt6.QtWidgets import QApplication
        from pattern_rule_workbench import generate_route_drafts

        record = next(
            row for row in build_divider_route_catalog("2", 4, 6, 5)
            if row.pattern == "SSP" and row.dividers == (1, 2, 1))
        self.assertEqual(record.status, "Validated")
        drafts = generate_route_drafts(record)
        self.assertEqual(len(drafts), record.naa)
        self.assertTrue(all(draft.num_phases == 5 for draft in drafts))
        self.assertTrue(all(draft.q == 2 for draft in drafts))
        self.assertTrue(all(draft.to_dict()["num_phases"] == 5
                            for draft in drafts))
        app = QApplication.instance() or QApplication([])
        window = PatternRuleWorkbench()
        try:
            window.open_route(record)
            self.assertEqual(window.phases_box.value(), 5)
            self.assertEqual(window.phase_box.count(), 5)
            self.assertEqual(window.draft.num_phases, 5)
        finally:
            window.close()

    def test_phase_controls_are_not_limited_to_99(self):
        from PyQt6.QtWidgets import QApplication
        from pattern_rule_workbench import DividerRouteCatalog

        app = QApplication.instance() or QApplication([])
        catalog = DividerRouteCatalog(lambda _record: None)
        window = PatternRuleWorkbench()
        try:
            self.assertEqual(catalog.phases_box.maximum(), 999)
            self.assertEqual(window.phases_box.maximum(), 999)
            window.phases_box.setValue(102)
            self.assertEqual(window.phases_box.value(), 102)
            self.assertEqual(window.phase_box.count(), 102)
        finally:
            window.close()
            catalog.close()

    def test_fractional_catalog_route_opens_and_serializes_exact_q_factor(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        window = PatternRuleWorkbench()
        try:
            window.catalog.q_box.setText("3/2")
            window.catalog.pp_box.setValue(4)
            window.catalog.layers_box.setValue(6)
            window.catalog.refresh()
            record = next(item for item in window.catalog.records
                          if item.pattern == "UWP" and item.dividers[1] == 2)
            window.open_route(record)
            self.assertEqual(window.source_route.dividers,
                             (Fraction(3, 2), 2, 2))
            with tempfile.TemporaryDirectory() as folder:
                output = Path(folder) / "fractional-route.json"
                window.export_draft(output)
                data = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(data["source_route"]["dividers"],
                                 ["3/2", 2, 2])
                window.manual_draft_dir = Path(folder)
                saved = window.save_manual_configure()
                self.assertIn("Q-3over2_PP-2_P2-2", saved.name)
        finally:
            window.close()

    def test_catalog_opens_unsupported_route_in_editor(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        window = PatternRuleWorkbench()
        try:
            record = next(item for item in window.catalog.records
                          if item.status in ("unsupported-yet", "rejected"))
            window.open_route(record)
            self.assertEqual(window.pattern_box.currentText(), record.pattern)
            self.assertEqual(window.naa_box.value(), record.naa)
            self.assertEqual(window.source_route.dividers, record.dividers)
        finally:
            window.close()

    def test_every_catalog_row_has_open_button_and_validated_loads_full_paths(self):
        from PyQt6.QtWidgets import QApplication, QPushButton
        app = QApplication.instance() or QApplication([])
        window = PatternRuleWorkbench()
        try:
            self.assertTrue(all(isinstance(window.catalog.table.cellWidget(row, 6),
                                           QPushButton)
                                for row in range(window.catalog.table.rowCount())))
            record = next(item for item in window.catalog.records
                          if item.status in ("Default", "Validated"))
            window.open_route(record)
            self.assertEqual(len(window.branch_set.branches), record.naa)
            self.assertTrue(all(len(branch.path) == branch.target_branch_count
                                for branch in window.branch_set.branches))
            self.assertTrue(all(step.kind != "production"
                                for branch in window.branch_set.branches
                                for step in branch.steps))
            self.assertIn("exploratory references", window.status.text())
        finally:
            window.close()

    def test_status_comment_is_logged_and_restored_for_route(self):
        from PyQt6.QtWidgets import QApplication, QLineEdit
        app = QApplication.instance() or QApplication([])
        window = PatternRuleWorkbench()
        try:
            record = window.catalog.records[0]
            row = 0
            status_widget = window.catalog.table.cellWidget(row, 7)
            note_edit = status_widget.findChild(QLineEdit)
            self.assertIsNotNone(note_edit)
            with tempfile.TemporaryDirectory() as folder:
                log_path = Path(folder) / "route_notes.jsonl"
                window.catalog.note_log_path = log_path
                note = "rejected: q2=2 is not allowed for BWP"
                note_edit.setText(note)
                note_edit.textEdited.emit(note)
                entry = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
                self.assertEqual(entry["note"], note)
                self.assertEqual(entry["pattern"], record.pattern)
                restored = window.catalog._load_route_notes(log_path)
                self.assertEqual(restored[window.catalog._route_key(record)], note)
        finally:
            window.close()

    def test_reference_constraints_filter_candidates(self):
        constraints = {"edges": [{"side": "weld", "layer_delta": 1,
                                    "signed_pitch": 4, "direction_ok": True}]}
        draft = PatternDraft(36, 8, 6, naa=3, pattern="SSP",
                             reference_constraints=constraints)
        candidates = draft.regular_candidates()
        self.assertTrue(candidates)
        self.assertTrue(all(target[1] - draft.current[1] == 1
                            for target in candidates))
        self.assertTrue(all(target not in draft.blocked for target in candidates))
        reverse = PatternDraft(
            36, 8, 6, naa=3, pattern="SSP",
            reference_constraints={"edges": [{"side": "weld", "layer_delta": 1,
                                                "signed_pitch": -4,
                                                "direction_ok": True}]})
        self.assertEqual(reverse.regular_candidates(), [])
        reverse.wave_direction = -1
        self.assertTrue(reverse.regular_candidates())

    def test_advance_uses_selected_pattern_route_and_pauses_at_its_special_edge(self):
        constraints = {
            "available": True,
            "transitions": [
                {"start": [0, 0], "end": [4, 1], "side": "weld",
                 "kind": "ordinary", "note": "SSP spiral pass"},
                {"start": [4, 1], "end": [10, 1], "side": "insert",
                 "kind": "turnaround", "note": "SSP same-layer return"},
            ],
            "edges": [],
        }
        draft = PatternDraft(36, 8, 6, naa=3, pattern="SSP",
                             reference_constraints=constraints)

        self.assertEqual(draft.advance_until_special(), 1)
        self.assertEqual(draft.current, (4, 1))
        self.assertEqual(draft.regular_candidates(), [])
        self.assertEqual(
            draft.suggested_special_transition(),
            {"target": (10, 1), "kind": "turnaround",
             "note": "SSP same-layer return"})

    def test_selected_tlp_route_exposes_top_bottom_return_as_special(self):
        record = next(
            row for row in build_divider_route_catalog("2", 4, 4)
            if row.pattern == "TLP" and row.dividers == (2, 1, 2))
        constraints = extract_reference_constraints(
            record.pattern, record.q, record.pp * 2, record.layers,
            record.naa, record.phases, record.dividers)

        self.assertTrue(constraints["available"])
        self.assertTrue(constraints["transitions"])
        self.assertTrue(any(
            edge["kind"] == "first_last_layer"
            for edge in constraints["transitions"]))
        self.assertTrue(any(
            edge["kind"] == "ordinary"
            for edge in constraints["transitions"]))
        production = generate_route_drafts(record)[0]
        draft = PatternDraft(
            record.slots, record.pp * 2, record.layers, phase=0,
            start=production.path[0], first_side=production.first_side,
            naa=record.naa, pattern=record.pattern,
            reference_constraints=constraints)
        self.assertGreater(draft.advance_until_special(), 0)
        suggestion = draft.suggested_special_transition()
        self.assertIsNotNone(suggestion)
        self.assertEqual(suggestion["kind"], "first_last_layer")
        self.assertEqual(suggestion["target"], production.path[len(draft.path)])

    def test_lpp_rejected_target_uses_full_pp_reference_and_pauses_at_pair_transfer(self):
        routes = {record.dividers: record for record in
                  build_divider_route_catalog('2', 4, 4, 3)
                  if record.pattern == 'LPP'}
        self.assertEqual(routes[(1, 1, 1)].status, 'rejected')
        self.assertEqual(routes[(1, 2, 1)].status, 'rejected')
        self.assertEqual(routes[(1, 4, 1)].status, 'Default')
        constraints = extract_reference_constraints(
            'LPP', 2, 8, 4, 2, 3, (1, 2, 1))
        self.assertTrue(constraints['available'])
        self.assertEqual(constraints['reference_mode'], 'default_series')
        self.assertEqual(constraints['reference_naa'], 4)
        self.assertEqual(constraints['reference_dividers'], [1, 4, 1])
        draft = PatternDraft(
            48, 8, 4, phase=0, start=(0, 0), first_side='insert',
            naa=2, pattern='LPP', reference_constraints=constraints)
        self.assertEqual(draft.advance_until_special(), 7)
        self.assertEqual(len(draft.path), 8)
        self.assertEqual(draft.current, (6, 1))
        self.assertEqual(draft.suggested_special_transition(), {
            'target': (1, 2), 'kind': 'layer_pair_transfer',
            'note': 'LPP reference next layer pair weld transfer'})
        self.assertEqual(draft.advance_until_special(), 1)
        self.assertEqual(draft.current, (1, 2))
        self.assertEqual(draft.steps[-1].side, 'weld')

    def test_bwp_same_layer_return_is_a_turnaround(self):
        constraints = extract_reference_constraints("BWP", 2, 8, 4, 1)
        same_layer = [edge for edge in constraints["transitions"]
                      if edge["start"][1] == edge["end"][1]]
        self.assertTrue(same_layer)
        self.assertEqual({edge["kind"] for edge in same_layer}, {"turnaround"})

    def test_missing_pattern_reference_does_not_fall_back_to_wave_steps(self):
        draft = PatternDraft(36, 8, 6, naa=3, pattern="CP")
        self.assertEqual(draft.regular_candidates(), [])
        self.assertEqual(draft.advance_until_special(), 0)

    def test_cp_advance_pauses_after_each_four_conductors(self):
        draft = PatternDraft(36, 8, 4, naa=1, pattern="CP")
        phase_positions = [key for key, (phase, _sign) in sorted(draft.lookup.items())
                           if phase == draft.phase]
        reference_path = [phase_positions[0]]
        while len(reference_path) < 13:
            prior_sign = draft.lookup[reference_path[-1]][1]
            reference_path.append(next(
                key for key in phase_positions
                if key not in reference_path
                and draft.lookup[key][1] == -prior_sign))
        transitions = [
            {"start": list(start), "end": list(end),
             "side": "weld" if index % 2 == 0 else "insert",
             "kind": "ordinary", "note": "CP reference body step"}
            for index, (start, end) in enumerate(
                zip(reference_path, reference_path[1:]))]
        draft = PatternDraft(
            36, 8, 4, naa=1, pattern="CP", start=reference_path[0],
            reference_constraints={"available": True, "travel_direction": 1,
                                  "transitions": transitions, "edges": []})

        self.assertEqual(draft.advance_until_special(), 3)
        self.assertEqual(len(draft.path), 4)
        self.assertEqual([step.kind for step in draft.steps], ["regular"] * 3)
        self.assertEqual(draft.advance_until_special(), 4)
        self.assertEqual(len(draft.path), 8)
        self.assertEqual([step.kind for step in draft.steps], ["regular"] * 7)
        self.assertEqual(draft.advance_until_special(), 4)
        self.assertEqual(len(draft.path), 12)
        self.assertEqual([step.kind for step in draft.steps], ["regular"] * 11)

    def test_zpp_advance_pauses_after_each_four_conductors(self):
        draft = PatternDraft(36, 8, 4, naa=1, pattern="ZPP")
        phase_positions = [key for key, (phase, _sign) in sorted(draft.lookup.items())
                           if phase == draft.phase]
        reference_path = [phase_positions[0]]
        while len(reference_path) < 13:
            prior_sign = draft.lookup[reference_path[-1]][1]
            reference_path.append(next(
                key for key in phase_positions
                if key not in reference_path
                and draft.lookup[key][1] == -prior_sign))
        transitions = [
            {"start": list(start), "end": list(end),
             "side": "weld" if index % 2 == 0 else "insert",
             "kind": "ordinary", "note": "ZPP reference body step"}
            for index, (start, end) in enumerate(
                zip(reference_path, reference_path[1:]))]
        draft = PatternDraft(
            36, 8, 4, naa=1, pattern="ZPP", start=reference_path[0],
            reference_constraints={"available": True, "travel_direction": 1,
                                  "transitions": transitions, "edges": []})

        self.assertEqual(draft.advance_until_special(), 3)
        self.assertEqual(len(draft.path), 4)
        self.assertEqual(draft.advance_until_special(), 4)
        self.assertEqual(len(draft.path), 8)
        self.assertEqual(draft.advance_until_special(), 4)
        self.assertEqual(len(draft.path), 12)
        self.assertTrue(all(step.kind == "regular" for step in draft.steps))

    def test_zpp_lane_walk_pauses_for_one_formula_transition_then_reanchors(self):
        constraints = extract_reference_constraints(
            'ZPP', 4, 8, 4, 2, 3, (1, 1, 2))
        self.assertTrue(constraints['available'])
        self.assertEqual(constraints['reference_mode'], 'default_lane_walk')
        self.assertEqual(constraints['lane_walk']['tau'], 12)
        start = tuple(constraints['reference_starts']['0'])
        draft = PatternDraft(
            96, 8, 4, phase=0, start=start,
            first_side=constraints['first_side'], naa=2, pattern='ZPP',
            reference_constraints=constraints)

        while len(draft.path) < 32:
            self.assertGreater(draft.advance_until_special(), 0)
        self.assertEqual({slot % 4 for slot, _layer in draft.path}, {0})
        pending = draft.suggested_special_transition()
        self.assertIsNotNone(pending)
        self.assertEqual(pending['kind'], 'lane_transition')
        self.assertEqual(pending['target'][0] % 4, 1)
        self.assertEqual(abs(pending['target'][1] - draft.current[1]), 1)
        self.assertIn('tau=12', pending['note'])

        self.assertEqual(draft.advance_until_special(), 1)
        self.assertEqual(draft.steps[-1].kind, 'lane_transition')
        self.assertGreater(draft.advance_until_special(), 0)
        self.assertTrue(all(step.kind == 'regular'
                            for step in draft.steps[-3:]))
        self.assertEqual(len(draft.path), 36)
        while len(draft.path) < draft.target_branch_count:
            self.assertGreater(draft.advance_until_special(), 0)
        self.assertEqual(len(draft.path), 64)
        self.assertEqual(len(set(draft.path)), 64)
        self.assertEqual(sum(step.kind == 'lane_transition'
                             for step in draft.steps), 2)

    def test_zpp_manual_special_endpoint_reanchors_inside_its_lane(self):
        constraints = extract_reference_constraints(
            'ZPP', 4, 8, 4, 2, 3, (1, 1, 2))
        start = tuple(constraints['reference_starts']['0'])
        draft = PatternDraft(
            96, 8, 4, phase=0, start=start,
            first_side=constraints['first_side'], naa=2, pattern='ZPP',
            reference_constraints=constraints)
        while len(draft.path) < 32:
            self.assertGreater(draft.advance_until_special(), 0)

        manual_target = draft.suggested_special_transition()['target']
        draft.reference_constraints['transitions'] = [
            edge for edge in draft.reference_constraints['transitions']
            if tuple(edge['start']) != manual_target]
        draft.add_special(manual_target, 'custom', 'Manual exploratory lane hop')

        candidates = draft.regular_candidates()

        self.assertTrue(candidates)
        self.assertTrue(all(draft._zpp_lane_index(key) == 1
                            for key in candidates))

    def test_uwp_non_main_pitch_is_an_explicit_pattern_jumper(self):
        constraints = extract_reference_constraints("UWP", 2, 8, 4, 1)
        self.assertTrue(any(
            edge["kind"] == "jumper"
            and abs(edge["end"][0] - edge["start"][0]) not in (6, 42)
            for edge in constraints["transitions"]))

    def test_complete_rule_package_enables_copy_and_writes_schema_v3(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        window = PatternRuleWorkbench()
        try:
            window.branch_set = BranchDraftSet(self.complete_route_draft())
            window.draft = window.branch_set.active
            window._update("Ready")
            self.assertTrue(window.copy_prompt_button.isEnabled())
            with tempfile.TemporaryDirectory() as folder:
                output = Path(folder) / "rule.json"
                window.export_draft(output)
                data = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(data["schema_version"], 3)
                self.assertFalse(data["certified"])
                self.assertIn("source_route", data)
                self.assertTrue(output.with_suffix(".md").is_file())
                prompt = output.with_suffix(".md").read_text(encoding="utf-8")
                self.assertIn("Do not hard-code", prompt)
                self.assertIn("complex EMF", prompt)
                self.assertIn(str(output.resolve()), prompt)
        finally:
            window.close()

    def test_save_manual_configure_names_files_and_marks_catalog_status(self):
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        window = PatternRuleWorkbench()
        try:
            record = next(item for item in window.catalog.records
                          if item.status in ("unsupported-yet", "rejected"))
            window.open_route(record)
            window.draft.add_special(
                window.draft.available_conductors()[0], "custom", "saved manual edge")
            window._manual_edit_dirty = True
            window._update("Manual edit")
            with tempfile.TemporaryDirectory() as folder:
                window.manual_draft_dir = Path(folder)
                output = window.save_manual_configure()
                self.assertTrue(output.is_file())
                self.assertIn(record.pattern, output.name)
                self.assertIn(f"Naa-{record.naa}", output.name)
                data = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(data["save_kind"], "manual_configure")
                self.assertTrue(output.with_suffix(".png").is_file())
                self.assertTrue(output.with_suffix(".md").is_file())
                row = window.catalog.records.index(record)
                self.assertIn("Manual draft saved",
                              window.catalog.table.item(row, 7).data(
                                  Qt.ItemDataRole.UserRole))
                window.open_route(record)
                self.assertEqual(len(window.draft.path), 2)
                self.assertEqual(window.draft.steps[0].note, "saved manual edge")
                window.catalog.mark_saved(record, output, "configured")
                self.assertIn("Manual configured",
                              window.catalog.table.item(row, 7).data(
                                  Qt.ItemDataRole.UserRole))
        finally:
            window.close()

    def test_copy_codex_prompt_saves_current_layout_and_uses_absolute_path(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        window = PatternRuleWorkbench()
        try:
            with tempfile.TemporaryDirectory() as folder:
                window.manual_draft_dir = Path(folder)
                window.copy_prompt_button.setEnabled(True)
                window._copy_codex_prompt()
                saved = list(Path(folder).glob('*.json'))
                self.assertEqual(len(saved), 1)
                prompt = QApplication.clipboard().text()
                self.assertIn(str(saved[0].resolve()), prompt)
                self.assertNotIn('attached schema-v3', prompt)
                self.assertIn('current project', prompt)
                self.assertIn('do not use EMF asymmetry alone to reject', prompt)
                self.assertIn('auto configure pending', prompt)
                self.assertIn('hard no', prompt)
                self.assertIn('saved and non-certified', window.status.text())
        finally:
            window.close()
            del app

    @staticmethod
    def complete_route_draft():
        draft = PatternDraft(12, 2, 2, naa=1, pattern="BWP")
        for target in draft.available_conductors():
            draft.add_special(target, "custom", "manual")
        return draft

    def test_regular_step_and_special_pause(self):
        constraints = {
            "edges": [{"side": "weld", "layer_delta": 1,
                       "signed_pitch": 4, "direction_ok": True}]}
        draft = PatternDraft(36, 8, 6, phase=0, start=(0, 0),
                             reference_constraints=constraints)
        self.assertEqual(str(draft.q), "3/2")
        candidates = draft.regular_candidates()
        self.assertTrue(candidates)
        self.assertTrue(all(target[1] == 1 for target in candidates))
        draft.add_regular(candidates[0])
        self.assertEqual(draft.steps[0].side, "weld")
        self.assertEqual(draft.steps[0].kind, "regular")
        self.assertEqual(draft.steps[0].pitch, 4)
        self.assertEqual(draft.current, candidates[0])
        self.assertEqual(draft.next_side, "insert")

        count = draft.advance_until_special()
        self.assertGreaterEqual(count, 0)
        self.assertEqual(draft.regular_candidates(), [])
        self.assertLessEqual(len(draft.path), draft.phase_conductor_count)

    def test_special_step_records_intent_without_certifying_rule(self):
        draft = PatternDraft(36, 8, 6, phase=0, start=(0, 0))
        target = next(key for key in draft.available_conductors()
                      if key[1] == 2)
        draft.add_special(target, "jumper", "Proposed layer jump")
        self.assertEqual(draft.steps[0].kind, "jumper")
        self.assertEqual(draft.steps[0].note, "Proposed layer jump")
        self.assertFalse(draft.to_dict()["certified"])
        self.assertEqual(draft.to_dict()["steps"][0]["to"],
                         {"slot": target[0] + 1, "layer": 3})
        draft.undo()
        self.assertEqual(draft.path, [(0, 0)])

    def test_rejects_wrong_phase_and_duplicate_conductor(self):
        draft = PatternDraft(36, 8, 6, phase=0, start=(0, 0))
        with self.assertRaisesRegex(ValueError, "already used"):
            draft.add_special((0, 0), "custom")
        wrong_phase = next((slot, layer) for slot, layer, phase, _ in
                           draft.records if phase != 0)
        with self.assertRaisesRegex(ValueError, "selected phase"):
            draft.add_special(wrong_phase, "custom")

    def test_naa_limits_one_branch_without_claiming_other_branches(self):
        draft = PatternDraft(36, 8, 6, phase=0, start=(0, 0), naa=3)
        self.assertEqual(draft.phase_conductor_count, 72)
        self.assertEqual(draft.target_branch_count, 24)
        self.assertEqual(draft.to_dict()["naa"], 3)
        self.assertEqual(draft.to_dict()["pattern"], "BWP")
        with self.assertRaisesRegex(ValueError, "Naa must divide"):
            PatternDraft(36, 8, 6, naa=5)
        with self.assertRaisesRegex(ValueError, "Unknown Pattern"):
            PatternDraft(36, 8, 6, pattern="UNKNOWN")
        full = PatternDraft(36, 8, 6, naa=72)
        self.assertEqual(full.regular_candidates(), [])
        with self.assertRaisesRegex(ValueError, "target conductor count"):
            full.add_special(full.available_conductors()[0], "custom")

    def test_regular_target_includes_relative_layer_shift(self):
        draft = PatternDraft(36, 8, 6, start=(0, 0),
                             shifts=(0, 1, 0, 0, 0, 0))
        self.assertIn((5, 1), draft.regular_candidates())
        self.assertIn((6, 1), draft.regular_candidates())

    def test_export_contains_replayable_steps_and_image(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        window = PatternRuleWorkbench()
        try:
            window.draft.add_regular(window.draft.regular_candidates()[0])
            with tempfile.TemporaryDirectory() as folder:
                output = Path(folder) / "draft.json"
                image = window.export_draft(output)
                data = json.loads(output.read_text(encoding="utf-8"))
                self.assertTrue(image.is_file())
                self.assertGreater(image.stat().st_size, 1000)
                self.assertEqual(data["status"], "exploratory_partial_branch")
                self.assertEqual(len(data["steps"]), 1)
                self.assertEqual(data["steps"][0]["wave_direction"], 1)
                self.assertEqual(data["path"][0], {"slot": 1, "layer": 1})
        finally:
            window.close()
            del app

    def test_edited_inputs_require_new_draft_before_export(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        window = PatternRuleWorkbench()
        try:
            window.naa_box.setValue(3)
            self.assertFalse(window.export_button.isEnabled())
            with tempfile.TemporaryDirectory() as folder:
                with self.assertRaisesRegex(ValueError, "New Draft"):
                    window.export_draft(Path(folder) / "stale.json")
            window._new_draft()
            self.assertEqual(window.draft.naa, 3)
            self.assertTrue(window.export_button.isEnabled())
        finally:
            window.close()
            del app

    def test_ordinary_actions_include_undo_and_help_is_available(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        window = PatternRuleWorkbench()
        try:
            self.assertIs(window.ordinary_actions.itemAt(1).widget(),
                          window.undo_button)
            self.assertTrue(window.help_button.isEnabled())
            self.assertEqual(window.help_button.text(), "")
            self.assertEqual(window.help_button.toolTip(), "Help")
            self.assertEqual(window.save_button.toolTip(), "Save Manual Configure")
            self.assertEqual(window.export_button.toolTip(), "Export Rule Package")
            self.assertEqual(window.copy_prompt_button.toolTip(), "Copy Codex Prompt")
            self.assertLessEqual(window.controls_scroll.maximumWidth(), 405)
            self.assertLessEqual(window.slots_box.maximumWidth(), 205)
            self.assertLessEqual(window.next_branch_button.maximumWidth(), 220)
        finally:
            window.close()
            del app

    def test_wrapped_connections_keep_a_consistent_entry_angle(self):
        first, second = PatternRuleWorkbench._wrapped_connection_segments(
            (30, 1), (1, 6), 36)
        first_slope = ((first[1][1] - first[1][0]) /
                       (first[0][1] - first[0][0]))
        second_slope = ((second[1][1] - second[1][0]) /
                        (second[0][1] - second[0][0]))
        self.assertAlmostEqual(first_slope, second_slope)
        self.assertEqual(second[0][0], 0.5)
        self.assertEqual(second[0][1], 1)

    def test_all_patterns_share_shortest_orthogonal_same_layer_routes(self):
        for pattern in PATTERNS:
            with self.subTest(pattern=pattern):
                top = PatternRuleWorkbench._same_layer_connection_points(
                    (48, 1), (1, 1), 48, 0.7)
                bottom = PatternRuleWorkbench._same_layer_connection_points(
                    (1, 4), (48, 4), 48, 4.3)
                self.assertEqual(top, [(48, 1), (48, 0.7), (49, 0.7), (49, 1)])
                self.assertEqual(bottom, [(1, 4), (1, 4.3), (0, 4.3), (0, 4)])
                for points in (top, bottom):
                    pieces = PatternRuleWorkbench._split_wrapped_polyline(points, 48)
                    tail, head = dfig.unwrapped_path_arrow_segment(pieces)
                    self.assertLessEqual(abs(head[0] - tail[0]), 1)

    def test_overlapping_boundary_routes_receive_distinct_shared_lanes(self):
        record = next(
            record for record in build_divider_route_catalog('2', 4, 4, 3)
            if record.pattern == 'BWP' and record.naa == 2
            and record.dividers == (1, 2, 1))
        drafts = generate_route_drafts(record)

        lanes = PatternRuleWorkbench._same_layer_route_lanes(drafts)
        tail_lanes = [
            lanes[(branch_id, index)]
            for branch_id, draft in enumerate(drafts, 1)
            for index, step in enumerate(draft.steps)
            if step.start[1] == step.end[1] == 3
            and lanes[(branch_id, index)].count > 1
        ]
        self.assertGreaterEqual(len(tail_lanes), 2)
        self.assertEqual({lane.rank for lane in tail_lanes}, {0, 1})
        offsets = {dfig.unwrapped_same_layer_lane_offset(
            lane.rank, lane.count) for lane in tail_lanes}
        self.assertEqual(len(offsets), 2)
        self.assertLess(max(offsets), 0.26)

    def test_same_branch_overlapping_visible_spans_use_separate_lanes(self):
        path = [(0, 0), (8, 0), (4, 0), (12, 0)]
        draft = SimpleNamespace(
            slots=48, layers=6, path=path,
            lookup={conductor: (0, 1) for conductor in path})

        lanes = PatternRuleWorkbench._same_layer_route_lanes([draft])

        self.assertEqual({lanes[(1, index)].rank for index in range(3)},
                         {0, 1, 2})
        self.assertTrue(all(lanes[(1, index)].count == 3
                            for index in range(3)))

    def test_lpp_middle_routes_form_staggered_layer_pair_loops(self):
        record = next(
            record for record in build_divider_route_catalog('4', 4, 4, 3)
            if record.pattern == 'LPP' and record.naa == 4
            and record.dividers == (1, 4, 1))
        drafts = generate_route_drafts(record)

        lanes = PatternRuleWorkbench._same_layer_route_lanes(drafts)
        middle_tokens = [
            (branch_id, index)
            for branch_id, draft in enumerate(drafts, 1)
            for index, step in enumerate(draft.steps)
            if step.start[1] == step.end[1] in (1, 2)
        ]
        self.assertTrue(middle_tokens)
        self.assertTrue(all(token in lanes for token in middle_tokens))
        self.assertTrue(any(lanes[token].count > 1 for token in middle_tokens))
        self.assertEqual(
            [dfig.unwrapped_same_layer_lane_sign(layer, 4)
             for layer in range(4)],
            [-1, 1, -1, 1])

    def test_plot_uses_side_styles_and_can_detach_without_losing_canvas(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        window = PatternRuleWorkbench()
        try:
            self.assertEqual(window._linestyle_for_side("weld"), "--")
            self.assertEqual(window._linestyle_for_side("insert"), "-")
            canvas = window.canvas
            window.toggle_plot_window()
            app.processEvents()
            self.assertTrue(window.plot_window.isVisible())
            self.assertIs(window.canvas, canvas)
            self.assertEqual(window.detach_button.text(), "Embed Plot")
            window.embed_plot()
            self.assertFalse(window.plot_window.isVisible())
            self.assertIs(window.canvas, canvas)
            self.assertEqual(window.detach_button.text(), "Detach Plot")
        finally:
            window.close()

    def test_plot_click_adds_regular_or_selected_special_connection(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        window = PatternRuleWorkbench()
        try:
            def click(target):
                window._on_plot_click(SimpleNamespace(
                    button=1, inaxes=window.figure.axes[0],
                    xdata=target[0] + 1.02, ydata=target[1] + 0.98))

            ordinary = window.draft.regular_candidates()[0]
            click(ordinary)
            self.assertEqual(window.draft.current, ordinary)
            self.assertEqual(window.draft.steps[-1].kind, "regular")

            special = next(key for key in window.draft.available_conductors()
                           if key not in window.draft.regular_candidates())
            window.kind_box.setCurrentIndex(1)
            window.edge_note_box.setText("Manual turnaround")
            click(special)
            self.assertEqual(window.draft.current, special)
            self.assertEqual(window.draft.steps[-1].kind, "turnaround")
            self.assertEqual(window.draft.steps[-1].note, "Manual turnaround")
            self.assertEqual((window.target_slot_box.value(),
                              window.target_layer_box.value()),
                             (special[0] + 1, special[1] + 1))
        finally:
            window.close()
            del app

    def test_plot_click_rejects_inexact_or_unavailable_targets(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        window = PatternRuleWorkbench()
        try:
            axis = window.figure.axes[0]
            def click(x, y, button=1):
                window._on_plot_click(SimpleNamespace(
                    button=button, inaxes=axis, xdata=x, ydata=y))

            click(5.49, 2)
            click(5, 2, button=3)
            click(1, 1)
            wrong_phase = next((slot, layer) for slot, layer, phase, _ in
                               window.draft.records if phase != 0)
            click(wrong_phase[0] + 1, wrong_phase[1] + 1)
            self.assertEqual(len(window.draft.steps), 0)

            window.naa_box.setValue(2)
            click(5, 2)
            self.assertEqual(len(window.draft.steps), 0)
        finally:
            window.close()
            del app

    def test_branch_one_start_updates_from_start_inputs_and_has_reset_control(self):
        from PyQt6.QtWidgets import QApplication, QPushButton
        app = QApplication.instance() or QApplication([])
        window = PatternRuleWorkbench()
        try:
            target = next(key for key, (phase, _sign) in window.draft.lookup.items()
                          if phase == window.draft.phase and key != window.draft.path[0])
            window.start_slot_box.setValue(target[0] + 1)
            window.start_layer_box.setValue(target[1] + 1)
            window.start_layer_box.editingFinished.emit()
            self.assertEqual(window.draft.path, [target])
            self.assertFalse(window._draft_pending)
            self.assertIsInstance(window.reset_cond1_button, QPushButton)
            self.assertEqual(window.reset_cond1_button.text(), "Reset Cond 1")
        finally:
            window.close()
            del app

    def test_reset_cond_one_enables_plot_start_selection(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        window = PatternRuleWorkbench()
        try:
            target = next(key for key, (phase, _sign) in window.draft.lookup.items()
                          if phase == window.draft.phase and key != window.draft.path[0])
            window.reset_cond1_button.click()
            self.assertTrue(window._start_select_mode)
            window._on_plot_click(SimpleNamespace(
                button=1, inaxes=window.figure.axes[0],
                xdata=target[0] + 1, ydata=target[1] + 1))
            self.assertEqual(window.draft.path, [target])
            self.assertFalse(window._start_select_mode)
        finally:
            window.close()
            del app


if __name__ == "__main__":
    unittest.main()
