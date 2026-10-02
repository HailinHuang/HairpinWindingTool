from fractions import Fraction
import hashlib
import unittest

from half_integer_q_connection_formulas import (
    HalfIntegerQFormulaError,
    build_uwp_half_integer_p2_definition,
    resolve_uwp_half_integer_formula,
    transfer_uwp_half_integer_q_pp,
)


class HalfIntegerQFormulaBindingTests(unittest.TestCase):
    def test_bindings_keep_exact_source_and_target_dividers(self):
        for q in (Fraction(1, 2), Fraction(3, 2), Fraction(5, 2)):
            with self.subTest(q=q):
                p2 = resolve_uwp_half_integer_formula(
                    "uwp_half_integer_p2", q, (q, 1, 2), pole_pairs=4)
                self.assertEqual(p2.source_dividers, (q, 1, 2))
                self.assertEqual(p2.target_dividers, (q, 1, 2))
                self.assertEqual(p2.source_naa, 2 * q)
                self.assertEqual(p2.target_naa, 2 * q)

                if q > 1:
                    transfer = resolve_uwp_half_integer_formula(
                        "uwp_half_integer_q_pp", q, (q, 2, 1), pole_pairs=4)
                    self.assertEqual(transfer.source_dividers, (q, 1, 2))
                    self.assertEqual(transfer.target_dividers, (q, 2, 1))
                    self.assertEqual(transfer.source_naa, transfer.target_naa)

    def test_bindings_reject_nonintegral_or_out_of_family_tuples(self):
        cases = (
            ("uwp_half_integer_p2", Fraction(3, 2), (Fraction(3, 2), 1, 1), 4),
            ("uwp_half_integer_p2", Fraction(3, 2), (Fraction(3, 2), 2, 2), 4),
            ("uwp_half_integer_q_pp", Fraction(3, 2), (Fraction(3, 2), 1, 2), 4),
            ("uwp_half_integer_q_pp", Fraction(3, 2), (Fraction(3, 2), 2, 1), 3),
        )
        for route, q, dividers, pole_pairs in cases:
            with self.subTest(route=route, dividers=dividers, pole_pairs=pole_pairs):
                with self.assertRaises(HalfIntegerQFormulaError):
                    resolve_uwp_half_integer_formula(
                        route, q, dividers, pole_pairs=pole_pairs)

        with self.assertRaises(HalfIntegerQFormulaError):
            resolve_uwp_half_integer_formula(
                "uwp_half_integer_q_pp", Fraction(1, 2),
                (Fraction(1, 2), 2, 1), pole_pairs=4)

        for q in (2, Fraction(1, 3), 0):
            with self.subTest(q=q):
                with self.assertRaises(HalfIntegerQFormulaError):
                    resolve_uwp_half_integer_formula(
                        "uwp_half_integer_p2", q, (q, 1, 2), pole_pairs=4)

    def test_divider_rule_rejects_q_d_p2_when_d_p2_exceeds_two(self):
        from types import SimpleNamespace

        import get_winding_pattern as gw

        q = Fraction(3, 2)
        dividers = (q, 2, 2)
        winding = SimpleNamespace(
            q=q, num_slots=36, num_poles=8, num_phases=3,
            num_layers=4, ab=6, branch_dividers=dividers)
        layout = SimpleNamespace(
            phase_shift_list=[0] * 4, radial_shift=0,
            inlet_from_weld_side=0)
        configuration = SimpleNamespace(
            tp_type="Regular", tp_interval=0, tp_times=0, uni_tp=0,
            pltp_fl=0, pltp_ll=0, jltp=0, jld=1)
        expected_reason = (
            "UWP pp-divider and P2-divider share the same splitting allowance; "
            "their product must be 1 or 2.")

        self.assertFalse(gw.is_half_integer_uwp_p2_factorization(
            "UWP", winding, dividers))
        self.assertFalse(gw.supports_half_integer_uwp_p2(
            "UWP", winding, dividers))

        decision = gw.resolve_pattern_route(
            "UWP", winding, dividers, configuration, layout)
        self.assertEqual(decision.status, "disabled")
        self.assertEqual(decision.admission, "rejected")
        self.assertEqual(decision.rule_id, "uwp_factor_rejected")
        self.assertEqual(decision.reason, expected_reason)

        with self.assertRaises(gw.PatternConfigurationError) as caught:
            gw.get_winding_layout(
                "UWP", configuration, winding, layout, allow_candidate=True)
        self.assertEqual(caught.exception.category, "pattern_specific_infeasible")
        self.assertEqual(str(caught.exception),
                         f"[pattern_specific_infeasible] UWP: {expected_reason}")

        lpp_winding = SimpleNamespace(
            q=q, num_slots=36, num_poles=8, num_phases=3,
            num_layers=4, ab=3, branch_dividers=(q, 1, 2))
        lpp = gw.resolve_pattern_route("LPP", lpp_winding, (q, 1, 2))
        self.assertEqual(lpp.status, "disabled")
        self.assertEqual(lpp.admission, "rejected")
        self.assertEqual(lpp.rule_id, "lpp_factor_rejected")


class HalfIntegerUWPIntegrationTests(unittest.TestCase):
    def test_public_paths_match_pre_migration_signatures(self):
        from types import SimpleNamespace

        import get_winding_pattern as gw

        cases = (
            (Fraction(1, 2), 3, 4, (Fraction(1, 2), 1, 2),
             "38c93231468555c07609b3ab1cb98d4633cebb746c54395bd719d5cea781c950",
             "uwp_half_integer_p2"),
            (Fraction(3, 2), 3, 4, (Fraction(3, 2), 1, 2),
             "5cb18f74ab1f90b0d6392466c0f488fec57db6a6f1ad87068d41f1e662a98f29",
             "uwp_half_integer_p2"),
            (Fraction(5, 2), 5, 4, (Fraction(5, 2), 1, 2),
             "0fa6f2bd0deae26b00c3713dd141d51a1faf20383813aeee89b25e7b714caf06",
             "uwp_half_integer_p2"),
            (Fraction(3, 2), 3, 4, (Fraction(3, 2), 2, 1),
             "d1102ef480e309da8db6c57f519ea3e17a645997ffdce3dd56dec98da6b4e007",
             "uwp_half_integer_q_pp"),
            (Fraction(5, 2), 5, 4, (Fraction(5, 2), 2, 1),
             "de4c261e970c585b56640e8a364fce3ba6b9d593670511b205019fbc208bf01f",
             "uwp_half_integer_q_pp"),
        )

        for q, phases, layers, dividers, expected_hash, route_name in cases:
            with self.subTest(q=q, phases=phases, dividers=dividers):
                poles = 8
                winding = SimpleNamespace(
                    q=q, num_slots=int(q * poles * phases), num_poles=poles,
                    num_phases=phases, num_layers=layers,
                    ab=int(dividers[0] * dividers[1] * dividers[2]),
                    branch_dividers=dividers)
                layout = SimpleNamespace(
                    phase_shift_list=[index % 2 for index in range(layers)],
                    radial_shift=0, inlet_from_weld_side=0)
                configuration = SimpleNamespace(
                    tp_type="Regular", tp_interval=0, tp_times=0, uni_tp=0,
                    pltp_fl=0, pltp_ll=0, jltp=0, jld=1)

                decision = gw.resolve_pattern_route(
                    "UWP", winding, dividers, configuration, layout)
                self.assertEqual(decision.status, "enabled", decision.reason)
                self.assertEqual(decision.admission, "supported")
                self.assertEqual(decision.route_name, route_name)

                starts, branches = gw.get_winding_layout(
                    "UWP", configuration, winding, layout, allow_candidate=True)
                self.assertTrue(branches.layout_report["layout_retained"])
                signature = hashlib.sha256(repr((
                    starts, [(branch_id, path) for branch_id, path in branches]
                )).encode()).hexdigest()
                self.assertEqual(signature, expected_hash)


class HalfIntegerUWPP2DefinitionTests(unittest.TestCase):
    def test_definition_is_parameterized_by_half_integer_q(self):
        for q in (Fraction(1, 2), Fraction(3, 2), Fraction(5, 2)):
            for phases in (3, 5):
                for layers in (2, 4):
                    with self.subTest(q=q, phases=phases, layers=layers):
                        poles = 8
                        slots = int(q * poles * phases)
                        shifts = [0] + [(-1) ** index * index
                                        for index in range(1, layers)]
                        phase_by_position = {
                            ((slot + shifts[0]) % slots, 0): slot % phases
                            for slot in range(slots)
                        }
                        definition = build_uwp_half_integer_p2_definition(
                            q,
                            dividers=(q, 1, 2),
                            num_slots=slots,
                            num_poles=poles,
                            num_phases=phases,
                            num_layers=layers,
                            phase_shift_list=shifts,
                            phase_by_position=phase_by_position,
                        )

                        period = int(2 * q * phases)
                        expected_order = sorted(
                            range(period), key=lambda slot: (slot % phases, slot))
                        self.assertEqual(definition.slots_per_two_poles, period)
                        self.assertEqual(
                            definition.slots_per_pole_region, q * phases)
                        self.assertEqual(
                            [start[2] for start in definition.starts], expected_order)
                        self.assertEqual(
                            len(definition.starts), int(2 * q) * phases)
                        self.assertEqual(
                            len(definition.connections), 8 * (layers // 2) - 1)
                        self.assertEqual(
                            definition.connections[:4],
                            ((1, 1, 0), (1, -1, 1), (1, 1, 0), (1, -1, 1)),
                        )
                        self.assertEqual(definition.connections[-1], (1, 1, 0))

    def test_definition_rejects_invalid_geometry_and_missing_phase_records(self):
        q = Fraction(3, 2)
        params = dict(
            q=q,
            dividers=(q, 1, 2),
            num_slots=36,
            num_poles=8,
            num_phases=3,
            num_layers=4,
            phase_shift_list=[0, 0, 0, 0],
            phase_by_position={(slot, 0): slot % 3 for slot in range(36)},
        )
        for changes in (
            {"num_slots": 37},
            {"num_phases": 4},
            {"num_layers": 3},
            {"dividers": (q, 2, 2)},
            {"phase_by_position": {}},
        ):
            with self.subTest(changes=changes):
                candidate = dict(params)
                candidate.update(changes)
                with self.assertRaises(HalfIntegerQFormulaError):
                    build_uwp_half_integer_p2_definition(**candidate)


class HalfIntegerUWPTransferTests(unittest.TestCase):
    def test_transfer_reverses_and_rotates_complete_second_cohort(self):
        q = Fraction(3, 2)
        shifts = [0, 1]
        first_cohort_path = [
            (0, 0, 0), (5, 1, 4), (9, 0, 9), (14, 1, 13),
            (18, 0, 18), (23, 1, 22), (27, 0, 27), (32, 1, 31),
        ]
        second_cohort_path = list(reversed(first_cohort_path))
        source = [
            (branch_id, list(second_cohort_path if branch_id == 2
                             else first_cohort_path))
            for branch_id in range(1, 10)
        ]
        oriented = [
            (branch_id, list(first_cohort_path if branch_id != 2
                             else reversed(second_cohort_path)))
            for branch_id in range(1, 10)
        ]
        pole_sign = {
            (0, 0): 1, (32, 1): -1,
        }
        result = transfer_uwp_half_integer_q_pp(
            source,
            oriented,
            q=q,
            source_dividers=(q, 1, 2),
            target_dividers=(q, 2, 1),
            num_slots=36,
            num_poles=8,
            num_phases=3,
            num_layers=2,
            phase_shift_list=shifts,
            pole_sign_by_position=pole_sign,
        )

        self.assertEqual(result.two_pole_slot_period, 9)
        self.assertEqual(result.slots_per_pole_region, Fraction(9, 2))
        self.assertEqual(result.branch_rotations, (0, 18, 0, 0, 0, 0, 0, 0, 0))
        self.assertEqual(
            [branch_id for branch_id, _ in result.branches], list(range(1, 10)))
        self.assertEqual(result.branches[0][1], tuple(oriented[0][1]))
        self.assertEqual(
            result.branches[1][1],
            tuple((slot, layer, position) for slot, layer, position in
                  ((18, 0, 0), (23, 1, 4), (27, 0, 9), (32, 1, 13),
                   (0, 0, 18), (5, 1, 22), (9, 0, 27), (14, 1, 31))),
        )

    def test_transfer_rejects_no_second_cohort_and_invalid_edges(self):
        q = Fraction(3, 2)
        shifts = [0, 0]
        path = [(0, 0, 0), (4, 1, 4), (9, 0, 9), (13, 1, 13),
                (18, 0, 18), (22, 1, 22), (27, 0, 27), (31, 1, 31)]
        source = [(branch_id, list(path)) for branch_id in range(1, 10)]
        oriented = [(branch_id, list(path)) for branch_id in range(1, 10)]
        pole_sign = {(0, 0): 1, (31, 1): -1}
        with self.assertRaises(HalfIntegerQFormulaError):
            transfer_uwp_half_integer_q_pp(
                source, oriented, q=q,
                source_dividers=(q, 1, 2), target_dividers=(q, 2, 1),
                num_slots=36, num_poles=8, num_phases=3, num_layers=2,
                phase_shift_list=shifts, pole_sign_by_position=pole_sign)

        wrong_direction = list(path)
        wrong_direction[2], wrong_direction[3] = (
            wrong_direction[3], wrong_direction[2])
        reversed_source = [
            (branch_id, list(reversed(wrong_direction)) if branch_id == 2
             else list(path))
            for branch_id in range(1, 10)
        ]
        target_branches = [
            (branch_id, wrong_direction if branch_id == 2 else list(path))
            for branch_id in range(1, 10)
        ]
        with self.assertRaises(HalfIntegerQFormulaError):
            transfer_uwp_half_integer_q_pp(
                reversed_source, target_branches, q=q,
                source_dividers=(q, 1, 2), target_dividers=(q, 2, 1),
                num_slots=36, num_poles=8, num_phases=3, num_layers=2,
                phase_shift_list=shifts, pole_sign_by_position=pole_sign)


if __name__ == "__main__":
    unittest.main()
