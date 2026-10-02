# Naa divider rules

Read relevant sections before changing or reviewing `Naa`, `(q-divider, pp-divider, P2)`, Pattern route
admission, fractional-q construction, branch terminal orientation, or the Pattern
Rule Workbench.

## Common identity

All divider tuples use:

```text
pp = poles / 2
pp-divisors = {d in positive integers | pp mod d = 0}
Naa = q-divider * pp-divider * P2
```

- `q-divider` is the selected factor contributed by q.
- `pp-divider` is any positive integer factor in `pp-divisors`. Do not use `PP`
  as shorthand in formulas because `pp` is the pole-pair count itself.
- `P2` is 1 or 2.
- For integer `q`, `Q` must be an integer divisor of `q`.
- Positive half-integer `q` has exploratory constructions, including
  `(q,pp-divider,2)` and `(q,2,1)`. Keep their existing interface and evidence;
  use the active resolver for exact admission and the public generator for
  production status. This factor identity does not expand the support domain.

Do not encode parameter tuples, q values, pole counts, or Pattern whitelists as a
substitute for these factor rules. A factor identity makes a tuple enumerable; it
does not by itself admit a production connection.

## Divider-type formulas

Classify the tuple by the factors greater than one:

- No divider: `(1,1,1)`, `Naa=1`.
- q-divider only: `(q-divider,1,1)`, `Naa=q-divider`.
- pp-divider only: `(1,pp-divider,1)`, `Naa=pp-divider`.
- P2 only: `(1,1,2)`, `Naa=2`.
- Mixed q + pp-divider: `(q-divider,pp-divider,1)`,
  `Naa=q-divider*pp-divider`.
- Mixed q + P2: `(q-divider,1,2)`, `Naa=2*q-divider`.
- Mixed pp-divider + P2: `(1,pp-divider,2)`,
  `Naa=2*pp-divider`.
- Mixed q + pp-divider + P2: `(q-divider,pp-divider,2)`,
  `Naa=2*q-divider*pp-divider`.

The type name describes factor composition, not Pattern support. Always consult
the executable Pattern admission function and generated-layout validators.

## P2 domain families

For explicit UWP routes, pp-divider and P2 share a splitting allowance: their
product must be 1 or 2. Larger explicit factors are rejected. An implicit
sector-array default is classified by its own identity before this explicit
split guard; do not promote it to an explicitly selected production route.
Use the reason maintained in `PATTERN_REJECTION_REASONS.md`.

- Unit q-divider integer family: `Naa = 2*1*pp-divider`.
- Proper q-divider integer family: `Naa = 2*q-divider*pp-divider`, where
  `1 < q-divider < q` and `q-divider` divides q.
- Full q-divider integer family: `Naa = 2*q*pp-divider`; no cross-Pattern general route is
  implied, so use the current Pattern classifier and runtime validation.
- Positive-half-integer family: `Naa = 2*q*pp-divider`; currently UWP only, with pp-divider
  dividing pole pairs, odd `m >= 3`, and positive even layers.

The detailed formula documentation is
`Latest_Python_Files/Version 7.6/PATTERN_DIVIDER_FORMULA_SUPPORT.md`; resolver
decisions remain the admission authority. Keep documentation and the Pattern
Rule Workbench synchronized whenever admission changes.

## Admission and result levels

`resolve_pattern_route()` and `PatternRouteDecision.admission` own production
admission. `selected_integer_divider_route()` is a compatibility wrapper.
The current rejection registry is
`Latest_Python_Files/Version 7.6/PATTERN_REJECTION_REASONS.md`; maintain rejection
rules there rather than adding another independent rejection table.

Keep these meanings distinct:

- `Default`: the automatic Pattern factorization label; it does not certify a layout.
- `enabled` / `supported`: preflight admission; it is not `Validated`.
- `Validated`: an admitted route passed successful public generation and required
  checks. Manual Workbench drafts remain exploratory and non-certified.
- `rejected`: explicit exclusions or case-generation failures; show the exact reason.
- `unsupported-yet`: no current implementation/admission rule, not a proof of
  physical impossibility; preserve manual exploration.
- `Candidate`: provisional evidence or unresolved required checks. EMF asymmetry
  alone does not make a retained layout Candidate or rejected: retain it as
  `not strong symmetry layout` with electrical diagnostics.

Use the shared resolver decision as executable truth. Do not duplicate admission
decisions in UI or documentation code.

## Common P2 terminal invariant

For every explicit or derived route with `P2=2`:

1. Determine N/S regions from the shifted phase map. Region assignment must
   follow q, pole count, phase count, and layer phase shifts.
2. A phase inlet must be in an N-pole region.
3. The neutral outlet must be in an S-pole region.
4. Reverse any S-inlet/N-outlet branch.
5. Recompute start-conductor IDs, conductor order/index information, drawing
   terminals, filters, and exports from the oriented paths.

Apply this as common post-processing. Do not add per-Pattern terminal exceptions.

## Validation boundary

Project policy: EMF asymmetry alone is neither a layout rejection condition nor
a construction-domain boundary. For every Pattern/divider family, retain a
layout when conductor positions are not occupied more than once and all branches
have equal conductor counts. Manage an EMF-asymmetric result as
`not strong symmetry layout`, with EMF and symmetry diagnostics attached.
Do not prune a construction merely because no equal-EMF plan exists. Retention
does not certify strong symmetry or erase other topology/phase/edge diagnostics.
Treat older instructions that reject layouts solely for unequal parallel EMF as
historical; apply the current resolver and retention contract.

For any new or expanded route, check exact conductor coverage, equal branch
length, phase membership, signed direction, ordered Pattern connection sides
and layer spans, and the applicable nonzero parallel complex-EMF rule. Record
actual pitch for review; do not use its magnitude as a Pattern identity or
route-admission whitelist. Every actual insertion, weld and return connection
may cross at most one pole-region boundary along its signed circumferential
travel. In the integer-q domain the region width is `tau=m*q` slots; this is
a common physical edge limit, separate from numeric pitch identity. Apply it
to candidate construction and public generation. Test zero and nonzero phase shifts
when shifts are supported. Keep electrically unequal candidates drawable only
through the `not strong symmetry layout` path, across integer and fractional q.
