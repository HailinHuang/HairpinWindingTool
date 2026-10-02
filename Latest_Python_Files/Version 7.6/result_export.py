from __future__ import annotations

import os
import zipfile
from datetime import datetime
from xml.sax.saxutils import escape

import cond_info_operation as cio
import get_winding_pattern as gw
from PyQt6.QtWidgets import QFileDialog


class ResultExportMixin:
    def _branch_export_directory(self):
        export_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "branch_connection_exports")
        os.makedirs(export_dir, exist_ok=True)
        return export_dir

    def _default_branch_workbook_path(self):
        try:
            pattern = gw.get_pattern_label(gw.normalize_pattern_name(self.input_fields["pattern_name"].text()))
        except Exception:
            pattern = self.input_fields.get("pattern_name").text() if "pattern_name" in self.input_fields else "Pattern"
        q = self.get_int_field("q", 0)
        poles = self.get_int_field("num_poles", 0)
        layers = self.get_int_field("num_layers", 0)
        phases = self.get_int_field("num_phases", 3)
        naa = self.get_int_field("ab", 0)
        slots = self.get_int_field("num_slots", q * poles * phases if q and poles and phases else 0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = (
            f"Slot{self._safe_filename_part(slots)}_"
            f"Pole{self._safe_filename_part(poles)}_"
            f"Layer{self._safe_filename_part(layers)}_"
            f"Naa{self._safe_filename_part(naa)}_"
            f"{self._safe_filename_part(pattern)}_"
            f"{timestamp}_conn.xlsx"
        )
        return os.path.join(self._branch_export_directory(), filename)

    def _voltage_difference_export_directory(self):
        export_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voltage_difference_exports")
        os.makedirs(export_dir, exist_ok=True)
        return export_dir

    def _default_voltage_difference_workbook_path(self):
        try:
            pattern = gw.get_pattern_label(gw.normalize_pattern_name(self.input_fields["pattern_name"].text()))
        except Exception:
            pattern = self.input_fields.get("pattern_name").text() if "pattern_name" in self.input_fields else "Pattern"
        q = self.get_int_field("q", 0)
        poles = self.get_int_field("num_poles", 0)
        layers = self.get_int_field("num_layers", 0)
        phases = self.get_int_field("num_phases", 3)
        naa = self.get_int_field("ab", 0)
        slots = self.get_int_field("num_slots", q * poles * phases if q and poles and phases else 0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = (
            f"Slot{self._safe_filename_part(slots)}_"
            f"Pole{self._safe_filename_part(poles)}_"
            f"Layer{self._safe_filename_part(layers)}_"
            f"Naa{self._safe_filename_part(naa)}_"
            f"{self._safe_filename_part(pattern)}_"
            f"{timestamp}_vd.xlsx"
        )
        return os.path.join(self._voltage_difference_export_directory(), filename)

    def _default_voltage_difference_svg_path(self):
        try:
            pattern = gw.get_pattern_label(gw.normalize_pattern_name(self.input_fields["pattern_name"].text()))
        except Exception:
            pattern = self.input_fields.get("pattern_name").text() if "pattern_name" in self.input_fields else "Pattern"
        q = self.get_int_field("q", 0)
        poles = self.get_int_field("num_poles", 0)
        layers = self.get_int_field("num_layers", 0)
        phases = self.get_int_field("num_phases", 3)
        naa = self.get_int_field("ab", 0)
        slots = self.get_int_field("num_slots", q * poles * phases if q and poles and phases else 0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = (
            f"Slot{self._safe_filename_part(slots)}_"
            f"Pole{self._safe_filename_part(poles)}_"
            f"Layer{self._safe_filename_part(layers)}_"
            f"Naa{self._safe_filename_part(naa)}_"
            f"{self._safe_filename_part(pattern)}_"
            f"{timestamp}_vd_plot.svg"
        )
        return os.path.join(self._voltage_difference_export_directory(), filename)

    def _clean_sheet_name(self, raw_name, used_names):
        invalid_chars = set('[]:*?/\\')
        name = "".join("_" if ch in invalid_chars else ch for ch in str(raw_name)).strip()
        name = name or "Sheet"
        name = name[:31]
        base = name
        suffix_index = 2
        while name in used_names:
            suffix = f"_{suffix_index}"
            name = f"{base[:31 - len(suffix)]}{suffix}"
            suffix_index += 1
        used_names.add(name)
        return name

    def _excel_col_name(self, index):
        index = int(index)
        name = ""
        while index:
            index, remainder = divmod(index - 1, 26)
            name = chr(ord("A") + remainder) + name
        return name

    def _xml_text(self, value):
        return escape(str(value), {'"': "&quot;", "'": "&apos;"})

    def _worksheet_xml(self, rows):
        row_xml = []
        for row_index, row in enumerate(rows, start=1):
            cells = []
            for col_index, value in enumerate(row, start=1):
                if value in (None, ""):
                    continue
                cell_ref = f"{self._excel_col_name(col_index)}{row_index}"
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    cells.append(f'<c r="{cell_ref}"><v>{value}</v></c>')
                else:
                    cells.append(
                        f'<c r="{cell_ref}" t="inlineStr"><is><t>{self._xml_text(value)}</t></is></c>'
                    )
            row_xml.append(f'<row r="{row_index}">{"".join(cells)}</row>')
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheetViews><sheetView workbookViewId="0"><pane xSplit="1" ySplit="1" '
            'topLeftCell="B2" activePane="bottomRight" state="frozen"/></sheetView></sheetViews>'
            '<sheetFormatPr defaultRowHeight="15"/>'
            '<sheetData>'
            f'{"".join(row_xml)}'
            '</sheetData>'
            '</worksheet>'
        )

    def _write_xlsx_workbook(self, file_path, sheets):
        if not sheets:
            raise ValueError("No sheets to export.")
        overrides = [
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        ]
        workbook_sheets = []
        workbook_rels = []
        for sheet_index, (sheet_name, _rows) in enumerate(sheets, start=1):
            overrides.append(
                f'<Override PartName="/xl/worksheets/sheet{sheet_index}.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            )
            workbook_sheets.append(
                f'<sheet name="{self._xml_text(sheet_name)}" sheetId="{sheet_index}" r:id="rId{sheet_index}"/>'
            )
            workbook_rels.append(
                f'<Relationship Id="rId{sheet_index}" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                f'Target="worksheets/sheet{sheet_index}.xml"/>'
            )

        content_types = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            f'{"".join(overrides)}'
            '</Types>'
        )
        root_rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/>'
            '</Relationships>'
        )
        workbook_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets>'
            f'{"".join(workbook_sheets)}'
            '</sheets>'
            '</workbook>'
        )
        workbook_rels_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'{"".join(workbook_rels)}'
            '</Relationships>'
        )

        with zipfile.ZipFile(file_path, "w", compression=zipfile.ZIP_DEFLATED) as workbook:
            workbook.writestr("[Content_Types].xml", content_types)
            workbook.writestr("_rels/.rels", root_rels)
            workbook.writestr("xl/workbook.xml", workbook_xml)
            workbook.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
            for sheet_index, (_sheet_name, rows) in enumerate(sheets, start=1):
                workbook.writestr(f"xl/worksheets/sheet{sheet_index}.xml", self._worksheet_xml(rows))

    def _build_phase_branch_sheets(self):
        if not hasattr(self, "db_conductor_id") or self.db_conductor_id is None:
            self.extract_parameters()
        sheets = []
        used_names = set()
        phase_counts = {}
        for global_branch_index, branch_info in enumerate(self.db_conductor_id, start=1):
            branch_id, conductors = branch_info
            if not conductors:
                continue
            first_slot, first_layer = conductors[0][:2]
            try:
                phase_index = cio.get_phase_index(first_slot, first_layer, self.cond_info)
            except Exception:
                phase_index = (global_branch_index - 1) // max(1, self.Winding_Para.ab)
            phase_label = self._phase_label(phase_index)
            phase_counts[phase_label] = phase_counts.get(phase_label, 0) + 1
            sheet_name = self._clean_sheet_name(
                f"Phase{phase_label}_Branch{phase_counts[phase_label]}",
                used_names,
            )

            rows = [["Layer \\ Slot"] + [slot + 1 for slot in range(self.Winding_Para.num_slots)]]
            for layer in range(self.Winding_Para.num_layers):
                rows.append([f"L{layer + 1}"] + [""] * self.Winding_Para.num_slots)

            for sequence_index, conductor_id in enumerate(conductors, start=1):
                slot, layer = conductor_id[:2]
                row_index = int(layer) + 1
                col_index = int(slot) + 1
                existing = rows[row_index][col_index]
                rows[row_index][col_index] = sequence_index if existing == "" else f"{existing};{sequence_index}"

            sheets.append((sheet_name, rows))
        return sheets

    def _add_parameter_rows(self, rows, section, keys):
        for key in keys:
            if key in self.input_fields:
                rows.append([section, key, self.get_field_value(key)])

    def _build_layout_parameter_sheet(self):
        rows = [["Section", "Parameter", "Value"]]
        try:
            pattern = gw.get_pattern_label(gw.normalize_pattern_name(self.input_fields["pattern_name"].text()))
        except Exception:
            pattern = self.input_fields["pattern_name"].text() if "pattern_name" in self.input_fields else ""

        rows.extend([
            ["Export", "exported_at", datetime.now().isoformat(timespec="seconds")],
            ["Export", "app_version", "7.6"],
            ["Pattern", "pattern", pattern],
        ])

        self._add_parameter_rows(rows, "Winding", [
            "q", "num_poles", "num_layers", "num_phases", "ab", "num_slots", "curesistivity",
        ])
        self._add_parameter_rows(rows, "Layout", [
            "pattern_name", "inlet_from_weld_side", "radial_shift", "CW", "in_out_connection",
        ])
        rows.append([
            "Inlet Position",
            "phase_a_index_adjustments",
            ", ".join(str(value) for value in getattr(self, "inlet_index_adjustments_phase_a", [])),
        ])
        self._add_parameter_rows(rows, "Phase Shift", [
            "phase_shift_pattern", "phase_shift", "PSL",
        ])
        self._add_parameter_rows(rows, "Transposition", [
            "tp_type", "tp_interval", "tp_times", "uni_tp", "pltp_fl", "pltp_ll", "jltp",
        ])
        for name, prefix in (("PoleN Transposition", "pole_n"),
                             ("PoleS Transposition", "pole_s")):
            self._add_parameter_rows(rows, name, [
                f"{prefix}_{suffix}" for suffix in
                ("tp_type", "tp_interval", "tp_times", "uni_tp", "pltp_fl", "pltp_ll", "jltp")
            ])
        self._add_parameter_rows(rows, "Figure Layout", [
            "Single_Phase_Draw", "grid_color_pattern", "fig_branch_line_color", "linewidth",
            "line_alpha", "draw_arrow", "arrow_size", "radii_gap", "line_single_side", "same_layer_route_style", "inline_angle",
            "outline_angle", "inlet_line_length", "slotindex_fontsize_custom",
            "slotindex_offset", "slotindex_rotation", "wedge_circle", "plot_inner_radius",
            "plot_layer_height_scale", "plot_margin", "plot_zoom", "plot_padding",
            "legend_position", "legend_fontsize", "grid_alpha",
        ])

        if hasattr(self, "Winding_Para"):
            rows.extend([
                ["Derived Winding", "num_slots", self.Winding_Para.num_slots],
                ["Derived Winding", "conductors_per_phase_branch",
                 self.Winding_Para.num_poles * self.Winding_Para.num_layers * self.Winding_Para.q / self.Winding_Para.ab],
            ])
        if hasattr(self, "Layout_Para"):
            phase_shift_list = getattr(self.Layout_Para, "phase_shift_list", None)
            if phase_shift_list is not None:
                rows.append(["Derived Layout", "phase_shift_list", ", ".join(str(v) for v in phase_shift_list)])

        return ("Parameters", rows)

    def _build_voltage_difference_workbook_sheets(self):
        self._sync_vd_adjustments_from_inputs()
        self.extract_parameters()
        voltage_drop = self._voltage_drop_input()
        index_span = self._voltage_index_span_input(self.cond_info)
        voltage_matrix, index_matrix, max_voltage, max_index = self._compute_voltage_difference_matrix(
            self.cond_info,
            voltage_drop,
            index_span,
        )
        all_adjustments = self._current_all_branch_adjustments()
        matrix_result = getattr(self, "_vd_last_matrix_result", None)
        cross_phase_pairs = getattr(matrix_result, "cross_phase_pair_count", 0)
        total_pairs = getattr(matrix_result, "pair_count", 0)

        summary_rows = [
            ["Metric", "Value"],
            ["exported_at", datetime.now().isoformat(timespec="seconds")],
            ["voltage_drop_DC", voltage_drop],
            ["index_difference", index_span],
            ["max_voltage_difference_DC", max_voltage],
            ["max_equivalent_index_difference", max_index],
            ["phase_aware_voltage", "on"],
            ["cross_phase_adjacent_pairs", cross_phase_pairs],
            ["adjacent_layer_pair_count", total_pairs],
            ["all_branch_index_adj", ", ".join(str(value) for value in all_adjustments)],
            [
                "phase_a_index_adj",
                ", ".join(str(value) for value in getattr(self, "inlet_index_adjustments_phase_a", [])),
            ],
        ]

        slot_headers = [slot + 1 for slot in range(self.Winding_Para.num_slots)]
        voltage_rows = [["InterLayer \\ Slot"] + slot_headers]
        index_rows = [["InterLayer \\ Slot"] + slot_headers]
        for row_index, row in enumerate(voltage_matrix):
            row_label = f"L{row_index + 1}L{row_index + 2}"
            voltage_rows.append([row_label] + [round(float(value), 6) for value in row])
        for row_index, row in enumerate(index_matrix):
            row_label = f"L{row_index + 1}L{row_index + 2}"
            index_rows.append([row_label] + [round(float(value), 6) for value in row])

        return [
            ("Summary", summary_rows),
            ("VoltageDiff", voltage_rows),
            ("IndexDiff", index_rows),
        ]

    def export_voltage_difference_xlsx(self):
        try:
            self.extract_parameters()
            default_path = self._default_voltage_difference_workbook_path()
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Voltage Difference Plot",
                default_path,
                "Excel Workbook (*.xlsx);;All Files (*)",
            )
            if not file_path:
                return
            if not os.path.splitext(file_path)[1]:
                file_path += ".xlsx"
            if os.path.splitext(file_path)[1].lower() != ".xlsx":
                file_path += ".xlsx"
            sheets = self._build_voltage_difference_workbook_sheets()
            self._write_xlsx_workbook(file_path, sheets)
            self.update_voltage_difference_view()
            message = f"Voltage difference workbook exported: {file_path}"
            self.message_log.append(message)
            if hasattr(self, "vd_result_display"):
                self.vd_result_display.append(f"\n{message}")
        except Exception as exc:
            event_id = self._record_unexpected_error("volt_diff_xlsx_export", exc)
            if hasattr(self, "vd_result_display"):
                self.vd_result_display.setText(f"Voltage difference export failed: {exc}\nReference: {event_id}")
            self.message_log.append(f"Voltage difference export failed: {exc} [Reference: {event_id}]")

    def export_voltage_difference_svg(self):
        try:
            self.extract_parameters()
            file_path = self._default_voltage_difference_svg_path()
            self.update_voltage_difference_view()
            self.vd_figure.savefig(file_path, format="svg", bbox_inches="tight")
            message = f"Voltage difference SVG exported: {file_path}"
            self.message_log.append(message)
            if hasattr(self, "vd_result_display"):
                self.vd_result_display.append(f"\n{message}")
        except Exception as exc:
            event_id = self._record_unexpected_error("volt_diff_svg_export", exc)
            if hasattr(self, "vd_result_display"):
                self.vd_result_display.setText(f"Voltage difference SVG export failed: {exc}\nReference: {event_id}")
            self.message_log.append(f"Voltage difference SVG export failed: {exc} [Reference: {event_id}]")

    def export_branch_connection_sheets(self):
        try:
            self.extract_parameters()
            default_path = self._default_branch_workbook_path()
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Phase-Branch Connection Sheets",
                default_path,
                "Excel Workbook (*.xlsx);;All Files (*)",
            )
            if not file_path:
                return
            if not os.path.splitext(file_path)[1]:
                file_path += ".xlsx"
            if os.path.splitext(file_path)[1].lower() != ".xlsx":
                file_path += ".xlsx"
            sheets = [self._build_layout_parameter_sheet()] + self._build_phase_branch_sheets()
            self._write_xlsx_workbook(file_path, sheets)
            self.message_log.append(f"Phase-branch connection workbook exported: {file_path}")
        except Exception as exc:
            event_id = self._record_unexpected_error("branch_workbook_export", exc)
            self.message_log.append(f"Phase-branch connection export failed: {exc} [Reference: {event_id}]")
