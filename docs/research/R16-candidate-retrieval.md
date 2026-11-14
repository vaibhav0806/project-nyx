# R16 — Candidate continuity and reference retrieval

Date: 2026-11-15. Owner: inline implementation. Status: backend mechanisms implemented;
small real-encoder development comparison complete, broader labeled-photo evaluation pending.

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
