# Technical architecture

Status: working architecture, 2026-10-19. M1 has local clip import/sampling, encoder inference, SQLite retrieval, a CLI and an HTML gallery. The M2 localhost interface adds enabled rolling recording, automatic background indexing, interactive search and separate source playback. Verification, cloud voice and actions remain planned. [Decisions](decisions.md) distinguishes established preferences from open selections.

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
- Start on localhost. No cloud media fallback or automatic capture on process startup.

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

`capture.py` extracts frames and preserves actual selected decoded offsets. `memory.py` uses ordinary SQLite rows plus `sqlite-vec` cosine-distance functions; this is an exact scan with metadata filters, not an ANN index. Its small-corpus performance does not establish large-archive scalability. `retrieval.py` excludes indexing/failed clips and cleans up failed imports. `perception.py` loads a pinned, safetensors-only checkpoint without remote code. `report.py` produces an escaped, self-contained HTML gallery. No live camera or cloud session starts automatically.

## Recording/search implementation

`nyx serve` binds FastAPI/Uvicorn to `127.0.0.1` and serves packaged browser assets from `src/nyx/web/`. MediaRecorder produces independent approximately ten-second video-only files; the next recorder starts on the same camera stream before the previous one stops. Segment boundaries can overlap slightly. Each completed segment uploads automatically with session/sequence identity and browser-clock metadata. Camera access requires explicit Start/Resume. Pause/Stop releases tracks, and source replay uses a separate player.

`recording.py` owns a durable `capture.sqlite3` journal of sessions, segments and interruption events. A stable segment UUID makes duplicate delivery/indexing idempotent. Uploads are staged and atomically renamed into managed recordings, then queued. Original media survives indexing failure; incomplete uploads never become searchable. Startup marks active sessions interrupted, recovers staged files and requeues saved interrupted indexing without opening a camera. Ephemeral job-status polling remains separate from this durable capture journal.

One cached inference worker advances index generators in two-image batches. Searches take priority between batches; current model loading, FFmpeg decoding or inference cannot be preempted. Admission allows at most eight pending capture segments, one manual import and one interactive search. The browser stops capture if saving cannot keep up; a small bounded queue plus the finalizing recorder tail retains pending uploads for retry/download. Browser-exit delivery is best effort.

The 1 GiB budget counts original videos in recordings/incoming, including existing imports. Uploads are bounded by remaining budget, a 256 MiB request limit and a 256 MiB free-disk guard; originals are never automatically deleted. Model cache and derived thumbnails are outside this video budget. Retention/source-aware deletion remain pending.

Coverage displays latest saved and searchable sampled times alongside interruption history; it does not assert continuous observed coverage. Uncertain interrupted segments remain searchable by clip offset with unknown wall-clock time. Imports also retain unknown capture time unless explicitly supplied. Browser/OS suspension can affect actual capture and needs hardware evaluation. Media endpoints expose registered sources with HTTP range support; host/origin checks remain in place. No cloud media fallback is configured.

The M1 crop comparison remains experimental: full-frame plus four overlapping crops did not improve recall@3/@5 on the existing public fixture, so application indexing remains full-frame. See R3 for results and limitations.
