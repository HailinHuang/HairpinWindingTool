# Pattern Divider Formula and Support Matrix

## Version 7.6 current status

ZPP `q_and_p2`, `(Q,1,2)` with `Q>1`, is explicitly rejected with
`q and p2 share same route` (user decision, 2026-10-02). See the
[rejection registry](PATTERN_REJECTION_REASONS.md).

### TLP even-Q cohort joins (owner approved, 2026-10-02)

The existing `tlp_q_only_pair_join` route now covers `(Q,1,1)` for even
`2<=Q<=q`, `Q|q`, integer q, at least two pole pairs, and even `L>=2` in
one native phase set (`m=3` or a supported odd m not divisible by three).
Use the public full-q `(q,1,2)` source, with `2q` parents per phase and
q parents in each outer-layer cohort. Join `g=2q/Q` consecutive complete
parents within a cohort, preserving generated phase/cohort/lane order.
This uses the existing generic join formula with the actual source count;
the legacy full-Q route name/binding remains compatible.

Each parent contains `pp*L` conductors. Each target has `2q*pp*L/Q`
conductors, Q branches per phase and `Q/2` per outer-layer cohort. New seams
advance one q lane, span `L-1` layers and have pitch magnitude `tau-1` or
`tau+1`, `tau=m*q`; sign normalized along layer traversal is positive.
Each seam crosses at most one pole region. Body passes,
N-to-S parents, complete unique occupancy and normalized weld direction
remain required; every seam is checked, including later joins.

For neutral zero-shift inputs and local phase phi, a branch starting at lane
a has complex EMF
`pp*L*exp(i*pi*phi*(1+1/m))*sum(exp(i*pi*r/(m*q)), r=a..a+g-1)`.
Its nonzero magnitude is `pp*L*sin(pi/(m*Q))/sin(pi/(2*m*q))`.
Q=2 gives equal parallel complex EMF; Q>2 has successive group angles
`2*pi/(m*Q)` and remains `not strong symmetry layout`. Two-layer cases
retain their explicit structural-overlap qualification. Manual TP and
post-connection shifts follow the current shared contracts below and can
still fail actual output validation. Insert-side inlet remains required.

The reviewed schema-v3 q=4/Q=2 fixture is a frozen pre-promotion path oracle;
its old review notes/local illustration references are historical, and its
manual non-certification flags stay false. Public generation is checked
against its exact ordered paths. Native proper-Q finite evidence covers
32 q/Q/pole/layer/phase cases; this is not universal or release certification.
The existing six-geometry TLP q-only inventory has eight supported and
one rejected request. Owner-approved integer-global-q arrays now reuse the
same local construction. For `m=3k`, `k>=2`, use `q_s=k*q`, `L_s=L/k`,
even `2<=Q<=q_s`, `Q|q_s`, `pp>=2`, and even `L_s>=2`. Global q need not
be even and Q need not divide global q; each local public route must pass.
Join `g=2q_s/Q` whole `(q_s,1,2)` parents per cohort, then apply the
canonical `2*q*j` slot and `L_s*j` layer offsets. The global branch length
is `2q*pp*L/Q`, with Q branches per phase and `Q/2` per outer-layer cohort.
No `k|Q` condition applies. Fractional-global-q arrays remain unsupported-yet.
Insert-side entry and the existing TP/post-connection-shift contracts remain.

A separate pre-admission mapped-edge exploration for `m=3k`,
`k=2,3,4`, tested 48 combinations across eight proper-q pairs and
`(pp,L_local)=(2,2)` or `(3,4)`. In that matrix, each branch joins
`g=2*k*q/Q` parents and each set rotates by `2*q*j` slots. All 48 pass the
one-region connection-stage check in canonical local coordinates. The earlier
22/26 safe/unsafe split and `k|Q` admission inference are withdrawn: the 26
cases have 52 two-boundary records only against fixed global slot-zero
intervals after rotation. For `(m,q,Q)=(9,4,2)`, the +37 seam local 135->28
becomes global 143->36 with offset 8 and tau=36. Its local unwrapped 135->172
crosses one region; global 143->180 crosses two fixed intervals. The current
post-connection contract does not repeat that gate after rigid relocation.
Canonical phase-set mapping preserves the complete parents and creates no
new connections. The six-phase `(q,Q,pp,L)=(4,2,3,8)` example retains
valid local identities and all 1,152 conductors once, while its aggregate
report keeps `multi_phase_emf_mismatch`; it is not strongly certified. Fresh
strict public generation now verifies those 48 cases against an independent
complete-parent, edge and complex-EMF formula, plus local-only/full local Q,
15/18 phases, shifts and rejection cases. Workbench includes local q-only
divisors and reports public generation separately from retained layout/Auto
diagnostics. Source changes make the earlier private hash receipt historical;
the current public tests and refreshed finite-status receipt bind this admission.
This remains finite validation, not universal or release certification. See
[current validation](../../docs/VALIDATION.md).

### Post-connection phase/radial shifts (2026-09-29)

Every implemented Pattern route now validates its connection construction
before phase/slot and radial/layer relocation. All ten Pattern families accept
these layout controls at the public route entry; the relocated winding still
requires unique full occupancy, preserved phase/pole sign and electrical
retention. Connection identity and pole-region limits are not re-evaluated on
the relocated endpoints. Older zero-shift route descriptions and finite-case
shift probes below describe their earlier construction scope, not a current
shift-admission restriction. Inlet requirements and formula domains remain.
An individual shift can still fail for zero fundamental EMF.

### Manual transposition inputs (2026-09-29)

Manual Regular offsets, Times and Interval settings use the same implemented
constructors and output validation as Auto recipes across all ten Pattern
families. A private Auto token is not required to submit these settings.
This supersedes the TP-only part of older neutral-configuration restrictions;
post-connection shifts follow the rule above, while inlet requirements and
formula domains remain unchanged.
Admission permits generation to be attempted, not automatic validation of the
result. Duplicate occupancy, incomplete coverage and invalid connections still
reject the generated case; EMF asymmetry alone remains a retained diagnostic.
The fixed-path TSP sector/pass-partition formulas and the UWP short-P2 formula
do not implement transposition. Their specific limits remain visible rather
than silently discarding input. Other constructor-specific limits also remain.
For legacy UWP full-circle waves, Times/Interval retain the mandatory q-lane
transition at unselected edges. Regular Uniform cancels its `pp-1` within-wave
offsets at the wave boundary, then advances one q lane. These geometry rules
keep the full q-lane occupancy while allowing the requested transposition to
change the within-wave path. A schedule that still repeats positions fails the
ordinary generated-layout check with its exact reason.


Use the [V7.6 Naa-Division status page](pattern_naa_division_layout.html)
for finite, source-linked route decisions and public generation examples.
Its [machine-readable results](pattern_route_inventory.json) and
[integer-q status summary](INTEGER_Q_DIVIDER_SUPPORT_STATUS.md) are generated
from the V7.6 public resolver. A preflight admission is not a Validated
generated layout; Candidate and retained-but-not-strong results remain
separate.

### TSP regular manual-route closure (2026-09-29)

`tsp_spiral_pass_partition` closes the five saved unsupported TSP routes at
`q=2, pp=4, L=4`: `(1,2,1)`, `(2,1,1)`, `(1,2,2)`, `(2,2,2)`, and `(2,4,1)`.
The Workbench displays the public result for saved routes: the last three,
plus existing `(1,4,2)`, show `not strong symmetry layout` without a manual
status prefix. Their saved drafts remain available for inspection.
The user approved either circumferential direction for a top-bottom insertion
return, provided ordinary spiral passes remain intact, every layer pair has
one lower-to-higher weld direction, and each actual edge crosses at most one
pole-region boundary. This supersedes the old return-direction exclusion for
the different `(1,2,1)` example; it does not relax body or weld checks.

The registered input scope is positive **integer global q**, neutral Regular
settings, zero transposition/phase/radial shifts, and insert-side inlet. Native
odd-phase windings and existing arrays of three-phase sets are supported. Use
local `q_s=q, L_s=L, m_s=m` for a native set. With `k=m/3` arrayed sets, use
`q_s=k*q, L_s=L/k, m_s=3`; `L_s` must be positive and even. Fractional global-q
arrays are outside this new family, even if their local q is integral; existing
fractional constructors remain unchanged.

For selected `(Q,D,P2)`, require `Q|q_s`, `D|pp`, `P2 in {1,2}` and
`Naa=Q*D*P2` even. Derive:

```text
tau = m_s*q_s                  # one local pole-region width in slots
C = Naa/2                     # branches in each of two outer-layer cohorts
G = gcd(q_s,C)                 # disjoint lane groups per cohort
a = L_s/2; g = gcd(a,pp)       # pole-pair step and its orbit count
passes_per_branch = q_s*pp/C
conductors_per_branch = passes_per_branch*L_s
```

For every integer-global-q Regular TSP route, the user-selected Pattern-wide
feature floor is eight conductors per branch. Its count is
`B=2*q*pp*L/Naa`; `B<8` is an explicit rejection with the computed count,
including for phase-set arrays. This floor applies before selecting a default
or specialized constructor. Fractional-global-q routes retain their existing
admission rules. For this new complete-pass constructor, the independent
`passes_per_branch>=2` guard also applies, giving `B>=2*L_s`; together its
minimum is `B>=max(8, 2*L_s)`. The constant eight is the user's engineering
cutoff; the `2*L_s` term follows from two full layer traversals.

Each of the `G` groups covers `q_s/G` lanes. In direction `d in {+1,-1}`,
visit fixed-lane pass heads `r-d*c+d*t*a (mod pp)`, with `0<=c<g` and
`0<=t<pp/g`. The `+a` orbit has `pp/g` distinct residues; the `g` consecutive
cosets partition all pole pairs. Ordinary edges are `d*tau`. Returns within
an orbit are `d*tau`; returns between orbits are `-d*tau`. A lane join uses
`d*tau+lane_delta`, with the next origin decreased by `d*(g-1)`. Layer order
and travel both reverse in the second cohort, preserving normalized weld
direction while occupying the opposite conductor polarity in each layer.
Cut each group into `C/G` equal paths at complete-pass boundaries. Require
`passes_per_branch>=2`, so every new branch contains a top-bottom return.
The new constructor's structural minimum is `2*L_s` conductors, in addition
to the Pattern-wide eight-conductor floor above.

The constructor derives its own cohort/lane/cut inlet arrangement. It does
not promise that every D-contributed inlet is equally spaced, or reproduce
every saved branch's arbitrary rotation/order. The separate fixed-lane
`tsp_pp_p2_sector` formula keeps its equal-sector contract and precedence.
All previously registered constructors and defaults retain precedence. Odd
Naa, one-pass cuts, shifted configurations, and fractional global q are not
admitted by this fallback; their existing route decisions remain authoritative.

Public generation checks exact coverage, equal branch lengths, phase/sign,
N-to-S terminals, monotone body passes, q-lane consistency, recorded signed
travel, normalized weld direction, one-region returns, and ordered identity.
Arrays also pass local and mapped aggregate checks. EMF asymmetry remains a
retained `not strong symmetry layout`, never a construction-domain filter.
At the saved geometry, `(1,2,1)` and `(2,1,1)` are `Validated`; the other three
new rows are retained non-strong layouts. Saved drafts remain non-certified.

The finite six-geometry TSP inventory now contains 60 supported, 24 rejected,
and 2 unsupported requests after the eight-conductor floor; this is a bounded
inventory, not a domain proof.
The replayable closure audit (local research excluded)
records 1,308 formula checks and 141 new-route public generations, including
native m=3/5/7 and arrays m=6/9/12. Earlier dated TSP boundary observations
below describe their original constructors; this distinct fallback supersedes
their old total-route `unsupported-yet` conclusions where its domain applies.

## V7.6 parameterized divider formula layer (2026-09-28)

Special connection construction now has a shared formula module,
[`divider_connection_formulas.py`](divider_connection_formulas.py). It takes
source and target divider triples `(Q, D, P2)` and derives branch-count changes
from their products, `Naa = Q * D * P2`. A parent partition uses
`target Naa / source Naa` equal slices; an adjacent join uses
`source Naa / target Naa` parents per result. Both ratios must be positive
integers. A factor reference can apply an exact rational scale, and an identity
transfer requires equal Naa while preserving every source path and its order.
Ordering is explicit: source-major keeps each parent's children
together, while piece-major groups the same slice from every parent before
continuing to the next slice.

| Route | Parent triple | Target triple | Formula and ordering |
| --- | --- | --- | --- |
| `tsp_spiral_pass_partition` | Complete local spiral passes | `(Q,D,P2)` | Two outer-layer cohorts, gcd-derived pole-pair orbits, q-lane joins, then equal complete-pass cuts; see the current closure rule above. |
| `zpp_pp_only_indexed_translation` | `(D,1,1)` | `(1,D,1)` | Within each phase, translate source branch `j` by `(a*j mod D)*num_slots/D`, where `a` is the least positive stride satisfying `gcd(a,D)=1` and `gcd(D,2*(pp/D)*a-1)=1`. Direct domains use `q=Naa=D`, `D|pp`; `D=2` retains the old half-turn. Arrayed `a>1` remains unsupported pending mapped global-edge validation. |
| `zpp_pp_only_centered_entry_translation` | `(q,1,1)` | `(1,D,1)` | For `D>q`, `q|D`, and `D|pp`, target branch `j` takes the centered window of source branch `j mod q`, with length `source_length/(D/q)`, then translates that window from its actual source sector to `(a*j mod D)`. The stride `a` uses the indexed-sector permutation rule above. |
| `tsp_pp_only_q_p2_identity` | `(q,1,2)` | `(1,2q,1)` | Identity transfer: preserve every public full-q TSP parent path in branch order. Exact factor binding derives source Q as target D/2; `Naa=q*1*2=1*(2q)*1`. Requires integer `q>=2` and `2q|pp`; public source and target preflight remain authoritative. |
| `tlp_q_only_pair_join` | `(q,1,2)` | `(Q,1,1)` | Join `2q/Q` consecutive public full-q parents within each phase/outer-layer cohort; even `Q|q`, `2<=Q<=q`. Full-Q remains the two-parent special case and retains its legacy binding. |
| `tsp_pp_p2_sector` | Direct construction | `(1,D,2)` | For region `j`, use `r_j=j*(pp/D)`, fixed lane `a_j=floor(j*q/D)`, and phase inlet `s(phi,j)=q*(phi+m*(2*r_j+(phi mod 2)))+a_j`. Pair a first-layer `+tau` path with a last-layer `-tau` path, where `tau=m*q`; each path has `C=q*pp*L/D` conductors. Require `q` to divide `D`, `D` to divide `pp`, and, for every lane `a`, exactly one visit to every residue `0..pp-1` in `{(j*(pp/D)+n*(L/2)) mod pp | 0<=j<D, floor(j*q/D)=a, 0<=n<q*pp/D}`. Arrayed phases use each set's local q/layers and must pass mapped global checks. |
| `tlp_pp_only_even` | `(Q,2,1)` | `(Q,D,1)` | Partition each public parent into `D/2` complete layer-pass paths; source-major. The formula binding derives parent Q from target Q. Direct support keeps legacy `Q=1, q<=2` and adds full-Q `Q=q>1`. For `k=m/3` arrayed sets, map `(Q_global,D_global,1)` to `(k*Q_global,D_global/k,1)` in each local set, preserving Naa. The local divider must be even and at least 4, divide `pp`, and local `L` must be even and at least 4. |
| `tlp_pp_p2_short_unit` | `(1,1,2)` | `(1,D,2)` | Partition into `D` complete layer-pass units; source-major, then apply the route's sector rotation. |
| `tlp_q_pp_p2_parent_slices` | `(1,D,2)` | `(2,D,2)` | Partition each public PP+P2 parent into two contiguous, equal complete-pass paths; source-major. The parent supplies the D-sector and outer-layer inlet lineage. |
| `zlp_pp_p2_source_cut` | `(1,1,2)` | `(1,D,2)` | Partition into `D` equal paths; source-major. |
| `ssp_q_pp_parent_cut`, `slp_q_pp_parent_cut` | `(1,D,1)` | `(Q,D,1)` | Partition complete `2L` blocks into Q children; SSP uses lane-major blocks, SLP stably filters the same blocks into contiguous q-lane cohorts. Each child keeps `q/Q` lanes with `pp/D` repetitions. |
| `slp_q_pp_p2_parent_cut` | `(q,1,2)` | `(Q,D,2)` | From each public full-Q P2 parent, select `pp/D` passes per lane. Regroup `q/Q` adjacent lane cuts into target branches; append complete `2L` blocks in sector-major order and reverse lane order on alternate blocks. Requires integer `q>1`, `1<Q<q`, `Q|q`, `D>1`, `D|pp`, even `pp/D`, `P2=2`, and `Naa=2QD`. |
| `cp_q_only_pair_join` | `(Q,1,2)` | `(Q,1,1)` | Join adjacent generated parents in same-phase order; the caller validates each seam. |
| `uwp_q_only_series` | `(Q,1,2)` | `(Q,1,1)` | Join q/P2 parents in phase/group order after pairing each cohort branch with its corresponding second-cohort branch. |
| `cp_q_pp_full_parent_slices` | `(Q,1,2)` | `(Q,D,1)` | Partition each same-phase parent into `D/2` equal paths; piece-major within each phase. For `Q>1`, keep integer `q>1`, `Q|q`, even `D>=4`, `D|pp`; for `Q=1`, use positive integer `q`, even `D>=4`, `D|pp`, and `(q odd or D≡2 (mod 4))`. Even q with `D≡0 (mod 4)` stays on its separate CP constructors. Both families require `P2=1`, `ab=Q*D`, and passing public source/target preflight. |
| `cp_q_pp_p2_parent_slices` | `(Q,1,P2)` | `(Q,D,P2)` | Partition every same-phase public parent into `D` equal consecutive paths; source-major. Admit non-default integer-q CP tuples with `Q>1`, `Q|q`, `D>1`, `D|pp`, `P2=2`, `ab=2QD`, and passing public source/target preflight. |
| `cp_pp_sector_slices` | `(1,4,1)` | `(1,D,1)` | Partition into `D/4` equal paths; source-major. |
| `cp_pp_four_pass_weave` | `(1,D,2)` | `(1,D,1)` | Route-specific four-parent weave over `Nlayer`-sized pass blocks. |
| `cp_pp_parent_half_translation` | `(1,1,2)` | `(1,4,1)` | Select the second parent half and translate it by offsets derived from `tau=mq`, slot count, and the half's endpoint displacement. |

The source parent's start positions and ordered direction come from the
Pattern's public reference generation; these formulas do not store sampled
conductor coordinates. Pattern-specific bridge, phase, identity, edge, and
electrical checks remain in the public route path. The shared divider-ratio
engine replaces repeated cuts and joins; its SSP/SLP block formula and CP
equations replace the corresponding inline transformations. The CP Q+PP row
below records admission expansions validated through public generation,
including a PP-only gap that reuses the same P2-parent formula. Other Pattern-specific formulas remain explicit until they can be
expressed without changing their verified order. The half-integer-q UWP family
has a separate formula owner and is described below; it does not use this
integer-divider formula engine.

### TLP Q=2 plus PP plus P2 parent slices (2026-09-29)

The public TLP `(1,D,2)` parent has `2D` branches per phase. For target
`(2,D,2)`, partition each parent in generated order into two equal contiguous
paths. The shared formula gives `Naa_target/Naa_parent=2`, so each target
branch contains `C=L*(q/2)*(pp/D)` conductors and
`B=(q/2)*(pp/D)` complete layer passes. No new connection is inserted: every
retained signed edge, layer order, and TLP return comes from the public parent.
This lineage carries the parent's PP-sector placement, unlike cutting a
`(2,1,2)` parent and inferring D from a new label.

The formula domain requires positive even integer q, `D>1`, `D|pp`,
`2D<=pp`, even `L>=4`, and `B>=2`. Actual admission additionally requires a
publicly generated `(1,D,2)` parent, neutral Regular settings, zero phase and
radial shifts, zero transposition, and the insert-side inlet. The target must
have `2D` positive pole-region cohorts per phase across its two outer layers:
each layer has D sectors separated by `pp/D`, with two distinct q-lane starts
per sector. In the saved q=2 case the two lanes exhaust q. For larger q they
may be adjacent; the user accepted distinct adjacent lanes when the complete
route passes independent checks. The constructor reports whether they happen
to be separated by q/2, but that diagnostic is not an admission condition.

Source and target pass unique conductor-position occupancy, equal branch
length, shifted-map phase membership and N-to-S terminals, ordered TLP
identity, normalized weld direction, and independent electrical retention.
The target contains only intact slices of the source, so it neither changes
ordinary pitch nor invents a special return. The saved q=2, pp=4, L=4
Workbench draft has the same Phase-A ordered path set as the public target;
the draft itself remains non-certified. Public q=2/4/6 samples passed for
pp=4/6/8 and L=4/6/8/10/12, plus D=3 cases and mapped six-/nine-phase
samples. These are checked examples, not an all-geometry proof or a strong
symmetry claim. EMF-only asymmetry remains `not strong symmetry layout`.

Production admission is narrower than the symbolic formula: source placement
can fail, as seen at q=2 or 6, pp=8, D=4, L=4; these cases remain
`unsupported-yet`, not physically rejected. For arrays of three-phase sets,
the current local constructor requires even `L_local>=4`; short or odd local
layer sets are an unresolved model boundary, including m=12 with global
L=8. Nonneutral configurations, other Q values, and two-layer degeneration
are outside this admission. Earlier `(2,1,2)` complete-source cut probes below
remain evidence for a different method and do not define this route.

### TLP full-Q even PP partition (2026-09-29)

The prior TLP cut supported target `(1,D,1)` only for `q<=2`. The shared
partition formula now uses public parent `(Q,2,1)` and target `(Q,D,1)`, so
the branch-count ratio is `Naa_target/Naa_parent = D/2`. Each parent is cut
source-major into `D/2` contiguous paths. Since `D|pp`, each child contains
`2*pp/D` complete `L`-conductor passes. The formula binding takes Q from the
target tuple; it stores no sampled branch starts or conductor coordinates.

Direct three-phase support retains legacy `Q=1, q<=2` and adds full-Q
`Q=q>1`. Both require integer q, even `D>=4`, `D|pp`, even `L>=4`, neutral
Regular configuration, the route-required inlet, and supported phase
topology. A selected route still needs its actual public `(Q,2,1)` parent to
generate. Proper-Q `1<Q<q` remains `unsupported-yet` because the current
parent path does not establish the required coverage for that family.

For an array of `k=m/3` equal layer-assigned three-phase sets, factor mapping
preserves the global branch product:
`(Q_global,D_global,1) -> (k*Q_global,D_global/k,1)`. This is admitted only
for full global Q, `k|D_global`, even local `D=D_global/k>=4`, `D_global|pp`,
and even local `L=L_global/k>=4`. The local q divider is then
`k*Q_global=q_local`. Each set is generated through the same public route;
the mapped aggregate must also pass occupancy, phase, ordered TLP identity,
one-region edge, weld-direction and electrical checks. Other array factor
maps, proper-Q targets, and local arrays with `L_local=2` remain
`unsupported-yet` under this extension.

The cut validator tags each parent's phase, q-lane and ordered pole-region
sequence. For full-Q parents it requires a stable phase and q-lane, and every
child must equal its exact contiguous parent slice at complete layer-pass
boundaries. This preserves sector order without assuming that every `L`-pass
block occupies one pole region. The public source/target checks remain the
admission authority; these conditions describe the implemented domain, not
manufacturing certification.

The refreshed finite scan uses the same six integer geometries as the prior
view. Only the TLP Q+PP cell changed: supported preflights move from 6 to 9,
unsupported-yet from 9 to 6, and rejected stays at 3. Across all TLP formula
cells, supported moves from 21 to 24, unsupported-yet from 30 to 27, and
rejected stays at 35. No other Pattern/formula cell changed. These are
preflight tuple counts, not the number of cases proved by generation.

Seven full-Q extension samples passed public generation and full ordered
identity checks:

| Route view | `(q,pp,D,L,m)` | Local factors when arrayed | Public result |
| --- | --- | --- | --- |
| Direct | `(2,4,4,4,3)` | — | retained-not-strong; identity valid |
| Direct | `(3,6,6,6,3)` | — | retained-not-strong; identity valid |
| Direct | `(4,8,4,4,3)` | — | retained-not-strong; identity valid |
| Direct | `(6,6,6,6,3)` | — | retained-not-strong; identity valid |
| Array, m=6 | `(2,8,8,8,6)` | `(4,4,1)`, local `q=4,L=4` | retained-not-strong; set identities valid |
| Array, m=9 | `(2,12,12,12,9)` | `(6,4,1)`, local `q=6,L=4` | retained-not-strong; set identities valid |
| Array, m=12 | `(2,16,16,16,12)` | `(8,4,1)`, local `q=8,L=4` | retained-not-strong; set identities valid |

All seven generated layouts are retained with complete unique occupancy and
valid TLP identity. Their `parallel_emf_mismatch` diagnostic (and the arrays'
`multi_phase_emf_mismatch`) remains visible, so they are not strong-symmetry
certifications. Proper-Q `(q=4,Q=2,D=4)`, an odd local divider, and a three-
layer local array boundary remain `unsupported-yet`; they are not rejected as
physically impossible. Exact requests, resolver decisions and public results
are replayable in the [TLP status-page section](pattern_naa_division_layout.html#pattern-tlp)
and [machine-readable inventory](pattern_route_inventory.json).

### TSP `(1,D,2)` admission comparison (2026-09-28)

Before `tsp_pp_p2_sector`, the finite `pp_and_p2` route scan had 0 supported
requests and 10 `unsupported-yet` requests: TSP had no constructor for these
tuples. The refreshed scan has 3 supported and 7 `unsupported-yet`; this is a
bounded inventory result, not the full mathematical domain. Eight public
samples passed generation and route validation: six direct integer-q
cases and two phase-set arrays. The `(1,1,2)` `tsp_default` path and the
existing `(1,2q,1)` identity transfer remain unchanged. The validator checks
actual N-sign inlet ranks and q-lanes from `phase_map()` independently of the
formula path builder.

### ZPP PP-only indexed sector translation

The indexed formula extends the former (1,2,1) half-turn route. For target
(1,D,1), equal Naa fixes the source as (D,1,1); ZPP's Q*P2=q rule then fixes
q=D and Naa=D. For each phase, keep the public source branch order j=0..D-1
and translate every conductor in branch j by ((a*j) mod D)*num_slots/D slots
modulo num_slots. This is a whole-path translation: conductor order, layer,
phase, and signed travel are inherited from the public parent. The route uses
DividerFactorRef(1) so the registered formula derives the source Q-divider from
the target PP-divider.

Let r=pp/D, which must be a positive integer. In a fixed layer, the source
parent's q-lane/pole-index relation gives branch classes c-j (mod D). A
translation by a*j sectors advances the pole index by 2*r*a*j, because
num_slots/D = 2*pp*m/D and one pole region spans m*q=m*D slots. The translated
classes are c+(2*r*a-1)*j (mod D). The route therefore chooses the least
positive a satisfying both gcd(a,D)=1 and gcd(D,2*r*a-1)=1: the first
condition makes the translated sector offsets distinct, and the second makes
the lane classes cover all D classes exactly once. The factors 2 and -1 come
from the two-pole slot period and the source branch-class relation. For every
integer D>=2 and r>=1, a valid stride exists: modulo each prime divisor of D,
exclude zero and (when 2r is invertible) the single residue that makes
2*r*a-1 zero; at least one residue remains, and the Chinese remainder theorem
combines them. The implementation chooses the least valid representative
below D.

The old direct-route admission required gcd(D,2*r-1)=1, which is exactly the
new rule with a=1. Every previously admitted direct route therefore keeps its
branch offsets and generated path signature. The extension admits formerly
non-coprime direct requests when a larger stride supplies a permutation. Direct
domains remain q=Naa=D, D|pp, positive even Nlayer, supported phase count,
neutral Regular settings, weld-side inlet, and a generatable public (D,1,1)
parent. Public target generation and route validation still decide whether a
request is retained and Validated.

For an array of s=H/3>1 three-phase sets, legacy a=1 cases retain their
existing local-set path. Arrayed a>1 is explicitly unsupported-yet while
mapped global signed edges fail the one-pole-region check in the sampled
counterexample. This leaves array admission unchanged; local formula success
alone does not validate the mapped aggregate. An older admitted a=1 example
(q_global,pp,Nlayer,H,D)=(1,3,6,9,3) still passes its local checks and is
retained despite an EMF mismatch, but an independent aggregate edge audit
found 12 insertion edges crossing two pole boundaries. That is a pre-existing
validation gap, not evidence that the global array edges pass. Both old and
candidate array paths continue to require integer set-slot offsets and even
positive local layer groups. This formula does not change the separate ZPP
(Q,2,1) weld-direction findings.

### ZPP centered-entry PP-only extension

The new `zpp_pp_only_centered_entry_translation` route derives target
`(1,D,1)` from the public ZPP `(q,1,1)` parent when `D>q`, `q|D`, and
`D|pp`. For target branch index `j`, select parent `j mod q` and its centered
window of `parent_length/(D/q)` conductors. Replicate that window across the
`D/q` sector cohorts, preserving its path order and layer/q metadata. Place it
in destination sector `(a*j mod D)`, translating from the window's actual
starting sector by a multiple of `num_slots/D`; derive `a` with the indexed
sector rule above and `r=pp/D`. This is a centered-window deployment, not a
disjoint cut of the entire parent path. The branch count and expected length
remain `D` and `parent_length/(D/q)` per phase.

The executable domain requires positive integer `q`, even positive layers, a
supported phase topology, `D>q`, `q|D`, `D|pp`, the public `(q,1,1)` source,
neutral Regular settings, and a weld-side inlet. The existing whole-path
`(D,1,1)->(1,D,1)` route remains selected at `q=D`, preserving its route and
path signatures. For an arrayed six-phase sample that resolves through its
existing local `q=D` route, this extension does not introduce a new aggregate
array rule.

Strict public generation plus `validate_selected_zpp()` passed for
`(q,pp,L,m;D)=(1,6,4,3;3)`, `(2,4,4,3;4)`, `(2,4,4,5;4)`, and
`(3,12,4,3;6)`. The q=2, D=4 ordered paths match the retained phase-A manual
package exactly; the sampled strides include `a=2` for D=3 and `a=5` for
D=6, `pp/D=2`. Non-dividing `q∤D`, `D∤pp`, and odd-layer source boundaries
remain outside the new route; an existing default case that fails its branch
length remains `rejected` with its structural reason.

Public generation samples include the prior a=1 layouts
(q,pp,L,m,D)=(3,3,4,3,3), (5,10,6,5,5), (8,8,6,5,8), and
(10,20,4,3,10), plus new a=2 direct (3,6,4,3,3) and a=5 direct
(6,12,4,3,6) cases. All six are retained and pass coverage, identity,
electrical, and edge checks; the exact a=1 and new direct boundary paths are
signature-locked in focused divider tests. The old bounded sweep covered
D=2..10, r=pp/D=1..6, Nlayer in {4,6}, and H in {3,5}: its 180 previously
admitted requests preserve a=1. All 36 formerly disabled direct requests
across nine (D,r) pairs now generated and passed public route validation in
the same bounded sample. Coverage, phase membership, exact occupancy, ordered
identity, electrical checks, and the one-pole-region edge limit passed for all
36. These finite cases validate the listed range; they do not certify every
geometry or any arrayed a>1 route.

## V7.6 half-integer-q UWP formula family (2026-09-27)

[`half_integer_q_connection_formulas.py`](half_integer_q_connection_formulas.py)
owns the exact connection definitions for the registered half-integer UWP
routes. Divider identity remains `Naa = Q * D * P2`. For positive
`q = n + 1/2`, the denominator-clearing factor is `2`, so both the public P2
parent `(q,1,2)` and its full-wave transfer target `(q,2,1)` have
`Naa = 2*q`. The parent constructor is registered for `D*P2 = 2`; the transfer
keeps the same Naa while moving the split to `D=2, P2=1`.

| Route | Source dividers | Target dividers | Derived rule |
| --- | --- | --- | --- |
| `uwp_half_integer_p2` | `(q,1,2)` | `(q,1,2)` | Build the existing ordered UWP P2 parent from exact `T=2*m*q` slot periods and the shifted phase map. |
| `uwp_half_integer_q_pp` | public `(q,1,2)` parent | `(q,2,1)` | Reverse each S-inlet parent path to N-to-S, then translate the second cohort by whole `T`-slot periods into the opposite half-circumference. |

The preconditions remain the existing geometry and route checks: positive
half-integer q, positive integer `Naa`, a currently supported phase count, even
pole and layer counts, exact `slots=q*poles*m`, one integer phase shift per
layer, and a pp-divider that divides the pole-pair count. For the transfer,
`q>1` supplies a nonempty second cohort and `D=2` must divide the pole-pair
count; q=`1/2` has no second cohort. The exact pole-region width is
`tau=m*q`, retained as a `Fraction` for signed travel checks. The two-pole
period `T=2*m*q` is integral for the registered phase geometries.

The UWP split contract requires `D*P2` in `{1,2}`. The only half-integer P2
parent in this family is `(q,1,2)`, and its transfer target is `(q,2,1)` when
`q>1`. An explicit `(q,D,2)` with `D>1` is `rejected` with the existing
reason that the pp-divider and P2-divider share a splitting allowance; an
integer Naa alone does not establish a connection formula. The existing
implicit BWP/UWP global-wave sector array has its own route and Pattern
identity and is not a parent for these formulas. LPP's explicit half-integer
exclusions remain in force. Other Patterns without a public half-integer
parent remain `unsupported-yet`.

The formula layer preserves the public parent's branch order and conductor
membership. Public generation still owns shifted phase records, N-to-S
orientation, coverage, unique occupancy, phase membership, Pattern identity,
terminals, edge direction, and the one-pole-region crossing limit. EMF remains
a separate diagnostic: an EMF mismatch alone does not reject a retained layout,
which remains labelled `not strong symmetry layout` rather than certified as
strong symmetry. Formula extraction does not create a strong-symmetry
requirement or promote a Candidate route.

## V7.6 half-integer-q BWP base-wave formula (2026-09-27)

[`half_integer_q_connection_formulas.py`](half_integer_q_connection_formulas.py)
also owns the BWP single-branch base wave used by its half-integer global-wave
candidate routes. This extraction replaces only BWP's inline base-position and
run-direction construction. Public generation still applies branch phase
rotation and layer shifts, attaches the base phasor tag, checks ordinary wave
edges, and reports coverage, electrical retention, and Pattern identity.
UWP's base wave and the shared fractional-wave checks are unchanged.

For positive half-integer `q`, supported phase count `m`, even pole count `P`,
and even layer count `L`, define the two-pole slot period `T=2*m*q`, the short
pitch `S=floor(T/2)`, the long pitch `H=T-S`, and the pass count `R=2*q`.
The exact slot condition remains `Nslot=q*P*m`. Start with `seed=0`. For pass
`r=0..R-1`, set `epsilon=+1` for even `r` and `-1` for odd `r`; visit layer
pairs in ascending order when `epsilon=+1` and descending order otherwise. At
pole index `i=0..P-1` in pair `j`, derive

```text
offset = floor(i/2)*T + (i mod 2)*S
slot   = (seed + epsilon*offset) mod Nslot
layer  = 2*j + (i mod 2)                  when epsilon=+1
layer  = 2*j + (1 - (i mod 2))            when epsilon=-1
```

After each pass, set `seed=(last_slot-S) mod Nslot`. The resulting immutable
definition also records one travel direction for each pass/layer-pair run;
the caller uses it for the existing ordinary-edge check. The builder requires
integral `T` and `R`, exact slot geometry, supported phases, even poles/layers,
and the existing neutral Regular, zero-transposition, zero-radial-shift,
insert-side candidate configuration.

The behavior-parity probe covered `q=1/2,3/2,5/2`, `m=3,5,7`, `P=8`,
`L=4`, and `Naa=1 or 2`: all 18 complete generated-path signatures and all 18
default route states match the pre-extraction baseline. Those states remain
Candidate-blocked by Pattern identity; opt-in exploration still reports
Candidate identity. This is formula ownership cleanup, not a new BWP admission
or production validation. EMF remains a separate diagnostic and cannot reject
an otherwise retained layout.

## V7.6 CP P2-parent slicing expansion (2026-09-27)

The `cp_q_pp_full_parent_slices` route retains its existing Q+PP family where
`Q>1`, integer `q>1`, `Q|q`, even `D>=4`, and `D|pp`. The PP-only family has
`Q=1`, positive integer `q`, even `D>=4`, `D|pp`, and either odd `q` or
`D≡2 (mod 4)`. Thus odd q can use parent slicing at any admitted even D, while
even q uses it at `D≡2 (mod 4)`; even q with `D≡0 (mod 4)` stays on the
existing four-sector constructors. `D=2` remains separate. Both families
require `P2=1`, `ab=Q*D`, and passing public source and target preflight. CP
requires positive global `Nlayer` divisible by four, a supported phase
domain, and neutral Regular, zero-shift, insert-side configuration. For an
array of `k=m/3` three-phase sets, each local layer group `Nlayer/k` must also
be positive and even; only the global layer count has the fourfold rule.

The source is the same geometry's public CP `(Q,1,2)` layout. It has `2Q`
parents per phase; each parent is split into `D/2` equal consecutive slices.
The ratio is derived from `(Q*D)/(Q*1*2)=D/2`. With `Q=1`, the source is
`(1,1,2)` and its two parents per phase produce `D` target branches. Every
admitted even D gives `D/2` equal slices per parent. The route emits slice
index first and generated parent order second, giving `Q*D` branches per
phase of length `2*q*pp*Nlayer/(Q*D)`. `D=2` remains separate; even-q
`D≡0 (mod 4)` stays on its existing CP constructors.

Public generation and independent checks passed for
`(q,pp,Q,D,Nlayer,m)=(2,8,2,4,4,3)`, `(4,4,2,4,4,3)`,
`(4,8,2,4,4,3)`, `(3,8,3,4,4,3)`, `(6,12,2,6,4,5)`, and the existing
`(3,6,3,6,4,5)` reference. The L=8 array sample `(4,8,2,4,8,6)` also passed.
New PP-only samples passed for `(2,6,1,6,4,3)`, `(4,6,1,6,4,5)`,
`(3,10,1,10,4,5)`, `(2,14,1,14,4,3)`, and `(5,14,1,14,4,7)`.
Every sample's target paths were compared exactly with the piece-major slices
of public `(Q,1,2)` parent paths. Checks covered conductor coverage and unique
occupancy, equal branch lengths, phase membership, topology retention, CP
identity and cross-layer edges, and the one-pole-region travel limit. For
`m=6`, CP identity and edge checks run on each independent three-phase set.
The earlier Q>1 representative layouts report `parallel_emf_mismatch`; the
L=8 array also reports `multi_phase_emf_mismatch`. They remain retained as
`not strong symmetry layout`; EMF asymmetry does not reject this construction.

The PP-only q-domain now includes `q=1` when its public `(1,1,2)` source and
target preflight pass. A 36-request direct sample covered `D=6/10/14`,
`pp/D=1/2/3`, `Nlayer=4`, and odd `m=3/5/7/9`: all 27 requests at `m=3/5/7`
generated and passed identity, occupancy, direction, CP edge, and electrical
retention checks. The nine `m=9` requests remained disabled because four layers
cannot be evenly assigned to three-phase sets. Direct q=1 requests with
`m=3`, `Nlayer=8/12` also remain disabled: their public `(1,1,2)` sources
report duplicate and missing conductors. Those are source-method boundaries,
not a general exclusion of q=1.

The odd-q expansion was sampled separately at neutral `Nlayer=4`,
`q∈{1,3,5}`, `D∈{4,8,12}`, `pp/D∈{1,2}`, and `m∈{3,5}`. All 36 public
requests generated with paths exactly matching the piece-major slices of the
same-geometry public `(1,1,2)` parents. They passed coverage, equal branch
length, phase, CP identity, cross-layer edges, signed travel and electrical
retention checks. Twelve had no EMF error; 24 reported only
`parallel_emf_mismatch` and remain `not strong symmetry layout`. Additional
ordered-path checks passed for `(q,pp,D,L,m)=(3,8,8,4,5)` and
`(5,12,12,4,5)`. The existing q=1, D=6 family and even-q D=4/8 constructors
retain their prior route selection.

The array controls `q_global=1,m=6,Nlayer=8` and
`q_global=1,m=9,Nlayer=12` already resolve locally to q=2/3 with four layers
per three-phase set. Twelve public requests over `D=6/10/14`, `pp/D=1/2`
passed and retained valid per-set identity. Their EMF diagnostics remain
separate from construction admission; these controls do not add an arrayed
q=1 rule.

A separate new-rule array check at `q_global=1,m=9,Nlayer=12`, local q=3,
passed public generation and per-set identity. The m=6, L=8 local-q=2 control
keeps its existing even-q route.
With only four layers, `m=9` still cannot divide the layers evenly among its
three-phase sets. For direct `q∈{1,3}`, `pp=D=4`, `m=3`, `Nlayer=8`, the public
`(1,1,2)` source reports duplicate/missing conductor positions (78 at q=1;
270 at q=3), so public generation remains disabled even though the factor
tuple satisfies the new PP-only formula.

This sample set establishes representative full/proper Q and D cases; it does
not certify every layer and phase geometry. For example, `(4,8,2,4,8,3)` is
disabled because its public CP P2 source has duplicate and missing conductors;
the same factors and layer count pass as two local four-layer sets at `m=6`.
The new PP-only samples at `Nlayer=4` do not imply universal layer support:
`(2,6,1,6,8,3)` and `(2,14,1,14,8,3)` remain disabled because their public
`(1,1,2)` sources contain duplicate and missing conductors. This is a
geometry-specific source failure. `D=2` remains on its separate constructor;
even q with `D≡0 (mod 4)` remains on the existing four-sector constructors,
while odd q may use the P2-parent slices when public preflight passes. Odd D
remains outside the equal-slice ratio, and nonzero phase shifts remain outside
the neutral-configuration gate.

## V7.6 CP Q+PP+P2 parent slicing (2026-09-28)

The new `cp_q_pp_p2_parent_slices` route covers selected, non-default CP
`(Q,D,2)` tuples when `Q>1`, `Q|q`, `D>1`, and `D|pp`. The factor identity
sets `Naa=2QD`; the source has the same Q and P2 dividers and `D=1`, so

```text
Naa_target / Naa_source = (Q*D*P2) / (Q*1*P2) = D.
```

Generate the same-geometry public `(Q,1,2)` reference. Within each phase,
retain its generated parent order and cut each of the `Q*P2` parents into D
equal consecutive pieces. This yields `Q*D*P2` branches per phase. Each child
has `num_slots*Nlayer/(num_phases*Naa)` conductors; the common P2 pass then
orients every child from an N-pole inlet to an S-pole outlet. The route creates
no new connection edge because each child is a subpath of a validated parent.
For these references, CP's actual `Connection` vectors supply each directed
slot step. The source generator checks every vector against its endpoint, the
divider formula slices those steps with the parent path, and admission requires
complete signed evidence before applying the one-pole-region limit.

Admission keeps CP's positive global `Nlayer` divisible by four, supported
phase domain, neutral Regular zero-shift settings, insert-side inlet, CLWP
profile, and public source/target preflight. Arrayed three-phase sets also
require an even positive local layer count. A selected tuple equal to the
CP default factorization remains on the Default route and is not intercepted.
There is no parity restriction on D; its integer value is derived from the
target/source divider ratio.

The finite matrix previously contained six `unsupported-yet` requests in this
domain: `(q,pp,Q,D,L,m)` equal to `(4,4,2,2,4,3)`, `(4,4,2,4,4,3)`,
`(6,6,2,3,4,5)`, `(6,6,2,6,4,5)`, `(6,6,3,2,4,5)`, and
`(6,6,3,6,4,5)`. Focused public generation now checks all six against exact
parent slices, unique coverage, equal branch lengths, phase membership,
ordered CP identity, cross-layer edges, and the one-pole-region travel limit.
A six-phase `q=4, pp=8, L=12, (Q,D,P2)=(2,2,2)` array also passes per-set
path mapping and identity. EMF-only mismatches remain retained as
`not strong symmetry layout`; they do not block construction admission.
Nondivisor Q/D, default factorizations, and the existing `Nlayer` and
configuration gates remain unchanged.

This file preserves the Version 7.5 support reference copied on 2026-09-24.
All dated research and counts below, including sections titled "Current",
describe their stated historical snapshot. They do not independently change
V7.6 admission or replace the current resolver and generated-path checks.
The V7.5 research page (local research excluded)
and candidate review (local research excluded)
retain the original evidence links. Fractional-q interfaces remain available
in V7.6; this update adds no fractional-q construction or fractional-q scan.

## V7.6 three-phase-set array model (2026-09-25)

The runtime now accepts every phase count `m=3k` as `k` independent three-phase
sets. Each set uses the existing 120-degree sequence, owns an equal contiguous
layer group, and is rotated by `360/m` electrical degrees from the previous
set. The total layer count must be divisible by `k`; route support is still
decided by resolving the selected divider tuple against each local set, then
generating and validating the complete array. The local route name may differ
from the route selected using global q when local q maps to another registered
three-phase construction. A set is rejected only when its own selected
construction or the complete array fails its Pattern-specific checks. Odd
local layer groups report ordered Pattern identity as `unverified` while
retaining separate electrical checks. The canonical phase records and
phase-set coordinate transforms are owned by `phase_topology.py`; Pattern
connection rules remain in `get_winding_pattern.py`. The older tables below
are historical route evidence for their stated formulas and parameter domains;
they are not blanket admission of every route at the new phase counts. See the
[phase model](PATTERN_DEFINITIONS_AND_CONSTRAINTS.md#executable-phase-count-extension-2026-09-25).

## V7.6 CP PP-only constructor correction (2026-09-25)

The former `cp_pp_pair_join` intact-parent matcher has been removed from
production admission. Its earlier q=2, pp=D=4 samples are historical method
evidence and are no longer current `Validated` routes. The active CP PP-only
method is `cp_pp_four_pass_weave`: it consumes the public `(1,2,2)` source in
per-phase generated order and applies the four-pass slice rule in
[`PATTERN_DEFINITIONS_AND_CONSTRAINTS.md`](PATTERN_DEFINITIONS_AND_CONSTRAINTS.md#cp-pp-divider-four-pass-weave).
The route shape is derived from the reference branch length
`q * pp / D = 4`, with `D=2`; each case still passes the public resolver and
generated-path checks. The updated q=2, pp=4, L=4, m=3 sketch is publicly
`Validated`. Other tuples without an applicable registered constructor remain
`unsupported-yet`; withdrawing the former matcher is not a blanket CP
exclusion.

## V7.6 CP full-Q/full-PP parent slicing (2026-09-25 historical baseline)

The mixed CP tuple `(q,pp,1)` is now registered for integer `q>1` and even
`pp>=4`, with `Q=q` and `D=pp`. The constructor uses the same geometry's
public `(q,1,2)` reference, slices every same-phase parent into `pp/2` equal
consecutive `2L` segments, and groups by segment index then generated source
order. The q=2, pp=4, L=4, m=3 Phase-A manual sketch is reproduced exactly;
the q=3, pp=6, L=4, m=5 case verifies the parameter-derived rule beyond that
draft. Public preflight still checks the source and complete target, including
coverage, phase/direction, ordered CP identity, edges, and one-region travel.

The neutral generated layouts have `parallel_emf_mismatch` and remain retained
as `not strong symmetry layout`; this does not block route admission. The
Workbench catalog may report `Validated` when its separate Auto probe finds a
strongly symmetric configuration. The former intact-parent `cp_pp_pair_join`
is still withdrawn.

## V7.6 CP `(1,4,1)` parent half-translation (2026-09-26)

The second manual draft now has a parameter-derived constructor for even integer
`q>1` when the selected divider is `(1,4,1)` and four divides the actual
pole-pair count. From the same geometry's public CP `(1,1,2)` source, select
the per-phase parent whose first signed slot step is `+τ`, where `τ=mq`.
With `N=num_slots`, `k=N*L/(4m)`, take its second half `H=P[k:2k]` and
calculate `δ=(H[-1].slot-H[0].slot) mod N`. Emit four forward copies shifted
by `[τ−δ, τ−1, 2τ−δ, 2τ−1] mod N`. The resulting path starts are derived from
the source geometry; manual `inlet_index_adjustments_phase_a` remain outside
the production configuration.

The rule reproduces the saved q=2, poles=8, L=4, m=3 Phase-A conductor groups
after the expected cyclic inlet rotations/reversals and branch reorder. Public
checks also pass for q=2/4 with eight pole pairs at m=3, and q=2 with eight
pole pairs at m=5, all at L=4. Coverage, phase/direction, ordered CP identity,
selected CP edges, and the one-region limit pass. The neutral output retains
`parallel_emf_mismatch`. The Workbench keeps the route's generated status;
Auto Configure separately reports that strong symmetry is not yet verified.

This is a bounded route. Odd q remains `unsupported-yet`, and the actual
pole-pair count must be divisible by four. Each geometry still goes through
public generation: for example, q=2/poles=16/L=8/m=3 fails in its public P2
source, and q=2/poles=16/L=12/m=9 fails target CP edge validation. Preserve
those case-level failures; an inlet translation does not make every layer or
phase combination valid.

## V7.6 CP PP-sector slicing from four-sector source (2026-09-26)

For even integer `q>1`, CP `(1,D,1)` now has a further constructor when
`D>4`, `4|D`, and `D|pp`. It publicly generates the same geometry's `(1,4,1)`
layout, then cuts each complete branch into `D/4` equal consecutive paths.
The new route introduces no connection edge and passes the public source and
target checks for coverage, phase/direction, ordered CP identity, signed edges,
one-region travel, and electrical retention. Generated examples include
`q=2, pp=8, D=8` and `q=2, pp=12, D=12` at `L=4, m=3`; EMF mismatch is retained
as `not strong symmetry layout`.

This extends supported pole-pair factors that are multiples of four, but is
not a complete CP PP-only matrix. D=2 retains its four-pass rule; adjacent
four-sector parent joins fail terminal direction even when their ordered edge
identity passes. D=6 and odd D still lack a validated general construction.
Source or target failures at other layer and phase counts remain case-specific.

## Closeout phase and review boundary (2026-09-24)

This dated snapshot's CP intact-parent statements were superseded by the
2026-09-25 constructor correction above.

The offline Version 7.5 closeout review (local research excluded)
links to the focused candidate audit (local research excluded). The
confirmed one-pole-region rule applies to every insertion, weld and return:
the actual signed connection may cross at most one pole-region boundary.
The CP PP-only parent-pair method now has a guarded public constructor using
local joins and distinct PP inlet sectors. Four sampled q=2, pp=D=4, L=4
cases at m=3/5/7/9 pass public generation; other geometries remain subject
to case-specific preflight. Its earlier three-region join is archived as
rejected. The SLP odd-sector
half-sector method is rejected because its returns cross multiple regions.
Neither judgment rejects the whole divider family. ZLP PP+P2 has generated
examples for optional visual QA.
All 80 Pattern × Divider-type cells have source states; 24 contain at least
one tuple with no registered source, and six contain exploratory default
identity decisions. These are cell counts, not counts of supported routes.
Keep the former pending and repair or qualify the latter from actual paths.

The CP PP-only intact-parent method has four saved complete-path examples
after the one-region gate. They are now public-generated CP routes for those
four sampled geometries following designer confirmation of the ordered CP
connection and per-case production validation. In the first case,
the q=2, pp=D=4, L=4, m=3 example now joins slot 32/layer 3 to slot
25/layer 1 rather than the rejected slot 32 to slot 13 connection. A
source-bound counterexample below shows that unconstrained complete paths do
not establish PP-divider inlet sectors. The registered method therefore
requires one inlet in each selected sector; broader CP PP-only constructions
remain a technical backlog item. Representative public-generated SVGs are
saved in the workflow review. The tested TSP/TLP
odd-D parent methods are bounded method counterexamples; other constructions
remain pending. They are archived without manual review until a different
construction produces an exact public-generated target path with a concrete
ordered-connection question.

## CP Q-only adjacent P2-parent pairing (2026-09-25)

For integer `q` and `Q>1` with `Q|q`, the CP `(Q,1,1)` route uses the same
Pattern's public `(Q,1,2)` source. Group source branches by the phase of their
inlet while preserving V7.6's generated order within each phase. Concatenate
adjacent pairs `(1,2)`, `(3,4)`, and so on without reversing either parent.
Each seam must be an ordered CLWP insertion with `abs(dl)=Nlayer/2`; the source
and target must pass CP identity, phase, occupancy, equal-length, retention, and
one-pole-region checks. The route is limited to neutral Regular, insert-side
generation and positive `Nlayer` divisible by four. Failed pairs remain
case-specific rejected or Candidate results; the constructor does not search
nonadjacent matches.

Public generation evidence at `Nlayer=4`, `poles=8`, `m=3`:

| `q` | `Q` | Source branches per phase | Target result |
| ---: | ---: | ---: | --- |
| 2 | 2 | 4 | 6 retained branches of length 32; valid CP identity; maximum one region crossing. |
| 4 | 2 | 4 | 6 retained branches of length 64; valid CP identity; maximum one region crossing. |
| 4 | 4 | 8 | 12 retained branches of length 32; valid CP identity; maximum one region crossing. |

The q=3, Q=3, poles=8 sample is rejected because the adjacent `(3,4)` parent
seam has `dl=0`, so it is not a CLWP insertion. This is a case-level failure,
not a blanket exclusion for CP Q-only routes.

## Current exploration and admission rule (2026-09-24)

For integer `q`, even layers and odd `m >= 3`, recognize each Pattern by the
complete ordered circumferential direction, radial layer travel and
insertion/weld connection roles in every branch. A numeric pitch or `tau`
interval never establishes identity and must not be a Pattern-specific route
gate. Constructors may use pitch to place endpoints; record the resulting
values as geometry. For an intended arc longer than half the slot circle,
the constructor must record a complete signed step for every edge and the
recognizer must verify it against the endpoints. Without that evidence,
shortest-arc direction is only the current coordinate inference.

For each candidate, check coverage, unique occupancy, equal branch length,
phase and terminal polarity, actual edge sides and layer spans, ordered
direction, weld travel per layer pair, and electrical retention. EMF mismatch
is a separate symmetry diagnostic. A candidate that satisfies the manual
construction characteristics and does not overlap another Pattern is
provisionally accepted, then checked through public generation and saved with
representative generated-path SVGs. Historical pitch-only failures below are
method observations under the former rule, not current Pattern rejections;
their counts require a fresh ordered-direction replay before route promotion.

## Unified odd-m rule and sampled evidence

All divider constructions use one phase parameter `m`, with the shared
precondition that `m` is an odd integer at least 3. A formula must derive
its slot pitch, phase map, signed direction and terminal checks from `m`;
there is no separate three-phase admission rule. Checks at `m=3/5/7` are
samples of this one rule, not proof for every odd `m`. A sampled failure
bounds the proposed construction method, and a sampled success remains
subject to the public generator and independent path checks.

The BWP Auto `min_pin_types` formula early stop has a narrower audited
three-phase optimization domain. Other odd phase counts use full search
with the same Pattern construction rules, not a separate winding route.

Historical probes below may use numeric pitch windows that the current
ordered Pattern policy supersedes. Their recorded failures bound those dated
methods; use current connection order, radial travel, phase and full-path
checks before making a present route decision.

### Production TLP PP-only even-D cut from the approved D=2 route (2026-09-24)

The public route now admits `(1,D,1)` when `q` is a positive integer at most
2, `D>2` is even and divides `pp`, `L>=4` is even, and `m>=3` is odd. It
generates the approved `(1,2,1)` parent and cuts each complete parent branch
into `D/2` equal children at whole `L`-conductor pass boundaries. Every target
passes the public coverage, electrical-retention, TLP identity, return and weld
checks. The finite public regression covers 150 tuples with integer `q∈{1,2}` for
`pp=4..10`, `L=4..12` and sampled `m=3/5/7`. Regular, zero-shift,
insertion-side configuration is the admitted setting; other configurations
retain their separate route checks. Parallel EMF asymmetry remains a diagnostic.

For `q=1`, even `D>2` dividing `pp`, take every approved TLP `(1,2,1)`
parent branch and divide it into `D/2` contiguous children at complete
`L`-conductor pass boundaries. Each parent covers every one of its `pp`
pole-pair sectors exactly once; its children partition those sectors, with
`2*pp/D` distinct sectors per child. The route has one symbolic odd-m phase
parameter. `m=3/5/7` are samples of that same construction, not separate
admission paths.

The 450-case source scan (local research excluded)
uses integer `q=1..6`, legal even `D>2` for `pp=4/6/8/10`, even `L=4..12`
and sampled odd `m=3/5/7`. It records 150 passing paths at integer `q∈{1,2}` and 300
approved-parent blocks at q=3..6. The independent
exact-case audit (local research excluded)
replays all 75 q=1 paths and verifies coverage, equal branches, phase and
signed direction, N-to-S terminals, nonzero branch fundamental, full TLP
identity, top-bottom return, TLP weld direction and pitch, PP-sector
partition and half-turn paired inlets. All 75 pass at `(pp,D)` of `(4,4)`,
`(6,6)`, `(8,4)`, `(8,8)` and `(10,10)`, with `L=4/6/8/10/12` and
`m=3/5/7`. This exact-case research supported the production cut above;
other odd m remain outside this finite verification grid.

At q=2, 30 passing cases have identical ordered paths to registered
`(2,D/2,1)` Q+PP routes. The other 45 have no registered Q+PP comparator;
none has the q=1 PP-sector-lineage certificate. These q=2 paths are admitted
as the same TLP PP-only construction: overlap with another divider tuple of
the same Pattern is recorded, not a cross-Pattern conflict. q=3..6 parent blocks
limit this source method and do not reject those target routes. Nonneutral
phase shift, transposition and weld-side inlet are outside this audit.

The q=2 repeated-sector audit (local research excluded)
finds a weaker shared invariant in all 75 q=2 cases: each registered parent
covers each PP sector twice, once per q lane, and each child contains
`2*q*pp/D` distinct sectors. That condition also holds for the 30 exact
Q+PP aliases, so it cannot establish an exclusive PP-only factor. A stronger
whole-sector proposal would place both q lanes of each sector in one child.
At `q=2, pp=D=6, L=4, m=3`, the
complete-pass regroup enumeration (local research excluded)
tries all 384 orders and orientations of the four parent passes spanning
the first two sectors; none has legal TLP edges. This is a counterexample to
that fixed-parent regrouping method only. The single odd-m formula remains
unchanged; `m=3` here is a minimal counterexample sample, not a phase-specific
rule.

The cyclic-start audit (local research excluded)
then rotates each approved q=2 `(1,2,1)` parent at every whole-L pass
boundary before the D/2 cut. All 1,080 starts across the 75 neutral
`m=3/5/7` cases pass independent whole-path topology, signed phase, N-to-S
terminal, nonzero fundamental, full TLP identity, physical-edge and weld
checks. They yield four or eight distinct conductor partitions per case;
60 starts exactly reproduce a registered Q+PP path. All retain a parallel
EMF mismatch diagnostic without being rejected on that basis.

The following factor-lineage discussion is historical research context, not a
production admission gate. In every audited parent,
the two q-lane blocks traverse the same `pp` sectors in the same order, so
copies of a given sector are exactly `pp` passes apart on the cyclic path.
Each D>=4 child contains `4*pp/D <= pp` consecutive passes and therefore
cannot hold both q lanes of any complete sector. All 1,080 sampled paths
confirm zero complete sectors per child. This limits that stricter proposed
factor interpretation; it does not invalidate the admitted TLP path or require
a different source for the current PP-only construction.

A broader same-phase cross-parent enumeration (local research excluded)
at `q=2, pp=D=6` permits each of the four required sector/lane passes to
come from either approved D=2 parent. For every even `L=4..12` and sampled
odd `m=3/5/7`, its `2^4 * 4! * 2^4 = 6,144` parent selections, orders and
orientations produce no complete TLP-legal child: 92,160 failures across
15 cases. Each directed pass-edge graph has 16 legal two-pass joins, but
the longest path without repeating a required sector/lane cell has only
two passes. This rules out a larger family of fixed-parent pass
regroupings under the same symbolic odd-m rule; it does not reject TLP
PP-only or constructions that change pass geometry or special returns.

### Bounded SSP/SLP proper-Q plus PP parent cut (2026-09-24)

For `1<Q<q`, `Q|q`, and `D>1`, `D|pp`, the registered neutral,
Regular, insertion-side SSP/SLP mechanism
groups complete `2L` blocks from each same-Pattern `(1,D,1)` PP parent
branch into Q children. A child contains `(q/Q)*(pp/D)` complete lane
blocks. SSP takes contiguous cuts from its lane-major parent. SLP stably
filters the sector-major parent's blocks into Q contiguous q-lane cohorts,
keeping the original block order within each child. This construction uses the
same symbolic odd `m>=3` rule at every phase count; 3, 5, 7 and 9 are
validation samples, not separate implementations. The historical
`spiral_q_pp_parent_cut_probe.py`/
`spiral_q_pp_parent_cut_result.json` scan covers q=4/6, pp=2..10, every
proper Q and D factor, L=2..12 even, and sampled odd m=3/5/7. All 1,836
cases pass independent complete-path occupancy, equal-length, signed phase,
physical edge, Pattern identity and SLP weld-direction checks. Of these,
900 target tuples had no registered constructor at the historical scan date;
the other 936 were already source-enabled. There are 1,674 retained
EMF-asymmetric cases. None of
these counts certifies strong symmetry or a target factor meaning.

The source route determines the connection-unit order. SSP's PP parent and
the classifier-default SLP parent are q-lane-major. The selected
`slp_pp_only` parent is sector-major. The probe therefore checks each
child's actual `2L` block start phasor: it must contain exactly `q/Q`
distinct q lanes, each with `S=pp/D` blocks, and the Q siblings from one
PP parent must partition all q lanes. This invariant holds in 1,494/1,836
cases, including 684/900 targets that were unregistered at scan time. It
fails in 342 selected SLP PP-parent **contiguous cuts**, including 216
formerly unregistered targets. This is a counterexample to that cut method;
stable lane regrouping handles those 216 without changing block interiors. Every
lane-partitioned candidate has a parallel EMF mismatch, which is retained
as a diagnostic, not a construction rejection. The 306 two-layer rows have
the identity analyzer's `degenerate-two-layer` confidence rather than full
Pattern-identity evidence.

When `S=1`, all 972 cuts isolate q-lane groups within one PP sector. In
sector-major SLP parents with `S>1`, cuts can instead isolate whole or
partial sectors. The
`spiral_q_pp_alias_audit.py`/`spiral_q_pp_alias_result.json` comparison
checks the 432 cases with `Q*D|pp` against the public `(1,Q*D,1)` route:
162 have identical per-branch conductor sets, and 36 have identical
ordered paths. All 162 set aliases fail the Q-lane partition invariant;
the other 270 comparisons preserve Q-lane partition and differ physically.
Thus neither a universal PP-only alias nor a universal Q-divider
construction is established merely by equal cuts. PP-sector lineage comes
from the registered parent.

The separate `spiral_q_pp_support_audit.py`/
`spiral_q_pp_support_audit_result.json` replays all 900 formerly unregistered
full-identity cases with even L=2..12 (450 SSP, 450 SLP).
All 900 now match public generated paths and pass an independent full-path check, including physical Pattern
edges, nonzero fundamental in every branch, SLP weld direction and
production spiral edge validators. These
exact neutral Regular insertion-side tuples have **sampled production
evidence** for the registered PP-parent cut. Every one has parallel EMF mismatch, so
each is retained as `not strong symmetry`. The public Q+PP
constructor is registered under its lane and configuration guards;
nonneutral settings, physical realization
and broader proof across odd m remain pending. The two-layer results use
the same ordered-construction rule with documented small-parameter overlap.

### ZLP PP plus P2 from a complete P2 parent (2026-09-24)

For a selected `(1,D,2)` with `D>1` and `D|pp`, the constructor generates
the same geometry's public ZLP `(1,1,2)` layout, then splits every ordered
P2 branch into D equal contiguous children. Even L makes each child length
`q*(pp/D)*L` even, preserving insertion/weld parity. The public route checks
complete occupancy, signed phase, pair-local ZLP edges, Pattern identity,
nonzero branch fundamentals and P2 N-to-S terminals. It uses one symbolic
odd `m>=3` rule. Existing classifier-default ZLP routes keep their own
constructor.

For a selected PP+P2 cut, transposition and inlet settings are checked against
the actual configured P2 parent and target children before route admission.
Phase/radial shifts follow the post-connection rule above; for example,
`(q,pp,D,L,m)=(1,4,2,2,3)` with layer shifts `[0,3]` now reaches the
electrical check and fails for zero fundamental EMF, not Pattern connections.
Weld-side inlet and manual inlet adjustment are likewise case-validated;
the tested settings at this geometry do not generate.

The construction depends on a complete P2 parent. A parent-generation
failure leaves only a case-limited pending result; it does not reject the
whole PP+P2 route. The corrected odd-`m` mirror axis now gives complete P2
parents and independently checked public PP+P2 children in all 540 selected
neutral finite-domain cases at q=1..6, pp=2..10, even L=2..12 and m=3/5/7.
The earlier `(q,pp,D,L,m)=(2,4,2,4,5)` parent failure was caused by the
three-phase axis and is retained only as a regression witness. The replayable
finite audit is
`workbench_preview/even_d_source_partition_20260923/zlp_pp_p2_source_cut_audit.py`
with its neighboring JSON result. EMF mismatch remains a diagnostic.

### CP PP-only intact-parent pairing research (2026-09-24)

The pending selected `(1,D,1)` target has half as many branches as the
registered CP `(1,D,2)` source. A direct construction hypothesis pairs two
complete same-phase source paths into each child. Because each source has an
even conductor count and the target uses an insertion-side inlet, the first
edge is a weld and the join is an **insertion-side CLWP edge**. It must cross
`L/2` layers and follow the ordered signed layer/travel rule. Slot pitch is
recorded as geometry, not used as a CP identity or admission whitelist. Every
actual edge must also cross at most one pole-region boundary. The
probe permits either orientation of both parents.

In eleven neutral discriminating cases, ten had a validated public source.
Four yield phase-local exact covers that pass conductor occupancy, topology,
electrical checks, ordered CP identity and the current selected CP edge
validator after the one-region join gate. A sector-constrained exact cover
gives D distinct pole-pair inlet sectors per phase in all four. They use
`q=2, pp=D=4, L=4` and sample the same
construction at
`m=3/5/7/9`; the former `q=4, pp=D=4, L=6, m=5` cover relied on a
multi-region join and is now a counterexample to this intact-parent method.
Their target resolver now enables the guarded parent-pair constructor only
where its actual complete paths pass. Distinct inlet sectors are required by
this method, but do not establish every possible PP-factor construction.

An independent sector-lineage counterexample probe (local research excluded)
replays `q=2, pp=D=4, L=4, m=3` with the public source. Each phase has 576
complete-parent exact covers, 64 with one **target inlet** in each of the
four physical pole-pair sectors. The first unconstrained cover passes all
192/192 occupancy, equal-length, phase/electrical, ordered CP identity and
selected CP edge checks, yet each phase starts twice in sector 0 and twice
in sector 2, missing sectors 1 and 3. A sector-bijective alternative passes
the same full checks. Those 64 covers have six distinct parent-sector pair
signatures, so a fixed pair offset is also false. This proves that generic
complete-path validity and parent exact cover alone cannot establish the
proposed PP-factor inlet lineage; sector bijection is a distinguishing
hypothesis at `pp=D`, not yet a sufficient general rule for `D|pp`. The
576-cover count and its examples predate the one-region connection gate;
they are archival method evidence and must not be read as 576 currently
eligible covers. The
source-bound case ledger (local research excluded)
includes both complete paths, all branches, and the exact-cover budget.

A bounded exact sector-translation probe (local research excluded)
then tested the 64 sector-bijective complete-parent covers in every phase at
`q=2, pp=D=4, L=4` and `m=3/5/7/9`. Each sample has 576 exact covers per
phase, but **zero** sector-bijective covers whose ordered target branches are
pure translations of one branch by the physical pole-pair sector width.
Thus adding exact slot translation to sector-bijective inlet coverage would
exclude this intact-parent candidate method. This is a method counterexample,
not a proof that CP PP-only is impossible: CP may require coordinated layer
reflection, reversal, a different parent partition, or a new starting
conductor. Its 64-cover count also predates the one-region gate and is
archival rather than a count of currently eligible covers. The
source-bound ledger (local research excluded)
records the four sampled odd `m` values, all phase-local covers, source and
validator hashes, and the 120-second budget.

Six source-valid cases have no valid intact-parent join under the checked
order/reversal method. At `q=2, pp=D=2, L=2, m=3`, all 144 pairs were checked;
24 have nonzero slot travel and the required layer span but fail the ordered
insertion direction. The first joins `(7,layer 1)` to `(12,layer 0)`. One
case has no usable source. The old slot 32/layer 3 to slot 13/layer 1 CP
join crosses three regions; the replacement joins slot 32/layer 3 to
slot 25/layer 1 and enters one adjacent region. Next establish the broader
PP-factor inlet/sector relation and derive another starting-conductor or source
partition for the method counterexamples. The guarded constructor uses one
symbolic odd `m>=3` parameter
governs all cases; sampled phase counts do not create separate routes. See the
replayable probe (local research excluded)
and its neighboring JSON result.

### SSP/SLP Q+PP nonneutral method boundaries (2026-09-24)

The `spiral_q_pp_configuration_probe.py`/
`spiral_q_pp_configuration_result.json` sample tries five isolated settings
on the registered `(1,D,1)` PP parent before cutting: alternating layer
shift, Uniform offset, Times, Interval, and weld-side inlet. At three
`(q,Q)` pairs, six `(pp,D)` pairs, L=4/6 and m=3/5/7, all 1,080
attempts stop before the target cut: 660 source decisions are disabled and
420 SLP source generations fail. These are limitations of reusing the
registered parent under those settings, not rejections of `(Q,D,1)`.

The separate `spiral_q_pp_shift_transfer_probe.py`/
`spiral_q_pp_shift_transfer_result.json` applies layer offsets
`[0,1,0,1,...]` directly to all 1,836 neutral candidate paths. Every
translated path keeps unique conductor occupancy and phase/sign coverage;
subtracting each layer's offset reproduces the neutral path exactly. Yet
every case violates the physical SSP/SLP ordinary-edge pitch: for an
adjacent-layer edge, `ds_physical = ds_neutral + shift[end_layer]
- shift[start_layer]`, so its required signed `±tau` becomes `±tau±1`.
In 1,530 L>=4 cases the Pattern identity analyzer also reports changed
spiral/lap direction on insertion edges. The 306 L=2 identities are
`degenerate-two-layer`; their physical weld edges still fail the independent
pitch check. The smallest sampled witness, SSP `q=4,Q=2,pp=D=2,L=2,m=3`,
starts `(0,0)→(13,1)` with `tau=12`. These are counterexamples to direct
layer translation, not to a compensating shifted construction. No shifted
production route is enabled.

## Odd-phase BWP and UWP Q+PP construction (2026-09-23)

For positive integer `q`, a proper divisor `1<Q<q`, `D>1` dividing `pp`,
`P2=1`, positive even layers, and odd `m>=3`, BWP reuses its existing
bidirectional lane/sector constructor at `(Q,D,1)`. The selected edge oracle
uses the phase-derived pole pitch `m*q` for adjacent-layer ALWP edges and
`m*q` or `m*q-1` for the same-layer return. The source's earlier `m=3` gate
and fixed `3q` check had hidden valid five- and seven-phase paths. The
selected production route samples the requested layer shifts, transposition
settings and inlet side through the existing constructor, then checks coverage,
electrical retention, BWP wave edges and body pin types. Radial shifts and
manual inlet adjustments remain outside this route. Sampled weld-side inlets
currently fail the wave-edge check; there is no general weld-side construction
claim. Tuples that match the classifier default at any odd phase count keep
the existing configurable default path; those results have their own case
checks and do not claim the selected edge oracle. P2=2 remains explicitly
rejected.

UWP `(Q,2,1)` with `1<Q<=q`, `Q|q`, even `pp`, positive even layers and odd
`m>=3` uses its existing `(Q,1,2)` reference plus second-pole-region
deployment. The configurable PP path now passes the requested phase count to
the shifted phase map. The router uses the generator's PP-configuration
validator: Regular with supported layer shifts and Uniform/Jump offsets can be
sampled; Times, Interval and weld-side inlet are disabled for this route.
Its signed adjacent-layer edges retain the `(m-1)q < pitch < (m+1)q` test.

The registered UWP Q+PP exact audit (local research excluded)
replays all 720 `(Q,2,1)` tuples with `q=2..6`, `1<Q<=q`, `Q|q`, even
`pp=2..10`, even `L=2..12` and sampled `m=3/5/7` under neutral Regular,
zero-shift, insertion-side settings. Independent complete-path checks verify
all 720 exact cases: unique occupancy, signed phase, adjacent-layer directed
wave edges in the stated open interval, unchanged q lane on insertion edges,
full Pattern identity, N-to-S terminals, disjoint Q groups of `q/Q` lanes,
full pp-sector coverage in every two-layer wave block, and paired inlets half
a circumference apart on complementary outer layers. A legacy generic wave
probe assumed the narrower `m*q +/- 1` pitch and missed 75 valid cases at
`q=6, Q=2, L>=4`; the route-specific interval audit rechecks those paths.
Every verified case reports parallel EMF mismatch and is retained as
`not strong symmetry layout`, without strong-symmetry certification. These
finite exact cases do not prove nonzero shifts, transposition settings, weld
inlets or all odd phase counts. Three cases in the earlier nine-case wave
sample overlap and are counted once in the HTML ledger.

The registered UWP Q+P2 exact audit (local research excluded)
replays all 1,440 `(Q,1,2)` tuples with `q=2..6`, `1<Q<=q`, `Q|q`,
`pp=1..10`, even `L=2..12` and sampled `m=3/5/7` under neutral Regular,
zero-shift, insertion-side settings. Independent all-branch checks verify
1,425 exact cases: unique occupancy, phase membership and signed direction,
full Pattern identity, P2 N-to-S terminals, Q disjoint q-lane groups, paired
cohorts entering from complementary outer layers, full pp-sector coverage in
each two-layer wave block, and a consistent directed edge orientation per
branch satisfying `(m-1)q < pitch < (m+1)q`. At `pp=1`, both circular
directions can satisfy that interval; the audit does not assert a unique
direction. The balanced constructor records its intended signed travel for
every edge; a long forward arc at `pp=1` must not be reinterpreted as the
opposite shortest arc. This rule uses the same symbolic odd `m` for all
phase counts, and P2 orientation reverses the recorded sign when needed.
The remaining 15 cases are precisely `Q=q, pp=1, L=2` at the
sampled phase counts: their public insertion-side two-conductor branches
lack the required ALWP body Pin identity. The separate public weld-terminal
route below resolves those exact tuples under its neutral weld-side settings.
The older generic `m*q +/- 1` edge probe is too narrow for many valid Q+P2 paths and is not
the route-specific audit oracle. All 1,425 verified cases report parallel
EMF mismatch and remain `not strong symmetry layout`, not certified strong
symmetry. These insertion-side audit cases do not prove every odd `m`,
nonzero shift or transposition setting; the weld-side route has its own scope.

The default UWP P2-only exact audit (local research excluded)
replays all 1,080 `(1,1,2)` tuples at integer `q=1..6`, `pp=1..10`,
even `L=2..12` and sampled `m=3/5/7` under neutral Regular, zero-shift,
insertion-side settings. Independent all-branch topology, signed phase,
UWP edge, full Pattern identity, P2 N-to-S terminal, q-lane and sector
coverage checks verify 1,077 exact cases under the current ordered-identity
rule. Each verified branch admits a consistent directed edge orientation;
at `pp=1`, the two-pole circumference can make opposite circular travel
equivalent, so no unique direction is claimed. The three pending
`q=1, pp=1, L=2` insertion-side tuples require the registered weld-terminal
route below, which provides an ALWP body Pin through the public generator.
The other 87 cases previously appeared pending because the legacy UWP
constructor omitted signed travel metadata at a long-arc edge. Preserving
its constructor direction and reversing that metadata with P2 orientation
lets the same ordered identity check verify them at `m=3/5/7`, without a
phase-count exception. No verified P2-only case
reports parallel EMF mismatch, which is still not a general strong-symmetry
or manufacturing certification. The result does not prove nonzero shifts,
transposition settings, or all odd phase counts.

The short UWP P2 weld-terminal construction (local research excluded)
derives both branches per phase and q lane directly from the shifted phase
map at zero shift for `q=Q=1..6`, `pp=1`, `L=2`, `P2=2`, sampled odd
`m=3/5/7`. It joins the unique N slot to the diametric S slot across the
opposite layer, then repeats with complementary layer orientation. With
weld-side terminals, each two-conductor branch has one physical ALWP
insertion Pin and no weld edge. Its 18-case audit (local research excluded)
independently verifies complete occupancy, phase/sign, Pin roles, full UWP
identity and P2 N-to-S terminals. This supplies bounded **production
support** for the three P2-only and 15 full-Q + P2 exact cases;
the public generator reproduces all 18 paths under neutral Regular settings
with weld-side inlets. Fifteen q>1 cases retain parallel EMF mismatch as
`not strong symmetry layout`. The one-pole-pair geometry does not identify a
unique circumferential direction. Nonzero shifts, other layer counts, and
manufacturing implementation remain unverified.

UWP PP-only `(1,2,1)` now derives one positive-polarity start belt for each
phase with zero-based belt index `((m+1)*phase) mod (2m)`, rather than the
three-entry sequence `(0,4,2)`. Its forward edge oracle uses `m*q-1`, `m*q`,
or `m*q+1`. The same PP configuration validator is applied in the resolver,
so a Times/Interval or weld-side request is disabled before generation.
In the bounded zero-shift Regular public-entry sweep, all 180 applicable
`q=1..6`, even `pp=2..10`, even `L=2..12` cases were retained at each of
`m=3/5/7`; layer shift and Uniform/Jump samples also retained.

The registered UWP PP-only exact audit (local research excluded)
replays all 540 of those selected integer-q tuples. Independent all-branch
topology, signed phase, directed wave-edge, nonzero fundamental, full Pattern
identity and terminal checks verify each exact case. Each two-layer wave block
covers all `pp` sectors twice at one q lane; each phase has two inlets half a
turn apart on complementary outer layers. This is one parameterized odd-`m`
construction sampled at `m=3/5/7`, not separate phase-specific routes. The
three overlapping cases from the earlier nine-case wave audit are counted
once in the HTML ledger. These results apply to neutral Regular, zero-shift,
insertion-side starts; the sampled nonzero shifts and transpositions are not
promoted to this full-domain finding. EMF asymmetry remains a separate
diagnostic, not a construction rejection or strong-symmetry certification.

A zero-shift Regular public-entry sweep over `q=2..6`, `pp=1..10`,
`L=2/4/6/8/10/12`, `m=3/5/7` retained all 306 applicable BWP cases at each
phase count. The corresponding UWP sweep over even `pp=2..10` retained all
240 applicable cases at each phase count. These are bounded source-generator
checks, not a guarantee for every nonzero shift or transposition. EMF-only
asymmetry remains `not strong symmetry layout`; occupancy, phase and
Pattern-edge checks remain separate.

The registered BWP proper-Q + PP exact audit (local research excluded)
replays all 450 selected `bwp_q_pp` tuples in the finite integer domain.
Its independent full-path topology, signed phase, BWP edge/return, nonzero
fundamental, q-lane partition, ordered Pattern identity and D inlet-sector
checks verify all 450 exact Regular, zero-shift cases across sampled odd
`m=3/5/7`. The 39 `L=2` cases retain a separate overlap diagnostic but pass
the current ordered identity rule. The Q groups are disjoint sets
of `q/Q` q lanes per phase; each group has D inlet sectors in one residue
class modulo `pp/D`. All 450 verified layouts report parallel EMF mismatch
and are retained as `not strong symmetry layout`, without strong-symmetry
certification. The audit replays the registered parameterized constructor;
it does not independently derive a new constructor or prove untested
nonneutral configurations or every odd m.

### Pending even-D source-path partition hypothesis (2026-09-23)

For CP, ZPP, TSP and TLP, a bounded research probe partitions complete
same-Pattern `(Q,1,2)` source paths into `D/2` equal contiguous segments for
even `D>2`, giving the branch count and length of `(Q,D,1)`. This keeps every
retained local edge and cuts only at even-length segment boundaries. The
replayable `workbench_preview/even_d_source_partition_20260923/probe.py`
records 33 cases: 26 passed its all-branch occupancy, phase/sign, terminal,
Pattern identity and applicable edge/weld checks; seven lacked a valid source.
These are exploratory paths, not registered support.

The simple cut does not yet establish the pp-divider's inlet-sector meaning.
At CP q=Q=2, pp=D=4, L=4, m=3, its phase inlet starts cover respectively
4, 2 and 4 distinct pole-pair sectors. TSP, TLP and ZPP also show incomplete
coverage in that sample family. The D-sector expectation is a falsifiable
extension of the registered D=2 deployment, not yet an independent Pattern
rule. Define that invariant, then test a bijective sector relocation with
full occupancy, edge, return and terminal revalidation. Source-unavailable
cases remain pending for a different construction, not rejected as impossible.

A second bounded probe,
`workbench_preview/even_d_source_partition_20260923/sector_relocation_probe.py`,
rotates complete segments by pole-pair steps and solves an exact-cover
assignment with `Q` inlets in each of `D` sampled sectors. It found 26
path-validated exploratory candidates and seven source-blocked cases in the
same 33-case set. Every candidate passed the probe's full occupancy,
phase/sign, terminal, Pin, neutral TSP/TLP signed-edge and return, CP/ZPP edge,
and applicable TLP weld checks. This still does not prove the branch-wide
meaning of the PP factor: the first CP q=Q=2, pp=D=4, L=4, m=3 branch starts in
sector 0 but visits sectors 0, 1 and 2. Inlet quotas alone cannot promote the
route. The next rule must define each branch's allowed sector traversal from
approved Pattern behavior and test that invariant independently.

The 2026-09-24 V3 lineage test compares **every** V2 target branch with a
distinct contiguous `D/2` cut of an approved `(Q,2,1)` branch after a whole
pole-pair rotation, preserving conductor order and layer. The replayable
`workbench_preview/even_d_source_partition_20260923/d2_lineage_probe.py`
now records 13 bijective matches, three rotation-only counterexamples,
11 unavailable `D=2` sources, four unavailable V2 sources and two V2 path
counterexamples in the same 33-case set. The first rotation-only
counterexample is CP `q=Q=2, pp=D=6, L=6, m=3`:
only 18 of 36 target branches match any rotated D=2 cut. The formerly used
ZPP `q=4, Q=2, pp=D=4, L=4, m=5` source is unavailable under the current
same-layer-pair weld-direction check; its older correspondence is historical
geometry evidence only. A D=2 route can
traverse all pole-pair sectors, so branch confinement to its inlet sector is
not an approved invariant. The counterexamples reject only this rotation-only
lineage hypothesis; reflected or reversed transformations and independent
target constructions remain pending.

A bounded V4 comparison tested the original cases and selected factor-relation
contrasts within the finite q/pp/layer/m scope. It used the approved D=2
deployment's geometric ingredients kept explicit: layer reflection, a pole
mirror anchored to the **whole source branch inlet** and preserving its q lane,
path reversal, and odd pole-pitch translation. It found an all-branch bijection
for 23 of 68 cases: 19 need only whole pole-pair rotations; four need two
operations. Another 41 lack a usable V2 or D=2 source. Two further cases
have a V2 path counterexample. Two source-available
TSP cases at `q=Q=2, pp=8, D=4`, including `L=4, m=3` and `L=12, m=7`,
fail the V2 exact-cover search: no disjoint whole-segment rotations satisfy
its hypothesized Q starts in D sampled sectors. This bounds V2's inlet quota
or rotation scheme, not the target TSP route. In the first CP
`q=Q=2, pp=D=6, L=6, m=3` case, half
the branches match with odd-pole translation plus reversal and half with layer
reflection plus q-lane pole mirror. Earlier ZPP transform matches are not
current-source evidence because the corresponding D=2 source now fails the
same-layer-pair weld-direction check. The replayable comparison and source hashes are in
`workbench_preview/even_d_source_partition_20260923/d2_transform_probe.py`
and `d2_transform_result.json`. This is an exact geometric correspondence
between already path-validated V2 candidates and approved D=2 fragments;
it does not prove these operations preserve each Pattern's divider meaning
or admit a production route.

The repeated-sector TSP counterexample led to a V5 exhaustive inlet-set
comparison at `q=Q=2, pp=8, D=4`. For each TSP/TLP geometry with even
`L=4..12` and odd `m=3/5/7`, all 70 ways to choose four of eight pole-pair
inlet sectors were passed through the same whole-segment exact-cover search
and all-branch Pattern checks: 30 matrices and 2,100 set evaluations. TLP
accepts exactly the six sets closed under half-turn pairing
`s -> (s+pp/2) mod pp` at every tested L and m. The first TSP conjecture,
two even-indexed plus two odd-indexed sectors, is **false** beyond L=4/12:
it predicts 36 successes at L=6/8/10 but finds only 6/18/6, with 34/22/34
classification mismatches respectively per m. Within this matrix, the
observed TSP sets depend on L and are unchanged across m=3/5/7. At L=6/10,
the six accepted sets are half-turn paired; L=8 has 18 accepted sets with
three cyclic sector-set classes. The original evenly spaced V2 set
`(0,2,4,6)` fails TSP at L=4/12 but succeeds at L=6/8/10, while it succeeds
for TLP at every tested L. These are bounded construction observations,
not a derived general PP-divider rule. The next proof obligation is to
derive the layer-dependent TSP and half-turn TLP conditions from signed
passes, top-bottom returns and weld direction, then test other q/Q and D
relations. The TSP success-count sequence by layer-pair count `n=L/2` is
36, 6, 18, 6, 36 for n=2..6. The apparent period-four recurrence is false:
an L=16 extrapolation has only six accepted sets, not 18. Evidence and
hashes are in
`workbench_preview/even_d_source_partition_20260923/inlet_sector_relation_probe.py`
and `inlet_sector_relation_result.json`.

V6 tests the factor relation `g=gcd(n,pp)` at TSP `q=Q=2, pp=8, D=4,
m=3`, enumerating all 70 inlet sets for each even L=4..32. Across 1,050
checks, the **same accepted set family** recurs whenever g recurs, with no
classification mismatch: g=1 or 8 accepts the six half-turn-paired sets;
g=2 accepts all 36 parity-balanced sets; g=4 accepts 18 sets (one sector
per residue modulo 4, or all four sectors of one parity). L>12 is
extrapolation outside the declared finite inventory. The finite-domain
V5 matrices independently show the same accepted families for m=3/5/7.
This is a parameter-derived candidate explanation, not a proof from signed
TSP connections. In a TSP pass, `L-1` adjacent-layer spiral steps each
advance one pole region, and the top-bottom return adds `+1` or `-1`:
the complete pass therefore advances `L` or `L-2` pole regions. Derive how
that transition yields the observed gcd inlet classes while preserving
every CLWP return before admitting any route. The V6 evidence is in
`workbench_preview/even_d_source_partition_20260923/layer_pair_factor_probe.py`
and `layer_pair_factor_result.json`.

### Pending odd-D paired-source bridge hypothesis (2026-09-24)

For TSP and TLP, pair complete same-Pattern `(Q,1,2)` source branches
within each phase, concatenate each ordered pair, and cut the joined path
into `D` equal, even-length `(Q,D,1)` branches. This moves the source
branch bridge inside the middle target branch when `D` is odd; it is a
candidate construction, not a registered route. The bounded probe checks
occupancy, phase and signed direction, Pattern identity, N-to-S terminals,
top-bottom return pitch, and TLP weld direction on complete paths. EMF
asymmetry remains a separate diagnostic.

At `q=Q=2`, odd `D=3/5` dividing `pp=3/5/6/9/10`, and the sampled
`(L,m)=(4,3),(6,5),(12,7)`, 24 of 30 TSP/TLP cases form retained path
candidates. All 15 sampled TLP cases pass. Six TSP cases lack a legal
top-bottom return under any ordered source pairing. They refute this
particular bridge method for those tuples; they do not reject the TSP
factor family. The same symbolic odd-`m` construction is used throughout;
the three phase counts are samples rather than separate rules. Derive the
bridge-pitch and cut conditions from `q,Q,pp,D,L,m`, then check other
q/Q relations, phase shifts and transposition before considering admission.
The hash-stamped evidence is
`workbench_preview/even_d_source_partition_20260923/odd_d_pair_bridge_probe.py`
and `odd_d_pair_bridge_result.json`.

The next bounded checks distinguish method conditions from route support.
For source paths with `q=Q`, let `tau=mq`, `n=L/2`, and `g=gcd(pp,n)`.
Measured in pole regions modulo `2pp`, the lower/upper source inlet
cohorts have endpoint displacements `1-2g` / `2g-1` for TSP and `-1` / `+1`
for TLP. A replayable source endpoint scan matched this relation in all
2,160 TSP/TLP cases at q=Q=1..6, pp=1..10, even L=2..12 and m=3/5/7;
540 of those sources had candidate rather than valid Pattern identity.
This is finite source evidence, not a proof for arbitrary odd m.

The simple bridge pairs paths within each inlet cohort, so each cohort's
`Q` members require even `Q`. For TSP the bridge pitch is
`(2g-1)tau ± 1` after pole-ring orientation; the method's permitted
top-bottom return pitch is `tau-1`, `tau` or `tau+1`, yielding the tested
factor condition `g in {1,pp}`. TLP source displacement is independent of
`g`, giving its same-cohort bridge a legal oriented `tau ± 1` pitch.
Across 252 q=Q=2 odd-D cases, 42 lacked a retained L=2 source; of 210
source-available cases, 177 produced complete-path candidates and 33 were
pairing-method counterexamples, with no mismatch to the factor predictor.
Across a separate 120-case q=Q=1..5 parity sample, 42 candidates and 78
method counterexamples matched the even-Q plus TSP-factor predictor.
Source transformations, proper `q>Q`, phase shifts, transposition and
other cut locations remained open at this stage. None of these
counterexamples establishes target-route impossibility. The replayable
evidence and case records are
`odd_d_factor_probe.py` / `odd_d_factor_result.json`,
`odd_d_q_parity_probe.py` / `odd_d_q_parity_result.json`, and
`odd_d_source_endpoints_probe.py` / `odd_d_source_endpoints_result.json`
in the same preview directory.

For the proper integer factors within q=1..6, only `(q,Q)=(4,2),(6,2),
(6,3)` occur. The current TSP/TLP `(Q,1,2)` raw constructors stop after
one q-lane pole cycle, leaving branches shorter than the required physical
length when `1<Q<q`. An exploratory completion joins `q/Q` copies of each
raw branch translated by consecutive physical slots, with a top-bottom
return between copies. It orients source branches N-to-S and independently
checks complete occupancy, equal branch length, phase and signed direction,
all connection edges, Pattern identity, top-bottom returns and TLP weld
direction. At neutral settings, pp=1..10, even L=4..12 and m=3/5/7,
684 of 900 source cases pass; 216 refute this simple lane sweep. The
method's finite-domain predictor needs `pp>1`; TSP additionally needs
`gcd(L/2,pp) in {1,pp}`. The pp=1 counterexamples show a separate
small-pole weld or insertion-edge conflict. This candidate does not repair
the production route by itself. All 684 path candidates have a parallel
complex-EMF mismatch. They remain retained `not strong symmetry layout`
evidence, not strong-symmetry results.

Composing that source candidate with the odd-D ordered pairing and cut
produces 354 complete-path candidates among 630 cases with odd D>1 dividing
pp<=10. In 99 cases the source sweep fails; in 177 the pairing fails.
All applicable even-Q and TSP gcd method predictions match these results.
All 354 target path candidates also have parallel complex-EMF mismatch;
this is separately diagnosed and does not reject their topology.
The representative q=4,Q=2,pp=D=3,L=4,m=3 construction succeeds for both
TSP and TLP. A q=4,Q=2,pp=6,D=3,L=4,m=3 TSP source sweep fails its
top-bottom return pitch, while Q=3 source-valid cases lack a legal complete
pairing. These are method boundaries. No additional proper-Q source or
odd-D target support is promoted from this research: symbolic derivation,
shifted/transposed paths and public-entry integration still require work.
Replayable evidence is
`proper_q_p2_completion_probe.py` / `proper_q_p2_completion_result.json`
and `proper_q_odd_d_target_probe.py` / `proper_q_odd_d_target_result.json`
in the same preview directory.

### TSP q-only adjacent P2 pairing formula (2026-09-29)

For target `(Q,1,1)`, the source and target branch counts per phase are `2Q`
and `Q`, because `Naa_source=Q*1*2=2Q` and `Naa_target=Q*1*1=Q`. Group
the source branches by phase and join adjacent source paths in their generated
order. When `Q=q_local`, use the public `(Q,1,2)` source. For proper Q, the
raw TSP source is oriented N-to-S and completed by `q_local/Q` consecutive
q-lane sweeps; every completed source and joined target is checked by the
public layout path.

The return seam uses `tau=m_local*q_local`,
`g=gcd(L_local/2,pp)`, and
`r=min(2g-1,2pp-2g+1)`. Its signed slot pitch has magnitude `r*tau±1`.
The registered one-region domain requires `r=1`, equivalently
`g in {1,pp}`. It also requires integer `q`, even `Q>1` with `Q|q`, `pp>1`,
and even `L_local>=4`. Native phase counts use the V7.6 supported phase
domain. For an `m=3k` phase-set array, the global layer count must divide
equally among the `k` sets, and each set independently satisfies the local
q, layer, and gcd conditions. The selected route remains limited to neutral
Regular settings, zero shifts, insert-side inlet, and ALWP+CLWP.

Eight public samples passed generated coverage, phase/sign, N-to-S, phasor,
TSP edge and ordered-identity checks: native m=3 full-Q `(q,Q,pp,L)=(2,2,2,4)`;
native m=3 proper-Q `(4,2,3,4)` and `(6,2,3,4)` (two and three q-lane
sweeps); native m=5 `(2,2,2,4)`; native m=7 `(2,2,2,6)`; and phase-set arrays
at m=6/9/12 with local layers 4. All five native samples are `Validated`. The
three array layouts pass each local identity and mapped aggregate validation,
and remain `retained-not-strong` for EMF-only asymmetry. The negative
samples preserve the interior-gcd and odd-Q outcomes, `pp=1`, `L_local=2`,
and an m=12 array with `L_local=3`. In the fixed six-geometry TSP `q_only`
cell, two requests are now supported, six remain `unsupported-yet`, and the
pre-existing rejected request remains rejected. This finite cell does not
close the broader q, pole-pair, layer, or phase domain.

### TLP full-Q q-only adjacent P2 pairing (2026-09-29)

For target `(Q,1,1)`, use the public full-Q parent `(Q,1,2)`, group its
`2Q` branches by phase without changing their generated order, and apply the
shared divider `join` as `(1,2)`, `(3,4)`, and so on. The target has Q branches
per phase, each containing `2*q*pp*L/Q` conductors; full-Q `Q=q` reduces this
to `2*pp*L`. A source branch contains `pp*L` conductors. The formula binding
derives the source P2 factor from the target tuple and stores no sampled slot
coordinates.

The registered domain is integer even `q=Q>=2`, `pp>=2`, even `L>=2`, and one
native phase set (`three_phase_set_count(m)=1`). `pp>=2` comes from the public
source's `(Q,1,2)` P2 factor and TLP's shared `pp-divider * P2-divider <= pp`
constraint. Q even is required because the source has two Q-branch outer-layer
cohorts; adjacent pairs then stay within a cohort. The generated source check
requires each cohort to cover all q lanes once, and each joined pair to contain
adjacent lanes. Two-layer `L=2` is admitted as the tested degenerate case; it
does not require a separate constructor.

Let `tau=m*q`. The joined N-to-S source halves meet at a top-bottom return.
After orienting the seam in the TLP layer-traversal direction, its signed pitch
must be `tau-1` or `tau+1`, and the actual seam must cross at most one pole
region. Public source and target checks also cover occupancy, equal branch
counts, phase/sign, q-lane coordinates, ordered TLP identity, weld direction,
and electrical retention. Neutral Regular settings, zero shifts, and the
insert-side inlet are required. Phase-set arrays and nonneutral configurations
are outside this route.

On the unchanged six-geometry q-only cell, six of the original eight
`unsupported-yet` requests are now supported; two proper-Q cases remain
`unsupported-yet`, and the existing rejected odd-Q request remains rejected.
Only this matrix cell changes. Across the TLP matrix, supported preflights move
from 24 to 30, `unsupported-yet` from 27 to 21, and rejected stays at 35. The
six matrix samples all pass public generation and ordered identity: four report
`Validated`; the q=4 and q=6 layouts are retained with
`parallel_emf_mismatch` and remain `retained-not-strong`. Additional public
samples cover q=8, odd `pp`, an even-layer `L=2` case at q=4, and a TLP
`gcd(L/2,pp)` interior that is outside the separate TSP formula. The replayable
TLP probe result (local research excluded)
records source hashes, route decisions, pair lineage, bridge pitches, and
negative boundaries.

At `q=Q=pp=2`, `L=4`, `m=3`, the q-only route and existing TLP `(1,2,1)` PP-only
route have identical per-branch conductor sets but different ordered paths.
The selected divider tuple remains represented by its public `(Q,1,2)` source
and adjacent-pair lineage; unordered conductor sets alone do not distinguish
that geometric alias.

### TSP/TLP q-only adjacent P2 pairing exploratory boundary evidence (2026-09-24)

For `(Q,1,1)` with `Q>1` dividing integer q, take the same Pattern's
complete `(Q,1,2)` source, group its `2Q` N-to-S branches by phase, and
join each adjacent pair in series. This reduces the branch count to Q per
phase. The new seam must be a legal insertion-side top-bottom return; the
complete target is rechecked for unique coverage, equal counts, phase and
signed direction, phasor coordinates, Pattern identity, all edge pitches,
N-to-S terminals of this method, and TLP weld direction. A public retained
source is used when available. Proper-Q source completion remains
exploratory and is marked separately.

The historical replayable finite scan `q_only_pair_bridge_probe.py`/
`q_only_pair_bridge_result.json` covers TSP/TLP q=2..6, every `Q>1` dividing
q, pp=1..10, even L=4..12, and m=3/5/7: 2,400 cases. It finds 1,140
complete-path candidates (TSP 465, TLP 675), 894 adjacent-pairing
counterexamples and 366 cases without this source. Among 2,034 source-valid
cases, the bounded method predictor has no mismatch: Q is even, and TSP
also needs `gcd(L/2,pp) in {1,pp}`. Odd-Q pairings can join two conductors
on the same boundary layer instead of a top-bottom return; TSP interior
gcd cases can violate the return pitch. These are failures of adjacent
pairing, not proof that a Q-only route is physically impossible. The scan was
a path-method boundary study, not production route admission.
The TSP production formula and its stricter public sample domain are recorded
above. TLP's registered production boundary is limited to the full-Q even-Q
domain described above; the broader historical scan remains path-method
evidence, not admission for proper-Q, phase-array, or other unregistered cases.

The saved-seam audit `q_only_bridge_pitch_audit.py`/
`q_only_bridge_pitch_result.json` sharpens the boundary. Let `tau=mq` and
`g=gcd(L/2,pp)`. The source order has two boundary-layer inlet cohorts of
Q branches per phase. With even Q, adjacent pairs stay within a cohort:
all 1,266 source-valid even-Q cases have top-bottom seams. With odd Q, one
pair crosses cohorts per phase: all 768 source-valid odd-Q cases have
exactly m same-layer seams. In the 591 even-Q TSP cases, each seam has
absolute pitch `k*tau±1`, where `k=min(2g-1,2pp-2g+1)`; k=1 exactly when
g is 1 or pp. All 675 even-Q TLP cases have absolute seam pitch `tau±1`.
The audit measures complete saved paths, while the endpoint formula still
needs a symbolic proof before it can authorize arbitrary geometry.

The separate `q_only_registered_pair_audit.py`/
`q_only_registered_pair_audit_result.json` regenerates every available
registered full-Q parent and independently checks all 684 adjacent-pair
paths (279 TSP, 405 TLP), including nonzero fundamental in each branch.
The paths pass; 456 retain parallel EMF mismatch. This is bounded **path
method evidence**, not Q-only support. In all 684 cases, every joined
branch mixes two parent q lanes. For example, TLP `q=Q=pp=2`,
`L=4`, `m=3` joins parent branches 1 and 2, whose two halves occupy q
lanes 0 and 1. Branch count and Pattern identity alone do not establish
that the Q factor has its intended lane/sector lineage. A separate lineage
check now verifies in all 684 cases that each adjacent pair shares one
signed-layer-parity cohort; its two parents occupy adjacent q lanes and
each covers every pp sector once; within each cohort the pairs partition
all q lanes. This is a coherent TSP/TLP connection hypothesis, but it is
not a distinguishing Q-factor certificate. In 75 comparable TLP
`q=Q=2` cases, the candidate and the public `(1,2,1)` PP-only route have
identical per-branch conductor sets. Of their 750 corresponding branches,
405 have identical ordered paths; the other 345 have different physical
edges and terminals. Factor attribution remains pending even though the
paths themselves pass independent validation.

The alternative `q_only_same_lane_pair_probe.py`/
`q_only_same_lane_pair_result.json` pairs the two whole P2 parent branches
in each phase and q lane, trying both orders. In all 1,350 source-valid
full-Q cases across TSP/TLP, both orders make a same-boundary-layer seam,
which is neither a legal top-bottom return nor an adjacent-layer insertion
edge; 150 other cases have no
usable parent under this method. The smallest sampled counterexample is
TSP `q=Q=pp=2`, `L=4`, `m=3`: both same-lane seam orders have layer
change zero. Every complete L-conductor pass in each source-valid pair
has fixed complementary layer orientation: one parent's passes go from
bottom to top, the other's from top to bottom. Any cross-parent edge
between intact oriented passes therefore remains on one boundary layer.
The stronger signed-layer-parity audit gives the same obstruction without
assuming intact passes. Let `sigma` be the actual signed phase direction of
a conductor and `c = sigma*(-1)^layer`. Every one of the 1,350 paired
same-lane parent cases has constant `c` within a parent and opposite `c`
between its two parents. A valid consecutive edge flips `sigma`; TSP/TLP
edges at even `L` change layer by `1` or `L-1`, both odd, so they preserve
`c`. No edge can cross those fixed parent conductor sets under this
neutral phase map, even after splitting or reversing their passes. This
does not exclude a different conductor partition or a nonneutral source.
The `q_only_pass_interleave_probe.py`/
`q_only_pass_interleave_result.json` enumerates all order-preserving pass
merges for 72 representative q=2/3/4, pp=2/3/4, L=4/6, m=3/5 cases;
none has a locally legal complete branch. This refutes whole-pass
reordering with those orientations, not all Q-only constructions. A
revised connector or pass orientation and a parameter-derived Q-factor
invariant remain pending. The same symbolic odd-m construction is sampled at
`m=3/5/7`; no separate three-phase route is introduced.

### Pending TSP/TLP pp-divider plus P2 source cut (2026-09-24)

The `(1,D,2)` target has `2D` branches per phase. One candidate method
generates the same Pattern's retained `(1,1,2)` source and cuts each complete
branch into `D` equal, even-length contiguous segments. Each segment has
`B=q*pp/D` complete L-layer passes because `D|pp`. The cut preserves the
source's ordinary edges and removes only edges at segment boundaries. A
TSP/CLWP or TLP/CLLP top-bottom return remains *inside* every segment only
when `B>=2`; N-to-S parity follows from even segment length but is checked
again from the destination phase map. This is a method condition, not a
general impossibility statement for B=1.

A replayable neutral-setting scan covers integer q=1..6, pp=2..10, every
`D>1` dividing pp, even L=2..12 and m=3/5/7 for both Patterns: 3,672
cases. The registered P2 source is unavailable or fails retention in 2,652.
Of 1,020 source-valid cases, 750 cuts pass full conductor coverage, phase,
signed direction, Pattern identity, N-to-S endpoints, phasor coordinates,
all edges and TLP weld direction. The other 270 have exactly one pass per
segment and lack the required top-bottom return. Source-valid results in
this scan occur only at integer `q∈{1,2}` and `L>=4`; `q>2` and `L=2` remain source-method
boundaries. Of the 750 path candidates, 510 show parallel complex-EMF
mismatch and are retained as `not strong symmetry layout`; 240 have no
EMF asymmetry detected by this check. Neither category is manufacturing
certification or a production `(1,D,2)` route.

The probe records each phase's actual inlet pole-pair sectors, because
occupancy, Pin identity and N-to-S endpoints alone do not establish the
intended pp-divider sector grouping. A parameter-derived sector contract,
shifted and transposed constructions, and a valid q>2 source remain to be
established before route admission. Evidence is
`workbench_preview/even_d_source_partition_20260923/pp_p2_source_split_probe.py`
and `pp_p2_source_split_result.json`.

The proposed shortcut "exactly D distinct inlet sectors per phase" is
refuted by path-valid cuts. For example, TLP q=1, pp=6, D=3, L=4, m=3 can
start once in each of all six pole-pair sectors. Neither inlet count nor
confinement to D physical sectors is a valid admission rule.

For TLP, a stronger lineage candidate cuts the *public approved*
`(1,2,1)` PP parent instead of the raw `(1,1,2)` P2 source. Its two parent
cohorts are related by the registered reflection and pole translation. The
same `B=q*pp/D` complete-pass condition applies to each of the `2D` child
branches. In an integer `q∈{1,2}`, even pp=2..10, L=4..12, m=3/5/7 neutral scan, 285 of
360 cuts pass all-branch validation; the 75 failures all have B=1 and lack
the internal CLLP return. Every passing candidate has half-turn-paired
inlet-sector multiplicities `c[s]=c[(s+pp/2) mod pp]`. This describes its
approved-parent lineage, but the parent's PP=2 meaning does not prove a
target PP=D division when D differs from 2. The lineage hypothesis and
counterexamples are in `tlp_pp_parent_p2_cut_probe.py` and
`tlp_pp_parent_p2_cut_result.json`.

A 360-case configuration sample of registered TSP/TLP P2 sources with integer
`q∈{1,2}` at
pp=4/6, D=2/3, L=4/6 and m=3/5/7 finds 72/72 neutral and 72/72 alternating
phase-shift path candidates. The alternating shifts change every sampled
source path. Uniform, Times and Interval payloads yield 36/72, 72/72 and
36/72 path candidates, respectively, but every passing TP case has the same
physical source path as Regular. All 27 physically changed Uniform sources
fail the equal cut; 45 other TP cases lack a usable source. Thus this sample
does not establish a physically active transposition route. See
`pp_p2_configuration_probe.py` and
`pp_p2_configuration_result.json`.

For q>2, an additional exploratory source takes one complete `pp*L` pole
cycle from the same-Pattern raw `(1,1,2)` path, orients it N-to-S, and sweeps
the `q` adjacent slot lanes. It is parameterized by the same odd `m` in the
phase map and pole pitch; there are no phase-count branches. Of 1,200 source
cases at q=3..6, pp=1..10, L=4..12 and m=3/5/7, 912 pass full-path checks and
288 refute this completion method. The finite predictor needs pp>1; TSP
additionally needs `gcd(L/2,pp) in {1,pp}`. Each sampled `m` has 304 passing
sources. This source is exploratory, even when its path is retained. The
representative q=3, pp=D=2, L=4 construction also passes at m=9/11 for both
Patterns; this spot check does not expand the finite census.

Composing the source-valid q>2 branches with equal D cuts covers 2,040
target cases. It yields 1,584 complete-path `(1,D,2)` candidates and 456
source-method failures, with 528 candidates at each of m=3/5/7. All 1,584
candidates have parallel EMF mismatch and are retained as `not strong
symmetry layout`; none is strong-symmetry or manufacturing certification.
The PP-sector inlet contract, shifted and transposed cases, and production
route admission remain pending. The replayable files are
`workbench_preview/even_d_source_partition_20260923/unit_q_p2_lane_source_probe.py`,
`unit_q_p2_lane_source_result.json`, `unit_q_pp_p2_target_probe.py` and
`unit_q_pp_p2_target_result.json`.

### Pending TSP/TLP PP-only direct P2 pair-and-cut (2026-09-24)

For `(1,D,1)`, `D>1` dividing pp, a direct method joins the two complete
same-phase `(1,1,2)` source branches and cuts the resulting series into D
equal children. Each child contains `B=2*q*pp/D` full L-layer passes; this
is at least two for legal integer q and D. The method uses one symbolic odd
phase parameter `m>=3`. Values m=3/5/7 are validation samples, never
separate three-phase and other-odd-phase constructions.

The `pp_only_p2_pair_cut_probe.py`/
`pp_only_p2_pair_cut_result.json` neutral scan covers TSP/TLP q=1..6,
pp=2..10, every D>1 dividing pp, L=4..12 even and m=3/5/7: 3,060
cases. It finds 1,476 complete-path candidates, 1,128 direct-join method
counterexamples, and 456 source-method blocks. The three sampled m values
have identical state counts: 492/376/152 each. Every source-valid odd-D
case retains the cross-source join inside a target child. That join has a
same-layer insertion edge and all 1,128 fail the TSP/TLP insertion-side
transition rule. Every source-valid even-D case removes the join at a cut
boundary; all 1,476 passing children exactly equal separate cuts of the
two P2 parents. This path alias cannot establish the PP-divider sector
meaning. These findings limit this direct construction only. They do not
exclude a transformed-cohort or other PP-only route, and they do not alter
the separately approved reflected TLP D=2 route. No new production route
is enabled.

A follow-up intact-parent reversal probe (local research excluded)
tests both orders and every whole-path reversal at the smallest odd-D witness
`q=1, pp=D=3, L=4` for TSP and TLP, sampling the same symbolic rule at
`m=3/5/7/9`. All 64 target variants fail the complete current checks: per
Pattern and sampled `m`, four have no radial top-bottom return at the join,
and four fail phase/sign sequence; all eight also fail ordered identity.
Measured pitches are recorded only as geometry. The probe checks occupancy,
electrical retention, ordered identity, radial edges and TLP weld travel for
every variant, with a public P2 source as a positive control. These are
bounds on intact-parent transformations, not a rejection of odd-D PP-only.
The neighboring JSON records every seam and source hash.

The follow-up coupled reflection probe (local research excluded)
tested that hypothesis at the same witness. For one complete parent with inlet
slot `a`, it maps `(slot,layer)` to
`(2*a-slot+k*tau mod slots, L-1-layer)`, where `k=0..5`; either parent may be
mapped, each may be reversed, and both join orders are tested. Of 96 variants
per Pattern and sampled `m=3/5/7/9`, none passes the complete current checks.
Failure flags overlap: 48 have duplicate or missing occupancy, 48 fail
phase/sign, 48 lack the required radial return, and 60 fail ordered identity.
One reflected example has a correct radial return and ordered identity but
duplicates conductors; its pitch does not decide Pattern identity. This only
excludes the fixed complete-parent reflection family at the witness.

A third intact-pass pairing probe (local research excluded)
splits each P2 parent into three complete `L=4` passes, then allows either
order and whole-pass reversal when pairing six passes into three target
branches. At each sampled odd `m=3/5/7/9`, both Patterns have 120 options per
phase: 60 fail phase/sign, 36 fail ordered identity and 24 pass the local
pair checks. The passing graph is two disjoint triangles, one within each P2
parent. Its maximum matching has two pairs, so no three-pair exact cover
exists and no full target can be certified by this method. The next distinct
hypothesis changes pass composition or source partition. The
case ledger (local research excluded)
records all phases, checks and source hashes.

A stronger fixed-source cohort parity probe (local research excluded)
checks the actual public P2 paths at `q=1`, `pp=D=3/5`, `L=4/6` and one odd
phase parameter sampled at `m=3/5/7/9`: all 32 cases have two opposite,
constant `c = phase_sign * (-1)^layer` conductor cohorts in every phase.
Their source lengths are `D*L`; an odd-D PP-only target needs `D` branches
of `2*L` conductors per phase. A legal adjacent-layer or top-bottom TSP/TLP
edge changes layer parity and alternates phase sign, preserving `c`.
Consequently, splitting or reordering these fixed source conductors cannot
connect the two cohorts, and neither odd-`D` cohort can be partitioned into
whole target branches because `D*L` is not divisible by `2*L`. The
case ledger (local research excluded)
records all parent branches, phases and source hashes. This is a conditional
method obstruction under the neutral source partition, not a route rejection;
a changed conductor partition or phase map remains pending.

### Pending TSP/TLP Q+PP+P2 complete-source cut (2026-09-24)

This section studies a `(Q,1,2)` source. The separately admitted TLP
`(1,D,2) -> (2,D,2)` parent-slice formula above has different PP lineage;
its admission does not certify these older source-cut candidates.

For integer `Q>1` dividing q and `D>1` dividing pp, one method takes a
retained same-Pattern `(Q,1,2)` source and cuts each complete branch into D
equal contiguous `(Q,D,2)` children. Each child has
`B=(q/Q)*(pp/D)` complete L-layer passes. The cut retains source internal
edges but removes D−1 former junctions per parent. Every child still needs
an internal CLWP/CLLP top-bottom return, so B>=2 is necessary for this
method. Destination N-to-S terminals, phase/sign, coverage, phasor
coordinates, every connection edge, Pattern identity and TLP weld direction
are independently checked. A proper-Q source completed by q-lane sweeps is
marked exploratory; full-Q source paths come from the public generator.

The `q_pp_p2_source_cut_probe.py`/
`q_pp_p2_source_cut_result.json` finite scan covers TSP/TLP q=2..6, every
Q>1 dividing q, pp=2..10, every D>1 dividing pp, L=4..12 even and
m=3/5/7: 4,080 cases. It finds 2,388 path candidates (TSP 1,023, TLP
1,365), 1,350 B=1 cut failures and 342 proper-Q source-method failures;
the B predictor has no sampled mismatch. All 2,388 candidates have
parallel EMF mismatch and are retained as `not strong symmetry layout`.
This is no production support claim. In particular, the cut has not proved
that the target D factor represents a pp-divider sector construction.

The separate `q_pp_p2_alias_audit.py`/
`q_pp_p2_alias_result.json` shows why that distinction matters. At proper
Q with `D=q/Q`, each cut isolates one whole q-lane sweep. Among 390
applicable cases, 303 are path candidates; in all 303, their complete
ordered physical branch family is identical to the public `(q,1,2)`
full-Q P2 route. The other 87 do not pass this equal-cut method. Exact
branch equality is a counterexample to interpreting the candidate's
factor label as proof of a distinct PP division. It does not reject the
requested `(Q,D,2)` route; a divider-specific inlet-sector/lineage
contract remains pending.

## ZLP P2-only mirror route (2026-09-23)

The 2026-09-23 designer status review explicitly rejects every ZLP tuple with
Q-divider greater than 1 and the CP no-divider `(1,1,1)` tuple. The production
resolver, public generator, and Workbench catalog use the same exclusions and
reasons recorded in `PATTERN_REJECTION_REASONS.md`. Older ZLP Q-divider scans
below remain historical construction evidence, not current admission.

ZLP `(q-divider, pp-divider, P2)=(1,1,2)` is admitted through a distinct
phase-local mirror construction. Generate the same Pattern's `(1,1,1)` reference,
orient each phase N-to-S, use its first half for Branch 1, then mirror that half
in layer and unshifted slot coordinates for Branch 2. For zero-based phase
index `phi`, the review construction uses mirror axis
`K_phi=([m(L-2)+1]q-1+2q*phi) mod slots`. At m=3 this equals the earlier
`(3L-5)q-1+2q*phi` axis. Reapply the destination layer shift after
reflection. The source and selected route run the normal occupancy, equal
length, phase, electrical, ZLP edge, pin identity and P2 terminal checks.

The axis probe (local research excluded)
finds exact phase-local reflected complements in all 108 discriminating
neutral cases at q=1..3, pp=2/4/6, L=2/4/6 and m=3/5/7/9; the older
three-phase axis complements only 54 of them. The independent
public P2 audit (local research excluded)
checks 1,080 finite-domain cases at q=1..6, pp=1..10, even L=2..12 and
m=3/5/7. It verifies 1,008 complete public paths. The other 72 cases have
q>=3 and pp=1: an ordered insertion edge in the unchanged default source
keeps their public decision Candidate. That case-limited source failure is
not a rejection of the P2 mirror axis. A single simple pitch template is
insufficient for 648 of the verified layouts; actual signed endpoints,
connection sides, layer changes and ordered identity remain the checks.

The eight designer-approved q=2/3, 8/10-pole, 2/4/6-layer, Interval and
shifted examples are reproduced through `get_winding_layout`; the q=2,
8-pole, four-layer catalog row is `Validated`. Admission is factor-based, with
per-case construction failures retaining their exact reject reason. Odd layers
and fractional q are outside this route. Edge and pair-local zigzag checks use
the unshifted slot frame so layer shifts do not alter the underlying ZLP pin
identity. The bounded audit counts below predate this promotion.

## Half-integer q-and-pp transfer (2026-09-22)

UWP admits `(q,2,1)`, `Naa=2q`, for positive half-integer q with a nonempty
second inlet cohort (`floor(q)>0`), even pole-pair count, odd `m>=3` and
positive even layers. The source remains `(q,1,2)`. Reverse its S-inlet paths,
then translate those complete waves by integer multiples of the two-pole slot
period `2*m*q` into the second half circumference. Per-branch conductor sets,
N-to-S signs, adjacent-layer edges and signed wave pitches are checked again.
The q=1/2 source has no second cohort and would create an unchanged alias.

All ten Patterns are enumerated for this target. BWP, SSP, SLP, ZLP, TSP, TLP,
ZPP and CP remain `unsupported-yet`: they have no implemented transferable
half-integer q-and-P2 source. This is not a physical-impossibility finding or
a new rejection of their P2=1 target. LPP retains its explicit factor exclusion.
SSP mixed P2=2 formulas remain rejected. The distinct `(1,1,2)` construction
is admitted for its guarded even-q domain; case-specific Auto determines status.

`half_integer_q_pp_route_decision` supplies the resolver, generator, UI and
Workbench decision. Integer admission still uses its existing classifier.
EMF asymmetry does not reject this route: strong-count impossibility retains
`not strong symmetry layout`; unresolved configuration remains `auto configure
pending`. This is candidate construction evidence, not engineering approval.

The workbench now applies the common strong-count proof, guarded Auto
configuration search and solved/pending/hard-no classification to all ten
Patterns. See [AUTO_CONFIGURE_RULES.md](AUTO_CONFIGURE_RULES.md). This changes
configuration resolution and catalog status, not Pattern admission rules.

Auto Configure now evaluates unique valid implementations and chooses the
minimum pin-type count by default. The main Transposition tab also offers
minimum changed connection events and minimum normalized average pin length.
See the metric definitions and extension API in `AUTO_CONFIGURE_RULES.md`.
All completed alternatives still satisfy the same strong/electrical checks;
objective ranking never changes admission or promotes a retained pending case.

As of 2026-09-22, integer BWP/UWP common-TP recipes derive their offset and
connection-position domains from geometry instead of fixed recipe caps.
Every Default/Validated formula also runs the resolver on Open/Reload; loaded
paths, reference transitions and exported effective parameters agree with its
completed result. Already strong baselines count as completed with no change.
The historical counts below predate the all-Pattern refresh and are retained for
traceability. The current timestamped JSON/CSV evidence is generated by
`audit_auto_configure_formulas.py` under `workbench_preview/auto_configure_rules/`.

## Current bounded ten-Pattern audit (2026-09-22)

The refreshed q=1..6 integer plus admitted half-integer 3/2..11/2,
pp=1..6, layers=2/4/6, three-phase, zero-shift matrix contains 13,860 rows.

| Pattern | Default | Validated | Hard no | Pending | Candidate | Rejected | Unsupported |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BWP | 318 | 63 | 165 | 42 | 0 | 798 | 0 |
| UWP | 216 | 141 | 222 | 51 | 0 | 756 | 0 |
| SSP | 171 | 63 | 138 | 135 | 0 | 840 | 39 |
| SLP | 156 | 63 | 192 | 136 | 62 | 168 | 609 |
| ZLP | 349 | 41 | 165 | 61 | 5 | 324 | 441 |
| CP | 49 | 13 | 127 | 28 | 36 | 596 | 537 |
| ZPP | 120 | 78 | 180 | 0 | 0 | 480 | 528 |
| TSP | 38 | 12 | 52 | 0 | 69 | 315 | 900 |
| TLP | 38 | 24 | 52 | 0 | 69 | 339 | 864 |
| LPP | 240 | 0 | 0 | 0 | 12 | 1134 | 0 |

Evidence files are
`workbench_preview/auto_configure_rules/formula_audit_all_patterns_20260922T074122Z.json`
and the matching CSV. These are bounded software results, not formula
whitelists or manufacturing certification.

## Current BWP/UWP completion snapshot (2026-09-21)

Fresh catalog enumeration for integer q=2..6, pole pairs=2..10, three phases,
and four layers contains no `unsupported-yet` entries for either Pattern.
All enumerated divider tuples were included, not only default Naa values.

| Pattern | Default | Validated | Proven count hard no | Auto configure pending | Rejected | Unsupported-yet |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BWP | 141 | 42 | 102 | 53 | 338 | 0 |
| UWP | 90 | 54 | 71 | 39 | 422 | 0 |

These are catalog route counts, not independent physical certifications. The
hard-no column corresponds to `not strong symmetry layout`. Pending means the
bounded automatic search did not establish strong symmetry, not impossibility.
Rejection reasons remain in the linked registry below. This snapshot does not
establish support for every layer count, fractional q, or transposition setting.

### Reusable construction and admission lessons

- Preserve `Naa = Q * D * P2` and Q dividing integer q; distinguish these
  enumeration conditions from a constructor's actual geometric requirements.
- BWP q/pp partitioning reuses the existing lane/sector construction. Preserve
  its generated-path validators and explicit P2 exclusion; do not infer new
  physical support from arithmetic factorization alone.
- UWP `pp_only` with D=2 uses q complete waves in each layer pair. Its second
  branch starts half a circumference away at the bottom layer and travels in
  the opposite circumferential direction. Even pole pairs and positive even
  layers suffice for this deployment; the old minimum of four pole pairs is
  unnecessary.
- UWP `(Q,2,1)` for 1<Q<=q reuses the `(Q,1,2)` q/P2 reference construction,
  with second-cohort bottom-layer deployment and reversed pole travel. It
  partitions q lanes, so Q need not divide the pole count. Require Q dividing
  q, D=2 dividing pole pairs, Naa=2Q, odd `m>=3` and positive even layers;
  do not retain the old `poles % Naa` or even-poles-per-sector restrictions.
- Proper-Q UWP `q_only` joins matching N-to-S q/P2 reference branches at
  same-layer outlet/inlet junctions, reducing 2Q branches to Q. Keep this
  explicit junction exception scoped to that construction. Full-Q q-only
  remains rejected as a duplicate BWP route.
- Reuse the shared transposition/phase-shift transformation and validate its
  output, including signed edge direction and N inlets. Do not widen pitch
  tolerances simply to admit an otherwise invalid result.
- Exact occupancy, equal branch sizes, phase membership and legal edges remain
  independent checks. EMF asymmetry does not define construction boundaries.
  Use the signed-category divisibility proof for hard no; finite-search failure
  belongs to auto-configure pending.

The last 15 missing UWP tuples were closed by changing only two admission
predicates, without new path algorithms or parameter-specific exceptions.
Focused checks covered those tuples at 2/4/6 layers, both zero and alternating
layer shifts (90 generated layouts), plus wave-order, reference-route and
exclusion checks. Arbitrary configurations still pass through runtime guards.

UWP full-Q `q_only`, `(q,1,1)` with q>1, is explicitly rejected because it
duplicates BWP full-Q q-only. Use BWP for that construction. This does not affect
proper-Q UWP q-only (`1<Q<q`) or the no-divider `(1,1,1)` case.

Current UWP rule: `pp-divider * P2` must be 1 or 2 because the factors share
one splitting allowance. All pp-divider > 2 tuples are rejected, in addition
to pp-divider=2/P2=2. This supersedes older D>2 candidate/support descriptions.

BWP/UWP strong-symmetry grouping and automatic configuration now follow
[AUTO_CONFIGURE_RULES.md](AUTO_CONFIGURE_RULES.md): only proven count-obstruction
cases remain in the `not strong symmetry layout` catalog group. Unresolved
strong-symmetry configurations retain their generated Workbench route status,
with the pending Auto Configure assessment in the reason. Physical EMF
diagnostics remain separate and are not relabelled as electrically balanced.

Current rejection statuses and reasons are maintained in
[PATTERN_REJECTION_REASONS.md](PATTERN_REJECTION_REASONS.md).
Use `rejected` for both explicit exclusions and case-generation failures;
`unsupported-yet` remains distinct. This supersedes historical status wording below.

Date: 2026-09-21. Scope: Version 7.5 production connection generation and the
Pattern Rule Workbench. This document records implemented software support; an
unsupported tuple is not a proof of physical impossibility.

Pattern topology and manuscript-derived constraints are maintained separately in
[Pattern definitions and constraints](PATTERN_DEFINITIONS_AND_CONSTRAINTS.md).
The 2026-09-21 TLP repair corrects signed lap pole tracking within existing
admission rules; four layers are not intrinsically unsupported. The workbench
derives its updated case status from the generator. See the reference's bounded
regression evidence rather than treating this repair as general route expansion.

## 1. Common factor identity

Every divider tuple is written as `(q-divider, pp-divider, P2)` and must satisfy:

```text
pp = poles / 2
pp-divisors = {d in positive integers | pp mod d = 0}
pp-divider in pp-divisors
Naa = q-divider * pp-divider * P2
```

- `Naa` is the number of parallel branches per phase.
- `q-divider` is the selected factor contributed by `q`.
- `pp` is the pole-pair count, not a divider.
- `pp-divider` is any positive integer factor of `pp`; the set of all allowed
  values is `pp-divisors`.
- `P2` is `1` or `2`; `P2=2` is the extra split between the two pole regions.
- For positive integer `q`, `q-divider` is an integer divisor of `q`.
- For positive half-integer `q`, the currently implemented P2 candidate uses
  `q-divider=q`; therefore `2*q` and `Naa` remain integers.

Factor arithmetic only makes a tuple enumerable. A Pattern is usable only when
its own admission function accepts the tuple and the generated connection passes
coverage, branch length, phase/direction, Pattern edge rules, and the applicable
complex-EMF check.

## 2. Divider-type formulas

The type name is determined by which factors are greater than one. A factor set
to one is inactive.

| Divider type | Tuple condition | Formula |
| --- | --- | --- |
| No divider | `(1,1,1)` | `Naa = 1` |
| q-divider only | `(q-divider,1,1)`, `q-divider>1` | `Naa = q-divider` |
| pp-divider only | `(1,pp-divider,1)`, `pp-divider>1` | `Naa = pp-divider` |
| P2 only | `(1,1,2)` | `Naa = 2` |
| Mixed q + pp-divider | `(q-divider,pp-divider,1)`, both dividers greater than one | `Naa = q-divider * pp-divider` |
| Mixed q + P2 | `(q-divider,1,2)`, `q-divider>1` | `Naa = 2 * q-divider` |
| Mixed pp-divider + P2 | `(1,pp-divider,2)`, `pp-divider>1` | `Naa = 2 * pp-divider` |
| Mixed q + pp-divider + P2 | `(q-divider,pp-divider,2)`, both dividers greater than one | `Naa = 2 * q-divider * pp-divider` |

These names describe factor composition only. They do not claim that every
Pattern implements the corresponding connection.

## 3. P2 domain formulas

| Family | Formula | Arithmetic conditions | Current general status |
| --- | --- | --- | --- |
| Unit q-divider | `Naa = 2 * 1 * pp-divider` | Integer `q`; `pp-divider` is any factor of `pp` | Implemented only by Pattern-specific routes that explicitly admit P2, such as CP. BWP excludes `P2=2`. |
| Proper integer q-divider | `Naa = 2 * q-divider * pp-divider` | Integer `q`; `1 < q-divider < q`; `q-divider` divides `q`; `pp-divider` divides `pp` | General factor-driven support exists for UWP, subject to its balance plan and geometry guards. |
| Full integer q-divider | `Naa = 2 * q * pp-divider` | Positive integer `q`; `pp-divider` divides `pp` | No cross-Pattern general route. Some default layouts may realize individual tuples; they remain governed by each Pattern's default classifier and runtime validation. |
| Half-integer q-divider | `Naa = 2 * q * pp-divider` | Positive half-integer `q`; `q-divider=q`; `pp-divider` divides `pp` | UWP candidate route implemented for odd `m>=3` and positive even layers. Other Patterns are unsupported for this family. |

For every admitted `P2=2` route, terminal orientation is applied after connection
generation using the shifted phase map: phase inlet must be in an N-pole region
and neutral outlet in an S-pole region. Reversed paths also receive recomputed
start-conductor and conductor-index order. Pole regions therefore follow `q`,
phase count, pole count, and layer phase shift.

## 4. Current Pattern support

### 2026-09-21 Existing-construction extensions

Non-wave Pattern admission now runs through `resolve_pattern_route()`. The
resolver carries a stable rule id, `enabled`/`disabled`/`candidate` status,
effective configuration, required terminal side, and expected body pin profile.
Its phase predicate is symbolic: odd `m >= 3`, with verification at m=3/5/7;
ordinary pitch is `tau=m*q`, and Z paired pitch is `(m-1)q+1`. The compatibility
wrapper `selected_integer_divider_route()` retains the old constructor names.

Before the 2026-09-23 explicit exclusions, q=2..6, pp=2..10, and even layers
2..20 produced the same pre-generation census for each m=3/5/7: SSP 420/420,
SLP 420/420, ZPP 780/780, ZLP 1,080/1,430, CP 48/420, and LPP PP-only defaults
1,300/1,300. These ZLP/CP/LPP counts must not be used as current admission totals.
Other arithmetic tuples were Disabled by the ZLP branch-length identity or the
cached CP construction/coverage/edge oracle. ZPP and ZLP EMF-only mismatch
is retained as `not strong symmetry layout`. Unexpected body pin types or a
changed pass/return identity are Candidate-only. The two-layer case can be
identity-underdetermined and is labeled `degenerate-two-layer` without inventing
a new body pin type.

UWP proper-Q `q_only`, `(Q,1,1)` with `1<Q<q` and `Q|q`, now uses a series
construction. Generate `(Q,1,2)` at twice Naa, including its N-to-S terminal
orientation. Within each phase concatenate branch i and branch Q+i, preserving
both source paths and connecting the first outlet to the second inlet on the
same layer with an explicit series weld. The result has Q equal-length branches
per phase and records each bridge separately. Source-wave edge rules remain
unchanged; opposite travel in the two source segments is allowed for this
derived series variant. Even poles/layers and odd phase count >=3 are required;
the current entry uses regular unshifted reference configuration. Full-Q q-only
is outside this extension. EMF asymmetry does not reject the retained layout.

- BWP selected `(Q,D,1)` admits proper Q (`1<Q<q`, `Q|q`) and `D>1`
  dividing pole pairs, with odd `m>=3` and even layers. It reuses the existing
  bidirectional constructor and same-layer returns. Selected configurations
  pass generated edge and pin checks; classifier-default tuples at every odd
  phase count retain their separate configurable path.
- UWP `(Q,1,2)` now includes full Q (`Q=q>1`), using one full-circle wave per
  layer pair and the existing q/P2 construction and N-to-S post-processing.
- UWP `(q,2,1)` now reuses the q/P2 reference deployment, with odd `m>=3`,
  even layers and even pole-pair count. The second q-branch cohort starts at the
  half-turn bottom N region and travels backward. Configuration handling is
  shared with the existing proper-Q PP=2 route.
- These additions preserve explicit pp/P2 exclusions and asymmetric-layout
  retention. They do not implement UWP full-Q q-only or a general D>2 deployment.

The dated extensions above supersede narrower limits in older table entries.

The table summarizes general production admission, not every default tuple.
`Runtime` means that a tuple satisfying the formula can still be rejected for a
specific pole/layer/shift/inlet geometry.

| Pattern | pp-divider-only, `P2=1` | P2 formula support | Integer mixed q-divider support | Positive half-integer support | Important limits |
| --- | --- | --- | --- | --- | --- |
| BWP | `(1,pp-divider,1)` implemented | All tuples with `P2=2` are rejected | Proper-Q `(Q,D,1)` registered for `1<Q<q`, `Q|q`, `D>1`, `D|pp`, odd `m>=3` and even layers; classifier defaults retain their separate path at every phase count | Existing implicit `(1,Naa,1)` sector array when `Naa` divides pole pairs; separate global-wave route and identity. Four fixed six-phase phase-set samples for `q=h/2`, `h∈{1,3,5,7}`, use local `bwp_default`, as summarized below | Selected proper-Q mixed configurations are sampled against coverage, electrical retention, shifted wave edges and body pin identity. Radial shift and manual inlet adjustment remain unsupported; classifier defaults have their own configurable path. EMF asymmetry alone is retained, not rejected. |
| UWP | `(1,pp-divider,1)` implemented for admitted geometries | Proper integer q-divider supports `(q-divider,pp-divider,1/2)`; short `pp=1, L=2, Q=q, P2=2` uses a neutral weld-terminal ALWP public route | `(Q,2,1)` registered for `1<Q<=q`, `Q|q`, even `pp` and odd `m>=3`; other proper-Q plans keep their separate guards | Explicit `(q,1,2)` P2 parent and, for `q>1`, its `(q,2,1)` full-wave transfer; implicit `(1,Naa,1)` sector array remains separate. `(q,D,2)` with `D>1` is rejected by the `D*P2` split contract. | Positive even layers. Short P2 requires weld-side inlet; Q+PP=2 uses the configurable PP route's Regular shift and Uniform/Jump guards while Times, Interval and weld-side inlet are disabled there. Other integer routes and explicit Auto retain their own checks. Half-integer routes require odd `m>=3` and even layers; transfer requires a second cohort and even pole pairs. Public generation applies the exact one-pole-region gate. Identity failures remain Candidate for `allow_candidate` exploration. EMF mismatch alone does not reject a retained layout, which remains `not strong symmetry layout`. |
| SSP | `(1,pp-divider,1)` implemented | Distinct P2-only `(1,1,2)` via reflected q-lane cohort; mixed P2 excluded | Proper `(Q,D,1)` uses the registered PP-parent cut when `Q|q`, `D|pp`, `1<Q<q`, `D>1`, and its q-lane partition holds; existing defaults remain | No direct three-phase half-integer formula; finite phase-set samples only for `q=h/2`, `h∈{1,3,5,7}`, `m=6`, four poles, `L=8`, target `(h,2,1)` | P2-only requires even positive integer q/layers, pp>=2, odd m>=3 and unshifted insert-side inlet. Odd integer q is rejected for the registered equal-cohort construction, without claiming physical impossibility. Full coverage, phase, N-to-S terminals, uniform welds and spiral identity are checked. Screenshot q=2/pp=4/L=4 is Validated after Auto insertion-side transposition; other geometries retain individual strong/pending status. |
| SLP | `(1,pp-divider,1)` implemented by pole-pair block selection and exact `slots/pp-divider` branch translation | P2-only `(1,1,2)`, PP+P2 `(1,D,2)` when `pp/D` is even, full-Q `(q,D,2)` when `pp/D` is even, paired-lane full-PP `(q/2,pp,2)` when q/2 is integral, and proper-Q+PP+P2 `(Q,D,2)` when `1<Q<q`, `Q|q`, `D>1`, `D|pp`, and `pp/D` is even; each actual path remains subject to public generation and the one-region gate. The separate `pp=8,D=2` whole-sector method still fails its current 108-case replay | Proper `(Q,D,1)` uses registered stable q-lane regrouping of complete PP-parent blocks; proper `(Q,D,2)` uses full-Q P2 parent regrouping over the same q-lane and PP-sector factors | Unsupported | Even local layers, integer q, odd `m>=3`; the new P2 route also requires proper Q, `Q|q`, `D>1`, `D|pp`, and even `pp/D`. It uses neutral Regular settings and an insert-side inlet, then public source/target generation checks coverage, phase, SLP edges, weld direction, N-to-S terminals, identity and one-region travel. Nine direct samples cover q=4..12, even `pp/D` values 2/4/6 and an odd q-lane group width of 3; six- and nine-phase arrays also pass local-set identity and mapped generation. In the refreshed 18-request `q_and_pp_and_p2` scan cell, support changes from 9 to 12, `unsupported-yet` from 5 to 2, and 4 rejected requests stay unchanged. The three promoted requests are `(q,pp,L,m;Q,D,P2)=(4,4,4,3;2,2,2),(6,6,4,5;2,3,2),(6,6,4,5;3,3,2)`. These samples add a bounded `(Q,D,2)` subset; odd `pp/D` remains outside this formula, while D=1 and full-Q requests retain separate constructors. Weld-side inlets remain closed for this new route. Existing defaults and registered P2 constructors retain their own admission. EMF-only mismatch is retained as `not strong symmetry layout`. Older selected matrices predate the one-region rule and require replay. |
| ZLP | Q=1 PP tuples retain per-case admission | Distinct P2-only `(1,1,2)` via a phase-local layer/slot mirror; selected PP+P2 `(1,D,2)` cuts complete P2 parents when they generate | All Q-divider>1 tuples are explicitly rejected, including mixed formulas | Finite six-phase phase-set samples only: `q=h/2`, `h=3/5/7`, poles=`2h`, `m=6`, `L=8`, target `(1,h,2)`; `h=1` is a separate mirrored boundary with ambiguous half-circle travel | Integer q, even layers and odd `m>=3`; ALLP+SLPP identity with `(m-1)q+1` paired edge in unshifted coordinates. A failed P2 parent leaves the selected PP+P2 case pending; older ZLP Q scans predate the explicit exclusion. EMF-only mismatch is reported, not rejected. |
| CP | `(1,2,1)` uses the registered four-pass slice weave when the `(1,2,2)` source has four `Nlayer`-sized passes per branch; `(1,4,1)` uses four calculated parent-half translations for even integer q when `4|pp`; `(1,D,1)` with `D>4`, `4|D`, `D|pp` cuts the public four-sector paths into `D/4` equal pieces; the `Q=1`, even `D>=4`, `D|pp`, `(q odd or D≡2 (mod 4))` family slices public `(1,1,2)` parents into `D/2` pieces when its public source passes preflight | `(1,pp-divider,2)` implemented | `(Q,1,1)` joins adjacent same-phase `(Q,1,2)` parents; `(Q,2,1)` uses common second-sector deployment; full-Q/full-PP `(q,pp,1)` slices the public `(q,1,2)` parent when `q>1` and even `pp>=4` | Finite six-phase phase-set samples only: `q=h/2`, `h∈{3,5,7}`, `m=6`, four poles, `L=8`, target `(h,1,2)`; `h=1` `(1,2,1)` is route-disabled; no direct half-q constructor | Every CP route requires positive `Nlayer` divisible by 4, supported phase count, insert-side inlet and CLWP-only body. The `(1,4,1)` route selects the public `(1,1,2)` parent with first signed step `+mq`, takes its second half, and applies offsets `[mq-δ, mq-1, 2mq-δ, 2mq-1]`; q=2, poles=8, L=4, m=3 reproduces the saved Phase-A conductor groups after inlet rotations/reversals and reorder. The higher-D sector slicing preserves source conductor order and introduces no new edge. The q=1 `D≡2 (mod 4)` family passed direct L=4 and arrayed local-layer samples; q=1 direct L=8/12 cases with invalid P2 sources remain disabled by preflight. Odd q remains outside half-translation and four-sector-slice constructors; this PP-only parent-slice formula covers odd-q even-D cases when public preflight passes. Each retained source and target passes coverage, phase/direction, identity, edges, and one-region preflight. The neutral result can be `not strong symmetry layout` and Auto Configure may report pending separately while Workbench keeps the generated route status; EMF asymmetry alone does not reject. Full-Q/full-PP slicing uses `pp/2` equal `2L` pieces and is separately checked; the former intact-parent matcher remains withdrawn. No-divider `(1,1,1)` remains explicitly rejected. |
| ZPP | (1,D,1) uses indexed whole-branch translations of the same-Naa (D,1,1) q-parent. Direct domains use q=Naa=D; arrays resolve per local set with q_local=Naa_local=D, q_global=D/s. | (q-divider,pp-divider,P2) implemented when q-divider*P2=q; every P2=2 tuple is rejected for positive odd integer effective q because q=2*Q has no integer Q | (Q,2,1) uses the common deployment for proper Q; full Q retains the existing ZPP route | Unsupported | Direct domains require D|pp and the least positive a with gcd(a,D)=1 and gcd(D,2*(pp/D)*a-1)=1; D=2 preserves its half-turn. Previously admitted direct routes remain a=1. Arrayed a>1 remains unsupported-yet after mapped global edges crossed two pole boundaries; one legacy a=1 array also has 12 such edges under an independent aggregate audit. The former direct D=3, pp=6 boundary is now Validated with a=2; all 36 previously disabled requests in the bounded direct sweep generated successfully. Supported phase/topology, positive even direct layers, neutral Regular settings, weld-side inlet and generated-parent checks remain. Phase-set rejection uses the effective local q, so a fractional global q is not treated as odd by itself. The bounded Q+PP weld-direction findings are unchanged. |
| TSP | Existing full-local-q identity transfer `(1,2q_s,1)` retains precedence; other PP-only tuples may use `tsp_spiral_pass_partition` | Existing defaults and fixed-lane `(1,D,2)` sectors retain precedence; complete-pass partition adds other eligible P2 tuples | Existing adjacent-parent q-only and second-sector routes retain precedence; complete-pass partition closes even-Naa gaps across Q, PP and P2 factors | No new fractional-global-q admission; existing fractional routes unchanged | New fallback: integer global q, even local layers, Q divides local q, D divides pp, P2 in {1,2}, even Naa, and at least two complete local-layer passes per branch. Neutral Regular/unshifted insert-side only. See the current closure section for gcd orbit coverage, cohort/lane/cut lineage, native odd-phase and phase-set array checks. At the saved q=2/pp=4/L=4 geometry all five formerly unsupported manual routes generate; asymmetric results remain not strong symmetry layouts. Equal-D-sector inlets remain a contract of the separate fixed-lane constructor. |
| TLP | `(1,2,1)` uses layer-and-pole-reflected deployment; legacy `(1,D,1)` for even `D>2`, `D|pp`, `q<=2` cuts complete passes; direct full-Q `(q,D,1)` cuts public `(q,2,1)` parents when `q>1`, even `D>=4`, `D|pp`, and even `L>=4` | `(1,D,2)` cuts public `(1,1,2)` into phase-preserving PP-sector short units. `(2,D,2)` cuts each public `(1,D,2)` parent into two complete-pass children when q is even, `D>1`, `D|pp`, `2D<=pp`, even `L>=4`, and `B=(q/2)(pp/D)>=2`; each selected positive sector has two distinct inlet lanes per outer layer. Other P2 routes keep their separate guards. | `(Q,2,1)` uses common second-sector deployment, subject to `2<=pp` | Finite six-phase phase-set samples only: `q=h/2`, `h∈{1,3,5,7}`, `m=6`, four poles, `L=8`, target `(h,2,1)`; no general odd-`h` family | Odd native `m>=3`, neutral Regular, insert-side inlet and zero shifts/TP for the new parent-slice route; each admitted phase-set local view needs even `L_local>=4`. Preserve signed ALLP+CLLP, untransposed welds with one lower-to-higher direction per layer pair, and returns oriented with layer traversal. All TLP routes require `D*P2<=pp`. The saved q=2, pp=4, L=4 `(2,2,2)` draft is reproduced by public generation, while the draft remains exploratory. The q=4/6 route permits distinct adjacent inlet lanes when full coverage, identity, edges, weld and electrical checks pass; q/2 lane spacing is diagnostic. Source placement or short local-layer failures remain `unsupported-yet`. D=2 PP-only keeps separate Auto; the half-integer PhaseSetSpec samples remain their own bounded family. Other PP tuples remain unsupported where no constructor is registered. |
| LPP | Only full PP `(1,pp,1)` is admitted, subject to case validation | All other Q/PP/P2 tuples are rejected by the confirmed LPP construction rule | Unsupported | Finite six-phase phase-set samples only: `q=h/2`, `h∈{1,3,5,7}`, `m=6`, four poles, `L=8`, target `(1,2,1)`; no direct half-integer formula | Odd `m>=3`, even layers, weld-side inlet; SLPP-only opposite-direction layer-pair loop. The q=2, pp=4, L=4 lower-D examples reverse weld travel and remain rejected despite earlier route notes. A full-PP tuple can still fail its own case validation. |

### SLP proper-Q + PP + P2 parent-regroup extension (2026-09-28)

The new proper-Q+PP+P2 route is derived from the public full-Q P2 parent
`(q,1,2)`. For each phase and P2 cohort, divide the parent passes into `D`
sectors. For target lane group `g`, take the contiguous lanes
`[g*(q/Q),(g+1)*(q/Q))`; each target contains `q/Q` lanes and `pp/D` passes
per lane. Traverse complete `2L` blocks in sector-major order, reversing the
lane order on alternate blocks. Each branch therefore has
`(q/Q)*(pp/D)*L` conductors and the target has `2QD` branches per phase.

The formula domain is integer `q>1`, proper `1<Q<q`, `Q|q`, `D>1`, `D|pp`,
even `pp/D`, `P2=2`, positive even local layers, and supported phase topology.
Production admission also requires Regular settings, zero TP/phase/radial
shifts, no inlet adjustment, and an insert-side inlet. It generates the same
Pattern's public `(q,1,2)` source and then applies the formula to the requested
`(Q,D,2)` target. Public validation remains
authoritative for exact coverage, branch length, phase, SLP insertion/return
grammar, welding direction, N-to-S terminals, ordered identity, and the
one-region gate.

The before/after source snapshot is the prior `pattern_route_inventory.json`
saved in `Backups/slp_q_pp_p2_lane_regroup_20260928_181159/`. Across the
bounded 860-request scan, the SLP `q_and_pp_and_p2` cell contains 18 requests:
9 supported, 5 `unsupported-yet`, and 4 rejected before this formula; after
refresh it contains 12 supported, 2 `unsupported-yet`, and the same 4 rejected.
The three newly admitted scan requests are
`(q,pp,L,m;Q,D,P2)=(4,4,4,3;2,2,2)`,
`(6,6,4,5;2,3,2)`, and `(6,6,4,5;3,3,2)`. Nine direct cases and two
arrayed public cases pass generated coverage, equal length, local identity,
and route checks. The direct samples include `pp/D=2,4,6` and `q/Q=3`.
Odd `pp/D` stays outside this formula; `D=1` and full-Q requests retain their
separate routes. The independent `(1,D,2)` whole-sector formula and its
one-region boundary are unchanged. EMF mismatch remains a retained diagnostic,
not a construction rejection.

The nondefault odd-sector sample `(q,pp,L,m;Q,D,P2)=(8,8,4,3;2,8,2)` stays
`unsupported-yet`. The separate `(6,6,4,3;2,2,2)` request equals SLP's
classifier-default tuple and retains its pre-existing generated `rejected`
result. That default result is not a general rejection of odd `pp/D` values.

### SLP proper-Q + PP single-sector weld extension (2026-09-28)

The selected `(Q,D,1)` route still builds its insert-side reference by stable
q-lane regrouping of complete `(1,D,1)` PP-parent blocks. A sampled one-
conductor rotation exposed a parameterized weld construction for the single-
sector boundary `D=pp`: for each insert-side path `P=[c0,...,cn]`, emit
`P'=[c1,...,cn,c0]`. With pole-region slot width `tau=m*q` and `Q|q`, the
closing signed slot step is `tau-(q/Q-1)`. Production records every edge's
signed travel and checks the closing edge against this derived value.

Admission is limited to the existing selected route domain plus `D=pp>1`,
`P2=1`, positive even layers, a supported phase topology, neutral Regular
configuration, zero phase/radial/TP shifts, and no inlet adjustment. Weld-side
is still disabled for repeated sectors (`pp/D>1`); the sampled `pp/D=2`
seams crossed three pole regions. The route remains insert-side for those
geometries. Classifier-default routes keep their existing constructor.

Eight public geometry samples generated and were retained: seven direct cases spanning
`(q,Q,pp,L,m)=(4,2,2,4,3)`, `(6,3,2,4,3)`, `(6,2,3,4,3)`,
`(6,2,3,8,7)`, `(8,4,2,8,3)`, `(8,2,4,4,5)`, and `(9,3,3,8,3)`, plus
one six-phase array with global `q=4,m=6,L=8` and local `q=8,Q=4,pp=2,L=4`.
The generated weld paths equal the one-conductor rotations of insert-side
paths, include signed travel for every edge, stay within one pole-region
crossing per edge, and pass set-aware SLP identity; direct odd-phase samples
also pass the SLP route validators. All eight public results are
`retained-not-strong` because of EMF asymmetry (`parallel_emf_mismatch`; the
array also reports `multi_phase_emf_mismatch`), so this extension does not
claim strong-symmetry certification. Shift, Times, radial shift, inlet
adjustment, and repeated-sector weld cases remain guarded. EMF-only mismatch
continues to be retained as `not strong symmetry layout`. The [replayable
rule card and sample matrix](workbench_preview/slp_q_pp_single_sector_weld_20260928/README.md)
record the formula, boundary, and focused regression command.

### Sampled six-phase half-integer phase-set lift

For SLP and ZPP, four existing public samples at `m=6`, four poles, `L=8`,
neutral Regular settings, zero phase shifts, and divider tuple `(h,2,1)` with
`h=2q∈{3,5}` resolve as `enabled/supported` and generate through
`get_winding_layout`. The existing `PhaseSetSpec` maps two local three-phase
sets with `q_local=h` and four layers each. Each sample passes ordered
identity, unique occupancy, signed-edge, pin-role and one-pole-region checks;
its EMF mismatches remain retained diagnostics.

These are verified tuple samples, not a registered half-integer formula family
for every odd `h>=3`. In the matrix above, SLP/ZPP `Unsupported` refers to a
separate direct single-set half-integer formula; it does not override the
sampled phase-set routes. Other `h` values, Patterns and geometries remain
unverified. See the reviewed formula card and replayable evidence (local research excluded).

For TLP, four existing public phase-set samples at `q=h/2`, `h∈{1,3,5,7}`,
`m=6`, four poles, `L=8`, and target `(h,2,1)` resolve as `enabled/supported`
and generate successfully. Each of the two local three-phase sets uses
`q_local=h`, `L_local=4`, and a public `(h,1,2)` parent. The local target route
is `tlp_pp_only_two` for `h=1` and `tlp_q_pp_two` for `h=3,5,7`; the common
operation is the existing `PhaseSetSpec` lift, not one universal local TLP
formula. The full-path evidence maps both complete local identities and signed
travel records through exact ordered paths. The global identity report itself
lists edge-role details for only half of the global edges, so that report alone
is not complete evidence. The `L_global=4` / `L_local=2` boundary is excluded:
its observed identity has only ALLP and does not establish the TLP pin grammar.
See the reviewed TLP phase-set card and replayable evidence (local research excluded).
Unsampled `h`, layer counts, phase counts, pole counts, and shifts remain
unverified; this entry does not add a universal odd-`h` formula or route.

For BWP, four existing public phase-set samples at the same fixed geometry
(`m=6`, four poles, `L=8`, target `(h,2,1)`) cover `q=h/2` for
`h∈{1,3,5,7}`. The two local sets use integer `q_local=h` and each resolves
through the existing public `bwp_default` route. At `h=1`, early global
preclassification reports `bwp_fractional_sector_array`, but final generation
still dispatches to the local defaults; `h=3/5/7` use the local integer
fallback directly. This is evidence for the existing phase-set path, not a
new BWP formula or general odd-`h` admission. Every sample passes BWP wave,
return, weld, occupancy, signed-step, and ordered-identity checks; EMF
mismatches remain `not strong symmetry layout`. The global identity detail
table is not treated as complete: mapped local identity reports cover the
global ordered paths. See the [reviewed BWP phase-set card and replayable
evidence](workbench_preview/half_integer_q_bwp_phase_set_lift_20260927/README.md).
The card's four examples do not test a returnless branch, although the BWP
contract allows optional returns.

For SSP, four existing public samples at `q=h/2`, `h∈{1,3,5,7}`, use the
same fixed geometry (`m=6`, four poles, `L=8`) and target `(h,2,1)`. Both local
three-phase sets resolve the existing integer-q route at `q_local=h`; all four
public global routes are enabled and generate successfully. The phase-set
coordinate mapping preserves each ordered local path, global/local occupancy,
phase and polarity, and SSP identity. Edge signed travel is inferred from the
unique endpoint shortest arc because the generated SSP paths do not contain
constructor-recorded `signed_travel` metadata; return and weld step patterns
are inherited from the public local parent, not claimed as independent closed
formulas. EMF mismatches remain `not strong symmetry layout` diagnostics. The
matrix's `Unsupported` for SSP refers to the direct three-phase half-q
no-divider construction; it does not override these phase-set samples. This
finite evidence does not register a new SSP formula or extend direct
half-integer admission. See the [reviewed SSP phase-set card and replayable
evidence](workbench_preview/half_integer_q_ssp_phase_set_lift_20260927/README.md).

For LPP, four existing public phase-set samples at `q=h/2`, `h∈{1,3,5,7}`,
use the fixed geometry `m=6`, four poles, `L=8`, and global target `(1,2,1)`.
Each local three-phase set has integer `q_local=h` and uses its existing
`lpp_pp_default` full-PP route. All public decisions are enabled and generate
successfully; each passes 27 focused count, occupancy, ordered-identity,
phase/polarity, edge, and coordinate-lineage checks. The N-to-S terminal gate
does not apply because `P2=1`. Signed steps are unique endpoint-inferred
shortest arcs, not recorded physical travel or an independent closed-form
step rule. Global `multi_phase_emf_mismatch` remains a diagnostic with no
non-EMF errors. These samples do not add a direct half-integer formula or
production admission. See the [reviewed LPP phase-set card and replayable
evidence](workbench_preview/half_integer_q_lpp_phase_set_lift_20260927/README.md).

For ZLP, the fixed six-phase samples use `m=6`, `L=8`, and global
`q=h/2`. At `h=3,5,7`, choose `poles=2h` and target `(1,h,2)`; both local
three-phase sets use the existing `zlp_default` route. Each passes 30 focused
identity, N-to-S, occupancy, phase/polarity, transition-state, and mapping
checks. The local paired pitch is `2h+1`. The `h=1` sample (`q=1/2`, two
poles) is a separate boundary using `zlp_p2_mirrored`, not part of this
`h>=3` candidate family. Its 36 global half-circle edges retain both `+3` and
`-3` travel candidates, so physical signed travel is unresolved. Public ZLP
paths do not record `signed_travel`; the other samples' steps are endpoint
choices, not verified physical travel. The four public samples resolve as
supported and generate, with global EMF mismatch retained only as a
`not strong symmetry layout` diagnostic. This is bounded phase-set evidence,
not a direct half-integer formula or general odd-`h` admission. See the
reviewed ZLP phase-set card and replayable evidence (local research excluded).

For CP, three existing public phase-set samples at `q=h/2`, `h∈{3,5,7}`, use
`m=6`, four poles, `L=8`, neutral Regular settings, zero shifts, insert-side
inlet, and target `(h,1,2)`. Each local three-phase set has integer
`q_local=h` and uses its existing `cp_default` route. The public global and
local paths match exactly after P2 endpoint orientation and the real
`PhaseSetSpec` mapping; coverage, CP identity, phase/polarity, and one-region
checks pass. The samples are retained despite local `parallel_emf_mismatch`
and global `multi_phase_emf_mismatch`; no physical `signed_travel` metadata
exists, so endpoint-inferred steps are not claimed as actual conductor travel.
The alternative `(h,2,1)` is disabled for these same samples by duplicate and
missing conductor preflight (72, 120, and 168 respectively). At `h=1`, the
`(1,2,1)` local route is unsupported and the global phase-set request is
disabled; it is not part of the `h=3/5/7` composition evidence. These are
finite examples of existing local integer-q defaults, not a direct half-q
constructor, a new CP formula, or general odd-`h` production admission. See
the reviewed CP phase-set card and replayable evidence (local research excluded).

## 5. Status meanings in Pattern Rule Workbench

### Learned SLP pp-divider route

The SLP PP-only route `(1,D,1)` uses one symbolic rule for every admitted
divider `D`: derive Branch 1 from the no-divider phase reference by selecting
`pp/D` pole-pair sectors and alternating the q-lane order between consecutive
sectors, then rotate it by `k*slots/D` for each later branch. For `D=2`, Branch 2
is therefore an exact half-circumference copy of Branch 1. The designer q=2,
pp=4, L=4 draft established the block order and its `tau-1` same-layer return;
the executable rule contains no coordinates or geometry tuple from that draft.

The bounded regression sweep over q=2..6, pp=2..10, even layers 2..20 and
m=3/5/7 produced 2,550 selected PP-only layouts. Every case had complete unique
coverage, equal nonzero complex branch EMF, valid SLP identity, and exact
circumferential copies. Runtime validation remains authoritative outside that
evidence grid.

### SLP P2 lap-pass routes

The selected P2 constructors derive immutable `L`-conductor lap passes from
the same Pattern's no-divider reference. P2-only `(1,1,2)` splits each phase
reference in two and cyclically rotates complete passes to an N-to-S
inlet/outlet. Full-Q `(q,D,2)` partitions each q lane into `2D` sectors of
`pp/D` passes; adjacent sectors use forward and reversed pass order. This
construction requires even `pp/D`. The paired-lane full-PP route
`(q/2,pp,2)` joins one upward pass and one downward pass from adjacent q
lanes, using the signed return pitch `-(tau-1)`.

The PP+P2 route `(1,D,2)` is constructed when `pp/D` is even. Each branch
joins `pp/(2D)` complete pole-pair sector paths in the existing SLP sector
order. Within a sector, ascending q lanes alternate upward and downward
passes, then the remaining passes return through descending lanes. Odd
sectors reverse the pass order; even sectors come first, followed by odd
sectors in reverse sector order. The saved q=2, pp=4, L=4 `(1,2,2)` paths
are reproduced exactly. The earlier bounded `pp=2D` sweep at q=1..6,
pp=4/6/8/10, L=2..20 even, m=3/5/7 found 612/720 generated cases; its
remaining 108 q=1, L>=4 identity candidates belong to that dated sweep.

The 108-case multi-sector audit (local research excluded)
has been replayed under the one-region rule for `pp=8,D=2`, `q=1..6`, even
`L=2..12`, and sampled `m=3/5/7` under neutral Regular insertion-side
settings. **All 108 whole-sector constructions fail** because at least one
same-layer return crosses multiple pole regions. Their earlier 108/108 public
success report is archived in `Backups/pole_region_rule_20260924` and is no
longer an admission claim. The registered
`(q=2,pp=8,D=2,L=4,m=5)` comparator now reports Candidate identity and
cannot be publicly generated without `allow_candidate`. This rejects the
whole-sector construction method, not every possible `(1,D,2)` SLP route.
The
replayable probe (local research excluded)
records source and validator hashes. At `pp=6,D=2`, odd `pp/D=3` would need
one-and-a-half complete sector paths per child, so only this whole-sector
grouping method is inapplicable; the route remains pending for a different
partition.

All three routes require integer q, even positive layers and odd `m>=3`.
Neutral Regular with an insert-side inlet supplies the base reference; an explicit
Auto recipe must still pass the generated-layout checks. The generated
case must pass exact conductor coverage, equal branch length, phase and signed
direction, SLP pass and return edges, one normalized welding direction per
layer pair, N-to-S P2 terminals, and Pattern identity. Complex branch EMF is
reported separately; asymmetry retains the layout as `not strong symmetry`
without certifying it as electrically balanced. The 48-slot, 8-pole, 4-layer
manual packages are design examples, not coordinate rules or manufacturing
approval. PP+P2 tuples outside the even-sector factor relation remain
unsupported-yet until they have a validated constructor.

### Designer complementary full-circle UWP construction

The admitted selected `pp_only` route `(1,2,1)` now uses the schema-v3
designer-derived construction for every positive integer q. This extension is
limited to `pp-divider=2`; other divider constructions are unchanged. Each layer pair contains
q full-circle waves of `poles` conductors. One branch ascends layer pairs;
the complementary branch starts half a circumference away on the last layer
and descends pairs. Both branches alternate the lane order between pairs. Its half-circle
start is phase-compatible under the existing even pole-pair admission.
The second branch retains its bottom-layer N inlet and travels in the opposite
circumferential direction. Its directed pitch is negative; wave pitch magnitudes
and the alternating q-lane schedule are unchanged.
The last lane of each pair is the first lane of the next pair: the pair-jump
pitch is `m*q`, and wave transitions have pitch `m*q +/- 1`, independently of q.
The supplied draft is one lane ordering, not a required coordinate snapshot.
The original classifier remains the admission authority; other decompositions
and out-of-family geometries retain their existing constructions. Regular
insert-side inputs are required. Independent coverage, phase/sign,
nonzero complex-EMF and adjacent-layer/forward-pitch checks apply. This is
software validation, not manufacturing approval.

Selected `q_and_pp` tuples `(Q,2,1)` with `1 < Q <= q` and `Q` dividing q
instead reuse the UWP `q_p2` reference `(Q,1,2)`, within the existing proper-Q
admission domain. Each layer pair contains `q/Q` full-circle waves and uses
the reference's neutral q-position groups unless transposition is explicitly
selected. Auto permutations preserve intact weld pairs; no permutation advance
is permitted on welding edges.
Only the construction input is mapped: the actual divider identity remains
`(Q,2,1)` and does not receive P2-specific terminal orientation. The reference
edge contract is `(m-1)*q < forward pitch < (m+1)*q` with adjacent layers.
For deployment, each phase's first Q branches start in N regions at the top;
the second Q branches start half a circumference away at the bottom and travel
in the opposite circumferential direction. Reflect the second cohort's layers
and pole travel, retaining its q-position schedule and conductor order. Interpret
the edge contract in each branch's travel direction. Recheck N inlets against
the shifted phase map after configuration. For q=4, poles=8, layers=4, Q=2,
Phase A starts are S1/L1, S3/L1, S49/L4 and S51/L4.
The configuration stage still applies additional Regular offsets and layer
shifts, with complete coverage and nonzero complex branch EMF checked after
transformation. For q=6/Q=2/poles=8/layers=4, the shifted `[0,1,0,1]` case
is retained at m=3/5/7 with a `parallel_emf_mismatch` diagnostic; it is not
certified as strongly symmetric. Other pp-divider values and P2 routes keep
their existing constructions.

### Configurable integer UWP PP-only routes

All integer UWP routes admitted as `pp_only` share the same configuration stage,
including complementary two-branch and existing higher-divider constructions.
Regular `uni_tp` permutes q positions on ordinary weld steps, restarting its
schedule at each explicit wave transition. `jltp` advances q positions at
layer-pair jumps. Group offsets add to the global offsets for branches classified
by their unshifted inlet phase-map sign (`PoleN`/`PoleS`); an active group with no
members is rejected. Layer shifts translate each conductor by its own layer's
integer slot offset. Zero settings preserve the base path.

Generation validates neutral edge pitch, shifted forward direction, complete
coverage and nonzero branch EMF. Duplicate conductors and reversed edges reject
the case. Unequal parallel complex EMF is reported separately; a layout that
passes the other gates is retained as `not strong symmetry layout`.
This stage supports Regular Uniform/Jump and phase shifts; Auto, Times/Interval,
first/last-layer offsets, reverse jump direction, radial swaps and manual inlet
adjustments remain outside this change. Fractional-q candidate routes retain
their separate construction and configuration handling.

The Workbench has two tabs: `Divider Route Catalog` and `Pattern Rule Editor`.
Every Open button selects the editor directly. Reference documents remain on disk.

The Route column names the Naa formula independently of implementation dispatch:
`no_divider`, `q_only`, `pp_only`, `p2_only`, `q_and_pp`, `q_and_p2`,
`pp_and_p2`, or `q_and_pp_and_p2`. A factor is active when it differs from one;
this includes the positive half-integer q factor, including q=1/2.
Default and unimplemented rows also have formula names.

`rejected` identifies an explicit admission exclusion, including every BWP
`P2=2` tuple. `unsupported-yet` identifies a tuple with no implemented admission
route. Neither label asserts physical impossibility. The earlier `Unsupported`
label in historical descriptions below is superseded by these two labels.

- **Default**: the Pattern's automatic factor priority generated a complete base
  layout for the displayed geometry.
- **Validated**: an Enabled selected non-default production route generated a
  complete base layout and passed its route and identity validators.
- **rejected**: an explicit rule exclusion or an admitted formula whose actual
  geometry failed generation/validation; the exact reason remains on the row.
- **unsupported-yet**: no current production admission rule exists. The row
  remains available for manual exploration; it is not an impossibility ruling.
- **Candidate**: drawable Workbench evidence that cannot enter production
  calculation or export, normally because pin inventory or Pattern identity
  changed and needs separate approval.

The catalog now enumerates both integer-q tuples and the positive-half-integer
UWP family `(q,pp-divider,2)`. Fractional rows for all other Patterns are deliberately
shown as `unsupported-yet`, so the absence of an implementation is visible rather
than hidden by a whitelist or an empty table.

For BWP, every integer catalog row with `P2=2` is likewise shown as
`rejected`, including a tuple that the generic factor-priority decomposition
would otherwise classify as a default. This is an explicit Pattern admission
boundary, not a physical-impossibility claim.

## 6. Validation boundary

**Current UWP divider exclusion (superseding the 2026-09-21 wording):**
`pp-divider * P2` must be either 1 or 2. Tuples with a larger product are
explicitly rejected by `UWP-PP-P2` in
`PATTERN_REJECTION_REASONS.md`. This includes mixed PP+P2 tuples and PP
factors greater than 2. PP-only/Q+PP with `(D,P2)=(2,1)` and P2 routes with
`(D,P2)=(1,2)` retain their separate construction rules.

**Project policy, 2026-09-21:** EMF asymmetry alone must not reject a layout or
restrict the construction domain. Retain layouts with no duplicate conductor
positions and equal conductor counts across branches as
`not strong symmetry layout` when EMF is asymmetric. Apply this to every Pattern
and divider family, not only half-integer UWP. Keep EMF, phase, topology and
symmetry diagnostics separate from the retention decision; retention is not
certification. This supersedes EMF-only rejection requirements above and in
historical records. Descriptions of existing executable rejection behavior above
remain implementation observations, not the desired policy; this documentation
policy is now implemented in the shared generator validation and UWP plan selection.
Balanced q-position plans are preferred, with an occupancy-safe fallback when
equal distribution is unavailable. The runtime retains asymmetry diagnostics
without treating them as successful electrical certification; duplicate positions,
unequal branch counts/lengths and independent phase/edge errors remain guarded.

`P2=2` N-to-S terminal orientation is common post-processing for every Pattern.
Pattern admission remains Pattern-specific. A drawable half-integer UWP with
unequal parallel complex EMF is retained as `not strong symmetry layout` and labelled
`This winding pattern does not feature strong symmetry.` Calculation publication
still requires the stronger electrical gates used by the normal layout path.

For historical integer-route evidence and tested matrices, see the
Version 7.5 integer-q status record (local research excluded).
For the current finite V7.6 view, see
[INTEGER_Q_DIVIDER_SUPPORT_STATUS.md](INTEGER_Q_DIVIDER_SUPPORT_STATUS.md).

### Welding-direction audit correction (2026-09-22)

TLP `(1,2,1)` and `(Q,2,1)`, plus TSP/CP `(Q,2,1)`, now reverse pole
travel together with the second cohort layer traversal. TLP Auto recipes that
transpose welding edges are rejected before objective ranking and replay.
No formula has been newly admitted by this correction.

The bounded audit still finds direction conflicts in ZPP `(Q,2,1)` and LPP
smaller-PP routes. ZPP reflection fails its current Z-edge guard. A distinct
PP-only `(1,2,1)` constructor is now registered from its same-Naa supported
`(2,1,1)` q-parent; it does not resolve the Q+PP audit. LPP now
rejects all tuples except `(1,pp,1)` following the 2026-09-24 user decision;
historical Enabled/Validated labels for smaller PP factors are superseded. See
the reproducible audit (local research excluded)
and its adjacent JSON/CSV records for parameters, exceptions and tested bounds.

## CP phase-array layer admission clarification (2026-09-28)

The previous array admission applied the global `Nlayer % 4 == 0` rule again
to every locally indexed three-phase set. That wrongly disabled some valid
array constructions. The corrected boundary keeps global positive
`Nlayer % 4 == 0`, then requires each local set's `Nlayer/(m/3)` to be positive
and even so the CP half-layer insertion span is integral. All cases still pass
the public source/target preflight and route-specific CP validators.

Publicly generated samples at global `Nlayer=12`, `m=6` cover:

| `(q,pp,Q,D)` | Route | Local layers | Result |
|---|---|---:|---|
| `(2,8,2,4)` | `cp_q_pp_full_parent_slices` | 6 | retained, valid per-set identity and CP edges |
| `(1,8,1,8)` | `cp_pp_sector_slices` | 6 | retained, valid per-set identity and CP edges |
| `(2,12,2,6)` | `cp_q_pp_full_parent_slices` | 6 | retained, valid per-set identity and CP edges |

Each sample has complete unique occupancy, equal branch lengths, valid phase
membership, and at most one pole-region crossing per edge. EMF-only errors are
retained as `not strong symmetry layout`. The former gate rejected these
because local six-layer groups are not divisible by four. The corrected gate
still disables global `Nlayer=10`; it also disables `m=12`, global
`Nlayer=12`, whose local three-layer groups cannot form integral `L_local/2`
CP insertion edges. The sampled cases and rejection boundaries are finite
evidence, not proof of every geometry.
