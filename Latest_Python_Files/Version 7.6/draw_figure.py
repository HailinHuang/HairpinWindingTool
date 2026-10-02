# -*- coding: utf-8 -*-
"""
Created on Fri Jun 21 20:12:40 2024

@author: ezzhh5
"""

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import Circle, Wedge, Arc, Polygon, Rectangle, FancyArrowPatch
import numpy as np
from collections import namedtuple
import get_winding_pattern as gw
import cond_info_operation as cio

def fig_value(Fig_Para, name, default):
    return getattr(Fig_Para, name, default)

def line_value(Line_Para, name, default):
    return getattr(Line_Para, name, default)

def current_radius_same_layer_arc(Layout_Para):
    pattern_name = getattr(Layout_Para, 'pattern_name', '')
    try:
        pattern_name = gw.normalize_pattern_name(pattern_name, allow_extra=False)
    except Exception:
        pattern_name = str(pattern_name).strip().upper()
    return pattern_name in ('ZPP', 'LPP')

def alternate_linestyle(linestyle):
    if linestyle == '-':
        return '--'
    if linestyle == '--':
        return '-'
    return linestyle

WELD_SIDE = -1
INSERT_SIDE = 1
SameLayerRouteLane = namedtuple('SameLayerRouteLane', ['rank', 'count'])


def same_layer_route_style(Line_Para):
    """Return the persisted Figure-tab choice, keeping older configs unchanged."""
    return getattr(Line_Para, 'same_layer_route_style', 'direct_arc')


def is_outer_or_inner_same_layer(start_conductor_id, end_conductor_id, Winding_Para):
    start_layer = start_conductor_id[1]
    return (
        start_layer == end_conductor_id[1]
        and start_layer in (0, Winding_Para.num_layers - 1)
    )


def build_same_layer_route_lanes(
        branches, Winding_Para, pole_region_by_conductor=None,
        close_loop=False, boundary_only=True):
    """Assign stable, distinct lanes within one physical pole-pair region."""
    pole_region_by_conductor = pole_region_by_conductor or {}
    grouped = {}
    for branch_id, cond_ids in branches:
        pairs = [
            (segment_index, cond_ids[segment_index], cond_ids[segment_index + 1])
            for segment_index in range(max(0, len(cond_ids) - 1))
        ]
        if close_loop and len(cond_ids) > 1:
            pairs.append((len(cond_ids) - 1, cond_ids[-1], cond_ids[0]))
        for segment_index, start, end in pairs:
            if start[1] != end[1]:
                continue
            if (boundary_only
                    and start[1] not in (0, Winding_Para.num_layers - 1)):
                continue
            start_pole = pole_region_by_conductor.get(start)
            end_pole = pole_region_by_conductor.get(end)
            physical_region = (
                tuple(sorted((start_pole, end_pole)))
                if start_pole is not None and end_pole is not None
                else tuple(sorted((start[0], end[0])))
            )
            group_key = (start[1], physical_region)
            pitch = abs(start[0] - end[0]) % Winding_Para.num_slots
            pitch = min(pitch, Winding_Para.num_slots - pitch)
            phase_belt = tuple(sorted((start[2], end[2])))
            stable_key = (pitch, *phase_belt, start[0], end[0], branch_id, segment_index)
            grouped.setdefault(group_key, []).append(
                (stable_key, (branch_id, segment_index))
            )

    lanes = {}
    for records in grouped.values():
        records.sort(key=lambda record: record[0])
        count = len(records)
        for rank, (_, token) in enumerate(records):
            lanes[token] = SameLayerRouteLane(rank, count)
    return lanes


def _unwrapped_horizontal_intervals(start_slot, end_slot, num_slots):
    """Return the visible horizontal spans of one shortest periodic route."""
    start_x = start_slot + 1
    end_x = start_x + shortest_periodic_delta(start_slot, end_slot, num_slots)
    low, high = sorted((start_x, end_x))
    left, right = 0.5, num_slots + 0.5
    intervals = []
    for shift in (-num_slots, 0, num_slots):
        visible_low = max(left, low + shift)
        visible_high = min(right, high + shift)
        if visible_high > visible_low:
            intervals.append((visible_low, visible_high))
    return tuple(intervals)


def build_unwrapped_same_layer_route_lanes(
        branches, Winding_Para, close_loop=False, boundary_only=True):
    """Assign lanes by overlap of the horizontal spans visible on the grid."""
    grouped = {}
    for branch_id, cond_ids in branches:
        pairs = [
            (segment_index, cond_ids[segment_index], cond_ids[segment_index + 1])
            for segment_index in range(max(0, len(cond_ids) - 1))
        ]
        if close_loop and len(cond_ids) > 1:
            pairs.append((len(cond_ids) - 1, cond_ids[-1], cond_ids[0]))
        for segment_index, start, end in pairs:
            if start[1] != end[1]:
                continue
            if (boundary_only
                    and start[1] not in (0, Winding_Para.num_layers - 1)):
                continue
            pitch = abs(shortest_periodic_delta(
                start[0], end[0], Winding_Para.num_slots))
            phase_belt = tuple(sorted((start[2], end[2])))
            stable_key = (pitch, *phase_belt, start[0], end[0], branch_id, segment_index)
            intervals = _unwrapped_horizontal_intervals(
                start[0], end[0], Winding_Para.num_slots)
            grouped.setdefault(start[1], []).append(
                (stable_key, (branch_id, segment_index), intervals))

    lanes = {}
    for records in grouped.values():
        occupied_by_rank = []
        assignments = []
        for _, token, intervals in sorted(records, key=lambda record: record[0]):
            rank = next((candidate for candidate, occupied in enumerate(occupied_by_rank)
                         # Touching spans share a vertical leg at the conductor,
                         # so they also need separate lanes.
                         if not any(max(a0, b0) <= min(a1, b1)
                                    for a0, a1 in intervals
                                    for b0, b1 in occupied)), None)
            if rank is None:
                rank = len(occupied_by_rank)
                occupied_by_rank.append([])
            occupied_by_rank[rank].extend(intervals)
            assignments.append((token, rank))
        count = max(1, len(occupied_by_rank))
        for token, rank in assignments:
            lanes[token] = SameLayerRouteLane(rank, count)
    return lanes


def same_layer_route_radius(layer, lane_rank, lane_count, Winding_Para, Fig_Para, radii_gap=0.20):
    """Return a first/last-layer route radius using the configured uniform gap."""
    gap = max(0.01, float(radii_gap))
    if layer == 0:
        return Fig_Para.outer_radius + gap * (lane_rank + 1)
    if layer == Winding_Para.num_layers - 1:
        return max(0.01, Fig_Para.inner_radius - gap * (lane_rank + 1))
    raise ValueError('Radial-centre routing only applies to the first and last layers.')

def initial_connection_side(Layout_Para, branch_adjustment=0):
    # When inlet_from_weld_side rotates the branch start by one conductor,
    # reverse even/odd side mapping so existing internal connection features
    # stay aligned with the original layout.
    if getattr(Layout_Para, 'inlet_from_weld_side', 0) == 1:
        side_index = INSERT_SIDE
    else:
        side_index = WELD_SIDE
    if int(branch_adjustment) % 2 != 0:
        side_index = next_connection_side(side_index)
    return side_index

def next_connection_side(side_index):
    return INSERT_SIDE if side_index == WELD_SIDE else WELD_SIDE

def linestyle_for_side(base_linestyle, side_index):
    return base_linestyle if side_index == INSERT_SIDE else alternate_linestyle(base_linestyle)

def line_color_for_side_and_pin(fig_branch_line_color, side_index, layer_shift, current_direction, next_direction, branch_color):
    if fig_branch_line_color == 1:
        return branch_color
    if side_index == WELD_SIDE:
        return 'grey'
    if abs(layer_shift) == 1:
        return 'green' if next_direction == current_direction else 'red'
    if abs(layer_shift) == 0:
        return 'blue'
    if abs(layer_shift) > 1:
        return 'purple' if next_direction == current_direction else 'deeppink'
    return 'black'

def direction_label_from_slots(start_slot, end_slot, Winding_Para):
    slot_shift = end_slot - start_slot
    wrap_threshold = Winding_Para.q * Winding_Para.num_phases * 2
    if abs(slot_shift) > wrap_threshold:
        if slot_shift > 0:
            slot_shift -= Winding_Para.num_slots
        else:
            slot_shift += Winding_Para.num_slots
    return 'F' if slot_shift > 0 else 'B'

def legend_options(Fig_Para, default_fontsize=11):
    position = fig_value(Fig_Para, 'legend_position', 'center')
    fontsize = fig_value(Fig_Para, 'legend_fontsize', default_fontsize)
    positions = {
        'center': ('center', (0.5, 0.5)),
        'upper right': ('upper right', (0.98, 0.98)),
        'lower right': ('lower right', (0.98, 0.02)),
        'right': ('center right', (0.98, 0.5)),
    }
    loc, anchor = positions.get(position, positions['center'])
    return loc, anchor, fontsize


def grid_legend_options(Fig_Para, default_fontsize=11):
    """Respect the selected legend position without covering the right grid edge."""
    position = fig_value(Fig_Para, 'legend_position', 'center')
    fontsize = fig_value(Fig_Para, 'legend_fontsize', default_fontsize)
    positions = {
        # Preserve the original data-centred placement for the centre choice.
        'center': ('center', (0.0, 0.0), 'data'),
        # Right-side choices use the dedicated margin rather than grid data.
        'upper right': ('upper left', (1.02, 1.0), 'axes'),
        'lower right': ('lower left', (1.02, 0.0), 'axes'),
        'right': ('center left', (1.02, 0.5), 'axes'),
    }
    loc, anchor, coordinate_space = positions.get(position, positions['center'])
    return loc, anchor, fontsize, coordinate_space
    
def get_slot_layer_angles_radii(Winding_Para, Fig_Para):
    slot_layer_angles_radii = {}  # 存储每个槽和每层导体的角度和半径的数组
    for slot in range(int(Winding_Para.num_slots/Fig_Para.Figure_Division)):
        angle_per_slot = 360 / Winding_Para.num_slots
        slot_layer_angles_radii[slot] = {}
        for layer in range(Winding_Para.num_layers):
            inner_rad = Fig_Para.outer_radius - (layer + 1) * Fig_Para.layer_height
            outer_rad = Fig_Para.outer_radius - (layer) * Fig_Para.layer_height
            rotation_angle = Fig_Para.rotation_angle
            if Fig_Para.CW == 1: 
                theta1 = 360 - (slot + 1) * angle_per_slot + angle_per_slot / 2 + rotation_angle
                theta2 = 360 - slot * angle_per_slot + angle_per_slot / 2 + rotation_angle
            else:
                theta1 = slot * angle_per_slot - angle_per_slot / 2 + rotation_angle
                theta2 = (slot + 1) * angle_per_slot - angle_per_slot / 2 + rotation_angle
            avg_radius = (inner_rad + outer_rad) / 2
            avg_angle = np.mod((theta1 + theta2) / 2 * np.pi / 180,2 * np.pi)
            slot_layer_angles_radii[slot][layer] = (avg_angle, avg_radius)
    return slot_layer_angles_radii

def draw_circular_winding_pattern(Winding_Para, Fig_Para):
    fig, ax = plt.subplots(figsize=(8, 8), dpi=300)
    angle_per_slot = 360 / Winding_Para.num_slots
    slot_layer_angles_radii = get_slot_layer_angles_radii(Winding_Para, Fig_Para)
    for slot in range(int(Winding_Para.num_slots/Fig_Para.Figure_Division)):
        phasor = slot % int(Winding_Para.q*Winding_Para.num_phases*2)
        for layer in range(Winding_Para.num_layers):
            color = 'none'
            inner_rad = Fig_Para.outer_radius - (layer + 1) * Fig_Para.layer_height
            outer_rad = Fig_Para.outer_radius - (layer) * Fig_Para.layer_height
            rotation_angle = Fig_Para.rotation_angle
            if Fig_Para.CW == 1: 
                theta1 = 360 - (slot + 1) * angle_per_slot + angle_per_slot / 2 + rotation_angle
                theta2 = 360 - slot * angle_per_slot + angle_per_slot / 2 + rotation_angle
            else:
                theta1 = slot * angle_per_slot - angle_per_slot / 2 + rotation_angle
                theta2 = (slot + 1) * angle_per_slot - angle_per_slot / 2 + rotation_angle
            avg_radius = (inner_rad + outer_rad) / 2
            avg_angle = np.mod((theta1 + theta2) / 2 * np.pi / 180,2 * np.pi)
            wedge = Wedge((0, 0), outer_rad, theta1, theta2, width=Fig_Para.layer_height, facecolor=color, edgecolor='black', linewidth=0.5)
            ax.add_patch(wedge)
            circle_radius = min(Fig_Para.inner_layer_width,Fig_Para.layer_height)/3  # 设置圆形的半径
            circle_linewidth = Fig_Para.inner_layer_width*3  # 设置圆形的线粗
            # 在扇形绘制循环内部添加 Circle 图形
            if fig_value(Fig_Para, 'wedge_circle', 1) == 1:
                circle_center_x = avg_radius * np.cos(avg_angle)
                circle_center_y = avg_radius * np.sin(avg_angle)
                circle = Circle((circle_center_x, circle_center_y), circle_radius, facecolor='none', edgecolor='black', linewidth=circle_linewidth, zorder=2)
                ax.add_patch(circle)
        if slot % 1 == 0:
            index_rotation = 0 if Fig_Para.slotindex_rotation == 0 else theta1 + (theta2 - theta1) / 2 - 90
            text_offset = Fig_Para.slotindex_offset  # 调整此值以更改槽号标签离内圆的距离
            ax.text((Fig_Para.outer_radius - text_offset) * np.cos((theta1 + theta2) / 2 * np.pi / 180),
                    (Fig_Para.outer_radius - text_offset) * np.sin((theta1 + theta2) / 2 * np.pi / 180),
                    f'{slot+1}', ha='center', va='center', fontsize=Fig_Para.slotindex_fontsize,
                    rotation=index_rotation, rotation_mode='anchor')
            
            # ax.text((inner_rad - 0.2) * np.cos((theta1 + theta2) / 2 * np.pi / 180),
            #         (inner_rad - 0.2) * np.sin((theta1 + theta2) / 2 * np.pi / 180),
            #         f'{phasor+1}', ha='center', va='center', fontsize=Fig_Para.slotindex_fontsize-4,
            #         rotation=index_rotation, rotation_mode='anchor')
    
    # 设置坐标轴范围和隐藏边框
    sub_margin = fig_value(Fig_Para, 'plot_margin', 0.2)
    ax.set_xlim(-Fig_Para.outer_radius-sub_margin, Fig_Para.outer_radius+sub_margin, auto=True)
    ax.set_ylim(-Fig_Para.outer_radius-sub_margin, Fig_Para.outer_radius+sub_margin, auto=True)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.spines['left'].set_visible(False)
    # Keep circles round by expanding limits, not by boxing the axes into a square.
    ax.set_aspect('equal', adjustable='datalim')
    ax.axis('off')  # 隐藏坐标轴
    return ax,slot_layer_angles_radii

def draw_circular_winding_pattern_ax(Winding_Para, Fig_Para, ax):
    """
    Draws a circular winding pattern on the provided Matplotlib axis.
    """
    ax.clear()  # Clear previous drawings
    angle_per_slot = 360 / Winding_Para.num_slots
    slot_layer_angles_radii = get_slot_layer_angles_radii(Winding_Para, Fig_Para)

    for slot in range(int(Winding_Para.num_slots / Fig_Para.Figure_Division)):

        for layer in range(Winding_Para.num_layers):
            color = 'none'
            inner_rad = Fig_Para.outer_radius - (layer + 1) * Fig_Para.layer_height
            outer_rad = Fig_Para.outer_radius - (layer) * Fig_Para.layer_height
            rotation_angle = Fig_Para.rotation_angle

            if Fig_Para.CW == 1: 
                theta1 = 360 - (slot + 1) * angle_per_slot + angle_per_slot / 2 + rotation_angle
                theta2 = 360 - slot * angle_per_slot + angle_per_slot / 2 + rotation_angle
            else:
                theta1 = slot * angle_per_slot - angle_per_slot / 2 + rotation_angle
                theta2 = (slot + 1) * angle_per_slot - angle_per_slot / 2 + rotation_angle

            avg_radius = (inner_rad + outer_rad) / 2
            avg_angle = np.mod((theta1 + theta2) / 2 * np.pi / 180, 2 * np.pi)

            # Draw wedges
            wedge = Wedge(
                (0, 0), outer_rad, theta1, theta2, width=Fig_Para.layer_height, 
                facecolor=color, edgecolor='black', linewidth=0.5
            )
            ax.add_patch(wedge)

            # Draw small circles inside the slots
            if fig_value(Fig_Para, 'wedge_circle', 1) == 1:
                circle_radius = Fig_Para.inner_layer_width / 4
                circle_linewidth = Fig_Para.inner_layer_width * 3
                circle_center_x = avg_radius * np.cos(avg_angle)
                circle_center_y = avg_radius * np.sin(avg_angle)
                circle = Circle(
                    (circle_center_x, circle_center_y), circle_radius,
                    facecolor='none', edgecolor='black', linewidth=circle_linewidth, zorder=2
                )
                ax.add_patch(circle)

        if slot % 1 == 0:
            index_rotation = 0 if Fig_Para.slotindex_rotation == 0 else theta1 + (theta2 - theta1) / 2 - 90
            text_offset = Fig_Para.slotindex_offset  

            ax.text(
                (Fig_Para.outer_radius - text_offset) * np.cos((theta1 + theta2) / 2 * np.pi / 180),
                (Fig_Para.outer_radius - text_offset) * np.sin((theta1 + theta2) / 2 * np.pi / 180),
                f'{slot+1}', ha='center', va='center', fontsize=Fig_Para.slotindex_fontsize,
                rotation=index_rotation, rotation_mode='anchor'
            )

    # Set limits and hide axes
    sub_margin = fig_value(Fig_Para, 'plot_margin', 0.2)
    ax.set_xlim(-Fig_Para.outer_radius - sub_margin, Fig_Para.outer_radius + sub_margin, auto=True)
    ax.set_ylim(-Fig_Para.outer_radius - sub_margin, Fig_Para.outer_radius + sub_margin, auto=True)
    # Keep circles round by expanding limits, not by boxing the axes into a square.
    ax.set_aspect('equal', adjustable='datalim')
    ax.axis('off')  # Hide coordinate axes

    return slot_layer_angles_radii


def get_colormap_hex_codes(cmap_name, num_branch, n):
    """Generate a list of hex color codes from a colormap."""
    cmap = plt.get_cmap(cmap_name)
    values = [(i/n)/num_branch for i in range(num_branch)]
    rgba_colors = cmap(values) 
    hex_codes = [mcolors.to_hex(color) for color in rgba_colors]
    return hex_codes

def color_slot_layer(ax, slot, layer, color, Fig_Para, Winding_Para, slot_layer_angles_radii, alpha=0.5):
    rotation_angle = Fig_Para.rotation_angle
    num_slots = Winding_Para.num_slots
    CW = Fig_Para.CW
    layer_height = Fig_Para.layer_height
    outer_radius = Fig_Para.outer_radius
    # num_slots = Winding_Para.num_slots
    angle, avg_radius = slot_layer_angles_radii[slot][layer]
    outer_rad = outer_radius - (layer) * layer_height
    #rotation_angle = 0  # 顺时针旋转角度，单位：度
    angle_per_slot = 360 / num_slots
    if CW == 1:
        theta1 = 360 - (slot + 1) * angle_per_slot + angle_per_slot / 2 + rotation_angle
        theta2 = 360 - slot * angle_per_slot + angle_per_slot / 2 + rotation_angle
    else:
        theta1 = slot * angle_per_slot - angle_per_slot / 2 + rotation_angle
        theta2 = (slot + 1) * angle_per_slot - angle_per_slot / 2 + rotation_angle
        
   # Remove existing wedges within the same slot area
    for artist in ax.artists[:]:
        if isinstance(artist, Wedge):
            if artist.theta1 == theta1 and artist.theta2 == theta2 and artist.r == outer_rad and artist.width == layer_height:
                artist.remove()    
    wedge = Wedge((0, 0), outer_rad, theta1, theta2, width=layer_height, facecolor=color, edgecolor='black', linewidth=1, alpha=alpha)

    wedge.set_zorder(1)
    # 添加 wedge 到第一层
    ax.add_artist(wedge)
    
def color_group_conductors(ax, group_conductors_id, color, Fig_Para, Winding_Para, slot_layer_angles_radii, alpha=0.5):
    processed_combinations = set()  # 用于存储已处理过的slot和layer组合的集合
    for conductor_id in group_conductors_id:
        slot, layer = conductor_id[:2]
        current_combination = (slot, layer)  # 当前slot和layer组合
        # 检查当前组合是否已经出现过
        if current_combination not in processed_combinations:
            color_slot_layer(ax, slot, layer, color, Fig_Para, Winding_Para, slot_layer_angles_radii, alpha=alpha)
            processed_combinations.add(current_combination) 
            
# Main functionalities in Python  B. Draw lines
def circle_center(a, b, c):
    ab_slope = (b[1] - a[1]) / (b[0] - a[0])
    bc_slope = (c[1] - b[1]) / (c[0] - b[0])
    ab_perp_slope = -1 / ab_slope
    bc_perp_slope = -1 / bc_slope
    ab_midpoint = (a + b) / 2
    bc_midpoint = (b + c) / 2
    center_x = (ab_perp_slope * ab_midpoint[0] - bc_perp_slope * bc_midpoint[0] + bc_midpoint[1] - ab_midpoint[1]) / (ab_perp_slope - bc_perp_slope)
    center_y = ab_perp_slope * (center_x - ab_midpoint[0]) + ab_midpoint[1]
    return np.array([center_x, center_y])

def draw_triangle(ax, center, angle, size=1, color='black', fill=True):
    """
    在指定中心点和角度绘制一个小三角形。
    
    参数：
        ax: Matplotlib的axes对象
        center: 三角形中心点的坐标 (x, y)
        angle: 三角形指向的角度 (单位：弧度)
        size: 三角形的大小，可根据需要进行缩放
        color: 三角形的颜色
        fill: 是否填充三角形
    """
    # 计算三角形的顶点坐标
    vertex1 = np.array([center[0] + size * np.cos(angle), center[1] + size * np.sin(angle)])
    vertex2 = np.array([center[0] + size * np.cos(angle + 2 * np.pi / 3), center[1] + size * np.sin(angle + 2 * np.pi / 3)])
    vertex3 = np.array([center[0] + size * np.cos(angle - 2 * np.pi / 3), center[1] + size * np.sin(angle - 2 * np.pi / 3)])
    triangle_vertices = [vertex1, vertex2, vertex3]
    # 创建并添加三角形
    triangle = Polygon(triangle_vertices, color=color, fill=fill)
    ax.add_patch(triangle)

def draw_inlet_line(ax, start_conductor_id, line_length, line_angle, slot_layer_angles_radii, color='black', linewidth=2, alpha=1.0):
    start_slot, start_layer, _ = start_conductor_id
    start_angle, start_radius = slot_layer_angles_radii[start_slot][start_layer]

    # 计算圆心坐标
    center_x = start_radius * np.cos(start_angle)
    center_y = start_radius * np.sin(start_angle)

    # 计算直线段的终点坐标
    end_angle = start_angle + np.deg2rad(line_angle)
    end_x = center_x + line_length * np.cos(end_angle)
    end_y = center_y + line_length * np.sin(end_angle)

    # 画直线段
    ax.plot([center_x, end_x], [center_y, end_y], color=color, linewidth=linewidth, alpha=alpha)


def draw_radial_center_arc_connection(
    ax, start_angle, start_radius, end_angle, end_radius, route_radius,
    color, linestyle, linewidth, draw_arrow, arrow_size, line_alpha,
):
    """Draw radial legs joined by a centre-origin circular arc."""
    start = np.array([start_radius * np.cos(start_angle), start_radius * np.sin(start_angle)])
    end = np.array([end_radius * np.cos(end_angle), end_radius * np.sin(end_angle)])
    route_start = np.array([route_radius * np.cos(start_angle), route_radius * np.sin(start_angle)])
    route_end = np.array([route_radius * np.cos(end_angle), route_radius * np.sin(end_angle)])

    for segment_start, segment_end in ((start, route_start), (route_end, end)):
        ax.plot(
            [segment_start[0], segment_end[0]],
            [segment_start[1], segment_end[1]],
            color=color,
            linestyle=linestyle,
            linewidth=linewidth,
            alpha=line_alpha,
        )

    start_deg = (np.degrees(start_angle) + 360.0) % 360.0
    end_deg = (np.degrees(end_angle) + 360.0) % 360.0
    ccw = (end_deg - start_deg) % 360.0
    theta1, theta2 = (start_deg, start_deg + ccw) if ccw <= 180.0 else (end_deg, end_deg + 360.0 - ccw)
    ax.add_patch(Arc(
        (0.0, 0.0), 2 * route_radius, 2 * route_radius,
        angle=0, theta1=theta1, theta2=theta2,
        color=color, linestyle=linestyle, linewidth=linewidth, alpha=line_alpha,
    ))

    axis_radius = route_radius + max(0.25, 0.30 * linewidth)
    current_limit = max(abs(value) for value in (*ax.get_xlim(), *ax.get_ylim()))
    if axis_radius > current_limit:
        ax.set_xlim(-axis_radius, axis_radius)
        ax.set_ylim(-axis_radius, axis_radius)

    if draw_arrow:
        direction = end - route_end
        direction /= np.linalg.norm(direction)
        normal = np.array([-direction[1], direction[0]])
        arrow_size = max(0.2, float(arrow_size))
        base, height = 0.08 * arrow_size, 0.20 * arrow_size
        base_center = end - height * direction
        points = np.array([end, base_center + base * normal, base_center - base * normal])
        ax.add_patch(Polygon(points, closed=True, color=color, alpha=line_alpha))
    
def draw_connection(
    ax, start_slot, start_layer, end_slot, end_layer,
    slot_layer_angles_radii, Winding_Para,
    color='black', linestyle='-', linewidth=1,
    CW=1, direction='F', draw_arrow=1,
    avoid_overlap=True, lane_idx=None, num_lanes=2,
    # Treat bulges as desired *radial* offsets at the arc crest (not control radius)
    outer_bulge=1.2, inner_bulge=0.6, mid_bulge=0.6,
    lane_spacing=0.30,                 # lane separation added as extra *radial* offset
    angular_nudge_deg=0.0,             # only for cross-layer arcs
    # Pitch scaling (short < integer < long)
    k_pitch_rel_outer=3,  outer_scale_min=0.30, outer_scale_max=1.00,
    k_pitch_rel_inner=0.6,  inner_scale_min=0.50, inner_scale_max=1.30,
    # Numerical guard: prevents huge sag when chord normal nearly tangential to radial
    cos_floor=0.35,
    arrow_size=1.0, line_alpha=1.0,
    force_same_layer_current_radius=False,
    Fig_Para=None, same_layer_route_style='direct_arc', route_lane=None, radii_gap=0.20,
):
    import numpy as np
    from matplotlib.patches import Arc, Polygon

    def _norm_deg(x): return (x + 360.0) % 360.0
    def _minor_deg(a, b):
        d = abs((b - a) % (2*np.pi))
        if d > np.pi: d = 2*np.pi - d
        return np.degrees(d)

    # ---------- polar coords ----------
    start_ang, start_r = slot_layer_angles_radii[start_slot][start_layer]
    end_ang,   end_r   = slot_layer_angles_radii[end_slot][end_layer]

    # unwrap across 0/360 (e.g., 43→1)
    s_eff, e_eff = start_slot, end_slot
    if abs(end_slot - start_slot) > Winding_Para.num_slots / 2:
        if start_slot < end_slot:
            s_eff += Winding_Para.num_slots; start_ang += 2*np.pi
        else:
            e_eff += Winding_Para.num_slots; end_ang   += 2*np.pi

    # stable lane
    if avoid_overlap:
        if lane_idx is None:
            lane_idx = (s_eff + e_eff + start_layer) % num_lanes
        lane_centered = lane_idx - (num_lanes - 1)/2.0
    else:
        lane_centered = 0.0

    # endpoints & chord
    s = np.array([start_r*np.cos(start_ang), start_r*np.sin(start_ang)])
    e = np.array([end_r*np.cos(end_ang),     end_r*np.sin(end_ang)])
    v = e - s; d = np.linalg.norm(v)
    if d < 1e-9: return
    t = v / d
    n = np.array([-t[1], t[0]])                   # chord left-normal (CCW)
    mid = 0.5*(s + e)

    # outward radial direction at chord midpoint; ensure n points outward
    rhat = mid / (np.linalg.norm(mid) + 1e-12)
    if np.dot(n, rhat) < 0: n = -n

    # sweep vs integer pitch (mechanical degrees)
    sep_deg = _minor_deg(start_ang, end_ang)
    int_deg = 360.0 / Winding_Para.num_poles
    rel = sep_deg / max(int_deg, 1e-9)            # <1 short, =1 integer, >1 long

    same_layer_arrow_ccw = None

    if (
        same_layer_route_style == 'radial_center_arc'
        and Fig_Para is not None
        and start_layer == end_layer
        and start_layer in (0, Winding_Para.num_layers - 1)
    ):
        route_lane = route_lane or SameLayerRouteLane(0, 1)
        route_radius = same_layer_route_radius(
            start_layer,
            route_lane.rank,
            route_lane.count,
            Winding_Para,
            Fig_Para,
            radii_gap,
        )
        draw_radial_center_arc_connection(
            ax,
            start_ang,
            start_r,
            end_ang,
            end_r,
            route_radius,
            color,
            linestyle,
            linewidth,
            draw_arrow,
            arrow_size,
            line_alpha,
        )
        return

    # ---------------- SAME-LAYER: sagitta from *radial* targets ----------------
    if start_layer == end_layer:
        # decide bulge direction and pitch-aware radial target
        if start_layer == 0:
            sign = +1.0  # outward
            scale = np.clip(1.0 + k_pitch_rel_outer*(rel - 1.0),
                            outer_scale_min, outer_scale_max)
            target_radial = outer_bulge * float(scale)
        elif start_layer == Winding_Para.num_layers - 1:
            sign = -1.0  # inward
            # NEW: inner layer also pitch-aware (short<int<long)
            scale = np.clip(1.0 + k_pitch_rel_inner*(rel - 1.0),
                            inner_scale_min, inner_scale_max)
            target_radial = inner_bulge * float(scale)
        else:
            mid_idx = (Winding_Para.num_layers - 1) / 2.0
            sign = +1.0 if start_layer <= mid_idx else -1.0
            target_radial = mid_bulge

        # lane separation added as *radial* offset (doesn't distort pitch scaling)
        target_radial += lane_centered * lane_spacing

        # convert desired RADIAL crest offset to sagitta along n:
        # radial_offset = sag * cosφ  →  sag = target_radial / cosφ
        cos_phi = max(cos_floor, float(np.dot(n, rhat)))
        sag = max(1e-6, target_radial / cos_phi)

        # sagitta geometry → circle center on the OPPOSITE side of the bulge
        a = d / 2.0
        R = (a*a + sag*sag) / (2.0*sag)
        c = R - sag
        center = mid - sign * c * n
        radius = R
        if force_same_layer_current_radius:
            center = np.array([0.0, 0.0])
            radius = 0.5 * (start_r + end_r)

        # Arc angles (Arc draws CCW theta1→theta2)
        A = _norm_deg(np.degrees(np.arctan2(s[1]-center[1], s[0]-center[0])))
        B = _norm_deg(np.degrees(np.arctan2(e[1]-center[1], e[0]-center[0])))
        ccw = (B - A) % 360.0
        same_layer_arrow_ccw = ccw <= 180.0
        if ccw <= 180.0:
            theta1, theta2 = A, A + ccw
            arc_start_deg, arc_end_deg = theta1, theta2
        else:
            theta1, theta2 = B, B + (360.0 - ccw)
            arc_start_deg, arc_end_deg = theta1, theta2

    # ---------------- CROSS-LAYER: mild 3-point arc -------------------
    else:
        control_r  = 0.5*(start_r + end_r)
        control_ang = 0.5*(start_ang + end_ang) + np.deg2rad(lane_centered*angular_nudge_deg)
        control = np.array([control_r*np.cos(control_ang), control_r*np.sin(control_ang)])
        center = circle_center(s, control, e)
        radius = np.linalg.norm(center - s)
        A = _norm_deg(np.degrees(np.arctan2(s[1]-center[1], s[0]-center[0])))
        B = _norm_deg(np.degrees(np.arctan2(e[1]-center[1], e[0]-center[0])))
        ccw = (B - A) % 360.0
        if ccw <= 180.0:
            theta1, theta2 = A, A + ccw
            arc_start_deg, arc_end_deg = theta1, theta2
        else:
            theta1, theta2 = B, B + (360.0 - ccw)
            arc_start_deg, arc_end_deg = theta1, theta2

    # ---------------- draw & arrow ----------------
    ax.add_patch(Arc(center, 2*radius, 2*radius, angle=0,
                     theta1=theta1, theta2=theta2,
                     color=color, linestyle=linestyle, linewidth=linewidth, alpha=line_alpha))

    want_cw = (CW == 1 and direction == 'F') or (CW == 0 and direction == 'B')
    if draw_arrow:
        edge = 2.5
        if start_layer == end_layer:
            # Same-layer arcs are sometimes drawn with theta1/theta2 reversed
            # to keep the visible arc short. Anchor the arrow to the actual
            # end conductor angle instead of the rendered Arc endpoint.
            if same_layer_arrow_ccw:
                phi = B - edge; head = phi + 90.0
            else:
                phi = B + edge; head = phi - 90.0
        elif not want_cw:  # CCW
            phi = arc_end_deg - edge; head = phi + 90.0
        else:            # CW
            phi = arc_start_deg + edge; head = phi - 90.0
        pr, hr = np.deg2rad(phi), np.deg2rad(head)
        x = center[0] + radius*np.cos(pr); y = center[1] + radius*np.sin(pr)
        arrow_size = max(0.2, float(arrow_size))
        base, h = 0.08 * arrow_size, 0.20 * arrow_size
        pts = np.array([
            [x + h*np.cos(hr),              y + h*np.sin(hr)],
            [x + base*np.cos(hr + np.pi/2), y + base*np.sin(hr + np.pi/2)],
            [x + base*np.cos(hr - np.pi/2), y + base*np.sin(hr - np.pi/2)],
        ])
        ax.add_patch(Polygon(pts, closed=True, color=color, alpha=line_alpha))



def draw_seq_connection(ax, start_conductor_id, num_cond, Winding_Para, Layout_Para, Fig_Para, Line_Para, direction, ltp, ptp, slot_layer_angles_radii, side_index, color='black'):
    # 调用 get_seq_connection 函数来获取 start_conductor_id 和 group_conductors_id
    CW = Fig_Para.CW
    single_side = Line_Para.line_single_side
    linewidth = Line_Para.linewidth
    draw_arrow = Line_Para.draw_arrow
    linestyle = Line_Para.linestyle
    arrow_size = line_value(Line_Para, 'arrow_size', 1.0)
    line_alpha = line_value(Line_Para, 'line_alpha', 1.0)
    same_layer_current_radius = current_radius_same_layer_arc(Layout_Para)
    start_conductor_id, group_conductors_id = gw.get_seq_connection(start_conductor_id, num_cond, Winding_Para, Layout_Para, direction, ltp, ptp, CW=CW)
    for i in range(len(group_conductors_id) - 1):
        start_slot, start_layer, start_phasor = group_conductors_id[i]
        end_slot, end_layer, end_phasor = group_conductors_id[i+1]
        if (single_side == 0) or (single_side == side_index):
            current_linestyle = linestyle_for_side(linestyle, side_index)
            draw_connection(ax, start_slot, start_layer, end_slot, end_layer, slot_layer_angles_radii, Winding_Para, color, current_linestyle, linewidth,CW,direction,draw_arrow, arrow_size=arrow_size, line_alpha=line_alpha, force_same_layer_current_radius=same_layer_current_radius)
        start_conductor_id = (end_slot, end_layer, end_phasor)
    return start_conductor_id,group_conductors_id

def draw_branch_connections(ax, start_conductor_id, Connection, slot_layer_angles_radii, Fig_Para, Winding_Para, Layout_Para, Line_Para, color, branch_adjustment=0):
    connections_df = gw.get_cond_info_df(Connection)
    outline_angle = Line_Para.outline_angle
    fig_branch_line_color = Fig_Para.fig_branch_line_color
    branch_color = color
    group_conductors_id = []
    if Line_Para.inlet_line == 1:
        if fig_branch_line_color == 0:
            inlet_line_color = 'red'
        else:
            inlet_line_color = branch_color
        draw_inlet_line(ax, start_conductor_id, Line_Para.inlet_line_length, Line_Para.inline_angle, slot_layer_angles_radii, color=inlet_line_color, linewidth=Line_Para.linewidth*2, alpha=line_value(Line_Para, 'line_alpha', 1.0))
    side_index = initial_connection_side(Layout_Para, branch_adjustment)
        
    for index, row in connections_df.iterrows():
        num_cond = row['num_cond']
        direction = row['direction']
        ltp = row['ltp']
        ptp = row['ptp']
        if ltp == 'jumper' or isinstance(ltp, int) == True:
            color = 'green'
        elif ltp == 'parallel':
            color = 'red'
        elif ltp == 'wave' and ptp != 'none' and index % 2==0:
            color = 'blue'
        else:
            color = 'black'
        if fig_branch_line_color == 1:
            color = branch_color
        start_conductor_id,sub_group_conductors_id = draw_seq_connection(ax, start_conductor_id, num_cond, Winding_Para, Layout_Para, Fig_Para, Line_Para, direction, ltp, ptp, slot_layer_angles_radii,side_index,color)
        group_conductors_id.extend(sub_group_conductors_id[:-1])
        side_index = next_connection_side(side_index)
    group_conductors_id.append(start_conductor_id)

    if getattr(Layout_Para, 'in_out_connection', 0) == 1 and len(group_conductors_id) > 1:
        draw_cond_id_segment(
            ax,
            group_conductors_id[-1],
            group_conductors_id[0],
            group_conductors_id[1] if len(group_conductors_id) > 2 else None,
            side_index,
            slot_layer_angles_radii,
            Fig_Para,
            Winding_Para,
            Line_Para,
            branch_color,
            current_radius_same_layer_arc(Layout_Para),
        )
    
    if Line_Para.outlet_line == 1:
        slot,layer,phasor = start_conductor_id
        if layer == Winding_Para.num_layers - 1:
            outline_angle = 180
        if fig_branch_line_color == 0:
            color = 'black'
        else:
            color = branch_color
        draw_inlet_line(ax, start_conductor_id, Line_Para.inlet_line_length, outline_angle, slot_layer_angles_radii, color, linewidth=Line_Para.linewidth*2, alpha=line_value(Line_Para, 'line_alpha', 1.0))   
    if Fig_Para.grid_color_pattern == 'branch':
        color_group_conductors(ax, group_conductors_id, color, Fig_Para, Winding_Para, slot_layer_angles_radii, alpha=0.5)
    return start_conductor_id,group_conductors_id


def get_conn_direction(start_slot,end_slot,num_slots):
    diff = (end_slot - start_slot) % num_slots

    if diff == 0:
        current_direction = 0
    elif diff <= num_slots/2:
        current_direction = +1
    else:
        current_direction = -1
    
    return current_direction


def shortest_periodic_delta(start_slot, end_slot, num_slots):
    """Return the signed shortest slot delta, preferring rightward on a tie."""
    right_delta = (end_slot - start_slot) % num_slots
    left_delta = right_delta - num_slots
    return right_delta if right_delta <= abs(left_delta) else left_delta


def build_unwrapped_same_layer_path(start, end, num_slots, lane):
    """Build one periodic 90-degree same-layer route using the shortest span."""
    delta = shortest_periodic_delta(start[0], end[0], num_slots)
    end_x = start[0] + delta
    return [start, (start[0], lane), (end_x, lane), (end_x, end[1])]


def unwrapped_path_arrow_segment(pieces, start_fraction=0.60, end_fraction=0.82):
    """Return a local arrow segment on the longest visible path section."""
    segments = [(a, b) for piece in pieces for a, b in zip(piece, piece[1:])]
    a, b = max(segments, key=lambda pair: np.hypot(
        pair[1][0] - pair[0][0], pair[1][1] - pair[0][1]))
    point = lambda fraction: (
        a[0] + fraction * (b[0] - a[0]),
        a[1] + fraction * (b[1] - a[1]))
    return point(start_fraction), point(end_fraction)


def unwrapped_same_layer_lane_offset(lane_rank, lane_count):
    """Return a compact lane offset that stays clear of conductor indices."""
    count = max(1, int(lane_count))
    rank = min(max(0, int(lane_rank)), count - 1)
    return 0.08 + 0.16 * (rank + 1) / (count + 1)


def unwrapped_same_layer_lane_sign(layer, num_layers):
    """Route each layer-pair outward to form a complete loop profile."""
    if layer == 0:
        return -1
    if layer == num_layers - 1:
        return 1
    return -1 if layer % 2 == 0 else 1


def draw_cond_id_segment(
    ax,
    start_conductor_id,
    end_conductor_id,
    next_conductor_id,
    side_index,
    slot_layer_angles_radii,
    Fig_Para,
    Winding_Para,
    Line_Para,
    branch_color,
    same_layer_current_radius,
    branch_id,
    segment_index,
    same_layer_route_lanes,
):
    start_slot, start_layer, _ = start_conductor_id
    end_slot, end_layer, _ = end_conductor_id
    next_slot = next_conductor_id[0] if next_conductor_id is not None else None

    current_direction = get_conn_direction(start_slot, end_slot, Winding_Para.num_slots)
    next_direction = get_conn_direction(end_slot, next_slot, Winding_Para.num_slots) if next_slot is not None else current_direction
    layer_shift = end_layer - start_layer
    color = line_color_for_side_and_pin(
        Fig_Para.fig_branch_line_color,
        side_index,
        layer_shift,
        current_direction,
        next_direction,
        branch_color,
    )
    direction = direction_label_from_slots(start_slot, end_slot, Winding_Para)
    linestyle = linestyle_for_side(Line_Para.linestyle, side_index)

    if (Line_Para.line_single_side == 0) or (Line_Para.line_single_side == side_index):
        route_lane = same_layer_route_lanes.get((branch_id, segment_index))
        draw_connection(
            ax,
            start_slot,
            start_layer,
            end_slot,
            end_layer,
            slot_layer_angles_radii,
            Winding_Para,
            color=color,
            linestyle=linestyle,
            linewidth=Line_Para.linewidth,
            CW=Fig_Para.CW,
            direction=direction,
            draw_arrow=Line_Para.draw_arrow,
            arrow_size=line_value(Line_Para, 'arrow_size', 1.0),
            line_alpha=line_value(Line_Para, 'line_alpha', 1.0),
            force_same_layer_current_radius=same_layer_current_radius,
            Fig_Para=Fig_Para,
            same_layer_route_style=same_layer_route_style(Line_Para),
            route_lane=route_lane,
            radii_gap=line_value(Line_Para, 'radii_gap', 0.20),
        )


def draw_branch_connections_with_cond_ids(
    ax, cond_ids, slot_layer_angles_radii, Fig_Para, Winding_Para, Layout_Para,
    Line_Para, color, branch_adjustment=0, branch_id=None, same_layer_route_lanes=None,
):
    start_conductor_id = cond_ids[0]
    outline_angle = Line_Para.outline_angle
    fig_branch_line_color = Fig_Para.fig_branch_line_color
    branch_color = color
    group_conductors_id = cond_ids
    line_alpha = line_value(Line_Para, 'line_alpha', 1.0)
    same_layer_current_radius = current_radius_same_layer_arc(Layout_Para)
    branch_id = branch_id if branch_id is not None else -1
    same_layer_route_lanes = same_layer_route_lanes or {}
    if Line_Para.inlet_line == 1:
        if fig_branch_line_color == 0:
            inlet_line_color = 'black'
        else:
            inlet_line_color = branch_color
        draw_inlet_line(ax, start_conductor_id, Line_Para.inlet_line_length, Line_Para.inline_angle, slot_layer_angles_radii, color=inlet_line_color, linewidth=Line_Para.linewidth*2, alpha=line_alpha)
        
    side_index = initial_connection_side(Layout_Para, branch_adjustment)
    for i in range(1,len(cond_ids)):
        draw_cond_id_segment(
            ax,
            cond_ids[i - 1],
            cond_ids[i],
            cond_ids[i + 1] if i + 1 < len(cond_ids) else None,
            side_index,
            slot_layer_angles_radii,
            Fig_Para,
            Winding_Para,
            Line_Para,
            branch_color,
            same_layer_current_radius,
            branch_id,
            i - 1,
            same_layer_route_lanes,
        )
        side_index = next_connection_side(side_index)

    if getattr(Layout_Para, 'in_out_connection', 0) == 1 and len(cond_ids) > 1:
        draw_cond_id_segment(
            ax,
            cond_ids[-1],
            cond_ids[0],
            cond_ids[1] if len(cond_ids) > 2 else None,
            side_index,
            slot_layer_angles_radii,
            Fig_Para,
            Winding_Para,
            Line_Para,
            branch_color,
            same_layer_current_radius,
            branch_id,
            len(cond_ids) - 1,
            same_layer_route_lanes,
        )
        
    if Line_Para.outlet_line == 1:
        end_conductor_id = cond_ids[-1]
        slot,layer,phasor = end_conductor_id
        if layer == Winding_Para.num_layers - 1:
            outline_angle = 180
        if fig_branch_line_color == 0:
            color = 'black'
        else:
            color = branch_color
        draw_inlet_line(ax, end_conductor_id, Line_Para.inlet_line_length, outline_angle, slot_layer_angles_radii, color, linewidth=Line_Para.linewidth*2, alpha=line_alpha)   
        
    if Fig_Para.grid_color_pattern == 'branch':
        color = branch_color  
        color_group_conductors(ax, group_conductors_id, color, Fig_Para, Winding_Para, slot_layer_angles_radii, alpha=fig_value(Fig_Para, 'grid_alpha', 0.3))
    

def color_phases(cond_info,Winding_Para,Fig_Para,phase_colors,slot_layer_angles_radii, ax):
    if Fig_Para.grid_color_pattern == 'phase':
        # ===== Build legend handles and labels =====
        phase_names = [f"Phase {chr(ord('A') + i)}" for i in range(Winding_Para.num_phases)]
        handles = [
            Rectangle((0, 0), 1, 1, facecolor=color, edgecolor='black', linewidth=1)
            for color in phase_colors
        ]

        #legend_height = len(phase_colors) * legend_spacing
        if Fig_Para.phase_legend == 1:
            legend_loc, legend_anchor, legend_fontsize, coordinate_space = grid_legend_options(Fig_Para, 10)
            legend = ax.legend(
                handles,
                phase_names,
                loc=legend_loc,
                bbox_to_anchor=legend_anchor,
                bbox_transform=ax.transData if coordinate_space == 'data' else ax.transAxes,
                frameon=True,
                fontsize=legend_fontsize,
                handlelength=1.5,
                labelspacing=0.8,
                borderpad=0.5,
                handletextpad=0.5
            )
            # ===== Beautify legend frame with rounded corners =====
            frame = legend.get_frame()
            frame.set_facecolor('white')
            frame.set_edgecolor('black')
            frame.set_linewidth(1.2)
            frame.set_alpha(0.9)
            # Rounded corners
            frame.set_boxstyle("round,pad=0.5,rounding_size=0.3")  # tweak rounding_size as needed
            
        for i in range(len(cond_info)):
            slot = cond_info[i][0]
            layer = cond_info[i][1]
            phase_index = cond_info[i][2]
            pole_index = cond_info[i][6]
            base_color = phase_colors[phase_index]
            color = (float(base_color[0]), float(base_color[1]), float(base_color[2]))
            if slot < Winding_Para.num_slots/Fig_Para.Figure_Division:
                if pole_index % 2 == 0:
                    color_slot_layer(ax, slot, layer, color, Fig_Para, Winding_Para, slot_layer_angles_radii, alpha=fig_value(Fig_Para, 'grid_alpha', 0.25))
                else:
                    color_slot_layer(ax, slot, layer, color, Fig_Para, Winding_Para, slot_layer_angles_radii, alpha=min(1.0, fig_value(Fig_Para, 'grid_alpha', 0.25) + 0.35))
    return ax

def legend_branches(Winding_Para, num_branch, colors, slot_layer_angles_radii, ax, Fig_Para=None, branch_ids=None):
    """
    Create a clean, centered legend for branches.
    """
    branch_names = [f"Branch {i}" for i in (branch_ids if branch_ids is not None else range(1, num_branch + 1))]
    handles = []

    # Create proxy patches for legend entries
    for color in colors:
        patch = Rectangle((0, 0), 1, 1, facecolor=color, edgecolor='black', linewidth=1,alpha=1)
        handles.append(patch)

    legend_loc, legend_anchor, legend_fontsize, coordinate_space = (
        grid_legend_options(Fig_Para, 12) if Fig_Para is not None else ('center', (0.0, 0.0), 12, 'data')
    )
    legend = ax.legend(
        handles,
        branch_names,
        loc=legend_loc,
        bbox_to_anchor=legend_anchor,
        bbox_transform=ax.transData if coordinate_space == 'data' else ax.transAxes,
        frameon=True,               # draw a frame
        fontsize=legend_fontsize,
        # title="Branches",           # add a clear title
        # title_fontsize=13,
        handlelength=1.5,           # length of color boxes
        labelspacing=0.5,           # vertical spacing
        borderpad=0.8,              # padding inside legend frame
        handletextpad=0.8           # space between color box and text
    )

    # Beautify legend frame
    frame = legend.get_frame()
    frame.set_facecolor('white')     # background color
    frame.set_edgecolor('black')     # border color
    frame.set_linewidth(1.2)
    frame.set_alpha(0.9)             # slight transparency

    return ax
    
def draw_winding_scheme(Winding_Para,Fig_Para,Layout_Para):
    # Define the figure parameters
    num_phases = Winding_Para.num_phases
    cmap = plt.get_cmap(Fig_Para.phase_cmap_name)
    phase_colors = [cmap(i) for i in np.linspace(0, 1, num_phases)]
    cond_info = gw.Winding_Phase_division(Winding_Para,Layout_Para)
    ax,slot_layer_angles_radii = draw_circular_winding_pattern(Winding_Para, Fig_Para)
    color_phases(cond_info,Winding_Para,Fig_Para,phase_colors,slot_layer_angles_radii, ax)
    return ax,slot_layer_angles_radii,cond_info


def prepare_branch_draw_jobs(cond_info, Winding_Para, Layout_Para, Fig_Para, Line_Para,
                             branch_id=None, phase_id=None):
    """Resolve all, one-phase, or one-branch drawing jobs without changing model data."""
    n_branch = 1
    No_line = 0
    start_conductor_ids = cio.get_start_cond_ids_with_cond_info(cond_info)

    num_branch = len(start_conductor_ids)
    if num_branch != Winding_Para.ab*Winding_Para.num_phases:
        print ('Wrong parallel branches setting! Please check the parameter settings')
    if branch_id is None and Line_Para.Single_Phase_Draw == 1:
        num_branch = int(len(start_conductor_ids) / Winding_Para.num_phases)
    cmap = plt.get_cmap(Fig_Para.branch_cmap_name)
    if num_branch == 2:
        colors = [cmap(0.0), cmap(1.0)]   # far apart for high contrast
    else:
        colors = [cmap(i) for i in np.linspace(0, 1, num_branch)]

    phase_a_adjustments = list(getattr(Layout_Para, 'inlet_index_adjustments_phase_a', []))
    phase_a_branch_index = 0
    draw_jobs = []
    for start_conductor_id in start_conductor_ids:
        slot,layer,phasor = start_conductor_id
        conductor_ids = cio.get_cond_ids_with_cond_info(cond_info,n_branch)
        phase_index = cio.get_phase_index(slot, layer, cond_info)
        branch_adjustment = 0
        if phase_index == 0 or (phase_index is None and n_branch <= Winding_Para.ab):
            if phase_a_branch_index < len(phase_a_adjustments):
                branch_adjustment = phase_a_adjustments[phase_a_branch_index]
            phase_a_branch_index += 1

        selected = (n_branch == branch_id if branch_id is not None else
                    phase_index == phase_id if phase_id is not None else
                    Line_Para.Single_Phase_Draw == 0 or phase_index == 0)
        if selected:
            color = colors[n_branch - 1 if branch_id is not None else No_line]
            draw_jobs.append((n_branch, conductor_ids, color, branch_adjustment))
            No_line += 1
        n_branch += 1

    return draw_jobs, [job[2] for job in draw_jobs]


def draw_circular_winding_layout(ax,cond_info,start_conductor_ids,Winding_Para,Layout_Para,Fig_Para,
                                 Line_Para,branch_id=None, phase_id=None):
    slot_layer_angles_radii = get_slot_layer_angles_radii(Winding_Para, Fig_Para)
    draw_jobs, colors = prepare_branch_draw_jobs(
        cond_info, Winding_Para, Layout_Para, Fig_Para, Line_Para,
        branch_id=branch_id, phase_id=phase_id)
    num_branch = len(draw_jobs)
    pole_region_by_conductor = {
        (row[0], row[1], row[5]): row[6]
        for row in cond_info
        if len(row) > 6
    }
    same_layer_route_lanes = build_same_layer_route_lanes(
        [(branch_id, conductor_ids) for branch_id, conductor_ids, _, _ in draw_jobs],
        Winding_Para,
        pole_region_by_conductor,
        close_loop=getattr(Layout_Para, 'in_out_connection', 0) == 1,
    )
    for branch_id, conductor_ids, color, branch_adjustment in draw_jobs:
        draw_branch_connections_with_cond_ids(
            ax,
            conductor_ids,
            slot_layer_angles_radii,
            Fig_Para,
            Winding_Para,
            Layout_Para,
            Line_Para,
            color,
            branch_adjustment=branch_adjustment,
            branch_id=branch_id,
            same_layer_route_lanes=same_layer_route_lanes,
        )
    if Fig_Para.grid_color_pattern == 'branch':
        if Fig_Para.branch_legend == 1 and draw_jobs:
            legend_branches(Winding_Para,num_branch,colors,slot_layer_angles_radii, ax, Fig_Para,
                            branch_ids=[job[0] for job in draw_jobs])

            
def _split_unwrapped_path(points, num_slots):
    """Split a short periodic path at the slot seam, preserving direction."""
    left, right = 0.5, num_slots + 0.5
    pieces = [[points[0]]]
    shift = 0
    for original_start, original_end in zip(points, points[1:]):
        start = (original_start[0] + shift, original_start[1])
        end = (original_end[0] + shift, original_end[1])
        if end[0] > right or end[0] < left:
            boundary = right if end[0] > right else left
            fraction = (boundary - start[0]) / (end[0] - start[0])
            y = start[1] + fraction * (end[1] - start[1])
            pieces[-1].append((boundary, y))
            delta = -num_slots if boundary == right else num_slots
            shift += delta
            pieces.append([(boundary + delta, y), (end[0] + delta, end[1])])
        else:
            pieces[-1].append(end)
    return pieces


def draw_unwrapped_winding_layout(ax, cond_info, start_conductor_ids, Winding_Para,
                                 Layout_Para, Fig_Para, Line_Para, branch_id=None, phase_id=None):
    """Draw cached physical connections on a periodic slot/layer grid."""
    slots, layers = Winding_Para.num_slots, Winding_Para.num_layers
    jobs, colors = prepare_branch_draw_jobs(
        cond_info, Winding_Para, Layout_Para, Fig_Para, Line_Para,
        branch_id=branch_id, phase_id=phase_id)
    phase_colors = [plt.get_cmap(Fig_Para.phase_cmap_name)(v)
                    for v in np.linspace(0, 1, Winding_Para.num_phases)]
    branch_colors = {branch: color for branch, _, color, _ in jobs}
    selected = {tuple(c) for _, conductors, _, _ in jobs for c in conductors}
    ax._winding_edges = []
    ax._winding_terminals = []
    alpha = line_value(Line_Para, 'line_alpha', 1.0)
    linewidth = Line_Para.linewidth
    # External terminal rails are display annotations, not new model connections.
    phase_by_branch = {branch: int(cio.get_phase_index(conductors[0][0], conductors[0][1], cond_info))
                       for branch, conductors, _, _ in jobs}
    all_phase_by_branch = {int(row[3]): int(row[2]) for row in cond_info
                           if int(row[3]) > 0}
    local_branch_number = {}
    local_branch_label = {}
    for phase in sorted(set(all_phase_by_branch.values())):
        phase_branches = sorted(branch for branch, branch_phase in all_phase_by_branch.items()
                                if branch_phase == phase)
        for local_number, branch in enumerate(phase_branches, start=1):
            local_branch_number[branch] = local_number
            local_branch_label[branch] = f'{chr(65 + phase)}{local_number}'
    visible_phases = sorted(set(phase_by_branch.values())) if Line_Para.inlet_line else []
    rail_palette = ('#1565c0', '#e07800', '#238b45', '#8e44ad', '#c0392b', '#00838f')
    neutral_color = '#455a64'
    phase_rails = {phase: -0.55 - 0.55 * index for index, phase in enumerate(visible_phases)}
    inlet_label_tiers = {}
    for phase in visible_phases:
        inlets = sorted((conductors[0][0] + 1, branch) for branch, conductors, _, _ in jobs
                        if phase_by_branch[branch] == phase)
        previous_slot, tier = None, 0
        for slot, branch in inlets:
            tier = tier + 1 if previous_slot is not None and slot - previous_slot <= 2 else 0
            inlet_label_tiers[branch] = tier
            previous_slot = slot
    neutral_y = 0.05
    rail_top = min([0.45] + list(phase_rails.values()) + ([neutral_y] if Line_Para.outlet_line else []))
    def draw_rail(y, color, label, gid, label_at_left=False):
        ax.plot([0.5, slots + 0.5], [y, y], color=color, linewidth=max(1.2, linewidth),
                alpha=alpha, zorder=6, gid=gid)
        ax.annotate(label, (0.5 if label_at_left else slots / 2 + 0.5, y),
                    xytext=(-4, 0) if label_at_left else (0, 3),
                    textcoords='offset points',
                    ha='right' if label_at_left else 'center',
                    va='center' if label_at_left else 'bottom', fontsize=9, color=color, zorder=7,
                    bbox=dict(facecolor='white', edgecolor='none', alpha=0.9, pad=1))
    for phase, y in phase_rails.items():
        draw_rail(y, rail_palette[phase % len(rail_palette)], f'Phase {chr(65 + phase)}',
                  f'phase-rail-{phase}', label_at_left=True)
    if Line_Para.outlet_line and jobs:
        draw_rail(neutral_y, neutral_color, 'Neutral line', 'neutral-rail')
    for slot in range(slots):
        for layer in range(layers):
            ax.add_patch(Rectangle((slot + 0.5, layer + 0.5), 1, 1,
                                  facecolor='white', edgecolor='#d6dce3', linewidth=0.5, zorder=0))
    for row in cond_info:
        slot, layer, phase, branch, _, phasor = row[:6]
        if (branch_id is not None or Line_Para.Single_Phase_Draw) and (slot, layer, phasor) not in selected:
            continue
        color = (phase_colors[int(phase)] if Fig_Para.grid_color_pattern == 'phase'
                 else branch_colors.get(branch, '#eeeeee'))
        ax.add_patch(Rectangle((slot + 0.5, layer + 0.5), 1, 1, facecolor=color,
                              edgecolor='none', alpha=min(0.3, fig_value(Fig_Para, 'grid_alpha', 0.25)), zorder=1))
        ax.plot(slot + 1, layer + 1, marker='o', markersize=3.5,
                color=color, markeredgecolor='#333333', markeredgewidth=0.4, zorder=5)

    # Separate every pair of routes whose visible horizontal spans overlap.
    # Pitch ordering keeps nested routes stable with longer spans farther out.
    same_layer_lanes = build_unwrapped_same_layer_route_lanes(
        [(branch, conductors) for branch, conductors, _, _ in jobs],
        Winding_Para,
        close_loop=getattr(Layout_Para, 'in_out_connection', 0) == 1,
        boundary_only=False)
    for branch, conductors, branch_color, adjustment in jobs:
        pairs = list(zip(conductors, conductors[1:]))
        if getattr(Layout_Para, 'in_out_connection', 0) == 1 and len(conductors) > 1:
            pairs.append((conductors[-1], conductors[0]))
        side = initial_connection_side(Layout_Para, adjustment)
        for index, (start, end) in enumerate(pairs):
            direction = get_conn_direction(start[0], end[0], slots)
            following = conductors[index + 2] if index + 2 < len(conductors) else (
                conductors[1] if index == len(conductors) - 1 and len(conductors) > 2 else None)
            next_direction = get_conn_direction(end[0], following[0], slots) if following else direction
            color = line_color_for_side_and_pin(Fig_Para.fig_branch_line_color, side,
                end[1] - start[1], direction, next_direction, branch_color)
            x0, y0 = start[0] + 1, start[1] + 1
            delta = shortest_periodic_delta(start[0], end[0], slots)
            x1, y1 = x0 + delta, end[1] + 1
            points = [(x0, y0), (x1, y1)]
            if y0 == y1:
                route_lane = same_layer_lanes.get(
                    (branch, index), SameLayerRouteLane(0, 1))
                rank, count = route_lane.rank, route_lane.count
                offset = unwrapped_same_layer_lane_offset(rank, count)
                lane = y0 + unwrapped_same_layer_lane_sign(
                    start[1], layers) * offset
                points = build_unwrapped_same_layer_path(
                    (x0, y0), (end[0] + 1, y1), slots, lane)
            if Line_Para.line_single_side in (0, side):
                pieces = _split_unwrapped_path(points, slots)
                gid = f'connection-{branch}-{index}'
                ax._winding_edges.append(dict(branch=branch, index=index, start=tuple(start),
                                              end=tuple(end), side=side, gid=gid))
                for part in pieces:
                    xs, ys = zip(*part)
                    ax.plot(xs, ys, color=color, linewidth=linewidth, alpha=alpha,
                            linestyle=linestyle_for_side(Line_Para.linestyle, side), zorder=3, gid=gid)
                if len(pieces) > 1:
                    # The right seam alone carries a continuation arrow. Use the
                    # actual local tangent so diagonal and reverse wraps agree.
                    right_part = next(part for part in pieces
                                      if part[0][0] == slots + 0.5 or part[-1][0] == slots + 0.5)
                    a, b = (right_part[:2] if right_part[0][0] == slots + 0.5 else right_part[-2:])
                    head = right_part[0] if right_part[0][0] == slots + 0.5 else right_part[-1]
                    tail = (head[0] - 0.18*(b[0]-a[0]), head[1] - 0.18*(b[1]-a[1]))
                    ax.annotate('', xy=head, xytext=tail, annotation_clip=False,
                                arrowprops=dict(arrowstyle='-|>', color=color, alpha=alpha,
                                                lw=linewidth, shrinkA=0, shrinkB=0,
                                                mutation_scale=8*line_value(Line_Para, 'arrow_size', 1.0)),
                                zorder=6, gid=f'boundary-arrow-{branch}-{index}')
                if Line_Para.draw_arrow:
                    tail, head = unwrapped_path_arrow_segment(
                        pieces, start_fraction=0.16, end_fraction=0.28)
                    ax.annotate('', xy=head, xytext=tail, arrowprops=dict(arrowstyle='-|>',
                                color=color, alpha=alpha, lw=linewidth,
                                mutation_scale=8*line_value(Line_Para, 'arrow_size', 1.0)),
                                zorder=4, gid=f'arrow-{branch}-{index}')
            side = next_connection_side(side)
        for kind, conductor, enabled in (
                ('inlet', conductors[0], Line_Para.inlet_line),
                ('outlet', conductors[-1], Line_Para.outlet_line)):
            if enabled:
                x, y = conductor[0] + 1, conductor[1] + 1
                phase = phase_by_branch[branch]
                rail_y = phase_rails[phase] if kind == 'inlet' else neutral_y
                color = rail_palette[phase % len(rail_palette)] if kind == 'inlet' else neutral_color
                curve = 0.09
                lead = FancyArrowPatch(
                    (x, y), (x, rail_y), arrowstyle='-', connectionstyle=f'arc3,rad={curve}',
                    color=color, linewidth=linewidth, alpha=alpha, zorder=6)
                lead.set_gid(f'{kind}-{branch}')
                ax.add_patch(lead)
                ax.plot(x, rail_y, marker='o', markersize=3, color=color, zorder=7)
                if kind == 'inlet':
                    ax.annotate(local_branch_label[branch], (x, rail_y),
                                xytext=(0, 3 + 12 * inlet_label_tiers[branch]),
                                textcoords='offset points', ha='center', va='bottom',
                                fontsize=8, color=color, zorder=7,
                                fontweight='bold')
                ax._winding_terminals.append(dict(branch=branch, kind=kind, conductor=tuple(conductor)))
    if jobs and ((Fig_Para.grid_color_pattern == 'branch' and fig_value(Fig_Para, 'branch_legend', 0)) or
            (Fig_Para.grid_color_pattern == 'phase' and fig_value(Fig_Para, 'phase_legend', 0))):
        is_phase = Fig_Para.grid_color_pattern == 'phase'
        if is_phase:
            handles = [Rectangle((0, 0), 1, 1, facecolor=c) for c in phase_colors]
            labels = [f'Phase {chr(65 + i)}' for i in range(len(phase_colors))]
        else:
            handles, labels = [], []
            for phase in sorted(set(phase_by_branch.values())):
                handles.append(Rectangle((0, 0), 1, 1, facecolor='none', edgecolor='none'))
                labels.append(f'Phase {chr(65 + phase)}')
                for branch, _, color, _ in jobs:
                    if phase_by_branch[branch] == phase:
                        handles.append(Rectangle((0, 0), 1, 1, facecolor=color))
                        labels.append(f'Branch {local_branch_number[branch]}')
        ax.legend(handles, labels,
                  loc='lower center', bbox_to_anchor=(0.5, 1.02), ncol=min(6, len(handles)),
                  fontsize=fig_value(Fig_Para, 'legend_fontsize', 9))
    label_headroom = 0.4 + 0.55 * max(0, max(inlet_label_tiers.values(), default=0) - 1)
    ax.set(xlim=(0.5, slots+0.5), ylim=(layers+0.55, rail_top - label_headroom if rail_top < 0.45 else 0.45),
           xlabel='Slot', ylabel='Layer (outer to inner)')
    ax.set_xticks(range(1, slots+1))
    ax.set_yticks(range(1, layers+1))
    ax.tick_params(axis='x', labelsize=7 if slots <= 72 else 5, labelrotation=0 if slots <= 72 else 90)
    ax.set_aspect('auto')
    ax.set_position([0.08, 0.12, 0.88, 0.76])
    return ax


def draw_winding_scheme_ax(Winding_Para, Fig_Para, Layout_Para, ax, cond_info=None):
    """
    Draws the main winding scheme on the provided Matplotlib axis.
    """
    # Define the figure parameters
    num_phases = Winding_Para.num_phases
    cmap = plt.get_cmap(Fig_Para.phase_cmap_name)
    phase_colors = [cmap(i) for i in np.linspace(0, 1, num_phases)]

    # Get conductor info
    if cond_info is None:
        cond_info = gw.Winding_Phase_division(Winding_Para, Layout_Para)

    # Use the existing axis to draw the pattern
    slot_layer_angles_radii = draw_circular_winding_pattern_ax(Winding_Para, Fig_Para, ax)

    # Apply phase coloring
    color_phases(cond_info, Winding_Para, Fig_Para, phase_colors, slot_layer_angles_radii, ax)

    return slot_layer_angles_radii

            

