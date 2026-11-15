# R28 — Preserve decoded imports and recover interrupted indexing

Date: 2026-11-16. Owner: inline. Status: bounded implementation and verification complete.
Decision: keep a saved, decoded import after indexing failure and permit explicit reuse after
restart. No UI change, automatic inference retry, new provider, dependency or recording deletion.

## Failures reproduced

An actual synthetic video imported through the API decoded successfully, then a deterministic
encoder outage failed indexing. Cleanup removed the saved video copy as well as its derived
frames. The new regression failed on source preservation before the repair. The invalid-video
cleanup test is separate and remains enforced.

A second failing regression interrupted an indexing generator after one committed batch, then
reopened the app with a model factory that must not be called. The stale import remained
`indexing` indefinitely. Captured segments already have their own journal/recovery protocol;
imports must not be disguised as captured segments or assigned invented capture clocks.

## Bounded repair

Once frame extraction succeeds, an imported saved copy survives subsequent embedding or index
persistence failures. Failed frame rows/derived output still clear and failed sources stay out
of search and media serving. Undecodable new uploads retain the previous cleanup behavior.
Managed sources are never replaced by the retry operation.

On startup, interrupted non-capture index rows become failed with an explicit restart reason;
partial frame rows clear. This is metadata recovery, not model loading, automatic inference or
an assertion that an incomplete source is usable. Captured segments retain their existing
capture-journal recovery path.

Backend-only `POST /api/videos/{video_id}/retry-index` accepts a failed import whose retained
source is in its managed recording path. It reuses its ID, name, original capture timestamp and
sampling interval, through the existing bounded indexing worker. It returns the normal202 job ID.
It refuses unknown, ready/in-progress, missing/empty/unmanaged and capture-owned sources. A
capture-session marker is sufficient to refuse this route even if that journal entry is absent.
Concurrent duplicate retries are refused. No frontend control was added or changed.

Retained failed media still counts toward the saved-video cap. Retry at a full cap needs no new
video copy; additional uploads are refused while the retained source survives. There is no
automatic expiry or raised cap. This replaces the old cleanup assertion for decoded media with
source-byte preservation while retaining all partial-evidence exclusion assertions.

## Verification

Synthetic API outage/restart/retry tests preserve hashes, IDs and original capture times. Tests
cover failure before the first embedding batch and after one committed batch, duplicate retries,
full-budget refusal, capture ownership, unavailable and unmanaged paths, unknown IDs and ready
sources. Existing captured-segment recovery/retry and invalid-video cleanup checks still pass.

A separate process executed real FFmpeg extraction and committed one batch, then terminated via
`os._exit(17)`. Reopening the app recovered failed/zero-frame state without loading inference.
Explicit retry completed with the same video ID and unchanged original/saved file hashes.
Artifact: data/runs/import-hard-exit-20261116/results.json. This is a real process interruption
with synthetic embeddings; it is not a power-loss/filesystem durability guarantee.

Synthetic Chrome cancellation, playback failure, library/candidate controls and reminder checks
passed with zero page errors (data/runs/import-recovery-browser-20261116/results.json).
Python3.12.11/macOS arm64, locked dependencies and FFmpeg8.1. **547 tests passed in25.47s**,
with Ruff lint/format (117 files), three JavaScript syntax, local Markdown link and diff checks. Author review only; no independent review, hosted CI, PR or merge claim.
No private footage upload, hardware capture or paid inference; conservative provider accounting
remains about$3.21/$5.

## Limits and next gates

This covers sources saved and decoded by indexing. A model-initialization failure before any
copy/index record is created still follows the temporary-upload cleanup path and requires
re-upload from the caller's original file. It is not claimed to have this retained-source retry
capability. Resume restarts extraction/embedding rather than resuming a partial vector batch.
Unavailable/corrupted retained sources fail honestly and remain preserved; this does not repair
media. No capture clocks are inferred from import/retry time. Recognition, false wakes, real
human speech and long-duration household acceptance remain open product gates.
