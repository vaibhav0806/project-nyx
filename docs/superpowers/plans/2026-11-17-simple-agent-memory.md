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
- [ ] Add failing contract tests for equal voice/text tool names, descriptions and schemas;
  actual selected call binding, multi-step continuation, rejected arguments, cancellation and sources.
- [ ] Extract the existing look_for_object/remember/recall/identify contracts into one module.
  Tools consume the actual utterance and server-owned evidence; source/turn IDs are server-bound.
- [ ] Use native chat-completion tool calls for typed execution with the same policy and tools;
  adapt results into existing API observations/steps/sources/review_context fields. Retain voice IO.
- [ ] Delete CloudVerifier.decide's long JSON-planner prompt/action-loop implementation when callers
  use the shared native contract. Keep validation/execution, not two live planning implementations.
- [ ] Run API, SDK binding, context/source and cancellation tests; commit after GREEN.

## Task 3: Automatic general memory and lossless existing data

Files: create src/nyx/personal_memory.py and tests/test_personal_memory.py; integrate voice.py,
 companion.py and shared agent tools; consolidate statements.py rather than retain a second writer.
- [ ] Add failing persistence/restart tests for facts, preferences, reports, plans and no-op input.
- [ ] Implement memory turn processing: retrieve related candidates, one compact Luna interpretation,
  validate operations, persist atomically. Return relevant memories and any clarification needed.
  Sources are actual user-turn/evidence IDs. Successful processing is idempotent by input turn.
- [ ] Add failing ordinary-move versus explicit-correction/retraction tests. Persist links/history;
  validate real prior IDs, source availability and chronology. Main agent never chooses database IDs.
- [ ] Add provider/embedding/write-failure tests: preserve raw input; no partial links or false success.
- [ ] Add existing-R29-store conversion/read tests, source deletion and context-eviction tests.
- [ ] Wire automatic processing into typed and activated spoken turns with one owner per turn;
  memory results reach response generation. Do not add a separate autonomous agent loop.
- [ ] Run targeted persistence, context, API and voice tests (GREEN); commit.

## Task 4: Single visual path and removal of redundant judges

Files: reference.py, verification.py, personal_memory.py, agent_tools.py, statements.py and tests.
- [ ] Add failing real-protocol tests for a short object observation, earlier supporting frame,
  explicit text-only memory, missing/ambiguous object, depicted object and different source clocks.
- [ ] Consolidate reference policies into a single task; carry observed source/uncertainty metadata.
  Keep original source timestamps and evidence separation. Use Flash-Lite and schema field docs.
- [ ] Delete the independent ambiguity call, separate correction-check call, duplicate reference
  policy flag and optional duplicated visual-scene prompt variants; update experiment callers.
- [ ] Assert protocol traces contain no removed judges. Retain clarification/failed-source behavior
  and actual source validators. Known unsafe R29 inputs remain acceptance regressions.
- [ ] Run visual, memory, source-failure and API tests; commit after GREEN.

## Task 5: Retire departure feature without harming recording or the UI contract

Files: companion.py, realtime.py, observation.py, intentions.py, reminders.py, verification.py,
 app.py as actual imports require; relevant tests. Do not edit src/nyx/web.
- [ ] Add failing API tests for no active departure tools/AI calls and compatible inactive observation/
  delivery polling; recording/indexing remains functional and original reminder rows preserved.
- [ ] Remove departure-specific runtime wiring, model prompts, detection/tracking and scheduling
  implementations. Keep cached lookup acknowledgements. Preserve existing historical data.
- [ ] Remove obsolete tests/experiment imports only with replacement coverage for retained contracts.
- [ ] Run recording/import/source/voice API/browser boundaries and commit after GREEN.

## Task 6: Real model acceptance and iteration

Files: experiments/companion/simple_agent_replay.py and simple_agent_cases.json;
 docs/research/R30-simple-agent-memory.md; tests for reproduced general defects.
- [ ] Freeze development and source-separated heldout dialogues before paid calls, covering the
  spec's positive, ambiguous, temporal and failure workflows with exact expected source relations.
- [ ] Run selected Luna/Lite defaults, unforced native actions and actual SQLite writes/reopen.
  Log every call, latency, usage, actual saved content, selected sources and final answer.
- [ ] Trace failures by stage; reproduce general defects with a failing regression before repair.
  No fixture-specific runtime rules; do not tune on opened heldout outputs or omit failed saves.
- [ ] A bounded Flash comparison may diagnose model limitations; no automatic runtime fallback or
  silent model substitution. Report a failed selected-model gate rather than claim readiness.
- [ ] Run final fresh dialogues, natural public-video diagnostic and offline local-data checks.

## Task 7: Final verification, cleanup, evidence and backup

- [ ] Run full pytest, Ruff lint/format, existing JS syntax, synthetic browser boundaries and local
  source preservation checks. Inspect failures before changing code. No real capture hardware.
- [ ] Search imports/callers to prove deleted planners, judges and departure implementations are
  gone; one shared policy/tool contract remains. Keep data migration and API adapters clearly scoped.
- [ ] Update decisions/design/architecture/scope/milestones/README/AGENTS together with measured
  outcomes, model IDs, remaining failures and exact provider usage. No CI/merge-ready shortcut.
- [ ] Review the whole diff inline, resolve material findings, commit; optional backup ONLY to
  work/memory-reliability. Verify remote main/UI/original recordings unchanged. No new PR yet.
