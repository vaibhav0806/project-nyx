# Visual and spoken depth implementation plan

> Execute inline with superpowers:executing-plans; no subagents. Latest user authorization covers
> the remaining testing and general backend fixes, with no repeated approval gate.

**Goal:** Broader measured visual/spoken workflow reliability, not fixture-specific passing rules.
**Architecture:** Existing Python/SQLite/LiveKit app; isolated public/synthetic experiment harnesses.
**Tech stack:** Locked Python environment, Pillow, existing OpenRouter/LiveKit providers.
**Spec:** [Design](../specs/2026-11-15-visual-spoken-depth-design.md).

## Constraints and review focus

Work/memory-reliability only, no main/UI edits, preserve data/cap, cumulative $2 test ceiling.
No hardware/private-media tests or external messages. Keep source/prompt/model identities in
artifacts; no annotation proxy as final-answer accuracy. Runtime must never import fixture data.
Inspect missing/ambiguous object labels, unsafe positives, provider errors, out-of-order speech,
turn ownership, source attribution and stale responses; avoid silent success or repeated effects.

### Task 1: Broader visual baseline

Files: experiments/companion/visual_cases.py, visual_verification_replay.py, scorer tests.
- [x] Freeze source-separated positive/negative/count labels and test scoring, identity and failures.
- [x] Run RED, implement bounded manifest/runner/scorer using actual CloudVerifier and guarded client.
- [x] Run development Lite/Flash comparisons with original inputs/prompt; retain heldout for selection.
- [x] Audit errors manually, record R22 method/results/limits and commit.

### Task 2: Spoken workflow faults and general fixes

Files: tests/test_realtime.py, relevant new protocol tests; realtime.py/speech.py only for failures.
- [x] Read primary provider protocol and SDK behavior, then reproduce boundary faults before fixes.
- [x] Add meaningful reorder/interruption/tool/restart regressions across household utterances.
- [x] Implement minimal general corrections; run focused/full tests and commit.

### Task 3: Selected visual and spoken comparisons

- [x] Select only evidence-backed model/prompt behavior, with regression tests for policy changes.
- [x] Run heldout visual conditions and expanded household/spoken tools, counting failures and spend.
- [x] Preserve safety/recall/latency tradeoffs; leave mixed experiments opt-in rather than force a win.
- [x] Record R22/R23 results and commit.

R22's stronger model and prompt candidate exhausted their per-run guards, with unrun cases
retained in denominators. The prompt candidate was rejected and baseline visual behavior kept;
there is no paid selected-visual holdout run to claim. Native household development/heldout
dispatch checks and later semantic diagnostic/fresh-evidence checks are separate from real
household/acoustic acceptance. Final wake ablations did not justify a runtime change.

### Task 4: Final verification and branch backup

- [ ] Review inline; run full tests, lint/format, JS, links/diff and synthetic browser as relevant.
- [ ] Update milestones/architecture/decisions; explicitly retain real household/acoustic/soak gates.
- [ ] Commit clean branch and optionally push it; verify main/UI unchanged.
