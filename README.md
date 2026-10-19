# Nyx

**Personal intelligence for a longer, independent life.**

We’re building Nyx to help people stay independent as they age: a physical AI companion that sees, listens, and remembers, so they can keep living on their own terms.

Nyx is intended to connect live surroundings, recorded history, conversations, and simple actions through natural speech. The first development target is a laptop demo; older adults are the intended starting audience.

## Project state

**Continuous local recording and background indexing are available; household evaluation remains in progress.**

The camera stays off until explicitly enabled. Completed video-only segments save and index automatically while candidate search and separate source playback remain available. Existing clips remain compatible. The user demonstrated cookie-packet, phone, keys and raised-hand retrieval; this is useful developer evidence, not an independent accuracy benchmark.

A pinned SigLIP 2 encoder runs on this Mac's MPS GPU. Results remain unverified visual candidates. VLM verification, voice, reminders and intended-user evaluation are later milestones. See [measured retrieval results](docs/research/R3-local-retrieval.md) and [continuous indexing implementation](docs/superpowers/plans/2026-10-19-continuous-recording.md).

## Run the local demo

Requires Python 3.12, uv, FFmpeg on PATH, and a browser with MediaRecorder support (Chrome was tested).

```bash
uv sync --python 3.12 --extra vision --extra web
uv run --no-sync nyx --data-dir data/manual-demo serve
```

Open **http://127.0.0.1:8000** and press **Start recording**. Approximately every ten seconds, a completed segment saves and starts indexing automatically. Search can run while the camera stays on; select a candidate to replay its source in a separate player. **Pause recording** releases the camera; **Resume recording** reopens it explicitly. **Stop recording** saves the final segment. **Import video** still indexes a local file without inventing its recording time.

Capture is video-only. The page shows latest saved and searchable sample times separately, a backlog, and pause/interruption history; these timestamps do not guarantee gap-free coverage. Search starts seeing each segment only after indexing completes. The first model load or current decoding/inference batch can delay search; queued search takes priority between small indexing batches.

The saved original-video budget is **1 GiB**, including existing clips. Recording stops on a full backlog, upload failure, quota or low disk space; existing clips are preserved. Thumbnails and the model cache use additional space. Failed uploads stay available for retry/download while the page remains open. A browser exit can lose the unsaved tail. Camera loss or detected suspension stops capture with an interruption warning; merely hiding the tab does not deliberately stop it. Browser/OS recording behavior and clock accuracy still need real hardware testing.

On server restart, saved interrupted work is requeued and live sessions are marked interrupted. A camera never reopens automatically. Interrupted tails retain searchable clip offsets but no asserted wall-clock time. Original media and inference stay on this laptop; the server binds to localhost. `Ctrl+C` stops it; `serve --port 8001` selects another port. Retention policy, source-aware deletion and the thirty-minute real-camera soak remain open M2 work.

## Try the baseline

Requires Python 3.12 (uv can select it), uv, and FFmpeg on PATH.

```bash
uv sync --python 3.12 --extra vision
uv run --no-sync nyx doctor
uv run --no-sync nyx index /absolute/path/to/clip.mp4 --interval 2
uv run --no-sync nyx search "a television remote control" --html data/runs/search.html
uv run --no-sync nyx list
```

Open the printed gallery path in a browser. Frames link to the copied source clip at its sampled offset. Use descriptive search phrases initially. Retrieved candidates do not establish presence, absence, or the latest sighting.

The default `data/` directory is ignored by Git. Put `--data-dir /chosen/directory` before the command to keep independent indexes. An index records the checkpoint/revision/preprocessing identity and refuses incompatible embeddings. `search --start 10 --end 30` filters offsets within clips; `--video-id ID` selects a clip. Capture wall-clock time stays unknown unless you supply an actual timezone-aware `index --recorded-at` value.

The optional vision dependencies and first model use require downloads. Inference is local; clips/images are not sent to a cloud provider. Cached use can be tested with `HF_HUB_OFFLINE=1` before the command. The index/search CLI loads the model on each invocation; warm benchmark query times exclude that startup.

## Checks and experiment

```bash
uv run --no-sync pytest -q
uv run --no-sync ruff check src tests experiments
uv run --no-sync ruff format --check src tests experiments
node --check src/nyx/web/app.js
uv run --no-sync python experiments/image-text-retrieval/run.py \
  --download-samples --output data/runs/siglip-baseline
```

The test suite uses deterministic local fixtures and FFmpeg, with no model download or provider calls. Use `uv sync --python 3.12 --extra web` for the full API suite without model dependencies. Without the web extra, API tests are skipped. The real-model experiment is separate; use a fresh output directory for each run. See [experiment method](experiments/image-text-retrieval/README.md), including the optional crop comparison and household-clip protocol.

An opt-in browser smoke check starts its own temporary localhost server and isolated headless Chrome, using generated camera frames instead of a real webcam. It requires the vision/web extras, installed Chrome and the cached model. Generate the benchmark clip first, then use a fresh output directory:

```bash
HF_HUB_OFFLINE=1 uv run --no-sync python tests/browser_smoke.py \
  --video data/runs/siglip-baseline/scenes.mp4 --output data/runs/web-smoke
```

It checks file import, real-model search, playback offsets, automatic multi-segment indexing, search/replay while recording, pause/resume, denied/interrupted camera behavior, navigation/reload and mobile overflow. It writes screenshots and results under the output directory; this does not validate actual camera hardware or intended-user usability.

## Read these first

| Document | Purpose |
| --- | --- |
| [Design](docs/design.md) | Mission, intended user, experience, and product principles |
| [Scope](docs/scope.md) | Laptop demo, first development slice, and later work |
| [Architecture](docs/architecture.md) | Components, data flow, evidence, and model boundaries |
| [Repository structure](docs/repository.md) | Where code, research, experiments, tests, and data belong |
| [Milestones](docs/milestones.md) | Build order, deliverables, acceptance checks, and status |
| [Research](docs/research/README.md) | Open questions, bounded assignments, and findings format |
| [Decisions](docs/decisions.md) | Established direction, proposals, and unresolved choices |
| [Agent instructions](AGENTS.md) | Rules for agents working in this repository |

## Proposed technical direction

- Python backend and local recording/storage.
- A small image/text encoder for background visual retrieval.
- SQLite records and vector search linked to original evidence.
- A vision-language model to inspect current frames or verify retrieved candidates on demand.
- Cloud voice connected to narrow backend tools.
- JEPA as a separate experiment in temporal features, event selection, and prediction.

SigLIP 2 through PyTorch/Transformers is the initial measured baseline, not a final production model choice. FastAPI with packaged plain HTML/CSS/JavaScript powers the recording/search interface. Other runtimes and sampling policies remain subject to experiments and review. See [Decisions](docs/decisions.md).

## Development and research

Use [Milestones](docs/milestones.md) for project progress. Use [Research](docs/research/README.md) to assign questions and record evidence. Runnable experiments live in `experiments/`; reusable application behavior lives in `src/nyx/`.

Raw video, audio, model weights, personal interview notes, and databases stay outside Git. Commit anonymized findings and small permitted fixtures.
