"""Branch divider UI and dispatch compatibility checks."""
import os
import math
import hashlib
import unittest
from unittest.mock import patch
import json
from pathlib import Path
from collections import Counter, namedtuple
from fractions import Fraction
from types import SimpleNamespace
import get_winding_pattern as gw
from phase_topology import default_phase_map, electrical_summary, phase_map
from explicit_connections import validate_branches
from divider_connection_formulas import (
    DividerConnectionFormula, DividerFactorRef, DividerFormulaError,
    apply_route_formula, phase_set_local_dividers,
    derive_parent_entry_tensor, walk_parent_entry_tensor,
    ROUTE_FORMULA_BINDINGS, ROUTE_FORMULA_FAMILIES, cp_four_pass_weave,
    cp_parent_half_translation, spiral_q_pp_parent_cut,
    slp_q_pp_single_sector_weld_rotation, tsp_pp_p2_sector_branches,
    tsp_pp_p2_sector_lane_residues, slp_q_pp_p2_lane_regroup,
    tsp_pp_p2_sector_residues_are_complete, zpp_indexed_sector_stride,
)


class DividerConnectionFormulaTests(unittest.TestCase):
    def test_zpp_centered_entry_route_family_is_registered(self):
        self.assertEqual(
            ROUTE_FORMULA_FAMILIES[
                "zpp_pp_only_centered_entry_translation"],
            "divider_zpp_centered_entry_translation")

    def test_parent_entry_tensor_preserves_cell_order_and_walk_direction(self):
        parents = [
            (10, [(0, 0, "a"), (1, 0, "b")]),
            (20, [(2, 0, "c"), (3, 0, "d")]),
        ]
        tensor = derive_parent_entry_tensor(
            parents,
            key_by_coordinate={
                (0, 0): (0, 0, 0, 0), (2, 0): (0, 0, 0, 0),
                (1, 0): (0, 0, 1, 0), (3, 0): (0, 0, 1, 0),
            })
        keys = ((0, 0, 0, 0), (0, 0, 1, 0))

        walk = walk_parent_entry_tensor(tensor, keys, part_index=7)

        self.assertEqual(walk.source_ids, (10, 20))
        self.assertEqual(walk.part_index, 7)
        self.assertEqual(walk.path, [
            (0, 0, "a"), (2, 0, "c"), (1, 0, "b"), (3, 0, "d")])
        reverse = walk_parent_entry_tensor(
            tensor, keys, part_index=8, direction=-1)
        self.assertEqual(reverse.path, list(reversed(walk.path)))
        self.assertEqual(reverse.source_ids, (20, 10))

    def test_parent_entry_tensor_rejects_missing_or_duplicate_coordinates(self):
        with self.assertRaisesRegex(DividerFormulaError, "no inlet-tensor key"):
            derive_parent_entry_tensor(
                [(1, [(0, 0, 0)])], key_by_coordinate={})

        with self.assertRaisesRegex(DividerFormulaError, "more than once"):
            derive_parent_entry_tensor(
                [(1, [(0, 0, 0)]), (2, [(0, 0, 1)])],
                key_by_coordinate={(0, 0): (0, 0, 0, 0)})

        tensor = derive_parent_entry_tensor(
            [(1, [(0, 0, 0)])],
            key_by_coordinate={(0, 0): (0, 0, 0, 0)})
        with self.assertRaisesRegex(DividerFormulaError, "repeats conductor"):
            walk_parent_entry_tensor(
                tensor, ((0, 0, 0, 0), (0, 0, 0, 0)))

    def test_zpp_centered_entry_translation_matches_manual_pp_only_candidate(self):
        from pattern_rule_workbench import _base_inputs

        winding, transposition, layout = _base_inputs(
            "ZPP", 2, 8, 4, 2, (2, 1, 1), 3)
        _starts, database = gw.get_winding_layout(
            "ZPP", transposition, winding, layout)
        parents = [(branch_id, path) for branch_id, path in database]

        branches = DividerConnectionFormula(
            "zpp_centered_entry_translation", (2, 1, 1), (1, 4, 1)
        ).apply(
            parents, num_slots=winding.num_slots, pp=4,
            group_keys=(0, 0, 1, 1, 2, 2), group_order=(0, 1, 2))

        self.assertEqual(len(branches), 12)
        self.assertEqual({len(branch.path) for branch in branches}, {16})
        self.assertEqual([branch.path[0][0] for branch in branches[:4]],
                         [0, 13, 24, 37])
        self.assertEqual([branch.path[0][1] for branch in branches[:4]],
                         [0, 0, 0, 0])
        self.assertEqual([branch.source_ids for branch in branches[:4]],
                         [(1,), (2,), (1,), (2,)])
        self.assertEqual([branch.part_index for branch in branches[:4]],
                         [0, 0, 1, 1])
        package_name = (
            "ZPP_q-2_pp-4_L-4_Naa-4_Q-1_PP-4_P2-1_Ph-A_Side-insert_"
            "Shifts-0-0-0-0_20260925-160009-173286.json")
        package_path = Path(__file__).with_name("pattern_rule_drafts") / package_name
        package = json.loads(package_path.read_text(encoding="utf-8"))
        candidate_paths = [
            [(node["slot"] - 1, node["layer"] - 1)
             for node in branch["path"]]
            for branch in package["branches"]
        ]
        self.assertEqual(
            [[node[:2] for node in branch.path] for branch in branches[:4]],
            candidate_paths)

    def test_zpp_centered_entry_translation_requires_complete_integer_sector_groups(self):
        parents = [(10, [(0, 0), (1, 0)]), (20, [(2, 0), (3, 0)])]
        with self.assertRaisesRegex(DividerFormulaError, "Q must divide D"):
            DividerConnectionFormula(
                "zpp_centered_entry_translation", (2, 1, 1), (1, 3, 1)
            ).apply(
                parents, num_slots=12, pp=4,
                group_keys=(0, 0), group_order=(0,))

        with self.assertRaisesRegex(DividerFormulaError, "D must divide pp"):
            DividerConnectionFormula(
                "zpp_centered_entry_translation", (2, 1, 1), (1, 4, 1)
            ).apply(
                parents, num_slots=12, pp=6,
                group_keys=(0, 0), group_order=(0,))

        with self.assertRaisesRegex(DividerFormulaError, "symmetric centered"):
            DividerConnectionFormula(
                "zpp_centered_entry_translation", (2, 1, 1), (1, 4, 1)
            ).apply(
                [(10, [(slot, slot) for slot in range(6)]),
                 (20, [(slot + 6, slot) for slot in range(6)])],
                num_slots=16, pp=4,
                group_keys=(0, 0), group_order=(0,))

        with self.assertRaisesRegex(DividerFormulaError, "exactly Q parents"):
            DividerConnectionFormula(
                "zpp_centered_entry_translation", (2, 1, 1), (1, 4, 1)
            ).apply(
                [(10, [(0, 0), (1, 0)])], num_slots=16,
                pp=4,
                group_keys=(0,), group_order=(0,))

    def test_zpp_centered_entry_translation_derives_non_unit_sector_stride(self):
        parents = [
            (10, [(slot, slot, 0) for slot in range(6)]),
            (20, [(slot + 6, slot, 1) for slot in range(6)]),
        ]

        branches = DividerConnectionFormula(
            "zpp_centered_entry_translation", (2, 1, 1), (1, 6, 1)
        ).apply(
            parents, num_slots=72, pp=12,
            group_keys=(0, 0), group_order=(0,))

        self.assertEqual([branch.path[0][0] for branch in branches],
                         [2, 68, 50, 44, 26, 20])

    def test_zpp_centered_entry_translation_supports_odd_divider_arithmetic(self):
        branches = DividerConnectionFormula(
            "zpp_centered_entry_translation", (1, 1, 1), (1, 3, 1)
        ).apply(
            [(10, [(slot, slot) for slot in range(3)])],
            num_slots=12, pp=3, group_keys=(0,), group_order=(0,))

        self.assertEqual([branch.path[0][0] for branch in branches],
                         [1, 5, 9])

    def test_zpp_q_pp_p2_manual_candidate_uses_ordered_parent_slices(self):
        parents = [
            (branch_id, [(branch_id * 100 + index, index % 4, branch_id)
                         for index in range(16)])
            for branch_id in range(1, 5)
        ]

        children = DividerConnectionFormula(
            "partition", (2, 1, 2), (2, 2, 2), "piece").apply(parents)

        self.assertEqual([child.source_ids for child in children],
                         [(1,), (2,), (3,), (4,), (1,), (2,), (3,), (4,)])
        self.assertEqual([child.part_index for child in children],
                         [0, 0, 0, 0, 1, 1, 1, 1])
        self.assertEqual([child.path for child in children], [
            path[:8] for _, path in parents
        ] + [
            path[8:] for _, path in parents
        ])

    def test_zpp_q_pp_p2_formula_matches_manual_package_cut_order(self):
        draft_dir = Path(__file__).with_name("pattern_rule_drafts")
        source_name = (
            "ZPP_q-2_pp-4_L-4_Naa-4_Q-2_PP-1_P2-2_Ph-A_Side-insert_"
            "Shifts-0-0-0-0_20260929-090545-046455.json")
        target_name = (
            "ZPP_q-2_pp-4_L-4_Naa-8_Q-2_PP-2_P2-2_Ph-A_Side-insert_"
            "Shifts-0-0-0-0_20260929-090700-346973.json")
        source_package = json.loads(
            (draft_dir / source_name).read_text(encoding="utf-8"))
        target_package = json.loads(
            (draft_dir / target_name).read_text(encoding="utf-8"))
        parents = [
            (branch_id, [(node["slot"], node["layer"])
                         for node in branch["path"]])
            for branch_id, branch in enumerate(source_package["branches"])
        ]

        children = apply_route_formula(
            "zpp_q_pp_p2_parent_slices", parents, (2, 2, 2),
            group_keys=(0, 0, 1, 1), group_order=(0, 1))

        expected = [
            [(node["slot"], node["layer"]) for node in branch["path"]]
            for branch in target_package["branches"]
        ]
        self.assertEqual([child.path for child in children], expected)
        self.assertEqual([child.source_ids for child in children], [
            (0,), (1,), (0,), (1,), (2,), (3,), (2,), (3,)])
        self.assertEqual([child.part_index for child in children],
                         [0, 0, 1, 1, 0, 0, 1, 1])
        self.assertFalse(source_package["certified"])
        self.assertFalse(target_package["certified"])
        self.assertEqual(
            target_package["source_route"]["status"], "unsupported-yet")

    def test_phase_set_local_dividers_preserve_naa(self):
        for global_dividers, set_count, expected in (
                ((2, 8, 1), 2, (4, 4, 1)),
                ((3, 12, 2), 3, (9, 4, 2)),
                ((2, 16, 1), 4, (8, 4, 1))):
            with self.subTest(global_dividers=global_dividers,
                              set_count=set_count):
                local = phase_set_local_dividers(
                    global_dividers, set_count)
                self.assertEqual(local, expected)
                self.assertEqual(math.prod(local), math.prod(global_dividers))

        with self.assertRaisesRegex(DividerFormulaError, 'divisible'):
            phase_set_local_dividers((2, 7, 1), 2)

        binding = ROUTE_FORMULA_BINDINGS['tlp_pp_only_even']
        self.assertEqual(
            binding.resolve_source_dividers((6, 8, 1)), (6, 2, 1))

    def test_slp_q_pp_p2_formula_regroups_complete_parent_blocks(self):
        q, pp, layers = 4, 8, 2
        dividers = (2, 2, 2)
        parents = []
        for cohort in range(2):
            for lane in range(q):
                path = [
                    (cohort * 1000 + lane * 100 + index,
                     index % layers, lane)
                    for index in range(pp * layers)
                ]
                parents.append((cohort * q + lane + 1, path))

        children = slp_q_pp_p2_lane_regroup(
            parents, dividers=dividers, q=q, pp=pp,
            layer_count=layers)

        self.assertEqual(len(children), 2 * 2 * 2)
        self.assertEqual([child.part_index for child in children[:4]],
                         [0, 1, 2, 3])
        self.assertEqual(children[0].source_ids, (1, 2))
        self.assertEqual(
            [node[2] for node in children[0].path[::4]], [0, 1, 1, 0])
        self.assertEqual({len(child.path) for child in children}, {16})
        self.assertEqual(
            sorted(node for child in children for node in child.path),
            sorted(node for _, path in parents for node in path))

    def test_slp_q_pp_p2_formula_requires_two_pass_sector_units(self):
        parents = [
            (index + 1, [(index, layer, index)
                         for layer in range(12)])
            for index in range(8)
        ]
        with self.assertRaisesRegex(DividerFormulaError, 'even number of passes'):
            slp_q_pp_p2_lane_regroup(
                parents, dividers=(2, 2, 2), q=4, pp=6,
                layer_count=2)


class SlpProperQMixedP2Tests(unittest.TestCase):
    def test_mixed_q_pp_p2_parent_regroup_generates_and_validates(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs

        cases = (
            (4, 4, 2, 2, 4, 3),
            (6, 6, 2, 3, 4, 3),
            (8, 8, 2, 4, 4, 3),
            (8, 8, 2, 2, 4, 3),
            (12, 12, 3, 6, 4, 5),
            (12, 12, 3, 2, 4, 5),
            (6, 6, 3, 3, 2, 5),
            (6, 6, 2, 3, 4, 5),
            (6, 6, 3, 3, 4, 5),
            (8, 8, 2, 4, 4, 6),
            (8, 8, 2, 4, 6, 9),
        )
        for q, pp, q_divider, pp_divider, layers, phases in cases:
            factors = (q_divider, pp_divider, 2)
            with self.subTest(q=q, pp=pp, factors=factors, L=layers, m=phases):
                winding, tp, layout = _base_inputs(
                    'SLP', q, 2 * pp, layers, math.prod(factors),
                    factors, phases)
                decision = gw.resolve_pattern_route(
                    'SLP', winding, factors, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                self.assertEqual(decision.rule_id,
                                 'slp_q_pp_p2_parent_cut')

                starts, database = gw.get_winding_layout(
                    'SLP', tp, winding, layout)

                self.assertEqual(starts, [path[0] for _, path in database])
                self.assertEqual(len(database), winding.ab * phases)
                self.assertEqual(
                    {len(path) for _, path in database},
                    {winding.num_slots * layers // (winding.ab * phases)})
                self.assertTrue(database.layout_report['layout_retained'])
                if phases == 3:
                    identity = analyze_pattern_identity(
                        'SLP', database, winding, layout)
                else:
                    # Multi-set arrays have local q and slot geometry; the
                    # global-coordinate identity analyzer is not authoritative.
                    identity = gw._analyze_pattern_identity_for_sets(
                        'SLP', database, winding, layout)
                self.assertEqual(identity['status'], 'valid', identity)
                self.assertEqual(
                    database.layout_report['pattern_identity']['status'],
                    'valid')
                validation_views = (
                    gw._three_phase_set_views(database, winding, layout)
                    if phases > 3 else ((database, winding, layout),))
                for local_database, local_winding, local_layout in validation_views:
                    gw.validate_slp_q_pp_p2_parent_cut(
                        local_database, local_winding, local_layout)

                if phases < 6:
                    lane_width = q // q_divider
                    sectors_per_lane = pp // pp_divider
                    for _, path in database:
                        lane_counts = Counter(node[2] for node in path)
                        self.assertEqual(len(lane_counts), lane_width)
                        self.assertEqual(set(lane_counts.values()),
                                         {sectors_per_lane * layers})
                        self.assertEqual(
                            min(lane_counts) // lane_width,
                            max(lane_counts) // lane_width)

    def test_mixed_q_pp_p2_keeps_non_formula_boundaries_closed(self):
        from pattern_rule_workbench import _base_inputs

        cases = (
            (8, 8, 2, 8, 4, 'unsupported-yet'),  # odd pp/D=1; no formula
            (6, 6, 2, 2, 4, 'rejected'),  # existing classifier-default failure
            (6, 6, 2, 4, 4, 'unsupported-yet'),  # D does not divide pp
        )
        for q, pp, q_divider, pp_divider, layers, admission in cases:
            factors = (q_divider, pp_divider, 2)
            with self.subTest(q=q, pp=pp, factors=factors):
                winding, tp, layout = _base_inputs(
                    'SLP', q, 2 * pp, layers, math.prod(factors), factors, 3)
                decision = gw.resolve_pattern_route(
                    'SLP', winding, factors, tp, layout)
                self.assertEqual(decision.status, 'disabled')
                self.assertEqual(decision.admission, admission)

    def test_mixed_q_pp_p2_keeps_insert_guard_and_checks_manual_tp_output(self):
        from pattern_rule_workbench import _base_inputs

        factors = (2, 2, 2)
        winding, tp, layout = _base_inputs(
            'SLP', 4, 8, 4, math.prod(factors), factors, 3)
        layout.inlet_from_weld_side = 1
        decision = gw.resolve_pattern_route('SLP', winding, factors, tp, layout)
        self.assertEqual(decision.status, 'disabled')

        winding, tp, layout = _base_inputs(
            'SLP', 4, 8, 4, math.prod(factors), factors, 3)
        tp.uni_tp = 1
        decision = gw.resolve_pattern_route('SLP', winding, factors, tp, layout)
        self.assertEqual(decision.status, 'enabled')
        with self.assertRaisesRegex(ValueError, 'parent order'):
            gw.get_winding_layout('SLP', tp, winding, layout)

    def test_tsp_pp_p2_sector_formula_is_parameterized_by_divider_tuple(self):
        formula = tsp_pp_p2_sector_branches(2, 4, (1, 4, 2), 4, 3)

        self.assertEqual(len(formula), 24)
        self.assertEqual(
            [branch.path[0] for branch in formula[:8]],
            [(0, 0, 0), (0, 3, 0), (12, 0, 0), (12, 3, 0),
             (25, 0, 1), (25, 3, 1), (37, 0, 1), (37, 3, 1)])
        self.assertTrue(tsp_pp_p2_sector_residues_are_complete(
            2, 4, (1, 4, 2), 4))
        self.assertEqual(
            dict(tsp_pp_p2_sector_lane_residues(2, 4, (1, 4, 2), 4)),
            {0: (0, 2, 1, 3), 1: (2, 0, 3, 1)})
        self.assertFalse(tsp_pp_p2_sector_residues_are_complete(
            2, 4, (1, 2, 2), 4))
        with self.assertRaisesRegex(DividerFormulaError, 'dividers \(1,D,2\)'):
            tsp_pp_p2_sector_lane_residues(2, 4, (2, 2, 2), 4)

    def test_zpp_sector_stride_is_minimal_and_covers_the_bounded_gaps(self):
        expected_new_strides = {
            (3, 2): 2, (3, 5): 2, (5, 3): 2,
            (6, 2): 5, (6, 5): 5, (7, 4): 2,
            (9, 2): 2, (9, 5): 2, (10, 3): 3,
        }
        for divider in range(2, 11):
            for repetitions in range(1, 7):
                with self.subTest(D=divider, r=repetitions):
                    stride = zpp_indexed_sector_stride(divider, repetitions)
                    self.assertEqual(math.gcd(stride, divider), 1)
                    self.assertEqual(
                        math.gcd(divider, 2 * repetitions * stride - 1), 1)
                    if math.gcd(divider, 2 * repetitions - 1) == 1:
                        self.assertEqual(stride, 1)
                    elif (divider, repetitions) in expected_new_strides:
                        self.assertEqual(
                            stride, expected_new_strides[(divider, repetitions)])

        actual_gaps = {
            (divider, repetitions)
            for divider in range(2, 11)
            for repetitions in range(1, 7)
            if math.gcd(divider, 2 * repetitions - 1) != 1
        }
        self.assertEqual(actual_gaps, set(expected_new_strides))

    def test_zpp_indexed_translation_applies_coprime_sector_stride(self):
        parents = [(10, [(0, 0)]), (20, [(1, 0)]), (30, [(2, 0)])]
        result = apply_route_formula(
            'zpp_pp_only_indexed_translation', parents, (1, 3, 1),
            num_slots=9, group_keys=(0, 0, 0), group_order=(0,),
            sector_stride=2, sector_repetitions=2)

        self.assertEqual([branch.part_index for branch in result], [0, 1, 2])
        self.assertEqual([branch.path for branch in result], [
            [(0, 0)], [(7, 0)], [(5, 0)],
        ])
        with self.assertRaisesRegex(DividerFormulaError,
                                    'factor-derived ZPP stride'):
            apply_route_formula(
                'zpp_pp_only_indexed_translation', parents, (1, 3, 1),
                num_slots=9, group_keys=(0, 0, 0), group_order=(0,),
                sector_stride=1, sector_repetitions=2)

    def test_partition_formula_uses_each_divider_factor(self):
        branches = [(1, [(0, 0, 0), (1, 0, 1),
                         (2, 0, 0), (3, 0, 1)])]
        cases = (
            ((1, 1, 1), (2, 1, 1)),
            ((1, 2, 1), (1, 4, 1)),
            ((1, 1, 1), (1, 1, 2)),
        )
        for source, target in cases:
            with self.subTest(source=source, target=target):
                result = DividerConnectionFormula(
                    'partition', source, target).apply(branches)
                self.assertEqual([row.path for row in result],
                                 [branches[0][1][:2], branches[0][1][2:]])

    def test_parent_partition_supports_source_and_piece_order(self):
        branches = [
            (10, [(0, 0, 0), (1, 0, 1), (2, 0, 0), (3, 0, 1)]),
            (20, [(4, 0, 0), (5, 0, 1), (6, 0, 0), (7, 0, 1)]),
        ]
        source_order = DividerConnectionFormula(
            'partition', (1, 1, 2), (1, 4, 1), 'source').apply(branches)
        piece_order = apply_route_formula(
            'cp_q_pp_full_parent_slices', branches, (1, 4, 1))
        self.assertEqual([row.source_ids for row in source_order],
                         [(10,), (10,), (20,), (20,)])
        self.assertEqual([row.source_ids for row in piece_order],
                         [(10,), (20,), (10,), (20,)])
        self.assertEqual([row.part_index for row in piece_order], [0, 0, 1, 1])

    def test_cp_q_pp_p2_parent_slice_binding_carries_q_and_p2(self):
        route = 'cp_q_pp_p2_parent_slices'
        binding = ROUTE_FORMULA_BINDINGS[route]
        self.assertEqual(binding.resolve_source_dividers((2, 3, 2)),
                         (2, 1, 2))

        branches = [
            (10, [(slot, 0, slot % 2) for slot in range(6)]),
            (20, [(slot + 6, 0, slot % 2) for slot in range(6)]),
        ]
        pieces = apply_route_formula(route, branches, (2, 3, 2))
        self.assertEqual([piece.source_ids for piece in pieces],
                         [(10,), (10,), (10,), (20,), (20,), (20,)])
        self.assertEqual([piece.part_index for piece in pieces],
                         [0, 1, 2, 0, 1, 2])
        self.assertEqual([piece.path for piece in pieces], [
            branches[0][1][0:2], branches[0][1][2:4], branches[0][1][4:6],
            branches[1][1][0:2], branches[1][1][2:4], branches[1][1][4:6],
        ])

    def test_adjacent_join_uses_the_three_factor_ratio_and_keeps_parent_order(self):
        branches = [(index, [(index, 0, index % 2)]) for index in range(4)]
        joined = apply_route_formula(
            'cp_q_only_pair_join', branches, (2, 1, 1))
        self.assertEqual([row.source_ids for row in joined], [(0, 1), (2, 3)])
        self.assertEqual([row.path for row in joined], [
            [(0, 0, 0), (1, 0, 1)], [(2, 0, 0), (3, 0, 1)]])
        self.assertEqual(
            ROUTE_FORMULA_BINDINGS['cp_q_only_pair_join'].resolve_source_dividers(
                (2, 1, 1)),
            (2, 1, 2),
        )

    def test_uwp_q_only_join_uses_parameterized_divider_binding(self):
        parents = [
            (10, [(0, 0)]), (20, [(1, 0)]),
            (11, [(2, 0)]), (21, [(3, 0)]),
        ]

        pieces = apply_route_formula(
            'uwp_q_only_series', parents, (2, 1, 1))

        self.assertEqual([piece.source_ids for piece in pieces],
                         [(10, 20), (11, 21)])
        self.assertEqual([piece.path for piece in pieces],
                         [[(0, 0), (1, 0)], [(2, 0), (3, 0)]])

    def test_slp_single_sector_weld_rotation_derives_step_from_dividers(self):
        cases = ((4, 2, 2, 3), (6, 3, 2, 5), (6, 2, 3, 7))
        for q, q_divider, pp, phases in cases:
            with self.subTest(q=q, Q=q_divider, pp=pp, m=phases):
                num_slots = 2 * pp * phases * q
                closing_step = phases * q - (q // q_divider - 1)
                path = [(0, 0, 0), (3, 1, 1),
                        ((num_slots - closing_step) % num_slots, 0, 0)]
                rotated, actual_step = slp_q_pp_single_sector_weld_rotation(
                    [(17, path)], dividers=(q_divider, pp, 1),
                    q=q, pp=pp, phase_count=phases, num_slots=num_slots)

                self.assertEqual(actual_step, closing_step)
                self.assertEqual(rotated[0].source_ids, (17,))
                self.assertEqual(rotated[0].path, path[1:] + path[:1])

    def test_slp_single_sector_weld_rotation_rejects_repeated_pp_sectors(self):
        with self.assertRaisesRegex(DividerFormulaError,
                                   'one PP sector per child'):
            slp_q_pp_single_sector_weld_rotation(
                [(1, [(0, 0, 0), (1, 1, 1)])],
                dividers=(2, 2, 1), q=4, pp=4, phase_count=3,
                num_slots=48)

    def test_zpp_indexed_translation_resolves_cross_factor_and_groups_in_order(self):
        parents = [
            (10, [(0, 0), (1, 1)]), (20, [(1, 0), (2, 1)]),
            (30, [(2, 0), (3, 1)]), (40, [(3, 0), (4, 1)]),
        ]
        binding = ROUTE_FORMULA_BINDINGS[
            'zpp_pp_only_indexed_translation']
        self.assertEqual(
            binding.resolve_source_dividers((1, 2, 1)), (2, 1, 1))

        result = apply_route_formula(
            'zpp_pp_only_indexed_translation', parents, (1, 2, 1),
            num_slots=8, group_keys=(0, 1, 0, 1), group_order=(0, 1))

        self.assertEqual([row.source_ids for row in result],
                         [(10,), (30,), (20,), (40,)])
        self.assertEqual([row.part_index for row in result], [0, 1, 0, 1])
        self.assertEqual([row.path for row in result], [
            parents[0][1], [(6, 0), (7, 1)],
            parents[1][1], [(7, 0), (0, 1)],
        ])

    def test_zpp_indexed_translation_requires_complete_groups_and_integer_sectors(self):
        parents = [(10, [(0, 0)]), (20, [(1, 0)])]
        with self.assertRaises(DividerFormulaError):
            apply_route_formula(
                'zpp_pp_only_indexed_translation', parents, (1, 2, 1),
                num_slots=8, group_keys=(0, 1), group_order=(0, 1))
        with self.assertRaises(DividerFormulaError):
            apply_route_formula(
                'zpp_pp_only_indexed_translation', parents, (1, 2, 1),
                num_slots=7, group_keys=(0, 0), group_order=(0,))
        with self.assertRaisesRegex(DividerFormulaError, 'stride coprime'):
            apply_route_formula(
                'zpp_pp_only_indexed_translation',
                [(10, [(0, 0)]), (20, [(1, 0)]),
                 (30, [(2, 0)]), (40, [(3, 0)])],
                (1, 4, 1), num_slots=16,
                group_keys=(0, 0, 0, 0), group_order=(0,),
                sector_stride=2)

    def test_identity_formula_preserves_order_and_requires_equal_naa(self):
        parents = [
            (10, [(0, 0, 0), (2, 1, 0)]),
            (20, [(4, 0, 1), (6, 1, 1)]),
        ]
        result = DividerConnectionFormula(
            'identity', (2, 1, 2), (1, 4, 1)).apply(parents)

        self.assertEqual([item.source_ids for item in result], [(10,), (20,)])
        self.assertEqual([item.part_index for item in result], [0, 0])
        self.assertEqual([item.path for item in result], [path for _, path in parents])
        with self.assertRaisesRegex(DividerFormulaError, 'same Naa'):
            DividerConnectionFormula(
                'identity', (2, 1, 2), (1, 2, 1)).apply(parents)

    def test_tsp_identity_binding_derives_the_full_q_p2_parent(self):
        binding = ROUTE_FORMULA_BINDINGS[
            'tsp_pp_only_q_p2_identity']

        self.assertEqual(binding.operation, 'identity')
        self.assertEqual(
            binding.resolve_source_dividers((1, 8, 1)), (4, 1, 2))
        self.assertEqual(
            binding.resolve_source_dividers((1, 4, 1)), (2, 1, 2))

    def test_formula_rejects_non_integral_factor_changes(self):
        with self.assertRaises(DividerFormulaError):
            DividerConnectionFormula(
                'partition', (1, 1, 1), (Fraction(3, 2), 1, 1)
            ).apply([(1, [(0, 0, 0), (1, 0, 1)])])

    def test_cp_formulas_derive_weave_and_slot_offsets(self):
        layer_count = 2
        # Unique conductor records make the exact pass order easy to verify.
        parents = [(index + 1, [(index * 100 + item, 0, item % 2)
                                for item in range(8)])
                   for index in range(4)]
        woven = cp_four_pass_weave(parents, layer_count)
        p1, p2, p3, p4 = [path for _, path in parents]
        self.assertEqual(woven, [
            p1[:4] + p2 + p1[4:],
            p3[6:] + p4[4:] + p3[4:6] + p4[2:4] + p3[:4] + p4[:2],
        ])

        paths, offsets = cp_parent_half_translation(
            [(0, 0, 1), (2, 1, 0), (5, 0, 1)],
            num_slots=24, pole_pitch=6)
        self.assertEqual(offsets, (1, 5, 7, 11))
        self.assertEqual(paths[0][0], (1, 0, 1))

    def test_spiral_parent_formula_shares_q_pp_parameters_across_orders(self):
        def parent_path(lanes):
            return [node for block, lane in enumerate(lanes)
                    for node in ((2 * block, 0, lane),
                                 (2 * block + 1, 1, lane))]

        lane_major = spiral_q_pp_parent_cut(
            parent_path((0, 0, 1, 1, 2, 2, 3, 3)),
            q_divider=2, pp_divider=4, q=4, pp=8, layer_count=1,
            block_order='lane_major')
        sector_major = spiral_q_pp_parent_cut(
            parent_path((0, 2, 1, 3, 0, 2, 1, 3)),
            q_divider=2, pp_divider=4, q=4, pp=8, layer_count=1,
            block_order='sector_major')
        self.assertEqual([[block[0][2] for block in
                           [path[i:i + 2] for i in range(0, len(path), 2)]]
                          for path in lane_major],
                         [[0, 0, 1, 1], [2, 2, 3, 3]])
        self.assertEqual([[block[0][2] for block in
                           [path[i:i + 2] for i in range(0, len(path), 2)]]
                          for path in sector_major],
                         [[0, 1, 0, 1], [2, 3, 2, 3]])


class SpiralQppParentCutTests(unittest.TestCase):
    def test_public_route_accepts_ui_namedtuple_for_supported_phase_counts(self):
        from pattern_rule_workbench import _base_inputs

        for pattern, phases in (('SSP', 3), ('SLP', 5),
                                ('SLP', 6), ('SSP', 7),
                                ('SLP', 9), ('SLP', 12)):
            with self.subTest(pattern=pattern, m=phases):
                factors = (1, 1, 1)
                layers = (2 * (phases // 3)
                          if phases % 3 == 0 else 2)
                winding, tp, layout = _base_inputs(
                    pattern, 4, 4, layers, 1, factors, phases)
                WindingParaGroup = namedtuple(
                    'WindingParaGroup', vars(winding).keys())
                ui_winding = WindingParaGroup(**vars(winding))
                decision = gw.resolve_pattern_route(
                    pattern, ui_winding, factors, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                starts, database = gw.get_winding_layout(
                    pattern, tp, ui_winding, layout)
                self.assertEqual(starts, [path[0] for _, path in database])
                self.assertEqual(len(database), phases)

    def test_public_proper_q_pp_cut_preserves_complete_spiral_paths(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs
        from phase_topology import phase_map

        # The first two paths are the smallest two-layer distinction; the
        # remaining cases exercise multi-sector SSP and a new odd phase count.
        cases = (
            ('SSP', 4, 2, 2, 2, 2, 3),
            ('SLP', 4, 2, 2, 2, 2, 5),
            ('SSP', 6, 3, 10, 2, 12, 7),
            ('SLP', 6, 3, 6, 6, 4, 9),
            ('SSP', 8, 4, 2, 2, 4, 9),
            ('SLP', 8, 4, 2, 2, 4, 9),
            ('SLP', 4, 2, 4, 2, 4, 3),
            ('SLP', 6, 2, 6, 2, 2, 5),
        )
        for pattern, q, Q, pp, D, layers, phases in cases:
            with self.subTest(pattern=pattern, q=q, Q=Q, pp=pp, D=D,
                              L=layers, m=phases):
                factors = (Q, D, 1)
                winding, tp, layout = _base_inputs(
                    pattern, q, 2 * pp, layers, Q * D, factors, phases)
                decision = gw.resolve_pattern_route(
                    pattern, winding, factors, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                starts, database = gw.get_winding_layout(
                    pattern, tp, winding, layout)
                self.assertEqual(starts, [path[0] for _, path in database])
                self.assertEqual(len(database), phases * Q * D)
                self.assertEqual({len(path) for _, path in database},
                                 {winding.num_slots * layers // (phases * Q * D)})
                records = phase_map(winding.num_slots, 2 * pp, layers,
                                    layout.phase_shift_list, phases)
                report = validate_branches(
                    [path for _, path in database], records,
                    winding.num_slots, 2 * pp, winding.ab, phases)
                self.assertTrue(report['layout_retained'], report)
                self.assertTrue(report['topology_valid'], report)
                identity = analyze_pattern_identity(
                    pattern, database, winding, layout)
                self.assertEqual(identity['status'], 'valid', identity)
                gw.validate_pp_only_spiral(pattern, database, winding, layout)
                if pattern == 'SLP':
                    gw.validate_slp_factor_route(database, winding, layout)
                source_sectors = pp // D
                for group_start in range(0, len(database), Q):
                    lane_sets = []
                    for _, path in database[group_start:group_start + Q]:
                        lanes = Counter(node[2]
                                        for node in path[::2 * layers])
                        self.assertEqual(set(lanes.values()), {source_sectors})
                        lane_sets.append(set(lanes))
                    self.assertEqual(set.union(*lane_sets), set(range(q)))
                    self.assertEqual(sum(map(len, lane_sets)), q)

    def test_slp_multisector_regroups_whole_blocks_in_parent_order(self):
        from pattern_rule_workbench import _base_inputs

        factors = (2, 2, 1)
        winding, tp, layout = _base_inputs('SLP', 4, 8, 4, 4, factors, 3)
        decision = gw.resolve_pattern_route('SLP', winding, factors,
                                            tp, layout)
        self.assertEqual(decision.status, 'enabled', decision.reason)
        self.assertEqual(decision.rule_id, 'slp_q_pp_parent_cut')
        _, children = gw.get_winding_layout('SLP', tp, winding, layout)
        parent_winding, _, _ = _base_inputs('SLP', 4, 8, 4, 2,
                                           (1, 2, 1), 3)
        _, parents = gw.get_winding_layout('SLP', tp, parent_winding, layout)
        blocks = [parents[0][1][index:index + 8]
                  for index in range(0, len(parents[0][1]), 8)]
        self.assertEqual(children[0][1],
                         [node for block in (blocks[0], blocks[1],
                                             blocks[6], blocks[7])
                          for node in block])
        self.assertEqual(children[1][1],
                         [node for block in blocks[2:6] for node in block])

    def test_slp_proper_q_pp_single_sector_supports_public_weld_rotation(self):
        from pattern_rule_workbench import _base_inputs
        from pattern_identity import pole_region_crossings

        cases = (
            (4, 2, 2, 4, 3),
            (6, 3, 2, 4, 3),
            (6, 2, 3, 4, 3),
            (6, 2, 3, 8, 7),
            (8, 4, 2, 8, 3),
            (8, 2, 4, 4, 5),
            (9, 3, 3, 8, 3),
            (4, 4, 2, 8, 6),
        )
        for q, Q, pp, layers, phases in cases:
            with self.subTest(q=q, Q=Q, pp=pp, L=layers, m=phases):
                factors = (Q, pp, 1)
                winding, tp, insert_layout = _base_inputs(
                    'SLP', q, 2 * pp, layers, Q * pp, factors, phases)
                insert_decision = gw.resolve_pattern_route(
                    'SLP', winding, factors, tp, insert_layout)
                self.assertEqual(insert_decision.status, 'enabled',
                                 insert_decision.reason)
                _, insert_database = gw.get_winding_layout(
                    'SLP', tp, winding, insert_layout)

                _weld_winding, weld_tp, weld_layout = _base_inputs(
                    'SLP', q, 2 * pp, layers, Q * pp, factors, phases)
                weld_layout.inlet_from_weld_side = 1
                weld_decision = gw.resolve_pattern_route(
                    'SLP', _weld_winding, factors, weld_tp, weld_layout)
                self.assertEqual(weld_decision.status, 'enabled',
                                 weld_decision.reason)
                self.assertEqual(weld_decision.rule_id,
                                 'slp_q_pp_parent_cut')
                starts, weld_database = gw.get_winding_layout(
                    'SLP', weld_tp, _weld_winding, weld_layout)

                self.assertEqual(starts,
                                 [path[0] for _, path in weld_database])
                self.assertEqual(
                    [path for _, path in weld_database],
                    [path[1:] + path[:1]
                     for _, path in insert_database])
                travel = weld_database.signed_travel
                self.assertEqual(set(travel),
                                 {branch_id for branch_id, _ in weld_database})
                pole_region_width = phases * q
                for branch_id, path in weld_database:
                    self.assertEqual(len(travel[branch_id]), len(path) - 1)
                    for (start, end, step) in zip(
                            path, path[1:], travel[branch_id]):
                        self.assertEqual(
                            (start[0] + step) % _weld_winding.num_slots,
                            end[0])
                        self.assertLessEqual(
                            pole_region_crossings(
                                start[0], step, pole_region_width), 1)
                self.assertEqual(
                    gw._analyze_pattern_identity_for_sets(
                        'SLP', weld_database, _weld_winding, weld_layout)[
                            'status'],
                    'valid')
                if phases % 3:
                    gw.validate_pp_only_spiral(
                        'SLP', weld_database, _weld_winding, weld_layout)
                    gw.validate_slp_factor_route(
                        weld_database, _weld_winding, weld_layout)

    def test_slp_proper_q_pp_weld_rotation_keeps_configuration_guards(self):
        from pattern_rule_workbench import _base_inputs

        factors = (2, 2, 1)
        for setting in ('shift', 'times', 'radial', 'inlet_adjustment'):
            with self.subTest(setting=setting):
                winding, tp, layout = _base_inputs(
                    'SLP', 4, 4, 4, 4, factors, 3)
                layout.inlet_from_weld_side = 1
                if setting == 'shift':
                    layout.phase_shift_list = [0, 1, 0, 1]
                elif setting == 'times':
                    tp.tp_type, tp.tp_times = 'Times', 1
                elif setting == 'radial':
                    layout.radial_shift = 1
                else:
                    layout.inlet_index_adjustments_phase_a = [1]
                decision = gw.resolve_pattern_route(
                    'SLP', winding, factors, tp, layout)
                self.assertEqual(decision.status,
                                 'enabled' if setting == 'times' else 'disabled',
                                 decision.reason)

    def test_slp_proper_q_pp_weld_rotation_rejects_multiple_sectors(self):
        from pattern_rule_workbench import _base_inputs

        factors = (2, 2, 1)
        winding, tp, layout = _base_inputs(
            'SLP', 4, 8, 4, 4, factors, 3)
        layout.inlet_from_weld_side = 1
        decision = gw.resolve_pattern_route(
            'SLP', winding, factors, tp, layout)
        self.assertEqual(decision.status, 'disabled')
        self.assertEqual(decision.required_inlet, 'insert')

    def test_parent_cut_configuration_is_guarded_for_every_odd_phase(self):
        from pattern_rule_workbench import _base_inputs

        for pattern, phases in (('SSP', 3), ('SSP', 7),
                                ('SLP', 5), ('SLP', 9)):
            for setting in ('shift', 'times'):
                with self.subTest(pattern=pattern, m=phases,
                                  setting=setting):
                    factors = (2, 2, 1)
                    winding, tp, layout = _base_inputs(
                        pattern, 4, 4, 4, 4, factors, phases)
                    if setting == 'shift':
                        layout.phase_shift_list = [0, 1, 0, 1]
                    else:
                        tp.tp_type, tp.tp_times = 'Times', 1
                    decision = gw.resolve_pattern_route(
                        pattern, winding, factors, tp, layout)
                    self.assertEqual(decision.status,
                                     'disabled' if setting == 'shift' or phases == 9
                                     else 'enabled')

    def test_existing_slp_multisector_default_is_preserved(self):
        from pattern_rule_workbench import _base_inputs

        factors = (2, 3, 1)
        winding, tp, layout = _base_inputs('SLP', 4, 12, 4, 6,
                                           factors, 5)
        decision = gw.resolve_pattern_route('SLP', winding, factors,
                                            tp, layout)
        self.assertEqual(decision.status, 'enabled', decision.reason)
        self.assertEqual(decision.rule_id, 'slp_default')
        _, database = gw.get_winding_layout('SLP', tp, winding, layout)
        self.assertEqual(len(database), 5 * 6)


class MultiplesOfThreePhaseSupportTests(unittest.TestCase):
    def test_route_rejects_layer_counts_that_cannot_split_three_phase_sets(self):
        from pattern_rule_workbench import _base_inputs

        for phases, layers, set_count in ((6, 5, 2), (9, 4, 3), (12, 6, 4)):
            with self.subTest(phases=phases, layers=layers):
                winding, tp, layout = _base_inputs(
                    'SLP', 4, 4, layers, 8, (4, 2, 1), phases)
                decision = gw.resolve_pattern_route(
                    'SLP', winding, (4, 2, 1), tp, layout)
                self.assertEqual(decision.status, 'disabled')
                self.assertEqual(
                    decision.rule_id, 'unsupported_phase_layer_allocation')
                self.assertIn(f'divisible by {set_count}', decision.reason)

    def test_multiples_of_three_phase_routes_use_valid_three_phase_sets(self):
        from pattern_rule_workbench import _base_inputs

        factors = (4, 2, 1)
        for phases in (6, 9, 12):
            with self.subTest(m=phases):
                layers = 6 if phases == 6 else 2 * (phases // 3)
                pattern = 'SLP'
                if phases == 6:
                    slp_winding, slp_tp, slp_layout = _base_inputs(
                        'SLP', 4, 4, layers, 8, factors, phases)
                    slp_decision = gw.resolve_pattern_route(
                        'SLP', slp_winding, factors, slp_tp, slp_layout)
                    self.assertEqual(slp_decision.status, 'disabled')
                    self.assertIn('SLP welds reverse travel', slp_decision.reason)
                    pattern = 'SSP'
                winding, tp, layout = _base_inputs(
                    pattern, 4, 4, layers, 8, factors, phases)
                self.assertEqual(winding.num_slots, phases * 16)
                if phases == 6:
                    self.assertEqual(winding.num_slots, 96)
                decision = gw.resolve_pattern_route(
                    pattern, winding, factors, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                starts, database = gw.get_winding_layout(
                    pattern, tp, winding, layout)
                self.assertEqual(starts, [path[0] for _, path in database])
                self.assertEqual(len(database), phases * 8)
                self.assertEqual(
                    database.phase_set_array['slot_offsets'],
                    tuple(8 * group for group in range(phases // 3)))
                self.assertAlmostEqual(
                    database.phase_set_array['electrical_step_degrees'],
                    360 / phases)

                positions = [(slot, layer) for _, path in database
                             for slot, layer, _ in path]
                self.assertEqual(len(positions), len(set(positions)))
                self.assertEqual(len(positions), winding.num_slots * layers)
                records = phase_map(
                    winding.num_slots, winding.num_poles, winding.num_layers,
                    layout.phase_shift_list, phases)
                phase_by_position = {
                    (slot, layer): phase
                    for slot, layer, phase, _ in records
                }
                self.assertTrue(all(
                    len({phase_by_position[node[:2]] for node in path}) == 1
                    for _, path in database))
                report = validate_branches(
                    [path for _, path in database], records,
                    winding.num_slots, winding.num_poles, winding.ab, phases)
                self.assertTrue(report['layout_retained'], report)
                self.assertTrue(report['topology_valid'], report)
                electrical = electrical_summary(
                    records, winding.num_slots, winding.num_poles, phases)
                self.assertTrue(electrical['balanced'], electrical)
                self.assertEqual(len(electrical['sets']), phases // 3)
                identity = gw._analyze_pattern_identity_for_sets(
                    pattern, database, winding, layout)
                expected_identity = 'unverified' if phases == 6 else 'valid'
                self.assertEqual(identity['status'], expected_identity, identity)
                self.assertEqual(len(identity['phase_sets']), phases // 3)
                if phases == 6:
                    self.assertEqual(
                        identity['phase_sets'][0]['identity_confidence'],
                        'legacy-odd-layer')
                    self.assertEqual(
                        identity['phase_sets'][0]['ordered_qualification'],
                        'unsupported-domain')
                self.assertEqual(
                    database.layout_report['pattern_identity']['status'],
                    expected_identity)

    def test_triplet_array_generation_extends_beyond_twelve_phases(self):
        from pattern_rule_workbench import _base_inputs

        for phases in (15, 18):
            with self.subTest(m=phases):
                layers = 2 * (phases // 3)
                factors = (1, 1, 1)
                winding, tp, layout = _base_inputs(
                    'SSP', 4, 4, layers, 1, factors, phases)
                decision = gw.resolve_pattern_route(
                    'SSP', winding, factors, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                _, database = gw.get_winding_layout(
                    'SSP', tp, winding, layout)
                self.assertEqual(len(database), phases)
                self.assertEqual(
                    database.phase_set_array['slot_offsets'],
                    tuple(8 * group for group in range(phases // 3)))
                self.assertAlmostEqual(
                    database.phase_set_array['electrical_step_degrees'],
                    360 / phases)
                self.assertEqual(
                    database.layout_report['pattern_identity']['status'],
                    'valid')

    def test_local_three_phase_constructor_can_differ_from_global_q_route(self):
        from pattern_rule_workbench import _base_inputs

        cases = (
            # Global half-q maps to an integer local q in each 3-phase set.
            ('BWP', Fraction(1, 2), 4, 4, 2, (1, 2, 1), 6, None),
            # SSP has no global half-q route; its local integer-q formula is valid.
            ('SSP', Fraction(1, 2), 4, 4, 1, (1, 1, 1), 6, None),
        )
        for pattern, q, poles, layers, naa, factors, phases, local_route in cases:
            with self.subTest(pattern=pattern, q=q):
                winding, tp, layout = _base_inputs(
                    pattern, q, poles, layers, naa, factors, phases)
                decision = gw.resolve_pattern_route(
                    pattern, winding, factors, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                starts, database = gw.get_winding_layout(
                    pattern, tp, winding, layout, allow_candidate=True)
                self.assertEqual(starts, [path[0] for _, path in database])
                self.assertTrue(all(
                    item['route_name'] == local_route
                    for item in database.phase_set_array['routes']))
                self.assertTrue(database.layout_report['layout_retained'])
                self.assertTrue(database.layout_report['topology_valid'])

    def test_integer_q_divider_is_checked_against_each_local_three_phase_set(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'BWP', 1, 4, 4, 2, (2, 1, 1), 6)
        decision = gw.resolve_pattern_route(
            'BWP', winding, (2, 1, 1), tp, layout)
        self.assertEqual(decision.status, 'enabled', decision.reason)
        _, database = gw.get_winding_layout(
            'BWP', tp, winding, layout, allow_candidate=True)
        self.assertEqual(len(database), 12)
        self.assertEqual(
            [item['route_name'] for item in database.phase_set_array['routes']],
            [None, None])
        self.assertTrue(database.layout_report['topology_valid'])

    def test_local_pattern_failures_still_reject_the_complete_array(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'SLP', 4, 4, 6, 8, (4, 2, 1), 6)
        decision = gw.resolve_pattern_route(
            'SLP', winding, (4, 2, 1), tp, layout)
        self.assertEqual(decision.status, 'disabled')
        self.assertIn('SLP welds reverse travel', decision.reason)

    def test_multiphase_phase_division_uses_the_shared_grouped_map(self):
        for phases in (6, 9, 12):
            with self.subTest(m=phases):
                set_count = phases // 3
                poles = 4
                slots = phases * poles // 2
                layers = 2 * set_count
                shifts = [0, 1] * set_count
                winding = SimpleNamespace(
                    q=Fraction(slots, poles * phases), num_slots=slots,
                    num_poles=poles, num_layers=layers, num_phases=phases)
                cond_info = gw.Winding_Phase_division(
                    winding, SimpleNamespace(phase_shift_list=shifts),
                    log=lambda _message: None)
                records = phase_map(slots, poles, layers, shifts, phases)
                self.assertEqual(
                    {(row[0], row[1], row[2]) for row in cond_info},
                    {(slot, layer, phase)
                     for slot, layer, phase, _sign in records})
                sign_by_position = {
                    (slot, layer): sign
                    for slot, layer, _phase, sign in records
                }
                self.assertTrue(all(
                    sign_by_position[row[:2]] == (-1) ** (row[6] + row[2])
                    for row in cond_info))
                counts = Counter(row[2] for row in cond_info)
                self.assertEqual(set(counts), set(range(phases)))
                self.assertEqual(len(set(counts.values())), 1)

    def test_fractional_multiphase_division_uses_local_three_phase_q(self):
        can_divide, q_fraction, pole_unit = gw.can_phase_division(12, 4, 6)
        self.assertTrue(can_divide)
        self.assertEqual(q_fraction, (1, 2))
        self.assertEqual(pole_unit, 1)
        self.assertFalse(gw.can_phase_division(6, 4, 6)[0])


class BwpOddPhaseMixedDividerTests(unittest.TestCase):
    def test_proper_q_pp_route_uses_phase_scaled_wave_pitch(self):
        from pattern_rule_workbench import _base_inputs
        from phase_topology import phase_map

        cases = ((4, 2, 4, 5, 2, 2), (6, 4, 12, 7, 3, 2),
                 (4, 10, 2, 5, 2, 2))
        for q, pp, layers, phases, Q, D in cases:
          for shifted in (False, True):
            with self.subTest(q=q, pp=pp, layers=layers, phases=phases,
                              shifted=shifted):
                factors = (Q, D, 1)
                winding, tp, layout = _base_inputs(
                    'BWP', q, 2 * pp, layers, Q * D, factors, phases)
                if shifted:
                    layout.phase_shift_pattern = 'Normal'
                    layout.phase_shift_list = [0, 1] * (layers // 2)
                decision = gw.resolve_pattern_route(
                    'BWP', winding, factors, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                starts, database = gw.get_winding_layout(
                    'BWP', tp, winding, layout, allow_candidate=True)
                self.assertEqual(starts, [path[0] for _, path in database])
                self.assertTrue(database.layout_report['layout_retained'])
                self.assertEqual(len(database), phases * Q * D)
                self.assertEqual({len(path) for _, path in database},
                                 {winding.num_slots * layers // (phases * Q * D)})
                positions = [(slot, layer) for _, path in database
                             for slot, layer, _ in path]
                self.assertEqual(len(positions), len(set(positions)))
                self.assertEqual(len(positions), winding.num_slots * layers)
                phase_by_position = {(slot, layer): phase for slot, layer,
                                     phase, _ in phase_map(
                                         winding.num_slots, 2 * pp, layers,
                                         layout.phase_shift_list, phases)}
                pole_pitch = phases * q
                for _, path in database:
                    self.assertEqual(len({phase_by_position[node[:2]]
                                          for node in path}), 1)
                    for start, end in zip(path, path[1:]):
                        pitch = (((end[0] - layout.phase_shift_list[end[1]])
                                  - (start[0] - layout.phase_shift_list[start[1]])
                                  + winding.num_slots // 2)
                                  % winding.num_slots) - winding.num_slots // 2
                        step = end[1] - start[1]
                        self.assertTrue(
                            (abs(step) == 1 and abs(pitch) == pole_pitch)
                            or (step == 0 and abs(pitch) in
                                (pole_pitch - 1, pole_pitch)),
                            (start, end, pitch))

    def test_selected_route_preflight_matches_generation_configuration_gate(self):
        from pattern_rule_workbench import _base_inputs

        for configuration, enabled in (('Times', True), ('Interval', False),
                                       ('weld', True)):
            with self.subTest(configuration=configuration):
                winding, tp, layout = _base_inputs(
                    'BWP', 4, 4, 4, 4, (2, 2, 1), 5)
                if configuration == 'Times':
                    tp.tp_type, tp.tp_times = 'Times', 1
                elif configuration == 'Interval':
                    tp.tp_type, tp.tp_interval = 'Interval', 1
                else:
                    layout.inlet_from_weld_side = 1
                decision = gw.resolve_pattern_route(
                    'BWP', winding, winding.branch_dividers, tp, layout)
                self.assertEqual(decision.status,
                                 'enabled' if enabled else 'disabled')
                if enabled:
                    _, database = gw.get_winding_layout('BWP', tp, winding, layout)
                    self.assertTrue(database.layout_report['layout_retained'])
                    self.assertEqual(
                        database.layout_report['pattern_identity']['status'],
                        'valid')
                else:
                    self.assertIn('duplicate slot/layer', decision.reason)

    def test_existing_transposition_connections_are_checked_per_case(self):
        from pattern_rule_workbench import _base_inputs

        for field, enabled in (('uni_tp', True), ('pltp_fl', True),
                               ('jltp', True)):
            with self.subTest(field=field):
                winding, tp, layout = _base_inputs(
                    'BWP', 4, 4, 4, 4, (2, 2, 1), 5)
                setattr(tp, field, 1)
                decision = gw.resolve_pattern_route(
                    'BWP', winding, winding.branch_dividers, tp, layout)
                self.assertEqual(decision.status, 'enabled' if enabled else 'disabled')
                if enabled:
                    _, database = gw.get_winding_layout('BWP', tp, winding, layout)
                    self.assertTrue(database.layout_report['layout_retained'])
                    self.assertEqual(
                        database.layout_report['pattern_identity']['status'],
                        'valid')
                else:
                    self.assertIn('invalid wave edge', decision.reason)

    def test_default_factorization_is_phase_symbolic_and_configurable(self):
        from pattern_rule_workbench import _base_inputs
        from phase_topology import phase_map

        for phases in (3, 5, 7):
            for configuration in ('neutral', 'shift', 'Times', 'weld'):
                with self.subTest(phases=phases, configuration=configuration):
                    factors = (2, 3, 1)
                    winding, tp, layout = _base_inputs(
                        'BWP', 4, 6, 4, 6, factors, phases)
                    self.assertEqual(tuple(gw.classify_branch_mode(
                        6, 4, 6, 'BWP')[1:4]), factors)
                    if configuration == 'shift':
                        layout.phase_shift_list = [0, 1, 0, 1]
                    elif configuration == 'Times':
                        tp.tp_type, tp.tp_times = 'Times', 1
                    elif configuration == 'weld':
                        layout.inlet_from_weld_side = 1
                    decision = gw.resolve_pattern_route(
                        'BWP', winding, factors, tp, layout)
                    self.assertEqual(decision.rule_id, 'bwp_default')
                    self.assertEqual(decision.status, 'enabled')
                    _, database = gw.get_winding_layout(
                        'BWP', tp, winding, layout, allow_candidate=True)
                    self.assertTrue(database.layout_report['layout_retained'])
                    phases_by_position = {(slot, layer): phase
                                          for slot, layer, phase, _ in phase_map(
                                              winding.num_slots, 6, 4,
                                              layout.phase_shift_list, phases)}
                    for _, path in database:
                        self.assertEqual(len({phases_by_position[node[:2]]
                                              for node in path}), 1)
                        for start, end in zip(path, path[1:]):
                            pitch = ((end[0] - layout.phase_shift_list[end[1]]
                                      - start[0] + layout.phase_shift_list[start[1]]
                                      + winding.num_slots // 2)
                                     % winding.num_slots) - winding.num_slots // 2
                            self.assertLessEqual(abs(end[1] - start[1]), 1)
                            self.assertTrue(
                                (phases - 1) * 4 < abs(pitch) <
                                (phases + 1) * 4)


class UwpManualTranspositionTests(unittest.TestCase):
    def test_regular_uniform_keeps_each_full_wave_in_its_q_lane(self):
        from pattern_rule_workbench import _base_inputs

        for q, layers in ((2, 4), (4, 4), (4, 8)):
            with self.subTest(q=q, layers=layers):
                winding, tp, layout = _base_inputs(
                    'UWP', q, 8, layers, 2, (1, 1, 2))
                _, neutral = gw.get_winding_layout('UWP', tp, winding, layout)
                tp.uni_tp = 1
                _, paths = gw.get_winding_layout('UWP', tp, winding, layout)
                self.assertNotEqual(paths, neutral)
                coordinates = [tuple(node[:2]) for _, path in paths for node in path]
                self.assertEqual(len(coordinates), len(set(coordinates)))
                self.assertEqual(len(coordinates), winding.num_slots * layers)

    def test_times_and_interval_preserve_required_q_lane_transitions(self):
        from pattern_rule_workbench import _base_inputs

        for q, layers in ((2, 4), (2, 16), (4, 4), (4, 8)):
            for mode in ('Times', 'Interval'):
                with self.subTest(q=q, layers=layers, mode=mode):
                    winding, tp, layout = _base_inputs(
                        'UWP', q, 8, layers, 2, (1, 1, 2))
                    _, neutral = gw.get_winding_layout('UWP', tp, winding, layout)
                    tp.tp_type = mode
                    if mode == 'Times':
                        tp.tp_times = 1
                    else:
                        tp.tp_interval = winding.num_poles * layers * q // 4
                    starts, paths = gw.get_winding_layout('UWP', tp, winding, layout)
                    coordinates = [tuple(node[:2]) for _, path in paths for node in path]
                    self.assertEqual(set(coordinates), {
                        (slot, layer) for slot in range(winding.num_slots)
                        for layer in range(layers)})
                    self.assertEqual(len(coordinates), len(set(coordinates)))
                    self.assertEqual(starts, [path[0] for _, path in paths])
                    self.assertEqual({len(path) for _, path in paths}, {8 * layers * q // 2})
                    self.assertNotEqual(paths, neutral)
                    self.assertEqual(paths.layout_report['pattern_identity']['status'], 'valid')
                    for field in ('uni_tp', 'pltp_fl', 'pltp_ll', 'jltp'):
                        setattr(tp, field, 1)
                    _, with_disabled_values = gw.get_winding_layout('UWP', tp, winding, layout)
                    self.assertEqual(with_disabled_values, paths)


class UwpOddPhaseQppTests(unittest.TestCase):
    def test_proper_q_p2_preserves_forward_long_arc_for_odd_m(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs

        for q, divider in ((4, 2), (6, 2), (6, 3)):
            for layers in (2, 4):
                for phases in (3, 5, 7, 9):
                    with self.subTest(q=q, Q=divider, L=layers, m=phases):
                        factors = (divider, 1, 2)
                        winding, tp, layout = _base_inputs(
                            'UWP', q, 2, layers, 2 * divider,
                            factors, phases)
                        decision = gw.resolve_pattern_route(
                            'UWP', winding, factors, tp, layout)
                        self.assertEqual(decision.status, 'enabled',
                                         decision.reason)
                        _, database = gw.get_winding_layout(
                            'UWP', tp, winding, layout)
                        travel = getattr(database, 'signed_travel', None)
                        self.assertIsInstance(travel, dict)
                        self.assertEqual(analyze_pattern_identity(
                            'UWP', database, winding, layout)['status'],
                            'valid')
                        self.assertTrue(all(
                            step != 0 and
                            (start[0] + step - end[0]) % winding.num_slots == 0
                            for branch_id, path in database
                            for step, start, end in zip(
                                travel[branch_id], path, path[1:])))
                        self.assertTrue(any(
                            abs(step) > winding.num_slots // 2
                            for steps in travel.values() for step in steps))

    def test_public_p2_wave_preserves_constructor_travel_for_odd_m(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs

        for phases in (3, 5, 7, 9):
            with self.subTest(m=phases):
                winding, tp, layout = _base_inputs(
                    'UWP', 2, 2, 4, 2, (1, 1, 2), phases)
                decision = gw.resolve_pattern_route(
                    'UWP', winding, (1, 1, 2), tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                _, database = gw.get_winding_layout('UWP', tp, winding, layout)
                travel = getattr(database, 'signed_travel', None)
                self.assertIsInstance(travel, dict)
                self.assertEqual(set(travel), {branch_id for branch_id, _ in database})
                for branch_id, path in database:
                    self.assertEqual(len(travel[branch_id]), len(path) - 1)
                    self.assertTrue(all(
                        step and (step - end[0] + start[0]) % winding.num_slots == 0
                        for step, start, end in zip(travel[branch_id], path,
                                                    path[1:])))
                identity = analyze_pattern_identity(
                    'UWP', database, winding, layout)
                self.assertEqual(identity['status'], 'valid', identity)
                pitch = 2 * phases
                expected = (pitch, pitch + 1, pitch, pitch,
                            pitch, pitch - 1, pitch)
                self.assertEqual(travel[1], expected)
                self.assertEqual(travel[2],
                                 tuple(-step for step in reversed(expected)))

    def test_short_p2_weld_terminal_route_uses_physical_alwp_pins(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs
        from phase_topology import phase_map

        for q in range(1, 7):
            for phases in (3, 5, 7, 9):
                with self.subTest(q=q, m=phases):
                    factors = (q, 1, 2) if q > 1 else (1, 1, 2)
                    winding, tp, layout = _base_inputs(
                        'UWP', q, 2, 2, 2 * q, factors, phases)
                    layout.inlet_from_weld_side = 1
                    decision = gw.resolve_pattern_route(
                        'UWP', winding, factors, tp, layout)
                    self.assertEqual(decision.status, 'enabled',
                                     decision.reason)
                    self.assertEqual(decision.rule_id, 'uwp_short_p2_weld')
                    _, database = gw.get_winding_layout(
                        'UWP', tp, winding, layout)
                    self.assertEqual(len(database), 2 * q * phases)
                    self.assertTrue(all(len(path) == 2
                                        for _, path in database))
                    records = phase_map(winding.num_slots, 2, 2,
                                        layout.phase_shift_list, phases)
                    report = validate_branches(
                        [path for _, path in database], records,
                        winding.num_slots, 2, winding.ab, phases)
                    self.assertTrue(report['layout_retained'], report)
                    lookup = {(slot, layer): (phase, sign)
                              for slot, layer, phase, sign in records}
                    for _, path in database:
                        start, end = path
                        self.assertEqual(lookup[start[:2]][1], 1)
                        self.assertEqual(lookup[end[:2]],
                                         (lookup[start[:2]][0], -1))
                    identity = analyze_pattern_identity(
                        'UWP', database, winding, layout)
                    self.assertEqual(identity['status'], 'valid', identity)
                    self.assertEqual(set(identity['pin_types']), {'ALWP'})
                    self.assertEqual(len(identity['insertion_edges']),
                                     len(database))
                    self.assertFalse(identity['weld_edges'])
                    layout.inlet_from_weld_side = 0
                    self.assertEqual(gw.resolve_pattern_route(
                        'UWP', winding, factors, tp, layout).status, 'disabled')

    def test_uwp_body_identity_uses_adjacent_layer_wave_pins(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs

        for phases in (3, 5, 7):
            with self.subTest(phases=phases):
                factors = (1, 2, 1)
                winding, tp, layout = _base_inputs(
                    'UWP', 2, 4, 4, 2, factors, phases)
                _, database = gw.get_winding_layout(
                    'UWP', tp, winding, layout, allow_candidate=True)
                identity = analyze_pattern_identity(
                    'UWP', database, winding, layout)
                self.assertEqual(identity['status'], 'valid', identity['reason'])
                self.assertEqual(set(identity['pin_types']), {'ALWP'})

    def test_pp_only_has_one_forward_and_one_reverse_wave_per_phase(self):
        from pattern_rule_workbench import _base_inputs
        from phase_topology import phase_map

        for q, pp, layers, phases in ((2, 2, 4, 3), (2, 2, 4, 5),
                                      (3, 4, 6, 7)):
            with self.subTest(q=q, pp=pp, layers=layers, phases=phases):
                factors = (1, 2, 1)
                winding, tp, layout = _base_inputs(
                    'UWP', q, 2 * pp, layers, 2, factors, phases)
                decision = gw.resolve_pattern_route(
                    'UWP', winding, factors, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                starts, database = gw.get_winding_layout(
                    'UWP', tp, winding, layout, allow_candidate=True)
                self.assertEqual(len(database), 2 * phases)
                self.assertEqual(starts, [path[0] for _, path in database])
                self.assertTrue(database.layout_report['layout_retained'])
                positions = [node[:2] for _, path in database for node in path]
                self.assertEqual(len(positions), winding.num_slots * layers)
                self.assertEqual(len(positions), len(set(positions)))
                records = {(slot, layer): (phase, sign)
                           for slot, layer, phase, sign in phase_map(
                               winding.num_slots, 2 * pp, layers,
                               layout.phase_shift_list, phases)}
                for index, (_, path) in enumerate(database):
                    self.assertEqual(len({records[node[:2]][0]
                                          for node in path}), 1)
                    direction = -1 if index % 2 else 1
                    for start, end in zip(path, path[1:]):
                        pitch = (direction * (end[0] - start[0])) % winding.num_slots
                        self.assertEqual(abs(end[1] - start[1]), 1)
                        self.assertIn(pitch, (phases * q - 1, phases * q,
                                              phases * q + 1))

    def test_pp_only_configuration_preflight_matches_public_generation(self):
        from pattern_rule_workbench import _base_inputs

        for phases in (3, 5, 7):
            for setting in ('shift', 'Uniform', 'Jump', 'Times', 'Interval', 'weld'):
                with self.subTest(phases=phases, setting=setting):
                    winding, tp, layout = _base_inputs(
                        'UWP', 2, 4, 4, 2, (1, 2, 1), phases)
                    if setting == 'shift':
                        layout.phase_shift_list = [0, 1, 0, 1]
                    elif setting == 'Uniform':
                        tp.uni_tp = 1
                    elif setting == 'Jump':
                        tp.jltp = 1
                    elif setting == 'Times':
                        tp.tp_type, tp.tp_times = 'Times', 1
                    elif setting == 'Interval':
                        tp.tp_type, tp.tp_interval = 'Interval', 1
                    else:
                        layout.inlet_from_weld_side = 1
                    decision = gw.resolve_pattern_route(
                        'UWP', winding, winding.branch_dividers, tp, layout)
                    if setting in ('shift', 'Uniform', 'Jump'):
                        self.assertEqual(decision.status, 'enabled')
                        _, database = gw.get_winding_layout(
                            'UWP', tp, winding, layout, allow_candidate=True)
                        self.assertTrue(database.layout_report['layout_retained'])
                    else:
                        self.assertEqual(decision.status, 'disabled')

    def test_q_pp_two_uses_odd_phase_reference(self):
        from pattern_rule_workbench import _base_inputs
        from phase_topology import phase_map

        for q, pp, layers, phases, Q in (
                (2, 2, 4, 5, 2), (4, 4, 6, 5, 2),
                (6, 4, 12, 7, 3)):
            with self.subTest(q=q, pp=pp, layers=layers, phases=phases):
                factors = (Q, 2, 1)
                winding, tp, layout = _base_inputs(
                    'UWP', q, 2 * pp, layers, 2 * Q,
                    factors, phases)
                decision = gw.resolve_pattern_route(
                    'UWP', winding, factors, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                starts, database = gw.get_winding_layout(
                    'UWP', tp, winding, layout, allow_candidate=True)
                self.assertEqual(starts, [path[0] for _, path in database])
                self.assertTrue(database.layout_report['layout_retained'])
                positions = [(node[0], node[1]) for _, path in database
                             for node in path]
                self.assertEqual(len(positions), winding.num_slots * layers)
                self.assertEqual(len(positions), len(set(positions)))
                phase_by_position = {(slot, layer): phase for slot, layer,
                                     phase, _ in phase_map(
                                         winding.num_slots, 2 * pp, layers,
                                         layout.phase_shift_list, phases)}
                for index, (_, path) in enumerate(database):
                    self.assertEqual(len({phase_by_position[node[:2]]
                                          for node in path}), 1)
                    direction = -1 if index % (2 * Q) >= Q else 1
                    for start, end in zip(path, path[1:]):
                        pitch = (direction * (end[0] - start[0])) % winding.num_slots
                        self.assertEqual(abs(end[1] - start[1]), 1)
                        self.assertTrue((phases - 1) * q < pitch <
                                        (phases + 1) * q)

    def test_q_pp_configuration_samples_match_router(self):
        from pattern_rule_workbench import _base_inputs

        for configuration in ('shift', 'Uniform', 'Jump',
                              'Times', 'Interval', 'weld'):
            with self.subTest(configuration=configuration):
                winding, tp, layout = _base_inputs(
                    'UWP', 4, 8, 4, 4, (2, 2, 1), 5)
                if configuration == 'shift':
                    layout.phase_shift_list = [0, 1, 0, 1]
                elif configuration == 'Uniform':
                    tp.uni_tp = 1
                elif configuration == 'Jump':
                    tp.jltp = 1
                elif configuration == 'Times':
                    tp.tp_type, tp.tp_times = 'Times', 1
                elif configuration == 'Interval':
                    tp.tp_type, tp.tp_interval = 'Interval', 1
                else:
                    layout.inlet_from_weld_side = 1
                decision = gw.resolve_pattern_route(
                    'UWP', winding, winding.branch_dividers, tp, layout)
                if configuration in ('Times', 'Interval', 'weld'):
                    self.assertEqual(decision.status, 'disabled')
                else:
                    self.assertEqual(decision.status, 'enabled', decision.reason)
                    _, database = gw.get_winding_layout(
                        'UWP', tp, winding, layout, allow_candidate=True)
                    self.assertTrue(database.layout_report['layout_retained'])


class SspDistinctP2Tests(unittest.TestCase):
    def test_general_even_q_domain_and_unsupported_boundaries(self):
        from pattern_rule_workbench import _base_inputs
        from phase_topology import phase_map
        for q in range(1, 7):
            for poles in (4, 6, 8):
                for layers in (2, 4, 6):
                    for phases in (3, 5):
                        with self.subTest(q=q, poles=poles, layers=layers, phases=phases):
                            w, tp, layout = _base_inputs('SSP', q, poles, layers, 2, (1, 1, 2), phases)
                            starts, db = gw.get_winding_layout('SSP', tp, w, layout)
                            nodes = [n[:2] for _, p in db for n in p]
                            self.assertEqual(len(nodes), len(set(nodes)))
                            self.assertEqual(len(nodes), w.num_slots*layers)
                            self.assertEqual({len(p) for _, p in db}, {q*poles*layers//2})
                            signs = {(s, l): sign for s, l, _, sign in phase_map(
                                w.num_slots, poles, layers, [0]*layers, phases)}
                            self.assertTrue(all(signs[p[0][:2]] == 1 and signs[p[-1][:2]] == -1
                                                for _, p in db))
                            self.assertEqual(starts, [p[0] for _, p in db])
                            self.assertEqual(db.layout_report['pattern_identity']['status'], 'valid')
        for q, poles, layers, phases in ((1, 8, 4, 3), (3, 8, 4, 3),
                                         (2, 2, 4, 3), (2, 8, 3, 3), (2, 8, 4, 4)):
            w, tp, layout = _base_inputs('SSP', q, poles, layers, 2, (1, 1, 2), phases)
            self.assertEqual(gw.resolve_pattern_route('SSP', w, w.branch_dividers, tp, layout).status,
                             'disabled')

    def test_p2_neutral_reproduces_saved_paths_without_duplicate_q_only_topology(self):
        from pattern_rule_workbench import _base_inputs
        saved = json.loads(Path('pattern_rule_drafts/SSP_q-2_pp-4_L-4_Naa-2_Q-1_PP-1_P2-2_Ph-A_Side-weld_Shifts-0-0-0-0_20260922-142928-672985.json').read_text())
        expected = [[(n['slot']-1, n['layer']-1) for n in b['path']]
                    for b in saved['branches']]
        w, tp, layout = _base_inputs('SSP', 2, 8, 4, 2, (1, 1, 2))
        _, database = gw.get_winding_layout('SSP', tp, w, layout)
        self.assertEqual([[n[:2] for n in p] for _, p in database[:2]], expected)
        self.assertTrue(database.layout_report['layout_retained'])
        self.assertFalse(database.layout_report['electrically_valid'])
        w.branch_dividers = (2, 1, 1)
        _, other = gw.get_winding_layout('SSP', tp, w, layout)
        canonical = lambda db: sorted(min(tuple(n[:2] for n in p),
                                         tuple(n[:2] for n in p[::-1])) for _, p in db)
        self.assertNotEqual(canonical(database), canonical(other))

    def test_p2_auto_validated_replay_and_welding_rule(self):
        from pattern_rule_workbench import _base_inputs, build_divider_route_catalog
        w, tp, layout = _base_inputs('SSP', 2, 8, 4, 2, (1, 1, 2))
        starts, database = gw.get_auto_configured_layout('SSP', tp, w, layout, allow_candidate=True)
        auto = database.auto_configuration
        self.assertEqual(database.layout_report['pattern_identity']['status'], 'valid')
        self.assertTrue(auto['completed'])
        self.assertTrue(database.layout_report['electrically_valid'])
        implementation = next(i for i in auto['implementations']
                              if i['implementation_id'] == auto['implementation_id'])
        replay_starts, replay = gw.replay_auto_configuration('SSP', implementation, w, layout)
        self.assertEqual((replay_starts, list(replay)), (starts, list(database)))
        for _, path in database:
            for a, b in zip(path[::2], path[1::2]):
                low, high = sorted((a, b), key=lambda n: n[1])
                self.assertEqual((high[0]-low[0]+24) % 48-24, 6)
        row = next(r for r in build_divider_route_catalog('2', 4, 4)
                   if r.pattern == 'SSP' and r.dividers == (1, 1, 2))
        self.assertEqual(row.status, 'Validated')


class ZlpPpP2SourceCutTests(unittest.TestCase):
    def test_public_pp_p2_cut_uses_complete_p2_parent(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs
        from phase_topology import phase_map

        cases = ((1, 4, 2, 2, 3), (2, 4, 2, 4, 3),
                 (1, 6, 3, 2, 5), (1, 4, 2, 2, 9))
        for q, pp, D, layers, phases in cases:
            with self.subTest(q=q, pp=pp, D=D, L=layers, m=phases):
                factors = (1, D, 2)
                winding, tp, layout = _base_inputs(
                    'ZLP', q, 2 * pp, layers, 2 * D, factors, phases)
                decision = gw.resolve_pattern_route(
                    'ZLP', winding, factors, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                if q == 1:
                    UIWinding = namedtuple('UIWinding', vars(winding).keys())
                    winding = UIWinding(**vars(winding))
                starts, database = gw.get_winding_layout(
                    'ZLP', tp, winding, layout)
                self.assertEqual(starts, [path[0] for _, path in database])
                self.assertEqual(len(database), phases * 2 * D)
                self.assertEqual({len(path) for _, path in database},
                                 {winding.num_slots * layers // (phases * 2 * D)})
                records = phase_map(winding.num_slots, 2 * pp, layers,
                                    layout.phase_shift_list, phases)
                report = validate_branches(
                    [path for _, path in database], records,
                    winding.num_slots, 2 * pp, winding.ab, phases)
                self.assertTrue(report['layout_retained'], report)
                gw.validate_selected_zlp(database, winding, layout)
                self.assertEqual(analyze_pattern_identity(
                    'ZLP', database, winding, layout)['status'], 'valid')
                pole_sign = {(slot, layer): sign
                             for slot, layer, _, sign in records}
                self.assertTrue(all(
                    (pole_sign[path[0][:2]], pole_sign[path[-1][:2]]) ==
                    (1, -1) for _, path in database))

    def test_former_parent_failure_generates_with_odd_m_axis(self):
        from pattern_rule_workbench import _base_inputs

        factors = (1, 2, 2)
        winding, tp, layout = _base_inputs('ZLP', 2, 8, 4, 4,
                                           factors, 5)
        decision = gw.resolve_pattern_route('ZLP', winding, factors,
                                            tp, layout)
        self.assertEqual(decision.status, 'enabled', decision.reason)
        starts, database = gw.get_winding_layout('ZLP', tp, winding, layout)
        self.assertEqual(starts, [path[0] for _, path in database])
        self.assertEqual(len(database), winding.ab * winding.num_phases)
        self.assertTrue(database.layout_report['layout_retained'])

    def test_existing_zlp_default_keeps_its_constructor(self):
        from pattern_rule_workbench import _base_inputs

        factors = (1, 4, 2)
        winding, tp, layout = _base_inputs('ZLP', 1, 8, 4, 8,
                                           factors, 3)
        self.assertIsNone(gw._selected_integer_divider_route(
            'ZLP', winding))
        decision = gw.resolve_pattern_route('ZLP', winding, factors,
                                            tp, layout)
        self.assertNotEqual(decision.rule_id, 'zlp_pp_p2_source_cut')

    def test_shifted_pp_p2_child_uses_shifted_parent_validation(self):
        from pattern_rule_workbench import _base_inputs

        factors = (1, 2, 2)
        winding, tp, layout = _base_inputs('ZLP', 1, 8, 2, 4,
                                           factors, 3)
        layout.phase_shift_list = [0, 1]
        decision = gw.resolve_pattern_route('ZLP', winding, factors,
                                            tp, layout)
        self.assertEqual(decision.status, 'enabled', decision.reason)
        _, database = gw.get_winding_layout('ZLP', tp, winding, layout)
        gw.validate_selected_zlp(database, winding, layout)

    def test_weld_inlet_and_manual_inlet_adjustment_are_not_admitted(self):
        from pattern_rule_workbench import _base_inputs

        for setting in ('weld', 'adjust'):
            with self.subTest(setting=setting):
                factors = (1, 2, 2)
                winding, tp, layout = _base_inputs('ZLP', 1, 8, 2, 4,
                                                   factors, 3)
                if setting == 'weld':
                    layout.inlet_from_weld_side = 1
                else:
                    layout.inlet_index_adjustments_phase_a = [1]
                decision = gw.resolve_pattern_route('ZLP', winding, factors,
                                                    tp, layout)
                self.assertEqual(decision.status, 'disabled')

    def test_post_connection_shift_does_not_revalidate_source(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs('ZLP', 1, 8, 2, 4,
                                           (1, 2, 2), 3)
        layout.phase_shift_list = [0, 3]
        decision = gw.resolve_pattern_route('ZLP', winding, (1, 2, 2),
                                            tp, layout)
        self.assertEqual(decision.status, 'enabled')
        with self.assertRaisesRegex(ValueError, 'electrical validation: zero_fundamental'):
            gw.get_winding_layout('ZLP', tp, winding, layout)


class ZlpP2OnlyTests(unittest.TestCase):
    REVIEW_DIR = Path('workbench_preview/zlp_p2only_parameter_review_20260923')

    def test_p2_mirror_axis_uses_one_odd_phase_rule(self):
        from pattern_rule_workbench import _base_inputs

        for q in (1, 2):
            for layers in (4, 6):
                for phases in (3, 5, 7, 9):
                    with self.subTest(q=q, L=layers, m=phases):
                        winding, tp, layout = _base_inputs(
                            'ZLP', q, 8, layers, 2, (1, 1, 2), phases)
                        decision = gw.resolve_pattern_route(
                            'ZLP', winding, winding.branch_dividers, tp, layout)
                        self.assertEqual(decision.status, 'enabled',
                                         decision.reason)
                        starts, database = gw.get_winding_layout(
                            'ZLP', tp, winding, layout)
                        self.assertEqual(starts,
                                         [path[0] for _, path in database])
                        self.assertEqual(
                            database.layout_report['pattern_identity']['status'],
                            'valid')
                        self.assertTrue(database.layout_report['layout_retained'])

    def test_public_route_reproduces_approved_layouts(self):
        from pattern_rule_workbench import _base_inputs
        from phase_topology import phase_map

        cases = (
            ('01_q2_p8_l4_regular', 2, 8, 4, (0, 0, 0, 0), None),
            ('02_q3_p8_l4_regular', 3, 8, 4, (0, 0, 0, 0), None),
            ('03_q2_p10_l4_regular', 2, 10, 4, (0, 0, 0, 0), None),
            ('04_q2_p8_l2_regular', 2, 8, 2, (0, 0), None),
            ('05_q2_p8_l6_regular', 2, 8, 6, (0, 0, 0, 0, 0, 0), None),
            ('06_q2_p8_l4_interval2', 2, 8, 4, (0, 0, 0, 0), 2),
            ('07_q2_p8_l4_shift_0-1-0-1', 2, 8, 4, (0, 1, 0, 1), None),
            ('08_q2_p8_l4_shift_0-1-2-3', 2, 8, 4, (0, 1, 2, 3), None),
        )
        for name, q, poles, layers, shifts, interval in cases:
            with self.subTest(name=name):
                approved = json.loads((self.REVIEW_DIR / f'{name}.json').read_text(
                    encoding='utf-8'))
                expected = [[(node['slot'] - 1, node['layer'] - 1)
                             for node in branch['path']]
                            for branch in approved['branches']]
                winding, tp, layout = _base_inputs(
                    'ZLP', q, poles, layers, 2, (1, 1, 2))
                layout.phase_shift_list = list(shifts)
                if interval is not None:
                    tp.tp_type = 'Interval'
                    tp.tp_interval = interval
                decision = gw.resolve_pattern_route(
                    'ZLP', winding, winding.branch_dividers, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                starts, database = gw.get_winding_layout(
                    'ZLP', tp, winding, layout)
                self.assertEqual([[node[:2] for node in path]
                                  for _, path in database[:2]], expected)
                self.assertEqual(starts, [path[0] for _, path in database])
                self.assertEqual(database.layout_report['pattern_identity']['status'],
                                 'valid')
                self.assertFalse(database.layout_report['pattern_identity'][
                    'unexpected_pin_types'])
                self.assertTrue(database.layout_report['layout_retained'])
                self.assertTrue(database.layout_report['electrically_valid'])
                signs = {(slot, layer): sign for slot, layer, _, sign in phase_map(
                    winding.num_slots, poles, layers, shifts, 3)}
                self.assertTrue(all(signs[path[0][:2]] == 1
                                    and signs[path[-1][:2]] == -1
                                    for _, path in database))

    def test_catalog_marks_approved_route_validated(self):
        from pattern_rule_workbench import build_divider_route_catalog
        row = next(record for record in build_divider_route_catalog('2', 4, 4)
                   if record.pattern == 'ZLP'
                   and record.dividers == (1, 1, 2))
        self.assertEqual(row.status, 'Validated', row.reason)

    def test_parameter_derived_admission_and_reject_reasons(self):
        from pattern_rule_workbench import _base_inputs

        for q in range(1, 6):
            for poles in range(2, 13, 2):
                for layers in (2, 4, 6):
                    for phases in (3, 5):
                        with self.subTest(q=q, poles=poles, layers=layers,
                                          phases=phases):
                            winding, tp, layout = _base_inputs(
                                'ZLP', q, poles, layers, 2, (1, 1, 2), phases)
                            decision = gw.resolve_pattern_route(
                                'ZLP', winding, winding.branch_dividers, tp, layout)
                            self.assertTrue(decision.reason)
                            if decision.status == 'enabled':
                                starts, database = gw.get_winding_layout(
                                    'ZLP', tp, winding, layout)
                                self.assertEqual(starts,
                                                 [path[0] for _, path in database])
                                self.assertEqual(
                                    database.layout_report['pattern_identity']['status'],
                                    'valid')

        for q, poles, layers, phases in ((2, 8, 3, 3), (2, 8, 4, 4)):
            winding, tp, layout = _base_inputs(
                'ZLP', q, poles, layers, 2, (1, 1, 2), phases)
            self.assertEqual(gw.resolve_pattern_route(
                'ZLP', winding, winding.branch_dividers, tp, layout).status,
                'disabled')

    def test_shifted_phase_map_rejects_slot_mutation(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs('ZLP', 2, 8, 4, 2, (1, 1, 2))
        layout.phase_shift_list = [0, 1, 0, 1]
        _, database = gw.get_winding_layout('ZLP', tp, winding, layout)
        mutated = [[branch_id, list(path)] for branch_id, path in database]
        slot, layer, position = mutated[0][1][1]
        mutated[0][1][1] = ((slot + 2) % winding.num_slots, layer, position)
        with self.assertRaisesRegex(ValueError, 'electrical validation'):
            gw.validate_selected_zlp(mutated, winding, layout)

    def test_selected_zlp_rejects_nonadjacent_layer_edge(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs('ZLP', 2, 8, 4, 2, (1, 1, 2))
        _, database = gw.get_winding_layout('ZLP', tp, winding, layout)
        mutated = [[branch_id, list(path)] for branch_id, path in database]
        slot, _layer, position = mutated[0][1][1]
        mutated[0][1][1] = (slot, 3, position)
        with patch.object(gw, '_validate_selected_electrical'):
            with self.assertRaisesRegex(ValueError, 'invalid lap edge'):
                gw.validate_selected_zlp(mutated, winding, layout)


class SlpP2WeldInletTests(unittest.TestCase):
    def test_p2_weld_inlet_keeps_physical_slp_and_n_to_s_terminals(self):
        from pattern_rule_workbench import _base_inputs
        import layout_analysis as la

        for q, poles in ((2, 6), (3, 4)):
            with self.subTest(q=q, poles=poles):
                winding, tp, layout = _base_inputs(
                    'SLP', q, poles, 6, 2, (1, 1, 2))
                layout.inlet_from_weld_side = 1
                decision = gw.resolve_pattern_route(
                    'SLP', winding, winding.branch_dividers, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                starts, database = gw.get_winding_layout(
                    'SLP', tp, winding, layout)
                self.assertEqual(starts, [path[0] for _, path in database])
                self.assertEqual(len(database), winding.ab * winding.num_phases)
                self.assertTrue(database.layout_report['layout_retained'])
                self.assertEqual(
                    la.analyze_pattern_identity('SLP', database, winding, layout)['status'],
                    'valid')
                gw.validate_slp_factor_route(database, winding, layout)
                signs = {(slot, layer): sign for slot, layer, _, sign in
                         phase_map(winding.num_slots, winding.num_poles,
                                   winding.num_layers, layout.phase_shift_list,
                                   winding.num_phases)}
                self.assertTrue(all(
                    (signs[path[0][:2]], signs[path[-1][:2]]) == (1, -1)
                    for _, path in database))

    def test_p2_weld_inlet_rejects_invalid_lap_direction(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs('SLP', 1, 6, 2, 2, (1, 1, 2))
        layout.inlet_from_weld_side = 1
        with self.assertRaisesRegex(ValueError, 'ordinary lap pass'):
            gw.get_winding_layout('SLP', tp, winding, layout)

    def test_p2_weld_inlet_validates_manual_transposition_output(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs('SLP', 3, 4, 6, 2, (1, 1, 2))
        layout.inlet_from_weld_side = 1
        _, neutral = gw.get_winding_layout('SLP', tp, winding, layout)
        tp.uni_tp = 1
        decision = gw.resolve_pattern_route(
            'SLP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.status, 'enabled')
        _, transposed = gw.get_winding_layout('SLP', tp, winding, layout)
        self.assertNotEqual(transposed, neutral)


class SlpOtherWeldInletTests(unittest.TestCase):
    def test_validated_default_and_selected_p2_weld_inlets(self):
        from pattern_rule_workbench import _base_inputs
        import layout_analysis as la

        cases = (
            (2, 4, 4, 3, (1, 1, 1), None),
            (4, 8, 6, 5, (2, 4, 2), 'slp_pair_lane_p2'),
            (2, 8, 4, 3, (1, 2, 2), 'slp_pp_p2_sector'),
        )
        for q, poles, layers, phases, factors, route in cases:
            with self.subTest(q=q, poles=poles, factors=factors):
                winding, tp, layout = _base_inputs(
                    'SLP', q, poles, layers, math.prod(factors), factors, phases)
                layout.inlet_from_weld_side = 1
                decision = gw.resolve_pattern_route(
                    'SLP', winding, factors, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                self.assertEqual(decision.route_name, route)
                starts, database = gw.get_winding_layout('SLP', tp, winding, layout)
                self.assertEqual(starts, [path[0] for _, path in database])
                self.assertTrue(database.layout_report['layout_retained'])
                self.assertEqual(la.analyze_pattern_identity(
                    'SLP', database, winding, layout)['status'], 'valid')
                gw.validate_slp_factor_route(database, winding, layout)
                if route is not None:
                    layout.inlet_from_weld_side = 0
                    _, insert_database = gw.get_winding_layout(
                        'SLP', tp, winding, layout)
                    self.assertEqual(
                        {branch_id: set(path) for branch_id, path in database},
                        {branch_id: set(path) for branch_id, path in insert_database})
                    layout.inlet_from_weld_side = 1
                if factors[2] == 2:
                    signs = {(slot, layer): sign for slot, layer, _, sign in
                             phase_map(winding.num_slots, winding.num_poles,
                                       winding.num_layers, layout.phase_shift_list,
                                       winding.num_phases)}
                    self.assertTrue(all(
                        (signs[path[0][:2]], signs[path[-1][:2]]) == (1, -1)
                        for _, path in database))

    def test_other_weld_inlets_keep_actual_boundary_rejections(self):
        from pattern_rule_workbench import _base_inputs

        for q, poles, layers, factors in (
                (4, 8, 4, (2, 2, 1)),
                (2, 8, 4, (2, 1, 2))):
            with self.subTest(factors=factors):
                winding, tp, layout = _base_inputs(
                    'SLP', q, poles, layers, math.prod(factors), factors)
                layout.inlet_from_weld_side = 1
                decision = gw.resolve_pattern_route(
                    'SLP', winding, factors, tp, layout)
                self.assertEqual(decision.status, 'disabled')

    def test_added_p2_weld_routes_reject_non_neutral_configuration(self):
        from pattern_rule_workbench import _base_inputs

        for q, poles, layers, phases, factors in (
                (4, 8, 6, 5, (2, 4, 2)),
                (2, 8, 4, 3, (1, 2, 2))):
            for change in ('tp', 'phase_shift'):
                with self.subTest(factors=factors, change=change):
                    winding, tp, layout = _base_inputs(
                        'SLP', q, poles, layers, math.prod(factors), factors, phases)
                    layout.inlet_from_weld_side = 1
                    if change == 'tp':
                        tp.uni_tp = 1
                    else:
                        layout.phase_shift_list = [1] * layers
                    decision = gw.resolve_pattern_route(
                        'SLP', winding, factors, tp, layout)
                    if change == 'phase_shift' or factors == (2, 4, 2):
                        self.assertEqual(decision.status, 'disabled')
                        with self.assertRaises(gw.PatternConfigurationError):
                            gw.get_winding_layout('SLP', tp, winding, layout)
                    else:
                        self.assertEqual(decision.status, 'enabled')
                        gw.get_winding_layout('SLP', tp, winding, layout)


class SlpPpP2EvenSectorTests(unittest.TestCase):
    def test_sector_join_candidate_is_not_reported_as_validated(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs

        factors = (1, 2, 2)
        winding, tp, layout = _base_inputs(
            'SLP', 1, 16, 2, 4, factors, 3)
        decision = gw.resolve_pattern_route(
            'SLP', winding, factors, tp, layout)
        self.assertEqual(decision.status, 'candidate')
        self.assertIn('crosses multiple pole regions', decision.reason)
        with self.assertRaisesRegex(
                gw.PatternConfigurationError, 'Generated layout is isolated as Candidate'):
            gw.get_winding_layout('SLP', tp, winding, layout)
        _, candidate = gw.get_winding_layout(
            'SLP', tp, winding, layout, allow_candidate=True)
        self.assertEqual(analyze_pattern_identity(
            'SLP', candidate, winding, layout)['status'], 'candidate')

        winding, tp, layout = _base_inputs(
            'SLP', 2, 8, 4, 4, factors, 3)
        decision = gw.resolve_pattern_route(
            'SLP', winding, factors, tp, layout)
        self.assertEqual(decision.status, 'enabled', decision.reason)
        self.assertEqual(decision.rule_id, 'slp_pp_p2_sector')
        _, database = gw.get_winding_layout('SLP', tp, winding, layout)
        self.assertTrue(database.layout_report['layout_retained'])
        self.assertEqual(analyze_pattern_identity(
            'SLP', database, winding, layout)['status'], 'valid')
        gw.validate_slp_factor_route(database, winding, layout)

    def test_multi_sector_weld_inlet_uses_the_same_complete_paths(self):
        from pattern_rule_workbench import _base_inputs

        for phases in (3, 5, 7, 9):
            with self.subTest(m=phases):
                factors = (1, 2, 2)
                layers = 6 if phases == 9 else 4
                winding, tp, layout = _base_inputs(
                    'SLP', 2, 8, layers, 4, factors, phases)
                _, inserted = gw.get_winding_layout('SLP', tp, winding, layout)
                layout.inlet_from_weld_side = 1
                decision = gw.resolve_pattern_route(
                    'SLP', winding, factors, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                _, welded = gw.get_winding_layout('SLP', tp, winding, layout)
                self.assertTrue(welded.layout_report['layout_retained'])
                self.assertEqual(welded.layout_report['pattern_identity']['status'],
                                 'valid')
                self.assertEqual(
                    {branch_id: {node[:2] for node in path}
                     for branch_id, path in welded},
                    {branch_id: {node[:2] for node in path}
                     for branch_id, path in inserted})

    def test_odd_sector_count_remains_a_method_gap(self):
        from pattern_rule_workbench import _base_inputs

        factors = (1, 2, 2)
        winding, tp, layout = _base_inputs('SLP', 2, 12, 4, 4, factors, 5)
        decision = gw.resolve_pattern_route(
            'SLP', winding, factors, tp, layout)
        self.assertEqual(decision.status, 'disabled')
        self.assertFalse(gw.pattern_rejects_divider_tuple('SLP', factors))


class SlpLearnedPpDividerTests(unittest.TestCase):
    def test_pp_route_checks_non_neutral_configuration_after_generation(self):
        from pattern_rule_workbench import _base_inputs

        for change, pp_divider in (
                ('times', 2), ('times', 4), ('phase_shift', 2)):
            with self.subTest(change=change, pp_divider=pp_divider):
                winding, tp, layout = _base_inputs(
                    'SLP', 2, 8, 6, pp_divider, (1, pp_divider, 1))
                if change == 'times':
                    tp.tp_type = 'Times'
                    tp.tp_times = 1
                else:
                    layout.phase_shift_list = [2] * winding.num_layers
                decision = gw.resolve_pattern_route(
                    'SLP', winding, winding.branch_dividers, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                starts, database = gw.get_winding_layout(
                    'SLP', tp, winding, layout)
                self.assertEqual(
                    starts, [path[0] for _, path in database])
                self.assertTrue(database.layout_report['layout_retained'])
                self.assertEqual(
                    database.layout_report['pattern_identity']['status'],
                    'valid')

        winding, tp, layout = _base_inputs(
            'SLP', 2, 8, 6, 2, (1, 2, 1))
        tp.uni_tp = 1
        _, database = gw.get_winding_layout('SLP', tp, winding, layout)
        self.assertTrue(database.layout_report['layout_retained'])
        self.assertEqual(database.layout_report['pattern_identity']['status'],
                         'valid')

    def test_pp_route_accepts_ui_namedtuple_winding_parameters(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'SLP', 2, 8, 6, 2, (1, 2, 1))
        winding_group = namedtuple(
            'WindingPara',
            ['q', 'num_poles', 'num_layers', 'num_phases', 'num_slots',
             'ab', 'branch_dividers'])
        ui_winding = winding_group(*(
            getattr(winding, field) for field in winding_group._fields))

        starts, database = gw.get_winding_layout(
            'SLP', tp, ui_winding, layout)

        self.assertEqual(starts, [path[0] for _, path in database])
        self.assertEqual(len(database), ui_winding.ab * ui_winding.num_phases)
        self.assertTrue(database.layout_report['layout_retained'])

        auto_starts, auto_database = gw.get_auto_configured_layout(
            'SLP', tp, ui_winding, layout)
        self.assertEqual(
            auto_starts, [path[0] for _, path in auto_database])
        self.assertTrue(auto_database.auto_configuration['completed'])

    def test_pp_two_reproduces_designer_branch_and_half_circle_copy(self):
        from pattern_rule_workbench import _base_inputs

        package = Path(__file__).parent / 'pattern_rule_drafts' / (
            'SLP_q-2_pp-4_L-4_Naa-2_Q-1_PP-2_P2-1_Ph-A_Side-weld_'
            'Shifts-0-0-0-0_20260922-213917-060899.json')
        saved = json.loads(package.read_text(encoding='utf-8'))
        expected_branch = [
            (node['slot'] - 1, node['layer'] - 1)
            for node in saved['branches'][0]['path']
        ]
        winding, tp, layout = _base_inputs(
            'SLP', 2, 8, 4, 2, (1, 2, 1))

        starts, database = gw.get_winding_layout(
            'SLP', tp, winding, layout)
        phase_a = [database[index * winding.num_phases][1]
                   for index in range(winding.ab)]

        self.assertEqual([node[:2] for node in phase_a[0]], expected_branch)
        self.assertEqual(
            [node[:2] for node in phase_a[1]],
            [((slot + winding.num_slots // 2) % winding.num_slots, layer)
             for slot, layer in expected_branch])
        self.assertEqual(starts, [path[0] for _, path in database])
        self.assertTrue(database.layout_report['layout_retained'])
        self.assertTrue(database.layout_report['electrically_valid'])
        self.assertEqual(
            database.layout_report['pattern_identity']['status'], 'valid')

    def test_pp_branches_follow_symbolic_sector_and_circumferential_rule(self):
        from pattern_rule_workbench import _base_inputs

        cases = (
            (2, 4, 4, 2, 3),
            (3, 6, 6, 3, 5),
            (4, 8, 8, 4, 7),
        )
        for q, pole_pairs, layers, pp_divider, phases in cases:
            with self.subTest(q=q, pp=pole_pairs, layers=layers,
                              pp_divider=pp_divider, phases=phases):
                winding, tp, layout = _base_inputs(
                    'SLP', q, 2 * pole_pairs, layers, pp_divider,
                    (1, pp_divider, 1), phases)
                _, database = gw.get_winding_layout(
                    'SLP', tp, winding, layout)
                tau = phases * q
                branch_shift = winding.num_slots // pp_divider
                phase_a = [database[index * phases][1]
                           for index in range(pp_divider)]
                expected_base_starts = []
                for sector in range(pole_pairs // pp_divider):
                    anchor = (-2 * sector * tau) % winding.num_slots
                    lanes = (range(q) if sector % 2 == 0
                             else range(q - 1, -1, -1))
                    expected_base_starts.extend(
                        (anchor + lane) % winding.num_slots
                        for lane in lanes)
                self.assertEqual(
                    [node[0] for node in phase_a[0][::2 * layers]],
                    expected_base_starts)
                for branch_index, path in enumerate(phase_a):
                    self.assertEqual(
                        [node[:2] for node in path],
                        [((node[0] + branch_index * branch_shift)
                          % winding.num_slots, node[1])
                         for node in phase_a[0]])
                occupied = [node[:2] for _, path in database for node in path]
                self.assertEqual(len(occupied), len(set(occupied)))
                self.assertEqual(
                    set(occupied),
                    {(slot, layer)
                     for slot in range(winding.num_slots)
                     for layer in range(layers)})


class TspTlpAdmissionReviewTests(unittest.TestCase):
    def test_tlp_p2_parent_scales_linearly_with_integer_q(self):
        from pattern_rule_workbench import _base_inputs

        for q in range(1, 7):
            with self.subTest(q=q):
                winding, tp, layout = _base_inputs(
                    'TLP', q, 8, 4, 2, (1, 1, 2))
                starts, database = gw.get_winding_layout(
                    'TLP', tp, winding, layout)
                self.assertEqual(len(database), 2 * winding.num_phases)
                self.assertEqual(starts, [path[0] for _, path in database])
                self.assertEqual(
                    {len(path) for _, path in database}, {16 * q})
                self.assertEqual(
                    database.layout_report['pattern_identity']['status'],
                    'valid')

    def test_tlp_q_pp_p2_parent_slices_reproduce_saved_draft(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'TLP', 2, 8, 4, 8, (2, 2, 2))
        decision = gw.resolve_pattern_route(
            'TLP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.status, 'enabled', decision.reason)
        self.assertEqual(decision.rule_id, 'tlp_q_pp_p2_parent_slices')
        starts, database = gw.get_winding_layout('TLP', tp, winding, layout)
        self.assertEqual(len(database), 24)
        self.assertEqual(starts, [path[0] for _, path in database])
        self.assertEqual(database.layout_report['pattern_identity']['status'],
                         'valid')
        self.assertTrue(database.layout_report['layout_retained'])

        draft_path = next((Path(__file__).parent / 'pattern_rule_drafts').glob(
            'TLP_q-2_pp-4_L-4_Naa-8_Q-2_PP-2_P2-2_Ph-A_Side-weld_'
            'Shifts-0-0-0-0_20260929-104214-297797.json'))
        draft = json.loads(draft_path.read_text(encoding='utf-8'))
        expected = {
            tuple((node['slot'] - 1, node['layer'] - 1)
                  for node in branch['path'])
            for branch in draft['branches']
        }
        lookup = {(slot, layer): phase for slot, layer, phase, _ in phase_map(
            winding.num_slots, winding.num_poles, winding.num_layers,
            layout.phase_shift_list, winding.num_phases)}
        actual = {tuple(node[:2] for node in path) for _, path in database
                  if lookup[path[0][:2]] == 0}
        self.assertEqual(actual, expected)

    def test_tlp_q_pp_p2_parent_slices_integer_geometry_domain(self):
        from pattern_rule_workbench import _base_inputs

        for q in (2, 4, 6):
            for pp in (4, 6, 8):
                for layers in (4, 6, 8, 10, 12):
                    with self.subTest(q=q, pp=pp, layers=layers):
                        winding, tp, layout = _base_inputs(
                            'TLP', q, 2 * pp, layers, 8, (2, 2, 2))
                        decision = gw.resolve_pattern_route(
                            'TLP', winding, winding.branch_dividers, tp, layout)
                        self.assertEqual(decision.status, 'enabled', decision.reason)
                        starts, database = gw.get_winding_layout(
                            'TLP', tp, winding, layout)
                        self.assertEqual(len(database), 8 * winding.num_phases)
                        self.assertEqual(
                            {len(path) for _, path in database},
                            {pp * q * layers // 4})
                        self.assertEqual(
                            database.layout_report['pattern_identity']['status'],
                            'valid')
                        self.assertTrue(database.layout_report['layout_retained'])
                        self.assertEqual(
                            database.parent_slice_report['uniformly_spaced_lanes'],
                            q == 2)

    def test_tlp_q_pp_p2_parent_slices_phase_set_lift(self):
        from pattern_rule_workbench import _base_inputs

        for q, pp, layers, phases in ((2, 4, 8, 6),
                                      (4, 6, 8, 6),
                                      (2, 4, 12, 9)):
            with self.subTest(q=q, pp=pp, layers=layers, phases=phases):
                winding, tp, layout = _base_inputs(
                    'TLP', q, 2 * pp, layers, 8, (2, 2, 2), phases)
                decision = gw.resolve_pattern_route(
                    'TLP', winding, winding.branch_dividers, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                starts, database = gw.get_winding_layout(
                    'TLP', tp, winding, layout)
                self.assertEqual(len(database), 8 * phases)
                self.assertEqual(starts, [path[0] for _, path in database])
                self.assertEqual(
                    database.layout_report['pattern_identity']['status'],
                    'valid')
                self.assertTrue(database.layout_report['layout_retained'])

    def test_tlp_q_pp_p2_short_local_phase_set_is_unresolved(self):
        from pattern_rule_workbench import _base_inputs

        for phases, layers in ((6, 4), (9, 6), (12, 8)):
            with self.subTest(phases=phases, layers=layers):
                winding, tp, layout = _base_inputs(
                    'TLP', 2, 8, layers, 8, (2, 2, 2), phases)
                decision = gw.resolve_pattern_route(
                    'TLP', winding, winding.branch_dividers, tp, layout)
                self.assertEqual(decision.status, 'disabled')
                self.assertEqual(decision.admission, 'unsupported-yet')

    def test_tlp_q_pp_p2_parent_slices_extend_pp_factor(self):
        from pattern_rule_workbench import _base_inputs

        for q, pp, divider, layers in ((2, 6, 3, 4),
                                       (4, 6, 3, 6),
                                       (6, 6, 3, 8),
                                       (4, 8, 4, 8)):
            with self.subTest(q=q, pp=pp, divider=divider, layers=layers):
                factors = (2, divider, 2)
                winding, tp, layout = _base_inputs(
                    'TLP', q, 2 * pp, layers, 4 * divider, factors)
                decision = gw.resolve_pattern_route(
                    'TLP', winding, factors, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                starts, database = gw.get_winding_layout(
                    'TLP', tp, winding, layout)
                self.assertEqual(len(database), 4 * divider * winding.num_phases)
                self.assertEqual(starts, [path[0] for _, path in database])
                self.assertTrue(database.layout_report['layout_retained'])

        for q in (2, 6):
            with self.subTest(q=q, pp=8, divider=4):
                winding, tp, layout = _base_inputs(
                    'TLP', q, 16, 4, 16, (2, 4, 2))
                decision = gw.resolve_pattern_route(
                    'TLP', winding, winding.branch_dividers, tp, layout)
                self.assertEqual(decision.status, 'disabled')
                self.assertEqual(decision.admission, 'unsupported-yet')
                self.assertIn('short-unit deployment', decision.reason)

    def test_tlp_pp_p2_short_unit_public_route_reproduces_saved_draft(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'TLP', 2, 8, 4, 4, (1, 2, 2))
        decision = gw.resolve_pattern_route(
            'TLP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.status, 'enabled', decision.reason)
        self.assertEqual(decision.rule_id, 'tlp_pp_p2_short_unit')
        starts, database = gw.get_winding_layout('TLP', tp, winding, layout)
        self.assertEqual(len(database), 12)
        self.assertEqual(starts, [path[0] for _, path in database])
        self.assertEqual(database.layout_report['pattern_identity']['status'], 'valid')
        self.assertTrue(database.layout_report['layout_retained'])
        self.assertEqual(database.layout_report['layout_status'],
                         'not strong symmetry layout')

        draft_path = next((Path(__file__).parent / 'pattern_rule_drafts').glob(
            'TLP_q-2_pp-4_L-4_Naa-4_Q-1_PP-2_P2-2_Ph-A_Side-weld_'
            'Shifts-0-0-0-0_20260924-211319-973271.json'))
        draft = json.loads(draft_path.read_text(encoding='utf-8'))
        expected = {
            tuple((node['slot'] - 1, node['layer'] - 1)
                  for node in branch['path'])
            for branch in draft['branches']
        }
        lookup = {(slot, layer): phase for slot, layer, phase, _ in phase_map(
            winding.num_slots, winding.num_poles, winding.num_layers,
            layout.phase_shift_list, winding.num_phases)}
        actual = {tuple(node[:2] for node in path) for _, path in database
                  if lookup[path[0][:2]] == 0}
        self.assertEqual(actual, expected)

    def test_tlp_pp_p2_short_units_extend_by_factors_and_keep_shared_exclusion(self):
        from pattern_rule_workbench import _base_inputs

        for q, pp, divider, phases in ((1, 4, 2, 5), (2, 6, 3, 3)):
            with self.subTest(q=q, pp=pp, divider=divider, phases=phases):
                winding, tp, layout = _base_inputs(
                    'TLP', q, 2 * pp, 4, 2 * divider,
                    (1, divider, 2), phases)
                starts, database = gw.get_winding_layout(
                    'TLP', tp, winding, layout)
                self.assertEqual(len(database), 2 * divider * phases)
                self.assertEqual(starts, [path[0] for _, path in database])
                self.assertEqual(
                    database.layout_report['pattern_identity']['status'],
                    'valid')
                self.assertEqual(
                    len({node[:2] for _, path in database for node in path}),
                    winding.num_slots * winding.num_layers)
                report = database.sector_deployment_report
                for sectors in report['inlet_sectors_by_parent'].values():
                    self.assertEqual(len(set(sectors)), divider)
                    self.assertEqual(set(sectors), {
                        (sectors[0] + k * (pp // divider)) % pp
                        for k in range(divider)})

        winding, tp, layout = _base_inputs(
            'TLP', 2, 8, 4, 8, (1, 4, 2))
        decision = gw.resolve_pattern_route(
            'TLP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.status, 'disabled')
        self.assertEqual(decision.rule_id, 'tlp_factor_rejected')

    def test_tlp_auto_and_replay_never_transpose_welds(self):
        from pattern_rule_workbench import _base_inputs
        for divider in (1, 2):
            w, tp, layout = _base_inputs('TLP', 2, 8, 6, 2*divider, (divider, 2, 1))
            _, database = gw.get_auto_configured_layout('TLP', tp, w, layout)
            auto = database.auto_configuration
            self.assertTrue(auto['completed'])
            for implementation in auto['implementations']:
                _, replay = gw.replay_auto_configuration('TLP', implementation, w, layout)
                for _, path in replay:
                    for a, b in zip(path[::2], path[1::2]):
                        pitch = (b[0]-a[0]+w.num_slots//2) % w.num_slots-w.num_slots//2
                        self.assertEqual(abs(pitch), 6, implementation['effective_parameters'])

    def test_tlp_second_sector_welds_share_layer_pair_direction(self):
        from pattern_rule_workbench import _base_inputs
        for q, divider in ((1, 1), (2, 1), (2, 2), (4, 2), (4, 4)):
            for poles in (4, 8, 12):
                for layers in (4, 6):
                    for phases in (3, 5):
                        with self.subTest(q=q, Q=divider, poles=poles,
                                          layers=layers, phases=phases):
                            w, tp, layout = _base_inputs(
                                'TLP', q, poles, layers, 2*divider,
                                (divider, 2, 1), phases)
                            if 1 < divider < q:
                                decision = gw.resolve_pattern_route('TLP', w, w.branch_dividers, tp, layout)
                                self.assertEqual(decision.status, 'disabled')
                                self.assertIn('reference unavailable', decision.reason)
                                continue
                            starts, database = gw.get_winding_layout('TLP', tp, w, layout)
                            occupied = [node[:2] for _, path in database for node in path]
                            self.assertEqual(len(occupied), len(set(occupied)))
                            self.assertEqual(len(occupied), w.num_slots*layers)
                            self.assertEqual({len(p) for _, p in database},
                                             {q*poles*layers//w.ab})
                            travel = {}
                            for _, path in database:
                                for a, b in zip(path[::2], path[1::2]):
                                    low, high = sorted((a, b), key=lambda n: n[1])
                                    self.assertEqual(high[1]-low[1], 1)
                                    pitch = ((high[0]-low[0]+w.num_slots//2)
                                             % w.num_slots-w.num_slots//2)
                                    self.assertEqual(abs(pitch), phases*q)
                                    travel.setdefault((low[1], high[1]), set()).add(pitch)
                            self.assertTrue(all(len(values) == 1 for values in travel.values()),
                                            travel)
                            self.assertEqual(starts, [p[0] for _, p in database])

    def test_tlp_pp_only_two_uses_approved_top_bottom_layout(self):
        from automatic_transposition import assess_strong_symmetry
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs
        from phase_topology import phase_map

        for q in (1, 2):
            for poles in (4, 8, 12):
                for layers in (4, 6):
                    for phases in (3, 5):
                        with self.subTest(q=q, poles=poles, layers=layers,
                                          phases=phases):
                            factors = (1, 2, 1)
                            winding, tp, layout = _base_inputs(
                                'TLP', q, poles, layers, 2, factors, phases)
                            decision = gw.resolve_pattern_route(
                                'TLP', winding, factors, tp, layout)
                            self.assertEqual(decision.status, 'enabled',
                                             decision.reason)
                            self.assertEqual(decision.rule_id,
                                             'tlp_pp_only_two')
                            starts, database = gw.get_winding_layout(
                                'TLP', tp, winding, layout)
                            paths = [path for _, path in database]
                            self.assertEqual(starts, [path[0] for path in paths])
                            self.assertEqual(len(paths), phases * 2)
                            self.assertEqual({len(path) for path in paths},
                                             {q * poles * layers // 2})
                            occupied = [node[:2] for path in paths for node in path]
                            self.assertEqual(len(occupied), len(set(occupied)))
                            self.assertEqual(set(occupied), {
                                (slot, layer) for slot in range(winding.num_slots)
                                for layer in range(layers)})
                            records = phase_map(
                                winding.num_slots, poles, layers,
                                layout.phase_shift_list, phases)
                            report = validate_branches(
                                paths, records, winding.num_slots, poles, 2,
                                phases=phases)
                            self.assertTrue(report['layout_retained'], report)
                            self.assertTrue(report['electrically_valid'], report)
                            identity = analyze_pattern_identity(
                                'TLP', database, winding, layout)
                            self.assertEqual(identity['status'], 'valid', identity)
                            self.assertEqual(set(identity['pin_types']),
                                             {'ALLP', 'CLLP'})
                            tau = phases * q
                            for path in paths:
                                for left, right in zip(path, path[1:]):
                                    pitch = ((right[0] - left[0]
                                              + winding.num_slots // 2)
                                             % winding.num_slots
                                             - winding.num_slots // 2)
                                    layer_delta = right[1] - left[1]
                                    self.assertIn(abs(layer_delta),
                                                  (1, layers - 1))
                                    if abs(layer_delta) == layers - 1:
                                        self.assertIn(abs(pitch),
                                                      (tau - 1, tau, tau + 1))
                                    else:
                                        self.assertEqual(abs(pitch), tau)
                            gw.validate_tlp_pp_only_two_returns(database, winding)
                            reversed_return = json.loads(json.dumps(list(database)))
                            changed = False
                            for _branch_id, path in reversed_return:
                                for edge_index in range(len(path) - 1):
                                    left, right = path[edge_index:edge_index + 2]
                                    if (edge_index % 2 == 1
                                            and abs(right[1] - left[1])
                                            == layers - 1):
                                        right[0] = (left[0] - tau) % winding.num_slots
                                        changed = True
                                        break
                                if changed:
                                    break
                            self.assertTrue(changed)
                            with self.assertRaisesRegex(ValueError, 'reversed'):
                                gw.validate_tlp_pp_only_two_returns(
                                    reversed_return, winding)
                            assessment = assess_strong_symmetry(
                                database, records, winding.num_slots, poles, 2)
                            self.assertEqual(assessment['hard_no'],
                                             bool(assessment['proof']))

    def test_tlp_even_pp_divider_cuts_whole_approved_passes(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs
        from phase_topology import phase_map

        for q, pp, divider, layers, phases in (
                (1, 4, 4, 4, 3), (1, 10, 10, 12, 7),
                (2, 4, 4, 4, 5), (2, 8, 4, 8, 3),
                (2, 10, 10, 12, 7)):
            with self.subTest(q=q, pp=pp, divider=divider,
                              layers=layers, phases=phases):
                factors = (1, divider, 1)
                winding, tp, layout = _base_inputs(
                    'TLP', q, 2 * pp, layers, divider, factors, phases)
                decision = gw.resolve_pattern_route(
                    'TLP', winding, factors, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                self.assertEqual(decision.rule_id, 'tlp_pp_only_even')
                starts, database = gw.get_winding_layout(
                    'TLP', tp, winding, layout)
                paths = [path for _, path in database]
                self.assertEqual(starts, [path[0] for path in paths])
                self.assertEqual(len(paths), phases * divider)
                self.assertEqual({len(path) for path in paths},
                                 {2 * q * pp * layers // divider})
                records = phase_map(winding.num_slots, 2 * pp, layers,
                                    layout.phase_shift_list, phases)
                report = validate_branches(
                    paths, records, winding.num_slots, 2 * pp,
                    divider, phases)
                self.assertTrue(report['layout_retained'], report)
                identity = analyze_pattern_identity(
                    'TLP', database, winding, layout)
                self.assertEqual(identity['status'], 'valid', identity)
                self.assertEqual(identity['identity_confidence'], 'full')
                self.assertEqual(set(identity['pin_types']), {'ALLP', 'CLLP'})
                gw.validate_tlp_welds(database, winding, layout)
                gw.validate_tlp_pp_only_two_returns(database, winding)
        winding, tp, layout = _base_inputs(
            'TLP', 3, 8, 4, 4, (1, 4, 1), 3)
        self.assertEqual(gw.resolve_pattern_route(
            'TLP', winding, (1, 4, 1), tp, layout).status, 'disabled')
        winding, _, _ = _base_inputs(
            'TLP', 1, 9, 4, 4, (1, 4, 1), 3)
        self.assertFalse(gw.supports_tlp_pp_only_even(
            winding, (1, 4, 1)))

    def test_tlp_even_pp_divider_public_finite_domain(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs

        tested = 0
        for q in (1, 2):
            for pp in range(4, 11):
                for divider in range(4, pp + 1, 2):
                    if pp % divider:
                        continue
                    for layers in range(4, 13, 2):
                        for phases in (3, 5, 7):
                            with self.subTest(q=q, pp=pp, D=divider,
                                              L=layers, m=phases):
                                factors = (1, divider, 1)
                                winding, tp, layout = _base_inputs(
                                    'TLP', q, 2 * pp, layers, divider,
                                    factors, phases)
                                decision = gw.resolve_pattern_route(
                                    'TLP', winding, factors, tp, layout)
                                self.assertEqual(decision.status, 'enabled',
                                                 decision.reason)
                                _, database = gw.get_winding_layout(
                                    'TLP', tp, winding, layout)
                                self.assertTrue(database.layout_report[
                                    'layout_retained'])
                                identity = analyze_pattern_identity(
                                    'TLP', database, winding, layout)
                                self.assertEqual(identity['status'], 'valid')
                                self.assertEqual(
                                    identity['identity_confidence'], 'full')
                                tested += 1
        self.assertEqual(tested, 150)

    def test_tlp_even_pp_divider_extends_to_full_q_and_phase_sets(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs

        direct_cases = (
            (2, 4, 4, 4, 3),
            (3, 6, 6, 6, 3),
            (4, 8, 4, 4, 3),
            (6, 6, 6, 6, 3),
        )
        for q, pp, divider, layers, phases in direct_cases:
            factors = (q, divider, 1)
            with self.subTest(q=q, pp=pp, D=divider, L=layers,
                              phases=phases):
                winding, tp, layout = _base_inputs(
                    'TLP', q, 2 * pp, layers, q * divider,
                    factors, phases)
                decision = gw.resolve_pattern_route(
                    'TLP', winding, factors, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                self.assertEqual(decision.rule_id, 'tlp_pp_only_even')
                _, database = gw.get_winding_layout(
                    'TLP', tp, winding, layout)
                self.assertTrue(database.layout_report['layout_retained'])
                self.assertEqual(len(database), phases * q * divider)
                self.assertEqual(
                    {len(path) for _, path in database},
                    {2 * pp * layers // divider})
                identity = analyze_pattern_identity(
                    'TLP', database, winding, layout)
                self.assertEqual(identity['status'], 'valid', identity)
                self.assertEqual(identity['identity_confidence'], 'full')
                self.assertEqual(set(identity['pin_types']), {'ALLP', 'CLLP'})

        for set_count in (2, 3, 4):
            q, local_divider = 2, 4
            pp = local_divider * set_count
            divider = local_divider * set_count
            layers = 4 * set_count
            phases = 3 * set_count
            factors = (q, divider, 1)
            with self.subTest(set_count=set_count, q=q, pp=pp,
                              D=divider, L=layers, phases=phases):
                winding, tp, layout = _base_inputs(
                    'TLP', q, 2 * pp, layers, q * divider,
                    factors, phases)
                decision = gw.resolve_pattern_route(
                    'TLP', winding, factors, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                _, database = gw.get_winding_layout(
                    'TLP', tp, winding, layout)
                self.assertTrue(database.layout_report['layout_retained'])
                self.assertEqual(
                    {len(path) for _, path in database},
                    {2 * pp * layers // divider})
                self.assertEqual(
                    database.layout_report['pattern_identity']['status'],
                    'valid')
                self.assertEqual(
                    {route['rule_id']
                     for route in database.phase_set_array['routes']},
                    {'tlp_pp_only_even'})

        winding, tp, layout = _base_inputs(
            'TLP', 4, 16, 4, 8, (2, 4, 1), 3)
        decision = gw.resolve_pattern_route(
            'TLP', winding, (2, 4, 1), tp, layout)
        self.assertEqual(decision.admission, 'unsupported-yet')

    def test_tlp_short_pass_identity_uses_ordered_lap_edges_without_return(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'TLP', 1, 8, 4, 4, (1, 4, 1), 3)
        _, database = gw.get_winding_layout('TLP', tp, winding, layout)
        short = [[1, list(database[0][1][:winding.num_layers])]]
        identity = analyze_pattern_identity('TLP', short, winding, layout)
        self.assertEqual(identity['status'], 'valid', identity)
        self.assertEqual(set(identity['pin_types']), {'ALLP'})
        self.assertNotIn('CLLP', identity['missing_pin_types'])
        bad = json.loads(json.dumps(short))
        edge = bad[0][1]
        edge[2][0] = (edge[1][0] + winding.num_phases * winding.q) % winding.num_slots
        bad_identity = analyze_pattern_identity('TLP', bad, winding, layout)
        self.assertEqual(bad_identity['status'], 'candidate', bad_identity)

    def test_tsp_pp_only_two_uses_complete_pass_partition(self):
        from pattern_rule_workbench import _base_inputs, build_divider_route_catalog
        winding, tp, layout = _base_inputs(
            'TSP', 2, 8, 4, 2, (1, 2, 1))
        decision = gw.resolve_pattern_route(
            'TSP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.status, 'enabled')
        self.assertEqual(decision.rule_id, 'tsp_spiral_pass_partition')
        _, database = gw.get_winding_layout('TSP', tp, winding, layout)
        self.assertEqual(database.layout_report['pattern_identity']['status'], 'valid')
        build_divider_route_catalog.cache_clear()
        records = build_divider_route_catalog('2', 4, 4)
        tsp = next(record for record in records
                   if record.pattern == 'TSP'
                   and record.dividers == (1, 2, 1))
        tlp = next(record for record in records
                   if record.pattern == 'TLP'
                   and record.dividers == (1, 2, 1))
        self.assertEqual(tsp.status, 'Validated')
        self.assertNotIn(tlp.status, ('unsupported-yet', 'rejected', 'Candidate'))

    def test_tlp_pp_only_two_auto_layout_is_validated_and_replayable(self):
        from pattern_rule_workbench import _base_inputs
        winding, tp, layout = _base_inputs(
            'TLP', 2, 8, 4, 2, (1, 2, 1))
        starts, database = gw.get_auto_configured_layout(
            'TLP', tp, winding, layout, allow_candidate=True)
        auto = database.auto_configuration
        self.assertEqual(auto['status'], 'strong symmetry layout')
        self.assertTrue(auto['completed'])
        selected_score = gw.auto_tp.objective_score(
            auto['metrics'], auto['objective'])
        self.assertEqual(
            selected_score,
            min(gw.auto_tp.objective_score(item['metrics'], auto['objective'])
                for item in auto['implementations']))
        implementation = next(
            item for item in auto['implementations']
            if item['implementation_id'] == auto['implementation_id'])
        replay_starts, replay = gw.replay_auto_configuration(
            'TLP', implementation, winding, layout,
            allow_candidate=True)
        self.assertEqual(replay_starts, starts)
        self.assertEqual(list(replay), list(database))
        self.assertTrue(replay.layout_report['layout_retained'])
        self.assertTrue(replay.layout_report['electrically_valid'])
        self.assertEqual(
            replay.layout_report['pattern_identity']['status'], 'valid')
        self.assertEqual(
            set(replay.layout_report['pattern_identity']['pin_types']),
            {'ALLP', 'CLLP'})
        tampered = json.loads(json.dumps(implementation))
        tampered['effective_parameters']['uni_tp'] = 1
        with self.assertRaisesRegex(ValueError, 'not emitted|do not match'):
            gw.replay_auto_configuration(
                'TLP', tampered, winding, layout, allow_candidate=True)

    def test_missing_pp_constructions_stay_closed_except_registered_routes(self):
        from pattern_rule_workbench import _base_inputs
        cases = ((2, 8, (2, 4, 1)),
                 (2, 8, (2, 2, 2)), (1, 6, (1, 3, 1)),
                 (1, 8, (1, 2, 2)))
        for pattern in ('TSP', 'TLP'):
            for q, poles, factors in cases:
                with self.subTest(pattern=pattern, q=q, factors=factors):
                    naa = factors[0] * factors[1] * factors[2]
                    winding, tp, layout = _base_inputs(
                        pattern, q, poles, 4, naa, factors)
                    self.assertFalse(gw.pattern_rejects_divider_tuple(
                        pattern, factors, q))
                    decision = gw.resolve_pattern_route(
                        pattern, winding, factors, tp, layout)
                    if pattern == 'TSP' and naa % 2 == 0:
                        self.assertEqual(decision.admission, 'supported')
                        self.assertEqual(decision.rule_id, 'tsp_spiral_pass_partition')
                        continue
                    if pattern == 'TLP' and factors in (
                            (2, 4, 1), (1, 2, 2), (2, 2, 2)):
                        expected_route = {
                            (2, 4, 1): 'tlp_pp_only_even',
                            (1, 2, 2): 'tlp_pp_p2_short_unit',
                            (2, 2, 2): 'tlp_q_pp_p2_parent_slices',
                        }[factors]
                        self.assertEqual(decision.status, 'enabled')
                        self.assertEqual(decision.rule_id, expected_route)
                        continue
                    self.assertEqual(decision.status, 'disabled')
                    self.assertEqual(decision.rule_id,
                                     f'{pattern.lower()}_route_unsupported')
                    self.assertIn('no validated construction', decision.reason)
                    with patch.object(gw, '_dispatch_winding_pattern') as dispatch:
                        with self.assertRaisesRegex(
                                gw.PatternConfigurationError,
                                'no validated construction'):
                            gw.get_winding_layout(pattern, tp, winding, layout)
                        dispatch.assert_not_called()
                    # Arithmetic defaults must not bypass missing construction.
                    if tuple(gw.classify_branch_mode(
                            naa, q, poles, pattern)[1:4]) == factors:
                        del winding.branch_dividers
                        with self.assertRaisesRegex(
                                gw.PatternConfigurationError,
                                'no validated construction'):
                            gw.get_winding_layout(pattern, tp, winding, layout)

    def test_catalog_distinguishes_missing_default_from_failed_reference(self):
        from pattern_rule_workbench import build_divider_route_catalog
        build_divider_route_catalog.cache_clear()
        with patch('pattern_rule_workbench.PATTERNS', ('TSP', 'TLP')):
            try:
                default_rows = build_divider_route_catalog('1', 3, 4)
                failed_rows = build_divider_route_catalog('4', 4, 4)
                fractional_rows = build_divider_route_catalog('3/2', 4, 4)
            finally:
                build_divider_route_catalog.cache_clear()
        for pattern in ('TSP', 'TLP'):
            missing = next(r for r in default_rows
                           if r.pattern == pattern and r.dividers == (1, 3, 1))
            self.assertEqual(missing.status, 'unsupported-yet')
            self.assertIn('no validated construction', missing.reason)
            failed = next(r for r in failed_rows
                          if r.pattern == pattern and r.dividers == (2, 2, 1))
            self.assertEqual(failed.status, 'rejected')
            self.assertIn('q/P2 reference unavailable', failed.reason)
            self.assertIn('conductors', failed.reason)
            fractional = [r for r in fractional_rows if r.pattern == pattern]
            self.assertTrue(fractional)
            for row in fractional:
                if (pattern == 'TLP'
                        and row.dividers == (Fraction(3, 2), 4, 2)):
                    self.assertEqual(row.status, 'rejected')
                    self.assertIn('share the available pole-pair division',
                                  row.reason)
                else:
                    self.assertEqual(row.status, 'unsupported-yet')


class TspPpOnlyIdentityRouteTests(unittest.TestCase):
    def test_parameterized_family_matches_public_parent_paths(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs

        samples = (
            (2, 4, 2, 3),
            (2, 4, 4, 3),
            (3, 6, 6, 5),
            (4, 8, 4, 3),
            (2, 8, 6, 5),
            (3, 12, 4, 7),
            (4, 16, 8, 3),
            (5, 20, 4, 5),
        )
        for q, pp, layers, phases in samples:
            with self.subTest(q=q, pp=pp, layers=layers, phases=phases):
                naa = 2 * q
                parent_winding, tp, parent_layout = _base_inputs(
                    'TSP', q, 2 * pp, layers, naa, (q, 1, 2), phases)
                target_winding, _, target_layout = _base_inputs(
                    'TSP', q, 2 * pp, layers, naa, (1, 2 * q, 1), phases)

                parent_decision = gw.resolve_pattern_route(
                    'TSP', parent_winding, parent_winding.branch_dividers,
                    tp, parent_layout)
                self.assertEqual(parent_decision.status, 'enabled',
                                 parent_decision.reason)
                parent_starts, parent = gw.get_winding_layout(
                    'TSP', tp, parent_winding, parent_layout)

                decision = gw.resolve_pattern_route(
                    'TSP', target_winding, target_winding.branch_dividers,
                    tp, target_layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                self.assertEqual(decision.route_name,
                                 'tsp_pp_only_q_p2_identity')
                starts, database = gw.get_winding_layout(
                    'TSP', tp, target_winding, target_layout)

                self.assertEqual(starts, parent_starts)
                self.assertEqual(list(database), list(parent))
                self.assertTrue(database.layout_report['layout_retained'])
                self.assertEqual(
                    database.layout_report['pattern_identity']['status'], 'valid')
                self.assertEqual(
                    database.layout_report['pattern_identity'][
                        'identity_confidence'], 'full')
                self.assertIn('parallel_emf_mismatch',
                              database.layout_report['errors'])
                self.assertEqual(database.layout_status,
                                 'not strong symmetry layout')

    def test_workbench_catalog_uses_public_auto_validation(self):
        from pattern_rule_workbench import build_divider_route_catalog

        build_divider_route_catalog.cache_clear()
        record = next(item for item in build_divider_route_catalog(
            '2', 4, 4) if item.pattern == 'TSP'
            and item.dividers == (1, 4, 1))

        self.assertEqual(record.status, 'Validated')
        self.assertIn('strong symmetry layout', record.reason)

    def test_identity_transfer_matches_local_q_in_arrayed_phase_sets(self):
        from pattern_rule_workbench import _base_inputs

        samples = (
            # global q, poles, layers, Naa, phases, local q
            (2, 16, 4, 8, 6, 4),
            (2, 24, 6, 12, 9, 6),
            (1, 20, 10, 10, 15, 5),
        )
        for q, poles, layers, naa, phases, local_q in samples:
            with self.subTest(phases=phases, local_q=local_q):
                source_winding, tp, source_layout = _base_inputs(
                    'TSP', q, poles, layers, naa,
                    (local_q, 1, 2), phases)
                target_winding, _, target_layout = _base_inputs(
                    'TSP', q, poles, layers, naa,
                    (1, 2 * local_q, 1), phases)

                source_decision = gw.resolve_pattern_route(
                    'TSP', source_winding,
                    source_winding.branch_dividers, tp, source_layout)
                target_decision = gw.resolve_pattern_route(
                    'TSP', target_winding,
                    target_winding.branch_dividers, tp, target_layout)
                self.assertEqual(source_decision.status, 'enabled',
                                 source_decision.reason)
                self.assertEqual(target_decision.status, 'enabled',
                                 target_decision.reason)
                self.assertEqual(
                    target_decision.route_name,
                    'tsp_pp_only_q_p2_identity')

                source_starts, source = gw.get_winding_layout(
                    'TSP', tp, source_winding, source_layout)
                target_starts, target = gw.get_winding_layout(
                    'TSP', tp, target_winding, target_layout)

                self.assertEqual(target_starts, source_starts)
                self.assertEqual(list(target), list(source))
                self.assertTrue(target.layout_report['layout_retained'])
                self.assertEqual(
                    target.layout_report['pattern_identity']['status'],
                    'valid')
                self.assertIn('multi_phase_emf_mismatch',
                              target.layout_report['errors'])
                self.assertEqual(target.layout_status,
                                 'not strong symmetry layout')

    def test_identity_transfer_rejects_non_emf_electrical_errors(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'TSP', 2, 8, 4, 4, (1, 4, 1), 3)
        original_get_layout = gw.get_winding_layout

        def corrupted_parent(pattern, tp_info, parent_winding,
                             parent_layout, **kwargs):
            starts, source = original_get_layout(
                pattern, tp_info, parent_winding, parent_layout, **kwargs)
            if tuple(parent_winding.branch_dividers) != (2, 1, 2):
                return starts, source
            rows = [[branch_id, [tuple(conductor) for conductor in path]]
                    for branch_id, path in source]
            rows[0][1][0] = tuple(source[2][1][0])
            return starts, gw._CandidateBranches(rows)

        gw._cached_neutral_non_wave_preflight.cache_clear()
        try:
            with patch.object(gw, 'get_winding_layout',
                              side_effect=corrupted_parent):
                with self.assertRaisesRegex(
                        gw.PatternConfigurationError,
                        'TSP PP-only identity transfer branches fail electrical '
                        'validation: duplicate_conductor, missing_conductor'):
                    original_get_layout('TSP', tp, winding, layout)
        finally:
            gw._cached_neutral_non_wave_preflight.cache_clear()

    def test_identity_domain_stays_narrow_while_pass_partition_closes_other_routes(self):
        from pattern_rule_workbench import _base_inputs

        unsupported = (
            (1, 2, 2),
            (2, 4, 2),
            (4, 4, 4),
            (2, 6, 6),
        )
        for q, pp, divider in unsupported:
            with self.subTest(q=q, pp=pp, divider=divider):
                winding, tp, layout = _base_inputs(
                    'TSP', q, 2 * pp, 4, divider,
                    (1, divider, 1), 3)
                decision = gw.resolve_pattern_route(
                    'TSP', winding, winding.branch_dividers, tp, layout)
                self.assertFalse(gw.supports_integer_tsp_pp_only_q_p2_identity(
                    winding, winding.branch_dividers))
                self.assertEqual(decision.admission, 'supported')
                self.assertEqual(decision.rule_id, 'tsp_spiral_pass_partition')

    def test_selected_identity_route_keeps_its_neutral_configuration_gate(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'TSP', 2, 8, 4, 4, (1, 4, 1), 3)
        tp.tp_type, tp.tp_times = 'Times', 1

        decision = gw.resolve_pattern_route(
            'TSP', winding, winding.branch_dividers, tp, layout)

        self.assertEqual(decision.status, 'enabled')
        self.assertEqual(decision.rule_id, 'tsp_pp_only_q_p2_identity')
        self.assertEqual(decision.admission, 'supported')
        gw.get_winding_layout('TSP', tp, winding, layout)

    def test_proper_q_parent_failure_does_not_expand_the_identity_domain(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'TSP', 4, 8, 4, 4, (2, 1, 2), 3)
        decision = gw.resolve_pattern_route(
            'TSP', winding, winding.branch_dividers, tp, layout)

        self.assertEqual(decision.status, 'disabled')
        self.assertIn('branch 1 has 16 conductors; expected 32',
                      decision.reason)
        with self.assertRaisesRegex(
                gw.PatternConfigurationError,
                'branch 1 has 16 conductors; expected 32'):
            gw.get_winding_layout('TSP', tp, winding, layout)


class TspQOnlyPairJoinRouteTests(unittest.TestCase):
    def test_proper_q_parent_sweeps_each_missing_lane_in_formula_module(self):
        from divider_connection_formulas import (
            tsp_q_lane_sweep_completion)

        completed = tsp_q_lane_sweep_completion(
            [(7, [(0, 0, 0), (1, 0, 1)])], q=4, q_divider=2,
            num_slots=12, phase_signs={(0, 0): (0, -1)})

        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].source_ids, (7,))
        self.assertEqual(completed[0].path, [
            (1, 0, 1), (0, 0, 0),
            (2, 0, 2), (1, 0, 1),
        ])

    def test_formula_binding_joins_adjacent_q_p2_parents(self):
        binding = ROUTE_FORMULA_BINDINGS['tsp_q_only_pair_join']
        self.assertEqual(
            binding.resolve_source_dividers((2, 1, 1)), (2, 1, 2))

        parents = [
            (10, [(0, 0, 0)]), (11, [(1, 0, 0)]),
            (12, [(2, 0, 0)]), (13, [(3, 0, 0)]),
        ]
        joined = apply_route_formula(
            'tsp_q_only_pair_join', parents, (2, 1, 1))

        self.assertEqual([item.source_ids for item in joined],
                         [(10, 11), (12, 13)])
        self.assertEqual([item.path for item in joined], [
            [(0, 0, 0), (1, 0, 0)],
            [(2, 0, 0), (3, 0, 0)],
        ])

    def test_public_generation_covers_native_and_phase_array_samples(self):
        from pattern_rule_workbench import _base_inputs
        from explicit_connections import EMF_ASYMMETRY_ERRORS

        samples = (
            # q, Q, pp, layers, phases
            (2, 2, 2, 4, 3),       # finite scan delta, full-Q
            (4, 2, 3, 4, 3),       # proper-Q source completion
            (6, 2, 3, 4, 3),       # three consecutive q-lane sweeps
            (2, 2, 2, 4, 5),       # native odd phase count
            (2, 2, 2, 6, 7),       # second finite scan delta
            (2, 2, 2, 8, 6),       # two three-phase sets
            (2, 2, 2, 12, 9),      # three three-phase sets
            (2, 2, 2, 16, 12),     # four three-phase sets
        )
        for q, Q, pp, layers, phases in samples:
            with self.subTest(q=q, Q=Q, pp=pp, layers=layers,
                              phases=phases):
                winding, tp, layout = _base_inputs(
                    'TSP', q, 2 * pp, layers, Q, (Q, 1, 1), phases)
                decision = gw.resolve_pattern_route(
                    'TSP', winding, winding.branch_dividers, tp, layout)
                self.assertEqual(decision.admission, 'supported',
                                 decision.reason)
                self.assertEqual(decision.route_name,
                                 'tsp_q_only_pair_join')

                _starts, database = gw.get_winding_layout(
                    'TSP', tp, winding, layout)
                report = database.layout_report
                self.assertEqual(len(database), Q * phases)
                self.assertEqual(
                    {len(path) for _branch_id, path in database},
                    {2 * q * pp * layers // Q})
                self.assertTrue(report['layout_retained'])
                self.assertEqual(report['pattern_identity']['status'], 'valid')
                self.assertFalse(
                    set(report['errors']) - EMF_ASYMMETRY_ERRORS,
                    report['errors'])

    def test_validator_rejects_a_corrupted_return_pitch(self):
        from pattern_rule_workbench import _base_inputs
        from layout_analysis import signed_circular_distance
        from pattern_identity import circular_travel_steps, pole_region_crossings

        winding, tp, layout = _base_inputs(
            'TSP', 2, 4, 4, 2, (2, 1, 1), 3)
        _starts, database = gw.get_winding_layout(
            'TSP', tp, winding, layout)
        branch_id, path = database[0]
        parent_length = (
            (winding.num_poles // 2) * winding.num_layers * winding.q
            // winding.branch_dividers[0])
        outlet = path[parent_length - 1]
        inlet = path[parent_length]
        phase_sign = {
            (slot, layer): (phase, sign)
            for slot, layer, phase, sign in phase_map(
                winding.num_slots, winding.num_poles, winding.num_layers,
                layout.phase_shift_list, winding.num_phases)
        }
        inlet_phase, inlet_sign = phase_sign[inlet[:2]]
        outlet_slot = (
            outlet[0] - layout.phase_shift_list[outlet[1]])
        expected_pitches = {
            winding.num_phases * winding.q - 1,
            winding.num_phases * winding.q + 1,
        }
        replacement = None
        for slot in range(winding.num_slots):
            if phase_sign[(slot, inlet[1])] != (inlet_phase, inlet_sign):
                continue
            inlet_slot = slot - layout.phase_shift_list[inlet[1]]
            if abs(signed_circular_distance(
                    winding.num_slots, inlet_slot, outlet_slot)) \
                    in expected_pitches:
                continue
            steps = circular_travel_steps(
                outlet_slot % winding.num_slots,
                inlet_slot % winding.num_slots, winding.num_slots)
            if (steps and min(
                    pole_region_crossings(
                        outlet_slot, step,
                        winding.num_phases * winding.q)
                    for step in steps) <= 1):
                replacement = (
                    slot, inlet[1],
                    (slot - layout.phase_shift_list[inlet[1]])
                    % winding.q)
                break

        self.assertIsNotNone(replacement, 'expected a legal wrong-pitch seam')
        path[parent_length] = replacement
        with self.assertRaisesRegex(
                ValueError, 'gcd-derived return formula'):
            gw.validate_tsp_q_only_pair_join(database, winding, layout)

    def test_pair_formula_boundaries_use_pass_partition_and_old_rejection_stays(self):
        from pattern_rule_workbench import _base_inputs

        unsupported = (
            (2, 2, 4, 4, 3),     # interior gcd: g=2, pp=4
            (2, 2, 1, 4, 3),     # one pole pair
            (2, 2, 2, 2, 3),     # two-layer return-role boundary
        )
        for q, Q, pp, layers, phases in unsupported:
            with self.subTest(q=q, Q=Q, pp=pp, layers=layers,
                              phases=phases):
                winding, tp, layout = _base_inputs(
                    'TSP', q, 2 * pp, layers, Q, (Q, 1, 1), phases)
                decision = gw.resolve_pattern_route(
                    'TSP', winding, winding.branch_dividers, tp, layout)
                self.assertFalse(gw.supports_integer_tsp_q_only_pair_join(
                    winding, winding.branch_dividers))
                self.assertEqual(decision.admission, 'supported', decision.reason)
                self.assertEqual(decision.rule_id, 'tsp_spiral_pass_partition')

        winding, tp, layout = _base_inputs(
            'TSP', 6, 4, 4, 3, (3, 1, 1), 3)
        odd_q = gw.resolve_pattern_route(
            'TSP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(odd_q.admission, 'rejected')

        winding, tp, layout = _base_inputs(
            'TSP', 2, 4, 12, 2, (2, 1, 1), 12)
        odd_local_layers = gw.resolve_pattern_route(
            'TSP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(odd_local_layers.admission, 'rejected')

        winding, tp, layout = _base_inputs(
            'TSP', 2, 4, 4, 2, (1, 2, 1), 3)
        pp_only_d2 = gw.resolve_pattern_route(
            'TSP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(pp_only_d2.admission, 'supported')
        self.assertEqual(pp_only_d2.rule_id, 'tsp_spiral_pass_partition')

        winding, tp, layout = _base_inputs(
            'TSP', 6, 12, 4, 3, (3, 1, 1), 5)
        decision = gw.resolve_pattern_route(
            'TSP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.admission, 'rejected')

    def test_finite_q_only_matrix_includes_the_pass_partition_extension(self):
        from refresh_pattern_naa_division_layout import (
            scan_geometries, scan_inventory)

        inventory = scan_inventory(
            scan_geometries(), probe_generation=False)
        cell = next(item for item in inventory['cells']
                    if item['pattern'] == 'TSP'
                    and item['formula'] == 'q_only')

        self.assertEqual(cell['counts'], {
            'supported': 8, 'rejected': 1})


class TlpQOnlyPairJoinRouteTests(unittest.TestCase):
    def test_formula_binding_joins_full_q_p2_parents(self):
        binding = ROUTE_FORMULA_BINDINGS['tlp_q_only_pair_join']
        self.assertEqual(
            binding.resolve_source_dividers((8, 1, 1)), (8, 1, 2))

        parents = [
            (10, [(0, 0, 0)]), (11, [(1, 0, 1)]),
            (12, [(2, 0, 2)]), (13, [(3, 0, 3)]),
        ]
        joined = apply_route_formula(
            'tlp_q_only_pair_join', parents, (4, 1, 1))
        self.assertEqual([item.source_ids for item in joined],
                         [(10, 11), (12, 13)])
        self.assertEqual([item.path for item in joined], [
            [(0, 0, 0), (1, 0, 1)],
            [(2, 0, 2), (3, 0, 3)],
        ])

    def test_public_generation_covers_matrix_and_formula_domain_samples(self):
        from explicit_connections import EMF_ASYMMETRY_ERRORS
        from pattern_rule_workbench import _base_inputs

        samples = (
            # q, Q, pp, layers, phases; first six are current matrix rows.
            (2, 2, 2, 2, 3),
            (2, 2, 4, 4, 3),
            (2, 2, 2, 4, 3),
            (2, 2, 2, 6, 7),
            (4, 4, 4, 4, 3),
            (6, 6, 6, 4, 5),
            (8, 8, 5, 4, 3),
            (2, 2, 3, 4, 3),
            (4, 4, 3, 4, 3),
            (4, 4, 4, 2, 3),
        )
        for q, Q, pp, layers, phases in samples:
            with self.subTest(q=q, Q=Q, pp=pp, layers=layers,
                              phases=phases):
                winding, tp, layout = _base_inputs(
                    'TLP', q, 2 * pp, layers, Q, (Q, 1, 1), phases)
                decision = gw.resolve_pattern_route(
                    'TLP', winding, winding.branch_dividers, tp, layout)
                self.assertEqual(decision.admission, 'supported',
                                 decision.reason)
                self.assertEqual(decision.route_name,
                                 'tlp_q_only_pair_join')

                _starts, database = gw.get_winding_layout(
                    'TLP', tp, winding, layout)
                report = database.layout_report
                self.assertEqual(len(database), Q * phases)
                self.assertEqual(
                    {len(path) for _branch_id, path in database},
                    {2 * pp * layers})
                self.assertTrue(report['layout_retained'])
                self.assertEqual(report['pattern_identity']['status'], 'valid')
                self.assertFalse(
                    set(report['errors']) - EMF_ASYMMETRY_ERRORS,
                    report['errors'])

    def test_q_only_lineage_remains_identifiable_under_pp_only_set_alias(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'TLP', 2, 4, 4, 2, (2, 1, 1), 3)
        _starts, q_only = gw.get_winding_layout(
            'TLP', tp, winding, layout)
        q_only_paths = [tuple(tuple(node[:2]) for node in path)
                        for _branch_id, path in q_only]

        winding, tp, layout = _base_inputs(
            'TLP', 2, 4, 4, 2, (1, 2, 1), 3)
        _starts, pp_only = gw.get_winding_layout(
            'TLP', tp, winding, layout)
        pp_only_paths = [tuple(tuple(node[:2]) for node in path)
                         for _branch_id, path in pp_only]

        self.assertEqual(
            sorted(tuple(sorted(path)) for path in q_only_paths),
            sorted(tuple(sorted(path)) for path in pp_only_paths))
        self.assertNotEqual(q_only_paths, pp_only_paths)
        self.assertEqual(q_only.layout_report['pattern_route']['rule_id'],
                         'tlp_q_only_pair_join')

    def test_q_only_seam_validator_rejects_a_wrong_return_pitch(self):
        from layout_analysis import signed_circular_distance
        from pattern_identity import circular_travel_steps, pole_region_crossings
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'TLP', 8, 10, 4, 8, (8, 1, 1), 3)
        _starts, database = gw.get_winding_layout(
            'TLP', tp, winding, layout)
        parent_length = (winding.num_poles // 2) * winding.num_layers
        outlet = database[0][1][parent_length - 1]
        inlet = database[0][1][parent_length]
        phase_sign = {
            (slot, layer): (phase, sign)
            for slot, layer, phase, sign in phase_map(
                winding.num_slots, winding.num_poles, winding.num_layers,
                layout.phase_shift_list, winding.num_phases)
        }
        inlet_phase, inlet_sign = phase_sign[inlet[:2]]
        outlet_slot = outlet[0] - layout.phase_shift_list[outlet[1]]
        tau = winding.num_phases * winding.q
        valid_pitches = {tau - 1, tau + 1}
        replacement = None
        for slot in range(winding.num_slots):
            if phase_sign[(slot, inlet[1])] != (inlet_phase, inlet_sign):
                continue
            inlet_slot = slot - layout.phase_shift_list[inlet[1]]
            if abs(signed_circular_distance(
                    winding.num_slots, inlet_slot, outlet_slot)) in valid_pitches:
                continue
            steps = circular_travel_steps(
                outlet_slot % winding.num_slots,
                inlet_slot % winding.num_slots, winding.num_slots)
            if (steps and min(
                    pole_region_crossings(outlet_slot, step, tau)
                    for step in steps) <= 1):
                replacement = (
                    slot, inlet[1],
                    (slot - layout.phase_shift_list[inlet[1]]) % winding.q)
                break

        self.assertIsNotNone(replacement)
        database[0][1][parent_length] = replacement
        with self.assertRaisesRegex(ValueError, 'tau plus or minus one'):
            gw.validate_tlp_q_only_pair_join(database, winding, layout)

    def test_q_only_seam_validator_rejects_a_corrupt_q_coordinate(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'TLP', 2, 4, 4, 2, (2, 1, 1), 3)
        _starts, database = gw.get_winding_layout(
            'TLP', tp, winding, layout)
        slot, layer, lane = database[0][1][0]
        database[0][1][0] = (slot, layer, (lane + 1) % winding.q)
        with self.assertRaisesRegex(ValueError, 'invalid q coordinates'):
            gw.validate_tlp_q_only_pair_join(database, winding, layout)

    def test_proper_q_and_nonformula_boundaries_keep_current_status(self):
        from pattern_rule_workbench import _base_inputs

        for q, Q, pp, layers, phases in ((4, 2, 4, 4, 3), (6, 2, 6, 4, 5)):
            with self.subTest(q=q, Q=Q):
                winding, tp, layout = _base_inputs(
                    'TLP', q, 2 * pp, layers, Q, (Q, 1, 1), phases)
                decision = gw.resolve_pattern_route(
                    'TLP', winding, winding.branch_dividers, tp, layout)
                self.assertEqual(decision.admission, 'supported')
                _, database = gw.get_winding_layout('TLP', tp, winding, layout)
                self.assertEqual({len(path) for _, path in database},
                                 {2 * q * pp * layers // Q})
                self.assertTrue(database.layout_report['layout_retained'])

        unsupported = ((2, 2, 1, 4, 3),)  # P2 parent unavailable at pp=1.
        for q, Q, pp, layers, phases in unsupported:
            with self.subTest(q=q, Q=Q, pp=pp, layers=layers,
                              phases=phases):
                winding, tp, layout = _base_inputs(
                    'TLP', q, 2 * pp, layers, Q, (Q, 1, 1), phases)
                decision = gw.resolve_pattern_route(
                    'TLP', winding, winding.branch_dividers, tp, layout)
                self.assertEqual(decision.admission, 'unsupported-yet')

        for q, Q, pp, layers, phases in (
                (3, 3, 2, 4, 3),  # Odd-Q cross-cohort rejection.
                (6, 3, 6, 4, 5),  # Existing structural rejection.
        ):
            with self.subTest(q=q, Q=Q, pp=pp, layers=layers,
                              phases=phases):
                winding, tp, layout = _base_inputs(
                    'TLP', q, 2 * pp, layers, Q, (Q, 1, 1), phases)
                decision = gw.resolve_pattern_route(
                    'TLP', winding, winding.branch_dividers, tp, layout)
                self.assertEqual(decision.admission, 'rejected')

        winding, tp, layout = _base_inputs(
            'TLP', 2, 4, 4, 2, (2, 1, 1), 6)
        array_decision = gw.resolve_pattern_route(
            'TLP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(array_decision.admission, 'supported')
        _, array = gw.get_winding_layout('TLP', tp, winding, layout)
        self.assertEqual(len(array), winding.num_phases * winding.ab)
        self.assertEqual({len(path) for _, path in array}, {16})
        self.assertTrue(array.layout_report['layout_retained'])
        self.assertIn('multi_phase_emf_mismatch', array.layout_report['errors'])

    def test_manual_settings_shifts_and_required_inlet_follow_shared_contract(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'TLP', 2, 4, 4, 2, (2, 1, 1), 3)
        tp.tp_type, tp.tp_times = 'Times', 1
        self.assertEqual(gw.resolve_pattern_route(
            'TLP', winding, winding.branch_dividers, tp, layout).status,
            'enabled')
        with self.assertRaisesRegex(ValueError, 'q-lane identity'):
            gw.get_winding_layout('TLP', tp, winding, layout)

        winding, tp, layout = _base_inputs(
            'TLP', 2, 4, 4, 2, (2, 1, 1), 3)
        layout.phase_shift_list[1] = 1
        self.assertEqual(gw.resolve_pattern_route(
            'TLP', winding, winding.branch_dividers, tp, layout).status,
            'enabled')
        _, shifted = gw.get_winding_layout('TLP', tp, winding, layout)
        self.assertTrue(shifted.layout_report['layout_retained'])

        winding, tp, layout = _base_inputs(
            'TLP', 2, 4, 4, 2, (2, 1, 1), 3)
        layout.inlet_from_weld_side = 1
        self.assertEqual(gw.resolve_pattern_route(
            'TLP', winding, winding.branch_dividers, tp, layout).status,
            'disabled')

    def test_finite_q_only_matrix_delta_matches_formula_domain(self):
        from refresh_pattern_naa_division_layout import (
            scan_geometries, scan_inventory)

        inventory = scan_inventory(
            scan_geometries(), probe_generation=False)
        cell = next(item for item in inventory['cells']
                    if item['pattern'] == 'TLP'
                    and item['formula'] == 'q_only')
        self.assertEqual(cell['counts'], {
            'supported': 8, 'rejected': 1})


class TspPpP2SectorRouteTests(unittest.TestCase):
    def test_default_factor_tuple_expands_without_displacing_tsp_default(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'TSP', 1, 8, 8, 8, (1, 4, 2), 3)
        decision = gw.resolve_pattern_route(
            'TSP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.status, 'enabled', decision.reason)
        self.assertEqual(decision.route_name, 'tsp_pp_p2_sector')
        _, expanded = gw.get_winding_layout('TSP', tp, winding, layout)
        self.assertEqual(len(expanded), 24)
        self.assertEqual(expanded.layout_report['pattern_identity']['status'],
                         'valid')

        winding, tp, layout = _base_inputs(
            'TSP', 2, 4, 2, 2, (1, 1, 2), 3)
        decision = gw.resolve_pattern_route(
            'TSP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.status, 'enabled', decision.reason)
        self.assertEqual(decision.rule_id, 'tsp_default')
        _, default_layout = gw.get_winding_layout(
            'TSP', tp, winding, layout)
        self.assertEqual(len(default_layout), 6)
        self.assertEqual(default_layout.layout_report['pattern_route']['rule_id'],
                         'tsp_default')

    def test_validator_rejects_inlet_region_lane_mismatch_from_phase_map(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'TSP', 2, 8, 4, 8, (1, 4, 2), 3)
        _, database = gw.get_winding_layout('TSP', tp, winding, layout)
        records = phase_map(
            winding.num_slots, winding.num_poles, winding.num_layers,
            layout.phase_shift_list, winding.num_phases)
        phase_sign = {
            (slot, layer): (phase, sign)
            for slot, layer, phase, sign in records
        }
        current_starts = {
            path[0][0] for _branch_id, path in database
            if path[0][1] == 0
            and phase_sign[path[0][:2]][0] == 0
        }
        replacement = next(
            slot for slot, layer, phase, sign in records
            if layer == 0 and phase == 0 and sign == 1
            and slot not in current_starts)
        path = database[0][1]
        self.assertEqual(phase_sign[path[0][:2]], (0, 1))
        path[0] = (replacement, path[0][1], replacement % winding.q)

        with self.assertRaisesRegex(ValueError,
                                    'region/lane inlet partition'):
            gw.validate_tsp_pp_p2_sector(database, winding, layout)

    def test_parameterized_inlet_formula_passes_public_generation_samples(self):
        from pattern_rule_workbench import _base_inputs

        samples = (
            # q, pp, D, layers, phases
            (1, 4, 4, 2, 3),
            (2, 2, 2, 2, 3),
            (2, 4, 4, 4, 3),
            (2, 12, 4, 4, 3),
            (3, 6, 6, 4, 5),
            (4, 8, 8, 4, 7),
            (2, 4, 4, 4, 6),  # locally resolved array of two 3-phase sets
            (2, 6, 6, 6, 9),  # locally resolved array of three 3-phase sets
        )
        for q, pp, divider, layers, phases in samples:
            with self.subTest(q=q, pp=pp, D=divider,
                              layers=layers, phases=phases):
                naa = 2 * divider
                winding, tp, layout = _base_inputs(
                    'TSP', q, 2 * pp, layers, naa,
                    (1, divider, 2), phases)
                starts, database = gw.get_winding_layout(
                    'TSP', tp, winding, layout)

                self.assertEqual(len(database), 2 * divider * phases)
                expected_length = q * pp * layers // divider
                self.assertEqual(
                    {len(path) for _branch_id, path in database},
                    {expected_length})
                self.assertEqual(
                    sum(len(path) for _branch_id, path in database),
                    winding.num_slots * layers)
                self.assertEqual(len(starts), len(database))
                self.assertTrue(database.layout_report['layout_retained'])
                identity = database.layout_report['pattern_identity']
                self.assertEqual(identity['status'], 'valid', identity)
                self.assertEqual(
                    database.layout_report['pattern_route']['rule_id'],
                    'tsp_pp_p2_sector')

                records = phase_map(
                    winding.num_slots, winding.num_poles,
                    winding.num_layers, layout.phase_shift_list,
                    winding.num_phases)
                phase_sign = {
                    (slot, layer): (phase, sign)
                    for slot, layer, phase, sign in records
                }
                for _branch_id, path in database:
                    self.assertEqual(phase_sign[path[0][:2]][1], 1)
                    self.assertEqual(phase_sign[path[-1][:2]][1], -1)
                    self.assertEqual(
                        {phase_sign[node[:2]][0] for node in path},
                        {phase_sign[path[0][:2]][0]})

        winding, tp, layout = _base_inputs(
            'TSP', 2, 8, 4, 8, (1, 4, 2), 3)
        _, database = gw.get_winding_layout('TSP', tp, winding, layout)
        manual_path = (
            Path(__file__).parent / 'pattern_rule_drafts' /
            'TSP_q-2_pp-4_L-4_Naa-8_Q-1_PP-4_P2-2_Ph-A_Side-weld_'
            'Shifts-0-0-0-0_20260927-220113-776173.json')
        manual = json.loads(manual_path.read_text(encoding='utf-8'))
        expected_phase_a = {
            tuple((node['slot'] - 1, node['layer'] - 1)
                  for node in branch['path'])
            for branch in manual['branches']
        }
        actual_phase_a = {
            tuple(node[:2] for node in path)
            for _branch_id, path in list(database)[:8]
        }
        self.assertEqual(actual_phase_a, expected_phase_a)

    def test_fixed_lane_boundaries_use_the_distinct_pass_partition(self):
        from pattern_rule_workbench import _base_inputs

        samples = (
            (3, 2, 2, 4, 3),   # q lanes cannot be evenly assigned to D
            (2, 4, 2, 4, 3),   # lane residue collision
            (2, 4, 4, 2, 3),   # adjacent starts collide at L=2
            (2, 4, 4, 8, 3),   # a long pass returns to its own start
            (2, 8, 4, 4, 3),   # repeated PP sectors collide
            (3, 12, 6, 4, 3),  # repeated sectors collide for this layer step
            (2, 4, 4, 6, 9),   # local q does not divide the selected D
        )
        for q, pp, divider, layers, phases in samples:
            with self.subTest(q=q, pp=pp, D=divider,
                              layers=layers, phases=phases):
                winding, tp, layout = _base_inputs(
                    'TSP', q, 2 * pp, layers, 2 * divider,
                    (1, divider, 2), phases)
                decision = gw.resolve_pattern_route(
                    'TSP', winding, winding.branch_dividers, tp, layout)
                self.assertFalse(gw.supports_integer_tsp_pp_p2_sector(
                    winding, winding.branch_dividers))
                self.assertEqual(decision.admission, 'supported', decision.reason)
                self.assertEqual(decision.rule_id, 'tsp_spiral_pass_partition')

    def test_workbench_retains_publicly_generated_emf_asymmetry(self):
        from pattern_rule_workbench import build_divider_route_catalog

        build_divider_route_catalog.cache_clear()
        record = next(item for item in build_divider_route_catalog(
            '2', 4, 4) if item.pattern == 'TSP'
            and item.dividers == (1, 4, 2))

        self.assertEqual(record.status, 'not strong symmetry layout')
        self.assertIn('parallel_emf_mismatch', record.reason)


class HalfIntegerQPPTransferTests(unittest.TestCase):
    def test_transfer_support_and_all_pattern_catalog(self):
        from pattern_rule_workbench import _base_inputs, build_divider_route_catalog
        q = Fraction(3, 2)
        for phases in (3, 5, 7):
            for pattern in gw.PATTERN_REGISTRY:
                winding, tp, layout = _base_inputs(
                    pattern, q, 8, 4, 3, (q, 2, 1), phases=phases)
                self.assertEqual(gw.supports_half_integer_uwp_q_pp(
                    pattern, winding, winding.branch_dividers), pattern == 'UWP')
                if pattern == 'UWP':
                    _, database = gw.get_winding_layout(
                        pattern, tp, winding, layout, allow_candidate=True)
                    self.assertEqual(len(database), 3 * phases)
                    self.assertEqual(
                        database.layout_report['pattern_identity']['status'],
                        'candidate')
                    self.assertIn(
                        'pole region',
                        database.layout_report['pattern_identity']['reason'])
        rows = [r for r in build_divider_route_catalog('3/2', 4, 4)
                if r.dividers == (q, 2, 1)]
        self.assertEqual(len(rows), 10)
        self.assertNotIn(next(r for r in rows if r.pattern == 'UWP').status,
                         ('rejected', 'unsupported-yet'))

    def test_transfer_preserves_coverage_and_wave_edges(self):
        from pattern_rule_workbench import _base_inputs
        from phase_topology import phase_map
        for q in (Fraction(3, 2), Fraction(5, 2), Fraction(7, 2)):
            for pp in (2, 4, 6):
                for layers in (2, 4, 6):
                    winding, tp, layout = _base_inputs(
                        'UWP', q, 2*pp, layers, int(2*q), (q, 2, 1))
                    layout.phase_shift_list = [i % 2 for i in range(layers)]
                    starts, database = gw.get_winding_layout(
                        'UWP', tp, winding, layout, allow_candidate=True)
                    positions = [node[:2] for _, path in database for node in path]
                    self.assertEqual(len(positions), len(set(positions)))
                    self.assertEqual(set(positions), {(s, l) for s in range(winding.num_slots)
                                                     for l in range(layers)})
                    self.assertEqual(len({len(path) for _, path in database}), 1)
                    lookup = {(s, l): (p, sign) for s, l, p, sign in phase_map(
                        winding.num_slots, 2*pp, layers, layout.phase_shift_list, 3)}
                    for _, path in database:
                        self.assertEqual(len({lookup[node[:2]][0] for node in path}), 1)
                        self.assertEqual(lookup[path[0][:2]][1], 1)
                        self.assertEqual(lookup[path[-1][:2]][1], -1)
                        directions = set()
                        for a, b in zip(path, path[1:]):
                            self.assertEqual(abs(b[1]-a[1]), 1)
                            ds = ((b[0]-layout.phase_shift_list[b[1]]) -
                                  (a[0]-layout.phase_shift_list[a[1]])) % winding.num_slots
                            ds = ds if ds <= winding.num_slots//2 else ds-winding.num_slots
                            self.assertIn(abs(ds), (int(3*q), int(3*q)+1))
                            directions.add(1 if ds > 0 else -1)
                        self.assertEqual(len(directions), 1)
                    self.assertEqual(starts, [path[0] for _, path in database])

    def test_transfer_rejects_missing_cohort_and_odd_pp(self):
        from pattern_rule_workbench import _base_inputs
        for q, pp in ((Fraction(1, 2), 4), (Fraction(3, 2), 3)):
            winding, tp, layout = _base_inputs('UWP', q, 2*pp, 4, int(2*q), (q, 2, 1))
            self.assertFalse(gw.supports_half_integer_uwp_q_pp('UWP', winding, (q, 2, 1)))
            with self.assertRaises(ValueError):
                gw.get_winding_layout('UWP', tp, winding, layout)

    def test_transfer_retains_asymmetry_and_has_distinct_connections(self):
        from pattern_rule_workbench import _base_inputs
        q = Fraction(3, 2)
        winding, tp, layout = _base_inputs('UWP', q, 8, 4, 3, (q, 1, 2))
        _, source = gw.get_winding_layout(
            'UWP', tp, winding, layout, allow_candidate=True)
        winding.branch_dividers = (q, 2, 1)
        self.assertEqual(gw.resolve_pattern_route('UWP', winding).status, 'enabled')
        _, target = gw.get_auto_configured_layout(
            'UWP', tp, winding, layout, allow_candidate=True)
        self.assertEqual(target.auto_configuration['status'], 'not strong symmetry layout')
        edges = lambda db: {frozenset((a[:2], b[:2])) for _, path in db
                            for a, b in zip(path, path[1:])}
        self.assertNotEqual(edges(source), edges(target))


class FractionalRouteDecisionTests(unittest.TestCase):
    def test_route_contract_is_shared_with_the_production_module(self):
        import pattern_route_contract as contract

        self.assertIs(gw.PatternRouteRule, contract.PatternRouteRule)
        self.assertIs(gw.PatternRouteDecision, contract.PatternRouteDecision)
        self.assertIs(gw.PATTERN_ROUTE_RULES, contract.PATTERN_ROUTE_RULES)

    def test_implicit_half_integer_routes_expose_their_default_dividers(self):
        from pattern_rule_workbench import _base_inputs

        q = Fraction(3, 2)
        for pattern, naa, expected in (
                ('BWP', 2, (1, 2, 1)),
                ('UWP', 3, (q, 1, 2))):
            with self.subTest(pattern=pattern):
                winding, tp, layout = _base_inputs(pattern, q, 8, 4, naa)
                decision = gw.resolve_pattern_route(
                    pattern, winding, configuration=tp, layout=layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                self.assertEqual(decision.admission, 'supported')
                self.assertEqual(decision.dividers, expected)
                self.assertTrue(decision.is_default)

    def test_implicit_fractional_sector_keeps_existing_candidate_scope(self):
        from pattern_rule_workbench import _base_inputs

        q = Fraction(7, 2)
        winding, tp, layout = _base_inputs('UWP', q, 8, 6, 4)
        decision = gw.resolve_pattern_route(
            'UWP', winding, configuration=tp, layout=layout)
        self.assertEqual(decision.status, 'enabled', decision.reason)
        self.assertEqual(decision.dividers, (1, 4, 1))
        self.assertEqual(decision.route_name, 'uwp_fractional_sector_array')
        starts, database = gw.get_winding_layout(
            'UWP', tp, winding, layout, allow_candidate=True)
        self.assertEqual(len(starts), 12)
        self.assertEqual(database.layout_report['pattern_identity']['status'],
                         'candidate')

        winding.branch_dividers = (1, 4, 1)
        explicit = gw.resolve_pattern_route(
            'UWP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(explicit.status, 'disabled')
        self.assertEqual(explicit.admission, 'rejected')

    def test_each_existing_half_integer_constructor_has_a_route_decision(self):
        from pattern_rule_workbench import _base_inputs

        q = Fraction(3, 2)
        cases = (
            ('UWP', 8, 3, (q, 1, 2), 'uwp_half_integer_p2'),
            ('UWP', 8, 3, (q, 2, 1), 'uwp_half_integer_q_pp'),
            ('BWP', 8, 2, (1, 2, 1), 'bwp_fractional_sector_array'),
            ('UWP', 8, 2, (1, 2, 1), 'uwp_fractional_sector_array'),
        )
        for pattern, poles, naa, factors, route_name in cases:
            with self.subTest(pattern=pattern, factors=factors):
                winding, tp, layout = _base_inputs(
                    pattern, q, poles, 4, naa, factors)
                decision = gw.resolve_pattern_route(
                    pattern, winding, factors, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                self.assertEqual(decision.dividers, factors)
                self.assertEqual(decision.route_name, route_name)
                starts, database = gw.get_winding_layout(
                    pattern, tp, winding, layout, allow_candidate=True)
                self.assertEqual(starts, [path[0] for _, path in database])
                self.assertTrue(database.layout_report['layout_retained'])
                self.assertEqual(database.layout_report['pattern_route']['rule_id'],
                                 decision.rule_id)

    def test_half_integer_divider_identity_does_not_borrow_a_count_route(self):
        from pattern_rule_workbench import _base_inputs

        q = Fraction(3, 2)
        cases = (
            ('UWP', 8, 6, (q, 4, 1), 'rejected'),
            ('BWP', 8, 3, (q, 1, 2), 'rejected'),
            ('SSP', 8, 3, (q, 2, 1), 'unsupported-yet'),
            ('BWP', 12, 3, (q, 2, 1), 'unsupported-yet'),
            ('UWP', 12, 3, (1, 3, 1), 'rejected'),
        )
        for pattern, poles, naa, factors, category in cases:
            with self.subTest(pattern=pattern, factors=factors):
                winding, tp, layout = _base_inputs(
                    pattern, q, poles, 4, naa, factors)
                decision = gw.resolve_pattern_route(
                    pattern, winding, factors, tp, layout)
                self.assertEqual(decision.status, 'disabled')
                self.assertEqual(decision.admission, category)
                self.assertTrue(decision.reason)
                with patch.object(gw, '_dispatch_winding_pattern') as dispatch:
                    with self.assertRaises(gw.PatternConfigurationError):
                        gw.get_winding_layout(pattern, tp, winding, layout)
                    dispatch.assert_not_called()

    def test_half_integer_transfer_uses_the_binary_source_domain_for_other_q(self):
        from pattern_rule_workbench import _base_inputs

        q = Fraction(5, 2)
        winding, tp, layout = _base_inputs(
            'UWP', q, 8, 4, 5, (q, 2, 1))
        decision = gw.resolve_pattern_route(
            'UWP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.status, 'enabled', decision.reason)
        self.assertEqual(decision.route_name, 'uwp_half_integer_q_pp')
        _, database = gw.get_winding_layout(
            'UWP', tp, winding, layout, allow_candidate=True)
        deployment = database.sector_deployment_report
        self.assertEqual(deployment['source_dividers'], (q, 1, 2))
        self.assertEqual(deployment['target_dividers'], (q, 2, 1))

        winding, tp, layout = _base_inputs(
            'UWP', q, 8, 4, 10, (q, 4, 1))
        decision = gw.resolve_pattern_route(
            'UWP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.status, 'disabled')
        self.assertEqual(decision.admission, 'rejected')
        self.assertIn('splitting allowance', decision.reason)

    def test_half_integer_configuration_keeps_weld_side_guard_and_radial_candidate(self):
        from pattern_rule_workbench import _base_inputs

        q = Fraction(3, 2)
        winding, tp, layout = _base_inputs('UWP', q, 8, 4, 3, (q, 1, 2))
        layout.inlet_from_weld_side = 1
        weld = gw.resolve_pattern_route('UWP', winding, configuration=tp,
                                        layout=layout)
        self.assertEqual(weld.status, 'disabled')
        self.assertIn('weld-side inlet', weld.reason)
        layout.inlet_from_weld_side = 0
        layout.radial_shift = 1
        radial = gw.resolve_pattern_route('UWP', winding, configuration=tp,
                                          layout=layout)
        self.assertEqual(radial.status, 'enabled')
        _starts, candidate = gw.get_winding_layout(
            'UWP', tp, winding, layout, allow_candidate=True)
        self.assertTrue(candidate.layout_report['layout_retained'])
        self.assertEqual(candidate.layout_report['pattern_identity']['status'],
                         'candidate')

    def test_dispatch_uses_the_resolved_route_without_classifying_again(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs('ZLP', 2, 8, 4, 2, (1, 1, 2))
        decision = gw.PatternRouteDecision(
            'enabled', 'zlp_p2_mirrored', 'registered route', 'ZLP',
            (1, 1, 2), route_name='zlp_p2_mirrored')
        expected = (['sentinel'], [['sentinel']])
        with patch.object(gw, '_selected_integer_divider_route',
                          side_effect=AssertionError('route was reselected')):
            with patch.object(gw, '_zlp_p2_from_reference',
                              return_value=expected) as constructor:
                actual = gw._dispatch_winding_pattern(
                    'ZLP', tp, winding, layout, route_decision=decision)
        self.assertIs(actual, expected)
        constructor.assert_called_once_with(tp, winding, layout)

    def test_public_generation_hands_the_same_decision_to_dispatch(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'BWP', Fraction(3, 2), 8, 4, 2, (1, 2, 1))
        original_resolver = gw.resolve_pattern_route
        original_dispatch = gw._dispatch_winding_pattern
        resolved = []
        dispatched = []

        def resolve(*args, **kwargs):
            decision = original_resolver(*args, **kwargs)
            resolved.append(decision)
            return decision

        def dispatch(*args, **kwargs):
            dispatched.append(kwargs.get('route_decision'))
            return original_dispatch(*args, **kwargs)

        with patch.object(gw, 'resolve_pattern_route', side_effect=resolve):
            with patch.object(gw, '_dispatch_winding_pattern', side_effect=dispatch):
                _, database = gw.get_winding_layout(
                    'BWP', tp, winding, layout, allow_candidate=True)
        self.assertEqual(len(resolved), 1)
        self.assertEqual(len(dispatched), 1)
        self.assertIs(dispatched[0], resolved[0])
        self.assertEqual(database.layout_report['pattern_route']['admission'],
                         'supported')


class GeneralPatternRuleTests(unittest.TestCase):
    def test_ssp_mixed_p2_routes_are_rejected_before_construction(self):
        from pattern_rule_workbench import _base_inputs, build_divider_route_catalog
        for q in (1, 2, 3, 4, 6):
            for pp in (2, 3, 4):
                for divider in gw.divisors(q):
                    for pole_divider in gw.divisors(pp):
                        factors = (divider, pole_divider, 2)
                        if factors == (1, 1, 2):
                            continue
                        w, t, l = _base_inputs(
                            'SSP', q, 2*pp, 4, 2*divider*pole_divider, factors)
                        with self.subTest(q=q, pp=pp, factors=factors):
                            self.assertTrue(gw.pattern_rejects_divider_tuple('SSP', factors, q))
                            self.assertIsNone(gw.selected_integer_divider_route('SSP', w))
                            decision = gw.resolve_pattern_route('SSP', w, factors, t, l)
                            self.assertEqual(decision.status, 'disabled')
                            self.assertIn('mixed P2-divider', decision.reason)
                            with patch.object(gw, '_dispatch_winding_pattern') as dispatch:
                                with self.assertRaisesRegex(ValueError, 'SSP mixed P2-divider'):
                                    gw.get_winding_layout('SSP', t, w, l)
                                dispatch.assert_not_called()
        rows = [r for r in build_divider_route_catalog('2', 4, 4)
                if r.pattern == 'SSP' and r.dividers[2] == 2 and r.dividers != (1, 1, 2)]
        self.assertTrue(rows)
        self.assertTrue(all(r.status == 'rejected' for r in rows))
        self.assertTrue(all('mixed P2-divider' in r.reason for r in rows))

    def test_ssp_odd_q_p2_is_rejected_by_equal_cohort_rule(self):
        from pattern_rule_workbench import _base_inputs, build_divider_route_catalog
        for q in (1, 3, 5):
            w, t, l = _base_inputs('SSP', q, 8, 4, 2, (1, 1, 2))
            self.assertTrue(gw.pattern_rejects_divider_tuple('SSP', (1, 1, 2), q))
            decision = gw.resolve_pattern_route('SSP', w, (1, 1, 2), t, l)
            self.assertEqual(decision.status, 'disabled')
            self.assertIn('two equal q-lane cohorts', decision.reason)
            with self.assertRaisesRegex(ValueError, 'two equal q-lane cohorts'):
                gw.get_winding_layout('SSP', t, w, l)
            row = next(r for r in build_divider_route_catalog(str(q), 4, 4)
                       if r.pattern == 'SSP' and r.dividers == (1, 1, 2))
            self.assertEqual(row.status, 'rejected')
            self.assertIn('two equal q-lane cohorts', row.reason)
        self.assertFalse(gw.pattern_rejects_divider_tuple('SSP', (1, 1, 2), 2))
        rows = [r for r in build_divider_route_catalog('3/2', 4, 4)
                if r.pattern == 'SSP']
        self.assertTrue(rows)
        self.assertTrue(all(r.status == 'rejected' for r in rows if r.dividers[2] == 2))
        self.assertTrue(all(r.status == 'unsupported-yet' for r in rows if r.dividers[2] == 1))

    def test_zpp_q_and_p2_is_rejected_before_construction(self):
        from pattern_rule_workbench import _base_inputs

        reason = 'q and p2 share same route'
        for q, q_divider, phases in ((4, 2, 3), (6, 3, 3), (3, 2, 3),
                                     (Fraction(3, 2), Fraction(3, 2), 3),
                                     (4, 2, 6), (4, 2, 9), (4, 2, 12)):
            factors = (q_divider, 1, 2)
            layers = 8 if phases == 3 else 4 * (phases // 3)
            winding, tp, layout = _base_inputs(
                'ZPP', q, 8, layers, math.prod(factors), factors, phases)
            with self.subTest(q=q, factors=factors, phases=phases):
                self.assertTrue(gw.pattern_rejects_divider_tuple('ZPP', factors))
                self.assertEqual(gw.divider_exclusion_reason('ZPP', factors, q),
                                 reason)
                self.assertIsNone(gw.selected_integer_divider_route('ZPP', winding))
                decision = gw.resolve_pattern_route('ZPP', winding, factors, tp, layout)
                self.assertEqual((decision.status, decision.admission),
                                 ('disabled', 'rejected'))
                self.assertIn(reason, decision.reason)
                with patch.object(gw, '_dispatch_winding_pattern') as dispatch:
                    with self.assertRaisesRegex(ValueError, reason):
                        gw.get_winding_layout('ZPP', tp, winding, layout)
                    dispatch.assert_not_called()

        for pattern, factors in (('ZPP', (1, 1, 2)), ('ZPP', (2, 1, 1)),
                                 ('ZPP', (2, 2, 2)), ('SLP', (2, 1, 2))):
            with self.subTest(pattern=pattern, factors=factors):
                self.assertFalse(gw.pattern_rejects_divider_tuple(
                    pattern, factors, 4, 4))

    def test_zpp_odd_integer_q_rejects_every_p2_two_divider_tuple(self):
        from pattern_rule_workbench import _base_inputs

        reason = ('ZPP P2=2 requires q=2*Q; an odd positive integer effective q '
                  'has no integer Q. This rejects the registered construction '
                  'for this geometry, not every possible physical layout.')
        for q_divider in range(1, 5):
            for pp_divider in (1, 2, 4):
                factors = (q_divider, pp_divider, 2)
                winding, tp, layout = _base_inputs(
                    'ZPP', 3, 8, 4, math.prod(factors), factors)
                with self.subTest(factors=factors):
                    self.assertTrue(gw.pattern_rejects_divider_tuple(
                        'ZPP', factors, 3, 4))
                    decision = gw.resolve_pattern_route(
                        'ZPP', winding, factors, tp, layout)
                    self.assertEqual(
                        (decision.status, decision.admission, decision.rule_id),
                        ('disabled', 'rejected', 'zpp_factor_rejected'))
                    expected_reason = ('q and p2 share same route'
                                       if q_divider > 1 and pp_divider == 1
                                       else reason)
                    self.assertEqual(decision.reason, expected_reason)
                    with patch.object(gw, '_dispatch_winding_pattern') as dispatch:
                        with self.assertRaises(ValueError) as error:
                            gw.get_winding_layout('ZPP', tp, winding, layout)
                        self.assertIn(expected_reason, str(error.exception))
                        dispatch.assert_not_called()

    def test_zpp_odd_q_rule_uses_effective_local_q_and_preserves_other_domains(self):
        from pattern_rule_workbench import _base_inputs

        fractional, tp, layout = _base_inputs(
            'ZPP', Fraction(3, 2), 8, 4, 2, (1, 1, 2))
        self.assertFalse(gw.pattern_rejects_divider_tuple(
            'ZPP', (1, 1, 2), Fraction(3, 2), 4))
        fractional_decision = gw.resolve_pattern_route(
            'ZPP', fractional, (1, 1, 2), tp, layout)
        self.assertNotEqual(fractional_decision.rule_id, 'zpp_factor_rejected')

        arrayed, tp, layout = _base_inputs(
            'ZPP', Fraction(3, 2), 8, 8, 4, (1, 2, 2), phases=6)
        local_q_decision = gw.resolve_pattern_route(
            'ZPP', arrayed, (1, 2, 2), tp, layout)
        self.assertEqual(local_q_decision.rule_id, 'phase_set_route_mismatch')
        self.assertIn('odd positive integer effective q', local_q_decision.reason)

        even_q, tp, layout = _base_inputs(
            'ZPP', 4, 8, 4, 8, (2, 2, 2))
        self.assertFalse(gw.pattern_rejects_divider_tuple(
            'ZPP', (2, 2, 2), 4, 4))
        even_decision = gw.resolve_pattern_route(
            'ZPP', even_q, (2, 2, 2), tp, layout)
        self.assertNotEqual(even_decision.rule_id, 'zpp_factor_rejected')

    def test_ssp_q_and_pp_default_paths_pass_independent_geometry_oracle(self):
        from math import gcd
        from pattern_rule_workbench import _base_inputs
        from automatic_transposition import assess_strong_symmetry
        generated = Counter()
        for q in (2, 3, 4, 6):
            for pp in (2, 3, 4):
                for divider in gw.divisors(q):
                    if divider == 1:
                        continue
                    for pole_divider in gw.divisors(pp):
                        for layers in (2, 3, 4):
                            for phases in (3, 5):
                                factors = (divider, pole_divider, 1)
                                naa = divider*pole_divider
                                w, t, l = _base_inputs('SSP', q, 2*pp, layers,
                                                       naa, factors, phases)
                                decision = gw.resolve_pattern_route('SSP', w, factors, t, l)
                                with self.subTest(q=q, pp=pp, factors=factors,
                                                  layers=layers, phases=phases):
                                    # Q-first default extraction: gcd(Naa,q) must equal Q.
                                    if gcd(naa, q) != divider:
                                        self.assertEqual(decision.status, 'disabled')
                                        self.assertIn('no validated construction', decision.reason)
                                        continue
                                    self.assertEqual(decision.status, 'enabled', decision.reason)
                                    starts, db = gw.get_winding_layout('SSP', t, w, l)
                                    family = 'q_only' if pole_divider == 1 else 'q_and_pp'
                                    generated[family] += 1
                                    paths = [p for _, p in db]
                                    self.assertEqual(len(paths), phases*naa)
                                    self.assertEqual(starts, [p[0] for p in paths])
                                    self.assertEqual({len(p) for p in paths},
                                                     {q*2*pp*layers//naa})
                                    occupied = [node[:2] for p in paths for node in p]
                                    self.assertEqual(len(occupied), len(set(occupied)))
                                    self.assertEqual(set(occupied),
                                        {(s, layer) for s in range(w.num_slots)
                                         for layer in range(layers)})
                                    tau = phases*q
                                    travel = {}
                                    for p in paths:
                                        phase = (p[0][0]//q) % phases
                                        sign = (-1)**(p[0][0]//q)
                                        self.assertEqual(len({s % q for s, _, _ in p}), q//divider)
                                        for index, (s, layer, _) in enumerate(p):
                                            self.assertEqual((s//q) % phases, phase)
                                            self.assertEqual((-1)**(s//q), sign*(-1)**index)
                                        for index, (a, b) in enumerate(zip(p, p[1:])):
                                            pitch = (b[0]-a[0]+w.num_slots//2) % w.num_slots-w.num_slots//2
                                            dl = b[1]-a[1]
                                            if dl:
                                                self.assertEqual(abs(dl), 1)
                                                self.assertEqual(pitch, dl*tau)
                                            else:
                                                self.assertIn(a[1], (0, layers-1))
                                                self.assertIn(pitch, (tau, tau+1))
                                            if index % 2 == 0 and dl:
                                                pair = tuple(sorted((a[1], b[1])))
                                                travel.setdefault(pair, set()).add(pitch*(1 if dl > 0 else -1))
                                    self.assertTrue(all(len(v) == 1 for v in travel.values()))
                                    self.assertEqual(db.layout_report['pattern_identity']['status'], 'valid')
                                    records = default_phase_map(w.num_slots, 2*pp, layers, phases)
                                    assessment = assess_strong_symmetry(db, records, w.num_slots, 2*pp, naa)
                                    self.assertEqual(assessment['hard_no'], bool(assessment['proof']))
        self.assertGreater(generated['q_only'], 0)
        self.assertGreater(generated['q_and_pp'], 0)

    def test_ssp_q_routes_keep_pending_separate_from_count_hard_no(self):
        from pattern_rule_workbench import _base_inputs
        for q, pp, factors, expected in (
                (2, 4, (2, 1, 1), 'auto configure pending'),
                (3, 4, (3, 1, 1), 'not strong symmetry layout'),
                (2, 4, (2, 2, 1), 'auto configure pending'),
                (3, 4, (3, 2, 1), 'not strong symmetry layout')):
            w, t, l = _base_inputs('SSP', q, 2*pp, 4,
                                   factors[0]*factors[1], factors)
            _, db = gw.get_auto_configured_layout('SSP', t, w, l)
            self.assertTrue(db.layout_report['layout_retained'])
            self.assertEqual(db.auto_configuration['status'], expected)
            self.assertEqual(db.auto_configuration['assessment']['hard_no'],
                             expected == 'not strong symmetry layout')

    def test_auto_bwp_rule_ranks_single_field_candidates_and_marks_search_scope(self):
        from pattern_rule_workbench import _base_inputs
        import automatic_transposition as auto_tp
        w, t, l = _base_inputs('BWP', 4, 8, 4, 2, (2, 1, 1))
        first_tp = SimpleNamespace(**vars(t))
        first_tp.uni_tp = 1
        _, first = gw.get_winding_layout('BWP', first_tp, w, l)

        def physical_shapes(paths):
            return {(min(a[1], b[1]), max(a[1], b[1]),
                     min(abs(a[0]-b[0]), w.num_slots-abs(a[0]-b[0])))
                    for _, p in paths for a, b in zip(p[1::2], p[2::2])}

        for objective in auto_tp.AUTO_CONFIGURE_OBJECTIVES:
            with self.subTest(objective=objective):
                _, paths = gw.get_auto_configured_layout('BWP', t, w, l,
                    objective=objective,
                    pin_length_evaluator=lambda a, b, span, wa, wb: 200+10*span+wa+wb)
                report = paths.auto_configuration
                self.assertTrue(report['completed'])
                self.assertFalse(report['fast_path_applied'])
                self.assertTrue(report['search_complete'])
                self.assertEqual(report['optimality_scope'],
                                 'best_in_evaluated_recipe_domain')
                self.assertGreater(report['evaluated_implementation_count'], 1)
                self.assertEqual(report['objective'], objective)
                scores = [auto_tp.objective_score(row['metrics'], objective)
                          for row in report['implementations']]
                self.assertEqual(auto_tp.objective_score(report['metrics'], objective), min(scores))
                self.assertEqual(len(physical_shapes(paths)), report['metrics']['pin_type_count'])
                winner = report['objectives'][objective]
                self.assertEqual(winner['implementation_id'], report['implementation_id'])
                replay_tp = SimpleNamespace(**report['effective_parameters'])
                _, replay = gw.get_winding_layout('BWP', replay_tp, w, l)
                self.assertEqual(paths, replay)
                if objective == 'min_pin_types':
                    self.assertLess(len(physical_shapes(paths)), len(physical_shapes(first)))
                    self.assertEqual(len(physical_shapes(paths)), 6)

    def test_auto_candidates_never_change_weld_side_connections(self):
        from pattern_rule_workbench import _base_inputs
        import automatic_transposition as auto_tp

        cases = (('BWP', (2, 1, 1)), ('UWP', (2, 1, 2)),
                 ('SSP', (1, 1, 2)), ('SLP', (1, 2, 1)),
                 ('TSP', (2, 1, 2)), ('TLP', (2, 1, 2)),
                 ('ZLP', (1, 1, 2)), ('CP', (2, 1, 2)),
                 ('ZPP', (2, 1, 1)), ('LPP', (1, 4, 1)))
        rejected_patterns = set()
        for pattern, factors in cases:
            with self.subTest(pattern=pattern):
                naa = factors[0] * factors[1] * factors[2]
                w, t, l = _base_inputs(pattern, 2, 8, 4, naa, factors)
                _, reference = gw.get_winding_layout(pattern, t, w, l)
                _, configured = gw.get_auto_configured_layout(pattern, t, w, l)
                if configured.auto_configuration['weld_rule_rejections']:
                    rejected_patterns.add(pattern)
                for implementation in configured.auto_configuration['implementations']:
                    _, replay = gw.replay_auto_configuration(
                        pattern, implementation, w, l)
                    contract = auto_tp.weld_side_contract(
                        reference, replay, w.num_slots, l)
                    self.assertTrue(contract['valid'],
                                    (implementation['effective_parameters'], contract))
        self.assertTrue({'TSP', 'LPP'} <= rejected_patterns,
                        rejected_patterns)

    def test_auto_length_uses_explicit_normalized_geometry_not_physical_fallback(self):
        from pattern_rule_workbench import _base_inputs
        w, t, l = _base_inputs('BWP', 2, 8, 4, 2, (2, 1, 1))
        _, paths = gw.get_auto_configured_layout(
            'BWP', t, w, l, objective='min_average_pin_length')
        metrics = paths.auto_configuration['metrics']
        self.assertGreater(metrics['average_pin_length_normalized'], 0)
        self.assertEqual(metrics['normalized_length_basis'],
                         'slot_and_layer_span_geometry_per_pole_pitch')
        self.assertIsNone(metrics['average_pin_length_mm'])
        _, reported = gw.get_auto_configured_layout(
            'BWP', t, w, l, objective='min_average_pin_length',
            pin_length_evaluator=lambda *args: 250.0)
        self.assertEqual(reported.auto_configuration['metrics']['average_pin_length_mm'], 250.0)

    def test_wave_auto_configure_combined_offsets_and_derived_plan(self):
        from pattern_rule_workbench import _base_inputs
        from copy import deepcopy
        for pattern, q, poles, factors in (
                ('BWP', 6, 12, (2, 2, 1)),
                ('UWP', 4, 8, (4, 1, 2)),
                ('UWP', 6, 12, (6, 1, 2))):
            with self.subTest(pattern=pattern, q=q):
                naa = factors[0]*factors[1]*factors[2]
                w, t, l = _base_inputs(pattern, q, poles, 4, naa, factors)
                original = deepcopy((vars(w), vars(t), vars(l)))
                starts, baseline = gw.get_winding_layout(pattern, t, w, l)
                actual_starts, db = gw.get_auto_configured_layout(pattern, t, w, l)
                auto = db.auto_configuration
                self.assertTrue(auto['completed'], auto)
                self.assertTrue(db.layout_report['electrically_valid'])
                if pattern == 'BWP':
                    self.assertEqual(starts, actual_starts)
                else:
                    self.assertEqual([(s*poles//w.num_slots, layer) for s, layer, _ in starts],
                                     [(s*poles//w.num_slots, layer) for s, layer, _ in actual_starts])
                self.assertEqual(len({n[:2] for _, p in db for n in p}), w.num_slots*4)
                records = default_phase_map(w.num_slots, poles, 4)
                categories = {(s, layer): (phase, layer,
                    (poles*s + (w.num_slots if sign < 0 else 0)) % (2*w.num_slots))
                    for s, layer, phase, sign in records}
                by_phase = {}
                for _, path in db:
                    phase = categories[path[0][:2]][0]
                    counts = Counter(categories[n[:2]] for n in path)
                    if phase in by_phase:
                        self.assertEqual(counts, by_phase[phase])
                    by_phase[phase] = counts
                replay_tp = SimpleNamespace(**vars(t))
                replay_tp.__dict__.update(auto['effective_parameters'])
                _, replay = gw.get_winding_layout(pattern, replay_tp, w, l)
                self.assertEqual(db, replay)
                self.assertEqual((vars(w), vars(t), vars(l)), original)
                if pattern == 'UWP':
                    def weld_pairs(paths):
                        return {frozenset((a[:2], b[:2])) for _, p in paths
                                for a, b in zip(p[::2], p[1::2])}
                    self.assertEqual(weld_pairs(db), weld_pairs(baseline))

    def test_shifted_auto_preserves_regions_and_p2_terminal_polarity(self):
        from pattern_rule_workbench import _base_inputs
        from copy import deepcopy
        for pattern, q, poles, factors in (
                ('BWP', 6, 12, (2, 2, 1)), ('UWP', 2, 8, (1, 1, 2))):
            w, t, l = _base_inputs(pattern, q, poles, 4,
                                  factors[0]*factors[1]*factors[2], factors)
            l.phase_shift_list = [0, 1, 0, 1]
            original = deepcopy((vars(w), vars(t), vars(l)))
            starts, baseline = gw.get_winding_layout(pattern, t, w, l)
            actual, db = gw.get_auto_configured_layout(pattern, t, w, l)
            def regions(values):
                return [(((s-l.phase_shift_list[layer]) % w.num_slots)*poles//w.num_slots,
                         layer) for s, layer, _ in values]
            self.assertEqual(regions(starts), regions(actual))
            self.assertTrue(db.auto_configuration['completed'])
            self.assertEqual((vars(w), vars(t), vars(l)), original)
            if factors[2] == 2:
                signs = {(s, layer): sign for s, layer, phase, sign in
                         gw.phase_map(w.num_slots, poles, 4, l.phase_shift_list)}
                for _, path in db:
                    self.assertEqual(signs[path[0][:2]], 1)
                    self.assertEqual(signs[path[-1][:2]], -1)

    def test_all_wave_default_validated_rows_load_completed_auto_paths(self):
        from pattern_rule_workbench import (
            build_divider_route_catalog, generate_route_drafts, _base_inputs)
        seen = set()
        for q, pp in ((2, 2), (4, 4), (6, 6)):
            for row in build_divider_route_catalog(str(q), pp, 4):
                if row.pattern not in ('BWP', 'UWP') or row.status not in ('Default', 'Validated'):
                    continue
                with self.subTest(pattern=row.pattern, q=q, factors=row.dividers):
                    seen.add((row.pattern, row.status))
                    drafts = generate_route_drafts(row)
                    auto = drafts[0].reference_constraints['auto_configuration']
                    self.assertTrue(auto['completed'], auto)
                    w, t, l = _base_inputs(row.pattern, q, 2*pp, 4, row.naa, row.dividers)
                    _, db = gw.get_auto_configured_layout(row.pattern, t, w, l)
                    phase = {(s, layer): f for s, layer, f, sign in
                             default_phase_map(w.num_slots, 2*pp, 4)}
                    expected = [[n[:2] for n in p] for _, p in db if phase[p[0][:2]] == 0]
                    self.assertEqual([d.path for d in drafts], expected)
                    self.assertEqual(drafts[0].to_dict()['reference_constraints']['auto_configuration'], auto)
        self.assertEqual(seen, {(p, s) for p in ('BWP', 'UWP') for s in ('Default', 'Validated')})

    def test_uwp_neutral_keeps_branch_lanes_and_weld_pairs(self):
        from pattern_rule_workbench import _base_inputs
        for q, divider in ((2, 2), (4, 2), (6, 3)):
            for factors in ((divider, 2, 1), (divider, 1, 2)):
                with self.subTest(q=q, factors=factors):
                    w, t, l = _base_inputs('UWP', q, 8, 4, 2*divider, factors)
                    _, db = gw.get_winding_layout('UWP', t, w, l)
                    width = q // divider
                    for _, path in db:
                        self.assertEqual(len({(s % q)//width for s, _, _ in path}), 1)
                        for a, b in zip(path[::2], path[1::2]):
                            self.assertEqual(a[0] % q, b[0] % q)
                    self.assertEqual(len({n[:2] for _, p in db for n in p}),
                                     w.num_slots*w.num_layers)

    def test_uwp_auto_and_explicit_transposition_preserve_weld_pairs(self):
        from pattern_rule_workbench import _base_inputs
        def welds(db):
            return {frozenset((a[:2], b[:2])) for _, p in db
                    for a, b in zip(p[::2], p[1::2])}
        for q, divider in ((2, 2), (4, 2), (6, 3)):
            for factors in ((divider, 2, 1), (divider, 1, 2)):
                with self.subTest(q=q, factors=factors):
                    w, t, l = _base_inputs('UWP', q, 8, 4, 2*divider, factors)
                    _, base = gw.get_winding_layout('UWP', t, w, l)
                    if factors[2] == 2:
                        t.tp_type = 'Auto'
                        for key, value in gw.uwp_balanced_q_settings(w).items():
                            setattr(t, key, value)
                    else:
                        t.uni_tp = 1
                        t.jltp = 1
                    _, changed = gw.get_winding_layout('UWP', t, w, l)
                    if q == 2 or factors[2] == 1:
                        self.assertNotEqual(base, changed)
                    self.assertEqual(welds(base), welds(changed))

    def test_tlp_q_and_pp_two_deploys_q_p2_reference(self):
        from pattern_rule_workbench import _base_inputs
        for phases in (3, 5, 7):
            for q, divider in ((2, 2), (4, 4), (4, 2)):
                for layers in (2, 4, 6):
                    with self.subTest(m=phases, q=q, Q=divider, L=layers):
                        w, tp, layout = _base_inputs(
                            'TLP', q, 8, layers, 2*divider,
                            (divider, 2, 1), phases)
                        decision = gw.resolve_pattern_route(
                            'TLP', w, w.branch_dividers, tp, layout)
                        reference = SimpleNamespace(**vars(w))
                        reference.branch_dividers = (divider, 1, 2)
                        source_decision = gw.resolve_pattern_route(
                            'TLP', reference, reference.branch_dividers, tp, layout)
                        if decision.status != 'enabled':
                            continue
                        self.assertEqual(source_decision.status, 'enabled')
                        starts, database = gw.get_winding_layout('TLP', tp, w, layout)
                        tau = phases*q
                        self.assertEqual({s // tau for s, _, _ in starts},
                                         {0, 1, w.num_poles//2, w.num_poles//2+1})
                        self.assertEqual(database.layout_report['pattern_identity']['status'],
                                         'valid')
                        from phase_topology import phase_map
                        records = phase_map(w.num_slots, w.num_poles,
                                            layers, [0]*layers, phases)
                        signs = {(s, l): sign for s, l, _, sign in records}
                        paths = [path for _, path in database]
                        report = validate_branches(paths, records, w.num_slots,
                                                   w.num_poles, w.ab,
                                                   phases=phases)
                        self.assertTrue(report['layout_retained'], report)
                        self.assertEqual(sum(map(len, paths)), w.num_slots*layers)
                        self.assertTrue(all(signs[p[0][:2]] == 1 and
                                            signs[p[-1][:2]] == -1 for p in paths))
                        tau = phases*q
                        for path in paths:
                            for a, b in zip(path, path[1:]):
                                pitch = (b[0]-a[0]+w.num_slots//2)%w.num_slots-w.num_slots//2
                                self.assertEqual(abs(pitch), tau)
                                self.assertIn(abs(b[1]-a[1]), (1, layers-1))

    def test_shared_q_pp_second_sector_deployment(self):
        from pattern_rule_workbench import _base_inputs
        for pattern, q, divider, layers in (
                ('TSP', 2, 2, 4), ('TLP', 2, 2, 4),
                ('ZPP', 4, 2, 4)):
            for phases in (3, 5, 7):
                with self.subTest(pattern=pattern, m=phases):
                    w, tp, layout = _base_inputs(
                        pattern, q, 8, layers, 2*divider, (divider,2,1), phases)
                    decision = gw.resolve_pattern_route(pattern, w, w.branch_dividers, tp, layout)
                    self.assertEqual(decision.status, 'enabled', decision.reason)
                    starts, database = gw.get_winding_layout(pattern, tp, w, layout)
                    tau = phases*q
                    self.assertEqual({s//tau for s, _, _ in starts}, {0,1,4,5})
                    self.assertEqual({l for s,l,_ in starts if s >= w.num_slots//2},
                                     {layers-1})
                    self.assertEqual(starts, [path[0] for _, path in database])
                    self.assertTrue(database.layout_report['layout_retained'])
                    identity = database.layout_report['pattern_identity']
                    self.assertEqual(identity['status'], 'valid', identity['reason'])
                    self.assertFalse(identity['unexpected_pin_types'])
                    directions = {}
                    for edge in identity['weld_edges']:
                        if not edge['layer_step'] or not edge['slot_step']:
                            continue
                        pair = tuple(sorted((edge['start_layer'], edge['end_layer'])))
                        direction = 1 if edge['layer_step']*edge['slot_step'] > 0 else -1
                        directions.setdefault(pair, set()).add(direction)
                    if pattern in ('TSP', 'TLP'):
                        self.assertTrue(all(len(values) == 1 for values in directions.values()),
                                        directions)
                    self.assertIn('sector_deployment', database.layout_report)
                    layout.phase_shift_list = [w.num_slots] * layers
                    equivalent = gw.resolve_pattern_route(
                        pattern, w, w.branch_dividers, tp, layout)
                    self.assertEqual(equivalent.status, 'enabled',
                                     equivalent.reason)
                    shifted_starts, shifted = gw.get_winding_layout(
                        pattern, tp, w, layout)
                    self.assertEqual(shifted_starts, starts)
                    self.assertEqual(list(shifted), list(database))

    def test_lpp_rejects_every_non_full_pp_factor(self):
        from pattern_rule_workbench import _base_inputs

        for phases in (3, 5, 7):
            for divider in (1, 2):
                with self.subTest(m=phases, D=divider):
                    winding, tp, layout = _base_inputs(
                        'LPP', 2, 8, 4, divider, (1, divider, 1), phases)
                    self.assertTrue(gw.pattern_rejects_divider_tuple(
                        'LPP', winding.branch_dividers, 2, 4))
                    decision = gw.resolve_pattern_route(
                        'LPP', winding, winding.branch_dividers, tp, layout)
                    self.assertEqual(decision.rule_id, 'lpp_factor_rejected')
                    self.assertEqual(decision.status, 'disabled')
                    with self.assertRaisesRegex(
                            gw.PatternConfigurationError, 'full pole-pair count'):
                        gw.get_winding_layout('LPP', tp, winding, layout)

    def test_lpp_full_pp_reference_sampled_odd_phase_and_layer_domains(self):
        from pattern_rule_workbench import _base_inputs

        cases = ((1, 4, 4, 3), (2, 4, 6, 5),
                 (3, 6, 4, 7))
        for q, pp, layers, phases in cases:
            with self.subTest(q=q, pp=pp, L=layers, m=phases):
                winding, tp, layout = _base_inputs(
                    'LPP', q, 2 * pp, layers, pp,
                    (1, pp, 1), phases)
                starts, database = gw.get_winding_layout(
                    'LPP', tp, winding, layout)
                self.assertEqual(starts, [path[0] for _, path in database])
                self.assertTrue(database.layout_report['layout_retained'])
                self.assertEqual(
                    database.layout_report['pattern_identity']['status'], 'valid')

    def test_tlp_q_and_pp_two_catalog_and_exclusions(self):
        from pattern_rule_workbench import build_divider_route_catalog, _base_inputs
        record = next(row for row in build_divider_route_catalog('2', 4, 4)
                      if row.pattern == 'TLP' and row.dividers == (2, 2, 1))
        self.assertNotIn(record.status, ('rejected', 'unsupported-yet', 'Candidate'))
        for factors in ((1, 2, 1), (2, 4, 1), (2, 2, 2)):
            self.assertFalse(gw.pattern_rejects_divider_tuple('TLP', factors, 2))
        self.assertFalse(gw.pattern_rejects_divider_tuple(
            'TLP', (1, 2, 2), 2, pp=4))
        self.assertTrue(gw.pattern_rejects_divider_tuple(
            'TLP', (1, 4, 2), 2, pp=4))
        self.assertTrue(gw.pattern_rejects_divider_tuple(
            'TLP', (1, 2, 2), 2, pp=2))
        rejected = next(row for row in
                        build_divider_route_catalog('2', 4, 4)
                        if row.pattern == 'TLP'
                        and row.dividers == (1, 4, 2))
        self.assertEqual(rejected.status, 'rejected')
        self.assertIn('pp-divider x P2-divider <= pp=4', rejected.reason)
        over_limit, tp, layout = _base_inputs(
            'TLP', 2, 8, 4, 8, (1, 4, 2), 3)
        decision = gw.resolve_pattern_route(
            'TLP', over_limit, (1, 4, 2), tp, layout)
        self.assertEqual(decision.status, 'disabled')
        self.assertIn('pp-divider x P2-divider <= pp=4', decision.reason)
        for q, poles, phases, layers, factors in (
                (2, 6, 3, 4, (2, 2, 1)),
                (2, 8, 4, 4, (2, 2, 1)),
                (2, 8, 3, 3, (2, 2, 1)),
                (3, 8, 3, 4, (2, 2, 1))):
            w, tp, layout = _base_inputs('TLP', q, poles, layers, 4, factors, phases)
            self.assertEqual(gw.resolve_pattern_route(
                'TLP', w, factors, tp, layout).status, 'disabled')

    def test_non_wave_route_resolver_owns_admission_and_explicit_rejections(self):
        from pattern_rule_workbench import _base_inputs

        cases = (
            ('SSP', 2, 8, 6, (1, 2, 1), 'enabled', 'ssp_pp_only'),
            ('SLP', 2, 8, 6, (1, 2, 1), 'enabled', 'slp_pp_only'),
            ('ZLP', 2, 8, 4, (2, 2, 1), 'disabled', 'zlp_factor_rejected'),
            ('ZPP', 4, 8, 4, (2, 1, 2), 'disabled', 'zpp_factor_rejected'),
            ('CP', 2, 8, 4, (1, 2, 2), 'enabled', 'cp_pp_p2'),
            ('LPP', 2, 8, 4, (1, 2, 1), 'disabled', 'lpp_factor_rejected'),
            ('LPP', 2, 8, 4, (1, 4, 1), 'enabled', 'lpp_pp_default'),
            ('TSP', 2, 8, 4, (1, 2, 1), 'enabled', 'tsp_spiral_pass_partition'),
            ('TLP', 2, 8, 4, (1, 2, 1), 'enabled', 'tlp_pp_only_two'),
            ('LPP', 2, 8, 4, (2, 1, 1), 'disabled', 'lpp_factor_rejected'),
        )
        for pattern, q, poles, layers, factors, status, rule_id in cases:
            with self.subTest(pattern=pattern, factors=factors):
                naa = factors[0] * factors[1] * factors[2]
                winding, tp, layout = _base_inputs(
                    pattern, q, poles, layers, naa, factors)
                decision = gw.resolve_pattern_route(
                    pattern, winding, factors, tp, layout)
                self.assertEqual(decision.status, status)
                self.assertEqual(decision.rule_id, rule_id)
                self.assertTrue(decision.reason)

    def test_cp_layer_admission_requires_a_multiple_of_four(self):
        from pattern_rule_workbench import _base_inputs

        factors = (1, 2, 2)
        reason = 'CP requires a positive layer count divisible by 4.'
        winding, tp, layout = _base_inputs('CP', 2, 8, 4, 4, factors)
        decision = gw.resolve_pattern_route('CP', winding, factors, tp, layout)
        self.assertEqual((decision.status, decision.rule_id),
                         ('enabled', 'cp_pp_p2'))
        _, database = gw.get_winding_layout('CP', tp, winding, layout)
        self.assertTrue(database.layout_report['layout_retained'])

        winding, tp, layout = _base_inputs('CP', 2, 8, 6, 4, factors)
        decision = gw.resolve_pattern_route('CP', winding, factors, tp, layout)
        self.assertEqual((decision.status, decision.rule_id),
                         ('disabled', 'cp_layer_multiple_of_four'))
        self.assertEqual(decision.reason, reason)
        with patch.object(gw, '_dispatch_winding_pattern') as dispatch:
            with self.assertRaisesRegex(gw.PatternConfigurationError, reason):
                gw.get_winding_layout('CP', tp, winding, layout)
        dispatch.assert_not_called()

    def test_zlp_q_divider_and_cp_no_divider_are_explicitly_rejected(self):
        from pattern_rule_workbench import _base_inputs, build_divider_route_catalog

        cases = (
            ('ZLP', 2, 8, (2, 1, 1), 'ZLP does not support Q-divider greater than 1.'),
            ('ZLP', 2, 8, (2, 2, 1), 'ZLP does not support Q-divider greater than 1.'),
            ('ZLP', 2, 8, (2, 2, 2), 'ZLP does not support Q-divider greater than 1.'),
            ('ZLP', 4, 8, (2, 1, 1), 'ZLP does not support Q-divider greater than 1.'),
            ('CP', 2, 8, (1, 1, 1), 'CP does not allow the no-divider (1,1,1) route.'),
        )
        for pattern, q, poles, factors, reason in cases:
            with self.subTest(pattern=pattern, q=q, factors=factors):
                naa = math.prod(factors)
                winding, tp, layout = _base_inputs(
                    pattern, q, poles, 4, naa, factors)
                self.assertTrue(gw.pattern_rejects_divider_tuple(pattern, factors, q))
                self.assertEqual(gw.divider_exclusion_reason(pattern, factors, q), reason)
                if pattern == 'ZLP':
                    self.assertFalse(gw.supports_integer_zlp_factors(winding, factors))
                decision = gw.resolve_pattern_route(
                    pattern, winding, factors, tp, layout)
                self.assertEqual(decision.status, 'disabled')
                self.assertEqual(decision.reason, reason)
                with patch.object(gw, '_dispatch_winding_pattern') as dispatch:
                    with self.assertRaisesRegex(gw.PatternConfigurationError, reason[:3]):
                        gw.get_winding_layout(pattern, tp, winding, layout)
                    dispatch.assert_not_called()
                row = next(row for row in build_divider_route_catalog(str(q), poles // 2, 4)
                           if row.pattern == pattern and row.dividers == factors)
                self.assertEqual((row.status, row.reason), ('rejected', reason))

    def test_high_value_non_wave_routes_use_symbolic_odd_phase_rules(self):
        from pattern_rule_workbench import _base_inputs

        cases = (
            ('SSP', 2, 8, 6, (1, 2, 1)),
            ('SLP', 2, 8, 6, (1, 2, 1)),
            ('ZPP', 2, 8, 6, (1, 2, 2)),
            ('CP', 2, 8, 4, (1, 2, 2)),
            ('LPP', 2, 8, 4, (1, 4, 1)),
        )
        for phases in (3, 5, 7):
            for pattern, q, poles, layers, factors in cases:
                with self.subTest(phases=phases, pattern=pattern):
                    naa = factors[0] * factors[1] * factors[2]
                    winding, tp, layout = _base_inputs(
                        pattern, q, poles, layers, naa, factors)
                    winding.num_phases = phases
                    winding.num_slots = phases * q * poles
                    decision = gw.resolve_pattern_route(
                        pattern, winding, factors, tp, layout)
                    self.assertEqual(decision.status, 'enabled', decision.reason)
                    starts, database = gw.get_winding_layout(
                        pattern, tp, winding, layout)
                    self.assertEqual(starts, [path[0] for _, path in database])
                    self.assertTrue(database.layout_report['layout_retained'],
                                    database.layout_report)

    def test_pattern_identity_reports_pin_profiles_and_isolates_new_pin_types(self):
        from copy import deepcopy
        from pattern_rule_workbench import _base_inputs
        from layout_analysis import analyze_pattern_identity

        expected = {
            'SSP': {'ALWP', 'SLPP'},
            'SLP': {'ALLP', 'SLPP'},
            'TSP': {'ALWP', 'CLWP'},
            'TLP': {'ALLP', 'CLLP'},
            'ZLP': {'ALLP', 'SLPP'},
            'ZPP': {'SLPP'},
            'CP': {'CLWP'},
            'LPP': {'SLPP'},
        }
        for pattern, pin_types in expected.items():
            with self.subTest(pattern=pattern):
                poles = 8 if pattern == 'ZLP' else 4
                winding, tp, layout = _base_inputs(pattern, 2, poles, 4, 2)
                winding.branch_dividers = tuple(gw.classify_branch_mode(
                    2, 2, poles, pattern)[1:4])
                if pattern == 'ZLP':
                    winding.branch_dividers = (1, 1, 2)
                _, database = gw.get_winding_layout(pattern, tp, winding, layout)
                report = analyze_pattern_identity(
                    pattern, database, winding, layout)
                self.assertEqual(set(report['pin_types']), pin_types)
                self.assertEqual(report['status'], 'valid', report)
                # Compatible short signatures are diagnostics, not an identity
                # veto; each branch must preserve the selected ordered family.
                self.assertIn(pattern, report['compatible_patterns'])
                self.assertTrue(all(row['status'] == 'valid'
                                    for row in report['branch_identity']))

        winding, tp, layout = _base_inputs('ZPP', 2, 4, 4, 2)
        winding.branch_dividers = (2, 1, 1)
        _, database = gw.get_winding_layout('ZPP', tp, winding, layout)
        changed = deepcopy(database)
        changed[0][1][1] = (changed[0][1][1][0], 1,
                            changed[0][1][1][2])
        report = analyze_pattern_identity('ZPP', changed, winding, layout)
        self.assertEqual(report['status'], 'candidate')
        self.assertIn('ALPP', report['unexpected_pin_types'])

    def test_known_structure_failures_are_disabled_before_generation(self):
        from pattern_rule_workbench import _base_inputs

        cases = (
            ('CP', 2, 4, 8, (1, 2, 2), 'duplicate slot/layer'),
        )
        for pattern, q, poles, layers, factors, reason in cases:
            with self.subTest(pattern=pattern):
                naa = factors[0] * factors[1] * factors[2]
                winding, tp, layout = _base_inputs(
                    pattern, q, poles, layers, naa, factors)
                decision = gw.resolve_pattern_route(
                    pattern, winding, factors, tp, layout)
                self.assertEqual(decision.status, 'disabled')
                self.assertIn(reason, decision.reason)

    def test_identity_candidate_is_workbench_only(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'CP', 2, 8, 4, 4, (1, 2, 2), phases=5)
        identity = {'status': 'candidate', 'reason': 'new body pin role'}
        gw._cached_neutral_non_wave_preflight.cache_clear()
        try:
            with patch('layout_analysis.analyze_pattern_identity',
                       return_value=identity):
                decision = gw.resolve_pattern_route(
                    'CP', winding, winding.branch_dividers, tp, layout)
                self.assertEqual(decision.status, 'candidate')
                with self.assertRaisesRegex(ValueError, 'Candidate'):
                    gw.get_winding_layout('CP', tp, winding, layout)
                _, database = gw.get_winding_layout(
                    'CP', tp, winding, layout, allow_candidate=True)
                self.assertEqual(
                    database.layout_report['pattern_identity']['status'],
                    'candidate')
        finally:
            gw._cached_neutral_non_wave_preflight.cache_clear()

    def test_non_wave_configuration_capabilities_classify_before_generation(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'SSP', 2, 8, 6, 2, (1, 2, 1), phases=5)
        tp.tp_type = 'Auto'
        self.assertEqual(gw.resolve_pattern_route(
            'SSP', winding, winding.branch_dividers, tp, layout).status,
            'enabled')

        cases = (
            ('Times', {'tp_times': 1}, {}),
            ('Interval', {'tp_interval': 2}, {}),
            ('Regular', {'uni_tp': 1}, {}),
            ('Regular', {}, {'phase_shift_list': [0, 1, 0, 1, 0, 1]}),
            ('Regular', {}, {'radial_shift': 1}),
            ('Regular', {}, {'inlet_index_adjustments_phase_a': [1, 0]}),
        )
        for tp_type, tp_values, layout_values in cases:
            with self.subTest(tp_type=tp_type, tp_values=tp_values,
                              layout_values=layout_values):
                winding, tp, layout = _base_inputs(
                    'SSP', 2, 8, 6, 2, (1, 2, 1), phases=5)
                tp.tp_type = tp_type
                for key, value in tp_values.items():
                    setattr(tp, key, value)
                for key, value in layout_values.items():
                    setattr(layout, key, value)
                decision = gw.resolve_pattern_route(
                    'SSP', winding, winding.branch_dividers, tp, layout)
                if 'inlet_index_adjustments_phase_a' in layout_values:
                    self.assertEqual(decision.status, 'disabled')
                    self.assertIn('no inlet adjustment', decision.reason)
                else:
                    self.assertEqual(decision.status, 'enabled', decision.reason)
                    if tp_type == 'Interval':
                        with self.assertRaisesRegex(ValueError, 'duplicate slot/layer'):
                            gw.get_winding_layout('SSP', tp, winding, layout)
                    else:
                        gw.get_winding_layout('SSP', tp, winding, layout)

        winding, tp, layout = _base_inputs(
            'SSP', 2, 8, 6, 2, (1, 2, 1), phases=5)
        branch_length = winding.num_poles*winding.num_layers*winding.q//winding.ab
        for tp_type, field, value, phrase in (
                ('Times', 'tp_times', 0, 'Times requires'),
                ('Times', 'tp_times', branch_length, 'Times requires'),
                ('Interval', 'tp_interval', 0, 'Interval requires'),
                ('Interval', 'tp_interval', branch_length, 'Interval requires')):
            with self.subTest(tp_type=tp_type, field=field, value=value):
                tp.tp_type = tp_type
                setattr(tp, field, value)
                decision = gw.resolve_pattern_route(
                    'SSP', winding, winding.branch_dividers, tp, layout)
                self.assertEqual(decision.status, 'disabled')
                self.assertIn(phrase, decision.reason)
                tp.tp_type = 'Regular'
                setattr(tp, field, 0)

        tp.tp_type = 'Auto'
        tp.uni_tp = winding.q
        tp.pole_group_tp = {'PoleN': {'tp_type': 'Regular',
                                      'uni_tp': winding.q}}
        layout.phase_shift_list = [winding.num_slots] * winding.num_layers
        layout.inlet_index_adjustments_phase_a = [branch_length, 0]
        normalized = gw.resolve_pattern_route(
            'SSP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(normalized.status, 'enabled', normalized.reason)
        self.assertEqual(normalized.effective_configuration, 'Regular')

        winding, tp, layout = _base_inputs(
            'ZPP', 2, 8, 6, 4, (1, 2, 2), phases=5)
        layout.inlet_from_weld_side = 0
        decision = gw.resolve_pattern_route(
            'ZPP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.status, 'disabled')
        self.assertIn('weld-side inlet', decision.reason)

        winding, tp, layout = _base_inputs(
            'SSP', 2, 8, 6, 2, (2, 1, 1), phases=5)
        tp.tp_type = 'Times'
        tp.tp_times = 1
        decision = gw.resolve_pattern_route(
            'SSP', winding, winding.branch_dividers, tp, layout)
        self.assertTrue(decision.is_default)
        self.assertEqual(decision.status, 'enabled', decision.reason)

    def test_target_domain_route_counts_by_phase(self):
        for phases in (3, 5, 7):
            expected = {'SSP': 690, 'SLP': 1840, 'ZPP': 880,
                        'ZLP': {3: 450, 5: 50, 7: 55}[phases], 'CP': 69}
            counts = Counter()
            lpp_defaults = 0
            for q in range(2, 7):
                for pp in range(2, 11):
                    poles = 2 * pp
                    for layers in range(2, 21, 2):
                        for q_divider in gw.divisors(q):
                            for pp_divider in gw.divisors(pp):
                                for p2_divider in (1, 2):
                                    factors = (q_divider, pp_divider, p2_divider)
                                    winding = SimpleNamespace(
                                        q=q, num_slots=phases*q*poles,
                                        num_poles=poles, num_phases=phases,
                                        num_layers=layers,
                                        ab=q_divider*pp_divider*p2_divider,
                                        branch_dividers=factors)
                                    for pattern in expected:
                                        if gw.selected_integer_divider_route(
                                                pattern, winding) is not None:
                                            counts[pattern] += 1
                        lpp_defaults += 1
            self.assertEqual(dict(counts), expected)
            self.assertEqual(lpp_defaults, 450)

    def test_all_patterns_auto_configuration_status(self):
        from pattern_rule_workbench import (
            PATTERNS, _base_inputs, build_divider_route_catalog, generate_route_drafts)
        seen = set()
        for q in ('2', '4'):
            for row in build_divider_route_catalog(q, 4, 4):
                if row.status in ('rejected', 'unsupported-yet'):
                    continue
                with self.subTest(pattern=row.pattern, q=q, factors=row.dividers):
                    w,t,l = _base_inputs(row.pattern,row.q,8,4,row.naa,row.dividers)
                    _,db = gw.get_auto_configured_layout(row.pattern,t,w,l)
                    auto = db.auto_configuration
                    assessment = auto['assessment']
                    seen.add(row.pattern)
                    self.assertTrue(db.layout_report['layout_retained'])
                    self.assertEqual(row.status == 'not strong symmetry layout',
                                     assessment['hard_no'])
                    if assessment['hard_no']:
                        self.assertTrue(assessment['proof'])
                        self.assertEqual(auto['attempts'], 0)
                    elif auto['status'] == 'strong symmetry layout':
                        self.assertTrue(assessment['strong'])
                        self.assertTrue(db.layout_report['electrically_valid'])
                    else:
                        self.assertEqual(row.status, 'auto configure pending')
        self.assertEqual(seen, set(PATTERNS))
        row = next(r for r in build_divider_route_catalog('2',4,4)
                   if r.pattern == 'TLP' and r.dividers == (2,1,2))
        self.assertEqual(row.status, 'Default')
        drafts = generate_route_drafts(row)
        self.assertEqual(drafts[0].reference_constraints['auto_configuration']['status'],
                         'strong symmetry layout')

    def test_uwp_remaining_pp_two_admission_cases(self):
        from pattern_rule_workbench import _base_inputs
        cases=[(q,2,1) for q in range(2,7)]
        cases += [(q,pp,2) for q in (4,6) for pp in (2,6,10)]
        cases += [(6,pp,3) for pp in (2,4,8,10)]
        for q,pp,Q in cases:
            for layers in (2,4,6):
                with self.subTest(q=q,pp=pp,Q=Q,layers=layers):
                    w,t,l=_base_inputs('UWP',q,2*pp,layers,2*Q,(Q,2,1))
                    self.assertIsNotNone(gw.selected_integer_divider_route('UWP',w))
                    for shifts in ([0]*layers,[0,1]*(layers//2)):
                        l.phase_shift_list=shifts
                        starts,db=gw.get_winding_layout('UWP',t,w,l)
                        report=db.layout_report
                        self.assertTrue(report['layout_retained'],report)
                        records=gw.phase_map(w.num_slots,2*pp,layers,shifts)
                        signs={(s,layer):sign for s,layer,phase,sign in records}
                        self.assertTrue(all(signs[s[:2]]==1 for s in starts))
                        self.assertEqual(len({n[:2] for _,p in db for n in p}),w.num_slots*layers)
                        self.assertEqual(len({len(p) for _,p in db}),1)

    def test_uwp_full_q_only_rejected_as_bwp_duplicate(self):
        from pattern_rule_workbench import _base_inputs,build_divider_route_catalog
        for q in (2,3,4,6):
            rows=build_divider_route_catalog(str(q),4,4)
            row=next(r for r in rows if r.pattern=='UWP' and r.dividers==(q,1,1))
            self.assertEqual(row.status,'rejected')
            self.assertIn('same as BWP',row.reason)
            w,t,l=_base_inputs('UWP',q,8,4,q,(q,1,1))
            with self.assertRaisesRegex(ValueError,'same as BWP'):
                gw.get_winding_layout('UWP',t,w,l)
            self.assertFalse(gw.pattern_rejects_divider_tuple('BWP',(q,1,1),q))
        self.assertFalse(gw.pattern_rejects_divider_tuple('UWP',(1,1,1),1))
        self.assertFalse(gw.pattern_rejects_divider_tuple('UWP',(2,1,1),4))

    def test_uwp_shared_pp_p2_allowance(self):
        from pattern_rule_workbench import _base_inputs,build_divider_route_catalog
        for q in ('4','6','1.5'):
            for row in build_divider_route_catalog(q,6,4):
                if row.pattern != 'UWP' or row.dividers[1]*row.dividers[2] in (1,2):
                    continue
                self.assertEqual(row.status,'rejected')
                self.assertIn('product must be 1 or 2',row.reason)
                w,t,l=_base_inputs('UWP',row.q,12,4,row.naa,row.dividers)
                with self.assertRaisesRegex(ValueError,'product must be 1 or 2'):
                    gw.get_winding_layout('UWP',t,w,l)
        for factors in ((1,1,1),(2,2,1),(2,1,2)):
            self.assertFalse(gw.pattern_rejects_divider_tuple('UWP',factors))

    def test_general_strong_symmetry_count_rule(self):
        from automatic_transposition import strong_symmetry_count_rule
        for q in (Fraction(1),Fraction(3,2),Fraction(4)):
            for pp in (1,2,4):
                for layers in (2,4,6):
                    slots=int(6*q*pp)
                    records=default_phase_map(slots,2*pp,layers)
                    counts=Counter((phase,layer,(2*pp*s+(slots if sign<0 else 0))%(2*slots))
                                   for s,layer,phase,sign in records)
                    for naa in (1,2,3,4,8):
                        rule=strong_symmetry_count_rule(records,slots,2*pp,naa)
                        self.assertEqual(rule['hard_no'],any(n%naa for n in counts.values()))
                        self.assertEqual(rule['hard_no'],bool(rule['category_count_gcd']%naa))
                        self.assertEqual(rule,strong_symmetry_count_rule(list(reversed(records)),slots,2*pp,naa))
        with self.assertRaises(ValueError):
            strong_symmetry_count_rule([],96,8,4)

    def test_auto_configure_strong_pending_and_hard_no(self):
        from pattern_rule_workbench import _base_inputs, build_divider_route_catalog, generate_route_drafts
        for factors,naa,expected in (((2,1,1),2,'strong symmetry layout'),
                                     ((4,2,1),8,'strong symmetry layout'),
                                     ((2,2,1),4,'auto configure pending'),
                                     ((4,4,1),16,'not strong symmetry layout')):
            with self.subTest(factors=factors):
                w,t,l=_base_inputs('BWP',4,8,4,naa,factors)
                _,db=gw.get_auto_configured_layout('BWP',t,w,l)
                auto=db.auto_configuration
                self.assertEqual(auto['status'],expected)
                if expected=='strong symmetry layout':
                    self.assertTrue(auto['assessment']['strong'])
                    self.assertTrue(db.layout_report['electrically_valid'])
                    # Group by actual phase, never by assumed branch-ID blocks.
                    records=default_phase_map(96,8,4)
                    shuffled=list(reversed(db))
                    self.assertTrue(gw.auto_tp.assess_strong_symmetry(shuffled,records,96,8,naa)['strong'])
                elif auto['assessment']['hard_no']:
                    self.assertTrue(all(p['remainder'] for p in auto['assessment']['proof']))
                else:
                    self.assertFalse(auto['assessment']['hard_no'])
                    self.assertFalse(auto['completed'])
                    _, baseline = gw.get_winding_layout('BWP', t, w, l)
                    self.assertEqual(db, baseline)
                    self.assertTrue(db.layout_report['layout_retained'])
                    self.assertEqual(db.layout_report['electrically_valid'],
                                     baseline.layout_report['electrically_valid'])
        rows=build_divider_route_catalog('4',4,4)
        grouped=[r for r in rows if r.pattern in ('BWP','UWP') and r.status=='not strong symmetry layout']
        self.assertEqual([(r.pattern,r.dividers) for r in grouped],[('BWP',(4,4,1))])
        solved=next(r for r in rows if r.pattern=='BWP' and r.dividers==(2,1,1))
        drafts=generate_route_drafts(solved)
        self.assertEqual(drafts[0].reference_constraints['auto_configuration']['status'],
                         'strong symmetry layout')

    def test_catalog_rejections_have_unified_status_and_reason(self):
        from pattern_rule_workbench import build_divider_route_catalog
        for q in ('4','1.5'):
            rows=build_divider_route_catalog(q,4,4)
            self.assertTrue(any(r.status=='rejected' for r in rows))
            self.assertTrue(any(r.status=='unsupported-yet' for r in rows))
            for row in rows:
                self.assertNotIn(row.status,('unsupported','Unsupported','Eligible but rejected for this case'))
                if row.status=='rejected':
                    self.assertTrue(row.reason.strip())

    def test_uwp_q_only_series_from_oriented_q_p2(self):
        from pattern_rule_workbench import _base_inputs
        for q,Q,poles in ((4,2,8),(6,2,4),(6,3,6),(8,4,8),(9,3,6)):
            for layers in (2,4,6):
                with self.subTest(q=q,Q=Q,poles=poles,layers=layers):
                    w,t,l=_base_inputs('UWP',q,poles,layers,Q,(Q,1,1))
                    self.assertEqual(gw.selected_integer_divider_route('UWP',w),'uwp_q_only_series')
                    starts,db=gw.get_winding_layout('UWP',t,w,l)
                    reference=SimpleNamespace(**vars(w))
                    reference.ab=2*Q
                    reference.branch_dividers=(Q,1,2)
                    _,source=gw.get_winding_layout('UWP',t,reference,l)
                    self.assertEqual(len(db),3*Q)
                    for phase in range(3):
                        for group in range(Q):
                            a=source[phase*2*Q+group][1]
                            b=source[phase*2*Q+Q+group][1]
                            self.assertEqual(a[-1][1],b[0][1])
                            self.assertEqual(db[phase*Q+group][1],a+b)
                    self.assertTrue(db.layout_report['layout_retained'],db.layout_report)
                    self.assertEqual(starts,[p[0] for _,p in db])
                    self.assertEqual(len(db.series_connections),3*Q)

    def test_existing_constructions_extended_divider_routes(self):
        from pattern_rule_workbench import _base_inputs, _probe_route
        cases = [('BWP',4,8,(2,2,1)),('BWP',4,8,(2,4,1)),
                 ('BWP',6,12,(2,3,1)),('BWP',6,12,(3,2,1)),
                 ('UWP',3,6,(3,1,2)),('UWP',4,8,(4,1,2)),
                 ('UWP',6,12,(6,1,2)),('UWP',4,8,(4,2,1)),
                 ('UWP',6,12,(6,2,1))]
        for pattern,q,poles,factors in cases:
            for layers in (2,4,6):
                with self.subTest(pattern=pattern,q=q,factors=factors,layers=layers):
                    naa=factors[0]*factors[1]*factors[2]
                    w,t,l=_base_inputs(pattern,q,poles,layers,naa,factors)
                    self.assertIsNotNone(gw.selected_integer_divider_route(pattern,w))
                    starts,db=gw.get_winding_layout(pattern,t,w,l)
                    self.assertTrue(db.layout_report['layout_retained'],db.layout_report)
                    self.assertEqual(starts,[path[0] for _,path in db])
                    if pattern=='UWP':
                        signs={(s,layer):sign for s,layer,phase,sign in
                               default_phase_map(w.num_slots,poles,layers)}
                        self.assertTrue(all(signs[p[0][:2]]==1 for _,p in db))
                    ok,reason=_probe_route(pattern,q,poles,layers,naa,factors)
                    self.assertTrue(ok,reason)

    def test_uwp_pp_and_p2_are_mutually_exclusive(self):
        from pattern_rule_workbench import _base_inputs, build_divider_route_catalog
        for q in ('4','1.5'):
            rows = build_divider_route_catalog(q,4,4)
            excluded = [r for r in rows if r.pattern == 'UWP'
                        and r.dividers[1] > 1 and r.dividers[2] == 2]
            self.assertTrue(excluded)
            for row in excluded:
                self.assertEqual(row.status,'rejected')
                self.assertIn('product must be 1 or 2',row.reason)
                w,t,l = _base_inputs('UWP',row.q,8,4,row.naa,row.dividers)
                self.assertIsNone(gw.selected_integer_divider_route('UWP',w))
                with self.assertRaisesRegex(ValueError,'product must be 1 or 2'):
                    gw.get_winding_layout('UWP',t,w,l)
        for factors,naa in (((1,2,1),2),((2,2,1),4),((2,1,2),4)):
            w,t,l = _base_inputs('UWP',4,8,4,naa,factors)
            self.assertFalse(gw.pattern_rejects_divider_tuple('UWP',factors))
            gw.get_winding_layout('UWP',t,w,l)

    def test_designer_package_preserves_conductor_sets(self):
        package = Path(__file__).parent / 'pattern_rule_drafts' / (
            'UWP_q-2_pp-4_L-4_Naa-2_Q-1_PP-2_P2-1_Ph-A_Side-insert_Shifts-0-0-0-0_'
            '20260921-203707-699283.json')
        if not package.exists():
            self.skipTest('Original designer package is no longer in pattern_rule_drafts.')
        data = json.loads(package.read_text(encoding='utf-8'))
        from pattern_rule_workbench import _base_inputs
        w,t,l = _base_inputs('UWP',2,8,4,2,(1,2,1))
        _,db = gw.get_winding_layout('UWP',t,w,l)
        for branch, generated in zip(data['branches'],db[:2]):
            expected = [(n['slot']-1,n['layer']-1) for n in branch['path']]
            self.assertEqual(set(n[:2] for n in generated[1]),set(expected))
        l.phase_shift_list = [0,1,0,1]
        _, shifted = gw.get_winding_layout('UWP',t,w,l)
        self.assertEqual([[((n[0]+l.phase_shift_list[n[1]]) % w.num_slots,n[1])
                           for n in p] for _,p in db],
                         [[n[:2] for n in p] for _,p in shifted])
        for q in (3,4,5):
            w.q=q
            self.assertTrue(gw.supports_uwp_complementary_waves(w))

    def test_designer_uwp_pp_two_branch_wave_order(self):
        for q in (1, 2, 3, 4, 5, 7, 11):
            for poles in (8, 12, 16):
                for layers in (2, 4, 6):
                    with self.subTest(q=q, poles=poles, layers=layers):
                        w = SimpleNamespace(q=q, num_slots=3*q*poles,
                            num_poles=poles, num_layers=layers, num_phases=3,
                            ab=2, branch_dividers=(1, 2, 1))
                        t = SimpleNamespace(tp_type='Regular', tp_interval=0,
                            tp_times=0, uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1)
                        l = SimpleNamespace(phase_shift_list=[0]*layers,
                            radial_shift=0, inlet_from_weld_side=0)
                        _, db = gw.get_winding_layout('UWP', t, w, l)
                        paths = [b[1] for b in db]
                        self.assertEqual(paths[1][0][:2], (w.num_slots//2, layers-1))
                        for branch, path in enumerate(paths[:2]):
                            for a,b in zip(path,path[1:]):
                                self.assertEqual(abs(b[1]-a[1]),1)
                                self.assertIn(((1 if branch == 0 else -1)*(b[0]-a[0])) % w.num_slots,
                                              (3*q-1,3*q,3*q+1))
                            for index, node in enumerate(path):
                                pair = index // (q*poles)
                                expected_pair = pair if branch == 0 else layers//2-1-pair
                                self.assertEqual(node[1]//2, expected_pair)
                        report = validate_branches(paths,
                            default_phase_map(w.num_slots,poles,layers), w.num_slots,poles,2)
                        self.assertTrue(report['electrically_valid'], report)

    def test_uwp_pp_configurations_apply_to_multiple_dividers(self):
        from pattern_rule_workbench import _base_inputs
        from phase_topology import phase_map
        for ab,poles in ((2,8),(4,16),(6,24)):
            for tp_values in ({'uni_tp':1}, {'jltp':1},
                              {'uni_tp':1,'jltp':1},
                              {'pole_group_tp':{'PoleN':{'uni_tp':1}}}):
                with self.subTest(ab=ab,tp=tp_values):
                    w,t,l = _base_inputs('UWP',2,poles,4,ab,(1,ab,1))
                    _,base = gw.get_winding_layout('UWP',t,w,l)
                    for key,value in tp_values.items(): setattr(t,key,value)
                    _,changed = gw.get_winding_layout('UWP',t,w,l)
                    self.assertNotEqual(base,changed)
                    for shifts in ([1]*4,[0,1,0,1],[0,0,1,1],[12]*4):
                        l.phase_shift_list=shifts
                        starts,db=gw.get_winding_layout('UWP',t,w,l)
                        self.assertEqual(starts,[path[0] for _,path in db])
                        self.assertEqual([[((s+shifts[layer])%w.num_slots,layer)
                                           for s,layer,_ in path] for _,path in changed],
                                         [[n[:2] for n in path] for _,path in db])
                        report=validate_branches([path for _,path in db],
                            phase_map(w.num_slots,poles,4,shifts),w.num_slots,poles,ab)
                        self.assertTrue(report['electrically_valid'],report)

    def test_uwp_pp_settings_reject_unimplemented_or_invalid_output(self):
        from pattern_rule_workbench import _base_inputs
        w,t,l=_base_inputs('UWP',2,8,4,2,(1,2,1))
        t.pltp_fl=1
        with self.assertRaisesRegex(ValueError,'pltp_fl'):
            gw.get_winding_layout('UWP',t,w,l)
        t.pltp_fl=0
        l.phase_shift_list=[0,-20,0,-20]
        with self.assertRaisesRegex(ValueError,'reverse or overrun'):
            gw.get_winding_layout('UWP',t,w,l)

    def test_uwp_pp_two_integer_q_layer_shifts(self):
        from pattern_rule_workbench import _base_inputs
        from phase_topology import phase_map
        for q in (1, 2, 3, 4, 5, 7, 11):
            with self.subTest(q=q):
                w,t,l = _base_inputs('UWP',q,8,4,2,(1,2,1))
                self.assertEqual(gw.selected_integer_divider_route('UWP',w),'pp_only')
                _,base = gw.get_winding_layout('UWP',t,w,l)
                l.phase_shift_list = [0,1,0,1]
                _,db = gw.get_winding_layout('UWP',t,w,l)
                self.assertEqual(
                    [[((s+l.phase_shift_list[layer])%w.num_slots,layer)
                       for s,layer,_ in path] for _,path in base],
                    [[n[:2] for n in path] for _,path in db])
                report = validate_branches([path for _,path in db],
                    phase_map(w.num_slots,8,4,l.phase_shift_list),w.num_slots,8,2)
                self.assertTrue(report['electrically_valid'],report)

    def test_uwp_proper_q_pp_two_uses_q_p2_rule(self):
        from pattern_rule_workbench import _base_inputs
        from phase_topology import phase_map
        for q,divider,poles in ((4,2,8),(6,2,8),(6,3,12),
                                (8,2,8),(8,4,16),(9,3,12),(12,3,12)):
            for layers in (2,4,6):
                with self.subTest(q=q,divider=divider,layers=layers):
                    w,t,l = _base_inputs('UWP',q,poles,layers,2*divider,(divider,2,1))
                    self.assertEqual(gw.selected_integer_divider_route('UWP',w),'uwp_q_factor_pp')
                    _,base = gw.get_winding_layout('UWP',t,w,l)
                    reference = SimpleNamespace(**vars(w))
                    reference.branch_dividers = (divider,1,2)
                    # Compare before P2-specific terminal orientation: the real
                    # route is still (Q,2,1), not a relabelled P2 route.
                    _,expected = gw._uwp_balanced_q_factor(t,reference,l)
                    for index, ((_,actual),(_,source)) in enumerate(zip(base,expected)):
                        descending = index % (2*divider) >= divider
                        rotation = (actual[0][0]-source[0][0]) % w.num_slots
                        transformed = [((slot+rotation)%w.num_slots,
                                        layers-1-layer if descending else layer,position)
                                       for slot,layer,position in source]
                        if descending:
                            anchor = transformed[0][0]-transformed[0][0]%q
                            transformed = [((2*anchor-(s-s%q)+s%q)%w.num_slots,layer,pos)
                                           for s,layer,pos in transformed]
                        self.assertEqual(actual,transformed)
                    if q == 4 and layers == 4:
                        self.assertEqual([p[0][:2] for _,p in base[:4]],
                                         [(0,0),(2,0),(48,3),(50,3)])
                    self.assertEqual(w.branch_dividers,(divider,2,1))
                    for branch_index, (_,path) in enumerate(base):
                        self.assertEqual(Counter(n[1]//2 for n in path),
                                         dict.fromkeys(range(layers//2),(q//divider)*poles))
                        for a,b in zip(path,path[1:]):
                            self.assertEqual(abs(b[1]-a[1]),1)
                            direction = 1 if branch_index%(2*divider)<divider else -1
                            self.assertTrue(2*q < (direction*(b[0]-a[0]))%w.num_slots < 4*q)
                    l.phase_shift_list = [1]*layers
                    _,db = gw.get_winding_layout('UWP',t,w,l)
                    self.assertEqual(len(db),3*2*divider)
                    report = validate_branches([path for _,path in db],
                        phase_map(w.num_slots,poles,layers,l.phase_shift_list),
                        w.num_slots,poles,2*divider)
                    self.assertTrue(report['topology_valid'],report)
                    signs = {(s,layer):sign for s,layer,phase,sign in phase_map(
                        w.num_slots,poles,layers,l.phase_shift_list)}
                    self.assertTrue(all(signs[p[0][:2]] == 1 for _,p in db))

    def test_uwp_q_pp_reference_retains_unbalanced_shift(self):
        from pattern_rule_workbench import _base_inputs
        w,t,l = _base_inputs('UWP',6,8,4,4,(2,2,1))
        l.phase_shift_list = [0,1,0,1]
        _,db = gw.get_winding_layout('UWP',t,w,l)
        self.assertEqual(db.layout_status,'not strong symmetry layout')
        self.assertTrue(db.layout_report['layout_retained'])
        self.assertFalse(db.layout_report['electrically_valid'])
        self.assertEqual(db.layout_report['errors'],['parallel_emf_mismatch'])

    def test_uwp_unbalanced_plan_retention_and_occupancy_guards(self):
        from pattern_rule_workbench import _base_inputs, _probe_route
        from copy import deepcopy
        w,t,l = _base_inputs('UWP',6,4,2,6,(3,1,2))
        self.assertTrue(gw.supports_uwp_balanced_q_factor(w,w.branch_dividers))
        _,db = gw.get_winding_layout('UWP',t,w,l)
        self.assertEqual(db.layout_status,'not strong symmetry layout')
        self.assertTrue(db.layout_report['topology_valid'])
        self.assertEqual(len({n[:2] for _,p in db for n in p}),w.num_slots*w.num_layers)
        self.assertEqual(len({len(p) for _,p in db}),1)
        ok,reason = _probe_route('UWP',6,4,2,6,(3,1,2))
        self.assertTrue(ok)
        self.assertTrue(reason.startswith('not strong symmetry layout'))
        corrupt = deepcopy(db)
        corrupt[0][1][0] = corrupt[0][1][1]
        with self.assertRaisesRegex(ValueError,'duplicate_conductor'):
            gw._validate_selected_electrical('test',corrupt,w,l)
        corrupt = deepcopy(db)
        corrupt[0][1].pop()
        with self.assertRaisesRegex(ValueError,'branch_length'):
            gw._validate_selected_electrical('test',corrupt,w,l)

    def test_uwp_pp_shift_for_other_q_and_zero_config_compatibility(self):
        from pattern_rule_workbench import _base_inputs
        for q,poles,layers,ab in ((1,8,4,4),(3,16,2,4)):
            with self.subTest(q=q):
                w,t,l=_base_inputs('UWP',q,poles,layers,ab,(1,ab,1))
                _,base=gw.get_winding_layout('UWP',t,w,l)
                w._uwp_pp_base=True
                _,old=gw.pattern_UWP(t,w,l)
                self.assertEqual(base,old)
                del w._uwp_pp_base
                l.phase_shift_list=[0,1]*(layers//2)
                _,db=gw.get_winding_layout('UWP',t,w,l)
                self.assertEqual([[((n[0]+l.phase_shift_list[n[1]])%w.num_slots,n[1])
                                   for n in path] for _,path in base],
                                 [[n[:2] for n in path] for _,path in db])

    def test_tlp_signed_lap_count_across_layers_and_poles(self):
        from phase_topology import phase_map
        for poles in (4, 6, 8, 12):
            for layers in (4, 6, 8, 10):
                for direction in (1, -1):
                    with self.subTest(poles=poles, layers=layers, direction=direction):
                        slots = 6*poles
                        winding = SimpleNamespace(q=2, num_slots=slots, num_poles=poles,
                                                  num_layers=layers, num_phases=3, ab=2)
                        tp = SimpleNamespace(tp_type='Regular', tp_interval=0, tp_times=0,
                            uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=direction)
                        layout = SimpleNamespace(phase_shift_list=[0]*layers,
                            radial_shift=0, inlet_from_weld_side=0)
                        _, database = gw.get_winding_layout('TLP', tp, winding, layout)
                        report = validate_branches([b[1] for b in database],
                            phase_map(slots, poles, layers, layout.phase_shift_list),
                            slots, poles, 2)
                        self.assertTrue(report['electrically_valid'], report)

    def test_tlp_four_layer_terminal_side_and_shifted_phase_map(self):
        from phase_topology import phase_map
        for side in (0, 1):
            for shifts in ([0]*4, [0, 1, 0, 1]):
                with self.subTest(side=side, shifts=shifts):
                    winding = SimpleNamespace(q=2, num_slots=24, num_poles=4,
                        num_layers=4, num_phases=3, ab=2)
                    tp = SimpleNamespace(tp_type='Regular', tp_interval=0, tp_times=0,
                        uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1)
                    layout = SimpleNamespace(phase_shift_list=shifts, radial_shift=0,
                        inlet_from_weld_side=side)
                    _, database = gw.get_winding_layout('TLP', tp, winding, layout)
                    report = validate_branches([b[1] for b in database],
                        phase_map(24, 4, 4, shifts), 24, 4, 2)
                    self.assertTrue(report['electrically_valid'], report)

    def test_tsp_signed_jumper_selects_reference_backward_bridge(self):
        winding = SimpleNamespace(q=2, num_slots=24, num_poles=4,
            num_layers=4, num_phases=3, ab=2)
        layout = SimpleNamespace(phase_shift_list=[0]*4, radial_shift=0,
            inlet_from_weld_side=0)
        for direction, expected_pitch in ((-1, -5), (1, 7)):
            with self.subTest(direction=direction):
                tp = SimpleNamespace(tp_type='Regular', tp_interval=0, tp_times=0,
                    uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=1, jld=direction)
                _, database = gw.get_winding_layout('TSP', tp, winding, layout)
                path = database[0][1]
                self.assertEqual(path[7][:2], (6, 3))
                self.assertEqual(path[8][1], 0)
                self.assertEqual((path[8][0]-path[7][0]+12) % 24-12, expected_pitch)
                report = validate_branches([b[1] for b in database],
                    default_phase_map(24, 4, 4), 24, 4, 2)
                self.assertTrue(report['electrically_valid'], report)

    def test_tlp_four_layer_lap_progression_and_electrical_balance(self):
        winding = SimpleNamespace(q=2, num_slots=24, num_poles=4,
                                  num_layers=4, num_phases=3, ab=2)
        tp = SimpleNamespace(tp_type='Regular', tp_interval=0, tp_times=0,
                             uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1)
        layout = SimpleNamespace(phase_shift_list=[0]*4, radial_shift=0,
                                 inlet_from_weld_side=0)
        starts, database = gw.get_winding_layout('TLP', tp, winding, layout)
        paths = [branch[1] for branch in database]
        report = validate_branches(paths, default_phase_map(24, 4, 4), 24, 4, 2)
        self.assertTrue(report['electrically_valid'], report)
        self.assertEqual(len(starts), 6)
        for path in paths:
            # Production P2 orientation may reverse the complete branch.
            path = path if path[0][1] == 0 else path[::-1]
            # One lap traversal has alternating +tau/-tau steps: net +tau,
            # irrespective of even layer count; its return spans top-bottom.
            for offset in range(0, len(path), 4):
                block = path[offset:offset+4]
                self.assertEqual([n[1] for n in block], [0, 1, 2, 3])
                self.assertEqual([(b[0]-a[0]) % 24 for a,b in zip(block,block[1:])],
                                 [6, 18, 6])
            for offset in range(3, len(path)-1, 4):
                self.assertEqual(path[offset+1][1]-path[offset][1], -3)

    def test_manual_sample_requires_parallel_emf_correction(self):
        sample = json.loads(Path(__file__).with_name(
            'pattern_process_draft_q4_UWP_sample.json').read_text())
        paths = [[((node['slot'] - 1 + offset) % 48, node['layer'] - 1)
                  for node in branch['path']]
                 for offset in (0, 8, 16) for branch in sample['branches']]
        report = validate_branches(paths, default_phase_map(48, 4, 6), 48, 4, 4)
        self.assertTrue(report['topology_valid'])
        self.assertEqual(report['errors'], ['parallel_emf_mismatch'])

    def test_uwp_automatic_balanced_q_divider(self):
        tp = SimpleNamespace(tp_type='Regular', tp_interval=0, tp_times=0,
                             uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1)
        for q, divider, poles in ((4, 2, 4), (6, 2, 4), (6, 3, 6),
                                  (8, 4, 8), (9, 3, 18), (12, 6, 12)):
            for layers in (2, 6):
                with self.subTest(q=q, divider=divider, poles=poles, layers=layers):
                    slots, ab = 3*q*poles, 2*divider
                    winding = SimpleNamespace(q=q, num_slots=slots, num_poles=poles,
                        num_layers=layers, num_phases=3, ab=ab,
                        branch_dividers=(divider, 1, 2))
                    layout = SimpleNamespace(phase_shift_list=[0]*layers,
                        radial_shift=0, inlet_from_weld_side=0)
                    tp = SimpleNamespace(tp_type='Auto', jld=1,
                                         **gw.uwp_balanced_q_settings(winding))
                    starts, database = gw.get_winding_layout('UWP', tp, winding, layout)
                    report = validate_branches([b[1] for b in database],
                        default_phase_map(slots, poles, layers), slots, poles, ab)
                    self.assertTrue(report['electrically_valid'], report)
                    for _, path in database:
                        self.assertEqual(Counter(node[0] % q for node in path),
                                         dict.fromkeys(range(q), poles*layers//ab))
                        for index, (a, b) in enumerate(zip(path, path[1:])):
                            pitch = min((b[0]-a[0]) % slots, (a[0]-b[0]) % slots)
                            self.assertTrue(2*q < pitch < 4*q)
                            self.assertEqual(abs(b[1]-a[1]), 1)
                    signs = {(s, l): sign for s, l, phase, sign in
                             default_phase_map(slots, poles, layers)}
                    self.assertTrue(all(signs[node[:2]] == 1 for node in starts))

    def test_uwp_automatic_balance_supports_every_pp_divisor(self):
        tp = SimpleNamespace(tp_type='Regular', tp_interval=0, tp_times=0,
                             uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1)
        for poles in (4, 6, 8, 12):
            pole_pairs = poles // 2
            for pp in gw.divisors(pole_pairs):
                with self.subTest(poles=poles, pp=pp):
                    factors = (2, pp, 2)
                    winding = SimpleNamespace(
                        q=4, num_slots=12*poles, num_poles=poles,
                        num_layers=6, num_phases=3, ab=4*pp,
                        branch_dividers=factors)
                    layout = SimpleNamespace(phase_shift_list=[0]*6,
                        radial_shift=0, inlet_from_weld_side=0)
                    self.assertTrue(gw.supports_uwp_balanced_q_factor(
                        winding, factors))
                    self.assertEqual(gw.selected_integer_divider_route(
                        'UWP', winding), 'uwp_balanced_q')
                    starts, database = gw.get_winding_layout(
                        'UWP', tp, winding, layout)
                    report = validate_branches(
                        [branch[1] for branch in database],
                        default_phase_map(winding.num_slots, poles, 6),
                        winding.num_slots, poles, winding.ab)
                    self.assertTrue(report['topology_valid'], report)
                    self.assertEqual(len(starts), 3*winding.ab)
                    self.assertEqual(len({tuple(node[:2]) for _, path in database
                                          for node in path}), winding.num_slots*6)

    def test_uwp_q6_q8_all_pp_and_odd_phase_matrix(self):
        tp = SimpleNamespace(tp_type='Regular', tp_interval=0, tp_times=0,
                             uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1)
        admitted = rejected = 0
        for phases in (3, 5, 7):
            for q in (6, 8):
                for q_divider in gw.divisors(q):
                    if q_divider in (1, q):
                        continue
                    for poles in (4, 6, 8, 12):
                        for pp in gw.divisors(poles // 2):
                            factors = (q_divider, pp, 2)
                            winding = SimpleNamespace(
                                q=q, num_slots=phases*q*poles, num_poles=poles,
                                num_layers=6, num_phases=phases,
                                ab=2*q_divider*pp, branch_dividers=factors)
                            branch_length = (6//2)*(q//q_divider)*(poles//pp)
                            # A nondivisible count uses the registered
                            # occupancy-safe fallback; PP/P2 exclusion still
                            # applies before construction.
                            mathematically_admissible = (
                                not gw.pattern_rejects_divider_tuple(
                                    'UWP', factors))
                            self.assertEqual(
                                gw.supports_uwp_balanced_q_factor(winding, factors),
                                mathematically_admissible,
                                (phases, q, q_divider, poles, pp, branch_length))
                            if not mathematically_admissible:
                                rejected += 1
                                continue
                            admitted += 1
                            layout = SimpleNamespace(phase_shift_list=[0]*6,
                                radial_shift=0, inlet_from_weld_side=0)
                            with self.subTest(m=phases, q=q, Q=q_divider,
                                              poles=poles, pp=pp):
                                _, database = gw.get_winding_layout(
                                    'UWP', tp, winding, layout)
                                report = validate_branches(
                                    [branch[1] for branch in database],
                                    default_phase_map(winding.num_slots, poles, 6,
                                                      phases),
                                    winding.num_slots, poles, winding.ab, phases)
                                self.assertTrue(report['topology_valid'], report)
        self.assertEqual(admitted, 48)
        self.assertEqual(rejected, 84)
        self.assertGreater(rejected, 0)

    def test_uwp_balanced_route_uses_phase_parity_rule(self):
        base = dict(q=6, num_poles=4, num_layers=6, ab=4,
                    branch_dividers=(2, 1, 2))
        for phases in (1, 2, 4, 6):
            winding = SimpleNamespace(num_phases=phases,
                num_slots=phases*6*4, **base)
            self.assertFalse(gw.supports_uwp_balanced_q_factor(
                winding, winding.branch_dividers))

    def test_uwp_automatic_balance_rejects_incompatible_settings(self):
        winding = SimpleNamespace(q=4, num_slots=48, num_poles=4, num_layers=6,
                                  num_phases=3, ab=4, branch_dividers=(2, 1, 2))
        tp = SimpleNamespace(tp_type='Auto', jld=1, **gw.uwp_balanced_q_settings(winding))
        layout = SimpleNamespace(phase_shift_list=[0]*6, radial_shift=0,
                                 inlet_from_weld_side=0)
        gw.get_winding_layout('UWP', tp, winding, layout)
        for target, key, value in ((tp, 'uni_tp', 2), (tp, 'tp_type', 'Times'), (tp, 'jld', -1),
                                    (layout, 'radial_shift', 1),
                                    (layout, 'phase_shift_list', [1]*6),
                                    (layout, 'inlet_from_weld_side', 1)):
            with self.subTest(key=key):
                original = getattr(target, key)
                setattr(target, key, value)
                with self.assertRaises(ValueError):
                    gw.get_winding_layout('UWP', tp, winding, layout)
                setattr(target, key, original)
        self.assertFalse(gw.supports_uwp_balanced_q_factor(winding, (4, 1, 2)))
        self.assertFalse(gw.supports_uwp_balanced_q_factor(winding, (2, 3, 2)))
        self.assertFalse(gw.supports_uwp_balanced_q_factor(winding, (2, 1, 1)))


    def test_newly_admitted_routes_still_reject_invalid_generated_paths(self):
        tp = SimpleNamespace(tp_type='Regular', tp_interval=0, tp_times=0,
                             uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1)
        cases = [('UWP', q, layers, 2, (1, 2, 1), 'invalid forward edge')
                 for q in (3, 4, 5) for layers in (4, 6)]
        for pattern, q, layers, ab, factors, error in cases:
            with self.subTest(pattern=pattern, q=q, layers=layers):
                winding = SimpleNamespace(q=q, num_slots=q*24, num_poles=8,
                                          num_layers=layers, num_phases=3,
                                          ab=ab, branch_dividers=factors)
                layout = SimpleNamespace(phase_shift_list=[0]*layers,
                                         radial_shift=0, inlet_from_weld_side=0)
                self.assertIsNotNone(
                    gw.selected_integer_divider_route(pattern, winding))
                with self.assertRaisesRegex(ValueError, error):
                    gw.get_winding_layout(pattern, tp, winding, layout)

    def test_q4_uses_general_factor_route_across_layers(self):
        for layers in (2, 4, 6, 8):
            winding = SimpleNamespace(q=4, num_poles=8, num_layers=layers,
                                      num_phases=3, ab=4,
                                      branch_dividers=(2, 1, 2))
            self.assertEqual(gw.selected_integer_divider_route('UWP', winding),
                             'uwp_balanced_q')

    def test_q2_full_factor_has_no_configuration_override(self):
        winding = SimpleNamespace(q=2, num_poles=8, num_layers=6,
                                  num_phases=3, ab=4,
                                  branch_dividers=(2, 2, 1))
        self.assertIsNone(gw.selected_integer_divider_route('UWP', winding))
        with self.assertRaises(ValueError):
            gw.branch_dividers_for_pattern('UWP', winding)

    def test_pp_only_admission_has_no_q_or_layer_whitelist(self):
        for q in (1, 2, 3, 4, 7):
            for layers in (2, 4, 6):
                self.assertTrue(gw.supports_integer_pp_only(
                    'UWP', q, 8, layers, 3, 2))

    def test_half_integer_sector_candidates_beyond_old_whitelist(self):
        tp = SimpleNamespace(tp_type='Regular', tp_interval=0, tp_times=0,
                             uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1)
        layout = SimpleNamespace(phase_shift_list=[0]*6, radial_shift=0,
                                 inlet_from_weld_side=0)
        for pattern in ('BWP', 'UWP'):
            for q in (Fraction(1, 2), Fraction(9, 2), Fraction(11, 2)):
                with self.subTest(pattern=pattern, q=q):
                    winding = SimpleNamespace(q=q, num_slots=int(q*24),
                                              num_poles=8, num_layers=6,
                                              num_phases=3, ab=2)
                    self.assertTrue(gw.is_fractional_sector_array_candidate(
                        pattern, winding))
                    _, database = gw.get_winding_layout(
                        pattern, tp, winding, layout, allow_candidate=True)
                    report = validate_branches(
                        [branch[1] for branch in database],
                        default_phase_map(winding.num_slots, 8, 6),
                        winding.num_slots, 8, 2)
                    self.assertTrue(report['topology_valid'], report['errors'])
                    self.assertEqual(
                        database.layout_report['pattern_identity']['status'],
                        'candidate')

class CpPpFourPassWeaveTests(unittest.TestCase):
    def test_cp_pp_sector_slices_follow_divider_factor(self):
        from collections import Counter
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs

        for q, pp, divider, phases in (
                (2, 8, 8, 3), (2, 12, 12, 3), (2, 16, 8, 3),
                (2, 16, 16, 3), (4, 8, 8, 3), (2, 8, 8, 5),
                (2, 8, 8, 7)):
            with self.subTest(q=q, pp=pp, divider=divider, phases=phases):
                winding, tp, layout = _base_inputs(
                    'CP', q, 2 * pp, 4, divider,
                    (1, divider, 1), phases)
                decision = gw.resolve_pattern_route(
                    'CP', winding, winding.branch_dividers, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                self.assertEqual(decision.route_name, 'cp_pp_sector_slices')
                _, database = gw.get_winding_layout(
                    'CP', tp, winding, layout)
                paths = [path for _, path in database]
                self.assertEqual(len(paths), winding.num_phases * divider)
                self.assertEqual({len(path) for path in paths},
                                 {2 * q * pp * winding.num_layers // divider})
                occupancy = Counter(node[:2] for path in paths for node in path)
                self.assertEqual(len(occupancy), winding.num_slots * 4)
                self.assertTrue(all(count == 1 for count in occupancy.values()))
                self.assertEqual(analyze_pattern_identity(
                    'CP', database, winding, layout)['status'], 'valid')
                self.assertTrue(database.layout_report['layout_retained'])

    def test_cp_pp_sector_slices_do_not_enable_other_factors(self):
        from pattern_rule_workbench import _base_inputs

        for q, pp, divider in ((2, 12, 6), (3, 8, 8)):
            with self.subTest(q=q, pp=pp, divider=divider):
                winding, tp, layout = _base_inputs(
                    'CP', q, 2 * pp, 4, divider,
                    (1, divider, 1), 3)
                decision = gw.resolve_pattern_route(
                    'CP', winding, winding.branch_dividers, tp, layout)
                self.assertNotEqual(decision.route_name, 'cp_pp_sector_slices')

    def test_cp_pp_sector_slices_keep_public_source_failure(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'CP', 2, 16, 8, 8, (1, 8, 1), 3)
        decision = gw.resolve_pattern_route(
            'CP', winding, winding.branch_dividers, tp, layout)
        self.assertNotEqual(decision.status, 'enabled')
        self.assertIn('duplicate', decision.reason.lower())

    def test_public_cp_pp_weave_reproduces_saved_manual_sketch(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs
        from pattern_identity import circular_travel_steps, pole_region_crossings

        q, poles, layers, phases = 2, 8, 4, 3
        factors = (1, 2, 1)
        winding, tp, layout = _base_inputs(
            'CP', q, poles, layers, 2, factors, phases)
        decision = gw.resolve_pattern_route(
            'CP', winding, factors, tp, layout)
        self.assertEqual(decision.status, 'enabled', decision.reason)
        self.assertEqual(decision.route_name, 'cp_pp_four_pass_weave')

        starts, database = gw.get_winding_layout('CP', tp, winding, layout)
        paths = [path for _, path in database]
        self.assertEqual(starts, [path[0] for path in paths])
        self.assertEqual(len(paths), phases * 2)
        self.assertEqual({len(path) for path in paths}, {8 * layers})

        source_winding, _, _ = _base_inputs(
            'CP', q, poles, layers, 4, (1, 2, 2), phases)
        _, source = gw.get_winding_layout('CP', tp, source_winding, layout)
        records = phase_map(
            winding.num_slots, poles, layers, layout.phase_shift_list, phases)
        phase_sign = {(slot, layer): (phase, sign)
                      for slot, layer, phase, sign in records}
        source_by_phase = {phase: [] for phase in range(phases)}
        for _, path in source:
            source_by_phase[phase_sign[path[0][:2]][0]].append(path)

        expected = []
        lap = layers
        for phase in range(phases):
            p1, p2, p3, p4 = source_by_phase[phase]
            expected.append(p1[:2*lap] + p2 + p1[2*lap:])
            expected.append(
                p3[3*lap:] + p4[2*lap:] + p3[2*lap:3*lap]
                + p4[lap:2*lap] + p3[:2*lap] + p4[:lap])
        self.assertEqual(paths, expected)

        draft_path = Path(__file__).with_name('pattern_rule_drafts') / (
            'CP_q-2_pp-4_L-4_Naa-2_Q-1_PP-2_P2-1_Ph-A_Side-weld_'
            'Shifts-0-0-0-0_20260925-153535-498962.json')
        draft = json.loads(draft_path.read_text(encoding='utf-8'))
        phase_a_paths = [[node[:2] for node in path] for path in paths
                         if phase_sign[path[0][:2]][0] == 0]
        manual_paths = [[(node['slot'] - 1, node['layer'] - 1)
                         for node in branch['path']]
                        for branch in draft['branches']]
        self.assertEqual(phase_a_paths, manual_paths)

        occupancy = Counter(node[:2] for path in paths for node in path)
        self.assertEqual(len(occupancy), winding.num_slots * layers)
        self.assertTrue(all(count == 1 for count in occupancy.values()))
        report = validate_branches(
            paths, records, winding.num_slots, poles, winding.ab, phases)
        self.assertTrue(report['layout_retained'], report)
        self.assertTrue(report['topology_valid'], report)
        self.assertTrue(report['electrically_valid'], report)
        self.assertEqual(
            analyze_pattern_identity('CP', database, winding, layout)['status'],
            'valid')
        self.assertEqual(
            database.layout_report['pattern_route']['route_name'],
            'cp_pp_four_pass_weave')
        gw.validate_selected_cp(database, winding, layout)
        region_pitch = phases * q
        self.assertTrue(all(
            pole_region_crossings(start[0], step, region_pitch) <= 1
            for path in paths for start, end in zip(path, path[1:])
            for step in circular_travel_steps(
                start[0], end[0], winding.num_slots)))

    def test_old_intact_parent_matcher_stays_withdrawn(self):
        from pattern_route_contract import PATTERN_ROUTE_RULES
        from pattern_rule_workbench import _base_inputs

        self.assertNotIn('cp_pp_pair_join', PATTERN_ROUTE_RULES)
        self.assertIn('cp_pp_parent_half_translation', PATTERN_ROUTE_RULES)
        winding, tp, layout = _base_inputs(
            'CP', 2, 8, 4, 4, (1, 4, 1), 3)
        decision = gw.resolve_pattern_route(
            'CP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.status, 'enabled', decision.reason)
        self.assertEqual(
            decision.route_name, 'cp_pp_parent_half_translation')


class CpQPP2ParentSliceTests(unittest.TestCase):
    def test_public_route_cuts_all_current_unsupported_matrix_cases(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs
        from pattern_identity import pole_region_crossings

        cases = (
            (4, 4, 2, 2, 4, 3),
            (4, 4, 2, 4, 4, 3),
            (6, 6, 2, 3, 4, 5),
            (6, 6, 2, 6, 4, 5),
            (6, 6, 3, 2, 4, 5),
            (6, 6, 3, 6, 4, 5),
        )
        route = 'cp_q_pp_p2_parent_slices'
        for q, pp, Q, D, layers, phases in cases:
            factors = (Q, D, 2)
            with self.subTest(q=q, pp=pp, Q=Q, D=D, m=phases):
                winding, tp, layout = _base_inputs(
                    'CP', q, 2 * pp, layers, 2 * Q * D, factors, phases)
                decision = gw.resolve_pattern_route(
                    'CP', winding, factors, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                self.assertEqual(decision.route_name, route)

                starts, database = gw.get_winding_layout(
                    'CP', tp, winding, layout)
                paths = [path for _, path in database]
                target_length = winding.num_slots * layers // (
                    phases * winding.ab)
                self.assertEqual(starts, [path[0] for path in paths])
                self.assertEqual(len(paths), phases * winding.ab)
                self.assertEqual({len(path) for path in paths}, {target_length})

                source_winding, _, _ = _base_inputs(
                    'CP', q, 2 * pp, layers, 2 * Q, (Q, 1, 2), phases)
                source_winding._capture_cp_constructor_travel = True
                _, source = gw.get_winding_layout(
                    'CP', tp, source_winding, layout)
                source_travel = getattr(source, 'signed_travel', None)
                self.assertIsNotNone(source_travel)
                self.assertEqual(
                    set(source_travel), {branch_id for branch_id, _ in source})
                records = phase_map(
                    winding.num_slots, 2 * pp, layers,
                    layout.phase_shift_list, phases)
                phase_sign = {
                    (slot, layer): (phase, sign)
                    for slot, layer, phase, sign in records
                }
                source_by_phase = {phase: [] for phase in range(phases)}
                for branch_id, path in source:
                    source_phase = phase_sign[path[0][:2]][0]
                    source_by_phase[source_phase].append((branch_id, path))

                expected_database = gw._CandidateBranches()
                expected_travel = {}
                for phase in range(phases):
                    self.assertEqual(len(source_by_phase[phase]), 2 * Q)
                    pieces = apply_route_formula(
                        route, source_by_phase[phase], factors)
                    for piece in pieces:
                        branch_id = len(expected_database) + 1
                        parent_id = piece.source_ids[0]
                        width = len(piece.path)
                        first_edge = piece.part_index * width
                        expected_travel[branch_id] = tuple(
                            source_travel[parent_id][
                                first_edge:first_edge + width - 1])
                        expected_database.append([branch_id, piece.path])
                expected_database.signed_travel = expected_travel
                expected_starts, expected_database = (
                    gw.orient_p2_branches_n_to_s(
                        expected_database, winding, layout))
                self.assertEqual(paths, [path for _, path in expected_database])
                self.assertEqual(starts, expected_starts)
                self.assertEqual(database.signed_travel,
                                 expected_database.signed_travel)

                occupancy = Counter(
                    node[:2] for path in paths for node in path)
                self.assertEqual(len(occupancy), winding.num_slots * layers)
                self.assertTrue(all(count == 1 for count in occupancy.values()))
                report = validate_branches(
                    paths, records, winding.num_slots, 2 * pp,
                    winding.ab, phases)
                self.assertTrue(report['layout_retained'], report)
                self.assertTrue(report['topology_valid'], report)
                self.assertTrue(database.layout_report['layout_retained'])
                self.assertEqual(
                    analyze_pattern_identity(
                        'CP', database, winding, layout)['status'], 'valid')
                self.assertTrue(set(database.layout_report['errors']) <= {
                    'parallel_emf_mismatch', 'multi_phase_emf_mismatch'})
                gw.validate_selected_cp(database, winding, layout)
                region_pitch = phases * q
                self.assertEqual(
                    set(database.signed_travel),
                    {branch_id for branch_id, _ in database})
                for branch_id, path in database:
                    signed_steps = database.signed_travel[branch_id]
                    self.assertEqual(len(signed_steps), len(path) - 1)
                    for (start, end), step in zip(
                            zip(path, path[1:]), signed_steps):
                        self.assertIs(type(step), int)
                        self.assertNotEqual(step, 0)
                        self.assertEqual(
                            (start[0] + step) % winding.num_slots, end[0])
                        self.assertLessEqual(
                            pole_region_crossings(
                                start[0], step, region_pitch), 1)

    def test_phase_array_maps_the_same_local_parent_formula(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs

        q, pp, layers, phases = 4, 8, 12, 6
        factors = (2, 2, 2)
        winding, tp, layout = _base_inputs(
            'CP', q, 2 * pp, layers, 2 * factors[0] * factors[1],
            factors, phases)
        decision = gw.resolve_pattern_route(
            'CP', winding, factors, tp, layout)
        self.assertEqual(decision.status, 'enabled', decision.reason)
        self.assertEqual(decision.route_name,
                         'cp_q_pp_p2_parent_slices')
        _, database = gw.get_winding_layout('CP', tp, winding, layout)
        self.assertEqual(
            set(database.signed_travel),
            {branch_id for branch_id, _ in database})

        source_winding, _, _ = _base_inputs(
            'CP', q, 2 * pp, layers, 2 * factors[0],
            (factors[0], 1, 2), phases)
        _, source = gw.get_winding_layout(
            'CP', tp, source_winding, layout)
        target_views = gw._three_phase_set_views(database, winding, layout)
        source_views = gw._three_phase_set_views(
            source, source_winding, layout)
        self.assertEqual(len(target_views), 2)
        self.assertEqual(len(source_views), 2)

        for target_view, source_view in zip(target_views, source_views):
            local_database, local_winding, local_layout = target_view
            local_source, source_winding, source_layout = source_view
            records = phase_map(
                source_winding.num_slots, source_winding.num_poles,
                source_winding.num_layers, source_layout.phase_shift_list,
                source_winding.num_phases)
            phase_by_position = {
                (slot, layer): phase
                for slot, layer, phase, _sign in records
            }
            source_by_phase = {
                phase: [] for phase in range(source_winding.num_phases)
            }
            for branch_id, path in local_source:
                source_by_phase[phase_by_position[path[0][:2]]].append(
                    (branch_id, path))

            expected_database = []
            for phase in range(source_winding.num_phases):
                pieces = apply_route_formula(
                    'cp_q_pp_p2_parent_slices', source_by_phase[phase],
                    factors)
                expected_database.extend(
                    [len(expected_database) + 1, piece.path]
                    for piece in pieces)
            _, expected_database = gw.orient_p2_branches_n_to_s(
                expected_database, local_winding, local_layout)
            self.assertEqual(
                [path for _, path in local_database],
                [path for _, path in expected_database])
            self.assertEqual(
                analyze_pattern_identity(
                    'CP', local_database, local_winding,
                    local_layout)['status'], 'valid')
            gw.validate_selected_cp(
                local_database, local_winding, local_layout)
        self.assertTrue(database.layout_report['layout_retained'])

    def test_route_preserves_default_and_rejects_out_of_domain_factors(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'CP', 6, 12, 4, 8, (2, 2, 2), 5)
        decision = gw.resolve_pattern_route(
            'CP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.status, 'enabled', decision.reason)
        self.assertTrue(decision.is_default)
        self.assertIsNone(decision.route_name)
        self.assertEqual(decision.rule_id, 'cp_default')

        invalid_cases = (
            (6, 6, 4, 5, (4, 2, 2)),  # Q does not divide q.
            (4, 6, 4, 3, (2, 4, 2)),  # D does not divide pp.
        )
        for q, pp, layers, phases, factors in invalid_cases:
            with self.subTest(q=q, pp=pp, factors=factors):
                winding, tp, layout = _base_inputs(
                    'CP', q, 2 * pp, layers,
                    factors[0] * factors[1] * factors[2], factors, phases)
                decision = gw.resolve_pattern_route(
                    'CP', winding, factors, tp, layout)
                self.assertEqual(decision.status, 'disabled')
                self.assertEqual(decision.admission, 'unsupported-yet')

        winding, tp, layout = _base_inputs(
            'CP', 4, 8, 6, 8, (2, 2, 2), 3)
        decision = gw.resolve_pattern_route(
            'CP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.status, 'disabled')
        self.assertEqual(decision.rule_id, 'cp_layer_multiple_of_four')


class CpFullQFullPpParentSliceTests(unittest.TestCase):
    def test_public_route_reproduces_saved_manual_sketch_by_parent_slices(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs
        from pattern_identity import circular_travel_steps, pole_region_crossings

        q, poles, layers, phases = 2, 8, 4, 3
        pp = poles // 2
        factors = (q, pp, 1)
        winding, tp, layout = _base_inputs(
            'CP', q, poles, layers, q * pp, factors, phases)
        decision = gw.resolve_pattern_route(
            'CP', winding, factors, tp, layout)
        self.assertEqual(decision.status, 'enabled', decision.reason)
        self.assertEqual(decision.route_name, 'cp_q_pp_full_parent_slices')

        starts, database = gw.get_winding_layout(
            'CP', tp, winding, layout)
        paths = [path for _, path in database]
        target_length = winding.num_slots * layers // (phases * winding.ab)
        self.assertEqual(starts, [path[0] for path in paths])
        self.assertEqual(len(paths), phases * q * pp)
        self.assertEqual({len(path) for path in paths}, {target_length})

        source_winding, _, _ = _base_inputs(
            'CP', q, poles, layers, 2 * q, (q, 1, 2), phases)
        _, source = gw.get_winding_layout(
            'CP', tp, source_winding, layout)
        records = phase_map(
            winding.num_slots, poles, layers, layout.phase_shift_list, phases)
        phase_sign = {(slot, layer): (phase, sign)
                      for slot, layer, phase, sign in records}
        source_by_phase = {phase: [] for phase in range(phases)}
        for _, path in source:
            source_by_phase[phase_sign[path[0][:2]][0]].append(path)
        expected = [
            path[part * target_length:(part + 1) * target_length]
            for phase in range(phases)
            for part in range(pp // 2)
            for path in source_by_phase[phase]
        ]
        self.assertEqual(paths, expected)

        draft_path = Path(__file__).with_name('pattern_rule_drafts') / (
            'CP_q-2_pp-4_L-4_Naa-8_Q-2_PP-4_P2-1_Ph-A_Side-weld_'
            'Shifts-0-0-0-0_20260925-153022-297220.json')
        draft = json.loads(draft_path.read_text(encoding='utf-8'))
        phase_a_paths = [[node[:2] for node in path] for path in paths
                         if phase_sign[path[0][:2]][0] == 0]
        manual_paths = [[(node['slot'] - 1, node['layer'] - 1)
                         for node in branch['path']]
                        for branch in draft['branches']]
        self.assertEqual(phase_a_paths, manual_paths)

        occupancy = Counter(node[:2] for path in paths for node in path)
        self.assertEqual(len(occupancy), winding.num_slots * layers)
        self.assertTrue(all(count == 1 for count in occupancy.values()))
        report = validate_branches(
            paths, records, winding.num_slots, poles, winding.ab, phases)
        self.assertTrue(report['layout_retained'], report)
        self.assertTrue(report['topology_valid'], report)
        self.assertEqual(report['errors'], ['parallel_emf_mismatch'])
        self.assertEqual(database.layout_status, 'not strong symmetry layout')
        self.assertFalse(database.layout_report['electrically_valid'])
        self.assertEqual(
            analyze_pattern_identity('CP', database, winding, layout)['status'],
            'valid')
        gw.validate_selected_cp(database, winding, layout)
        region_pitch = phases * q
        self.assertTrue(all(
            pole_region_crossings(start[0], step, region_pitch) <= 1
            for path in paths for start, end in zip(path, path[1:])
            for step in circular_travel_steps(
                start[0], end[0], winding.num_slots)))

    def test_q_pp_route_uses_formula_across_factor_domains(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs
        from pattern_identity import circular_travel_steps, pole_region_crossings

        cases = (
            (2, 8, 2, 4, 4, 3),  # Full Q, proper D.
            (4, 4, 2, 4, 4, 3),  # Proper Q, full D.
            (4, 8, 2, 4, 4, 3),  # Proper Q and proper D.
            (3, 8, 3, 4, 4, 3),  # Odd q with proper D.
            (6, 12, 2, 6, 4, 5), # Proper Q and D=6 at five phases.
            (3, 6, 3, 6, 4, 5),  # Existing full-Q/full-D reference.
            (4, 8, 2, 4, 8, 6),  # L=8 distributed across six phases.
        )
        for q, pp, Q, D, layers, phases in cases:
            with self.subTest(q=q, pp=pp, Q=Q, D=D, m=phases):
                poles = 2 * pp
                factors = (Q, D, 1)
                winding, tp, layout = _base_inputs(
                    'CP', q, poles, layers, Q * D, factors, phases)
                decision = gw.resolve_pattern_route(
                    'CP', winding, factors, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                self.assertEqual(
                    decision.route_name, 'cp_q_pp_full_parent_slices')

                starts, database = gw.get_winding_layout(
                    'CP', tp, winding, layout)
                paths = [path for _, path in database]
                target_length = winding.num_slots * layers // (
                    phases * winding.ab)
                self.assertEqual(starts, [path[0] for path in paths])
                self.assertEqual(len(paths), phases * Q * D)
                self.assertEqual({len(path) for path in paths},
                                 {target_length})

                records = phase_map(
                    winding.num_slots, poles, layers,
                    layout.phase_shift_list, phases)
                phase_sign = {
                    (slot, layer): (phase, sign)
                    for slot, layer, phase, sign in records
                }
                self.assertTrue(all(
                    len({phase_sign[node[:2]][0] for node in path}) == 1
                    for path in paths))

                source_winding, _, _ = _base_inputs(
                    'CP', q, poles, layers, 2 * Q, (Q, 1, 2), phases)
                _, source = gw.get_winding_layout(
                    'CP', tp, source_winding, layout)
                source_by_phase = {phase: [] for phase in range(phases)}
                for _, source_path in source:
                    source_phase = phase_sign[source_path[0][:2]][0]
                    source_by_phase[source_phase].append(source_path)
                expected = [
                    source_path[part * target_length:(part + 1) * target_length]
                    for phase in range(phases)
                    for part in range(D // 2)
                    for source_path in source_by_phase[phase]
                ]
                self.assertEqual(paths, expected)

                occupancy = Counter(
                    node[:2] for path in paths for node in path)
                self.assertEqual(len(occupancy), winding.num_slots * layers)
                self.assertTrue(all(count == 1 for count in occupancy.values()))
                report = validate_branches(
                    paths, records, winding.num_slots, poles,
                    winding.ab, phases)
                self.assertTrue(report['layout_retained'], report)
                self.assertTrue(report['topology_valid'], report)
                self.assertIn('parallel_emf_mismatch', report['errors'])
                self.assertTrue(set(report['errors']) <= {
                    'parallel_emf_mismatch', 'multi_phase_emf_mismatch'})
                if layers == 8 and phases == 6:
                    self.assertIn(
                        'multi_phase_emf_mismatch', report['errors'])
                self.assertEqual(database.layout_status,
                                 'not strong symmetry layout')
                phase_set_views = ()
                if phases > 3 and phases % 3 == 0:
                    # Ordered CP identity is defined per independent 3-phase
                    # set; a global-q view does not preserve local q geometry.
                    phase_set_views = gw._three_phase_set_views(
                        database, winding, layout)
                    self.assertEqual(len(phase_set_views), phases // 3)
                    identities = [
                        analyze_pattern_identity('CP', *view)
                        for view in phase_set_views
                    ]
                    self.assertTrue(all(
                        identity['status'] == 'valid'
                        for identity in identities), identities)
                else:
                    self.assertEqual(
                        analyze_pattern_identity(
                            'CP', database, winding, layout)['status'], 'valid')
                validation_views = phase_set_views or ((
                    database, winding, layout),)
                for local_database, local_winding, local_layout in validation_views:
                    gw.validate_selected_cp(
                        local_database, local_winding, local_layout)
                    region_pitch = (
                        local_winding.num_phases * local_winding.q)
                    self.assertTrue(all(
                        pole_region_crossings(start[0], step, region_pitch) <= 1
                        for _, path in local_database
                        for start, end in zip(path, path[1:])
                        for step in circular_travel_steps(
                            start[0], end[0], local_winding.num_slots)))

    def test_q_pp_formula_rejects_nondivisor_q_and_odd_d(self):
        from pattern_rule_workbench import _base_inputs

        cases = (
            (4, 8, (3, 4, 1), 12),
            (4, 9, (2, 3, 1), 6),
        )
        for q, poles, factors, branch_count in cases:
            with self.subTest(q=q, poles=poles, factors=factors):
                winding, tp, layout = _base_inputs(
                    'CP', q, poles, 4, branch_count, factors, 3)
                decision = gw.resolve_pattern_route(
                    'CP', winding, factors, tp, layout)
                self.assertEqual(decision.status, 'disabled')
                self.assertTrue(decision.reason)

    def test_pp_only_d_congruent_two_reuses_p2_parent_slices(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs
        from pattern_identity import circular_travel_steps, pole_region_crossings

        cases = (
            (2, 6, 6, 3),
            (4, 6, 6, 5),
            (3, 10, 10, 5),
            (2, 14, 14, 3),
            (5, 14, 14, 7),
        )
        for q, pp, D, phases in cases:
            with self.subTest(q=q, pp=pp, D=D, m=phases):
                factors = (1, D, 1)
                winding, tp, layout = _base_inputs(
                    'CP', q, 2 * pp, 4, D, factors, phases)
                decision = gw.resolve_pattern_route(
                    'CP', winding, factors, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                self.assertEqual(
                    decision.route_name, 'cp_q_pp_full_parent_slices')

                starts, database = gw.get_winding_layout(
                    'CP', tp, winding, layout)
                paths = [path for _, path in database]
                target_length = winding.num_slots * 4 // (phases * D)
                self.assertEqual(starts, [path[0] for path in paths])
                self.assertEqual(len(paths), phases * D)
                self.assertEqual({len(path) for path in paths},
                                 {target_length})

                source_winding, _, _ = _base_inputs(
                    'CP', q, 2 * pp, 4, 2, (1, 1, 2), phases)
                _, source = gw.get_winding_layout(
                    'CP', tp, source_winding, layout)
                records = phase_map(
                    winding.num_slots, 2 * pp, 4,
                    layout.phase_shift_list, phases)
                phase_by_position = {
                    (slot, layer): phase
                    for slot, layer, phase, _sign in records
                }
                source_by_phase = {phase: [] for phase in range(phases)}
                for _, source_path in source:
                    phase = phase_by_position[source_path[0][:2]]
                    source_by_phase[phase].append(source_path)
                expected = [
                    source_path[part * target_length:(part + 1) * target_length]
                    for phase in range(phases)
                    for part in range(D // 2)
                    for source_path in source_by_phase[phase]
                ]
                self.assertEqual(paths, expected)

                occupancy = Counter(node[:2]
                                    for path in paths for node in path)
                self.assertEqual(len(occupancy), winding.num_slots * 4)
                self.assertTrue(all(count == 1 for count in occupancy.values()))
                report = validate_branches(
                    paths, records, winding.num_slots, 2 * pp, D, phases)
                self.assertTrue(report['layout_retained'], report)
                self.assertTrue(report['topology_valid'], report)
                self.assertIn('parallel_emf_mismatch', report['errors'])
                self.assertEqual(database.layout_status,
                                 'not strong symmetry layout')
                self.assertEqual(
                    analyze_pattern_identity(
                        'CP', database, winding, layout)['status'], 'valid')
                gw.validate_selected_cp(database, winding, layout)
                region_pitch = phases * q
                self.assertTrue(all(
                    pole_region_crossings(start[0], step, region_pitch) <= 1
                    for path in paths
                    for start, end in zip(path, path[1:])
                    for step in circular_travel_steps(
                        start[0], end[0], winding.num_slots)))

    def test_q1_pp_only_parent_slices_follow_public_source_preflight(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs
        from pattern_identity import circular_travel_steps, pole_region_crossings

        cases = (
            (6, 6, 4, 3),    # Direct, D=pp.
            (30, 10, 4, 5),  # Direct, pp/D=3.
            (42, 14, 4, 7),  # Direct, larger D.
            (12, 6, 8, 6),   # Two sets with four local layers each.
            (18, 6, 12, 9),  # Three sets with four local layers each.
        )
        for pp, divider, layers, phases in cases:
            with self.subTest(pp=pp, D=divider, L=layers, m=phases):
                winding, tp, layout = _base_inputs(
                    'CP', 1, 2 * pp, layers, divider,
                    (1, divider, 1), phases)
                decision = gw.resolve_pattern_route(
                    'CP', winding, winding.branch_dividers, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                self.assertEqual(
                    decision.route_name, 'cp_q_pp_full_parent_slices')

                starts, database = gw.get_winding_layout(
                    'CP', tp, winding, layout)
                paths = [path for _, path in database]
                target_length = winding.num_slots * layers // (
                    phases * winding.ab)
                self.assertEqual(starts, [path[0] for path in paths])
                self.assertEqual(len(paths), phases * divider)
                self.assertEqual({len(path) for path in paths},
                                 {target_length})

                source_winding, _, _ = _base_inputs(
                    'CP', 1, 2 * pp, layers, 2, (1, 1, 2), phases)
                _, source = gw.get_winding_layout(
                    'CP', tp, source_winding, layout)
                records = phase_map(
                    winding.num_slots, 2 * pp, layers,
                    layout.phase_shift_list, phases)
                phase_sign = {
                    (slot, layer): (phase, sign)
                    for slot, layer, phase, sign in records
                }
                source_by_phase = {phase: [] for phase in range(phases)}
                for _, source_path in source:
                    phase = phase_sign[source_path[0][:2]][0]
                    source_by_phase[phase].append(source_path)
                expected = [
                    source_path[part * target_length:(part + 1) * target_length]
                    for phase in range(phases)
                    for part in range(divider // 2)
                    for source_path in source_by_phase[phase]
                ]
                self.assertEqual(paths, expected)

                occupancy = Counter(
                    node[:2] for path in paths for node in path)
                self.assertEqual(len(occupancy), winding.num_slots * layers)
                self.assertTrue(all(count == 1 for count in occupancy.values()))
                self.assertTrue(all(
                    len({phase_sign[node[:2]][0] for node in path}) == 1
                    for path in paths))
                self.assertTrue(all(
                    phase_sign[path[0][:2]][1] == 1
                    and phase_sign[path[-1][:2]][1] == -1
                    for path in paths))

                report = validate_branches(
                    paths, records, winding.num_slots, 2 * pp,
                    winding.ab, phases)
                self.assertTrue(report['layout_retained'], report)
                self.assertTrue(report['topology_valid'], report)
                self.assertTrue(database.layout_report['layout_retained'])

                phase_set_views = ()
                if phases > 3 and phases % 3 == 0:
                    phase_set_views = gw._three_phase_set_views(
                        database, winding, layout)
                    self.assertEqual(len(phase_set_views), phases // 3)
                    identities = [
                        analyze_pattern_identity('CP', *view)
                        for view in phase_set_views
                    ]
                    self.assertTrue(all(
                        identity['status'] == 'valid'
                        for identity in identities), identities)
                else:
                    identity = analyze_pattern_identity(
                        'CP', database, winding, layout)
                    self.assertEqual(identity['status'], 'valid')

                validation_views = phase_set_views or ((
                    database, winding, layout),)
                for local_database, local_winding, local_layout in validation_views:
                    gw.validate_selected_cp(
                        local_database, local_winding, local_layout)
                    region_pitch = (
                        local_winding.num_phases * local_winding.q)
                    self.assertTrue(all(
                        pole_region_crossings(start[0], step,
                                              region_pitch) <= 1
                        for _, path in local_database
                        for start, end in zip(path, path[1:])
                        for step in circular_travel_steps(
                            start[0], end[0], local_winding.num_slots)))

    def test_odd_q_pp_only_parent_slices_preserve_order_and_welds(self):
        from pattern_identity import analyze_ordered_pattern
        from pattern_rule_workbench import _base_inputs

        cases = (
            (1, 4, 4, 4, 3),
            (1, 8, 8, 4, 3),
            (3, 4, 4, 4, 3),
            (3, 8, 8, 4, 5),
            (5, 12, 12, 4, 5),
        )
        for q, pp, D, layers, phases in cases:
            with self.subTest(q=q, pp=pp, D=D, L=layers, m=phases):
                winding, tp, layout = _base_inputs(
                    'CP', q, 2 * pp, layers, D, (1, D, 1), phases)
                decision = gw.resolve_pattern_route(
                    'CP', winding, winding.branch_dividers, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                self.assertEqual(
                    decision.route_name, 'cp_q_pp_full_parent_slices')

                source_winding, _, _ = _base_inputs(
                    'CP', q, 2 * pp, layers, 2, (1, 1, 2), phases)
                source_decision = gw.resolve_pattern_route(
                    'CP', source_winding, source_winding.branch_dividers,
                    tp, layout)
                self.assertEqual(source_decision.status, 'enabled')
                _, source = gw.get_winding_layout(
                    'CP', tp, source_winding, layout)
                starts, database = gw.get_winding_layout(
                    'CP', tp, winding, layout)
                paths = [path for _, path in database]
                target_length = winding.num_slots * layers // (phases * D)
                self.assertEqual(target_length % 2, 0)
                self.assertEqual(starts, [path[0] for path in paths])
                self.assertEqual(len(paths), phases * D)
                self.assertEqual({len(path) for path in paths}, {target_length})

                records = phase_map(
                    winding.num_slots, 2 * pp, layers,
                    layout.phase_shift_list, phases)
                phase_sign = {
                    (slot, layer): (phase, sign)
                    for slot, layer, phase, sign in records
                }
                source_ordered = analyze_ordered_pattern(
                    'CP', source, source_winding, layout)
                target_ordered = analyze_ordered_pattern(
                    'CP', database, winding, layout)
                self.assertEqual(source_ordered['ordered_status'], 'valid')
                self.assertEqual(target_ordered['ordered_status'], 'valid')
                parents = {phase: [] for phase in range(phases)}
                for (_, path), branch_report in zip(
                        source, source_ordered['branch_reports']):
                    phase = phase_sign[path[0][:2]][0]
                    parents[phase].append((
                        path, branch_report['observed_signature']))
                self.assertTrue(all(len(group) == 2
                                    for group in parents.values()))

                expected_paths = []
                expected_edges = []
                for phase in range(phases):
                    for piece in range(D // 2):
                        start = piece * target_length
                        stop = start + target_length
                        for parent_path, parent_edges in parents[phase]:
                            expected_paths.append(parent_path[start:stop])
                            expected_edges.append(parent_edges[start:stop - 1])
                self.assertEqual(paths, expected_paths)
                weld_travel = {pair: set() for pair in range(layers // 2)}
                for branch_report, parent_edges in zip(
                        target_ordered['branch_reports'], expected_edges):
                    actual_edges = branch_report['observed_signature']
                    for key in ('side', 'start', 'end', 'layer_step',
                                'actual_slot_steps', 'pole_region_crossings'):
                        self.assertEqual(
                            [edge[key] for edge in actual_edges],
                            [edge[key] for edge in parent_edges])
                    self.assertTrue(all(
                        len(edge['actual_slot_steps']) == 1
                        and max(edge['pole_region_crossings']) <= 1
                        for edge in actual_edges))
                    for edge in actual_edges:
                        layer_step = edge['layer_step']
                        if edge['side'] == 'insert':
                            self.assertEqual(abs(layer_step), layers // 2)
                        else:
                            self.assertEqual(abs(layer_step), 1)
                            first_layer = edge['start'][1]
                            last_layer = edge['end'][1]
                            if first_layer // 2 == last_layer // 2:
                                weld_travel[first_layer // 2].add(
                                    edge['actual_slot_steps'][0]
                                    * (1 if layer_step > 0 else -1))
                tau = phases * q
                self.assertEqual(weld_travel, {0: {tau}, 1: {-tau}})

                occupancy = Counter(
                    node[:2] for path in paths for node in path)
                self.assertEqual(len(occupancy), winding.num_slots * layers)
                self.assertTrue(all(count == 1
                                    for count in occupancy.values()))
                self.assertTrue(all(
                    len({phase_sign[node[:2]][0] for node in path}) == 1
                    and phase_sign[path[0][:2]][1] == 1
                    and phase_sign[path[-1][:2]][1] == -1
                    for path in paths))
                report = validate_branches(
                    paths, records, winding.num_slots, 2 * pp, D, phases)
                self.assertTrue(report['layout_retained'], report)
                self.assertTrue(report['topology_valid'], report)
                self.assertTrue(set(report['errors']) <= {
                    'parallel_emf_mismatch', 'multi_phase_emf_mismatch'})
                gw.validate_selected_cp(database, winding, layout)

    def test_odd_q_pp_only_parent_slices_keep_route_boundaries(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs

        controls = (
            (1, 6, 6, 'cp_q_pp_full_parent_slices'),
            (2, 4, 4, 'cp_pp_parent_half_translation'),
            (2, 8, 8, 'cp_pp_sector_slices'),
        )
        for q, pp, D, route in controls:
            with self.subTest(q=q, pp=pp, D=D):
                winding, tp, layout = _base_inputs(
                    'CP', q, 2 * pp, 4, D, (1, D, 1), 3)
                decision = gw.resolve_pattern_route(
                    'CP', winding, winding.branch_dividers, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                self.assertEqual(decision.route_name, route)

        array_controls = (
            (1, 4, 4, 8, 6, 'cp_pp_parent_half_translation'),
            (1, 8, 8, 8, 6, 'cp_pp_sector_slices'),
            (1, 4, 4, 12, 9, 'cp_q_pp_full_parent_slices'),
        )
        for q, pp, D, layers, phases, route in array_controls:
            with self.subTest(q=q, pp=pp, D=D, L=layers, m=phases):
                winding, tp, layout = _base_inputs(
                    'CP', q, 2 * pp, layers, D, (1, D, 1), phases)
                decision = gw.resolve_pattern_route(
                    'CP', winding, winding.branch_dividers, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                self.assertEqual(decision.route_name, route)
                _, database = gw.get_winding_layout(
                    'CP', tp, winding, layout)
                self.assertTrue(database.layout_report['layout_retained'])
                self.assertTrue(all(
                    analyze_pattern_identity('CP', *view)['status'] == 'valid'
                    for view in gw._three_phase_set_views(
                        database, winding, layout)))

        for q, pp, D, layers, reason in (
                (3, 6, 4, 4, 'no validated construction'),
                (3, 6, 3, 4, 'no validated construction'),
                (1, 4, 4, 8, 'duplicate'),
                (3, 4, 4, 8, 'duplicate')):
            with self.subTest(q=q, pp=pp, D=D, L=layers):
                winding, tp, layout = _base_inputs(
                    'CP', q, 2 * pp, layers, D, (1, D, 1), 3)
                decision = gw.resolve_pattern_route(
                    'CP', winding, winding.branch_dividers, tp, layout)
                self.assertEqual(decision.status, 'disabled')
                self.assertIn(reason, decision.reason.lower())

        winding, tp, layout = _base_inputs(
            'CP', 1, 8, 4, 4, (1, 4, 1), 3)
        layout.phase_shift_list[1] = 1
        decision = gw.resolve_pattern_route(
            'CP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.status, 'disabled')

    def test_q1_pp_only_keeps_source_and_phase_layer_preflight_boundaries(self):
        from pattern_rule_workbench import _base_inputs

        cases = (
            (6, 8, 3, ('duplicate', 'misses')),
            (6, 12, 3, ('duplicate', 'misses')),
            (6, 4, 9, ('divisible by 3',)),
        )
        for pp, layers, phases, reason_parts in cases:
            with self.subTest(pp=pp, L=layers, m=phases):
                winding, tp, layout = _base_inputs(
                    'CP', 1, 2 * pp, layers, 6, (1, 6, 1), phases)
                decision = gw.resolve_pattern_route(
                    'CP', winding, winding.branch_dividers, tp, layout)
                self.assertEqual(decision.status, 'disabled')
                for reason_part in reason_parts:
                    self.assertIn(reason_part, decision.reason.lower())

    def test_pp_only_d6_layer8_keeps_public_p2_source_failure_disabled(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'CP', 2, 12, 8, 6, (1, 6, 1), 3)
        decision = gw.resolve_pattern_route(
            'CP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.status, 'disabled')
        self.assertEqual(
            decision.route_name, 'cp_q_pp_full_parent_slices')
        self.assertIn('duplicate', decision.reason.lower())
        self.assertIn('misses', decision.reason.lower())

    def test_q_pp_formula_keeps_l8_three_phase_source_failure_disabled(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'CP', 4, 16, 8, 8, (2, 4, 1), 3)
        decision = gw.resolve_pattern_route(
            'CP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.status, 'disabled')
        self.assertIn('duplicate', decision.reason.lower())
        self.assertIn('misses', decision.reason.lower())

    def test_full_q_full_pp_route_keeps_neutral_insert_side_gate(self):
        from pattern_rule_workbench import _base_inputs

        cases = (
            ('inlet', {'inlet_from_weld_side': 1}),
            ('adjustment', {'inlet_index_adjustments_phase_a': [1]}),
            ('phase shift', {'phase_shift_list': [0, 1, 0, 0]}),
        )
        for label, values in cases:
            with self.subTest(setting=label):
                winding, tp, layout = _base_inputs(
                    'CP', 2, 8, 4, 8, (2, 4, 1), 3)
                for key, value in values.items():
                    setattr(layout, key, value)
                decision = gw.resolve_pattern_route(
                    'CP', winding, winding.branch_dividers, tp, layout)
                self.assertEqual(decision.status, 'disabled')

        winding, tp, layout = _base_inputs(
            'CP', 2, 8, 4, 8, (2, 4, 1), 3)
        tp.tp_type = 'Interval'
        tp.tp_interval = 1
        decision = gw.resolve_pattern_route(
            'CP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.status, 'disabled')


class CpPpFourSectorTranslationTests(unittest.TestCase):
    def test_public_route_reconstructs_manual_conductor_groups(self):
        from pattern_rule_workbench import _base_inputs
        from phase_topology import phase_map

        q, poles, layers, phases = 2, 8, 4, 3
        factors = (1, 4, 1)
        winding, tp, layout = _base_inputs(
            'CP', q, poles, layers, 4, factors, phases)
        decision = gw.resolve_pattern_route(
            'CP', winding, factors, tp, layout)
        self.assertEqual(decision.status, 'enabled', decision.reason)
        self.assertEqual(decision.route_name, 'cp_pp_parent_half_translation')

        _, database = gw.get_winding_layout('CP', tp, winding, layout)
        paths = [path for _, path in database]
        records = phase_map(
            winding.num_slots, poles, layers, layout.phase_shift_list, phases)
        phase_at = {(slot, layer): phase
                    for slot, layer, phase, _sign in records}
        draft_path = Path(__file__).with_name('pattern_rule_drafts') / (
            'CP_q-2_pp-4_L-4_Naa-4_Q-1_PP-4_P2-1_Ph-A_Side-weld_'
            'Shifts-0-0-0-0_20260925-170545-125560.json')
        draft = json.loads(draft_path.read_text(encoding='utf-8'))
        actual_phase_a = {
            frozenset(node[:2] for node in path)
            for path in paths if phase_at[tuple(path[0][:2])] == 0}
        manual_phase_a = {
            frozenset((node['slot'] - 1, node['layer'] - 1)
                      for node in branch['path'])
            for branch in draft['branches']}
        self.assertEqual(actual_phase_a, manual_phase_a)
        manual_sequences = [
            [(node['slot'] - 1, node['layer'] - 1)
             for node in branch['path']]
            for branch in draft['branches']]
        unmatched = list(manual_sequences)
        for generated_path in (
                path for path in paths
                if phase_at[tuple(path[0][:2])] == 0):
            generated = [node[:2] for node in generated_path]
            match_index = None
            for index, manual in enumerate(unmatched):
                for oriented in (manual, list(reversed(manual))):
                    if len(oriented) != len(generated):
                        continue
                    inlet_shift = (
                        generated[0][0] - oriented[0][0]
                    ) % winding.num_slots
                    translated = [
                        ((slot + inlet_shift) % winding.num_slots, layer)
                        for slot, layer in oriented]
                    if translated == generated:
                        match_index = index
                        break
                if match_index is not None:
                    break
            self.assertIsNotNone(
                match_index, 'generated path must match a manual path after inlet rotation/reversal')
            unmatched.pop(match_index)
        self.assertEqual(unmatched, [])

        occupancy = Counter(node[:2] for path in paths for node in path)
        self.assertEqual(len(occupancy), winding.num_slots * layers)
        self.assertTrue(all(count == 1 for count in occupancy.values()))
        report = validate_branches(
            paths, records, winding.num_slots, poles, winding.ab, phases)
        self.assertTrue(report['layout_retained'], report)
        self.assertTrue(report['topology_valid'], report)
        self.assertEqual(report['errors'], ['parallel_emf_mismatch'])
        self.assertEqual(database.layout_status, 'not strong symmetry layout')
        from layout_analysis import analyze_pattern_identity
        self.assertEqual(
            analyze_pattern_identity('CP', database, winding, layout)['status'],
            'valid')
        gw.validate_selected_cp(database, winding, layout)

    def test_even_q_and_divisible_four_pp_route_is_parameterized(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs

        for q, pp, phases in ((2, 8, 3), (4, 8, 3), (2, 8, 5)):
            with self.subTest(q=q, pp=pp, phases=phases):
                factors = (1, 4, 1)
                winding, tp, layout = _base_inputs(
                    'CP', q, 2 * pp, 4, 4, factors, phases)
                decision = gw.resolve_pattern_route(
                    'CP', winding, factors, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                self.assertEqual(
                    decision.route_name, 'cp_pp_parent_half_translation')
                _, database = gw.get_winding_layout(
                    'CP', tp, winding, layout)
                report = validate_branches(
                    [path for _, path in database],
                    phase_map(winding.num_slots, 2 * pp, 4,
                              layout.phase_shift_list, phases),
                    winding.num_slots, 2 * pp, winding.ab, phases)
                self.assertTrue(report['layout_retained'], report)
                self.assertTrue(report['topology_valid'], report)
                self.assertEqual(report['errors'], ['parallel_emf_mismatch'])
                self.assertEqual(
                    analyze_pattern_identity(
                        'CP', database, winding, layout)['status'], 'valid')
                gw.validate_selected_cp(database, winding, layout)

    def test_four_sector_translation_keeps_nondivisor_unsupported(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'CP', 2, 12, 4, 4, (1, 4, 1), 3)
        decision = gw.resolve_pattern_route(
            'CP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.admission, 'unsupported-yet')

    def test_parent_source_generation_still_bounds_layer_cases(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'CP', 2, 8, 8, 4, (1, 4, 1), 3)
        decision = gw.resolve_pattern_route(
            'CP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.status, 'disabled')
        self.assertEqual(decision.admission, 'rejected')
        self.assertIn('duplicate', decision.reason.lower())

    def test_translation_route_keeps_neutral_insert_side_configuration(self):
        from pattern_rule_workbench import _base_inputs

        for key, value in (
                ('inlet_from_weld_side', 1),
                ('inlet_index_adjustments_phase_a', [1]),
                ('phase_shift_list', [0, 1, 0, 0])):
            with self.subTest(setting=key):
                winding, tp, layout = _base_inputs(
                    'CP', 2, 8, 4, 4, (1, 4, 1), 3)
                setattr(layout, key, value)
                decision = gw.resolve_pattern_route(
                    'CP', winding, winding.branch_dividers, tp, layout)
                self.assertEqual(decision.status, 'disabled')

    def test_public_cp_pp_weave_uses_each_supported_phase_group(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'CP', 2, 8, 4, 2, (1, 2, 1), 5)
        decision = gw.resolve_pattern_route(
            'CP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.status, 'enabled', decision.reason)
        _, database = gw.get_winding_layout('CP', tp, winding, layout)
        paths = [path for _, path in database]
        records = phase_map(
            winding.num_slots, winding.num_poles, winding.num_layers,
            layout.phase_shift_list, winding.num_phases)
        report = validate_branches(
            paths, records, winding.num_slots, winding.num_poles,
            winding.ab, winding.num_phases)
        self.assertTrue(report['layout_retained'], report)
        self.assertTrue(report['topology_valid'], report)
        self.assertTrue(report['electrically_valid'], report)
        self.assertEqual(
            analyze_pattern_identity('CP', database, winding, layout)['status'],
            'valid')
        self.assertEqual(len(paths), 2 * winding.num_phases)


class CpArrayGlobalLayerGateTests(unittest.TestCase):
    def test_global_multiple_of_four_allows_even_local_cp_layer_groups(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs
        from pattern_identity import circular_travel_steps, pole_region_crossings

        cases = (
            (2, 16, (2, 4, 1), 8, 'cp_q_pp_full_parent_slices'),
            (1, 16, (1, 8, 1), 8, 'cp_pp_sector_slices'),
            (2, 24, (2, 6, 1), 12, 'cp_q_pp_full_parent_slices'),
        )
        for q, poles, factors, naa, expected_route in cases:
            with self.subTest(q=q, poles=poles, factors=factors):
                winding, tp, layout = _base_inputs(
                    'CP', q, poles, 12, naa, factors, 6)
                decision = gw.resolve_pattern_route(
                    'CP', winding, factors, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                self.assertEqual(decision.route_name, expected_route)

                starts, database = gw.get_winding_layout(
                    'CP', tp, winding, layout)
                paths = [path for _, path in database]
                self.assertEqual(starts, [path[0] for path in paths])
                self.assertEqual(len(paths), winding.num_phases * naa)
                expected_length = (
                    winding.num_slots * winding.num_layers
                    // (winding.num_phases * naa))
                self.assertEqual({len(path) for path in paths},
                                 {expected_length})

                occupancy = Counter(
                    node[:2] for path in paths for node in path)
                self.assertEqual(
                    len(occupancy), winding.num_slots * winding.num_layers)
                self.assertTrue(all(count == 1 for count in occupancy.values()))
                self.assertTrue(database.layout_report['layout_retained'])
                self.assertEqual(database.layout_status,
                                 'not strong symmetry layout')
                self.assertTrue(set(database.layout_report['errors']) <= {
                    'parallel_emf_mismatch', 'multi_phase_emf_mismatch'})

                local_views = gw._three_phase_set_views(
                    database, winding, layout)
                self.assertEqual(len(local_views), 2)
                for local_database, local_winding, local_layout in local_views:
                    self.assertEqual(
                        analyze_pattern_identity(
                            'CP', local_database, local_winding,
                            local_layout)['status'], 'valid')
                    gw.validate_selected_cp(
                        local_database, local_winding, local_layout)
                    region_width = (
                        local_winding.num_phases * local_winding.q)
                    self.assertTrue(all(
                        pole_region_crossings(start[0], step, region_width) <= 1
                        for _, path in local_database
                        for start, end in zip(path, path[1:])
                        for step in circular_travel_steps(
                            start[0], end[0], local_winding.num_slots)))

    def test_global_layer_multiple_of_four_remains_required_for_cp_arrays(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'CP', 2, 16, 10, 8, (2, 4, 1), 6)
        decision = gw.resolve_pattern_route(
            'CP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.status, 'disabled')
        self.assertIn('divisible by 4', decision.reason)

    def test_global_fourfold_and_even_local_layer_requirements_are_distinct(self):
        from pattern_rule_workbench import _base_inputs

        direct, tp, layout = _base_inputs(
            'CP', 2, 16, 6, 8, (2, 4, 1), 3)
        direct_decision = gw.resolve_pattern_route(
            'CP', direct, direct.branch_dividers, tp, layout)
        self.assertEqual(direct_decision.status, 'disabled')
        self.assertIn('divisible by 4', direct_decision.reason)

        odd_local, tp, layout = _base_inputs(
            'CP', 2, 16, 12, 8, (2, 4, 1), 12)
        local_decision = gw.resolve_pattern_route(
            'CP', odd_local, odd_local.branch_dividers, tp, layout)
        self.assertEqual(local_decision.status, 'disabled')
        self.assertIn('positive even local layer count',
                      local_decision.reason)


class CpQOnlyAdjacentPairTests(unittest.TestCase):
    def test_public_route_pairs_adjacent_p2_parents_in_phase_order(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs
        from pattern_identity import circular_travel_steps, pole_region_crossings

        cases = ((2, 2, 8, 4, 3), (4, 2, 8, 4, 3), (4, 4, 8, 4, 3))
        for q, Q, poles, layers, phases in cases:
            with self.subTest(q=q, Q=Q, poles=poles, layers=layers):
                winding, tp, layout = _base_inputs(
                    'CP', q, poles, layers, Q, (Q, 1, 1), phases)
                decision = gw.resolve_pattern_route(
                    'CP', winding, winding.branch_dividers, tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                self.assertEqual(decision.route_name, 'cp_q_only_pair_join')

                starts, database = gw.get_winding_layout(
                    'CP', tp, winding, layout)
                parent = SimpleNamespace(
                    q=q, num_slots=winding.num_slots, num_poles=poles,
                    num_phases=phases, num_layers=layers, ab=2 * Q,
                    branch_dividers=(Q, 1, 2))
                _, source = gw.get_winding_layout('CP', tp, parent, layout)
                records = phase_map(
                    winding.num_slots, poles, layers,
                    layout.phase_shift_list, phases)
                phase_sign = {(slot, layer): (phase, sign)
                              for slot, layer, phase, sign in records}
                source_by_phase = {phase: [] for phase in range(phases)}
                for _, path in source:
                    source_by_phase[phase_sign[path[0][:2]][0]].append(path)
                expected = [
                    source_by_phase[phase][index]
                    + source_by_phase[phase][index + 1]
                    for phase in range(phases)
                    for index in range(0, 2 * Q, 2)]
                paths = [path for _, path in database]
                self.assertEqual(paths, expected)
                self.assertEqual(starts, [path[0] for path in paths])
                self.assertEqual(len(paths), phases * Q)
                self.assertEqual(
                    {len(path) for path in paths},
                    {winding.num_slots * layers // (phases * Q)})

                occupancy = Counter(node[:2]
                                    for path in paths for node in path)
                self.assertEqual(len(occupancy), winding.num_slots * layers)
                self.assertTrue(all(count == 1 for count in occupancy.values()))
                for path in paths:
                    path_phases = {phase_sign[node[:2]][0] for node in path}
                    signs = [phase_sign[node[:2]][1] for node in path]
                    self.assertEqual(len(path_phases), 1)
                    self.assertEqual((signs[0], signs[-1]), (1, -1))
                    self.assertTrue(all(left == -right
                                        for left, right in zip(signs, signs[1:])))
                branch_report = validate_branches(
                    paths, records, winding.num_slots, poles, Q, phases)
                self.assertTrue(branch_report['layout_retained'], branch_report)
                self.assertTrue(branch_report['topology_valid'], branch_report)
                identity = analyze_pattern_identity(
                    'CP', database, winding, layout)
                self.assertEqual(identity['status'], 'valid', identity['reason'])
                gw.validate_selected_cp(database, winding, layout)
                region_pitch = phases * q
                self.assertTrue(all(
                    pole_region_crossings(start[0], step, region_pitch) <= 1
                    for path in paths for start, end in zip(path, path[1:])
                    for step in circular_travel_steps(
                        start[0], end[0], winding.num_slots)))
                self.assertEqual(
                    database.layout_report['pattern_route']['route_name'],
                    'cp_q_only_pair_join')

    def test_invalid_adjacent_parent_bridge_stays_case_rejected(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'CP', 3, 8, 4, 3, (3, 1, 1), 3)
        decision = gw.resolve_pattern_route(
            'CP', winding, winding.branch_dividers, tp, layout)
        self.assertEqual(decision.route_name, 'cp_q_only_pair_join')
        self.assertEqual(decision.status, 'disabled')
        self.assertIn('CLWP insertion', decision.reason)


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication
from main_pyqt6 import WindingApp


class WindingDividerTests(unittest.TestCase):
    def test_half_q_q_and_pp_config_roundtrip(self):
        w = self.window
        w._apply_config_payload({'inputs': {
            'q': '3/2', 'num_poles': '8', 'num_phases': '3',
            'num_layers': '4', 'ab': '3', 'pattern_name': 'UWP',
            'q_divider': '1.5', 'pp_divider': '2', 'p2_divider': '1'}})
        w._validate_divider_route(check_only=True)
        self.assertEqual(w._selected_dividers(), (Fraction(3, 2), 2, 1))
        payload = w._build_config_payload()
        w._apply_config_payload(payload)
        self.assertEqual(w._selected_dividers(), (Fraction(3, 2), 2, 1))

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = WindingApp()

    def tearDown(self):
        self.window.close()

    def test_default_and_integer_choices_update_naa_exactly(self):
        w = self.window
        self.assertEqual(w._selected_dividers(), (Fraction(3, 2), 1, 2))
        f = w.input_fields
        f['q'].setText('4')
        f['q'].editingFinished.emit()
        f['q_divider'].setCurrentText('2')
        f['pp_divider'].setCurrentText('4')
        f['p2_divider'].setCurrentText('2')
        self.assertEqual(f['ab'].text(), '16')
        self.assertEqual([f['q_divider'].itemText(i) for i in range(f['q_divider'].count())],
                         ['1', '2', '4'])

    def test_ssp_distinct_p2_tuple_is_admitted_before_generation(self):
        w = self.window
        f = w.input_fields
        f['q'].setText('2')
        f['q'].editingFinished.emit()
        f['pattern_name'].setText('SSP')
        f['ab'].setText('2')
        f['ab'].editingFinished.emit()
        f['q_divider'].setCurrentText('1')
        f['p2_divider'].setCurrentText('2')
        w._validate_divider_route()

    def test_config_preserves_selection_and_rejects_inconsistent_product(self):
        w = self.window
        f = w.input_fields
        f['q'].setText('2')
        f['q'].editingFinished.emit()
        f['q_divider'].setCurrentText('1')
        f['pp_divider'].setCurrentText('2')
        saved = w._build_config_payload()
        w._apply_config_payload(saved)
        self.assertEqual(w._selected_dividers(), (1, 2, 1))
        bad = {'inputs': dict(saved['inputs'], ab='3')}
        with self.assertRaisesRegex(ValueError, 'divider product'):
            w._apply_config_payload(bad)

    def test_legacy_config_infers_pattern_default(self):
        w = self.window
        w._apply_config_payload({'inputs': {'q': '2', 'num_poles': '8',
                                            'num_phases': '3', 'ab': '2',
                                            'pattern_name': 'BWP'}})
        self.assertEqual(w._selected_dividers(), (2, 1, 1))

    def test_fractional_unsupported_pattern_is_blocked(self):
        w = self.window
        w.input_fields['pattern_name'].setText('SSP')
        w.input_fields['ab'].setText('1')
        w.input_fields['ab'].editingFinished.emit()
        with self.assertRaisesRegex(ValueError, 'divider combination'):
            w._validate_divider_route()
        self.assertIn('not supported', w.divider_status.text())

    def test_p2_change_preserves_integer_naa_for_half_q_divider(self):
        w = self.window
        w.input_fields['p2_divider'].setCurrentText('1')
        self.assertEqual(w.input_fields['p2_divider'].currentText(), '1')
        self.assertEqual(w.input_fields['q_divider'].currentText(), '1')
        self.assertEqual(w.input_fields['ab'].text(), '1')


class ZppPpOnlyHalfTurnTests(unittest.TestCase):
    def test_zpp_pp_only_route_reproduces_draft_and_validates_layout(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'ZPP', 2, 8, 4, 2, (1, 2, 1), phases=3)
        decision = gw.resolve_pattern_route(
            'ZPP', winding, (1, 2, 1), tp, layout)
        self.assertEqual(decision.status, 'enabled', decision.reason)
        self.assertEqual(decision.route_name, 'zpp_pp_only_half_turn')

        starts, database = gw.get_winding_layout('ZPP', tp, winding, layout)
        self.assertEqual(starts, [path[0] for _, path in database])
        self.assertEqual(len(database), 2 * winding.num_phases)
        self.assertEqual({len(path) for _, path in database}, {32})
        report = validate_branches(
            [path for _, path in database],
            phase_map(winding.num_slots, winding.num_poles,
                      winding.num_layers, layout.phase_shift_list,
                      winding.num_phases),
            winding.num_slots, winding.num_poles, winding.ab,
            winding.num_phases)
        self.assertTrue(report['layout_retained'], report)
        self.assertTrue(report['topology_valid'], report)
        self.assertTrue(report['electrically_valid'], report)
        self.assertEqual(analyze_pattern_identity(
            'ZPP', database, winding, layout)['status'], 'valid')
        gw.validate_selected_zpp(database, winding, layout)

        from pattern_identity import pole_region_crossings
        for branch_id, path in database:
            self.assertEqual(len(database.signed_travel[branch_id]),
                             len(path) - 1)
            for edge_index, (start, end) in enumerate(zip(path, path[1:])):
                self.assertLessEqual(pole_region_crossings(
                    start[0], database.signed_travel[branch_id][edge_index],
                    winding.num_phases * winding.q), 1)

        draft = next((Path(__file__).parent / 'pattern_rule_drafts').glob(
            'ZPP_q-2_pp-4_L-4_Naa-2_Q-1_PP-2_P2-1_Ph-A_Side-insert_'
            'Shifts-0-0-0-0_20260925-154131-072893.json'))
        saved = json.loads(draft.read_text(encoding='utf-8'))
        phase_by_position = {
            (slot, layer): phase for slot, layer, phase, _sign in phase_map(
                winding.num_slots, winding.num_poles, winding.num_layers,
                layout.phase_shift_list, winding.num_phases)}
        phase_a = [path for _, path in database
                   if phase_by_position[path[0][:2]] == 0]
        self.assertEqual(len(phase_a), 2)
        for actual, branch in zip(phase_a, saved['branches']):
            expected = [(node['slot'] - 1, node['layer'] - 1)
                        for node in branch['path']]
            self.assertEqual([node[:2] for node in actual], expected)

    def test_zpp_half_turn_scales_with_pole_pair_layer_and_phase_counts(self):
        from pattern_rule_workbench import _base_inputs

        for pp, layers, phases in ((6, 4, 3), (4, 6, 3), (4, 4, 5)):
            with self.subTest(pp=pp, layers=layers, phases=phases):
                winding, tp, layout = _base_inputs(
                    'ZPP', 2, 2 * pp, layers, 2, (1, 2, 1), phases)
                decision = gw.resolve_pattern_route(
                    'ZPP', winding, (1, 2, 1), tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                starts, database = gw.get_winding_layout(
                    'ZPP', tp, winding, layout)
                self.assertEqual(starts, [path[0] for _, path in database])
                self.assertEqual(len(database), 2 * phases)
                self.assertTrue(database.layout_report['electrically_valid'])
                self.assertEqual(database.layout_report['pattern_identity']['status'],
                                 'valid')

    def test_zpp_half_turn_rejects_insert_side_inlet(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'ZPP', 2, 8, 4, 2, (1, 2, 1), phases=3)
        layout.inlet_from_weld_side = 0
        decision = gw.resolve_pattern_route(
            'ZPP', winding, (1, 2, 1), tp, layout)
        self.assertEqual(decision.status, 'disabled')
        self.assertIn('weld-side inlet', decision.reason)

    def test_zpp_pp_only_route_needs_its_generatable_q_parent(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'ZPP', 4, 8, 4, 2, (1, 2, 1), phases=3)
        decision = gw.resolve_pattern_route(
            'ZPP', winding, (1, 2, 1), tp, layout)
        self.assertEqual(decision.status, 'disabled')
        self.assertEqual(decision.admission, 'unsupported-yet')
        self.assertIn('no validated construction', decision.reason)


class ZppIndexedSectorTranslationTests(unittest.TestCase):
    PATH_SIGNATURES = {
        (3, 3, 3, 4):
            '9b3ef236a55c9b69ef4f831cf7bbcae84e707eca63f9e3b1522018f02534a137',
        (5, 10, 5, 6):
            '280df1f6ffd6bf538f641ce6cf5cd95c900bba068acd353450c5b24f7d134de0',
        (8, 8, 5, 6):
            '07e6b707e495f31ddf61c348483293ae29dec43f8c7b96ea6df28a64875c7dcc',
        (10, 20, 3, 4):
            '4158042fa6c3397e18a189d398423cbc07894d063b0083a2de8f5fa3d3ed304c',
    }

    def test_coprime_domains_generate_and_match_pre_migration_paths(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs

        for (divider, pp, phases, layers), expected_signature in \
                self.PATH_SIGNATURES.items():
            with self.subTest(divider=divider, pp=pp, phases=phases,
                              layers=layers):
                winding, tp, layout = _base_inputs(
                    'ZPP', divider, 2 * pp, layers, divider,
                    (1, divider, 1), phases)
                decision = gw.resolve_pattern_route(
                    'ZPP', winding, (1, divider, 1), tp, layout)
                self.assertEqual(decision.status, 'enabled', decision.reason)
                expected_route = (
                    'zpp_pp_only_half_turn' if divider == 2 else
                    'zpp_pp_only_indexed_translation')
                self.assertEqual(decision.route_name, expected_route)

                starts, database = gw.get_winding_layout(
                    'ZPP', tp, winding, layout)
                self.assertEqual(starts, [path[0] for _, path in database])
                signature = hashlib.sha256(json.dumps(
                    [(branch_id, path) for branch_id, path in database],
                    separators=(',', ':')).encode('utf-8')).hexdigest()
                self.assertEqual(signature, expected_signature)
                self.assertTrue(database.layout_report['layout_retained'])
                self.assertTrue(database.layout_report['topology_valid'])
                self.assertTrue(database.layout_report['electrically_valid'])
                self.assertEqual(
                    analyze_pattern_identity(
                        'ZPP', database, winding, layout)['status'], 'valid')
                gw.validate_selected_zpp(database, winding, layout)

    def test_non_coprime_boundary_uses_formula_derived_sector_stride(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs

        divider, pp, phases, layers = 3, 6, 3, 4
        winding, tp, layout = _base_inputs(
            'ZPP', divider, 2 * pp, layers, divider,
            (1, divider, 1), phases)
        decision = gw.resolve_pattern_route(
            'ZPP', winding, (1, divider, 1), tp, layout)
        self.assertEqual(decision.status, 'enabled', decision.reason)
        self.assertEqual(decision.route_name,
                         'zpp_pp_only_indexed_translation')

        starts, database = gw.get_winding_layout(
            'ZPP', tp, winding, layout)
        self.assertEqual(starts, [path[0] for _, path in database])
        signature = hashlib.sha256(json.dumps(
            [(branch_id, path) for branch_id, path in database],
            separators=(',', ':')).encode('utf-8')).hexdigest()
        self.assertEqual(
            signature,
            'c0fd89294d112395165f9cd6661719edc55c70b3560d70a4797a8a9c72c07d68')
        self.assertEqual(
            database.indexed_sector_deployment['sector_index_multiplier'], 2)
        self.assertEqual(
            database.indexed_sector_deployment['slot_translation_per_branch'],
            (0, 72, 36))
        counts = Counter(
            (slot, layer) for _branch_id, path in database
            for slot, layer, _phase in path)
        self.assertEqual(len(counts), winding.num_slots * layers)
        self.assertTrue(all(count == 1 for count in counts.values()))
        self.assertEqual(len({len(path) for _, path in database}), 1)
        self.assertTrue(database.layout_report['layout_retained'])
        self.assertTrue(database.layout_report['topology_valid'])
        self.assertTrue(database.layout_report['electrically_valid'])
        self.assertEqual(analyze_pattern_identity(
            'ZPP', database, winding, layout)['status'], 'valid')
        gw.validate_selected_zpp(database, winding, layout)

        invalid_winding, invalid_tp, invalid_layout = _base_inputs(
            'ZPP', divider, 10, layers, divider,
            (1, divider, 1), phases)
        invalid = gw.resolve_pattern_route(
            'ZPP', invalid_winding, (1, divider, 1),
            invalid_tp, invalid_layout)
        self.assertEqual(invalid.admission, 'unsupported-yet')

    def test_composite_non_coprime_domain_uses_stride_five(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs

        divider, pp, phases, layers = 6, 12, 3, 4
        winding, tp, layout = _base_inputs(
            'ZPP', divider, 2 * pp, layers, divider,
            (1, divider, 1), phases)
        decision = gw.resolve_pattern_route(
            'ZPP', winding, (1, divider, 1), tp, layout)
        self.assertEqual(decision.status, 'enabled', decision.reason)

        starts, database = gw.get_winding_layout(
            'ZPP', tp, winding, layout)
        self.assertEqual(starts, [path[0] for _, path in database])
        signature = hashlib.sha256(json.dumps(
            [(branch_id, path) for branch_id, path in database],
            separators=(',', ':')).encode('utf-8')).hexdigest()
        self.assertEqual(
            signature,
            '182d627421b7f24d533a4c3d315c2eb824f218664888eceaeee3cb4a3142d650')
        deployment = database.indexed_sector_deployment
        self.assertEqual(deployment['sector_index_multiplier'], 5)
        self.assertEqual(
            deployment['slot_translation_per_branch'],
            (0, 360, 288, 216, 144, 72))
        self.assertTrue(database.layout_report['layout_retained'])
        self.assertEqual(analyze_pattern_identity(
            'ZPP', database, winding, layout)['status'], 'valid')
        gw.validate_selected_zpp(database, winding, layout)

    def test_arrayed_three_phase_sets_apply_indexed_translation_locally(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'ZPP', 1, 6, 6, 3, (1, 3, 1), phases=9)
        decision = gw.resolve_pattern_route(
            'ZPP', winding, (1, 3, 1), tp, layout)
        self.assertEqual(decision.status, 'enabled', decision.reason)
        self.assertEqual(decision.route_name,
                         'zpp_pp_only_indexed_translation')

        starts, database = gw.get_winding_layout(
            'ZPP', tp, winding, layout)
        self.assertEqual(starts, [path[0] for _, path in database])
        self.assertEqual(database.phase_set_array['set_count'], 3)
        self.assertTrue(database.layout_report['layout_retained'])
        self.assertTrue(database.layout_report['topology_valid'])
        self.assertEqual(database.layout_report['layout_status'],
                         'not strong symmetry layout')
        self.assertEqual(database.layout_report['pattern_identity']['status'],
                         'valid')

        local_views = gw._three_phase_set_views(database, winding, layout)
        self.assertEqual(len(local_views), 3)
        for local_database, local_winding, local_layout in local_views:
            self.assertEqual((local_winding.q, local_winding.num_phases,
                              local_winding.num_layers), (3, 3, 2))
            gw.validate_selected_zpp(
                local_database, local_winding, local_layout)
            self.assertEqual(analyze_pattern_identity(
                'ZPP', local_database, local_winding,
                local_layout)['status'], 'valid')

    def test_non_coprime_stride_array_stays_unsupported_on_global_edge_failure(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'ZPP', 1, 12, 6, 3, (1, 3, 1), phases=9)
        decision = gw.resolve_pattern_route(
            'ZPP', winding, (1, 3, 1), tp, layout)
        self.assertEqual(decision.status, 'disabled')
        self.assertEqual(decision.rule_id, 'zpp_array_stride_unvalidated')
        self.assertEqual(decision.admission, 'unsupported-yet')
        self.assertIn('mapped global signed edges', decision.reason)

        # Rebuild the local formula result under an explicit research-only
        # decision to retain the counterexample behind the admission boundary.
        topology = gw._phase_topology_for_winding(winding, layout)
        forced_decision = gw.PatternRouteDecision(
            'enabled', 'zpp_pp_only_indexed_translation',
            'Research-only assembly for the global edge counterexample.',
            'ZPP', (1, 3, 1),
            route_name='zpp_pp_only_indexed_translation',
            required_inlet='weld')
        _starts, candidate = gw._array_three_phase_winding_sets(
            'ZPP', tp, winding, layout, 3,
            route_decision=forced_decision, topology=topology)
        audit = analyze_pattern_identity('ZPP', candidate, winding, layout)
        self.assertEqual(audit['status'], 'candidate')
        self.assertIn('2 boundaries', audit['reason'])
        with self.assertRaisesRegex(ValueError, 'multiple pole regions'):
            gw.validate_selected_zpp(candidate, winding, layout)


class PostConnectionShiftTests(unittest.TestCase):
    def test_public_identity_uses_pre_shift_connection_validation(self):
        from layout_analysis import analyze_pattern_identity
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'ZPP', 2, 8, 6, 8, (2, 4, 1))
        layout.phase_shift_list = [0, 1] * 3
        _starts, shifted = gw.get_winding_layout('ZPP', tp, winding, layout)
        self.assertEqual(analyze_pattern_identity(
            'ZPP', shifted, winding, layout)['status'], 'valid')

    def test_post_shift_identity_is_bound_to_original_winding_and_inlet(self):
        from layout_analysis import (analyze_pattern_identity,
                                     _validated_post_shift_identity)
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'ZPP', 2, 8, 4, 2, (2, 1, 1))
        layout.phase_shift_list = [0, 1] * 2
        _starts, shifted = gw.get_winding_layout('ZPP', tp, winding, layout)
        altered = SimpleNamespace(**vars(winding))
        altered.q, altered.num_poles = 1, 16
        self.assertEqual(analyze_pattern_identity(
            'ZPP', shifted, altered, layout)['status'],
            analyze_pattern_identity(
                'ZPP', list(shifted), altered, layout)['status'])
        layout.inlet_from_weld_side = 1 - layout.inlet_from_weld_side
        self.assertIsNone(_validated_post_shift_identity(
            'ZPP', shifted, winding, layout))

    def test_multiphase_identity_uses_pre_shift_connection_validation(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'ZPP', 1, 8, 8, 2, None, phases=6)
        layout.phase_shift_list = [0, 1] * 4
        _starts, shifted = gw.get_winding_layout('ZPP', tp, winding, layout)
        self.assertEqual(shifted.layout_report['pattern_identity']['status'],
                         'valid')
        self.assertEqual(gw._analyze_pattern_identity_for_sets(
            'ZPP', shifted, winding, layout)['status'], 'valid')

    def test_sector_deployment_starts_follow_post_connection_shift(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'TSP', 2, 8, 4, 4, (2, 2, 1))
        _starts, base = gw.get_winding_layout('TSP', tp, winding, layout)
        layout.phase_shift_list = [0, 1, 0, 1]
        starts, shifted = gw.get_winding_layout('TSP', tp, winding, layout)
        deployment = shifted.sector_deployment_report
        self.assertEqual(deployment['starts'], starts)
        expected_source = [
            ((node[0] + layout.phase_shift_list[node[1]])
             % winding.num_slots, *node[1:])
            for node in base.sector_deployment_report['source_starts']]
        self.assertEqual(deployment['source_starts'], expected_source)
        self.assertEqual(shifted.layout_report['sector_deployment'], deployment)

    def test_indexed_zpp_deployment_starts_follow_post_connection_shift(self):
        from pattern_rule_workbench import _base_inputs

        for q, poles, layers, naa, factors in (
                (3, 12, 4, 3, (1, 3, 1)),
                (2, 8, 4, 2, (1, 2, 1))):
            with self.subTest(q=q, factors=factors):
                winding, tp, layout = _base_inputs(
                    'ZPP', q, poles, layers, naa, factors)
                layout.phase_shift_list = [1, 0] * (layers // 2)
                starts, shifted = gw.get_winding_layout(
                    'ZPP', tp, winding, layout)
                self.assertEqual(
                    shifted.indexed_sector_deployment['starts'], starts)
                if hasattr(shifted, 'half_turn_deployment'):
                    self.assertEqual(
                        shifted.half_turn_deployment['starts'], starts)

    def test_fractional_transposition_report_uses_shifted_coordinates(self):
        from fractions import Fraction
        from pattern_rule_workbench import _base_inputs

        q = Fraction(3, 2)
        winding, tp, layout = _base_inputs(
            'UWP', q, 8, 6, 3, (q, 1, 2))
        tp.pole_group_tp = {'PoleN': {'tp_type': 'Times', 'tp_times': 1}}
        layout.phase_shift_list = [0, 1] * 3
        _starts, paths = gw.get_winding_layout(
            'UWP', tp, winding, layout, allow_candidate=True)
        details = paths.transposition_report
        self.assertEqual(details['coordinate_reference'], 'after shift')
        self.assertTrue(details['edges'])
        for edge in details['edges']:
            path = paths[edge['branch'] - 1][1]
            index = edge['edge'] - 1
            self.assertEqual(edge['from'], path[index][:2])
            self.assertEqual(edge['to'], path[index + 1][:2])
            self.assertEqual((edge['from'][0] + edge['signed_pitch'])
                             % winding.num_slots, edge['to'][0])
        positions = {node[:2] for _branch, path in paths for node in path}
        for exchange in details['exchanges']:
            self.assertTrue(set(exchange['conductors']) <= positions)
            self.assertTrue({node for pair in exchange['weld_pairs']
                             for node in pair} <= positions)

    def test_odd_phase_radial_swap_uses_one_global_layer_set(self):
        from pattern_rule_workbench import _base_inputs

        winding, tp, layout = _base_inputs(
            'ZPP', 2, 8, 8, 2, (1, 2, 1), phases=7)
        _starts, base = gw.get_winding_layout('ZPP', tp, winding, layout)
        layout.radial_shift = 1
        _starts, shifted = gw.get_winding_layout('ZPP', tp, winding, layout)
        checked = 0
        for (_base_id, base_path), (_shift_id, shift_path) in zip(base, shifted):
            for before, after in zip(base_path, shift_path):
                if before[1] in (3, 4) and before[0] < 14:
                    self.assertEqual(after[:2],
                                     (before[0], 4 if before[1] == 3 else 3))
                    checked += 1
        self.assertGreater(checked, 0)
        self.assertTrue(shifted.layout_report['layout_retained'])

    def test_signed_travel_and_series_bridge_follow_shifted_endpoints(self):
        from pattern_rule_workbench import _base_inputs

        cases = [('ZPP', 2, 8, 4, 2, (1, 2, 1)),
                 ('UWP', 4, 8, 4, 2, (2, 1, 1))]
        for pattern, q, poles, layers, naa, dividers in cases:
            with self.subTest(pattern=pattern):
                winding, tp, layout = _base_inputs(
                    pattern, q, poles, layers, naa, dividers)
                layout.phase_shift_list = gw.get_phase_shift_list(
                    winding, 'Increment', -1, 1, log=lambda _: None)
                layout.radial_shift = 1
                _starts, paths = gw.get_winding_layout(
                    pattern, tp, winding, layout)
                travel = getattr(paths, 'signed_travel', {})
                for branch_id, path in paths:
                    if branch_id in travel:
                        self.assertEqual(len(travel[branch_id]), len(path) - 1)
                        for (start, end), step in zip(zip(path, path[1:]),
                                                      travel[branch_id]):
                            self.assertEqual((start[0] + step)
                                             % winding.num_slots, end[0])
                for bridge in getattr(paths, 'series_connections', ()):
                    path = paths[bridge['branch_id'] - 1][1]
                    index = bridge['edge_index']
                    self.assertEqual(bridge['start'], path[index][:2])
                    self.assertEqual(bridge['end'], path[index + 1][:2])

    def test_supported_patterns_apply_phase_and_radial_shifts_after_connections(self):
        from pattern_rule_workbench import _base_inputs

        cases = [(pattern, 6, 2, None) for pattern in (
            'BWP', 'UWP', 'SSP', 'TSP', 'SLP', 'ZLP', 'ZPP', 'TLP')]
        cases += [('CP', 4, 2, None), ('LPP', 4, 4, (1, 4, 1)),
                  ('ZPP', 6, 8, (2, 4, 1))]
        for pattern, layers, naa, dividers in cases:
            winding, tp, neutral = _base_inputs(
                pattern, 2, 8, layers, naa, dividers)
            base_starts, base_paths = gw.get_winding_layout(
                pattern, tp, winding, neutral)
            for slot_shift, radial_shift in ((1, 0), (0, 1), (1, 1)):
                with self.subTest(pattern=pattern, layers=layers, naa=naa,
                                  slot_shift=slot_shift, radial_shift=radial_shift):
                    layout = _base_inputs(
                        pattern, 2, 8, layers, naa, dividers)[2]
                    layout.phase_shift_list = gw.get_phase_shift_list(
                        winding, 'Normal', slot_shift, 1, log=lambda _: None)
                    layout.radial_shift = radial_shift
                    starts, paths = gw.get_winding_layout(
                        pattern, tp, winding, layout)

                    def shifted(node):
                        slot, layer, *tail = node
                        if radial_shift and 0 < layer < layers - 1 and slot < 6:
                            layer += 1 if layer % 2 else -1
                        return ((slot + layout.phase_shift_list[layer])
                                % winding.num_slots, layer, *tail)

                    expected = [[branch_id, [shifted(node) for node in path]]
                                for branch_id, path in base_paths]
                    self.assertEqual(list(paths), expected)
                    self.assertEqual(starts,
                                     [shifted(node) for node in base_starts])
                    self.assertTrue(paths.layout_report['layout_retained'])
                    self.assertEqual(paths.layout_report['pattern_identity']['status'],
                                     'valid')


if __name__ == '__main__':
    unittest.main()
