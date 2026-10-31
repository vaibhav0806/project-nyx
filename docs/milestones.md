# Milestones

## Faster streaming synthesis and overlapped frame checks — 2026-10-31

The running demo selects Sarvam Bulbul v4 Flash using the existing private key; all
12 generic acknowledgement clips use its same companion voice. Synthetic English/Hindi
first audio measured 253–390 ms versus 2164–2761 ms for the former Gemini path. A separate
uncached Nyx sentence pipeline test measured 307 ms to first audio. These exclude retrieval
and browser playback, so end-to-end improvement is not yet measured.

Independent frame decoding and verification overlap in bounded workers, preserving result
order. Clear question-only transcript context skips the model and frame decode; mixed
placement statements remain eligible. Added explicit planner timing. Kept Luna after a
small GPT-4.1 mini trial made an incorrect initial last-seen tool choice.

Validation: 397 deterministic tests pass; lint, format and diff checks pass. Regression
coverage includes streaming PCM, cancellation, redacted provider failures, consistent
acknowledgement/answer voices, frame-work overlap/order, and context-call avoidance.
See R6 for models, texts, measured timings, source links and limitations. No developer
camera/microphone capture or new household-image upload was used.

## Single-user wording and latency diagnosis — 2026-10-31

Fixed “the person’s hand” in existing answer formatting and new vision location prompts.
Added acknowledgement cache-read and browser playback diagnostics. Two local requests
showed Jev under 0.7 seconds; later planning/history dominated the delay. Identical
answers came from two requests using deterministic English phrasing; duplicate delivery
was not established. No claim of reduced retrieval latency. Validation: 393 tests pass,
Python lint/format, JavaScript syntax and diff checks pass; no real media captured.

## Relaxed, plain-language personality — 2026-10-31

Updated planner and generated-speech instructions for the approved calm, relaxed,
attentive and lightly witty character. Everyday spoken words and short sentences
are required in English and Hindi/Hinglish. Humor follows a playful mood and stays
out of worried, frustrated or serious exchanges. Updated the design and decision
records. Existing checked findings remain brief and factual with no added model call.
Validation: Python lint/format and the 390-test deterministic suite pass. These
checks protect the existing pipeline; actual model tone still needs listening review.

## Companion wording correction — 2026-10-31

Corrected internal third-person user labels and unattributed hand wording in checked
answers; removed the redundant “in front of you” location for an already-described
user activity. Updated planner/generated-speech style and Hindi address guidance.
Recorded personality research and a concrete character brief in R7 and design.md.
Validation: 390 deterministic tests pass, including screenshot reproduction, hand
ownership, distinct visitors and unchanged evidence. No live camera/microphone or
provider calls were used; broader conversational quality still needs listening feedback.

## Conversation UI delivery — 2026-10-31

Implemented the approved dark “Just a conversation” design in the packaged web interface:
current question/answer, talk/stop, mute, typing, camera state/pause, optional source dialog,
and settings/history. Existing recording, source review and deletion controls remain available.

Validation: deterministic browser checks cover typed and voice-transcribed responses, source
visibility, clearing previous evidence on a new voice turn, stop control, mute state, dialog
Escape/focus behavior, and mobile overflow. The full suite passes 342 tests; Python lint/format
and JavaScript syntax checks pass. Desktop and mobile screenshots were inspected. API replies are fixtures; no real camera/microphone
or provider requests are used. Real-room voice and household accuracy remain separate gates.


## Cloud MVP switch — 2026-10-28 (current)

Cloud inference is now the primary runtime; prior local-only status below is
historical. OpenRouter supplies planner/vision, multimodal embeddings and activated
STT/TTS. Local wake, inexpensive observation, the small detector and storage remain.
MLX/Qwen/SigLIP generation/embedding runtime dependencies were removed; original
media remains intact. No dual inference stack or provider framework was added.

**Measured:** 21/21 planner regression, 10/10 feedback and 12/12 additional cases;
7/7 guided real-model API flow with full GPT-5.4 vision and GPT-5.4 Mini planner.
The synthetic 24-frame index rebuild preserved media hashes/source metadata.
Companion browser and real-local-wake voice browser checks passed with fake devices.
The actual cloud STT/agent/vision/TTS API chain passed on synthetic input (9.11 s).
See [R9](research/R9-cloud-mvp.md) for methods, earlier failures and limitations.

The installed-environment suite passes **324 tests**, lint/format, JS syntax and
offline packaging. Approximately $0.33 of the $2 test cap was used; 4.16 GB of
retired Qwen/SigLIP weights were removed.

The MVP cloud wiring is implemented. Independent household validation, real-room
voice/echo, timely departure detection and intended-user evaluation remain open.
General long-term memory and time-based reminders remain later work. These results
do not establish merge readiness or production reliability. No push or merge.


Updated: 2026-10-28. **M1 household validation is pending; M2 continuous recording and background indexing are implemented locally. User authorized this expansion after successful manual retrieval.**

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


### Feedback evaluation completed; redirect exclusion bug fixed — 2026-10-28

Restored the previously selected pinned Qwen3.5-2B 8-bit checkpoint and locked
runtime after local cleanup. Ran six additional conversation cases with actual
planning and controlled tools. Under tightened scoring (older footage must widen
the window; continuing without rejection must retain earlier exclusions), the
baseline passed **3/6**. Moving the request into its own user message also passed
3/6. Experimental review-choice tools/compact prompts traded failures rather than
improving overall reliability; bounded reasoning passed 1/3 targeted cases.
These alternatives were reverted from application code. Planner v23 remains.

Fixed a separate executor bug: redirecting a search toward dated history now
preserves the agent's excluded frame IDs. A regression test verifies the actual
arguments delivered to the tool. No phrase/object routing was added.

Verification: **285 deterministic tests pass**, including restored vision tests;
lint/format and changed document links pass. No browser/hardware/provider tests.
All owned model processes exited; minimum sampled memory metric across completed
runs was 21%, above the approved 10% cutoff. One unbounded-reasoning probe was
manually stopped after failing to produce a usable decision. See R8 for timing,
manual answer-quality failures and limits of automated scoring.

Next decision: compare a more capable text planner on these now-development cases
and separate fresh cases. Do not treat more prompt iterations on this small set
as evidence of dependable conversation or improved visual recognition.


### Larger planner comparison did not justify switching — 2026-10-28

The same v23 prompt and six feedback cases scored **3/6** on a pinned Qwen3.5-4B
8-bit conversion, unchanged from the tightened 2B baseline. It retained a new
attribute but still failed temporal/exclusion handling. The 39.27-second run
peaked at about 6.35 GiB MLX allocations and sampled as low as 14% free-memory
metric; it exited normally above the approved cutoff. No recognition/API-flow
claim follows from controlled tool observations. The four new transfer cases
remain unrun. See [R8](research/R8-companion-loop.md).

No application change or model replacement. Unused 4B weights were deleted,
including the verified shared cache blob; active 2B weights remain. This rules out
adopting that larger checkpoint on the present evidence, not all larger models.
Experimental CLI checks/scoring tests and documentation checks pass. The latest
full application suite remains 285 passing tests from the preceding follow-up.


### Stale review context repaired — 2026-10-28

The browser no longer presents a hidden old frame as the current review target
after a successful nonvisual reply. Planner lookup no longer reaches past newer
visual work or explicit confirmation to resurrect an older candidate. Clarifying
questions retain their pending candidate; explicitly displayed evidence wins.
Context version 28 retains the existing tools/model and adds no inference stage.

Verification: **290 tests pass**, lint/format/JS syntax and local documentation
links pass. Synthetic browser check `candidate-context-browser-20261028` passes
rejection, confirmation, reload, hidden-reference clearing and existing synthetic
speech/activity checks with no browser errors. No actual camera/provider use.

A factual-only context prompt (v27) still scored 3/6 and was reverted. Separate
request-interpretation probes also confused rejection/continuation with new tasks;
no second model call was added. These failures and the boundary-tested state fix
are distinct: no claim that v28 resolves the broader conversation accuracy gate.
All owned model/browser processes exited. See R8.

### Guided MVP wrap-up — 2026-10-28

The focused object-finding demo is ready for guided developer testing; broader
M1–M5 household/voice/event acceptance remains open. The [runbook](mvp-demo.md)
covers setup, review, voice and shutdown. UI now labels departure reminders as
experimental and explicit item confirmation as “Confirmed by you.”

Actual local Qwen/SigLIP API flow passed 7/7 structural checks: ambiguity,
correction, recent history, conversational rejection, confirmation, topic switch
and stop. The fixture reviewer still had to reject a wrong crop. A separate blank
image returned uncertainty. These reused development examples do not resolve the
3/6 broader planner result or establish automatic item identity. See R8.

Voice startup was repaired for the documented partial offline wake-model cache.
Actual tiny.en with one generated pronunciation passed the browser wake/barge-in,
playback and lifecycle checks; another pronunciation missed the name. Providers
and visual/agent outputs were mocked. Real-room echo/provider latency remain open.
See R6. No hardware or uploaded media was used.

Final checks: **291 tests pass**, Ruff/format/JavaScript checks pass, the synthetic
companion browser passes review/reload and speech/activity checks, and the offline
wheel's 26 runtime/assets match source. Model processes exited. Next evidence
needed is a permitted representative room trial and intended-user feedback, not
another architecture layer; dependable departure reminders remain later work.

### Remote-main regression comparison — 2026-10-28

**Do not merge yet.** Main's 109 tests pass in its locked environment. Branch's
292 tests pass after fixing a real old-index compatibility failure caused solely
by Transformers processor metadata serialization. Same public-fixture retrieval
results match exactly across three queries after repair; both versions pass the
same synthetic recording/search lifecycle browser check. Copied old media,
capture states and transcripts remain readable. Six original-suite differences
are classified in R8 (stricter judgment schema, candidate labels, adaptive
sampling and spoken review language).

Main's original BF16 visual model was stopped at the authorized memory cutoff
before output; its comparison-only weights were removed. Branch completed four
visual development checks, but a direct quality superiority claim is unavailable.
Four previously unrun planner cases scored **2/4**, including time-widening and
unresolved-reference failures. These reinforce the existing conversation concern.
No merge/push or remote merge-readiness claim; see [R8](research/R8-companion-loop.md).

The upgraded synthetic index also reopens under main with exactly matching
retrieval results (rollback read verified). Final lint/format, documentation links
and packaged runtime checks pass. Comparison environment/model weights were
removed; no experiment remains running.

### Reliability deep dive and strict earlier-history tool — 2026-10-28

**Semantic conversation failures remain unresolved; do not merge yet.** Added a
real earlier-than-frame time boundary to the history tool, with exact recorded
source time, unchanged rejection state, missing/unknown-time errors and bounded
repair. An established boundary survives query refinements/continuations within
the request. The agent chooses whether to use it; no phrase/scenario routing.

Extensive local prompt/context/tool-interface/reasoning experiments did not produce
a dependable replacement. Broader rewrites regressed existing behavior and were
reverted. A larger 4B/8-bit model with bounded reasoning reached 9/10 focused cases
but still failed a time-only request, with substantially longer execution; it was
not adopted and its trial weights were removed. A separate semantic reviewer
rejected correct plans and was not added.

The retained 2B/v38 runtime passed 17/21 existing planner checks versus baseline
16/21 with no previously passing case lost. Focused feedback remains 5/10 and the
additional 12-case set 5/12. The seven-step actual-model guided API demo still
passes; **306 deterministic tests**, lint/format and offline packaging pass.
These are distinct evidence layers, not a completed household/conversation gate.
See [R8](research/R8-companion-loop.md) for all iterations, failures and resource
limits. No hosted-planner credentials are configured; any paid/provider change
needs the applicable authorization. No merge or push.

### Activated speech diagnostics — 2026-10-28

Added durable, bounded local attempt/turn diagnostics and immediate activated STT
transcript persistence. Failed routing/cancelled turns remain inspectable; browser
failure stage and actual playback-start reports are distinct from TTS generation.
329 tests and synthetic real-wake browser integration passed. No private media
was uploaded for verification. Statement-to-image linking and grounded response
synthesis remain next work; this change does not implement that product behavior.

## Speech-linked finding and surrounding replay — 2026-10-28

Historical matches now replay up to ten seconds before and after the sighting,
across available segments in the same reliably timed capture session. Gaps are
not reconstructed. Imported or uncertain recordings use clip-local bounds.

The history tool searches captured user transcripts by object words or within
90 seconds of the sighting (30 candidates). The visual model selects at most two
existing transcript IDs. Exact quotes are attributed separately from visual
findings; intended placement is not confirmed placement. This bounded feature
is not general long-term semantic memory. Listen now (30 seconds) bypasses missed
wake activation; ignored wake attempts stay quiet in the conversation UI. Idle audio is not
archived, so missed statements cannot be recovered.

Verification: 334 deterministic tests and companion/voice synthetic browser checks
passed. User-authorized saved glasses footage replayed three segments totaling
20 seconds and stopped correctly in the browser. Full cloud API retrieval passed
with that footage and a synthetic location statement in an isolated database.
The actual saved transcripts had no placement statement and yielded no false
citation. No real camera/microphone opened. Private artifacts remain ignored in
`data/runs/glasses-context-evaluation/`. Wake accuracy remains an open limitation;
these results do not establish perfect household accuracy or merge readiness.

### Voice cancellation diagnostics and activation retry — 2026-10-28

Real test transcripts confirm placement speech persisted and acknowledgment
playback began. Subsequent history jobs lost their active voice turn and cancelled;
previous logs cannot establish which caller cleared the turn. Do not claim that
historical root cause is proven. Fixed transcription failure consuming explicit
activation, error cleanup cancelling that window, and Listen now replacing an
active request. Added bounded cancellation source/epoch/turn diagnostics, explicit
job-cancel events, job IDs and stack function/line locations for agent failures,
and stack locations for transcription failures (no raw exception/provider payload).
335 tests and synthetic voice browser smoke pass. Historical cancellation cause
and a fresh real-user complete test remain open; no merge readiness claim.

## Bounded latency improvements — 2026-10-29

Measured previous real-user flow: question receipt to speech playback was about
55 seconds; history tool execution occupied roughly 46 seconds. Old diagnostics
cannot split that interval into individual provider calls or queue delays.

Ingestion now runs in a separate single worker from interactive jobs, allowing
one ingestion request and one interactive request to overlap. Model initialization
is synchronized; SQLite writes remain short transactions. No extra speculative
vision calls, new model downloads or broader worker pool. Capture embeddings use
batches of eight selected images instead of two. Text embeddings use a 64-entry
per-encoder in-memory LRU, removing repeated calls for identical queries while
returning independent arrays. The model/embedding identity is unchanged.

Text answers display before TTS finishes. Jobs expose initial queue and accumulated
work time, history results split retrieval/decode/verification/context time, and
server logs record cloud endpoint/model/outcome/duration without payloads or keys.

Deterministic tests explicitly hold ingestion blocked while searches and observation
finish. A synthetic no-op scheduling probe completed in 0.03 ms while ingestion
was blocked: this proves isolation, not real cloud response latency. No new paid
model benchmark was run. A fresh real-provider test is needed to quantify the
end-to-end improvement; provider latency and sequential visual checks remain.

Validation: 336 tests passed in 7.24 seconds; lint, formatting and JavaScript
syntax checks pass. Companion synthetic browser regression passed with no browser
errors, including cancellation, candidate corrections and event delivery. The first
browser run exposed a test race between persisted conversation text and UI request
completion; the assertion now waits for completion before checking cleared state.

## Parallel history verification — 2026-10-29

Measured repeated single-frame cloud round trips dominate history lookup. A trial
sending four images in one generation request took 30.53 s including TTS, offering
no meaningful gain; that prompt/schema experiment was discarded.

Retained approach: overlap at most three independent single-image checks with the
same GPT-5.4 model and existing judgment prompt. Consume results in original
retrieval/time order; an earlier ambiguous result still asks for clarification,
and a later match cannot replace an earlier selected match. All checked frames
remain in evidence metadata. Errors propagate rather than becoming negative
observations. No speculative batch beyond the current three is launched. Up to
two extra checks can be billed compared with serial early exit. Already-sent
requests cannot be cancelled upstream. Generator boundaries still allow agent
cancellation between batches. Background ingestion remains a separate worker.

Real saved-data replay, same question/context/time and fresh TTS:

| Run | Answer ready | Including TTS |
| --- | ---: | ---: |
| Previous serial optimized | 25.69 s | 30.64 s |
| Parallel | 14.24 s | 20.24 s |
| Parallel repeat | 15.32 s | 21.58 s |

Both parallel runs returned the same correct attributed location statement.
The first selected the same evidence frame as the previous optimized run.
Six checks ran in each parallel replay; the earlier serial run checked five.
Verification wall time fell from 18.32 s to 8.52/8.02 s. Context association took
2.46/4.05 s, retrieval ~0.96 s, decoding ~0.7 s, and TTS 6.00/6.26 s.
This is two development replays, not a latency SLA or a broad accuracy benchmark.
No original microphone audio or browser playback timing was available. Raw private
artifacts stay under ignored `data/runs/latency-replay/`. Total additional trial
spend was ~$0.0788; $1.3612 remains from the $2 key cap.

340 tests passed, including simultaneous execution with a barrier, preserved result
order, earlier ambiguity, bounded concurrency and propagated provider failure.
Lint/format pass. The model and semantic verification rules are unchanged.
Full-response TTS still delays first audio; streaming or shorter conversational
wording remains future work. These changes improve latency but do not make the
experience instantaneous.

### Lower-cost models and retrieval scale review — 2026-10-29

Adopted Luna planning, Gemini 3.5 Flash-Lite vision/context, configurable six-way
visual checks and diversified semantic candidate nomination. Embeddings unchanged.
341 deterministic tests, 39 real planner cases (21 main + 12 holdout + 6 feedback),
4 public visual cases per model, and synthetic companion browser regression passed.
Actual saved-data replay returned the correct statement-linked answer in 9.41 s,
14.83 s including TTS. Synthetic 129,600-frame exact-vector scans stayed under 0.5 s.
This does not establish multi-day recall: current video rate and 1 GiB stop budget
cannot retain days. No raw recordings deleted, budget increased or index rebuilt.
See [R10](research/R10-low-cost-retrieval.md) for full evidence and limits.

### Recording compression MVP — 2026-10-29

Direct work on main authorized. New browser recordings request 720p/up to 15 fps
and target 1 Mbps rather than 2.5 Mbps. Continuous ten-second segments and codec
fallbacks remain. UI explicitly states no automatic expiry and stop on full budget.
Old recordings/imports, timestamps and the 1 GiB byte budget are unchanged.

Saved-footage browser replay measured 2.52 MB versus 0.64 MB for the same ~10-second
clip (74.5% smaller); compact playback retained 720p and expected duration. Cloud
vision recognized glasses at the tested offset in both profiles. This is a narrow
quality check, not proof for small/distant objects or fast motion. 341 deterministic
tests passed; synthetic browser regression covers capture, new profile requests,
video-only recording, evidence review, cancellation and reminders. Details and
reproduction command in [R11](research/R11-recording-compression.md).

### Conversation control polish — 2026-10-31

Ignored wake attempts remain in diagnostics without a user-facing warning. The main
microphone icon stays stable during work and playback; muted controls show a red
slash. Typing uses a neutral border with keyboard focus retained on other controls.
The synthetic browser regression passes, including ignored speech and mute state.

### Jev spoken routing and acknowledgements — 2026-10-31

Implemented Jev 1.14 via the OpenRouter Decisions API, with a direct Luna reply for
high-confidence general conversation and the existing agent for evidence/actions
or uncertainty. Exact greetings retain their shortcut. A fixed acknowledgement
runs alongside tool work; session/turn/epoch and browser completion guards reject
stale playback. Typed requests keep their existing agent path.

Validation: 354 tests pass, including typed decision parsing, uncertainty, responder
deferral, acknowledgement authentication/cancellation, and browser late-audio
suppression. Ruff lint/format, JS syntax and whitespace checks pass. Ten synthetic
live text cases matched intended routes; see [R6](research/R6-handsfree-voice.md#jev-routing-check--2026-10-31)
for timings, cost and limits. No real camera/microphone used. The 0.95 threshold
needs broader calibration; full spoken latency and room echo remain open.

### Natural speech and local time — 2026-10-31

Historical replies now use rounded elapsed time and checked location details,
with a short identity qualifier instead of the image-review disclaimer. User
statements remain explicitly attributed. Browser timezone reaches both voice and
typed requests; simple clock questions use deterministic local time, and planner
context includes the local offset and zone. Exact source metadata is unchanged.

Validation: 363 tests pass, including equivalent-offset elapsed times, 37-minute
rounding, unknown/future timestamps, spoken/typed clock shortcuts, local planner
context and browser timezone transport. Python lint/format and JS syntax pass.
No real camera/microphone or paid model calls used for these changes.

### Physical location wording — 2026-10-31

Removed the vision prompt's invitation to use image position in the conversational
location field. Current and historical reply formatting drops camera-coordinate
clauses while preserving physical landmarks. Seven regression cases cover the
reported right-hand example, coordinate-only locations and actual table positions.
370 tests, lint, format and whitespace checks pass. No cloud or hardware calls.

### Two-stage streaming voice — 2026-10-31

Implemented Jev route/lookup/language classification before stage-two generation
or tool work; general questions and action-only requests have no lookup filler.
Prepared twelve local acknowledgement clips, six English and six Hindi. Missing
clips skip filler instead of synthesizing it during a turn. General replies and
Hindi translation stream into sentence buffering and two concurrent, ordered TTS
streams. Existing English evidence answers go directly to streaming speech.
Browser PCM playback is bounded, interruptible, and starts before the full answer
finishes. Removed per-turn warmup and parallelized independent frame decoding.

Validation: 384 tests pass; lint/format, JS syntax and whitespace checks pass.
Tests include real localhost HTTP delivery before generation completes, disconnect
cleanup, wake/stop cancellation, no filler for QA, and ordered concurrent synthesis.
A real-HTTP test exposed delayed cleanup on disconnect; the response now explicitly
closes its iterator under cancellation shielding. Synthetic English/Hindi provider
checks and limitations are recorded in [R6](research/R6-handsfree-voice.md#two-stage-streaming-checks--2026-10-31).
No real camera/microphone or private-media inputs used in developer verification.
Provider first-audio delay, real-room interruption quality and p95 latency remain
open. Later chunks/requests cannot remove those provider or retrieval dependencies.

### Consistent voice settings — 2026-10-31

Shared the preferred acknowledgement synthesis settings across complete and
streamed speech. Retained the existing twelve cached clips. Answer playback now
uses a separate 24 kHz audio context, preserving 16 kHz microphone processing.
385 tests pass, including exact speech-payload parity and a browser assertion for
separate capture/playback sample rates. Lint/format and JS syntax pass. Tests use
synthetic audio; no claim of a completed human listening comparison.

### LiveKit Agents and Sarvam realtime voice — 2026-10-31

Replaced the custom spoken conversation loop with LiveKit Agents 1.8.10 over local
browser WebSocket audio IO. Removed batch utterance/NDJSON reply APIs, Jev voice
routing and custom sentence synthesis workers. Sarvam Saaras v4 realtime handles
partials/VAD with Nyx hints; Bulbul v4 Flash streams female Ritu speech, matching
12 regenerated English/Hindi acknowledgement clips. Detected speech language flows
into the reply and TTS. Native speech connection keepalives send no idle audio.

LiveKit controls turns, interruption and token-to-speech scheduling. Visual tools
skip the duplicate planner; cached acknowledgement and tool work overlap. Existing
frame decoding/verification concurrency is retained. Follow-up/session gating,
source attribution, authorized reminder operations and cancellation remain.

Validation: 353 tests, lint/format, JS syntax and whitespace checks pass; provider
checks used generated English/Hindi speech only. Isolated Chrome exercised actual
STT/LLM/TTS, local-time replies, separate 16/24 kHz capture/playback, muted cleanup
and video-only fake-camera capture with no JS errors. Synthetic vision fixtures
exercise the tool path without sending real images. R6 records exact measurements.
Full room-noise/echo interruption quality, p95 latency and faster LLM generation
remain unvalidated; this does not establish subsecond end-to-end responses.

### Companion speech preset — 2026-10-31

Selected Shalini's actual English/Hindi Companion presets after the user's request.
Answers, reminders and all 12 cached acknowledgements match. Both streaming provider
checks passed (357/338 ms first audio); 49 focused tests and lint passed. Listening
preference remains for user review. See R6 for the measured scope.

### Quiet waiting and gradual answer text — 2026-10-31

Replaced the central Thinking placeholder with three softly moving dots and hid
Thinking from the conversation status. Answer text now appears progressively with
a short initial fade; display animation does not delay streaming audio. New turns
and interruption cancel pending text updates. Reduced-motion preferences use static
dots and immediate text. Conversation browser checks cover waiting, gradual reveal,
new-turn cancellation, Hindi text and reduced motion.

### Speech-paced screen text — 2026-10-31

Replaced accelerated screen reveal with LiveKit playback-synchronized transcription
for voice replies. Typed replies use one word at a time with punctuation pauses.
Anchored the answer area and disabled balanced rewrapping during replies. Regression
checks verify no text before playback, interrupted text stops, fixed fallback pacing,
and stable vertical position. Synthetic Chrome voice playback passed without JS
errors. Timing is estimated because Sarvam exposes no exact word timestamps.
