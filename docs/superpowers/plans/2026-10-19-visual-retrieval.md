# M1 — Local visual retrieval

Authorized: user requested work to resume on 2026-10-19.
Spec: [Scope](../../scope.md), [Architecture](../../architecture.md).
Execution: inline; no subagents, commits, or pushes requested.

## Deliverable

A reproducible local CLI to index a supplied clip into SQLite/`sqlite-vec`, query it with an aligned encoder, and produce source-linked candidate results and an HTML gallery. No camera capture, cloud calls, VLM verification, or voice in this slice.

## Tasks and checks

1. Replace the interrupted flat-module draft tests with tests for real SQLite vector ranking/persistence, incompatible encoder rejection, transaction failure, media timestamps, and invalid inputs. Run and observe missing implementation failures before code.
2. Implement `src/nyx/memory.py`, `capture.py`, `perception.py`, `retrieval.py`, `report.py`, and `cli.py` only as required. Use lazy optional vision imports. Add semantic tests only as separately executed benchmarks.
3. Benchmark a pinned SigLIP 2 checkpoint on permitted public images assembled into a clip, including positive, absent, crop/obscured, and duplicate cases. Preserve scene labels, known clip intervals, metrics, and failures. Public samples are a smoke benchmark, not proof of household-object accuracy.
4. Run deterministic tests, lint, CLI smoke checks, and a separate fresh self-review. Document actual performance, run commands, and remaining M1 gaps.

## Execution notes

- Ruling: work in the existing `feat/visual-memory` branch. This is an unborn repository with no base commit or existing application; an additional worktree provides no useful source isolation here.
- Ruling: source-linked CLI/gallery is the bounded M1 deliverable. Live capture and the interactive application remain M2.
- Ruling: no automatic commit or subagent review; user instructions take precedence over skill defaults. Perform a separate self-review.
- The legacy draft `tests/test_nyx.py` is replaced because it assumes an unimplemented flat module and API beyond M1; preserve its persistence, sampling, and invalid-media scenarios in the new tests.

## Progress

- Setup: complete; Python 3.12 environment, optional vision dependencies, MPS and SQLite extension verified.
- Storage/import/search/gallery: implemented; deterministic RED-to-GREEN cycles cover ranking/persistence, timestamps, identity, partial failures, gallery escaping, CLI bounds and dataset labels.
- Real-model experiment: corrected public-image runs completed on MPS, including cached offline execution. See R3 results; actual household clips remain an M1 gap.
- Validation: 19 tests passed both in the working environment and an isolated environment without optional vision dependencies. Ruff lint/format, compile checks, wheel/sdist build and contents, Markdown links, and actual CLI index/search/list artifacts passed. Cached offline MPS inference completed.
- Self-review: checked model/preprocessing identity, partial-import visibility and cleanup, actual sampled timestamps, query bounds, gallery escaping and evidence references, benchmark labels, and documentation claims. No further blocking issue found for this bounded baseline; household recall and browser rendering remain unverified.
- Ruling: use a generated candidate gallery rather than an API/browser app for M1. It makes source evidence reviewable without expanding into M2; future app integration remains necessary.
- Ruling: the sample dataset uses four public images and derivatives. Treat it as a feasibility smoke test, keep M1 in progress until independently labelled household clips are evaluated, and report occurrence misses alongside query hit rate.
- Ruling: the optional IAB browser was unavailable, so no visual browser-rendering claim is made for the gallery. Content/link escaping and generated evidence references are verified separately.

## Follow-up — Spatial crop comparison

User requested continuation after reviewing the working baseline. Continue the existing M1/R3 crop experiment from the architecture; no live capture or later milestone is started. Implement inline, without commits or subagents.

Goal: compare full-frame embeddings against full-frame plus four overlapping corner crops on identical extracted frames. Rank each source frame once by its best view. Preserve the full-frame application default until independent household evidence supports a change.

- [x] Extend `experiments/image-text-retrieval/run.py` with crop generation, per-frame max-view ranking, and occurrence scoring. Record every positive occurrence's rank, recall at 1/3/5, average precision and latest-labelled-occurrence rank. These are coarse scene labels, not verified last-seen answers.
- [x] Test crop coverage on odd-sized images, frame deduplication, deterministic tie order, and scoring with more relevant occurrences than top-k slots in `tests/test_nyx.py`; observe failures before implementation.
- [x] Run both strategies with the cached pinned encoder on the same decoded frames. Record inference/view count, timing, negatives and source-linked galleries; treat the small correlated fixture as diagnostic only.
- [x] Update R3 and experiment instructions. Tests: 22 passed; Ruff lint clean. Offline MPS run `siglip-crops-005`: no recall@3/@5 improvement, marginal AP gain, five views per frame. Full-frame remains the default. Household evaluation is pending; manual capture UI follows separately.

Review focus: crop boundaries must preserve edge pixels; five views must not occupy five result slots for one frame; recall denominators must count all relevant scenes; absent targets must not acquire false presence labels; comparison must use identical media and model weights. No production schema or dependency change is needed.
