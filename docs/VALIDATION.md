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
| Finite-status decisions, source drift and navigation | `test_pattern_naa_division_layout` |
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

### Finite divider-status provenance (2026-10-02)

The existing six-geometry sample was refreshed without changing production rules:
80 Pattern/formula cells contain 860 preflight requests, with unchanged counts
of 430 supported, four Candidate, 367 rejected and 59 unsupported-yet requests.
Public generation is shown only for explicitly run examples; retained EMF
asymmetry remains `retained-not-strong`, separate from strong-symmetry certification.
Neither the counts nor those examples establish complete-domain support.

The inventory records the 14-file local Python import closure, per-file SHA-256
values and an aggregate digest of the sorted compact file map, normalizing CRLF
to LF (`sha256-sorted-file-map-lf-v1`). The generator compares entry/exit source
signatures before writing resources. `--check` verifies that map and the exact
HTML/Markdown rendering of the saved JSON, including its generation timestamp.
Excluded V7.5 research is described without links to missing repository files.

All 22 direct status tests passed, including five new checks for newline
portability, topology-source changes, source drift, rendering consistency and
repository navigation. The exact staged source also passed `--check` in an
isolated LF checkout using the existing environment. Four older TLP preflight
assertions were corrected using
the current 2026-09-29 post-connection-shift and manual-transposition rules in
`PATTERN_DIVIDER_FORMULA_SUPPORT.md`, confirmed by the resolver implementation.
They assert `enabled`/`supported` and the original rule IDs, retain inlet rejection,
and do not claim public generation for preflight-only probes. Unchanged runtime,
fixtures and environment reuse prior scoped evidence; no full regression was run.

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

### Native TLP proper-Q and multiphase review (2026-10-02)

The native `(Q,1,1)` proper-Q route passed 17 focused tests covering exact
reviewed paths, 32 public matrix cases, two additional q/Q pairs, seam and
cohort corruption, the two-layer qualification, shifts, Workbench status and
the multiphase admission guard. The ZPP `(Q,1,2), Q>1` exclusion passed 18
focused tests covering named-reason precedence, rejected pre-construction
dispatch and unaffected ZPP/SLP controls. `refresh_pattern_naa_division_layout.py
--check` confirmed the refreshed 14-file source receipt and rendered resources.

A separate private candidate review covered 48 mapped cases: eight proper-q
pairs, `(pp,L_local)=(2,2)` and `(3,4)`, and `m=6,9,12`. Its independent
checker verified 200,448 positions, 199,152 edges and 23,760 new seams, and
rejected seven deliberate corruptions. A bounded re-review corrected the earlier
22/26 safe/unsafe classification: all 48 pass the one-region connection-stage
check in their canonical local phase-set coordinates. The 26 cases still have
52 two-boundary records against fixed global slot-zero intervals after rotation;
these are coordinate diagnostics, not failed construction edges. The proposed
`k=m/3` dividing Q restriction is withdrawn. Existing source and saved paths were
reused without generation or production changes. For q=4, Q=2, m=9, a +37 seam
maps local 135->28 to global 143->36 with offset 8 and tau=36: unwrapped local
135->172 crosses one region, while global 143->180 crosses two fixed intervals.
The current contract checks connections before relocation and does not repeat
pole-region identity checks on rotated endpoints. A representative
six-phase layout retains all positions and local identities while its global
report keeps `multi_phase_emf_mismatch`; no strong-symmetry or manufacturing
claim follows. At that private-review stage, public TLP phase-array admission
was `unsupported-yet`; the subsequent owner-approved admission below supersedes
that boundary. The saved matrix,
checker and figures remain excluded local review evidence under
`Latest_Python_Files/Version 7.6/workbench_preview/tlp_multiphase_20261002/`.

### Owner-approved TLP phase-array admission (2026-10-02)

The integer-global-q array guard now delegates to supported local constructors
and the existing aggregate structural preflight. For `m=3k`, use `q_s=k*q`
and `L_s=L/k`: even `2<=Q<=q_s`, `Q|q_s`, `pp>=2`, even `L_s>=2`,
and insert-side entry. No `k|Q` restriction or global-Q-divides-q test is added.
Fractional-global-q remains unsupported-yet for this route.

A failing public test first reproduced rejection of the rotated +37-slot seam;
a separate failing catalog test reproduced the missing local Q=2 row at
global q=1, m=6. The updated public tests cover all 48 former private cases,
five local-factor/set-count cases including 15/18 phases, exact mapped parent
nodes, phase/polarity, occupancy, branch counts, local signed edges and an
independent nonzero complex-EMF formula. Corrupting a seam through the public
generation path still fails; invalid factors, local layers, short sources,
fractional scope and post-connection shifts are covered.

Workbench enumerates extra TLP q-only requests from local q. Successful public
generation can mark a route Validated while Auto remains pending; its retained
`not strong symmetry layout` and EMF diagnostics are now visible in the reason.
The Auto decision algorithm and production certification gates are unchanged.
The private saved-source receipt predates this source edit and is historical;
current tests and refreshed 14-file finite-status resources supply fresh evidence.

Scoped checks passed: 17 TLP proper-Q tests, eight existing TLP q-only tests,
eight existing phase-array tests, the named ZPP exclusion control, two existing
Workbench status checks, all 22 direct finite-status tests, and the refreshed
status `--check`. Two legacy array-rejection expectations were updated for the
approved local-construction contract and now verify public generation/retention.
The initial status probe lacked its generation call; it now exercises the
public route. Six affected status/provenance checks were rerun successfully
outside the Windows sandbox after temporary-directory ACLs blocked fixture setup;
the other 16 passing status checks were reused for unchanged cases.
Unchanged fixtures and environment reuse prior evidence; no full regression ran.

Unvalidated domains include complete integer coverage, deferred fractional
families, native Windows DPI/button flows, current packaged-resource acceptance,
manufacturing behavior, and clean installation on another machine. No complete
suite pass is claimed.

Use full discovery only for broad impact, broader failures, or an explicit request:
`python -X utf8 -m unittest discover -s . -p 'test_*.py' -v`.
Restore offscreen overrides before a native application launch.
