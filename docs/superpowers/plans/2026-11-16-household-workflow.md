# Household workflow implementation plan

Execute inline with executing-plans; no subagents or renewed approval loop. User authorized this
work. Spec: ../specs/2026-11-16-household-workflow-design.md. Existing Python/SQLite/cloud stack;
main/UI/recordings preserved, no private upload/hardware, $5 cumulative provider cap.

- [x] Freeze public source-separated visual/report workflows and scoring. Add meaningful scorer,
      provenance and source-leakage tests. Prepare edited fixture videos; record natural-video scope.
- [x] Run actual API development workflows with guarded real resolver/embedding/planner calls;
      inspect each stage and actual final answers. Record baseline failures before implementation.
- [x] Reproduce failures deterministically, implement minimal general backend fixes, and run
      targeted regressions. Freeze selection before heldout, preserving existing models by default.
- [x] Run heldout, restart/ambiguity and spoken-tool boundary checks. Report failures explicitly;
      broaden with permitted natural public clips and offline existing local-media checks.
- [x] Update R29/milestones/architecture decisions as appropriate, run full checks, commit regularly
      on work/memory-reliability, and optionally back up only that branch. No new PR/merge yet.

Validation completion does not mean acceptance passed: the final fresh four-case holdout retains
one unsafe two-phone association. Preserve it as an open release gate; no automatic main/PR
publication. See R29 for every selection, failed trial, native handoff repair and current limits.

Final default remains joint plus conservative veto. The separated pipeline/handoff is opt-in after
a baseline comparison exposed a new unsafe saved link. Core default1/4; fresh known-case default3/4;
opt-in results must stay distinct. Validation/research pass complete, broad household acceptance
not complete.577 tests and source/UI/main preservation checks passed; usage$4.73185091/$5.
