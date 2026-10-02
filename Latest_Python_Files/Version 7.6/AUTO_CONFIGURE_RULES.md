# All-Pattern Auto Configure Rules

Updated 2026-09-22. Scope: Pattern Rule Workbench catalog/drafts and main-window Auto.

## Reusable execution workflow

Use this sequence for another Pattern/formula extension or Auto objective:

1. Read the current production classifier and relevant Pattern rules. Record the
   exact case (q, poles, phases, layers, Q/D/P2, shifts, inlet side and fixed pole
   group settings). Back up touched sources. Admission comes from factors and
   construction rules, never a table of previously successful parameter tuples.
2. Add a failing behavior test with an independent expected result. Distinguish
   missing admission, failed neutral construction, count hard no, unconfigured
   but retained layout, and a completed strong implementation.
3. Generate geometry-derived recipes through the public generator. Retain its
   occupancy, branch-length, phase, edge and P2 N-to-S checks. Group counts by
   the actual phase map; never assume the first Naa paths are one phase.
4. Apply the weld-side contract before symmetry or objective ranking: preserve
   the neutral reference's physical welding-edge multiset (including repeated
   edges), and require one phase-shift-corrected lower-to-higher travel direction
   per cross-layer pair. Deduplicate the remaining complete ordered physical
   paths, assess every valid strong implementation, then rank separately for
   each objective. Do not stop at the first success or skip an already strong
   Default/Validated baseline.
5. Replay the winner using `replay_auto_configuration()` and its exported
   effective parameters. Verify catalog,
   loaded paths, reference transitions and draft metadata agree. UI Auto uses
   the same resolver; explicit Regular/Times/Interval remain manual.
6. Run the small contract suite below first. Add the affected divider, phase,
   connection and UI/config regression cases. Compare unrelated wider failures
   against pre-edit sources instead of weakening assertions or guards.
7. Record the tested domain, result counts, objective and metric basis, pending
   cases, independent-review findings and actual verification evidence here and
   in the changelog. Keep old snapshots dated; they are not current certificates.

Ownership: `automatic_transposition.py` owns recipe enumeration, objective IDs,
metrics and score ordering; `get_winding_pattern.get_auto_configured_layout`
owns guarded generation and selection; `pattern_rule_workbench.py` owns catalog
and draft integration; `main_pyqt6.py` owns the Transposition tab and config UI.

Fast contract check from the active-version directory:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
& '../../.venv/Scripts/python.exe' -X utf8 -m unittest test_automatic_transposition test_auto_configure_pending_rules test_auto_configure_strategy_ui test_winding_dividers.GeneralPatternRuleTests.test_auto_objectives_rank_multiple_implementations_instead_of_first_success test_winding_dividers.GeneralPatternRuleTests.test_auto_length_uses_explicit_normalized_geometry_not_physical_fallback -v
```

Use test-shell environment overrides only for verification; restore them before
native launch. Example follow-up request: "Extend Auto Configure for <Pattern /
formula> using AUTO_CONFIGURE_RULES.md; keep factor rules and retention policy,
verify all three objective winners and explicit replay, then update evidence."

## Implementation objectives and extension API

The Transposition tab offers these stable, persisted objective IDs. Missing
legacy config values default to `min_pin_types`. The selector is active in Auto
mode; changing it invalidates cached calculation/preview/inductance results.

| ID | UI implementation class | Primary metric | Tie break |
| --- | --- | --- | --- |
| `min_transpositions` | 1. Minimum transpositions | Changed connection events against the neutral common-TP reference, summed over every phase/branch | Fewer pin types, then deterministic recipe order |
| `min_pin_types` | 2. Minimum pin types (default) | Distinct insertion-pin `(min layer, max layer, absolute circular slot span)` geometries | Fewer changed connection events, then recipe order |
| `min_average_pin_length` | 3. Shortest normalized average pin length | Quantity-weighted dimensionless complete body-pin geometry proxy | Fewer pin types, fewer changed connection events, then recipe order |

A changed connection event has a different phase-shift-corrected signed slot
pitch or ordered layer pair at the same branch/edge index as the reference.
Both insertion and welding edges, including cyclic returns, count. This counts
connection events rather than nonzero TP fields or shop-floor operations. The
reference zeroes common TP fields; fixed PoleN/PoleS settings remain fixed, so
the count measures additional common TP relative to that reference.

Types use the existing geometric pin-shape convention, not only ALWP/SLPP family
names. Count physical insertion edges from every generated branch with the
correct inlet-side parity. If Connect ends is enabled, include its last-to-first
edge in pin/weld inventory, length inputs and changed-edge counts. Terminal
I-pins are not body pins in this metric. The present main-window Auto
integration requires zero inlet rotations, so later terminal adjustments cannot
change the scored pins. Manual TP modes retain their explicit inlet workflow.

The third objective uses one explicit normalized geometry rule in both the
catalog and the main window. For each physical insertion pin:

```text
2 + sqrt((insert_span/pole_pitch)^2
         + (layer_span/max(L-1,1))^2)
  + (weld_span_a+weld_span_b)/(2*pole_pitch)
```

The overall mean weights each shape by its physical quantity across all phases.
This dimensionless proxy is a deterministic comparison rule, not copper length
or manufacturing approval. When a physical evaluator is supplied, the existing
end-winding model remains available as `average_pin_length_mm` for reporting,
but it does not select the third objective's winner.

```python
import automatic_transposition as auto_tp
import get_winding_pattern as gw

length_model = auto_tp.make_pin_length_evaluator(winding, stator, inslot, end_winding)
starts, paths = gw.get_auto_configured_layout(
    pattern, tp, winding, layout,
    objective='min_pin_types',  # or either other stable ID above
    pin_length_evaluator=length_model,
)
result = paths.auto_configuration
selected = result['effective_parameters']
alternatives = result['implementations']  # unique valid path implementations
winners = result['objectives']           # independent winner per metric
```

`pin_length_evaluator(layer_a, layer_b, insert_span, weld_span_a, weld_span_b)`
is the extension interface for another physical model; return a positive finite
length in mm. A custom callable is labelled as a custom model. Add future
objective IDs to `AUTO_CONFIGURE_OBJECTIVES` and their independent score to
`objective_score`; extend pure-score and real-path replay tests together.

Metadata retains the selected objective, actual metrics, physical-path identity,
all unique valid implementation summaries, three objective winners, attempt
count and search scope. More than one objective may select the same paths.
Each implementation also exports its `rule_id`, ordered `physical_paths`, and
`effective_start_schedule`. The latter is currently `null`: inlet adjustment
is not treated as an independent constructive start search. Any future non-null
schedule must preserve phase, inlet pole region, inlet layer and branch identity
and must regenerate through the public constructor.
Selection is the minimum within the evaluated recipe domain only. Pending and
count-hard-no cases retain their baseline and are not labelled optimized.
Normalized-length ranking rounds the mean to 9 decimal places before tie breaking,
so floating-point summation noise cannot prefer more pin types or connection
events. Raw normalized and optional physical means remain in metadata; this is
not an accuracy claim.
Main-window Auto uses a canonical forward `jld=1` seed; a negative readonly
derived Jump value cannot change its reference direction on the next run.

### Objective verification snapshot

The integrated 100-test regression run passed; after the closure, refresh and
floating-point tie fixes, the final 22-test objective/UI contract suite also
passed (`.test_auto_objectives.log`, `.test_auto_objectives_final.log`). Independent
review found the Connect ends omission; its closed BWP/UWP reproductions now
match the displayed pin inventories. UI refresh, config persistence, actual
three-objective calculation and canonical Auto reference direction are covered.

For BWP q=4, poles=8, layers=4, (Q,D,P2)=(2,1,1), insert-side inlet and open
ends, the search finds 52 unique valid implementations. The default objective
selects 6 pin geometries versus 7 in the former first-success recipe. The saved
machine geometry gives 441.106 mm estimated mean length. Replayable config and
all implementation summaries are in `workbench_preview/auto_strategy_qa/`:
`completed_bwp_config.json` and `completed_bwp_objectives.json`. These are evidence
examples, not admission lists. Offscreen screenshots at 1366x768 and 1920x1080
cover default/manual/completed states; they are not native Windows DPI acceptance.

The common resolver now applies to all ten Patterns: BWP, UWP, SSP, SLP, ZLP,
CP, ZPP, TSP, TLP and LPP. It does not expand their divider admission or bypass
Pattern-specific configuration guards. Source-route labels and draft metadata
show the same configuration outcome as the catalog. Raw EMF-asymmetry report
labels are diagnostics, not a substitute for the catalog's hard-no proof.

Bounded checks at q=2/4, pp=4, layers=4 cover retained catalog routes in all ten
Patterns. In particular TLP q=2, pp=4, layers=4, Naa=4, `(2,1,2)` is solved by
Regular uni_tp=1 with the other TP fields zero; its default catalog status is
restored with verified strong-count and electrical evidence.

## Objective and evidence

Strong symmetry requires equal conductor COUNTS per `(phase, layer, signed electrical position)` across the parallel branches of each actual phase. Group by the phase map, not branch-number slices: BWP may interleave phases. Use
`signed_angle_key = (poles * slot + (slots if sign < 0 else 0)) % (2 * slots)`.
EMF equality alone is insufficient. Complete unique coverage and equal branch lengths are prerequisites; independent electrical validation must also pass before Auto reports a solved strong layout.

## General hard-no rule (all valid q/pp/layer/Naa combinations)

This rule is independent of Pattern and branch construction. Use the actual
complete phase map for the specified geometry and shifts, never a partial draft.
Let m be phase count, P=2*pp, S=m*P*q, L=layer count and A=Naa. Require exact
integer S and positive integer P, L and A; do not truncate fractional q.
The phase-map implementation must support the requested geometry; unsupported
or invalid input is not a mathematical hard-no proof.

For each conductor at zero-based slot s and layer l, with actual phase f and
sign d from the phase map, define:

```text
k = (f, l, (P*s + (S if d == -1 else 0)) mod (2*S))
C[k] = number of conductors in category k over the complete winding
G = gcd of all positive C[k]

hard_no_count_symmetry <=> there exists k with C[k] mod A != 0
                      <=> G mod A != 0
otherwise required branch quota[k] = C[k] / A
```

Proof: A equal branches in a phase must each have the same integer count n[k],
so C[k]=A*n[k]. A nonzero remainder contradicts that necessary condition.
All remainders zero establish an integer allocation only, not connected paths,
legal pitches, valid terminals, or a feasible TP recipe. Consequently passing
the count rule is NOT a proof of strong symmetry or of constructibility.

The invariant assumes every slot-layer conductor is used exactly once and the
underlying phase map is fixed. Changes of geometry, phase map or conductor set
require recomputation. Arbitrary permitted branch-start relocation or TP cannot
change this inventory, so the obstruction holds beyond any finite search.

`automatic_transposition.strong_symmetry_count_rule(records, slots, poles, naa)`
implements the geometry-only check without requiring a generated layout. It
returns G, category counts, feasible quotas or a witness list containing phase,
layer, signed angle key, C[k], A and remainder. It is reused by the existing
layout assessor. The general rule works for integer or rational q whenever a
complete valid phase map exists; it does not grant new Pattern admission.

See STRONG_SYMMETRY_TARGET_PROMPT.md (local research excluded) for the
next construction/search task.

## Classification outcomes

| Outcome | Workbench handling | Required evidence |
| --- | --- | --- |
| Solved | Default/Validated, with strong-symmetry reason and selected parameters | Actual generated paths pass coverage, electrical and exact signed layer-count checks |
| Pending | `auto configure pending`; drawable and editable | No invariant obstruction, but no verified solution in the searched recipes |
| Hard no | `not strong symmetry layout`; still retained | At least one total signed layer-position population is not divisible by Naa |

The hard-no test follows from integer allocation: equal parallel branches must each receive `total/Naa` conductors of every category. Transposition and relocating starts within a pole region cannot alter the inventory of a complete winding. Store category, total, Naa and remainder as the proof. This proves impossibility of the stated strong COUNT symmetry, not impossibility of equal EMF or physical construction. A failed bounded search is never a hard no.

## Auto construction process

1. Generate the original route and independently check the actual phase-map populations.
2. Include an already strong baseline as a scored implementation.
3. If category divisibility fails, retain the original layout and record the proof; do not waste configuration search on an impossible allocation.
4. For integer BWP/UWP, derive the common TP recipe domain from geometry: every nonzero joint offset residue modulo q, every Interval and Times value from 1 through branch conductor count minus one. BWP consumes Uniform, Jump and last-layer offsets; UWP also enumerates the first-layer field, subject to its route guards. Try simple existing recipes first. For the UWP balanced-Q constructor, also try its derived explicit Auto payload. Other Patterns retain their previous bounded recipes.
   When the neutral layout is unresolved, enumerate every usable
   `tp_start_index` for each Interval/Times recipe. An already strong neutral
   layout keeps the canonical start index while comparing its TP recipes; the
   exported scope records this finite-domain distinction.
5. Regenerate each candidate through the existing public generator and its guards. Do not bypass rejected edges, overlaps or unimplemented TP settings.
6. A changed start must stay in the original branch's pole region and layer. Branch order/identity must remain stable. The current search varies TP only; independent per-branch start relocation is permitted by the design policy but is NOT exhaustively searched yet.
7. Reject any candidate that changes a physical weld or conflicts within a
   welding layer pair. This feasibility rule has priority over strong symmetry,
   electrical validity and all three objectives. Score every remaining unique
   strong, electrically valid candidate; keep each objective's winner and record
   its TP payload, metrics and starts. Otherwise retain the baseline as pending.

### BWP integer-q rule-first stage

For the reusable derivation and differential-validation procedure, see
[`BWP_AUTO_CONFIGURE_RULE_WORKFLOW.md`](BWP_AUTO_CONFIGURE_RULE_WORKFLOW.md).

For insertion-side BWP, manuscript v3 Table IV gives the pin-type target
`N_L + 1`, where `N_L` is the layer count. Auto uses this formula as an early
stop target: for `min_pin_types`, it stops immediately after a candidate
reaches exactly `N_L + 1` and passes the public generator plus occupancy,
phase, edge, electrical, strong-count, start-region and weld-side checks. The
pin count is then at the manuscript target. The objective's transposition
tie-break is not searched beyond that candidate.

The formula stop is enabled within the differentially checked envelope only:
integer `q=2..6`, pole pairs `1..6`, 2/4/6 layers, three phases, insertion-side
inlet and zero layer shifts. This is a search-mode guard, not a divider or
Pattern-admission whitelist. Uniform, Last-layer, and Jumper-layer Regular
recipes precede combined Regular, Interval and Times recipes; First-layer is
omitted because the BWP constructor does not consume it. If no valid candidate
reaches the exact formula target, Auto completes the existing recipe search.
The entire generated BWP recipe queue precedes the currently selected TP input,
so a selected Interval cannot run ahead of the prioritized offset recipes.
Other objectives, weld-side inlet, and out-of-envelope inputs also use full
search.

The formula-specific differential covered 381 BWP cases. Status matched full
search in 381/381; among 339 cases with an available pin-type result, primary
pin counts matched in 339/339. In five cases, full search found the same pin
count with a lower transposition tie-break, which the requested early stop does
not optimize. There were 204 formula stops and 177 full-search fallbacks.
Candidate attempts fell from 308,629 to 249,443; measured aggregate time was
395.9 s for full search and 310.3 s for the formula stop. These are paired
audit-run observations, not a runtime guarantee. The other objectives remain
on full recipe search.

For the BWP q=4, 8-pole, 4-layer, `(Q,D,P2)=(2,1,1)` insertion-side case, the
formula target is 5 but the best recipe result has 6 pin types. It therefore
continues full search instead of stopping at a nonminimum result. In the
reference q=2, 8-pole, 6-layer, Naa=2 insertion-side case, `pltp_ll=1` reaches
the target 7 after three recipe attempts and stops there. Machine-readable
case evidence is in
`workbench_preview/auto_configure_rules/bwp_min_pin_formula_verified_20260923_order2/`.

The result is a formula-target pin-count stop within the tested envelope, not
global optimization of the secondary transposition tie-break, arbitrary TP
recipes, independent starts, or physical manufacturability.

Replay recomputes the neutral reference and the same weld-side contract. Auto
metadata records the rule version and rejection count so discarded welding-side
transpositions are visible instead of silently participating in ranking.

Non-wave Auto candidates carry a Pattern-specific geometry-rule ID plus a
process-private authorization token. Only the Auto resolver and
`replay_auto_configuration()` can supply that token; adding the exported rule ID
to a direct `get_winding_layout()` call does not open manual admission. Every
authorized candidate still runs through the normal constructor and all Pattern
validators. Candidates that alter a defining edge,
pin identity, coverage, terminals or electrical validity are discarded. Search
metadata lists tested rule IDs and keeps independent per-branch starts and
unemitted pole-group schedules explicit as unsearched dimensions.

When full search runs, the integer wave search covers this common-TP recipe
domain without fixed q, pole-count or example-case caps. The BWP rule-first case
is deliberately narrower and reports that scope explicitly. Neither path is a
proof that arbitrary connections, independent branch-start relocation,
independent PoleN/PoleS settings, or all TP start indices have been exhausted.
Every candidate still passes the public generator's admission and layout guards.
A neutral construction failure remains a case-generation rejection; this
resolver does not synthesize a new topology.

The resolver is `get_auto_configured_layout()`; the recipe owner is
`automatic_transposition.configuration_recipes()` and the pure count assessment
is `automatic_transposition.assess_strong_symmetry()`. Catalog probing,
Open/Reload and selected-reference extraction use the same resolver. Reference
edges are extracted from the exact configured database loaded into the draft.
Exported reference metadata includes `completed`, `effective_parameters`, starts,
attempt count and feasibility evidence. `completed=true` requires actual strong
counts and electrical validity, including when the original zero-TP layout
already satisfies those checks. Default/Validated is never a reason to skip
Auto Configure. Pending and hard-no layouts remain drawable with
`completed=false`. Main-window Auto also uses this resolver and the selected
objective; explicit Regular/Times/Interval retain manual settings.

## Formula-wide rules, without whitelists

Enumerate every Q divisor of integer q, every D divisor of pole pairs, and
P2 in {1,2}; retain the tuple identity even when two formulas share Naa.
Use `Naa=Q*D*P2` and the common production classifier before configuration.

| Pattern | Formula families handled by the same resolver | Existing exclusions |
| --- | --- | --- |
| BWP | 1, Q, D, Q*D | P2=2 remains rejected |
| UWP | 1, proper Q, D, 2*Q, Q*D, with D*P2 in {1,2} | Full-Q q-only for q>1 duplicates BWP; larger splitting products remain rejected |
| Half-integer UWP | Naa=2*q*D, subject to the same split allowance | Candidate admission and fractional TP guards remain in force |

These formula families are enumeration rules, not unconditional construction or
strong-symmetry guarantees. Actual phase-map inventories determine hard no;
generated branches determine success. Neither a successful example nor a failed
search adds a parameter tuple to an admission list. All Default/Validated rows
must have a completed Auto result, and their loaded/exported paths must reproduce
that same result. Neutral Regular generation remains neutral outside the
automatic operation.

## Earlier bounded-search snapshot: q=4, pp=4, layers=4 (2026-09-21)

| Pattern | Tuple | Result / configuration |
| --- | --- | --- |
| BWP | `(2,1,1)` | Strong: Regular, uni_tp=1, other TP fields zero |
| BWP | `(4,1,1)` | Strong: Regular, uni_tp=1, other TP fields zero |
| BWP | `(4,2,1)` | Strong: Interval, tp_interval=1, other TP fields zero |
| BWP | `(2,2,1)`, `(2,4,1)` | Pending; no hard-no count obstruction |
| BWP | `(4,4,1)` | Hard no: signed layer-position population 8 cannot be divided among Naa=16 branches |
| UWP | `(4,1,2)`, `(4,2,1)` | Pending; existing EMF balance does not establish strong layer-count symmetry |

These are verified examples, not parameter whitelists or proofs about all q/pole/layer combinations. Existing strong baseline routes need no parameter change. Other explicit Pattern exclusions stay governed by `PATTERN_REJECTION_REASONS.md`.

The 2026-09-22 resolver supersedes that snapshot: explicit derived Auto solves
the full-Q UWP P2 example. A regression at BWP q=6, pp=6, layers=4,
(Q,D,P2)=(2,2,1) verifies that combined offsets find strong counts missed by the
old single-field recipes, with original starts preserved. These cases are tests,
not dispatch conditions. Current matrix evidence is stored in
`workbench_preview/auto_configure_rules/formula_audit.json`.

## Ten-Pattern formula audit after objective integration (2026-09-22)

The current bounded audit covers integer q=1..6 plus admitted positive
half-integers 3/2..11/2, pole pairs=1..6, layers=2/4/6, three phases and zero
layer shifts. It contains 13,860 Pattern/formula cases. Catalog status totals
are 1,695 Default, 498 Validated, 1,293 proved count hard no, 453 retained
pending, 253 Candidate, 5,750 rejected and 3,918 unsupported-yet.

Pending remains only in BWP (42), UWP (51), SSP (135), SLP (136), ZLP (61)
and CP (28). TSP, TLP, ZPP and LPP have no pending rows in this bounded domain;
their remaining rows are solved, proved hard no, Candidate, rejected or
unsupported according to their production rules. Search exhaustion is not an
impossibility proof.

Evidence:
`workbench_preview/auto_configure_rules/formula_audit_all_patterns_20260922T074122Z.json`
and the matching CSV. `audit_auto_configure_formulas.py` first classifies
neutral-strong and hard-no rows, then performs the full Auto search only for
unresolved rows. This audit optimization does not change interactive Catalog
or main-window resolution.

## Earlier wave-only verification before objective ranking (2026-09-22)

The bounded matrix enumerates all factor tuples at integer q=1..6, pole
pairs=1..6, layers=2/4/6, three phases and zero layer shifts: 2,352 cases.

| Pattern | Completed strong | Retained count hard no | Retained pending | Rejected |
| --- | ---: | ---: | ---: | ---: |
| BWP | 381 | 165 | 42 | 588 |
| UWP | 357 | 141 | 42 | 636 |

All 738 actual Default/Validated catalog rows were opened, exported in memory,
and replayed through the public generator using their effective parameters.
Every loaded phase-A path matched that explicit replay. BWP comprised 318
Default and 63 Validated rows; UWP comprised 216 Default and 141 Validated rows.
The remaining 84 pending cases are not claimed solved or impossible.

85 focused tests passed, including nonzero shifts, P2 terminal polarity, intact
UWP weld pairs, full input nonmutation, pending retention and existing topology,
connection and classic regressions. The broader 123-test run retained 16 failing
assertions and 10 errors, all reproduced against pre-edit sources; it is not a
passing full suite. Independent read-only review found no reproducible regression.
This evidence is bounded software verification, not manufacturing certification.
