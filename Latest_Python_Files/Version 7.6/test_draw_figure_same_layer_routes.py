import unittest
from collections import namedtuple

import matplotlib.pyplot as plt
from matplotlib.patches import Arc

from draw_figure import (
    SameLayerRouteLane,
    build_same_layer_route_lanes,
    build_unwrapped_same_layer_route_lanes,
    draw_connection,
    same_layer_route_radius,
)


WindingPara = namedtuple("WindingPara", "num_layers num_slots num_poles")
FigurePara = namedtuple(
    "FigurePara",
    "outer_radius inner_radius layer_height inner_layer_width slotindex_offset",
)


class SameLayerRouteTests(unittest.TestCase):
    def setUp(self):
        self.winding = WindingPara(num_layers=6, num_slots=48, num_poles=8)
        self.figure = FigurePara(
            outer_radius=12.0,
            inner_radius=3.0,
            layer_height=1.5,
            inner_layer_width=1.0,
            slotindex_offset=-0.55,
        )

    def test_lines_in_one_physical_region_receive_distinct_lanes(self):
        branches = [
            (10, [(0, 0, 4), (6, 0, 4)]),
            (11, [(1, 0, 4), (7, 0, 4)]),
            (12, [(2, 0, 4), (8, 0, 4)]),
        ]
        pole_regions = {
            (0, 0, 4): 0, (6, 0, 4): 1,
            (1, 0, 4): 0, (7, 0, 4): 1,
            (2, 0, 4): 0, (8, 0, 4): 1,
        }

        lanes = build_same_layer_route_lanes(branches, self.winding, pole_regions)

        self.assertEqual({lane.rank for lane in lanes.values()}, {0, 1, 2})
        self.assertTrue(all(lane.count == 3 for lane in lanes.values()))

    def test_different_physical_regions_restart_at_their_base_radius(self):
        branches = [
            (10, [(0, 0, 4), (3, 0, 4)]),
            (11, [(1, 0, 4), (7, 0, 4)]),
            (12, [(2, 0, 4), (12, 0, 4)]),
        ]
        pole_regions = {
            (0, 0, 4): 0, (3, 0, 4): 1,
            (1, 0, 4): 2, (7, 0, 4): 3,
            (2, 0, 4): 4, (12, 0, 4): 5,
        }

        lanes = build_same_layer_route_lanes(branches, self.winding, pole_regions)

        self.assertEqual({lane.rank for lane in lanes.values()}, {0})
        self.assertTrue(all(lane.count == 1 for lane in lanes.values()))

    def test_same_region_orders_lanes_by_pitch_before_branch_order(self):
        branches = [
            (30, [(3, 0, 4), (10, 0, 4)]),  # pitch 7
            (20, [(0, 0, 4), (5, 0, 4)]),   # pitch 5
            (10, [(1, 0, 4), (9, 0, 4)]),   # pitch 8
        ]
        pole_regions = {
            (3, 0, 4): 0, (10, 0, 4): 1,
            (0, 0, 4): 0, (5, 0, 4): 1,
            (1, 0, 4): 0, (9, 0, 4): 1,
        }

        lanes = build_same_layer_route_lanes(branches, self.winding, pole_regions)

        self.assertEqual(lanes[(20, 0)].rank, 0)
        self.assertEqual(lanes[(30, 0)].rank, 1)
        self.assertEqual(lanes[(10, 0)].rank, 2)

    def test_outer_and_inner_layers_route_to_opposite_sides(self):
        outer_radii = [same_layer_route_radius(0, rank, 3, self.winding, self.figure) for rank in range(3)]
        inner_radii = [same_layer_route_radius(5, rank, 3, self.winding, self.figure) for rank in range(3)]

        self.assertEqual(len(set(outer_radii)), 3)
        self.assertEqual(len(set(inner_radii)), 3)
        self.assertTrue(all(radius > self.figure.outer_radius for radius in outer_radii))
        self.assertTrue(all(radius < self.figure.inner_radius for radius in inner_radii))
        self.assertEqual(outer_radii, sorted(outer_radii))
        self.assertEqual(inner_radii, sorted(inner_radii, reverse=True))

    def test_explicit_radii_gap_controls_grid_clearance_and_lane_spacing(self):
        gap = 0.20
        outer = [same_layer_route_radius(0, rank, 3, self.winding, self.figure, gap) for rank in range(3)]
        inner = [same_layer_route_radius(5, rank, 3, self.winding, self.figure, gap) for rank in range(3)]

        self.assertEqual(outer, [12.20, 12.40, 12.60])
        self.assertEqual(inner, [2.80, 2.60, 2.40])

    def test_lane_assignment_is_stable_across_input_branch_order(self):
        branches = [
            (20, [(4, 0, 2), (8, 0, 2)]),
            (10, [(0, 0, 2), (4, 0, 2)]),
        ]
        forward = build_same_layer_route_lanes(branches, self.winding)
        reverse = build_same_layer_route_lanes(list(reversed(branches)), self.winding)

        self.assertEqual(forward, reverse)

    def test_unwrapped_overlapping_spans_use_distinct_lanes_across_regions(self):
        branches = [
            (10, [(0, 0, 2), (8, 0, 2)]),
            (11, [(4, 0, 2), (12, 0, 2)]),
            (12, [(16, 0, 2), (20, 0, 2)]),
        ]

        lanes = build_unwrapped_same_layer_route_lanes(
            branches, self.winding, boundary_only=False)

        self.assertNotEqual(lanes[(10, 0)].rank, lanes[(11, 0)].rank)
        self.assertEqual(lanes[(10, 0)].count, 2)
        self.assertEqual(lanes[(11, 0)].count, 2)
        self.assertEqual(lanes[(12, 0)].rank, 0)

    def test_unwrapped_seam_spans_share_lanes_only_when_visible_parts_do_not_overlap(self):
        branches = [
            (10, [(46, 5, 2), (2, 5, 2)]),
            (11, [(47, 5, 2), (3, 5, 2)]),
            (12, [(10, 5, 2), (14, 5, 2)]),
        ]

        lanes = build_unwrapped_same_layer_route_lanes(
            branches, self.winding, boundary_only=False)

        self.assertNotEqual(lanes[(10, 0)].rank, lanes[(11, 0)].rank)
        self.assertEqual(lanes[(12, 0)].rank, 0)

    def test_radial_center_mode_draws_two_radial_legs_and_one_center_arc(self):
        figure, axis = plt.subplots()
        try:
            coordinates = {
                0: {0: (0.0, 11.25)},
                8: {0: (1.1, 11.25)},
            }
            draw_connection(
                axis, 0, 0, 8, 0, coordinates, self.winding,
                draw_arrow=0,
                Fig_Para=self.figure,
                same_layer_route_style="radial_center_arc",
                route_lane=SameLayerRouteLane(2, 3),
            )

            self.assertEqual(len(axis.lines), 2)
            self.assertEqual(sum(isinstance(patch, Arc) for patch in axis.patches), 1)
            self.assertGreater(axis.get_xlim()[1], self.figure.outer_radius)
        finally:
            plt.close(figure)


if __name__ == "__main__":
    unittest.main()
