# R19 — Complete report recall and context management

Date: 2026-11-15. Status: report/context and candidate evaluations complete; visual review ongoing.
Owner: inline implementation. Decision affected: next recall/context reliability pass.

## Method and frozen cases

Sixteen predeclared synthetic workflows, eight development/eight held out, in
`experiments/companion/recall_workflows.json`. SHA256
`e1477b83a163b745ee505e59be8a582fb439ef7f439840544f2eecb67b7f9791`.
Groups and report texts cannot cross splits. Cases cover recent-context eviction (32/40 filler
turns), restart, explicit corrections, historical as-of state, intentions, normal moves,
retraction, deleted-source/absent/hypothetical/future negatives, distinguishing attributes and
English/Hindi/Hinglish. Fixture report clocks are explicitly backdated synthetic labels, not
capture dates of household events. Every case reopens an isolated application/database.

The real reference resolver, Gemini Embedding 2 encoder, typed planner, statement citation
verification and API worker execute; no forced initial action or fake inference. Score exact
directly selected report IDs, required transcript attribution and supported negative outcomes.
Transitive dependencies are not counted as additional selected reports. Failed/uncited outputs
cannot pass; failed cases remain in the denominator. Setup-link outcomes are scored too.
This is attribution/contract quality, not a semantic judge of every word of a free-form answer.
It does not measure image retrieval, STT/TTS, natural household or physical-instance accuracy.

Baseline application revision is `c4d544e`; Python 3.12 and locked project environment. Model
fingerprints/provider usage/exact outputs are saved in ignored run artifacts. Development and
holdout baseline runs precede runtime changes. Detailed held-out outcomes stay out of tuning.

## Development baseline

Eight of eight workflows passed; no failed provider requests. Six positive workflows and two
negative workflows, with literal report identities and expected link/abstention labels. API query
latency p50 6548.5 ms, nearest-rank p95 7472 ms (only eight queries; not a robust service percentile).
Setup/embedding time is separately included in each case's overall elapsed time. Fifty provider
requests, observed key usage $1.21559082 → $1.24779756, delta $0.03220674; settlement may lag.

Held-out baseline completed all eight cases: aggregate 7/8 workflow score, observed delta
$0.05246001 and final key snapshot $1.30025757/2. Detailed failure outcomes remain sealed until
the final selected comparison; no runtime change is selected from that aggregate score.

```sh
uv run --env-file .env --no-sync python -m experiments.companion.recall_workflows --output data/runs/recall-context-baseline-dev --split development --max-spend 0.20
uv run --env-file .env --no-sync python -m experiments.companion.recall_workflows --output data/runs/recall-context-baseline-holdout --split holdout --max-spend 0.20
```

Use fresh output directories to reproduce. Existing per-request spending guards count cumulative
key usage and response costs under the original $2 ceiling. Raw fixture databases/outputs stay
ignored. No camera/microphone, private media, new account or new paid service.

## Source-aware context change

The audit reproduced typed planning serializing old assistant answers even when
`sources_available` was false. New provider-boundary tests failed before the fix. Shared recent
context now suppresses unavailable answers/candidate/report-reference metadata, preserves the
latest object-query constraints and dates, and projects only relevant metadata. It selects up to
12 complete turns inside 12,000 Unicode characters, clipping individual user/assistant text at
1,500/1,200 characters with a truncation flag. These are context copies; stored text is unchanged.
It stops at a budget boundary instead of skipping a recent turn and reconnecting to older context.

Spoken startup restores date/availability/truncation metadata, withholding invalidated answers.
Each actual spoken model continuation keeps whole user/tool exchanges within 48 items and
24,000 text characters (including instructions, arguments and tool output). Current calls/results
stay paired. An oversized active exchange fails before inference rather than silently dropping
its evidence. This bounds model text, not media, exact tokens, or all SDK process memory. The
existing deletion API blocks active voice turns; restart restores source-filtered context.

Tests use actual planner serialization, LiveKit ChatContext and our socket/turn persistence,
replacing external speech/model IO. An 80-turn live-history test preserves the current tool pair
and trusted instructions. Raw saved rows remain unchanged. Planner prompt version is now 46;
context policy `bounded-source-aware-v1` is recorded in verifier metadata. No UI edits.

The selected development replay again passed 8/8 workflows, 50 provider requests. Query p50
6308 ms/p95-nearest-rank7209 ms; baseline was 6548.5/7472 ms. One small run does not establish a
latency improvement. Observed spend $0.040982475, final key snapshot $1.345259015/2. Both baseline
and selected runs include failures in the denominator; selected holdout evaluation remains pending.
Artifact: `data/runs/recall-context-selected-dev/results.json`. Further visual evidence, multi-day
load and Hydra evidence are separate checks.

## Candidate-pool crowding development experiment

The report workflows passed, so a separate code-derived visual-retrieval regression targets
competition before nomination: 80 high-scoring distractor samples fill the flat top-64 pool,
excluding a lower-scoring source that the actual decoder/verifier can recognize. Tests first
reproduced the miss, then verified the older scene's original frame ID, capture timestamp and
media URL after source balancing. Controlled inference scores/color judgments are boundary
fixtures here; they do not establish encoder or VLM semantic accuracy.

`Store.search(source_balanced=True)` ranks in rounds of four samples per source bucket. Known
capture sessions share a UTC-minute bucket across clips; other records use their video ID.
Filters apply before ranking, including availability status, times and excluded frame IDs.
After each bucket's first four nominations, remaining slots fill from later rounds; one source
can still fill the pool if no alternatives exist. This is sampling diversity, not an event merge.
Only semantic latest-history nomination enables it by default; ordinary similarity/latest APIs
retain their prior ordering. `NYX_SOURCE_BALANCED_CANDIDATES=0` opts that route out. Pool/check
limits remain 64/12, and final model verification is still required. Reference nomination and
freshness weighting remain disabled.

Offline comparison reused R16's compatible cached 768-d Gemini vectors and 24 development COCO
photos. Each photo queries other photos for its annotated category. The crowded condition repeats
the highest-scoring irrelevant source 80 times, with simulated candidate timestamps and unchanged
vectors. Uncrowded sources have one sample each. Real SQLite nomination and diversity execute;
metadata-only stores intentionally have no playable media and never produce visual answers.
Labels count distinct relevant photo sources, not repeated frames. Images were evaluated earlier;
this is a new stress condition, not an untouched household dataset or text-query benchmark.

| Development condition | Flat candidate Recall@12 | Balanced candidate Recall@12 | Flat/balanced distinct pool sources |
| --- | --- | --- | --- |
| Uncrowded, 24 queries | 0.7105 | 0.7105 | 23 / 23 |
| Crowded, 24 queries | 0.1873 | 0.6847 | 2.0833 / 23 |

No individual development query regressed in either condition. Mean SQL/diversity query time
increased from 1.016 to 1.461 ms in the crowded condition, on this tiny corpus. No provider calls
or new downloads. Freeze four-per-bucket nomination for the final held-out comparison; no tuning
on the remaining sixteen-photo split. Larger-index query cost is still to be measured.

```sh
uv run --no-sync python -m experiments.companion.candidate_pool_replay --data data/evaluation/coco-small --embeddings data/runs/coco-embedding-gemini2-v1/embeddings.npz --output data/runs/source-pool-development
```

The prior public text queries use category-proxy labels. They do not independently label every
word of a query: for example COCO's bottle category does not establish a water bottle or contents.
Do not turn those proxy scores into precise physical-instance/final-answer accuracy.

## Final report/context review and fresh evaluation

The first selected original holdout scored 6/8 versus baseline 7/8. Investigation found lost
latest-report selection, an affirmative Hinglish plan rejected because it was not completed,
and the harness's 60-request cap being treated as a tool-validation error. These original cases
are now diagnostic regressions, not untouched holdout evidence. The cap raises `CloudError`;
the workflow allowance is 96 requests under unchanged per-request spend/cumulative $2 guards.
Failures and not-run cases remain in the denominator. Concurrent usage snapshots overlap and
must not be summed as independent costs.

Before the fixes, twelve fresh cases were frozen in `report_intent_workflows.json`, six per
split with separate objects/wording. Baseline dev 3/6 and holdout 4/6 became selected 6/6 in each
split, with zero incomplete cases. Forty requests per selected split. Dev query p50 7837→7447 ms;
holdout 6693.5→6756.5 ms, so no latency win is established. Original diagnostic sets then passed
8/8 each. This remains report attribution/contract evidence, not free-form answer accuracy.
Artifacts: `data/runs/report-intent-{baseline,selected}-{dev,holdout}/results.json` and
`data/runs/recall-context-diagnostic-final-{dev,holdout}/results.json`.

`search_statements` now explicitly supports `selection=latest_report`, independently of `as_of`.
It selects by known report timestamp after semantic citation verification; ties or unknown dates
ask for clarification. Default `all` preserves multiple reports. Typed and native spoken tools
preserve the selection constraint. Citation instructions distinguish an affirmative unfulfilled
plan from a cancelled intention; plans never establish completed placement.

Author review also reproduced deletion after spoken-session startup. Every continuation now
rechecks persisted source availability through bounded SDK message-ID/turn-ID mappings, retaining
the user question and withholding stale assistant/tool claims. Original SDK/saved rows are not
mutated. Restart restores structured object/date/selection constraints. Fingerprints now record
planner version47, statement selection version2, and `bounded-source-aware-v2/live-availability`.
The earlier startup-only/context-v1 description above documents the initial checkpoint.
Full deterministic suite at this checkpoint: 473 passed. Synthetic Chrome speech/cancellation,
playback denial, old library, candidate controls and sustained activity passed with zero page
errors; this uses fake devices and deterministic external model boundaries.

The frozen source-balancing holdout scored crowded Recall@12 0.1220→0.8482 across sixteen
queries; uncrowded 0.8884 was unchanged, with no individual regressions. Distinct pool sources
increased 1.6875→15. Mean crowded SQL/diversity time increased about1.07→1.52 ms on this tiny
corpus. Larger 10k-vector costs and synthetic multi-day recovery are reported separately in R21.

## Real visual workflow finding

A separate real decoder/embedding/verifier replay used four earlier public COCO development
photos as generated still videos, plus an empty gray scene. Replay clocks are synthetic and
original photo times unknown. Four of five category/source/time/media checks passed; a bottle
query wrongly selected a soda can on the round table in image13659. Manual inspection confirmed
the category/location error. This is a diagnostic failure to address, not proof that nearest
neighbors or category labels establish a correct visual answer. Artifact:
`data/runs/visual-workflow-final/results.json`. A bounded corroboration experiment follows before
any claim that this check is resolved.
