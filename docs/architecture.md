# Technical architecture

Status: working architecture, 2026-10-19. M1 has local clip import/sampling, encoder inference, SQLite retrieval, a CLI and an HTML gallery. The M2 localhost interface adds enabled rolling recording, automatic background indexing, interactive search and separate source playback. M3 now adds bounded temporal retrieval and local model checking; M4 adds local wake listening with Sarvam activated-question voice; a bounded companion/event-request slice was added on 2026-10-20. [Decisions](decisions.md) distinguishes established preferences from open selections.

## Shape of the system

One Python application owns capture, persistence, retrieval, tool execution, and reminders. A small browser interface owns interaction and evidence playback. Model inference runs outside the API request/event loop so recording and controls remain responsive.

```text
Camera / imported video
  -> timestamped recording files
  -> selected frames or clips
  -> small visual encoder
  -> SQLite vectors + source metadata

Question -> backend tool -> current frame OR historical candidates
  -> on-demand visual inspection / verification
  -> evidence-backed result -> cloud voice -> person

Assistant conversation / explicit remembered fact / reminder
  -> attributed SQLite records -> retrieval / scheduling
```

Start with in-process queues and a single controlled inference worker. Add process separation only where actual blocking behavior or reliability requires it. No message broker or distributed service topology is needed for the laptop demo.

## Responsibilities

| Component | Owns | Boundary |
| --- | --- | --- |
| Capture | Recording segments, current frames, scene/view identity, actual capture times and gaps | It does not decide what a scene means. |
| Perception | Image/text embeddings and on-demand frame/clip inspection | Outputs include model/version and uncertainty; inference failures remain failures. |
| Retrieval | Query encoding, filters, candidate ranking, source lookup, and verified-sighting selection | Candidate similarity is not a probability or proof. |
| Memory | SQLite records, vectors, transcripts, notes, source links, retention and deletion | Storage does not supply interpretation or establish evidence truth. |
| Voice | Cloud session, audio turn state, interruption, transcript and tool-result exchange | Permanent credentials stay backend-side; tools own durable facts and actions. |
| Actions | Reminder scheduling and note operations | State persists; retries do not create duplicate actions. |
| Browser UI | Conversation controls, setup, status, search results, playback and memory controls | It presents verified findings and candidates distinctly. |

## Model choices and runtime

The baseline candidate is a small image/text encoder such as CLIP or SigLIP. Both sides of a similarity query must use compatible representations from the same checkpoint/preprocessing scheme. Store model ID, revision, dimensionality, and preprocessing identity; never mix incompatible vectors in one searchable index.

Use a VLM on demand to inspect a current scene or verify retrieved candidate moments. Compare small local candidates before selecting a checkpoint. MLX-VLM is an optional inference library for supported Apple Silicon VLMs; PyTorch/Transformers is another path. The application should isolate the calls it actually needs without building a general provider framework.

JEPA produces visual representations and supports research into temporal features/prediction. Text search over its representations requires an additional alignment or retrieval mechanism. Test its contribution against a simple baseline before adding it to the application. LeRobot may become relevant to future robot hardware/control work; it is not a dependency of this laptop memory demo.

Current local hardware was observed as an M4 Pro with 24 GB unified memory. This establishes the test machine, not inference throughput or usable memory under load. The pinned SigLIP 2 baseline has run on MPS; see [R3 findings](research/R3-local-retrieval.md) for measurements and limitations. Python 3.12 and uv now define the baseline environment; optional vision dependencies are separated from the deterministic test setup.

## Retrieval flow

1. Record media or import a clip; preserve known capture metadata and unknowns.
2. Sample periodically and/or after useful visual changes. Record the sampling policy and coverage.
3. Embed frames and store vectors with segment, scene, capture time, clip offset, and thumbnail references.
4. Encode a descriptive query using the matching text encoder; apply requested time/scene filters and retrieve candidates.
5. Inspect original frames or denser clip samples when a verified answer is needed. Whole-frame embeddings may miss small objects; benchmark crops or another retrieval path if necessary.
6. Return grounded findings linked to evidence. A last-seen answer uses the latest verified sighting within searched coverage; top similarity alone cannot establish it.

Temporal questions such as “last,” “before,” or “this afternoon” require explicit time handling. Broad household questions may need query interpretation in addition to visual embeddings. Validate these separately from simple descriptive retrieval.

## Data contract

| Record | Essential information |
| --- | --- |
| Recording | ID, source/camera, scene ID, path, known capture start/end, import time, coverage/status |
| Frame / clip | Source recording, exact offset or interval, actual capture time when known, preview reference |
| Embedding | Evidence ID, model ID/revision, preprocessing identity, dimension, vector |
| Finding | Source evidence, grounded description, verification state/method, uncertainty |
| Utterance | Session, speaker, transcript, occurred-at time |
| Saved fact | User-attributed content, created-at time, source, correction/supersession history |
| Reminder | Original request, resolved time/timezone, request ID, state, delivery and acknowledgement timestamps |

Use SQLite plus `sqlite-vec` as the proposed baseline. Ordinary SQL handles timestamps, sources, facts, and action state. Full-text search can handle transcript/note retrieval initially; add text embeddings when evaluation shows a need. A memory framework such as Mem0 remains optional.

## Runtime behavior

- Capture and recording controls stay responsive during model work.
- Bound inference queues; coalesce obsolete background jobs and prioritize interactive work. Priority does not preempt a GPU operation already in flight, so background work also needs bounded inputs.
- Never let a late analysis result overwrite newer current evidence.
- Keep history append-only where appropriate; saved-fact corrections retain attribution and supersession.
- A capture gap and an indexing gap are different states. Report both when they affect an answer.
- Retention/deletion removes source-linked derived data. Pending actions and explicitly saved facts have their own lifecycle.
- Start on localhost. No cloud visual fallback. A configured page starts camera/microphone automatically after browser permissions; backend process startup alone opens no devices.

## Baseline experiments

Record exact versions and results using [Research](research/README.md):

- Aligned encoder retrieval on real small-object scenes: recall@k, latency, memory and misses.
- Candidate VLM verification: correct/incorrect/uncertain findings on identical candidate images.
- Motion baseline versus JEPA features: meaningful-event recall, false triggers, latency, and compatibility on this Mac.
- Voice provider: target-language comprehension, interruptions, echo, tool latency, and measured usage.

## Starting references

These are source pointers, not endorsed performance results. Recheck exact versions at experiment time.

- [CLIP](https://github.com/openai/CLIP)
- [SigLIP 2 model](https://huggingface.co/google/siglip2-base-patch16-224)
- [Meta V-JEPA repository](https://github.com/facebookresearch/vjepa2)
- [MLX-VLM](https://github.com/Blaizzy/mlx-vlm)
- [sqlite-vec](https://github.com/asg017/sqlite-vec)
- [Mem0](https://github.com/mem0ai/mem0)

## M1 implementation notes

`capture.py` extracts frames and preserves actual selected decoded offsets. `memory.py` uses ordinary SQLite rows plus `sqlite-vec` cosine-distance functions; this is an exact scan with metadata filters, not an ANN index. Its small-corpus performance does not establish large-archive scalability. `retrieval.py` excludes indexing/failed clips and cleans up failed imports. `perception.py` loads a pinned, safetensors-only checkpoint without remote code. `report.py` produces an escaped, self-contained HTML gallery. The backend alone opens no hardware; the configured browser startup behavior is described below.

## Recording/search implementation

`nyx serve` binds FastAPI/Uvicorn to `127.0.0.1` and serves packaged browser assets from `src/nyx/web/`. MediaRecorder produces independent approximately ten-second video-only files; the next recorder starts on the same camera stream before the previous one stops. Segment boundaries can overlap slightly. Each completed segment uploads automatically with session/sequence identity and browser-clock metadata. Without Sarvam configuration, camera access requires Start/Resume. With voice configured, the page automatically requests camera/microphone access on load. Pause/Stop releases tracks, and source replay uses a separate player.

`recording.py` owns a durable `capture.sqlite3` journal of sessions, segments and interruption events. A stable segment UUID makes duplicate delivery/indexing idempotent. Uploads are staged and atomically renamed into managed recordings, then queued. Original media survives indexing failure; incomplete uploads never become searchable. Startup marks active sessions interrupted, recovers staged files and requeues saved interrupted indexing without opening a camera. Ephemeral job-status polling remains separate from this durable capture journal.

One cached inference worker advances index generators in two-image batches. Searches take priority between batches; current model loading, FFmpeg decoding or inference cannot be preempted. Admission allows at most eight pending capture segments, one manual import and one interactive search. The browser stops capture if saving cannot keep up; a small bounded queue plus the finalizing recorder tail retains pending uploads for retry/download. Browser-exit delivery is best effort.

The 1 GiB budget counts original videos in recordings/incoming, including existing imports. Uploads are bounded by remaining budget, a 256 MiB request limit and a 256 MiB free-disk guard; originals are never automatically deleted. Model cache and derived thumbnails are outside this video budget. Manual source-aware deletion is available; automatic expiry and retention duration remain undecided.

Coverage displays latest saved and searchable sampled times alongside interruption history; it does not assert continuous observed coverage. Uncertain interrupted segments remain searchable by clip offset with unknown wall-clock time. Imports also retain unknown capture time unless explicitly supplied. Browser/OS suspension can affect actual capture and needs hardware evaluation. Media endpoints expose registered sources with HTTP range support; host/origin checks remain in place. No cloud media fallback is configured.

The M1 crop comparison remains experimental: full-frame plus four overlapping crops did not improve recall@3/@5 on the existing public fixture, so application indexing remains full-frame. See R3 for results and limitations.

## Source deletion

`DELETE /api/videos/{id}` requires capture stopped and no active upload/inference work. Deletion records a durable intent in `capture.sqlite3`, marks source evidence unavailable, removes the managed original/frame directory, removes frame/vector and video rows, then completes the tombstone. A captured source retains its stable ID as deleted so duplicate segment uploads cannot recreate it. Tombstones retain only the source ID/path/state; capture-session timing/history metadata remains. This is application-level removal, not secure erasure of filesystem/database free pages or already downloaded copies.

Pending deletions retry before startup can requeue capture work. Persistent filesystem failures leave evidence hidden and the app available for retry. Source and thumbnail-directory paths are checked against managed locations before removal. Frame IDs increase across deletion, including indexes created by the earlier version, so stale thumbnail URLs cannot point to newly indexed evidence. The browser requests confirmation, clears candidate/replay/filter state on success and refreshes storage/coverage. There is no scheduled expiry.

## M3 temporal answers

`memory.py` computes observation time from known capture start plus decoded offset using a deterministic SQLite function that returns normalized UTC timestamps. This avoids floating Julian-day boundary errors. Relevance search preserves existing offset filters; date filters and latest ordering exclude unknown clock times. `answers.py` scans twelve newest dated samples first and can fall back to five semantic candidates, deduplicated and ordered by time. It stops at a model-positive observation and reports the limited checked scope. Nearby samples within four seconds of the chosen source are unverified context, constrained by the same explicit time bounds. No exhaustive last-sighting, object persistence or identity claim follows from this bounded retrieval.

`verification.py` loads pinned Qwen3-VL-2B through native Transformers on demand, safetensors only and without remote code. Original source frames are decoded at their offsets, resized to a bounded image input and checked with a strict visible/not-visible/uncertain contract. Invalid output or model-reported ambiguity stays uncertain. Findings include judgment, model/prompt identity and evidence links; the candidate's original similarity is not a presence probability. See R4 for the comparison-only Smol candidate and measurement limitations.

`POST /api/answer` runs history checks on the existing worker; `POST /api/inspect` accepts an explicit fresh snapshot, bounded to 2 MiB and two megapixels. Capture time must be aware and fresh at admission, worker start and after model loading. The response includes exact snapshot bytes, time and age in the bounded ephemeral job result; no permanent snapshot archive is created. Model work may make the view stale by response time, so answers describe the captured moment rather than guaranteeing current location. History jobs referencing deleted sources are invalidated; browser deletion clears answer/replay state.

The worker admits one visual-answer job (history or snapshot) and one search, yielding between inspected images. Current generation/load/decode cannot be preempted. M3 keeps the existing encoder/index intact and does not introduce a provider registry, cloud media path, extra memory model or JEPA dependency.

## M4 hands-free voice

`voice.py` owns the Sarvam adapter, local wake recognizer, exclusive microphone session and SQLite conversation records. `voice.js` and `audio-worklet.js` own 16 kHz mono microphone input, energy/silence segmentation, startup, mute and playback. A separate microphone stream prevents ambient audio from entering recorded videos. Automatic startup is the product behavior, including future hardware; synthetic-only inputs are the testing rule.

A local session accepts at most 25 seconds of PCM per request, one speech task at a time. Browser input stops at 24 seconds; only one bounded utterance is in flight. Idle utterances go to pinned faster-whisper tiny.en CPU/int8 on a request worker, independent of the GPU queue. Only name-prefixed speech or the next utterance within a ten-second activation window reaches Sarvam. Name-only activation has a local acknowledgement tone. The microphone session has a thirty-second lease refreshed by heartbeats; multiple tabs cannot hold it concurrently.

Sarvam `saaras:v4` transcribes activated audio; `sarvam-105b` with reasoning disabled selects a validated chat/current/latest/relevance/clarify plan; common greetings have a local text fast path after activated STT. Recent question/object context and brief nonvisual chat replies support conversation; earlier visual claims are not supplied as fresh facts. Bounds must be aware ISO dates. The browser calls the existing visual tool and the reply endpoint checks the authoritative completed job, object, time bounds, mode and turn age. A fixed clarification or the tool's answer, with locally formatted timestamps, goes to `bulbul:v4-flash` speech synthesis with `shubh_enhi_companion`. No image/video goes to Sarvam. Credentials stay backend-side.

Cancellation invalidates generations and prevents subsequent cloud steps, late UI updates and playback; an already-running request/inference is not preempted. During processing, the browser retains one bounded subsequent utterance. During playback it performs local wake checks and can interrupt on a recognized name. Real speaker echo and robustness still need validation; this is not unrestricted full-duplex speech. Completion of playback opens an explicit ten-second active follow-up window. Text/plan/answer/source IDs persist in `conversations.sqlite3`; pending turns become interrupted on restart. Source deletion marks dependent conversation references unavailable, and transcript text stays visibly distinct from evidence. Complete means produced, not delivery acknowledged. Raw mic audio and response audio remain ephemeral. See [R6](research/R6-handsfree-voice.md) for measured behavior and limits.

M4 feedback follow-up: the fixed browser speech threshold was replaced by a lower adaptive floor, a 350 ms pre-roll and a 550 ms end silence. The audio worklet batches 20 ms chunks. At most one local wake probe is in flight, using a 2.5-second rolling speech window; completed turns wait for that probe and recheck the final utterance so a name-only call stays local. The server uses the same bounded inference gates and microphone lease. A configured startup queues a low-priority visual-model preload; no camera/microphone is opened by model warming. Reply audio is held in a bounded 16-entry per-provider RAM cache, never an ambient-audio archive. The UI shows microphone level and response timing; first-audio timing includes the silence wait and any pending-turn delay.


## Companion and live-event implementation

`agent.py` runs at most six validated observe/act decisions, with a between-call time limit, repeated-action prevention and cancellation. Qwen's text-only path chooses tools and reconstructs descriptive queries from a bounded recent conversation. Available input state and compact tool observations inform subsequent steps. Visual completion selects authoritative tool results; it cannot replace them with generated visual prose. An explicit policy checks an available fresh view first for present-location questions. Temporal retrieval selects semantic candidates inside a bounded dated window and checks them newest-first; it remains incomplete sampling, with unknown capture dates excluded.

The separate `search_matches` tool checks semantically ranked candidates including unknown recording dates. Its answer identifies a matching moment and preserves unknown time; it cannot establish the latest sighting. Planner input distinguishes dated and undated source availability.

An invalid decision, including a completion referencing no current-turn observation,
can receive up to two correction attempts inside the existing six-decision limit.
Repeated invalid output returns uncertainty. An identical repeated history action
advances to the next unused wider window for that query (2/24/168 hours, then all
dated history); a changed query can revisit a window. Explicit last-sighting and
current “still there” requests receive the matching historical/current tool policy.
Camera-unavailable requests can use available history. Adjustments and correction
reasons persist with the actual tool trace; these policies do not create evidence.
A completed authoritative final tool result is returned even if it consumes the
last permitted decision. Remaining-tool guidance is supplied during continuation;
schema placeholders cannot become a resolved object query.

For the current single-task workflows, a completed tool result selects its authoritative observation directly, without another language-model generation. Uncertain results still require an agent decision about the next useful search. This preserves evidence checks while avoiding a redundant completion call.

`attention.py` compares inexpensive grayscale local blocks. `activity.py` owns shared
elapsed-time nomination: persistent reference-relative change needs three samples
and 0.5 s support; 0.8 s adjacent-frame quiet settles an episode; a gap over 0.5 s
resets continuity. Isolated changes returning to the reference are discarded. The
thresholds are initial engineering settings, not learned semantic importance.

Continuous indexing requests decoded observations at `min(interval, 0.1)` seconds,
then selects before/during/settled/periodic frames and removes skipped thumbnails
before embedding. Existing `interval_seconds` retains the requested nominal index
interval for retry compatibility; the source's `sampling_policy` records its actual
dense scan policy and frame rows retain actual decoded offsets. Source frame rates
can supply fewer observations. Independent segments and discontinuities retain
anchors; anchor/periodic frames can still include brief activity. Manual periodic
imports and existing ready sources retain their policies. Original media,
retention/deletion and encoder compatibility are unchanged.

`observation.py` owns an ephemeral session-bound buffer of at most 64 images bounded
to six seconds (each at most 640×360). The browser targets 100 ms observations while
a departure request is armed. Session/sample gaps invalidate the epoch. The shared
window nominates a qualified episode before settling; first/middle/last selection
keeps exact image/time attribution. Meaningful continued activity can be rechecked
after one second. `Observer.accept` consumes a nomination only after job admission;
an unaccepted recent nomination survives a busy worker, with an eight-second expiry.
This is independent of saved segment indexing and cannot preempt running inference.

`departure_action` separates temporal nomination, fallible interpretation and request
eligibility. It requires qualified activity, explicit departure/approach/interaction
flags without uncertainty, an automatically inferred exterior exit region, and
independent observed movement toward that region. It selects armed requests created no later than the
first inspected sample. The durable claim boundary rechecks state using only those
request IDs. Episode ID, timing, model judgment and action reason accompany delivery
evidence; the UI exposes phase and decision. No general-purpose event importance
model, permanent live-frame archive or cloud media path is introduced. A consistently
wrong set of observations can still produce a false reminder; R8 records earlier
entering failures and the subsequent direction rejection.

`events.py` contains reusable image-plane evidence, without reminder contents or
room coordinates. A lazy Torchvision SSDLite320 MobileNet V3 Large COCO_V1 detector
runs on CPU over a roughly 5 Hz sample of the entire retained six-second window
(at most 32 images), including context before the latest activity episode. Scores
below 0.6 are excluded. Timestamped detections are reused only within the same
camera session/epoch. One unambiguous entity is associated through actual observations;
misses up to 0.8 s remain explicit gaps, without interpolation. Longer gaps, multiple
entities and implausible position jumps start a new trajectory. Association is a
fallible image-plane continuity rule, not identity recognition. Maximum bottom-center displacement below 0.08
of normalized image coordinates skips semantic inference. This is position change,
not a test for all body/hand motion.

Qwen departure prompt v4 returns semantic cues plus a stable, image-grounded region
on a 0..1000 coordinate scale. Strict parsing normalizes it to 0..1; uncertain or
invalid regions cannot authorize action. `region_motion` calculates bottom-center
distance to that rectangle. Both toward and near-approach relations can corroborate
separate semantic interaction; receding, reversal and stationary evidence cannot.
Distance contraction needs 0.08; a 0.03 tolerance detects conflicting direction;
0.06 labels image-plane proximity only. These global starting policies do not
measure 3D distance or intent. The action gate recomputes motion from detector boxes;
the VLM cannot supply its own passing motion result. Direction uses every associated
observation, so an intermediate cumulative reversal cannot be hidden by the three
semantic images. The first/middle/last actual associated observations go to Qwen;
their exact times are retained separately as `semantic_frame_times`. CPU-only
abstentions have no semantic image times. Boxes, detector fingerprint,
region, exact inspected times, relation and rejection reason accompany evidence.
Successive inferred regions in one camera epoch need matching kinds and at least
0.5 overlap IoU to count as consistent. A changed/unknown region blocks the current
action; an initial estimate is provisional and can still qualify with other evidence.
This checks consistency, not exterior-door truth. Region history resets across views.
No scene calibration UI, automatic identity, model provider registry or arbitrary-
condition action engine is added. Buffered detection and VLM work share the existing
worker: this is not uninterrupted CPU tracking during a long semantic generation. Detector misses and weak
region inference still limit recognition; an exterior label remains fallible.

`intentions.py` owns durable next-departure requests and separate notification attempts in `intentions.sqlite3`. Atomic claims prevent concurrent replay. Expired unclaimed attempts become missed; lost or restarted playback remains interrupted. User acknowledgement is separate. An armed request survives restart, but an old detected event is not fresh evidence after restart. No cron job establishes departure and no general action registry is added.

Sequence evidence must have ordered aware times ending at the event time. Its first
frame, rather than only its last, must follow each eligible request's creation. A
sequence straddling a new request can serve an older armed request while leaving the
new one armed for subsequent evidence.

`companion.py` owns the API/tool integration and `web/companion.js` shares existing camera/voice controls. Typed and default voice requests use the same local loop; configured Sarvam supplies activated STT and reply/reminder TTS. UI evidence links and conversations keep their existing source-deletion rules. Interactive work, background indexing and event inspection share a single model worker. Fresh event checks receive interactive priority ahead of queued background indexing; running inference is not preempted, so stale event checks can still be missed. See [R8](research/R8-companion-loop.md) for resources, actual checks and failures.
