# R10 — Low-cost models and multi-day retrieval

Date: 2026-10-29. Status: implemented MVP changes; multi-day recall remains unproven.
Question: can newer inexpensive models reduce latency/cost without breaking the
finding flow, and does the current retrieval architecture handle several days?

## Model evidence and decision

Source-reported OpenRouter prices per million tokens, checked 2026-10-29:

| Model | Input | Output | Public visual checks | Measured single-image latency |
| --- | ---: | ---: | ---: | ---: |
| GPT-6 Luna | $0.10 | $0.50 | 4/4 | 2.47–3.82 s |
| Gemini 3.5 Flash-Lite | $0.30 | $2.50 | 4/4 | 1.70–2.08 s |
| Gemini 3.8 Flash | $0.825 | $4.125 | 4/4 | 3.67–11.28 s |
| Previous GPT-5.4 | $2.50 | $15.00 | prior baseline | prior replay in R9 |

Sources: [Luna](https://openrouter.ai/openai/gpt-6-luna),
[Flash-Lite](https://openrouter.ai/google/gemini-3.5-flash-lite),
[Flash](https://openrouter.ai/google/gemini-3.8-flash),
[live catalog](https://openrouter.ai/api/v1/models).
The catalog and Flash page showed different prices ($0.825/$4.125 versus a
promotional $0.75/$3.75); the table uses the fetched catalog. Actual usage depends
on routing, image/token accounting, reasoning and discounts. These are not flat
per-image costs. Luna was released September 22 and Flash-Lite July 21, 2026,
according to their model pages. Newest Flash was slower in this small experiment.

Selected Luna for planning, Flash-Lite for image judgment and transcript association.
No local model download, provider registry, automatic retry or hidden expensive
fallback. Existing environment overrides remain. Embeddings/STT/TTS are unchanged;
no index rebuild is needed because the embedding model did not change.

Four reused public fixtures cover generic ambiguous remotes, spatially qualified
remote, single remote crop, and empty image. This is a small development check,
not household accuracy. All three models passed all four using the existing
single-image prompt/schema. Luna passed the 21 main planner cases and 12 separate
holdout cases. The initial planner harness failed before inference due to obsolete
Transformers metadata; it now records installed cloud-runtime package versions.

## Real saved-data replay

Same authorized phone footage and actual transcript; isolated DB copies, fixed
original search clock and no camera/microphone access. Full Luna planning/vision
returned the correct attributed statement in 13.98 s, 19.02 s including fresh TTS.
Luna planning + Flash-Lite vision at concurrency three took 8.69 s, 14.30 s with TTS.
Final configuration (six concurrent checks plus diversity) took 9.41 s, 14.83 s
with TTS, returning the same correct answer. Final timing: retrieval 1.03 s,
decode 1.26 s, vision 3.62 s, statement association 1.24 s, TTS 5.42 s.
It inspected 12 nominated frames rather than six: wider evidence coverage has a
cost even when latency is similar. One replay per configuration cannot establish
statistical superiority, generic accuracy or optimal concurrency. Raw microphone
and browser playback latency are excluded. Source artifacts are ignored under
`data/runs/cheap-models/` and `data/runs/latency-replay/`.

## Which images are checked

The agent chooses a query and time window. Local vector similarity ranks saved
sampled frames, not every video frame. For semantic latest-history search, retrieve
up to 64 candidates, nominate up to 12 while preferring frames at least four
seconds apart within each clip, then check nominees newest first. Deferred nearby
frames fill unused slots. This reduces one burst occupying the entire shortlist;
it does not establish semantic event identity or guarantee recall. Clarification,
rejection, earlier-than boundaries and widening remain agent tools. Evidence is a
candidate, not identity confirmation or proof of current location.

Vision runs in bounded groups of six (NYX_HISTORY_CONCURRENCY, range 1–8), retaining
ordered result consumption. Up to five additional checks can be billed before early
termination. Existing ambiguity and error handling remain. The prior semantic
fallback query duplicated a subset of the same ranked pool; it is omitted on this
path. Nonsemantic latest search retains its fallback behavior.

## Scale experiment and product boundary

Synthetic local SQLite/768-dimensional vectors, one synthetic source with offsets
at two-second intervals; identical normalized vectors, no real model/network/media.
Temporary DB removed after experiment. This measures scan/filter overhead, not
ranking quality. Result limit 64; no external vector service.

| Frames | Full scan | Two-hour filter |
| ---: | ---: | ---: |
| 10,000 | 0.028 s | 0.031 s |
| 50,000 | 0.136 s | 0.148 s |
| 129,600 | 0.467 s | 0.349 s |

129,600 samples correspond to three days at two-second spacing. Current exact
vector search is linear, and timestamp filtering uses a computed SQL function:
this is not an ANN index or indexed timestamp pruning. At measured scale the scan
is not the dominant bottleneck, so no new database infrastructure is justified.
For larger archives, persisted indexed capture timestamps and a measured vector
index are appropriate follow-ups; keep the evidence/time contract intact.

Storage is a separate blocker. Actual saved segments measured 168,180,073 bytes
over 527.19 seconds, extrapolating to ~27.6 GB/day at that rate. The existing 1 GiB
stop-without-delete budget therefore supports roughly 56 minutes, not days.
This rate is scene/codec-dependent, not a universal estimate. Originals and budget
remain unchanged. A multi-day product needs explicit compression/retention choices
and event-linked before/after clips with periodic coverage. Do not silently delete
recordings or infer that unrecorded/unindexed events did not happen.

Recommendation: retain the bounded SQLite MVP and cheaper models now; evaluate
recall with events planted across several days before claiming multi-day accuracy.
Use persistent cross-segment event representatives for duplicate reduction and
choose retention policy before extending recording duration. Avoid a hierarchy of
summaries or distributed infrastructure without that evidence.

Final verification: 341 deterministic tests, all 39 planner cases (21 main,
12 holdout, 6 feedback), and the synthetic companion browser regression passed.
New vision-model performance on real departure-event detection remains unevaluated;
that feature is still experimental. No claim of broad household accuracy or
merge readiness. At the final spend check, $1.2996 remained of the $2 cap.
