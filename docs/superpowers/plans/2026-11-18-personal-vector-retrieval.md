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

- [ ] Add failing regressions for vec0 migration/ranking and candidate-bounded validation.
- [ ] Implement `memory_vectors.py` connection/backfill/KNN and transactional indexing in
  `personal_memory.py`; narrow `_read_rows(..., identifiers=...)` to records and dependencies.
- [ ] Run memory tests, review migration/filter semantics and commit vector retrieval.
- [ ] Remove spoken recall barrier; move early/current context validation to background
  threads, suppress background clarification questions without discarding raw input.
- [ ] Test blocked-writer recall and quiet unresolved saves; run focused/full checks and commit.
- [ ] Replay a copied local manual-test database offline, compare SQLite/Python ranking,
  benchmark realistic vector sizes, document evidence/limitations and commit findings.

Execution and final self-review stay inline under the repository's no-subagent instruction.
