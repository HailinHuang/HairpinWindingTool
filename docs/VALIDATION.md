# Version 7.6 validation

## Engineering gates

Check exact coverage and unique position occupancy; equal branch counts;
phase membership/pole sign; alternating direction/signed travel; ordered Pattern
connection sides/layer spans and legal edge/pitch geometry; consistent welding
travel; and applicable P2 N-to-S terminal orientation. Preserve default and
alternative routes.

Electrical checks report nonzero complex branch EMF and parallel symmetry.
Asymmetry alone does not reject a unique-occupancy/equal-count layout. Retention
does not certify strong symmetry or manufacturability. Preflight, successful
public generation, and exploratory/manual evidence remain separate.

## Focused commands

From the repository root:

```powershell
Set-Location 'Latest_Python_Files/Version 7.6'
$env:QT_QPA_PLATFORM = 'offscreen'
$env:MPLCONFIGDIR = Join-Path $env:TEMP 'hairpin-matplotlib'
& '..\..\.venv\Scripts\python.exe' -X utf8 -m unittest <dotted-test> -v
```

| Scope | Existing checks |
| --- | --- |
| Phase maps/independent electrical reference | `test_phase_topology` |
| Included examples/config roundtrip | `test_classic_regression.ClassicBusinessRegressionTests.test_copied_config_examples_import`, `test_fractional_config_file_roundtrip_preserves_slots` in the same class |
| Export contents | `test_classic_regression.ClassicBusinessRegressionTests.test_branch_export_writes_real_workbook` |
| Main-window admission boundary | `test_main_pattern_route_ui` |
| Saved exploratory fixtures | `test_pattern_rule_workbench.SavedManualDividerDraftCharacterizationTests` |
| Public route versus saved independent path | `test_zpp_centered_entry_admission.ZppCenteredEntryAdmissionTests.test_q2_d4_public_paths_match_the_saved_manual_package` |
| Workbench serialization | `test_pattern_rule_workbench.PatternDraftTests.test_complete_rule_package_enables_copy_and_writes_schema_v3` |
| Help-page navigation | `test_pattern_naa_division_layout.PatternNaaDivisionLayoutTests.test_saved_page_covers_patterns_and_links_to_archived_evidence` |
| Finite-status provenance after refresh | `python refresh_pattern_naa_division_layout.py --check` |

Selected JSON fixtures retain their original names because tests read those
paths. They are inputs/oracles, not current certification receipts. Other drafts,
preview plots, investigation outputs, and historical source snapshots are excluded.

## Current coverage

On 2026-10-02, the initial 132-file staged selection passed 31 focused tests: 16 phase-topology
tests, one saved-path ZPP public-generation check, seven main-window route tests,
three configuration/workbook checks, two saved-draft checks, one schema-v3 export
check, and one help-navigation check. The main window and Workbench were constructed
offscreen. Seven installed runtime pins matched requirements; both entry modules
imported from the isolated tree. All 58 Python and 44 JSON staged files parsed.
The exact staged-content scan found no credential or personal-workspace-path
matches and no file over 5 MB. Local navigation resolves within selected files.

The final import also includes `half_integer_q_source_receipt.py` and its direct
test module. All nine receipt-window tests passed from their exact staged files
in the isolated checkout; unchanged source and fixtures reuse the checks above.
The launcher binds an external, reviewed manifest and receipt before probe import
and around resolver/generation calls. Its tests use standard-library fakes; they
do not establish TLP/UWP construction validity. Generated manifests, receipts
and probe outputs remain local evidence outside Git.

The initial UI check reproduced an old expectation that radial shift was disabled
for a half-integer BWP case. The existing post-connection-shift implementation and
resolver enable this control. The test now checks that preflight boundary; no
production module or launcher was changed. All affected UI checks were rerun.

An additional bounded probe at BWP `q=5/2`, 12 poles, 6 layers, `Naa=3`, dividers
`(1,3,1)` confirmed enabled preflight but strict public-generation
`pattern_identity_candidate` rejection for both baseline and radial-shift requests,
because actual connections cross multiple pole regions. This is a current
candidate boundary, not a certified construction or a migration regression.

The finite-status resources have a stale source signature. Their archived examples
are not current acceptance. Refresh is a separate source-bound task; this import
does not rerun all routes or change production admission.

### Finite half-integer ZPP formula evidence (2026-10-02)

The fresh r2 probe passed at `h=3,5,7`, with `q_global=h/2`, `q_local=h`,
six phases in two phase sets, four poles, eight global layers and four local
layers, and dividers `(h,2,1)`. Requests used neutral Regular transposition,
weld-side entry, and zero phase/radial shifts. All nine target preflights and
nine strict public calls passed; twelve constructor captures were recorded,
with zero Candidate calls. The three `h=1` checks were route-only and are
excluded from the generated family evidence.

The recorded connection formula uses `regular_tp=3*h`, the signed slot step
`3*h*d + (((r+d*t) mod h)-r)`, where `r` is the local lane in `[0,h)`,
`d` is signed direction (`-1` or `+1`), and `t` is the integer Connection
`ptp` field. Starts are `(R + 6*h*n, 0, R mod h)` for `n=0..1`,
`R=0..3*h-1`; three comes from the local phase count, `6*h` is twice the
`3*h` pole-region width, and two start blocks come from four poles.
The seven connection roles alternate four `SLPP_insert` edges with three weld
edges. The vectors are `(1,0,1), (1,1,0), (1,0,1), (-1,1,0), (1,0,1),
(1,1,0), (1,0,1)`, derived by repeating the four-vector block `local_layers/2`
times and dropping its final vector, as replayed against captured constructors.
This statement
records the sampled family; it does not prove all odd `h` or other geometries.

All three sample gates passed, including Pattern identity, phase/polarity,
signed travel, weld geometry, phase-set mapping, and exact unique occupancy.
The global layouts contain 288/480/672 unique conductor positions with equal
eight-conductor branches. All retain `not strong symmetry layout`; electrical
asymmetry remains diagnostic. The native global role analyzer reports only
half of the global edges. Independent mapped role checks cover exactly once
all 252/420/588 edges, with no missing, unexpected, duplicate, or mismatched
roles. The native half-coverage is retained as a diagnostic limitation.

Snapshot `v76-zpp-half-q-m6-l8-20261002-r2-a3a54e3c` binds 26 inputs to closure
SHA-256 `a3a54e3c97ad88fdd74f507cf36452807009a549c67c08060136dd4a92a94191`.
The persisted result is `family_passed`; final readback is `verified`.
An independent standard-library audit matched all 29 manifest entries by byte
size and SHA-256, the manifest's own digest, and the generation/end source maps
against the receipt. Supervisor review accepted this finite evidence node.
Evidence is local under the excluded
`Latest_Python_Files/Version 7.6/workbench_preview/half_integer_q_zpp_connection_family_refresh_20260929/`
directory; the r2 receipt, result, integrity manifest, and final readback remain
local audit artifacts. They are separate from the isolated staged-tree checks
above. No production source or admission change, native three-phase
half-integer-q ZPP formula, universal closure, or manufacturing acceptance is
claimed. Future source changes require a fresh binding before reusing evidence.

Unvalidated domains include complete integer coverage, deferred fractional
families, native Windows DPI/button flows, current packaged-resource acceptance,
manufacturing behavior, and clean installation on another machine. No complete
suite pass is claimed.

Use full discovery only for broad impact, broader failures, or an explicit request:
`python -X utf8 -m unittest discover -s . -p 'test_*.py' -v`.
Restore offscreen overrides before a native application launch.
