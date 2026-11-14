# Memory reliability implementation

Spec: [approved workstreams](../specs/2026-11-15-memory-reliability-design.md).
User authorized execution and regular commits on 2026-11-15, then required a local branch and
no push to main. Work inline on `work/memory-reliability`, keeping commits local; do not delegate. Existing drafts
are this session's research/design. Provider spending and private media boundaries still apply.

## Constraints and interfaces

The user's later explicit instruction excludes UI changes. Preserve contributors' existing UI;
do not edit `src/nyx/web/` or alter frontend behavior. Backend changes retain current API contracts.

Keep one Python application and authoritative SQLite/source files. Derived vectors carry encoder
fingerprints and stable source IDs. Preserve recordings and 1 GiB stop-without-delete behavior.
Use public/synthetic fixtures, no hardware. A backend can change only after measured capability
and source-availability checks; no silent production switch follows a connection test.

Capture selection takes ordered `(offset_seconds, image_or_path)` rows and returns original rows.
History candidates retain `id`, `video_id`, `offset_seconds`, `observed_at` and encoder identity.
Temporal policy takes an explicit aware clock; unknown times remain unknown. Correction links
reference existing persisted statement IDs without rewriting source transcripts or observations.
Tests use real storage/action boundaries with fake inference only at external providers.

## Review focus

- A new irrelevant/undated/future candidate must not become a valid current or dated answer.
- Brief objects must be counted as missed if no selected sample contains them.
- Neighboring segments must not monopolize nomination or merge across unrelated capture sessions.
- An explicit correction affects current reports without erasing historical evidence.
- Remote IDs must resolve to available authoritative sources; server loss/deletion must be honest.

### Task 1: Isolated Hydra capability trial

- [x] Inspect only deployed Hydra metadata and host capacity, never other project data/secrets.
- [x] Create a bounded separate Nyx service/volume/token if existing graph isolation is insufficient.
- [x] Verify health, auth isolation, synthetic 768-dimensional vector round trip, and actual server
  similarity-query capability. No embedding inference is needed to reuse vectors.
- [x] Record query results, image revision, limitations and decision in R13 or a dedicated finding.
- [x] Check Markdown links/diff and commit plan/research/status with normal hooks.

Expected: isolated usable storage and a factual retrieval capability verdict; missing native
vector operations are reported, not replaced by claims that local ranking ran on Hydra.

### Task 2: Labeled replay and sampling coverage

Files: `experiments/companion/memory_replay.py`, `tests/test_memory_replay.py`,
`src/nyx/attention.py`, `src/nyx/retrieval.py`, related existing tests.

- [x] Add failing tests for manifest/source-time validation, event-overlap scoring, independent
  splits and real selector comparison. Add the reproduced 3.0–5.9-second small-object regression.
- [x] Run focused tests and inspect intended failures before implementing minimal harness/coverage.
- [x] Implement a bounded periodic sampling floor combined with activity samples, preserving offsets
  and recording actual selection policy. Keep live proactive-event filtering separate.
- [x] Run replay with generated scenes and permitted cached fixtures. Report actual case counts,
  event retention and extra samples; generated cases are not household accuracy.
- [x] Run focused storage/indexing tests, lint and commit.

Expected: deterministic selector comparison and retained sample in the known missed interval.

### Task 3: Candidate nomination and representations

Files: `src/nyx/answers.py`, `src/nyx/retrieval.py`, `src/nyx/memory.py`,
`src/nyx/perception.py`, relevant tests and replay harness.

- [x] Write failing cross-segment diversity and reference-image nomination tests with real Store.
- [x] Add source-time-aware diversity and bounded text/image candidate fusion while preserving
  excluded IDs, time filters, known-time policies and final verification.
- [x] Benchmark representation variants on frozen cases. Keep model/format changes versioned and
  existing indexes intact. Verify native-video wire support only within remaining authorized budget.
- [x] Promote measured improvements; record unavailable/untested variants explicitly.
- [x] Run focused/full tests as appropriate and commit.

Expected: improved targeted nomination without timestamp, identity or attribution regressions.

### Task 4: Memory policy and correction semantics

Files: a cohesive `src/nyx/memory_policy.py` if needed, `statements.py`, agent/tool validation,
verification prompts and tests; avoid a general framework.

- [x] Write failing policy tests for exact historical requests, future/unknown times, irrelevant
  fresh records, explicit correction, ambiguous contradiction and source deletion/restart.
- [x] Implement versioned query-aware freshness ranking as an opt-in evaluated policy, not expiry.
- [x] Add minimal attributed correction links with validated target IDs and idempotent persistence;
  preserve old reports for historical requests and keep observations distinct.
- [x] Compare no-decay and permitted policy variants using cached compatible artifacts; freeze
  selected behavior before untouched evaluation. Keep access reinforcement disabled.
- [x] Run storage/action/planner/voice regression tests and commit.

Expected: explicit corrections survive restart and do not rewrite source truth or historical recall.

### Task 5: Justified backend route and recovery

- [x] Resolve the remote-route gate: Task 1 did not establish native similarity support, so the
  conditional Hydra runtime integration is not applicable. Keep the compatible vectors/local sources.
- [x] If capabilities are absent, retain local retrieval and report the evidence; do not introduce
  a substitute service or speculative backend registry.
- [x] Add regressions for unavailable/stale index, interruption, restart/backlog and full storage.
- [x] Verify backend capture/index/voice health and recovery through existing interfaces; keep UI unchanged.
- [x] Run synthetic browser verification and actual regression suite; commit the coherent slice.

Expected: honest backend failure/recovery behavior with preserved evidence and unchanged UI.

### Task 6: Final verification and evidence

- [ ] Freeze and run the selected held-out evaluation, counting failed/incomplete cases and costs.
- [ ] Run full pytest, Ruff check/format, JavaScript syntax, Markdown links and diff checks.
- [ ] Review the whole change inline as required by the user's no-subagent instruction; fix
  important findings with regressions. Do not claim independent review or hosted CI.
- [ ] Update milestones/decisions/architecture/scope with actual delivered behavior and unknowns.
- [ ] Commit verified increments locally on the work branch; do not push to main.

Expected: exact reported checks, clean working tree, evidence-backed claims and remaining limits.
