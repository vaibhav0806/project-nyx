# Simple shared agent and general memory

Approved by the user on 2026-11-17, including final model selection. Implementation is authorized
inline on work/memory-reliability with regular commits and optional branch-only backup. Main and
src/nyx/web remain untouched. Private recordings remain offline; real model tests use public or
synthetic fixtures only, no hardware. Retain original recordings, timestamps, sources, the 1 GiB
stop-without-delete cap and the ten-day search target. No Hydra migration, embedding rebuild,
new provider, autonomous outreach, purchases, generic event framework or demo production.

## Models and budget

User selected openai/gpt-6-luna for shared conversation and memory interpretation and
 google/gemini-3.5-flash-lite for visual understanding. Keep google/gemini-embedding-2 and Sarvam
speech unchanged. Remove the split voice/typed model policy. Do not introduce a fallback router
or extra judges. A failed model-quality gate must be reported and repaired, not hidden by fixtures.
On 2026-11-17 key metadata verified cumulative limit $8, usage $4.73185091, headroom $3.26814909.
This supersedes the former $5 ceiling; it is not an additional $8. Per-run paid guards at most
$0.25, sequential paid experiments, preserve at least $0.10 settlement headroom. Report costs.

## Responsibilities

One short conversational policy (about 80–100 words, including personality) and native tool
contracts are shared by voice and text. Keep the cached lookup acknowledgement. Tool descriptions
own parameter semantics. The agent chooses tools and responds; it does not manage correction IDs
or database state. Preserve transport, playback, cancellation and existing API/UI response contracts.

The memory component automatically considers completed user inputs for useful general memories:
facts, preferences, reports, plans and events. It retrieves related records and performs one focused
interpretation when needed. Return no-op, append, correction/retraction, or clarification. Store
source-linked content with time and relationships; ordinary moves append events, explicit corrections
version earlier reports. Retain original wording and history. Never store assistant guesses as user
facts or turn plans into observed events. Related-memory matching belongs here, not in the main agent.
Queries/greetings are not affirmative facts. Historical/current questions preserve source clocks.

Visual understanding has one responsibility and one concise prompt per task; uncertain results
remain uncertain. Consolidate reference policies, eliminate the standalone ambiguity checker and
separate correction judge. Images are interpreted once per needed visual task; checked identity
can travel inside a valid owned turn, never across unrelated frames or a new utterance.

Retire departure-specific tools, prompts, observer actions and active delivery scheduling from this
slice. Preserve stored reminder records. Camera recording/indexing continues independently. Existing
frontend polling endpoints may return inactive/empty compatible responses; retain no obsolete AI
planner/detector branch behind those endpoints. Migration ends with obsolete implementations deleted.

## Persistence and acceptance

Use the existing Python process and SQLite. Existing statement/conversation data remains readable
through a lossless conversion or narrow read adapter; never delete it or rewrite original media.
Writes are idempotent, transactional, validate actual source/target IDs and active-turn ownership,
and preserve user input on model/provider/embedding failure. Context eviction/restart must not lose
memories. Deleted/unavailable evidence cannot support claims. Do not invent unknown capture clocks.

Acceptance includes ordinary English/Hindi facts/preferences, shown-item placement, later recall,
normal moves, corrections/retractions, future plans, contradictory/unknown information, ambiguous
objects, explicit recall after restart and context eviction, source deletion and provider/write
faults. Freeze fresh source-separated cases before model calls; preserve all failures. Reuse R29
failures as regressions, not unseen accuracy. Run default model paths through real native tool
selection and actual persistence; final answers are audited, not inferred from job completion.
No fixture IDs, category aliases, scene coordinates or canned sample answers in application code.
