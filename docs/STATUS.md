# Version 7.6 status

Version 7.6 is the supported development target. Current executable support comes
from the production resolver and successful public generation. This repository
selects current source/tests, required help resources, and regression inputs.

## Current integer closure review (2026-10-03)

The selected integer domain is closed at parameterized construction, accepted
exclusion and manual-capability level: q=1..6, even poles 4..16, even global
layers 4..12, phases {3,5,6,7,9,11,12,13}, with positive even local layers
for arrays. Its 1,302 geometries are scope targets, not 1,302 generated or
certified layouts. New local constructions
extend TLP even-gcd/odd-q P2 parent cuts, TSP complete-pass partitioning down
to one pass when B=L_s>=8, CP polarity-pool/quartet partitions, and SLP
physical N-belt passes with a separate weld-side cycle/gcd partition. The
CP necessary conditions are 2|Naa for odd H=L_s/2 and H|Naa for even H;
global layer admissibility remains a separate gate. Valid older CP/TLP
mother ordering and three-phase SLP paired-lane routes retain precedence.

Affected failures have been reviewed against actual public-mother and weld
oracles, then rerun successfully. All 16 previously omitted odd-local-q
TLP array mappings pass exact P2-mother cut and public-generation checks.
The existing finite status sample has 501 supported and 359 rejected
preflights across 860 requests; its current source signature passes.
The owner cancelled the historical UWP same-layer series-weld exception.
Integer local q_s, Q|q_s and D=P2=1 are rejected before native/array dispatch;
full-Q q_s>1 retains the BWP identity reason. Targeted checks close the six
earlier UWP boundary Candidate/public failures by accepted exclusion, and
preserve legal PP/P2 construction, inlet anchors and manual operations.
There is no remaining owner decision in this selected closure. A neutral
construction does not certify arbitrary manual TP; preflight, public
generation, Auto and strong symmetry remain separate.

Branch `codex/core-fractional-q-local`, HEAD `12692cd4de31`; current work is
uncommitted/unpushed. The earlier delivery review below predates these new
changes and is historical. No clean-install, native/package, manufacturing
or broad-regression acceptance is claimed.

## Workstreams

GitHub `main` is the shared baseline. Core / Workbench owns Pattern/divider
construction, branch routing, phase topology, identity, connection formulas,
resolver admission, exploratory Workbench and engineering validation.
Application / UI / JMAG owns main-application UI/configuration, JMAG integration,
result export, packaging and peripheral features. Coordinate shared interface
changes through the respective sections of
[Master Work Status](https://github.com/HailinHuang/HairpinWindingTool/issues/1).

## Implemented

- PyQt6 layout/phase/branch views, configuration/data export, winding-function and
  voltage-difference analysis, and inductance controls.
- Shared Pattern route decisions across admission, construction, main UI, and
  Workbench. `selected_integer_divider_route()` is a compatibility wrapper.
- Parameterized integer and selected fractional connection families, with separate
  supported, candidate, rejected, and unsupported admission states.
- Owner-approved native TLP proper-Q cohort joins ([Issue #7](https://github.com/HailinHuang/HairpinWindingTool/issues/7))
  and the ZPP `q_and_p2` exclusion ([Issue #8](https://github.com/HailinHuang/HairpinWindingTool/issues/8)).
  Owner-approved integer-global-q TLP phase arrays now resolve through local
  constructors and full-array gates; local q-only factors are visible in
  Workbench. See [Issue #9](https://github.com/HailinHuang/HairpinWindingTool/issues/9).
- Exploratory Workbench schema-v3 packages; manual completion does not certify routes.
- Local integer-q closure extends CP/TLP Q-only public parents by consecutive
  PP cuts, and extends SLP's existing proper-Q P2 lane regrouping to D=1
  when pp is even. Full-Q TLP phase arrays retain valid legacy mappings first,
  then may use admitted same-factor local Q-parent cuts. Scoped public tests
  pass. Selected-domain parameterized closure and manual-capability
  classification are complete; actual configured gates and Auto stay separate.
- Owner-approved integer-local-q ZPP actual-lane endpoint cyclic permutation
  and gcd partition now has public admission. It uses configured full-Q public
  parents, keeps successful older routes and existing owner exclusions, and
  validates complete signed travel plus actual adjacent-layer weld pitch/direction.
  TSP/TLP odd Naa is explicitly excluded for integer local q and positive even
  local layers under their current grammar, by layer-zero polarity counts.
- [UWP P2-only inlet anchors](https://github.com/HailinHuang/HairpinWindingTool/issues/11)
  now order each phase's positive-belt first-layer entry before its last-layer
  entry. At `q=2,pp=4,L=6,Naa=2,m=3`, B1 is Slot 9/Layer 1 and B2 is
  Slot 10/Layer 6. The seed rule is parameterized; connection vectors and
  production admission are unchanged.
- Local unpublished half-integer TLP q-only cohort extension: q=h/2 (odd h),
  m=3k with 4 dividing k, even Q dividing q_s=kh/2, even L_s=L/k>=2,
  and pp>=2. Thirteen public examples pass independent formula checks;
  non-strong electrical diagnostics remain visible. Other rational-q
  constructions need their own canonical phase/connection rules.
- Local half-integer Workbench expansion reuses existing integer-local
  divider formulas when q=h/2, m=3k and k is even. SLP/SSP/TLP public
  examples preserve full occupancy, phase, adjacent-layer welds and
  insertion-only same-layer returns. Each local formula retains its own
  conditions; enumeration does not widen resolver admission.
- Local rational TLP half-belt complementary translation formula: reduced q=a/b>1, even a, odd b>2,
  native odd m, b|(2m-1), P=2bR, even L>=4, and `(Q,D,P2)=(q,pp,2)`.
  The bijective slot pairing and four layer walks give complete coverage,
  adjacent-layer welds of pitch H=q(m-1/2), uniform geometric direction,
  N-to-S terminals and legal one-region edges. Strict public generation and
  Workbench status pass focused checks; no new pin-type rule was added.
  Complex-EMF mismatch remains `not strong symmetry layout`.
- The same half-belt complementary translation formula now has an owner-accepted
  four-layer SLP replacement at maximal `(q,pp,2)`. Same-layer boundary
  returns are insertion pins; all actual welds join adjacent layers. Both
  rational lap routes retain valid phase-only shifts. Radial relocation belongs
  to CHW and is outside this construction exploration.
- [Finite divider-status provenance and navigation](https://github.com/HailinHuang/HairpinWindingTool/issues/2)
  refreshed for the existing six geometries: 80 cells and 860 resolver requests.
  The JSON, page and summary share a 14-file local Python source signature;
  navigation stays within repository resources.

## Limitations and blockers

- The finite status view covers only its listed geometries/settings. Counts are
  preflight requests; selected public examples do not establish family-wide or
  complete integer-domain support. Recheck its source signature before reuse.
- Half-integer ZPP has fresh finite evidence for the six-phase construction
  described below. Other geometries remain unverified; local probe outputs and
  receipts are excluded from the repository selection.
- Local half-integer TLP/UWP finite checks pass, but Issue #4's portable
  published-source acceptance is pending. Other rational-q one-pass SLP examples
  have explicit occupancy/weld-direction or pole-region obstacles; these do not
  establish physical impossibility or general unsupported winding domains.
- Earlier rational TLP graph witnesses have mixed weld pitches. They do not
  prove the owner's same-pitch requirement. The new closed formula admits only
  its stated parameter family; q=5/3 and q=6/5/m=7 remain unsupported-yet for
  this route. Other rational geometries/constructions remain open.
- Extend the established formula across other Patterns/divider classes before
  beginning a new formula. TLP even-L and SLP L=4 maximal routes are admitted;
  eight other Pattern grammars have a method-negative finite maximal example.
  Intact TLP parent joins lack a foreign-parent H seam. Other assemblies,
  SLP layer counts and divider routes remain open; no universal closure is claimed.
- The half-integer UWP L=2 sector-parent specialization `(q,pp,2)` is
  Candidate only. It has complete geometry but one weld and zero insertion
  edges per branch; the existing owner-confirmed D*P2<=2 exclusion remains.
  An owner decision is pending before any admission exception.
- The preceding private TLP/UWP 26/41-input receipt bindings are historical
  after the shared source edits for rational admission. Current scoped tests
  and the refreshed finite-status signature cover this local delta; they do
  not refresh portable published-source or broader acceptance.
- The owner selected the first integer-q closure domain on 2026-10-03:
  q=1..6; even global poles 4..16 and layers 4..12; phases
  {3,5,6,7,9,11,12,13}. For m=3k arrays, require a positive even local
  layer count L/k; local two-layer results retain their identity qualification.
  Include the union of global and integer-local Q factors, all D|pp and
  P2 in {1,2}, with route exclusions preserved. Phase shifts are covered by
  parameter rules and boundary/counterexample checks; manual Regular, Times,
  Interval, pole-group payloads and inlet/outlet adjustments are classified
  by each route's actual capability. Construction or owner-accepted explicit
  exclusion closes a route; Candidate/unsupported-yet does not. Auto and
  strong symmetry are separate. This domain is selected, not yet closed.
- The ZPP endpoint/gcd formula covers its stated integer-local parameter domain
  subject to successful configured parents and all public gates. Manual payloads
  still need route-specific capability classification. Fixed-global aggregate
  boundary diagnostics remain separate from canonical phase-set admission.
  The TSP/TLP odd-Naa proof does not address a different grammar, fractional
  local q or odd local layers. Other integer Pattern/route gaps remain open.
- Current packaged/native Windows acceptance, manufacturing validation, broad
  regression, cross-platform acceptance, and clean dependency installation are
  unverified. Earlier package smoke predates current source.
- One optional historical UWP fixture is absent; its existing test explicitly skips.

## Next priorities

Track these as discrete GitHub Issues with focused acceptance:

1. Core: [Close the selected integer-divider domain](https://github.com/HailinHuang/HairpinWindingTool/issues/3),
   with parameterized constructions or owner-accepted exclusions and route-specific
   configuration capabilities. The first domain is selected; closure is in progress.
2. Core: [Complete source-bound half-integer TLP/UWP validation](https://github.com/HailinHuang/HairpinWindingTool/issues/4),
   with local finite evidence complete and portable published-source acceptance pending.
3. Application: [Establish packaged/native acceptance tied to current source](https://github.com/HailinHuang/HairpinWindingTool/issues/5).

GitHub [Issues](https://github.com/HailinHuang/HairpinWindingTool/issues) are the
authoritative backlog. This list states priorities, not a second task database.

Delivery coordination lives in [Master Work Status](https://github.com/HailinHuang/HairpinWindingTool/issues/1),
separate from the engineering Issues. Keep its update time, task/phase,
branch/commit, unpushed changes, validation, blockers and next action current.
Use live Git for branch/commit and unpushed state.

## Last meaningful validation

On 2026-10-03, 44 new/affected checks passed for ZPP endpoint/gcd admission,
TSP/TLP odd-Naa rejection, signed-evidence corruption, older ZPP paths and the
existing finite-status view. Together with 61 reused unchanged engineering
checks, this local pass has 105 distinct passing checks. The 14-file source
signature and exact resources passed `--check`. The six-geometry view now has
479 supported preflights; this does not establish the selected integer domain's
closure or certify strong symmetry. See [VALIDATION.md](VALIDATION.md).

The finite-status refresh passed all 22 direct status tests, including five new
provenance/navigation checks, and `refresh_pattern_naa_division_layout.py --check`.
The six geometries and request count are unchanged. Four TLP status assertions
now follow the established shift/manual-transposition admission contract;
production rules, inlet rejection and generation certification gates are unchanged.

On 2026-10-02, 31 focused tests passed from an isolated copy of the staged files.
Runtime pins/imports, required fixtures, help navigation, staged secret/size checks,
and independent source comparison were checked. One stale UI test expectation
was corrected; production code was unchanged. See [VALIDATION.md](VALIDATION.md).

Also on 2026-10-02, the source-bound ZPP probe passed for `h=3,5,7`,
`q_global=h/2`, six phases, four poles, eight layers, and dividers `(h,2,1)`.
Nine strict public calls passed under neutral Regular transposition, zero shifts,
and weld-side entry. Layouts retain `not strong symmetry layout`; independent
mapped connection roles cover all edges despite diagnostic half-coverage from
the native global role analyzer. The 29-file evidence readback passed. This is
finite formula evidence within existing admission; production admission and
universal route closure were not expanded. See [VALIDATION.md](VALIDATION.md).

The native TLP proper-Q implementation passed 17 focused route tests, including
exact reviewed-path comparison, the bounded formula matrix, nonzero shifts and
the mapped-array admission boundary. Eighteen targeted ZPP/related route tests
passed for the named exclusion, precedence and unaffected controls. A separate
48-case private multiphase review passes the connection-stage edge checks in
all cases. The earlier 22/26 safe/unsafe classification was a false positive:
fixed slot-zero pole intervals were checked after rigid phase-set rotation.
The 52 two-boundary records remain coordinate diagnostics; they do not impose
`k=m/3` dividing Q. Owner-approved integer-global-q arrays now pass strict
public generation for the same 48 cases, plus local-only Q factors, full local
Q and 15/18 phases. The subsequent local half-integer cohort extension
uses integral even local q and is unpublished. The six-phase example retains a global
`multi_phase_emf_mismatch`, so local phase-set identity does not establish
strong symmetry. Workbench preserves Auto pending and retained-layout errors
while marking successfully generated routes Validated. These findings do not
certify strong symmetry or a release. See
[VALIDATION.md](VALIDATION.md) and [Issue #9](https://github.com/HailinHuang/HairpinWindingTool/issues/9).

At 2026-10-02 20:15 CST, local branch `codex/core-fractional-q-local` has an
uncommitted half-integer TLP cohort extension from parent `12692cd4de31`.
All 33 affected route tests and nine receipt-window tests pass. Fresh bound
finite probes pass 20 TLP and nine UWP strict public calls with final readback;
their private probe corrections preserve all construction gates. A representative
half-q connection figure passes public occupancy/count/identity checks and
retains EMF diagnostics. Six other rational-q cases were checked against an
explicit one-pass SLP model; its finite obstructions and figures await owner
judgment about a multipole construction direction. No source was committed or
pushed, and no remote Issue was updated for this local pass. Broader regression,
native/package, clean-install and manufacturing acceptance remain unverified.
See [VALIDATION.md](VALIDATION.md) for formulas and evidence boundaries.

At 2026-10-02 20:46 CST, the same local branch has three complete four-layer
rational TLP geometry witnesses: q=4/3 and 5/3 at m=5/P=6, and q=6/5 at
m=7/P=10. They cover 160/200/336 unique positions with equal four-conductor
N-to-S branches, legal signed edges and uniform welding in actual layer pairs.
Independent checks, deliberate corruption controls and bounded saved-path review
passed. The q=2/3/m=5/P=6 control has an isolated conductor for this TLP
geometry. Weld-side entry is an unresolved candidate variant; the three finite
solutions do not establish universal rational support. Production files and
admission are unchanged in this exploration; no public generation, commit,
push or remote Issue update was performed. Connection figures and formulas are
recorded in [VALIDATION.md](VALIDATION.md).

At 2026-10-02 21:33 CST, the owner-accepted weld-side TLP variant has a
parameterized half-belt complementary translation constructor and admission on the same local branch.
The q=4/3/m=5/P=6/L=4 example publicly covers 160 unique positions with
eight branches per phase and weld pitch 6 throughout. The full formula,
independent proof, focused positive/rejection tests, phase-corruption gate and
existing post-connection-shift contract are recorded in [VALIDATION.md](VALIDATION.md).
All 22 direct finite-status checks are complete, including five Temp fixtures
rerun outside the sandbox; the refreshed source signature matches. Earlier
private TLP/UWP source bindings are historical after these shared-source edits.
The source remains uncommitted/unpushed; no remote Issue was changed. Broader
regression, native/package, clean-install and manufacturing checks remain unrun.

The 2026-10-02 UWP inlet repair passed 12 focused rule/compatibility tests,
including 72 native cases, three integer phase-set examples, one fractional-q
phase-set example and a post-connection shift check. Independent comparison
preserved per-branch position sets in 54 cases and generation/failure classification
in 144 insertion/weld-side cases. The finite status resources were regenerated
for the repaired source. Earlier source-bound formula receipts, including the
ZPP receipt above, require a new source binding before reuse against this source.
Full regression and packaged/native acceptance were not rerun.

At 2026-10-02 22:54 CST, the same local branch has the owner-accepted SLP
extension of the existing half-belt complementary translation formula.
The ten SLP parameter cases, nine TLP parameter cases and rejection controls
pass in 15 rational route tests; 60 ordered-identity/integration tests also pass.
The owner's no-same-layer-welding rule applies to the constructed paths.
Radial relocation is a CHW feature outside this exploration; the briefly
added checks are excluded from the final delta. Phase-only shift compatibility
remains. The public zero-shift SLP example has 160 unique positions and
40 adjacent-layer welds, with insertion-only same-layer returns.
The 80-cell/860-request status resources were refreshed after the source
writer window closed, and their signature check passes. Prior 22 status-test
results remain scoped historical evidence, rather than a new full rerun.
Branch `codex/core-fractional-q-local` remains at parent `12692cd4de31`
with 15 changed tracked files, zero staged files, and no new durable files.
No commit, push or remote Issue update was performed. Other Pattern/divider
extensions of this formula remain open, so new-formula exploration stays paused.
Native/package, clean-install, manufacturing and broader regression checks
remain unrun. See [VALIDATION.md](VALIDATION.md).

At 2026-10-02 23:51 CST, the owner-prioritized half-integer pass extends
Workbench enumeration to existing integer-local factors with q=h/2,
m=3k, even k and integral local q_s=kh/2. No core constructor or resolver
rule changed in this pass. Four new tests pass, including 11 strict public
SLP/SSP/TLP parameter cases; 28 affected compatibility tests also pass.
Complete representative branch plots were rendered and visually checked.
After source writer closure, the 80-cell/860-request finite status view was
refreshed and its source-signature check passes. Earlier signature claims
above describe their own snapshots. The UWP two-layer sector-parent Candidate and the existing
whole-wave transfer's D>2 collision are recorded with parameter proofs.

Local Master work state: task/phase is completed half-integer formula
extension with scoped validation; branch `codex/core-fractional-q-local`, parent commit
`12692cd4de31`; 15 tracked files changed, zero staged and no new durable
files; all current changes remain uncommitted/unpushed. The pending decision
is whether to accept the UWP two-layer, zero-insertion-edge specialization
and permit its narrow family to change the existing splitting exclusion.
Next action is to continue existing half-q formulas across the remaining
Pattern/route classes; that work can proceed independently of the UWP decision.
No commit, push or remote Issue update was performed. Clean-install,
native/package, manufacturing and broader regression acceptance remain unrun.

At 2026-10-03 12:10 CST, local review and GitHub upload preparation are
complete. Independent read-only review found no actionable algorithm blocker
in the seven changed production/test files. The 146 applicable scoped tests
are complete: 141 passed in the initial selected-source run and five
status-provenance tests passed after rerunning with writable temporary access.
Exact staged Python/test bytes were checked; a complete short-path export
contains all 136 Git blobs and required fixtures. Syntax, JSON, explicit
allowlist, credential/size, whitespace and finite-source signature checks pass.
No production repair or new route admission was added by this review.

Local Master work state: task/phase is reviewed source delivery awaiting
publication instruction; branch `codex/core-fractional-q-local`, HEAD
`12692cd4de31`; 15 changed files are staged and remain uncommitted/unpushed.
Current remote main is `9e39ffab1894e964b1b899162d8a475024e1a97a`:
UWP PR #12 is merged. Its UWP constructor and inlet regression class are
preserved exactly in this source. The local TLP branch and main have
diverged from `d761034`; there are 19 source-tree differences against main,
including the previously delivered TLP/ZPP work and its required fixture.
Prepare publication on a new branch from current main using this reviewed
Core tree, preserving shared history and avoiding a duplicate UWP repair.
After authorized publication, update the existing Master Work Status #1
Core section and the relevant engineering handoff; do not create another
Master Issue or overwrite the Application/JMAG section.

There is no source-delivery blocker. The unapproved UWP two-layer
specialization remains Candidate and its exclusion is unchanged. Existing
invalid m=9 fixtures in two unrelated UWP methods are outside these checks.
No full regression, clean install, native/package, manufacturing or universal
route certification is claimed. No commit, push or remote write was performed.
