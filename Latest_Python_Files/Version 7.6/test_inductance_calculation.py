"""Independent checks for active-length partial-inductance aggregation."""

import math
import unittest

import numpy as np

import inductance_calculation as ic


class InductanceCalculationTests(unittest.TestCase):
    def test_rectangular_conductor_gmr_uses_exact_width_and_height_gmd(self):
        square_gmr = ic.rectangular_conductor_gmr(0.001, 0.001)
        rectangular_gmr = ic.rectangular_conductor_gmr(0.004, 0.002)

        self.assertAlmostEqual(square_gmr, 0.0004470491559036624, places=15)
        self.assertAlmostEqual(rectangular_gmr, 0.0013416068639590493, places=15)
        self.assertAlmostEqual(
            rectangular_gmr,
            ic.rectangular_conductor_gmr(0.002, 0.004),
            places=15,
        )

    def test_active_inductance_reports_gmr_from_conductor_dimensions(self):
        conductors = [
            (0, 0, 0, 1, 0, 0, 0),
            (3, 0, 0, 1, 1, 0, 0),
            (1, 0, 1, 2, 0, 0, 0),
            (2, 0, 1, 2, 1, 0, 0),
        ]
        phase_records = [
            (0, 0, 0, 1), (3, 0, 0, -1),
            (1, 0, 1, -1), (2, 0, 1, 1),
        ]
        result = ic.calculate_active_inductance(
            conductors, phase_records, num_slots=6, layer_radii_mm=[50.0],
            active_length_mm=120.0, conductor_width_mm=4.0,
            conductor_height_mm=2.0)

        self.assertAlmostEqual(
            result.conductor_gmr_m,
            ic.rectangular_conductor_gmr(0.004, 0.002),
            places=15,
        )

    def test_normalized_matrix_uses_each_pair_of_self_inductances(self):
        matrix = np.array([
            [4.0, -1.0, 2.0],
            [-1.0, 9.0, 3.0],
            [2.0, 3.0, 16.0],
        ])

        normalized = ic.normalize_inductance_matrix(matrix)

        np.testing.assert_allclose(
            normalized,
            [
                [1.0, -1.0 / 6.0, 0.25],
                [-1.0 / 6.0, 1.0, 0.25],
                [0.25, 0.25, 1.0],
            ],
        )

    def test_normalized_matrix_rejects_nonpositive_self_inductance(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            ic.normalize_inductance_matrix([[1.0, 0.0], [0.0, 0.0]])

    def test_finite_parallel_segment_matches_closed_form(self):
        length = 0.120
        spacing = 0.010
        expected = (ic.MU_0 / (2 * math.pi)
                    * (length * math.asinh(length / spacing)
                       - math.hypot(length, spacing) + spacing))

        actual = ic.finite_parallel_partial_inductance(length, spacing)

        self.assertAlmostEqual(actual, expected, places=15)

    def test_branch_matrix_uses_layout_position_and_signed_direction(self):
        conductors = [
            (0, 0, 0, 1, 0, 0, 0),
            (3, 0, 0, 1, 1, 0, 0),
            (1, 0, 1, 2, 0, 0, 0),
            (2, 0, 1, 2, 1, 0, 0),
        ]
        phase_records = [
            (0, 0, 0, 1),
            (3, 0, 0, -1),
            (1, 0, 1, -1),
            (2, 0, 1, 1),
        ]

        result = ic.calculate_active_inductance(
            conductors,
            phase_records,
            num_slots=6,
            layer_radii_mm=[50.0],
            active_length_mm=120.0,
            conductor_width_mm=4.0,
            conductor_height_mm=2.0,
        )

        self.assertEqual(result.branch_ids, (1, 2))
        self.assertEqual(result.branch_phases, (0, 1))
        np.testing.assert_allclose(result.branch_matrix_h, result.branch_matrix_h.T)
        self.assertGreater(result.branch_matrix_h[0, 0], 0.0)
        self.assertGreater(result.branch_matrix_h[1, 1], 0.0)
        self.assertNotAlmostEqual(result.branch_matrix_h[0, 1], 0.0, places=15)
        reversed_result = ic.calculate_active_inductance(
            conductors,
            [phase_records[0], phase_records[1],
             (1, 0, 1, 1), (2, 0, 1, -1)],
            num_slots=6,
            layer_radii_mm=[50.0],
            active_length_mm=120.0,
            conductor_width_mm=4.0,
            conductor_height_mm=2.0,
        )
        self.assertAlmostEqual(
            reversed_result.branch_matrix_h[0, 1],
            -result.branch_matrix_h[0, 1],
            places=15,
        )
        self.assertLessEqual(
            abs(result.branch_matrix_h[0, 1]),
            math.sqrt(result.branch_matrix_h[0, 0] * result.branch_matrix_h[1, 1]),
        )
        np.testing.assert_allclose(np.diag(result.branch_coupling_matrix), 1.0)
        np.testing.assert_allclose(np.diag(result.phase_coupling_matrix), 1.0)
        self.assertAlmostEqual(
            result.branch_coupling_matrix[0, 1],
            result.branch_matrix_h[0, 1]
            / math.sqrt(result.branch_matrix_h[0, 0]
                        * result.branch_matrix_h[1, 1]),
        )

    def test_phase_matrix_assumes_equal_current_sharing_between_parallel_branches(self):
        branch_matrix = np.array([
            [4.0, 1.0, 0.4, 0.2],
            [1.0, 4.0, 0.2, 0.4],
            [0.4, 0.2, 5.0, 1.0],
            [0.2, 0.4, 1.0, 5.0],
        ])

        phases, phase_matrix = ic.aggregate_phase_matrix(
            branch_matrix, branch_phases=(0, 0, 1, 1))

        self.assertEqual(phases, (0, 1))
        np.testing.assert_allclose(phase_matrix, [[2.5, 0.3], [0.3, 3.0]])

    def test_phase_matrix_rejects_wrong_branch_count_in_any_phase(self):
        with self.assertRaisesRegex(ValueError, "branches per phase"):
            ic.aggregate_phase_matrix(
                np.eye(6),
                branch_phases=(0, 0, 0, 1, 1, 2),
                expected_phase_ids=(0, 1, 2),
                expected_branches_per_phase=2,
            )

    def test_invalid_or_unassigned_layout_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "assigned branch"):
            ic.calculate_active_inductance(
                [(0, 0, 0, 0, 0, 0, 0)],
                [(0, 0, 0, 1)],
                num_slots=1,
                layer_radii_mm=[50.0],
                active_length_mm=120.0,
                conductor_width_mm=4.0,
                conductor_height_mm=2.0,
            )


if __name__ == "__main__":
    unittest.main()
