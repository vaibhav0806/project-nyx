# R16 — Candidate continuity and reference retrieval

Date: 2026-11-15. Owner: inline implementation. Status: backend mechanisms implemented;
small real-encoder development comparison complete, broader labeled-photo evaluation pending.

Update: the bounded COCO comparison below is complete. Its mixed held-out results keep the
reference route experimental; no production embedding/format switch was selected.

## Backend changes

Store records an optional explicit capture-session ID via an additive SQLite migration. New
capture indexing passes the journal's actual session ID. Imports remain unassociated; retry may
add a known association but cannot reassign a conflicting one. Original media, source offsets,
encoder identity and existing embeddings are preserved.

Candidate diversity uses absolute capture times across segments only when both belong to the
same known capture session. Otherwise the existing within-clip rule applies. This spreads nearby
nominations across boundaries, not a semantic event/identity merge. Unknown capture times cannot
establish cross-clip continuity.

Optional reference nomination searches the same Store using an image vector as well as the text
vector, with identical source/time/exclusion filters. Alternating route reservations bound the
candidate set; reciprocal-rank scores order that set. The existing visual/reference verifier still
checks evidence. Similarity and rank scores are not correctness probabilities.

`NYX_REFERENCE_CANDIDATES=1` opts history into reference nomination; default is disabled pending
broader evaluation. Bare text formatting remains the active baseline. No frontend files or UI
contracts were changed. The active vector backend remains SQLite; R14 does not establish a usable
Hydra ranking path.

## Real model development experiment

Command (paid, within the existing cumulative $2 limit):

```sh
uv run --env-file .env --no-sync python experiments/companion/embedding_replay.py --fixture data/runs/companion-retrieval-fixture --output data/runs/embedding-replay-gemini2-v1 --max-spend 0.15
```

The output directory already exists; reproductions need fresh output paths. Source: R3/R9's
twelve edited still scenes from four permitted public assets, with existing labels. Copied media
and generated a separate Gemini Embedding 2 / 768-d index; the source SigLIP index was not changed.
Encoder preprocessing is `rgb-jpeg90-768-v1`, through OpenRouter, existing Python 3.12 runtime.
This is not an untouched dataset or household/unique-instance accuracy evaluation.

| Comparison | Positive queries | Mean Recall@3 | Mean reciprocal rank |
| --- | --- | --- | --- |
| Bare text | 12 | 0.9375 | 1.0 |
| Search-instruction text | 12 | 0.9375 | 1.0 |
| Generic text, reference examples | 3 | 0.2778 | 0.5111 |
| Same text plus reference | 3 | 0.7222 | 1.0 |

Queries include English, Hindi and Hinglish; these small counts do not establish language parity.
Two label-negative queries per text variant are recorded without inventing a similarity-based
abstention threshold. This experiment assesses candidates, not final grounded answers or confidence.

Provider usage increased from $1.159319385 to approximately $1.160744785, delta $0.0014254.
The script checks prior usage and the per-run allowance before operations, reserving request
headroom. It records failures and partial results. Cached queries are marked by provider-request
count and must not be counted as live inference latency. Raw artifacts stay under ignored data/.

## Recommendation and limits

Keep bare text and leave reference nomination opt-in until the broader source-separated comparison.
The benefit on three cases is encouraging, but they reuse source views and do not establish
cross-view object identity or household robustness. Preserve existing shared embeddings rather than
replacing the model based on this result. Native-video wire/temporal quality remains unverified;
no new provider account, local model stack or raw-audio index was introduced.

Next evaluation uses a bounded subset of COCO val2017 annotations and separately selected public
CC-BY small-object photos, with source-separated development/holdout groups and declared category
or same-photo crop targets. Record capture times as unknown; photo labels do not establish a
real ten-day timeline. Keep actual failures and sample/resource counts visible.

## Source-separated COCO small-object comparison

Downloaded only val2017 instance annotations (19,987,840 bytes; pinned SHA256
`e8c7f7908f1d7278341fae127d0da654f102f11bd7b21d8aeefa635b8c810b6f`) and a deterministic
40-photo subset (6,072,289 bytes). Selected annotation license 4 (CC-BY), ten distinct photos
each for bottle/cup/remote/cell phone, with target boxes covering 0.1–2% of image area. Excluded
the earlier COCO cats asset. Stored licenses, source/Flickr credit URLs, hashes and bounding boxes
in the private manifest. No new raw media is committed or approved for stage publication.

Twenty-four source photos are development, sixteen held out. Source IDs and byte hashes cannot
cross groups. Queries are category descriptions in English, Hindi and Hinglish; reference queries
use an annotated crop to seek its original photo among same-split distractors. This evaluates
category retrieval and same-photo crop matching, not cross-view physical identity. Capture dates
remain unknown. All 40 downloads and 50 embedding requests succeeded; no failed cases were omitted.

| Split / comparison | Queries | Mean Recall@3 | Mean reciprocal rank |
| --- | --- | --- | --- |
| Development, bare text | 12 | 0.3765 | 0.9583 |
| Development, search instructions | 12 | 0.3571 | 0.9583 |
| Held-out, bare text | 12 | 0.4231 | 0.9583 |
| Held-out, search instructions | 12 | 0.4544 | 1.0 |
| Development, reference targets: text | 8 | 0.25 | 0.1795 |
| Development, reference targets: fusion | 8 | 0.375 | 0.3490 |
| Held-out, reference targets: text | 8 | 0.25 | 0.2913 |
| Held-out, reference targets: fusion | 8 | 0.375 | 0.2708 |

For category questions, Recall@3 measures the fraction of all relevant photos retrieved, not
the percentage of questions answered correctly. Reference targets have one relevant photo.
The fusion route's higher held-out Recall@3 accompanies worse mean reciprocal rank, so it is
not a clear overall improvement. No tuning followed inspection of held-out results. Keep bare
formatting because the development instruction comparison did not improve, and keep reference
nomination disabled by default. Verification/final answer behavior was not measured by this run.

The separate run's immediate usage delta was $0.0048866; its final snapshot reported $1.165991285
of the existing $2 limit. Cached vectors/IDs are in `embeddings.npz` with model fingerprints and
source hashes; they can support offline ranking analysis without new image requests.

```sh
uv run --env-file .env --no-sync python experiments/companion/coco_embedding.py --data data/evaluation/coco-small --output data/runs/coco-embedding-gemini2-v1 --max-spend 0.15
```

The output directory already exists. CPU ranking uses normalized cosine and the application's
actual `merge_candidates` function; this is a representation/fusion experiment, not a database
speed comparison. Same-query cache hits across splits are not live model latency measurements.
Sources: [COCO](https://cocodataset.org/),
[annotation mirror](https://huggingface.co/datasets/merve/coco/blob/main/annotations/instances_val2017.json).

## Native-video transport probe and billing settlement

Generated two silent two-second MP4 clips from the permitted R3 still-scene slideshow (cats and
coffee), 512-pixel width at one frame/second, each below 256 KiB. A single embedding request using
the `video_url` content shape with data URLs was rejected with HTTP 400. No vectors were produced;
this does not prove the underlying model lacks video support or rule out a different API shape.
Keep native-video embedding out of the runtime until its supported transport is verified.
Artifact: ignored `data/runs/native-video-embedding-wire-v1/results.json`.

The probe's immediate usage delta was zero. Its later key snapshot was $1.167639685, higher than
the earlier final snapshots: billing may settle after a request or other key activity may occur.
Per-run deltas above are observed snapshots, not final invoice amounts. Overall observed key
growth since the first run's baseline was $0.0083203 at this check, still inside the original $2
cap. Benchmark guards now also count response-reported costs before key usage settles and retain
usage metadata for future runs. No additional paid replay was needed to test that guard.
