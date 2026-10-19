# R3 — Local visual-retrieval baseline

Owner: implementation session (inline)
Status: in progress; semantic smoke benchmark complete, independent household evaluation pending
Date: 2026-10-19
Decision affected: M1 / P3 / P4 / O4

## Question and method

Can a small local aligned encoder retrieve source-linked moments without a generative VLM? The implementation imports clips, extracts actual selected decoded timestamps using FFmpeg, stores normalized features and evidence references in SQLite, ranks with `sqlite-vec` cosine distance, and writes candidate galleries.

The smoke dataset contains twelve derived scenes from four public still images, assembled into a 24-second clip. It includes mirrored/cropped/grayscale scenes, a small coffee cup and remote, covered remotes, and a blank scene. Eight positive descriptive queries and two absent-object queries were scored. This is deliberately small, correlated data; no household-camera video, moving objects, intended-user recordings or glasses/keys sightings were evaluated.

Sources and SHA-256 digests are in each local run's `dataset.json`. Source references are public Hugging Face documentation/COCO examples and scikit-image reference images; raw media is ignored by Git. [Experiment method and commands](../../experiments/image-text-retrieval/README.md).

## Measured environment

- Apple M4 Pro, 24 GB unified memory, macOS 15.7.2; MPS available and used.
- Python 3.12.12; torch 2.14.1, transformers 4.57.6, numpy 2.5.4, sqlite-vec 0.1.9, pillow 12.3.0.
- Model: `google/siglip2-base-patch16-224`.
- Pinned revision: `75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2`.
- Preprocessing identity: `88acf431ff7614d8b483901a6081638db423762041c19387afbbcf820d43636b`; 768-dimensional normalized embeddings.
- First-time model download completed separately; no media is uploaded for inference. An additional run succeeded with `HF_HUB_OFFLINE=1` after caching model/assets.

## Observed results

Corrected offline run: `data/runs/siglip-mps-offline-004/results.json`.

| Measurement | Result |
| --- | --- |
| Relevant candidate at rank 1 | 8 / 8 positive queries |
| Relevant candidate within top 3 | 8 / 8 positive queries |
| Absent glasses/keys queries | Both still return candidates; no presence/absence claim is made |
| Cached offline model load | 1.844 s |
| First image encoding in process | 0.181 s |
| Index 12 sampled frames, after one image warm-up | 0.274 s |
| First text query + SQLite search | 12.5 ms |
| Remaining nine queries, p50 / p95 | 9.3 / 10.2 ms |
| Process peak RSS | 495.9 MiB |
| End-of-run MPS driver allocation | 1.50 GiB |

These are single-process smoke measurements. Query times exclude model loading, VLM verification, voice and playback; image inference was warmed before indexing. Host RSS and MPS driver allocation are separate observations, not values to add into a claimed peak unified-memory requirement. The corrected online-metadata run had a 5.740 s load and 10.8 ms warm-query p95; neither is a production latency guarantee.

### Candidate coverage

A successful query hit does not mean every occurrence was retrieved. Counts below use the coarse object-category scene labels; they do not score full relational/temporal language understanding.

| Query | Relevant first candidate? | Relevant scenes among top 3 / all labelled relevant scenes |
| --- | --- | --- |
| two cats resting on a sofa | Yes | 3 / 3 |
| a cup of coffee | Yes | 3 / 3 |
| a man using a camera on a tripod | Yes | 1 / 1 |
| parrots | Yes | 2 / 2 |
| a television remote control | Yes | 3 / 4 |
| a metal spoon | Yes | 2 / 3 |
| coffee in a cup on a saucer | Yes | 3 / 3 |
| cats next to remote controls | Yes | 2 / 4 |
| a pair of eyeglasses | Not applicable | 0 / 0 |
| a set of house keys | Not applicable | 0 / 0 |

The small standalone remote is outside the top three, but there are four relevant scenes: a three-result budget cannot include all four. This alone is not evidence of poor object recognition. The spoon query also excludes a labelled small occurrence from its top three. The relational cats/remotes query admits the covered-remotes scene as a candidate. Eyeglasses and keys are absent from the dataset but still receive nearest-neighbor matches. A query hit rate on this dataset therefore does not establish reliable last-seen recall or a correctness threshold.

### Spatial crop comparison

Follow-up run `data/runs/siglip-crops-005/crop-comparison.json` used the same pinned model, MPS and decoded frames offline. Compared full-frame embeddings with the maximum similarity over the full frame plus four overlapping corner crops (each two-thirds of each image axis, rounded up). Each source frame occupies one result slot. The application index remains full-frame only.

| Measurement | Full frame | Full frame + crops |
| --- | --- | --- |
| Encoded views | 12 | 60 |
| Macro occurrence recall at 3, eight positive queries | 86.46% | 86.46% |
| Macro occurrence recall at 5 | 100% | 100% |
| Mean average precision, coarse category labels | 0.9693 | 0.9755 |
| Small standalone remote rank | 4 | 4 |
| Small coffee/spoon scene rank for spoon query | 5 | 4 |

The additional 48 crop encodings took 0.589 s including local image decoding/preprocessing. Baseline clip import/indexing took 0.275 s in this run; these are different scopes of work, not an isolated throughput comparison. No separate crop peak-memory benchmark was taken.

The remote query already places all four relevant scenes before any irrelevant scene (average precision 1.0). The small-spoon scene is the clearer ranking weakness. Crops improve its rank by one but do not improve recall at 3 or 5. Absent-object queries still return candidates, and taking a maximum over more views can raise irrelevant scores. Keep the simpler full-frame default; there is no evidence here to justify five background encodings per sampled frame. This experiment was informed by the same fixture's labels and is not held-out or household validation.

The comparison reports every relevant scene's rank and the latest labelled scene's rank. The latter is a retrieval diagnostic using category labels, not a verified last-seen answer. Relational queries still use coarse object labels, so these metrics do not establish relation understanding.

## First developer scene examples

On 2026-10-19 the developer recorded a real scene through the manual interface and shared screenshots showing relevant top candidates for a cookie packet, a smartphone, keys and a raised hand. This is observed positive-example feedback, not a labelled accuracy benchmark. No negative, occlusion, duplicate-identity or last-seen evaluation was scored, and a raised-hand still does not establish temporal action recognition. Personal footage and screenshots remain outside Git.

## Recommendation

Keep this encoder as a working local baseline for further experiments. It runs on the laptop with modest observed resource use, and the evidence/storage path is reproducible. Do not freeze the model choice or treat similarity as verified presence.

Next collect a permitted, independently labelled household clip set with actual glasses, keys, documents, placement/removal, duplicates, occlusion and viewpoint changes. Measure occurrence coverage and retrieval failures; compare spatial crops or another encoder if small objects are missed. Then evaluate on-demand VLM verification. JEPA event/prediction research remains separate.

### First household clip protocol

No existing household footage was available when the user was asked on 2026-10-19. A manual recording/import interface is the next bounded development task; this research milestone remains open.

For an initial diagnostic clip, keep one camera fixed for 60–120 seconds. Use three recognisable objects such as glasses, keys and a wallet: begin with an empty view, show each clearly for at least six seconds, move one beside a landmark, partly cover one, then remove it from view. Include a later sighting of a previously seen object and one object that never appears. Avoid people and personal documents in this fixture.

Before looking at search results, label clip intervals with each object's visible identity, location/landmark and whether it is clearly visible, partial or hidden. Record camera interruptions separately. Keep that label sheet and footage under ignored `data/evaluation/`; preserve unknown wall-clock time for imported clips. Inspect replay at returned offsets and score relevant occurrence ranks, latest visible occurrence coverage and negative-query failures separately. Record identity ambiguity rather than guessing between duplicate objects. This first clip is a diagnostic; freeze queries and evaluate a second independently labelled clip before changing the encoder or sampling policy.

## Reproduction and artifacts

```bash
uv sync --python 3.12 --extra vision
uv run --no-sync python experiments/image-text-retrieval/run.py \
  --download-samples --output data/runs/new-baseline
HF_HUB_OFFLINE=1 uv run --no-sync python experiments/image-text-retrieval/run.py \
  --output data/runs/new-offline-baseline
```

Raw local outputs: `data/runs/siglip-mps-003/`, `data/runs/siglip-mps-offline-004/`; example gallery: `data/runs/remote-search.html`. The first local run was invalidated by a dataset source-label ordering bug; it is marked `INVALID.txt` and excluded. A regression test now verifies original-scene label/source correspondence. Every reported semantic result above comes from the corrected fixture generation.
