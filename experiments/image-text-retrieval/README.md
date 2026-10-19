# Image/text retrieval baseline

Question: can a small local aligned encoder retrieve source-linked visual moments on the M4 Pro without a generative VLM?

This is an R3 semantic smoke experiment. It reuses the application capture, encoder, storage, search, and gallery code. It is not a household-camera accuracy evaluation or a motion/event benchmark.

## Run

From the repository root, with FFmpeg on PATH:

```bash
uv sync --python 3.12 --extra vision
uv run --no-sync python experiments/image-text-retrieval/run.py \
  --download-samples --output data/runs/siglip-baseline
```

The explicit `--download-samples` flag fetches four public reference images into `data/evaluation/source/`. The first model use downloads the pinned Google SigLIP 2 checkpoint into the normal Hugging Face cache. No input image or clip is sent to a provider for inference.

After those files have been downloaded, verify cached execution separately:

```bash
HF_HUB_OFFLINE=1 uv run --no-sync python experiments/image-text-retrieval/run.py \
  --output data/runs/siglip-offline
```

Use a new output directory for each run. Add `--device cpu` for an explicit CPU comparison; `auto` selects Apple MPS when available. CPU performance has not been measured.

## Inputs and scoring

The script assembles twelve two-second scenes from four public still images: cats/remotes, coffee/spoon, camera/tripod, and parrots. Derived scenes include a mirrored image, small objects within a larger frame, covered remotes, a remote crop, a blank scene, grayscale coffee, and one parrot. These are derived still scenes, not twelve independent photographs or natural video events.

`dataset.json` records source URLs, SHA-256 digests, transformations as scene names, labels and intervals. Eight positive descriptive queries and two absent-object queries are evaluated. `hit_at_1`/`hit_at_3` mean that at least one relevant scene appears in the top k; they do not mean every occurrence was found. Per-query relevant-scene counts make those misses visible.

Absent-object queries intentionally still receive nearest-neighbor candidates. The system makes no absence/presence decision. The galleries label results as unverified candidates and similarity as non-probabilistic.

## Artifacts

Each run writes:

- `dataset.json`: source provenance and scene labels.
- `scenes.mp4`, `input_frames/`: controlled test media, ignored by Git.
- `index/`: copied source, extracted frames, SQLite metadata and vectors.
- `results.json`: checkpoint, versions, device, load/index/query measurements, hits and limitations.
- `galleries/`: self-contained HTML candidate reports with source-clip links.

Image inference is warmed once before timed indexing. Load timing excludes the original model download. Query timing includes text encoding and SQLite search, and excludes model startup, VLM verification, cloud voice and playback. Host peak RSS and end-of-run MPS driver allocation are separate observations; do not add them into a claimed peak unified-memory requirement.

## Current findings

See [R3 findings](../../docs/research/R3-local-retrieval.md). A source-label ordering bug invalidated the first local run; it is marked invalid locally and covered by a regression test. Only corrected, labelled runs are reported.

Next: independently labelled household clips with actual glasses/keys/documents, negatives, occlusion and changing viewpoints. Compare full-frame retrieval with spatial crops and assess occurrence recall and temporal coverage before using candidates for last-seen answers.

## Compare spatial crops

```bash
HF_HUB_OFFLINE=1 uv run --no-sync python experiments/image-text-retrieval/run.py \
  --compare-crops --output data/runs/new-crop-comparison
```

This adds four overlapping corner crops per decoded frame (two-thirds of each axis, rounded up), and ranks each frame once by its best full/cropped view. The full-frame baseline reuses the same SQLite vectors; both strategies use one shared query encoding. The application's indexing policy is unchanged.

Additional artifacts are `crop-comparison.json`, `view-features.npy` (frame, view, embedding dimensions) and paired top-five galleries. JSON records every candidate's frame/view, crop box in decoded-image pixels, similarity, all labelled occurrence ranks, recall at 1/3/5, average precision and latest-labelled-scene rank. Summary scores average the eight positive queries; negative-query quality remains uncalibrated. A missing slot beyond k is not automatically a recognition failure when there are more than k relevant scenes.

The first comparison found unchanged recall at 3/5 and a small ranking gain for the spoon, with five times as many encoded views. Keep the full-frame default pending independent footage. Full method, limits and the manual household-clip protocol are in [R3](../../docs/research/R3-local-retrieval.md).
