# Milestones

Updated: 2026-10-20. **M1 household validation is pending; M2 continuous recording and background indexing are implemented locally. User authorized this expansion after successful manual retrieval.**

This is the single project progress tracker. Detailed implementation tasks are written for the approved next milestone when the user asks to build. Research can inform the plan without silently changing scope.

## Status

| ID | Milestone | Status | Depends on | Completion evidence |
| --- | --- | --- | --- | --- |
| M0 | Agree on design, scope, repo layout, and research plan | Complete | — | User reviewed in Zed and requested implementation to resume |
| M1 | Prove local visual retrieval feasibility | In progress | M0 + implementation instruction | [Measured public-image smoke baseline](research/R3-local-retrieval.md); independent household clips still needed |
| M2 | Build an inspectable recording/search slice | In progress | M1; manual capture enables its evaluation | [Continuous implementation](superpowers/plans/2026-10-19-continuous-recording.md), [history controls](superpowers/plans/2026-10-19-history-controls.md), and [R8](research/R8-companion-loop.md): thirty-minute synthetic recording phase, explicit deletion and large-library restart checks; hardware soak remains |
| M3 | Add verified visual answers and fresh inspection | In progress | M2; user explicitly requested M3 | [R4](research/R4-local-verification.md): local Qwen model checks, bounded temporal history and snapshot inspection; independent household/uncertainty evaluation pending |
| M4 | Connect natural voice and durable transcripts | In progress | M3; user selected Sarvam and hands-free startup | [Hands-free plan](superpowers/plans/2026-10-19-handsfree-voice.md), [R6 findings](research/R6-handsfree-voice.md): local wake + Sarvam + existing visual tools + transcripts; real-room, language, spoken barge-in and latency gates pending |
| M5 | Add personal recall and reminders | In progress | M4; bounded event slice authorized 2026-10-20 | [R8](research/R8-companion-loop.md): next-departure request/delivery prototype; event accuracy, general recall and timed reminders remain open |
| M6 | Evaluate the integrated laptop demo with intended users | Not started | M2–M5 + R1/R2 findings | No evaluation yet |
| M7 | Select and validate standalone hardware | Later | M6 + hardware decision | No hardware selected |

Owners are unassigned until a person accepts a task. Human research assignments live in the [Research board](research/README.md).

## M0 — Review the foundation

- [x] Document the current product intent and full laptop scope.
- [x] Separate established decisions, proposals, and unknowns.
- [x] Propose architecture and repository boundaries.
- [x] Write milestone acceptance conditions and research briefs.
- [x] User reviewed the package and requested work to resume.
- [x] Resume the first local visual-retrieval milestone; later choices remain open.

Deliverable: an agreed direction with open choices visible. Preparing these documents does not approve them.

## M1 — Prove local retrieval feasibility

Use an explicitly provided or permitted short video/image set before making the pipeline continuous.

1. Review the paused setup files, establish an isolated Python environment, and verify the selected runtime/device.
2. Create a small annotated evaluation set with present, absent, obscured, small, and duplicate objects across several moments.
3. Run a small aligned encoder and descriptive queries; retain exact timestamps and preprocessing/model identity.
4. Measure recall@k, wrong candidate examples, cold/warm latency, peak memory and indexing throughput.
5. Record results under R3, choose the baseline or explain why another approach is needed.

Done when: a reproducible run retrieves labelled moments, stores source-linked vectors in SQLite, and reports actual quality/resource results. Fixed gates should be agreed from these results before expanding the pipeline. A synthetic colored-frame test is not a semantic retrieval benchmark.

Evidence: [R3](research/R3-local-retrieval.md) records the baseline and crop comparison. Five-view crops did not improve occurrence recall@3/@5 on the public fixture; full-frame indexing remains the default. No household clip was available when asked. The user demonstrated matching cookie-packet, phone, keys and raised-hand results and then authorized continuous expansion. This developer demonstration does not close independent M1 evaluation.

## M2 — Make recordings and search inspectable

1. Establish the approved `src/nyx/` layout; reconcile the earlier draft tests and dependencies.
2. Import a local clip and display candidate frames with source offsets and playback.
3. Add explicitly enabled recording, timestamped segments, stop/pause, recording state and capture-gap reporting.
4. Add bounded background indexing, storage limits, retained-range display, and source-aware deletion.
5. Verify restart recovery and separation of import time from actual recording time.

Done when: a thirty-minute controlled recording can be searched and replayed at correct moments after restart, controls work, and incomplete/failed indexing cannot masquerade as verified history. Results remain labelled candidates.

Current delivery: explicitly enabled continuous video-only capture in approximately ten-second independently playable segments; automatic background indexing; interactive search and separate source replay; pause/resume; saved/searchable sample times and interruption history; bounded backlog; 1 GiB original-video cap without deletion; idempotent delivery and saved-work restart recovery. Existing manual imports remain compatible. Deterministic/API and real-model synthetic-camera checks are recorded in the [implementation plan](superpowers/plans/2026-10-19-continuous-recording.md).

User-reported check: automatic indexing worked during a 2–3 minute trial on 2026-10-19. This does not replace the thirty-minute resource/restart evaluation.

Explicit source-aware deletion and repeatable longer synthetic checks are implemented locally: 54 tests pass, and a 75.68-second real-model synthetic-camera run checked concurrent search, nine automatically indexed segments, confirmed/cancelled deletion and reload. See the [history controls plan](superpowers/plans/2026-10-19-history-controls.md) for measurements and limitations.

Remaining: retention duration, independent household labels and the thirty-minute actual-camera/resource/restart evaluation. Synthetic browser capture does not close those gates. Interrupted browser-exit tails may be lost and uncertain segments do not assert wall-clock coverage. Model cache/thumbnails are outside the original-video cap.

## M3 — Answer from visual evidence

1. Compare a small on-demand VLM on the retrieved candidates using the same labelled inputs.
2. Add fresh-frame inspection for current questions and source verification for historical questions.
3. Apply time filters and select the latest verified sighting for last-seen questions.
4. Add supported landmark guidance and clarify ambiguous duplicates.
5. Exercise hidden objects, camera movement, out-of-order model results and capture failure.

Done when: each current/historical answer links to the appropriate evidence and can state uncertainty. Proposed evaluation targets to review after M1: 27 useful correct answers in 30 current-location trials and zero invented current locations in 20 deliberate uncertainty cases. These are targets, not measured performance.

Current M3 slice: explicit aware time bounds and capture-plus-offset observation times; newest-first checking with bounded older semantic fallback; on-demand Qwen source-frame verification; source-linked answer/replay and nearby unverified context; explicitly requested snapshots with freshness checks. The UI describes the checked scope and never guarantees a complete last sighting or current location. [R4](research/R4-local-verification.md) records the small two-model comparison; [implementation plan](superpowers/plans/2026-10-19-visual-answers.md) records checks.

Remaining M3 acceptance work: labelled household current/history/uncertainty trials; independent landmark and duplicate-object checks; small/occluded objects, actual camera movement and complete temporal recall. Unrestricted natural-language time/event interpretation remains beyond this explicit-mode developer interface. No acceptance target above has been claimed met.

## M4 — Speak and retain conversations

1. Trial cloud voice in the intended language and choose a provider based on measured behavior.
2. Connect backend tools for current inspection and history search.
3. Add microphone controls, turn state, interruption/recovery and visible transcripts.
4. Persist attributed conversation records across session/app restart.
5. Measure end-of-speech to first useful answer with retrieval/verification included.

Done when: spoken questions, follow-ups and interruptions work end to end; the app does not confuse transcripts with visual evidence. Proposed current-location latency target: p95 below five seconds across 30 trials; report history queries separately and revise transparently if evidence demands it.

Current M4 slice starts camera and microphone with the configured page, detects the name locally, sends activated questions to Sarvam, invokes local current/history checks and speaks grounded answers. Independent mute, response stop and persisted attributed conversation text are available. This is the intended automatic product behavior, also for possible hardware; tests use fake devices. The feedback follow-up adds local wake checks during playback, brief conversational replies without vision, a ten-second active follow-up window and one pending utterance during processing. Playback interruption is synthetically verified; actual echo and full-duplex reliability remain open. No target-language/noise cohort or p95 claim is made. The original cold smoke took about 21 seconds; the feedback iteration measured two preloaded visual questions at 4.68/3.14 seconds after recorded-audio submission, excluding browser endpoint/playback time. See [R6](research/R6-handsfree-voice.md).

## M5 — Recall and follow through

1. Save explicitly stated facts and retrieve earlier assistant conversations with source attribution.
2. Support corrections/supersession and clarify uncertain references.
3. Parse reminder times, ask for ambiguity resolution, and read back the interpreted time/timezone.
4. Persist reminders, deduplicate repeated action requests, and support list/cancel/acknowledge operations.
5. Report overdue reminders after sleep/restart and preserve actual delivery state.

Done when: an earlier conversation/fact can be recalled in a new session, and a reminder completes the intended daily-life loop. Proposed history gate: 18 correct evidence-linked outcomes in 20 scripted history questions, including expected uncertainty cases. Exactly-once audible delivery across crashes is not assumed.

## M6 — Evaluate the laptop experience

1. Combine R1/R2 findings into three real daily-life workflows.
2. Run the controlled current/history/uncertainty tests and appropriate deterministic checks.
3. Run one hour of recording/indexing/conversation to measure storage growth, memory, CPU/GPU pressure, inference frequency, latency and provider usage.
4. Have at least two intended users try the workflows without coaching; record completion, misunderstanding and recovery per person.
5. Fix the highest-impact failures and produce a demonstration with source evidence.

Done when: repeatable results and limitations are written down, the integrated loop works for the chosen situations, and the user can decide whether it justifies a home/device pilot. A small trial is not broad market validation.

## M7 — Validate a dedicated device

Choose hardware only after measuring the laptop workload. Verify camera/audio, echo, storage, heat, startup, physical recording/mute controls, and power/network recovery. Repeat the same tasks and run an extended soak test. This milestone is outside the initial laptop build estimate.

## Updating progress

Use `Not started`, `In progress`, `Blocked`, `Ready for review`, or `Complete`. A blocked entry names the dependency and next useful action. A complete entry links a result, check, or demonstration and records material limitations. Never mark application milestones complete because a plan, draft test, package file, or download exists.


## Companion/event progress — 2026-10-20

The user authorized implementation and local experiments, then local commits with no push. The working branch adds a local tool loop for typed/spoken questions, contextual correction and recent-history selection, inexpensive adaptive frame selection, live observation independent of segment indexing, and durable next-departure requests with cancel/replay/expiry/playback/acknowledgement controls. [R8](research/R8-companion-loop.md) records measured evidence and failures; [the execution plan](superpowers/plans/2026-10-20-agent-observation.md) records scope and checks.

M3/M4 remain in progress: local-model development examples exercise tool selection and contextual follow-up, but household quality and latency targets are not met. M5 is now in progress for the bounded event-conditioned request only. Public-video departure checks have false positives, misses and potential late notification; deterministic wiring success does not close recognition acceptance. General saved-fact/assistant recall, timed/recurring reminders and overdue scheduled delivery remain unimplemented. M2's thirty-minute synthetic recording phase completed with 179 indexed segments and 112 candidate searches. The long harness had later UI-test failures, documented separately from successful large-library restart/deletion and short complete lifecycle follow-ups in R8. Actual-camera validation remains open.

Departure follow-up: **163 deterministic tests pass**, including regressions for a
sequence straddling a new request, exact inspected-frame attribution and suppression
of unchanged/low-noise live bursts. A two-minute replay-clock test stays quiet across
periodic checks and resumes on change. The isolated generated-media reminder browser
check passes. The nine-case reversal experiment rejects another model-call gate;
departure accuracy remains open. See R8 for the separate resource-limited live replay;
no new household, hardware, latency or recognition acceptance gate is closed.

### Temporal window and conversation verification follow-up

The approved temporal window now runs before automatic embedding and live inference:
controlled 0.1 s returned-to-baseline disturbances are suppressed, lasting placement
qualifies, activity shares episode IDs and busy inference does not consume a pending
nomination. A separate action gate matches temporal/model cues to eligible armed
requests. Full recordings and source timestamps remain intact. Live phases and
decision reasons are visible. General event importance and personal memory remain
outside this bounded slice.

**192 deterministic tests pass.** Generated-video tests exercise actual FFmpeg and
index selection; lifecycle checks cover cancellation, camera stop and stale inference.
The generated-media browser reminder scenario passes brief-flash suppression followed
by sustained activity, playback, cancellation, acknowledgement and denied playback.

Expanded real-planner development checks found and fixed continuation/routing gaps.
The latest ten scripted cases pass query-attribute, tool-path and bounded-completion
checks with real Qwen and controlled tool observations. These are not independent
household retrieval trials. Dense real-model API replay produced an exit reminder
and an erroneous entry reminder; recognition acceptance remains unmet. See
[R8](research/R8-companion-loop.md) and the
[implementation plan](superpowers/plans/2026-10-20-temporal-attention.md).

### Grounded event follow-up — 2026-10-20

**217 deterministic tests pass.** Automatic region inference and independent object
detections now provide reusable trajectory evidence before a departure action.
Tests cover different region positions, reverse motion, stationary/turnback cases,
missing/multiple detections, malformed coordinates, authoritative action rejection
and preserved armed requests. The generated-media browser speech/cancel/acknowledge/
denied-playback flow and offline wheel check pass.

Nine reused public diagnostic sequences produced one action on three exit proxies,
zero on four negatives and zero on two ambiguous cases. Live entry replay blocked
a confident semantic false departure using observed movement away from the door;
live exit replay still missed the event because of detector gaps. Automatic exit
labels and sparse trajectories remain fallible. This does not establish dependable
household recognition, arbitrary automatic conditions or useful advance warning.
M1–M5 remain in progress. See [R8](research/R8-companion-loop.md) and the
[grounded event plan](superpowers/plans/2026-10-20-grounded-events.md).

### Buffered trajectory follow-up — 2026-10-20

**227 deterministic tests pass.** Bounded dense detector observations now retain
explicit gaps, reset ambiguous associations, check full-track direction and attribute
the exact three semantic images. Successive region estimates are checked within a
camera epoch. Full context survives activity-episode boundaries. Generated-camera
browser checks, lint/format/JS and the byte-matched offline wheel pass.

All nine full-sequence replays ran with armed requests: 79 jobs, 19 semantic checks.
One of three staged exit proxies created a notification, about eight seconds after
the crossing bracket; two were missed. Indoor evidence produced one false action.
No advance-warning or household recognition gate is met. The first aborted replay
also exposed a repeated-reminder conversation failure; isolated evaluation does not
fix that product weakness. M1–M5 remain in progress. See
[R8](research/R8-companion-loop.md) and the
[tracking plan](superpowers/plans/2026-10-20-continuous-trajectories.md).

### Resource-aware runtime replacement — 2026-10-20

The user selected Qwen3.5-2B MLX 8-bit on Apple Silicon. One authorized synthetic
image smoke passed: 5.62 s load, 2.91 s generation, 2.70 GiB reported peak MLX
allocation. The process exited and the obsolete Qwen3-VL cache was removed (4.3 GB).
**234 deterministic tests pass**, with lint/JS and offline packaging checks.

A post-inference continuity veto now withholds superseded positives and keeps the
request armed. Its real-video regression was interrupted during the resource pause;
new-model recognition, multi-image semantics and conversation evaluation remain open.
Heavy inference stays paused beyond the completed smoke. No M1–M5 acceptance gate
is closed. Details and limitations are in [R8](research/R8-companion-loop.md).

### Conversation reliability wiring — 2026-10-20

Mutation validation now participates in bounded agent repair before executing a tool,
with a second authorization check at execution. Tests cover misrouted cancellation
recovery, negation, ambiguous targets and preservation of existing reminders. Search
continuation is scoped to the resolved query; corrected descriptions can revisit
recent windows, and time widening retains their attributes. Prompt v9 strengthens
current-turn/correction precedence. Observation status text separates checking from
stale/changed/uncertain evidence.

All verification in this continuation uses deterministic boundaries. The real-model
reminder/correction scenarios remain pending while inference is paused. No recognition,
conversation quality or M1–M5 acceptance gate is declared met.

Verification: 246 deterministic tests; final companion status regression 34/34;
lint/format/JS and offline wheel checks pass. Browser and real-model validation remain
separate pending work.

### Reminder display clarification — 2026-10-20

Existing reminder rows now show request timestamps, readable lifecycle states and
specific accessible cancel-button labels. This distinguishes repeated messages
without adding backend state or another agent workflow. JavaScript syntax and diff
checks pass; browser interaction and model inference were not run during this small
memory-constrained UI update. Prior deterministic suite remains 246 tests; it was not
rerun for text/DOM-label-only edits.

### Two-flow MVP validation — 2026-10-20

Focus is now object finding → correction → history and next-departure reminders.
A real Qwen3.5/SigLIP API run found an indexing compatibility failure, then after
repair completed two turns with incorrect placeholder answers and a dropped
spatial correction. Pooling and malformed-answer handling now have regression
coverage; revised visual prompting has not been rerun. Memory pressure stopped
the history turn, and departure replay was deferred. Neither flow meets its MVP
acceptance goal yet; no milestone is newly closed. See [R8](research/R8-companion-loop.md).

Verification: **251 deterministic tests pass**, Ruff and formatting pass, edited
document links resolve, and the offline wheel matches the changed runtime files.
These checks do not substitute for the pending real-model flow validation.

### Correction continuation guard — 2026-10-20

Fixed a guard that rejected current inspection for a changed query after any prior
current inspection. Same-query repetitions remain rejected. The regression failed
before the change; all **252 deterministic tests pass** afterwards. No model
loaded or inference run. The MVP experiment now offers `--current-only` to isolate
two conversation turns without indexing/history. Further inference requires user
approval; real correction quality, history and departure acceptance remain open.

### Approved inference retry stopped by memory guard — 2026-10-20

The approved current-only two-turn experiment was stopped at 6.09 seconds when
the system free-memory metric reached 22% (25% cutoff). Neither turn completed.
The owned process exited and the metric recovered to 48%; no retry was run.
No new quality result or acceptance gate. The prior 252 deterministic tests
remain the latest code verification; no code changed. Details: [R8](research/R8-companion-loop.md).

### Current-view check completed; correction still fails — 2026-10-20

With the user-approved 10% watchdog cutoff, the two-turn current-only run completed
in 15.05 seconds and exited. Visual prompt v2 produced an actual location matching
the left remote, without placeholder text. The planner still omitted “on the
left” from its correction query; the initial answer also failed to acknowledge
two matching remotes. Thus correction/ambiguity acceptance remains unmet. No
history/departure test or additional inference followed. See [R8](research/R8-companion-loop.md)
for timings and memory limitations. No code changed; prior 252-test result stands.

### Clarification wiring; follow-up resolution still open — 2026-10-20

Ambiguity now survives parsing and returns a question through current/history,
direct snapshot and voice paths. Multi-match or invalid-count output cannot
confirm a single location; history stops before choosing an older match.
Five isolated real planner cases passed on prompt v10. Subsequent integrated
checks on final visual v5/planner v12 correctly clarified a generic two-remotes
request, but repeated the question after a right-hand clarification instead of
inspecting. All model processes exited; no MVP acceptance gate closed.
See [R8](research/R8-companion-loop.md) for each iteration and limits.

Verification: **261 deterministic tests pass**; lint, format, local document
links and byte-matched offline wheel pass. Browser interaction was not rerun.

### Integrated flow evaluation — 2026-10-20

Clarification follow-ups now reach inspection in real API testing, and saved-query
context preserves attributes into history. Final isolated visual checks passed
4/4 development cases. The final three-turn API run retained the right-hand query
and selected recent dated footage, but manual inspection found wrong historical
item/location attribution. The latest broad planner result was 13/16 on v16; a
final v17 targeted rerun was 4/5, with a historical qualifier failure when prior
query hints were absent. No general conversation/recognition acceptance claim.

Full video replays armed reminders for two exit proxies and one entry clip. Both
exits were missed; two false semantic departure claims on entry were blocked by
the independent direction check. No notification was created. Recognition and
timely departure delivery remain open MVP blockers. See [R8](research/R8-companion-loop.md).

Final verification: **265 deterministic tests pass**, lint/format and offline
packaging pass. The synthetic browser speech check passes with no browser errors:
100 ms flash suppression, sustained activity, pending-audio cancellation, spoken
delivery/acknowledgement, playback-denial failure reporting and library paging.
Its first attempt failed because it expected obsolete raw state labels and the
old Cancel accessible name; the harness was updated to existing readable labels
and rerun successfully. These are fake model/audio/device boundaries, not real
recognition or Sarvam performance. All owned experiment processes exited.

### Guided object finding implemented — 2026-10-20

One complete reviewable flow is now wired: ask → clarify the object → search
history → inspect a possible match → reject or explicitly confirm. Confirmation
is user-attributed and preserves the recording timestamp, including unknown time;
it survives restart and is invalidated when its source is deleted. Duplicate
confirmation requests do not create duplicate turns. No automatic identity claim.

The actual-model development run returned the wrong crop at offset 16 s; a
fixture-provenance-based simulated reviewer rejected it, received offset 8 s
(containing the intended remote), then confirmed that frame. This verifies the
review workflow, not autonomous recognition or real user usability. The isolated
browser check passes rejection, confirmation and reload alongside synthetic
speech/activity controls. Automatic lookalike identification and departure
recognition remain open; no broader M1–M5 accuracy gate is declared complete.

Final verification: **269 deterministic tests pass**; lint, formatting, JavaScript
syntax and offline packaging checks pass. The packaged runtime and web assets
match the working source. Synthetic browser review coverage is recorded above;
no additional inference was required for final checks.


### Conversational candidate rejection — 2026-10-20

Typed/activated spoken feedback and the rejection button now enter the ordinary
agent loop. Displayed candidate references survive in recent conversation plans;
the planner can choose query refinements, time windows, exclusions or clarification.
Search execution honors excluded frames without a rejection-phrase router.

Verification: **277 deterministic tests pass**, including agent-selected rejection
through the real API, restart context, direct-result feedback and argument bounds.
Synthetic browser checks cover button rejection followed by typed rejection,
different returned frames, confirmation/reload and existing speech controls.
Lint, formatting, JavaScript syntax and offline packaging pass.

Final planner v23 passed **3/5 focused real-model cases** with controlled tool
observations: two casual rejection phrases and thanks. It dropped a new handle
attribute in one case and carried old exclusions into an unrelated new-object
request in another. The conversational wiring is implemented; robust semantic
feedback handling remains open. This is not a recognition or full MVP acceptance
claim. See [R8](research/R8-companion-loop.md) for iterations and limitations.


### Retrieval continuation repaired; broader planner evaluation prepared — 2026-10-28

Rejected frames now filter out before the database result limit, so a follow-up
can reach candidates beyond the original five best matches or latest-mode window.
Regression tests reject five/seventeen candidates and still retrieve an eligible
next candidate, with source/time constraints and the existing work bound intact.
The agent remains responsible for choosing exclusions and its next search.

Six additional conversation cases cover different objects, casual rejection,
attribute correction, topic changes, time widening without rejection, and stopping.
Scoring rejects vacuous exclusion passes (no search) and stale/unrequested
exclusions. Cases are prepared but **not run with the model**; no prompt change or
claim of improved planner accuracy. The prior 3/5 result remains the latest.

Verification: **281 tests pass, 2 optional PyTorch tests skip** in a recreated
Python 3.12 web/test-only environment. An initial full run exposed these tests'
unconditional torch import; they now explicitly skip when the vision extra is
absent and still run when installed. Lint/format and changed document links pass.
No model inference, hardware capture, vision downloads or browser run this turn.
