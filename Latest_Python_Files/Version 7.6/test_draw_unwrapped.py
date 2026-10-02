import copy
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch
import draw_figure as df


class UnwrappedTests(unittest.TestCase):
    def setUp(self):
        self.w = NS(num_slots=8, num_layers=3, num_phases=1, ab=1)
        self.layout = NS(in_out_connection=1, inlet_index_adjustments_phase_a=[])
        self.fig = NS(branch_cmap_name='tab10', phase_cmap_name='tab10',
                      grid_color_pattern='branch', fig_branch_line_color=1,
                      branch_legend=0, phase_legend=0)
        self.line = NS(Single_Phase_Draw=0, line_single_side=0, linestyle='-',
                       linewidth=1, draw_arrow=1, inlet_line=1, outlet_line=1)
        self.rows = [[7, 0, 0, 1, 0, 1, 0], [0, 1, 0, 1, 1, -1, 0],
                     [2, 1, 0, 1, 2, 1, 0], [4, 2, 0, 1, 3, -1, 0]]
        self.ax = plt.subplots()[1]

    def tearDown(self):
        plt.close('all')

    def draw(self):
        return df.draw_unwrapped_winding_layout(
            self.ax, self.rows, [], self.w, self.layout, self.fig, self.line)

    def test_expected_edges_wrap_terminals_and_no_generation(self):
        original = copy.deepcopy(self.rows)
        with patch.object(df.gw, 'Winding_Phase_division', side_effect=AssertionError):
            self.draw()
        self.assertEqual(self.rows, original)
        edges = self.ax._winding_edges
        self.assertEqual([(e['start'][:2], e['end'][:2], e['side']) for e in edges],
                         [((7, 0), (0, 1), -1), ((0, 1), (2, 1), 1),
                          ((2, 1), (4, 2), -1), ((4, 2), (7, 0), 1)])
        wrapped = [line for line in self.ax.lines if line.get_gid() == 'connection-1-0']
        self.assertEqual(len(wrapped), 2)
        self.assertEqual(wrapped[0].get_xdata()[-1], 8.5)
        self.assertEqual(wrapped[1].get_xdata()[0], 0.5)
        self.assertFalse(any((t.get_gid() or '').startswith('seam-')
                             for t in self.ax.texts))
        self.assertEqual(len(self.ax._winding_terminals), 2)

    def test_side_filter_honors_inlet_adjustment(self):
        self.layout.inlet_index_adjustments_phase_a = [1]
        self.line.line_single_side = 1
        self.draw()
        self.assertEqual([e['index'] for e in self.ax._winding_edges], [0, 2])
        self.assertTrue(all(e['side'] == 1 for e in self.ax._winding_edges))

    def test_arrows_are_off_center_and_only_right_seam_has_tangent_arrow(self):
        self.draw()
        arrow = next(t for t in self.ax.texts if t.get_gid() == 'arrow-1-2')
        # Unsplit diagonal runs from (3, 2) to (5, 3).
        self.assertLess(arrow.xy[0], 3.7)
        self.assertLess(arrow.xy[1], 2.35)
        seams = [t for t in self.ax.texts if (t.get_gid() or '').startswith('boundary-arrow-')]
        self.assertEqual(len(seams), 1)
        head, tail = seams[0].xy, seams[0].get_position()
        self.assertEqual(head[0], 8.5)
        self.assertGreater(head[0], tail[0])
        self.assertAlmostEqual((head[1]-tail[1])/(head[0]-tail[0]), 1.0)

    def test_phase_and_neutral_rails_connect_actual_terminal_slots(self):
        self.w.num_phases = 2
        self.rows += [[3, 0, 1, 2, 0, 1, 0], [6, 1, 1, 2, 1, -1, 0]]
        self.draw()
        lines = {line.get_gid(): line for line in self.ax.lines if line.get_gid()}
        rails = [lines[key] for key in ('phase-rail-0', 'phase-rail-1', 'neutral-rail')]
        self.assertEqual(len({line.get_color() for line in rails}), 3)
        self.assertTrue(all(max(line.get_ydata()) < 0.5 for line in rails))
        leads = {patch.get_gid(): patch for patch in self.ax.patches if patch.get_gid()}
        for kind, branch in (('inlet', 1), ('inlet', 2), ('outlet', 1), ('outlet', 2)):
            self.assertIsInstance(leads[f'{kind}-{branch}'], FancyArrowPatch)
        self.assertIn('Phase A', [t.get_text() for t in self.ax.texts])
        self.assertIn('Phase B', [t.get_text() for t in self.ax.texts])
        self.assertIn('Neutral line', [t.get_text() for t in self.ax.texts])

    def test_inlets_use_phase_local_branch_labels_and_curved_rail_leads(self):
        self.w.ab = 2
        self.rows = [[0, 0, 0, 1, 0, 1, 0], [2, 1, 0, 1, 1, -1, 0],
                     [4, 0, 0, 2, 0, 1, 0], [6, 1, 0, 2, 1, -1, 0]]
        self.line.outlet_line = 0
        self.draw()
        texts = [text.get_text() for text in self.ax.texts]
        self.assertIn('A1', texts)
        self.assertIn('A2', texts)
        self.assertFalse(any(text.startswith(('I', 'O')) for text in texts))
        leads = [patch for patch in self.ax.patches
                 if isinstance(patch, FancyArrowPatch) and (patch.get_gid() or '').startswith('inlet-')]
        self.assertEqual(len(leads), 2)
        for lead, x in zip(sorted(leads, key=lambda patch: patch.get_gid()), (1, 5)):
            vertices = lead.get_path().vertices
            self.assertGreater(max(vertices[:, 0]) - min(vertices[:, 0]), 0.02)
            self.assertGreater(max(vertices[:, 0]), x + 0.02)
            self.assertGreaterEqual(min(vertices[:, 0]), x - 0.01)

    def test_inlet_labels_do_not_overlap_phase_title_or_each_other(self):
        self.w.num_slots = 48
        self.w.ab = 4
        self.rows = [row for branch, slot in enumerate((0, 1, 24, 25), 1)
                     for row in ([slot, 0, 0, branch, 0, 1, 0],
                                 [(slot + 6) % 48, 1, 0, branch, 1, -1, 0])]
        self.line.outlet_line = 0
        self.ax.figure.set_size_inches(8, 4)
        self.draw()
        self.ax.figure.canvas.draw()
        renderer = self.ax.figure.canvas.get_renderer()
        labels = [text for text in self.ax.texts
                  if text.get_text() in {'Phase A', 'A1', 'A2', 'A3', 'A4'}]
        for index, first in enumerate(labels):
            for second in labels[index + 1:]:
                self.assertFalse(first.get_window_extent(renderer).overlaps(
                    second.get_window_extent(renderer)),
                    f'{first.get_text()} overlaps {second.get_text()}')

    def test_same_slot_inlets_on_first_and_tail_layers_have_distinct_labels(self):
        self.w.num_slots = 48
        self.w.num_layers = 4
        self.w.ab = 4
        self.rows = [row for branch, layer in enumerate(range(4), 1)
                     for row in ([24, layer, 0, branch, 0, 1, 0],
                                 [28 + layer, (layer + 1) % 4, 0, branch, 1, -1, 0])]
        self.line.outlet_line = 0
        self.ax.figure.set_size_inches(8, 4)
        self.draw()
        self.ax.figure.canvas.draw()
        renderer = self.ax.figure.canvas.get_renderer()
        labels = [text for text in self.ax.texts
                  if text.get_text() in {'A1', 'A2', 'A3', 'A4'}]
        self.assertEqual(len(labels), 4)
        axes_top = self.ax.get_window_extent(renderer).y1
        for index, first in enumerate(labels):
            self.assertLessEqual(first.get_window_extent(renderer).y1, axes_top)
            for second in labels[index + 1:]:
                self.assertFalse(first.get_window_extent(renderer).overlaps(
                    second.get_window_extent(renderer)),
                    f'{first.get_text()} overlaps {second.get_text()}')

    def test_same_layer_and_circular_settings_do_not_change_grid(self):
        self.fig.CW = -1
        self.fig.Figure_Division = 4
        self.fig.outer_radius = 100
        self.draw()
        same = next(l for l in self.ax.lines if l.get_gid() == 'connection-1-1')
        self.assertGreater(len(same.get_xdata()), 2)
        self.assertEqual(tuple(self.ax.get_xlim()), (0.5, 8.5))
        self.assertGreater(self.ax.get_ylim()[0], self.ax.get_ylim()[1])

    def test_circular_and_unwrapped_use_same_ordered_actual_branch(self):
        self.layout.inlet_index_adjustments_phase_a = [1]
        self.draw()
        self.fig.CW = 1
        self.fig.branch_legend = 0
        self.line.outline_angle = 0
        self.line.inline_angle = 0
        self.line.inlet_line_length = 1
        with patch.object(df, 'get_slot_layer_angles_radii', return_value={}), \
                patch.object(df, 'draw_cond_id_segment') as draw_segment, \
                patch.object(df, 'draw_inlet_line'), patch.object(df, 'color_group_conductors'):
            df.draw_circular_winding_layout(self.ax, self.rows, [], self.w,
                                            self.layout, self.fig, self.line)
        circular_edges = [(call.args[1], call.args[2], call.args[4])
                          for call in draw_segment.call_args_list]
        self.assertEqual(circular_edges, [(e['start'], e['end'], e['side'])
                                         for e in self.ax._winding_edges])

    def test_reverse_wrap_and_same_layer_lanes(self):
        self.rows = [[0, 0, 0, 1, 0, 1, 0], [7, 0, 0, 1, 1, -1, 0],
                     [5, 0, 0, 1, 2, 1, 0]]
        self.layout.in_out_connection = 0
        self.draw()
        wrapped = [l for l in self.ax.lines if l.get_gid() == 'connection-1-0']
        self.assertEqual(wrapped[0].get_xdata()[-1], 0.5)
        self.assertEqual(wrapped[1].get_xdata()[0], 8.5)
        arrow = next(t for t in self.ax.texts if t.get_gid() == 'boundary-arrow-1-0')
        self.assertEqual(arrow.xy[0], 8.5)
        self.assertGreater(arrow.get_position()[0], arrow.xy[0])
        self.assertEqual(arrow.get_position()[1], arrow.xy[1])
        second = next(l for l in self.ax.lines if l.get_gid() == 'connection-1-1')
        self.assertNotEqual(wrapped[0].get_ydata()[1], second.get_ydata()[1])

    def test_nested_tail_layer_routes_put_longer_connection_outside(self):
        self.w.num_slots = 16
        self.w.ab = 2
        self.layout.in_out_connection = 0
        self.rows = [[3, 2, 0, 1, 0, 1, 0], [9, 2, 0, 1, 1, -1, 1],
                     [4, 2, 0, 2, 0, 1, 0], [8, 2, 0, 2, 1, -1, 1]]
        self.draw()
        long_route = next(line for line in self.ax.lines if line.get_gid() == 'connection-1-0')
        short_route = next(line for line in self.ax.lines if line.get_gid() == 'connection-2-0')
        # The long route encloses the short one, so the short vertical legs
        # cannot intersect the long horizontal run.
        self.assertGreater(long_route.get_ydata()[1], short_route.get_ydata()[1])

    def test_tail_same_layer_route_uses_shortest_three_segment_path(self):
        self.layout.in_out_connection = 0
        cases = (
            ((7, 0), lambda start, end: end >= start),
            ((0, 7), lambda start, end: end <= start),
        )
        for (start_slot, end_slot), follows_direction in cases:
            with self.subTest(start=start_slot, end=end_slot):
                self.ax.clear()
                self.rows = [[start_slot, 2, 0, 1, 0, 1, 0],
                             [end_slot, 2, 0, 1, 1, -1, 1]]
                self.draw()
                route = [line for line in self.ax.lines
                         if line.get_gid() == 'connection-1-0']
                self.assertEqual(len(route), 2)
                horizontal_length = 0
                has_vertical_leg = False
                for line in route:
                    xs, ys = list(line.get_xdata()), list(line.get_ydata())
                    self.assertTrue(all(follows_direction(a, b)
                                        for a, b in zip(xs, xs[1:])))
                    horizontal_length += sum(abs(b - a) for a, b in zip(xs, xs[1:])
                                             if b != a)
                    has_vertical_leg |= any(a == b and c != d
                                            for a, b, c, d in zip(xs, xs[1:], ys, ys[1:]))
                self.assertEqual(horizontal_length, 1)
                self.assertTrue(has_vertical_leg)

    def test_middle_layer_pairs_use_distinct_outward_loop_lanes(self):
        self.w.num_layers = 4
        self.w.ab = 4
        self.layout.in_out_connection = 0
        self.rows = [
            [1, 1, 0, 1, 0, 1, 0], [5, 1, 0, 1, 1, -1, 1],
            [2, 1, 0, 2, 0, 1, 0], [6, 1, 0, 2, 1, -1, 1],
            [1, 2, 0, 3, 0, 1, 0], [5, 2, 0, 3, 1, -1, 1],
            [2, 2, 0, 4, 0, 1, 0], [6, 2, 0, 4, 1, -1, 1],
        ]
        self.draw()

        layer_two = [next(line for line in self.ax.lines
                          if line.get_gid() == f'connection-{branch}-0')
                     for branch in (1, 2)]
        layer_three = [next(line for line in self.ax.lines
                            if line.get_gid() == f'connection-{branch}-0')
                       for branch in (3, 4)]
        self.assertTrue(all(line.get_ydata()[1] > 2 for line in layer_two))
        self.assertTrue(all(line.get_ydata()[1] < 3 for line in layer_three))
        self.assertEqual(len({line.get_ydata()[1] for line in layer_two}), 2)
        self.assertEqual(len({line.get_ydata()[1] for line in layer_three}), 2)

    def test_single_phase_styles_and_terminal_toggles(self):
        self.w.num_phases = 2
        self.rows += [[3, 0, 1, 2, 0, 1, 0], [6, 1, 1, 2, 1, -1, 0]]
        self.line.Single_Phase_Draw = 1
        self.line.inlet_line = self.line.outlet_line = self.line.draw_arrow = 0
        self.fig.fig_branch_line_color = 0
        self.draw()
        self.assertTrue(all(e['branch'] == 1 for e in self.ax._winding_edges))
        self.assertEqual(self.ax._winding_terminals, [])
        self.assertFalse(any((l.get_gid() or '').startswith('phase-rail-') or
                             l.get_gid() == 'neutral-rail' for l in self.ax.lines))
        weld = next(l for l in self.ax.lines if l.get_gid() == 'connection-1-0')
        insert = next(l for l in self.ax.lines if l.get_gid() == 'connection-1-1')
        self.assertEqual((weld.get_color(), weld.get_linestyle()), ('grey', '--'))
        self.assertEqual((insert.get_color(), insert.get_linestyle()), ('blue', '-'))

    def test_wrapped_connections_have_no_side_numbers(self):
        self.w.ab = 8
        self.layout.in_out_connection = 0
        self.rows = [row for branch in range(1, 9) for row in
                     ([7, 0, 0, branch, 0, 1, 0], [0, 1, 0, branch, 1, -1, 0])]
        self.draw()
        self.ax.figure.canvas.draw()
        self.assertFalse(any((t.get_gid() or '').startswith('seam-')
                             for t in self.ax.texts))
        self.assertEqual(len([t for t in self.ax.texts
                              if (t.get_gid() or '').startswith('boundary-arrow-')]), 8)

    def test_explicit_branch_overrides_single_phase_without_mutation(self):
        self.w.num_phases = 2
        self.rows += [[3, 0, 1, 2, 0, 1, 0], [6, 1, 1, 2, 1, -1, 0]]
        original = copy.deepcopy(self.rows)
        all_jobs, _ = df.prepare_branch_draw_jobs(self.rows, self.w, self.layout, self.fig, self.line)
        self.line.Single_Phase_Draw = 1
        self.fig.branch_legend = 1
        df.draw_unwrapped_winding_layout(self.ax, self.rows, [], self.w,
                                         self.layout, self.fig, self.line, branch_id=2)
        self.assertEqual({e['branch'] for e in self.ax._winding_edges}, {2})
        self.assertEqual({t['branch'] for t in self.ax._winding_terminals}, {2})
        self.assertEqual([t.get_text() for t in self.ax.get_legend().get_texts()],
                         ['Phase B', 'Branch 1'])
        self.assertFalse(any(l.get_gid() == 'phase-rail-0' for l in self.ax.lines))
        edge = next(l for l in self.ax.lines if l.get_gid() == 'connection-2-0')
        self.assertEqual(edge.get_color(), all_jobs[1][2])
        self.assertEqual(self.rows, original)
        self.assertEqual(self.line.Single_Phase_Draw, 1)

    def test_branch_legend_groups_phase_and_uses_phase_local_numbers(self):
        self.w.num_phases = 2
        self.w.ab = 2
        self.rows = [[0, 0, 0, 1, 0, 1, 0], [2, 1, 0, 1, 1, -1, 0],
                     [1, 0, 1, 2, 0, 1, 0], [3, 1, 1, 2, 1, -1, 0],
                     [4, 0, 1, 3, 0, 1, 0], [6, 1, 1, 3, 1, -1, 0],
                     [5, 0, 0, 4, 0, 1, 0], [7, 1, 0, 4, 1, -1, 0]]
        self.line.Single_Phase_Draw = 1
        self.fig.branch_legend = 1
        self.draw()
        legend = self.ax.get_legend()
        self.assertEqual([item.get_text() for item in legend.get_texts()],
                         ['Phase A', 'Branch 1', 'Branch 2'])
        self.ax.clear()
        df.draw_unwrapped_winding_layout(self.ax, self.rows, [], self.w,
                                         self.layout, self.fig, self.line, branch_id=4)
        self.assertEqual([item.get_text() for item in self.ax.get_legend().get_texts()],
                         ['Phase A', 'Branch 2'])

    def test_circular_explicit_branch_preserves_identity_and_palette(self):
        self.w.num_phases = 2
        self.rows += [[3, 0, 1, 2, 0, 1, 0], [6, 1, 1, 2, 1, -1, 0]]
        all_jobs, _ = df.prepare_branch_draw_jobs(self.rows, self.w, self.layout, self.fig, self.line)
        self.line.Single_Phase_Draw = 1
        self.fig.branch_legend = 1
        with patch.object(df, 'get_slot_layer_angles_radii', return_value={}), \
                patch.object(df, 'draw_branch_connections_with_cond_ids') as draw_branch:
            df.draw_circular_winding_layout(self.ax, self.rows, [], self.w,
                                            self.layout, self.fig, self.line, branch_id=2)
        draw_branch.assert_called_once()
        self.assertEqual(draw_branch.call_args.kwargs['branch_id'], 2)
        self.assertEqual(draw_branch.call_args.args[1], [(3, 0, 1), (6, 1, -1)])
        self.assertEqual(draw_branch.call_args.args[7], all_jobs[1][2])
        self.assertEqual([t.get_text() for t in self.ax.get_legend().get_texts()], ['Branch 2'])


if __name__ == '__main__':
    unittest.main()
