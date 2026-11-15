# R19 — Complete report recall and context management

Date: 2026-11-15. Status: baseline established; context audit and selected fixes in progress.
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
