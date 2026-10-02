# BWP Auto Configure Rule Workflow

Use this workflow when deriving, changing, or broadening a BWP Auto Configure
shortcut. It keeps rule discovery, full-search differential evidence, runtime
eligibility, and user-facing optimality claims aligned.

## Current validated rule

- Manuscript v3 Table IV insertion-side formula: `minimum pin types = N_L + 1`,
  where `N_L` is the layer count. The formula supplies the target count for the
  `min_pin_types` objective; a candidate must still pass the existing public
  generator, occupancy, phase, edge, electrical, strong-count, start-region,
  and weld-side checks.
- Stop only when an accepted candidate reaches the exact target. Uniform,
  Last-layer, and Jumper-layer single-field Regular recipes are prioritized;
  First-layer T.P. is excluded because BWP does not consume it. The BWP recipe
  queue is checked before the current selected-input TP, so a selected Interval
  cannot preempt these rules. A target miss continues through the remaining
  recipe search and then checks the selected input.
- The stop is enabled only for integer `q=2..6`, pole pairs `1..6`, layers
  `{2,4,6}`, three phases, insertion-side inlet, and zero layer shifts. This is
  the measured search envelope, not a divider tuple whitelist or admission
  rule. Other objectives and inputs use full recipe search.
- The 2026-09-23 differential covered 381 BWP cases. Status matched full search
  in 381/381. Among 339 cases with a pin-type result, primary pin count matched
  in 339/339. Five cases had the same pin count but full search found a better
  transposition tie-break; the formula stop intentionally does not search that
  secondary objective. There were 204 formula stops and 177 full-search
  fallbacks. Candidate attempts were 249,443 versus 308,629, and measured
  aggregate elapsed time was 310.3 s versus 395.9 s. Timings are machine
  observations, not guarantees.

Case-level evidence is saved under
`workbench_preview/auto_configure_rules/bwp_min_pin_formula_verified_20260923_order2/`.
The result summary and evidence history are also recorded in
`AUTO_CONFIGURE_RULES.md`.

## Repeatable workflow

1. **State the intended objective and domain.** Identify which parameter axes
   are covered: q, pole pairs, layers, phases, phase shifts, divider routes,
   and TP objective. Separate current production routes from pending or
   unsupported formulas.
2. **Read current code ownership.** Inspect `automatic_transposition.py` for
   recipe construction and `get_winding_pattern.py` for Auto resolution and
   public generator validation. Read only the relevant BWP section in
   `PATTERN_DEFINITIONS_AND_CONSTRAINTS.md` and follow
   `.agents/skills/hairpin-workflow/references/divider-rules.md` when changing
   divider behavior.
3. **Build the differential case set.** Start from the latest BWP formula
   audit matrix and include every case in the proposed fast-path envelope,
   including Default, Validated, and pending statuses. Do not infer support
   from arithmetic divisibility alone. The current audit harness constructs
   three-phase, zero-shift cases; extend it before claiming coverage for other
   phases or shifts.
4. **Compare against full recipe search.** The audit harness remains with
   the Version 7.5 research archive and was not copied into this baseline.
   Run the historical audit from that directory:

   ```powershell
   & '..\..\.venv\Scripts\python.exe' audit_bwp_auto_rule_diff.py `
     --output-dir 'workbench_preview/auto_configure_rules/bwp_rule_diff_YYYYMMDD'
   ```

   The defaults cover integer q=2..6, pole pairs 1..6, and 2/4/6 layers from
   the current formula matrix. The auditor includes a forced full-search
   baseline for every fast-path hit; no-hit cases already complete full
   search. It writes JSON and CSV case-level results.
5. **Use objective-specific acceptance.** For a formula-target stop, compare
   result status and primary pin count with full search for every case with an
   available result. Also report effective parameters and metrics. Compare
   secondary tie-breaks separately: a documented early-stop objective may
   leave those unoptimized, but must not imply they match full search. Any
   primary mismatch means narrow the eligibility condition or retain full
   search. Treat elapsed time as supporting evidence; use candidate counts and
   exact primary-result comparisons as stable checks.
6. **Implement a general eligibility rule.** Derive candidates from geometry
   and recipe fields. Do not key off a list of successful divider tuples or
   sample cases. Keep runtime validation in the public generator path. Add
   explicit domain metadata so reports show which rule ran.
7. **Test boundaries and fallback.** Cover the first and last enabled q/pp/layer
   values, values outside the envelope, fractional q, changed phase count,
   nonzero shifts, insertion and weld-side inlets, each objective, an exact
   formula hit from a selected Interval input, a formula miss, and replay of
   the selected implementation.
   Out-of-domain cases and formula misses must continue full search.
8. **Record the result.** Update `AUTO_CONFIGURE_RULES.md`, this workflow's
   current validated-rule section, and `CHANGELOG_Version_7.5.md`. Preserve the
   exact matrix, scope, match counts, objective exceptions, output paths, and
   focused test commands. Do not describe a finite recipe search as global
   optimality or physical/manufacturing certification.

## Reuse prompt

For a later BWP rule change, ask:

> Follow `BWP_AUTO_CONFIGURE_RULE_WORKFLOW.md` to derive and differentially
> validate the proposed BWP Auto Configure rule. State the objective and domain,
> compare every case with full recipe search, keep out-of-domain fallback, and
> update the result record only after the comparison passes.
