# Continuous recording and background search

Authorized: user explicitly requested this after demonstrating real-scene cookie-packet, phone, keys and raised-hand retrieval. User selected a 1 GiB saved-video budget; stop at the limit and preserve existing clips. Execute inline without subagents. The user separately requested publication of the manual baseline: `67fcaf5` is pushed to `main`; the user subsequently tested this continuous slice for 2–3 minutes and requested publication to `main`.

Spec: [Scope](../../scope.md), [Architecture](../../architecture.md), [Milestones](../../milestones.md). This implements the next M2 slice, not visual verification or voice.

## Engineering choices

- Keep the existing browser/FastAPI/PyTorch/SQLite stack. Finalize independent approximately ten-second video-only segments. Start the next recorder on the same camera stream before stopping the previous one; boundaries may overlap and are not assumed exact. Raw MediaRecorder timeslices are not independently playable by specification: [W3C recording contract](https://www.w3.org/TR/mediastream-recording/#mediarecorder-methods).
- Upload each completed segment automatically with a session ID, sequence, recording timestamps and stable segment ID. Persist segment metadata and state in a separate `capture.sqlite3` journal so admission does not require a loaded model. Store original video once, under managed recordings. Retry the same sequence idempotently; failed/partial uploads never become searchable.
- Bound server backlog to eight saved segments and browser upload buffering to three segments. Stop on admission/upload failure rather than losing footage silently. One cooperative inference worker yields after small image batches; queued search runs before the next background batch. Model loading/current batch cannot be preempted.
- Display recording state separately from saved/indexed coverage and failed/interrupted segments. Keep search and a separate source replay player available during capture. Pause releases the camera; resume requires explicit action. Keep recording when the tab is merely hidden, but stop on camera loss, page exit or detected suspension; report uncertainty/gaps rather than claiming uninterrupted coverage.
- The budget covers managed original-video bytes including existing clips, not model cache/thumbnails. Refuse uploads at the budget or low free space; no automatic expiry/deletion. Display the distinction. Retention policy/source-aware deletion remain later M2 work.
- On startup, mark live sessions interrupted, remove incomplete uploads and requeue saved/indexing segments. Stable IDs make replay after a crash idempotent. Never automatically reopen a camera. Browser-exit tail delivery is best effort and must remain explicitly uncertain.

## Tasks

- [x] `memory.py`/`retrieval.py`: stable recording IDs and resumable, batch-yielding indexing; preserve originals on captured-segment failures. Keep CLI import behavior and compatible existing indexes.
- [x] `recording.py`: durable sessions/segments/events, original-byte budget, bounded admission, idempotent retry and restart recovery. Test timestamps, quota, duplicates, interrupted uploads and orphan cleanup.
- [x] `app.py`: cooperative priority worker; capture start/status/heartbeat/pause/stop/segment endpoints; status and replay work without blocking inference. Tests prove search runs between index batches and saved segments recover across app restart.
- [x] `web/app.js`/`index.html`/`style.css`: automatic rolling capture, bounded upload/retry, independent replay, pause/resume/stop, current saved/searchable ranges and gaps. Preserve file import. No camera access on load; all synthetic/browser checks avoid real camera activation.
- [x] Run deterministic tests, real-model multi-segment browser recording/search/replay, failure/recovery checks, syntax/lint/build and author self-review. Update canonical docs with measured results and remaining M2 gaps.

Review focus: recorder chunks must actually decode separately; late stop/upload callbacks must not restart capture; duplicate delivery must not duplicate searchable frames; incomplete jobs must remain unsearchable; search priority must work under active indexing; old user footage must survive schema/setup changes and app restart. A short controlled run does not satisfy the pending thirty-minute hardware soak.

## Execution evidence

2026-10-19, M4 Pro / 24 GB, pinned SigLIP 2 checkpoint and MPS, Chrome 155.0.8059.80:

- Fresh isolated `uv run --isolated --extra web pytest -q`: **44 passed**, without downloading/loading vision weights. Tests cover priority between inference batches, stable-ID replay, duplicate delivery, actual sampled coverage, interrupted uploads, staged-save recovery, app restart, preserved originals on quota/model failure and unknown clock time for interrupted tails.
- `ruff check`, `ruff format --check`, `node --check`, `uv build`, packaged browser/module inspection, Markdown links and `git diff --check` pass.
- Offline real-model browser run: `uv run --no-sync python tests/browser_smoke.py --video data/runs/siglip-crops-005/scenes.mp4 --output data/runs/web-continuous-004`. Raw results/screenshots are ignored local artifacts at that output path.
- Two independent full segments decoded/indexed automatically while capture remained active; followed by a paused tail and resumed interrupted tail: **four captured segments ready plus one imported clip**. Full segments lasted about ten seconds; their latest sampled offsets were 8.285s and 8.282s. The interrupted tail retained source/offset search with unknown clock time.
- Search and separate replay succeeded during capture. Pause released tracks, resume reacquired video-only tracks, camera interruption stopped capture, simple tab hiding did not. Stop while camera permission was pending released the eventually returned tracks. Navigation released tracks and reload did not request camera access. No uncaught browser errors; desktop/mobile screenshots inspected and no mobile horizontal overflow.
- Only synthetic camera frames were used in automated verification. The earlier user demonstration provides developer retrieval evidence; no new room-camera footage was captured. Thirty-minute real-camera/sleep/resource checks, independent household labels, retention policy and deletion remain open; M1/M2 are not marked complete.
