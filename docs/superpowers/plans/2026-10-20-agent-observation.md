# Agent and continuous observation implementation plan

**Goal:** Demonstrate conversational object finding and a next-departure reminder through one local companion loop.

**Authorization:** The user approved these two workflows and requested autonomous implementation and experiments on 2026-10-20, then authorized coherent local commits with no push. Work inline; no publication, real camera/microphone tests, cloud visual processing, or purchases. Existing 1 GiB original-video retention remains unchanged. General fact recall, timed reminders, identity recognition and hardware are outside this slice.

**Architecture:** Keep the single Python application and existing worker. Reuse pinned Qwen for bounded JSON tool decisions and local sequence inspection; SigLIP remains the visual retrieval encoder. Cheap local change detection selects historical frames and live observation bursts. Persist intentions and delivery attempts separately from evidence. Browser live observation must not wait for segment indexing.

**Resource constraints:** Actual checkout machine has 16 GiB unified memory and about 26 GiB disk free, unlike the earlier 24 GiB research machine. No preexisting runtime/data/model cache was found in the default locations. Reuse existing locked dependencies; download only pinned models required for measured checks. Preserve at least 8 GiB disk headroom and target under 10 GiB new downloads/artifacts.

## Tasks

- [x] Adaptive sampling (`attention.py`, `capture.py`, `retrieval.py`): test static reduction, small local changes, before/after frames, heartbeat coverage and unknown dates; implement an inexpensive image-difference baseline, compare on controlled videos, retain fixed sampling CLI compatibility and explicit sampling metadata.
- [x] Durable event requests (`intentions.py`): test idempotent creation, restart, cancel, atomic one-delivery claim, expiry of stale events, delivery failure/acknowledgement and replay. A next-departure request is not a cron job. No audible exactly-once claim across crashes.
- [x] Local bounded agent (`agent.py`, `verification.py`): test multi-tool current→recent→older search, contextual correction, explicit time bounds, evidence-only completion, cancellation and loop limits. Local planner sees a bounded recent conversation and tool observations, not all raw history. Add API and a typed conversation surface sharing the same tools as voice.
- [x] Continuous observer (`observation.py`, `verification.py`, browser assets): test bounded fresh chronological bursts, camera/session ownership, pause/restart reset, negative/uncertain sequences, motion without departure and no repeat notification. Local model checks visual departure cues only for active requests; show model uncertainty and delivery state. Do not infer identity or departure from disappearance alone.
- [x] Integrate browser/voice: fresh snapshots, voice context, interruption, explicit reminder status/cancel, local observer state and optional Sarvam speech for a user-requested reminder. In-flight local inference remains nonpreemptible. No new paid provider probes.
- [ ] Scenario checks and documentation: deterministic suite, real pinned local model experiments on permitted public/synthetic fixtures, isolated browser tests with fake devices, measured resource/latency reports, docs/decisions/milestones consistency. Record failures as well as positive examples.

## Review focus

1. A recent weak match cannot become a current fact; unknown capture time stays unknown.
2. A model or stale queue must not deliver a reminder after cancellation or from old footage.
3. Duplicate frame selection must not imply continuous verified object presence.
4. Agent final text must use authoritative tool evidence, with source-deletion invalidation.
5. Stop/pause/mute/cancel/reload must not leave unseen observation or repeated speech running.

Execution proceeds inline under the user's explicit instruction to keep working while unavailable. Test behavior before implementation; record measured limitations rather than marking M1–M5 complete prematurely.

## Execution ledger

- Baseline initially failed because the system Python omitted SQLite extension loading. Switched the environment to uv-managed Python 3.12.11; the existing suite then passed without application workarounds.
- Adaptive sampling and durable intentions: new tests failed before implementation, then passed. Chose local block image differences with existing NumPy/Pillow before adding OpenCV; this avoids a dependency until a measured comparison warrants it. Per-segment anchor samples preserve offsets; selection is not evidence of unchanged semantics.
- Agent and live-observation APIs: tests failed on missing routes/modules, then passed. Local Qwen text planning required multimodal content-list formatting; real probes after the fix selected current inspection, departure reminder creation and chat appropriately. These three requests do not establish overall planner quality.
- Baseline plus current new tests: 129 passed. Local model downloads and runtime setup left approximately 19 GiB free. Models run unquantized; no additional model or cloud provider is needed yet.

- Browser integration: typed companion and default local-agent voice flows pass with isolated generated media and deterministic visual/provider boundaries. Native local ASR is exercised separately. No provider calls were made. Current local model trial 004: snapshot lookup 7.62 s, recent-history follow-up 19.60 s, departure request 3.82 s, cancellation 6.03 s; single samples only.
- Real sequence checks exposed misses, entering/stationary/closet false positives and potentially late notification. Prompt/schema constraints are not evidence of correct departure. A second text-only classifier was tried and not integrated because it retained errors while losing positives. The acceptance gate remains open; R8 records the diagnostic runs.
- Inline review added regressions for cancellation/time limits between history images, snapshot ageing during final planning, explicit unsupported clock-time requests, replay of cancelled requests, expired/restarted notifications and persisted tool/model metadata. Latest suite: 144 passed, lint/format and JavaScript syntax checks passed. A 30-minute synthetic recording/search soak is in progress.

- Follow-up regressions cover unknown-date imported matches, live checks preceding queued background work, one bounded correction of a nonexistent completion reference, and old active requests remaining visible. Latest full suite: 148 passed. Actual API replay created a pending notification in 3.93 s but also falsely triggered on entry; recognition acceptance remains open. Native video and labelled-image comparisons are recorded in R8 and were not promoted.
- The first 30-minute capture/search phase reached 182 indexed segments; its later deletion check exposed a browser limit hiding sources beyond the newest fifty. Added explicit older-source access, observed the browser regression fail before and pass after, and preserved phase results earlier in the harness. Process restart retained 183 sources and working candidate search/range playback. A corrected full soak is running; do not claim its outcome yet.
