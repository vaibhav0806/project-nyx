# R27 — Full local playback and unreadable-source recovery

Date: 2026-11-16. Owner: inline. Status: bounded engineering pass complete.
Question: Can all saved local videos decode, and does damaged evidence prevent useful recall?
Decision: isolate source decode failures without hiding provider errors or asserting absence.

## Local audit

The existing library contains 92 recording files, all registered in the 92-row video index;
there are no unregistered files in its recordings directory. Read-only SQLite backup supplies
the audit's copied index. Strict FFmpeg video decoding (`-xerror -err_detect explode`, audio
excluded) read all video frames for all 92 sources successfully. Before/after SHA256 matched
for every source. No recording, original index, transcript or capture clock was modified.
No private image/audio/vector was sent to a provider. No camera/microphone was opened.

Artifact: data/runs/full-local-integrity-20261116/results.json. The expanded local audit records
its decode mode and checkpoints results per source. Command:

```sh
uv run --no-sync python -m experiments.companion.local_replay_audit --data data/cloud-demo --output data/runs/full-local-integrity-reproduction --limit 256 --full-decode
```

Output must be new. The bounded limit covers this 92-file library; it is not an unlimited scan.
Strict codec decoding is not a human assessment of image/audio quality, semantic recognition,
physical identity or timestamp correctness. Audio integrity was not evaluated. A good library
snapshot does not guarantee future capture or ten-day continuous operation.

## Reproduced failure and general repair

Synthetic fixtures reproduce a same-size damaged newest recording with an older valid source.
All six initially failing checks (three routes × partially/all-damaged histories) aborted on
source decoding, before usable older evidence could be returned. These are actual indexed
synthetic videos, not canned runtime cases or substitutions for private data.

Source decoding now has a narrow failure boundary: unreadable, missing or timed-out frames are
uncertain/unavailable, with no location and `model_checked=false`. History continues within its
existing candidate bounds. Valid candidates keep their original ordering, IDs, offsets and
capture times. All-damaged histories return uncertainty with an explicit unreadable-frame note;
no failed frame is treated as a negative observation or passed to a model. Scope separately
counts attempted/unavailable/model-checked frames and request metrics exclude skipped inference.
This applies to overlapping source-frame checks, image-batch fallback and reference comparisons.

The catch encloses only decoding. Model/provider exceptions still propagate; no unsupported
positive is reused on outage. Source path containment still fails before decoding. Batch
cardinality checks remain strict. Metadata policy is `unavailable-not-negative-v1`.
No source is deleted, permanently marked bad, reindexed or silently repaired by this change.
Restoring an original file restores its normal eligibility on the next lookup.

## Verification

Six source-failure regressions observed RED, then GREEN after the repair. Additional tests check
that decode timeout never calls a provider, provider failure propagates, and original audit
bytes/databases survive both first-frame and full-video audit modes. A real TestClient/API worker
check returns the older valid source after damage; restoring bytes and reopening the app returns
the newer source without reindexing. External inference is synthetic in these checks; this is
backend recovery evidence, not recognition accuracy.

**538 tests passed in 24.86 seconds.** Ruff lint/format passed (117 Python files), three JavaScript
syntax checks and diff checks passed. Synthetic Chrome capture/speech/cancellation, playback
failure, library/candidate controls and reminder checks passed with zero page errors. Artifact:
data/runs/source-failure-browser-20261116/results.json. UI files remain byte-identical to stable
cfe8fa4. Author review only; no independent review, hosted CI, PR or merge-readiness claim.
No paid inference in this pass; prior conservative spending remains about $3.21/$5 total.

## Remaining product gates

This removes an avoidable backend failure; it does not repair damaged media or add whole-file
checksum validation to every live query. Capture availability still uses registered byte counts,
not cryptographic identity. Candidate limits and gaps still bound last-sighting claims. Visual
category confusion, physical identity/location accuracy, false wakes/homophones, real-room human
speech and long-duration operation remain open. Existing source-preservation, 1 GiB cap, branch,
UI and private-media boundaries remain. The product is an improved working prototype, not a
validated dependable household assistant.
