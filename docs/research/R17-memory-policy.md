# R17 — Report corrections and freshness policy

Date: 2026-11-15. Owner: inline implementation. Status: implemented locally and evaluated on
bounded synthetic cases; household and spoken end-to-end acceptance remain open.
Decision affected: ten-day pilot report lifecycle and opt-in ranking.

## Question and implementation

Can explicit corrections change current report recall while preserving earlier reports for
historical requests? Can recency help without promoting irrelevant or stale-source records?

SQLite now stores an additive correction edge between actual persisted report IDs. A separate
schema-constrained model check must establish an explicit correction/retraction of the same
referent. A normal later move, ambiguous statement or unrelated object is not a correction.
Affirmative destinations must occur in the new transcript; retractions have no positive location.
The old transcript/observation is retained. Correction edges survive restart and prevent an
invalidated replacement from resurrecting the withdrawn report.

Current recall excludes corrected, unavailable and future reports. Explicit aware `as_of` lookup
uses report/correction timestamps, preserving microseconds and timezone equivalence; unknown
dates cannot establish historical state. Both semantic and legacy transcript routes use the same
scope. Model-selected IDs are checked again after inference. Correction and recall dependencies
include prior transcript/media sources, so source invalidation propagates. A source invalidated
during embedding cannot leave a partial link. Tool IDs stay internal; frontend files are unchanged.

The versioned `nyx-memory-v1` priority is `r + max(0,r) * w * 2^(-age_days/h)` for current eligible
reports. Unknown times get no freshness bonus and future reports are ineligible. Historical,
last-seen and report-only intents disable the bonus. It is ranking, not confidence, identity or
truth. No access reinforcement, expiry, deletion, automatic contradiction inference or universal
entity model is introduced. `NYX_MEMORY_RECENCY_WEIGHT` defaults to **0**;
`NYX_MEMORY_HALF_LIFE_DAYS` defaults to 7. Application historical lookup disables recency explicitly.

## Real-provider correction replay

Predeclared eight development and eight held-out synthetic pairs, including English, Hindi and
Hinglish, explicit correction/intention/retraction, later moves, different objects, hypotheticals,
uncertainty and instruction injection. Different objects/wording separate the two groups. Initial
report links and relevance vectors are labeled fixtures; correction inference, persistence,
restart and historical filtering use the actual backend. No camera/audio/private media.

Provider: existing OpenRouter configuration, Gemini 3.5 Flash reference model, correction prompt
version 1, temperature 0; model/runtime fingerprints and request usage are saved. Python 3.12,
same locked application environment. No prompt tuning followed held-out inspection.

| Split | Correct decisions/kinds | Lifecycle checks | Failed requests |
| --- | --- | --- | --- |
| Development | 7/8 | 8/8 | 0 |
| Held-out | 8/8 | 8/8 | 0 |

All eight negative examples left the earlier report active. One valid Hindi correction asked
for clarification; it did not silently withdraw the old report. These small counts do not
establish language parity, resistance to arbitrary injection, or natural household accuracy.
Immediate observed key-usage increase was $0.022209; billing may settle later.

A separate four-turn API replay used the actual typed planner, reference resolver, Gemini
Embedding 2 vectors and SQLite, with no forced initial action. It saved a blue-glasses-case
report, searched for its ID before correcting it, recalled the replacement, and used the exact
earlier `as_of` timestamp to return the original. All four jobs succeeded; restart/current/history
checks passed. Immediate usage delta $0.005110635, final key snapshot $1.21161682 of the existing
$2 cap. No LiveKit/STT/TTS end-to-end quality claim follows this text workflow.

```sh
uv run --env-file .env --no-sync python -m experiments.companion.correction_replay --output data/runs/correction-replay-v1 --max-spend 0.12
uv run --env-file .env --no-sync python -m experiments.companion.correction_replay --output data/runs/correction-api-v1 --max-spend 0.12 --workflow-only
```

These directories already exist; reproductions need fresh output paths. Each request checks
key usage and response-reported costs with headroom and a bounded request count. Raw synthetic
transcripts/databases/results stay under ignored `data/`.

## Cached-vector freshness stress test

Reused R16's exact 40 public-photo Gemini vectors and annotation identities, with source-separated
24 development/16 held-out photos. Each photo is an image query against other same-split photos;
category annotations label relevance. Assigned **synthetic** dates in three schedules: relevant
items old, relevant items new, mixed. These dates are not capture timestamps. Some records have
unknown/future dates to exercise eligibility. Current and historical intents compare half-lives
1/3/7/30 days and weights 0/.25/.5: 144 comparisons, zero provider requests. No chronology is
claimed to represent actual user behavior, and the selected production weight was frozen at 0.

| Held-out current schedule | Baseline Recall@3 / MRR | Nonzero-weight Recall@3 range / MRR range |
| --- | --- | --- |
| Relevant old | 0.3036 / 0.7229 | 0–0.1425 / 0.1147–0.5229 |
| Relevant new | 0.3036 / 0.7229 | 0.4256–0.6618 / 0.8958–1.0 |
| Mixed | 0.3036 / 0.7229 | 0.2932–0.3452 / 0.6406–0.7365 |

The benefit reverses when relevance correlates differently with age. Historical rankings are
unchanged by weight. Keep recency disabled by default; this stress result supports a guardrail,
not a proprietary accuracy claim or an optimized decay formula.

```sh
uv run --no-sync python -m experiments.companion.priority_replay --data data/evaluation/coco-small --embeddings data/runs/coco-embedding-gemini2-v1/embeddings.npz --output data/runs/priority-replay-v1
```

## Recommendation and remaining limits

Use attributed correction/retraction and explicit historical lookup. Keep SQLite authoritative,
bare shared text/image embeddings active, reference nomination and nonzero decay experimental.
Next gate is a broader labeled report-and-video workflow including speech, uncertainty and source
loss, followed by a rehearsed recording. The ten-day query window still does not establish ten
days of continuous storage under the unchanged 1 GiB cap. See [R16](R16-candidate-retrieval.md),
[R14](R14-self-hosted-hydra.md) and the [execution plan](../superpowers/plans/2026-11-15-memory-reliability.md).
