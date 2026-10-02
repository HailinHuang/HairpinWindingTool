# Engineering decisions

| Decision | Reason | Consequence |
| --- | --- | --- |
| Preserve V7.6 module/test/input locations. | Launchers, imports, resources, and fixture tests use them. | Select files without restructuring runtime code. |
| Use one production route decision. | Separate UI/core admission tables diverge. | `resolve_pattern_route()` owns admission; `selected_integer_divider_route()` delegates. |
| Divider arithmetic enumerates requests, not support. | Legal factors do not prove legal connections. | `Naa=Q*D*P2`; integer `Q` divides `q`, `D` divides pole pairs, `P2` is 1 or 2. Use resolver/generation gates. |
| Retain unique-occupancy/equal-count asymmetric layouts. | Electrical symmetry and retention are distinct. | Label `not strong symmetry layout` with diagnostics; equal nonzero complex EMF gates strong symmetry separately. |
| Successful public generation establishes validated routes. | Preflight/manual sketches omit full-path checks. | Candidate/manual packages remain exploratory, including saved regression inputs. |
| Pattern identity follows connection structure. | Pitch magnitude or finite examples cannot define a family. | Preserve ordered sides/layer spans, terminal orientation, legal signed edges, and common connection limits. |
| Derive rules from parameters and explicit domains. | Tuple-specific exceptions conceal boundaries. | State formulas, factor conditions, constant sources, examples, and counterexamples before admission changes. |
| Bind evidence to the source tested. | Shared changes invalidate receipts and generated status. | Refresh declared source-closure receipts after writers release the source window. |

The detailed constraints and code-owner map are in
[PATTERN_DEFINITIONS_AND_CONSTRAINTS.md](../Latest_Python_Files/Version%207.6/PATTERN_DEFINITIONS_AND_CONSTRAINTS.md).
The [divider support document](../Latest_Python_Files/Version%207.6/PATTERN_DIVIDER_FORMULA_SUPPORT.md)
and [rejection registry](../Latest_Python_Files/Version%207.6/PATTERN_REJECTION_REASONS.md)
describe construction boundaries. Finite failures do not prove physical impossibility.

Historical workspace research stays local. Preserve only required small
regression inputs in Git; use Git history for future changes and Issues for
unfinished work.
