# Household workflow implementation plan

Execute inline with executing-plans; no subagents or renewed approval loop. User authorized this
work. Spec: ../specs/2026-11-16-household-workflow-design.md. Existing Python/SQLite/cloud stack;
main/UI/recordings preserved, no private upload/hardware, $5 cumulative provider cap.

- [ ] Freeze public source-separated visual/report workflows and scoring. Add meaningful scorer,
      provenance and source-leakage tests. Prepare edited fixture videos; record natural-video scope.
- [ ] Run actual API development workflows with guarded real resolver/embedding/planner calls;
      inspect each stage and actual final answers. Record baseline failures before implementation.
- [ ] Reproduce failures deterministically, implement minimal general backend fixes, and run
      targeted regressions. Freeze selection before heldout, preserving existing models by default.
- [ ] Run heldout, restart/ambiguity and spoken-tool boundary checks. Report failures explicitly;
      broaden with permitted natural public clips and offline existing local-media checks.
- [ ] Update R29/milestones/architecture decisions as appropriate, run full checks, commit regularly
      on work/memory-reliability, and optionally back up only that branch. No new PR/merge yet.
