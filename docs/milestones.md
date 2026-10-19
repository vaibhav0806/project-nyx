# Milestones

Updated: 2026-10-19. **M1 household validation is pending; M2 continuous recording and background indexing are implemented locally. User authorized this expansion after successful manual retrieval.**

This is the single project progress tracker. Detailed implementation tasks are written for the approved next milestone when the user asks to build. Research can inform the plan without silently changing scope.

## Status

| ID | Milestone | Status | Depends on | Completion evidence |
| --- | --- | --- | --- | --- |
| M0 | Agree on design, scope, repo layout, and research plan | Complete | — | User reviewed in Zed and requested implementation to resume |
| M1 | Prove local visual retrieval feasibility | In progress | M0 + implementation instruction | [Measured public-image smoke baseline](research/R3-local-retrieval.md); independent household clips still needed |
| M2 | Build an inspectable recording/search slice | In progress | M1; manual capture enables its evaluation | [Continuous implementation](superpowers/plans/2026-10-19-continuous-recording.md): durable rolling capture, prioritized search, budget and restart recovery; retention/deletion and hardware soak remain |
| M3 | Add verified visual answers and fresh inspection | Not started | M2 | No verifier yet |
| M4 | Connect natural voice and durable transcripts | Not started | M3 | No voice integration yet |
| M5 | Add personal recall and reminders | Not started | M4 | No personal-memory/action implementation yet |
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

Remaining: retention policy/source-aware deletion, independent household labels and the thirty-minute actual-camera/resource/restart evaluation. Synthetic browser capture does not close those gates. Interrupted browser-exit tails may be lost and uncertain segments do not assert wall-clock coverage. Model cache/thumbnails are outside the original-video cap.

## M3 — Answer from visual evidence

1. Compare a small on-demand VLM on the retrieved candidates using the same labelled inputs.
2. Add fresh-frame inspection for current questions and source verification for historical questions.
3. Apply time filters and select the latest verified sighting for last-seen questions.
4. Add supported landmark guidance and clarify ambiguous duplicates.
5. Exercise hidden objects, camera movement, out-of-order model results and capture failure.

Done when: each current/historical answer links to the appropriate evidence and can state uncertainty. Proposed evaluation targets to review after M1: 27 useful correct answers in 30 current-location trials and zero invented current locations in 20 deliberate uncertainty cases. These are targets, not measured performance.

## M4 — Speak and retain conversations

1. Trial cloud voice in the intended language and choose a provider based on measured behavior.
2. Connect backend tools for current inspection and history search.
3. Add microphone controls, turn state, interruption/recovery and visible transcripts.
4. Persist attributed conversation records across session/app restart.
5. Measure end-of-speech to first useful answer with retrieval/verification included.

Done when: spoken questions, follow-ups and interruptions work end to end; the app does not confuse transcripts with visual evidence. Proposed current-location latency target: p95 below five seconds across 30 trials; report history queries separately and revise transparently if evidence demands it.

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
