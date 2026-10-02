# -*- coding: utf-8 -*-
"""Standalone PyQt6 manual winding layout tool."""

from __future__ import annotations

import os
import sys
from datetime import datetime

os.environ.setdefault("MPLCONFIGDIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".matplotlib"))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from manual_layout_core import ManualLayoutCore, ManualLayoutParams
import get_winding_pattern as gw


class ManualLayoutApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Manual Layout Tool")
        self.setGeometry(80, 80, 1500, 900)
        self.input_fields = {}
        self.field_labels = {}
        self.grid_buttons = {}
        self.optimizing_transposition = False
        self.branch_colors = [
            "#1d4ed8", "#dc2626", "#059669", "#9333ea", "#d97706", "#0891b2",
            "#be123c", "#4f46e5", "#16a34a", "#c2410c", "#7c3aed", "#0f766e",
        ]
        self.phase_colors = ["#d9f99d", "#fecaca", "#bae6fd", "#fde68a", "#ddd6fe", "#bbf7d0"]
        self.core = ManualLayoutCore(log=self.log)
        self.init_ui()
        self.apply_settings(silent=True)

    def init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        self.main_splitter.setChildrenCollapsible(False)

        upper = QSplitter(Qt.Orientation.Horizontal)
        upper.setChildrenCollapsible(False)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        self.tabs = QTabWidget()
        self.tabs.setUsesScrollButtons(True)
        self.tabs.addTab(self.create_winding_tab(), "Winding")
        self.tabs.addTab(self.create_layout_tab(), "Layout")
        self.tabs.addTab(self.create_pattern_tab(), "Trans Pattern")
        self.tabs.addTab(self.create_output_tab(), "Output")
        self.tabs.addTab(self.create_settings_tab(), "Settings")
        self.tabs.addTab(self.create_help_tab(), "Help")
        left_layout.addWidget(self.tabs, 1)

        action_row = QHBoxLayout()
        for text, callback in [
            ("Start", self.start_layout),
            ("Undo", self.undo),
            ("Clear", self.clear_layout),
            ("Auto Fill Pattern", self.auto_fill_pattern),
        ]:
            btn = QPushButton(text)
            btn.clicked.connect(callback)
            self.configure_button(btn, 100)
            action_row.addWidget(btn)
        left_layout.addLayout(action_row)

        file_row = QHBoxLayout()
        for text, callback in [
            ("Export CSV", self.export_csv),
            ("Save Session", self.save_session),
            ("Load Session", self.load_session),
        ]:
            btn = QPushButton(text)
            btn.clicked.connect(callback)
            self.configure_button(btn, 110)
            file_row.addWidget(btn)
        left_layout.addLayout(file_row)

        self.grid_scroll = QScrollArea()
        self.grid_scroll.setWidgetResizable(False)
        self.grid_placeholder = QLabel("Start a layout to show the slot grid.")
        self.grid_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.grid_scroll.setWidget(self.grid_placeholder)

        upper.addWidget(left)
        upper.addWidget(self.grid_scroll)
        upper.setStretchFactor(0, 0)
        upper.setStretchFactor(1, 1)
        upper.setSizes([560, 940])

        bottom = QSplitter(Qt.Orientation.Horizontal)
        bottom.setChildrenCollapsible(False)
        self.branch_table = self.make_table(["Branch", "Position", "Count", "Left"])
        self.pin_table = self.make_table(["L1", "L2", "Y", "Type", "Pitch", "Num"])
        self.message_log = QTextEdit()
        self.message_log.setReadOnly(True)
        self.message_log.setPlaceholderText("Messages...")
        bottom.addWidget(self.branch_table)
        bottom.addWidget(self.pin_table)
        bottom.addWidget(self.message_log)
        bottom.setSizes([460, 440, 520])

        self.main_splitter.addWidget(upper)
        self.main_splitter.addWidget(bottom)
        self.main_splitter.setStretchFactor(0, 5)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([690, 180])
        root.addWidget(self.main_splitter)

    def configure_button(self, button, min_width=100):
        button.setMinimumSize(min_width, 34)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def make_table(self, headers):
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        return table

    def add_field(self, form, label, key, default, kind="text", options=None):
        label_widget = QLabel(label)
        if kind == "combo":
            widget = QComboBox()
            widget.addItems(options or [])
            widget.setCurrentText(default)
        elif kind == "check":
            widget = QCheckBox()
            widget.setChecked(bool(default))
        else:
            widget = QLineEdit(str(default))
            widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.input_fields[key] = widget
        self.field_labels[key] = label_widget
        form.addRow(label_widget, widget)
        return widget

    def create_winding_tab(self):
        tab = QWidget()
        form = QFormLayout(tab)
        self.add_field(form, "Slots per pole per phase (q):", "q", "2")
        self.add_field(form, "Number of phases:", "num_phases", "3")
        self.add_field(form, "Number of poles:", "num_poles", "4")
        self.add_field(form, "Number of layers:", "num_layers", "4")
        self.add_field(form, "Parallel branches:", "ab", "2")
        num_slots = self.add_field(form, "Number of slots:", "num_slots", "24")
        num_slots.setReadOnly(True)
        return tab

    def create_layout_tab(self):
        tab = QWidget()
        form = QFormLayout(tab)
        self.add_field(form, "Phase shift pattern:", "phase_shift_pattern", "Normal", "combo", ["Normal", "Increment", "None"])
        self.add_field(form, "Phase shift:", "phase_shift", "1")
        self.add_field(form, "Phase shift layer (PSL):", "psl", "1")
        self.add_field(form, "Radial shift:", "radial_shift", "0")
        self.add_field(form, "Inlet from weld side:", "inlet_from_weld_side", False, "check")
        self.add_field(form, "Full symmetry:", "full_symmetry", False, "check")
        self.add_field(form, "First-last connection:", "first_last_connection", True, "check")
        return tab

    def create_pattern_tab(self):
        tab = QWidget()
        form = QFormLayout(tab)
        pattern = self.add_field(
            form,
            "Pattern:",
            "pattern_name",
            "Manual",
            "combo",
            ["Manual"] + gw.get_available_patterns(),
        )
        pattern.currentTextChanged.connect(self.update_pattern_controls)
        tp_type = self.add_field(form, "Transposition type:", "tp_type", "Regular", "combo", ["Regular", "Times", "Interval", "Optimize"])
        tp_type.currentTextChanged.connect(self.update_transposition_controls)
        for label, key, default in [
            ("Transposition times:", "tp_times", "0"),
            ("Transposition interval:", "tp_interval", "0"),
            ("Universal transposition:", "uni_tp", "0"),
            ("Parallel TP first layer:", "pltp_fl", "0"),
            ("Parallel TP last layer:", "pltp_ll", "0"),
            ("Jump layer TP:", "jltp", "0"),
            ("Jump layer direction:", "jld", "1"),
        ]:
            self.add_field(form, label, key, default)
        self.update_transposition_controls()
        return tab

    def create_output_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()
        self.add_field(form, "CSV output folder:", "output_path", "manual_layout_output")
        layout.addLayout(form)
        browse = QPushButton("Browse Output Folder")
        browse.clicked.connect(self.browse_output_folder)
        self.configure_button(browse, 160)
        layout.addWidget(browse)
        layout.addStretch(1)
        return tab

    def create_settings_tab(self):
        tab = QWidget()
        form = QFormLayout(tab)
        self.add_field(form, "Theme:", "ui_theme", "Light", "combo", ["Light", "Dark"])
        self.add_field(form, "Window font size:", "ui_font_size", "10")
        self.add_field(form, "Grid cell width:", "grid_cell_width", "36")
        self.add_field(form, "Grid cell height:", "grid_cell_height", "28")
        self.add_field(form, "Grid header height:", "grid_header_height", "28")
        self.add_field(form, "Folded figure:", "folded_figure", True, "check")
        self.add_field(form, "Folding pages:", "folding_pages", "2")
        self.add_field(form, "Window width:", "window_width", "1500")
        self.add_field(form, "Window height:", "window_height", "900")
        self.add_field(form, "Left panel width:", "left_panel_width", "560")
        self.add_field(form, "Bottom panel height:", "bottom_panel_height", "180")
        apply = QPushButton("Apply Window Settings")
        apply.clicked.connect(self.apply_settings)
        self.configure_button(apply, 180)
        form.addRow(apply)
        return tab

    def create_help_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setPlainText(
            "Manual Layout Tool Help\n\n"
            "Winding panel\n"
            "- q: slots per pole per phase. Integer q and half-slot q are supported.\n"
            "- Number of phases, poles, layers, and branches define the grid and branch group size.\n"
            "- Number of slots is calculated automatically from q * phases * poles.\n\n"
            "Layout panel\n"
            "- Phase shift pattern controls layer slot shifts. Normal alternates shifted/unshifted layer groups; Increment accumulates by layer group.\n"
            "- Phase shift is the slot offset. PSL is the number of layers in each shift group.\n"
            "- Inlet from weld side changes which side is counted as pin-forming in pin shape analysis.\n"
            "- Full symmetry restricts each branch to the same phasor/layer count target.\n"
            "- First-last connection allows layer 1 and the last layer to be treated as adjacent.\n\n"
            "Trans Pattern panel\n"
            "- Manual means the user fills the layout by clicking valid phase-A slots.\n"
            "- BWP, UWP, SSP, SLP, and TSP can be auto-filled into the manual grid.\n"
            "- Transposition type follows the main tool: Regular, Times, Interval, or Optimize.\n"
            "- Optimize chooses a strong-layout transposition rule based on pattern, q, branches, and poles.\n\n"
            "Output panel\n"
            "- CSV output folder is where branch1.csv, branch2.csv, ... are written.\n"
            "- Export CSV writes the current layout in the branch CSV format used by the existing tools.\n\n"
            "Settings panel\n"
            "- Theme switches Light/Dark.\n"
            "- Window font size changes the whole GUI font.\n"
            "- Grid cell width/height and Grid header height control the slot grid geometry.\n"
            "- Folded figure stacks long slot grids vertically by page.\n"
            "- Folding pages controls how many horizontal slot segments are stacked.\n"
            "- Window and splitter sizes tune the exe window layout.\n\n"
            "Buttons\n"
            "- Start validates inputs and creates a fresh slot grid.\n"
            "- Undo restores the previous placement step.\n"
            "- Clear resets the current layout with the current parameters.\n"
            "- Auto Fill Pattern fills phase-A conductors from the selected built-in pattern.\n"
            "- Export CSV writes branch CSV files.\n"
            "- Save Session and Load Session store or restore the current manual editing state.\n\n"
            "Grid colors\n"
            "- Green means valid next position.\n"
            "- Yellow means valid but likely constrained.\n"
            "- Orange means valid but no continuation was found.\n"
            "- Blue numbered cells are already placed conductors."
        )
        layout.addWidget(help_text)
        return tab

    def update_pattern_controls(self):
        try:
            pattern = gw.normalize_pattern_name(self.field_text("pattern_name"))
        except ValueError:
            return
        if pattern in ("ZPP", "LPP"):
            inlet = self.input_fields.get("inlet_from_weld_side")
            if isinstance(inlet, QCheckBox) and not inlet.isChecked():
                inlet.setChecked(True)
                self.log(f"{pattern} requires inlet from weld side; inlet_from_weld_side enabled.")

    def update_transposition_controls(self):
        if self.optimizing_transposition:
            return
        tp_type = self.field_text("tp_type")
        if tp_type == "Optimize":
            self.optimize_transposition()
            return
        active = {
            "tp_times": tp_type == "Times",
            "tp_interval": tp_type == "Interval",
            "uni_tp": tp_type == "Regular",
            "pltp_fl": tp_type == "Regular",
            "pltp_ll": tp_type == "Regular",
            "jltp": tp_type == "Regular",
            "jld": tp_type == "Regular",
        }
        for key, enabled in active.items():
            self.set_transposition_field_state(key, enabled)

    def set_transposition_field_state(self, key, enabled):
        widget = self.input_fields.get(key)
        label = self.field_labels.get(key)
        if widget is None:
            return
        if isinstance(widget, QLineEdit):
            widget.setReadOnly(not enabled)
            widget.setEnabled(True)
        else:
            widget.setEnabled(enabled)
        if enabled:
            widget.setStyleSheet("background:#fff8cc; color:#111827; border:1px solid #d97706;")
            if label is not None:
                label.setStyleSheet("color:#111827; font-weight:bold;")
        else:
            widget.setStyleSheet("background:#e5e7eb; color:#6b7280; border:1px solid #cbd5e1;")
            if label is not None:
                label.setStyleSheet("color:#9ca3af;")

    def set_transposition_type(self, tp_type):
        combo = self.input_fields["tp_type"]
        self.optimizing_transposition = True
        combo.setCurrentText(tp_type)
        self.optimizing_transposition = False
        self.update_transposition_controls()

    def set_field_text(self, key, value):
        widget = self.input_fields.get(key)
        if widget is not None and not isinstance(widget, (QComboBox, QCheckBox)):
            widget.setText(str(value))

    def optimize_transposition(self):
        try:
            pattern = gw.normalize_pattern_name(self.field_text("pattern_name"))
            q = int(float(str(self.field_text("q")).strip()))
            ab = self.int_field("ab", 2)
            poles = self.int_field("num_poles", 4)
        except ValueError:
            self.log("Invalid inputs for transposition optimization.")
            self.set_transposition_type("Regular")
            return

        for key in ["tp_interval", "tp_times", "uni_tp", "pltp_fl", "pltp_ll", "jltp"]:
            self.set_field_text(key, "0")
        self.set_field_text("jld", "1")

        if pattern == "BWP" and q == ab:
            self.set_transposition_type("Times")
            self.set_field_text("tp_times", "1")
            self.log("Transposition optimized: Type=Times, Times=1.")
        elif pattern == "BWP" and 2 * q == ab:
            if poles % 4 != 0:
                self.log("Optimize failed: BWP with 2q=branches requires poles to be a multiple of 4.")
                self.set_transposition_type("Regular")
                return
            interval = int(poles / 4)
            self.set_transposition_type("Interval")
            self.set_field_text("tp_interval", str(interval))
            self.log(f"Transposition optimized: Type=Interval, Interval={interval}.")
        elif pattern == "UWP" and ab == 2:
            self.set_transposition_type("Regular")
            self.log("Transposition optimized: Type=Regular, all transposition values set to 0.")
        elif pattern == "UWP" and ab == 2 * q:
            self.set_transposition_type("Interval")
            self.set_field_text("tp_interval", "1")
            self.log("Transposition optimized: Type=Interval, Interval=1.")
        elif pattern in ("SSP", "SLP") and ab in (q, 2 * q, poles):
            self.set_transposition_type("Regular")
            self.set_field_text("pltp_ll", "1")
            self.log("Transposition optimized: Type=Regular, pltp_ll=1.")
        else:
            self.set_transposition_type("Regular")
            self.log("No matching strong-layout transposition rule; using Regular defaults.")

    def field_text(self, key):
        widget = self.input_fields[key]
        if isinstance(widget, QComboBox):
            return widget.currentText()
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        return widget.text()

    def float_field(self, key, default=0.0):
        try:
            return float(str(self.field_text(key)).strip())
        except (TypeError, ValueError):
            return default

    def int_field(self, key, default=0):
        try:
            return int(float(str(self.field_text(key)).strip()))
        except (TypeError, ValueError):
            return default

    def params_from_fields(self):
        if self.field_text("tp_type") == "Optimize":
            self.optimize_transposition()
        q = self.float_field("q", 2.0)
        num_phases = self.int_field("num_phases", 3)
        num_poles = self.int_field("num_poles", 4)
        num_layers = self.int_field("num_layers", 4)
        num_slots = int(round(q * num_phases * num_poles))
        self.input_fields["num_slots"].setText(str(num_slots))
        return ManualLayoutParams(
            q=q,
            num_phases=num_phases,
            num_poles=num_poles,
            num_layers=num_layers,
            ab=self.int_field("ab", 2),
            phase_shift=self.int_field("phase_shift", 1),
            psl=self.int_field("psl", 1),
            phase_shift_pattern=self.field_text("phase_shift_pattern"),
            radial_shift=self.int_field("radial_shift", 0),
            inlet_from_weld_side=1 if self.field_text("inlet_from_weld_side") else 0,
            full_symmetry=bool(self.field_text("full_symmetry")),
            first_last_connection=bool(self.field_text("first_last_connection")),
            pattern_name=self.field_text("pattern_name"),
            tp_type=self.field_text("tp_type"),
            tp_times=self.int_field("tp_times", 0),
            tp_interval=self.int_field("tp_interval", 0),
            uni_tp=self.int_field("uni_tp", 0),
            pltp_fl=self.int_field("pltp_fl", 0),
            pltp_ll=self.int_field("pltp_ll", 0),
            jltp=self.int_field("jltp", 0),
            jld=self.int_field("jld", 1),
            output_path=str(self.field_text("output_path")).strip() or "manual_layout_output",
        )

    def fill_fields_from_params(self):
        p = self.core.params
        pattern_value = "Manual"
        if str(p.pattern_name).strip().lower() != "manual":
            pattern_value = gw.get_pattern_label(gw.normalize_pattern_name(p.pattern_name, allow_extra=False))
        values = {
            "q": p.q,
            "num_phases": p.num_phases,
            "num_poles": p.num_poles,
            "num_layers": p.num_layers,
            "ab": p.ab,
            "num_slots": self.core.num_slots,
            "phase_shift_pattern": p.phase_shift_pattern,
            "phase_shift": p.phase_shift,
            "psl": p.psl,
            "radial_shift": p.radial_shift,
            "inlet_from_weld_side": bool(p.inlet_from_weld_side),
            "full_symmetry": p.full_symmetry,
            "first_last_connection": p.first_last_connection,
            "pattern_name": pattern_value,
            "tp_type": p.tp_type,
            "tp_times": p.tp_times,
            "tp_interval": p.tp_interval,
            "uni_tp": p.uni_tp,
            "pltp_fl": p.pltp_fl,
            "pltp_ll": p.pltp_ll,
            "jltp": p.jltp,
            "jld": p.jld,
            "output_path": p.output_path,
        }
        for key, value in values.items():
            widget = self.input_fields.get(key)
            if widget is None:
                continue
            if isinstance(widget, QComboBox):
                widget.setCurrentText(str(value))
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            else:
                widget.setText(str(value))
        self.update_transposition_controls()

    def start_layout(self):
        try:
            self.core.params = self.params_from_fields()
            self.core.start()
            self.build_grid()
            self.refresh_all()
        except Exception as exc:
            QMessageBox.critical(self, "Start Failed", str(exc))
            self.log(f"Start failed: {exc}")

    def clear_layout(self):
        try:
            if self.core.winding_para is None:
                self.start_layout()
                return
            self.core.clear()
            self.build_grid()
            self.refresh_all()
            self.log("Layout cleared.")
        except Exception as exc:
            QMessageBox.warning(self, "Clear Failed", str(exc))

    def undo(self):
        if self.core.undo():
            self.refresh_all()
            self.log("Undo completed.")
        else:
            self.log("Nothing to undo.")

    def auto_fill_pattern(self):
        try:
            self.core.params = self.params_from_fields()
            count = self.core.auto_fill_pattern()
            self.build_grid()
            self.refresh_all()
            self.log(f"Auto fill completed: {count} conductors.")
        except Exception as exc:
            QMessageBox.warning(self, "Auto Fill Failed", str(exc))
            self.log(f"Auto fill failed: {exc}")

    def export_csv(self):
        try:
            if self.core.winding_para is None:
                self.start_layout()
            folder = self.core.export_csv(self.field_text("output_path"))
            self.log(f"CSV exported to: {folder}")
        except Exception as exc:
            QMessageBox.warning(self, "Export Failed", str(exc))
            self.log(f"Export failed: {exc}")

    def save_session(self):
        if self.core.winding_para is None:
            self.start_layout()
        default_name = f"manual_layout_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path, _ = QFileDialog.getSaveFileName(self, "Save Session", default_name, "JSON Files (*.json)")
        if not path:
            return
        try:
            self.core.save_session(path)
            self.log(f"Session saved: {path}")
        except Exception as exc:
            QMessageBox.warning(self, "Save Failed", str(exc))

    def load_session(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Session", "", "JSON Files (*.json)")
        if not path:
            return
        try:
            self.core.load_session(path)
            self.fill_fields_from_params()
            self.build_grid()
            self.refresh_all()
            self.log(f"Session loaded: {path}")
        except Exception as exc:
            QMessageBox.warning(self, "Load Failed", str(exc))
            self.log(f"Load failed: {exc}")

    def browse_output_folder(self):
        path = QFileDialog.getExistingDirectory(self, "CSV Output Folder", self.field_text("output_path"))
        if path:
            self.input_fields["output_path"].setText(path)

    def branch_base_color(self, branch_index):
        return self.branch_colors[branch_index % len(self.branch_colors)]

    def mix_colors(self, color_a, color_b, ratio):
        ratio = max(0.0, min(float(ratio), 1.0))
        a = color_a.lstrip("#")
        b = color_b.lstrip("#")
        ar, ag, ab = int(a[0:2], 16), int(a[2:4], 16), int(a[4:6], 16)
        br, bg, bb = int(b[0:2], 16), int(b[2:4], 16), int(b[4:6], 16)
        rr = round(ar * (1 - ratio) + br * ratio)
        rg = round(ag * (1 - ratio) + bg * ratio)
        rb = round(ab * (1 - ratio) + bb * ratio)
        return f"#{rr:02x}{rg:02x}{rb:02x}"

    def branch_conductor_color(self, branch_index, cond_index):
        base = self.branch_base_color(branch_index)
        group_size = max(1, getattr(self.core, "group_size", 1))
        shade_ratio = 0.12 + 0.58 * (cond_index % group_size) / max(group_size - 1, 1)
        return self.mix_colors(base, "#ffffff", shade_ratio)

    def readable_text_color(self, background):
        bg = background.lstrip("#")
        r, g, b = int(bg[0:2], 16), int(bg[2:4], 16), int(bg[4:6], 16)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b)
        return "#111827" if luminance > 150 else "#ffffff"

    def build_grid(self):
        old = self.grid_scroll.takeWidget()
        if old is not None:
            old.deleteLater()
        self.grid_buttons = {}
        grid_widget = QWidget()
        grid_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout = QGridLayout(grid_widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(2)

        label_width = max(46, self.grid_cell_width())
        header_height = self.grid_header_height()
        page_ranges = self.grid_page_ranges()
        row_cursor = 0
        for page_index, (start_slot, end_slot) in enumerate(page_ranges):
            show_phase_index = page_index == 0
            row_offset = row_cursor
            if show_phase_index:
                phase_title = QLabel("Phase")
                phase_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
                phase_title.setFixedSize(label_width, header_height)
                layout.addWidget(phase_title, row_offset, 0)
            slot_title = QLabel("Slot")
            slot_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            slot_title.setFixedSize(label_width, header_height)
            slot_row = row_offset + 1 if show_phase_index else row_offset
            first_layer_row = slot_row + 1
            layout.addWidget(slot_title, slot_row, 0)

            for column, slot in enumerate(range(start_slot, end_slot), start=1):
                if show_phase_index:
                    phase = self.core.phase_at(slot, 0)
                    phase_label = QLabel(chr(ord("A") + phase) if phase >= 0 else "-")
                    phase_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    phase_label.setFixedSize(self.grid_cell_width(), header_height)
                    phase_label.setStyleSheet(f"background:{self.phase_colors[phase % len(self.phase_colors)]}; border:1px solid #d1d5db;")
                    layout.addWidget(phase_label, row_offset, column)
                slot_label = QLabel(str(slot + 1))
                slot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                slot_label.setFixedSize(self.grid_cell_width(), header_height)
                layout.addWidget(slot_label, slot_row, column)

            for layer in range(self.core.params.num_layers):
                layer_label = QLabel(f"L{layer + 1}")
                layer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layer_label.setFixedSize(label_width, self.grid_cell_height())
                layout.addWidget(layer_label, first_layer_row + layer, 0)
                for column, slot in enumerate(range(start_slot, end_slot), start=1):
                    btn = QPushButton("")
                    btn.setFixedSize(self.grid_cell_width(), self.grid_cell_height())
                    btn.clicked.connect(lambda _checked=False, l=layer, s=slot: self.on_slot_clicked(l, s))
                    btn.setToolTip(f"Slot {slot + 1}, Layer {layer + 1}, Phase {chr(ord('A') + self.core.phase_at(slot, layer))}, Pole {self.core.pole_at(slot, layer) + 1}")
                    layout.addWidget(btn, first_layer_row + layer, column)
                    self.grid_buttons[(layer, slot)] = btn
            row_cursor += self.core.params.num_layers + (2 if show_phase_index else 1) + 1
        grid_widget.adjustSize()
        self.grid_scroll.setWidget(grid_widget)
        self.auto_resize_for_layers()

    def on_slot_clicked(self, layer, slot):
        try:
            self.core.place(layer, slot)
            self.refresh_all()
        except Exception as exc:
            QMessageBox.warning(self, "Invalid Move", str(exc))

    def refresh_all(self):
        self.refresh_grid()
        self.refresh_tables()

    def refresh_grid(self):
        if self.core.winding_para is None:
            return
        for (layer, slot), btn in self.grid_buttons.items():
            value = int(self.core.slots[layer][slot])
            phase = self.core.phase_at(slot, layer)
            status = self.core.classify_valid_position(layer, slot)
            btn.setText(str(value) if value else "")
            btn.setEnabled(status in ["valid", "risk", "dead"] and phase == 0)
            if value:
                branch_info = self.core.position_branch_info(layer, slot) or {"branch": 0, "branch_label": 1, "cond_index": value - 1}
                branch = branch_info["branch"]
                cond_index = branch_info["cond_index"]
                color = self.branch_conductor_color(branch, cond_index)
                border = self.branch_base_color(branch)
                text_color = self.readable_text_color(color)
                btn.setToolTip(
                    f"Branch {branch_info['branch_label']}, Conductor {cond_index + 1}, "
                    f"Slot {slot + 1}, Layer {layer + 1}"
                )
                style = f"background:{color}; color:{text_color}; border:2px solid {border}; font-weight:bold;"
            elif phase != 0:
                color = self.phase_colors[phase % len(self.phase_colors)]
                style = f"background:{color}; color:#374151; border:1px solid #d1d5db;"
            elif status == "valid":
                style = "background:#86efac; color:#052e16; border:1px solid #16a34a;"
            elif status == "risk":
                style = "background:#fde047; color:#422006; border:1px solid #ca8a04;"
            elif status == "dead":
                style = "background:#fdba74; color:#431407; border:1px solid #ea580c;"
            else:
                style = "background:#f3f4f6; color:#9ca3af; border:1px solid #d1d5db;"
            btn.setStyleSheet(style)

    def refresh_tables(self):
        rows = self.core.branch_detail_rows() if self.core.winding_para is not None else []
        self.branch_table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            values = [row["branch"], row["position"], row["count"], row["left"]]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.branch_table.setItem(row_idx, col, item)

        pin_rows = self.core.pin_shape_rows() if self.core.winding_para is not None else []
        self.pin_table.setRowCount(len(pin_rows))
        for row_idx, row in enumerate(pin_rows):
            values = [row["L1"], row["L2"], row["Y"], row["Type"], row["Pitch"], row["Num"]]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.pin_table.setItem(row_idx, col, item)

    def grid_cell_width(self):
        return max(24, min(self.int_field("grid_cell_width", 36), 72))

    def grid_cell_height(self):
        return max(22, min(self.int_field("grid_cell_height", 28), 54))

    def grid_header_height(self):
        return max(18, min(self.int_field("grid_header_height", 28), 54))

    def folded_figure_enabled(self):
        return bool(self.field_text("folded_figure"))

    def folding_pages(self):
        return max(1, min(self.int_field("folding_pages", 2), max(self.core.num_slots, 1)))

    def grid_page_ranges(self):
        if self.core.winding_para is None or not self.folded_figure_enabled():
            return [(0, self.core.num_slots)]
        pages = self.folding_pages()
        slots_per_page = (self.core.num_slots + pages - 1) // pages
        ranges = []
        for page in range(pages):
            start = page * slots_per_page
            end = min(start + slots_per_page, self.core.num_slots)
            if start < end:
                ranges.append((start, end))
        return ranges or [(0, self.core.num_slots)]

    def auto_resize_for_layers(self):
        if self.core.winding_para is None:
            return
        page_count = len(self.grid_page_ranges())
        header_rows = 2 + max(0, page_count - 1)
        desired_height = 360 + (
            page_count * self.core.params.num_layers * (self.grid_cell_height() + 4)
            + header_rows * (self.grid_header_height() + 4)
            + page_count * 12
        )
        screen = QApplication.primaryScreen()
        if screen is not None:
            desired_height = min(desired_height, screen.availableGeometry().height() - 60)
        desired_height = max(760, int(desired_height))
        self.resize(max(self.width(), self.int_field("window_width", 1500)), desired_height)
        bottom_height = max(130, self.int_field("bottom_panel_height", 180))
        if self.main_splitter.count() == 2:
            self.main_splitter.setSizes([max(420, desired_height - bottom_height), bottom_height])

    def apply_settings(self, silent=False):
        theme = self.field_text("ui_theme") if "ui_theme" in self.input_fields else "Light"
        font_size = max(8, min(self.int_field("ui_font_size", 10), 18))
        app = QApplication.instance()
        if app is not None:
            font = app.font()
            font.setPointSize(font_size)
            app.setFont(font)
        self.setFont(QFont(self.font().family(), font_size))
        if theme == "Dark":
            self.setStyleSheet(f"""
                QWidget {{ background:#202124; color:#f1f3f4; font-size:{font_size}pt; }}
                QLineEdit, QTextEdit, QComboBox, QTableWidget {{
                    background:#2b2d31; color:#f1f3f4; border:1px solid #5f6368; border-radius:4px;
                }}
                QPushButton {{
                    background:#303134; color:#f1f3f4; border:1px solid #5f6368; border-radius:4px; padding:4px 8px;
                }}
                QPushButton:disabled {{ color:#9aa0a6; }}
                QTabBar::tab {{ background:#2b2d31; color:#f1f3f4; padding:7px 13px; border:1px solid #3c4043; }}
                QTabBar::tab:selected {{ background:#202124; }}
                QSplitter::handle {{ background:#4a4d52; }}
            """)
        else:
            self.setStyleSheet(f"""
                QWidget {{ background:#f6f7f9; color:#111827; font-size:{font_size}pt; }}
                QLineEdit, QTextEdit, QComboBox, QTableWidget {{
                    background:#ffffff; color:#111827; border:1px solid #d5d8de; border-radius:4px;
                }}
                QPushButton {{
                    background:#ffffff; color:#111827; border:1px solid #d5d8de; border-radius:4px; padding:4px 8px;
                }}
                QPushButton:hover {{ background:#eef2f7; }}
                QPushButton:disabled {{ color:#9ca3af; }}
                QTabBar::tab {{ background:#f0f2f5; color:#374151; padding:7px 13px; border:1px solid #d5d8de; }}
                QTabBar::tab:selected {{ background:#ffffff; color:#111827; }}
                QSplitter::handle {{ background:#d5d8de; }}
            """)
        self.resize(max(1100, self.int_field("window_width", 1500)), max(720, self.int_field("window_height", 900)))
        left_width = max(460, self.int_field("left_panel_width", 560))
        bottom_height = max(130, self.int_field("bottom_panel_height", 180))
        if self.main_splitter.count() == 2:
            self.main_splitter.setSizes([max(420, self.height() - bottom_height), bottom_height])
            upper = self.main_splitter.widget(0)
            if isinstance(upper, QSplitter):
                upper.setSizes([left_width, max(500, self.width() - left_width)])
        if self.core.winding_para is not None:
            self.build_grid()
            self.refresh_all()
        if not silent:
            self.log("Window settings applied.")

    def log(self, message):
        if hasattr(self, "message_log"):
            self.message_log.append(str(message))


def main():
    app = QApplication(sys.argv)
    window = ManualLayoutApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
