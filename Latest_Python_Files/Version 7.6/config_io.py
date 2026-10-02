from __future__ import annotations

import json
import math
import os
from datetime import datetime
from fractions import Fraction

import automatic_transposition as auto_tp
import get_winding_pattern as gw
from PyQt6.QtWidgets import QCheckBox, QComboBox, QFileDialog, QLineEdit


class ConfigIOMixin:
    def _config_directory(self):
        config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "configs")
        os.makedirs(config_dir, exist_ok=True)
        return config_dir

    def _default_config_path(self):
        q = self.get_int_field("q", 0)
        poles = self.get_int_field("num_poles", 0)
        layers = self.get_int_field("num_layers", 0)
        phases = self.get_int_field("num_phases", 3)
        naa = self.get_int_field("ab", 0)
        slots = self.get_int_field("num_slots", q * poles * phases if q and poles and phases else 0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = (
            f"config_{timestamp}_"
            f"Slot{self._safe_filename_part(slots)}_"
            f"Pole{self._safe_filename_part(poles)}_"
            f"Layer{self._safe_filename_part(layers)}_"
            f"Naa{self._safe_filename_part(naa)}.json"
        )
        return os.path.join(self._config_directory(), filename)

    def _build_config_payload(self):
        self._sync_vd_adjustments_from_inputs()
        inputs = {}
        widget_types = {}
        for key in sorted(self.input_fields):
            widget = self.input_fields[key]
            if isinstance(widget, QComboBox):
                inputs[key] = (widget.currentData() if key == "auto_configure_objective"
                               else widget.currentText())
                widget_types[key] = "combo"
            elif isinstance(widget, QCheckBox):
                inputs[key] = 1 if widget.isChecked() else 0
                widget_types[key] = "checkbox"
            elif isinstance(widget, QLineEdit):
                inputs[key] = widget.text()
                widget_types[key] = "line_edit"
        try:
            branch_count = self.get_int_field("ab", len(getattr(self, "inlet_index_adjustments_phase_a", [])))
            pattern_id = gw.normalize_pattern_name(self.input_fields["pattern_name"].text())
            inlet_adjustments = self._coerce_phase_a_adjustments(branch_count, pattern_id, strict=False)
        except Exception:
            inlet_adjustments = list(getattr(self, "inlet_index_adjustments_phase_a", []))
        return {
            "format": "WindingDesignToolConfig",
            "app_version": "7.6",
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "inputs": inputs,
            "widget_types": widget_types,
            "inlet_index_adjustments_phase_a": list(inlet_adjustments),
            "volt_diff_inlet_adjustments_all": list(getattr(self, "volt_diff_inlet_adjustments_all", [])),
        }

    def _apply_config_payload(self, payload):
        # Import owns its TP values. Intermediate divider signals must not
        # restore a previous route's settings over the imported configuration.
        self._loading_balance_config = True
        try:
            result = self._apply_config_payload_inputs(payload)
        finally:
            self._loading_balance_config = False
        self._refresh_divider_status()
        if (self.input_fields["tp_type"].currentText() == "Auto"
                and getattr(self, "_uwp_balance_key", None) is None):
            self.update_transp_type("Auto")
        self._invalidate_inductance_if_stale()
        return result

    def _apply_config_payload_inputs(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("Config file must contain a JSON object.")
        inputs = payload.get("inputs", payload)
        if not isinstance(inputs, dict):
            raise ValueError("Config file does not contain an inputs object.")
        inputs = dict(inputs)
        objective = inputs.get("auto_configure_objective",
                               auto_tp.DEFAULT_AUTO_CONFIGURE_OBJECTIVE)
        if objective not in auto_tp.AUTO_CONFIGURE_OBJECTIVES:
            raise ValueError(f"Unknown Auto Configure strategy: {objective}")
        inputs["auto_configure_objective"] = objective
        for key, default in (("inductance_mu_r", "1.0"),):
            if key not in inputs and key in self.input_fields:
                self.input_fields[key].setText(default)
        if "tp_type" in inputs:
            inputs["tp_type"] = auto_tp.normalize_tp_type(inputs["tp_type"])
        divider_keys = ("q_divider", "pp_divider", "p2_divider")
        if any(key in inputs for key in divider_keys):
            if not all(key in inputs for key in divider_keys):
                raise ValueError("Config must contain all three divider fields.")
            product = math.prod(Fraction(str(inputs[key])) for key in divider_keys)
            if product != int(inputs.get("ab", self.input_fields["ab"].text())):
                raise ValueError("Config divider product must equal Naa.")
        if getattr(self, '_uwp_balance_key', None) is not None:
            kind, values = self._uwp_previous_tp
            kind = auto_tp.normalize_tp_type(kind)
            self.update_transp_type(kind)
            for name, value in values.items():
                self.tp_fields[name].setText(str(value))
        self._uwp_balance_key = None
        for prefix in ("pole_n", "pole_s"):
            type_key = f"{prefix}_tp_type"
            if type_key not in inputs:
                self.input_fields[type_key].setCurrentText("Regular")
            for suffix in ("tp_interval", "tp_times", "uni_tp", "pltp_fl",
                           "pltp_ll", "jltp"):
                key = f"{prefix}_{suffix}"
                if key not in inputs:
                    self.input_fields[key].setText("0")
        if "winding_input_mode" not in inputs:
            self.input_fields["winding_input_mode"].setCurrentText("q and poles")

        # Old configs predate per-pole settings. Clear values from any previous
        # session before applying them so an import cannot inherit stale choices.
        for prefix in ("pole_n", "pole_s"):
            for suffix in ("tp_type", "tp_interval", "tp_times", "uni_tp",
                           "pltp_fl", "pltp_ll", "jltp"):
                key = f"{prefix}_{suffix}"
                if key not in inputs:
                    widget = self.input_fields[key]
                    if isinstance(widget, QComboBox):
                        widget.setCurrentText("Regular")
                    else:
                        widget.setText("0")

        applied = 0
        skipped = 0
        for key, value in inputs.items():
            if key in divider_keys:
                applied += 1
                continue
            widget = self.input_fields.get(key)
            if widget is None:
                skipped += 1
                continue
            if isinstance(widget, QComboBox):
                if key == "auto_configure_objective":
                    widget.setCurrentIndex(widget.findData(value))
                    applied += 1
                    continue
                value_text = str(value)
                if widget.findText(value_text) < 0:
                    widget.addItem(value_text)
                # Resolve slot/q values only after every imported field is present.
                if key == "winding_input_mode":
                    widget.blockSignals(True)
                widget.setCurrentText(value_text)
                if key == "winding_input_mode":
                    widget.blockSignals(False)
            elif isinstance(widget, QCheckBox):
                widget.setChecked(str(value).strip().lower() in ("1", "true", "yes", "on"))
            elif isinstance(widget, QLineEdit):
                widget.setText(str(value))
            else:
                skipped += 1
                continue
            applied += 1

        if "inlet_index_adjustments_phase_a" in payload:
            self.inlet_index_adjustments_phase_a = self._safe_int_list(payload.get("inlet_index_adjustments_phase_a"))
        if "volt_diff_inlet_adjustments_all" in payload:
            self.volt_diff_inlet_adjustments_all = self._safe_int_list(payload.get("volt_diff_inlet_adjustments_all"))
        else:
            self.volt_diff_inlet_adjustments_all = []

        from_slots = self.input_fields["winding_input_mode"].currentText() == "Slots and poles"
        self.input_fields["q"].setReadOnly(from_slots)
        self.input_fields["num_slots"].setReadOnly(not from_slots)
        for key in ("q", "num_slots"):
            field = self.input_fields[key]
            field.style().unpolish(field)
            field.style().polish(field)
        self._resolve_slot_inputs()
        self._sync_dividers_from_inputs()
        if all(key in inputs for key in divider_keys):
            for key in divider_keys:
                box = self.input_fields[key]
                value = str(inputs[key])
                if box.findText(value) < 0:
                    raise ValueError(f"Config {key} is not a valid divider for the imported q and poles.")
                box.blockSignals(True)
                box.setCurrentText(value)
                box.blockSignals(False)
            self._divider_user_selected = True
        self._refresh_divider_status()
        self._refresh_weld_inlet_availability()
        self._refresh_route_option_availability()

        ui_setting_keys = {
            "ui_theme",
            "ui_font_size",
            "ui_button_height",
            "window_width",
            "window_height",
            "left_panel_width",
            "bottom_panel_height",
        }
        if any(key in inputs and key in self.input_fields for key in ui_setting_keys):
            try:
                self.apply_settings(silent=True)
            except Exception:
                pass

        try:
            self.update_transp_range()
            self._refresh_fractional_uwp_transposition_options(self._pattern_base_inputs())
        except Exception:
            pass

        try:
            self.refresh_vd_optimization_estimate()
        except Exception:
            pass

        return applied, skipped

    def export_config(self):
        default_path = self._default_config_path()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Config",
            default_path,
            "JSON Config (*.json);;Text Files (*.txt);;All Files (*)",
        )
        if not file_path:
            return
        if not os.path.splitext(file_path)[1]:
            file_path += ".json"
        try:
            payload = self._build_config_payload()
            with open(file_path, "w", encoding="utf-8") as config_file:
                json.dump(payload, config_file, indent=2, ensure_ascii=True)
            self.message_log.append(f"Config exported: {file_path}")
        except OSError as exc:
            event_id = self._record_unexpected_error("config_export", exc)
            self.message_log.append(f"Config export failed: {exc} [Reference: {event_id}]")

    def import_config(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Config",
            self._config_directory(),
            "Config Files (*.json *.txt);;All Files (*)",
        )
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as config_file:
                payload = json.load(config_file)
            applied, skipped = self._apply_config_payload(payload)
            self.message_log.append(
                f"Config imported: {file_path} ({applied} fields applied, {skipped} skipped)."
            )
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            event_id = self._record_unexpected_error("config_import", exc)
            self.message_log.append(f"Config import failed: {exc} [Reference: {event_id}]")
