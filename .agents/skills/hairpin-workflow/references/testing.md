# Focused verification

## Commands

From the workspace root, select V7.6. The interpreter is two levels above it:

```powershell
Set-Location 'Latest_Python_Files/Version 7.6'
$env:QT_QPA_PLATFORM = 'offscreen'
$env:MPLCONFIGDIR = Join-Path (Get-Location) '.matplotlib'
& '..\..\.venv\Scripts\python.exe' -X utf8 -m unittest test_vd_neighbour_summary -v
```

Replace the module with the appropriate dotted test below. Other platforms need a compatible interpreter (usually `.venv/bin/python`) and their shell's environment syntax; Windows launch/build scripts are not portable. Claim support only for environments actually tested.

## Select by impact

| Impact | Existing starting point | Extra evidence |
| --- | --- | --- |
| Button sizes | `test_plot_docking.PlotDockingTests.test_actions_are_uniform_and_toggle_stays_in_bottom_area` | Affected-state screenshot. |
| Parameter columns | `test_plot_docking.PlotDockingTests.test_parameter_tabs_use_shared_compact_two_column_geometry` | Affected tab/window sizes. |
| Docking/zoom | Relevant `test_plot_docking` and `test_workbench` methods | Interaction, canvas/data preservation. |
| Same-layer drawing | `test_draw_figure_same_layer_routes`, `test_main_pyqt6_same_layer_route_ui` | Rendered geometry; assess electrical impact. |
| Config/export | Relevant `test_classic_regression` methods | Roundtrip or actual export content. |
| Neighbour voltage | `test_vd_neighbour_summary` | Independent values, ring wraparound, both diagonals. |
| UI/model boundary | `test_workbench` | Preview isolation, stale clearing, visual-only CW. |
| Topology/connections | `test_phase_topology`, `test_explicit_connections`, `test_classic_regression` | Independent electrical oracle, rejection cases, integer-q compatibility. |
| Source import/documentation | Included paths, changed instructions/links, final staged delta; reuse valid unchanged-source evidence | Record clean-install, native/package and broader validation limits. |
| Package/release | Affected regression; full discovery only for broad impact, broader failures or an explicit request | Build, launch artifact, config import/export, layout and VD flows as applicable. |

Read relevant tests before relying on them. This map is not evidence they currently pass; mixed test files need not run in full for a static change.

Full discovery only for broad impact, broader failures or an explicit request, from V7.6:

```powershell
& '..\..\.venv\Scripts\python.exe' -X utf8 -m unittest discover -s . -p 'test_*.py' -v
```

Capture affected UI states. Responsive/global geometry changes cover 1366x768 and 1920x1080 and relevant scaling (100%, 125%, 150%). Use a fresh process per `QT_SCALE_FACTOR`. Offscreen captures do not establish native Windows DPI acceptance.

`validate_workbench.py` imports a fixed historical backup and asserts baseline equality. Inspect compatibility before reuse; do not mandate it for every current UI change. For a local fix, capture the current application and affected state directly.

Before a native application or packaged-executable launch, restore the original `QT_QPA_PLATFORM` and `QT_SCALE_FACTOR` environment values (remove them if originally unset), or use a fresh shell without the test overrides. Do not count an offscreen launch as native artifact acceptance.

Documentation checks cover links, paths/commands, skill metadata and routing cases. Do not run a full business suite merely to edit prose.
