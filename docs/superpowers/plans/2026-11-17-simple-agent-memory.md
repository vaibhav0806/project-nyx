# Simple shared agent and memory implementation plan

> Execute inline with superpowers:executing-plans; user forbids subagents. Use test-driven-development
> and verification-before-completion. No permission loop between reversible authorized tasks.

**Goal:** Make ordinary memory/recall work through one understandable agent and a focused memory component.
**Architecture:** Shared native tools and short policy across text and voice. Memory owns source-linked
interpretation and updates; visual tools own image interpretation. SQLite and existing transports stay.
**Tech stack:** Existing Python/FastAPI/LiveKit/OpenRouter/SQLite stack; no new orchestration framework.
**Spec:** ../specs/2026-11-17-simple-agent-memory-design.md

## Global constraints

Follow the spec's branch/UI/source/privacy boundaries and cumulative $8 provider limit. Keep Sarvam
speech, embeddings, original data and 1 GiB stop-without-delete behavior. Main stays untouched.
Work inline, regular commits, optional work-branch push only. No new PR/merge is requested.

## Task 1: Shared concise policy and model defaults

Files: create src/nyx/agent_policy.py; update realtime.py and tests/test_realtime.py; create
 tests/test_agent_policy.py. Policy includes personality, short English/Hindi replies, useful
memory/context, honest uncertainty and brief clarification. Tool manuals stay in tool definitions.
- [x] Add failing tests importing one shared policy and verifying realtime uses it and Luna.
- [x] Run `uv run --no-sync pytest -q tests/test_agent_policy.py tests/test_realtime.py` (RED).
- [x] Export `AGENT_INSTRUCTIONS`, `AGENT_MODEL`, `VISION_MODEL` from agent_policy.py; replace
  duplicated realtime instructions/default. Example contract:
  `from nyx.agent_policy import AGENT_INSTRUCTIONS, AGENT_MODEL, VISION_MODEL`.
- [x] Run targeted tests (GREEN), inspect removed instructions, commit the coherent change.

## Task 2: Shared native tools and typed agent execution

Files: create src/nyx/agent_tools.py; repurpose agent.py; update realtime.py, companion.py,
 verification.py and relevant test_agent/test_companion/test_realtime tests.
- [x] Add failing contract tests for equal voice/text tool names, descriptions and schemas;
  actual selected call binding, multi-step continuation, rejected arguments, cancellation and sources.
- [x] Extract lookup/recall/identify contracts into one module; automatic preparation owns writes.
  Tools consume the actual utterance and server-owned evidence; source/turn IDs are server-bound.
- [x] Use native chat-completion tool calls for typed execution with the same policy and tools;
  adapt results into existing API observations/steps/sources/review_context fields. Retain voice IO.
- [x] Delete CloudVerifier.decide's long JSON-planner prompt/action-loop implementation when callers
  use the shared native contract. Keep validation/execution, not two live planning implementations.
- [x] Run API, SDK binding, context/source and cancellation tests; commit after GREEN.

## Task 3: Automatic general memory and lossless existing data

Files: create src/nyx/personal_memory.py and tests/test_personal_memory.py; integrate voice.py,
 companion.py and shared agent tools; consolidate statements.py rather than retain a second writer.
- [x] Add failing persistence/restart tests for facts, preferences, reports, plans and no-op input.
- [x] Implement memory turn processing: retrieve related candidates, one compact Luna interpretation,
  validate operations, persist atomically. Return relevant memories and any clarification needed.
  Sources are actual user-turn/evidence IDs. Successful processing is idempotent by input turn.
- [x] Add failing ordinary-move versus explicit-correction/retraction tests. Persist links/history;
  validate real prior IDs, source availability and chronology. Main agent never chooses database IDs.
- [x] Add provider/embedding/write-failure tests: preserve raw input; no partial links or false success.
- [x] Add existing-R29-store conversion/read tests, source deletion and context-eviction tests.
- [x] Wire automatic processing into typed and activated spoken turns with one owner per turn;
  memory results reach response generation. Do not add a separate autonomous agent loop.
- [x] Run targeted persistence, context, API and voice tests (GREEN); commit.

## Task 4: Single visual path and removal of redundant judges

Files: reference.py, verification.py, personal_memory.py, agent_tools.py, statements.py and tests.
- [x] Add failing real-protocol tests for a short object observation, earlier supporting frame,
  explicit text-only memory, missing/ambiguous object, depicted object and different source clocks.
- [x] Consolidate reference policies into a single task; carry observed source/uncertainty metadata.
  Keep original source timestamps and evidence separation. Use Flash-Lite and schema field docs.
- [x] Delete the independent ambiguity call, separate correction-check call, duplicate reference
  policy flag and optional duplicated visual-scene prompt variants; update experiment callers.
- [x] Assert protocol traces contain no removed judges. Retain clarification/failed-source behavior
  and actual source validators. Known unsafe R29 inputs remain acceptance regressions.
- [x] Run visual, memory, source-failure and API tests; commit after GREEN.

## Task 5: Retire departure feature without harming recording or the UI contract

Files: companion.py, realtime.py, observation.py, intentions.py, reminders.py, verification.py,
 app.py as actual imports require; relevant tests. Do not edit src/nyx/web.
- [x] Add failing API tests for no active departure tools/AI calls and compatible inactive observation/
  delivery polling; recording/indexing remains functional and original reminder rows preserved.
- [x] Remove departure-specific runtime wiring, model prompts, detection/tracking and scheduling
  implementations. Keep cached lookup acknowledgements. Preserve existing historical data.
- [x] Remove obsolete tests/experiment imports only with replacement coverage for retained contracts.
- [x] Run recording/import/source/voice API/browser boundaries and commit after GREEN.

## Task 6: Real model acceptance and iteration

Files: experiments/companion/recall_workflows.py, household_workflows.py and frozen general/household cases;
 docs/research/R30-simple-agent-memory.md; tests for reproduced general defects.
- [x] Freeze development and source-separated heldout dialogues before paid calls, covering the
  spec's positive, ambiguous, temporal and failure workflows with exact expected source relations.
- [x] Run selected Luna/Lite defaults, unforced native actions and actual SQLite writes/reopen.
  Log every call, latency, usage, actual saved content, selected sources and final answer.
- [x] Trace failures by stage; reproduce general defects with a failing regression before repair.
  No fixture-specific runtime rules or omitted failed saves. Opened holdouts become development/regressions;
  any proposed promotion requires fresh source-separated confirmation.
- [x] A bounded Flash comparison may diagnose model limitations; no automatic runtime fallback or
  silent model substitution. Report a failed selected-model gate rather than claim readiness.
- [x] Run final fresh dialogues, natural public-video diagnostic and offline local-data checks.

## Task 7: Final verification, cleanup, evidence and backup

- [x] Run full pytest, Ruff lint/format, existing JS syntax, synthetic browser boundaries and local
  source preservation checks. Inspect failures before changing code. No real capture hardware.
- [x] Search imports/callers to prove deleted planners, judges and departure implementations are
  gone; one shared policy/tool contract remains. Keep data migration and API adapters clearly scoped.
- [x] Update decisions/design/architecture/scope/milestones/README/AGENTS together with measured
  outcomes, model IDs, remaining failures and exact provider usage. No CI/merge-ready shortcut.
- [x] Review the whole diff inline, resolve material findings, commit; optional backup ONLY to
  work/memory-reliability. Verify remote main/UI/original recordings unchanged. No new PR yet.

## Historical execution checkpoint at61da728 — 2026-11-17

Tasks1–5 implemented and committed; no UI/main changes. Task6 found general memory16/16 correct
final answers, recall7/8 exact-source proxies with8 correct answers, but default identity/depiction
and Hindi identity caveats fail. SeeR30 for every repeated/failed run and costs. Task7 checks passed
at61da728:456tests27.05s, lint/format/JS/synthetic browser; private final2-row conversion unchanged.
No new PR/merge or readiness claim. Current quality iteration: experiment-only shorter reference
prompt passed core4/4; hard identity retest pending. Alternative agent wording did not fix Hindi;
new8-case bilingual source fidelity conditions frozen before low/medium reasoning comparison.
Default prompts/models stay until broader confirmation, not just the small development score.


## Root-cause checkpoint — 2026-11-17,8fd7c8f

Task6's bounded evaluations were executed; **the visual acceptance gate remains failed**.
Marking the measurement steps executed does not mark the overall product goal complete.
Scene-first output helps depiction tests but regresses appearance controls; it stays experiment-only.
The latest user requires minimal root-cause repairs, no further expansion of this checkpoint.

Two source regressions were first reproduced, then repaired at the storage/context boundary:
independent user facts survive unrelated lookup deletion; repeated assistant answers retain their
original evidence dependencies in both adapters. Legacy rows migrate conservatively. No new
judge, model fallback or prompt rule. Full suite471 passed45.40s; latest targeted150 passed5.59s.
Ruff113 files, JS syntax and synthetic Chrome compatibility pass. UI/main are unchanged.
Conservative cumulative usage5.32630835/8; paid runs stopped. Updated evidence is inR30.

Still open beyond this checkpoint: core ambiguous-object/physical-scene quality and real household/
acoustic/user acceptance. These are explicit remaining goal gates, not reasons to add infrastructure.
Local engineering verification and documentation are complete; optional publication is restricted
to the work branch. No new PR or merge is requested. The overall goal remains open for the gates above.


## Followup at4db9329 — historical scope and ordinary inspection

Historical-recall background scope now follows the explicit lookup cutoff in both adapters;
recall-v4 passes8/8 source/workflow proxies and8 reviewed final replies. Ordinary single-image
scene inspection is adopted separately: exact call equivalence to the tested candidate, all4
full public-history workflows reviewed correct, and reference-image comparison request unchanged.
The failed combined scene/appearance candidate remains experimental. Full suite479 passed25.81s;
lint/format113 files and JavaScript checks pass. SeeR30 for the new category-proxy error and all
model-comparison failures, not just aggregate improvements.

The shorter whole-view reference experiment still fails the phone ambiguity gate. The current
Lite reference role remains as selected by the user. A concrete unapplied proposal uses Luna for
both reference tasks and Lite for ordinary inspection; offline dispatch checks pass, but broader
acceptance is unproven. This default model-role decision and household/acoustic/user acceptance
remain open. Conservative cumulative provider usage5.37098615/8; all paid runs stopped.


## User-run household and voice check

Status: pending. The isolated instance is running at **http://127.0.0.1:8001**, using
`data/household-check-2026-11-17`; original recordings/memories were not imported. Its12 lookup
acknowledgement clips are prepared and the pinned wake model loads. No browser or hardware was
opened by automated testing. The normal app uses the configured cloud providers for selected
images and activated speech. Use the existing controls yourself when ready.
Actual LiveKit/Sarvam streaming reply synthesis also returns valid English/Hindi audio; playback
quality and room behaviour remain part of this check.

1. Show one clear everyday item and say “Hey Nyx, I put this in the hallway drawer.” Lower it,
   then ask by name where you said you put it. Expect the remembered report with a useful item
   description; it must not claim the item is still there or invent a proven identity.
2. Report a normal move, then explicitly correct that report. Ask for the latest remembered
   place. Expect the corrected report, with earlier reports retained as history.
3. Say you plan to put an item somewhere later. Ask whether you have already done it. Expect
   a plan, without a claim of completed placement, scheduling or proactive delivery.
4. Present two plausible items and say only “I put this on the table.” Expect a clarification.
   Supply the distinguishing detail and check that the intended item is remembered.
5. Try an English and a Hindi spoken question, including wake, an interruption and the reply.
   Check intelligibility, correct language, microphone mute/stop and whether normal room noise
   or the assistant's own speech causes unwanted turns.

Report pass/fail and the issue type; raw household footage/private transcripts do not need to be
sent to the thread. These user-run observations are required because automated verification is
limited to synthetic/public inputs and may not activate actual camera/microphone hardware.
If the server is stopped, restart it with:

```bash
uv run --env-file .env --no-sync nyx --data-dir data/household-check-2026-11-17 serve --port 8001
```

The model split proposal is withdrawn: fresh reference tests score Lite5/5 versus Luna4/5.
Keep the selected defaults. The old ambiguous-phone/paired-depiction failures and short synthetic
Hindi errors remain documented; this check does not silently waive those acceptance gates.
