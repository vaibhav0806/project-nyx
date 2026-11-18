# R36 — SQLite-native personal memory and independent reads

Date: 2026-11-18. Owner: Codex inline. Implemented; offline verification, not new acoustic acceptance.

## Decision and method

User approved quiet best-effort background saves, immediate committed-memory reads, linked
sqlite-vec storage and bounded validation. One continuous chat supplies recent context; immediate
read-after-write consistency is deliberately not promised. Keep existing models/embeddings/UI.

`memories` remains authoritative; a fingerprint-specific vec0 table holds existing vector bytes
and IDs. Backfill is additive and uses no embedding inference. New records and index entries
commit atomically. Encoder changes retain old records/indexes. Invalid/incompatible vectors stay
out; vector-byte drift is checked only on nominated candidates. Metadata eligibility runs inside
SQLite before KNN. Candidate validation reads only nominated records and their dependency closure;
invalid chains refill from later batches without a fixed candidate ceiling.

SQLite seconds provide a conservative date prefilter; Python checks exact microseconds on
retrieved records and replacement dates. Existing historical regression caught the lossy Julian-day
comparison during implementation. KNN's arbitrary selection across equidistant batch boundaries
also failed a new latest-first regression; tied boundaries now use native SQL cosine/recency
ordering. This path can scan eligible vectors inside SQLite but never transfers the vector corpus
to Python. No ANN or constant-time retrieval claim.

Spoken recall no longer waits for memory interpretation. Writes remain ordered. Prepared current
context and early candidate validation run off the voice event loop. Unresolved background receipts
remain internal, with neutral status and no delayed question; raw input and original receipts remain.
Coverage counts now describe inspected candidates, not a fabricated full-archive unavailable count.

## Measured results

Command:

```sh
uv run --no-sync python experiments/companion/personal_vector_check.py \
  --manual data/runs/early-memory-recall-evidence-v2 \
  --output data/runs/personal-vector-check-2026-11-18/final-results.json
```

Baseline is pinned repository code at4feac67. Five warm repetitions per size, seeded random
768-dimensional normalized vectors and a precomputed query; provider latency excluded.
Runtime: Python3.12.11, macOS15.7.3 arm64, SQLite3.50.4, sqlite-vec0.1.9.

| Records | Baseline recall median | vec0 recall median | Five-record revalidation | Additive backfill |
| --- | --- | --- | --- | --- |
| 1,000 |17.17ms|17.17ms|0.29ms|160ms|
|10,000 |180.45ms|106.90ms|0.30ms|1,740ms|

Exact top-five parity holds in both synthetic runs. The small collection has no measured speed
gain; 10k improves about41%. This includes local retrieval/filtering/validation, not voice latency.
One source turn supports synthetic records, so dependency diversity/write contention are not
representative. No larger capacity or p95 claim is established.

The preserved original manual missing-phone trial was replayed on a SQLite backup, with original
dialogue/answers already excluded from recent context. Actual query and existing three memories
went through production BackgroundMemory prefetch/context, with inference functions forbidden.
All three original candidates remain: shown-phone report, kitchen plan and kitchen-shelf plan.
The useful shelf lead remains a user plan, not a verified placement. Preparation3.06ms. Original
database hash and every copied memory row, including vector/photo bytes, remain unchanged.

This is retrieval/context parity on real saved data. No new conversational model, visual recognition,
STT/TTS or audible output was evaluated; previous R35 wording/latency evidence does not become a
new universal guarantee. Raw private results stay ignored. No hardware, paid inference or private
upload; cumulative provider usage unchanged by this pass. Running services were not restarted.

## Verification and remaining limits

Regression coverage includes native backfill, bounded candidates, invalid-leading-candidate refill,
vector drift, separate encoder indexes, transactional rollback, correction/retraction, source
withdrawal, timezone/microsecond state, blocked-writer nonblocking recall, quiet unresolved input
and off-event-loop validation. Full suite:506 passed34.07s; Ruff/format pass.
Final review performed inline under the no-subagent instruction; not independent PR review.

Query embeddings may still involve network latency. Exact KNN still scales with eligible vectors;
sqlite-vec is not a promise of ANN indexing. Optional relevance selection remains unchanged.
Interrupted/crashed unsaved inference still lacks durable automatic replay. Live household and
acoustic acceptance remain separate. PR CI/review gates are not established by this local pass.

Primary reference: [sqlite-vec KNN documentation](https://alexgarcia.xyz/sqlite-vec/features/knn.html).
