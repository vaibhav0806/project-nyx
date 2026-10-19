# Technical architecture

Status: working architecture, 2026-10-19. M1 has local clip import/sampling, encoder inference, SQLite retrieval, a CLI and an HTML gallery. A bounded M2 localhost interface adds manual clip recording/import/search and source playback. Continuous capture, verification, cloud voice and actions remain planned. [Decisions](decisions.md) distinguishes established preferences from open selections.

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

## Manual interface implementation

`nyx serve` binds FastAPI/Uvicorn to `127.0.0.1`. `app.py` serves packaged plain browser assets under `src/nyx/web/`, streams uploads into temporary incoming directories with a 256 MiB cap, and gives completed uploads to one inference worker. A task reservation covers upload and inference; extra tasks receive a busy response. The encoder loads lazily once and stays cached. Jobs are session-local status records, not durable workflow state. Library/evidence requests use short SQLite connections without loading the model.

MediaRecorder captures video only after Start and releases camera tracks on stop/navigation. Clips stop at two minutes, camera interruption or tab hiding. Review then Index explicitly transfers the clip to the same laptop server. Camera start time comes from the browser's clock; imports retain unknown capture time. This is short manual capture, not continuous coverage. Media is served by registered video/frame IDs with range responses for source seeking; arbitrary data-directory files are not exposed. Host and mutation-origin checks restrict browser access to the local app.

The M1 crop comparison lives only in the experiment: full-frame plus four overlapping crops, max score per distinct source frame. It did not improve recall@3/@5 on the existing public fixture, so the application retains full-frame indexing. See R3 for the full occurrence-rank results and limits.
