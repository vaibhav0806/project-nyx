# R12 — What should make Nyx substantially more reliable next?

Date: 2026-11-03. Owner: Codex, inline assessment requested by the user.
Status: findings ready for discussion; recommendations are not an approved implementation plan.
Baseline: `1e578ff8480610e950d025d4668c92ce7719bc84`.
Decision affected: next product milestone, conversation ownership, retrieval evaluation,
capture runtime and the eventual on-device product path.

## Question and method

Which changes most improve the probability that an everyday spoken request produces a useful,
evidence-supported answer, and that a failed request can be recovered without developer help?

Read the product vision, current milestone entries, R6/R9/R10/R11, and the capture, ingestion,
conversation, reference, statement, retrieval, verification and playback implementations.
Compared current primary documentation and research on 2026-11-03. Ran three isolated offline
probes against the actual implementation. No new camera/microphone capture, private-media
inspection/upload, model download or paid inference was used. Temporary probe databases were
removed. Environment: Python 3.12.11, Darwin 24.6.0 arm64, LiveKit Agents 1.8.10.

The unchanged baseline passed 378 tests plus lint, formatting and JavaScript syntax checks
earlier in this session before publication. Those checks do not measure household accuracy.
The probes below are narrow reproductions, not estimates of field failure rates.

Reproduce all three without credentials or devices:

```sh
uv run --no-sync python experiments/companion/reliability_probe.py
```

This research script reports the current outcomes; it is not a passing acceptance test and does
not assert that the observed failures should remain after fixes.

## Existing strengths to preserve

- Original recordings, capture timestamps, clip offsets and sampling/model fingerprints persist.
- Retrieval candidates remain distinct from user confirmation and current location.
- User statements and intended placements are attributed separately from visual observations.
- Saved uploads and interrupted indexing have recovery paths; source deletion is journaled.
- The one-application Python/SQLite architecture is sufficient for the current measured scale.
- Idle audio stays local, cloud credentials stay backend-only, and saved video stops at 1 GiB
  without automatically deleting recordings.

## Observed findings

### 1. Spoken turns lose accumulated evidence

**Reproduced, high priority.** In [realtime.py](../../src/nyx/realtime.py), the tool-result handler
replaces the turn's `sources` on every result. A visual lookup followed by statement retrieval
therefore loses the visual source IDs when the latter has no video sources. The assistant-item
handler persists that last list with the combined answer.

Offline method: use the real `serve()` function with fake session, socket, LLM and TTS adapters;
create one transcribed turn; execute a visual tool and then a statement tool; return
`['synthetic-video']` and `[]` respectively; complete the assistant message. Inspect its saved
turn, then call the existing source invalidation method.

Observed output:

```json
{"sources_after_two_tools": [], "status": "complete"}
{"sources_available_after_delete": true}
```

The same sequence also loses visible review evidence. In
[companion.js](../../src/nyx/web/companion.js), `request()` hides the source panel at the start
of every tool request and clears `reviewCandidate` if that particular result has no visual.
A Node probe executed the actual method with minimal DOM/tool fixtures:

```json
{"source_panel_after_visual": {"hidden": false}}
{"source_panel_after_statement": {"hidden": true, "reviewCandidate": null}}
```

The implication is limited but concrete: a valid multi-tool spoken answer can lose its source
review and deletion dependency. This does not establish that every spoken answer is affected.

**Proposed change:** accumulate structured evidence by turn/tool ID, retain visual review until
the turn changes or its source disappears, and persist all dependencies used by the final answer.
Preserve user-claim citations as well as video sources. Validate stale-turn/cancelled results.

### 2. Spoken and typed requests expose different capabilities

**Observed in code.** The spoken `look_for_object` tool accepts only `query`, `history`, and
`hours`. The underlying typed actions also support `excluded_frame_ids`, `before_frame_id`,
and undated matching. Voice therefore cannot express the full rejection/earlier-than contract
implemented in [agent.py](../../src/nyx/agent.py). This is a capability gap, not a measured
rate of model mistakes. The shared action loop still enforces some policies for voice calls.

Each LiveKit tool is currently relayed server → browser → `/api/agent` → polled job → browser
→ voice socket. `initial_action` makes that job execute one tool and finish; LiveKit owns the
continuation. The browser's `companion.working` gate and server `tool_lock` serialize tools even
though the model is configured for parallel calls. Per-tool jobs also overwrite the turn plan,
so the saved plan is not a complete multi-tool voice trace.

**Proposed change:** make one turn module own context, tool evidence, rejection state, temporal
bounds, cancellation and persistence. Typed and spoken adapters should cross the same seam.
Keep LiveKit for speech and turn management. Keep the browser responsible for media capture and
playback acknowledgements while reducing its role in relaying backend tools. This improves
locality and test leverage without introducing another service or a provider framework.

### 3. Frame selection can remove the only useful evidence

**Reproduced limitation.** Automatic ingestion scans at 0.1 seconds and applies
[select_activity_frames](../../src/nyx/attention.py), whose change detector works on 160×96
grayscale frames. Motion is a nomination signal; it does not guarantee object/event coverage.

Offline method: 100 synthetic 1280×720 frames at 10 Hz, uniform gray background; add a contrasting
25×13 pixel rectangle from 3.0 through 5.9 seconds, then remove it. Run the production selector.

```text
object visible: 3.0–5.9 seconds
selected offsets: [0.0]
selected frame containing object: false
```

This is not a household accuracy result. It demonstrates a failure class that no downstream
model can recover from the selected-frame index alone. The source video may still contain it.

**Proposed experiments:** measure event retention before embedding recall; compare the current
selector with a modest periodic floor plus activity frames; test query-directed denser inspection
of saved source intervals; evaluate crops when small objects are lost in full-frame representations.
Retain source offsets and uncertainty. Measure storage, ingestion backlog and cloud cost along
with recall, rather than embedding every frame by default.

### 4. Retrieval is bounded by a semantic shortlist, not the full video

**Observed in code and R10.** [answers.py](../../src/nyx/answers.py) nominates up to 12 frames
from 64 semantic candidates for companion history queries. Temporal diversity is within a
video ID, so successive ten-second recordings can still nominate nearly identical moments.
Candidates are then checked newest-first within the shortlist. A later true sighting ranked
outside the pool cannot be returned. Reference comparisons happen after text candidate retrieval;
the reference image does not itself retrieve historical images.

**Proposed change:** evaluate persistent cross-segment episodes and multiple source-linked
representatives; compare text and visual-reference candidate nomination; expand around promising
intervals in the source video. Keep the wording bounded to the checked evidence. An object crop
or a track is still fallible evidence, not proof of unique identity.

Use an explicit-user-enrolled object example only where it helps distinguish similar belongings.
Start with a few objects and local SQLite records. General room maps, scene graphs and new vector
infrastructure are not justified by the current measurements.

### 5. Voice timing has an available improvement path

**Observed in code.** The STT adapter receives speech/VAD events but does not request transcript
intervals or populate `SpeechData` start/end times. The browser freezes a 12-second window when
the final-transcript notification arrives, selecting up to six frames. This is a reasonable bounded
patch, but a long utterance or delayed finalization can exclude the demonstration.

The current Sarvam realtime documentation exposes optional segment timestamps on finals.
**Proposed experiment:** map the outgoing PCM sample clock to browser frame timestamps, including
the wake prebuffer and pauses; use the returned utterance interval to nominate frames around
the actual speech. Test delayed finals, two demonstrated objects and a correction mid-utterance.
Segment offsets need a validated clock mapping; they are not automatically wall-clock timestamps.

Endpointing currently uses 400 ms silence, zero additional minimum delay, VAD-style interruptions
and disabled false-interruption resume. Browser echo cancellation is requested, but field echo
quality is unmeasured. Test deliberate pauses, television speech, backchannels, self-echo and
English/Hindi code switching. Tune against those cases before choosing another speech provider.
Benchmark a dedicated wake detector against the existing Whisper wake path with false accepts
per hour, missed activations, distance and CPU measurements. No replacement is selected here.

### 6. Retention and recovery currently limit everyday use

**Observed/documented.** At the requested 1 Mbps encoding rate, 1 GiB is approximately 2.4 hours
before overhead; actual size varies. R11 already records this limit. The present policy is a
development constraint, not an all-day or multi-day memory policy.

Browser capture intentionally stops on delayed rotation, sleep, track interruption or failed
saving. Voice sockets require manual reconnection after closing. An indexing failure preserves
the saved recording but leaves it out of search. The journal handles restart of queued/indexing
work; it does not automatically retry already-failed segments. Browser pending upload blobs
are in memory, so page loss can lose unsaved material.

The direct answer endpoint attaches coverage information, while companion tools do not consistently
provide the same coverage state to the spoken answer. Saved-through and searchable-through maxima
also do not describe every gap between them.

**Proposed change:** expose capture, saved-media, indexing and voice health as separate states;
include applicable coverage gaps and lag in answer evidence; make recovery understandable without
opening diagnostics. Evaluate idempotent, bounded recovery of transient reads/indexing and
reconnections. Any retry policy should remain within an explicit time/cost budget and distinguish
authentication/quota failures from transient failures; it must not silently switch providers.

Keep the current stop-without-delete behavior until the user chooses a different storage/retention
policy. Test a native capture runtime for the eventual device after the browser baseline is measured;
native capture would still need device permissions, supervision, and honest sleep/power-loss gaps.

### 7. Durable claims are narrower than a complete personal memory

**Observed in code.** [statements.py](../../src/nyx/statements.py) stores one object-statement
record per turn. The original transcript remains the claim; destination/kind are in resolver
metadata. Retrieval ranks semantic candidates and asks a model to select relevant IDs, with
named-transcript lexical fallback. There is no general claim-validity or supersession model.
Prompts ask the model to retain contradictions, but corrections are not a durable first-class
operation across the memory lifecycle. Snapshot and revision retention also need to be considered
when designing a future “forget this” action.

**Proposed direction:** retain separate observed sightings, reported placements, intentions and
corrections with timestamps and source links. A correction should supersede a claim for present
answers without falsifying history. A useful answer can say “You later said you moved it; I haven't
seen that placement.” Evaluate this bounded object-memory extension before expanding to people,
arbitrary life facts, visits or automatic daily summaries.

### 8. The active spoken product lacks a representative acceptance suite

**Observed.** `tests/test_realtime.py` has five tests, covering audio synchronization, STT event
translation, endpoint options, playback acknowledgements and the initial idle-audio gate. Other
tests exercise backend tools and fixture-driven UI behavior. Earlier planner benchmarks largely
exercise the typed decision path or older runtime configurations. There is no tracked GitHub
workflow. This does not mean the repository is untested; it identifies the missing integrated
surface around the current spoken workflow.

**Proposed next milestone: reliable daily object recall in one room.**

Build a small, versioned replay suite with held-out cases, fixed source timestamps and explicit
expected evidence. Exercise the same typed and spoken turn module, then selected synthetic-audio
runs through the actual LiveKit wiring. Include:

- Visible, hidden, absent and lookalike objects; brief demonstrations and low light.
- “This/it,” clarification, corrections, rejection and “before that moment.”
- Claim-only answers, intentions versus placements, contradictions and source deletion.
- Interrupted tools, late results, disconnected STT/TTS, quota failures and partial verification.
- Restart, indexing backlog, capture gaps, budget exhaustion and playback denial.
- English, Hindi/Hinglish, pauses and interruptions.

Measure each stage: captured-event coverage, selected-frame coverage, candidate recall, visual
judgment precision, correct useful final answers, justified abstention, correction recovery,
source attribution, and p50/p95 speech-end-to-first-useful-audio. Count incomplete/failed runs
in the denominator. Measure per-success cost, idle CPU/memory and time requiring user intervention.
Cached acknowledgement audio is not the first useful answer.

Initial proposed gates for discussion: at least 90% correct useful answers on a balanced held-out
supported set; every factual location claim has source/time attribution; zero unsupported confident
locations in the finite deliberate-uncertainty set; all cancellation/deletion regressions pass.
Report raw counts by case class. A zero-failure finite set does not prove zero field risk. Set
latency and wake targets after recording the current end-to-end baseline and observing intended
users; small synthesis timings cannot establish a whole-product latency target.

## External evidence and how it changes the decision

These are source-reported capabilities/findings, not Nyx measurements. Accessed 2026-11-03.

- [Sarvam realtime STT](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/realtime-streaming)
  documents optional final-transcript intervals, live VAD configuration and early events. This
  supports a focused synchronization/endpointing experiment using the existing provider.
- [LiveKit turn tuning](https://docs.livekit.io/agents/logic/turns/tuning/) separates endpointing,
  interruptions, preprocessing and speculative generation. Test these independently.
  [Testing guidance](https://docs.livekit.io/testing/overview/) covers tool/error/grounding tests
  and multi-turn simulation; [data hooks](https://docs.livekit.io/testing/observability/data/)
  support locally collected per-turn latency and usage. Keep Nyx's diagnostics local.
- [Ego4D episodic memory](https://ego4d-data.org/docs/benchmarks/episodic-memory/) defines temporal
  language queries and visual-example last-occurrence localization. Borrow that task structure
  and time/object labels. Its wearable-camera setting differs from Nyx's fixed room, so public
  benchmark scores would not establish household performance. Dataset access/license must be
  checked before using any media.
- [LongMemEval](https://arxiv.org/abs/2410.10813) tests extraction, multi-session and temporal
  reasoning, updates and abstention. Adapt these dimensions to object claims and corrections;
  retain separate retrieval and final-answer scores.
- [Chrome lifecycle](https://developer.chrome.com/docs/web-platform/page-lifecycle-api) documents
  suspension/discard and lifecycle testing. This supports an explicit runtime resilience evaluation;
  it does not imply that every active recording tab is routinely discarded.
- [openWakeWord](https://github.com/dscripka/openWakeWord) describes custom wake models and
  false-accept/false-reject evaluation. Treat it as a comparison candidate. The project distinguishes
  its code license from the included models' noncommercial terms; do not treat those pretrained
  assets as a selected commercial dependency.
- [Gemma 4 overview](https://ai.google.dev/gemma/docs/core) describes small edge-oriented multimodal
  models. It is one local-feasibility candidate, not evidence that it meets Nyx's quality, Hindi,
  memory, power or latency needs. Compare local candidates on the same accepted replay cases.
- [StreamMem](https://arxiv.org/abs/2508.15717) studies bounded streaming video KV memory. This
  motivates future research but is not a drop-in SQLite retrieval replacement. Defer integration
  until the simpler event/source representation has a measured failure it could address.
- [Long-term smart-speaker study](https://mhealth.jmir.org/2024/1/e47472), based on interviews with
  20 older adults with sustained device use, emphasizes daily context and placement. It supports
  doing intended-user task/repair observation; it does not validate Nyx or local language assumptions.

## Recommended sequence and unresolved decisions

1. Fix turn-level source accumulation, source-panel persistence and spoken tool parity; add
   offline regressions and a small CI baseline.
2. Establish the current spoken end-to-end replay baseline and stage metrics.
3. Improve event/frame retention, temporal expansion and claim corrections against that baseline.
4. Exercise longer sessions and recovery within the approved storage budget; choose an explicit
   all-day retention policy before expanding capacity or deleting anything.
5. Evaluate intended-user task success and a bounded on-device runtime candidate using the same
   acceptance cases. Keep cloud prototype and eventual local-device claims explicit.

The highest-leverage architectural work is turn ownership, followed by source-linked event/claim
memory and capture health. Split these modules around domain behavior and testable interfaces;
file length alone is not a reason to refactor. Existing exact SQLite scans were not the dominant
latency in R10, so retain the database until new measurements justify a change.

The key product decision for discussion is whether the next milestone primarily targets dependable
one-room daily recall or near-term physical/offline-device feasibility. The former is recommended
first because it provides the evaluation contract for the latter. Reminders, people recognition
and calls remain separate product capabilities with their own validation needs.

No application code or runtime configuration was changed by this assessment.

## Subsequent implementation — 2026-11-03

After reviewing the assessment, the user selected all three workstreams and a ten-day pilot
horizon, then approved proceeding. The [foundation](../pilot.md) fixes source accumulation,
old-turn result isolation, source-panel persistence and lost candidate/trace metadata. Spoken
lookup now exposes exclusions/earlier-than constraints and 240-hour history; dated searches
exclude future evidence. All 384 deterministic tests pass. These are implementation checks,
not measured household accuracy.

Rerunning `uv run --no-sync python experiments/companion/reliability_probe.py` now reports
`sources_after_two_tools=["synthetic-video"]`, `sources_available_after_delete=false`, and
`hidden_after_statement=false`. The synthetic small-object selection failure is unchanged
(`selected_offsets=[0.0]`, `selected_contains_object=false`) and remains follow-on work.
The original findings above describe the recorded baseline commit, not the current fixed paths.
