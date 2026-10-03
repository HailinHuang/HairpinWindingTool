# Pattern Route Rejection Reasons

Version 7.6 baseline registry, copied from Version 7.5 on 2026-09-24.

## Status contract

Manual transposition is no longer rejected merely because it lacks an Auto
recipe token or is non-neutral. The implemented constructor and generated-path
checks decide the case. Phase/radial layout shifts are applied after validated
connections across all ten Pattern families; shifted endpoints are not a new
connection-identity rejection. Unique occupancy, phase/pole sign and electrical
retention still apply, so zero fundamental EMF can reject a particular shift.
The current rational TLP/SLP half-belt translation constructors require
adjacent-layer welds. Neutral four-layer SLP same-layer returns are insertion
pins, never welds. Radial relocation belongs to CHW and is outside this
fractional-q exploration; no additional radial rejection rule is introduced.
Inlet restrictions remain. Fixed TSP sector/pass-partition
formulas report that they have no transposition implementation; other explicit
constructor limitations and actual generated geometry failures remain errors.


- `rejected`: an explicit Pattern exclusion or failure to generate the requested case. This replaces `unsupported`, `Unsupported`, and `Eligible but rejected for this case` in the current route catalog.
- `unsupported-yet`: no implemented admission route. It is not an explicit rejection and must remain distinct.
- `not strong symmetry layout`: retained EMF-asymmetric layout; EMF mismatch alone is not a rejection reason.
- `Default` and `Validated`: successful generation under the applicable route checks, not manufacturing certification.

Every rejected record must retain its exact reason. Show it in the catalog tooltip and in the editor's `Reject reason` text. Never replace a detailed generator exception with a generic unsupported message.

## CP polarity-pool boundary (2026-10-03)

For integer local q_s and positive even L_s, put H=L_s/2. CP's current
canonical insert grammar requires Naa divisible by H when H is even,
or by two when H is odd. Full equal polarity pools, adjacent-layer W and
I span H give the count; no pin-type rule or EMF symmetry assumption is
added. The resolver reports `cp_polarity_pool_rejected` with the actual
q_s, L_s, H and Naa. Keep invalid-factor, no-divider and global/local
layer gates distinct. Legal larger-layer cases use configured public
quartet mothers rather than the old raw mother with duplicate/missing nodes.
See the [proof](PATTERN_DIVIDER_FORMULA_SUPPORT.md#integer-closure-extensions-and-review-boundary-2026-10-03).

SLP's long weld-inlet rotation is a method-negative result, superseded for
the admitted P2 family by insertion-only cycle/gcd joins and W cuts.

## UWP adjacent-layer weld requirement (2026-10-03)

The owner cancelled the historical same-layer series-weld exception.
For positive integer local q_s and Q|q_s, the current `(Q,1,1)` construction
is `rejected` with `uwp_factor_rejected` before native/array generation,
including implicit NoDivider and manual/shifted inputs. NoDivider and
proper-Q require a same-layer series junction; no historical metadata can
exempt that weld. Full-Q q_s>1 keeps the established BWP identity exclusion.
The D*P2<=2 splitting gate and legal adjacent PP/P2 routes remain distinct.
This rejects the registered construction by owner decision; it does not
prove every possible physical UWP layout impossible. Earlier dated series
authorization below is historical and superseded.

The current TSP complete-pass rule also supersedes the dated two-pass method
boundary below: one complete pass is allowed when B=L_s>=8, while B>=8,
even Naa and the actual fixed-recipe configuration gates remain mandatory.

## TSP complete-pass closure (2026-09-29)

The user approved top-bottom insertion returns in either circumferential
direction, subject to intact ordinary spiral passes, uniform normalized weld
direction, and at most one pole-region crossing per edge. This supersedes the
older TSP return-direction decision recorded below. `tsp_spiral_pass_partition`
now closes the saved `(1,2,1)`, `(2,1,1)`, `(1,2,2)`, `(2,2,2)`, and `(2,4,1)`
cases through a parameter-derived construction, not a tuple whitelist.

Use the [current formula and domain](PATTERN_DIVIDER_FORMULA_SUPPORT.md#tsp-regular-manual-route-closure-2026-09-29).
The fallback requires integer global q, an even Naa split into two outer-layer
cohorts, and at least two complete local-layer passes per branch. One-pass
cuts remain outside this constructor; that limit alone is not an impossibility
proof. Separately, the user set a Pattern-wide Regular TSP floor of eight
conductors per branch. The resolver computes `B=2*q*pp*L/Naa` and rejects
`B<8` for positive integer global q, before default or specialized routes
and before phase-set array deployment. Thus `(2,4,2)` at q=2/pp=4/L=4 has
`B=4` and is `rejected` with this exact reason. The eight-conductor cutoff
is an engineering decision; the fallback's two-pass bound is `B>=2*L_local`.
Above that floor, existing defaults and specialized routes keep precedence. Fractional-global-q
arrays remain unsupported for this new family. Non-neutral settings reject
with the existing exact configuration reason. EMF-only asymmetry is retained.

Earlier dated `unsupported-yet` observations below remain historical evidence
for their named constructors; this fallback supersedes the total-route status
where its domain applies. No saved manual draft is retroactively certified.

## Explicit rule exclusions

Half-integer UWP `(q,2,1)` is implemented by discrete whole-wave transfer.
PP-divider=2 must divide pole pairs. A source without a second inlet cohort
(q=1/2) produces only an unchanged alias and is not admitted as a new transfer.
Source absence for BWP/SSP/SLP/ZLP/TSP/ZPP/CP leaves this P2=1 target
`unsupported-yet`; do not copy their source P2 rejection onto the target.
TLP now has one registered full-Q even-Q adjacent-pair route for `(Q,1,1)`;
other TLP P2=1 targets still need their own admitted construction.
For legacy TLP integer/half-q pass cuts, a target that violates
`pp-divider * P2-divider <= pp` is an explicit factor rejection. The separate
b>2 maximal rational request `(q,pp,2)` is considered by the new
`tlp_rational_half_belt_translation` parameter theorem instead; exempting its factor
shape does not admit geometries outside that theorem. Other targets within
the legacy bound still require a registered route.
The registered TLP `(2,D,2)` route cuts public `(1,D,2)` parents for even
integer q, `D>1`, `D|pp`, `2D<=pp`, and sufficient even local layers. A parent
placement or short local-layer failure remains `unsupported-yet`; it is not a
new blanket TLP rejection. Two distinct adjacent inlet lanes are permitted
when the complete route passes independent checks.
For every ZPP tuple with `P2=2`, an odd positive integer effective q remains
an owner-approved explicit exclusion. Its original q=2*Q rationale described
the older constructor; the new endpoint/gcd formula does not use Q*P2=q
as a universal length condition. The owner explicitly retained this boundary.
Phase-set routes apply this check to each set's local q; a fractional global q
is not itself classified as odd.
LPP's existing factor exclusion still applies. EMF asymmetry is not a transfer
rejection. The executable owner is `half_integer_q_pp_route_decision`.

| Registry ID | Pattern / condition | Reject reason | Decision provenance | Code owner |
| --- | --- | --- | --- | --- |
| BWP-P2 | BWP, P2=2, any q-divider or pp-divider | BWP does not support P2-divider=2. | User-confirmed reject, 2026-09-21. | `get_winding_pattern.py`: `pattern_rejects_divider_tuple`, `divider_exclusion_reason` |
| SSP-P2 | SSP mixed P2=2 tuples other than `(1,1,2)` | SSP mixed P2-divider formulas remain excluded; only the distinct reflected P2-only `(1,1,2)` construction is registered. | Earlier blanket reject narrowed by the user's exact-equivalence review request, 2026-09-22. | Shared exclusion functions and route resolver |
| SSP-P2-ODD-Q | SSP `(1,1,2)` with positive odd integer q | SSP `(1,1,2)` reflected construction requires two equal q-lane cohorts; odd integer q cannot be divided into those cohorts. This rejects the registered construction for this geometry, not every possible physical layout. | User requested an explicit reject reason for the current construction, 2026-09-23. | `get_winding_pattern.py`: `pattern_rejects_divider_tuple`, `divider_exclusion_reason` |
| ZPP-P2-ODD-Q | Every ZPP `(Q,D,2)` tuple when effective q is a positive odd integer | ZPP P2=2 retains the owner-approved exclusion for odd positive integer effective q. This is an admission boundary, not a proof against every possible physical layout. | Original boundary 2026-09-29, explicitly retained with the endpoint/gcd family on 2026-10-03; phase-set checks use effective local q. | `get_winding_pattern.py`: `pattern_rejects_divider_tuple`, `divider_exclusion_reason`, `resolve_pattern_route` |
| ZPP-Q-P2-SHARED | ZPP `q_and_p2`: `(Q,1,2)` with `Q>1` | q and p2 share same route | User-confirmed reject, 2026-10-02. This reason takes precedence for the named divider type. | `get_winding_pattern.py`: `pattern_rejects_divider_tuple`, `divider_exclusion_reason`, `resolve_pattern_route` |
| ZLP-Q | ZLP, Q-divider greater than 1, with any PP/P2 factors | ZLP does not support Q-divider greater than 1. | User-confirmed general exclusion, 2026-09-23; route notes in `pattern_rule_drafts/route_notes.jsonl`. | Shared exclusion functions and route resolver |
| CP-NO-DIVIDER | CP `(1,1,1)` | CP does not allow the no-divider (1,1,1) route. | User-confirmed general exclusion, 2026-09-23; route note in `pattern_rule_drafts/route_notes.jsonl`. | Shared exclusion functions and route resolver |
| CP-LAYER-MULTIPLE-OF-4 | CP with a nonpositive layer count or a layer count not divisible by four | CP requires a positive layer count divisible by 4. | User rule added 2026-09-25. | `get_winding_pattern.py`: `_cp_layer_admission_reason`, `resolve_pattern_route`, `_validate_branch_decomposition` |
| UWP-FULL-Q-ONLY | UWP `(q,1,1)`, q>1 | UWP q-only with q-divider=q is the same as BWP q-only with q-divider=q; use the BWP route. | User-confirmed reject, 2026-09-21. | Shared exclusion functions, with actual q supplied |
| UWP-PP-P2 | UWP, pp-divider * P2 not in {1,2}, integer or fractional q | UWP pp-divider and P2-divider share the same splitting allowance; their product must be 1 or 2. | User-confirmed reject, 2026-09-21. | Same shared exclusion functions |
| LPP-FACTORS | Every LPP tuple other than `(1,pp,1)`, where `pp=poles/2` | LPP admits only its full-PP loop construction. Smaller PP factors reverse weld travel inside a layer pair in the reviewed construction; Q/P2 factors are outside the approved loop rule. | User-confirmed rejection, 2026-09-24, after review of q=2, pp=4, L=4 paths. This is the Pattern construction rule, not a manufacturing impossibility claim. | `pattern_rejects_divider_tuple`, `resolve_pattern_route`, `_validate_branch_decomposition` |
| TLP-PP-P2-SHARED | Legacy TLP when `pp-divider * P2-divider > pp`; excludes the separate b>2 maximal rational request `(q,pp,2)` from this factor veto | TLP's legacy pp-divider and P2-divider share the available pole-pair division; their product cannot exceed `pp=poles/2`. | User-confirmed route rejection note, 2026-09-24, for `(1,4,2)` at `pp=4`. The 2026-10-02 rational family uses its own closed constructor and resolver theorem; integer/half-q exclusions are unchanged. | `pattern_rejects_divider_tuple`, `divider_exclusion_reason`, `resolve_pattern_route` |
| TSP-TLP-ODD-NAA | Current TSP/TLP grammar; integer local q_s>0, positive even L_s, legal Q|q_s, D|pp, P2=1 and odd Naa | Layer-zero N/S pools each have q_s*pp nodes; B/L_s=2*q_s*pp/Naa forces Naa/2 branches of each polarity. Odd Naa cannot cover both pools. | Owner-accepted parameter rule, 2026-10-03; other grammars, fractional local q and odd local layers are outside the proof. | `resolve_pattern_route`, public branch decomposition; retain the TSP B>=8 floor |

These entries describe software rules, not proof of physical impossibility. Preserve the exact tuple and geometry with any report. Internal identifiers such as `unsupported_branch_decomposition` remain diagnostic API codes, not display statuses.

## Confirmation sources

Confirmation provenance is stored here so an implementation decision is not
mistaken for a user-approved reject. Session records are local development
evidence, not application inputs.

| Registry ID | User decision | Source |
| --- | --- | --- |
| BWP-P2 | BWP P2=2 must be rejected rather than unsupported. | 2026-09-21 session `01a0c3d6-b6d7-7a50-9115-b130f2b2fddb`, user records 9 and 298 |
| SSP-P2 | Earlier blanket rejection for overlap; superseded for the distinct P2-only construction after the user requested exact comparison and Validated status when distinct. | Earlier: 2026-09-22 session `01a0c736-8dff-7740-8747-ef762ca6b02e`, user record 626. Current: saved-path and Auto comparison in `workbench_preview/ssp_p2_equivalence/`. |
| SSP-P2-ODD-Q | Reject odd integer q for the registered equal-cohort mirror construction while preserving the possibility of another physical construction. | 2026-09-23 user request following the q=3, 72-slot, eight-pole Workbench review. |
| ZPP-P2-ODD-Q | Reject all selected ZPP P2=2 tuples for a positive odd integer effective q; do not classify fractional q as odd, and evaluate phase-set routes with local q. | User-directed V7.6 migration correction, 2026-09-29. |
| ZLP-Q | Reject Q-divider in ZLP across q-only and mixed formulas. | User confirmation in the 2026-09-23 status-update request; screenshot rows 55, 57-60 and their saved route notes. |
| CP-NO-DIVIDER | Reject CP with no divider. | User confirmation in the 2026-09-23 status-update request; screenshot row 61 and its saved route note. |
| CP-LAYER-MULTIPLE-OF-4 | CP is valid only when the layer count is positive and divisible by four. | User instruction in the 2026-09-25 V7.6 Pattern Advance request. |
| UWP-FULL-Q-ONLY | Full-Q q-only duplicates BWP full-Q q-only, therefore reject. | 2026-09-21 session `01a0c429-f2dc-7ef3-ae82-5c3e2d074bfa`, user record 551 |
| UWP-PP-P2 | pp-divider and P2 share one allowance; their product can only be 1 or 2. | Same session, user records 9 and 519 |
| LPP-FACTORS | Supersedes the earlier PP-only scope: reject all LPP factors except `(1,pp,1)`. | 2026-09-24 user confirmation after observing the weld reversal in the q=2, pp=4, L=4, D=1/2 layouts; the earlier 2026-09-21 scope allowed smaller PP factors. |
| TLP-PP2-REGULAR | Approve the two displayed TLP `(1,2,1)` layouts; reject the corresponding TSP layouts because the first/last-layer cross-connection direction reverses. | 2026-09-22 current review, explicit user confirmation against the displayed A1/A2 layout pair. |
| TLP-PP2-AUTO-Q2 | Approve the additional Workbench Auto layout for the reviewed q=2, eight-pole, four-layer case. | 2026-09-22 current review, explicit user confirmation of Auto `Times=1`, `tp_start_index=1`. |

## Withdrawn CP construction method (2026-09-25)

The `cp_pp_pair_join` method that matched intact CP P2-parent paths has been
withdrawn from production admission after review of the updated `(1,2,1)`
sketch. Its earlier generated examples must not be used as current `Validated`
evidence. This withdraws one construction method; it does not reject the CP
PP-divider family. Tuples without an applicable registered constructor remain
`unsupported-yet`. The active four-pass weave is documented in the CP section
of `PATTERN_DIVIDER_FORMULA_SUPPORT.md` and in the Pattern construction
definitions.

## Registered CP `(1,4,1)` half-translation boundary (2026-09-26)

The distinct `cp_pp_parent_half_translation` constructor admits even integer
`q>1` when the selected PP divider is four and four divides the actual
pole-pair count. It derives four branch inlet offsets from the public
`(1,1,2)` parent and then passes each requested geometry through public CP
generation and validation. Odd q remains outside this half-translation
construction, but it is not a general CP exclusion: PP-only `(1,D,1)` may use
the separate `cp_q_pp_full_parent_slices` route for positive odd integer `q`,
even `D>=4`, and `D|pp`, subject to CP layer/phase/configuration gates and
public source/target preflight. A failed source or transformed target retains
its exact case-level reason. These constructor-specific boundaries are not
physical-impossibility claims.

## Reviewed non-exclusions

ZPP PP-only `(1,D,1)` retains its two translation constructors and adds the
owner-approved [actual-lane endpoint/gcd family](PATTERN_DIVIDER_FORMULA_SUPPORT.md#zpp-actual-lane-endpoint-cyclic-permutation-and-gcd-partition-2026-10-03).
That family uses legal local factors and actual configured full-Q parents;
it does not weaken signed-edge, weld, identity or existing owner exclusions.
The legacy
whole-path translation uses a public same-Naa `(D,1,1)` parent and keeps its
direct domain `q=Naa=D`, `D|pp`, and stride `a` satisfying `gcd(a,D)=1` and
`gcd(D,2*(pp/D)*a-1)=1`. A separate centered-entry constructor uses the public
`(q,1,1)` parent when `D>q`, `q|D`, and `D|pp`. Target branch `j` takes the
centered parent window of length `parent_length/(D/q)` and translates it from
its actual source sector to `(a*j mod D)` using the same stride rule. Both
constructors retain supported phase/topology, positive even layers, neutral
Regular settings, weld-side inlet, and public parent/target generation checks.
The centered route matched the retained q=2, pp=4, L=4 phase-A package exactly;
additional strict public samples covered q=1, D=3, pp=6 and q=3, D=6, pp=12.
Cases outside `q|D` or `D|pp` do not enter the centered route. Those source-
specific boundaries and earlier weld findings do not exclude a distinct admitted
endpoint construction. Successful older routes retain priority; the new formula
also supplies canonical local paths for formerly blocked integer-q stride arrays.

The SLP `(1,2,2)` manual package for q=2, pp=4, L=4 previously carried a
"should reject" note without an engineering reason. A PP+P2 sector constructor
is now registered for the factor relation `pp=2*pp-divider`; the old note is
not an exclusion rule. The registered SLP P2-only, PP+P2 sector,
full-Q/even-sector, and paired-lane/full-PP constructors use case-specific
coverage, phase, edge, weld, terminal, and identity checks. An admitted case
that fails one of those checks is `rejected` with its exact generated reason.
Proper-Q+PP+P2 `(Q,D,2)` now has its own parent-regroup formula when
`1<Q<q`, `Q|q`, `D>1`, `D|pp`, and `pp/D` is even; requests outside that
formula retain the resolver's existing `unsupported-yet` or explicit rejection
classification. This does not change the separate `(1,D,2)` whole-sector
constructor or its one-region replay boundary.

TSP/TLP PP alternatives outside registered routes have no
located user-approved blanket reject and no general impossibility proof. They
are `unsupported-yet` when no constructor is registered. If a registered route
actually fails generation or validation, that geometry remains `rejected` with
its exact structural reason. Production dispatch stays closed for unsupported
rows. This review does not admit a new connection.

User review on 2026-09-22 approved the displayed TLP `(1,2,1)` pair and rejected
the corresponding TSP pair because its first/last-layer cross-connection
direction reverses. That historical decision was an admission distinction,
not a physical impossibility result, and is superseded for TSP by the explicit
2026-09-29 complete-pass decision above. The older adjacent-parent constructor
retains its separate bounded formula and public checks below.

### TSP q-only adjacent P2-parent pairing (2026-09-29)

For integer `(Q,1,1)`, pair adjacent same-phase branches from the same
Pattern's `(Q,1,2)` source in generated order. Admission requires even `Q>1`,
`Q|q`, `pp>1`, even local `L>=4`, and
`gcd(L/2,pp) in {1,pp}`. Proper-Q sources use the formula-derived q-lane
completion. Neutral Regular settings, zero shifts, insert-side inlet, and
ALWP+CLWP remain required. The complete source and joined target must pass
public coverage, phase/direction, N-to-S, TSP edge, ordered-identity,
one-region and electrical-retention checks. For phase-set arrays, every local
set must satisfy the formula and the mapped aggregate must pass public checks.
This route does not admit TSP `(1,2,1)`, odd Q, interior-gcd cases, or other
settings. See `PATTERN_DIVIDER_FORMULA_SUPPORT.md` for the finite samples and
current six-geometry matrix delta.

### TLP q-only adjacent P2-parent pairing (2026-09-29)

TLP `(Q,1,1)` uses adjacent same-phase branches from the public `(Q,1,2)`
parent when integer `Q=q>=2` is even, `pp>=2`, `L>=2` is even, and the phase
count is one native phase set. Neutral Regular settings, zero shifts, and an
insert-side inlet are required. The paired source cohorts must remain on one
outer layer, use adjacent q lanes, and form a top-bottom return with oriented
pitch `m*q±1`; the actual seam is checked against the one-pole-region limit.
Proper-Q tuples and arrays have no admission from this route. Proper-Q target
requests that cannot generate their public parent stay `unsupported-yet`.
On the fixed six-geometry q-only cell, six former `unsupported-yet` requests
are supported; two proper-Q cases remain `unsupported-yet`, and the existing
rejected request is unchanged. See `PATTERN_DIVIDER_FORMULA_SUPPORT.md` for
sample outcomes and the retained-not-strong EMF diagnostics.

### TSP full-q PP-only identity route (2026-09-27)

TSP `(1,2q_s,1)` is registered only for integer local `q_s>=2`, when `2q_s`
divides the pole-pair count and the same-Naa public `(q_s,1,2)` parent passes
the existing TSP layer, phase, configuration, coverage, edge, ordered-identity,
and electrical-retention checks. Direct symmetric phase counts use supported
odd `m>=3`. For an array of `k=m/3` three-phase sets, including even phase
totals, `q_s=k*q` and the layer count must be divisible by `k`. The formula
copies the parent's ordered paths unchanged.
Non-EMF phase, direction, occupancy, or electrical errors reject that case;
EMF-only mismatches remain retained diagnostics. TSP `(1,2,1)` and
proper-q-divider PP-only tuples remain outside this formula; a target outside
its domain does not inherit support from the q/P2 parent. See the parameterized
formula and current support matrix in
[`PATTERN_DIVIDER_FORMULA_SUPPORT.md`](PATTERN_DIVIDER_FORMULA_SUPPORT.md).

### TSP fixed-lane PP+P2 sector route (2026-09-28)

TSP `(1,D,2)` now has a direct formula for integer q with `D>1`, q dividing D,
D dividing pp, positive even layers, and an exact fixed-lane residue partition.
Public construction must pass. Each of D positive-pole regions contributes one
first-layer inlet and one last-layer inlet with opposite signed travel. Direct
phase counts use the supported odd domain; phase-set arrays apply the formula
with each set's local q and layers, then validate the mapped global layout.
Neutral Regular settings, zero shifts, insert-side inlet, and ALWP+CLWP remain
required.

Eight sampled tuples passed public generation, complete occupancy, phase and
direction, N-to-S terminals, one-region edge limits, and ordered TSP identity.
The validator also recovers region rank and q-lane from canonical N-sign
phase-map origins, independently of the formula path builder. The saved
`(q,pp,D,L,m)=(2,4,4,4,3)` layout matches all eight phase-A paths.
`parallel_emf_mismatch` and `multi_phase_emf_mismatch` remain retained
`not strong symmetry layout` diagnostics. `D|pp` alone does not admit the
route: q-lane omissions and residue collisions remain `unsupported-yet`,
including sampled `(3,2,2,4,3)`, `(2,4,2,4,3)`, `(2,4,4,2,3)`,
`(2,4,4,8,3)`, `(2,8,4,4,3)`, `(3,12,6,4,3)`, and local-array
`(2,4,4,6,9)` cases. A tuple inside the formula domain that fails a public
path check remains rejected with its generated reason. In the finite
`pp_and_p2` route scan, support changed from 0/10 to 3/10; the remaining seven
requests stay `unsupported-yet`.
TSP `(1,2,1)` and the existing `(1,2q_s,1)` identity route are unchanged.

## Case-specific generation failures

| Category | Reason details to preserve | Interpretation |
| --- | --- | --- |
| Conductor count | Branch ID, actual and expected counts; `branch_length`, `branch_count` | The generated partition does not have the required equal branch lengths/counts. |
| Occupancy | `duplicate_conductor`, `missing_conductor`, `unknown_conductor`, invalid slot/layer | The path repeats positions or does not cover the expected discrete domain. |
| Phase/direction | `mixed_phase_branch`, `direction_sequence`, `phase_branch_count` | The actual path violates phase membership or conductor sign sequence. |
| Pattern edge | Actual generator message, such as `CP selected branch has an invalid cross-layer edge` | An independent Pattern edge rule failed; do not classify this as EMF asymmetry. |
| Multi-region connection | Branch and edge index, one-based start/end slot and number of crossed pole-region boundaries | Any insertion, weld or return crossing more than one pole-region boundary rejects that generated construction. The Pattern/divider family remains available for another method; pitch magnitude alone is not the reason. |
| Terminals/junction | N-inlet / N-to-S endpoint error, or q-only same-layer bridge error | The requested terminal or explicit junction rule failed. |
| Configuration | Unsupported TP mode/offset, radial swap, inlet adjustment, shifted reverse/overrun | The current construction does not implement that configuration or its output violates a geometric constraint. |
| Degenerate electrical result | `zero_fundamental` | Existing zero-fundamental diagnostic; distinct from unequal branch EMF. |

EMF-only codes `parallel_emf_mismatch`, `three_phase_emf_mismatch` and `multi_phase_emf_mismatch` must remain diagnostics of retained layouts, never be entered as rejection rules.

## Inspected snapshot: q=4, pp=4, layers=4

This is a bounded observed snapshot from before the 2026-09-23 ZLP-Q and
CP-NO-DIVIDER exclusions, not a current admission matrix.

- BWP: all P2=2 tuples rejected by BWP-P2.
- UWP: all pp-divider > 2 tuples and pp-divider=2/P2=2 tuples are rejected by UWP-PP-P2. This supersedes the earlier mutual-exclusion-only rule.
- ZLP: `(2,4,1)`, `(2,4,2)`, `(4,4,2)` fail branch length; `(4,2,1)` references an unavailable slot/layer.
- CP: `(1,1,1)` fails branch length; `(1,2,2)` and `(1,4,2)` fail cross-layer edge checks.
- ZPP: `(1,1,1)`, `(2,1,1)`, `(4,4,2)` fail branch length.
- TSP and TLP: `(2,2,1)` uses the common second-sector deployment when its `(2,1,2)` reference passes. TLP keeps the legacy `(1,D,1)` cut for `q<=2` and adds full-Q `(q,D,1)` for integer `q>1`, even `D>=4`, `D|pp`, even `L>=4`, and a public `(q,2,1)` parent that generates. The distinct TLP `(2,D,2)` route cuts a public `(1,D,2)` parent into two complete-pass children under its own even-q and PP/P2 guards. For `k=m/3` phase-set arrays, the bounded full-Q PP-only mapping is `(Q,D,1)->(kQ,D/k,1)` with even local `D/k>=4` and even local `L>=4`; every set and the mapped aggregate must pass public validation. Other proper-Q PP targets and unmapped tuples remain `unsupported-yet`; reference or deployed coverage failures keep their exact method reason. See `PATTERN_DIVIDER_FORMULA_SUPPORT.md` for formulas and samples.
- LPP: `(1,4,2)` hits LPP-FACTORS.

## Maintenance

The generator remains the executable authority; this file is the single maintained rejection-reason registry. Add or revise an entry here when changing a rejection rule, and keep the generator's reason and Workbench display aligned. Other project documents should link here instead of maintaining competing rejection tables. Historical changelog entries are not active policy.
