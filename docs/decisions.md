# Decisions and open choices

## Natural replies and browser-local time — 2026-10-31

Use rounded elapsed time for spoken historical sightings, with the checked location when available. Remove the stock image-review and verification disclaimer from conversation; express candidate identity with a brief “I think”. Exact timestamps and evidence metadata remain available in View source. Unknown or future capture times must not become invented relative times. Attributed user statements remain quotes, without boilerplate. Browser IANA timezone accompanies typed and spoken requests. Simple current-clock questions are deterministic; other agent requests receive a local-offset current time and timezone. No model call is needed to read the clock.


## Jev voice routing — 2026-10-31

User requested a Kairo-style fast voice gate and selected Jev through OpenRouter.
Activated speech now uses `typesafe/jev-1.14` at `/api/alpha/decisions` after the
existing exact-greeting shortcut. A typed boolean probability of at least 0.95
permits a bounded Luna conversational answer; all other decisions use the existing
agent. The responder can also defer to the agent. This provisional threshold is
not a measured accuracy guarantee. Provider/invalid-response errors remain visible.
Tool requests get a fixed spoken acknowledgement concurrently with agent work;
late or cancelled acknowledgement audio is discarded. No new provider account,
SDK, idle-audio upload, or image input to Jev. Typed requests retain their existing
agent path. See [voice findings](research/R6-handsfree-voice.md#jev-routing-check--2026-10-31).


## Conversation-first demo interface — 2026-10-31

The user approved the “Just a conversation” Paper design and authorized implementation.
Use a quiet dark screen with the latest question and answer, a combined talk/stop control,
microphone mute, and optional typing. Evidence is available on demand through “View source”;
recording previews, search tools, history, and diagnostics belong in Settings & history.
Keep actual camera state visible and directly pausable. The visual redesign does not change
retrieval claims, provider boundaries, storage policy, or inference models. Continue with
packaged plain HTML/CSS/JavaScript and existing APIs. The user also authorized local commits.


## Speech-linked finding and surrounding replay — 2026-10-28

Historical matches now replay up to ten seconds before and after the sighting,
across available segments in the same reliably timed capture session. Gaps are
not reconstructed. Imported or uncertain recordings use clip-local bounds.

The history tool searches captured user transcripts by object words or within
90 seconds of the sighting (30 candidates). The visual model selects at most two
existing transcript IDs. Exact quotes are attributed separately from visual
findings; intended placement is not confirmed placement. This bounded feature
is not general long-term semantic memory. Listen now (30 seconds) bypasses missed
wake activation; ignored wake attempts stay quiet in the conversation UI. Idle audio is not
archived, so missed statements cannot be recovered.


## 2026-10-28 — Cloud is the primary MVP inference path

**Approved by the user and implemented in this branch.** Replace local Qwen/MLX
and SigLIP inference with OpenRouter reasoning/vision and multimodal embeddings;
consolidate activated STT/TTS onto OpenRouter. Retain local Whisper wake recognition,
activity filtering, the small event detector and recording/database storage.
No equally supported offline LLM/VLM path. User supplied a key with a $2 test cap.

The development index may be rebuilt without production compatibility machinery.
Preserve recordings and evidence timestamps. The explicit reindex command replaces
vectors transactionally; cloud models cannot query the old vector space. Current
model selections and measured limits are in [R9](research/R9-cloud-mvp.md).
Older local-only/Sarvam decisions below are historical and superseded by this decision.


Updated: 2026-10-20. This records discussion outcomes and engineering choices. The user explicitly resumed work on 2026-10-19; M1 retrieval and continuous recording/background indexing are authorized. Unmeasured model choices remain experiments.

## Status vocabulary

- **Established:** explicitly supplied or accepted in the discussion.
- **Proposed:** recommendation awaiting review or measurement.
- **Open:** an answer is still needed; record what will resolve it.
- **Superseded:** retained for traceability; no longer the working direction.

## Established direction

| ID | Decision | Basis |
| --- | --- | --- |
| D1 | Mission: extend agency, dignity, and independence as people age; start with older adults at home. | User clarification and approved pitch. |
| D2 | First target is a good laptop demo; standalone hardware follows. | Explicit user direction. |
| D3 | Product includes enabled continuous video recording, live inspection, searchable history, conversation/fact recall, and reminders. | User's feature notes and subsequent scope discussion. |
| D4 | Cloud voice is acceptable; explore local vision. Full offline operation is not required for this prototype. | Explicit user answer. |
| D5 | Investigate a light background perception/retrieval path and on-demand interpretation; keep JEPA research distinct from the retrieval baseline. | Working direction discussed with the user and teammate; exact model remains open. |
| D6 | Resume M1 local visual retrieval after the documentation review. | User explicitly requested “continue working now” on 2026-10-19; supersedes the earlier pause. |
| D8 | Stop continuous recording at a 1 GiB saved original-video budget; preserve existing clips. | Explicit user selection on 2026-10-19. |
| D7 | Work inline; no subagents without explicit user request. | User's personal rules. |

## Proposed technical choices

| ID | Proposal | Why / what must be checked |
| --- | --- | --- |
| P1 | One Python package in `src/nyx/`, with a small browser interface. | Running baseline: packaged plain browser assets; continuous capture now uses the same packaged browser stack. |
| P2 | Python 3.12, uv, FastAPI. | Dependencies installed/locked and validated for the bounded manual interface. |
| P3 | SQLite plus `sqlite-vec`, with original media on disk. | Keep timestamps, sources, vectors, facts and actions local; verify extension support and retrieval behavior. |
| P4 | Small aligned image/text encoder for the first retrieval baseline. | Enables descriptive-query retrieval; compare real small-object scenes before selecting a checkpoint. |
| P5 | Local small VLM for on-demand inspection/verification. | Keep heavier analysis selective; measure quality, latency and working memory. |
| P6 | Fixed-camera, one-room development setting with five described test objects. | Makes evaluation repeatable; final form and coverage need review. |
| P7 | Start with explicit memories and transcript retrieval; introduce a framework or extra indexing only when needed. | Avoid untested memory behavior and additional infrastructure. |

## Open choices

| ID | Question | Resolve through |
| --- | --- | --- |
| O1 | Which three daily-life workflows matter most to intended users? | R1 interviews and role-play. |
| O2 | Preferred language, interaction style, and installation/maintenance needs? | R1/R2 research. |
| O3 | Camera placement, acceptable recording coverage, retention duration and identity handling? (Demo video budget: D8.) | Product review plus R2 findings. |
| O4 | Encoder checkpoint, preprocessing, sampling/crop strategy, and retrieval thresholds? | R3 measured baseline. |
| O5 | VLM checkpoint/runtime and verification quality on retrieved candidates? | R4 measured comparison. |
| O6 | JEPA's useful contribution, Mac compatibility, and prediction task/data requirements? | R5 experiment. |
| O7 | Sarvam selected; target-language performance, interruptions, and tool latency remain open. | R6 trial. |
| O8 | Long-run capture reliability and retention/deletion controls beyond the current continuous slice? | M2 hardware soak and product review; current stack is selected below. |
| O9 | Dedicated hardware and standalone operating budget? | Measured laptop workload, then M7. |

## Superseded assumptions

- Desk object-finding as the full product: the desk is now a development setting within a broader independence mission.
- Cloud vision as the default: the current preference is local vision exploration and cloud voice. Cloud image processing needs its own decision.
- Voice-first implementation order: the next proposed technical experiment proves visual retrieval before voice integration.
- Snapshot-only history and no raw video: the user's scope explicitly includes recording while enabled, with selective indexing.
- Seven-day retention as a settled default: retention and capacity remain open.
- An implementation-ready API/file layout from the earlier generated plans: those details were drafts and must not dictate the design review.

## Recording a new decision

Add a row or short entry with: ID, date, status, decision owner, choice, alternatives considered, supporting evidence, tradeoff, and trigger for revisiting it. Update affected documents and link the relevant research finding. Only mark a proposal established when the user actually accepts it; only mark benchmark claims measured when a result exists.

## M1 implementation selections

- Python 3.12/uv and `src/nyx/` are the running baseline. Vision dependencies are optional; no API/UI framework is needed for the CLI slice.
- SigLIP 2 base at checkpoint `75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2` through PyTorch/Transformers is the first measured encoder. MPS inference works on this machine. This does not close the model-selection question.
- SQLite plus `sqlite-vec` cosine distance provides exact candidate ranking with metadata filters. No ANN scalability claim is made.
- A generated HTML candidate gallery is sufficient for M1 inspection. Live capture, browser interaction, VLM verification and voice remain separate work.
- Only permitted public reference images and synthetic fixtures were used. No live camera, household-media upload, cloud voice, interviews, or purchases were performed.

## Earlier manual interface implementation selections

2026-10-19, engineering calls following the user's request to continue and confirmation that no existing clip is available:

- Start the bounded M2 manual interface to enable M1 household evaluation; both milestones remain in progress. This does not waive the independent-evaluation gate for continuous recording.
- Use optional FastAPI/Uvicorn with packaged plain browser assets. A single local process and inference worker are sufficient; no React/build system or provider abstraction is needed. This refines the proposed root `web/` layout to `src/nyx/web/` so installed packages include the UI. Revisit when actual frontend complexity warrants it.
- Browser capture is video-only, opt-in, maximum two minutes, followed by explicit index/discard. Imported wall-clock time remains unknown; browser capture time uses the browser clock. Stop on track interruption or tab hiding instead of claiming continuous coverage.
- Keep the existing full-frame encoder default: the five-view crop experiment adds work without improving recall@3/@5 on the correlated smoke fixture. Revisit with independent household labels.
- Serve only localhost; source IDs resolve registered evidence and support range playback. Job status is ephemeral and does not imply durable restart recovery. No cloud-media fallback is introduced.

## Continuous recording implementation selections

2026-10-19, following the user's successful manual retrieval demonstration, explicit request to start and 1 GiB budget selection. This supersedes the manual-only boundary above; household accuracy evaluation remains open.

- Keep FastAPI, packaged plain browser assets and the pinned local encoder. Record independent approximately ten-second files and automatically save/index them; do not treat arbitrary MediaRecorder timeslices as playable files.
- Persist capture sessions/segments/events in `capture.sqlite3` separately from the embedding index. Stable segment IDs and staged atomic saves permit idempotent retries and recovery. Preserve saved sources even if a model fails.
- Advance one inference worker in two-image batches; prioritize queued search between them. This bounds contention without introducing another model copy or service. Long model load/decode calls remain nonpreemptible.
- Bound server pending segments to eight; stop browser capture on backpressure or save failure. Keep pending blobs for retry/download only while the page survives. Saved/searchable times and interruptions remain separate from camera-on state.
- Stop at 1 GiB original-video storage without deleting clips. Existing imports count; model cache/thumbnails are additional. Retention duration remains pending; explicit source-aware deletion is implemented in the follow-up below. Revisit sampling/segmentation/limits after a thirty-minute real-camera run and independent household evaluation.
- Do not auto-resume capture after restart. Interrupted tails have unknown wall-clock time while clip offsets remain searchable; hidden-tab recording and real sleep behavior still require hardware evaluation.
- The user requested the pre-automatic-indexing snapshot on GitHub: manual baseline `67fcaf5` is pushed to `main`. The user subsequently tested automatic indexing for 2–3 minutes and explicitly requested this continuous slice be pushed to `main`.

## History control implementation selections

2026-10-19, following the user's request to publish automatic indexing and proceed with next milestone work:

- Publish the tested continuous-indexing slice as `8356aa8` on `main`. Work on the next slice stays on `feat/history-controls` until separately published.
- Add explicit deletion of one source and its derived thumbnails/vectors, with confirmation. Require capture stopped and active inference/upload work finished; this simpler conflict boundary avoids introducing cancellation into the current worker.
- Keep durable deletion intent and ID tombstones in the existing capture journal. Finish interrupted cleanup before requeueing saved work; a retried deleted segment must never reappear. Do not load a vision model to delete footage. Preserve unrelated recordings.
- Preserve increasing frame IDs in SQLite metadata so old thumbnail URLs cannot alias new evidence, including for preexisting indexes. Database free pages/previous downloads are not securely erased.
- Add optional synthetic recording duration with backlog, server-process RSS and periodic search timings. These measurements exclude the browser/FFmpeg and do not close actual-camera or household-accuracy gates. Retention duration remains open and no automatic deletion is enabled.

## M3 implementation selections

2026-10-19, user explicitly requested M3 after discussing retrieval with temporal context:

- Keep the existing Python/MPS stack. Use Qwen3-VL-2B-Instruct at revision `89644892e4d85e24eaac8bacfd4f463576704203` as the initial on-demand checker after the [R4](research/R4-local-verification.md) smoke comparison. Keep SigLIP 2 for retrieval. SmolVLM-500M was benchmarked, not enabled as a fallback; its prompt/schema result does not establish general visual incapability.
- Require Transformers >=4.57.1 for the native Qwen3-VL path; the lock retains tested 4.57.6. No new inference framework or provider abstraction is added.
- Use explicit object/mode/date controls first. Date ordering uses capture start plus decoded offset, never import time. Latest answers cover checked samples only: twelve recent dated frames, with up to five semantic fallback candidates if needed. Full archive recall and natural-language temporal/event reasoning remain open.
- Keep source-linked neighbors as unverified context inside the selected time bounds. Inspect original source frames with the VLM; keep ambiguous/invalid responses uncertain. Landmark text is fallible model output, not independently validated guidance.
- Inspect current view only from an explicit snapshot of an already-enabled camera. Validate time at input, queue exit and model-load completion; display capture time and age. Retain snapshot evidence only in bounded ephemeral job results. Source deletion invalidates affected historical answer jobs.
- Preserve pending M2 history-control changes alongside M3 locally; the GitHub `main` publication remains the authorized continuous-indexing snapshot `8356aa8`. Neither this M3 work nor the history-controls follow-up is implicitly published.

## M4 hands-free voice selections

2026-10-19, user chose Sarvam, supplied credentials and explicitly rejected push-to-talk:

- The product starts camera/microphone with the app or future device and wakes to its name, like Alexa/Siri. This supersedes the previous manual-start/no-auto-resume browser choice. Browser permission/autoplay restrictions are visible recovery states. Automated developer tests use synthetic inputs only; that rule does not change product operation.
- The user subsequently explicitly selected v4 for both speech models. Use existing local visual tools, Sarvam STT (`saaras:v4`), constrained tool routing (`sarvam-105b`, reasoning disabled) and TTS (`bulbul:v4-flash`, now the companion persona). No cloud vision or ambient cloud stream. Credentials are loaded from ignored private `.env` by uv.
- Start with pinned faster-whisper tiny.en CPU/int8 for local utterance-based wake recognition. This can miss or falsely hear the name; it is not a production custom keyword model. Revisit after actual pronunciation/noise measurements. Keep raw audio bounded and ephemeral; video remains video-only.
- Keep plain browser audio and local HTTP transport. One microphone lease, bounded requests, generation cancellation, independent mute and visible transcripts are sufficient for this slice. The initial version paused listening during answers; the feedback follow-up below supersedes that behavior.
- Persist conversation text/tool context/source references in a separate SQLite file. Source deletion marks dependent references unavailable. Conversations are never asserted as fresh visual evidence; raw audio is not retained. Transcript deletion UI remains open.
- [R6](research/R6-handsfree-voice.md) records synthetic/provider evidence and cold integrated latency. The M4 latency and intended-language/user gates remain open. M2/M3/M4 changes remain local until separately published.

### M4 response to voice validation feedback

The user reported missed wake calls, slow reactions and “what’s up?” being treated as an object. Inspection confirmed a visual-only router, fixed speech threshold and unconditional audio discarding while busy/playback. The authorized fix adds a separate conversational intent, a fast common-greeting path after STT, concise evidence-derived spoken answers, Shubh's companion persona, local wake probing during speech/playback, bounded pending audio during processing, and a visible ten-second follow-up window. Idle audio outside activation stays local; activated follow-up speech may reach Sarvam. Existing evidence details remain on screen. Low-priority visual model preload moves cold loading to configured startup. Actual-room wake/echo and p95 latency remain unvalidated.

Keep tiny.en: a small synthetic comparison did not justify switching to base.en, which missed more wake prefixes and was slower on these clips. This is an experiment result, not proof of real-room reliability. The wire routing schema uses strings (empty for absent fields), normalized to internal nulls: live probes with nullable fields returned empty/clarification plans for valid questions, while the revised schema routed the exercised questions correctly. See [R6](research/R6-handsfree-voice.md).

## Publication authorization

2026-10-19: the user explicitly requested that all current work be pushed to GitHub. Publish the combined history controls, visual answers, hands-free Sarvam v4 voice and voice-feedback improvements on `main`. Earlier local-only entries above record development checkpoints and are superseded by this explicit publication request. Keep credentials, recordings, databases, generated artifacts and model weights outside Git. Publishing does not close the remaining M1–M4 validation gates or implement M5.


## Companion and event-request selections — 2026-10-20

The user approved a conversation-aware tool loop, continuous watching, adaptive indexing and a next-departure water-bottle reminder, and requested autonomous implementation/experiments. They subsequently authorized coherent local commits and explicitly prohibited pushing. The new work is on `feat/companion-loop`; earlier publication authorization applies to the older snapshot, not this work.

- Keep one Python process/package and the existing priority worker. A bounded local agent can inspect current evidence, search recent dated semantic candidates, widen history, create/list/cancel departure requests, clarify and converse. Qwen is reused for text decisions; no LangChain, service topology, extra text model or quantization is introduced. Revisit model choice after measured contextual/tool failures, not based on framework availability.
- Apply explicit product policies around the model: available current evidence first for present-location questions; visual completion cites tool observations; mutations require a corresponding user request; unsupported clock-time conditions cannot silently become unconditional reminders. Context is bounded recent conversation, not all past raw turns.
- Begin adaptive selection with local block image differences using existing NumPy/Pillow. Preserve initial, pre-change, changed, settled and periodic samples, along with actual offsets and sampling policy. Continuous files each retain an anchor. Source video remains untouched and the 1 GiB stop-without-deletion rule stands. OpenCV comparison remains an option if measurements warrant another dependency.
- Use fresh bounded live-frame sequences for active departure requests, independently of completed segment indexing. No semantic analysis of every frame, person identification, cloud vision or inference from disappearance alone. The small VLM has measured false positives/misses; keep this an explicitly experimental single-person doorway slice.
- Save next-departure intentions and notification attempts in `intentions.sqlite3`. Keep armed, pending, delivering, delivered, failed, missed, cancelled, interrupted and acknowledged states distinct. Deduplicate retries, expire stale events, prevent late callbacks after cancellation and never silently replay interrupted speech. Recurrence, scheduled reminders and general fact recall remain outside this slice.
- Default configured voice retains Sarvam activated STT/TTS but uses the local agent for decisions. Existing cloud-router code remains a compatibility path for tests/older callers. No new provider requests were made during this session.
- Experiments use synthetic devices and permitted offline/public replay. Public Charades data is evaluation-only under its restrictive license; raw clips/frames/contact sheets stay local and must not become redistributed product/demo assets. Downloads use bounded ranges rather than the entire dataset.

[R8](research/R8-companion-loop.md) records the actual 16 GiB machine, local-model checks and limitations. Running two model processes at once caused swapping; subsequent model tests run sequentially. No milestone accuracy or latency gate is declared met.

Follow-up inline checks preserve unknown-date footage through a separate best-match tool, give fresh event checks priority ahead of queued indexing, and permit one invalid-decision correction within the existing six-step budget. Active requests remain visible beyond recent-history limits. Native timestamped video was compared on the same diagnostic sequences but not promoted: it retained false triggers and missed an exit. The longer recording check exposed hidden older sources after fifty clips; explicit **Show older clips** restores their playback/deletion controls without changing retention.

Completed tool results now finish directly under the existing single-task policy, avoiding an unnecessary generation; uncertain results continue through model decisions. Browser delivery generations invalidate late audio on known cancellation/interruption. Recording-phase results, full lifecycle outcomes and harness failures are recorded separately in R8; no actual-camera or departure-quality gate is closed by them.

### Departure follow-up — 2026-10-20

Following the user's renewed implementation request, keep the existing model and
worker while fixing the event boundary: select the exact three live samples before
inspection, suppress unchanged bursts with the existing local change thresholds, and
require the entire inspected sequence to follow the request. The cheap gate retains
all nine reused public sequences, including their negatives; it does not resolve
direction or intent. No extra dependency/model download is needed.

A reversal-consistency experiment was rejected as a runtime gate: it retains only
one of three exit proxies while still accepting a stationary-doorway case, and adds
another expensive generation. This is diagnostic evidence of weak temporal reasoning,
not a quality improvement. Next recognition work should test explicit exit geometry
and chronological person motion on independently labelled fixed-camera views.

### Temporal window and agent continuation — 2026-10-20

The user approved the temporal window and separate event/action eligibility design,
requested implementation, and explicitly deferred general long-term memory. Inline
engineering choices for this slice:

- Share one elapsed-time `ActivityWindow` between live nomination and automatic
  indexing. Start with 0.5 s persistent change supported by three observations,
  0.8 s quiet to close an episode, and continuity reset after gaps over 0.5 s.
  Live observation targets 10 Hz; saved segments request 0.1 s decoded sampling.
  These settings preserve a lasting placement while rejecting controlled 0.1 s
  returned-to-baseline flashes. They are not household-validated semantic thresholds.
- Preserve full media, existing source policies and per-segment/periodic anchors.
  Nomination retains before/during/settled evidence; actual offsets remain original.
  Keep up to six seconds/64 live frames and inspect three. Consume nominations only
  after job admission; meaningful continued activity may recheck after three seconds.
- Keep an explicit narrow action gate for existing departure requests. Qualified
  activity, model exit cues and an eligible armed request are all required. Persist
  episode identity and decision reason with delivery evidence. This does not make
  a mistaken model judgment true; the dense entry replay still falsely triggers.
- Expanded real-planner checks exposed repeated tools, failed time-window widening,
  current/history routing errors and copied schema placeholders. Keep the custom
  bounded loop: show remaining choices during continuation, reject placeholder
  queries, allow up to two decision repairs inside six steps, and record explicit
  evidence-selection policies. An identical repeated history query advances to an
  unused wider window; a changed query can revisit a window. This is an auditable
  application rule, not a claim of unconstrained model reasoning.
- Conversation text remains in SQLite, with at most twelve completed turns from the
  recent twenty loaded as context. No summarization, fact memory, semantic chat
  recall, framework, new model download or cloud visual fallback is introduced.

[R8](research/R8-companion-loop.md) records the ten-case real-planner development
check, synthetic and public temporal replay, browser checks and remaining false
departure. Revisit thresholds/recognition using independent fixed-camera evidence;
do not mark household or event acceptance complete from these wiring checks.

### Reusable grounded event evidence — 2026-10-20

The user authorized the next recognition slice and required reusable automatic
behavior rather than a scenario-specific workaround. Engineering choices:

- Automatically infer the relevant region from actual images, without a predefined
  doorway position, clip-specific branch or mandatory manual calibration. Abstain
  on an unknown/ambiguous home exit. Retain the one supported next-departure action;
  general conditions and personal memory remain later work.
- Add independent entity localization through the existing optional Torchvision
  dependency: lazy CPU SSDLite320 MobileNet V3 Large COCO_V1, common 0.6 score cutoff.
  No additional framework or quantization. The small detector took roughly 0.1 s
  per three images in the diagnostic run. A measured Faster R-CNN MobileNet V3 FPN
  alternative took roughly 0.9–1.2 s, added ambiguous detections and did not fix
  coverage consistently, so it is not promoted or used as a fallback.
- Keep entity-position change and generic region-relative direction independent of
  semantic cues. Stationary/ambiguous observations skip VLM work. Direction toward
  the inferred exit must corroborate a positive semantic interaction; standing,
  entry and reversal can reject confident semantic mistakes.
- An initial rule also demanded footpoint proximity to the estimated door rectangle.
  Reject that physical-distance interpretation: perspective and imperfect bounds
  make it unsound. Keep proximity as a diagnostic; consistent direction plus separate
  semantic interaction is the action criterion. This change applies to all scenes.
- Preserve the existing timestamp/freshness/request/cancellation boundaries. A small
  model can mislabel a closet as an exterior exit; even multiple evidence sources
  cannot establish guaranteed correctness. Sparse three-image detector misses
  currently lose an exit in live replay. Do not close event or advance-warning gates.

The latest frozen development replay has one action on three staged exit proxies,
zero actions on four negatives and zero on two ambiguous cases. It is reused
development evidence, not independent accuracy. Live entry replay independently
exercises a confident VLM positive rejected by movement away from the door.
[R8](research/R8-companion-loop.md) contains results, failures and rejected alternatives.

### Buffered chronological trajectories — 2026-10-20

The user approved the next tracking slice. Keep the same small detector, Qwen and
single worker. Retain the full six-second context across activity episodes, sample
at roughly 5 Hz (at most 32 images), and permit meaningful changed activity checks
at one-second intervals. Cache detections by timestamp only within the same view.
Bridge at most 0.8 s of missing detections with explicit gaps; never invent a box.
Multiple subjects, longer gaps and implausible jumps split the association. Full
associated motion determines direction; three actual images determine semantic cues.

Compare successive automatically inferred exit bounds within one view (same kind,
IoU at least 0.5). Disagreement blocks that check; initial grounding remains provisional.
These are common geometric policies, without per-clip coordinates or reminder content.
Buffered tracking does not run continuously during the worker's slow VLM generation.

Complete-sequence evaluation is required before claiming recognition improvement.
The nine-clip protocol was frozen before inference, with coarse event brackets and
separate ambiguous/moving-camera cases. Each replay now asserts an armed request in
an isolated conversation: the first attempted shared-conversation run exposed a real
planner failure and cannot count inactive clips as negative passes. Preserve that
conversation weakness as open work. Latest results retain misses, late action and
false indoor grounding; no household accuracy or advance-warning gate is closed.
See [R8](research/R8-companion-loop.md) and the
[tracking plan](superpowers/plans/2026-10-20-continuous-trajectories.md).

### Reject superseded results before notification — 2026-10-20

The latest continuation adds a cheap post-inference guard before a positive result
creates a notification. Reuse the existing ActivityWindow over frames since the exact
last semantic image, within the same camera epoch. Missing retained history, capture
older than 0.5 s, a persistent new change or a still-unsettled change withholds action
and leaves the request armed. A completed brief flash alone may pass. Preserve the
checked-through time separately; do not relabel newer uninspected images as semantic
evidence. This rejects old decisions, without claiming to recognize the new scene.

The six-second buffer is also the maximum available continuity history. An eight-
second generation can therefore be withheld even with a correct positive. This is
an intentional conservative boundary, not a latency improvement or a fix for false
exterior-door labels. Model latency and automatic scene grounding remain open.

### Qwen3.5 2B 8-bit selection — 2026-10-20

The user selected the vision-enabled Qwen3.5-2B MLX 8-bit checkpoint and authorized
one short image inference to verify loading, while keeping video/model benchmarks
paused for memory pressure. Pin revision 562fb8ea19bbe7565a3ddf5b7d49899ea2c88d2b
of `mlx-community/Qwen3.5-2B-8bit`. The config declares qwen3_5 with a vision encoder
and affine 8-bit group-size-64 quantization. Disk weights are about 2.66 GB; this is
not an estimate of peak process or system memory.

Use a small lazy `mlx_runtime.py` generation boundary, preserving ordered text/image
parts and disabling thinking in both chat formatting and generation. All existing
inspection, bounded agent decisions and departure checks share it. Apple Silicon
selects this path by default; other systems retain the older Transformers path.
Explicit `model="qwen"` remains a diagnostic baseline, without automatic fallback
on MLX errors. The `mlx` dependency extra pins mlx-vlm 0.4.1; its Qwen3.5 support
requires Transformers 5, so the locked environment changes as part of this switch.

No broad accuracy claim follows from the synthetic smoke. Existing Qwen3-VL failures
remain the baseline; full new-model evaluation is deferred. The user authorized
removal of obsolete model weights after the replacement loads successfully. Keep
SigLIP retrieval, speech and detector assets; raw recordings are never cache cleanup.

### Conversation repair without model inference — 2026-10-20

The user authorized reminder/conversation reliability work while keeping real-model
inference paused. Validate mutation eligibility during bounded decision validation,
then recheck at the tool boundary. An unauthorized cancellation now returns a decision
repair signal before creating any tool observation or changing a reminder. Two repair
attempts still share the six-decision budget. Prior conversation cannot authorize a
mutation on the current turn.

Cancellation requires a direct supported cancellation request, no negation or embedded
"remind me to cancel" instruction, an exact active ID, and a reminder referent. When
several reminders are active, require one uniquely matched full reminder message or
clarify. Duplicate messages remain ambiguous; UI cancellation by ID remains available.
This conservative text guard is not general language understanding and may clarify
valid paraphrases. Existing request-ID idempotency is unchanged; distinct requests
with identical messages can still create separate reminders.

Planner prompt v9 prioritizes the latest correction, preserves compatible user-given
attributes, and separates prior answers from current evidence. Remaining search
windows/tools are computed per resolved query, rather than globally across different
objects. Query changes can revisit a recent window. Deterministic fixtures validate
context/arguments/repair behavior; actual Qwen understanding remains unmeasured.

### Keep the agent in control — 2026-10-20

The user reaffirmed broad agent control and asked to avoid overengineering. Prefer
existing tools and concise decision context over more workflow branches, stored query
state or new planning infrastructure. The agent owns interpretation, clarification,
tool selection and continuation; application checks enforce authorized mutations,
evidence attribution and lifecycle consistency. Existing routing policies remain
measured workarounds to revisit with model evaluation, not a template for adding more.

This continuation only improves existing reminder controls: readable lifecycle labels,
request timestamps to distinguish repeated messages, and descriptive cancellation
button labels. No new planner, backend state, model call or clarification workflow.

### Focus on two MVP experiences — 2026-10-20

The user accepted focusing on object finding with corrections/history and the
next-departure bottle reminder. Prioritize integrated evidence over new features
or general memory. A bounded real-model object run exposed Transformers 5 pooling
incompatibility, copied visual schema placeholders and a lost spatial correction.
Restore image/text pooling compatibility and reject malformed visual evidence;
retain agent ownership of query interpretation. Visual prompt version is now 2.
Memory pressure stopped the run before history completed; further model runs are
paused for headroom. New-model departure validation and correction reliability
remain open. See R8 for the measured failures and exact limitations.

### Model runs require renewed approval — 2026-10-20

The user authorized continued code/lightweight verification and requested approval
before any further model inference. Do not load models for the next experiment
until that approval arrives. The next proposed run isolates current inspection
and correction, without indexing/history, to reduce concurrent model memory.

The planner's repeated-current-check guard now compares the full action rather
than rejecting all current checks after the first. This aligns enforcement with
query-scoped continuation: the agent may refine a description after an uncertain
result, while the same query remains blocked. The six-step budget is unchanged.
This fixes a separate control-flow defect; it does not establish that Qwen retains
spatial corrections. No extra planner or rule for specific object attributes.

### Clarify ambiguous object requests — 2026-10-20

The user prefers a clarification over an unsupported direct answer. Preserve
visual ambiguity through parsing and current/history tools, stop the search, and
return a brief question. A model-reported match count must be exactly one before
a direct visible-location answer; missing/invalid counts fail uncertain. Counts
are model claims, not independent ground truth. General uncertainty still permits
search; explicit ambiguity asks the user before choosing another candidate.

Planner v12 preserves distinguishing attributes in its instructions and sends
compact prior utterances plus the latest request last. Visual prompt v5 reports
candidates before match count/decision. No regex for object attributes, separate
query model or new agent framework. Real checks show improved ambiguity handling
but repeated clarification on a usable spatial follow-up; see R8. The user
authorized these sequential tests at a 10% watchdog cutoff; all have exited.

### Preserve resolved query context and clarify evidence limits — 2026-10-20

The user authorized continued implementation and sequential model checks. Planner
v17 uses shorter instructions and includes the latest tool query from each saved
turn, without treating it as visual proof. Existing conversation storage is
sufficient; no new memory subsystem. Visual v6 counts candidates after attribute
filtering. Schema errors identify exact extra/missing fields for bounded repair.
An explicit first last-sighting search uses available dated history before
undated matches; unknown-time-only libraries remain supported.

Real tests improved current clarification resolution and preserved corrected
queries into history. They also demonstrated wrong historical item attribution
and missed departure proxies. Keep candidate/identity/temporal evidence distinct;
no identity claim or MVP acceptance follows from successful API jobs. Existing
movement and continuity checks remain intact despite missed detections.

### Dependable guided finding before automatic identity — 2026-10-20

The user prioritized one complete object-finding experience. A local two-image
comparison probe did not support automatic identity matching: raw generations
claimed a lookalike was visible, and all outputs failed the required JSON shape.
Do not add an automatic reference-matching feature on that evidence.

Historical visual hits now have `candidate` status and ask the user to review the
image. They do not repeat a model-inferred location as fact. The user can reject
a candidate and continue within the same query/time/source bounds, or explicitly
confirm the item in a saved frame. Confirmation is attributed to the user, not the
model, and says nothing about current location or a later sighting. The agent
cannot call the confirmation endpoint as a tool. Button confirmation is the MVP
interaction; voice-only confirmation is not implemented.

Use existing recordings and conversation storage: no reference-image cache, new
model, entity database or permanent snapshots. Confirmation request IDs are
idempotent, persist across restart, and conflict on different choices. Deleted
sources invalidate confirmation replay. Rejection exclusions are request-local;
they do not delete footage or establish object identity.


### Conversational feedback belongs to the agent — 2026-10-20

The user explicitly rejected a button-dependent deterministic retry workflow.
Natural-language feedback now goes through the normal agent loop; the rejection
button sends the same conversational request. The planner receives the displayed
candidate's frame reference and past exclusions, then chooses a refined query,
another historical window, another match search, or a clarification. There is no
phrase-matching rejection router. Search tools enforce model-selected exclusions.
This supersedes the fixed query/time/source retry described above. Explicit
confirmation remains a user-attributed UI action; background change detection is
unchanged. Persist only compact references in existing conversation storage.


### Rejected frames must not consume retrieval slots — 2026-10-28

Apply agent-selected exclusions in the existing SQLite search before ordering and
LIMIT, in both the primary and fallback searches. Previously history selected a
bounded result set and only then skipped rejected frames, preventing further
results from being reached after enough rejections. Keep the same per-request
candidate/model-check bounds and source/time filters. No change to the planner's
control over query, time window or rejection, and no automatic deletion.


### Pending review follows actual evidence state — 2026-10-28

Do not search backward past a newer visual tool request or explicit confirmation
to resurrect an older historical candidate as the active review target. A
clarification without another visual query may retain the pending candidate.
An explicitly displayed, server-resolved frame takes precedence. When a successful
browser request has no visual result and hides the result panel, clear its
presented-frame reference. This is evidence lifecycle bookkeeping, not a language
classifier or a new workflow; the agent still chooses queries, tools and exclusions.


## 2026-10-28 — Finish the guided finding MVP

Prioritize one reviewable object-finding experience for the authorized MVP wrap-up.
Keep the bounded local agent and existing tools; do not add another inference
stage or framework after unsuccessful planner probes. Present departure reminders
as experimental, and distinguish explicit user confirmation from model checks.
The demo runbook is [here](mvp-demo.md); broader household/voice acceptance remains
open in milestones. This narrows the demo promise, not the independence mission.

## 2026-10-28 — Preserve measured SigLIP index compatibility

The baseline comparison found identical pixels/tokens/embeddings but different
preprocessing hashes across the locked Transformers upgrade: v5 omitted the
nonfunctional `_processor_class` metadata key. Accept exactly those two measured
hashes for the pinned SigLIP2 model/revision, preserving stored identity/vectors
and all other mismatch checks. Do not silently rebuild or invalidate old libraries.
See R8 for the failed upgrade, measured equivalence, repair and regression checks.
The broader companion branch remains off main pending conversation reliability.

## 2026-10-28 — Time boundaries are distinct from candidate rejection

Expose optional `before_frame_id` on dated history searches. Resolve its actual
saved capture time in the executor and query strictly before it; do not mark the
frame rejected or remove it. Preserve an established bound across the request's
continued/refined visual searches, while allowing repair of a failed anchor lookup.
Unknown capture times remain unknown. This repairs a tool limitation: simply
widening a lookback window can return the same newest moment again.

Retain the selected Qwen3.5-2B 8-bit runtime and original planner format with the
minimal v38 schema addition. Do not adopt the tested prompt rewrites, larger model,
native adapter, review-choice mapping or extra LLM reviewer without better evidence.
They did not resolve the feedback failures consistently; several regressed existing
flows. See R8. Reliable semantic planning and merge readiness remain open.

## 2026-10-28 — Trace activated speech before routing

Activated cloud transcripts are persisted immediately after STT, before cancellation
checks or routing. Later failures leave an interrupted conversation record instead
of dropping the transcript. Local SQLite diagnostics link attempt/turn IDs across
activation, STT, routing, agent/tools, speech generation and browser playback.
Diagnostics retain the latest 2,000 events; that cap does not delete conversation
transcripts. Idle speech text, raw audio/images, credentials/session tokens and raw
provider error bodies are not logged. User requested this after a live statement
was absent from saved history; the original cause is not recoverable retrospectively.
This is observability, not statement-to-visual association or long-term recall.

## 2026-10-29 — Separate cloud ingestion from interaction

Replace the legacy single inference queue with two bounded serial workers: one
for capture/import and one for interactive tools. Cloud I/O no longer requires
local-model serialization. Retain ordered visual verification, no automatic retries,
and existing evidence/cancellation semantics. Use eight-image capture batches and
bounded text embedding reuse; measure provider and queue time before more changes.

## 2026-10-29 — Overlap three ordered visual checks

User requested another latency reduction after the 30-second replay. Retain the
same verification model and prompt; allow three concurrent frame checks with
ordered result consumption and explicit extra-request cost. Discard the multi-image
single-call trial because it did not improve measured latency. Do not replace
uncertainty handling or agent decisions with scenario-specific routing.

## 2026-10-29 — Cheaper cloud models and broader candidate nomination

User requested newer inexpensive models and higher concurrency. Adopt GPT-6 Luna
for planning and Gemini 3.5 Flash-Lite for vision/context after small visual,
planner and actual saved-data checks. Six concurrent single-frame checks, configurable
1–8. Semantic latest-history nomination spreads a 64-frame pool into up to 12
candidates before chronological checking. Preserve embeddings, original files,
1 GiB cap and evidence semantics. No new vector service: local scale scans remain
subsecond at 129,600 synthetic frames. See [R10](research/R10-low-cost-retrieval.md)
for measured limits, prices, storage constraints and unproven multi-day recall.

## 2026-10-29 — Bounded recording compression

User approved the compression MVP and direct work on main. For new browser
recordings, retain requested 1280x720 resolution and VP8-first codec support,
request at most 15 fps and target 1 Mbps rather than 2.5 Mbps. No post-upload
transcoding worker, automatic expiry, deletion or changes to originals. Preserve
continuous segments and the 1 GiB stop policy. See R11 for measured replay limits.
