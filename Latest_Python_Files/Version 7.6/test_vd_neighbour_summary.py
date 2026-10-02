"""Voltage-difference summary metrics for physically neighbouring conductors."""
import unittest
import math

import vd_optimize as vdo


class VDNeighbourSummaryTests(unittest.TestCase):
    def test_phase_angles_use_one_m_phase_formula(self):
        for phases in (3, 5, 7):
            for phase in range(phases):
                self.assertAlmostEqual(
                    vdo.phase_angle_rad(phase, phases),
                    -2.0 * math.pi * phase / phases)

    def test_adjacent_slot_metric_uses_same_layer_and_wraps_slot_ring_once(self):
        # slot, layer, phase, branch, conductor index
        conductors = [
            [0, 0, 0, 0, 0], [0, 1, 0, 0, 4],
            [1, 0, 0, 0, 7], [1, 1, 0, 0, 5],
        ]
        result = vdo.compute_adjacent_slot_voltage_difference(
            conductors, num_slots=2, num_layers=2, voltage_drop=100, index_span=10)

        self.assertAlmostEqual(result.max_voltage, 70.0)
        self.assertAlmostEqual(result.max_equivalent_index, 7.0)
        self.assertEqual(result.pair_count, 2)
        self.assertEqual(result.cross_phase_pair_count, 0)

    def test_adjacent_slot_interlayer_metric_checks_both_diagonals(self):
        conductors = [
            [0, 0, 0, 0, 0], [0, 1, 0, 0, 4],
            [1, 0, 0, 0, 7], [1, 1, 0, 0, 5],
        ]
        result = vdo.compute_adjacent_slot_interlayer_voltage_difference(
            conductors, num_slots=2, num_layers=2, voltage_drop=100, index_span=10)

        self.assertAlmostEqual(result.max_voltage, 50.0)
        self.assertAlmostEqual(result.max_equivalent_index, 5.0)
        self.assertEqual(result.pair_count, 2)


if __name__ == "__main__":
    unittest.main()
