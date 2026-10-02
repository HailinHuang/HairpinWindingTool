# Pattern Definitions and Constraints

## Current TLP q-only and ZPP Q+P2 boundaries (2026-10-02)

Owner-approved native TLP `(Q,1,1)` extends the earlier full-Q pair join to
even `Q|q`, `2<=Q<=q`: join `2q/Q` complete public `(q,1,2)` parents in
each outer-layer cohort. Preserve every body pass and check every new
top-bottom insertion seam, one-lane advance, signed travel, one-region
limit, occupancy, N-to-S orientation and weld direction. Q>2 remains a
retained non-strong layout; L=2 keeps its structural overlap qualification.
Multi-set arrays remain unsupported-yet. The bounded 48-case review passes
connection-stage checks in each canonical local set. Its earlier `k=m/3`
dividing Q restriction is withdrawn: fixed global pole counts after rigid
set rotation are coordinate diagnostics, not construction-stage failures.
Production admission still requires owner review and integration validation.
The [current formula/domain](PATTERN_DIVIDER_FORMULA_SUPPORT.md#tlp-even-q-cohort-joins-owner-approved-2026-10-02)
supersedes only the older proper-Q unsupported conclusion, not its historical
evidence or the shared transposition/shift rules below.

ZPP `(Q,1,2)` with `Q>1` is the owner's named-type exclusion:
`q and p2 share same route`. Apply it before odd-effective-q reasoning and
construction, including phase-set arrays. It does not exclude `D>1`, unit-Q,
P2=1 or other Pattern families, nor prove physical impossibility.

## Post-connection layout shifts (2026-09-29)

For every implemented Pattern route, construct and validate the connections
using the zero-shift layout first. Apply phase/slot and radial/layer relocation
to the completed conductors afterward. The relocated coordinates must still
have unique full occupancy, preserve each conductor's phase and pole sign, and
pass electrical retention checks. Do not run Pattern connection, pin-role,
signed-travel or pole-region identity checks again on the relocated endpoints.
The validated pre-shift connection identity remains attached to the result;
reported drawing coordinates and pitches follow the relocation. A shifted
layout with zero fundamental EMF remains an electrical failure. Inlet-side and
manual inlet-adjustment requirements still belong to the connection stage.
This section supersedes older route notes below that restrict phase/radial
shift admission or require post-shift connection validation.

## Manual transposition admission update (2026-09-29)

Manual TP inputs and Auto recipe TP inputs share constructor and generated-path
validation. Older neutral-configuration descriptions below no longer impose a
blanket TP-only restriction on an implemented constructor. Post-connection
layout shift follows the rule above; inlet limits and formula domains remain
unchanged. Input acceptance does not certify
coverage, Pattern identity or electrical balance; those are assessed on the
generated paths. Fixed formulas without a TP implementation must report that
limit rather than silently ignoring the settings. See
[current support](PATTERN_DIVIDER_FORMULA_SUPPORT.md#manual-transposition-inputs-2026-09-29).

Scope: Version 7.6 baseline, copied from Version 7.5 on 2026-09-24. This is a targeted developer reference for the supplied paper's
topology and manufacturing concepts. Runtime support remains defined by code.

## Read only what the change needs

| Task | Read first | Continue with |
| --- | --- | --- |
| Clarify a name or pin type | [Notation](#2-pins-patterns-and-notation) | [Source boundary](#1-provenance-and-evidence-levels) if needed |
| Repair or extend an existing Pattern | Its row in [family checks](#3-ten-connection-families) and [rule formulation](#verifiable-pattern-descriptions) | [Validation and production entry](#5-terminals-transposition-and-code-ownership) |
| Add a new Pattern | Family checks and rule formulation | Production integration below; reuse the [algorithm workflow](../../.agents/skills/hairpin-workflow/references/algorithm.md) |
| Change Naa or divider admission | [Support matrix](PATTERN_DIVIDER_FORMULA_SUPPORT.md) and [divider rules](../../.agents/skills/hairpin-workflow/references/divider-rules.md) | The affected family only; do not duplicate the admission matrix |
| Change illustrations | Guide maintenance (local research excluded) | [User guide](pattern_guide.html) |
| Shared connection rules help | Connection Rules maintenance (local research excluded) | [Connection Rules](connection_rules.html) |

## 1. Provenance and evidence levels

Source: `Manufacturability-Oriented Configuration Design for High-Slot-Number Hairpin Windings v3.docx`,
read on 2026-09-21. Relevant locations:

| Source location | Reusable content | Boundary |
| --- | --- | --- |
| Section II, Parametric Description; Tables I-II | Insertion span, weld shift, pin families | Descriptive classification, not executable admission |
| Section II, Branch-Construction Rules; Figs. 4-6 | Occupancy, phase, direction, uniform layer twisting | Necessary construction rules; more validation is required |
| Section II, Representative Connection Patterns; Fig. 7(a-j) | Ten Pattern families | Illustrated 24-slot, 4-pole, 4-layer, q=2, Naa=2 examples |
| Section III; Figs. 8-11; Tables III-V | Branch division, terminals, transposition, pin variety | Layout comparisons based on the 48-slot, 8-pole, 6-layer reference case |
| Sections IV-V | Phase-shift and application examples | Case-dependent performance, not general Pattern guarantees |

Keep three evidence levels explicit in future changes:

1. **Paper-derived definition:** the intended connection family or stated design
   constraint. It does not prove that the current implementation supports a tuple.
2. **Executable validation:** named parameters, generated full winding, identified
   checks, and passing regressions. A figure or enabled button is insufficient.
3. **Engineering assumption:** a proposed extension or unverified manufacturing
   judgment. Record it as a candidate until independent evidence supports it.

The source is a working manuscript containing terminology inconsistencies and
unfinished result cells. Do not treat its tables as universal physical limits.

### Executable phase-count extension (2026-09-25)

The software accepts the existing odd phase counts and every multiple of three,
`m = 3k`. A multiple-of-three winding is represented as `k` independent
three-phase sets. Each set keeps the original 120-degree phase sequence and
receives an equal, contiguous group of layers. Therefore the layer count must be
divisible by `k` (for example, six-phase uses two three-layer groups at six
layers; twelve-phase uses four groups and needs a layer count divisible by four).

The sets are arrayed around the stator in electrical angle steps of `360/m`.
Set `g` uses a `2*q*g` slot offset: six-phase sets are separated by 60 degrees;
nine-phase sets use 0, 40 and 80 degrees; twelve-phase sets use 0, 30, 60 and
90 degrees. The local three-phase winding uses `k*q` slots per pole per phase.
The phase map checks that these offsets land on integer slots.

`phase_topology.py` is the phase-assignment authority. Its
`build_phase_topology(slots, poles, layers, phases, shifts)` result carries an
immutable `PhaseRecord` for every slot/layer conductor, the explicit model
(`symmetric_polyphase` or `arrayed_three_phase_sets`), and `PhaseSetSpec`
objects that own each set's phase list, layer span, local q, slot offset and
reversible local/global coordinate transforms. `phase_map()` and
`default_phase_map()` remain tuple-returning compatibility views of that
topology. `Winding_Phase_division()` remains a legacy `Cond_info` adapter;
phase-A selection now queries the topology directly.

Topology construction establishes phase/sign assignment and phase-set
coordinates. It does not certify phase balance, strong symmetry, manufacturability,
or every Pattern route. Pattern routing and connection validation remain in
`get_winding_pattern.py`; a rejection after topology construction must be tied
to the selected Pattern's divider, geometry, layer transition, inlet or
connection rule. Multi-set generation and validation use the same canonical
set specifications rather than recalculating the `2*q*g` slot rotation and
layer partition in each helper.

This phase model does not enable every Pattern/divider combination by itself.
The selected divider tuple is resolved within each local three-phase set; its
local route name may differ when the local q differs from the global q. Each
local construction is checked before the complete array is checked for
full-winding coverage, phase membership, electrical balance and set angle.
When an array has odd-layer local sets, their ordered Pattern identity is
outside the current recognizer domain and the aggregate report marks it
`unverified` with its legacy confidence. The electrical phase model can still
pass. Each Pattern route must independently satisfy its local connection-side,
layer and weld-direction rules. Electrical acceptance is not strong-symmetry
or manufacturing certification. A successful phase topology is therefore
not a blanket admission for arbitrary Q/PP/P2, transposition or inlet choices.
The implementation is owned by `phase_topology.py`, `get_winding_pattern.py`
and the main application/workbench phase previews.

## 2. Pins, Patterns, and notation

A **pin** is a physical conductor with two in-slot legs. A **Pattern** is the
ordered connection family built from pins and welding connections. A Pattern
can contain several pin families; its name does not identify every pin in it.

- `Sin = (T, Ls)`: insertion-side slot span and radial layer separation.
- `Sw = (SwA, SwB)`: the two welding-end shifts. These are distinct from `Sin`.
- Relative to full coil pitch `tau = m*q`, `T < tau`, `T = tau`, and `T > tau`
  denote short, full, and long pitch in the paper.
- `Ls = 0`, `Ls = 1`, and `Ls > 1` denote same-layer, adjacent-layer, and
  cross-layer pins. Use absolute layer separation for this classification;
  preserve signed layer progression separately in the path.
- Table I uses relative outward/inward weld shifts: wave `(+,+)`, parallel
  `(+,-)`, lap `(-,-)`. Do not substitute these symbols directly for the
  generator's signed slot direction or a global clockwise direction.
- Table II pin names include ALWP, ALLP, SLPP, ALPP, CLWP, CLLP, SLWP, and SLLP.
  `SLPP` means single-layer parallel pin; `SLWP` means single-layer wave pin.
  The table's usage marks (`++`, `+`, `0`, `-`, `--`) are qualitative frequency,
  not winding polarity or software support.

Terminology corrections to preserve in code and documentation:

- Section II, Classification of Hairpin Pin Types, says "welding-end shift Sin"
  once. The preceding definition and Table I identify this quantity as `Sw`.
- Fig. 7 uses SSP/TSP/SLP/CP; later tables use SLSP/TBSP/SLLP/CLP for the same
  Pattern names. Use canonical project codes SSP/TSP/SLP/CP. `SLLP` is also a
  pin abbreviation in Table II, so retain the pin/Pattern context explicitly.
- `PATTERN_REGISTRY` and `normalize_pattern_name` own accepted software aliases;
  a manuscript abbreviation is not automatically a supported input alias.
- In the paper's Fig. 7, `p=4` means four poles. In project divider formulas,
  `pp = poles/2` means pole pairs. Paper `Dq/Da/Dp` correspond conceptually to
  project `q-divider/P2/pp-divider`; use the project identity from the matrix.

## 3. Ten connection families

These are defining topology descriptions, informed by Fig. 7 and the current
`pattern_<CODE>` functions. They are not a table of supported parameter ranges.
In SSP/SLP, **SL describes the boundary return**, not a branch confined to one layer.
In TSP/TLP, **TB describes the top-bottom return**.

The predicates below describe the **unshifted base variants illustrated in the
current guide**, before terminal relocation. They are necessary structural
properties, not exhaustive edge specifications. Branch splitting or transposition
may require different qualified predicates; do not apply a base-variant check to
an extension automatically. `L` is layer count, `dl` is signed layer change and
`ds` is intended signed slot displacement. A pass excludes its return; a layer
pair is (1,2), (3,4), etc. in one-based display notation.

| Code | Family structure | Base-variant predicate to test |
| --- | --- | --- |
| BWP | Adjacent-layer waves with forward/backward runs | Ordinary edges have `abs(dl)=1`; the same-layer return separates opposite slot directions. Test each run separately. |
| UWP | Wave progression retaining one circumferential direction | `abs(dl)=1` on every edge; `sign(ds)` is constant along the branch. |
| SSP | Spiral passes with same-layer boundary returns | In each pass, `dl` has constant sign and magnitude 1 and `sign(ds)` is constant; returns have `dl=0`. |
| TSP | Spiral passes with top-bottom returns | Same ordinary-pass checks as SSP; returns have `abs(dl)=L-1`. Jumper direction is a setting, not a fixed conductor index. |
| SLP | Lap passes with same-layer boundary returns | In each pass, `dl` has constant sign and magnitude 1; successive `sign(ds)` values alternate. Returns have `dl=0`. |
| TLP | Lap passes with top-bottom returns | Same ordinary-pass checks as SLP; returns have `abs(dl)=L-1`. Even-layer full-pitch passes have net displacement `+tau` or `-tau`. |
| ZLP | Offset lap steps inside layer pairs | Within a pair, adjacent-layer insertion pins reverse the preceding weld direction. Define pair-changing and same-layer return checks separately. |
| ZPP | Same-layer pins in a Z sequence | Insertion pins have `dl=0` and one slot direction; welds have `abs(dl)=1`. |
| CP | Pins crossing layer groups | The V7.6 production variant requires positive global `Nlayer` divisible by four. In an array of `k=m/3` three-phase sets, each local group `Nlayer/k` must also be positive and even; it need not itself be divisible by four. Insertion pins have `abs(dl)=L_local/2` and welds have `abs(dl)=1`. Other cross-layer constructions need a separate variant contract. |
| LPP | Repeated loops in layer pairs | Insertion pins have `dl=0`; their slot directions are opposite in the two layers of a pair. Welds have `abs(dl)=1`. The admitted divider is only `(1,pp,1)`, with `pp=poles/2`. |

### CP Q-only adjacent P2-parent construction

For integer `q` and a selected divisor `Q>1` of `q`, CP `(Q,1,1)` is
constructed from the same Pattern's public `(Q,1,2)` source. Within each phase,
preserve V7.6's generated branch order and join adjacent source branches as
`(1,2)`, `(3,4)`, and so on. Keep the source branch orientations. Each join is
an insertion connection with `abs(dl)=L_local/2`; the ordinary CP ordered-edge,
phase/polarity, occupancy, and one-pole-region checks still decide each case.
The route requires positive global `Nlayer` divisible by four. For an array
with `k=m/3` three-phase sets, each local layer count `Nlayer/k` must also be
positive and even; for example, global `Nlayer=12`, `m=6` gives two valid
six-layer CP groups. Neutral Regular settings and an insert-side inlet remain
required. Public source and target preflight decide each geometry. A failed
adjacent join remains a case-specific rejection or Candidate; do not substitute
a nonadjacent matching.

### CP pp-divider four-pass weave

For CP `(Q,D,P2)=(1,2,1)`, use the same geometry's public `(1,2,2)` branches.
Within each phase, retain V7.6's generated order: `P1` through `P4`. The
registered shape has four source branches per phase, each with `4L` conductors.
Build the two target paths from `L`-sized slices:

```text
Branch 1 = P1[0:2L] + P2[0:4L] + P1[2L:4L]
Branch 2 = P3[3L:4L] + P4[2L:4L] + P3[2L:3L]
         + P4[L:2L] + P3[0:2L] + P4[0:L]
```

The four-pass source shape follows `q * (poles/2) / D = 4`; the route keeps
the common positive global-`Nlayer`, `Nlayer % 4 == 0`, phase, configuration
and CP edge gates; array-local layer groups must also have a positive even
count.
Public generation remains the admission authority for each geometry. It checks
coverage, equal branch length, phase and direction, CLWP identity, electrical
retention, and the one-pole-region limit. The q=2, pp=4, L=4, m=3 saved sketch
now reproduces publicly as `Validated` with six 32-conductor branches and full
coverage. The former intact-parent matcher has been withdrawn; geometries
outside a registered construction remain `unsupported-yet`.

### CP P2-parent slicing

CP `(Q,D,P2)=(Q,D,1)` uses this constructor in either of two factor domains.
The Q+PP family keeps integer `q>1` and:

1. `Q>1`, `Q|q`, even `D>=4`, and `D|pp=poles/2`.

The PP-only family uses `Q=1`, positive integer `q`, even `D>=4`, `D|pp`, and
either odd `q` or `D≡2 (mod 4)`. Thus odd q can use parent slicing at any
admitted even D, while even q uses it at `D≡2 (mod 4)`; even q with
`D≡0 (mod 4)` remains on the existing four-sector constructors. `D=2` stays
separate. Both families require `ab=Q*D`. Start from the same geometry's
publicly generated CP `(Q,1,2)` reference. Within each phase, preserve the
reference's generated branch order; there are `2Q` parent branches per phase.
Since

```text
Naa_target / Naa_source = (Q*D) / (Q*1*2) = D/2,
```

split every parent into `D/2` equal consecutive slices. Emit target branches
by slice index first and source order second. This gives `Q*D` branches per
phase, each of length `2*q*pp*L/(Q*D)`, without matching or reordering
individual conductors. For the PP-only family, `Q=1` makes the source
`(1,1,2)`, with two parent branches per phase; every admitted even D gives
`D/2` equal slices per parent. `D=2` remains on its separate constructor, and
even-q `D≡0 (mod 4)` continues through the existing four-sector constructors.

Admission also requires positive global `Nlayer` divisible by four, the
supported phase domain, and the neutral Regular, insert-side configuration.
For an array of `k=m/3` three-phase sets, each local CP layer count `Nlayer/k`
must be positive and even; only the global count has the fourfold requirement.
Public source and target preflight still decides each geometry. Public
generation checks the source and target for exact coverage, equal
branch lengths, phase/direction, ordered CLWP identity, CP cross-layer edges,
and the one-pole-region limit. Independent samples include full and proper
Q/D factors, odd and even q, `D=4` and `D=6`, and `m=3`, `m=5`, and `m=6`.
For the six-phase array, identity and CP edges are checked in each independent
three-phase set. The earlier Q>1 representative samples report
`parallel_emf_mismatch`; the six-phase array also reports
`multi_phase_emf_mismatch`. They remain `not strong symmetry layout`, rather
than being rejected for EMF asymmetry.

The PP-only gap is admitted only when the public source and target preflight
pass. The original five `L=4` samples validate representative `D=6`, `10`,
and `14` cases with `q>1`. The q=1 extension passed 27 public requests at
`L=4`, covering `D=6/10/14`, `pp/D=1/2/3`, and `m=3/5/7`. The nine q=1,
`m=9`, `L=4` requests remain disabled because four layers cannot be evenly
assigned to three-phase sets. Direct q=1, `m=3`, `L=8/12` requests also
remain disabled when their public `(1,1,2)` source has duplicate and missing
conductors. These are case-level source boundaries, not a general q=1
exclusion.

The odd-q expansion passed 36 neutral public samples at `Nlayer=4`,
`q∈{1,3,5}`, `D∈{4,8,12}`, `pp/D∈{1,2}`, and `m∈{3,5}`. Exact target paths
match the piece-major slices of the same-geometry public `(1,1,2)` parents.
Every layout passes coverage, branch-length, phase, CP identity, cross-layer,
signed-travel, and electrical-retention checks. Twelve samples have no EMF
error; 24 report only `parallel_emf_mismatch` and remain
`not strong symmetry layout`. Additional exact-path checks pass for
`(q,pp,D,L,m)=(3,8,8,4,5)` and `(5,12,12,4,5)`. A separate three-phase-set
check with global q=1, m=9, and L=12 resolves local q=3 and passes public
generation and per-set identity; the m=6, L=8 local-q=2 control retains its
existing even-q route.

The formula remains subject to actual source generation. At `q∈{1,3}`,
`pp=D=4`, `m=3`, `Nlayer=8`, the public `(1,1,2)` source reports duplicate and
missing conductor positions (78 for q=1 and 270 for q=3), so those requests
remain disabled. The existing `m=9`, `Nlayer=4` boundary also remains disabled
because four layers cannot be divided among three-phase sets. Neither case
proves the formula impossible for geometries whose public preflight passes.

The array controls `q_global=1,m=6,L=8` and `q_global=1,m=9,L=12` resolve to
local q=2/3 and four layers per three-phase set. Twelve requests over
`D=6/10/14` and `pp/D=1/2` passed public generation, coverage, per-set
identity and CP edge checks. Their EMF diagnostics are retained separately;
these were already admitted through local q and do not expand the global-q
predicate. The samples do not certify every layer/phase combination. For
example, the `(1,1,2)` source is disabled for
`(q,pp,Q,D,L,m)=(2,6,1,6,8,3)` because it contains duplicate and missing
conductors. For the earlier Q+PP family, for example,
`(q,pp,Q,D,L,m)=(4,8,2,4,8,3)` is disabled because its public P2 source has
duplicate and missing conductors. With the same q, pp, Q, D, and L but `m=6`,
the two local three-phase sets each use four layers and pass their local
identity and edge checks. Nondivisor Q, odd D, nonzero phase shifts, and other
unsupported factor or source geometries remain outside this route.

### CP Q+PP+P2 parent slicing

For integer q, CP `(Q,D,P2)=(Q,D,2)` uses the public same-geometry
`(Q,1,2)` parent when `Q>1`, `Q|q`, `D>1`, and `D|pp`. The shared divider
identity gives `Naa_target/Naa_source=(Q*D*P2)/(Q*1*P2)=D`: within each
phase, split each ordered parent into D equal consecutive paths. This
produces `Q*D*P2` target branches per phase, with no newly formed connection
edge. The common P2 orientation makes every child N-to-S before the standard
CP coverage, phase, CLWP identity, and cross-layer checks. The reference
generator records directed slot steps from CP's actual connection vectors;
the split carries those steps to each child, where the one-pole-region check
uses signed travel rather than shortest-arc inference.

Keep default factorization on the existing Default route. The selected route
also requires the CP positive global layer count divisible by four, supported
phases, neutral Regular zero-shift settings, insert-side inlet, and public
source/target preflight. For an array of three-phase sets, each local CP layer
count must additionally be positive and even. D may be odd: its value is the
divider ratio, not an independent parity rule. EMF-only asymmetry remains
`not strong symmetry layout` and does not reject an otherwise retained path.

### CP four-sector translation from a P2 parent

For integer even `q>1`, CP `(Q,D,P2)=(1,4,1)` has a registered construction
when the actual pole-pair count is divisible by four. Start from the same
geometry's public `(1,1,2)` branches. For each phase, select the parent whose
first signed slot step is `+τ`, where `τ=mq`; let `N=num_slots`,
`k=N*L/(4m)`, take its second half `H=P[k:2k]`, and calculate
`δ=(H[-1].slot-H[0].slot) mod N`. Translate every node of `H` forward by
these four slot offsets, modulo `N`, to form the target branches:

```text
[τ−δ, τ−1, 2τ−δ, 2τ−1]
```

These computed per-branch inlet positions and the selected source direction
reproduce the saved q=2, pp=4, L=4, m=3 Phase-A conductor groups. Separate
generated checks pass for q=2/4, pp=8, L=4, m=3, and q=2, pp=8, L=4, m=5.
This route still
requires the ordinary insert-side inlet and neutral Regular configuration;
manual inlet-index adjustments are not an alternate production setting. The
public source and full target must pass coverage, phase/direction, ordered
CLWP identity, CP signed-edge, and one-pole-region checks. The neutral result
reports `parallel_emf_mismatch`, so it is retained as `not strong symmetry
layout`; this does not reject the route. The Workbench catalog currently
reports `auto configure pending` for the saved geometry because it has no
verified strong Auto configuration.

Keep odd `q` outside this half-translation constructor, keep `D=4` outside it
when four does not divide the actual pole-pair count, and keep any case whose
public source or target fails its checks outside admission. Odd-q PP-only
tuples may use the separate P2-parent-slice route above when its even-D,
`D|pp`, layer, phase, configuration, and public-preflight gates pass.

### CP PP-sector slices from the four-sector parent

For even integer `q>1`, a selected CP `(1,D,1)` with `D>4`, `4|D`, and
`D|pp` uses the same geometry's public `(1,4,1)` layout. Cut each complete
four-sector branch into `D/4` consecutive equal paths, preserving its conductor
order. Each target path has `2*q*pp*L/D` conductors; the construction creates
`D` branches per phase and introduces no new connection edge. Public generation
checks the four-sector source and every target path for exact coverage, equal
length, phase/direction, ordered CLWP identity, signed edges, one-region travel,
and electrical retention. The q=2, pp=8, D=8 and q=2, pp=12, D=12, L=4,
m=3 cases generate and retain complete CP layouts; their neutral EMF mismatch
is reported separately as `not strong symmetry layout`.

This four-sector cut does not establish a route for `D=2`, `D=6`, odd `D`, or
odd `q`.
Joining adjacent `(1,4,1)` branches for `D=2` produces N-to-N and S-to-S
terminals, failing the independent direction check. The existing D=2 four-pass
weave keeps its separate bounded domain. Any source or target failure at a
different layer count or phase count remains a case-level failure.
The separate PP-only P2-parent-slice route above covers odd q at even D>=4
when its public source and target preflight passes. At `L=8`, however, the
public `(1,1,2)` source has duplicate/missing positions for `q=1/3` at
`pp=D=4`, so those cases remain disabled. The q=2, pp=8, L=12, m=9 case also
fails CP edge validation. A calculated inlet shift and source direction
therefore solve bounded families, not every q/pp/layer change.

The production identity analyzer reconstructs insertion/weld parity from the
stored path and terminal side, then reports terminal I-pins separately from the
body inventory. Pin names describe the observed roles; they are not independent
proof of Pattern identity. The current body profiles are UWP `ALWP`, SSP `ALWP+SLPP`, SLP
`ALLP+SLPP`, TSP `ALWP+CLWP`, TLP `ALLP+CLLP`, ZLP `ALLP+SLPP`, ZPP `SLPP`,
CP `CLWP`, and LPP `SLPP`. Return roles are conditional: a valid short branch
need not exhibit every pin type or return present in its longer construction.
CP's `L/2` role remains CLWP when `L=2`, even though its numeric layer span is
one. This role-based exception avoids relabeling a cross-half construction as
an adjacent-layer wave.

An illegal ordered connection still produces a Candidate identity report.
Missing optional returns and a small-parameter identity overlap do not, by
themselves, produce Candidate status. Identity acceptance does not replace
coverage, phase, actual edge legality, terminal or electrical checks.

### Ordered Pattern identity policy (user-confirmed, 2026-09-24)

**Identity is determined by the complete layer traversal and connection order.**
Evaluate the actual ordered insertion and weld edges of each branch. Pin-type
inventory, pitch magnitude, the selected Pattern name, or the appearance of a
drawing is not identity evidence. Full-path means inspecting every
connection that is present, not requiring every short branch to contain an
entire long-parent period.

- **Pitch independence:** a Pattern specifies the ordered circumferential
  direction and radial layer progression of its ordinary and special
  connections, including insertion/weld side. No numeric pitch, `tau` window,
  or short/full/long pitch label is an identity or Pattern-specific admission
  condition. A constructor may choose a pitch to generate endpoints; that
  choice is output, not a reason to reject a different valid construction.
  Direction from discrete slot coordinates uses the shortest circular travel;
  an exact half-circumference edge has two equal directions. A route intending
  the longer arc needs complete `database.signed_travel[branch_id]` edge steps,
  checked against every physical endpoint, rather than a pitch whitelist.
  Reversal, regrouping and transposition must update that evidence before use.

- **One pole-region transition per connection (user-confirmed, 2026-09-24;
  connection-stage scope clarified 2026-09-29):** every completed insertion,
  weld, or return connection before layout relocation may stay in its starting
  pole region or enter one adjacent pole region along its signed circumferential
  travel. It may not cross two or more pole-region boundaries. For integer or
  positive half-integer q, each region is a half-open interval of exact rational
  width `tau = m*q` in zero-based slot coordinates; compute
  the boundary count as
  `abs(floor((start_slot + signed_step)/tau) - floor(start_slot/tau))`,
  using the unwrapped signed step. This includes a connection wrapping across
  slot zero. With no recorded signed travel, use the shortest circular arc;
  either equally short direction may qualify at exactly half circumference.
  This is a common connection-stage limit for all ten Patterns, not a
  Pattern-specific pitch whitelist. It applies to special returns as well as
  ordinary connections and is checked separately from the order/identity
  signature. A candidate that fails this limit before relocation is rejected
  even when its ordered Pattern grammar otherwise matches. Phase/radial layout
  relocation does not repeat this check on the displayed endpoints.

- **Short branches:** every branch must retain its Pattern's ordinary ordered
  construction. Divider cuts may omit special returns and their associated pin
  roles. In particular, a TLP short branch without a first/last-layer return is
  still TLP when it retains the TLP ordinary construction. Do not require a CLLP
  occurrence merely to prove the label, or borrow another branch's return as a
  substitute for checking this branch.
- **Returns that are present:** check their physical insertion/weld role and
  allowed connection structure. They must not introduce a new connection type
  outside the confirmed Pattern contract. Their pitch magnitude does not
  change the Pattern or independently block route admission.
- **Degenerate overlap:** when the same parameterized construction families are
  structurally distinct at larger parameters, their small-parameter overlap is
  accepted. Preserve the selected Pattern and report the overlap as a diagnostic,
  not a rejection. The larger construction must belong to the same rule family;
  merely changing a label is not a witness. No blanket two-layer exemption may
  suppress an actual illegal connection or sequence.
- **Recognition evidence:** retain branch-level sequence results and compatible
  family signatures. Missing distinguishing features on a short path are not
  evidence that another Pattern has replaced it. Check ordinary progression,
  pair/pass transitions and special returns in their actual order.
- **Production and review:** after the construction and applicable checks pass,
  synchronize the production constructor/admission, Workbench and HTML. Do not
  leave an accepted construction permanently in a research-only state. Deliver
  several representative SVGs from the actual public generator for each Pattern
  completed, showing parameters, branches, connection sides and special returns.

This policy supersedes older requirements for all pin roles to occur, for every
branch to contain a special return, and for every small parameter instance to
have a unique Pattern signature. It does not waive coverage, unique occupancy,
equal branch conductor counts, phase/direction, connection-side or P2
terminal checks. EMF and strong symmetry remain separate diagnostics under the
layout-retention policy. Odd-layer/fractional extensions retain their explicitly
qualified contracts; this work targets integer q, even layers and odd m >= 3.

The shared executable ordered contracts are in `pattern_identity.py`, integrated
through `layout_analysis.analyze_pattern_identity`. The ten-Pattern descriptions
in the HTML are rendered from that same contract registry.

For compatibility with existing evidence binders, a valid ordered check reports
`identity_confidence="full"`, including accepted short and two-layer branches.
This means every present connection passed the selected ordered contract; it
does not mean the geometry uniquely identifies a Pattern. Distinguishability is
reported separately in `identity_distinguishability`, `compatible_patterns` and
`degeneracy`. An invalid ordered check never reports full confidence. Do not
downgrade a passing case merely because a compatibility diagnostic is present.

### SLP pp-divider construction

For SLP `(q-divider, pp-divider, P2)=(1,D,1)`, where `D>1` divides the
pole-pair count, the production constructor derives every branch from the same
no-divider SLP reference. Split each phase reference into pole-pair blocks of
`2L` conductors. Branch 1 takes `pp/D` sectors at anchors
`s0 - 2*j*tau (mod slots)`, using ascending q-lane order for even `j` and
descending q-lane order for odd `j`. Branch `k+1` is the exact circumferential
translation of Branch 1 by `k*slots/D`; layer and in-block order are unchanged.

Ordinary lap edges retain signed pitch `+/-tau` and alternating layer travel.
The same-layer joins between selected blocks may use the adjacent parallel-pin
pitch `tau-1` or `tau+1`. Admission remains factor-driven and case validation
must still establish full unique coverage, equal branch counts, phase and signed
direction, nonzero branch EMF, and the SLP `ALLP+SLPP` identity. Parallel complex
EMF equality is reported separately; mismatch alone retains the layout as
`not strong symmetry layout`. This is
a symbolic construction rule, not a q, pole, layer, slot, or branch-ID whitelist.
Non-neutral TP, shift, inlet-side and inlet-adjustment settings enter this route;
generation and the same topology, phase, edge and identity checks decide each
case. A requested TP setting can leave the selected paths unchanged.

### SSP/SLP proper Q plus PP cut from a PP parent (2026-09-24)

For `(Q,D,1)` with `1<Q<q`, `Q|q`, `D>1`, and `D|pp`, the registered neutral,
Regular, insertion-side constructor generates the same Pattern's `(1,D,1)`
PP parent, then groups complete `2L`-conductor pass blocks into Q children.
SSP takes contiguous whole-block cuts from its lane-major parent. SLP keeps
the sector-major parent's block order and stably filters blocks into
contiguous q-lane cohorts. Each child must
contain exactly `q/Q` distinct q lanes, each repeated `pp/D` times; the Q
siblings partition all q lanes. SSP's selected PP parent has the needed
lane-major order. Existing classifier-default SLP routes keep their own
constructor and admission. A simple contiguous cut of a multi-sector SLP
parent can fail the lane-partition requirement even when stable regrouping
passes, as at `(q,Q,pp,D,L,m)=(4,2,4,2,4,3)`.

Every child is checked by the public complete-path, physical edge, phase,
Pattern identity and (for SLP) weld-direction validators. A short child may
omit a same-layer return while preserving ordered ordinary passes. The same
symbolic odd `m>=3` rule applies to every phase count. Sampled m=3/5/7/9
results are validation evidence, not separate three-phase rules. Parallel EMF
mismatch is retained and reported as `not strong symmetry layout`.
See `get_winding_pattern.py` (`supports_spiral_q_pp_parent_cut`,
`_spiral_q_pp_from_pp_parent`) and the bounded public-route audit in
`workbench_preview/even_d_source_partition_20260923/spiral_q_pp_support_audit_result.json`.

### SLP P2 construction from lap passes

For registered P2 routes, extract each phase's ordered `L`-conductor lap
passes from its no-divider SLP reference. A P2-only `(1,1,2)` branch takes
one half of that reference and may rotate whole passes to place its inlet in
an N region. Full-Q `(q,D,2)` divides each q lane into `2D` sectors of
`pp/D` passes, alternating ordinary and reverse sector order; this variant
requires even `pp/D`. The paired-lane full-PP `(q/2,pp,2)` variant requires
two q lanes per q-divider group and joins their complementary passes with a
signed same-layer return of `-(tau-1)`. These are factor/geometry rules; the
saved q=2, pp=4, L=4 manual paths are comparison examples only.

Proper-Q+PP+P2 `(Q,D,2)` has a separate parameterized parent-regroup formula.
Starting from the public full-Q P2 parent `(q,1,2)`, each target branch takes
`q/Q` adjacent q lanes and `pp/D` passes per lane. It appends complete `2L`
blocks in sector-major order, reversing the lane order on alternate blocks.
The registered domain is integer `q>1`, `1<Q<q`, `Q|q`, `D>1`, `D|pp`, and
even `pp/D`; it also requires positive even local layers, supported phase
topology, Regular settings with zero TP/phase/radial shifts, no inlet
adjustment, and an insert-side inlet. This admits a
proper-Q+PP subset without changing the distinct `(1,D,2)` whole-sector rule.
The source and target still pass public coverage, phase, SLP edge, weld,
terminal, identity, and one-region checks. The executable formula is in
`divider_connection_formulas.py`; `get_winding_pattern.py` selects it from the
divider parameters.

For P2-only, paired-lane full-PP P2 and PP+P2 sector weld-side inlets,
construct the same insert-side branches, rotate each complete conductor path
by one conductor, then orient each path from N to S. The changed physical
opening must still pass the SLP pass/return grammar, phase and electrical
checks, uniform welding direction, terminal polarity and Pattern identity.
Geometries that fail remain rejected case by case. The no-divider SLP route
uses its existing direct weld-side constructor with the same generated checks.
Proper Q+PP `(Q,D,1)` also permits the parameterized one-conductor weld
rotation when `D=pp` (one PP-parent sector per child); repeated-sector cases
remain insert-side-only. The route still uses neutral Regular settings, zero
shifts, no inlet adjustment, and generated path checks. See the Pattern support
matrix for the formula and replayable samples. Full-Q P2 retains its insert-side
guard pending a valid construction.

For `(1,D,2)` with even `pp/D`, one branch joins `pp/(2D)` complete
pole-pair sector paths. Within each sector it takes both passes of every q
lane: ascending lanes alternate pass direction, then unused complementary
passes return through descending lanes. Odd sectors reverse complete pass
order; even sectors precede odd sectors in reverse sector order. Consecutive
sector paths are joined in that SLP order, with every join checked as an
actual insertion-side return. The completed `(1,2,2)` draft at `pp=4` is an
exact comparison case; production validation determines each geometry's
status. Odd `pp/D` cannot use this whole-sector grouping because it would
need a fractional sector; that is a method boundary, not a route rejection.

The production checks use actual conductor coordinates and sides, rather
than Workbench special-edge labels. Lap-pass pitch alternates at adjacent
layers; same-layer returns stay on the insertion side and may have absolute
pitch `tau-1`, `tau`, or `tau+1`. All welds in a layer pair share a direction
after normalization from the lower to higher layer. The shifted phase map
sets N-to-S terminal orientation. Exact coverage, equal counts, phase and
signed direction, Pattern identity, and complex EMF are checked separately;
EMF mismatch alone retains a `not strong symmetry layout`. A stored Workbench
completion flag is not production validation.

Manufacturing advantages and tradeoffs are summarized in the user guide. They do
not substitute for any predicate or acceptance test.

Tables III-V omit TLP and LPP. Do not assign them another family's pin-count
formula. Even for listed families, count actual `(LA, LB, T)` geometries for the
chosen layout, terminal arrangement, and transposition. The paper treats this
tuple as a practical forming-family proxy conditional on compatible end shapes;
equal tuples alone do not prove identical tooling or absence of interference.

### Verifiable Pattern descriptions

Express a proposed rule as **variant/domain → edge or pass → predicate →
independent check**. Declare the divider, transposition and terminal assumptions;
separate ordinary edges, pair changes and returns. Do not infer a universal rule
from one sample or from how an SVG line is bent.
Assign these roles from the declared construction and check their counts; do not
classify an unexpected edge as a return merely to make the predicate pass.
Expected properties must be independent of the generator being tested.

Use ordered `(slot, layer)` coordinates and explicit edge sides. Define signed
slot displacement with the route's intended circumferential direction; screen
direction and unsigned shortest distance are insufficient. Declare the indexing
convention. For the guide's short-span examples, signed shortest steps are
unambiguous; a new long-span route must preserve its intended signed pitch.

Example: for an unshifted even-layer TLP pass using full pitch `tau=slots/poles`,
ordinary layer steps have one sign and magnitude 1, slot steps alternate
`+tau/-tau`, and their sum is `+tau` or `-tau`. A top-bottom return has absolute
layer span `layers-1`. Test these properties on the generated coordinates,
separately from count, phase and EMF checks; reversing the whole branch must
preserve the absolute predicates. Changed transposition or divider routes need
their own qualified predicates.

The guide's short **Check** statements cover the displayed base variants only.
They are necessary structural checks, not complete family-edge oracles or
permission to expand support. If an independent edge oracle is missing, record
the gap and retain candidate status until the proposed route has one.

### Case evidence without domain promotion

The TLP four-layer example demonstrates why signed lap displacement must replace
spiral step counting. It does not establish a general supported range. The TSP
jumper example demonstrates parameter-driven direction, not an edge-index rule.
See the Version 7.5 change log (local research excluded)
for historical results and guide maintenance (local research excluded)
for drawing conventions.

For focused reproductions, use these methods in
[test_winding_dividers.py](test_winding_dividers.py), class `GeneralPatternRuleTests`:
`test_tlp_four_layer_lap_progression_and_electrical_balance`,
`test_tlp_signed_lap_count_across_layers_and_poles`,
`test_tlp_four_layer_terminal_side_and_shifted_phase_map`, and
`test_tsp_signed_jumper_selects_reference_backward_bridge`.
Run only the relevant methods using the [test commands](../../.agents/skills/hairpin-workflow/references/testing.md).
Passing sample tests is evidence for those cases, not proof of all input tuples.

## 4. Common construction and validation gates

Apply independently; passing one gate does not imply the others pass. Software
acceptance needs the declared route's topology, edge, phase/EMF and applicable
symmetry checks. Evaluate mathematical twisting constraints where modeled; report
unmodeled tooling/clearance checks as unverified engineering requirements.
Software acceptance must not be described as manufacturing certification.

1. **Count and occupancy:** an equal-length full winding has
   `slots*layers/(phases*Naa)` conductor sides per branch. Check integer counts,
   every required slot-layer occupied exactly once, no unknown positions, and
   the correct branch count. Two-leg pins and terminal/I-pin arrangements must
   be accounted for before converting conductor-side counts to physical pins.
2. **Phase and direction:** every branch stays in its intended shifted phase
   map; successive in-slot conductor directions alternate. Preserve the signed
   path and phase assignment after transposition or reversal.
3. **Pattern edges:** validate ordered circumferential directions, layer
   changes, insertion/weld sides, returns, and wrap. Record actual slot pitches
   as construction data, not numeric identity/admission gates. A path with full
   occupancy can still violate its Pattern through its connection order.
   Before layout relocation, every connection is limited to one pole-region
   transition as defined above; lap pole-region tracking follows signed movement.
4. **Uniform welding side:** same-layer conductors use consistent twisting
   direction and angle under the paper's construction rule. A drawing or
   topology validator alone does not establish tooling or clearance feasibility.
5. **Electrical balance:** assess equal nonzero complex fundamental EMF for
   parallel branches and the intended multiphase relationship. Equal EMF
   magnitudes alone are insufficient.
6. **Strong symmetry:** inspect balanced signed layer-phasor distribution per
   branch as well as electrical balance. Global occupancy and fundamental-EMF
   equality alone do not prove equal layer exposure, AC impedance, or loss.
7. **Physical realization:** evaluate return clearance, bend radius, insulation,
   twisting/welding access, and busbar geometry for the actual design. Software
   topology acceptance does not certify these manufacturing properties.

Use the [divider rules](../../.agents/skills/hairpin-workflow/references/divider-rules.md)
for common P2 N-inlet/S-outlet orientation and candidate-status boundaries.

### User-directed parameterized exploration constraints (2026-09-28)

**2026-09-29 TSP update:** the user approved both circumferential directions
for top-bottom insertion returns, while keeping ordinary spiral passes,
uniform lower-to-higher weld direction per layer pair, and the one-pole-region
edge limit. The new complete-pass partition family closes the saved unsupported
integer-q routes, including `(1,2,1)` and the interior-gcd q-only case. Its
parameters, two-pass minimum, native/array scope, and independent checks are in
[the current support rule](PATTERN_DIVIDER_FORMULA_SUPPORT.md#tsp-regular-manual-route-closure-2026-09-29).
The user's subsequent Regular TSP feature decision rejects any integer-q
route with `2*q*pp*L/Naa < 8` conductors per branch, independently of the
new family's structural `2*L_local` two-pass requirement. Retained
EMF-asymmetric public layouts display `not strong symmetry layout` even when
a saved manual draft exists; that draft remains exploratory.
Above that floor, existing constructors retain their own domains and precedence. The dated
constructor-specific boundaries below do not exclude this new family.

These constraints guide formula derivation across Pattern variants. TSP
`(1,D,2)` and the bounded TSP `(Q,1,1)` route now have production formulas
described in the support matrix. The other items remain exploration
constraints. Production status still comes from the resolver and full
generated-layout checks, not this note alone.

1. **TSP `(1,D,2)` pole-region inlets.** The fixed-lane formula selects
   `D` equally spaced pole-pair regions and two inlets per region, one from
   each outer layer. It is admitted only when the q-lane residue partition and
   public TSP checks pass; `D|pp` alone is insufficient. For phase-set arrays,
   apply the formula with each set's local q and layer count, then validate the
   mapped global paths. The saved `(1,4,2)` drawing matches the generated
   phase-A paths. Workbench `(1,4,1)` and `(1,2,1)` remain P2=1 references, and
   TSP `(1,2,1)` now uses the distinct complete-pass partition family.
2. **SSP full-Q alternate conductor sets.** A full-Q SSP construction may use
   a different conductor set. Derive its special-connection types and their
   positions relative to the pole region and signed travel as formulas across
   `q`, `Q`, `pp`, `L`, and `m`. Check ordered SSP identity, PP-sector and
   q-lane coverage, and the complete generated path; a hand-selected set or a
   matching branch count is not sufficient evidence.
3. **TSP/TLP q-only special returns.** For TSP `(Q,1,1)`, adjacent same-phase
   branches from the public `(Q,1,2)` source are joined in generated order.
   Its seam pitch is parameterized as `r*tau±1`, with
   `tau=m_local*q_local`, `g=gcd(L_local/2,pp)`, and
   `r=min(2g-1,2pp-2g+1)`; `r=1` is required by the registered one-region
   boundary. Admission requires integer even `Q>1`, `Q|q`, `pp>1`, even local
   `L>=4`, and `g in {1,pp}`. Proper-Q source completion uses `q_local/Q`
   consecutive q-lane sweeps. TLP `(Q,1,1)` now joins adjacent same-phase
   branches from the public full-Q `(Q,1,2)` source. Its registered domain is
   integer even `Q=q>=2`, `pp>=2`, even `L>=2`, and one native phase set.
   The two Q-branch outer-layer cohorts stay intact under adjacent pairing;
   each pair joins adjacent q lanes. With `tau=m*q`, the oriented top-bottom
   seam pitch is `tau±1` and is checked for at most one pole-region crossing.
   Both routes require neutral Regular settings, zero shifts, insert-side inlet,
   and public source/target validation. TSP `(1,2,1)`, TLP proper-Q, and
   phase-array TLP q-only tuples remain outside these formulas. The current TLP
   finite matrix moves six q-only requests to supported; its two proper-Q
   requests remain `unsupported-yet` and its existing rejected request stays
   rejected. See the support matrix for public samples and boundary evidence.
4. **Preserve the classic body and allow layer degeneration.** Keep the classic
   body construction intact while allowing q-position changes within the same
   layer and pole region. Derive two-layer behavior as the degenerate case of
   the four-layer formula where the parameterization remains meaningful; check
   edge roles independently when the layer difference no longer distinguishes
   insertion from welding. Admission still requires public generation and
   independent occupancy, phase/direction, Pattern identity, edge, and
   electrical checks.

### TSP q-only adjacent P2-parent pairing

For `(Q,1,1)`, join adjacent same-phase branches from the same Pattern's
`(Q,1,2)` source in V7.6 generated order. The registered integer domain is
even `Q>1`, `Q|q`, `pp>1`, even local `L>=4`, and
`gcd(L/2,pp) in {1,pp}`. Its top-bottom seam magnitude is `r*tau±1`, where
`tau=m_local*q_local`, `g=gcd(L_local/2,pp)`, and
`r=min(2g-1,2pp-2g+1)`. Proper-Q sources are completed by `q_local/Q`
consecutive q-lane sweeps. The public source and target must pass coverage,
phase/sign, N-to-S, phasor, TSP edge, ordered identity, one-region, and
electrical-retention checks. Phase-set arrays must pass per-set formula and
mapped aggregate checks. The fixed six-geometry q-only cell changes from 0 to
2 supported requests; six remain `unsupported-yet` and its existing rejection
is unchanged. Public samples cover native `m=3/5/7`, including proper-Q sweeps
of two and three q-lanes, and arrays `m=6/9/12`. The five native layouts are
`Validated`; the three arrays retain valid local and aggregate identities but
remain `retained-not-strong` for EMF-only asymmetry.
The adjacent-parent formula remains bounded as stated. Other integer-q cases,
including `(1,2,1)`, can now use the separate complete-pass partition rule;
neither formula admits shifted or non-Regular settings.

### Common q-and-pp second-sector deployment

For registered `(Q,2,1)` routes, use the same Pattern's `(Q,1,2)` construction
as the source. Identify the source cohort from the unshifted inlet pole index,
not database order or N/S sign. Move the second pole cohort by `slots/2-tau`,
reflect its layer traversal, preserve conductor order and insertion/weld parity,
then reapply destination-layer phase shifts. UWP, TSP, TLP and CP also reflect
pole travel around the inlet belt, retaining the within-q lane, so layer reversal
does not reverse physical welding direction within a layer pair.
The common implementation currently registers
TSP, TLP, CP and ZPP; each still passes its own edge and body-pin predicates.
ZPP currently retains the older mapping: a bounded weld-direction audit found
conflicts, and simply reflecting its travel fails its existing Z-edge constraint.
It remains an unresolved topology finding, not a verified welding layout.

For the registered integer ZPP `(Q,D,2)` construction, `Q*P2=q`. Thus `P2=2`
requires `q=2*Q`; every positive odd integer effective q is explicitly
rejected for this construction, for all `D`. Phase-set routes apply the rule
to each local q, so a fractional global q is not classified as odd by itself.
This boundary is recorded in `PATTERN_REJECTION_REASONS.md` and does not claim
that every physical layout at odd q is impossible.

The ZPP PP-only `(1,D,1)` route uses the same-Naa public `(D,1,1)` q-parent.
Direct phase domains require `q=Naa=D` and `D|pp`. Let `r=pp/D`; choose the
least positive stride `a` for which `gcd(a,D)=1` and `gcd(D,2*r*a-1)=1`, then
translate source branch `j` as a whole by `((a*j) mod D)*num_slots/D`. This
preserves conductor order and signed travel while permuting both sector
offsets and lane classes. The former admission is the `a=1` subset, so its
branch offsets stay unchanged. `D=2` remains the existing half-turn and keeps
its former direct `q=Naa=2`, even-`pp` domain. Direct routes still require
positive even layers, a supported phase/topology, neutral Regular settings,
weld-side inlet, and a generatable public parent. All 36 requests that were
disabled by the old gcd condition in the bounded `D=2..10`, `pp/D=1..6`,
`Nlayer in {4,6}`, `H in {3,5}` sweep now pass public generation and route
validation. In particular, direct `(q,pp,Nlayer,H,D)=(3,6,4,3,3)` is now
Validated with `a=2`.

A separate PP-only constructor derives target `(1,D,1)` from the public
`(q,1,1)` parent when `D>q`, `q|D`, and `D|pp`. Each target branch uses the
centered window of one q-parent, of length `parent_length/(D/q)`, then places
that ordered window in its indexed sector. The old `q=D` whole-path route
keeps its existing construction. The support matrix records the factor guards,
configuration requirements, sample coverage, and generated-path evidence.

Arrayed `H=3s` routes retain the prior `a=1` local-set admission and its
integer set-slot offset (`s|2D`) and even positive local-layer (`2s|Nlayer`)
requirements. Arrayed `a>1` remains `unsupported-yet`: a sampled mapped global
layout has signed edges crossing two pole boundaries, despite valid local
formula results. An older admitted `a=1` array sample also has 12 such edges
under an independent aggregate audit; local checks do not establish global
edge validity. This is an existing validation gap and is recorded separately
from the direct-route expansion. The formula does not change the separate
`(Q,2,1)` direction findings.

This deployment does not create support when the q/P2 source is absent. BWP/SSP
P2 exclusions, SLP and ZLP Q>1 missing source routes, and LPP's full-PP identity guard
remain effective. Reference coverage failure, deployed coverage failure and a
Pattern identity collision keep their respective Disabled or Candidate status.
Unsupported software routes remain unsupported, not proven physically impossible.
For TSP/TLP specifically, PP alternatives without a registered constructor are
`unsupported-yet`, not blanket rejects. A registered route that fails its
reference, deployment, edge, occupancy, or identity validation remains a
case-specific rejection with the actual reason.

TSP's existing parameterized PP-only identity route for `(1,2q_s,1)` transfers
the public full-local-q `(q_s,1,2)` parent unchanged when integer `q_s>=2`,
`2q_s` divides the pole-pair count, and the existing TSP layer, phase,
configuration, and public-generation checks pass. For an array of `k=m/3`
three-phase sets, each set uses `q_s=k*q` and the layer count must be divisible
by `k`; a symmetric polyphase winding uses `q_s=q`. The same-Naa identity
transfer preserves every ordered path and validates final-path phase/direction
and electrical retention. EMF-only mismatch remains a retained
`not strong symmetry layout`. A parent that does not cover the requested
branch cannot establish this identity formula's support. Other PP tuples may
use the distinct complete-pass partition rule without changing that parent.

### Approved TLP pp-divider-two deployment

For every TLP divider tuple, the combined PP/P2 split must satisfy
`pp-divider * P2-divider <= pp`, where `pp = poles/2`. These factors share the
available pole-pair division; a tuple that exceeds it is explicitly rejected
by the common route resolver and Workbench catalog.

For TLP `(Q,D,P2)=(1,2,1)`, deploy the raw same-Pattern `(1,1,2)` reference by
moving the second pole cohort by `slots/2-tau` and reflecting both its layer order
and circumferential pole travel. This 2026-09-22 correction supersedes the earlier
layer-only mapping. Normalize every weld from the lower-numbered to the
higher-numbered layer: all welds within a Layer_Pair must share that direction.
Welding-side q-lane transposition is forbidden, including Auto recipes.
The mapping preserves ALLP+CLLP identity. The q-lane boundary is a top-bottom insertion return and may have
absolute pitch `tau-1`, `tau`, or `tau+1`; ordinary adjacent-layer edges retain
absolute pitch `tau`. This deployment approval applies to TLP. The earlier
TSP return-direction rejection was superseded by the explicit 2026-09-29
decision above; TSP `(1,2,1)` now uses its own complete-pass constructor.

The route is factor-driven and still requires a usable raw reference, complete
unique occupancy, equal branch lengths, phase/direction validity, retained
electrical diagnostics, and full Pattern identity. It does not admit other PP
factors or establish end-turn clearance and tooling feasibility.

V7.6 also has a parameterized even-divider cut from the public `(Q,2,1)` parent
to `(Q,D,1)`, including a bounded full-Q extension and equal three-phase-set
mapping. This is executable route support, not an expansion of the paper's
definition or a manufacturing claim; see the current formula and evidence
record in [PATTERN_DIVIDER_FORMULA_SUPPORT.md](PATTERN_DIVIDER_FORMULA_SUPPORT.md).

Auto results must pass the welding constraint before ranking and replay.
The earlier `Times=1, tp_start_index=1` example is superseded when it moves a
q-lane change onto a weld. Search may select insertion-side transposition; do not
hard-code replacement parameters or bypass TLP identity and edge checks.
First/last-layer return direction is measured relative to layer traversal, so
last-layer-inlet branches legitimately have negative circumferential returns.

### TLP mixed PP+P2 short-unit construction (2026-09-24)

For `(Q,D,P2)=(1,D,2)`, use the public `(1,1,2)` TLP layout as the
same-Pattern source. Split each source branch into `D` equal contiguous units
at complete `L`-conductor lap-pass boundaries. The two source inlet cohorts
already supply opposite circumferential and layer traversal; do not reverse
only one of those directions. Deploy corresponding units by whole pole-pair
sector rotations derived from `slots/D`. The saved `q=2, pp=4, L=4, D=2`
Workbench example is reproduced by rotating each second unit by `slots/2`.
When that placement overlaps, an unrotated complete-pass cut is permitted
only if the children of every source branch already occupy distinct PP sectors
at the required `pp/D` spacing. The example's slot offsets are not general
rules.

This constructor requires integer positive q, `D>1`, `D|pp`, `2D<=pp`, odd
`m>=3`, and even `L>=4`. Each actual generated case still checks full
occupancy, equal branch length, phase membership, N-to-S terminals, TLP
ordered identity, one-pole-region edges, same-pair weld direction and
electrical retention. A failed placement rejects that method for the case,
not every possible TLP construction. Short units may omit a first/last-layer
return while preserving the ordinary TLP order.

### TLP Q=2 plus PP plus P2 parent-slice construction (2026-09-29)

For `(Q,D,P2)=(2,D,2)`, take the public `(1,D,2)` TLP path for the same
geometry and split each source branch into two equal, contiguous pieces at
complete layer-pass boundaries. The source carries D-sector placement and
both outer-layer inlet cohorts. Each target path has
`L*(q/2)*(pp/D)` conductors; no physical connection is added or changed.
Require even integer q, `D>1`, `D|pp`, `2D<=pp`, even `L>=4`, and at least
two complete passes per child. The two starts in each selected positive
sector and outer layer must use distinct q-lanes. They may be adjacent:
q/2 spacing is recorded as a diagnostic, not required when the complete
path passes independent checks.

The production route requires a public parent that generates, neutral Regular
settings, zero shifts and transposition, and the insert-side inlet. Every
generated child must preserve phase membership, N-to-S orientation, unique
occupancy, TLP ordered identity, weld direction, and electrical retention.
The saved q=2, pp=4, L=4 eight-branch draft matches the public target path
set but remains exploratory evidence. A parent deployment failure is an
`unsupported-yet` construction boundary, not a physical impossibility
proof. Three-phase-set arrays reuse the same local formula only when each
local set has at least four even layers; a two-layer local degeneration
remains unresolved. See the formula and sampled domain in
[PATTERN_DIVIDER_FORMULA_SUPPORT.md](PATTERN_DIVIDER_FORMULA_SUPPORT.md).

### Distinct SSP P2-only construction (2026-09-22)

SSP `(1,1,2)` uses two equal q-lane cohorts from its `(2,1,1)` source.
Reflect the second cohort's layer order and circumferential pole travel around
its inlet belt while retaining within-q lane positions. The result reproduces
the reviewed saved draft and changes physical insertion returns and terminal
layers; equal occupied positions do not make it a q-only duplicate.
All first edges remain welds. Welding edges retain full pole pitch and one
lower-to-higher direction. Same-layer insertion returns remain on the first or
last layer and may connect different q lanes within the pole belt.

The geometric domain is even positive integer q, even layers, at least two pole
pairs, odd phase count at least three, zero shifts and insert-side inlet. Odd
integer q is rejected for this registered construction because two equal
q-lane cohorts cannot be formed; this does not exclude another physical
construction. Other missing geometry support remains unsupported-yet. Mixed P2 tuples remain excluded by
[the rejection registry](PATTERN_REJECTION_REASONS.md). Existing P2=1 routes
keep their constructors. Apply common P2 N-to-S orientation after construction.

The q=2 / pp=4 / L=4 / m=3 raw draft has unequal branch EMF and remains a retained
non-strong layout. Auto uses insertion-side transposition to obtain a distinct,
electrically valid strong result and hence `Validated`. Other geometries must
pass their own Auto checks; fourteen cases in the bounded audit remain pending
(twelve pp=3 cases and two q=6/pp=2/L=4 cases).
See `workbench_preview/ssp_p2_equivalence/` for exact side-labelled edge comparisons,
all common slot rotations, candidate implementations and geometric bounds.

### ZLP P2-only mirror construction (2026-09-23)

ZLP `(1,1,2)` uses a complete default `(1,1,1)` reference for each phase.
Orient that path N-to-S, split it into two equal halves, and keep the first half
as Branch 1. Branch 2 reflects Branch 1 across the layer order and a
phase-dependent circumferential axis. In zero-based unshifted slots the axis is
`K_phi=([m(L-2)+1]q-1+2q*phi) mod slots`, where `m` is the common odd phase
count. At `m=3` this reduces to the earlier `(3L-5)q-1+2q*phi` axis. The
additional `m q` offset for each layer pair beyond the first places the
mirror on the other conductor positions of the same phase. Restore the target
layer's shift after reflection. This puts the two P2 inlets on opposite
boundary layers. It is a
separate construction from the pp-divider circumferential array.

Evaluate ZLP edge pitch and the pair-local zigzag property in unshifted slot
coordinates. The physical slots still determine occupancy, phase membership,
terminal polarity and EMF. Existing `ALLP+SLPP` body roles remain required;
no extra pin type is introduced. The public route requires integer q, even
layers and a complete reference, then validates each generated geometry.
Odd layers and fractional q are outside the current P2-only construction.
The eight reviewed parameter layouts are stored in
`workbench_preview/zlp_p2only_parameter_review_20260923/`.

### ZLP PP plus P2 cut from a complete P2 parent (2026-09-24)

For a selected `(1,D,2)` with `D>1` and `D|pp`, generate the same geometry's
validated ZLP `(1,1,2)` parent. Divide each complete, ordered parent branch
into D equal contiguous children. Even L makes each child length
`q*(pp/D)*L` even, preserving insertion/weld parity. The public route then
checks full occupancy, phase and signed travel, every pair-local ZLP edge,
Pattern identity, nonzero branch fundamentals and each P2 N-to-S terminal.
It uses one odd `m>=3` parameter, with no three-phase-specific constructor.
Connection-stage TP and inlet settings still require the configured P2 parent
and children to pass path validation. Post-connection phase/radial shifts use
the common relocation rule above and retain independent electrical checks.

This is a parent-dependent construction. If the P2 parent fails at a geometry,
the child route remains case-pending rather than physically rejected. After
the symbolic odd-`m` mirror-axis repair, the neutral finite PP+P2 audit
replays all 540 selected cases at q=1..6, pp=2..10, even L=2..12 and
m=3/5/7 with complete parents and independently checked target paths. An
earlier `(q,pp,D,L,m)=(2,4,2,4,5)` parent failure belonged to the old
three-phase axis and is historical rather than a current exclusion. See
`get_winding_pattern.py` (`supports_zlp_pp_p2_source_cut`,
`_zlp_pp_p2_from_p2_parent`) and
`workbench_preview/even_d_source_partition_20260923/zlp_pp_p2_source_cut_audit_result.json`.

### Project layout-retention policy (2026-09-21)

UWP proper-Q q-only series variant: for `(Q,1,1)`, `1<Q<q`, `Q|q`, join each
phase's oriented `(Q,1,2)` source branches i and Q+i at a same-layer outlet/inlet
connection. This explicit series weld is an authorized exception to ordinary
UWP adjacent-layer edges. Preserve each source segment's path and travel
direction; do not apply a whole-branch single-direction predicate across the
series junction. Validate source edges, the same-layer junction, unique
occupancy, equal resulting branch lengths and N inlets independently.

EMF asymmetry alone must not reject a layout or define its construction boundary.
If conductor positions are not occupied more than once and every branch has the
same conductor count, retain the layout. An EMF-asymmetric layout is managed as
`not strong symmetry layout`; this applies to all Patterns, integer/fractional q,
divider routes, transpositions and phase shifts.

Continue calculating and displaying EMF and symmetry results. Do not discard
layouts or suppress construction merely because equal-EMF constraints fail.
Retaining a layout does not certify strong symmetry, complete coverage, legal
Pattern edges, correct phase/direction or manufacturing suitability: preserve
those independent diagnostics rather than treating retention as their approval.

This policy supersedes historical EMF-only rejection rules. It is a project
requirement; existing executable EMF rejection guards are not changed by this
documentation update and must be brought into alignment separately.

## 5. Terminals, transposition, and code ownership

### Workbench Advance for unsupported formulas (project rule, 2026-09-22)

For a selected formula that has no implemented connection construction, build
the exploratory Advance reference from the **same Pattern's default layout**.
Ignore the selected divider tuple and selected Naa when generating that
reference; retain them as the target draft's identity and conductor-count limit.
Do not substitute a different Pattern or infer support for the selected formula.

1. Generate the reference using the Pattern's default divider tuple and default
   Naa for the same slot/pole/layer/phase geometry. Preserve its conductor order,
   phase membership and insertion/welding sides. Neutral transposition remains
   neutral; loading a reference does not authorize automatic transposition.
2. Start with default branch 1 of the selected phase. On reaching its outlet,
   connect to default branch 2's inlet, then branch 3, and so on in default order.
   These are reference branches inside the current exploratory path, not a
   request to replace the selected target Naa with the default Naa.
   ZPP uses the q-lane rule below instead of a whole-branch series join; its
   default outlets can be separated by more than one layer.
3. Advance ordinary connections until the next Pattern-defined special
   connection, and pause **before** adding it. Show its type and exact default
   endpoint as the pending connection.
4. Clicking Advance at a pending special adds **only that one special connection**
   and stops immediately. A further click resumes ordinary progression until
   just before the next special connection. Consecutive special connections
   require one click per edge. Manual special-edge entry remains available.
5. TLP's special connection is its first-layer/last-layer return. Its ordinary
   lap steps must not be classified as wave jumpers or stopped by another
   Pattern's edge rules.
6. LPP's full-PP reference completes its loop block before moving to the next
   layer pair. For q=2, the first block has eight conductors: Advance stops at
   conductor 8 and proposes the weld-side edge into layers 3/4. This is a
   reference rule, not admission of a smaller PP factor.
7. Maintain one centrally accessible special-connections table with an explicit
   entry for every Pattern. Each entry identifies its ordinary/special boundary,
   applicable variant, connection side, and endpoint rule. Advance classification,
   pending-edge descriptions and the Workbench table view must use that same
   source; do not maintain independent rule copies in UI handlers.
8. For Patterns other than ZPP, a default-branch outlet-to-inlet join is an
   explicit exploratory series connection and a pause point. Preserve
   insertion/welding parity and reject duplicate or already-occupied endpoints.
   Stop at the current target branch conductor limit, exhausted reference, or a
   reported connection conflict.
9. If a Pattern has no generatable default reference, or its applicable special
   connection rule is undefined, report that limitation. Do not silently use a
   BWP/UWP fallback, invent an endpoint, or promote the formula to supported.

### ZPP q-lane exploratory reference

The Workbench can derive a zero-extra-transposition ZPP reference from the same
Pattern's public Regular paths when `m=3` and q is a positive integer. Let
`tau=m*q`. Replace each same-layer reference pitch with its signed `tau`, keep
the public layer-change pitch, and accept the transformed set only when every
edge preserves phase and alternating polarity, each path has unique conductors,
all paths have unique occupancy, and each path remains in one physical q-lane.
The lane key is `(slot - layer_shift) mod q`, with slot wrapping at the full
slot count. This rule has been sampled at q=3 and q=4; other domains remain
unverified unless the same checks pass.

Advance follows legal unoccupied ordinary connections in the current q-lane.
When none remain, the pending special transition uses
`delta_slot = direction*(m*q) + lane_delta`, where both `direction` and the
adjacent `lane_delta` are +1 or -1. An insertion transition stays in the same
layer; a weld stays within its adjacent layer pair. The target must preserve
phase, polarity, occupancy, and the selected edge side. Advance pauses before
the transition and adds only that edge on the next click. The four-conductor
ZPP checkpoint remains a review pause and does not create a connection.

This is an exploratory Workbench reference rule. It does not change ZPP
production admission, mark an unsupported divider tuple `Validated`, or alter
the public Regular paths. The direct public-path reload remains available for
comparison.

Reference selection: enumerate default Naa values in ascending order and select
the **smallest generatable Naa** for the same Pattern and geometry, independently
of the target Naa. Obtain its default dividers through `classify_branch_mode`
for integer q, or the implemented fractional default route. Failed references
do not justify substitution of another Pattern. Display and export the selected
reference Naa/dividers separately from the target Naa/dividers.

For each subsequent target branch, align the reference to its actual inlet slot
and layer. A last-layer inlet requires inward layer traversal and a corresponding
reversal of circumferential travel; reflecting layers alone is insufficient.
For a manually selected ZPP inlet on a layer with no compatible reference anchor,
retain the unused same-phase inlet as an unaligned exploratory branch. Record the
alignment failure and continue checking each later connection; automatic inlet
selection still requires an aligned reference. This does not admit the target
divider formula.
Compare welding travel in a common geometric orientation, from the lower-numbered
layer to the higher-numbered layer of each layer pair. Opposite signed travel
within that pair is a conflict even when conductor path traversal is reversed.
Preserve layer shifts, phase membership and occupied positions during alignment.
Try compatible reference inlets before rejecting a placement; arbitrary slot
reflection is not phase-preserving for every q-position. Do not mutate an earlier
branch's reference when aligning the next branch.

The executable registry is `pattern_rule_workbench.PATTERN_SPECIAL_RULES`, viewed
in the Workbench's **Special Connections** tab. BWP uses same-layer turnaround
and nonordinary-wave jumper rules; UWP uses nonordinary-wave jumper rules;
SSP/SLP/ZLP use same-layer returns; TSP/TLP use top-bottom returns. At two layers,
TSP/TLP insertion-return roles distinguish them from ordinary welding steps.
CP/ZPP retain their reference body pins as ordinary. LPP retains SLPP body pins
and marks the weld-side move to the next layer pair as a special pause. All
Patterns expose default-branch series joins as
explicit pause points. These rules are scoped to the generated base reference;
new variants require an explicit registry rule, not a visual guess.

For CP, Workbench Advance also stops after every four conductors in the current
draft path (at 4, 8, and subsequent multiples of 4), provided the target branch
is not complete. The next click resumes the ordinary reference path. This is a
review checkpoint only: it does not reclassify the CP connector or its CLWP pin
identity.

Implementation and verification evidence belong in the active-version changelog.
Exploratory series joins do not certify Pattern legality, EMF balance or
manufacturing feasibility. Keep these diagnostics separate from layout retention.

The **side of an edge** identifies an insertion pin or weld connection. The
**terminal side** identifies the exposed branch ends. Moving terminals changes
where a branch is opened and may require return pins or path rotation; do not
change only labels or line styles. Preserve conductor order, phase polarity,
start IDs, plots, and exports together. Current terminal requirements come from
`pattern_requires_weld_side_inlet`, not an independently maintained UI list.

Use `draw_figure.initial_connection_side` and `next_connection_side` for the
main plot's edge-side convention: insertion-side terminals start with a weld
edge, weld-side terminals start with an insertion edge (before any branch
adjustment). Do not infer the first edge directly from the terminal label.

Project transposition rule: neutral Regular settings must not exchange branch
q-position groups. UWP Q/P2 and derived Q/PP routes use their untransposed
base for zero settings; only explicit Auto enables the searched permutation.
Permutations advance between intact weld pairs, on insertion edges only.
Workbench Auto Configure, catalog probing and route loading share a verified
configuration result, including existing Default/Validated formulas. Their
reference transitions come from the exact configured paths. This automatic
operation is distinct from direct neutral Regular generation, which preserves
the untransposed base. Exploratory Times/Interval cuts also exclude welding edges.
Unequal EMF remains a separate retained-layout diagnostic.

The paper distinguishes localized transposition (pitch changes at selected
returns/boundaries) and continuous transposition (repeated pitch changes).
Its term "non-integer pitch" in this discussion must not be interpreted as
permission to place a leg at a fractional physical slot: the generator still
needs valid discrete endpoints. Neither strategy guarantees strong symmetry
without checking the generated branches and shifted phase map.

| Responsibility | Existing implementation to inspect |
| --- | --- |
| Production orchestration | `get_winding_pattern.py`: `get_winding_layout`, `_dispatch_winding_pattern`; use the public entry for acceptance tests |
| Canonical names and terminal requirements | `get_winding_pattern.py`: `PATTERN_REGISTRY`, `normalize_pattern_name`, `pattern_requires_weld_side_inlet` |
| Base availability and selected routes | `get_winding_pattern.py`: `resolve_pattern_route` owns status/reason/configuration; `selected_integer_divider_route` is the compatibility wrapper |
| Ordered paths and terminal relocation | `get_winding_pattern.py`: `pattern_<CODE>`, `shift_inlet_to_weld_side`, `orient_p2_branches_n_to_s` |
| Shared divider-route path formulas | [divider_connection_formulas.py](divider_connection_formulas.py): divider-ratio partition/join (including CP parent slices and CP/UWP q-only joins), SSP/SLP Q-lane parent cuts, CP four-pass weave, and CP parent-half translation; route admission and post-generation checks stay in `get_winding_pattern.py` |
| Half-integer-q connection formulas | [half_integer_q_connection_formulas.py](half_integer_q_connection_formulas.py): exact UWP `(q,1,2)` P2 parent, `(q,2,1)` second-cohort transfer, and BWP alternating base wave; route admission, public phase processing, and post-generation checks stay in `get_winding_pattern.py` |
| Independent occupancy and complex EMF | [explicit_connections.py](explicit_connections.py): `validate_branches`; it explicitly leaves Pattern-specific edge checks to callers |
| Existing route-specific connection checks | `get_winding_pattern.py`: `validate_pp_only_spiral`, `validate_pp_only_uwp`, `validate_uwp_proper_q_factor`, `validate_uwp_balanced_paths`, and relevant `validate_selected_*`; these retain side, span and direction checks without numeric Pattern pitch gates |
| Explicit sides and shifted edge pitches | `explicit_connections.py`: `ConnectionEdge`, `compile_edges`; [phase_topology.py](phase_topology.py): `phase_map`, `shifted_connection_slot` |
| Pin-role and Pattern identity | [layout_analysis.py](layout_analysis.py): `analyze_pattern_identity`; body pins and terminal I-pins are separate |
| Layer-phasor symmetry reporting | [layout_analysis.py](layout_analysis.py): `check_symmetry` and signed-occupancy reporting |
| Admission explanations and exploration | [pattern_rule_workbench.py](pattern_rule_workbench.py) and the linked support matrix |

Workbench-extracted edges are a sample vocabulary, not an independent family
specification. `extract_reference_constraints` and `generate_route_drafts` now
use the same first-edge convention as the main plot: insertion-side terminals
start with a weld edge, and weld-side terminals start with an insertion edge.
Treat exported edges as bounded evidence, not a replacement family definition.

### Production integration

- **Existing Pattern extension:** state the symbolic target domain and affected
  predicates, then update the existing generator and its route-specific checks.
  Preserve rejection of out-of-domain inputs; follow the existing divider workflow
  for admission and workbench/support-document synchronization.
- **New Pattern:** also connect the canonical registry/aliases, decomposition and
  configuration guards, and `_dispatch_winding_pattern`. Verify discoverability
  through the existing UI/catalog; avoid adding a second Pattern list.
- **Both:** add independent positive and rejection tests through
  `get_winding_layout`, not just `pattern_<CODE>`. Check actual edges, full
  coverage, phase/EMF, final P2 endpoints and start IDs. Include relevant shifted,
  transposed and relocated-terminal cases, or explicitly exclude them from the
  proposed domain. Confirm existing admitted cases remain valid.

Reuse [the workflow](../../.agents/skills/hairpin-workflow/SKILL.md) for sequencing
and completion, and [focused verification](../../.agents/skills/hairpin-workflow/references/testing.md)
for commands. Do not create a new process or infer promotion from diagram checks.
