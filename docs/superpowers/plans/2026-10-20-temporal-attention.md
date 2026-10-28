# Temporal attention and action gate implementation plan

**Goal:** Ignore isolated visual disturbances, preserve lasting changes and sustained
activity, and separate an event interpretation from permission to deliver a requested
departure reminder.

**Authorization/spec:** The user approved the window and event/action approach in the
conversation on 2026-10-20 and explicitly requested implementation. This extends the
[companion design](../../design.md) within the existing next-departure slice. General
personal memory and scheduled reminders remain deferred. Execute inline, with local
commits and no push; no subagents or new approval round.

**Architecture:** Keep the Python application, worker and existing NumPy/Pillow/Qwen
stack. Share a cheap elapsed-time activity window between live observation and
automatic indexing. Keep temporal nomination, model interpretation and request/action
eligibility separate. Explicit current-view requests bypass background filtering.

**Engineering starting values:** 10 Hz target cheap sampling; 0.5 s persistence with
at least three observations; 0.8 s quiet period to close an episode; gaps over 0.5 s
reset continuity; at most one nomination every 3 s while meaningful activity continues.
These are initial policy settings, not measured household thresholds. Keep at most
64 recent live frames and 6 s of context; inspect three exact timestamped samples.

## Constraints and review focus

- Keep full recordings and the 1 GiB stop-without-deletion rule. Dense selection can
  miss subtle events and each independent recording segment retains an anchor.
- A 0.1 s change followed by the original scene should not nominate embedding/model
  work; a fast placement leaving a persistent object should qualify after observation.
- Do not infer persistence across dropped samples, sleep or camera/session changes.
- Group activity under an episode ID; recheck a continuing episode only for further
  scene change. Do not lose a nomination merely because the worker is occupied.
- Model-positive output is fallible. Gate actions against active requests, temporal
  qualification, visual cue fields, freshness and cancellation; preserve replay and
  separate delivery/acknowledgement state.
- No cloud vision, real-device automated tests, new model/framework, RAM optimization
  project, or claim of reliable departure recognition.

## Task 1: Shared temporal filter and saved-frame selection

Files: new `src/nyx/activity.py`; `src/nyx/attention.py`, `src/nyx/retrieval.py`;
new `tests/test_activity.py`, existing `tests/test_attention.py`.

Interfaces: `ActivityWindow.observe(image, at)` returns state, episode ID,
qualification and timing. `select_activity_frames(frames)` selects original
timestamp/path rows. Continuous automatic indexing decodes at 0.1 s and records the
new sampling policy; manual imports/CLI periodic behavior stays compatible.

- [x] Write failing behavior tests for flashes, persistent placement, sustained motion,
  quiet closure, repeated disturbances, cadence gaps and before/after selection.
- [x] Run those tests and confirm expected failures; implement the smallest shared
  window and selector; rerun targeted tests.
- [x] Verify actual FFmpeg offsets and preserved source bytes with generated video.

## Task 2: Live observation and request/action eligibility

Files: `src/nyx/observation.py`, `src/nyx/companion.py`,
`src/nyx/intentions.py`, `src/nyx/web/companion.js`; observation/API/browser tests.

Interfaces: `Observer.feed` collects and nominates qualified episodes;
`Observer.accept` records actual job admission. `departure_action` returns an
explicit act/wait reason and eligible request IDs. Pass episode/timing/gate evidence
into the durable delivery boundary.

- [x] Write and run failing tests for suppressed flashes, lasting changes, one episode
  with meaningful rechecks, busy-worker recovery, source timestamps and invalidation.
- [x] Implement bounded live context, 100 ms browser sampling, phase/reason display,
  explicit request/action gating and stable episode IDs.
- [x] Test uncertain/inconsistent interpretation, no request, new/cancelled requests,
  stale inference, explicit current questions and no repeated delivery.
- [x] Run isolated browser checks with generated media, including a brief flash that
  must not trigger and a later sustained change that must deliver.

## Task 3: Conversation evidence, experiments and accurate documentation

Files: `experiments/companion/`, `tests/test_agent.py`, research/status/design docs.

- [x] Audit existing real-model versus deterministic coverage. Add a bounded real
  planner scenario runner that scores query attributes and multi-step search paths,
  with controlled tool observations explicitly labelled as doubles.
- [x] Replay synthetic temporal scenarios and selected existing public clips through
  the real window; measure nominations/rechecks and record misses as well as passes.
- [x] Run the full deterministic suite, lint/format, JavaScript syntax, synthetic
  browser integration and local Markdown-link checks. Keep local-model experiments
  separate and sequential; report resource-limited runs honestly.
- [x] Update decisions, architecture, scope, walkthrough, milestones and R8 with
  measured evidence. Commit coherent tested work locally; do not push.

## Execution ledger and rulings

- Task 1: temporal behavior tests failed on missing functionality before implementation,
  then passed. Actual generated-video decode/index checks preserve original bytes and
  offsets while excluding the flash and retaining placement context.
- Ruling: retain the nominal `interval_seconds` field for retry compatibility; record
  the denser actual scan in `sampling_policy` and original decoded offsets in frame
  records. Existing ready sources are not silently reindexed.
- Task 2: the live route uses admission-aware nominations, stable episode IDs and an
  explicit request gate. Synthetic browser checks passed flash suppression followed
  by reminder speech, cancellation, acknowledgement and denied playback. Dense local
  Qwen replay still falsely triggers on the entering case; that acceptance gate is open.
- Ruling: retain the existing departure model and report its failure. This slice
  implements narrow request relevance, not a general event-importance classifier.
- Task 3: expanded real-planner checks exposed repeated current/history actions and
  present/history routing errors. Regressions failed before fixes. Keep at most two
  decision repairs within six steps and record explicit policy adjustments, including
  widening an identical repeated history query. Do not add LangChain or a memory layer.
  Latest real-planner development run passed ten narrow cases with controlled tools;
  R8 keeps earlier failures and scoring changes distinct.
- Inline review reproduced a 4:3 camera being rejected by the live endpoint because
  snapshot scaling limited width alone; generated 4:3 browser verification now covers
  both bounds. An exact 0.5 s float boundary also has a regression and microsecond
  tolerance, without relaxing meaningful continuity gaps.

- Final verification: 192 deterministic tests; lint/format/JavaScript checks; generated
  4:3 camera/reminder browser scenario; offline wheel with nine current runtime
  modules/assets byte-matched; local Markdown links checked. No source/model/media
  publication or hosted provider call. All work remains local pending any future push.
