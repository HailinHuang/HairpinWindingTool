# Version 7.6 status

Version 7.6 is the supported development target. Current executable support comes
from the production resolver and successful public generation. This repository
selects current source/tests, required help resources, and regression inputs.

## Implemented

- PyQt6 layout/phase/branch views, configuration/data export, winding-function and
  voltage-difference analysis, and inductance controls.
- Shared Pattern route decisions across admission, construction, main UI, and
  Workbench. `selected_integer_divider_route()` is a compatibility wrapper.
- Parameterized integer and selected fractional connection families, with separate
  supported, candidate, rejected, and unsupported admission states.
- Exploratory Workbench schema-v3 packages; manual completion does not certify routes.

## Limitations and blockers

- Saved `pattern_route_inventory.json`, `pattern_naa_division_layout.html`, and
  `INTEGER_Q_DIVIDER_SUPPORT_STATUS.md` describe an older finite sample. Their
  source signature differs from current code; counts are not current support.
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

1. [Refresh finite divider-status provenance and navigation](https://github.com/HailinHuang/HairpinWindingTool/issues/2).
2. [Define the bounded integer-divider acceptance domain](https://github.com/HailinHuang/HairpinWindingTool/issues/3).
3. [Complete source-bound half-integer TLP/UWP validation](https://github.com/HailinHuang/HairpinWindingTool/issues/4).
4. [Establish packaged/native acceptance tied to current source](https://github.com/HailinHuang/HairpinWindingTool/issues/5).

GitHub [Issues](https://github.com/HailinHuang/HairpinWindingTool/issues) are the
authoritative backlog. This list states priorities, not a second task database.

Delivery coordination lives in [Master Work Status](https://github.com/HailinHuang/HairpinWindingTool/issues/1),
separate from the four engineering Issues above. Keep its update time, task/phase,
branch/commit, unpushed changes, validation, blockers and next action current.
Use live Git for branch/commit and unpushed state.

## Last meaningful validation

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
