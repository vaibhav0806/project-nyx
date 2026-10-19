# History controls implementation plan

> Execute inline with superpowers:executing-plans; no subagents. The user authorized continuing the next M2 work after publishing continuous indexing. Existing footage must remain intact during verification. New work stays local until separately published.

**Goal:** Let a person explicitly delete a saved source and its derived data, and make longer-run recording checks repeatable.

**Architecture:** Keep the Python/browser stack. Record deletion intent in the existing capture journal before hiding/removing evidence. Serialize deletion against uploads and reject it while inference work is active. Retry pending deletions before startup recovery can requeue captures. Retain an ID tombstone to prevent duplicate upload resurrection; never expire media automatically.

**Tech stack:** Existing FastAPI, SQLite, local filesystem, plain browser assets, pytest and opt-in Playwright.

**Spec:** [Scope](../../scope.md), [M2](../../milestones.md), [Architecture](../../architecture.md).

## Constraints and review focus

- No automatic deletion, real-camera activation, cloud media, new dependency, or unrelated refactor.
- Delete only managed source/thumbnail locations after validating containment; do not follow symlinks out of the workspace.
- Failures/restarts must not expose partially deleted evidence or permit the same capture sequence to recreate it.
- Unrelated recordings and their search results must survive; released storage and coverage must reflect removal.
- Reject active inference/upload conflicts with a useful retry message. Stop recording before deleting in the UI.
- Old results, scope filters and playback must clear after successful deletion. A cancelled confirmation changes nothing.

## Task 1: Durable source deletion

Files: `src/nyx/memory.py`, `src/nyx/recording.py`, `src/nyx/app.py`, `tests/test_app.py`.

Interfaces: `Store.hide_video(id)` / `Store.delete_video(id)`; `CaptureJournal.request_deletion(id, path)`, `deletions()`, `finish_deletion(id)`; `Workspace.delete_video(id)` / `recover_deletions()`; `DELETE /api/videos/{id}` returns `{id, deleted: true}`. Captures with no loaded/working model must also be removable. Request IDs must be registered sources or existing deletion tombstones.

- [x] Write API tests proving source/thumbnail/vector removal, unrelated source preservation and reopened search exclusion.
- [x] Write capture tests proving saved-but-unindexed removal, coverage/storage reduction and duplicate upload remaining deleted.
- [x] Write failure/restart test: filesystem removal fails after intent persists; media/search become unavailable, next startup finishes without loading a model.
- [x] Write busy/origin/invalid-ID/path-containment tests; run them and confirm expected failures.
- [x] Implement minimal journal tombstones and coordinated deletion, then pass the full suite.

## Task 2: Browser controls and longer-run checks

Files: `src/nyx/web/app.js`, `src/nyx/web/style.css`, `tests/browser_smoke.py`, canonical docs.

- [x] Add a separate Delete button per settled clip, with confirmation naming the source and permanent derived-data removal. Require capture stopped and disable during a foreground task.
- [x] Include saved failed captures in the history controls; clear old search/replay/scope on success and refresh coverage.
- [x] Extend synthetic-camera smoke check to cancel deletion, perform it, verify old media fails, and retain unrelated clips. No user recordings are used.
- [x] Add an optional recording duration and sample server RSS, backlog and search latency during the synthetic run. Report server RSS separately from total system memory; do not equate synthetic timing with hardware reliability.
- [x] Run the browser check with a longer synthetic recording, inspect desktop/mobile screenshots, then run deterministic tests/lint/syntax/build/link checks.
- [x] Update milestone evidence and provide an actual-camera thirty-minute protocol. The actual-camera gate stays open.

## Actual-camera thirty-minute protocol

The person running this check explicitly enables their camera; automated checks never do so.

1. Keep the laptop plugged in with sleep disabled for the uninterrupted baseline. Start recording, note the time, and deliberately show/move/remove three objects at written times. Include a similarly shaped distractor and a query for an absent object.
2. For thirty minutes, search every few minutes while capture continues. Check the latest saved/searchable timestamps and backlog; record task latency plus Activity Monitor CPU/memory and video bytes at start/end. Model cache/thumbnails are additional to the video budget.
3. Pause/resume once, then Stop and let indexing finish. Restart the local server and verify the selected object moments still replay at matching offsets, the pause remains visible and capture does not reopen automatically.
4. Test actual sleep/background behavior separately and expect an interruption/uncertain coverage rather than assuming continuous capture. Never interpret a missing retrieval match as absence.
5. Use a disposable recording to check cancelled/confirmed deletion and its search/playback disappearance after restart. Do not remove valued footage for a test.

## Execution evidence

- Inline implementation; no subagents. Deletion API tests were RED at missing route, then GREEN. A legacy-index regression reproduced stale thumbnail URL aliasing before the counter fix. Persistent cleanup failure reproduced startup failure before pending-cleanup recovery was made nonfatal.
- Ruling: deletion intent uses the existing capture journal rather than another file/service. Explicit Stop and no active jobs are required; a conflict returns 409 without changing media.
- Ruling: maintain a persistent increasing frame ID counter in existing SQLite metadata, seeded before legacy rows are removed. Without it, old frame URLs could return new unrelated evidence.
- Fresh isolated suite: **54 tests passed**. Lint, formatting, JavaScript syntax and package build pass; Markdown links/package assets checked separately.
- Offline real-model browser run `data/runs/web-history-001`: **75.68 seconds** continuous synthetic capture, **nine captured segments ready plus one imported clip** before deletion. Cancelled deletion preserved the import; confirmed deletion removed it, preserved unrelated captures and cleared old candidate/replay/filter state. Late camera permission cancellation, pause/resume, interruption, navigation/reload and mobile overflow checks passed with no uncaught browser errors. Desktop/mobile screenshots inspected.
- Four warm UI search round trips during capture: **0.320, 0.318, 0.322, 0.324 seconds**. Across 53 post-warmup samples, peak observed backlog was one segment and server-process RSS ranged **186.9–251.5 MiB**. These RSS samples exclude browser/FFmpeg and do not measure MPS/model allocation or total unified memory. The tiny changing-color synthetic scene does not represent room-video storage or semantic quality. No long-term memory-leak or p95 claim is made.
- Actual-camera thirty-minute/resource/restart evaluation and independent household labels stay open; no real room camera was activated in automated tests. Automatic expiry remains disabled. This follow-up was local at this validation checkpoint; the subsequent all-work publication request is recorded in [Decisions](../../decisions.md#publication-authorization).

Final inline review: a disappearing file during the storage scan reproduced a status failure; the scan now skips files removed concurrently. Incomplete-deletion playback remains disabled. All 54 tests pass after these fixes.
