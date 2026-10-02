from __future__ import annotations

import os

import numpy as np
import end_winding_calc as ewc
import inductance_calculation as ic
import phase_topology
from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QTabWidget, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout, QWidget,
)


class InductanceUIMixin:
    def create_inductance_tab(self):
        """Build the active-length self/mutual inductance workbench."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        controls = QGridLayout()
        controls.setHorizontalSpacing(10)
        controls.setVerticalSpacing(8)
        controls.addWidget(QLabel("Medium relative permeability (μr):"), 0, 0)
        self.inductance_mu_r_input = QLineEdit("1.0")
        self.inductance_mu_r_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.inductance_mu_r_input.setToolTip(
            "Homogeneous-medium multiplier. Use 1.0 for the bounded air/copper model.")
        self.input_fields["inductance_mu_r"] = self.inductance_mu_r_input
        controls.addWidget(self.inductance_mu_r_input, 0, 1)

        controls.addWidget(QLabel("Rectangular self GMR (mm):"), 0, 2)
        self.inductance_gmr_display = QLineEdit("—")
        self.inductance_gmr_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.inductance_gmr_display.setReadOnly(True)
        self.inductance_gmr_display.setToolTip(
            "Derived from the current conductor width and height using the "
            "rectangular-section geometric mean distance.")
        controls.addWidget(self.inductance_gmr_display, 0, 3)
        controls.setColumnStretch(1, 1)
        controls.setColumnStretch(3, 1)

        self.inductance_calculate_button = QPushButton("Calculate Inductance")
        self.configure_command_button(self.inductance_calculate_button, 190)
        self.inductance_calculate_button.setProperty("primaryAction", True)
        self.inductance_calculate_button.clicked.connect(self.calculate_inductance)
        controls.addWidget(self.inductance_calculate_button, 1, 0, 1, 2)
        self.inductance_help_button = QPushButton("? Model Guide")
        self.inductance_help_button.setToolTip(
            "Open the illustrated Inductance model guide.")
        self.inductance_help_button.clicked.connect(self.open_inductance_help)
        controls.addWidget(self.inductance_help_button, 1, 2, 1, 2)
        layout.addLayout(controls)

        self.inductance_model_note = QLabel(
            "Model scope: finite, straight active conductors in a homogeneous medium. "
            "Excludes end winding, slot/tooth iron-boundary effects, saturation, and "
            "frequency-dependent current redistribution. Mutual-inductance signs use "
            "the positive-current directions from the phase-topology sign map.")
        self.inductance_model_note.setWordWrap(True)
        self.inductance_model_note.setProperty("resultSummary", True)
        layout.addWidget(self.inductance_model_note)

        self.inductance_summary = QTextEdit()
        self.inductance_summary.setReadOnly(True)
        self.inductance_summary.setMinimumHeight(100)
        self.inductance_summary.setPlaceholderText(
            "Generate a layout, then select Calculate Inductance.")
        layout.addWidget(self.inductance_summary)

        matrix_toolbar = QHBoxLayout()
        self.inductance_normalization_note = QLabel(
            "Normalized: kij = Mij / sqrt(Lii Ljj); diagonal = 1; "
            "signed values follow the same reference-current directions.")
        self.inductance_normalization_note.setWordWrap(True)
        matrix_toolbar.addWidget(self.inductance_normalization_note, 1)
        self.inductance_matrix_popout_button = QPushButton("Pop Out Matrix")
        self.configure_command_button(self.inductance_matrix_popout_button, 150)
        self.inductance_matrix_popout_button.setMaximumWidth(180)
        self.inductance_matrix_popout_button.setEnabled(False)
        self.inductance_matrix_popout_button.clicked.connect(
            self.toggle_inductance_matrix_window)
        matrix_toolbar.addWidget(self.inductance_matrix_popout_button)
        layout.addLayout(matrix_toolbar)

        self.inductance_matrix_tabs = QTabWidget()
        phase_page, self.inductance_phase_table = (
            self._create_inductance_matrix_page())
        phase_normalized_page, self.inductance_phase_normalized_table = (
            self._create_inductance_matrix_page())
        branch_page, self.inductance_branch_table = (
            self._create_inductance_matrix_page())
        branch_normalized_page, self.inductance_branch_normalized_table = (
            self._create_inductance_matrix_page())
        self._inductance_matrix_pages = (
            phase_page, phase_normalized_page, branch_page,
            branch_normalized_page)
        self._inductance_matrix_tables = (
            self.inductance_phase_table,
            self.inductance_phase_normalized_table,
            self.inductance_branch_table,
            self.inductance_branch_normalized_table,
        )
        self.inductance_matrix_tabs.addTab(phase_page, "Phase matrix (μH)")
        self.inductance_matrix_tabs.addTab(
            phase_normalized_page, "Phase normalized (k)")
        self.inductance_matrix_tabs.addTab(branch_page, "Branch matrix (μH)")
        self.inductance_matrix_tabs.addTab(
            branch_normalized_page, "Branch normalized (k)")
        self.inductance_matrix_window = None
        self._detached_inductance_matrix_index = None
        layout.addWidget(self.inductance_matrix_tabs, 1)
        return tab

    @classmethod
    def _create_inductance_matrix_page(cls):
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        table = cls._create_inductance_matrix_table()
        page_layout.addWidget(table)
        return page, table

    @staticmethod
    def _create_inductance_matrix_table():
        table = QTableWidget(0, 0)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.setAlternatingRowColors(True)
        return table

    def _inductance_branch_labels(self, result):
        local_counts = {}
        labels = []
        for branch_id, phase in zip(result.branch_ids, result.branch_phases):
            local_counts[phase] = local_counts.get(phase, 0) + 1
            labels.append(
                f"{self._phase_label(phase)}-{local_counts[phase]}")
        return labels

    @staticmethod
    def _populate_inductance_matrix(table, matrix, labels, scale=1.0e6):
        display_matrix = np.asarray(matrix, dtype=float) * float(scale)
        size = len(labels)
        table.clear()
        table.setRowCount(size)
        table.setColumnCount(size)
        table.setHorizontalHeaderLabels(labels)
        table.setVerticalHeaderLabels(labels)
        for row in range(size):
            for column in range(size):
                item = QTableWidgetItem(f"{display_matrix[row, column]:.6g}")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, column, item)

    def toggle_inductance_matrix_window(self):
        """Move the selected matrix table between its tab and a window."""
        if (self.inductance_matrix_window is not None
                and self.inductance_matrix_window.isVisible()):
            self.embed_inductance_matrix()
            return
        index = self.inductance_matrix_tabs.currentIndex()
        if index < 0 or self._inductance_matrix_tables[index].rowCount() == 0:
            return
        if self.inductance_matrix_window is None:
            self.inductance_matrix_window = self._detached_plot_window_class(
                self,
                embed_callback=self.embed_inductance_matrix,
                title="Winding Design Tool — Inductance Matrix",
            )
            self.inductance_matrix_window.embed_button.setText("Embed Matrix")
            self.inductance_matrix_window.resize(900, 700)
        table = self._inductance_matrix_tables[index]
        self._inductance_matrix_pages[index].layout().removeWidget(table)
        self.inductance_matrix_window.content_layout.addWidget(table, 1)
        self._detached_inductance_matrix_index = index
        self.inductance_matrix_window.setWindowTitle(
            "Winding Design Tool — " + self.inductance_matrix_tabs.tabText(index))
        self.inductance_matrix_window.setStyleSheet(self.styleSheet())
        self.inductance_matrix_popout_button.setText("Embed Matrix")
        self.inductance_matrix_window.show()
        self.inductance_matrix_window.raise_()

    def embed_inductance_matrix(self):
        """Return a detached inductance matrix to its original tab page."""
        index = self._detached_inductance_matrix_index
        if index is None:
            return
        table = self._inductance_matrix_tables[index]
        if self.inductance_matrix_window is not None:
            self.inductance_matrix_window.content_layout.removeWidget(table)
        self._inductance_matrix_pages[index].layout().addWidget(table)
        table.show()
        if self.inductance_matrix_window is not None:
            self.inductance_matrix_window.hide()
        self._detached_inductance_matrix_index = None
        self.inductance_matrix_popout_button.setText("Pop Out Matrix")
        self.inductance_matrix_popout_button.setEnabled(
            any(item.rowCount() for item in self._inductance_matrix_tables))

    def _clear_inductance_result(self, message=""):
        self.embed_inductance_matrix()
        if hasattr(self, "inductance_gmr_display"):
            self.inductance_gmr_display.setText("—")
        if hasattr(self, "inductance_result"):
            del self.inductance_result
        self._inductance_cache_key = None
        for table in self._inductance_matrix_tables:
            table.clear()
            table.setRowCount(0)
            table.setColumnCount(0)
        self.inductance_matrix_popout_button.setEnabled(False)
        self.inductance_summary.setPlainText(message)

    def _inductance_source_key(self):
        physical_keys = (
            "winding_input_mode", "q", "num_slots", "num_poles", "ab",
            "num_layers", "num_phases", "q_divider", "pp_divider", "p2_divider",
            "stack_length", "SD1", "SD2", "H_yoke", "TH1", "TH2", "ksw",
            "G_cond", "C_side", "C_rad", "d_Ins", "d_coat", "Cond_Radi",
            "Overlap_Ins", "pattern_name", "inlet_from_weld_side", "radial_shift",
            "phase_shift_pattern", "phase_shift", "PSL", "tp_type", "tp_interval",
            "tp_times", "uni_tp", "pltp_fl", "pltp_ll", "jltp", "auto_configure_objective",
            "pole_n_tp_type", "pole_n_tp_interval", "pole_n_tp_times",
            "pole_n_uni_tp", "pole_n_pltp_fl", "pole_n_pltp_ll", "pole_n_jltp",
            "pole_s_tp_type", "pole_s_tp_interval", "pole_s_tp_times",
            "pole_s_uni_tp", "pole_s_pltp_fl", "pole_s_pltp_ll", "pole_s_jltp",
        )
        return (
            tuple((key, self.get_field_value(key)) for key in physical_keys),
            tuple(self.inlet_index_adjustments_phase_a),
            tuple(self.volt_diff_inlet_adjustments_all),
            self.inductance_mu_r_input.text().strip(),
        )

    def _invalidate_inductance_if_stale(self, _value=None):
        if (hasattr(self, "inductance_result")
                and self._inductance_source_key()
                != getattr(self, "_inductance_published_source_key", None)):
            self._clear_inductance_result(
                "Inductance result is stale because inputs changed. "
                "Select Calculate Inductance to update it.")

    def open_inductance_help(self):
        """Open the local illustrated active-length inductance guide."""
        guide_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "inductance_guide.html")
        if not os.path.isfile(guide_path):
            self.message_log.append(
                "Inductance Model Guide is unavailable: inductance_guide.html was not found.")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(guide_path)):
            self.message_log.append(
                "Inductance Model Guide could not be opened by the system browser.")

    def _connect_inductance_invalidation(self):
        connected = set()
        source_keys = {key for key, _value in self._inductance_source_key()[0]}
        source_keys.add("inductance_mu_r")
        for key in source_keys:
            widget = self.input_fields[key]
            if id(widget) in connected:
                continue
            connected.add(id(widget))
            if isinstance(widget, QComboBox):
                widget.currentTextChanged.connect(self._invalidate_inductance_if_stale)
            elif isinstance(widget, QCheckBox):
                widget.toggled.connect(self._invalidate_inductance_if_stale)
            elif isinstance(widget, QLineEdit):
                widget.textChanged.connect(self._invalidate_inductance_if_stale)

    def calculate_inductance(self):
        """Calculate matrices from the authoritative current layout state."""
        try:
            relative_permeability = float(self.inductance_mu_r_input.text())
            if relative_permeability <= 0.0:
                raise ValueError("Relative permeability must be positive.")

            exact_q, _ = self._resolve_slot_inputs()
            candidate = self._is_fractional_pattern_candidate(exact_q)
            if (self.tp_type_field.currentText() == "Auto"
                    and (any(self._safe_int_list(self.inlet_index_adjustments_phase_a))
                         or any(self._safe_int_list(self.volt_diff_inlet_adjustments_all)))):
                self.apply_auto_configuration(preserve_inlet_adjustments=True)
            state = self.extract_parameters(candidate_only=candidate)
            if state is None:
                state = self.calculation_state
            values = state.values
            winding = values["Winding_Para"]
            phase_records = phase_topology.phase_map(
                winding.num_slots,
                winding.num_poles,
                winding.num_layers,
                values["Layout_Para"].phase_shift_list,
                winding.num_phases,
            )
            layer_radii_mm = ewc.calculate_layer_beta_angle(
                values["EW_info"], winding, values["Stator_Para"],
                values["Inslot_Para"])[0]
            cache_key = (state.signature, relative_permeability)
            if (cache_key == getattr(self, "_inductance_cache_key", None)
                    and hasattr(self, "inductance_result")):
                result = self.inductance_result
            else:
                result = ic.calculate_active_inductance(
                    values["cond_info"],
                    phase_records,
                    num_slots=winding.num_slots,
                    layer_radii_mm=layer_radii_mm,
                    active_length_mm=values["Stator_Para"].StackLength,
                    conductor_width_mm=values["Inslot_Para"].Cond_Width,
                    conductor_height_mm=values["Inslot_Para"].Cond_Height,
                    relative_permeability=relative_permeability,
                    expected_branch_count=winding.num_phases * winding.ab,
                    expected_phase_ids=range(winding.num_phases),
                    expected_branches_per_phase=winding.ab,
                )
                self._inductance_cache_key = cache_key

            phase_labels = [self._phase_label(phase) for phase in result.phase_ids]
            branch_labels = self._inductance_branch_labels(result)
            self._populate_inductance_matrix(
                self.inductance_phase_table, result.phase_matrix_h, phase_labels)
            self._populate_inductance_matrix(
                self.inductance_phase_normalized_table,
                result.phase_coupling_matrix,
                phase_labels,
                scale=1.0,
            )
            self._populate_inductance_matrix(
                self.inductance_branch_table, result.branch_matrix_h, branch_labels)
            self._populate_inductance_matrix(
                self.inductance_branch_normalized_table,
                result.branch_coupling_matrix,
                branch_labels,
                scale=1.0,
            )
            self.inductance_result = result
            self._inductance_published_source_key = self._inductance_source_key()
            self.inductance_gmr_display.setText(
                f"{result.conductor_gmr_m * 1000.0:.6g}")
            self.inductance_matrix_popout_button.setEnabled(True)

            phase_self = ", ".join(
                f"{label}={value * 1.0e6:.6g} μH"
                for label, value in zip(phase_labels, np.diag(result.phase_matrix_h)))
            branch_self = np.diag(result.branch_matrix_h) * 1.0e6
            status = ("candidate layout; result is for inspection only"
                      if candidate else "current generated layout")
            self.inductance_summary.setPlainText(
                "Active-length partial inductance\n"
                f"Layout: {status}\n"
                f"Conductors: {result.conductor_count} | Branches: {len(result.branch_ids)} "
                f"| Active length: {result.active_length_m * 1000.0:.6g} mm\n"
                f"μr: {result.relative_permeability:.6g} | Rectangular GMR: "
                f"{result.conductor_gmr_m * 1000.0:.6g} mm\n"
                f"Branch self-L range: {branch_self.min():.6g} to "
                f"{branch_self.max():.6g} μH\n"
                f"Phase self-L — Equal current sharing: {phase_self}\n"
                "Normalized phase and branch matrices: "
                "kij = Mij / sqrt(Lii Ljj); diagonal = 1")
            self.message_log.append(
                "Active-length branch and phase inductance matrices updated.")
        except ValueError as exc:
            self._clear_inductance_result(f"Inductance unavailable: {exc}")
            self.message_log.append(f"Inductance calculation unavailable: {exc}")
        except Exception as exc:
            self._clear_inductance_result(
                "Inductance calculation failed. See System Messages.")
            event_id = self._record_unexpected_error("inductance_calculation", exc)
            self.message_log.append(
                f"Inductance calculation failed. Reference: {event_id}")
