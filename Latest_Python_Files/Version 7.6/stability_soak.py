"""Non-rendering stability soak for calculation/state publication."""

from __future__ import annotations

import argparse
import gc
import json
import os
from pathlib import Path
import statistics
import time
import tracemalloc


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).with_name(".matplotlib")))

from PyQt6.QtCore import QThread  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402
from main_pyqt6 import WindingApp  # noqa: E402


def run_soak(cycles=100):
    cycles = max(1, int(cycles))
    app = QApplication.instance() or QApplication([])
    window = WindingApp()
    window.input_fields["winding_input_mode"].setCurrentText("Slots and poles")
    window.input_fields["num_slots"].setText("48")
    window.input_fields["ab"].setText("2")
    window.input_fields["pattern_name"].setText("BWP")
    window._resolve_slot_inputs()
    window.extract_parameters()

    tracemalloc.start()
    gc.collect()
    memory_before = tracemalloc.get_traced_memory()[0]
    durations = []
    failures = []
    published_generations = []

    for index in range(cycles):
        expected_layers = 8 if index % 2 else 6
        window.input_fields["num_layers"].setText(str(expected_layers))
        started = time.perf_counter()
        try:
            window.analyze_layouts()
            app.processEvents()
            if window.Winding_Para.num_layers != expected_layers:
                raise AssertionError(
                    f"published {window.Winding_Para.num_layers} layers; expected {expected_layers}")
            if window.calculation_state.values["results"] is not window.results:
                raise AssertionError("published results do not match the compatibility interface")
            published_generations.append(window.calculation_state.generation)
        except Exception as exc:
            failures.append({"cycle": index, "type": type(exc).__name__, "message": str(exc)})
        durations.append(time.perf_counter() - started)

    gc.collect()
    memory_after, memory_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    active_threads_before_close = sum(thread.isRunning() for thread in window.findChildren(QThread))
    window.close()
    app.processEvents()
    active_threads_after_close = sum(thread.isRunning() for thread in window.findChildren(QThread))
    sorted_durations = sorted(durations)
    p95_index = max(0, min(len(sorted_durations) - 1, int(len(sorted_durations) * 0.95) - 1))

    return {
        "cycles": cycles,
        "failures": failures,
        "unique_published_states": len(set(published_generations)),
        "median_seconds": statistics.median(durations),
        "p95_seconds": sorted_durations[p95_index],
        "max_seconds": max(durations),
        "python_memory_before_mib": memory_before / (1024 * 1024),
        "python_memory_after_mib": memory_after / (1024 * 1024),
        "python_memory_growth_mib": (memory_after - memory_before) / (1024 * 1024),
        "python_memory_peak_mib": memory_peak / (1024 * 1024),
        "active_threads_before_close": active_threads_before_close,
        "active_threads_after_close": active_threads_after_close,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int, default=100)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_soak(args.cycles)
    text = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    raise SystemExit(1 if result["failures"] or result["active_threads_after_close"] else 0)


if __name__ == "__main__":
    main()
