# R30 — Can a simpler agent preserve useful memory and household recall?

Owner: Codex inline. Date: 2026-11-17. **Engineering/evaluation in progress; household acceptance fails.**

## Current checkpoint: root-cause repairs and rejected vision changes

At8fd7c8f, the shared policy remains95 words, memory140, reference122 and inspection87.
Models remain Luna for conversation/memory and Flash-Lite for vision. No extra judge, runtime
fallback, UI change or main publication was added. The user's latest direction is to stop
broadening this checkpoint and fix root causes rather than build rules for individual examples.

**Conversation provenance:** two failing regressions reproduced the same data-model problem.
The store treated an independent user statement and the assistant's lookup evidence as one
source. Deleting a lookup could hide a valid tea preference, while repeating a visual answer
without a new tool call lost the original evidence dependency and survived its deletion.
The store now distinguishes input sources/availability from assistant evidence and records the
bounded prior turns actually supplied to generation. SQLite follows those dependencies at read
time instead of copying an ever-growing ancestry into every answer. Both interfaces withhold
unavailable answers/tool metadata while preserving independently available user input. Explicit
frame confirmations remain dependent on their recording; legacy rows retain conservative old
dependencies during additive migration. Source withdrawal, correction races and future clocks
retain their guards. These are storage/context repairs, with no new AI calls or prompt rules.

Both reproductions now pass, with60 successive source-linked followups, legacy conversion,
explicit input withdrawal and actual voice-adapter coverage. Full suite:471 passed45.40s;
latest targeted checks after metadata/source-guard cleanup:150 passed5.59s. Synthetic Chrome
typed lookup, inactive polling and camera stop passed with0 page errors/paid calls/hardware use.

**Structured vision responses:** the coffee failure was a protocol failure, not a synonym rule:
Lite often returned a JSON array when the parser required an object. Both visual inspection
methods now request a strict object schema; malformed arrays still fail closed. Paired retest
recognized all6 coffee positives and retained both cane negatives. The complete native public
history replay-v3 then completed all4 workflows with reviewed correct basic answers: dated remote,
nine-day Hindi coffee, absent cane and undated coffee with unknown-date/current-location caveats.
It reuses hash-verified public Gemini2 vectors, not private recordings or a reembedded library.
Broader strict-schema app checks score13/16 fresh conditions,24/32 category/count (7 unsafe
positives), and4/12 physical/depiction. The schema repair does not solve visual understanding.

Latest general memory-v3 development/holdout each passed8/8 source/workflow proxies; all16 final
answers were read inline and correct. Earlier recall-v3 remains7/8 exact-source proxies with8
correct final replies; historical context overinclusion remains. These are bounded authored
conditions, not measured real-household or acoustic accuracy.

**Vision experiment rejected for runtime promotion:** one-call scene-first output improved the
old physical holdout4/12→12/12, fresh physical6/12→11/12, and category/count24/32→27/32
(unsafe positives7→4). The frozen fresh cup condition has an annotation disagreement: the image
shows two cups despite its single-target label. It remains a scored failure, not a relabeled win.
However paired-image appearance controls regressed: current app4/4; candidate revisions3/4,
2/4 and3/4. The latest still accepted a beer bottle against a soap-dispenser reference. Changes
to task placement and an explicit appearance field did not establish a safe complete contract.
All scene/comparison changes therefore remain experiment-only. Do not report their gains as
current product accuracy. Default hard reference identity still fails the known two-phone case.

The web-only clean install also exposed a real packaging failure: shared native tool definitions
need LiveKit Agents, previously installed only by the voice extra. Added the already-locked SDK
to the web extra; isolated typed API smoke passes. All125 resolved package versions/sources are
unchanged. No Whisper/Torch or cloud call was needed by that clean-install smoke.

Provider metadata:5.32518435/8 total;76 saved simple-pass reports contain0.59445744 in response
costs. Conservative cumulative usage is **5.32630835/8**, leaving2.67369165; metadata may settle
later. Paid runs are stopped for this checkpoint. Private92-video decode/256-vector checks and
two-record lossless conversion remain earlier offline evidence, not cloud semantic testing.
Real physical identity, acoustic speech/wake and user acceptance remain open; no PR or merge
readiness is claimed. See named ignored run artifacts in the execution ledger for reproduction.

## Historical checkpoint atb83faf8: evidence repair after full-path testing

Latest code36d16a4 uses a **95-word shared policy**, versus681 words in the previous spoken
policy. Policy8 adds a short Hindi instruction to preserve unconfirmed identity. Memory5 and
chosen Luna/Lite defaults remain. Bounded source flags and summaries are now consistent:
`identity_verified=false` on model sightings, true only for actual user confirmation; historical
summaries retain identity/current-location caveats and never rewrite “the person” into “you.”

The full public history workflow uncovered why prompt-only fixes were inconsistent: the old
`spoken_answer` replaced the safe retrieval answer with “I think I saw your…” and removed its
explicit caveat. It also manufactured listener ownership from generic people/hands. These
legacy rewrites and an unused statement-attachment branch are removed. Neutral summaries retain
physical landmarks and known/unknown time. Tests first reproduced11 failures, then95 targeted
checks passed. This is a general source-boundary repair, not a fixture-specific answer.

A second repair reuses visual checks only for identical owned turn, utterance, pixels and clocks.
Both resolved and ambiguous results are bounded to8 entries; changed evidence/new turns rerun,
source availability/freshness is rechecked, and cancelled/failed work cannot become a cached save.
Three regressions first showed duplicate calls, then passed; broader targeted81 checks passed.
This avoids repeated inconsistent inference without adding a judge or changing the UI.

Experimental shorter reference prompt:core4/4, hard identity3/4 with the same unsafe phones.
Increasing reasoning still3/4. Neither is promoted. Single Flash vision4/4 identity but7/12
physical/depiction, matching Luna there and failing the gate at higher cost. Flash conversation
comparison completed8 cases but lost identity caveats and introduced time overprecision; rejected.
The latest primary catalogue was checked via OpenRouter's models endpoint; stored costs are
observed responses, not a price-based quality claim. Main/default vision remains Lite.

Controlled bilingual wording retained identity caveats across8 possible-match replies, but the
actual streaming-v4 and complete-history-v1 still lost Hindi caveats. Adding explicit source flags
made streaming-v5 retain both English/Hindi caveats. **This small result is not universal fidelity.**
Full-history-v2 after summary repair now retains caveats for dated English and nine-day Hindi
positives and truthfully rejects a purple-cane negative. Its undated coffee lookup abstains where
v1 found the cup; inspect query/vision behavior before calling the complete workflow accepted.
All4 jobs complete, no negative is silently omitted. Latest general-memory reruns are ongoing.

All13 cached public media files were hash-matched against the known four-photo fixture before
API evaluation; compatible Gemini2 vectors were reused. Only copied DB dates were simulated
(1day,9days,unknown), original clocks/files unchanged. This is a public edited-video diagnostic,
not nine days of continuous natural footage. An offline exact-payload audit retained both640×480
frames with RGB mean error<0.047; the two-phone failure is not missing/cropped input.

Last full suite before latest summary repair:459 passed26.61s, lint/format/JS and synthetic Chrome
passed. Summary repair targeted95 passed5.44s. Final full suite/cost reconciliation still pending.
Earlier checkpoint tables below describe their named revisions and remain valid as history.

## Decision and method

Execute the approved [design](../superpowers/specs/2026-11-17-simple-agent-memory-design.md):
one shared native policy/tools, Luna conversation and memory, Flash-Lite vision. SQLite,
Gemini Embedding2 and Sarvam stay. No UI/main changes or new PR. Public/synthetic cloud inputs
only; private laptop media, transcripts and vectors remain offline. No real hardware activation.

The conversational policy is81 words; memory140, reference122 and inspection87 at61da728.
There is one focused memory interpretation policy for ingest/relevance and one prompt per visual
task. A needed image can require a second memory interpretation after observation; this is not
an extra judge. Removed JSON planning, separate ambiguity/correction/positive judges, duplicate
reference modes, departure detection and active delivery. Existing reminder/statement data stays.

Actual API runs cover embeddings, SQLite, interpretation, source links, unforced native tools,
restart/chat eviction and final replies. Source/setup scores are **proxies**, not semantic or
physical identity accuracy. Final answers are read by Codex inline, not a separate model judge
or human-user acceptance. Old opened R29 conditions remain reused regressions. New synthetic
conditions were frozen before inference; public-source splits exclude shared image IDs.

Machine/runtime measured: Apple arm64, macOS15.7.3, Python3.12.11; LiveKit agents/OpenAI plugin
1.8.10, OpenAI SDK3.42.0, NumPy2.5.4, sqlite-vec0.1.9. Models: openai/gpt-6-luna,
google/gemini-3.5-flash-lite, google/gemini-embedding-2. At61da728 policy7/memory5,
reference9/inspection10. Model names do not pin immutable provider weights.

## Implemented repairs

- General source-linked facts, preferences, habits, events, reports and plans; automatic processing
  before typed/spoken generation. Related-record matching and correction/retraction belong to memory.
- Ordinary moves append; corrections version actual prior records. Quotes, dependencies, clocks,
  source availability and compatible vectors are validated; writes are atomic and idempotent.
- Missing/deleted/future evidence is withheld in provider context copies, including raw prior
  transcripts. Original input stays durable. A failed response never deletes the user's input.
- Per-operation text/visual/memory grounding prevents one shown photo attaching to unrelated facts.
  Resolve visual pronouns before saving and refresh candidates with the actual observed description.
- Voice receives server-owned structured evidence through the existing transport/shared database;
  both adapters receive the same available context. Partial STT does not trigger memory writes.
- Stale single snapshots cannot bypass utterance-window clocks. Contradictory clarification plus
  proposed writes now clarifies without writes. Remembering a plan does not promise future delivery.
- Same SDK tools across interfaces; bounded native iterations, validation, cancellation, source
  rechecks, and explicit provider/embedding/persistence failures. No fixture IDs or coordinate rules.

## Earlier measured outcomes before strict-schema/source repairs

| Evaluation | Result | Practical limit |
| --- | --- | --- |
| General memory, development-v2 + holdout-v2 |8/8 +8/8 source/workflow proxies; all16 final answers read correctly | Authored synthetic conditions, policy4/memory4; later targeted policy changes separately tested |
| Recall holdout-v3 |7/8 exact-source proxies; all8 final answers read correctly | Historical lookup returned correct old state but automatic preparation also offered current state; extra source/context remains a limitation |
| Default household core development-v5 / holdout-v2 |3/4 +4/4 | Development bottle initially refused, no unsafe save; later stages cannot erase failed setup. Coarse/misclassified object descriptions limit recognition claims |
| Default hard identity holdout-v2 |3/4 | **Unsafe two-phone binding persists.** R29 merged joint baseline refused this known condition; simplification is not a global reliability win |
| Single Luna vision identity override |4/4 | Reused small regression; default remains user-selected Lite |
| Luna vision core development / holdout |3/4 +4/4 | Bottle remains unresolved; one better identity score does not establish broad superiority |
| Public COCO category/count,32 heldout conditions |Lite23/32, Luna24/32; unsafe proxies8 vs6 | Annotation/category proxy; small, occluded/incomplete annotations; not unique identity |
| New public-source16 conditions |Lite12/16, Luna12/16; unsafe proxies3 vs2 | Eight newly selected CC-BY photos, new to recorded local evaluation, not necessarily model training |
| Physical object vs screen/poster,12 conditions |Lite4/12, Luna7/12 | Lite7/8 depiction negatives falsely visible; Luna4/8. **Both fail physical/depiction gate** |
| Natural Charades cross-view diagnostic |1/1 each | One scripted bag clip, unknown original capture clock; replay clocks simulated |
| Native spoken clear/ambiguous save then recall |2 workflows complete; actual replies/source behavior reviewed | Clear bottle remembered; ambiguous pair unlinked; raw conversation quote explicitly distinguished from a saved memory |
| Native spoken plan/corrected report plus current-location challenge |2 workflows,4 final replies reviewed correct | Copied public report stores; no acoustic STT/TTS or live physical acceptance |
| Unsupported actions-v2 |4/4 API completions; all4 final replies correctly decline unsupported action | Requests can be remembered as plans; no scheduling, calls or recording actually performed |
| Spoken synthetic evidence-v3 / real LiveKit stream-v3 |2/2 complete each; English identity caveat correct, **Hindi identity caveat fails** | Hindi says “your remote” despite only a possible match; current-location caveat does not repair identity overstatement |
| Offline private library |92 full strict video decodes,256 stored-vector queries on copied1085-frame index | All bytes unchanged; no private semantic recognition or acoustic inference |
| Final private conversion-v2 |2/2 old records preserve vectors/photos/rows; original database unchanged | Copied database, zero inference; no private reembedding |

The shared agent explicitly preserving uncertainty and the lookup tool describing possible
lookalikes did **not** repair the repeated Hindi caveat failure. Do not count transport completion
as a semantic pass. Two experiment-only short prompt candidates are frozen atddff1e2; results
are pending. No runtime prompt/model promotion based on a single opened case.

## Failed trials retained

Recall holdout-v1 had3 clear successes of8 planned conditions, failed historical/irrelevant/future
selection and malformed operations, aborted seventh setup, eighth not run. Holdout-v2's8/8 proxy
hid an actual future-record false answer through chat; repaired context withholding was verified
in-v3. The v3 as-of source envelope still contains excess current context despite correct answer.

Household development-v1 was1/4 (unresolved pronouns saved and recalled), v2 was3/4 (unsafe cups),
v3 was4/4, latest protocol v5 returned3/4 with a refused bottle. Holdout-v1/v2 both4/4.
Development-v4 stopped **before any inference** on a decreasing provider usage snapshot; other
three cases not run. Budget guard now retains the high-water/locally reported usage without
loosening caps. Hard identity-v1 and-v2 each3/4 with the same unsafe phones. Preserve these failures;
never aggregate repeated repaired runs as unseen household accuracy.

Unsupported actions-v1 falsely promised a future reminder and failed the camera request's memory
protocol. Short plan/scheduling distinction and clarification-without-writes repaired-v2.
Spoken evidence-v2 completed1/2 because the harness only allowed one tool continuation; the
model legitimately requested a second tool. A bounded full continuation loop fixed that harness,
not semantic Hindi uncertainty. Streaming setup-v1 failed in the harness before paid requests
(plugin initialization in a worker thread); imports were moved to the main thread. No hardware
or provider inference occurred in that failed setup.

## Budget, costs and artifacts

Verified ceiling is$8 TOTAL, starting usage$4.73185091. All paid runs are sequential and capped
at ≤$0.25, with$0.10 cumulative settlement reserve and$0.02 run reserve. No purchases/new keys.
At the pre-ablation checkpoint, key metadata reports$4.90887277; accumulated response costs
are$0.17784856, giving conservative cumulative$4.90969947. Settlement can lag/decrease across
replicas; use response-cost sums and the larger cumulative estimate, not per-run metadata deltas.
Final checkpoint reconciliation: metadata5.32518435; saved response costs0.59445744;
conservative cumulative5.32630835/8. The top checkpoint supersedes the pre-ablation totals.

Representative earlier response costs: general-v2 16 cases$0.006459175; default hard identity4 cases
$0.0108847 vs single Luna$0.00518268; COCO32$0.0158893 vs$0.0056416; native report challenges
$0.00159135; unsupported4$0.0009463. These observed costs/latencies are workload/provider-specific.
Prior interim metadata-delta costs for recall-v1/v2 were incomplete; actual response sums are
$0.00307135 and$0.004122 respectively. No success-only cost accounting.

Raw permitted generations/results stay ignored under data/runs/simple-*; original private
artifacts remain local. Frozen recipes/cases and drivers live under experiments/companion/:
general_memory_workflows.json, household_workflows.json, household_identity_cases.json,
capability_cases.json, simple_fresh_visual_cases.json; recall_workflows.py, household_workflows.py,
household_spoken_replay.py, spoken_fresh_evidence.py, streaming_voice.py, capability_replay.py,
visual_verification_replay.py, physical_scene_replay.py, fresh_visual.py, local_replay_audit.py.
Streaming uses the installed SDK's actual request parameters/tools/parser, guarded HTTP hooks
and observed SSE usage; evaluation retries disabled. It opens no microphone or synthesis stream.

New public images:8 photos,1.16MiB, licensed provenance/credits/hashes retained in local manifest;
16 conditions frozen before calls. [COCO](https://cocodataset.org/) and
[CC BY2.0](https://creativecommons.org/licenses/by/2.0/) describe the source dataset/license;
those are source-reported provenance, not laptop accuracy evidence. Natural-video license/source
limitations remain those recorded in R29; do not redistribute cached Charades frames.

## Verification and recommendation

At8fd7c8f: **471 tests passed in45.40s**; Ruff lint/format (113 Python files), JavaScript syntax,
diff whitespace, local Markdown links and synthetic Chrome API/capture-stop/inactive-poll checks
pass. Browser replay uses zero paid inference or real hardware and has zero page errors.
UI has zero diff from128e2fe; local main remainscfe8fa4 and remote mainbdb7ad0. All125 locked
package versions/sources remain unchanged; only the web-extra SDK requirement was corrected.
Existing embeddings remain compatible; no private reembedding occurred.

Keep the simpler architecture and root-cause repairs on the work branch. Do not call the product
or a PR merge-ready: visual identity/depiction acceptance still fails, and no new PR/CI review
is requested or completed. The English/Hindi identity-stream repair passed only a small diagnostic;
actual acoustic/wake/turn-taking, physical household and human acceptance remain open. Reject the
scene-first default migration after appearance regressions. The user requested no further expansion
of this checkpoint, no overengineering and root-cause repairs instead of individual-case rules.
No demo production is included.
