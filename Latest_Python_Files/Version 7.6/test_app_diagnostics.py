"""Structured diagnostic logging and UI failure-reference checks."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication

from app_diagnostics import DiagnosticLog
from main_pyqt6 import WindingApp


class DiagnosticLogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_exception_record_contains_context_type_message_and_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "errors.jsonl"
            log = DiagnosticLog(path)
            try:
                raise RuntimeError("injected diagnostic failure")
            except RuntimeError as exc:
                event_id = log.record_exception("layout_analysis", exc, {"view": "winding"})

            record = json.loads(path.read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual(record["event_id"], event_id)
            self.assertEqual(record["context"], "layout_analysis")
            self.assertEqual(record["category"], "internal")
            self.assertEqual(record["exception_type"], "RuntimeError")
            self.assertEqual(record["message"], "injected diagnostic failure")
            self.assertEqual(record["metadata"], {"view": "winding"})
            self.assertIn("raise RuntimeError", record["traceback"])

    def test_ui_callback_reports_the_same_event_id_written_to_disk(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "errors.jsonl"
            window = WindingApp()
            window.diagnostic_log = DiagnosticLog(path)
            with patch.object(window, "extract_parameters", side_effect=RuntimeError("injected callback failure")):
                window.analyze_layouts()

            record = json.loads(path.read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual(record["context"], "layout_analysis")
            self.assertIn(record["event_id"], window.layout_display.toPlainText())
            self.assertIn(record["event_id"], window.message_log.toPlainText())
            window.close()

    def test_log_rotation_keeps_bounded_history(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "errors.jsonl"
            log = DiagnosticLog(path, max_bytes=1024, backup_count=2)
            for index in range(30):
                try:
                    raise RuntimeError(f"failure {index} " + "x" * 120)
                except RuntimeError as exc:
                    log.record_exception("rotation_test", exc)

            self.assertTrue(path.is_file())
            self.assertTrue(Path(str(path) + ".1").is_file())
            self.assertFalse(Path(str(path) + ".3").exists())


if __name__ == "__main__":
    unittest.main()
