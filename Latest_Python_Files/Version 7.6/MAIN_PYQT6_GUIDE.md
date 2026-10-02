# Version 7.6 Main Application Guide

Version 7.6 shares one route decision across the core, main window, and
Workbench. Current project state and validation scope are maintained in
`docs/STATUS.md` and `docs/VALIDATION.md` at the repository root. Historical
research remains local; the initial source import does not certify new routes.

## Purpose
`main_pyqt6.py` is the PyQt6 desktop entry point for the Winding Design Tool. Its `WindingApp` window collects winding, stator, layout, transposition, and figure parameters; generates and analyzes layouts; and exports data and plots.

## Launch
Use `run_main.bat` from this folder. It selects the project virtual environment and writes Matplotlib cache files under `.matplotlib`.

```powershell
Set-Location 'Latest_Python_Files/Version 7.6'
$env:MPLCONFIGDIR = "$PWD\.matplotlib"
& '..\..\.venv\Scripts\python.exe' -X utf8 .\main_pyqt6.py
```

Install the root `requirements.txt` into the root `.venv`. Runtime imports
require PyQt6, NumPy, Matplotlib, pandas, and SciPy. MATLAB is optional; the
program checks for `matlab.engine` when it starts. Packaging additionally
requires PyInstaller.

### Standalone Pattern Rule Workbench

`pattern_rule_workbench.py` is a separate development sketchpad; it does not
change the main app's Pattern dispatch or saved configuration. On Windows,
double-click `run_pattern_rule_workbench.bat`. Alternatively, launch it from
this folder with the project virtual environment:

```powershell
& '..\..\.venv\Scripts\python.exe' -X utf8 .\pattern_rule_workbench.py
```

The opening **Divider Route Catalog** accepts exact `q`, pole pairs, and layer
count. It derives slots and lists the current BWP/UWP/SSP/SLP/ZLP/CP/ZPP/TSP/
TLP/LPP default and alternative `(q-divider, pp-divider, P2)` routes for every feasible Naa.
For integer q, q-divider must divide q, pp-divider must be any factor of the pole-pair
count, P2-divider is 1 or 2, and Naa is their product. The catalog also lists
the positive-half-integer UWP candidate family
`(q-divider,pp-divider,P2)=(q,pp-divider,2)`, with
`Naa=2*q*pp-divider`; the same fractional tuples remain visible as Unsupported for
Patterns without an admitted construction. The **Formulas & Support** tab and
`PATTERN_DIVIDER_FORMULA_SUPPORT.md` summarize the common formulas, Pattern
matrix, status meanings, and validation boundary.
The formulas page also lists all factor-composition types: no divider,
q-divider only, pp-divider only, P2 only, mixed q+pp-divider, mixed q+P2,
mixed pp-divider+P2, and mixed q+pp-divider+P2. These labels describe the
factorization of Naa; they do not by themselves grant Pattern support.
The table calls the shared production resolver rather than maintaining a second
support matrix. It keeps `supported`, `Candidate`, `rejected`, and
`unsupported-yet` separate; only a supported route that passes public generation
appears as **Default** or **Validated**. Hover a row for its reason. Double-click
a row or use **Open** to inspect it. Candidate, rejected, and unsupported routes
open exploratory drafts without claiming a validated path.

The saved [Naa-division status page](pattern_naa_division_layout.html) describes
six stated integer-slot geometries. Its source signature is stale against
current code, so its saved counts and examples remain historical until a
source-bound refresh. This finite scan is not a universal support matrix.

Set slots, poles, even layers, Naa, Pattern draft type, phase, and a first conductor, then select
**New Draft / Reset**. **Add One Step** shows the next ordinary target from the
currently selected Pattern's ordered reference route, including relative layer
shifts. **Advance to Special** follows that Pattern route until its own explicit
special transition or the branch's conductor quota is reached. BWP/SSP/SLP/ZLP
pause before same-layer returns, TSP/TLP before top-bottom returns, and UWP
before jumpers. CP/ZPP/LPP keep following their repeating body topology. If a
non-wave Pattern has no supported reference route, it does not fall back to a
generic wave construction.
For a jumper, turnaround, first/last-layer edge, or another proposed edge,
enter its target and a note, then choose **Add Special Edge**. The direction
control can be changed before subsequent ordinary steps. **Undo Step** removes
the last edge. The plot and connection log update after each step.

Smart next-step candidates are extracted from the selected divider route when
available, otherwise from a supported default layout for
the same Pattern and dimensions. They reuse observed connection side, layer
change, direction, polarity, and signed-pitch categories; no second Pattern
generator is embedded in the workbench. If no reference layout can be built,
explicit special connections remain available and the reason is preserved.

**Export Rule Package** saves the currently visible draft and its explicit
ordered path, edge side, signed pitch, special-edge type, phase-map inputs,
designer notes, source route, extracted reference constraints, and completion
checks as schema-v3 JSON plus PNG and Markdown. Schema-v2 fields remain present.
After all Naa branches reach their quotas, **Copy Codex Prompt** copies a bounded
development handoff that prohibits numeric hard-coding and requires independent
coverage, phase, direction, edge, and complex-EMF validation. The export is
marked exploratory and never installs a
layout in the main app. It checks conductor uniqueness and phase membership
within the sketched branch, but it does not establish a full multi-branch
winding, electrical balance, mechanical clearance, or production validity.
Edits to the grid, Naa, phase, shifts, or start require **New Draft / Reset**;
export is disabled until those inputs are applied.

**Save Manual Configure** creates a timestamped, descriptive JSON/PNG/Markdown
checkpoint under `pattern_rule_drafts/`. Its name includes Pattern, q, pp,
layers, Naa, the three divider values, phase, first side, and shifts. Saving never changes production
dispatch. The matching catalog row immediately shows **Manual configured** in
Status only for a complete unique Naa layout; partial checkpoints show
**Manual draft saved**. Saving an untouched generated path shows **Production
checkpoint saved**, not a manual-configuration claim. The newest checkpoint is
restored on the next launch. Opening any route prefers its latest saved paths;
for Default/Validated routes, **Reload Production Path** restores the generator
result for comparison. Once a saved route is production-admitted, the catalog
shows **Default** or **Validated** as its status and keeps the saved checkpoint
path in the tooltip. Use saved exploratory files as inputs to a separate Codex
rule implementation task.

The editor follows the main layout convention: weld-side connections are
dashed and insert-side connections are solid. The left control pane has a
bounded compact width while the plot consumes remaining space. Help, manual
save, package export, and Codex-copy actions are icon buttons at the plot's
upper right. **Detach Plot** moves the same live canvas into a 1200×800 window;
**Embed Plot** returns it without recalculation or path loss.

Each catalog Status cell includes an editable route-note field. User edits are
appended immediately to `pattern_rule_drafts/route_notes.jsonl` with timestamp,
Pattern, q, pp, layers, Naa, divider tuple, route name, status, and note text.
The last note for each exact route is restored on launch and copied into
schema-v3 exports as `route_note`. The log intentionally preserves earlier
edits so a later Codex rule task can audit decisions such as
`rejected: q2=2 is not allowed for BWP`.

## Normal Workflow
1. Use `Import Config` to load a known design, or complete the inputs manually.
2. On **Winding**, supply q or slots, pole count, Naa, and layer count, then choose an enabled Pattern. Unsupported Pattern buttons turn gray and show the base-layout failure on hover. If an existing selection becomes unavailable after an input change, its Pattern field is highlighted. The check uses a regular, unshifted base layout; transposition, shifts, inlet settings, and other layout settings can still affect the final plot. Very large layouts are outside the interactive check.
3. Complete required inputs on **Stator**, **Inslot**, **End Winding**, **Layout**, **Transposition**, **Figure**, and **Plot Config**.
4. Select `Parameter Analyze` to calculate dependent parameters.
5. Select `Layout Analyze` to inspect generated layout data.
6. Select `Plot Layout` to draw the main winding figure.
7. Save or export the result using the lower action row.

`extract_parameters()` is the central input-to-model path. In the normal workflow, its successful return value is `None`; use the populated display and generated application state to confirm success.

Completed layouts are saved in one SQLite database at
`%LOCALAPPDATA%\HairpinWindingScript\calculations-v1.sqlite3` on Windows
(or `~/.cache/HairpinWindingScript/calculations-v1.sqlite3` when local app data
is unavailable). On a later launch, the same inputs restore the complete
calculation and plot data without running Auto Configure again. A changed
drawing setting may require refreshed display calculations, but the stored
Auto result is reused when its winding, layout, objective and physical-model
inputs still match. Changed source code or damaged entries trigger normal
recalculation. Fractional candidate layouts are not saved in this database.

### Automatic balanced integer UWP divider

For the manual q=4 sample, set **48 slots, 4 poles, 6 layers, UWP**, then
select **q-divider=2, pp-divider=1, P2=2** (Naa=4). The Transposition tab automatically selects
**Auto**, derives the cycle/local q-position advances and branch starts, and shows
the full derived schedule. Phase A starts are slots **1, 3, 13, 15**, layer 1;
the other phase starts are generated from their phase belts. An importable
configuration is available at
UWP balanced sample (local research excluded).

The construction applies one factor rule: q-divider is a proper divisor of integer q,
pp-divider is any factor of the pole-pair count, P2=2,
Naa=2*q-divider*pp-divider. For a single phase sequence, the verified route
requires an odd phase count of at least three and even layers. For a phase count
that is a multiple of three, the generator builds and checks equally layer-assigned
three-phase sets independently; each set must satisfy this route's construction
conditions. pp-divider divides each full-pole sweep into rotating, even-pole arcs;
the next lane takes the next pp-divider arc. The algorithm selects a common q-position
schedule from cycle and local-arc advances that gives every branch identical
occupancy of every q position and exact unique conductor coverage. No
q, pp-divider, Naa, slot-count, or pole-count tuple is whitelisted. The route is
admitted only when its branch conductor count is divisible by q, which is the
integer condition for that equal distribution. Phase counts divisible by three
use the project's three-phase-set array model; the resolver checks the resulting
three-phase construction rather than treating the sets as one phase sequence.
Every generated layout must pass independent coverage, phase, direction,
forward-edge and complex-EMF checks.
The manual sample's original paths do not pass parallel-EMF validation;
automatic balance adjusts their internal paths while retaining the sample starts.

Use unshifted layers and the insert-side inlet, without radial swaps, extra
PoleN/PoleS transposition or inlet-index adjustments. Switching away restores
the previous transposition settings. Config imports preserve the target's own
settings. The derived automatic fields are read-only; **Auto** reapplies
the automatic schedule. Electrical checks do not assess mechanical clearance.

### Half-integer BWP/UWP global-wave candidates

For three phases, q=1.5/2.5/3.5, even layers, and `Naa` dividing the number
of pole pairs `pp`, **BWP** and **UWP** offer separate inspection candidates.
Starts are evenly spaced at `total slots / Naa`, but each branch travels
through the full circumference rather than remaining in its starting sector.
Each wave segment spans `pp/Naa` pole pairs before the next layer-pair or
lane transition. BWP reverses the slot direction on its return sweeps; UWP
keeps ordinary sweeps forward. Short, direction-consistent special edges
join successive segments. The exported q=1.5 BWP single-branch draft remains
an exact sequence regression.

Integer layer shifts are applied after the default path. The report counts
shifted endpoints that cross a sector boundary; these do not reassign branch
identity. The detailed Layout Analysis lists every insertion-side jumper or
sweep transition with its default, shifted, and plotted shortest pitch.
Transposition, CHW/radial swap, weld-side inlet, and inlet-index
adjustments are not supported for this route. These diagrams are candidates,
not production calculations or manufacturing clearance approvals.

The established **UWP/Naa=2q** candidate takes precedence when its branch
count also happens to divide `pp`; its existing grouped-transposition rules
are unchanged. Other fractional q and branch counts retain the independent
Phase Division preview.

### Half-integer UWP layout candidate

The startup development example is already set to q=1.5, eight poles,
36 slots, six layers, Naa=3, and UWP in `q and poles` mode.

The existing public resolver and candidate-enabled generator retain this
construction for inspection. For `q=1.5`, eight poles, six layers, and `Naa=3`,
`get_winding_layout(..., allow_candidate=True)` generates nine paths with
Candidate identity. The normal production base check rejects this case with
`[pattern_identity_candidate]`; the main window does not currently admit it
through **Select Pattern**. Do not interpret a constructible route or a saved
candidate diagram as production validation. The Version 7.5 evidence remains
available for later investigation.

The following controls describe the retained exploratory path when a fractional
candidate is accessible; the `q=1.5` main-window case above is currently
blocked by its production base check. For fractional q, the Transposition tab
prompts the user to open **Advanced**.
Only half-integer UWP with `Naa=2q` enables independent **PoleN** and **PoleS**
settings. PoleN and PoleS classify each phase's branch starts by the signed
first-layer pole in the phase-division map: PoleN is the positive start group
(the phase-relative first pole), and PoleS is the negative start group (the
phase-relative second pole). They do not mean the same global physical pole
sector for all phases. For `q=n+1/2`, each phase normally has `n+1`
PoleN branches and `n` PoleS branches; at `q=1.5`, that is 2 and 1, so PoleS
has no within-phase branch pair to exchange. The controls can choose Regular,
Times, Interval, or Optimize independently only where legal pairs exist.
With **Regular**, Uniform `0` leaves the group unchanged; Uniform `1` rotates
all branches in that phase-relative group by one group position at **every**
insertion-side connection. A group with fewer than two branches cannot use it.
For three branches, the cyclic return is a one-position rotation but has a
physical slot displacement of `-2`; for four branches it is `-3`. Uniform
cannot be combined with the other Regular offsets. First-layer, last-layer,
and jump-layer values select signed slot displacements at eligible positions.
Values in gray fields are retained for later editing but are inactive for the
currently selected Type and are reported as zero in the generated candidate.
Times counts complete eligible insertion-side positions across all phases in
the chosen pole group. Interval counts physical
insertion-side connection positions (1, 2, 3, ...) and selects multiples of
the requested interval when a legal exchange exists there. Optimize checks at
most 200 insertion-side tail-swap candidates per group and reports whether it
exhausted that list.
The sign of Jump layer also selects the forward or reverse layer transition;
a direction without a legal candidate is rejected.
One selected Times/Interval position swaps complete downstream branch tails
at a single insertion-side cut. This changes one physical insertion-side
boundary, not both sides of a temporarily moved weld pair. Uniform rotates
all group tails at every cut. Every two-conductor weld pair remains intact;
one tail crossing exchanges the affected branches' downstream outlet paths.
Tails may lie in another physical pole sector or cross a sector boundary.
The terminal weld pair has no following insertion position and is excluded.
Uniform `1` is rejected when there are no insertion-side positions; it cannot
silently succeed without producing a transposition.
Pair crossovers change insertion-side pitch by at most one slot. For Uniform
cycles with more than two branches, the single cyclic return may differ by
up to group width minus one slots; this is a candidate rule, not a production
end-winding clearance approval.
The report lists selected cuts, involved branches, and changed insertion-side
edges for engineering review. A missing or conflicting position is rejected; the app does not publish
a partial exchange.
Grouped transposition candidates require zero inlet-index adjustments so the
reported changed edges still describe the displayed paths.

The generated paths cover each slot/layer once and stay within their assigned
phase, but the tested parallel branches have unequal complex fundamental EMFs.
Grouped transposition results are still candidate paths and crossover pitches
have not been approved as a production UWP connection rule.
The candidate is therefore not installed as a completed calculation. Parameter
analysis, end-winding results and branch-connection exports remain unavailable
for this fractional case. Other fractional Patterns and branch counts continue
to use Phase Division previews.

### Plot Layout views

After selecting **Plot Layout**, choose **Circular** or **Unwrapped** in the plot toolbar.
Both Plot Layout and Phase Division initially use **Unwrapped**. The **Branch** dropdown
beside View shows an individual actual branch without recalculation. **All** follows the
existing single-phase display option; selecting a specific branch overrides that option.
The branch choice is session-only and saved figure names identify a filtered branch.
Unwrapped shows every slot from left to right and layers from outer to inner, with the
same ordered branch connections and terminals as the circular layout. Connections that
cross the first/last slot boundary have matching continuation identifiers at both edges.
Same-layer connections use staggered routes. At the outer and inner layers, routes
within a physical pole region follow the same pitch ordering as Circular view, placing
longer nested connections farther from the conductor row to avoid line crossings.
This is a connection diagram, not a scaled
end-winding geometry drawing.

Direction arrows sit near the start of each displayed connection span rather than at its
midpoint. Continuation arrows appear only at the right slot boundary and follow the local
line direction; matching continuation identifiers remain on both boundaries.
Above the grid, inlet terminals connect vertically to their labeled Phase A/B/C rails,
and outlet terminals connect vertically to the Neutral line. The rails and their leads
use distinct phase/neutral colors. Dots indicate rail junctions; crossings without dots
are not junctions. Existing inlet/outlet visibility switches also control these rails.
These external rails annotate the drawing only and do not modify model or export connectivity.

Switching views uses the last plotted data snapshot. It does not apply pending input edits
or rerun winding generation; select **Plot Layout** or an existing Apply action to update
the drawing. Phase Division and Plot Layout retain separate view choices for the session.
These choices are not written into configuration files.

### Manual branch starts in Phase Division

1. Select **Plot Phase Division**, then enable **Manual starts**.
2. Choose a phase and branch from the dropdown. Outlined conductors show that branch's
   members. Clicking a conductor owned by another branch switches the dropdown to its owner.
3. Click a conductor in either Unwrapped or Circular view. A star marks the selected start;
   the selected integer branch's complete candidate sequence appears as dashed lines.
4. Select another branch to inspect or change its start. Each branch keeps its own draft
   start during the current phase preview. **Reset starts** clears all draft selections.

The integer-q first version changes the inlet within an existing branch by cyclically
rotating its generated Pattern sequence. It checks the new old-outlet-to-old-inlet join,
phase membership, occupancy and alternating directions; closed-loop previews additionally
validate and draw the final-to-first edge. An unavailable join or a click outside that
branch is rejected with an explanation. Arbitrary same-phase rerouting is not implemented.
The baseline is generated independently from the current Pattern/Transposition inputs;
existing production inlet-offset adjustments are not imported. CHW previews are unavailable
because Phase Division does not represent its connection-specific local swaps.

For fractional q, Phase Division initially assigns each conductor to one candidate branch
using a selected division plan, its default starts, and equal category quotas. For
q=1.5, pp=4 and Naa=2/3/4/6, the initial plan follows the documented
(P, R) rule (local research excluded). Other cases use the exploratory
position-first plan unless a candidate rule is selected in Branch Division. These
memberships do not reproduce an integer-q connected path. Strong
symmetry is preferred; if only weak symmetry is available, equal phase/layer counts do not
establish equal branch EMF. Selecting a branch previews its assigned conductors and allows
a draft inlet marker. It does not call the production connection generator or draw a
complete connection path. A division plan that cannot meet its quotas remains unavailable.

### Branch Division developer workbench

After **Plot Phase Division**, select **Branch Division...** on the plot toolbar.
The candidate planner uses the same supported phase count `m` shown in Phase
Division; for `m=3k`, layer groups must divide evenly among the `k` independent
three-phase sets. Its count-based quotas and phase labels are generated for all
`m` phases.
For fractional-q `Naa=2`, the initial candidate uses two contiguous half-ring
slot regions when the pole count permits them. For example, with 60 slots and
eight poles, Branch 1 is eligible in slots 1–30 and Branch 2 in slots 31–60.
In the modeless workbench, choose a Pattern, pole-region count `P`, and position
branches per region `R`; both controls accept custom positive integers. The hint line
shows factors available for the current Naa and poles, including `pp` and `q×2` when
applicable. `P × R` must equal Naa, and `P` must divide the pole count.

The table lists factor pairs across all Patterns; select a row to load its Pattern and
factors, or enter custom integers in the controls. **Strong candidate** and
**Weak candidate** describe division counts and starts only; **Unavailable** identifies
a rule that fails the current constraints or Pattern policy. **Preview selected rule**
shows its single-branch members in Phase Division without changing the Winding Pattern,
production connection state or configuration. **Mark draft preferred** records a
per-Pattern choice for the current q/pole/layer/Naa/shift inputs in this application
session. These draft choices are not saved to configuration files or treated as
approved Pattern rules. Plot Phase Division again after changing inputs.

These are session-only candidates, not engineering approval or changes to Plot Layout,
branch-sheet exports, or calculation state. Relevant input edits invalidate the drafts;
selecting Plot Phase Division again also resets them. Saving the displayed phase figure
adds `ManualStartCandidate` to its filename when this mode is active. No candidate start
data is persisted to configuration JSON in this version.

Line colors, width, opacity, arrows, single-phase/side filters and terminal visibility
apply in both views. Circular rotation, CW, radii, sector division and radial route geometry
do not affect the unwrapped slot-layer coordinates. Use the existing wheel zoom, **Fit View**
and **Detach Plot / Embed Plot** controls with either view. **Save layout as figure** saves
the displayed result; unwrapped filenames include `Unwrapped`. A failed drawing cannot
be saved; correct the input or settings and select **Plot Layout** again.

## Tabs
| Tab | Function |
| --- | --- |
| **Winding** | Main winding inputs, pattern selection, and inlet-position configuration. |
| **Stator** | Stator geometry. |
| **Inslot** | In-slot conductor and insulation geometry. |
| **End Winding** | End-winding geometry and calculation inputs. |
| **Layout** | Layout-specific settings and pattern behavior. |
| **Transposition** | Transposition type and valid ranges. |
| **Figure** | Layout appearance. Select `Apply Figure Settings` after edits. |
| **Plot Config** | Layout plot colors, lines, and slot-label options. Select `Apply Plot Config` after edits. |
| **Winding Factor** | Winding-function plot and data table. |
| **Volt Diff** | Adjacent-layer voltage-difference calculation, optimization, plotting, and export. |
| **Inductance** | Active-length branch and phase self/mutual partial-inductance matrices. |

The shared analyze/layout controls are hidden while **Volt Diff** or **Inductance** is active and restored when the user leaves those dedicated analysis tabs.

## Volt Diff
1. Generate a valid layout first.
2. On **Volt Diff**, select `No labels`, `Index diff`, or `Volt diff` and adjust the cell/text display settings.
3. Select `Update Volt Diff` to calculate the phase-aware voltage-difference and equivalent-index matrices.
4. Optionally select `Optimize Inlet Positions`. It runs in a background Qt worker.
5. To enter terminal adjustments manually, use `Config. inlet positions` on **Winding**. `Busbar Optimize` proposes values; select `Apply` to commit them.
6. Select `Export VD Plot XLSX` or `Export VD Plot SVG` to export the current result.

`vd_optimize.py` owns the Volt Diff scoring and `compute_voltage_difference_matrix(...)` API. `main_pyqt6.py` should call this API rather than duplicating the calculation.

The main layout and Volt Diff chart are intentionally separate: Layout uses `figure`, `ax`, and `canvas`; Volt Diff uses `vd_figure`, `vd_ax`, and `vd_canvas`. The right-side `QStackedWidget` switches between them, preventing heatmap scrollbars, colorbars, and redraws from affecting the Layout plot. `export_voltage_difference_svg()` must save `self.vd_figure`.

Volt Diff cell annotations automatically choose black or white text from the actual colormap background for readable contrast.

## Inductance

1. Generate or configure the current layout.
2. Keep **Medium relative permeability** at `1.0` for the bounded homogeneous air/copper model, or enter a documented homogeneous-medium multiplier.
3. The rectangular-conductor self GMR is calculated from the active conductor width and height using the rectangular-section geometric-mean-distance formula. The tab shows the derived value in millimetres after calculation.
4. Select **Calculate Inductance**. The tab displays phase and branch matrices in μH plus normalized phase and branch matrices. Branch labels are phase-local (`A-B1`, `A-B2`, and so on), while calculation data retains global branch IDs.
5. Select any matrix page and use **Pop Out Matrix** to inspect that same table in a resizable window. Select **Embed Matrix** or close the window to return it to the tab.

Select **? Model Guide** in the Inductance tab for an illustrated standalone reference covering inputs, assumptions, equations, interpretation, workflow and sources.

`inductance_calculation.py` places each active conductor at its current slot/layer radius, obtains signed current direction from `phase_topology.phase_map(...)`, and evaluates the finite-parallel-segment partial-inductance kernel. It aggregates conductor terms into the branch matrix with signed series incidence. The phase matrix assumes equal current sharing among every parallel branch of a phase. Positive branch/phase currents follow that sign map; a negative mutual term therefore means opposing flux linkage under this port-reference convention.

The normalized pages report the signed coupling ratio `kij = Mij / sqrt(Lii Ljj)` for both phase and branch matrices. Every diagonal self term is therefore exactly `1`. Using the geometric mean of the two self-inductances keeps the normalized matrix symmetric when `Lii` and `Ljj` differ; it is more precise than dividing every row by only one self term.

Changing a physical or inductance-model input clears the displayed matrices immediately and returns any detached matrix to its tab. Recalculate before using the result. Figure-only display edits keep the current physical result. The dedicated tab uses the full upper workspace so larger branch matrices can be inspected with their table scrollbars or in the pop-out window.

This is an active-length analytical approximation, not a finite-element result or full machine inductance. It excludes end-winding inductance/mutual coupling, slot and tooth iron-boundary effects, saturation, skew, and frequency-dependent skin/proximity redistribution. The permeability input scales a homogeneous medium; it is not a steel permeability or saturation model. Candidate layouts remain labelled for inspection only, and a calculated matrix does not certify winding symmetry or manufacturability.

## Supporting Modules
| Module | Responsibility |
| --- | --- |
| `main_pyqt6.py` | PyQt6 application entry point and integration owner; `WindingApp` retains the existing calls for extracted UI features. |
| `inductance_ui.py` | Inductance-tab UI, matrix display, result invalidation, and matrix window handling. |
| `config_io.py` | Configuration payload creation/application and JSON import/export. |
| `result_export.py` | Phase-branch and Volt Diff workbook/SVG export. |
| `pattern_route_contract.py` | Shared route decision and admission fields used by production and UI callers. |
| `get_winding_pattern.py` | Winding-pattern selection and layout generation. |
| `pattern_rule_workbench.py` | Exploratory route catalog and manual drafts; public generation gates validation labels. |
| `refresh_pattern_naa_division_layout.py` | Build and check the finite current rule page and inventory. |
| `draw_figure.py` | Main winding-layout drawing. |
| `layout_analysis.py` | Layout analysis and reporting. |
| `cond_info_operation.py` | Conductor information and branch organization. |
| `end_winding_calc.py` | End-winding calculation support. |
| `winding_function_calculation.py` | Winding-function calculation and plotting. |
| `vd_optimize.py` | Phase-aware Volt Diff matrix calculation and inlet optimization. |
| `inductance_calculation.py` | Active-length conductor, branch, and equal-sharing phase partial-inductance matrices. |
| `calculation_state.py` | Coherent publication unit for a completed calculation generation. |
| `app_diagnostics.py` | Bounded structured exception log with user-visible event references. |

## Files and Exports
| Action | Default destination |
| --- | --- |
| `Import Config` / `Export Config` | `configs\` (`.json`) |
| `Save layout as figure` | `plots\` |
| `Export Branch Sheets` | `branch_connection_exports\` (`.xlsx`) |
| `Export VD Plot XLSX` / `Export VD Plot SVG` | `voltage_difference_exports\` |

Configuration examples are kept in `configs\`. Preserve them as reproducible cases, including `config_20260704_143258_Slot48_Pole8_Layer6_Naa2 inlet positions.json`.

The lower action row provides initial end-winding calculation, configuration import/export, layout-figure saving, branch-sheet export, and placeholders for future `3D model` and `Config. in JMAG` integrations.

## Build
Run `build_main_pyqt6.bat` from this folder. It uses the project virtual environment's PyInstaller and produces `dist\WindingDesignTool_v7_6.exe`. Temporary build and spec files are written under `build\WindingDesignTool_v7_6\`.

The main EXE bundles the current Pattern, Connection Rules, Naa status, and
Inductance help pages with their light assets. The Pattern Rule Workbench still
runs separately through `run_pattern_rule_workbench.bat`. Links from bundled
help pages to archived Version 7.5 research or Python source files require the
source workspace; those targets are not inside the single-file EXE.

## Developer Notes
- Keep domain calculation rules in the supporting modules, not in UI handlers.
- Do not merge the Layout and Volt Diff Matplotlib canvases.
- Before editing source, create a timestamped backup under `Backups\` and document the change in `CHANGELOG_Version_7.6.md`.
- For headless GUI checks, use the project virtual environment with `QT_QPA_PLATFORM=offscreen` and a repo-local writable `MPLCONFIGDIR`.
- Use `performance_baseline.py` for separate response-time and allocation-tracing baselines. Use `stability_soak.py` for repeated non-rendering calculation/state verification.
- Unexpected user-action failures are recorded under `logs\winding_design_errors.jsonl`; the event ID shown in the UI identifies the matching JSONL record.
