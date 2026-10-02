# Version 7.6 status

Version 7.6 is the supported development target. Current executable support comes
from the production resolver and successful public generation. This repository
selects current source/tests, required help resources, and regression inputs.

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
- The integer-domain pole/layer/phase bounds are known; q upper bounds and
  configuration variants remain undecided. Universal route closure is unverified.
- Current packaged/native Windows acceptance, manufacturing validation, broad
  regression, cross-platform acceptance, and clean dependency installation are
  unverified. Earlier package smoke predates current source.
- One optional historical UWP fixture is absent; its existing test explicitly skips.

## Next priorities

Track these as discrete GitHub Issues with focused acceptance:

1. Core: [Define the bounded integer-divider acceptance domain](https://github.com/HailinHuang/HairpinWindingTool/issues/3),
   after q/configuration-domain decisions.
2. Core: [Complete source-bound half-integer TLP/UWP validation](https://github.com/HailinHuang/HairpinWindingTool/issues/4),
   after launcher review and a fresh source binding.
3. Application: [Establish packaged/native acceptance tied to current source](https://github.com/HailinHuang/HairpinWindingTool/issues/5).

GitHub [Issues](https://github.com/HailinHuang/HairpinWindingTool/issues) are the
authoritative backlog. This list states priorities, not a second task database.

Delivery coordination lives in [Master Work Status](https://github.com/HailinHuang/HairpinWindingTool/issues/1),
separate from the engineering Issues. Keep its update time, task/phase,
branch/commit, unpushed changes, validation, blockers and next action current.
Use live Git for branch/commit and unpushed state.

## Last meaningful validation

The finite-status refresh passed all 22 direct status tests, including five new
provenance/navigation checks, and `refresh_pattern_naa_division_layout.py --check`.
The six geometries and preflight counts are unchanged. Four TLP status assertions
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
Q and 15/18 phases. Fractional-global-q arrays for this route remain
`unsupported-yet`. The six-phase example retains a global
`multi_phase_emf_mismatch`, so local phase-set identity does not establish
strong symmetry. Workbench preserves Auto pending and retained-layout errors
while marking successfully generated routes Validated. These findings do not
certify strong symmetry or a release. See
[VALIDATION.md](VALIDATION.md) and [Issue #9](https://github.com/HailinHuang/HairpinWindingTool/issues/9).
