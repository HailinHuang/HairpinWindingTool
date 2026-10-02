"""Production admission checks for ZPP centered PP-only entry translation."""

import json
from pathlib import Path
import unittest

import get_winding_pattern as gw
from pattern_rule_workbench import _base_inputs
from phase_topology import phase_map


class ZppCenteredEntryAdmissionTests(unittest.TestCase):
    def _inputs(self, q, pp, layers, divider, *, phases=3):
        return _base_inputs(
            "ZPP", q, 2 * pp, layers, divider,
            (1, divider, 1), phases=phases)

    def _generate(self, q, pp, divider, *, layers=4, phases=3):
        winding, configuration, layout = self._inputs(
            q, pp, layers, divider, phases=phases)
        decision = gw.resolve_pattern_route(
            "ZPP", winding, (1, divider, 1), configuration, layout)
        self.assertEqual(decision.status, "enabled", decision.reason)
        expected_route = (
            "zpp_pp_only_centered_entry_translation" if phases != 6 else
            "zpp_pp_only_indexed_translation")
        self.assertEqual(decision.route_name, expected_route)

        _starts, database = gw.get_winding_layout(
            "ZPP", configuration, winding, layout, allow_candidate=False)
        if (q, pp, divider, phases) == (1, 6, 3, 3):
            self.assertEqual(database.centered_entry_deployment[
                "sector_stride"], 2)
        if (q, pp, divider, phases) == (3, 12, 6, 3):
            self.assertEqual(database.centered_entry_deployment[
                "sector_stride"], 5)
        expected_count = winding.num_phases * divider
        self.assertEqual(len(database), expected_count)
        expected_length = (
            winding.num_slots * winding.num_layers
            // (winding.num_phases * divider))
        self.assertEqual(
            {len(path) for _branch_id, path in database}, {expected_length})
        gw.validate_selected_zpp(database, winding, layout)

        phase_at = {
            (slot, layer): phase
            for slot, layer, phase, _sign in phase_map(
                winding.num_slots, winding.num_poles, winding.num_layers,
                layout.phase_shift_list, winding.num_phases)
        }
        occupied = set()
        branch_counts = [0] * winding.num_phases
        for branch_id, path in database:
            coordinates = [(node[0], node[1]) for node in path]
            self.assertTrue(all(coordinate not in occupied
                                for coordinate in coordinates))
            occupied.update(coordinates)
            phases_in_branch = {phase_at[coordinate]
                                for coordinate in coordinates}
            self.assertEqual(len(phases_in_branch), 1)
            branch_counts[next(iter(phases_in_branch))] += 1
            steps = database.signed_travel[branch_id]
            self.assertEqual(len(steps), len(path) - 1)
            for start, end, step in zip(path, path[1:], steps):
                self.assertEqual(
                    (start[0] + step) % winding.num_slots, end[0])
        self.assertEqual(branch_counts, [divider] * winding.num_phases)
        return database

    def test_parameterized_samples_generate(self):
        samples = (
            (1, 6, 3, 3),
            (2, 4, 4, 3),
            (3, 12, 6, 3),
            (2, 4, 4, 5),
            (2, 4, 4, 6),
        )
        for q, pp, divider, phases in samples:
            with self.subTest(q=q, pp=pp, divider=divider, phases=phases):
                self._generate(q, pp, divider, phases=phases)

    def test_q2_d4_public_paths_match_the_saved_manual_package(self):
        database = self._generate(2, 4, 4)

        package_path = Path(__file__).with_name("pattern_rule_drafts") / (
            "ZPP_q-2_pp-4_L-4_Naa-4_Q-1_PP-4_P2-1_Ph-A_Side-insert_"
            "Shifts-0-0-0-0_20260925-160009-173286.json")
        package = json.loads(package_path.read_text(encoding="utf-8"))
        expected_phase_a = [
            [(node["slot"] - 1, node["layer"] - 1)
             for node in branch["path"]]
            for branch in package["branches"]
        ]
        actual_phase_a = [
            [(node[0], node[1]) for node in path]
            for _branch_id, path in database[:4]
        ]
        self.assertEqual(actual_phase_a, expected_phase_a)

    def test_nonfactor_and_layer_boundaries_remain_unsupported(self):
        cases = (
            (2, 6, 3, 4, "rejected"),  # current default fails its branch length
            (2, 6, 4, 4, "unsupported-yet"),  # D does not divide pp
            (2, 4, 4, 3, "unsupported-yet"),  # source ZPP requires even layers
        )
        for q, pp, divider, layers, expected_admission in cases:
            with self.subTest(q=q, pp=pp, divider=divider, layers=layers):
                winding, configuration, layout = self._inputs(
                    q, pp, layers, divider)
                decision = gw.resolve_pattern_route(
                    "ZPP", winding, (1, divider, 1), configuration, layout)
                self.assertEqual(decision.admission, expected_admission)

    def test_non_neutral_configuration_does_not_enter_the_route(self):
        winding, configuration, layout = self._inputs(2, 4, 4, 4)
        layout.radial_shift = 1
        decision = gw.resolve_pattern_route(
            "ZPP", winding, (1, 4, 1), configuration, layout)
        self.assertEqual(decision.status, "disabled")

    def test_manual_q_p2_and_q_pp_p2_routes_stay_unsupported_without_a_source(self):
        for dividers, naa in (((2, 1, 2), 4), ((2, 2, 2), 8)):
            with self.subTest(dividers=dividers):
                winding, configuration, layout = self._inputs(
                    2, 4, 4, naa)
                winding.branch_dividers = dividers
                decision = gw.resolve_pattern_route(
                    "ZPP", winding, dividers, configuration, layout)
                self.assertEqual(decision.admission, "unsupported-yet")


if __name__ == "__main__":
    unittest.main()
