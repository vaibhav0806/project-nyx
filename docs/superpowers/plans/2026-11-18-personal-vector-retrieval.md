# Personal vector retrieval implementation plan

Execute inline as authorized; no subagents.

**Goal:** SQLite-native personal-memory search without foreground corpus walks or recall barriers.
**Architecture:** additive fingerprint-specific vec0 index, transactional write-through, bounded
record/dependency validation. Existing memory data remains authoritative.
**Tech stack:** Python, SQLite, installed sqlite-vec, existing LiveKit adapter.
**Spec:** ../specs/2026-11-18-personal-vector-retrieval-design.md

## Constraints and review focus

Preserve branch/main/UI/source data; no paid inference or private uploads. Check stale index
entries, corrected/deleted candidates ahead of valid candidates, historical state, restart,
and failed/unresolved saves. Do not trade recall correctness for a fixed oversampling limit.

## Tasks

- [x] Add failing regressions for vec0 migration/ranking and candidate-bounded validation.
- [x] Implement `memory_vectors.py` connection/backfill/KNN and transactional indexing in
  `personal_memory.py`; narrow `_read_rows(..., identifiers=...)` to records and dependencies.
- [x] Run memory tests, review migration/filter semantics and commit vector retrieval.
- [x] Remove spoken recall barrier; move early/current context validation to background
  threads, suppress background clarification questions without discarding raw input.
- [x] Test blocked-writer recall and quiet unresolved saves; run focused/full checks and commit.
- [x] Replay a copied local manual-test database offline, compare SQLite/Python ranking,
  benchmark realistic vector sizes, document evidence/limitations and commit findings.

Execution and final self-review stay inline under the repository's no-subagent instruction.

Verification: 506 tests/34.07s; Ruff/format pass. Commits47f64f1 and912d83d cover
vector retrieval and independent reads. Final self-review found a tied-KNN recency omission;
new regression failed then passed after SQL tie resolution. R36 records final offline
manual replay and scale evidence. No source/main/UI change, inference or service restart.
