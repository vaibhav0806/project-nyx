# Ten-Day Pilot Foundation Implementation Plan

> Execute inline using superpowers:executing-plans and test-driven-development.
> The user's standing instruction excludes subagents; the current go-ahead authorizes execution.

**Goal:** Preserve evidence across spoken tools and support dated object search across ten days.

**Architecture:** Bound evidence ownership to the active persisted turn, share existing action
validation, preserve browser source review, and add a 240-hour query window without expiry.

**Tech Stack:** Python 3.12, LiveKit Agents, FastAPI, SQLite, plain JavaScript, pytest.

**Spec:** [Ten-day pilot](../../pilot.md), approved direction 2026-11-03.

## Global Constraints

- Trailing 240-hour lookup; explicit all-history search preserves older-source access.
- 1 GiB video cap, stop without deletion. No automatic expiry or destructive recompression.
- Synthetic/fake-provider checks only; no paid calls, private-media access or devices.
- Preserve attribution, cancellation and existing data. Work inline in the authorized main checkout.
- Initially leave work local. On 2026-11-15 the user explicitly authorized publishing the
  existing foundation to main after verification.

## Review Focus

- Statement tools must preserve visual dependencies and review from the same turn.
- Interrupted-turn late results must not contaminate the next turn.
- Spoken exclusions and earlier-than bounds must reach shared policy validation.
- Day-nine sources belong to a ten-day query; day-eleven sources do not.
- New turns and source deletion must clear obsolete review evidence.

### Task 1: Voice evidence ownership

Files: `src/nyx/realtime.py`, `tests/test_realtime.py`.
Interface: correlate pending tool IDs to their dispatch turn; persist unioned valid sources.

- [x] Add `serve()` regressions for visual-plus-statement source retention/deletion and late old-turn results.
- [x] Observe baseline failures before implementation.
- [x] Capture turn identity at dispatch, reject obsolete results, merge dependencies for the active turn.
- [x] Run `uv run --no-sync pytest -q tests/test_realtime.py`; require all passing.

### Task 2: Browser evidence persists across tools

Files: `src/nyx/web/companion.js`, `src/nyx/web/voice.js`, `tests/test_conversation_ui.py`.
Interface: retain per-turn visual review until a new question or source invalidation.

- [x] Add a browser regression for visual then statement tools, new question and deletion.
- [x] Observe source-panel failure; preserve review for nonvisual tools of the same turn.
- [x] Run `uv run --no-sync pytest -q tests/test_conversation_ui.py`; require all passing.

### Task 3: Ten-day lookup and spoken constraints

Files: `src/nyx/agent.py`, `src/nyx/verification.py`, `src/nyx/realtime.py`,
`tests/test_agent.py`, `tests/test_companion.py`, `tests/test_realtime.py`.
Interface: history accepts 240 hours; widening reaches ten days; voice passes exclusions/bounds.

- [x] Add day-nine/day-eleven dated API evidence, widening and spoken argument dispatch regressions.
- [x] Observe baseline failures; extend validation, widening and tool arguments/descriptions.
- [x] Run `uv run --no-sync pytest -q tests/test_agent.py tests/test_companion.py tests/test_realtime.py`.

### Task 4: Verification and status

- [x] Run full pytest, lint/format, JavaScript syntax, Markdown links and diff checks.
- [x] Rerun the R12 offline probe and record changed outcomes and remaining limitations.
- [x] Review the diff inline for deletion, stale turns, bounds and preservation.
- [x] Update canonical documentation and milestones with exact results.

## Follow-on workstreams

This is the first bounded delivery in the approved three-workstream direction. Follow-on designs
cover claim corrections/ten-day held-out replay, event retention and source expansion,
capture/index/voice recovery, and a measured native/local comparison. Continuous ten-day recording
requires the capacity/preservation choice in the spec before increasing the disk budget.

## Execution evidence — 2026-11-03

Tasks 1–4 completed locally. Regressions were observed failing before their fixes: source
accumulation, old-turn isolation, persistent browser review, ten-day widening/API lookup,
candidate/trace preservation and metadata transport. Final full suite: **384 passed in 20.65s**.
Lint/format, JavaScript syntax and diff checks pass. R12 probe confirms both source failures
fixed and preserves the still-failing small-object example as follow-on evidence.

Ruling: keep work inline without subagents, as instructed by the user; review the diff directly.
Ruling: add an upper bound at search time after a synthetic future-dated source displaced valid
day-nine evidence; preserve the existing strict earlier-than bound when it is tighter.
Ruling: return candidate IDs/time/exclusions to the spoken model and preserve the multi-tool
conversation plan; exposing new arguments alone would leave follow-ups without usable IDs.

Inline review covered source invalidation, interrupted turns, bound validation, data preservation
and the five Review Focus cases. No schema migration, provider change or disk-budget change.
This is an author self-review, not an independent review or a merge-readiness attestation.

## Publication verification — 2026-11-15

The user requested publishing the latest existing work to main. Fresh verification:
384 tests passed in 20.21s; lint, format, JavaScript syntax and diff checks passed.
The offline probe still reproduces the small-object selection miss. No new retrieval
algorithm, provider or storage policy is part of this publication.
