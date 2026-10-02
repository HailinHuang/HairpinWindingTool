# HairpinWindingTool — Version 7.6

HairpinWindingTool is a Python/PyQt6 desktop application for constructing,
inspecting, and analyzing electric-machine hairpin winding layouts. Version 7.6
is the active development version. Its source, tests, inputs, and required help
resources retain their existing directory layout.

The application provides Pattern/divider selection, phase and branch views,
transposition controls, winding-function and voltage-difference analysis,
inductance calculations, and configuration/data export. The separate Pattern
Rule Workbench supports exploratory connections and schema-v3 draft packages.
Manual completion does not certify a production route.

Read [current status](docs/STATUS.md), [engineering decisions](docs/DECISIONS.md),
and [validation scope](docs/VALIDATION.md). GitHub
[Issues](https://github.com/HailinHuang/HairpinWindingTool/issues) are the task backlog.
Source and tests determine executable support.

## Run on Windows

The observed working environment uses 64-bit Python 3.11.15. Requirements pin
runtime versions observed in that environment; this is not a complete dependency
lock or a claim of cross-platform acceptance.

From the repository root:

```powershell
python -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
& '.\Latest_Python_Files\Version 7.6\run_main.bat'
```

For a small example, import
`Latest_Python_Files/Version 7.6/configs/config_20260703_104422_Slot48_Pole8_Layer6_Naa2.json`
and use Plot/Analyze. The focused checks below verify the included inputs and
configuration serialization. MATLAB is optional. External CAD/solver integration
needs its own installation and is outside the verified setup.

The Workbench launcher is `Latest_Python_Files/Version 7.6/run_pattern_rule_workbench.bat`.

## Source map

All application modules and tests are in `Latest_Python_Files/Version 7.6/`.

| Responsibility | Files |
| --- | --- |
| Desktop UI/config/export | `main_pyqt6.py`, `config_io.py`, `result_export.py`, `inductance_ui.py` |
| Admission/construction | `get_winding_pattern.py`, `pattern_route_contract.py`, divider formula modules |
| Topology/validation | `phase_topology.py`, `pattern_identity.py`, `explicit_connections.py` |
| Drawing/analysis | `draw_figure.py`, `layout_analysis.py`, calculation modules |
| Exploratory rules | `pattern_rule_workbench.py`, `manual_layout.py` |
| Inputs/regression | `configs/`, `assets/`, `test_*.py`, selected JSON fixtures |

Tests remain beside their modules. Selected JSON files in `pattern_rule_drafts/`
and one `workbench_preview/` subdirectory are inputs/reference oracles for existing
tests. Their original locations preserve those contracts; other drafts/previews
are excluded.

## Small useful validation

```powershell
Set-Location 'Latest_Python_Files/Version 7.6'
$env:QT_QPA_PLATFORM = 'offscreen'
& '..\..\.venv\Scripts\python.exe' -X utf8 -m unittest test_classic_regression.ClassicBusinessRegressionTests.test_copied_config_examples_import test_classic_regression.ClassicBusinessRegressionTests.test_fractional_config_file_roundtrip_preserves_slots -v
```

[VALIDATION.md](docs/VALIDATION.md) lists route, topology, fixture, and Workbench
checks. Offscreen tests do not establish native Windows DPI or packaged acceptance.
Build instructions are in
[the application guide](Latest_Python_Files/Version%207.6/MAIN_PYQT6_GUIDE.md).

Saved finite divider-status resources have stale source provenance. Treat their
counts/examples as historical until refreshed. Candidate, unsupported, retained
asymmetric, and successful public generation remain distinct statuses.
This source import does not claim complete engineering regression, a current
packaged release, manufacturing validation, or a fresh dependency installation.
