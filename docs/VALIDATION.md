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

### Latest integer construction review (2026-10-03)

The 400-request boundary check covered five selected geometry corners and
ten Patterns with eight factor choices per geometry (some choices coincide
at q=1). It reported 218 supported preflights, 179 rejected and three
Candidate. Six requests were not closed: three public-generation failures
and three Candidate at the UWP no-divider same-layer junction. This is
bounded evidence, not a scan/certification of the 1,302-geometry target.
The owner subsequently cancelled the documented UWP series-weld exception.
Positive integer local q_s, Q|q_s and D=P2=1 are rejected before native/array
dispatch, including explicit/implicit NoDivider, proper-Q, manual and shifted
requests. Full-Q q_s>1 retains its BWP identity reason. Independent identity
checking now rejects matching historical same-layer weld metadata as well.
New rejection tests reproduced the old behavior before this change and pass
afterwards; PP/P2 public coverage, ordered identity and implicit A=2 P2
selection remain valid controls. The six earlier UWP requests are closed
by this accepted construction exclusion, not an impossibility claim.

The final bounded pass completed 71 direct tests in one runner and two
explicit-exclusion catalog tests with unrelated Auto generation deliberately
omitted: 73 passed. These include ordered identity, UWP explicit/implicit and
native/array exclusions, manual/shifted negatives, configured PP/P2 coverage,
P2 inlet anchors, Regular/Times/Interval controls, Workbench rejection before
Auto probing, finite-state decisions/navigation, and one offscreen P2 UI check.
Two earlier legacy checks were stopped after they entered broader Auto searches;
they supply no new Auto result. Unchanged-source evidence above is reused.
Independent read-only review found no production blocker; its stale helper
assertions and status wording were reconciled with the current owner decision.

New TLP even-gcd and odd-q P2-parent cuts, TSP one-complete-pass B>=8
partitioning, CP polarity-pool/quartet cuts and local two-layer identity
transfer, and SLP N-belt/cycle-gcd partitions use independent configured
public-parent oracles. Tests check full unique occupancy, equal branch
lengths, canonical phase/sign, actual weld inheritance, adjacent-layer
pitch/direction, complete signed records, one-region edges and P2 terminals.
Negative controls reject failed configured parents, explicit null/partial
travel, extra-turn travel and incompatible actual welds without neutral retry.
Independent read-only engineering review found no remaining blocker in
these constructions; it did not certify untested manual configurations.

An affected 123-test run exposed stale expectations and real legacy source
ordering failures. The failures were corrected against construction oracles:
proper-Q raw TLP/TSP q/P2 mothers omit lanes; valid full-Q/P2-only mothers
keep priority. Valid CP local four/six-layer mothers preserve the saved
manual-weave order. Legacy SLP paired-lane ordering is retained at m_s=3;
native odd m>3 uses physical N-belt indexing. After these fixes, nine TLP
and catalog checks, five SLP compatibility checks and two SLP physical-weld
checks passed, alongside the earlier focused CP/TSP/evidence controls.
Changed test expectations now check actual public paths and welds, rather
than treating a passing assertion as proof of support.

All 22 directly affected finite-status checks were run: 19 passed and three
stale boundary expectations failed. The CP pool exclusion, SLP odd-sector
construction and TLP local-two-layer expectations were reconciled with their
parameter proofs and actual public generation. This also exposed the old TLP
D=4 sector source failure: the existing structural oracle now retains valid
old deployments and selects complete gcd/P2-parent cuts for failed ones.
The new red test reproduced that failure, then passed exact public Q-only
mother-cut oracles for both `(1,4,2)` and its retained `(2,4,2)` child at
q=2, pp=8, L=4, m=3. The three affected status methods then passed.

An inexpensive registration-only census covered the selected 1,302 geometries
and 190,380 Pattern/factor requests. Resolver, preflight and public generation
were explicitly excluded from that census, and constructor-quality predicates
were skipped: it is a registration check, not layout certification. It found
16 TLP full-global-Q array requests whose odd-local-q P2-parent cut was
registered but omitted from the array mapper. The mapper now accepts that
existing formula while keeping valid legacy mappings first. A new red test
reproduced the omission, then public generation and exact P2-mother cut oracles
passed for all 16 requests; the legacy mapping control also passed.

The existing six-geometry resources were refreshed after the final production
edit: 80 cells, 860 requests, 501 supported preflights and 359 rejected,
with no Candidate/unsupported-yet in that finite view. The 14-file source
signature is `299e7094b107d283b24c9a4006a713e1f304ba1de37b004874dd20f2538b1457`;
`refresh_pattern_naa_division_layout.py --check` and navigation checks pass.
The nine-request finite preflight change is UWP owner rejection only; unchanged
Pattern evidence is reused. This sample does not certify the selected domain.
Its closure is parameterized construction or accepted exclusion plus explicit
configuration capability, with actual configured mother/target gates still
required. No full regression or additional audit report is introduced.

Post-connection shifts transform both nodes and the canonical phase map;
the connection formula is checked before shifting. Configured-parent routes
preserve the requested TP fields and require actual mother/child gates.
Fixed recipes still enforce their actual neutral-only capability. Auto,
strong symmetry, full regression, clean install, native/package and
manufacturing acceptance remain outside this milestone.

### Integer-q closure in progress (2026-10-03)

The selected first domain contains 1,302 geometry tuples, before divider and
configuration choices. This number describes the target, not tested coverage
or completed closure. Auto, strong symmetry and broader release acceptance
remain separate.

The new CP/TLP Q-parent partition tests established failing public requests
before implementation, then passed 12 CP and seven TLP tests. Independent
oracles compare children with complete public `(Q,1,1)` parents and check
occupancy, equal lengths, canonical phase/polarity, ordered identity, signed
one-region travel, and weld pitch/direction. Missing, corrupt and failed parent
controls do not permit a substitute construction. Configured parents retain
their own actual-generation gates; the neutral proof does not certify every
manual payload.

SLP's existing proper-Q P2 lane-regrouping formula now accepts D=1 while
retaining even pp/D. Four new tests failed before the two admission/formula
conditions were extended, then passed. Their independent oracle checks public
full-Q parent blocks, full coverage, canonical phase/sign, N-to-S terminals,
ordered passes, insertion-only returns, one-region travel, and exact inheritance
of all actual welds. Native, local two-layer array and nonzero phase-shift
examples pass; odd-pass and established-route controls remain.

Twenty existing TLP cohort tests, nine post-connection-shift tests, two
CP Q-only tests, three CP global/local layer tests and the established TLP
even-PP/array method passed. Three established SLP mixed-P2 methods also passed,
covering older parameters, exclusions, insertion-side and manual-TP output gates.
This gives 61 distinct checks at this milestone. The
last assertion in that TLP method formerly described a now-supported proper-Q
request as unsupported. It now checks successful public generation and exact
four-way cuts of public `(2,1,1)` parents, including full unique occupancy.
Two corrupt-evidence tests first reproduced explicit-null parent records and
missing/extra global array records being treated as absent evidence. New-route
checks now reject these records before local projection; complete normal arrays
still pass. A legacy parent with no travel attribute may use its independently
validated unique short arcs. An explicit invalid record is never replaced.
One initial command named a nonexistent CP test class; the two real CP checks were then
run successfully. No behavioral failure was hidden by changing an expectation.
The existing six-geometry status sample was refreshed: 80 cells and 860
preflight requests now report 439 supported, two Candidate, 378 rejected and
41 unsupported-yet requests. All 22 direct status checks passed, bringing this
milestone to 83 distinct scoped tests. One stale proper-Q status assertion now
reports the admitted Q-parent route; its probe remains preflight-only. Five
provenance tests required the unrestricted execution token after their temporary
fixtures hit permission errors, including inside the ignored workspace preview
directory; they then passed without test or production changes.

At the preceding Q-parent/SLP milestone, `refresh_pattern_naa_division_layout.py
--check` passed against the 14-file
source signature `f3d21fe487870fc7b470b668d9623da59119261eadf766ae16772d634159b998`.
This refresh does not expand the six-geometry sample or establish closure of the
1,302-geometry target. Clean-install, native/package, manufacturing and broad
regression acceptance remain unverified.

The owner then accepted ZPP actual-lane endpoint cyclic permutation/gcd partition
and the current-grammar TSP/TLP odd-Naa exclusion. Nine ZPP tests and three
odd-Naa tests pass. ZPP independent oracles use actual full-Q public parents,
separate physical start/end lane maps, gcd cohorts/cuts and N-to-S orientation;
they verify every position, phase/sign, ordered edge, adjacent-layer weld,
pitch/direction and signed one-region travel. Cases include native odd phases,
local two-layer arrays, the old proper-Q+PP and variable-stride gaps, nonzero
phase shifts, selected-domain upper bounds and B=2 children. Two evidence tests
first reproduced null per-branch records escaping as TypeError; the new helper
and array projection gate now reject invalid sequence types/lengths explicitly.
Absent legacy evidence permits only unambiguous validated short arcs.

Nine established ZPP checks pass, including unchanged saved-path signatures.
Two former total-route negative assertions now verify exact endpoint/gcd
paths derived independently from actual public parents. Fixed-global aggregate
two-boundary diagnostics remain visible and separate from canonical array gates.
Independent review found an overly broad array flag that would change an existing
half-integer indexed route; a failing direct control preceded its restriction to
the original integer-global-q boundary. The final half-integer control passes.
The retained odd-effective-q P2 exclusion's reason test also passes after removing
the obsolete claim that every new ZPP construction needs Q*P2=q_s.

All 22 direct finite-status checks pass. The initial run had one stale array-stride
negative assertion; only that method was rerun after updating it to the approved
rule and actual retained public result. This yields 44 new/affected checks at this
milestone and 105 distinct checks across this local pass, reusing 61 unchanged
engineering checks from the preceding milestone. No full regression was run.
The existing 80 cells/860 requests now report 479 supported preflights, two
Candidate, 361 rejected and 18 unsupported-yet. The 14-file source signature is
`72e5e2e0d5441d3f1403db5c4501145876c620ec988ddbd39222dc48b1bd9c8a`;
`--check` passes. The previous signature is historical after these source edits.
Complete selected-domain and manual-configuration closure, Auto, strong symmetry,
clean-install, native/package and manufacturing acceptance remain open.

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

### Local half-integer extension and rational-q review (2026-10-02)

Local branch `codex/core-fractional-q-local` starts from published parent
`12692cd4de317e46df471c4078799d5dc4f879ef`. This work is uncommitted and unpublished.
Only the redundant global integer-q veto for the TLP q-only array route was
removed; local constructors and aggregate structural admission still own support.
Workbench enumerates its additional TLP factors from integral local q, including
half-integer global q. No general denominator-greater-than-two guard was relaxed.

For reduced `q=h/2`, odd positive h, and `m=3k`, the existing native cohort
constructor requires even `q_s=kh/2`, hence `4|k`. Use even `2<=Q<=q_s`,
`Q|q_s`, `pp>=2`, integral even `L_s=L/k>=2`, insert inlet, and the existing
transposition/shift gates. Set j maps slots by `h*j` and layers by `L_s*j`;
each branch joins `g=2*q_s/Q` whole parents of length `pp*L_s`.
Branch length is `2*q*pp*L/Q`; each phase has Q branches. No `k|Q` gate is added.

TDD first reproduced the blanket public rejection and missing catalog row.
All 33 affected tests subsequently passed: 20 `test_tlp_proper_q_route` tests,
nine `FractionalRouteDecisionTests`, and four `HalfIntegerQPPTransferTests`.
The new half-q matrix contains 13 public cases: h=1/3/5/7 with k=4 and
`(pp,L_s)=(2,2)/(3,4)`, plus five k=8/12 cases and proper/full local Q.
Independent node, occupancy, count, phase/polarity, signed edge and complex-EMF
formulas passed. Deliberately corrupted public seams, invalid local geometry and
weld-side entry still reject. Post-connection shifts and Workbench status passed.
The nine existing receipt-window tests also passed. Unchanged native controls,
fixtures and environment reuse prior scoped evidence; no full regression ran.

Fresh local source bindings ran the existing finite TLP/UWP engineering probes.
TLP passed 20 strict public calls, 24 raw captures and 16 target deployment
captures at h=1/3/5/7; all formula, mapped-role, strict-call and checkpoint gates
passed. UWP passed nine strict public calls at h=1/3/5, with zero Candidate calls;
all physical, capture/replay, owner, lineage/composition and retention gates passed.
Both families use six phases, four poles, eight global layers, four local layers,
neutral Regular transposition, insert inlet and zero shifts. The TLP 26-input
binding closure is `0e0f16cf8d6b8c4b8183557410c503b07872d5fc4884bfa19baa917e6e91a259`;
the UWP 41-input generation closure is
`76146b3b5c32d2dc42a43d51269262e8a833ccd58a13dbaada1aef1f613ce177`.
Source bytes stayed stable around all resolver/public calls and final readback.
These bind local working-tree bytes, not portable published-source acceptance
for Issue #4. Original probe failures are preserved: a TLP checkpoint variable
scope error before generation, and UWP capture-ledger contamination from resolver
preflight builds. Fresh private copies correct only those probe defects. UWP
still executes and separately counts those preflight hooks; actual returned-layout
capture and physical gates remain intact. Bounded supervisor review accepted
the probe-only corrections and saved readback.

A private exact-rational review checked native phase maps and one-pass SLP
pairing at `q=1/4,3/4,5/4,7/4` with m=3/P=4, `q=4/3` with m=5/P=6,
and `q=6/5` with m=7/P=10, all with L=4. Reduced `q=a/b` requires `b|P`
because `S/m=qP` is integral. Native phase feasibility also requires
`gcd(b,m)=1` for m=3 or supported odd m not divisible by three. The proposed
exact signed-belt repeat is `lcm(b,2)` poles: b gives integral repeated slot
displacement and two gives polarity repetition. This is a construction target,
not an admitted route. The current phase-array model additionally needs
integral `2qj`, so it does not lift b>2 with its existing rotation. In the three
`5/4,4/3,6/5` examples, phase-A source slots 0 and 1 share just one legal
forward neighbor (4/7/8) and one backward neighbor (12/34/76). Each uniform
direction has a two-source/one-target occupancy obstruction; mixed directions
fill counts but fail the unchanged SLP weld-direction gate. At q=1/4, slot 0
to opposite-sign same-phase slot 2 crosses two pole regions for either -1 or +2
travel. These are finite failures of the proposed one-pass family, not proof of
physical impossibility or all rational-q routes. A multipole constructor and
its Pattern identity remain an owner-review direction, without public admission.

Typical half-q connections and the rational pairing obstacles were generated
and visually checked under the excluded local folder
`Latest_Python_Files/Version 7.6/workbench_preview/fractional_q_local_20261002/`.
The half-q diagram's `q=3/2,m=12,P=4,L=16,Q=2` public layout has 24 equal
48-conductor branches and 1152 unique positions. It retains
`not strong symmetry layout` with `multi_phase_emf_mismatch`; EMF asymmetry is
diagnostic. No strong-symmetry, manufacturing, native/package or release claim
follows from these finite checks.

### Rational TLP half-belt complementary translation and admission (2026-10-02, local)

The owner accepted weld-side entry and requested a parameter formula giving
whole-family construction and admission, with the existing weld and
one-pole-boundary rules and no new pin-type rule. The closed
`tlp_rational_half_belt_translation` constructor now admits reduced q=a/b>1,
even a, odd b>2, native odd m (3, or odd m not divisible by three),
b|(2m-1), P=2bR, even L>=4 and `(Q,D,P2)=(q,pp,2)`.
Naa=qP=2aR; each branch has L conductor positions. The
[parameter proof](../Latest_Python_Files/Version%207.6/PATTERN_DIVIDER_FORMULA_SUPPORT.md#rational-tlp-half-belt-complementary-translation-family-2026-10-02-local)
derives H=q(m-1/2), the bijective slot map, four oriented layer walks,
equal phase counts, full occupancy and signed one-region legality. Every
actual weld spans one layer, has absolute pitch H and ds*dl=-H. Existing
ALLP/CLLP terminology and TLP grammar are retained.

Nine public parameter cases cover q=4/3,6/5,8/5,8/3,8/7,10/7,14/3;
m=3,5,11,13; P=6,10,12,14,28; and L=4,6,8. Independent exact belts,
occupancy/counts, signed edges and phasor sums agree with the theorem.
For q=4/3,m=5,P=6,L=4, all 160 positions occur once in 40 branches,
eight per phase, and every weld has pitch 6. A private independent reviewer
also checked eight stdlib-only cases covering 9,512 positions, including
composite b=15, m=23, R=2 and q>2, with no production imports or generation.
The exact EMF has magnitude L*cos(pi/(4m)); complex same-phase equality
fails, so public layouts retain `not strong symmetry layout` diagnostics.

TDD checks first reproduced the old rational divider/identity/catalog closure,
then passed the minimal formula, shared decision metadata, public dispatch
and validation changes. Two corruption controls preserve full occupancy and
branch length: one changes weld pitch to 7 while preserving phase and the
existing weld-direction rule; another swaps middle weld pairs between phases
while preserving pitch, direction, ordered TLP grammar and legal signed edges.
The latter initially returned a failed electrical report without rejecting it.
The independent reviewer identified the missing route gate; the existing
`_validate_selected_electrical` helper now rejects `mixed_phase_branch`,
while retaining EMF-asymmetry errors. Both failures were demonstrated before
the corresponding fixes. Outside-formula examples remain unsupported-yet;
invalid products, inlet adjustments, wrong inlet and unimplemented TP reject.

The legacy integer/half-q D*P2<=pp factor exclusion remains intact. Only the
separate b>2 maximal request is evaluated through the rational theorem.
Workbench enumerates exact integral Naa only, uses the resolver's required
weld inlet and marks successful strict public generation Validated, retaining
electrical diagnostics in its reason. Manual drafts remain exploratory.
The established post-connection shift contract is preserved and tested:
connection validation occurs before relocation, retained identity follows
the source connections, and relocated drawing pitches are diagnostic.

All 33 existing TLP/half-integer compatibility tests passed within the
39-test affected run (184.908 s). After the final rational gate and legacy
identity-call compatibility fixes, 71 focused tests passed (0.462 s): nine
rational route tests, 54 direct ordered-identity tests, six integration tests
and two existing fractional catalog decision tests. Applicable unchanged
compatibility evidence is reused; no full discovery/regression was run.
All 22 direct finite-status checks are also complete: 17 passed in the
sandboxed run; five provenance fixtures initially failed to create files in
Windows Temp, then passed outside the sandbox (0.251 s). No production
workaround was added. The refreshed 80-cell/860-request resources pass
`refresh_pattern_naa_division_layout.py --check`; rational cases were not
added to that finite integer scan.

The new source edits invalidate the prior private 26/41-input TLP/UWP
bindings as current-byte evidence. Those finite results remain historical;
their probes were not rerun and Issue #4's published-source acceptance is
still pending. The finite integer-status receipt was refreshed after the
source window closed, without adding rational scan cases. This local change
does not certify clean installation, current native/package behavior,
manufacturing tooling/clearance or broader platform/regression acceptance.
No source commit, push or remote Issue mutation was performed.

### Exploratory rational TLP multipole paths (2026-10-02)

Historical exploration below predates the closed uniform-pitch route above.
Its three finite witnesses use mixed weld pitches: q=4/3 has 6/7/8 slots,
q=5/3 has 7/8/9/10, and q=6/5/m=7 has 7/8/9/10. They are insufficient
for the owner's same-pitch requirement and do not establish formula admission.

The next local pass kept production source/admission unchanged and explored
partial uniform welding, rather than repeating the failed complete single-pass
matching. It found a two-layer `q=4/3,m=5,P=6` witness with two eight-conductor
N-to-S paths per phase; a cut removes a weld and gives four four-conductor paths.
All 80 positions are covered once. Its roles are `I,W,I,W,I,W,I` (weld-side
terminals), and its pure grammar overlaps TLP/TSP at two layers. Copying only
weld pairs into L layers gives `L*(h-1)+2` nodes per original `2h`-node path,
short of `L*h` by `L-2` terminal copies; no nondegenerate lift is inferred.

A necessary two-layer counting rule follows from the invariant
`c=sign*(-1)^layer`: every opposite-sign adjacent-layer edge preserves c.
For reduced `q=a/b`, native odd m, `gcd(b,m)=1`, even P and `b|P`, let A/B
be positive/negative conductor counts per phase in layer zero. Odd b gives
`A=B=aP/(2b)`; even b with `t=P/b` gives `A=t*(a+1)/2`, `B=t*(a-1)/2`.
Equal two-layer paths of `2h` conductors require `h|gcd(A,B)` and
`Naa=(A+B)/h=qP/h`. Connectivity remains a separate requirement. Thus
q=5/4/P=4 has A=3/B=2 and only h=1 at L=2. For even L>2 the component
count condition instead uses `h|(L/2)*A,(L/2)*B`; do not extend the two-layer
obstruction to every layer count.

Direct four-layer constrained path covers provide these new finite witnesses:

| q | m | P | `(Q,D,P2)` | Naa per phase | Branches / positions / edges |
| --- | --- | --- | --- | --- | --- |
| 4/3 | 5 | 6 | `(4/3,3,2)` | 8 | 40 / 160 / 120 |
| 5/3 | 5 | 6 | `(5/3,3,2)` | 10 | 50 / 200 / 150 |
| 6/5 | 7 | 10 | `(6/5,5,2)` | 12 | 84 / 336 / 252 |

Every branch has four conductors and `I,W,I` roles, starts N and ends S, and
passes exact coverage/occupancy/count, canonical phase/polarity, signed
one-region edges, ordered TLP grammar, nonzero individual EMF, and the existing
`validate_tlp_welds` geometry check. Top-bottom insertion returns distinguish
the complete four-layer layouts from the two-layer TLP/TSP overlap. The
q=4/3 and q=6/5 saved witnesses have TLP as their only global grammar match.
Weld travel is uniform in each actual adjacent layer pair; no edge is inferred
for an unused pair. Electrical equality is not a search or retention requirement.

The bounded construction hypothesis is odd b, `gcd(b,m)=1`, `P=2b`, L=4,
and `(Q,D,P2)=(q,b,2)`, so `Naa=qP=2a` and `qPL/Naa=4`. Select complete
equal open paths using the canonical phases and permitted TLP edge grammar;
the three finite solutions do not prove this full parameter domain. In the
`q=2/3,m=5,P=6` control, phase-A even-layer slot 7 is N; its only
opposite-sign odd-layer targets are 3/16. Signed steps -4/+9 each cross two
regions at `tau=10/3`. Ordinary and top-bottom TLP edges both change parity,
so this position is isolated for that canonical geometry. This is a scoped TLP
obstruction, not physical impossibility of all rational winding constructions.

The exploratory solver enumerated all eight adjacent-layer-pair direction
assignments for q=4/3/L=4/Naa=4 and q=2/3/L=4/Naa=4 without reaching its
search caps; neither had a phase-zero cover within this declared class. New
four-layer paths were built directly, not obtained from an incomplete lift.
Independent saved-path checks and three deliberate corruption controls
(duplicate occupancy, illegal long travel, wrong connection side) passed.
A read-only reviewer independently verified the counting rule, q=4/3 witnesses
and q=6/5 control. Typical complete phase-A paths and the review overview were
rendered and visually checked in the existing excluded local evidence folder.

All witnesses require weld-side entry, a different role parity from current
selected TLP routes. Their factor arithmetic is integral, but current public
resolution returns `rejected/invalid_dividers` for the rational Q, and ordered
identity retains `unsupported-domain` for b>2. These remain manual/exploratory
geometry witnesses, never `Validated`. Owner judgment about the inlet variant
and a sufficient parameterized constructor are still needed before admission.
This pass made zero public-generation calls and no production edits; previous
applicable route/receipt checks are reused for unchanged source. No commit,
push, remote Issue update or broader release validation was performed.

Unvalidated domains include complete integer coverage, deferred fractional
families, native Windows DPI/button flows, current packaged-resource acceptance,
manufacturing behavior, and clean installation on another machine. No complete
suite pass is claimed.

### UWP P2-only phase-local inlet repair (2026-10-02)

Issue [#11](https://github.com/HailinHuang/HairpinWindingTool/issues/11) fixes
the neutral Regular `(1,1,2)` inlet seed/order without changing connection
vectors or admission. At `q=2,pp=4,L=6,Naa=2,m=3`, public generation now gives
the following one-based entries, for both implicit and explicit dividers:

| Phase | Branch 1 | Branch 2 |
| --- | --- | --- |
| A | Slot 1 / Layer 1 | Slot 2 / Layer 6 |
| B | Slot 9 / Layer 1 | Slot 10 / Layer 6 |
| C | Slot 5 / Layer 1 | Slot 6 / Layer 6 |

The regression failed before the fix: Phase B entered at Slot 46/Layer 6,
then Slot 9/Layer 1. Six consecutive raw belts started B in S polarity;
the common N-to-S reversal exposed the wrong belt/order. The repair uses
each phase's first N slot from the construction phase map, seeds its partner
one `tau=m*q` pitch away, and orders the first-layer cohort first. The common
reversal still owns terminal orientation and signed-travel reversal.
The resulting tail lane is `(L/2) mod q`; see
`PATTERN_DIVIDER_FORMULA_SUPPORT.md` for the parameterized rule.

All 12 selected UWP tests passed: four new `UwpP2InletAnchorTests`, two
`UwpManualTranspositionTests`, and six relevant `UwpOddPhaseQppTests` for
P2 travel, PP-only configuration/travel, Q+PP configuration/construction and
body identity. New checks cover 72 native cases (`q=1..4`, `pp=2/4`,
`L=4/6/8`, `m=3/5/7`), mapped integer examples `(m,L)=(6,12),(9,12),(12,8)`
at global q=2, a mapped `q_global=1/2,m=6,L=8` example, and a nonzero
post-connection shift example. Assertions cover ordered inlets, complete
unique occupancy, equal branch counts, phase/polarity, signed edges,
Pattern identity and retained/electrical diagnostics as applicable.

An independent comparison with `origin/main` preserves each branch's entire
conductor-position set in 54 neutral native cases (`q=2/3/4`). First-layer
paths are identical; odd-indexed phase tails translate by the two-pole period
`2*m*q`, with unchanged signed edges. A separate 144-case insertion/weld-side
comparison at `q=1..4` preserves generation/failure classification: 72 insertion
calls pass and 72 weld-side calls keep their existing identity failure.
Independent read-only review found no remaining production correctness issue.

All 22 direct finite-status checks and two existing branch-label render checks
passed. The five status-provenance fixtures required a rerun with writable
Windows Temp access after sandbox permission errors; that rerun passed.
The regenerated source signature matches, with the same 80 cells and 860
requests and no classification/count changes in the isolated publication tree.
An offscreen cached-path render also confirms B1/B2 labels at the requested
positions; native Windows interaction and DPI behavior were not rerun.

The affected existing travel test now selects the reversed same-phase cohort
by `phases+1`, replacing the historical global branch ID 2. Its `m=9,L=4`
fixture asserts the established phase-set layer-allocation rejection. Baseline
replay confirmed 13 preexisting invalid m=9/L=2-or-4 assertions in that class;
12 remain in two unrelated proper-Q/short-weld test methods, outside this repair.
No whole-class or full-regression pass is claimed. The earlier 1,080-case P2
audit and other source-bound receipts, including half-integer ZPP, were not
rerun and need fresh binding after this production-source change.
Public interfaces, saved formats and manufacturing certification are unchanged.

### Same-formula SLP extension and welding-side clarification (2026-10-02, local)

The current exploration workflow first extends the established half-belt
complementary translation formula across Patterns and divider classes.
The owner accepted its four-layer SLP construction, then clarified that
same-layer welding is forbidden. Same-layer SLP returns remain insertion
pins; welding-end terminals do not change the path's I-W-I edge roles.
The [formula and proof](../Latest_Python_Files/Version%207.6/PATTERN_DIVIDER_FORMULA_SUPPORT.md#four-layer-slp-extension-of-half-belt-complementary-translation)
derive the two reciprocal-slot replacement paths, bijective full occupancy,
phase/polarity, equal counts, uniform H pitch, actual-pair weld directions
(-H,-H,+H), N-to-S terminals and one-pole-boundary legality. This adds no
pin types or numeric Pattern-identity whitelist. The route is registered
as `slp_rational_half_belt_translation`, with the existing maximal
`(Q,D,P2)=(q,pp,2)` domain and L=4 only.

Before implementation, six new SLP tests failed with unsupported generation
or a missing constructor (16 failures and two errors across their subtests).
After the constructor/resolver/identity/Workbench changes, neutral public
generation passes the ten parameter cells below. Independent test expectations
derive canonical phases/signs, complete occupancy, actual connection sides,
signed travel, weld-layer direction and nonzero EMF without trusting the
constructor's labels. Every same-layer edge must be insertion-side.

| q | m | P | L |
| --- | ---: | ---: | ---: |
| 4/3 | 5 | 6 and 12 | 4 |
| 6/5 | 3 and 13 | 10 | 4 |
| 8/5 | 3 | 10 | 4 |
| 8/3 | 5 | 6 | 4 |
| 8/7 | 11 | 14 | 4 |
| 10/7 | 11 | 28 | 4 |
| 14/3 | 5 | 6 | 4 |
| 16/15 | 23 | 30 | 4 |

The representative q=4/3,m=5,P=6,L=4 layout has 160 unique positions,
40 four-conductor branches, eight per phase, and 40 adjacent-layer welds
of H=6. A deliberate path corruption preserves unique occupancy and branch
length but makes one weld same-layer; public generation rejects it. Wrong
inlet, unproved layer/domain and other-divider controls remain rejected or
unsupported-yet as applicable. Workbench uses successful strict public
generation and displays retained non-strong electrical diagnostics.

The owner clarified that radial relocation is a CHW feature and does not
belong to this fractional-q construction exploration or its acceptance
criteria. The current checks apply to the constructed insertion/welding edges with zero radial
relocation. Phase-only shift compatibility retains the established pre-shift
identity/pitch reference. No radial-function change or new pin-type rule
remains in this delta.

The final affected rational run passes all 15 tests (2.266 s), including
the ten SLP and nine TLP parameter cells, direct welding corruption and
phase-only compatibility controls.
All 60 ordered-identity/integration tests pass (0.139 s). Applicable earlier
unchanged compatibility evidence is reused. Source writers then stopped;
the existing 80-cell/860-request finite status resources were regenerated
and `refresh_pattern_naa_division_layout.py --check` passes. The earlier
22 direct status tests were not all rerun; the finite status page does not
include fractional-q geometry. Earlier private TLP/UWP source bindings
remain historical after these edits.

The saved ten-Pattern maximal-split search at q=4/3,m=5,P=6,L=4 checks
the same H with each existing grammar, both inlet sides and all eight
actual-pair directions per side. TLP and SLP have complete covers; the
other eight Patterns have no phase-zero cover within this uncapped finite
method. This is not physical impossibility or complete route closure. A
parameter proof also excludes foreign-parent H weld seams when joining
intact TLP parents; alternative assemblies and other divider routes remain
open. New-formula exploration, including the separate q=5/3 method, is paused
until the existing formula's extension work is complete.

The complete phase-A candidate plot and corrected two-sided public connection
figure were rendered and visually checked in the existing ignored preview
folder. They are local evidence, not durable repository inputs. Complex-EMF
mismatch remains `not strong symmetry layout`, not a retention rejection.
No commit, push, remote Issue update, native/package, clean-install,
manufacturing or broader regression validation was performed in this pass.

### Half-integer integer-local divider expansion (2026-10-02, local)

The owner prioritized half-integer q while continuing existing formulas.
For q=h/2 with positive odd h, m=3k and even k give integer local
q_s=kh/2. With L=k*L_s, the existing phase-set transform is slot+h*j
modulo S and layer+L_s*j. The same Q/D/P2 tuple and existing local
constructor gates define the lift; no new native constructor or resolver
admission was added. Workbench now enumerates local integer factors,
deduplicates legacy fractional tuples and uses the shared decision for each.
See the [formula and proof](../Latest_Python_Files/Version%207.6/PATTERN_DIVIDER_FORMULA_SUPPORT.md#half-integer-q-lift-of-integer-local-divider-formulas-2026-10-02-local).

TDD first reproduced missing public SLP/SSP/TLP catalog rows and the missing
local-factor scope (four failures and one error). All four new
`test_winding_dividers.HalfIntegerLocalDividerTests` now pass (49.643 s).
The catalog controls prove that rejected SSP mixed-P2 rows remain rejected,
resolver-unsupported rows cannot run the public probe, 28 rows at
q=3/2,m=12,pp=4,L=16 are unique exact-factor products, and native/odd-k
catalog scopes remain unchanged. Phase-A drafts retain eight equal
24-conductor SLP branches, correct side metadata and adjacent-layer welds.

The independent lift oracle checks 11 strict public cells:

| Pattern | h | k | pp | L_s | `(Q,D,P2)` |
| --- | ---: | ---: | ---: | ---: | --- |
| SLP | 3 | 4 | 4 | 4 | `(2,2,2)` |
| SLP | 5 | 4 | 6 | 4 | `(2,3,2)` |
| SLP | 9 | 2 | 4 | 4 | `(3,2,2)` |
| SLP | 15 | 2 | 6 | 4 | `(3,3,2)` |
| SLP | 1 | 12 | 4 | 2 | `(2,2,2)` |
| SLP | 3 | 4 | 8 | 6 | `(3,2,2)` |
| SLP | 3 | 4 | 4 | 4 | `(2,2,1)` |
| SSP | 3 | 4 | 4 | 4 | `(2,2,1)` |
| SSP | 5 | 4 | 6 | 4 | `(2,3,1)` |
| TLP | 3 | 4 | 4 | 4 | `(2,2,2)` |
| TLP | 5 | 4 | 6 | 4 | `(2,3,2)` |

Expectations derive q=h/2, m=3k, P=2pp, L=k*L_s,
S=6*q_s*pp, tau=3*q_s and B=2*q_s*pp*L_s/(Q*D*P2).
Undoing each set rotation gives canonical belt floor(s/q_s), phase
3*j+belts%3 and sign (-1)^belts. Assertions check exact full position
occupancy, equal per-phase counts, alternating polarity, required N-to-S
terminals, independent nonzero phasor sums, every signed one-region edge,
adjacent-layer W pitch tau and one ds*dl per actual layer pair across phases.
Same-layer edges must be insertion-side on boundary layers. Two-layer
local overlap retains its existing qualification, not full identity proof.

The unchanged `HalfIntegerQPPTransferTests`, `FractionalRouteDecisionTests`,
`RationalSlpHalfBeltTranslationTests` and `RationalTlpHalfBeltTranslationTests`
pass all 28 tests (2.352 s). An independent read-only reviewer found no
blocking catalog issue. This is 32 focused tests in this pass; no new radial
function check, pin type, core admission or full regression was introduced.
Earlier unchanged ordered-identity, fixture and environment evidence is reused.
Representative strict public SLP/SSP/TLP branches at q=3/2,m=12,P=8,L=16
were rendered and visually checked under the existing ignored preview folder.
Each complete winding covers 2304 unique positions and retains non-strong
diagnostics; the plot is local evidence rather than a native UI acceptance run.

The unchanged half-q UWP sector-parent template was also specialized at
native odd m, L=2, D=pp, P2=2. The complete pairing uses pitch
u=(hm-1)/2 and gives h*pp two-conductor branches per phase, all adjacent
welds, canonical phase/polarity, one-region edges and fundamental magnitude
2*cos(pi/(2hm)). Six private cells `(h,m,pp)=(1,3,2),(3,3,4),(3,5,2),
(5,7,3),(7,11,2),(3,13,3)` pass independent exact arithmetic/occupancy
checks and agree with the current phase map. The q=3/2,m=3,P=8 diagram
covers all 72 positions. These are Candidate checks with zero public calls,
not production-family evidence: each branch has one W and zero I edges,
ordered identity is structurally overlapping, and body-pin/manufacturing
acceptance is unproved. The owner-confirmed D*P2<=2 exclusion is unchanged;
an owner decision was requested before any narrow exception.

The current whole-wave transfer has a separate method obstruction at D=2d,
d>1: repeated local-lane starts in distinct sectors translate to the same
opposite-half anchor. The q=3/2,m=3,P=8,L=4 example supplies the explicit
duplicate position. This is not a general UWP impossibility claim, and no
production fix or new formula was introduced for it.

After source writer closure, the 80-cell/860-request finite status resources
were refreshed and `refresh_pattern_naa_division_layout.py --check` passes;
prior 22 status tests remain unchanged scoped evidence. This finite integer
view was not expanded to half-q cases. Private earlier
26/41-input TLP/UWP receipt bindings remain historical. No clean install,
native/package, manufacturing, broad regression, commit, push or remote
Issue write was performed in this local pass.

### Local review and GitHub preparation (2026-10-03)

Independent read-only review of the seven changed production/test files
found no actionable algorithm blocker. It covered rational TLP/SLP domain
precedence and constructors, actual phase/coverage/identity/weld gates,
half-q TLP integer-local reuse, strict rational Workbench certification,
integer-local catalog enumeration and the inherited UWP inlet repair.
There was no new construction, admission change or radial investigation.

The exact staged-source run selects 146 tests: all 35
`test_tlp_proper_q_route` tests; the 17 half-q transfer/decision/local-catalog
tests; 12 affected UWP inlet/manual/PP/Q+PP compatibility tests; 60 ordered
identity/integration tests; and 22 finite-status tests. The initial run
took 289.359 s: 141 passed, while five provenance fixtures failed at
temporary-directory setup and cleanup under sandbox permissions. These
were environment errors, not failed production assertions. Only those five
were rerun with writable temporary access, and all passed (0.579 s).
All 146 applicable tests are now complete; no full discovery ran.

The first isolation path exceeded Windows' filename limit for four unchanged
ZPP draft files. Its Python/test blobs and the used TLP oracle match the
index; missing ZPP drafts are not inputs of this selected run. A short-path
raw Git-blob export then verified all 136 selected files byte-for-byte,
including every required fixture. Raw export also avoids checkout CRLF
filters on Windows BAT files. The complete export passes the existing
finite-status `--check`; no additional fixtures or ignore-policy changes
were introduced. Earlier unchanged fixture/environment evidence is reused.

All 15 staged delta paths remain explicitly allowlisted. Python compilation,
JSON parsing, whitespace and credential checks pass; no changed file exceeds
5 MB and no private previews, probe dumps, local settings, caches or outputs
enter the delivery. Only STATUS/VALIDATION gain this review record after
the tests; executable source and required fixture bytes stay the same.

GitHub main was fetched and confirmed at `9e39ffab1894e964b1b899162d8a475024e1a97a`,
with UWP PR #12 merged. AST comparison preserves main's complete UWP
constructor and inlet regression class exactly. The reviewed tree has 19
differences against main, including the earlier approved TLP/ZPP branch
and its two selected new files; no tracked file is deleted. Publication
should use current main as its base and preserve the complete reviewed
Core tree without rewriting shared history. The current local HEAD remains
`12692cd4de31`; these preparation steps do not commit, push or modify Issues.

The native UWP two-layer specialization remains an unapproved Candidate,
with its current factor exclusion intact. Two unrelated UWP methods retain
their known baseline-invalid m=9/L=2-or-4 cases and were not broadened into
this review. Historical private source receipts remain historical; current
finite checks do not establish portable whole-family, strong-symmetry,
clean-install, native/package, manufacturing or broad-regression acceptance.

Use full discovery only for broad impact, broader failures, or an explicit request:
`python -X utf8 -m unittest discover -s . -p 'test_*.py' -v`.
Restore offscreen overrides before a native application launch.
