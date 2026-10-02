# Engineering boundaries

Read the relevant current record before changing engineering behavior:

- [Pattern definitions and constraints](../../../../Latest_Python_Files/Version%207.6/PATTERN_DEFINITIONS_AND_CONSTRAINTS.md): pin/Pattern terminology, defining topology, terminal versus edge sides, source boundaries and validation gates. Read only the affected family and rule sections.
- BWP checkpoint (local research excluded): bounded/incomplete search and candidate separation.
- Fractional BWP review (local research excluded): IndexError/cast repairs do not establish correct construction.
- Fractional-q audit (local research excluded): supported-domain guard and algorithm boundaries.
- Classic phase validation (local research excluded): invariants, preview isolation and counterexamples.

The Version 7.5 checkpoint and audit records above are historical context, not current test results or an active task list. Verify status needed for the current decision.

Escalation examples include truncating q; changing slot/pole/phase membership, odd-layer polarity, radial shift, transposition, inlet positions, connection side, per-edge pitch or complex branch EMF. Relaxing a guard/tolerance needs engineering justification and independent validation.

Equal occupancy/counts do not establish electrical balance or manufacturability. Use independent phase/polarity/branch expectations and rejection examples, including equal counts with wrong voltage/direction. No result from a bounded search is not a proof of impossibility or global optimality.

Layout retention is separate from electrical certification: EMF asymmetry alone
must not reject a layout or bound its construction domain. Retain layouts with
unique conductor-position occupancy and equal branch conductor counts as
`not strong symmetry layout` when EMF is asymmetric. Keep the electrical and
other engineering diagnostics visible; do not label retention as strong symmetry
or manufacturing approval. This applies to all Pattern/divider families.

Keep exploratory candidates separate from production dispatch. Before promotion establish the intended rule, supported inputs, independent oracle, rejection behavior and existing-domain compatibility. Present concrete alternatives for unresolved engineering choices; preserve production guards while awaiting the decision.
