# Recall and context engineering implementation plan

> Execute inline using superpowers:executing-plans. User explicitly authorized this scope and
> sustained execution; do not request another plan approval or spawn subagents.

**Goal:** Improve complete recall and context behavior against labeled evaluations and fault cases.
**Architecture:** One Python/SQLite application; bounded source-aware recent context plus explicit
durable retrieval. Experiments exercise real tools/storage and separate provider-quality evidence.
**Tech stack:** Existing Python 3.12, FastAPI, SQLite/sqlite-vec, LiveKit and OpenRouter environment.
**Spec:** [Approved scope](../specs/2026-11-15-recall-context-design.md).

## Global constraints

Stay on `work/memory-reliability`; optional branch-only pushes, no main edits. No frontend edits.
Public/synthetic developer inputs, no hardware/private uploads. Original recordings and 1 GiB
stop-without-delete policy stay intact. Keep cumulative provider tests inside $2; use cached data
and guarded calls. No new paid account/service. Work inline, with author review explicitly labeled.

## Review focus

- Deleted-source assistant claims must not leak back through typed or live spoken context.
- Long chat/tool histories must remain bounded without orphaning a function result from its call.
- Pronoun/attribute continuity must not turn an unrelated task into the prior object's search.
- Durable report recall must survive restart/eviction, preserve correction/as-of semantics and abstain.
- Multi-day replay clocks must not masquerade as source capture timestamps or continuous coverage.

### Task 1: Labeled workflow baseline

Files: `experiments/companion/recall_workflows.py`, a frozen JSON case file, scorer tests.
Interface: labeled cases carry split/group, source reports, query, expected cited IDs/kind/location;
result rows retain selected IDs, exact answer, failures, elapsed time and provider cost.
- [x] Write scorer/manifest tests for wrong/extra citations, negatives, failed/missing outputs and leakage.
- [x] Run RED, implement the bounded harness using Conversations/Statements/API and guarded clients.
- [x] Freeze development/holdout conditions covering eviction, restart, corrections, negatives,
  similar objects and English/Hindi/Hinglish; record the baseline without tuning holdout.
- [x] Verify focused tests, record R19 baseline evidence and commit.

### Task 2: Source-aware bounded context

Files: `voice.py`, `companion.py`, `verification.py`, `realtime.py`, relevant tests;
small context helper only if responsibility warrants it. Consume Task 1 failure cases.
- [x] Reproduce invalidated typed answers and oversized typed/live history with failing real-boundary tests.
- [x] Implement bounded recent context, preserving attribution/query constraints; suppress unavailable
  assistant claims/metadata. Preserve current tool exchange and avoid unsupported summaries.
- [x] Verify typed/spoken wiring, long-chat/restart/pronoun regressions and source invalidation.
- [x] Run suite and quality development comparisons; commit only evidence-backed behavior.

### Task 3: Measured recall/verification fixes

Files: retrieval/statements/answers/verification and experiments only as reproduced failures require.
Consume frozen Task 1 development cases; holdout stays untouched for final selected comparison.
- [x] Trace development misses to candidate selection, temporal eligibility, citation or model routing.
- [x] Add failing regressions before minimal fixes; retain uncertainty and identity/source boundaries.
- [x] Compare development quality/latency and choose defaults; no decay/reference promotion on mixed evidence.
- [x] Run affected/full checks and commit findings, including unresolved cases.

### Task 4: Multi-day capacity and fault replay

Files: experiment harness and focused API/recording regression tests; no UI or new storage policy.
Consume real capture/index interfaces and synthetic date labels, preserving source/replay time distinction.
- [x] Add tests for replay scoring/capacity math and failed/interrupted work, then implement bounded replay.
- [x] Exercise known ten-day events/gaps, dated/undated/future/older sources, restart and backlog.
- [x] Measure generated-video bytes, sample/index throughput and additional index storage; project
  capacity transparently rather than claiming ten days ran. Reuse offline model boundaries for load.
- [x] Record failures, limits and capacity recommendation; verify and commit.

### Task 5: Hydra supported-interface decision

Files: research R20 and a reproducible isolated synthetic probe if a new interface is found.
Consume R14 deployed revision/namespace and public engine documentation; other project stays untouched.
- [x] Inspect current official interface/source and installed-revision capabilities; distinguish memory service.
- [x] Probe supported native vector operations on Nyx-only data if documented; compare identical vectors
  and filters against SQLite if capability exists. No all-vector download disguised as remote ranking.
- [x] Record exact response/revision/limitations; integrate only a useful tested route or retain SQLite.
- [x] Verify documentation/probe boundaries and commit the verdict.

### Task 6: Held-out evaluation and final review

- [x] Freeze selected changes and run held-out end-to-end cases with failures/costs counted.
- [x] Review the whole pass inline; fix important findings with regressions, label review as author's.
- [x] Run full pytest, Ruff, JS syntax, links/diff and relevant synthetic browser checks.
- [x] Update milestones/decisions/design/scope/architecture with measured behavior and remaining limits.
- [x] Commit clean branch; optional branch-only push. Confirm UI/main preservation and goal completion.

Final evidence: [R19](../../research/R19-recall-context.md), [R20](../../research/R20-hydra-interface-verdict.md)
and [R21](../../research/R21-multi-day-runtime.md). Author review found live-session invalidation
and report-selection/intent gaps; a fresh frozen12-case report set followed the original diagnostic
unblinding. Mixed positive-vision corroboration remains opt-in. Final484 tests and synthetic
browser passed; larger household/speech/continuous-operation gates remain explicit in milestones.
