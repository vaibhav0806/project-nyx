# R30 — Does a simpler agent preserve reliable general memory and household recall?

Owner: Codex inline, user-authorized 2026-11-17. **In progress; not household acceptance.**

## Decision and method

Implement the approved [design](../superpowers/specs/2026-11-17-simple-agent-memory-design.md)
with one shared native agent policy/tools, Luna conversation/memory and Flash-Lite vision.
Remove the legacy typed planner, separate judges and departure-specific runtime. Keep UI/main,
original sources, Gemini Embedding2 and Sarvam unchanged. Development cloud inputs are exclusively
synthetic/public; private Mac recordings remain offline. Key metadata verified $8 cumulative,
starting usage $4.73185091; per-run ≤$0.25 with settlement headroom, no overlapping paid runs.

Real-model runs use `recall_workflows.py` and `household_workflows.py` through actual memory
interpretation, embeddings, SQLite and native API response generation. Source attribution scores
are **proxies**, not final-answer semantic accuracy. Inspect actual answers, setup records,
visual support, correction links and provider traces. Failed runs stay in the denominator.
Old R29 cases are reused regression/development evidence, not fresh unseen household accuracy.

## Interim measured findings

- Deterministic migration checkpoint:434 tests passed30.02s at bb669d9, Ruff/diff checks clean.
  Retired assertions were replaced with actual shared SDK/API, source, persistence and failure
  coverage; the reduced count is not a before/after coverage metric.
- `data/runs/simple-memory-recall-development-v1`:8/8 source/workflow proxies, actual final answers
  reviewed and consistent with expected meanings. Cost$0.0024302. Includes plans, normal moves,
  corrections, Hindi, source loss and restart/chat eviction. This is a small synthetic regression.
- `simple-memory-recall-holdout-v1`:3 clear passing completed cases, historical/irrelevant-source
  failures and malformed memory operations; run aborted during seventh setup, eighth not run.
  No successful-job-only denominator. Memory selection and ingest protocol were repaired rather
  than restoring an extra judge. Current user quotes are required; future prior turns excluded.
- `simple-memory-recall-holdout-v2` at dbf4799:8/8 **source proxies**, cost$0.0031297. Final-answer
  review found a real unsafe answer in the future-date negative: the memory query excluded the
  future report but ordinary conversation history exposed its text. This run is **not8/8 semantic
  acceptance**. Added source/clock-aware transcript withholding and regression tests; rerun pending.
- `simple-memory-household-development-v1`:1/4 complete setup+recall proxies. The agent could save
  an unspecified deictic report before asking for visual identity, then recall that ungrounded
  record despite having clarified at the surface. Latest-only selection also returned both moves.
  Corrected bottle passed; generic/unsupported identity records are not acceptable household memory.
  Repair in progress: memory must resolve references before saving/selecting, use real related IDs
  for context-derived meaning, retain inherited visual clocks/photos and transitive sources.
- `simple-memory-local-audit-v1`: all92 existing videos fully decoded, original byte hashes unchanged;
  256 stored-vector queries against a copied1085-frame index. No acoustic or private semantic inference.
- `simple-memory-private-conversion-v1`: actual two old statement rows converted on a copied database;
  original rows/database/vectors/photos unchanged, zero inference. Original timestamps preserved.

## Fresh conditions frozen before inference

`experiments/companion/general_memory_workflows.json` adds16 synthetic general-memory conditions:
preferences, habits, events, multiple facts, plans, ordinary changes, corrections/retraction,
Hindi/Hinglish, hypothetical/question negatives, missing referents and restart/eviction. Each
records expected meaning for manual answer review, separate development/holdout source groups.
These are authored synthetic conditions, not a natural user population or external benchmark.
The file is committed before its first provider run; retain its hash in each result artifact.

## Still required

Rerun repaired recall and shown-item paths, challenge ambiguous/lookalike regressions, verify
fresh general-memory conditions and public visual category/depiction/natural-video data, exercise
spoken native selection/continuation with the same automatic memory preparation, and audit final
answers. Preserve all failures and actual costs. Real physical household identity, acoustic
turn-taking and human acceptance remain separate; no demo/recording production in this pass.
