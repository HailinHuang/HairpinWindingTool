# HairpinWindingTool development

- Source/tests and Git are executable truth; GitHub Issues are the only task backlog.
- New/resumed sessions: read `AGENTS.md` and `docs/STATUS.md`; use `README.md`
  as needed for setup and navigation.
- Local tasks: read relevant source and direct tests. Engineering changes also
  require relevant decisions, validation rules, and hairpin-workflow sections.
- Active code/tests live in `Latest_Python_Files/Version 7.6/`; use its launchers.
- Use task-relevant sections of `.agents/skills/hairpin-workflow/SKILL.md`.
  Announce mode, risk, scope, and checks. New code/file contents are English.
- Make the smallest relevant change. Preserve public calls/signals, saved formats,
  default/alternative routes, and user changes. Use LSP when available.
- Avoid speculative guards, fallbacks, abstractions, and unrelated refactors;
  preserve required validation and add safeguards only for demonstrated needs.
- For behavior changes, establish a failing test/reproducer, implement, then verify.
  Documentation needs content/path checks, not artificial behavior tests.
- Preserve exact conductor coverage, unique occupancy, equal branch counts,
  phase/polarity, signed travel, Pattern identity, and legal connections.
  Read relevant V7.6 constraints and divider-rules sections before rule changes.
- EMF asymmetry alone does not reject a unique-occupancy/equal-count layout.
  Retain it as `not strong symmetry layout` with electrical diagnostics.
  Equal nonzero complex branch EMF is a strong-symmetry gate, not a retention gate.
- `resolve_pattern_route()` and its shared decision contract own admission.
  Preflight is not `Validated`; public generation must succeed. Manual Workbench
  drafts remain exploratory and non-certified.
- Parameterize rules from geometry/divider factors; avoid tuple-specific exceptions.
  Keep admission, support documentation, and Workbench status synchronized.
- Scope checks to impact: docs/metadata use path/staging checks; local behavior
  uses direct tests; shared rules use affected invariant/regression checks.
  Full discovery needs broad impact, broader failures, or an explicit request.
- Delegate only independent work with a precise scope/reusable result. Use at most
  two workers and one owner per artifact; avoid duplicate implementation/review.
- Record unrelated findings as candidate Issues/notes; investigate only blockers.
- Preserve uncertain local historical copies; exclude them from Git. Never commit
  caches, outputs, backups, local settings, secrets, or audit dumps. Review files
  over 5 MB; exclude files over 20 MB unless their necessity is justified.
  Add new durable files to the repository's explicit `.gitignore` allowlist.
- Inspect live Git status before Git operations. Never force-push shared history
  or commit/push with failing or unrun applicable checks. Use imperative conventional
  messages with double-quoted `-m`. Add a license only at the owner's request.
- From V7.6: `..\..\.venv\Scripts\python.exe -X utf8 -m unittest <dotted-test> -v`.
  Set `QT_QPA_PLATFORM=offscreen` for UI tests; restore it before native launches.
  Launch: `run_main.bat`. Optional build: `build_main_pyqt6.bat` with PyInstaller.
- Finish with source/test updates, scoped validation, material state-document and
  Issue updates, an authorized commit, and a concise unfinished handoff in the Issue.
