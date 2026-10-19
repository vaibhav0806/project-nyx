# Manual local recording and search

Authorized scope: user requested continuation and confirmed no existing clip is available. Build the recording/import/search interface needed to collect the missing M1 footage. This starts a bounded portion of M2 while independent household evaluation remains open. Execute inline; no subagents, commits, cloud media or automatic camera access.

Spec: [Design](../../design.md), [Scope](../../scope.md), [Architecture](../../architecture.md).

## Design and engineering calls

Use FastAPI/Uvicorn on `127.0.0.1:8000`, with plain HTML/CSS/JavaScript served from packaged `src/nyx/web/`. No frontend build system or external assets. One background worker caches the encoder and serializes indexing/search; a busy request is rejected rather than accumulating inference jobs. Opening the app loads neither a model nor a camera.

The page has a large camera/replay area on the left and a clip library/search panel on the right. A muted blue/white palette (`#eff3f8`, `#ffffff`, `#1e3048`, `#5c6b7d`, `#335d9e`, recording `#ad3434`), system humanist sans text and large sentence-case controls support a calm evidence viewer. Source moments and recording state get emphasis; no marketing/dashboard decoration. Stack panels on narrow screens. This is developer inspection UI, not intended-user UX validation.

Browser capture is video-only after Start, capped at two minutes. Stop releases camera tracks and leaves a local preview; Index clip explicitly sends it to the same laptop's server. Discard removes the unsaved clip. File import preserves unknown capture time; browser clip time is reported by the browser clock. Unfinished uploads stay unsearchable. Limit uploads to 256 MiB, and serve source/thumbnail files only through registered evidence IDs. No room audio is recorded.

## Tasks

- [x] Add optional `web` dependencies and `nyx serve`. Implement `create_app` in `src/nyx/app.py`: streamed bounded imports, job status, serialized cached inference, list/search and evidence playback endpoints. Keep existing CLI working.
- [x] Add meaningful API tests in `tests/test_app.py`: index/search/reopen and range playback, unknown/known time, failed jobs and cleanup, single-job bound, invalid/empty/oversized/disconnected uploads, and evidence-ID/path boundaries. Use deterministic encoder at inference boundary; an initialization-pause wrapper exposes a real SQLite file-before-schema race. Missing app observed before implementation; race observed as a 500 before its lock fix.
- [x] Build the packaged local page and capture state transitions in `src/nyx/web/`. Capture never starts at load; stop/discard/navigation release tracks; capture interruption is visible. Search results stay unverified and link to original offsets.
- [x] Test the real browser import/search/replay loop with permitted fixture media and synthetic camera frames, including denied/interrupted capture, no actual room camera activation. Inspect desktop/mobile screenshots; run tests/lint/build and verify packaged web assets.
- [x] Update canonical docs and milestone evidence. M2 remains incomplete: continuous segments, pause/gaps/retention, deletion and restart recovery remain separate work. Record results and limitations here.

Review focus: cancellation/disconnection cannot strand upload files; only one inference job runs; original media must remain range-playable; upload/import time cannot replace capture time; recording state cannot imply continuous coverage across browser suspension or camera loss.

## Validation

- 29 deterministic tests passed in the working environment and an isolated environment with the web extra but without optional model dependencies. Ruff lint/format, JavaScript syntax, Python compilation and wheel/sdist build passed.
- Browser run `data/runs/web-smoke-006/browser-results.json`: Chrome 155.0.8059.80, cached model offline, real-model import/search, source seek at 14 seconds, synthetic video-only record/stop/index, capture-time preservation, denial/interruption, discard, tab hiding, navigation track release, reload persistence and 390px layout. No uncaught browser errors. Earlier browser runs exposed test-harness mistakes and a genuine mobile overflow; the latter was fixed. Desktop and fresh-mobile screenshots were inspected.
- Author self-review (inline per user instructions): checked first-index creation against concurrent library reads, worker/job bounds, failed/disconnected upload cleanup, evidence-ID file access, range playback, text escaping and camera lifecycle. Fixed the first-index race with a narrow store-initialization lock; its regression test failed with 500 before the fix and passes now. No further blocking issue found for this manual slice.
- Scope limits: synthetic camera verification does not validate physical camera hardware, actual household retrieval quality, suspend/resume reliability, the full two-minute duration under real load, or intended-user usability. There is no continuous coverage, durable task recovery, retention/deletion flow or disk budget. Model and web dependencies were downloaded; inference media stayed local. No actual camera, cloud voice, external messages, commits or pushes.
- Engineering calls: packaged plain assets instead of root `web/`, FastAPI/Uvicorn, a single cached inference worker and local session-only job status. These keep the manual demo small; continuous recording will need its own lifecycle and recovery work.
