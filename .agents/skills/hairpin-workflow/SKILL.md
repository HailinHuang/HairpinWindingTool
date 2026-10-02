---
name: hairpin-workflow
description: Route and execute development requests in the Hairpin Winding Script project using targeted context and verification. Use for its UI edits, features, debugging, refactoring, winding algorithms and releases; not unrelated projects or general engineering research.
---

# Hairpin Workflow

## Select one primary mode

Use intended outcome and actual impact, not file names or changed line counts. Work in the active version identified by the project entry; references target V7.6 unless marked as historical evidence.

| Mode | Trigger | Minimum workflow and completion evidence |
| --- | --- | --- |
| `explain` | Understand code, locate an entry, compare approaches | Read relevant sources; answer with evidence and limits; no implementation. |
| `ui-patch` | Static spacing, fonts, sizes, clipping or appearance | Locate widgets; minimal edit; targeted UI checks and affected-state screenshots. |
| `feature` | Add an interaction, export or capability | Establish acceptance criteria; failing behavior test; implement; related regression. |
| `debug` | Existing behavior crashes, yields wrong output or stale state | Reproduce; identify cause; failing regression; minimal repair and verify. |
| `refactor` | Restructure without changing behavior | Identify invariants; establish passing characterization coverage; restructure and rerun. |
| `algorithm` | Change winding rules, topology, EMF or supported domain | Establish engineering rules and independent oracle; validate candidates/rejection cases; retain candidate status until production criteria pass. |
| `release` | Package, change dependencies or prepare delivery | Identify version/environment; applicable checks; build and native artifact checks when packaging is in scope. A source import does not establish release certification. |

Documentation implementation uses `feature` with document/link checks instead of artificial behavior tests. Questions about algorithms remain `explain` unless the user requests changes or validation.

## Risk and escalation

- `low`: explanation or local static appearance/documentation, without behavior/rule changes.
- `normal`: bounded behavior change, repair or refactor under established rules.
- `high`: engineering-rule/domain changes, cross-module compatibility changes, persisted format changes or releases.
- Distinguish UI layout from winding layout. If context cannot resolve "fix the layout", ask one targeted question before dependent edits.
- Until resolved, announce `Mode: pending clarification | Risk: undetermined` and do only independent read-only investigation.
- Zoom/docking and config persistence are behavior: use `feature` or `debug`, not `ui-patch`.
- Changes to phase assignment, polarity, branches, pitch, engineering tolerances or production guards require `algorithm/high`. Read relevant [engineering constraints](references/algorithm.md) before choosing such a repair.
- Changes or reviews involving `Naa`, `(q-divider, pp-divider, P2)`, Pattern divider admission, fractional-q routes, or P2 terminal polarity must also read and follow relevant [Naa divider rules](references/divider-rules.md).
- Known-rule numerical defects can remain `debug/normal` when the rule is preserved and an independent expected result exists. Escalate if investigation reveals a rule change.
- Mixed requests use one primary mode plus the union of applicable checks. Prioritize a required algorithm change, then release delivery; otherwise the dominant requested outcome. Split independent unrelated outcomes when useful.
- User-selected modes do not suppress higher-risk verification. Explain escalation briefly; ask only if the intended engineering rule is unresolved.

## Execute with bounded context

For new/resumed sessions, read root AGENTS.md and docs/STATUS.md; use README.md as needed. Read the responsible symbol/module and direct tests before expanding. Engineering changes require relevant decision, validation, and skill sections. Use LSP if available, otherwise targeted search. Use relevant [test mapping](references/testing.md) for verification, [prompt examples](references/prompts.md) only when formulating requests.

Keep acceptance conditions and checks in working context, not a new TODO file. For behavior changes establish a failing reproduction/test first, implement the simplest fix, then refactor if useful. For wording/static appearance use suitable checks instead of implementation-mirroring tests. Documentation changes need business tests only when necessary to verify changed execution instructions.

After two failures of the same approach, inspect evidence and change hypothesis or method. Do not repeatedly widen searches. Report genuine blockers and their effect on verification.

## Delegate independent work

The main agent owns routing, implementation, integration and delivery. Small tasks use one agent; complex tasks may use at most two child agents.

- Investigator: independent module or falsifiable hypothesis; return locations, evidence, conclusion and recommended checks.
- Reviewer: algorithm, high-risk compatibility or substantial cross-module changes; check explicit invariants and return actionable findings with evidence.
- For those changes, default to one independent read-only reviewer once concrete rules or a diff exist. Add an investigator only for a separate open question. Do not spawn a reviewer just to classify a request or while blocked on intent. Packaging alone does not require a reviewer.
- Supply only the task, necessary paths, constraints and output contract. Avoid full conversation inheritance when unnecessary. Investigators/reviewers are read-only unless assigned separate implementation work. Parallel writers own disjoint files.
- No automatic plan/implement/review pipeline for a small patch. If delegation is unavailable, perform checks locally and disclose missing independent review when material.

## Finish

Stop when acceptance criteria and applicable checks pass. Expand checks for new failures, wider impact, unresolved risk or release needs. Before commit/push run applicable tests; never treat old counts as current results.

Report changes, checks actually run and material limits. Distinguish offscreen/native DPI evidence, candidates/engineering validation and build/launch-tested artifacts. Completing the workflow does not itself authorize commit, publication or candidate promotion.
