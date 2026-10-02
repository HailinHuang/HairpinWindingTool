import sys
import os
import math
import shutil
import json
import zipfile
from copy import deepcopy
from datetime import datetime
from fractions import Fraction
from types import SimpleNamespace as NS
from xml.sax.saxutils import escape
os.environ.setdefault("MPLCONFIGDIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".matplotlib"))
import get_winding_pattern as gw
import automatic_transposition as auto_tp
import draw_figure as dfig
import cond_info_operation as cio
import layout_analysis as la 
import end_winding_calc as ewc
import winding_function_calculation as wfc
import vd_optimize as vdo
import inductance_calculation as ic
import phase_topology as phase_topology
from app_diagnostics import DiagnosticLog
from calculation_state import CalculationState
import calculation_cache
from config_io import ConfigIOMixin
from inductance_ui import InductanceUIMixin
from result_export import ResultExportMixin
try:
    import matlab.engine
    MATLAB_ENGINE_AVAILABLE = True
except ModuleNotFoundError:
    matlab = None
    MATLAB_ENGINE_AVAILABLE = False
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from collections import namedtuple
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QTabWidget, QFormLayout, QTextEdit, QFrame, QSizePolicy, QCheckBox, QSpacerItem,
    QGridLayout, QComboBox, QTableWidgetItem, QTableWidget, QSplitter, QFileDialog, QDialog, QScrollArea,
    QProgressBar, QStackedWidget, QSpinBox, QHeaderView, QToolButton, QMessageBox
)
from PyQt6.QtCore import QPoint, QEvent, Qt, QObject, QThread, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QFont, QIntValidator, QDesktopServices
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas


class TextComboBox(QComboBox):
    """QComboBox compatibility adapter for configuration fields read as text."""

    def text(self):
        return self.currentText()

    def setText(self, text):
        self.setCurrentText(text)


class BranchDivisionDialog(QDialog):
    """Session-only workbench for candidate branch partitions by Pattern."""

    def __init__(self, owner):
        super().__init__(owner)
        from branch_start_preview import preferred_division_plan

        self.owner = owner
        data = owner.phase_preview
        self.naa = int(owner.get_field_value("ab"))
        self.patterns = sorted(phase_topology.FRACTIONAL_PATTERN_POLICIES)
        key = (str(data['q']), data['poles'], data['layers'], self.naa,
               tuple(data['shifts']), data['phases'])
        self.preferred_rules = owner._branch_division_preferences.setdefault(key, {})
        self.setWindowTitle("Branch Division — candidate rules")
        self.setMinimumSize(760, 480)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f"q={data['q']}  |  pp={data['poles']//2}  |  Naa={self.naa}  |  "
            "Candidate membership only; no connections are generated."))

        controls = QGridLayout()
        self.pattern = QComboBox()
        self.pattern.addItems(self.patterns)
        try:
            self.pattern.setCurrentText(gw.normalize_pattern_name(
                owner.get_field_value("pattern_name")))
        except ValueError:
            self.pattern.setCurrentText("BWP")
        controls.addWidget(QLabel("Pattern"), 0, 0)
        controls.addWidget(self.pattern, 0, 1)
        self.pole_groups = QSpinBox()
        self.pole_groups.setRange(1, max(99, data['poles'], self.naa))
        self.position_branches = QSpinBox()
        self.position_branches.setRange(1, max(99, self.naa))
        plan = preferred_division_plan(
            self.pattern.currentText(), data['slots'], data['poles'],
            data['layers'], self.naa, data['shifts'], data['phases'])
        proposed = ((plan['pole_divider'], plan['position_divider'])
                    if plan['status'] == 'candidate' else None)
        initial = self.preferred_rules.get(self.pattern.currentText()) or proposed
        self.pole_groups.setValue(initial[0] if initial else 1)
        self.position_branches.setValue(initial[1] if initial else self.naa)
        controls.addWidget(QLabel("Pole regions (P)"), 1, 0)
        controls.addWidget(self.pole_groups, 1, 1)
        controls.addWidget(QLabel("Branches per region (R)"), 1, 2)
        controls.addWidget(self.position_branches, 1, 3)
        layout.addLayout(controls)

        factors = [p for p in range(1, min(data['poles'], self.naa)+1)
                   if data['poles'] % p == 0 and self.naa % p == 0]
        self.options = [(pattern, p, self.naa // p)
                        for pattern in self.patterns for p in factors]
        pp = data['poles'] // 2
        pole_labels = [f"{p} ({'pp' if p == pp else 'pp/2' if 2*p == pp else 'whole' if p == 1 else '2pp' if p == data['poles'] else 'factor'})"
                       for p in factors]
        position_labels = sorted({self.naa // p for p in factors})
        twice_q = 2 * data['q']
        r_labels = [f"{r} (q×2)" if r == twice_q else str(r) for r in position_labels]
        hint = QLabel("Available factors — P: " + ", ".join(pole_labels) +
                      "  |  R: " + ", ".join(r_labels) +
                      ". Enter any positive integer to test a custom factor.")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.table = QTableWidget(len(self.options), 4)
        self.table.setHorizontalHeaderLabels(["Pattern", "Division", "Candidate status", "Draft preferred"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.cellClicked.connect(self._choose_pattern_row)
        layout.addWidget(self.table)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        actions = QHBoxLayout()
        self.preview_button = QPushButton("Preview selected rule")
        self.preview_button.clicked.connect(self.preview_rule)
        actions.addWidget(self.preview_button)
        self.mark_preferred_button = QPushButton("Mark draft preferred")
        self.mark_preferred_button.clicked.connect(self.mark_preferred)
        actions.addWidget(self.mark_preferred_button)
        actions.addStretch()
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        actions.addWidget(close_button)
        layout.addLayout(actions)

        self.pole_groups.valueChanged.connect(self._pole_changed)
        self.position_branches.valueChanged.connect(self.refresh)
        self.pattern.currentTextChanged.connect(self.refresh)
        self.refresh()

    def _pole_changed(self, value):
        if self.naa % value == 0:
            self.position_branches.setValue(self.naa // value)
        self.refresh()

    def _choose_pattern_row(self, row, _column):
        pattern, p, r = self.options[row]
        self.pattern.setCurrentText(pattern)
        self.pole_groups.setValue(p)
        self.position_branches.setValue(r)

    def _evaluate(self, pattern, division_rule=None):
        from branch_start_preview import evaluate_division_rule

        p, r = division_rule or (self.pole_groups.value(), self.position_branches.value())
        data = self.owner.phase_preview
        if p * r != self.naa:
            return None, "P × R must equal Naa."
        try:
            plan = evaluate_division_rule(pattern, data['slots'], data['poles'],
                                          data['layers'], self.naa, data['shifts'],
                                          (p, r), data['phases'])
        except (ValueError, TypeError) as exc:
            return None, str(exc)
        return plan, plan['reason']

    def refresh(self, _value=None):
        for row, (pattern, p, r) in enumerate(self.options):
            plan, reason = self._evaluate(pattern, (p, r))
            status = (f"{plan['symmetry'].capitalize()} candidate"
                      if plan and plan['status'] == 'candidate' else "Unavailable")
            preferred = self.preferred_rules.get(pattern) == (p, r)
            values = (pattern, f"{p} × {r}", status,
                      "Draft preferred" if preferred else "")
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
        plan, reason = self._evaluate(self.pattern.currentText())
        self.status.setText(f"{self.pattern.currentText()}: {reason} "
                            "Candidate status does not validate connection paths or branch EMF.")
        current = (self.owner.current_view_type == "phase" and
                   self.owner._manual_preview_signature() ==
                   self.owner._phase_input_signature)
        if not current:
            self.status.setText("Inputs changed. Plot Phase Division again before testing rules.")
        self.preview_button.setEnabled(bool(current and plan and plan['status'] == 'candidate'))
        self.mark_preferred_button.setEnabled(self.preview_button.isEnabled())

    def preview_rule(self):
        pattern = self.pattern.currentText()
        if self.owner._preview_branch_division(pattern,
                                                (self.pole_groups.value(),
                                                 self.position_branches.value())):
            self.status.setText(f"Previewing {pattern}: P={self.pole_groups.value()}, "
                                f"R={self.position_branches.value()}. Candidate only.")
        else:
            self.status.setText("Preview unavailable. Check the rule and refresh Phase Division if inputs changed.")

    def mark_preferred(self):
        pattern = self.pattern.currentText()
        plan, reason = self._evaluate(pattern)
        if plan and plan['status'] == 'candidate':
            self.preferred_rules[pattern] = (self.pole_groups.value(),
                                              self.position_branches.value())
            self.refresh()
            self.status.setText(f"Draft preferred rule for {pattern} recorded for this session.")


class VDOptimizeWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, problem, algorithm_id, time_budget_sec, initial_adjustments):
        super().__init__()
        self.problem = problem
        self.algorithm_id = algorithm_id
        self.time_budget_sec = time_budget_sec
        self.initial_adjustments = initial_adjustments

    def run(self):
        try:
            result = vdo.optimize(
                self.problem,
                self.algorithm_id,
                time_budget_sec=self.time_budget_sec,
                initial_adjustments=self.initial_adjustments,
            )
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class InletPositionDialog(QDialog):
    OPTIMIZE_MODES = [
        "Outer layer, nearest slots",
        "Inner layer, nearest slots",
        "Same slot, nearest layers",
        "Inlets and outlets compact",
    ]

    def __init__(self, parent, branch_count, initial_values, force_even=False):
        super().__init__(parent)
        self.parent_app = parent
        self.branch_count = branch_count
        self.force_even = force_even
        self.applied_values = None
        self.setWindowTitle("Config. terminals")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        header = QLabel("index adjustment")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        self.input_boxes = []
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        validator = QIntValidator(-999999, 999999, self)
        values = list(initial_values[:branch_count]) + [0] * max(0, branch_count - len(initial_values))
        for index in range(branch_count):
            label = QLabel(f"Branch {index + 1}")
            edit = QLineEdit(str(int(values[index])))
            edit.setValidator(validator)
            edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            edit.setFixedWidth(90)
            grid.addWidget(label, index, 0)
            grid.addWidget(edit, index, 1)
            self.input_boxes.append(edit)
        layout.addLayout(grid)

        optimize_layout = QHBoxLayout()
        self.optimize_mode_box = QComboBox()
        self.optimize_mode_box.addItems(self.OPTIMIZE_MODES)
        optimize_layout.addWidget(self.optimize_mode_box, 1)
        optimize_button = QPushButton("Busbar Optimize")
        optimize_button.clicked.connect(self.optimize_inputs)
        optimize_layout.addWidget(optimize_button)
        layout.addLayout(optimize_layout)

        self.warning_label = QLabel("")
        self.warning_label.setWordWrap(True)
        layout.addWidget(self.warning_label)

        buttons_layout = QHBoxLayout()
        apply_button = QPushButton("Apply")
        reset_button = QPushButton("Reset")
        cancel_button = QPushButton("Cancel")
        apply_button.clicked.connect(self.apply_values)
        reset_button.clicked.connect(self.reset_values)
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(apply_button)
        buttons_layout.addWidget(reset_button)
        buttons_layout.addWidget(cancel_button)
        layout.addLayout(buttons_layout)

    def read_values(self):
        values = []
        for index, edit in enumerate(self.input_boxes, start=1):
            text = edit.text().strip()
            if text in ("", "+", "-"):
                raise ValueError(f"Branch {index} adjustment must be an integer.")
            values.append(int(text))
        if self.force_even:
            odd_branches = [str(i + 1) for i, value in enumerate(values) if value % 2 != 0]
            if odd_branches:
                raise ValueError(
                    "ZPP/LPP require weld-side inlet parity; odd adjustment is not allowed for Branch "
                    + ", ".join(odd_branches)
                    + "."
                )
        return values

    def apply_values(self):
        try:
            self.applied_values = self.read_values()
        except ValueError as exc:
            self.warning_label.setText(f"Warning: {exc}")
            return
        self.accept()

    def reset_values(self):
        for edit in self.input_boxes:
            edit.setText("0")
        self.warning_label.setText("")

    def optimize_inputs(self):
        try:
            values = self.parent_app.compute_phase_a_inlet_optimization(self.optimize_mode_box.currentText())
        except Exception as exc:
            self.warning_label.setText(f"Warning: optimization failed: {exc}")
            return
        for edit, value in zip(self.input_boxes, values):
            edit.setText(str(int(value)))
        self.warning_label.setText("Optimized inputs filled. Click Apply to commit.")


class DetachedPlotWindow(QDialog):
    """Closing the secondary window returns the existing canvas to its owner."""

    def __init__(self, owner, embed_callback=None, title="Winding Design Tool — Plot"):
        super().__init__(owner, Qt.WindowType.Window)
        self.owner = owner
        self.embed_callback = embed_callback or owner.embed_plot
        self.setWindowTitle(title)
        self.resize(1000, 850)
        self.setMinimumSize(400, 300)
        self.content_layout = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addStretch()
        self.embed_button = QPushButton("Embed Plot")
        self.embed_button.setProperty("compactAction", True)
        self.embed_button.clicked.connect(self.embed_callback)
        header.addWidget(self.embed_button)
        self.content_layout.addLayout(header)

    def closeEvent(self, event):
        self.embed_callback()
        event.accept()

    def reject(self):
        # Escape must not hide the dialog while leaving the canvas detached.
        self.embed_callback()


class ElidedLabel(QLabel):
    """Single-line label that preserves its full text in a tooltip."""

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._full_text = ""
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.set_summary_text(text)

    def set_summary_text(self, text):
        self._full_text = str(text)
        self.setToolTip(self._full_text)
        self._refresh_elision()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_elision()

    def _refresh_elision(self):
        available = max(20, self.width() - 4)
        super().setText(self.fontMetrics().elidedText(
            self._full_text, Qt.TextElideMode.ElideRight, available))


class WindingApp(ConfigIOMixin, ResultExportMixin, InductanceUIMixin, QWidget):
    _detached_plot_window_class = DetachedPlotWindow
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Winding Design Tool")
        self.setGeometry(100, 100, 1200, 700)
        self.input_fields = {}  # ✅ Initialize once here
        self._option_help_buttons = {}
        self.inlet_index_adjustments_phase_a = []
        self.volt_diff_inlet_adjustments_all = []
        self.diagnostic_log = DiagnosticLog(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "winding_design_errors.jsonl")
        )
        self.initUI()

    def _record_unexpected_error(self, context, exc):
        metadata = {"current_view": getattr(self, "current_view_type", "uninitialized")}
        if hasattr(self, "tabs") and self.tabs.currentIndex() >= 0:
            metadata["tab"] = self.tabs.tabText(self.tabs.currentIndex())
        try:
            if isinstance(exc, OSError):
                category = "file"
            elif isinstance(exc, (ValueError, json.JSONDecodeError)):
                category = "input"
            else:
                category = "internal"
            return self.diagnostic_log.record_exception(context, exc, metadata, category=category)
        except OSError:
            return "diagnostic-log-unavailable"

    def initUI(self):
        self.setMinimumSize(860, 480)

        final_layout = QVBoxLayout(self)
        final_layout.setContentsMargins(8, 8, 8, 8)
        final_layout.setSpacing(8)

        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(8)

        upper_container = QWidget()
        upper_layout = QVBoxLayout(upper_container)
        upper_layout.setContentsMargins(0, 0, 0, 0)
        upper_layout.setSpacing(8)

        self.upper_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.upper_splitter.setChildrenCollapsible(False)

        left_container = QWidget()
        left_container.setMinimumWidth(480)
        left_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        self.left_splitter = QSplitter(Qt.Orientation.Vertical)
        self.left_splitter.setChildrenCollapsible(False)
        self.left_splitter.setHandleWidth(8)

        left_top = QWidget()
        left_top_layout = QVBoxLayout(left_top)
        left_top_layout.setContentsMargins(0, 0, 0, 0)
        left_top_layout.setSpacing(6)

        self.tabs = QTabWidget()
        self.tabs.setMinimumWidth(480)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.addTab(self.create_winding_params_tab(), "Winding")
        self.tabs.addTab(self.create_stator_params_tab(), "Stator")
        self.tabs.addTab(self.create_inslot_params_tab(), "Inslot")
        self.tabs.addTab(self.create_endwinding_params_tab(), "End Winding")
        self.tabs.addTab(self.create_layout_params_tab(), "Layout")
        self.tabs.addTab(self.create_transp_params_tab(), "Transposition")
        self.tabs.addTab(self.create_figure_params_tab(), "Figure")
        self.tabs.addTab(self.create_plot_config_tab(), "Plot Config")
        self.tabs.addTab(self.create_wf_params_tab(), "Winding Factor")
        self.tabs.addTab(self.create_volt_diff_tab(), "Volt Diff")
        self.tabs.addTab(self.create_inductance_tab(), "Inductance")
        left_top_layout.addWidget(self.tabs)

        self.workflow_container = QFrame()
        self.workflow_container.setProperty("workflowPanel", True)
        workflow_outer_layout = QVBoxLayout(self.workflow_container)
        workflow_outer_layout.setContentsMargins(8, 6, 8, 8)
        workflow_outer_layout.setSpacing(5)
        workflow_title = QLabel("Workflow")
        workflow_title.setProperty("sectionTitle", True)
        workflow_outer_layout.addWidget(workflow_title)
        self.workflow_layout = QGridLayout()
        self.workflow_layout.setContentsMargins(0, 0, 0, 0)
        self.workflow_layout.setHorizontalSpacing(8)
        self.workflow_layout.setVerticalSpacing(6)
        self.workflow_layout.setColumnStretch(0, 1)
        self.workflow_layout.setColumnStretch(1, 1)
        workflow_outer_layout.addLayout(self.workflow_layout)
        self.quick_analysis_container = self.workflow_container
        self.phase_actions = self.workflow_container

        self.analyze_button = QPushButton("Parameter Analyze")
        self.analyze_button.clicked.connect(self.analyze_parameters)
        self.configure_command_button(self.analyze_button)
        self.workflow_layout.addWidget(self.analyze_button, 0, 0)

        self.layout_analyze_button = QPushButton("Layout Analyze")
        self.layout_analyze_button.clicked.connect(self.analyze_layouts)
        self.configure_command_button(self.layout_analyze_button)
        self.workflow_layout.addWidget(self.layout_analyze_button, 0, 1)

        self.phase_plot_button = QPushButton("Plot Phase Division")
        self.configure_command_button(self.phase_plot_button)
        self.phase_plot_button.setProperty("secondaryAction", True)
        self.phase_plot_button.clicked.connect(self.preview_phase_division)
        self.workflow_layout.addWidget(self.phase_plot_button, 1, 0)

        self.plot_button = QPushButton("Plot Layout")
        self.plot_button.clicked.connect(self.plot_layout)
        self.configure_command_button(self.plot_button)
        self.plot_button.setProperty("primaryAction", True)
        self.workflow_layout.addWidget(self.plot_button, 1, 1)
        left_top_layout.addWidget(self.workflow_container)

        self.dependent_params_display = QTextEdit()
        self.dependent_params_display.setReadOnly(True)
        self.dependent_params_display.setPlaceholderText("Dependent parameters will appear here...")
        self.configure_text_panel(self.dependent_params_display)

        self.layout_display = QTextEdit()
        self.layout_display.setReadOnly(True)
        self.layout_display.setPlaceholderText("Layout info will appear here...")
        self.configure_text_panel(self.layout_display)

        self.left_info_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.left_info_splitter.setChildrenCollapsible(False)
        self.result_windows = {}
        self.result_window_buttons = {}
        self.result_collapse_buttons = {}
        self.result_summary_labels = {}
        self.result_containers = {}
        self.result_expanded = {}
        self.result_panel_layouts = {}
        self.result_panels = {"parameters": self.dependent_params_display,
                              "layout": self.layout_display}
        self.result_titles = {"parameters": "Dependent Parameters", "layout": "Layout Info"}
        for key, panel in self.result_panels.items():
            container = QWidget()
            panel_layout = QVBoxLayout(container)
            panel_layout.setContentsMargins(0, 0, 0, 0)
            panel_layout.setSpacing(4)
            header = QHBoxLayout()
            collapse = QPushButton("▸")
            collapse.setProperty("compactAction", True)
            collapse.setFixedWidth(30)
            collapse.setToolTip("Expand this result")
            collapse.clicked.connect(lambda checked=False, key=key: self.toggle_result_panel(key))
            header.addWidget(collapse)
            title = QLabel(self.result_titles[key])
            title.setProperty("sectionTitle", True)
            header.addWidget(title)
            header.addStretch()
            button = QPushButton("Pop Out")
            button.setProperty("compactAction", True)
            button.setToolTip("Open this result in a resizable window")
            button.clicked.connect(lambda checked=False, key=key: self.toggle_result_window(key))
            header.addWidget(button)
            panel_layout.addLayout(header)
            summary = ElidedLabel("No results yet.")
            summary.setProperty("resultSummary", True)
            panel_layout.addWidget(summary)
            panel_layout.addWidget(panel, 1)
            panel.setMinimumHeight(0)
            panel.hide()
            panel.textChanged.connect(lambda key=key: self._update_result_summary(key))
            self.result_window_buttons[key] = button
            self.result_collapse_buttons[key] = collapse
            self.result_summary_labels[key] = summary
            self.result_containers[key] = container
            self.result_expanded[key] = False
            self.result_panel_layouts[key] = panel_layout
            container.installEventFilter(self)
            self.left_info_splitter.addWidget(container)
        self.left_info_splitter.setSizes([70, 70])

        self.left_splitter.addWidget(left_top)
        self.left_splitter.addWidget(self.left_info_splitter)
        self.left_splitter.setSizes([520, 180])
        self._left_splitter_normal_sizes = self.left_splitter.sizes()
        self.left_splitter.splitterMoved.connect(self._remember_left_splitter_sizes)
        left_layout.addWidget(self.left_splitter)
        self.upper_splitter.addWidget(left_container)

        figure_container = QWidget()
        self.figure_container = figure_container
        figure_layout = QVBoxLayout()
        self.figure_layout = figure_layout
        figure_layout.setContentsMargins(0, 0, 0, 0)
        self.plot_toolbar = QWidget()
        plot_toolbar_layout = QVBoxLayout(self.plot_toolbar)
        plot_toolbar_layout.setContentsMargins(0, 0, 0, 0)
        plot_toolbar_layout.setSpacing(4)
        plot_primary_row = QHBoxLayout()
        plot_primary_row.setContentsMargins(0, 0, 0, 0)
        self.plot_view_title = QLabel("Plot Preview")
        self.plot_view_title.setProperty("sectionTitle", True)
        plot_primary_row.addWidget(self.plot_view_title)
        plot_primary_row.addStretch()
        self.branch_division_button = QPushButton("Branch Division...")
        self.branch_division_button.setProperty("compactAction", True)
        self.branch_division_button.clicked.connect(self.open_branch_division)
        plot_primary_row.addWidget(self.branch_division_button)
        self.branch_division_button.hide()
        self.phase_fit_button = QPushButton("Fit View")
        self.plot_fit_button = self.phase_fit_button
        self.phase_fit_button.setProperty("compactAction", True)
        self.phase_fit_button.setToolTip("Restore the complete current plot after zooming")
        self.phase_fit_button.clicked.connect(self.fit_plot_view)
        self.phase_fit_button.setEnabled(False)
        plot_primary_row.addWidget(self.phase_fit_button)
        self.plot_window_button = QPushButton("Detach Plot")
        self.plot_window_button.setProperty("compactAction", True)
        self.plot_window_button.clicked.connect(self.toggle_plot_window)
        plot_primary_row.addWidget(self.plot_window_button)
        plot_toolbar_layout.addLayout(plot_primary_row)

        self.phase_view_controls = QWidget()
        phase_view_layout = QHBoxLayout(self.phase_view_controls)
        phase_view_layout.setContentsMargins(0, 0, 0, 0)
        phase_view_layout.setSpacing(8)
        phase_view_layout.addStretch()
        phase_view_layout.addWidget(QLabel("View:"))
        self.phase_view_selector = QComboBox()
        self.phase_view_selector.addItems(["Circular", "Unwrapped"])
        self.phase_view_selector.setCurrentText("Unwrapped")
        self.phase_view_selector.setToolTip("View the same phase mapping without generating connections.")
        self.phase_view_selector.currentTextChanged.connect(self._render_phase_preview)
        phase_view_layout.addWidget(self.phase_view_selector)
        self.phase_cond_phase_label = QLabel("Cond/Phase: —")
        self.phase_cond_phase_label.setProperty("fieldLabel", True)
        self.phase_cond_phase_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.phase_cond_phase_label.setToolTip("Number of phase-assigned conductors for each phase")
        phase_view_layout.addWidget(self.phase_cond_phase_label)
        plot_toolbar_layout.addWidget(self.phase_view_controls)
        self.phase_view_controls.hide()
        self.phase_start_controls = QWidget()
        start_layout = QVBoxLayout(self.phase_start_controls)
        start_layout.setContentsMargins(0, 0, 0, 0)
        start_row = QHBoxLayout()
        self.phase_start_mode = QCheckBox("Manual starts")
        self.phase_start_mode.setToolTip("Candidate preview only; click a conductor after selecting a branch.")
        self.phase_start_mode.toggled.connect(self._toggle_manual_starts)
        start_row.addWidget(self.phase_start_mode)
        self.phase_start_help = self._make_option_help_button()
        self.phase_start_help.hide()
        start_row.addWidget(self.phase_start_help)
        self.phase_start_branch = QComboBox()
        self.phase_start_branch.setEnabled(False)
        self.phase_start_branch.currentIndexChanged.connect(self._manual_branch_changed)
        start_row.addWidget(self.phase_start_branch, 1)
        self.phase_start_reset = QPushButton("Reset starts")
        self.phase_start_reset.setProperty("compactAction", True)
        self.phase_start_reset.clicked.connect(self._reset_manual_starts)
        start_row.addWidget(self.phase_start_reset)
        phase_view_layout.insertLayout(0, start_row)
        self.phase_start_status = QLabel("Enable Manual starts to select candidate inlet positions.")
        self.phase_start_status.setWordWrap(True)
        start_layout.addWidget(self.phase_start_status)
        plot_toolbar_layout.addWidget(self.phase_start_controls)
        self.phase_start_controls.hide()
        self.branch_division_dialog = None
        self._branch_division_preferences = {}
        self._manual_start_context = None
        self._manual_start_results = {}
        self.winding_view_controls = QWidget()
        winding_view_layout = QHBoxLayout(self.winding_view_controls)
        winding_view_layout.setContentsMargins(0, 0, 0, 0)
        winding_view_layout.addStretch()
        winding_view_layout.addWidget(QLabel("View:"))
        self.winding_view_selector = QComboBox()
        self.winding_view_selector.addItems(["Circular", "Unwrapped"])
        self.winding_view_selector.setCurrentText("Unwrapped")
        self.winding_view_selector.setEnabled(False)
        self.winding_view_selector.setToolTip(
            "View the last plotted layout. Unwrapped shows all slots; rotation, CW, "
            "radii and Figure Division apply only to Circular.")
        self.winding_view_selector.currentTextChanged.connect(self._render_winding_view)
        winding_view_layout.addWidget(self.winding_view_selector)
        winding_view_layout.addWidget(QLabel("Phase:"))
        self.winding_phase_selector = QComboBox()
        self.winding_phase_selector.addItem("All", None)
        self.winding_phase_selector.setEnabled(False)
        self.winding_phase_selector.setToolTip("Draw all branches of one phase, or all phases.")
        self.winding_phase_selector.currentIndexChanged.connect(self._winding_phase_changed)
        winding_view_layout.addWidget(self.winding_phase_selector)
        winding_view_layout.addWidget(QLabel("Branch:"))
        self.winding_branch_selector = QComboBox()
        self.winding_branch_selector.addItem("All", None)
        self.winding_branch_selector.setEnabled(False)
        self.winding_branch_selector.setToolTip(
            "Choose one branch within the selected phase.")
        self.winding_branch_selector.currentIndexChanged.connect(self._render_winding_view)
        winding_view_layout.addWidget(self.winding_branch_selector)
        plot_toolbar_layout.addWidget(self.winding_view_controls)
        self.winding_view_controls.hide()
        self._winding_plot_data = None
        self._winding_candidate = False
        figure_layout.addWidget(self.plot_toolbar)
        self.plot_placeholder = QLabel("Plot is open in a separate window.\nClick Embed Plot to bring it back.")
        self.plot_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.plot_placeholder.setWordWrap(True)
        self.plot_placeholder.hide()
        figure_layout.addWidget(self.plot_placeholder, 1)
        self.plot_window = None
        self.figure, self.ax = plt.subplots(figsize=(8, 8), dpi=100)
        self.figure.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
        self.ax.axis("off")
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.canvas.setToolTip("Mouse wheel: zoom at cursor")

        self.vd_figure = Figure(figsize=(8, 4), dpi=100)
        self.vd_ax = self.vd_figure.add_subplot(1, 1, 1)
        self.vd_ax.axis("off")
        self.vd_canvas = FigureCanvas(self.vd_figure)
        self.vd_canvas.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.vd_canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.vd_canvas.setToolTip("Mouse wheel: zoom at cursor")
        self.vd_plot_scroll_area = QScrollArea()
        self.vd_plot_scroll_area.setWidgetResizable(True)
        self.vd_plot_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.vd_plot_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.vd_plot_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.vd_plot_scroll_area.setWidget(self.vd_canvas)

        self.plot_stack = QStackedWidget()
        self.plot_stack.addWidget(self.canvas)
        self.plot_stack.addWidget(self.vd_plot_scroll_area)
        self.plot_stack.setCurrentWidget(self.canvas)
        figure_layout.addWidget(self.plot_stack)
        figure_container.setLayout(figure_layout)
        self.upper_splitter.addWidget(figure_container)
        self.upper_splitter.setStretchFactor(0, 0)
        self.upper_splitter.setStretchFactor(1, 1)
        self.upper_splitter.setSizes([600, 780])

        upper_layout.addWidget(self.upper_splitter, 1)

        action_container = QWidget()
        self.action_container = action_container
        action_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        action_layout = QGridLayout(action_container)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setHorizontalSpacing(8)
        action_layout.setVerticalSpacing(4)
        action_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.action_layout = action_layout
        self.action_button_width = 200

        self.actions_toggle = QPushButton("Actions ▾")
        self.actions_toggle.setCheckable(True)
        self.actions_toggle.setProperty("compactAction", True)
        self.actions_toggle.setToolTip("Hide or show bottom actions")
        self.actions_toggle.toggled.connect(self._toggle_action_buttons)
        action_layout.addWidget(self.actions_toggle, 0, 0)

        self.init_calc_button = QPushButton("Initial End Winding Calculation")
        self.init_calc_button.clicked.connect(self.initial_end_winding_calc)
        self.configure_command_button(self.init_calc_button, 210)
        action_layout.addWidget(self.init_calc_button, 0, 1)

        self.import_config_button = QPushButton("Import Config")
        self.import_config_button.clicked.connect(self.import_config)
        self.configure_command_button(self.import_config_button, 140)
        action_layout.addWidget(self.import_config_button, 0, 2)

        self.export_config_button = QPushButton("Export Config")
        self.export_config_button.clicked.connect(self.export_config)
        self.configure_command_button(self.export_config_button, 140)
        action_layout.addWidget(self.export_config_button, 0, 3)

        self.save_layout_button = QPushButton("Save layout as figure")
        self.save_layout_button.clicked.connect(self.save_layout_as_figure)
        self.configure_command_button(self.save_layout_button, 180)
        action_layout.addWidget(self.save_layout_button, 1, 0)

        self.export_branch_sheet_button = QPushButton("Export Branch Sheets")
        self.export_branch_sheet_button.clicked.connect(self.export_branch_connection_sheets)
        self.configure_command_button(self.export_branch_sheet_button, 190)
        action_layout.addWidget(self.export_branch_sheet_button, 1, 1)

        self.model_3d_button = QPushButton("3D model")
        self.model_3d_button.clicked.connect(self.load_3d_model)
        self.configure_command_button(self.model_3d_button, 120)
        self.model_3d_button.setEnabled(False)
        self.model_3d_button.setToolTip("Coming soon")
        action_layout.addWidget(self.model_3d_button, 1, 2)

        self.config_jmag_button = QPushButton("Config. in JMAG")
        self.config_jmag_button.clicked.connect(self.config_in_jmag)
        self.configure_command_button(self.config_jmag_button, 150)
        self.config_jmag_button.setEnabled(False)
        self.config_jmag_button.setToolTip("Coming soon")
        action_layout.addWidget(self.config_jmag_button, 1, 3)
        self.action_buttons = [self.init_calc_button, self.import_config_button,
                               self.export_config_button, self.save_layout_button,
                               self.export_branch_sheet_button, self.model_3d_button,
                               self.config_jmag_button]
        for button in self.action_buttons:
            button.setProperty("compactAction", True)
            button.setFixedWidth(self.action_button_width)
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.actions_toggle.setFixedWidth(88)
        self.actions_toggle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        upper_layout.addWidget(action_container)

        self.message_log = QTextEdit()
        self.message_log.setReadOnly(True)
        self.message_log.setPlaceholderText("System messages...")
        self.configure_text_panel(self.message_log, min_height=120)

        self.result_display = QTextEdit()
        self.result_display.setReadOnly(True)
        self.result_display.setPlaceholderText("Calculation results...")
        self.configure_text_panel(self.result_display, min_height=120)
        self._calculation_result_sections = {}

        self.bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.bottom_splitter.setChildrenCollapsible(False)
        self.bottom_splitter.addWidget(self.message_log)
        self.bottom_splitter.addWidget(self.result_display)
        self.bottom_splitter.setMinimumHeight(120)
        self.bottom_splitter.setSizes([780, 760])

        self.main_splitter.addWidget(upper_container)
        self.main_splitter.addWidget(self.bottom_splitter)
        self.main_splitter.setStretchFactor(0, 5)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([760, 150])
        final_layout.addWidget(self.main_splitter)
        self.tabs.currentChanged.connect(self._sync_tab_context_layout)
        self._sync_tab_context_layout(self.tabs.currentIndex())
        self._prepare_classic_tabs()
        self.current_view_type = "empty"
        self.phase_preview = None
        self._update_plot_toolbar()
        self.canvas.mpl_connect("resize_event", self._on_plot_resize)
        self.canvas.mpl_connect("scroll_event", self._zoom_plot_event)
        self.canvas.mpl_connect("button_press_event", self._pick_manual_start)
        self.vd_canvas.mpl_connect("scroll_event", self._zoom_plot_event)
        self.apply_settings(silent=True)
        for key in ('num_layers', 'num_phases'):
            self.input_fields[key].textChanged.connect(
                lambda _value: self._refresh_divider_status())
        for key in ('phase_shift_pattern', 'tp_type'):
            self.input_fields[key].currentTextChanged.connect(
                lambda _value: self._refresh_divider_status())
        for key in ('radial_shift', 'inlet_from_weld_side'):
            self.input_fields[key].toggled.connect(
                lambda _value: self._refresh_divider_status())
            self.input_fields[key].toggled.connect(
                lambda _value: self._refresh_route_option_availability())
        self.input_fields["in_out_connection"].toggled.connect(
            lambda _value: self._refresh_connect_ends_availability())
        for field in self.tp_fields.values():
            field.textChanged.connect(lambda _value: self._refresh_divider_status())
        for prefix in ('pole_n', 'pole_s'):
            self.input_fields[f'{prefix}_tp_type'].currentTextChanged.connect(
                lambda _value: self._refresh_divider_status())
            for key in ('tp_interval', 'tp_times', 'uni_tp', 'pltp_fl',
                        'pltp_ll', 'jltp'):
                self.input_fields[f'{prefix}_{key}'].textChanged.connect(
                    lambda _value: self._refresh_divider_status())
        for key, _ in self._manual_preview_signature():
            field = self.input_fields[key]
            signal = (field.currentTextChanged if isinstance(field, QComboBox) else
                      field.toggled if isinstance(field, QCheckBox) else field.textChanged)
            signal.connect(self._invalidate_manual_starts)
        for field in self.input_fields.values():
            signal = (field.currentTextChanged if isinstance(field, QComboBox) else
                      field.toggled if isinstance(field, QCheckBox) else
                      field.textChanged if isinstance(field, QLineEdit) else None)
            if signal is not None:
                signal.connect(self._mark_auto_configuration_pending)
        self._pattern_support_cache = {}
        self._pattern_support_timer = QTimer(self)
        self._pattern_support_timer.setSingleShot(True)
        self._pattern_support_timer.timeout.connect(self._refresh_pattern_availability)
        for key in ("q", "num_slots", "num_poles", "ab", "num_layers", "num_phases"):
            self.input_fields[key].textChanged.connect(self._schedule_pattern_availability)
        self.input_fields["winding_input_mode"].currentIndexChanged.connect(
            self._schedule_pattern_availability)
        self.input_fields["pattern_name"].textChanged.connect(
            lambda _text: self._mark_selected_pattern_unavailable())
        self.input_fields["pattern_name"].textChanged.connect(
            self._schedule_pattern_availability)
        self.input_fields["pattern_name"].textChanged.connect(
            self._sync_dividers_from_inputs)
        self.input_fields["pattern_name"].textChanged.connect(
            lambda _text: self._refresh_current_layout_pattern_hint())
        self.input_fields["pattern_name"].textChanged.connect(
            lambda _text: self._refresh_route_option_availability())
        self._pole_group_guidance_timer = QTimer(self)
        self._pole_group_guidance_timer.setSingleShot(True)
        self._pole_group_guidance_timer.timeout.connect(
            self._refresh_pole_group_guidance)
        for key in ("phase_shift", "PSL"):
            self.input_fields[key].textChanged.connect(
                lambda _value: self._pole_group_guidance_timer.start(150))
        self.input_fields["phase_shift_pattern"].currentTextChanged.connect(
            lambda _value: self._pole_group_guidance_timer.start(150))
        for key in ("radial_shift", "inlet_from_weld_side"):
            self.input_fields[key].toggled.connect(
                lambda _value: self._pole_group_guidance_timer.start(150))
        for key in ("num_layers", "num_phases", "ab", "phase_shift", "PSL"):
            self.input_fields[key].textChanged.connect(
                lambda _value: self._refresh_route_option_availability())
        self.input_fields["phase_shift_pattern"].currentTextChanged.connect(
            lambda _value: self._refresh_route_option_availability())
        for key in ("q_divider", "pp_divider", "p2_divider"):
            self.input_fields[key].currentTextChanged.connect(
                lambda _value: self._refresh_route_option_availability())
        self._refresh_pattern_availability()
        self._refresh_current_layout_pattern_hint()
        self._connect_inductance_invalidation()

    def _prepare_classic_tabs(self):
        """Keep the 7.4 tab layout while allowing access to long parameter forms."""
        pages = [(self.tabs.widget(i), self.tabs.tabText(i)) for i in range(self.tabs.count())]
        self.tabs.blockSignals(True)
        self.tabs.clear()
        for page, name in pages:
            page.setProperty("parameterPage", True)
            page.layout().setAlignment(Qt.AlignmentFlag.AlignTop)
            for form in page.findChildren(QFormLayout):
                form.setContentsMargins(16, 14, 16, 14)
                form.setHorizontalSpacing(16)
                form.setVerticalSpacing(10)
                form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
                form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
                form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            for label in page.findChildren(QLabel):
                label.setWordWrap(True)
            for combo in page.findChildren(QComboBox):
                if combo.objectName() == "windingInputMode":
                    combo.setFixedWidth(150)
                    combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                    continue
                if combo.objectName() == "layoutPatternSelector":
                    q_field = self.input_fields.get("q")
                    combo.setFixedWidth(q_field.maximumWidth() if q_field is not None else 100)
                    combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                    continue
                if combo.property("dividerCombo"):
                    combo.setFixedWidth(65)
                    continue
                combo.setMaximumWidth(16777215)
                if combo.property("compactCombo"):
                    combo.setMinimumWidth(120)
                    combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                    continue
                width = max((combo.fontMetrics().horizontalAdvance(combo.itemText(i))
                             for i in range(combo.count())), default=100) + 48
                combo.setMinimumWidth(max(140, width))
                combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidget(page)
            self.tabs.addTab(scroll, name)
        self.tabs.blockSignals(False)
        self.tabs.setCurrentIndex(0)
        QTimer.singleShot(0, self._align_divider_row)

    def _align_divider_row(self):
        """Keep the divider row no wider than the q field above it."""
        container = getattr(self, "divider_row_container", None)
        q_field = getattr(self, "input_fields", {}).get("q")
        page = getattr(self, "_winding_params_page", None)
        if container is None or q_field is None or page is None:
            return
        q_right = q_field.mapTo(page, QPoint(q_field.width(), 0)).x()
        left = container.geometry().left()
        target_width = max(container.minimumSizeHint().width(), q_right - left)
        if container.width() != target_width:
            container.setFixedWidth(target_width)
            container.updateGeometry()

    def configure_command_button(self, button, min_width=160):
        button.setMinimumSize(min_width, 34)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _toggle_action_buttons(self, hidden):
        for button in self.action_buttons:
            button.setVisible(not hidden)
        if hidden:
            self.action_layout.removeWidget(self.actions_toggle)
            self.actions_toggle.setParent(self.result_containers["parameters"])
            self.actions_toggle.setText("▸")
            self.actions_toggle.setToolTip("Show actions")
            self.actions_toggle.setFixedSize(24, 24)
            self.actions_toggle.show()
            self._position_collapsed_actions_toggle()
        else:
            self.action_layout.addWidget(self.actions_toggle, 0, 0)
            self.actions_toggle.setText("Actions ▾")
            self.actions_toggle.setToolTip("Hide or show bottom actions")
            self.actions_toggle.setFixedWidth(88)
            self.actions_toggle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            self.actions_toggle.show()
        self.action_container.setVisible(not hidden)
        self._update_action_area_height()

    def _update_action_area_height(self):
        if not hasattr(self, "action_container"):
            return
        button_height = self.init_calc_button.height()
        height = 0 if self.actions_toggle.isChecked() else button_height * 2 + 4
        self.action_container.setFixedHeight(height)
        self.action_container.updateGeometry()

    def _position_collapsed_actions_toggle(self):
        container = getattr(self, "result_containers", {}).get("parameters")
        toggle = getattr(self, "actions_toggle", None)
        if container is None or toggle is None or toggle.parentWidget() is not container:
            return
        horizontal_margin = 0
        vertical_margin = 4
        toggle.move(
            horizontal_margin,
            max(vertical_margin, container.height() - toggle.height() - vertical_margin),
        )
        toggle.raise_()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Resize:
            if watched is getattr(self, "result_containers", {}).get("parameters"):
                self._position_collapsed_actions_toggle()
            elif watched is getattr(self, "_winding_params_page", None):
                QTimer.singleShot(0, self._align_divider_row)
        return super().eventFilter(watched, event)

    def _on_plot_resize(self, _event):
        if self.current_view_type in {"phase", "winding"}:
            self.canvas.draw_idle()

    def _zoom_plot_event(self, event):
        """Zoom the active Matplotlib axes around the pointer without recomputing data."""
        axes = getattr(event, "inaxes", None)
        x, y = getattr(event, "xdata", None), getattr(event, "ydata", None)
        if axes is None or x is None or y is None:
            return
        button = getattr(event, "button", None)
        if button not in ("up", "down"):
            return
        zoom = 1.2 if button == "up" else 1 / 1.2
        x0, x1 = axes.get_xlim()
        y0, y1 = axes.get_ylim()
        x_span, y_span = abs(x1 - x0), abs(y1 - y0)
        if x_span <= 1e-12 or y_span <= 1e-12:
            return
        new_x_span, new_y_span = x_span / zoom, y_span / zoom
        x_fraction = (x - x0) / (x1 - x0)
        y_fraction = (y - y0) / (y1 - y0)
        axes.set_xlim(x - new_x_span * x_fraction, x + new_x_span * (1 - x_fraction), auto=True)
        axes.set_ylim(y - new_y_span * y_fraction, y + new_y_span * (1 - y_fraction), auto=True)
        self._scale_plot_labels(axes)
        canvas = getattr(event, "canvas", None)
        if canvas is not None:
            canvas.draw_idle()

    def _plot_label_artists(self, axes):
        """Return in-grid labels that should follow geometry zoom.

        Titles, axis captions, and legends are interface text. Keeping them at
        their configured size makes Phase Division and Plot Layout respond to
        zoom in the same way.
        """
        artists = [*axes.texts, *axes.get_xticklabels(), *axes.get_yticklabels()]
        unique = []
        seen = set()
        for artist in artists:
            if id(artist) not in seen and hasattr(artist, "get_fontsize") and hasattr(artist, "set_fontsize"):
                seen.add(id(artist))
                unique.append(artist)
        return unique

    def _reset_plot_label_scale(self, axes):
        """Store unzoomed extents and font sizes after a plot is drawn or rebuilt."""
        if not hasattr(self, "_plot_label_scales"):
            self._plot_label_scales = {}
        x0, x1 = axes.get_xlim()
        y0, y1 = axes.get_ylim()
        extent = max(1e-12, math.sqrt(abs(x1 - x0) * abs(y1 - y0)))
        self._plot_label_scales[id(axes)] = {
            "extent": extent,
            "xlim": tuple(axes.get_xlim()),
            "ylim": tuple(axes.get_ylim()),
            "fonts": [(artist, artist.get_fontsize()) for artist in self._plot_label_artists(axes)],
        }

    def _scale_plot_labels(self, axes):
        state = getattr(self, "_plot_label_scales", {}).get(id(axes))
        if state is None:
            self._reset_plot_label_scale(axes)
            state = self._plot_label_scales[id(axes)]
        x0, x1 = axes.get_xlim()
        y0, y1 = axes.get_ylim()
        extent = max(1e-12, math.sqrt(abs(x1 - x0) * abs(y1 - y0)))
        scale = max(0.45, min(4.0, state["extent"] / extent))
        for artist, base_size in state["fonts"]:
            artist.set_fontsize(max(3.0, base_size * scale))

    def fit_plot_view(self):
        """Restore the canonical view without rebuilding plot data or artists."""
        state = getattr(self, "_plot_label_scales", {}).get(id(self.ax))
        if state is None:
            if self.current_view_type == "phase":
                self.preview_phase_division()
            elif self.current_view_type == "winding":
                self.plot_layout()
            return
        self.ax.set_xlim(*state["xlim"], auto=True)
        self.ax.set_ylim(*state["ylim"], auto=True)
        for artist, base_size in state["fonts"]:
            artist.set_fontsize(base_size)
        self.canvas.draw_idle()

    def _apply_plot_background(self, theme):
        """Keep the engineering canvas light and readable in every application theme."""
        color = "#f6f7f9"
        for figure, axes, canvas in ((self.figure, self.ax, self.canvas),
                                     (self.vd_figure, self.vd_ax, self.vd_canvas)):
            figure.patch.set_facecolor(color)
            figure.patch.set_edgecolor(color)
            axes.set_facecolor("none")
            axes.patch.set_alpha(0.0)
            canvas.setStyleSheet(f"background: {color};")

    def toggle_plot_window(self):
        if self.plot_window is not None and self.plot_window.isVisible():
            self.embed_plot()
            return
        if self.plot_window is None:
            self.plot_window = DetachedPlotWindow(self)
            self.plot_window.embed_button.hide()
        self.plot_window.setStyleSheet(self.styleSheet())
        self.plot_window.content_layout.addWidget(self.plot_toolbar)
        self.plot_window.content_layout.addWidget(self.plot_stack, 1)
        self.plot_placeholder.show()
        self.plot_window_button.setText("Embed Plot")
        self.plot_window.show()
        self.plot_window.raise_()

    def embed_plot(self):
        if self.plot_window is None:
            return
        self.figure_layout.insertWidget(0, self.plot_toolbar)
        self.figure_layout.addWidget(self.plot_stack, 1)
        self.plot_placeholder.hide()
        self.plot_window.hide()
        self.plot_window_button.setText("Detach Plot")

    def toggle_wf_plot_window(self):
        if self.wf_plot_window is not None and self.wf_plot_window.isVisible():
            self.embed_wf_plot()
            return
        if self.wf_plot_window is None:
            self.wf_plot_window = DetachedPlotWindow(
                self,
                embed_callback=self.embed_wf_plot,
                title="Winding Design Tool — Winding Function",
            )
        self.wf_plot_window.setStyleSheet(self.styleSheet())
        self.wf_plot_window.content_layout.addWidget(self.canvas_wf, 1)
        self.wf_plot_placeholder.show()
        self.wf_detach_button.setText("Embed Plot")
        self.wf_plot_window.show()
        self.wf_plot_window.raise_()

    def embed_wf_plot(self):
        if getattr(self, "wf_plot_window", None) is None:
            return
        self.wf_plot_container_layout.addWidget(self.canvas_wf, 1)
        self.wf_plot_placeholder.hide()
        self.wf_plot_window.hide()
        self.wf_detach_button.setText("Detach Plot")

    def toggle_result_window(self, key):
        window = self.result_windows.get(key)
        if window is not None and window.isVisible():
            self.embed_result_panel(key)
            return
        if window is None:
            window = DetachedPlotWindow(
                self, embed_callback=lambda: self.embed_result_panel(key),
                title="Winding Design Tool — " + self.result_titles[key])
            window.embed_button.setText("Embed Result")
            window.resize(800, 600)
            self.result_windows[key] = window
        window.setStyleSheet(self.styleSheet())
        self.result_collapse_buttons[key].setEnabled(False)
        self.result_panels[key].setMinimumHeight(0)
        self.result_panels[key].show()
        window.content_layout.addWidget(self.result_panels[key], 1)
        window.show()
        window.raise_()

    def embed_result_panel(self, key):
        window = self.result_windows.get(key)
        if window is None:
            return
        self.result_panel_layouts[key].addWidget(self.result_panels[key], 1)
        window.hide()
        self.result_collapse_buttons[key].setEnabled(True)
        expanded = self.result_expanded[key]
        self.result_panels[key].setMinimumHeight(110 if expanded else 0)
        self.result_panels[key].setVisible(expanded)
        self.result_summary_labels[key].setVisible(not expanded)

    def toggle_result_panel(self, key):
        """Expand or collapse one embedded result without changing its content."""
        if key not in self.result_panels:
            return
        window = self.result_windows.get(key)
        if window is not None and window.isVisible():
            return
        expanded = not self.result_expanded[key]
        self.result_expanded[key] = expanded
        panel = self.result_panels[key]
        panel.setMinimumHeight(110 if expanded else 0)
        panel.setVisible(expanded)
        self.result_summary_labels[key].setVisible(not expanded)
        button = self.result_collapse_buttons[key]
        button.setText("▾" if expanded else "▸")
        button.setToolTip("Collapse this result" if expanded else "Expand this result")
        self.left_info_splitter.updateGeometry()

    def _update_result_summary(self, key):
        panel = self.result_panels[key]
        title = self.result_titles[key].rstrip(":").casefold()
        summary = "No results yet."
        for line in panel.toPlainText().splitlines():
            candidate = line.strip()
            if candidate and candidate.rstrip(":").casefold() != title:
                summary = candidate
                break
        self.result_summary_labels[key].set_summary_text(summary)

    def closeEvent(self, event):
        thread = getattr(self, "vd_optimize_thread", None)
        if thread is not None and thread.isRunning():
            event.ignore()
            self.message_log.append("Volt Diff optimization is running; close the window after it finishes.")
            return
        self.embed_plot()
        self.embed_wf_plot()
        if hasattr(self, "inductance_matrix_window"):
            self.embed_inductance_matrix()
        for key in self.result_windows:
            self.embed_result_panel(key)
        super().closeEvent(event)

    def configure_text_panel(self, text_edit, min_height=110):
        text_edit.setMinimumHeight(min_height)
        text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        text_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def _show_layout_plot_canvas(self):
        if not hasattr(self, "canvas"):
            return
        self.canvas.setMinimumSize(0, 0)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.canvas.updateGeometry()
        if hasattr(self, "plot_stack"):
            self.plot_stack.setCurrentWidget(self.canvas)

    def _show_vd_plot_canvas(self):
        if hasattr(self, "vd_plot_scroll_area"):
            self.vd_plot_scroll_area.setWidgetResizable(True)
            self.vd_plot_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.vd_plot_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        if hasattr(self, "plot_stack") and hasattr(self, "vd_plot_scroll_area"):
            self.plot_stack.setCurrentWidget(self.vd_plot_scroll_area)
        if hasattr(self, "vd_plot_scroll_area"):
            self.vd_plot_scroll_area.viewport().update()

    def _make_option_help_button(self):
        button = QToolButton()
        button.setText("?")
        button.setFixedSize(20, 20)
        button.setAccessibleName("Unavailable option reason")
        button.setStyleSheet("QToolButton { border: 1px solid palette(mid); border-radius: 10px; font-weight: 600; }")
        button.setToolTip("Show why this option is unavailable.")
        button.clicked.connect(lambda _checked=False, item=button: QMessageBox.information(
            self, "Option unavailable", item.toolTip()))
        button.hide()
        return button

    def _set_option_availability(self, key, available, reason="", checked=None):
        field = self.input_fields[key]
        button = self._option_help_buttons.get(key)
        if checked is not None and field.isChecked() != checked:
            field.setChecked(checked)
        field.setEnabled(available)
        field.setToolTip("" if available else reason)
        if button is not None:
            button.setToolTip(reason or "Show why this option is unavailable.")
            button.setVisible(not available)

    def _route_option_decision(self, inputs, *, radial_shift=False,
                               weld_inlet=False):
        """Probe one neutral option setting through production route admission."""
        q, poles, branches, layers, phases = inputs
        pattern = gw.normalize_pattern_name(self.input_fields['pattern_name'].text())
        selected = self._selected_dividers()
        if math.prod(selected) != branches:
            return None
        key = (pattern, q, poles, branches, layers, phases, selected,
               bool(radial_shift), bool(weld_inlet))
        cache = getattr(self, '_route_option_probe_cache', {})
        if key not in cache:
            winding = NS(q=int(q) if q.denominator == 1 else q,
                         num_slots=int(q * poles * phases), num_poles=poles,
                         num_layers=layers, num_phases=phases, ab=branches,
                         branch_dividers=selected)
            tp = NS(tp_type='Regular', tp_interval=0, tp_times=0, uni_tp=0,
                    pltp_fl=0, pltp_ll=0, jltp=0, jld=1, pole_group_tp={})
            layout = NS(phase_shift_pattern='None',
                        phase_shift_list=[0] * layers,
                        radial_shift=int(radial_shift),
                        inlet_from_weld_side=int(weld_inlet),
                        inlet_index_adjustments_phase_a=[])
            if len(cache) >= 128:
                cache.clear()
            cache[key] = gw.resolve_pattern_route(
                pattern, winding, selected, tp, layout)
            self._route_option_probe_cache = cache
        return cache[key]

    def _refresh_route_option_availability(self, inputs=None):
        if inputs is None:
            try:
                inputs = self._pattern_base_inputs()
            except (ValueError, TypeError, ZeroDivisionError):
                inputs = None
        if inputs is None:
            if (hasattr(self, "_option_help_buttons")
                    and "radial_shift" in self._option_help_buttons):
                self._set_option_availability("radial_shift", True)
            if "in_out_connection" in self._option_help_buttons:
                self._refresh_connect_ends_availability()
            return
        try:
            weld = self.input_fields['inlet_from_weld_side'].isChecked()
            baseline = self._route_option_decision(inputs, weld_inlet=weld)
            probe_weld = weld
            if baseline is not None and baseline.status == 'disabled':
                probe_weld = not weld
                baseline = self._route_option_decision(
                    inputs, weld_inlet=probe_weld)
            radial = (self._route_option_decision(
                inputs, radial_shift=True, weld_inlet=probe_weld)
                      if baseline is not None else None)
            blocked = (baseline is not None and baseline.status != 'disabled'
                       and radial is not None and radial.status == 'disabled')
        except (AttributeError, KeyError, TypeError, ValueError,
                ZeroDivisionError, OverflowError):
            blocked, radial = False, None
        if "radial_shift" in self._option_help_buttons:
            self._set_option_availability(
                "radial_shift", not blocked,
                (radial.reason + " Keep CHW shift off; do not click.")
                if blocked else "", checked=False if blocked else None)
        if "in_out_connection" in self._option_help_buttons:
            self._refresh_connect_ends_availability()

    def _refresh_connect_ends_availability(self):
        """Disable loop closure only when the current generated branch paths reject it."""
        state = getattr(self, "calculation_state", None)
        if state is None:
            if "in_out_connection" in self._option_help_buttons:
                self._set_option_availability("in_out_connection", True)
            return
        values = state.values
        signature = self._calculation_input_signature()
        if signature != getattr(state, "signature", None):
            if "in_out_connection" in self._option_help_buttons:
                self._set_option_availability("in_out_connection", True)
            return
        if (bool(self.input_fields["in_out_connection"].isChecked())
                != bool(values["Layout_Para"].in_out_connection)):
            self._connect_ends_check_signature = None
            if (bool(self.input_fields["in_out_connection"].isChecked())
                    and getattr(self, "_connect_ends_unavailable_signature", None)
                    == signature):
                self.input_fields["in_out_connection"].setChecked(False)
        if self._connect_ends_check_signature == signature:
            return
        try:
            winding = values["Winding_Para"]
            layout = values["Layout_Para"]
            closure_layout = layout._replace(in_out_connection=1)
            phases = {(int(row[0]), int(row[1])): (int(row[2]), int(row[4]))
                      for row in values["cond_info"]}
            for _branch_id, conductors in values["db_conductor_id"]:
                if len(conductors) < 2:
                    raise ValueError("A branch needs at least two conductors for loop closure.")
                start, end = conductors[0], conductors[-1]
                start_phase_sign = phases.get(tuple(start[:2]))
                end_phase_sign = phases.get(tuple(end[:2]))
                if (start_phase_sign is None or end_phase_sign is None
                        or start_phase_sign[0] != end_phase_sign[0]):
                    raise ValueError("The branch inlet and outlet do not belong to the same phase.")
                if start_phase_sign[1] == end_phase_sign[1]:
                    raise ValueError("The closing connection does not alternate conductor directions.")
                gw.find_single_connection_between(end, start, winding, closure_layout)
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            reason = f"Unavailable for the current generated layout: {exc} Do not click."
            self._connect_ends_unavailable_signature = signature
            if "in_out_connection" in self._option_help_buttons:
                self._set_option_availability("in_out_connection", False, reason,
                                              checked=False)
        else:
            self._connect_ends_unavailable_signature = None
            if "in_out_connection" in self._option_help_buttons:
                self._set_option_availability("in_out_connection", True)
        finally:
            self._connect_ends_check_signature = signature

    def _update_plot_toolbar(self):
        """Keep plot-local controls aligned with the canvas currently shown."""
        if not hasattr(self, "plot_view_title"):
            return
        is_volt_diff = (hasattr(self, "tabs") and self.tabs.currentIndex() >= 0
                        and self.tabs.tabText(self.tabs.currentIndex()) == "Volt Diff")
        if is_volt_diff:
            title = "Volt Diff"
            can_fit = False
            show_phase = False
        else:
            title = {"phase": "Phase Division", "winding": "Plot Layout"}.get(
                getattr(self, "current_view_type", "empty"), "Plot Preview")
            if title == "Plot Layout" and self._winding_candidate:
                title = "Plot Layout • Candidate"
            can_fit = getattr(self, "current_view_type", "empty") in {"phase", "winding"}
            show_phase = getattr(self, "current_view_type", "empty") == "phase"
        self.plot_view_title.setText(title)
        self.plot_fit_button.setEnabled(can_fit)
        self.phase_view_controls.setVisible(show_phase)
        self.phase_start_controls.setVisible(show_phase)
        self._refresh_manual_starts_availability()
        self.branch_division_button.setVisible(show_phase)
        if not show_phase and getattr(self, "branch_division_dialog", None) is not None:
            self.branch_division_dialog.close()
            self.branch_division_dialog = None
        show_winding = not is_volt_diff and getattr(self, "current_view_type", "empty") == "winding"
        self.winding_view_controls.setVisible(show_winding)
        self.winding_view_selector.setEnabled(show_winding and self._winding_plot_data is not None)
        self.winding_phase_selector.setEnabled(show_winding and self._winding_plot_data is not None)
        self.winding_branch_selector.setEnabled(show_winding and self._winding_plot_data is not None)

    def _refresh_manual_starts_availability(self):
        if not hasattr(self, "phase_start_mode"):
            return
        fresh = False
        if getattr(self, "phase_preview", None) is not None:
            try:
                fresh = (self._manual_preview_signature() == getattr(
                    self, "_phase_input_signature", None))
            except (KeyError, TypeError, ValueError):
                fresh = False
        available = getattr(self, "current_view_type", "empty") == "phase" and fresh
        if not available and self.phase_start_mode.isChecked():
            self.phase_start_mode.blockSignals(True)
            self.phase_start_mode.setChecked(False)
            self.phase_start_mode.blockSignals(False)
            self.phase_start_branch.setEnabled(False)
        reason = ("Available only for a fresh Phase Division preview. Plot Phase Division "
                  "again after changing inputs; do not click while unavailable.")
        self.phase_start_mode.setEnabled(available)
        self.phase_start_mode.setToolTip(
            "Candidate preview only; click a conductor after selecting a branch."
            if available else reason)
        self.phase_start_help.setToolTip(reason)
        self.phase_start_help.setVisible(not available)

    def _rebuild_winding_branch_selector(self, selected_branch=None):
        """Show only branches compatible with the selected plot phase."""
        data = self._winding_plot_data
        if data is None:
            return
        if selected_branch is None:
            selected_branch = self.winding_branch_selector.currentData()
        selected_phase = self.winding_phase_selector.currentData()
        phases_by_branch = {}
        for row in data['cond_info']:
            branch = int(row[3])
            if branch > 0:
                phases_by_branch.setdefault(branch, set()).add(int(row[2]))
        phase_by_branch = {
            branch: next(iter(phases))
            for branch, phases in phases_by_branch.items() if len(phases) == 1
        }
        local_number_by_branch = {}
        for phase in sorted(set(phase_by_branch.values())):
            for local_number, branch in enumerate(sorted(
                    branch for branch, branch_phase in phase_by_branch.items()
                    if branch_phase == phase), start=1):
                local_number_by_branch[branch] = local_number
        self.winding_branch_selector.blockSignals(True)
        self.winding_branch_selector.clear()
        self.winding_branch_selector.addItem("Candidate • All" if self._winding_candidate else "All", None)
        for branch in sorted(phases_by_branch):
            phases = phases_by_branch[branch]
            if selected_phase is not None and phases != {selected_phase}:
                continue
            label = f"Branch {branch}"
            if branch in phase_by_branch and 0 <= phase_by_branch[branch] < 26:
                label = (f"{chr(ord('A') + phase_by_branch[branch])}: "
                         f"Branch {local_number_by_branch[branch]}")
            self.winding_branch_selector.addItem(label, branch)
        self.winding_branch_selector.setCurrentIndex(
            max(0, self.winding_branch_selector.findData(selected_branch)))
        self.winding_branch_selector.blockSignals(False)

    def _winding_phase_changed(self, _index=None):
        if self._winding_plot_data is None:
            return
        self._rebuild_winding_branch_selector()
        self._render_winding_view()

    def _sync_tab_context_layout(self, _index=None):
        if not hasattr(self, "tabs"):
            return
        tab_name = self.tabs.tabText(self.tabs.currentIndex())
        is_volt_diff = tab_name == "Volt Diff"
        is_dedicated_analysis = tab_name in ("Volt Diff", "Inductance")
        if hasattr(self, "plot_stack"):
            if is_volt_diff:
                self._show_vd_plot_canvas()
            else:
                self._show_layout_plot_canvas()
        if hasattr(self, "figure_container"):
            self.figure_container.setVisible(tab_name != "Inductance")
        if hasattr(self, "phase_actions"):
            self.phase_actions.setVisible(not is_dedicated_analysis)
        if hasattr(self, "quick_analysis_container"):
            self.quick_analysis_container.setVisible(not is_dedicated_analysis)
        if hasattr(self, "left_info_splitter"):
            self.left_info_splitter.setVisible(not is_dedicated_analysis)
        if hasattr(self, "left_splitter"):
            if is_dedicated_analysis:
                self._left_splitter_normal_sizes = self.left_splitter.sizes()
                self.left_splitter.setSizes([700, 0])
            elif getattr(self, "_left_splitter_normal_sizes", None):
                self.left_splitter.setSizes(self._left_splitter_normal_sizes)
        if tab_name == "Inductance":
            self._invalidate_inductance_if_stale()
        self._update_plot_toolbar()

    def _remember_left_splitter_sizes(self, *_args):
        """Preserve the user-selected Tab/result split outside the Volt Diff page."""
        if (not hasattr(self, "tabs")
                or self.tabs.tabText(self.tabs.currentIndex()) in ("Volt Diff", "Inductance")):
            return
        self._left_splitter_normal_sizes = self.left_splitter.sizes()


    def add_input_field(self, label_text, default_value, unit, is_checkbox=False, is_combo=False, combo_options=None):
        """Helper function to add input fields or checkboxes with proper alignment and unit labels."""
        row_layout = QHBoxLayout()
    
        # Left Spacer (to push input_widget to the center)
        left_spacer = QSpacerItem(20, 10, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        row_layout.setSpacing(8)
    
        # Create Input Widget (Checkbox or QLineEdit)
        if is_checkbox:
            input_widget = QCheckBox()  # Create a checkbox instead of QLineEdit
            input_widget.setChecked(default_value == "1")  # Set checked if default is "1"
            
        elif is_combo and combo_options:
            from PyQt6.QtWidgets import QComboBox
            input_widget = QComboBox()
            input_widget.addItems(combo_options)
            input_widget.setCurrentText(default_value)
            input_widget.setFixedWidth(100)
        
            # Center-align combo text
            input_widget.setEditable(True)
            input_widget.lineEdit().setAlignment(Qt.AlignmentFlag.AlignCenter)
            input_widget.setEditable(False)
        
            # Add left spacing before the combo box
            input_widget.setMinimumWidth(140)
            input_widget.setMaximumWidth(16777215)

        else:
            input_widget = QLineEdit(default_value)
            input_widget.setMinimumWidth(50)  # Set minimum width
            input_widget.setMaximumWidth(100)  # Set maximum width
            input_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)  # Allows resizing
            input_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Center align input text
    
        row_layout.addWidget(input_widget)  # Add input field or checkbox
    
        # Right Spacer (to keep input_widget at center)
        right_spacer = QSpacerItem(20, 10, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        row_layout.addStretch(1)
    
        # Add unit label at the end (if applicable)
        if unit:
            unit_label = QLabel(unit)
            unit_label.setFixedWidth(50)  # Fixed space for unit text
            row_layout.addWidget(unit_label)
    
        return row_layout, input_widget

    def create_compact_parameter_tab(self, tab_name, fields, start_row=0):
        """Build a consistently spaced two-column parameter page.

        ``fields`` keeps the established (label, default, unit, key[, checkbox])
        contract so configuration import/export and calculation code remain
        independent from the presentation layout.
        """
        tab = QWidget()
        grid = QGridLayout(tab)
        grid.setContentsMargins(16, 14, 16, 14)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(10)
        for column in (1, 3):
            grid.setColumnStretch(column, 1)

        if not hasattr(self, "compact_parameter_grids"):
            self.compact_parameter_grids = {}
        self.compact_parameter_grids[tab_name] = grid

        for index, field in enumerate(fields):
            label_text, default, unit, key = field[:4]
            is_checkbox = len(field) > 4 and bool(field[4])
            row, pair = divmod(index, 2)
            row += start_row
            label = QLabel(label_text)
            label.setProperty("fieldLabel", True)
            label.setWordWrap(True)
            row_layout, input_box = self.add_input_field(
                label_text, default, unit, is_checkbox=is_checkbox)
            self.input_fields[key] = input_box
            grid.addWidget(label, row, pair * 2)
            grid.addLayout(row_layout, row, pair * 2 + 1)

        grid.setRowStretch(start_row + (len(fields) + 1) // 2, 1)
        return tab, grid


    def create_winding_params_tab(self):
        fields = [
        ("Calculate from:", "", "", "winding_input_placeholder"),
        ("Slots per pole per phase (q):", "1.5", "", "q"),
        ("Number of Slots:", "36", "", "num_slots"),
        ("Number of Poles:", "8", "", "num_poles"),
        ("Number of Parallel Branches:", "3", "", "ab"),
        ("Number of Layers:", "6", "", "num_layers"),
        ("Number of Phases:", "3", "", "num_phases"),
        ("Cu resistivity:", "2.5364e-08", "Ω·m", "curesistivity"),
    ]
        tab, grid = self.create_compact_parameter_tab("Winding", fields)
        self._winding_params_page = tab
        tab.installEventFilter(self)
        mode = QComboBox()
        mode.setObjectName("windingInputMode")
        mode.addItems(["Slots and poles", "q and poles"])
        mode.setCurrentText("q and poles")
        self.input_fields["winding_input_mode"] = mode
        placeholder = self.input_fields.pop("winding_input_placeholder")
        row_layout = grid.itemAtPosition(0, 1).layout()
        row_layout.replaceWidget(placeholder, mode)
        placeholder.hide()
        placeholder.deleteLater()
        mode.setMinimumWidth(0)
        mode.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        mode.setMinimumContentsLength(12)
        def sync_input_mode():
            from_slots = mode.currentIndex() == 0
            self.input_fields["q"].setReadOnly(from_slots)
            self.input_fields["num_slots"].setReadOnly(not from_slots)
            for key in ("q", "num_slots"):
                field = self.input_fields[key]
                field.style().unpolish(field)
                field.style().polish(field)
            try:
                self._resolve_slot_inputs()
            except ValueError:
                pass
        mode.currentIndexChanged.connect(sync_input_mode)
        for key in ("num_slots", "num_poles", "num_phases", "q"):
            self.input_fields[key].editingFinished.connect(sync_input_mode)
        divider_row = QHBoxLayout()
        divider_row.setContentsMargins(0, 0, 0, 0)
        divider_row.setSpacing(8)
        divider_title = QLabel("Dividers:")
        divider_title.setMinimumWidth(82)
        divider_row.addWidget(divider_title)
        for key, label in (("q_divider", "Q:"),
                           ("pp_divider", "PP:"),
                           ("p2_divider", "P2:")):
            box = QComboBox()
            box.setProperty("dividerCombo", True)
            box.setFixedWidth(65)
            self.input_fields[key] = box
            divider_label = QLabel(label)
            divider_label.setFixedWidth(25)
            divider_row.addWidget(divider_label)
            divider_row.addWidget(box)
            box.currentIndexChanged.connect(self._on_divider_changed)
        divider_row.addStretch(1)
        divider_row.addWidget(QLabel("Pattern:"))
        self.layout_pattern_selector = QComboBox()
        self.layout_pattern_selector.setObjectName("layoutPatternSelector")
        self.layout_pattern_selector.setMinimumWidth(120)
        self.layout_pattern_selector.setToolTip(
            "Select the Pattern used for the winding layout.")
        for pattern in gw.get_available_patterns():
            self.layout_pattern_selector.addItem(gw.get_pattern_label(pattern), pattern)
        self.layout_pattern_selector.currentIndexChanged.connect(
            self._select_layout_pattern_from_combo)
        divider_row.addWidget(self.layout_pattern_selector)
        self.divider_row_container = QWidget()
        self.divider_row_container.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.divider_row_container.setLayout(divider_row)
        grid.addWidget(
            self.divider_row_container, 4, 0, 1, 4,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )
        self.q_divider_box = self.input_fields["q_divider"]
        self.pp_divider_box = self.input_fields["pp_divider"]
        self.p2_divider_box = self.input_fields["p2_divider"]
        self.divider_status = QLabel()
        self.divider_status.setWordWrap(True)
        grid.addWidget(self.divider_status, 5, 0, 1, 4)
        grid.setRowStretch(6, 1)
        for key in ("q", "num_slots", "num_poles", "num_phases", "ab"):
            self.input_fields[key].editingFinished.connect(self._sync_dividers_from_inputs)
        self.input_fields["ab"].textChanged.connect(self._on_naa_text_changed)
        sync_input_mode()
        self._sync_dividers_from_inputs()
        return tab

    def _refresh_current_layout_pattern_hint(self):
        """Keep the divider-row Pattern selector aligned with the layout field."""
        field = self.input_fields.get("pattern_name")
        pattern = "UWP"
        if field is not None:
            try:
                pattern = gw.normalize_pattern_name(field.text())
            except (TypeError, ValueError):
                pattern = field.text().strip() or "UWP"
        selector = getattr(self, "layout_pattern_selector", None)
        if selector is None:
            return
        index = selector.findData(pattern)
        if index >= 0 and selector.currentIndex() != index:
            selector.blockSignals(True)
            selector.setCurrentIndex(index)
            selector.blockSignals(False)

    def _select_layout_pattern_from_combo(self, _index):
        """Route divider-row Pattern selection through the existing validator."""
        selector = getattr(self, "layout_pattern_selector", None)
        if selector is not None and selector.currentData():
            self.set_pattern_with_validation(selector.currentData())

    def _selected_dividers(self):
        return tuple(Fraction(self.input_fields[key].currentText())
                     for key in ("q_divider", "pp_divider", "p2_divider"))

    @staticmethod
    def _divider_text(value):
        value = Fraction(value)
        return str(float(value)).rstrip("0").rstrip(".") if value.denominator == 2 else str(value)

    def _divider_choices(self, q, poles):
        if q <= 0 or poles <= 0 or poles % 2:
            raise ValueError("q must be positive and poles must be positive and even.")
        if q.denominator == 1:
            q_choices = gw.divisors(int(q))
        elif q.denominator == 2:
            q_choices = sorted({Fraction(1), q, *(q / divisor for divisor in gw.divisors(q.numerator)
                                                       if q / divisor >= 1)})
        else:
            raise ValueError("Only integer and half-integer q divider choices are available.")
        return (q_choices, gw.divisors(poles // 2), (1, 2))

    def _default_dividers(self, q, poles, ab, pattern):
        if q.denominator == 1:
            result = gw.classify_branch_mode(ab, int(q), poles, pattern)
            dividers = result[1:4] if result[0] != "unsupported" else None
            if (dividers is not None
                    and pattern != 'LPP'
                    and gw.pattern_rejects_divider_tuple(
                        pattern, dividers, q, poles // 2)):
                return None
            return dividers
        phases = int(self.input_fields['num_phases'].text())
        layers = int(self.input_fields['num_layers'].text())
        winding = NS(q=q, ab=ab, num_poles=poles, num_phases=phases,
                     num_layers=layers, num_slots=int(q * poles * phases))
        decision = gw.resolve_pattern_route(pattern, winding)
        return decision.dividers if decision.status in ('enabled', 'candidate') else None

    def _sync_dividers_from_inputs(self):
        try:
            q, _ = self._resolve_slot_inputs()
            poles = int(self.input_fields["num_poles"].text())
            ab = int(self.input_fields["ab"].text())
            pattern = gw.normalize_pattern_name(self.input_fields["pattern_name"].text()) if "pattern_name" in self.input_fields else "UWP"
            choices = self._divider_choices(q, poles)
            selected = self._default_dividers(q, poles, ab, pattern) or (Fraction(1), 1, 1)
            for key, options, value in zip(("q_divider", "pp_divider", "p2_divider"), choices, selected):
                box = self.input_fields[key]
                box.blockSignals(True)
                box.clear()
                box.addItems([self._divider_text(option) for option in options])
                box.setCurrentText(self._divider_text(value))
                box.blockSignals(False)
            self._divider_user_selected = False
            self._update_half_divider_availability()
            self._refresh_divider_status()
        except (ValueError, TypeError):
            pass

    def _on_divider_changed(self, _index):
        try:
            self._divider_user_selected = True
            self._update_half_divider_availability()
            product = math.prod(self._selected_dividers())
            if product.denominator != 1:
                box = (self.input_fields["q_divider"]
                       if self.sender() is self.input_fields["p2_divider"]
                       else self.input_fields["p2_divider"])
                box.blockSignals(True)
                box.setCurrentText("1" if box is self.input_fields["q_divider"] else "2")
                box.blockSignals(False)
                product = math.prod(self._selected_dividers())
                self._update_half_divider_availability()
            self._updating_divider_ab = True
            self.input_fields["ab"].setText(str(int(product)))
            self._updating_divider_ab = False
            self._refresh_divider_status()
            self._refresh_weld_inlet_availability()
            self._refresh_route_option_availability()
        except (ValueError, ZeroDivisionError):
            self._updating_divider_ab = False
            pass

    def _on_naa_text_changed(self, _text):
        try:
            branch_count = int(_text)
            if branch_count > 0:
                pattern = gw.normalize_pattern_name(
                    self.input_fields['pattern_name'].text())
                self._coerce_phase_a_adjustments(
                    branch_count, pattern, strict=False)
        except (KeyError, TypeError, ValueError):
            pass
        if not getattr(self, "_updating_divider_ab", False):
            self._sync_dividers_from_inputs()

    def _refresh_divider_from_inputs(self):
        self._sync_dividers_from_inputs()

    def _update_half_divider_availability(self):
        q_box = self.input_fields["q_divider"]
        pattern_field = self.input_fields.get("pattern_name")
        pattern = gw.normalize_pattern_name(
            pattern_field.text() if pattern_field is not None else "UWP",
            allow_extra=True)
        pp = Fraction(self.input_fields["pp_divider"].currentText())
        p2 = Fraction(self.input_fields["p2_divider"].currentText())
        for index in range(q_box.count()):
            value = Fraction(q_box.itemText(index))
            allowed = (value * pp * p2).denominator == 1
            item = q_box.model().item(index)
            item.setEnabled(allowed)
            item.setToolTip("" if allowed else
                            "Q x PP x P2 must produce an integer Naa.")
        p2_box = self.input_fields["p2_divider"]
        try:
            q, _ = self._resolve_slot_inputs()
            poles = int(self.input_fields['num_poles'].text())
            layers = int(self.input_fields['num_layers'].text())
            phases = int(self.input_fields['num_phases'].text())
        except (ValueError, TypeError, ZeroDivisionError):
            q = poles = layers = phases = None
        for index in range(p2_box.count()):
            factors = (Fraction(q_box.currentText()), pp,
                       Fraction(p2_box.itemText(index)))
            product = math.prod(factors)
            item = p2_box.model().item(index)
            if product.denominator != 1:
                item.setEnabled(False)
                item.setToolTip("Q x PP x P2 must produce an integer Naa.")
            elif None in (q, poles, layers, phases):
                item.setEnabled(True)
                item.setToolTip("")
            else:
                winding = NS(q=int(q) if q.denominator == 1 else q,
                             num_slots=int(q * poles * phases),
                             num_poles=poles, num_layers=layers,
                             num_phases=phases, ab=int(product),
                             branch_dividers=factors)
                decision = gw.resolve_pattern_route(pattern, winding, factors)
                item.setEnabled(decision.status != 'disabled')
                item.setToolTip(decision.reason if decision.status == 'disabled'
                                else "")

    def _refresh_divider_status(self):
        if getattr(self, '_syncing_uwp_balance', False):
            return
        try:
            self._sync_uwp_balanced_defaults()
            decision = self._validate_divider_route(check_only=True)
            if decision.status == 'candidate':
                self.divider_status.setText("Connection: Candidate. Validate layout.")
                self.divider_status.setToolTip(decision.reason)
                return
            q, _ = self._resolve_slot_inputs()
            poles = int(self.input_fields["num_poles"].text())
            ab = int(self.input_fields["ab"].text())
            pattern = (gw.normalize_pattern_name(self.input_fields["pattern_name"].text())
                       if "pattern_name" in self.input_fields else "UWP")
            if (getattr(self, '_uwp_balance_key', None) is not None
                    or self._selected_dividers() != self._default_dividers(
                        q, poles, ab, pattern)):
                self.divider_status.setText(
                    "Connection: Enabled (eligible). Validate layout.")
                self.divider_status.setToolTip(decision.reason)
            else:
                self.divider_status.setText("Connection: Enabled (available).")
                self.divider_status.setToolTip(decision.reason)
        except (ValueError, TypeError) as exc:
            self.divider_status.setText(
                "Connection: Disabled (not supported). See tooltip.")
            self.divider_status.setToolTip(str(exc))

    def _sync_uwp_balanced_defaults(self, force=False):
        """Apply the derived rule on route entry, and restore prior TP on exit."""
        if (getattr(self, '_loading_balance_config', False)
                or not hasattr(self, 'uwp_balance_notice')
                or 'pattern_name' not in self.input_fields):
            return
        q, _ = self._resolve_slot_inputs()
        winding = NS(q=int(q) if q.denominator == 1 else q,
                     num_slots=int(self.input_fields['num_slots'].text()),
                     num_poles=int(self.input_fields['num_poles'].text()),
                     num_layers=int(self.input_fields['num_layers'].text()),
                     num_phases=int(self.input_fields['num_phases'].text()),
                     ab=int(self.input_fields['ab'].text()),
                     branch_dividers=self._selected_dividers())
        pattern = gw.normalize_pattern_name(self.input_fields['pattern_name'].text())
        active = gw.selected_integer_divider_route(pattern, winding) == 'uwp_balanced_q'
        key = (winding.q, winding.num_poles, winding.num_layers,
               winding.branch_dividers) if active else None
        previous = getattr(self, '_uwp_balance_key', None)
        self.uwp_balance_notice.setVisible(active)
        if key == previous and not (force and active):
            return
        self._syncing_uwp_balance = True
        try:
            fields = ('tp_interval', 'tp_times', 'uni_tp', 'pltp_fl', 'pltp_ll', 'jltp')
            if active:
                if previous is None:
                    kind = self.tp_type_field.currentText()
                    self._uwp_previous_tp = (kind, {name: self.tp_fields[name].text()
                                                   for name in fields})
                kind = 'Auto'
                self._auto_effective_tp_type = 'Auto'
                values = auto_tp.uwp_balanced_settings(gw._uwp_balanced_q_pp_plan(winding))
                plan = gw._uwp_balanced_q_pp_plan(winding)
                starts = gw.uwp_balanced_phase_a_start_slots(winding)
                self.uwp_balance_notice.setText(
                    f"Automatic UWP balance: Q={plan['q_divider']}, "
                    f"PP={plan['pp_divider']}, P2=2; q-position advances "
                    f"cycle={plan['cycle_advance']}, local={plan['local_advance']} "
                    f"(mod {winding.q}); rotating "
                    f"{plan['arc_poles']}-pole PP arcs. Phase A start slots: "
                    + ', '.join(map(str, starts)) + "; layer 1. Other phases follow the phase belts.")
            else:
                kind, values = self._uwp_previous_tp
                kind = auto_tp.normalize_tp_type(kind)
            self.tp_type_field.blockSignals(True)
            self.tp_type_field.setCurrentText(kind)
            self.tp_type_field.blockSignals(False)
            for name, value in values.items():
                field = self.tp_fields[name]
                field.blockSignals(True)
                field.setText(str(value))
                field.blockSignals(False)
            self._uwp_balance_key = key
            self.update_transp_type(kind)
        finally:
            self._syncing_uwp_balance = False

    def _validate_divider_route(self, check_only=False):
        if not check_only and not getattr(self, "_divider_user_selected", False):
            self._sync_dividers_from_inputs()
        q, _ = self._resolve_slot_inputs()
        poles = int(self.input_fields["num_poles"].text())
        ab = int(self.input_fields["ab"].text())
        pattern = gw.normalize_pattern_name(self.input_fields["pattern_name"].text()) if "pattern_name" in self.input_fields else "UWP"
        selected = self._selected_dividers()
        if math.prod(selected) != ab:
            raise ValueError("The divider product must equal Naa.")
        phases = int(self.input_fields['num_phases'].text())
        layers = int(self.input_fields['num_layers'].text())
        winding = NS(q=int(q) if q.denominator == 1 else q,
                     num_slots=int(q * poles * phases), num_poles=poles,
                     num_layers=layers, num_phases=phases, ab=ab,
                     branch_dividers=selected)
        if 'tp_type' not in self.input_fields:
            decision = gw.resolve_pattern_route(pattern, winding, selected)
            if decision.status == 'disabled':
                raise ValueError(decision.reason)
            return decision
        displayed_tp_type = self.input_fields['tp_type'].currentText()
        effective_tp_type = (self._auto_effective_tp_type
                             if auto_tp.is_auto_type(displayed_tp_type)
                             else displayed_tp_type)
        tp = NS(tp_type=effective_tp_type,
                **{key: int(self.tp_fields[key].text()) for key in
                   ('tp_interval', 'tp_times', 'uni_tp', 'pltp_fl',
                    'pltp_ll', 'jltp')},
                pole_group_tp={group: dict(
                    tp_type=self.input_fields[f'{prefix}_tp_type'].currentText(),
                    **{key: int(self.input_fields[f'{prefix}_{key}'].text())
                       for key in ('tp_interval', 'tp_times', 'uni_tp',
                                   'pltp_fl', 'pltp_ll', 'jltp')})
                    for group, prefix in (('PoleN', 'pole_n'),
                                          ('PoleS', 'pole_s'))})
        tp.jld = -1 if tp.jltp < 0 else 1
        if auto_tp.is_auto_type(displayed_tp_type):
            # Admission uses the same neutral seed as the full resolver;
            # every generated recipe still passes the public route guards.
            tp.tp_type = "Regular"
            tp.jld = 1
            for key in auto_tp.TP_FIELD_NAMES:
                setattr(tp, key, 0)
        shift_pattern = self.input_fields['phase_shift_pattern'].currentText()
        shift = int(self.input_fields['phase_shift'].text())
        psl = int(self.input_fields['PSL'].text())
        layout = NS(
            phase_shift_pattern=shift_pattern,
            phase_shift_list=gw.get_phase_shift_list(
                winding, shift_pattern, shift, psl, log=lambda *_: None),
            radial_shift=self.input_fields['radial_shift'].isChecked(),
            inlet_from_weld_side=self.input_fields['inlet_from_weld_side'].isChecked(),
            inlet_index_adjustments_phase_a=self.inlet_index_adjustments_phase_a)
        decision = gw.resolve_pattern_route(
            pattern, winding, selected, tp, layout)
        if decision.status == 'candidate':
            if check_only or q.denominator != 1:
                return decision
            raise ValueError('Candidate routes are Workbench-only: ' + decision.reason)
        if decision.status != 'enabled':
            raise ValueError(decision.reason)
        route = decision.route_name
        if pattern == 'UWP' and q.denominator == 1 and (
                route == 'pp_only' or gw.uses_uwp_complementary_q_pp(winding)):
            gw.validate_uwp_pp_settings(tp,winding,layout)
            return decision
        if route == 'uwp_balanced_q':
            gw.validate_uwp_balanced_configuration(tp, winding, layout)
            return decision
        return decision

    def _resolve_slot_inputs(self):
        poles = int(self.input_fields["num_poles"].text())
        phases = int(self.input_fields["num_phases"].text())
        if phases <= 0:
            raise ValueError("Number of phases must be positive.")
        mode = self.input_fields.get("winding_input_mode")
        if mode is not None and mode.currentText() == "Slots and poles":
            slots = int(self.input_fields["num_slots"].text())
            q = phase_topology.winding_q(slots, poles, phases)
            self.input_fields["q"].setText(str(q))
        else:
            q = phase_topology.parse_q(self.input_fields["q"].text())
            total = q * poles * phases
            if total.denominator != 1:
                raise ValueError("q, phases and poles must produce an integer slot count.")
            slots = int(total)
            phase_topology.winding_q(slots, poles, phases)
            self.input_fields["num_slots"].setText(str(slots))
        return q, slots

    @staticmethod
    def _format_phase_counts(counts):
        if len(set(counts)) == 1:
            return f"Cond/Phase: {counts[0]}"
        names = "ABC" if len(counts) == 3 else tuple(
            f"P{phase + 1}" for phase in range(len(counts)))
        return "Cond/Phase: " + "  ".join(
            f"{phase} {count}" for phase, count in zip(names, counts))

    def preview_phase_division(self):
        """Compute slot/layer assignment only; never enter the pattern pipeline."""
        if self.branch_division_dialog is not None:
            self.branch_division_dialog.close()
            self.branch_division_dialog = None
        self.phase_preview = None
        self.phase_start_mode.blockSignals(True)
        self.phase_start_mode.setChecked(False)
        self.phase_start_mode.blockSignals(False)
        self._manual_start_context = None
        self._manual_start_results = {}
        self._phase_input_signature = None
        self.phase_start_branch.setEnabled(False)
        self.phase_start_status.setText("Enable Manual starts to select candidate inlet positions.")
        self.current_view_type = "empty"
        self._update_plot_toolbar()
        self._show_layout_plot_canvas()
        self.ax.clear()
        try:
            q, slots = self._resolve_slot_inputs()
            phases = int(self.input_fields["num_phases"].text())
            if not phase_topology.supports_phase_count(phases):
                raise ValueError(
                    "Use an odd phase count of at least three or any multiple of three.")
            poles = int(self.input_fields["num_poles"].text())
            layers = int(self.input_fields["num_layers"].text())
            from types import SimpleNamespace
            shifts = gw.get_phase_shift_list(SimpleNamespace(num_layers=layers),
                self.input_fields["phase_shift_pattern"].currentText(),
                int(self.input_fields["phase_shift"].text()), int(self.input_fields["PSL"].text()),
                log=lambda _: None)
            defaults = phase_topology.default_phase_map(slots, poles, layers, phases)
            records = tuple(phase_topology.apply_layer_shifts(defaults, slots, layers, shifts))
            result = phase_topology.electrical_summary(records, slots, poles, phases)
            complete = (len(records) == slots * layers and
                        {(s, l) for s, l, _, _ in records} ==
                        {(s, l) for s in range(slots) for l in range(layers)} and
                        all(0 <= p < phases and d in (-1, 1)
                            for _, _, p, d in records))
            self.phase_preview = dict(q=q, slots=slots, poles=poles, layers=layers,
                                      phases=phases, shifts=tuple(shifts),
                                      records=records, summary=result,
                                      clockwise=self.input_fields["CW"].isChecked())
            self._phase_input_signature = self._manual_preview_signature()
            if hasattr(self, "phase_cond_phase_label"):
                self.phase_cond_phase_label.setText(
                    self._format_phase_counts(result["counts"]))
            if result.get("balance_model") == "independent_three_phase_sets":
                symmetry_line = (
                    "Balance by three-phase winding sets: "
                    f"{'PASS' if result['balanced'] else 'WARNING: unbalanced set'}")
                error_label = "Relative set-balance error"
            else:
                symmetry_line = (
                    "Electrical symmetry: "
                    f"{'PASS' if result['balanced'] else 'WARNING: unbalanced or zero EMF'}")
                error_label = "Relative symmetry error"
            self.current_view_type = "phase"
            self._update_plot_toolbar()
            lines = ["Phase division only — connections not generated",
                     f"Slots: {slots}; poles: {poles}; layers: {layers}; q: {q}",
                     f"Mapping complete: {complete}",
                     symmetry_line,
                     f"{error_label}: {result['relative_error']:.6g}",
                     "Normalized conductor EMF (not volts):"]
            for group in result.get("sets", ()):
                first = group["phase_indices"][0]
                last = group["phase_indices"][-1]
                state = "balanced" if group["balanced"] else "unbalanced"
                first_label = self._phase_label(first)
                last_label = self._phase_label(last)
                array_state = ("aligned" if group.get("array_aligned", True)
                               else "misaligned")
                lines.append(
                    f"Set {group['set']} ({first_label}-{last_label}): "
                    f"{state}; array {array_state}; expected/observed offset "
                    f"{group['array_offset_degrees']:.6g}/"
                    f"{group.get('observed_array_offset_degrees', float('nan')):.6g} deg")
            for phase, (count, emf) in enumerate(zip(result["counts"], result["emf"]), 1):
                angle = math.degrees(math.atan2(emf.imag, emf.real)) if abs(emf) > 1e-12 else None
                angle_text = f"{angle:.6f} deg" if angle is not None else "undefined (zero EMF)"
                lines.append(f"{phase}: count={count}, amplitude={abs(emf):.8g}, angle={angle_text}")
            lines += [f"Layer slot offsets from default: {list(shifts)}",
                      "Positive offset moves toward increasing slot numbers; CW changes drawing only.",
                      "Layers are numbered 1..N, outer to inner.",
                      "CHW local layer swap is NOT applied (connection-specific operation).",
                      "Signs use explicit signed phase axes; legacy phase B uses a different terminal convention.",
                      "Legacy connection mapping is not certified for arbitrary q or odd layer counts.",
                      "This diagnostic does not validate connections or manufacturability."]
            self.layout_display.setPlainText("\n".join(lines))
            self.phase_preview["report"] = "\n".join(lines)
            self._render_phase_preview()
            self.message_log.append("Phase-only check completed; connections were not generated.")
        except (ValueError, ZeroDivisionError, OverflowError) as exc:
            self.phase_preview = None
            self.current_view_type = "empty"
            self._update_plot_toolbar()
            if hasattr(self, "phase_cond_phase_label"):
                self.phase_cond_phase_label.setText("Cond/Phase: —")
            self.ax.clear()
            self._apply_plot_background(self.get_field_value("ui_theme") if "ui_theme" in self.input_fields else "Light")
            self.ax.axis("off")
            self.canvas.draw()
            self.layout_display.setPlainText(f"Phase validation failed: {exc}")
            self.message_log.append(f"Phase validation failed: {exc}")

    def _manual_preview_signature(self):
        keys = ("winding_input_mode", "q", "num_slots", "num_poles", "num_layers",
                "num_phases", "ab", "pattern_name", "phase_shift_pattern", "phase_shift",
                "PSL", "radial_shift", "inlet_from_weld_side", "in_out_connection",
                "tp_type", "tp_interval", "tp_times", "uni_tp", "pltp_fl", "pltp_ll", "jltp",
                "auto_configure_objective")
        return tuple((key, str(self.get_field_value(key))) for key in keys)

    def _manual_preview_parameters(self):
        """Read only connection inputs; never run the production extraction pipeline."""
        from types import SimpleNamespace as NS
        data = self.phase_preview
        integer = lambda key: int(self.get_field_value(key))
        pattern = gw.normalize_pattern_name(self.get_field_value("pattern_name"))
        phases = integer("num_phases")
        winding = NS(q=data["q"], num_slots=data["slots"], num_poles=data["poles"],
                     num_layers=data["layers"], num_phases=phases, ab=integer("ab"))
        layout = NS(pattern_name=gw.get_pattern_label(pattern),
                    inlet_from_weld_side=int(gw.pattern_requires_weld_side_inlet(pattern)
                                              or integer("inlet_from_weld_side")),
                    phase_shift_pattern=self.get_field_value("phase_shift_pattern"),
                    phase_shift=integer("phase_shift"), PSL=integer("PSL"),
                    phase_shift_list=list(data["shifts"]), radial_shift=integer("radial_shift"),
                    in_out_connection=integer("in_out_connection"), CW=1, Single_Phase_Draw=0,
                    inlet_index_adjustments_phase_a=())
        transposition = NS(tp_type=self.get_field_value("tp_type"),
                           **{key: integer(key) for key in
                              ("tp_interval", "tp_times", "uni_tp", "pltp_fl", "pltp_ll")},
                           jltp=abs(integer("jltp")), jld=-1 if integer("jltp") < 0 else 1)
        return pattern, winding, layout, transposition

    def _invalidate_manual_starts(self, _value=None):
        changed = (self._manual_preview_signature()
                   != getattr(self, "_phase_input_signature", None))
        if changed and self.branch_division_dialog is not None:
            self.branch_division_dialog.close()
            self.branch_division_dialog = None
        if changed and (self._manual_start_context is not None
                        or self.phase_start_mode.isChecked()):
            self._manual_start_context = None
            self._manual_start_results.clear()
            self.phase_start_mode.blockSignals(True)
            self.phase_start_mode.setChecked(False)
            self.phase_start_mode.blockSignals(False)
            self.phase_start_branch.setEnabled(False)
            self.phase_start_status.setText("Inputs changed. Plot Phase Division again to choose starts.")
            if self.current_view_type == "phase" and self.phase_preview is not None:
                self.layout_display.setPlainText("Inputs changed — manual preview cleared.\n" +
                                                 self.phase_preview.get("report", ""))
            self._render_phase_preview()
        self._refresh_manual_starts_availability()

    def _toggle_manual_starts(self, enabled):
        if not enabled:
            self.phase_start_branch.setEnabled(False)
            if self.phase_preview is not None:
                self.layout_display.setPlainText(self.phase_preview.get("report", ""))
            self._render_phase_preview()
            return
        if self.current_view_type != "phase" or self.phase_preview is None:
            return
        if not self.phase_start_mode.isEnabled():
            return
        try:
            if self._manual_preview_signature() != self._phase_input_signature:
                raise ValueError("Inputs changed. Plot Phase Division again before choosing starts.")
            if self._manual_start_context is None:
                from branch_start_preview import build_preview_context
                self._manual_start_context = build_preview_context(
                    *self._manual_preview_parameters(), self.phase_preview["records"])
                self.phase_start_branch.blockSignals(True)
                self.phase_start_branch.clear()
                for branch in self._manual_start_context["branches"]:
                    self.phase_start_branch.addItem(
                        f"Phase {self._phase_label(branch['phase'])} / Branch {branch['number']}", branch['id'])
                self.phase_start_branch.blockSignals(False)
            self.phase_start_branch.setEnabled(bool(self._manual_start_context["branches"]))
            self._manual_branch_changed()
        except (ValueError, TypeError) as exc:
            self.phase_start_status.setText(str(exc))
            self.phase_start_mode.blockSignals(True)
            self.phase_start_mode.setChecked(False)
            self.phase_start_mode.blockSignals(False)
            self.phase_start_branch.setEnabled(False)

    def open_branch_division(self):
        if self.current_view_type != "phase" or self.phase_preview is None:
            return
        if self._manual_preview_signature() != self._phase_input_signature:
            self.phase_start_status.setText("Inputs changed. Plot Phase Division again before testing rules.")
            return
        try:
            if int(self.get_field_value("ab")) <= 0:
                raise ValueError
        except (TypeError, ValueError):
            self.phase_start_status.setText("Naa must be a positive integer for Branch Division.")
            return
        if self.branch_division_dialog is None or not self.branch_division_dialog.isVisible():
            self.branch_division_dialog = BranchDivisionDialog(self)
            self.branch_division_dialog.show()
        else:
            self.branch_division_dialog.raise_()
            self.branch_division_dialog.activateWindow()

    def _preview_branch_division(self, pattern, division_rule):
        """Show a selected candidate partition without changing production inputs."""
        if (self.current_view_type != "phase" or self.phase_preview is None
                or self._manual_preview_signature() != self._phase_input_signature):
            self.phase_start_status.setText("Inputs changed. Plot Phase Division again before testing rules.")
            return False
        from branch_start_preview import build_preview_context

        _, winding, layout, transposition = self._manual_preview_parameters()
        context = build_preview_context(pattern, winding, layout, transposition,
                                        self.phase_preview["records"], division_rule)
        if context["status"] != "division_candidate":
            self.phase_start_status.setText(context["reason"])
            return False
        self._manual_start_context = context
        self._manual_start_results.clear()
        self.phase_start_mode.blockSignals(True)
        self.phase_start_mode.setChecked(True)
        self.phase_start_mode.blockSignals(False)
        self.phase_start_branch.blockSignals(True)
        self.phase_start_branch.clear()
        for branch in context["branches"]:
            self.phase_start_branch.addItem(
                f"Phase {self._phase_label(branch['phase'])} / Branch {branch['number']}", branch['id'])
        self.phase_start_branch.blockSignals(False)
        self.phase_start_branch.setEnabled(True)
        self._manual_branch_changed()
        return True

    def _manual_branch_changed(self, _index=None):
        context = self._manual_start_context
        if context is None:
            return
        result = self._manual_start_results.get(self.phase_start_branch.currentData())
        if result:
            slot, layer = result["start"]
            text = f"Slot {slot+1}, layer {layer+1}: {result['reason']}"
        elif context["status"] == "candidate":
            text = "Click a highlighted conductor in this branch to preview a new inlet. Dashed paths are candidates only."
        elif context["status"] == "division_candidate":
            text = "Click a highlighted conductor to preview this candidate branch's members; connections are not generated."
        else:
            text = context["reason"]
        self.phase_start_status.setText(text)
        self.layout_display.setPlainText("Manual start preview — candidate only\n" + text + "\n\n" +
                                         self.phase_preview.get("report", ""))
        self._render_phase_preview()

    def _reset_manual_starts(self):
        self._manual_start_results.clear()
        self._manual_branch_changed()

    def _pick_manual_start(self, event):
        if (self.current_view_type != "phase" or not self.phase_start_mode.isChecked()
                or event.inaxes is not self.ax or event.button != 1
                or self._manual_start_context is None):
            return
        if self._manual_preview_signature() != self._phase_input_signature:
            self.phase_start_status.setText("Inputs changed. Plot Phase Division again before choosing starts.")
            return
        selected = None
        for patch in self.ax.patches:
            gid = patch.get_gid() or ""
            if gid.startswith("slot=") and patch.contains(event)[0]:
                parts = dict(item.split("=") for item in gid.split(";"))
                selected = int(parts["slot"]) - 1, int(parts["layer"]) - 1
                break
        if selected is not None:
            self._select_manual_start(*selected)

    def _select_manual_start(self, slot, layer):
        """Store a draft selection without publishing winding calculation state."""
        from branch_start_preview import preview_branch_start
        if self._manual_preview_signature() != self._phase_input_signature:
            self.phase_start_status.setText("Inputs changed. Plot Phase Division again before choosing starts.")
            return
        branch_id = self.phase_start_branch.currentData()
        context = self._manual_start_context
        branches = context["branches"]
        owner = next((branch for branch in branches
                      if (slot, layer) in (branch.get("members") or
                                           tuple(conductor[:2] for conductor in branch["path"]))), None)
        if owner is not None and owner["id"] != branch_id:
            branch_id = owner["id"]
            self.phase_start_branch.blockSignals(True)
            self.phase_start_branch.setCurrentIndex(self.phase_start_branch.findData(branch_id))
            self.phase_start_branch.blockSignals(False)
        result = preview_branch_start(context, branch_id, slot, layer)
        if result["status"] != "rejected":
            if any(other != branch_id and saved["status"] != "rejected" and saved["start"] == (slot, layer)
                   for other, saved in self._manual_start_results.items()):
                result = dict(result, status="rejected", path=(),
                              reason="This start is already selected by another branch.")
        self._manual_start_results[branch_id] = result
        self._manual_branch_changed()

    def _draw_manual_start_overlay(self):
        if not self.phase_start_mode.isChecked() or self._manual_start_context is None:
            return
        data, context = self.phase_preview, self._manual_start_context
        circular = self.phase_view_selector.currentText() == "Circular"
        def point(conductor):
            slot, layer = conductor[:2]
            if not circular:
                return slot + 1, layer + 1
            angle = (-1 if data["clockwise"] else 1) * 2 * math.pi * slot / data["slots"]
            radius = 1 - (layer + 0.5) * 0.52 / data["layers"]
            return radius * math.cos(angle), radius * math.sin(angle)
        branch_id = self.phase_start_branch.currentData()
        branch = next((b for b in context["branches"] if b["id"] == branch_id), None)
        if branch is None:
            return
        # Outline selectable members before the user chooses an inlet.
        members = branch.get("members") or branch["path"]
        if members:
            xs, ys = zip(*(point(c) for c in members))
            division = context["status"] == "division_candidate"
            self.ax.scatter(xs, ys, s=42 if division else 18, facecolors="none",
                            edgecolors="#202020", linewidths=1.2 if division else 0.6,
                            zorder=4, gid="manual-selectable")
        result = self._manual_start_results.get(branch_id)
        color = ("#6530ae", "#167747", "#bf3030")[branch["phase"]]
        if result and result["path"]:
            pairs = list(zip(result["path"], result["path"][1:]))
            if result.get("closed") and len(result["path"]) > 1:
                pairs.append((result["path"][-1], result["path"][0]))
            for index, (start, end) in enumerate(pairs):
                if circular:
                    pieces = [[point(start), point(end)]]
                else:
                    x, y = point(start)
                    direction = dfig.get_conn_direction(start[0], end[0], data["slots"])
                    delta = ((end[0]-start[0]) % data["slots"] if direction >= 0
                             else -((start[0]-end[0]) % data["slots"]))
                    pieces = dfig._split_unwrapped_path([(x, y), (x+delta, end[1]+1)], data["slots"])
                for piece in pieces:
                    xs, ys = zip(*piece)
                    self.ax.plot(xs, ys, linestyle="--", color=color, linewidth=1.5,
                                 zorder=5, gid=f"manual-preview-{branch_id}-{index}")
        for bid, saved in self._manual_start_results.items():
            x, y = point(saved["start"])
            valid = saved["status"] != "rejected"
            self.ax.plot(x, y, marker="*" if valid else "x", markersize=11,
                         color=("#151515" if bid == branch_id else "#555555") if valid else "#b91c1c",
                         markeredgecolor="white" if valid else "#b91c1c", markeredgewidth=0.6, zorder=7,
                         gid=f"manual-start-{bid}")
        title = (f"Candidate members: Phase {self._phase_label(branch['phase'])} / Branch {branch['number']} | No connections"
                 if context["status"] == "division_candidate" else
                 f"Candidate: Phase {self._phase_label(branch['phase'])} / Branch {branch['number']} | Not applied")
        self.ax.set_title(title, fontsize=10)

    def fit_phase_grid(self):
        """Backward-compatible alias for restoring the current plot view."""
        self.fit_plot_view()

    def _render_phase_preview(self, _view=None):
        """Render cached records so view changes cannot change their assignment."""
        if self.current_view_type != "phase" or self.phase_preview is None:
            return
        from matplotlib.patches import Wedge, Rectangle, Patch
        data = self.phase_preview
        slots, layers = data["slots"], data["layers"]
        from matplotlib import colormaps
        palette = colormaps['tab20'].resampled(data['phases'])
        colors = [palette(index) for index in range(data['phases'])]
        self._show_layout_plot_canvas()
        self.ax.clear()
        self._apply_plot_background(self.get_field_value("ui_theme") if "ui_theme" in self.input_fields else "Light")
        # Use the full rectangular canvas. Equal data scaling is preserved by
        # adjustable="datalim" below, rather than shrinking the axes to a square.
        # A vertical phase legend needs only a narrow right-hand margin.
        self.ax.set_position([0.02, 0.11, 0.88, 0.82])
        font_scale = max(0.55, min(1.0, self.canvas.width() / 560, self.canvas.height() / 560))
        circular = self.phase_view_selector.currentText() == "Circular"
        selected_members = None
        if self.phase_start_mode.isChecked() and self._manual_start_context is not None:
            if self._manual_start_context["status"] == "division_candidate":
                branch_id = self.phase_start_branch.currentData()
                branch = next((b for b in self._manual_start_context["branches"]
                               if b["id"] == branch_id), None)
                if branch is not None:
                    selected_members = set(branch["members"])
        for slot, layer, phase, sign in data["records"]:
            if circular:
                angle = (-1 if data["clockwise"] else 1) * 360 * slot / slots
                radius = 1.0 - layer * 0.52 / layers
                patch = Wedge((0, 0), radius, angle-180/slots, angle+180/slots,
                              width=0.52/layers, facecolor=colors[phase], edgecolor="#454545", linewidth=0.4)
                r = radius - 0.26/layers
                x, y = r * math.cos(math.radians(angle)), r * math.sin(math.radians(angle))
            else:
                x, y = slot+1, layer+1
                patch = Rectangle((x-.5, y-.5), 1, 1, facecolor=colors[phase],
                                  edgecolor="#454545", linewidth=0.4)
            self.ax.add_patch(patch)
            if self.phase_start_mode.isChecked():
                patch.set_alpha((0.95 if (slot, layer) in selected_members else 0.14)
                                if selected_members is not None else 0.28)
            patch.set_gid(f"slot={slot+1};layer={layer+1};phase={self._phase_label(phase)};sign={sign}")
            self.ax.text(x, y, "+" if sign > 0 else "-", ha="center", va="center",
                         fontsize=max(3, min(9, 420/slots) * font_scale), color="#151515")
        if circular:
            for slot in range(slots):
                angle = (-1 if data["clockwise"] else 1) * 2 * math.pi * slot / slots
                self.ax.text(1.07*math.cos(angle), 1.07*math.sin(angle), str(slot+1),
                             ha="center", va="center", fontsize=max(3, min(10, 520/slots) * font_scale))
            self.ax.text(0, 0, f"Layers 1–{layers}\nOuter → inner\nDirection: + / -",
                         ha="center", va="center", fontsize=9 * font_scale)
            self.ax.set_xlim(-1.16, 1.16, auto=True)
            self.ax.set_ylim(-1.16, 1.16, auto=True)
            self.ax.set_aspect("equal", adjustable="datalim")
            self.ax.axis("off")
        else:
            self.ax.set_position([0.08, 0.13, 0.80, 0.76])
            self.ax.set_xlim(.5, slots+.5)
            self.ax.set_ylim(layers+.5, .5)
            self.ax.set_aspect("auto")
            self.ax.set_xticks(range(1, slots+1))
            self.ax.set_yticks(range(1, layers+1))
            self.ax.tick_params(axis="x", labelsize=max(4, min(9, 500/slots)), labelrotation=90 if slots > 36 else 0)
            self.ax.set_xlabel("Slot")
            self.ax.set_ylabel("Layer (outer to inner)")
        self.ax.set_title(f"Phase division only | q = {data['q']}\n{data['slots']} slots / {data['poles']} poles",
                          fontsize=11 * font_scale)
        self.ax.legend(handles=[Patch(facecolor=color, label=self._phase_label(phase))
                                for phase, color in enumerate(colors)],
                       loc="upper left", bbox_to_anchor=(1.02, 1.0),
                       bbox_transform=self.ax.transAxes,
                       ncol=1, fontsize=9 * font_scale)
        self._draw_manual_start_overlay()
        self.canvas.draw()
        self._reset_plot_label_scale(self.ax)


    def create_stator_params_tab(self):
        fields = [
            ("Stack Length:", "120", "mm","stack_length"),
            ("Stator Outer Diameter:", "222", "mm","SD1"),
            ("Stator Inner Diameter:", "148", "mm","SD2"),
            ("Yoke Thickness:", "18", "mm","H_yoke"),
            ("Stator Tooth Tip Height (TH1):", "1.4", "mm","TH1"),
            ("Stator Tooth Tip Height (TH2):", "0.6", "mm","TH2"),
            ("Slot Width Ratio (ksw):", "0.55", " ","ksw"),
            ("Slot Opening Ratio (kso):", "0.3", " ","kso"),
        ]

        tab, _ = self.create_compact_parameter_tab("Stator", fields)
        return tab

    def create_inslot_params_tab(self):
        fields = [
            ("Gap Between Conductors:", "0.2", "mm","G_cond"),
            ("Side Clearance:", "0.105", "mm","C_side"),
            ("Radial Clearance:", "0.15", "mm","C_rad"),
            ("Insulation Thickness:", "0.22", "mm","d_Ins"),
            ("Coating Thickness:", "0.075", "mm","d_coat"),
            ("Wire Fillet Radius:", "0.5", "mm","Cond_Radi"),
            ("Overlap of Insulation:", "1", " ","Overlap_Ins",True)
        ]

        tab, _ = self.create_compact_parameter_tab("Inslot", fields)
        return tab

    def create_endwinding_params_tab(self):
        fields = [
    
            ("Min Side Gap of Conductors:", "0.5", "mm","gcond_min"),
            ("Min Side Bend Radius:", "1.5", "mm","Rbend_side_min"),
            ("Min Height Bend Radius:", "1.5", "mm","Rbend_height_min"),
            ("Pin End Straight Length:", "4", "mm","L_str"),
            ("Weld Straight Length:", "10", "mm","L_weld_str"),
            ("Gap Between Welding Points:", "3", "mm","gcond_weld"),
            ("Uniform End Winding Height:", "1", " ","Uni_EWH",True),
            ("Fixed Bend Radius:", "1", " ","fixed_Rbend",True),
        ]

        tab, _ = self.create_compact_parameter_tab("End Winding", fields)
        return tab

    def create_layout_params_tab(self):
        """Compact two-column layout controls without changing parameter keys."""
        tab = QWidget()
        grid = QGridLayout(tab)
        self.layout_params_grid = grid
        grid.setContentsMargins(16, 14, 16, 14)
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        def line_field(value, key):
            field = QLineEdit(value)
            field.setAlignment(Qt.AlignmentFlag.AlignCenter)
            field.setMinimumWidth(120)
            field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.input_fields[key] = field
            return field

        def checkbox_field(value, key):
            field = QCheckBox()
            field.setChecked(value == "1")
            self.input_fields[key] = field
            return field

        def combo_field(value, key, options):
            field = QComboBox()
            field.addItems(options)
            field.setCurrentText(value)
            field.setMinimumWidth(120)
            field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.input_fields[key] = field
            return field

        def add_field(row, column, label, field):
            grid.addWidget(QLabel(label), row, column)
            grid.addWidget(field, row, column + 1)

        pattern_field = line_field(gw.get_pattern_label("UWP"), "pattern_name")
        add_field(0, 0, "Pattern:", pattern_field)
        self.config_inlet_positions_button = QPushButton("Inlet setup")
        self.config_inlet_positions_button.setToolTip("Configure inlet positions")
        self.config_inlet_positions_button.setMinimumHeight(28)
        QTimer.singleShot(
            0, lambda: self.config_inlet_positions_button.setFixedHeight(pattern_field.height()))
        self.config_inlet_positions_button.setStyleSheet("""
            QPushButton {
                background-color: #e6f0ff;
                border: 1px solid #7ca7e8;
                border-radius: 4px;
                color: #174a91;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #d5e6ff; }
            QPushButton:pressed { background-color: #bdd7fb; }
        """)
        self.config_inlet_positions_button.clicked.connect(self.open_inlet_position_dialog)
        grid.addWidget(self.config_inlet_positions_button, 0, 2, 1, 2)
        switch_row = QWidget()
        switch_layout = QHBoxLayout(switch_row)
        switch_layout.setContentsMargins(0, 0, 0, 0)
        switch_layout.setSpacing(10)
        for label, key in (("Weld inlet:", "inlet_from_weld_side"),
                           ("CHW shift:", "radial_shift"),
                           ("Clockwise:", "CW"),
                           ("Connect ends:", "in_out_connection")):
            field = checkbox_field("1" if key == "CW" else "0", key)
            label_widget = QLabel(label)
            if key == "inlet_from_weld_side":
                self.weld_inlet_label = label_widget
            switch_layout.addWidget(label_widget)
            switch_layout.addWidget(field)
            if key != "CW":
                help_button = self._make_option_help_button()
                self._option_help_buttons[key] = help_button
                switch_layout.addWidget(help_button)
        switch_layout.addStretch()
        grid.addWidget(switch_row, 1, 0, 1, 4)

        shift_row = QWidget()
        shift_layout = QHBoxLayout(shift_row)
        shift_layout.setContentsMargins(0, 0, 0, 0)
        shift_layout.setSpacing(8)

        shift_mode = combo_field("None", "phase_shift_pattern",
                                 ["None", "Normal", "Increment"])
        shift_slot = line_field("0", "phase_shift")
        shift_layer = line_field("1", "PSL")
        shift_mode.setFixedWidth(150)
        shift_slot.setFixedWidth(72)
        shift_layer.setFixedWidth(72)
        for label, field in (("Shift mode:", shift_mode),
                             ("Shift slot:", shift_slot),
                             ("Shift layer:", shift_layer)):
            shift_layout.addWidget(QLabel(label))
            shift_layout.addWidget(field)
        shift_layout.addStretch()
        grid.addWidget(shift_row, 2, 0, 1, 4)

        pattern_label_area = QWidget()
        pattern_label_layout = QVBoxLayout(pattern_label_area)
        pattern_label_layout.setContentsMargins(0, 0, 8, 0)
        pattern_label_layout.setSpacing(6)
        pattern_label = QLabel("Select Pattern:")
        pattern_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        pattern_label_layout.addWidget(pattern_label)
        self.pattern_help_button = QPushButton("? Help")
        self.pattern_help_button.setToolTip("Open the illustrated Pattern Guide.")
        self.pattern_help_button.setMinimumHeight(28)
        self.pattern_help_button.clicked.connect(self.open_pattern_help)
        pattern_label_layout.addWidget(self.pattern_help_button)
        self.connection_rules_button = QPushButton("Connection Rules")
        self.connection_rules_button.setToolTip(
            "Open the visual reference for shared connection rules.")
        self.connection_rules_button.setMinimumHeight(28)
        self.connection_rules_button.clicked.connect(self.open_connection_rules)
        pattern_label_layout.addWidget(self.connection_rules_button)
        pattern_label_layout.addStretch()
        grid.addWidget(pattern_label_area, 3, 0)
        pattern_buttons_container = QWidget()
        pattern_buttons_layout = QGridLayout(pattern_buttons_container)
        self.pattern_buttons_layout = pattern_buttons_layout
        pattern_buttons_layout.setContentsMargins(0, 0, 0, 0)
        pattern_buttons_layout.setHorizontalSpacing(8)
        pattern_buttons_layout.setVerticalSpacing(6)
        self.pattern_buttons = {}
        for index, pattern in enumerate(gw.get_available_patterns()):
            button = QPushButton(pattern)
            button.setProperty("patternChoice", True)
            button.setMinimumHeight(30)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.clicked.connect(lambda _, p=pattern: self.set_pattern_with_validation(p))
            self.pattern_buttons[pattern] = button
            row, column = divmod(index, 5)
            pattern_buttons_layout.addWidget(button, row, column)
            pattern_buttons_layout.setColumnStretch(column, 1)
        grid.addWidget(pattern_buttons_container, 3, 1, 1, 3)
        grid.setRowStretch(4, 1)
        return tab

    def _pattern_base_inputs(self):
        """Read q and slots without changing the current input fields."""
        poles = int(self.input_fields["num_poles"].text())
        phases = int(self.input_fields["num_phases"].text())
        naa = int(self.input_fields["ab"].text())
        layers = int(self.input_fields["num_layers"].text())
        mode = self.input_fields["winding_input_mode"].currentText()
        if mode == "Slots and poles":
            slots = int(self.input_fields["num_slots"].text())
            q = phase_topology.winding_q(slots, poles, phases)
        else:
            q = phase_topology.parse_q(self.input_fields["q"].text())
            if (q * poles * phases).denominator != 1:
                raise ValueError("q, poles and phases must produce an integer slot count.")
        if naa <= 0 or layers <= 0:
            raise ValueError("Naa and layer count must be positive integers.")
        return q, poles, naa, layers, phases

    def _base_selected_route_decision(self, inputs=None):
        """Classify the selected factors without applying current layout options."""
        q, poles, branches, layers, phases = (
            self._pattern_base_inputs() if inputs is None else inputs)
        pattern = gw.normalize_pattern_name(
            self.input_fields['pattern_name'].text())
        selected = self._selected_dividers()
        winding = NS(q=int(q) if q.denominator == 1 else q,
                     num_slots=int(q * poles * phases), num_poles=poles,
                     num_layers=layers, num_phases=phases, ab=branches,
                     branch_dividers=selected)
        return gw.resolve_pattern_route(pattern, winding, selected)

    def _base_pattern_support(self, pattern, inputs):
        key = (pattern, *inputs)
        if key not in self._pattern_support_cache:
            if len(self._pattern_support_cache) >= 256:
                self._pattern_support_cache.clear()
            self._pattern_support_cache[key] = gw.evaluate_base_pattern_support(
                pattern, *inputs)
        return self._pattern_support_cache[key]

    def _schedule_pattern_availability(self, _value=None):
        self._refresh_weld_inlet_availability()
        self._refresh_route_option_availability()
        for button in self.pattern_buttons.values():
            button.setEnabled(False)
            button.setToolTip("Checking base Pattern support for the current winding inputs.")
        self._pattern_support_timer.start(120)

    def _refresh_pattern_availability(self):
        try:
            inputs = self._pattern_base_inputs()
        except (ValueError, TypeError, ZeroDivisionError) as exc:
            for button in self.pattern_buttons.values():
                button.setEnabled(False)
                button.setToolTip(str(exc))
            selector = getattr(self, "layout_pattern_selector", None)
            if selector is not None:
                for index in range(selector.count()):
                    item = selector.model().item(index)
                    item.setEnabled(False)
                    item.setToolTip(str(exc))
            self._mark_selected_pattern_unavailable(str(exc))
            self._refresh_weld_inlet_availability()
            self._refresh_route_option_availability()
            self._refresh_fractional_uwp_transposition_options(None)
            return
        for pattern, button in self.pattern_buttons.items():
            supported, reason = self._base_pattern_support(pattern, inputs)
            button.setEnabled(supported)
            button.setToolTip(reason)
            selector = getattr(self, "layout_pattern_selector", None)
            if selector is not None:
                index = selector.findData(pattern)
                if index >= 0:
                    item = selector.model().item(index)
                    item.setEnabled(supported)
                    item.setToolTip(reason)
        self._mark_selected_pattern_unavailable()
        self._refresh_weld_inlet_availability(inputs)
        self._refresh_route_option_availability(inputs)
        self._refresh_fractional_uwp_transposition_options(inputs)

    def _refresh_weld_inlet_availability(self, inputs=None):
        """Reflect route-specific weld inlet availability and fixed requirements."""
        field = self.input_fields["inlet_from_weld_side"]
        label = getattr(self, "weld_inlet_label", None)
        if inputs is None:
            try:
                inputs = self._pattern_base_inputs()
            except (ValueError, TypeError, ZeroDivisionError):
                inputs = None

        try:
            insert = (self._route_option_decision(inputs, weld_inlet=False)
                      if inputs is not None else None)
            weld = (self._route_option_decision(inputs, weld_inlet=True)
                    if inputs is not None else None)
        except (AttributeError, KeyError, TypeError, ValueError,
                ZeroDivisionError, OverflowError):
            insert = weld = None

        if insert is not None and weld is not None:
            insert_ok = insert.status != 'disabled'
            weld_ok = weld.status != 'disabled'
            if insert_ok and not weld_ok:
                reason = weld.reason + " Keep Weld inlet off; do not click."
                if field.isChecked():
                    self.message_log.append("Weld inlet was turned off: " + weld.reason)
                self._set_option_availability(
                    "inlet_from_weld_side", False, reason, checked=False)
                if label is not None:
                    label.setToolTip(reason)
                return
            if weld_ok and not insert_ok:
                reason = insert.reason + " The setting is fixed on."
                self._set_option_availability(
                    "inlet_from_weld_side", False, reason, checked=True)
                if label is not None:
                    label.setToolTip(reason)
                return

        self._set_option_availability("inlet_from_weld_side", True)
        if label is not None:
            label.setToolTip("")

    def _refresh_fractional_uwp_transposition_options(self, inputs):
        """Show the grouped transposition path for fractional UWP inputs."""
        try:
            noninteger = inputs is not None and inputs[0].denominator != 1
            decision = (self._base_selected_route_decision(inputs)
                        if noninteger else None)
            fractional_uwp = (decision is not None
                              and decision.status in ('enabled', 'candidate')
                              and decision.route_name in
                              ('uwp_half_integer_p2', 'uwp_half_integer_q_pp'))
        except (ValueError, KeyError, TypeError, ZeroDivisionError):
            noninteger = False
            fractional_uwp = False
        if noninteger:
            reason = "Only needed for fractional q. Open Advanced to set PoleN/PoleS transposition."
            if not fractional_uwp:
                reason += " Grouped transposition requires half-integer q, UWP, and Naa = 2q."
        else:
            reason = ""
        self.fractional_tp_notice.setText(reason)
        self.fractional_advanced_row.setVisible(noninteger)
        self.fractional_tp_notice.setVisible(noninteger)
        self.pole_group_advanced_content.setEnabled(fractional_uwp)
        self.pole_group_advanced_toggle.setEnabled(fractional_uwp)
        self.pole_group_advanced_toggle.setToolTip(reason if noninteger else "")
        self._refresh_pole_group_tp_adjacency(inputs, fractional_uwp)
        model = self.tp_type_field.model()
        for index in range(1, self.tp_type_field.count()):
            item = model.item(index)
            item.setEnabled(not noninteger)
            item.setToolTip(reason if noninteger else "")
        self.tp_type_field.setToolTip(
            reason if noninteger else '')

    def _refresh_pole_group_guidance(self):
        try:
            inputs = self._pattern_base_inputs()
            decision = self._base_selected_route_decision(inputs)
            fractional_uwp = (decision.status in ('enabled', 'candidate')
                              and decision.route_name in
                              ('uwp_half_integer_p2', 'uwp_half_integer_q_pp'))
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            inputs, fractional_uwp = None, False
        self._refresh_pole_group_tp_adjacency(inputs, fractional_uwp)

    def _refresh_pole_group_tp_adjacency(self, inputs, fractional_uwp):
        """Show phase-relative start-pole branch counts and legal positions."""
        if not hasattr(self, "pole_group_cond_labels"):
            return

        details = None
        unavailable_reason = "Available for half-integer UWP with Naa = 2q."
        if fractional_uwp and inputs is not None:
            try:
                q, poles, branches, layers, phases = inputs
                shifts = gw.get_phase_shift_list(
                    NS(num_layers=layers),
                    self.input_fields["phase_shift_pattern"].currentText(),
                    self.get_int_field("phase_shift", 0),
                    self.get_int_field("PSL", 1),
                )
                winding = NS(q=q, num_slots=int(q * poles * phases),
                             num_poles=poles, num_layers=layers,
                             num_phases=phases, ab=branches)
                signature = (q, poles, branches, layers, phases, tuple(shifts),
                             bool(self.input_fields["inlet_from_weld_side"].isChecked()),
                             bool(self.input_fields["radial_shift"].isChecked()))
                cache = getattr(self, "_pole_group_tp_adjacency_cache", {})
                if signature in cache:
                    details = cache[signature]
                else:
                    layout = NS(
                        phase_shift_list=shifts,
                        radial_shift=self.get_int_field("radial_shift", 0),
                        inlet_from_weld_side=int(
                            self.input_fields["inlet_from_weld_side"].isChecked()),
                    )
                    base_tp = NS(tp_type="Regular", tp_interval=0, tp_times=0,
                                 uni_tp=0, pltp_fl=0, pltp_ll=0, jltp=0, jld=1,
                                 pole_group_tp={})
                    _starts, database = gw.get_winding_layout("UWP", base_tp,
                                                                winding, layout)
                    records = gw.phase_map(winding.num_slots, winding.num_poles,
                                           winding.num_layers, shifts)
                    paths = [branch[1][:] for branch in database]
                    members = gw._fractional_start_pole_groups(
                        paths, winding, records)
                    details = {}
                    for group in ("PoleN", "PoleS"):
                        candidates = gw._fractional_swap_candidates(
                            paths, winding, records, group, shifts)
                        phases_at_position = {}
                        for first, _second, left, _right in candidates:
                            phases_at_position.setdefault(left // 2, set()).add(
                                first // branches)
                        positions = {position for position, present in
                                     phases_at_position.items()
                                     if len(present) == phases}
                        counts = [len(members[group][phase])
                                  for phase in range(phases)]
                        insert_positions = max(0, len(paths[0]) // 2 - 1)
                        details[group] = (counts, len(positions), insert_positions)
                    if len(cache) >= 16:
                        cache.clear()
                    cache[signature] = details
                    self._pole_group_tp_adjacency_cache = cache
            except (AttributeError, TypeError, ValueError, ZeroDivisionError) as exc:
                details = None
                unavailable_reason = str(exc)

        for group, prefix in (("PoleN", "pole_n"), ("PoleS", "pole_s")):
            counts, position_count, insert_positions = (
                details[group] if details is not None else ([], 0, 0))
            can_swap = position_count > 0
            can_cycle = (insert_positions > 0 and bool(counts)
                         and all(count >= 2 for count in counts))
            selector = self.input_fields[f"{prefix}_tp_type"]
            for index in range(1, selector.count()):
                selector.model().item(index).setEnabled(can_swap)
            for suffix in ("tp_interval", "tp_times", "uni_tp", "pltp_fl",
                           "pltp_ll", "jltp"):
                field = self.input_fields[f"{prefix}_{suffix}"]
                available = can_cycle if suffix == "uni_tp" else can_swap
                field.setValidator(None if available else self._zero_tp_validator)
            if details is None:
                self.pole_group_cond_labels[prefix].setText("-- branches")
                self.pole_group_tp_hints[prefix].setText(unavailable_reason)
                continue

            if len(set(counts)) == 1:
                count = counts[0]
                label = f"{count} {'branch' if count == 1 else 'branches'}"
            else:
                label = " / ".join(
                    f"{chr(65 + phase)}: {count}"
                    for phase, count in enumerate(counts))
            self.pole_group_cond_labels[prefix].setText(label)
            if position_count <= 0:
                self.pole_group_tp_hints[prefix].setText(
                    "No insertion-side positions."
                    if insert_positions <= 0 else
                    "No pair for transposition. Use Regular with all offsets 0."
                    if max(counts) < 2 else
                    "No legal pair exchanges. Uniform 1 may still rotate all "
                    "branches; Plot Layout validates the cycle.")
                continue
            self.pole_group_tp_hints[prefix].setText(
                f"Nominal input range: Times 1-{position_count}; "
                f"Interval 1-{position_count} insertion positions. "
                "Regular offsets are validated against candidate paths.")

    def _mark_selected_pattern_unavailable(self, reason=None):
        field = self.input_fields["pattern_name"]
        if reason is None:
            try:
                pattern = gw.normalize_pattern_name(field.text())
                button = self.pattern_buttons[pattern]
                reason = button.toolTip() if not button.isEnabled() else None
            except (ValueError, KeyError):
                reason = "Unknown Pattern."
        unavailable = reason is not None
        field.setProperty("patternUnavailable", unavailable)
        field.setToolTip(reason or "Base Pattern is available for these winding dimensions.")
        field.style().unpolish(field)
        field.style().polish(field)

    def set_pattern_with_validation(self, pattern):
        """Select only Patterns with a generated base layout for these dimensions."""
        try:
            pattern_id = gw.normalize_pattern_name(pattern)
            inputs = self._pattern_base_inputs()
        except ValueError as exc:
            self.message_log.append(f"Invalid pattern or winding input: {exc}")
            return
        supported, reason = self._base_pattern_support(pattern_id, inputs)
        if not supported:
            self.message_log.append(f"Error: {gw.get_pattern_label(pattern_id)} is unavailable: {reason}")
            return

        self._resolve_slot_inputs()
        pattern_label = gw.get_pattern_label(pattern_id)
        if gw.pattern_requires_weld_side_inlet(pattern_id):
            self.input_fields["inlet_from_weld_side"].setChecked(True)
            self.message_log.append(f"Warning: {pattern_label} requires inlet from weld side; inlet_from_weld_side enabled.")
        self.input_fields["pattern_name"].setText(pattern_label)
        self.message_log.append(f"Pattern '{pattern_label}' selected.")

    def open_pattern_help(self):
        """Open the local illustrated guide for the available Pattern families."""
        guide_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "pattern_guide.html")
        if not os.path.isfile(guide_path):
            self.message_log.append("Pattern Guide is unavailable: pattern_guide.html was not found.")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(guide_path)):
            self.message_log.append("Pattern Guide could not be opened by the system browser.")

    def open_connection_rules(self):
        """Open the local visual reference for shared connection rules."""
        rules_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "connection_rules.html")
        if not os.path.isfile(rules_path):
            self.message_log.append(
                "Connection Rules are unavailable: connection_rules.html was not found.")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(rules_path)):
            self.message_log.append(
                "Connection Rules could not be opened by the system browser.")

    def _safe_int_list(self, values):
        if values is None:
            return []
        if isinstance(values, str):
            parts = [part.strip() for part in values.replace(";", ",").split(",")]
            return [int(part) for part in parts if part]
        return [int(value) for value in values]

    def _coerce_phase_a_adjustments(self, branch_count, pattern_id=None, strict=False):
        values = self._safe_int_list(getattr(self, "inlet_index_adjustments_phase_a", []))
        values = values[:branch_count] + [0] * max(0, branch_count - len(values))
        if pattern_id and gw.pattern_requires_weld_side_inlet(pattern_id):
            odd_indexes = [index + 1 for index, value in enumerate(values) if value % 2 != 0]
            if odd_indexes and strict:
                raise ValueError(
                    "ZPP/LPP require weld-side inlet parity; odd inlet index adjustments are not allowed for Phase A Branch "
                    + ", ".join(str(index) for index in odd_indexes)
                    + "."
                )
        self.inlet_index_adjustments_phase_a = values
        return values

    def open_inlet_position_dialog(self):
        try:
            if self.tp_type_field.currentText() == "Auto":
                self.apply_auto_configuration(preserve_inlet_adjustments=True)
            self.extract_parameters()
            branch_count = int(self.Winding_Para.ab)
            pattern_id = gw.normalize_pattern_name(self.input_fields["pattern_name"].text())
        except Exception as exc:
            self.message_log.append(f"Cannot configure inlet positions before valid parameters: {exc}")
            return
        values = self._coerce_phase_a_adjustments(branch_count, pattern_id, strict=False)
        dialog = InletPositionDialog(
            self,
            branch_count,
            values,
            force_even=gw.pattern_requires_weld_side_inlet(pattern_id),
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.inlet_index_adjustments_phase_a = dialog.applied_values
            self.volt_diff_inlet_adjustments_all = []
            self.vd_adjustment_inputs = []
            self.message_log.append(
                "Phase A inlet index adjustments applied: "
                + ", ".join(str(value) for value in self.inlet_index_adjustments_phase_a)
            )
            try:
                self.extract_parameters()
            except ValueError as exc:
                self.message_log.append(f"Input or pattern validation failed after inlet adjustment: {exc}")

    def _normalized_signed_adjustment(self, shift, count):
        if count <= 0:
            return 0
        shift = int(shift) % count
        if shift > count / 2:
            shift -= count
        return shift

    def _rotate_conductors(self, conductors, adjustment):
        if not conductors:
            return conductors
        shift = int(adjustment) % len(conductors)
        return list(conductors[shift:]) + list(conductors[:shift])

    def _phase_for_conductor(self, conductor_id, cond_info):
        try:
            return cio.get_phase_index(conductor_id[0], conductor_id[1], cond_info)
        except Exception:
            return None

    def _phase_a_branch_infos(self, db_conductor_id, cond_info, expected_count=None):
        phase_a = []
        if expected_count is None:
            expected_count = getattr(getattr(self, "Winding_Para", None), "ab", 0)
        for list_index, branch_info in enumerate(db_conductor_id):
            branch_id, conductors = branch_info
            if not conductors:
                continue
            phase = self._phase_for_conductor(conductors[0], cond_info)
            if phase == 0:
                phase_a.append((list_index, branch_id, conductors))
        if expected_count and len(phase_a) < expected_count:
            phase_a = [
                (index, branch_info[0], branch_info[1])
                for index, branch_info in enumerate(db_conductor_id[:expected_count])
            ]
        return phase_a[:expected_count] if expected_count else phase_a

    def apply_phase_a_inlet_adjustments(self, db_conductor_id, cond_info, adjustments, expected_count=None):
        adjusted_db = [[branch_id, list(conductors)] for branch_id, conductors in db_conductor_id]
        for phase_a_index, (list_index, _branch_id, conductors) in enumerate(
            self._phase_a_branch_infos(adjusted_db, cond_info, expected_count=expected_count)
        ):
            if phase_a_index >= len(adjustments):
                break
            adjusted_db[list_index][1] = self._rotate_conductors(conductors, adjustments[phase_a_index])
        return adjusted_db

    def _coerce_all_branch_adjustments(self, branch_count, pattern_id=None, strict=False):
        values = self._safe_int_list(getattr(self, "volt_diff_inlet_adjustments_all", []))
        if not values:
            return None
        if len(values) != branch_count:
            if strict:
                raise ValueError(
                    f"Volt Diff inlet adjustments contain {len(values)} branches; expected {branch_count}."
                )
            self.volt_diff_inlet_adjustments_all = []
            return None
        if pattern_id and gw.pattern_requires_weld_side_inlet(pattern_id):
            odd_indexes = [index + 1 for index, value in enumerate(values) if value % 2 != 0]
            if odd_indexes:
                if strict:
                    raise ValueError(
                        "ZPP/LPP require weld-side inlet parity; odd Volt Diff inlet adjustments are not allowed for Branch "
                        + ", ".join(str(index) for index in odd_indexes)
                        + "."
                    )
                self.volt_diff_inlet_adjustments_all = []
                return None
        self.volt_diff_inlet_adjustments_all = values
        return values

    def apply_all_branch_inlet_adjustments(self, db_conductor_id, adjustments):
        adjusted_db = []
        for index, (branch_id, conductors) in enumerate(db_conductor_id):
            adjustment = adjustments[index] if index < len(adjustments) else 0
            adjusted_db.append([branch_id, self._rotate_conductors(conductors, adjustment)])
        return adjusted_db

    def _voltage_drop_input(self):
        return float(str(self.get_field_value("vd_phase_voltage_drop")).strip())

    def _voltage_index_span_input(self, cond_info):
        default_span = max([int(cond[4]) for cond in cond_info if len(cond) > 4 and int(cond[4]) >= 0], default=1)
        return max(float(default_span), 1.0)

    def _compute_voltage_difference_matrix(self, cond_info, voltage_drop, index_span):
        result = vdo.compute_voltage_difference_matrix(
            cond_info,
            self.Winding_Para.num_slots,
            self.Winding_Para.num_layers,
            voltage_drop,
            index_span,
            num_phases=getattr(self.Winding_Para, "num_phases", 3),
        )
        self._vd_last_matrix_result = result
        return (
            result.voltage_matrix,
            result.equivalent_index_matrix,
            result.max_voltage,
            result.max_equivalent_index,
        )

    def _cond_info_for_db(self, db_conductor_id):
        return cio.update_cond_info_with_branch_data(list(self.base_cond_info), db_conductor_id)

    def _voltage_score_for_adjustments(self, adjustments, voltage_drop, index_span):
        db_conductor_id = self.apply_all_branch_inlet_adjustments(self.base_db_conductor_id, adjustments)
        cond_info = self._cond_info_for_db(db_conductor_id)
        _voltage_matrix, _index_matrix, max_voltage, max_index = self._compute_voltage_difference_matrix(
            cond_info,
            voltage_drop,
            index_span,
        )
        return max_voltage, max_index

    def _current_all_branch_adjustments(self):
        total = len(getattr(self, "base_db_conductor_id", []))
        if total <= 0:
            return []
        values = self._safe_int_list(getattr(self, "volt_diff_inlet_adjustments_all", []))
        if len(values) == total:
            return values
        values = [0] * total
        phase_a_adjustments = self._safe_int_list(getattr(self, "inlet_index_adjustments_phase_a", []))
        for phase_a_index, (list_index, _branch_id, _conductors) in enumerate(
            self._phase_a_branch_infos(self.base_db_conductor_id, self.base_cond_info)
        ):
            if phase_a_index < len(phase_a_adjustments):
                values[list_index] = phase_a_adjustments[phase_a_index]
        return values

    def _sync_phase_a_adjustments_from_all(self, all_adjustments):
        phase_a_values = []
        for list_index, _branch_id, _conductors in self._phase_a_branch_infos(self.base_db_conductor_id, self.base_cond_info):
            if list_index < len(all_adjustments):
                phase_a_values.append(all_adjustments[list_index])
        if phase_a_values:
            self.inlet_index_adjustments_phase_a = phase_a_values

    def _sync_vd_adjustments_from_inputs(self):
        edits = getattr(self, "vd_adjustment_inputs", [])
        if not edits:
            return False
        total = len(getattr(self, "base_db_conductor_id", []))
        if total <= 0 or len(edits) != total or not hasattr(self, "base_cond_info"):
            return False
        values = [0] * total
        for branch_index, edit in edits:
            values[branch_index] = int(str(edit.text()).strip() or "0")
        self.volt_diff_inlet_adjustments_all = values
        return True

    def _clear_layout_items(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            child_layout = item.layout()
            widget = item.widget()
            if child_layout is not None:
                self._clear_layout_items(child_layout)
            if widget is not None:
                widget.deleteLater()

    def _build_vd_branch_phase_rows(self):
        rows = []
        phase_counts = {}
        for branch_index, (branch_id, conductors) in enumerate(getattr(self, "base_db_conductor_id", [])):
            if not conductors:
                continue
            try:
                phase_index = self._phase_for_conductor(conductors[0], self.base_cond_info)
            except Exception:
                phase_index = branch_index // max(1, getattr(self.Winding_Para, "ab", 1))
            phase_counts[phase_index] = phase_counts.get(phase_index, 0) + 1
            rows.append({
                "branch_index": branch_index,
                "branch_id": branch_id,
                "phase_index": phase_index,
                "phase_branch_index": phase_counts[phase_index],
            })
        return rows

    def _vd_algorithm_id(self):
        try:
            return vdo.normalize_algorithm_id(self.get_field_value("vd_algorithm"))
        except Exception:
            return "auto"

    def _build_vd_optimization_problem(self, voltage_drop=None, index_span=None):
        if voltage_drop is None:
            voltage_drop = self._voltage_drop_input()
        if index_span is None:
            index_span = self._voltage_index_span_input(self.cond_info)
        pattern_id = gw.normalize_pattern_name(self.input_fields["pattern_name"].text())
        force_even = gw.pattern_requires_weld_side_inlet(pattern_id)
        return vdo.VDOptimizationProblem(
            self.base_cond_info,
            self.base_db_conductor_id,
            self._build_vd_branch_phase_rows(),
            self.Winding_Para.num_slots,
            self.Winding_Para.num_layers,
            voltage_drop,
            index_span,
            force_even=force_even,
            num_phases=getattr(self.Winding_Para, "num_phases", 3),
        )

    def _format_vd_estimate_time(self, estimate):
        seconds = float(estimate.get("estimated_sec", 0.0))
        if seconds < 0.01:
            return "<0.01 s"
        if seconds < 60:
            return f"{seconds:.2f} s"
        return f"{seconds / 60:.1f} min"

    def refresh_vd_optimization_estimate(self, *_args, parameters_current=False):
        if not hasattr(self, "vd_estimate_label"):
            return
        try:
            if not parameters_current:
                self.extract_parameters()
            problem = self._build_vd_optimization_problem()
            algorithm_id = self._vd_algorithm_id()
            estimate = problem.estimate_runtime(algorithm_id, vdo.DEFAULT_TIME_BUDGET_SEC)
            self.vd_estimate_label.setText("Est: " + self._format_vd_estimate_time(estimate))
        except Exception as exc:
            self.vd_estimate_label.setText(f"Est: unavailable ({exc})")

    def _refresh_vd_adjustment_grid(self):
        if not hasattr(self, "vd_adjustment_grid"):
            return
        self._clear_layout_items(self.vd_adjustment_grid)
        self.vd_adjustment_inputs = []
        branch_rows = self._build_vd_branch_phase_rows()
        if not branch_rows:
            self.vd_adjustment_grid.addWidget(QLabel("Run Update Volt Diff to initialize branch inputs."), 0, 0)
            return

        current_values = self._current_all_branch_adjustments()
        phases = sorted({row["phase_index"] for row in branch_rows})
        max_phase_branches = max(
            [sum(1 for row in branch_rows if row["phase_index"] == phase_index) for phase_index in phases],
            default=0,
        )
        validator = QIntValidator(-999999, 999999, self)
        for grid_row, phase_index in enumerate(phases):
            self.vd_adjustment_grid.addWidget(QLabel(f"Phase {self._phase_label(phase_index)}"), grid_row, 0)
            phase_rows = [row for row in branch_rows if row["phase_index"] == phase_index]
            for col_offset, row_info in enumerate(phase_rows, start=1):
                cell = QWidget()
                cell_layout = QHBoxLayout(cell)
                cell_layout.setContentsMargins(0, 0, 0, 0)
                cell_layout.setSpacing(4)
                cell_layout.addWidget(QLabel(f"B{row_info['phase_branch_index']}"))
                edit = QLineEdit(str(current_values[row_info["branch_index"]]))
                edit.setValidator(validator)
                edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
                edit.setFixedWidth(54)
                cell_layout.addWidget(edit)
                self.vd_adjustment_grid.addWidget(cell, grid_row, col_offset)
                self.vd_adjustment_inputs.append((row_info["branch_index"], edit))

        reset_button = QPushButton("Reset")
        reset_button.setFixedWidth(72)
        reset_button.clicked.connect(self.reset_vd_adjustments_to_zero)
        self.vd_adjustment_grid.addWidget(reset_button, 0, max_phase_branches + 1)
        self.vd_adjustment_grid.setColumnStretch(max_phase_branches + 2, 1)

    def reset_vd_adjustments_to_zero(self):
        edits = getattr(self, "vd_adjustment_inputs", [])
        if not edits:
            try:
                self.extract_parameters()
                self._refresh_vd_adjustment_grid()
                edits = getattr(self, "vd_adjustment_inputs", [])
            except Exception:
                edits = []
        total = len(getattr(self, "base_db_conductor_id", []))
        self.volt_diff_inlet_adjustments_all = [0] * total
        for _branch_index, edit in edits:
            edit.setText("0")
        self.update_voltage_difference_view()

    def update_voltage_difference_view(self):
        try:
            self._sync_vd_adjustments_from_inputs()
            self.extract_parameters()
            self._refresh_vd_adjustment_grid()
            voltage_drop = self._voltage_drop_input()
            index_span = self._voltage_index_span_input(self.cond_info)
            voltage_matrix, index_matrix, max_voltage, max_index = self._compute_voltage_difference_matrix(
                self.cond_info,
                voltage_drop,
                index_span,
            )
            adjacent_slot_same_layer = vdo.compute_adjacent_slot_voltage_difference(
                self.cond_info, self.Winding_Para.num_slots, self.Winding_Para.num_layers,
                voltage_drop, index_span, num_phases=getattr(self.Winding_Para, "num_phases", 3),
            )
            adjacent_slot_adjacent_layer = vdo.compute_adjacent_slot_interlayer_voltage_difference(
                self.cond_info, self.Winding_Para.num_slots, self.Winding_Para.num_layers,
                voltage_drop, index_span, num_phases=getattr(self.Winding_Para, "num_phases", 3),
            )
            self._update_vd_neighbour_summary(
                max_voltage, adjacent_slot_same_layer.max_voltage,
                adjacent_slot_adjacent_layer.max_voltage,
            )
            self._draw_voltage_difference_matrix(voltage_matrix, index_matrix)
            all_adjustments = self._current_all_branch_adjustments()
            matrix_result = getattr(self, "_vd_last_matrix_result", None)
            cross_phase_pairs = getattr(matrix_result, "cross_phase_pair_count", 0)
            total_pairs = getattr(matrix_result, "pair_count", 0)
            index_label = "Max equivalent index difference" if cross_phase_pairs else "Max index difference"
            phase_aware_text = f"Phase-aware voltage: on ({cross_phase_pairs}/{total_pairs} cross-phase adjacent pairs)"
            self.vd_result_display.setText(
                "Max voltage difference — same slot / adjacent layers (DC): "
                f"{max_voltage:.6g}\n"
                "Max voltage difference — adjacent slots / same layer (DC): "
                f"{adjacent_slot_same_layer.max_voltage:.6g}\n"
                "Max voltage difference — adjacent slots / adjacent layers (DC): "
                f"{adjacent_slot_adjacent_layer.max_voltage:.6g}\n"
                f"{index_label}: {max_index:.6g}\n"
                f"Voltage drop (DC): {voltage_drop:.6g}\n"
                f"{phase_aware_text}\n"
                "Current index adj. is shown in the Phase/Branch inputs.\n"
                "All branches: "
                + ", ".join(str(value) for value in all_adjustments)
            )
            self.refresh_vd_optimization_estimate(parameters_current=True)
            return voltage_matrix, index_matrix, max_voltage, max_index
        except Exception as exc:
            event_id = self._record_unexpected_error("volt_diff_update", exc)
            self._update_vd_neighbour_summary(None, None, None)
            if hasattr(self, "vd_result_display"):
                self.vd_result_display.setText(f"Volt Diff failed: {exc}\nReference: {event_id}")
            if hasattr(self, "message_log"):
                self.message_log.append(f"Volt Diff failed: {exc} [Reference: {event_id}]")
            return None

    def _update_vd_neighbour_summary(self, same_slot, adjacent_slot_same_layer, adjacent_slot_adjacent_layer):
        """Refresh the Volt Diff tab metrics without changing the plotted matrix."""
        values = (
            ("vd_same_slot_value", same_slot),
            ("vd_adjacent_slot_same_layer_value", adjacent_slot_same_layer),
            ("vd_adjacent_slot_adjacent_layer_value", adjacent_slot_adjacent_layer),
        )
        for attribute, value in values:
            label = getattr(self, attribute, None)
            if label is not None:
                label.setText("—" if value is None else f"{float(value):.6g} V")

    def _remove_vd_colorbar(self):
        if getattr(self, "vd_colorbar", None) is not None:
            try:
                self.vd_colorbar.remove()
            except Exception:
                pass
            self.vd_colorbar = None

    def _configure_vd_canvas_size(self, slot_count, row_count, annotation_mode):
        self._show_vd_plot_canvas()
        cell_width = self._vd_cell_width_input()
        cell_height = self._vd_cell_height_input()
        target_width = max(680, int(slot_count) * cell_width + 340)
        target_height = max(480, int(row_count) * cell_height + 180)
        self.vd_canvas.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.vd_canvas.setMinimumSize(target_width, target_height)
        self.vd_canvas.resize(target_width, target_height)
        self.vd_figure.set_size_inches(target_width / self.vd_figure.dpi, target_height / self.vd_figure.dpi, forward=True)
        self.vd_canvas.updateGeometry()

    def _vd_annotation_mode(self):
        try:
            return str(self.get_field_value("vd_annotation_mode")).strip()
        except Exception:
            return "No labels"

    def _vd_cell_width_input(self):
        return max(6, min(self.get_int_field("vd_cell_width", 40), 200))

    def _vd_cell_height_input(self):
        return max(12, min(self.get_int_field("vd_cell_height", 72), 300))

    def _vd_font_size_input(self):
        return max(4, min(self.get_int_field("vd_font_size", 7), 30))

    def _vd_slot_ticks(self, slot_count, cell_width, font_size):
        slot_count = max(0, int(slot_count))
        if slot_count <= 0:
            return []
        label_chars = max(1, len(str(slot_count)))
        min_spacing_px = max(10.0, label_chars * max(float(font_size), 1.0) * 0.9 + 6.0)
        step = max(1, int(math.ceil(min_spacing_px / max(float(cell_width), 1.0))))
        ticks = list(range(0, slot_count, step))
        last_tick = slot_count - 1
        if ticks and ticks[-1] != last_tick:
            if len(ticks) > 1 and last_tick - ticks[-1] < step:
                ticks[-1] = last_tick
            else:
                ticks.append(last_tick)
        return ticks

    def _vd_cell_label_font_size(self, label, base_size, cell_width, cell_height):
        figure = getattr(self, "vd_figure", self.figure)
        dpi = max(float(figure.dpi), 1.0)
        label_chars = max(1, len(str(label)))
        width_limit = max(4.0, float(cell_width) * 0.92 * 72.0 / dpi / (label_chars * 0.55))
        height_limit = max(4.0, float(cell_height) * 0.62 * 72.0 / dpi)
        return max(4.0, min(float(base_size), width_limit, height_limit))

    def _vd_relative_luminance(self, rgb):
        linear_channels = []
        for channel in rgb[:3]:
            channel = max(0.0, min(float(channel), 1.0))
            if channel <= 0.03928:
                linear_channels.append(channel / 12.92)
            else:
                linear_channels.append(((channel + 0.055) / 1.055) ** 2.4)
        return (
            0.2126 * linear_channels[0]
            + 0.7152 * linear_channels[1]
            + 0.0722 * linear_channels[2]
        )

    def _vd_cell_label_color(self, cell_value, image):
        background_rgba = image.cmap(image.norm(float(cell_value)))
        alpha = float(background_rgba[3]) if len(background_rgba) > 3 else 1.0
        background_rgb = [
            float(channel) * alpha + (1.0 - alpha)
            for channel in background_rgba[:3]
        ]
        luminance = self._vd_relative_luminance(background_rgb)
        white_contrast = 1.05 / (luminance + 0.05)
        black_contrast = (luminance + 0.05) / 0.05
        return "white" if white_contrast >= black_contrast else "black"

    def _format_vd_cell_label(self, value, annotation_mode):
        if annotation_mode == "Index diff":
            return str(int(round(float(value))))
        value = float(value)
        if abs(value) >= 100:
            return f"{value:.0f}"
        if abs(value) >= 10:
            return f"{value:.1f}".rstrip("0").rstrip(".")
        return f"{value:.2f}".rstrip("0").rstrip(".")

    def _draw_voltage_difference_matrix(self, voltage_matrix, index_matrix=None):
        if not hasattr(self, "vd_ax") or not hasattr(self, "vd_canvas"):
            return
        self._remove_vd_colorbar()
        self.vd_ax.clear()
        self._apply_plot_background(self.get_field_value("ui_theme") if "ui_theme" in self.input_fields else "Light")
        vmax = max([max(row) for row in voltage_matrix], default=0.0)
        vmax = vmax if vmax > 0 else 1.0
        row_count = max(0, self.Winding_Para.num_layers - 1)
        annotation_mode = self._vd_annotation_mode()
        cell_width = self._vd_cell_width_input()
        cell_height = self._vd_cell_height_input()
        self._configure_vd_canvas_size(self.Winding_Para.num_slots, row_count, annotation_mode)
        # Reserve only the space required for the colorbar; keep the matrix
        # itself wide instead of leaving an artificial empty frame.
        self.vd_figure.subplots_adjust(left=0.09, right=0.90, top=0.9, bottom=0.16)
        image = self.vd_ax.imshow(voltage_matrix, cmap="plasma", aspect="auto", vmin=0, vmax=vmax)
        self.vd_colorbar = self.vd_figure.colorbar(image, ax=self.vd_ax, fraction=0.04, pad=0.025)
        self.vd_colorbar.set_label("Voltage Difference (DC)", fontsize=9, labelpad=8)
        self.vd_colorbar.ax.yaxis.set_ticks_position("right")
        self.vd_colorbar.ax.yaxis.set_label_position("right")
        self.vd_colorbar.ax.tick_params(axis="y", which="both", labelsize=8, pad=2, colors="black")
        self.vd_ax.set_title("Voltage Differences Between Adjacent Layers")
        self.vd_ax.set_xlabel("Slot")
        self.vd_ax.set_ylabel("InterLayer Index")
        self.vd_ax.set_xticks(np.arange(-0.5, self.Winding_Para.num_slots, 1), minor=True)
        self.vd_ax.set_yticks(np.arange(-0.5, row_count, 1), minor=True)
        self.vd_ax.grid(which="minor", color="black", linestyle="-", linewidth=0.45)
        self.vd_ax.tick_params(which="minor", bottom=False, left=False)
        self.vd_ax.set_axisbelow(False)
        tick_font_size = 8
        slot_ticks = self._vd_slot_ticks(self.Winding_Para.num_slots, cell_width, tick_font_size)
        self.vd_ax.set_xticks(slot_ticks)
        self.vd_ax.set_xticklabels([str(slot + 1) for slot in slot_ticks], fontsize=tick_font_size)
        self.vd_ax.set_yticks(list(range(row_count)))
        self.vd_ax.set_yticklabels([f"L{i + 1}L{i + 2}" for i in range(row_count)], fontsize=8)
        if annotation_mode != "No labels":
            label_matrix = index_matrix if annotation_mode == "Index diff" and index_matrix is not None else voltage_matrix
            text_size = self._vd_font_size_input()
            for row_index, row in enumerate(label_matrix):
                for slot_index, value in enumerate(row):
                    label = self._format_vd_cell_label(value, annotation_mode)
                    self.vd_ax.text(
                        slot_index,
                        row_index,
                        label,
                        ha="center",
                        va="center",
                        color=self._vd_cell_label_color(voltage_matrix[row_index][slot_index], image),
                        fontsize=self._vd_cell_label_font_size(label, text_size, cell_width, cell_height),
                    )
        self.vd_canvas.draw()
        self._reset_plot_label_scale(self.vd_ax)
        self.vd_canvas.update()
        if hasattr(self, "vd_plot_scroll_area"):
            self.vd_plot_scroll_area.viewport().update()

    def optimize_voltage_difference_inlets(self):
        try:
            if getattr(self, "vd_optimize_thread", None) is not None and self.vd_optimize_thread.isRunning():
                if hasattr(self, "message_log"):
                    self.message_log.append("Volt Diff optimization is already running.")
                return

            if self.tp_type_field.currentText() == "Auto":
                self.apply_auto_configuration(preserve_inlet_adjustments=True)
            self.extract_parameters()
            voltage_drop = self._voltage_drop_input()
            index_span = self._voltage_index_span_input(self.cond_info)
            problem = self._build_vd_optimization_problem(voltage_drop, index_span)
            algorithm_id = self._vd_algorithm_id()

            self._vd_optimize_input_signature = self._vd_optimize_source_signature()
            self.vd_optimize_worker = VDOptimizeWorker(
                problem,
                algorithm_id,
                vdo.DEFAULT_TIME_BUDGET_SEC,
                self._current_all_branch_adjustments(),
            )
            self.vd_optimize_thread = QThread(self)
            self.vd_optimize_worker.moveToThread(self.vd_optimize_thread)
            self.vd_optimize_thread.started.connect(self.vd_optimize_worker.run)
            self.vd_optimize_worker.finished.connect(self._handle_vd_optimize_finished)
            self.vd_optimize_worker.failed.connect(self._handle_vd_optimize_failed)
            self.vd_optimize_worker.finished.connect(self.vd_optimize_thread.quit)
            self.vd_optimize_worker.failed.connect(self.vd_optimize_thread.quit)
            self.vd_optimize_worker.finished.connect(self.vd_optimize_worker.deleteLater)
            self.vd_optimize_worker.failed.connect(self.vd_optimize_worker.deleteLater)
            self.vd_optimize_thread.finished.connect(self.vd_optimize_thread.deleteLater)
            self.vd_optimize_thread.finished.connect(self._clear_vd_optimize_worker_refs)

            if hasattr(self, "vd_optimize_button"):
                self.vd_optimize_button.setEnabled(False)
            if hasattr(self, "vd_optimize_progress"):
                self.vd_optimize_progress.setVisible(False)
            self.vd_optimize_progress_timer = QTimer(self)
            self.vd_optimize_progress_timer.setSingleShot(True)
            self.vd_optimize_progress_timer.timeout.connect(self._show_vd_optimize_progress_if_running)
            self.vd_optimize_progress_timer.start(1000)
            self.vd_optimize_thread.start()
        except Exception as exc:
            if hasattr(self, "vd_result_display"):
                self.vd_result_display.setText(f"Volt Diff optimization failed: {exc}")
            if hasattr(self, "message_log"):
                self.message_log.append(f"Volt Diff optimization failed: {exc}")

    def _show_vd_optimize_progress_if_running(self):
        thread = getattr(self, "vd_optimize_thread", None)
        if thread is not None and thread.isRunning() and hasattr(self, "vd_optimize_progress"):
            self.vd_optimize_progress.setVisible(True)

    def _clear_vd_optimize_worker_refs(self):
        self.vd_optimize_thread = None
        self.vd_optimize_worker = None

    def _finish_vd_optimize_progress(self):
        timer = getattr(self, "vd_optimize_progress_timer", None)
        if timer is not None:
            timer.stop()
            timer.deleteLater()
            self.vd_optimize_progress_timer = None
        if hasattr(self, "vd_optimize_progress"):
            self.vd_optimize_progress.setVisible(False)
        if hasattr(self, "vd_optimize_button"):
            self.vd_optimize_button.setEnabled(True)

    def _vd_optimize_source_signature(self):
        edits = tuple((index, field.text()) for index, field in
                      getattr(self, "vd_adjustment_inputs", ()))
        return self._calculation_input_signature(), edits

    def _handle_vd_optimize_finished(self, result):
        self._finish_vd_optimize_progress()
        if self._vd_optimize_source_signature() != getattr(self, "_vd_optimize_input_signature", None):
            self.message_log.append("Volt Diff optimization result discarded because inputs changed.")
            return
        try:
            best_adjustments = result.best_adjustments
            best_phase_a_adjustments = result.phase_a_template
            best_score = result.score

            self.volt_diff_inlet_adjustments_all = list(best_adjustments)
            self._refresh_vd_adjustment_grid()
            self.extract_parameters()
            self._refresh_vd_adjustment_grid()
            self.update_voltage_difference_view()
            result_mode = "exact" if result.is_exact else "approximate"
            optimize_message = (
                "Volt Diff inlet optimization applied. Algorithm: "
                f"{vdo.algorithm_label(result.algorithm_id)} ({result_mode}); "
                f"elapsed {result.elapsed_sec:.3g} s; estimated {result.estimated_sec:.3g} s; "
                f"evaluations {result.evaluations}; stopped: {result.stopped_reason}; "
                "Max voltage difference (DC): "
                f"{best_score[0]:.6g}; Phase A template index adj.: "
                + ", ".join(str(value) for value in best_phase_a_adjustments)
                + "; all branch index adj.: "
                + ", ".join(str(value) for value in best_adjustments)
            )
            self.message_log.append(
                optimize_message
            )
            if hasattr(self, "vd_result_display"):
                self.vd_result_display.append("\n" + optimize_message)
        except Exception as exc:
            if hasattr(self, "vd_result_display"):
                self.vd_result_display.setText(f"Volt Diff optimization failed: {exc}")
            if hasattr(self, "message_log"):
                self.message_log.append(f"Volt Diff optimization failed: {exc}")

    def _handle_vd_optimize_failed(self, message):
        self._finish_vd_optimize_progress()
        if hasattr(self, "vd_result_display"):
            self.vd_result_display.setText(f"Volt Diff optimization failed: {message}")
        if hasattr(self, "message_log"):
            self.message_log.append(f"Volt Diff optimization failed: {message}")

    def _slot_distance(self, slot_a, slot_b, num_slots):
        distance = abs(int(slot_a) - int(slot_b)) % num_slots
        return min(distance, num_slots - distance)

    def _candidate_shift_data(self, conductors, force_even):
        candidates = []
        count = len(conductors)
        for shift in range(count):
            if force_even and shift % 2 != 0:
                continue
            inlet = conductors[shift]
            outlet = conductors[(shift - 1) % count]
            candidates.append({
                "shift": shift,
                "adjustment": self._normalized_signed_adjustment(shift, count),
                "inlet": inlet,
                "outlet": outlet,
            })
        if not candidates:
            raise ValueError("No valid inlet adjustment candidates were found.")
        return candidates

    def _choose_candidate_for_target(self, candidates, target_slot, target_layer=None, required_layer=None, include_outlet=False):
        num_slots = self.Winding_Para.num_slots
        ranked = []
        for candidate in candidates:
            inlet_slot, inlet_layer = candidate["inlet"][:2]
            outlet_slot, outlet_layer = candidate["outlet"][:2]
            layer_penalty = 0
            if required_layer is not None:
                layer_penalty = 0 if inlet_layer == required_layer else 1000 + abs(inlet_layer - required_layer)
            slot_score = self._slot_distance(inlet_slot, target_slot, num_slots)
            layer_score = 0 if target_layer is None else abs(inlet_layer - target_layer)
            if include_outlet:
                slot_score += self._slot_distance(outlet_slot, target_slot, num_slots)
                if target_layer is not None:
                    layer_score += abs(outlet_layer - target_layer)
            ranked.append((
                layer_penalty,
                slot_score,
                layer_score,
                abs(candidate["adjustment"]),
                candidate["adjustment"],
                candidate,
            ))
        ranked.sort(key=lambda item: item[:5])
        return ranked[0][-1]

    def compute_phase_a_inlet_optimization(self, mode):
        self.extract_parameters()
        pattern_id = gw.normalize_pattern_name(self.input_fields["pattern_name"].text())
        force_even = gw.pattern_requires_weld_side_inlet(pattern_id)
        phase_a = self._phase_a_branch_infos(self.base_db_conductor_id, self.base_cond_info)
        if len(phase_a) != self.Winding_Para.ab:
            raise ValueError(f"Expected {self.Winding_Para.ab} Phase A branches, found {len(phase_a)}.")
        candidate_groups = [self._candidate_shift_data(conductors, force_even) for _idx, _branch_id, conductors in phase_a]

        best = None
        for target_slot in range(self.Winding_Para.num_slots):
            target_layers = [None]
            if mode == "Inlets and outlets compact":
                target_layers = list(range(self.Winding_Para.num_layers))
            for target_layer in target_layers:
                if mode == "Outer layer, nearest slots":
                    chosen = [self._choose_candidate_for_target(group, target_slot, required_layer=0) for group in candidate_groups]
                    score = (
                        sum(0 if candidate["inlet"][1] == 0 else 1000 + abs(candidate["inlet"][1]) for candidate in chosen),
                        sum(self._slot_distance(candidate["inlet"][0], target_slot, self.Winding_Para.num_slots) for candidate in chosen),
                    )
                elif mode == "Inner layer, nearest slots":
                    inner_layer = self.Winding_Para.num_layers - 1
                    chosen = [self._choose_candidate_for_target(group, target_slot, required_layer=inner_layer) for group in candidate_groups]
                    score = (
                        sum(0 if candidate["inlet"][1] == inner_layer else 1000 + abs(candidate["inlet"][1] - inner_layer) for candidate in chosen),
                        sum(self._slot_distance(candidate["inlet"][0], target_slot, self.Winding_Para.num_slots) for candidate in chosen),
                    )
                elif mode == "Same slot, nearest layers":
                    chosen = [self._choose_candidate_for_target(group, target_slot) for group in candidate_groups]
                    layers = [candidate["inlet"][1] for candidate in chosen]
                    score = (
                        sum(self._slot_distance(candidate["inlet"][0], target_slot, self.Winding_Para.num_slots) for candidate in chosen),
                        max(layers) - min(layers),
                        sum(abs(layer - round(sum(layers) / len(layers))) for layer in layers),
                    )
                else:
                    chosen = [
                        self._choose_candidate_for_target(group, target_slot, target_layer=target_layer, include_outlet=True)
                        for group in candidate_groups
                    ]
                    score = (
                        sum(
                            self._slot_distance(candidate["inlet"][0], target_slot, self.Winding_Para.num_slots)
                            + self._slot_distance(candidate["outlet"][0], target_slot, self.Winding_Para.num_slots)
                            for candidate in chosen
                        ),
                        sum(
                            abs(candidate["inlet"][1] - target_layer) + abs(candidate["outlet"][1] - target_layer)
                            for candidate in chosen
                        ),
                    )
                adjustments = [candidate["adjustment"] for candidate in chosen]
                score = tuple(score) + (sum(abs(value) for value in adjustments), adjustments)
                if best is None or score < best:
                    best = score
        if best is None:
            raise ValueError("No optimization result was found.")
        return list(best[-1])

    def create_transp_params_tab(self):
        tab = QWidget()
        form_layout = QVBoxLayout()  # Use vertical layout
        form_layout.setContentsMargins(16, 14, 16, 14)
        form_layout.setSpacing(10)
    
        # Create a horizontal layout for transposition type selection
        transp_type_layout = QHBoxLayout()
    
        # Label for "Types of Transposition"
        transp_label = QLabel("Transposition Type:")
        transp_type_layout.addWidget(transp_label)
    
        self.tp_type_field = TextComboBox()
        self.tp_type_field.addItems(["Auto", "Regular", "Times", "Interval"])
        self.tp_type_field.setCurrentText("Auto")
        self.tp_type_field.setMinimumWidth(150)
        transp_type_layout.addWidget(self.tp_type_field)
        self.tp_type_field.currentTextChanged.connect(self.update_transp_type)
        self.tp_type_field.currentTextChanged.connect(self.update_transp_range)

        form_layout.addLayout(transp_type_layout)

        objective_layout = QHBoxLayout()
        objective_layout.addWidget(QLabel("Auto Configure strategy:"))
        self.auto_configure_objective_field = TextComboBox()
        for objective, label in auto_tp.AUTO_CONFIGURE_OBJECTIVES.items():
            self.auto_configure_objective_field.addItem(label, objective)
        self.auto_configure_objective_field.setCurrentIndex(
            self.auto_configure_objective_field.findData(
                auto_tp.DEFAULT_AUTO_CONFIGURE_OBJECTIVE))
        self.auto_configure_objective_field.setToolTip(
            "Select the minimum among evaluated valid strong-symmetry recipes. "
            "Pin types use layer pair and slot span. Normalized average pin "
            "length uses the documented dimensionless slot/layer geometry proxy; "
            "a physical-model length may also be reported. This finite search "
            "does not prove global optimality.")
        self.input_fields["auto_configure_objective"] = self.auto_configure_objective_field
        objective_layout.addWidget(self.auto_configure_objective_field, 1)
        self.auto_configure_apply_button = QPushButton("Apply")
        self.auto_configure_apply_button.setToolTip(
            "Apply the selected automatic recipe and keep Auto selected.")
        self.auto_configure_apply_button.clicked.connect(
            lambda: self.apply_auto_configuration(keep_auto=True))
        objective_layout.addWidget(self.auto_configure_apply_button)
        form_layout.addLayout(objective_layout)
        self.auto_configuration_notice = QLabel()
        self.auto_configuration_notice.setWordWrap(True)
        form_layout.addWidget(self.auto_configuration_notice)
    
        # Keep related settings side by side so the tab leaves room for results.
        transp_fields = [
            ("Intervals of T.P.", "tp_interval"),
            ("Times of T.P.", "tp_times"),
            ("Uniform T.P.", "uni_tp"),
            ("First-layer T.P.", "pltp_fl"),
            ("Last-layer T.P.", "pltp_ll"),
            ("Jump-layer T.P.", "jltp"),
        ]

        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(0, 4, 0, 0)
        grid_layout.setHorizontalSpacing(10)
        grid_layout.setVerticalSpacing(10)
        self.tp_params_grid = grid_layout
        self.tp_fields = {}  # Store input fields
        self.tp_range_labels = {}  # Store range labels for dynamic updates

        for index, (label, key) in enumerate(transp_fields):
            row, pair = divmod(index, 2)
            column = pair * 3
            input_box = QLineEdit("0")
            input_box.setFixedSize(80, 30)
            input_box.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Center align text inside the input box
            self.tp_fields[key] = input_box
            self.input_fields[key] = input_box

            field_label = QLabel(label + ":")
            field_label.setWordWrap(True)
            field_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            grid_layout.addWidget(field_label, row, column)
            grid_layout.addWidget(input_box, row, column + 1)
    
            # Only show range for specific fields
            if key in ["uni_tp", "pltp_fl", "pltp_ll","jltp"]:
                range_label = QLabel("")  # Placeholder, will be updated dynamically
                range_label.setWordWrap(True)
                range_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
                self.tp_range_labels[key] = range_label  # Store label reference
                grid_layout.addWidget(range_label, row, column + 2)

        for column in (0, 2, 3, 5):
            grid_layout.setColumnStretch(column, 1)
    
        form_layout.addLayout(grid_layout)

        self.fractional_advanced_row = QWidget()
        fractional_advanced_layout = QHBoxLayout(self.fractional_advanced_row)
        fractional_advanced_layout.setContentsMargins(0, 0, 0, 0)
        fractional_advanced_layout.setSpacing(10)
        self.pole_group_advanced_toggle = QPushButton("Advanced")
        self.pole_group_advanced_toggle.setCheckable(True)
        self.pole_group_advanced_toggle.setMaximumWidth(
            self.pole_group_advanced_toggle.sizeHint().width() + 12)
        fractional_advanced_layout.addWidget(self.pole_group_advanced_toggle)
        self.fractional_tp_notice = QLabel()
        self.fractional_tp_notice.setWordWrap(True)
        fractional_advanced_layout.addWidget(self.fractional_tp_notice, 1)
        self.fractional_advanced_row.hide()
        form_layout.addWidget(self.fractional_advanced_row)

        self.uwp_balance_notice = QLabel()
        self.uwp_balance_notice.setWordWrap(True)
        self.uwp_balance_notice.hide()
        form_layout.addWidget(self.uwp_balance_notice)

        self.pole_group_advanced_content = QWidget()
        group_layout = QGridLayout(self.pole_group_advanced_content)
        group_layout.setContentsMargins(0, 4, 0, 0)
        group_layout.setHorizontalSpacing(12)
        group_layout.setVerticalSpacing(8)
        group_fields = [
            ("Interval", "tp_interval"), ("Times", "tp_times"),
            ("Uniform", "uni_tp"), ("First layer", "pltp_fl"),
            ("Last layer", "pltp_ll"), ("Jump layer (signed)", "jltp"),
        ]
        self.pole_group_cond_labels = {}
        self.pole_group_tp_hints = {}
        self._zero_tp_validator = QIntValidator(0, 0, self)
        for column, (name, prefix) in enumerate((("PoleN", "pole_n"), ("PoleS", "pole_s"))):
            panel = QWidget()
            panel_layout = QGridLayout(panel)
            panel_layout.setHorizontalSpacing(8)
            panel_layout.setVerticalSpacing(7)
            title = QLabel(name)
            title.setProperty("fieldLabel", True)
            capacity = QLabel("-- branches")
            capacity.setProperty("resultSummary", True)
            capacity.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            capacity.setToolTip(
                "Branch starts in this phase-relative first pole (+ direction)."
                if name == "PoleN" else
                "Branch starts in this phase-relative second pole (- direction).")
            self.pole_group_cond_labels[prefix] = capacity
            panel_layout.addWidget(title, 0, 0)
            panel_layout.addWidget(capacity, 0, 1)
            tp_type = TextComboBox()
            tp_type.addItems(["Regular", "Times", "Interval", "Optimize"])
            self.input_fields[f"{prefix}_tp_type"] = tp_type
            panel_layout.addWidget(QLabel("Type:"), 1, 0)
            panel_layout.addWidget(tp_type, 1, 1)
            for row, (label, suffix) in enumerate(group_fields, 2):
                field = QLineEdit("0")
                field.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.input_fields[f"{prefix}_{suffix}"] = field
                panel_layout.addWidget(QLabel(label + ":"), row, 0)
                panel_layout.addWidget(field, row, 1)
            tp_type.currentTextChanged.connect(
                lambda selected, p=prefix: self._update_pole_group_tp_type(p, selected))
            self._update_pole_group_tp_type(prefix, "Regular")
            hint = QLabel()
            hint.setProperty("resultSummary", True)
            hint.setWordWrap(True)
            self.pole_group_tp_hints[prefix] = hint
            panel_layout.addWidget(hint, len(group_fields) + 2, 0, 1, 2)
            panel_layout.setRowStretch(len(group_fields) + 2, 1)
            group_layout.addWidget(panel, 0, column)
        self._refresh_pole_group_tp_adjacency(None, False)
        self.pole_group_advanced_content.hide()
        self.pole_group_advanced_toggle.toggled.connect(
            self._set_pole_group_advanced_visible)
        form_layout.addWidget(self.pole_group_advanced_content)
    
        # Set initial state based on default type
        self._auto_effective_tp_type = "Regular"
        self.update_transp_type("Auto", run_auto=False)
        self.update_transp_range()  # Initialize range labels on tab creation
    
        tab.setLayout(form_layout)
        return tab

    def _set_pole_group_advanced_visible(self, visible):
        self.pole_group_advanced_content.setVisible(visible)

    def _update_pole_group_tp_type(self, prefix, selected_type):
        fields = {key: self.input_fields[f"{prefix}_{key}"] for key in
                  ("tp_interval", "tp_times", "uni_tp", "pltp_fl", "pltp_ll", "jltp")}
        editable = {
            "Regular": {"uni_tp", "pltp_fl", "pltp_ll", "jltp"},
            "Times": {"tp_times"},
            "Interval": {"tp_interval"},
            "Optimize": set(),
        }.get(selected_type, set())
        for key, field in fields.items():
            field.setReadOnly(key not in editable)
            field.setStyleSheet("background-color: white;" if key in editable
                                else "background-color: lightgray;")
            if key not in editable:
                field.setToolTip(
                    f"Inactive while {selected_type} is selected; stored value "
                    "is not applied.")
            elif key == "uni_tp":
                field.setToolTip(
                    "0: Off. 1: rotate all branches at every insertion-side "
                    "connection within this phase-relative pole group.")
            else:
                field.setToolTip("")
    
    def update_transp_range(self):
        """Updates the transposition range dynamically based on the current value of q."""
        try:
            q_value = int(self.input_fields["q"].text()) if "q" in self.input_fields else None
        except ValueError:
            q_value = None
    
        # Update range labels dynamically
        for key, label in self.tp_range_labels.items():
            if q_value:
                if key == "jltp":
                    # For jltp, show range from -q to q
                    range_list = list(range(-q_value+1, q_value))
                    range_text = f"Range: [{', '.join(map(str, range_list))}]"
                else:
                    # Default range 0 to q-1
                    range_text = f"Range: [{', '.join(map(str, range(q_value)))}]"
            else:
                # Fallback range description
                if key == "jltp":
                    range_text = "Range: [-q+1, ..., 0, ..., q-1]"
                else:
                    range_text = "Range: [0, 1, 2, ..., q-1]"
            label.setText(range_text)

    def update_transp_type(self, selected_type, run_auto=True):
        """Update input field states based on transposition type selection."""
        selected_type = auto_tp.normalize_tp_type(selected_type)
        if selected_type == "Auto" and self._auto_configuration_is_current():
            self.auto_configure_objective_field.setEnabled(True)
            self._display_auto_configuration(self.base_db_conductor_id.auto_configuration)
            return
        if self.tp_type_field.currentText() != selected_type:
            self.tp_type_field.setCurrentText(selected_type)
        self.input_fields["tp_type"] = self.tp_type_field
        is_auto = auto_tp.is_auto_type(selected_type)
        self.auto_configure_objective_field.setEnabled(is_auto)
        effective_type = selected_type
        if auto_tp.is_auto_type(selected_type):
            balanced = getattr(self, "_uwp_balance_key", None) is not None
            if balanced:
                self._auto_effective_tp_type = "Auto"
            elif (run_auto
                  and not getattr(self, "_syncing_uwp_balance", False)
                  and not getattr(self, "_loading_balance_config", False)):
                self._auto_effective_tp_type = "Regular"
                self.config_optimise_pattern()
                effective_type = self.tp_type_field.currentText()
                if effective_type != "Auto":
                    self._auto_effective_tp_type = effective_type
                self.tp_type_field.blockSignals(True)
                self.tp_type_field.setCurrentText("Auto")
                self.tp_type_field.blockSignals(False)
            effective_type = self._auto_effective_tp_type
        else:
            self._auto_effective_tp_type = selected_type
        # Reset styles
        for input_field in self.tp_fields.values():
            input_field.setReadOnly(True)
            input_field.setStyleSheet("background-color: lightgray;")  # Grey out read-only fields
    
        # Enable and highlight the correct fields based on type
        if not is_auto and effective_type == "Regular":
            self.tp_fields["uni_tp"].setReadOnly(False)
            self.tp_fields["pltp_fl"].setReadOnly(False)
            self.tp_fields["pltp_ll"].setReadOnly(False)
            self.tp_fields["jltp"].setReadOnly(False)
    
        elif not is_auto and effective_type == "Interval":
            self.tp_fields["tp_interval"].setReadOnly(False)
    
        elif not is_auto and effective_type == "Times":
            self.tp_fields["tp_times"].setReadOnly(False)
    
        # Highlight the enabled input fields
        for key, input_field in self.tp_fields.items():
            if not input_field.isReadOnly():
                input_field.setStyleSheet("background-color: white;")  # Highlight editable fields

        self.auto_configure_objective_field.setEnabled(is_auto)
        self._mark_auto_configuration_pending()

    def _auto_configuration_is_current(self):
        return (getattr(self, "_last_calculation_signature", None) is not None
                and getattr(getattr(self, "base_db_conductor_id", None),
                            "auto_configuration", None) is not None
                and self.tp_type_field.currentText() == "Auto"
                and self._calculation_input_signature() == self._last_calculation_signature)

    def _mark_auto_configuration_pending(self, _value=None):
        if self._auto_configuration_is_current():
            return
        self.auto_configuration_notice.setToolTip("")
        if self.tp_type_field.currentText() == "Auto":
            self.auto_configuration_notice.setText(
                "Pending calculation: Auto Configure will evaluate the selected "
                "strategy. Displayed TP values are provisional until Calculate.")
        else:
            self.auto_configuration_notice.setText(
                "Manual transposition settings are active.")

    def _display_auto_configuration(self, report):
        """Publish selected fields without rerunning automatic rule selection."""
        effective = report["effective_parameters"]
        self._auto_effective_tp_type = effective["tp_type"]
        active_fields = {
            "Regular": {"uni_tp", "pltp_fl", "pltp_ll", "jltp"},
            "Times": {"tp_times"},
            "Interval": {"tp_interval"},
        }.get(self._auto_effective_tp_type, set())
        for key, field in self.tp_fields.items():
            value = effective.get(key, 0)
            if key == "jltp":
                value *= effective.get("jld", 1)
            was_blocked = field.blockSignals(True)
            field.setText(str(value))
            field.blockSignals(was_blocked)
            field.setReadOnly(True)
            field.setStyleSheet(
                "background-color: white;" if key in active_fields
                else "background-color: lightgray;")
        objective = auto_tp.AUTO_CONFIGURE_OBJECTIVES[report["objective"]]
        status = report.get("status", "auto configure pending")
        if report.get("completed"):
            text = (f"{objective}: selected minimum among evaluated valid "
                    f"strong-symmetry recipes. {status}.")
        else:
            text = (f"{objective}: {status}; no completed strong-symmetry "
                    "selection. Retained layout is not an optimization result.")
        metrics = report.get("metrics")
        if metrics:
            text += (f" Transpositions: {metrics['transposition_count']}; "
                     f"pin types: {metrics['pin_type_count']}.")
            normalized = metrics.get("average_pin_length_normalized")
            text += (f" Normalized average pin length: {normalized:.3f}."
                     if normalized is not None else
                     " Normalized average pin length: unavailable.")
            physical = metrics.get("average_pin_length_mm")
            if physical is not None:
                text += f" Physical-model estimate: {physical:.3f} mm."
        text += " Finite recipe search; global optimality is not established."
        if report.get("fast_path_applied"):
            text += (" BWP insertion-side pin-type target N_L+1 reached; later TP "
                     "recipes were skipped. The pin-type minimum is met; the "
                     "transposition tie-break is limited to checked recipes.")
        changed = self.auto_configuration_notice.text() != text
        self.auto_configuration_notice.setText(text)
        self.auto_configuration_notice.setToolTip(report.get("scope", ""))
        if changed:
            self.message_log.append(text)

    def create_figure_params_tab(self):
        tab = QWidget()
        grid = QGridLayout(tab)
        grid.setContentsMargins(16, 14, 16, 14)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        self.compact_parameter_grids["Figure"] = grid

        def add_field(row, pair, text, content):
            label = QLabel(text)
            label.setProperty("fieldLabel", True)
            label.setWordWrap(True)
            grid.addWidget(label, row, pair * 2)
            if isinstance(content, QWidget):
                grid.addWidget(content, row, pair * 2 + 1)
            else:
                grid.addLayout(content, row, pair * 2 + 1)

        grid_pattern_box = QComboBox()
        grid_pattern_box.addItems(["branch", "phase"])
        grid_pattern_box.setCurrentText("branch")
        grid_pattern_box.setEditable(True)
        grid_pattern_box.lineEdit().setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid_pattern_box.setEditable(False)
        self.input_fields["grid_color_pattern"] = grid_pattern_box

        line_pattern_box = QComboBox()
        line_pattern_box.addItems(["branch", "Pin"])
        line_pattern_box.setCurrentText("branch")
        line_pattern_box.setEditable(True)
        line_pattern_box.lineEdit().setAlignment(Qt.AlignmentFlag.AlignCenter)
        line_pattern_box.setEditable(False)
        self.input_fields["fig_branch_line_color"] = line_pattern_box
        add_field(0, 0, "Grid color:", grid_pattern_box)
        add_field(0, 1, "Line color:", line_pattern_box)

        fields = [
            ("Show legend:", "1", " ", "Show_legend", True),
            ("Line width:", "1", " ", "linewidth"),
            ("Draw arrows:", "1", " ", "draw_arrow", True),
            ("Line Arrow size:", "1.0", " ", "arrow_size"),
            ("Radii gap:", "0.20", "plot r", "radii_gap"),
            ("Line side:", "0", " ", "line_single_side"),
            ("Single-phase lines:", "1", " ", "Single_Phase_Draw", True),
            ("Slot label font:", "auto", " ", "slotindex_fontsize_custom"),
        ]
        
        for index, field in enumerate(fields):
            row_layout, input_box = self.add_input_field(field[0], field[1], field[2], is_checkbox=field[4] if len(field) == 5 else False)
            self.input_fields[field[3]] = input_box
            row, pair = divmod(index, 2)
            add_field(row + 1, pair, field[0], row_layout)

        # Create a horizontal layout for inlet and outlet angle
        angle_layout = QHBoxLayout()
        
        inlet_label = QLabel("Inlet line angle (deg):")
        inlet_input = QLineEdit("30")
        inlet_input.setFixedWidth(60)
        self.input_fields["inline_angle"] = inlet_input
        
        outlet_label = QLabel("Outlet line angle (deg):")
        outlet_input = QLineEdit("60")
        outlet_input.setFixedWidth(60)
        self.input_fields["outline_angle"] = outlet_input
        
        angle_layout.addWidget(inlet_label)
        angle_layout.addWidget(inlet_input)
        angle_layout.addSpacing(20)  # Optional space between the two
        angle_layout.addWidget(outlet_label)
        angle_layout.addWidget(outlet_input)
        inlet_input.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Center align input text
        outlet_input.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Center align input text
        
        same_layer_route_layout, same_layer_route_box = self.add_input_field(
            "First/last-layer same-layer route:",
            "Radial-center arc",
            "",
            is_combo=True,
            combo_options=["Original direct arc", "Radial-center arc"],
        )
        same_layer_route_box.setMinimumWidth(220)
        self.input_fields["same_layer_route_style"] = same_layer_route_box

        advanced_content = QWidget()
        advanced_layout = QGridLayout(advanced_content)
        advanced_layout.setContentsMargins(0, 4, 0, 0)
        advanced_layout.setHorizontalSpacing(12)
        advanced_layout.setVerticalSpacing(8)
        route_label = QLabel("First/last same-layer route:")
        route_label.setProperty("fieldLabel", True)
        route_label.setWordWrap(True)
        advanced_layout.addWidget(route_label, 0, 0)
        advanced_layout.addLayout(same_layer_route_layout, 0, 1)
        advanced_layout.addLayout(angle_layout, 1, 0, 1, 2)
        advanced_content.hide()
        advanced_toggle = QPushButton("Advanced")
        advanced_toggle.setCheckable(True)
        advanced_toggle.toggled.connect(advanced_content.setVisible)
        self.figure_advanced_toggle = advanced_toggle
        self.figure_advanced_content = advanced_content
        grid.addWidget(advanced_toggle, 5, 0, 1, 4)
        grid.addWidget(advanced_content, 6, 0, 1, 4)

        apply_button = QPushButton("Apply Figure Settings")
        self.configure_command_button(apply_button, 190)
        apply_button.setProperty("primaryAction", True)
        apply_button.clicked.connect(self.plot_layout)
        grid.addWidget(apply_button, 7, 0, 1, 4)
        grid.setRowStretch(8, 1)
        return tab

    def create_plot_config_tab(self):
        tab = QWidget()
        grid = QGridLayout(tab)
        grid.setContentsMargins(16, 14, 16, 14)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        self.compact_parameter_grids["Plot Config"] = grid

        def add_field(row, pair, text, content):
            label = QLabel(text)
            label.setProperty("fieldLabel", True)
            label.setWordWrap(True)
            grid.addWidget(label, row, pair * 2)
            if isinstance(content, QWidget):
                grid.addWidget(content, row, pair * 2 + 1)
            else:
                grid.addLayout(content, row, pair * 2 + 1)

        fields = [
            ("Inner radius:", "3", " ", "plot_inner_radius"),
            ("Layer height scale:", "1.5", " ", "plot_layer_height_scale"),
            ("Plot margin:", "1.60", " ", "plot_margin"),
            ("Plot zoom:", "1.0", " ", "plot_zoom"),
            ("Figure padding:", "0.01", " ", "plot_padding"),
            ("Slot label offset:", "-0.55", " ", "slotindex_offset"),
            ("Legend font size:", "11", " ", "legend_fontsize"),
            ("Grid color alpha:", "0.30", " ", "grid_alpha"),
        ]

        for index, (label, default, unit, key) in enumerate(fields):
            row_layout, input_box = self.add_input_field(label, default, unit)
            self.input_fields[key] = input_box
            row, pair = divmod(index, 2)
            add_field(row, pair, label, row_layout)

        legend_layout, legend_box = self.add_input_field(
            "Legend position:",
            "center",
            " ",
            is_combo=True,
            combo_options=["center", "upper right", "lower right", "right", "none"],
        )
        legend_box.setProperty("compactCombo", True)
        legend_box.setMinimumWidth(120)
        self.input_fields["legend_position"] = legend_box
        add_field(4, 0, "Legend:", legend_layout)

        rotate_layout, rotate_box = self.add_input_field("Rotate slot labels:", "0", " ", is_checkbox=True)
        self.input_fields["slotindex_rotation"] = rotate_box
        add_field(4, 1, "Rotate slot labels:", rotate_layout)

        circle_layout, circle_box = self.add_input_field("Show slot circles:", "1", " ", is_checkbox=True)
        self.input_fields["wedge_circle"] = circle_box
        add_field(5, 0, "Slot circles:", circle_layout)

        theme = QComboBox()
        theme.addItems(["Light", "Dark"])
        self.input_fields["ui_theme"] = theme
        add_field(5, 1, "Theme:", theme)
        for index, (label, key, default) in enumerate([
            ("UI font:", "ui_font_size", "10"),
            ("Button height:", "ui_button_height", "34"),
        ]):
            row, field = self.add_input_field(label, default, "")
            self.input_fields[key] = field
            add_field(6, index, label, row)

        apply_button = QPushButton("Apply Plot")
        apply_button.setToolTip("Apply plot configuration")
        self.configure_command_button(apply_button, 180)
        apply_button.setProperty("primaryAction", True)
        apply_button.clicked.connect(self.plot_layout)
        grid.addWidget(apply_button, 7, 0, 1, 2)
        settings_button = QPushButton("Apply Interface")
        settings_button.setToolTip("Apply interface settings")
        settings_button.clicked.connect(lambda: self.apply_settings())
        grid.addWidget(settings_button, 7, 2, 1, 2)
        grid.setRowStretch(8, 1)
        return tab
    
    
    def create_wf_params_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.wf_plot_button = QPushButton("Plot Winding Function")
        self.configure_command_button(self.wf_plot_button, 200)
        self.wf_plot_button.setMaximumWidth(240)
        self.wf_plot_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.wf_plot_button.setProperty("primaryAction", True)
        self.wf_plot_button.clicked.connect(self.plot_winding_function_and_table)
        toolbar.addWidget(self.wf_plot_button)
        self.wf_detach_button = QPushButton("Detach Plot")
        self.configure_command_button(self.wf_detach_button, 140)
        self.wf_detach_button.setMaximumWidth(160)
        self.wf_detach_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.wf_detach_button.clicked.connect(self.toggle_wf_plot_window)
        toolbar.addWidget(self.wf_detach_button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
        self.figure_wf = Figure(figsize=(8, 4))
        self.ax_wf1 = self.figure_wf.add_subplot(2, 1, 1)
        self.ax_wf2 = self.figure_wf.add_subplot(2, 1, 2)
        self.canvas_wf = FigureCanvas(self.figure_wf)
        self.wf_plot_container = QWidget()
        self.wf_plot_container_layout = QVBoxLayout(self.wf_plot_container)
        self.wf_plot_container_layout.setContentsMargins(0, 0, 0, 0)
        self.wf_plot_placeholder = QLabel(
            "Winding-function plot is open in a separate window.\nClick Embed Plot to bring it back.")
        self.wf_plot_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.wf_plot_placeholder.setWordWrap(True)
        self.wf_plot_placeholder.hide()
        self.wf_plot_container_layout.addWidget(self.wf_plot_placeholder, 1)
        self.wf_plot_container_layout.addWidget(self.canvas_wf, 1)
        self.wf_plot_window = None
        layout.addWidget(self.wf_plot_container, 1)
        tab.setLayout(layout)
        return tab




    @staticmethod
    def _phase_label(phase):
        phase = int(phase)
        return chr(ord("A") + phase) if 0 <= phase < 26 else f"P{phase + 1}"











    def create_volt_diff_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        top_layout = QVBoxLayout()
        input_layout = QVBoxLayout()

        voltage_layout = QHBoxLayout()
        voltage_layout.addWidget(QLabel("Voltage drop (DC):"))
        self.vd_phase_drop_input = QLineEdit("400")
        self.vd_phase_drop_input.setFixedWidth(76)
        self.vd_phase_drop_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.input_fields["vd_phase_voltage_drop"] = self.vd_phase_drop_input
        voltage_layout.addWidget(self.vd_phase_drop_input)
        voltage_layout.addStretch(1)
        input_layout.addLayout(voltage_layout)

        annotation_layout = QHBoxLayout()
        annotation_layout.addWidget(QLabel("Annotation:"))
        self.vd_annotation_mode_box = QComboBox()
        self.vd_annotation_mode_box.addItems(["No labels", "Index diff", "Volt diff"])
        self.vd_annotation_mode_box.setMinimumWidth(100)
        self.vd_annotation_mode_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.input_fields["vd_annotation_mode"] = self.vd_annotation_mode_box
        annotation_layout.addWidget(self.vd_annotation_mode_box)
        annotation_layout.addStretch(1)
        input_layout.addLayout(annotation_layout)

        algorithm_layout = QHBoxLayout()
        algorithm_layout.setSpacing(8)
        algorithm_label = QLabel("Algorithm:")
        algorithm_label.setMinimumHeight(28)
        algorithm_layout.addWidget(algorithm_label)
        self.vd_algorithm_box = QComboBox()
        self.vd_algorithm_box.addItems([label for _algorithm_id, label in vdo.ALGORITHM_CHOICES])
        self.vd_algorithm_box.setMinimumWidth(120)
        self.vd_algorithm_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.vd_algorithm_box.setMinimumHeight(28)
        self.vd_algorithm_box.currentTextChanged.connect(self.refresh_vd_optimization_estimate)
        self.input_fields["vd_algorithm"] = self.vd_algorithm_box
        algorithm_layout.addWidget(self.vd_algorithm_box)
        self.vd_estimate_label = QLabel("Est: run Update Volt Diff.")
        self.vd_estimate_label.setWordWrap(False)
        self.vd_estimate_label.setMinimumHeight(28)
        self.vd_estimate_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        algorithm_layout.addStretch(1)
        input_layout.addLayout(algorithm_layout)
        input_layout.addWidget(self.vd_estimate_label)

        plot_grid_layout = QHBoxLayout()
        plot_grid_layout.addWidget(QLabel("Cell W:"))
        self.vd_cell_width_input = QLineEdit("40")
        self.vd_cell_width_input.setValidator(QIntValidator(6, 200, self))
        self.vd_cell_width_input.setFixedWidth(54)
        self.vd_cell_width_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.input_fields["vd_cell_width"] = self.vd_cell_width_input
        plot_grid_layout.addWidget(self.vd_cell_width_input)
        plot_grid_layout.addWidget(QLabel("Cell H:"))
        self.vd_cell_height_input = QLineEdit("72")
        self.vd_cell_height_input.setValidator(QIntValidator(12, 300, self))
        self.vd_cell_height_input.setFixedWidth(54)
        self.vd_cell_height_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.input_fields["vd_cell_height"] = self.vd_cell_height_input
        plot_grid_layout.addWidget(self.vd_cell_height_input)
        plot_grid_layout.addWidget(QLabel("Font:"))
        self.vd_font_size_input = QLineEdit("7")
        self.vd_font_size_input.setValidator(QIntValidator(4, 30, self))
        self.vd_font_size_input.setFixedWidth(46)
        self.vd_font_size_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.input_fields["vd_font_size"] = self.vd_font_size_input
        plot_grid_layout.addWidget(self.vd_font_size_input)
        plot_grid_layout.addStretch(1)
        input_layout.addLayout(plot_grid_layout)

        self.vd_neighbour_summary_card = QFrame()
        self.vd_neighbour_summary_card.setFrameShape(QFrame.Shape.StyledPanel)
        self.vd_neighbour_summary_card.setProperty("vdSummaryCard", True)
        self.vd_neighbour_summary_card.setMinimumWidth(0)
        self.vd_neighbour_summary_card.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        summary_layout = QVBoxLayout(self.vd_neighbour_summary_card)
        summary_layout.setContentsMargins(14, 12, 14, 12)
        summary_layout.setSpacing(6)
        summary_title = QLabel("Neighbour voltage limits (DC)")
        summary_title.setProperty("fieldLabel", True)
        summary_title.setWordWrap(True)
        summary_title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        summary_layout.addWidget(summary_title)

        def add_summary_metric(text, attribute):
            name = QLabel(text)
            name.setWordWrap(True)
            name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            value = QLabel("—")
            value.setProperty("vdMetricValue", True)
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            summary_layout.addWidget(name)
            summary_layout.addWidget(value)
            setattr(self, attribute, value)

        add_summary_metric("Same slot · adjacent layers", "vd_same_slot_value")
        add_summary_metric("Adjacent slots · same layer", "vd_adjacent_slot_same_layer_value")
        add_summary_metric("Adjacent slots · adjacent layers", "vd_adjacent_slot_adjacent_layer_value")
        summary_layout.addStretch(1)

        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(16)
        controls_layout.addLayout(input_layout, 1)
        controls_layout.addWidget(self.vd_neighbour_summary_card, 1)
        top_layout.addLayout(controls_layout)
        button_layout = QVBoxLayout()

        update_button = QPushButton("Update Volt Diff")
        self.configure_command_button(update_button, 180)
        update_button.setProperty("primaryAction", True)
        update_button.clicked.connect(self.update_voltage_difference_view)
        button_layout.addWidget(update_button)

        self.vd_optimize_button = QPushButton("Optimize Inlet Positions")
        self.configure_command_button(self.vd_optimize_button, 180)
        self.vd_optimize_button.clicked.connect(self.optimize_voltage_difference_inlets)
        button_layout.addWidget(self.vd_optimize_button)

        export_button = QPushButton("Export VD Plot XLSX")
        self.configure_command_button(export_button, 180)
        export_button.clicked.connect(self.export_voltage_difference_xlsx)
        button_layout.addWidget(export_button)

        export_svg_button = QPushButton("Export VD Plot SVG")
        self.configure_command_button(export_svg_button, 180)
        export_svg_button.clicked.connect(self.export_voltage_difference_svg)
        button_layout.addWidget(export_svg_button)
        top_layout.addLayout(button_layout)
        layout.addLayout(top_layout)

        layout.addWidget(QLabel("Current index adj. (Phase / Branch):"))
        self.vd_adjustment_inputs = []
        self.vd_adjustment_container = QWidget()
        self.vd_adjustment_grid = QGridLayout(self.vd_adjustment_container)
        self.vd_adjustment_grid.setContentsMargins(4, 4, 4, 4)
        self.vd_adjustment_grid.setHorizontalSpacing(10)
        self.vd_adjustment_grid.setVerticalSpacing(6)
        self.vd_adjustment_grid.addWidget(QLabel("Run Update Volt Diff to initialize branch inputs."), 0, 0)
        self.vd_adjustment_scroll = QScrollArea()
        self.vd_adjustment_scroll.setWidgetResizable(True)
        self.vd_adjustment_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.vd_adjustment_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.vd_adjustment_scroll.setMinimumHeight(92)
        self.vd_adjustment_scroll.setWidget(self.vd_adjustment_container)
        layout.addWidget(self.vd_adjustment_scroll)

        self.vd_result_display = QTextEdit()
        self.vd_result_display.setReadOnly(True)
        self.vd_result_display.setMinimumHeight(90)
        self.vd_result_display.setPlaceholderText("Voltage difference results will appear here...")
        layout.addWidget(self.vd_result_display)

        self.vd_optimize_progress = QProgressBar()
        self.vd_optimize_progress.setRange(0, 0)
        self.vd_optimize_progress.setTextVisible(True)
        self.vd_optimize_progress.setFormat("Optimizing inlet positions...")
        self.vd_optimize_progress.setMinimumHeight(18)
        self.vd_optimize_progress.setVisible(False)
        layout.addWidget(self.vd_optimize_progress)

        tab.setLayout(layout)
        return tab
    
    def plot_winding_function_and_table(self):
        try:
            try:
                self.extract_parameters()
            except Exception as e:
                self.message_log.append(f"Failed to extract parameters: {e}")
                return
    
            self.phase_cond_locations = wfc.get_phase_cond_locations(self.cond_info, phase=0)
            self.winding_func = wfc.get_winding_function(self.phase_cond_locations)
    
            # 清空并绘制 winding function 和其谱
            wfc.plot_winding_factor_ax(self.winding_func, self.Winding_Para, 50, ax1=self.ax_wf1, ax2=self.ax_wf2)
            self.canvas_wf.draw()
    

        except Exception as e:
            self.message_log.append(f"❌ Error during winding factor plotting: {str(e)}")


    # Helper function for safe widget data retrieval
    def get_field_value(self, field_key):
        widget = self.input_fields[field_key]
        if isinstance(widget, QComboBox):
            return widget.currentText()
        elif isinstance(widget, QCheckBox):
            return 1 if widget.isChecked() else 0
        else:
            return widget.text()

    def _safe_filename_part(self, value):
        text = str(value).strip()
        return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in text) or "0"













    @staticmethod
    def _phase_label(phase_index):
        phase_index = int(phase_index)
        if 0 <= phase_index < 26:
            return chr(ord("A") + phase_index)
        return str(phase_index + 1)













    def load_3d_model(self):
        self.message_log.append("3D model loader is reserved for future implementation.")

    def config_in_jmag(self):
        self.message_log.append("Config. in JMAG is reserved for future implementation.")

    def get_float_field(self, field_key, default):
        try:
            return float(str(self.get_field_value(field_key)).strip())
        except (KeyError, TypeError, ValueError):
            return default

    def get_int_field(self, field_key, default):
        try:
            return int(float(str(self.get_field_value(field_key)).strip()))
        except (KeyError, TypeError, ValueError):
            return default

    def apply_settings(self, silent=False):
        theme = self.get_field_value("ui_theme") if "ui_theme" in self.input_fields else "Light"
        checkmark_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "assets", "checkmark.svg").replace("\\", "/")
        font_size = max(8, min(18, self.get_int_field("ui_font_size", 10)))
        button_height = max(28, min(54, self.get_int_field("ui_button_height", 34)))
        window_width = max(860, self.get_int_field("window_width", self.width()))
        window_height = max(480, self.get_int_field("window_height", self.height()))
        left_width = max(460, self.get_int_field("left_panel_width", 600))
        bottom_height = max(110, self.get_int_field("bottom_panel_height", 150))

        app = QApplication.instance()
        if app is not None:
            font = QFont("Segoe UI")
            font.setPointSize(font_size)
            app.setFont(font)
        self.setFont(QFont(self.font().family(), font_size))

        if theme == "Dark":
            self.setStyleSheet(f"""
                QWidget {{
                    background: #202124;
                    color: #f1f3f4;
                    font-size: {font_size}pt;
                }}
                QLineEdit, QTextEdit, QComboBox, QTableWidget {{
                    background: #2b2d31;
                    color: #f1f3f4;
                    border: 1px solid #5f6368;
                    border-radius: 4px;
                    selection-background-color: #4c8bf5;
                }}
                QPushButton {{
                    background: #303134;
                    color: #f1f3f4;
                    border: 1px solid #5f6368;
                    border-radius: 4px;
                    padding: 4px 10px;
                    min-height: {button_height}px;
                }}
                QPushButton:hover {{ background: #3c4043; }}
                QTabWidget::pane {{ border: 1px solid #3c4043; }}
                QTabBar::tab {{
                    background: #2b2d31;
                    color: #f1f3f4;
                    padding: 7px 14px;
                    border: 1px solid #3c4043;
                    border-bottom: none;
                }}
                QTabBar::tab:selected {{ background: #202124; }}
                QSplitter::handle {{ background: #4a4d52; }}
            """)
        else:
            self.setStyleSheet(f"""
                QWidget {{
                    background: #f6f7f9;
                    color: #111827;
                    font-size: {font_size}pt;
                }}
                QLineEdit, QTextEdit, QComboBox, QTableWidget {{
                    background: #ffffff;
                    color: #111827;
                    border: 1px solid #d5d8de;
                    border-radius: 4px;
                    selection-background-color: #2f80ed;
                }}
                QPushButton {{
                    background: #ffffff;
                    color: #111827;
                    border: 1px solid #d5d8de;
                    border-radius: 4px;
                    padding: 4px 10px;
                    min-height: {button_height}px;
                }}
                QPushButton:hover {{ background: #eef2f7; }}
                QTabWidget::pane {{ border: 1px solid #d5d8de; }}
                QTabBar::tab {{
                    background: #f0f2f5;
                    color: #374151;
                    padding: 7px 14px;
                    border: 1px solid #d5d8de;
                    border-bottom: none;
                }}
                QTabBar::tab:selected {{
                    background: #ffffff;
                    color: #111827;
                }}
                QSplitter::handle {{ background: #d5d8de; }}
            """)

        self.setStyleSheet(self.styleSheet() + """
            QWidget[parameterPage="true"] { background: transparent; }
            QLabel[fieldLabel="true"] { font-weight: 600; }
            QLabel[sectionTitle="true"] { font-weight: 600; }
            QLabel[resultSummary="true"] { color: #596170; padding: 0px 8px 4px 38px; }
            QFrame[workflowPanel="true"] { border: 1px solid #d5d8de; border-radius: 4px; }
            QFrame[vdSummaryCard="true"] {
                border: 1px solid #9db4d0; border-radius: 7px;
            }
            QLabel[vdMetricValue="true"] { font-weight: 700; font-size: 12pt; }
            QLineEdit, QComboBox { min-height: 30px; padding: 1px 7px; }
            QCheckBox { min-height: 30px; spacing: 7px; }
            QScrollArea { border: none; background: transparent; }
            QPushButton[primaryAction="true"] {
                background: #2563eb; color: white; border: 1px solid #1d4ed8;
                font-weight: 600;
            }
            QPushButton[primaryAction="true"]:hover { background: #1d4ed8; }
            QPushButton[secondaryAction="true"] {
                background: transparent; color: #2563eb; border: 1px solid #2563eb;
                font-weight: 600;
            }
            QPushButton[secondaryAction="true"]:hover { background: #eef4ff; }
            QPushButton[compactAction="true"] {
                min-height: 0px; padding: 2px 8px;
            }
            QPushButton[patternChoice="true"]:disabled {
                background: #e5e7eb; color: #9ca3af;
                border: 1px solid #d1d5db;
            }
            QLineEdit[patternUnavailable="true"] {
                border: 1px solid #dc2626; background: #fff1f2;
            }
            QPushButton[actionToggle="true"] {
                background: #2563eb; color: white; border: 1px solid #1d4ed8;
                font-weight: bold;
            }
            QPushButton[actionToggle="true"]:hover { background: #1d4ed8; }
        """ + """
            QCheckBox::indicator {
                width: 17px; height: 17px;
                border: 1px solid #6b7280;
                border-radius: 3px;
                background: #ffffff;
            }
            QCheckBox::indicator:hover { border-color: #2563eb; }
            QCheckBox::indicator:checked {
                border: 1px solid #1d4ed8;
                background: #2563eb;
                image: url("CHECKMARK_PATH");
            }
            QCheckBox::indicator:disabled {
                border-color: #9ca3af;
                background: #e5e7eb;
            }
        """.replace("CHECKMARK_PATH", checkmark_path))
        readonly_background = "#383b40" if theme == "Dark" else "#e2e5e9"
        readonly_foreground = "#bdc1c6" if theme == "Dark" else "#596170"
        panel_border = "#5f6368" if theme == "Dark" else "#d5d8de"
        summary_foreground = "#bdc1c6" if theme == "Dark" else "#596170"
        secondary_hover = "#26364f" if theme == "Dark" else "#eef4ff"
        self.setStyleSheet(self.styleSheet() + f"""
            QLineEdit, QComboBox {{ font-size: {font_size + 1}pt; font-weight: 400; }}
            QLabel[vdMetricValue="true"] {{ font-size: {font_size + 1}pt; }}
            QLineEdit[readOnly="true"], QLineEdit:disabled {{
                background: {readonly_background}; color: {readonly_foreground};
            }}
            QFrame[workflowPanel="true"] {{ border-color: {panel_border}; }}
            QLabel[resultSummary="true"] {{ color: {summary_foreground}; }}
            QPushButton[secondaryAction="true"]:hover {{ background: {secondary_hover}; }}
        """)
        self._apply_plot_background(theme)
        for button in self.findChildren(QPushButton):
            if button.property("compactAction"):
                button.setFixedHeight(max(28, button.fontMetrics().height() + 8))
                if button in getattr(self, "action_buttons", ()):
                    button.setFixedWidth(self.action_button_width)
                else:
                    button.setMinimumWidth(0)
                    button.setMaximumWidth(max(90, button.fontMetrics().horizontalAdvance(button.text()) + 24))
            else:
                button.setMinimumHeight(button_height)
        self._update_action_area_height()
        if self.plot_window is not None:
            self.plot_window.setStyleSheet(self.styleSheet())
        if getattr(self, "wf_plot_window", None) is not None:
            self.wf_plot_window.setStyleSheet(self.styleSheet())
        for window in self.result_windows.values():
            window.setStyleSheet(self.styleSheet())

        self.resize(window_width, window_height)
        if hasattr(self, "upper_splitter"):
            self.upper_splitter.setSizes([left_width, max(420, window_width - left_width)])
        if hasattr(self, "main_splitter"):
            self.main_splitter.setSizes([max(430, window_height - bottom_height), bottom_height])
        if not silent and hasattr(self, "message_log"):
            self.message_log.append("Window settings applied.")
    
    
    # --- Button Actions ---
    
    def config_optimise_pattern(self):
        """Apply the shared Auto policy to the current UI fields.

        The historical method name remains as a compatibility entry point for
        callers and saved-workflow tests.
        """
        pattern_label = self.input_fields["pattern_name"].text()
        try:
            pattern = gw.normalize_pattern_name(pattern_label)
        except ValueError as exc:
            self.message_log.append(f"Invalid winding pattern: {exc}")
            return
        try:
            q, _ = self._resolve_slot_inputs()
            ab = int(self.input_fields["ab"].text())
            p = int(self.input_fields["num_poles"].text())
        except ValueError:
            self.message_log.append("Invalid Winding or Pole input values.")
            return

        if q.denominator != 1:
            if self._is_fractional_pattern_candidate(q):
                rule = auto_tp.select_automatic_rule(
                    pattern, q, p, ab, self._selected_dividers()[0])
                self._apply_automatic_transposition_rule(rule)
            else:
                self.message_log.append("No fractional-q pattern optimization rule is available.")
            return

        self._sync_uwp_balanced_defaults(force=True)
        if getattr(self, '_uwp_balance_key', None) is not None:
            self.message_log.append(self.uwp_balance_notice.text())
            return
        rule = auto_tp.select_automatic_rule(
            pattern, q, p, ab, self._selected_dividers()[0])
        if rule is None:
            self.message_log.append("No matching optimization rule applied.")
            return
        self._apply_automatic_transposition_rule(rule)

    def apply_auto_configuration(self, preserve_inlet_adjustments=False,
                                 keep_auto=False):
        """Evaluate Auto, optionally keeping Auto or materializing its recipe."""
        if self.tp_type_field.currentText() != "Auto":
            return False

        phase_a = list(self.inlet_index_adjustments_phase_a)
        all_branches = list(self.volt_diff_inlet_adjustments_all)
        self.inlet_index_adjustments_phase_a = []
        self.volt_diff_inlet_adjustments_all = []
        if hasattr(self, "vd_adjustment_fields"):
            self._refresh_vd_adjustment_grid()

        try:
            exact_q, _ = self._resolve_slot_inputs()
            self.extract_parameters(
                candidate_only=self._is_fractional_pattern_candidate(exact_q))
            report = self.base_db_conductor_id.auto_configuration
            effective = report["effective_parameters"]
            effective_type = effective["tp_type"]
            if keep_auto:
                self.message_log.append(
                    f"Auto Configure applied using {effective_type} parameters.")
                return True
            self.tp_type_field.setCurrentText(effective_type)
            for key, field in self.tp_fields.items():
                value = effective.get(key, 0)
                if key == "jltp":
                    value *= effective.get("jld", 1)
                field.setText(str(value))
        except Exception:
            self.inlet_index_adjustments_phase_a = phase_a
            self.volt_diff_inlet_adjustments_all = all_branches
            if hasattr(self, "vd_adjustment_fields"):
                self._refresh_vd_adjustment_grid()
            raise

        if preserve_inlet_adjustments:
            self.inlet_index_adjustments_phase_a = phase_a
            self.volt_diff_inlet_adjustments_all = all_branches
        self._last_calculation_signature = None
        if hasattr(self, "vd_adjustment_fields"):
            self._refresh_vd_adjustment_grid()
        self.message_log.append(
            f"Auto Configure applied as {effective_type} manual settings.")
        return True

    def _apply_automatic_transposition_rule(self, rule):
        """Apply a pure automatic-policy result without duplicating its rules."""
        if rule.error:
            self.message_log.append(rule.error)
            return
        self.update_transp_type(rule.effective_type)
        for key, value in rule.values.items():
            self.tp_fields[key].setText(str(value))
        self.message_log.append(
            f"Provisional transposition seed: Type={rule.effective_type}. "
            "Auto Configure strategy selection is pending Calculate.")

    def _calculation_input_signature(self):
        """Return a stable signature for every UI value that can affect results."""
        values = []
        for key in sorted(self.input_fields):
            if key.startswith("inductance_"):
                continue
            widget = self.input_fields[key]
            if (self.tp_type_field.currentText() == "Auto"
                    and key in self.tp_fields):
                value = "0"
            elif isinstance(widget, QCheckBox):
                value = widget.isChecked()
            elif isinstance(widget, QComboBox):
                value = (widget.currentData() if key == "auto_configure_objective"
                         else widget.currentText())
            elif hasattr(widget, "text"):
                value = widget.text()
            else:
                value = repr(widget)
            values.append((key, value))
        values.append(("inlet_index_adjustments_phase_a", tuple(self.inlet_index_adjustments_phase_a)))
        values.append(("volt_diff_inlet_adjustments_all", tuple(self.volt_diff_inlet_adjustments_all)))
        return tuple(values)
   
    def extract_parameters(self, candidate_only=False):
        """Extracts input values from self.input_fields and returns them as variables."""
        state_names = (
            "num_slots", "copper_fill_factor", "Rphase_active", "W_cond", "H_cond",
            "K_bend_side", "K_bend_height", "EW_info", "Stator_Para", "Winding_Para",
            "Inslot_Para", "Layout_Para", "Line_Para", "Fig_Para", "TP_info",
            "base_start_conductor_ids", "base_db_conductor_id", "base_cond_info",
            "db_conductor_id", "start_conductor_ids", "phase_A_conductor_id",
            "cond_info", "results", "candidate_report", "calculation_state",
            "_last_calculation_signature",
        )
        missing = object()
        previous_state = {name: getattr(self, name, missing) for name in state_names}
        try:
            route_decision = self._validate_divider_route()
            self._sync_vd_adjustments_from_inputs()
            input_signature = self._calculation_input_signature()
            required_state = (
                "Winding_Para", "Stator_Para", "Inslot_Para", "Layout_Para",
                "Line_Para", "Fig_Para", "TP_info", "db_conductor_id", "cond_info", "results",
            )
            if (not candidate_only
                    and input_signature == getattr(self, "_last_calculation_signature", None)
                    and all(hasattr(self, name) for name in required_state)):
                return
            # Retrieve Winding Parameters
            exact_q, num_slots = self._resolve_slot_inputs()
            if exact_q.denominator != 1:
                if not (candidate_only and route_decision.status in
                        ('enabled', 'candidate')):
                    raise ValueError("Fractional-q connection generation is not supported yet; use phase validation.")
            elif candidate_only:
                raise ValueError("The candidate-only layout route requires half-integer q.")
            q = exact_q if candidate_only else int(exact_q)
            num_poles = int(self.input_fields["num_poles"].text())
            num_layers = int(self.input_fields["num_layers"].text())
            num_phases = int(self.input_fields["num_phases"].text())
            ab = int(self.input_fields["ab"].text())
    
            # Update UI field
            if "num_slots" in self.input_fields:
                self.input_fields["num_slots"].setText(str(num_slots))

            if not candidate_only:
                cached = calculation_cache.load(self._calculation_input_signature())
                if cached is not None:
                    cached.install(self)
                    report = getattr(self.base_db_conductor_id,
                                     "auto_configuration", None)
                    if report is not None and self.tp_type_field.currentText() == "Auto":
                        self._display_auto_configuration(report)
                    self._connect_ends_check_signature = None
                    self._refresh_connect_ends_availability()
                    self.update_transp_range()
                    self.message_log.append("Restored matching calculation from saved results.")
                    return
    
            curesistivity = float(self.input_fields["curesistivity"].text())
    
            # Retrieve Stator Parameters
            Stack_length = float(self.input_fields["stack_length"].text())
            SD1 = float(self.input_fields["SD1"].text())
            SD2 = float(self.input_fields["SD2"].text())
            ksw = float(self.input_fields["ksw"].text())
            kso = float(self.input_fields["kso"].text())
            H_yoke = float(self.input_fields["H_yoke"].text())
            TH1 = float(self.input_fields["TH1"].text())
            TH2 = float(self.input_fields["TH2"].text())
    
            # Retrieve Inslot Parameters
            G_cond = float(self.input_fields["G_cond"].text())
            C_side = float(self.input_fields["C_side"].text())
            C_rad = float(self.input_fields["C_rad"].text())
            d_Ins = float(self.input_fields["d_Ins"].text())
            Overlap_Ins = 1 if self.input_fields["Overlap_Ins"].isChecked() else 0  # ✅ Checkbox
            d_coat = float(self.input_fields["d_coat"].text())
            Cond_Radi = float(self.input_fields["Cond_Radi"].text())
    
            # Retrieve End Winding Parameters
            gcond_min = float(self.input_fields["gcond_min"].text())
            fixed_Rbend = 1 if self.input_fields["fixed_Rbend"].isChecked() else 0  # ✅ Checkbox
            Uni_EWH = 1 if self.input_fields["Uni_EWH"].isChecked() else 0  # ✅ Checkbox
            Rbend_side_min = float(self.input_fields["Rbend_side_min"].text())
            Rbend_height_min = float(self.input_fields["Rbend_height_min"].text())
            L_str = float(self.input_fields["L_str"].text())
            L_weld_str = float(self.input_fields["L_weld_str"].text())
            gcond_weld = float(self.input_fields["gcond_weld"].text())
            
            # Retrieve Layout Parameters
            pattern_id = gw.normalize_pattern_name(self.input_fields["pattern_name"].text())
            pattern_name = gw.get_pattern_label(pattern_id)
            inlet_from_weld_side = 1 if self.input_fields["inlet_from_weld_side"].isChecked() else 0
            if gw.pattern_requires_weld_side_inlet(pattern_id) and inlet_from_weld_side == 0:
                inlet_from_weld_side = 1
                self.input_fields["inlet_from_weld_side"].setChecked(True)
                self.message_log.append(
                    f"Warning: {pattern_name} does not allow disabling inlet from weld side; checkbox restored."
                )
            in_out_connection = 1 if self.input_fields["in_out_connection"].isChecked() else 0
            radial_shift = 1 if self.input_fields["radial_shift"].isChecked() else 0
            CW = 1 if self.input_fields["CW"].isChecked() else 0
            phase_shift = int(self.input_fields["phase_shift"].text())
            PSL = int(self.input_fields["PSL"].text())
            phase_shift_pattern = self.input_fields["phase_shift_pattern"].currentText()
            
            # Retrieve Transposition Parameters
            tp_type = (self._auto_effective_tp_type
                       if self.input_fields["tp_type"].text() == "Auto"
                       else self.input_fields["tp_type"].text())
            tp_interval = int(self.input_fields["tp_interval"].text())
            tp_times = int(self.input_fields["tp_times"].text())
            uni_tp = int(self.input_fields["uni_tp"].text())
            pltp_fl = int(self.input_fields["pltp_fl"].text())
            pltp_ll = int(self.input_fields["pltp_ll"].text())
            jltp = abs(int(self.input_fields["jltp"].text()))
            jld = -1 if int(self.input_fields["jltp"].text()) < 0 else 1
        
            # Retrieve and parse Figure Parameters
            Show_legend = 1 if self.input_fields["Show_legend"].isChecked() else 0
            grid_color_pattern = self.get_field_value("grid_color_pattern")
            linewidth = max(0.1, float(self.get_field_value("linewidth")))
            line_alpha = min(max(self.get_float_field("line_alpha", 1.0), 0.0), 1.0)
            draw_arrow = int(self.get_field_value("draw_arrow"))
            arrow_size = max(0.2, min(self.get_float_field("arrow_size", 1.0), 5.0))
            radii_gap = max(0.01, self.get_float_field("radii_gap", 0.20))
            line_single_side = int(self.get_field_value("line_single_side"))
            Single_Phase_Draw = int(self.get_field_value("Single_Phase_Draw"))
            inline_angle = float(self.get_field_value("inline_angle"))
            outline_angle = float(self.get_field_value("outline_angle"))
            line_color_pattern = str(self.get_field_value("fig_branch_line_color")).strip().lower()
            fig_branch_line_color = 1 if line_color_pattern == "branch" else 0
            same_layer_route_style = (
                "radial_center_arc"
                if self.get_field_value("same_layer_route_style") == "Radial-center arc"
                else "direct_arc"
            )
            plot_inner_radius = max(0.5, self.get_float_field("plot_inner_radius", 3.0))
            k_layer_height = max(0.2, self.get_float_field("plot_layer_height_scale", 1.5))
            plot_margin = max(0.05, self.get_float_field("plot_margin", 1.60))
            plot_zoom = max(0.2, self.get_float_field("plot_zoom", 1.0))
            plot_padding = min(max(self.get_float_field("plot_padding", 0.01), 0.0), 0.20)
            slot_font_value = str(self.get_field_value("slotindex_fontsize_custom")).strip().lower()
            if slot_font_value in ("", "auto"):
                slotindex_fontsize = max(7, min(18, int(900 / max(num_slots, 1))))
            else:
                slotindex_fontsize = max(5, int(float(slot_font_value)))
            slotindex_offset = self.get_float_field("slotindex_offset", -0.55)
            slotindex_rotation = 1 if self.input_fields["slotindex_rotation"].isChecked() else 0
            wedge_circle = 1 if self.input_fields["wedge_circle"].isChecked() else 0
            legend_position = self.get_field_value("legend_position")
            legend_fontsize = max(7, self.get_int_field("legend_fontsize", 11))
            grid_alpha = min(max(self.get_float_field("grid_alpha", 0.30), 0.0), 1.0)
            
            # Constants / calculations
            Figure_Division = 1
            rotation_angle = 180 / num_slots
            phase_legend = Show_legend
            branch_legend = Show_legend
            if legend_position == "none":
                phase_legend = 0
                branch_legend = 0
            inner_radius = plot_inner_radius
            inner_layer_width = inner_radius * 2 * 3.1416 / num_slots
            layer_height = inner_layer_width * k_layer_height
            outer_radius = inner_radius + num_layers * layer_height
            phase_cmap_name = 'plasma'
            branch_cmap_name = 'rainbow'
            linestyle = self.get_field_value("linestyle") if "linestyle" in self.input_fields else '-'
            line_cmap_name = 'plasma'
            inlet_line = 1
            outlet_line = 1
            inlet_line_length = max(0.1, min(self.get_float_field("inlet_line_length", 1.2), 8.0))
            
            LineParaGroup = namedtuple('LinePara',['fig_branch_line_color','Single_Phase_Draw','inline_angle','outline_angle','linewidth','line_single_side','linestyle','inlet_line','outlet_line','inlet_line_length','draw_arrow','line_cmap_name','arrow_size','line_alpha','same_layer_route_style','radii_gap'])
            Line_Para =  LineParaGroup(fig_branch_line_color,Single_Phase_Draw,inline_angle,outline_angle,linewidth,line_single_side,linestyle,inlet_line,outlet_line,inlet_line_length,draw_arrow,line_cmap_name,arrow_size,line_alpha,same_layer_route_style,radii_gap)
            FigParaGroup = namedtuple('FigPara', ['rotation_angle', 'Figure_Division', 'CW', 'phase_legend','branch_legend','fig_branch_line_color', 'Single_Phase_Draw', 'phase_cmap_name', 'inner_radius', 'k_layer_height', 'inner_layer_width', 'layer_height', 'outer_radius','slotindex_fontsize','slotindex_offset','grid_color_pattern','branch_cmap_name','slotindex_rotation','wedge_circle','plot_margin','plot_zoom','plot_padding','legend_position','legend_fontsize','grid_alpha'])
            Fig_Para = FigParaGroup(rotation_angle, Figure_Division, CW, phase_legend, branch_legend, fig_branch_line_color, Single_Phase_Draw, phase_cmap_name, inner_radius, k_layer_height, inner_layer_width, layer_height, outer_radius,slotindex_fontsize,slotindex_offset,grid_color_pattern,branch_cmap_name,slotindex_rotation,wedge_circle,plot_margin,plot_zoom,plot_padding,legend_position,legend_fontsize,grid_alpha)
            
            # Compute Dependent Parameters
            W_slot = SD2 * math.pi / num_slots * ksw
            H_slot = ((SD1 - SD2) / 2 - H_yoke) - TH1 - TH2
            Area_slot = W_slot * H_slot
            W_cond = SD2 * math.pi / num_slots * ksw - d_coat * 2 - C_side * 2 - d_Ins * 2
            H_cond = (((SD1 - SD2) / 2 - H_yoke) - C_rad * 2 - d_Ins * (2 + Overlap_Ins)
                      - TH1 - TH2 - ((num_layers * 2) * d_coat) - (num_layers - 1) * G_cond) / num_layers
            
            K_bend_side = round(Rbend_side_min / W_cond,3)
            K_bend_height = round(Rbend_height_min / H_cond,3)
            Area_cond = W_cond * H_cond - Cond_Radi * Cond_Radi *(4 - math.pi) 
            Lcond_active_per_phase = Stack_length * num_slots * num_layers / num_phases / ab 
            Copper_fill_factor = Area_cond * num_layers / Area_slot
            Resistance_Active_per_phase = curesistivity * Lcond_active_per_phase / ab / Area_cond * 1000
            Rphase_active = Resistance_Active_per_phase * 1000  # mΩ
            
            # Store Parameters in NamedTuples
            EW_infoGroup = namedtuple('EW_info', ['gcond_min','fixed_Rbend','K_bend_side','K_bend_height','Rbend_side_min','Rbend_height_min','L_str','L_weld_str','uniform_ew_height','gcond_weld'])
            EW_info = EW_infoGroup(gcond_min, fixed_Rbend, K_bend_side, K_bend_height, Rbend_side_min, Rbend_height_min, L_str, L_weld_str,Uni_EWH,gcond_weld)
    
            StatorParaGroup = namedtuple('StatorPara', ['StackLength', 'SD1', 'SD2', 'H_yoke', 'TH1', 'TH2', 'ksw', 'kso'])
            Stator_Para = StatorParaGroup(Stack_length, SD1, SD2, H_yoke, TH1, TH2, ksw, kso)
    
            WindingParaGroup = namedtuple('WindingPara', ['q', 'num_poles', 'num_layers', 'num_phases', 'num_slots', 'ab', 'branch_dividers'])
            Winding_Para = WindingParaGroup(q, num_poles, num_layers, num_phases, num_slots, ab,
                                           self._selected_dividers())
    
            InslotParaGroup = namedtuple('InslotPara', ['Cond_Height', 'Cond_Width', 'Wire_Gap', 'Cond_Radi','Radial_Clearence', 'Side_Clearence', 'Wire_Coating_Thickness', 'Insulation_Thickness','Curesistivity_Eff'])
            Inslot_Para = InslotParaGroup(H_cond, W_cond, G_cond, Cond_Radi, C_rad, C_side, d_coat, d_Ins,curesistivity)
            
            phase_shift_list = gw.get_phase_shift_list(Winding_Para, phase_shift_pattern, phase_shift, PSL, log=self.message_log.append)
            raw_all_branch_adjustments = self._safe_int_list(getattr(self, "volt_diff_inlet_adjustments_all", []))
            all_branch_mode_requested = len(raw_all_branch_adjustments) == ab * num_phases
            if all_branch_mode_requested:
                inlet_index_adjustments_phase_a = [0] * ab
            else:
                inlet_index_adjustments_phase_a = self._coerce_phase_a_adjustments(ab, pattern_id, strict=True)
            LayoutParaGroup = namedtuple('LayoutPara', ['inlet_from_weld_side', 'phase_shift_pattern', 'phase_shift', 'PSL', 'radial_shift','Single_Phase_Draw','CW','in_out_connection','pattern_name','phase_shift_list','inlet_index_adjustments_phase_a'])
            Layout_Para = LayoutParaGroup(inlet_from_weld_side, phase_shift_pattern, phase_shift, PSL, radial_shift,Single_Phase_Draw,CW,in_out_connection,pattern_name,phase_shift_list,tuple(inlet_index_adjustments_phase_a))
            
            pole_group_tp = {}
            for group, prefix in (("PoleN", "pole_n"), ("PoleS", "pole_s")):
                pole_group_tp[group] = {
                    "tp_type": self.input_fields[f"{prefix}_tp_type"].currentText(),
                    **{suffix: int(self.input_fields[f"{prefix}_{suffix}"].text())
                       for suffix in ("tp_interval", "tp_times", "uni_tp",
                                      "pltp_fl", "pltp_ll", "jltp")},
                }
            TP_infoGroup = namedtuple('TP_info', ['tp_type','tp_interval','tp_times','uni_tp','pltp_fl','pltp_ll','jltp','jld','pole_group_tp'])
            TP_info = TP_infoGroup(tp_type,tp_interval,tp_times,uni_tp,pltp_fl,pltp_ll,jltp,jld,pole_group_tp)
            
            auto_report = None
            if self.tp_type_field.currentText() == "Auto":
                if (any(raw_all_branch_adjustments)
                        or any(inlet_index_adjustments_phase_a)):
                    raise ValueError(
                        "Auto Configure requires zero inlet adjustments so the "
                        "scored layout matches the result. Clear inlet adjustments "
                        "or select a manual transposition type.")
                # Derived signed display values must not reverse Auto's reference
                # when switching objectives or recalculating a saved selection.
                TP_info = TP_info._replace(tp_type="Regular", jld=1,
                                          **auto_tp.zero_values())
                evaluator = auto_tp.make_pin_length_evaluator(
                    Winding_Para, Stator_Para, Inslot_Para, EW_info)
                auto_key = (pattern_name, TP_info, Winding_Para, Layout_Para,
                            self.auto_configure_objective_field.currentData(),
                            Stator_Para, Inslot_Para, EW_info)
                saved_auto = (None if candidate_only else calculation_cache.load_auto(auto_key))
                if saved_auto is None:
                    base_start_conductor_ids, base_db_conductor_id = gw.get_auto_configured_layout(
                        pattern_name, TP_info, Winding_Para, Layout_Para,
                        allow_candidate=candidate_only,
                        objective=self.auto_configure_objective_field.currentData(),
                        pin_length_evaluator=evaluator)
                    if not candidate_only:
                        calculation_cache.save_auto(
                            auto_key, base_start_conductor_ids, base_db_conductor_id)
                else:
                    base_start_conductor_ids, base_db_conductor_id = saved_auto
                    self.message_log.append("Reused saved Auto Configure result.")
                auto_report = base_db_conductor_id.auto_configuration
                TP_info = TP_info._replace(**{
                    key: value for key, value in auto_report["effective_parameters"].items()
                    if key in TP_info._fields})
            else:
                base_start_conductor_ids, base_db_conductor_id = gw.get_winding_layout(
                    pattern_name, TP_info, Winding_Para, Layout_Para)
            if (gw.selected_integer_divider_route(pattern_name, Winding_Para) == 'uwp_balanced_q'
                    and any(raw_all_branch_adjustments)):
                raise ValueError('UWP balanced divider requires automatic branch starts; clear inlet adjustments.')
            grouped_exchanges = getattr(base_db_conductor_id,
                                        'transposition_report', {}).get('exchanges', [])
            if (candidate_only and hasattr(base_db_conductor_id, 'sector_array_report')
                    and (any(raw_all_branch_adjustments)
                         or any(inlet_index_adjustments_phase_a))):
                raise ValueError('Global wave candidates do not support inlet adjustments.')
            if candidate_only and grouped_exchanges and (
                    any(raw_all_branch_adjustments)
                    or any(inlet_index_adjustments_phase_a)):
                raise ValueError('Grouped transposition candidates do not support inlet adjustments.')
            base_cond_info = gw.Winding_Phase_division(Winding_Para, Layout_Para)
            all_branch_adjustments = self._coerce_all_branch_adjustments(
                len(base_db_conductor_id),
                pattern_id,
                strict=False,
            )
            if all_branch_adjustments is not None:
                db_conductor_id = self.apply_all_branch_inlet_adjustments(
                    base_db_conductor_id,
                    all_branch_adjustments,
                )
            else:
                db_conductor_id = self.apply_phase_a_inlet_adjustments(
                    base_db_conductor_id,
                    base_cond_info,
                    inlet_index_adjustments_phase_a,
                    expected_count=ab,
                )
            if (pattern_name == 'SLP'
                    and gw.selected_integer_divider_route(
                        pattern_name, Winding_Para) == 'pp_only'
                    and (any(all_branch_adjustments or ())
                         or any(inlet_index_adjustments_phase_a))):
                gw.validate_pp_only_spiral(
                    pattern_name, db_conductor_id, Winding_Para, Layout_Para)
                identity = gw._analyze_pattern_identity_for_sets(
                    pattern_name, db_conductor_id, Winding_Para, Layout_Para)
                if identity['status'] == 'candidate':
                    raise gw.PatternConfigurationError(
                        'pattern_identity_candidate',
                        'Adjusted layout is isolated as Candidate: '
                        + identity['reason'], pattern_name)
            if gw.uses_p2_divider(pattern_name, Winding_Para):
                start_conductor_ids, db_conductor_id = gw.orient_p2_branches_n_to_s(
                    db_conductor_id, Winding_Para, Layout_Para)
            else:
                start_conductor_ids = [
                    branch_info[1][0]
                    for branch_info in db_conductor_id if branch_info[1]
                ]
            phase_A_conductor_id = [
                [branch_id, conductors]
                for _list_index, branch_id, conductors in self._phase_a_branch_infos(
                    db_conductor_id, base_cond_info, expected_count=ab)
            ]
            cond_info = cio.update_cond_info_with_branch_data(list(base_cond_info), db_conductor_id)
            results = la.analyze_database(db_conductor_id, Winding_Para, Layout_Para)
            candidate_report = gw.fractional_uwp_candidate_report(
                db_conductor_id, Winding_Para, Layout_Para)
            if not candidate_only and candidate_report['layout_status'] != 'not strong symmetry layout':
                candidate_report = None
            if candidate_report is not None:
                if candidate_report.get('layout_status') == 'not strong symmetry layout':
                    self.message_log.append('not strong symmetry layout: retained with EMF asymmetry; not certified as electrically balanced.')
                candidate_report['transposition'] = getattr(
                    base_db_conductor_id, 'transposition_report', None)
                if hasattr(base_db_conductor_id, 'sector_array_report'):
                    candidate_report['sector_array'] = base_db_conductor_id.sector_array_report
            self._connect_ends_check_signature = None
            # Input resolution can normalize dependent fields such as q/slots;
            # cache the signature matching the values now visible to the user.
            if auto_report is not None:
                self._display_auto_configuration(auto_report)
            calculation_state = CalculationState.create(
                self._calculation_input_signature(),
                generation=getattr(getattr(self, "calculation_state", None), "generation", 0) + 1,
                num_slots=num_slots,
                copper_fill_factor=Copper_fill_factor,
                Rphase_active=Rphase_active,
                W_cond=W_cond,
                H_cond=H_cond,
                K_bend_side=K_bend_side,
                K_bend_height=K_bend_height,
                EW_info=EW_info,
                Stator_Para=Stator_Para,
                Winding_Para=Winding_Para,
                Inslot_Para=Inslot_Para,
                Layout_Para=Layout_Para,
                all_branch_adjustments=all_branch_adjustments,
                Line_Para=Line_Para,
                Fig_Para=Fig_Para,
                TP_info=TP_info,
                base_start_conductor_ids=base_start_conductor_ids,
                base_db_conductor_id=base_db_conductor_id,
                base_cond_info=base_cond_info,
                db_conductor_id=db_conductor_id,
                start_conductor_ids=start_conductor_ids,
                phase_A_conductor_id=phase_A_conductor_id,
                cond_info=cond_info,
                results=results,
                candidate_report=candidate_report,
            )
            if candidate_only:
                return calculation_state
            calculation_state.install(self)
            calculation_cache.save(calculation_state)
            self._refresh_connect_ends_availability()
            self.update_transp_range()  # ✅ Initialize range labels on tab creation
            
        except Exception as exc:
            # A failed generation must not expose a mixture of new parameters
            # and stale layout/results to later plot or export actions.
            for name, value in previous_state.items():
                if value is missing:
                    if hasattr(self, name):
                        delattr(self, name)
                else:
                    setattr(self, name, value)
            if isinstance(exc, ValueError):
                self.dependent_params_display.setText("Invalid input! Please check the values.")
                self.message_log.append(f"Input or pattern validation failed: {exc}")
            raise
         
    def _set_calculation_result_summary(self, section, text):
        """Keep concise Parameter and Layout summaries together in the bottom panel."""
        self._calculation_result_sections[section] = text.strip()
        self.result_display.setPlainText("\n\n".join(
            self._calculation_result_sections[key]
            for key in ("parameters", "layout")
            if self._calculation_result_sections.get(key)))

    @staticmethod
    def _brief_layout_analysis(result_text):
        prefixes = (
            "UWP half-integer q candidate layout only.",
            "BWP half-integer q candidate layout only.",
            "Electrical checks:",
            "Number of different pin shapes:",
            "This winding pattern",
        )
        lines = [line.strip() for line in result_text.splitlines()
                 if line.strip().startswith(prefixes)]
        if not lines:
            lines = [line.strip() for line in result_text.splitlines() if line.strip()][:2]
        return "Layout Analysis\n" + "\n".join(lines[:3])

    def _fractional_dependent_parameter_values(self, q, num_slots):
        """Calculate geometry-only values without invoking a winding-pattern generator."""
        num_poles = int(self.input_fields["num_poles"].text())
        num_layers = int(self.input_fields["num_layers"].text())
        num_phases = int(self.input_fields["num_phases"].text())
        ab = int(self.input_fields["ab"].text())
        if q <= 0 or min(num_slots, num_poles, num_layers, num_phases, ab) <= 0:
            raise ValueError("q, slots, poles, phases, layers and branches must be positive.")
        value = lambda key: float(self.input_fields[key].text())
        curesistivity, stack_length = value("curesistivity"), value("stack_length")
        sd1, sd2, ksw, h_yoke = value("SD1"), value("SD2"), value("ksw"), value("H_yoke")
        th1, th2 = value("TH1"), value("TH2")
        gap, c_side, c_rad = value("G_cond"), value("C_side"), value("C_rad")
        d_ins, d_coat, cond_radii = value("d_Ins"), value("d_coat"), value("Cond_Radi")
        overlap = 1 if self.input_fields["Overlap_Ins"].isChecked() else 0
        rbend_side, rbend_height = value("Rbend_side_min"), value("Rbend_height_min")
        slot_width = sd2 * math.pi / num_slots * ksw
        slot_height = ((sd1 - sd2) / 2 - h_yoke) - th1 - th2
        slot_area = slot_width * slot_height
        conductor_width = slot_width - 2 * (d_coat + c_side + d_ins)
        conductor_height = (((sd1 - sd2) / 2 - c_rad * 2 - d_ins * (2 + overlap)
                             - th1 - th2 - (num_layers * 2) * d_coat
                             - (num_layers - 1) * gap) / num_layers)
        conductor_area = conductor_width * conductor_height - cond_radii ** 2 * (4 - math.pi)
        if min(slot_area, conductor_width, conductor_height, conductor_area) <= 0:
            raise ValueError("The current geometry leaves no valid conductor area.")
        active_length = stack_length * num_slots * num_layers / num_phases / ab
        return {
            "num_slots": num_slots,
            "copper_fill_factor": conductor_area * num_layers / slot_area,
            "Rphase_active": curesistivity * active_length / ab / conductor_area * 1_000_000,
            "W_cond": conductor_width,
            "H_cond": conductor_height,
            "K_bend_side": round(rbend_side / conductor_width, 3),
            "K_bend_height": round(rbend_height / conductor_height, 3),
            "Winding_Para": NS(q=q, num_slots=num_slots, num_poles=num_poles,
                                 num_layers=num_layers, num_phases=num_phases, ab=ab),
        }

    def _resolve_dependent_slot_inputs(self):
        """Resolve q and slots for geometry-only analysis without topology constraints."""
        poles = int(self.input_fields["num_poles"].text())
        phases = int(self.input_fields["num_phases"].text())
        if poles <= 0 or phases <= 0:
            raise ValueError("Number of poles and phases must be positive.")
        if self.input_fields["winding_input_mode"].currentText() == "Slots and poles":
            slots = int(self.input_fields["num_slots"].text())
            if slots <= 0:
                raise ValueError("Number of slots must be positive.")
            q = Fraction(slots, poles * phases)
            self.input_fields["q"].setText(str(q))
        else:
            q = phase_topology.parse_q(self.input_fields["q"].text())
            if q <= 0:
                raise ValueError("q must be positive.")
            total = q * poles * phases
            if total.denominator != 1:
                raise ValueError("q, phases and poles must produce an integer slot count.")
            slots = int(total)
            self.input_fields["num_slots"].setText(str(slots))
        return q, slots

    def analyze_parameters(self):
        """Retrieves input values, calculates dependent parameters, and stores them in namedtuples."""
        try:
            exact_q, _ = self._resolve_dependent_slot_inputs()
            if exact_q.denominator != 1:
                values = self._fractional_dependent_parameter_values(exact_q, int(self.input_fields["num_slots"].text()))
            else:
                state = self.extract_parameters()
                values = state.values if state is not None else {
                    name: getattr(self, name) for name in (
                        "num_slots", "copper_fill_factor", "Rphase_active", "W_cond", "H_cond",
                        "K_bend_side", "K_bend_height", "Winding_Para")}
            winding = values["Winding_Para"]
            num_slots = values["num_slots"]
            copper_fill_factor = values["copper_fill_factor"]
            resistance = values["Rphase_active"]
            conductor_width = values["W_cond"]
            conductor_height = values["H_cond"]
            bend_side = values["K_bend_side"]
            bend_height = values["K_bend_height"]
    
            # Compute electrical checks
            num_elec_positions = winding.q * winding.num_layers
            num_conductors_per_branch = (winding.num_poles * winding.q * winding.num_layers) / winding.ab
            num_conductors_per_position = winding.num_poles / winding.ab
            
            # Symmetry check
            symmetry_message = ""
            if not num_conductors_per_position.is_integer():
                symmetry_message = "⚠️ Warning: Unable to achieve full symmetry (conductors per position is not an integer)"
            else:
                symmetry_message = "✅ Symmetry check passed (conductors per position is an integer)"
                
            self.message_log.append(symmetry_message)
            
            # Update Display
            self.dependent_params_display.setText(
                f"Dependent Parameters:\n"
                f" - q: {winding.q}\n"
                f" - Number of Slots: {num_slots}\n"
                f" - Conductor Width: {conductor_width:.3f} mm\n"
                f" - Conductor Height: {conductor_height:.3f} mm\n"
                f" - Copper fill factor: {copper_fill_factor:.3f}\n"
                f" - K_bend_side: {bend_side:.2f} \n"
                f" - K_bend_height: {bend_height:.2f}\n"
                f" - R_Phase_active: {resistance:.2f} mΩ\n"
                f" - Num Elec Positions: {num_elec_positions}\n"
                f" - Conductors per Branch: {float(num_conductors_per_branch):.0f}\n"
                f" - Conductors per Position: {num_conductors_per_position:.2f}\n"
            )
            self._calculation_result_sections.pop("layout", None)
            self._set_calculation_result_summary(
                "parameters",
                "Parameters\n"
                f"q: {winding.q} | Slots: {num_slots} | Poles: {winding.num_poles} | Layers: {winding.num_layers}\n"
                f"Phases: {winding.num_phases} | Parallel branches: {winding.ab}\n"
                f"Conductor: {conductor_width:.3f} × {conductor_height:.3f} mm | Cu fill: {copper_fill_factor:.3f}\n"
                f"R phase active: {resistance:.2f} mΩ")
    
            self.message_log.append("Dependent parameters updated.")
    
        except ValueError as exc:
            self.dependent_params_display.setText("Invalid input! Please check the values.")
            self._set_calculation_result_summary("parameters", "Parameters\nUnavailable: invalid input.")
            self.message_log.append(f"Input or pattern validation failed: {exc}")

            
        except ValueError as exc:
            self.dependent_params_display.setText("Invalid input! Please check the values.")
            self.message_log.append(f"Input or pattern validation failed: {exc}")
            
    def _is_fractional_pattern_candidate(self, exact_q):
        if exact_q.denominator == 1:
            return False
        decision = self._base_selected_route_decision()
        return decision.status in ('enabled', 'candidate')

    def analyze_layouts(self):
        """Analyzes the winding layout and displays results in the GUI."""
        try:
            exact_q, _ = self._resolve_slot_inputs()
            candidate = self._is_fractional_pattern_candidate(exact_q)
            state = self.extract_parameters(candidate_only=candidate)
            if candidate:
                self._discard_published_calculation()
                report = state.values['candidate_report']
                self.layout_display.setText(
                    la.format_fractional_candidate_analysis(
                        state.values['db_conductor_id'], state.values['Winding_Para'],
                        state.values['Layout_Para'], report,
                        state.values['all_branch_adjustments'],
                        pattern=gw.normalize_pattern_name(
                            self.input_fields["pattern_name"].text()))
                    + self._format_pole_group_tp_report(state.values['candidate_report'])
                    + self._format_sector_array_report(report, detailed=True))
                self._set_calculation_result_summary(
                    "layout", self._brief_layout_analysis(self.layout_display.toPlainText()))
                self.message_log.append("Fractional Pattern candidate analysis completed; production results were not published.")
                return
            # Get formatted results
            result_text = la.format_analysis_results(self.results)
            report = getattr(self, 'candidate_report', None)
            if report and report.get('layout_status') == 'not strong symmetry layout':
                result_text = 'not strong symmetry layout\n' + ', '.join(report['errors']) + '\n\n' + result_text

            # Display results in the layout display panel
            self.layout_display.setText(result_text)
            self._set_calculation_result_summary("layout", self._brief_layout_analysis(result_text))
    
            # Log the action in the message log
            self.message_log.append("Winding layout analysis completed.")
    
        except ValueError as exc:
            message = f"Layout analysis unavailable: {exc}"
            self.layout_display.setText(message)
            self._set_calculation_result_summary("layout", "Layout Analysis\nUnavailable: invalid input.")
            self.message_log.append(message)
        except Exception as e:
            event_id = self._record_unexpected_error("layout_analysis", e)
            message = f"Layout analysis failed. Reference: {event_id}"
            self.layout_display.setText(message)
            self._set_calculation_result_summary("layout", "Layout Analysis\nFailed. See System Messages.")
            self.message_log.append(message)

    def _discard_published_calculation(self):
        """Remove a previous production result before showing a candidate."""
        old_state = getattr(self, 'calculation_state', None)
        if old_state is None:
            return
        for name in old_state.values:
            if hasattr(self, name):
                delattr(self, name)
        del self.calculation_state
        self._last_calculation_signature = None

    @staticmethod
    def _format_uwp_candidate_analysis(report, drawn, pattern='UWP'):
        not_strong = bool(set(report['errors']) & gw.EMF_ASYMMETRY_ERRORS)
        checks = ("Unequal complex EMF between parallel branches "
                  "(parallel_emf_mismatch)."
                  if not_strong
                  else ", ".join(report['errors'] or ['no mismatch detected']))
        lines = [
            f"{pattern} candidate layout only. Electrical balance and "
            "production use are not approved.",
            ("Connection paths are drawn for inspection." if drawn else
             "Use Plot Layout to inspect the candidate connection paths."),
            ("This winding pattern does not feature strong symmetry." if not_strong else
             "This winding pattern features strong symmetry."),
            "Electrical checks: " + checks,
        ]
        if not drawn:
            for phase, values in sorted(report['branch_emf'].items()):
                emf = ", ".join(f"{real:.6g}{imag:+.6g}j" for real, imag in values)
                lines.append(f"Phase {WindingApp._phase_label(phase)} branch EMF: {emf}")
        return "\n".join(lines)

    @staticmethod
    def _format_pole_group_tp_report(report):
        metadata = report.get("transposition") if report else None
        if not metadata:
            return ""
        groups = metadata.get('groups', {}) if isinstance(metadata, dict) else {}
        selected = any(spec.get('tp_type') != 'Regular' or any(
            spec.get(key, 0) for key in ('uni_tp', 'pltp_fl', 'pltp_ll', 'jltp'))
            for spec in groups.values())
        if not selected:
            return ""
        lines = ["", "PoleN/PoleS transposition candidate:"]
        if isinstance(metadata, dict):
            lines.extend(f"{key}: {value}" for key, value in metadata.items())
        else:
            lines.append(str(metadata))
        return "\n".join(lines)

    @staticmethod
    def _format_sector_array_report(report, detailed=False):
        sector = report.get('sector_array') if report else None
        if not sector:
            return ''
        edges = sector['special_edges']
        crossings = sector['shifted_boundary_crossings']
        routing_differences = sum(
            edge['grid_shortest_pitch'] != edge['shifted_signed_pitch']
            for edge in edges)
        lines = [f"\nGlobal wave array: {sector['sectors']} evenly spaced starts, "
                 f"{sector['sector_slots']} slots between starts.",
                 f"Special edges: {len(edges)} insertion-side connections.",
                 f"Special edges using a different shortest-grid direction: "
                 f"{routing_differences}; inspect their default and plotted pitches.",
                 f"Phase-shift boundary crossings: {len(crossings)} "
                 "(branch identity follows its unshifted start)."]
        if detailed:
            for edge in edges:
                source_slot, source_layer = edge['from_default']
                target_slot, target_layer = edge['to_default']
                lines.append(
                    f"B{edge['branch_id']} {edge['kind']}: "
                    f"S{source_slot + 1}/L{source_layer + 1} -> "
                    f"S{target_slot + 1}/L{target_layer + 1}; "
                    f"default pitch {edge['default_signed_pitch']:+d}, "
                    f"shifted pitch {edge['shifted_signed_pitch']:+d}, "
                    f"plotted shortest pitch {edge['grid_shortest_pitch']:+d}.")
        return "\n".join(lines)

    def plot_layout(self):
        """Draw a validated integer layout or isolated fractional candidate."""
        self._show_layout_plot_canvas()
        try:
            exact_q, _ = self._resolve_slot_inputs()
            candidate = self._is_fractional_pattern_candidate(exact_q)
            state = getattr(self, "calculation_state", None)
            if (candidate or state is None
                    or state.signature != self._calculation_input_signature()):
                state = self.extract_parameters(candidate_only=candidate)
                if state is None:
                    state = self.calculation_state
            values = state.values
            if candidate:
                self._discard_published_calculation()
                report = values['candidate_report']
                self.layout_display.setText(
                    self._format_uwp_candidate_analysis(
                        report, drawn=True,
                        pattern=gw.normalize_pattern_name(
                            self.input_fields["pattern_name"].text()))
                    + self._format_pole_group_tp_report(report)
                    + self._format_sector_array_report(report))
            else:
                self.layout_display.setText(la.format_analysis_results(values['results']))
                report = values.get('candidate_report')
                if report and report.get('layout_status') == 'not strong symmetry layout':
                    self.layout_display.setText('not strong symmetry layout\n' + ', '.join(report['errors'])
                                                + '\n\n' + self.layout_display.toPlainText())
            signature = ((candidate, state.signature),
                         self.winding_view_selector.currentText(), self.winding_phase_selector.currentData(),
                         self.winding_branch_selector.currentData())
            if (self.current_view_type == "winding"
                    and signature == getattr(self, "_winding_plot_signature", None)):
                self._update_plot_toolbar()
                self.fit_plot_view()
                self.message_log.append("Reused unchanged winding layout plot.")
                return
            names = ("Winding_Para", "Fig_Para", "Layout_Para", "Line_Para",
                     "cond_info", "start_conductor_ids")
            self._winding_plot_data = deepcopy({name: values[name] for name in names})
            if candidate:
                self._winding_plot_data['candidate_report'] = values['candidate_report']
            self._winding_candidate = candidate
            phases_by_branch = {}
            for row in values['cond_info']:
                branch = int(row[3])
                if branch > 0:
                    phases_by_branch.setdefault(branch, set()).add(int(row[2]))
            selected_phase = self.winding_phase_selector.currentData()
            selected_branch = self.winding_branch_selector.currentData()
            available_phases = sorted({next(iter(phases)) for phases in phases_by_branch.values()
                                       if len(phases) == 1})
            self.winding_phase_selector.blockSignals(True)
            self.winding_phase_selector.clear()
            self.winding_phase_selector.addItem("All", None)
            for phase in available_phases:
                if 0 <= phase < 26:
                    self.winding_phase_selector.addItem(f"Phase {chr(ord('A') + phase)}", phase)
            self.winding_phase_selector.setCurrentIndex(
                max(0, self.winding_phase_selector.findData(selected_phase)))
            self.winding_phase_selector.blockSignals(False)
            self._rebuild_winding_branch_selector(selected_branch)
            self._winding_data_signature = candidate, state.signature
            self._render_winding_view()
        except Exception as exc:
            self._fail_winding_plot(exc)

    def _fail_winding_plot(self, exc):
        """Never expose a partial drawing as an exportable result."""
        self.ax.clear()
        self.ax.axis("off")
        self.current_view_type = "empty"
        self._winding_candidate = False
        self._winding_plot_signature = None
        getattr(self, "_plot_label_scales", {}).pop(id(self.ax), None)
        self._update_plot_toolbar()
        self.canvas.draw_idle()
        event_id = self._record_unexpected_error("layout_plot", exc)
        self.message_log.append(f"Error plotting layout: {exc} [Reference: {event_id}]")

    def _render_winding_view(self, _view=None):
        """Switch projection using the last plotted snapshot, never live inputs."""
        data = self._winding_plot_data
        if data is None:
            return
        try:
            self._show_layout_plot_canvas()
            self.current_view_type = "empty"
            self._update_plot_toolbar()
            self.ax.clear()
            winding, figure, layout, lines = (
                data[name] for name in ("Winding_Para", "Fig_Para", "Layout_Para", "Line_Para"))
            if self.winding_view_selector.currentText() == "Unwrapped":
                dfig.draw_unwrapped_winding_layout(
                    self.ax, data["cond_info"], data["start_conductor_ids"],
                    winding, layout, figure, lines, branch_id=self.winding_branch_selector.currentData(),
                    phase_id=self.winding_phase_selector.currentData())
            else:
                dfig.draw_winding_scheme_ax(winding, figure, layout, self.ax,
                                           cond_info=data["cond_info"])
                dfig.draw_circular_winding_layout(
                    self.ax, data["cond_info"], data["start_conductor_ids"],
                    winding, layout, figure, lines, branch_id=self.winding_branch_selector.currentData(),
                    phase_id=self.winding_phase_selector.currentData())
                self.apply_plot_view(figure)
            self._apply_plot_background("Light")
            self.phase_preview = None
            self.current_view_type = "winding"
            self._refresh_manual_starts_availability()
            self._winding_plot_signature = (
                self._winding_data_signature, self.winding_view_selector.currentText(),
                self.winding_phase_selector.currentData(),
                self.winding_branch_selector.currentData())
            self._update_plot_toolbar()
            self.canvas.draw()
            self._reset_plot_label_scale(self.ax)
            self.message_log.append(
                ("Plotted fractional candidate layout for inspection"
                 if self._winding_candidate else "Plotted winding layout successfully")
                + f" ({self.winding_view_selector.currentText()}).")
        except Exception as exc:
            self._fail_winding_plot(exc)

    def apply_plot_view(self, figure_parameters=None):
        if figure_parameters is None and not hasattr(self, "Fig_Para"):
            return
        figure_parameters = figure_parameters if figure_parameters is not None else self.Fig_Para
        padding = getattr(figure_parameters, "plot_padding", 0.01)
        padding = max(0.0, min(float(padding), 0.2))
        position = getattr(figure_parameters, "legend_position", "center")
        uses_right_margin = position in {"upper right", "lower right", "right"}
        axes_width = (0.75 - padding) if uses_right_margin else (1 - 2 * padding)
        self.ax.set_position([padding, padding, axes_width, 1 - 2 * padding])
        base_limit = (figure_parameters.outer_radius + figure_parameters.plot_margin) / max(figure_parameters.plot_zoom, 0.2)
        route_limit = max(abs(value) for value in (*self.ax.get_xlim(), *self.ax.get_ylim()))
        limit = max(base_limit, route_limit)
        self.ax.set_xlim(-limit, limit, auto=True)
        self.ax.set_ylim(-limit, limit, auto=True)
        # Preserve circular geometry while allowing the axes itself to fill a
        # non-square window. Matplotlib expands data limits, not a white frame.
        self.ax.set_aspect("equal", adjustable="datalim")
        self.ax.axis("off")

    def save_layout_as_figure(self):
        """Save the displayed result without recomputing parameters or connections."""
        if self.plot_stack.currentWidget() is not self.canvas:
            self.message_log.append("Use the Volt Diff export controls for its current plot.")
            return
        if self.current_view_type == "empty":
            self.message_log.append("Plot a layout or phase division before saving.")
            return
    
        # Ensure 'plots' directory exists
        save_folder = "plots"
        os.makedirs(save_folder, exist_ok=True)
    
        # Extract needed parameters for naming
        try:
            if self.current_view_type == "phase":
                slots = str(self.phase_preview["slots"])
                poles = str(self.phase_preview["poles"])
                layers = str(self.phase_preview["layers"])
                suffix = "Phase_" + self.phase_view_selector.currentText()
                if self.phase_start_mode.isChecked():
                    suffix += "_ManualStartCandidate"
            else:
                winding = self._winding_plot_data["Winding_Para"]
                slots = str(winding.num_slots)
                poles = str(winding.num_poles)
                layers = str(winding.num_layers)
                suffix = f"Naa{winding.ab}"
                if self._winding_candidate:
                    pattern = gw.normalize_pattern_name(
                        self._winding_plot_data["Layout_Para"].pattern_name)
                    suffix += f"_{pattern}Candidate"
                if self.winding_view_selector.currentText() == "Unwrapped":
                    suffix += "_Unwrapped"
                branch = self.winding_branch_selector.currentData()
                phase = self.winding_phase_selector.currentData()
                if branch is not None:
                    suffix += f"_Branch{branch}"
                elif phase is not None:
                    suffix += f"_Phase{chr(ord('A') + phase)}"
        except AttributeError:
            self.message_log.append("Missing parameters for file naming.")
            return
    
        # Optional sequence index (could be an internal counter or timestamp)
        sequence_index = datetime.now().strftime("%Y%m%d%H%M%S")  # Timestamp for uniqueness
    
        # Build the filename
        filename = f"S{slots}P{poles}L{layers}_{suffix}_{sequence_index}.png"
        save_path = os.path.join(save_folder, filename)
    
        try:
            save_dpi = max(72, min(self.get_int_field("save_dpi", 500), 1200))
            self.figure.savefig(save_path, dpi=save_dpi, bbox_inches='tight',
                                facecolor="white", edgecolor="white")
            self.message_log.append(f"Layout figure saved as: {save_path}")
        except Exception as e:
            event_id = self._record_unexpected_error("layout_figure_export", e)
            self.message_log.append(f"Failed to save layout figure: {e} [Reference: {event_id}]")

    def initial_end_winding_calc(self):
        self.extract_parameters()
        phase_resistance, phase_inductance, total_end_winding_length = ewc.calculate_end_parameters_by_results(self.Winding_Para,self.Stator_Para,self.Inslot_Para,self.EW_info,self.results)
        phase_resistance = phase_resistance * 1000
        phase_inductance = phase_inductance * 1000
        result_text = (
            f"Initial Calculation on End Winding(EW):\n"
            f"EW Phase resistance: {phase_resistance:.5f} mΩ\n"
            f"EW Phase Inductance: {phase_inductance:.5f} mH\n"
            f"Total End Winding Length: {total_end_winding_length:.2f} mm"
        )
        self.result_display.setText(result_text)
        self.message_log.append("Initial end winding calculations completed.")
        
        # Get the directory where the executable (or script) is located
        if getattr(sys, 'frozen', False):  # When running as an exe
            base_dir = os.path.dirname(sys.executable)
        else:  # When running as a script
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
        # Define the output path inside the executable's directory
        path = os.path.join(base_dir, "Pin_Info.csv")
        # Save the file
        la.output_3D_pin_info(self.phase_A_conductor_id, self.Winding_Para, self.Layout_Para, self.Stator_Para, self.Inslot_Para, self.EW_info, path)
        self.message_log.append(f"Initial pin info saved at: {path}")

    def is_matlab_installed():
        return shutil.which("matlab") is not None
    
    def optimize_end_winding(self):
        # Determine base directory (exe or script mode)
        base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
        self.message_log.append(f"Running MATLAB optimization... Base directory: {base_dir}")
        if not MATLAB_ENGINE_AVAILABLE:
            self.message_log.append("MATLAB Engine for Python is not installed. Install MATLAB Engine before running optimization.")
            return
        
        eng = None
        try:
            # Start MATLAB Engine in headless mode for performance
            import time
            start_time = time.time()
            eng = matlab.engine.start_matlab("-nojvm -nosplash -nodesktop")
    
            # Set working directory and path for MATLAB
            eng.addpath(base_dir, nargout=1)
            eng.cd(base_dir)
    
            # Execute MATLAB 'main' function (make sure your main.m is ready)
            eng.main(nargout=0)
    
            elapsed = time.time() - start_time
            self.message_log.append(f"✅ MATLAB script 'main.m' executed successfully in {elapsed:.2f} seconds.")
    
        except Exception as e:
            self.message_log.append(f"❌ Error: MATLAB execution failed. {str(e)}")
        finally:
            try:
                if eng is not None:
                    eng.quit()
            except Exception:
                self.message_log.append("⚠️ MATLAB engine was already closed or failed to close properly.")


    def final_end_winding_calc(self):
        PinInfo_Path = 'Pin_Info_WithEnd.csv'
        phase_resistance, phase_inductance, total_end_winding_length = ewc.calculate_phase_parameters_by_Pin_Info(self.Winding_Para,self.Stator_Para,self.Inslot_Para,self.EW_info,PinInfo_Path)
        
        result_text = (
            f"Final Calculation:\n"
            f"Updated Phase Resistance: {phase_resistance:.5f} Ohms\n"
            f"Updated Phase Inductance: {phase_inductance:.5f} H\n"
            f"Updated Total End Winding Length: {total_end_winding_length:.2f} mm"
        )
        self.result_display.setText(result_text)
        self.message_log.append("Final end winding calculations completed.")
        self.message_log.append("Final end winding stl exported.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WindingApp()
    window.show()
    sys.exit(app.exec())
