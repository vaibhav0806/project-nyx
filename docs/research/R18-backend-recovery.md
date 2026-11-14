# R18 — Saved-source recovery and evidence invalidation

Date: 2026-11-15. Owner: inline implementation. Status: bounded backend fixes and synthetic
browser verification complete locally. Decision affected: reliable pilot recovery, unchanged UI.

## Reproduced failures and fixes

1. After model-loading or embedding failure, retrying the same capture segment returned its
   failed state without scheduling indexing again. The complete original file remained playable.
   An explicit retry now validates unchanged metadata and saved size, respects the pending-work
   limit, and queues that original file. It does not replace it with retry-body bytes. Missing
   uploads retain the existing upload-retry path; incomplete saved files are preserved and refused.
   Failed jobs are not automatically retried indefinitely or billed in an unbounded loop.
2. Deleting a video invalidated saved conversation sources and visual jobs, but a cached
   statement-only answer could still be retrieved through its completed job/request ID. Job
   invalidation now includes transitive `sources`, as well as visually checked video IDs. The
   stale result is removed and replay returns the failed job, not the deleted-source answer.

Both failures were reproduced by new failing tests before the fixes. Regression coverage uses
real SQLite, the actual API/job worker and a generated video, with fakes only at model boundaries.
The retry test covers model-loading and embedding outages. Additional checks cover restart/backlog,
incomplete originals, incompatible encoder/index metadata and source loss during optional spoken
context verification. Optional context refusal preserves a still-valid visual candidate.

Existing regression cases retain interrupted-upload recovery, queued/indexing restart behavior,
stop-at-budget without deleting old recordings, deletion cleanup recovery, stale snapshots, turn
ownership/cancellation, speech transport failures and bounded capture backlog. These checks do not
prove an uninterrupted ten-day run or arbitrary provider/network resilience.

## Backend choice

Keep authoritative SQLite retrieval and existing shared Gemini text/image vectors. The isolated
Hydra service passed scoped storage/auth/round-trip checks but its deployed row engine rejected
the tested native similarity expressions. There is no verified useful remote retrieval route to
integrate; do not label local ranking as Hydra retrieval. See [R14](R14-self-hosted-hydra.md).

## Existing-UI browser check

The old browser smoke script assumed the prior always-visible typing/source/settings layout.
Its first run failed on the hidden typing field, then a stale recording-label assumption; the
navigation was updated to use existing Type instead, Settings, View source and camera controls.
Only the test harness changed. Every file under `src/nyx/web/` remains byte-identical to `cfe8fa4`.

Fresh headless Chrome with synthetic canvas video/silent audio and deterministic model/provider
fixtures passed: automatic capture, brief-flash suppression, sustained-activity delivery, cancelling
pending reminder audio, acknowledgement, playback-denied failure, current-view source display,
pause/stop, 151-clip history pagination, candidate rejection, conversational rejection, source
reference clearing, user confirmation and conversation persistence after reload. No real devices,
private media or paid provider requests were used. Browser `pageerror` list is empty.

```sh
uv run --no-sync python tests/companion_browser_smoke.py --output data/runs/memory-reliability-browser-review --speech --review-fixture data/runs/memory-reliability-review-fixture.mp4
```

Artifact directories already exist; use fresh paths to reproduce. The review fixture is a generated
16-second 160×96 solid-green MP4 at 2 fps, not semantic object evidence. The earlier no-review run
is `data/runs/memory-reliability-browser-v4/results.json`; the complete review run records all
optional flags true. Screenshots/server logs/results remain ignored under `data/`.

## Recommendation and limits

Retain the bounded recovery fixes and source invalidation. Keep contributor UI unchanged and
make no publication/hosted-CI claim from local browser success. Next acceptance work is an actual
rehearsed, permissioned end-to-end recording, broader labeled memory/vision/speech examples and a
separate decision about storage capacity. Current recording/retention and spending boundaries
remain intact. See [R17](R17-memory-policy.md) and [R15](R15-sampling-coverage.md).
