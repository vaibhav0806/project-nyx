# Nyx

**Personal intelligence for a longer, independent life.**

We’re building Nyx to help people stay independent as they age: a physical AI companion that sees, listens, and remembers, so they can keep living on their own terms.

Nyx is intended to connect live surroundings, recorded history, conversations, and simple actions through natural speech. The first development target is a laptop demo; older adults are the intended starting audience.

For a product-level explanation and a map of the working components, read [how the companion works](docs/companion-walkthrough.md).

## Project state

**A local conversational agent now connects current inspection, recent visual history and experimental departure reminders. Continuous recording and hands-free voice remain available; household, event and voice evaluation are still in progress.**

With Sarvam configured, the page starts camera recording and microphone wake listening automatically after browser permission. Without voice configuration, camera startup stays manual. Completed video-only segments save and index automatically while candidate search and separate source playback remain available. Existing clips remain compatible. The user demonstrated cookie-packet, phone, keys and raised-hand retrieval; this is useful developer evidence, not an independent accuracy benchmark.

A pinned SigLIP 2 encoder runs on this Mac's MPS GPU. Search results remain unverified visual candidates. M3 adds local model checks with source/time attribution and explicitly captured snapshots; these checks can be wrong. Scheduled reminders, general personal recall and intended-user evaluation remain later work; see [companion/event findings](docs/research/R8-companion-loop.md). See [measured retrieval results](docs/research/R3-local-retrieval.md), [continuous indexing implementation](docs/superpowers/plans/2026-10-19-continuous-recording.md) and [local verification findings](docs/research/R4-local-verification.md).

## Run the local demo

The **Talk to Nyx** field works without an API key. Ask “Where are my reading glasses?”, refine the description, or ask “Where did you last see them?” The local agent chooses tools over a bounded conversation and tool-result loop. Present-location requests inspect an available fresh view first; historical tools can search recent dated windows before widening. Imported clips with unknown dates can be checked as best matches, without claiming a latest sighting. Answers retain current/historical attribution. The details show what was checked. Stop cancels subsequent steps; in-flight inference can finish. Direct candidate search and explicit visual checks remain available below.

This is a small custom Python loop, without LangChain. It uses recent conversation
to construct descriptive queries and feeds tool observations back into the local
model. An identical repeated historical search advances to an untried wider window;
those policy adjustments persist with the trace. Conversation text is durable, but
only bounded recent context reaches the model; general long-term personal memory is
not implemented. [R8](docs/research/R8-companion-loop.md) separates real planner/query
checks with controlled tools from earlier integrated retrieval trials.

“Remind me to take my water bottle when I leave” saves a **next-departure** request. With recording running and the main door visible, a separate live observer checks local changes and selected short image sequences without waiting for saved-segment indexing. The reminder list shows actual state; Cancel removes an active request and **Got it** acknowledges played speech. Requests survive restart, but old events are not silently replayed. Spoken delivery requires Sarvam configuration and browser playback permission; display-only output is not counted as speech.

Cheap live observation targets ten samples per second. A short activity window ignores
isolated disturbances returning to the original scene, while lasting changes or
sustained activity can nominate inspection after 0.5 seconds. Activity groups into
episodes and settles after 0.8 seconds of quiet; sample gaps reset continuity. These
are prototype thresholds, not household-validated settings. The action gate separately
checks the model's exit cues against an active request. The whole checked sequence
must follow the request, and evidence names the three images actually inspected.

Nominated sequences now pass a separate small CPU object detector over up to six
seconds of buffered observations, sampled at roughly 5 Hz. A short missed detection
remains an explicit gap; long gaps, multiple subjects and position jumps reset the
trajectory. A single subject must have supported position change before three
actual observed images go to the VLM. Qwen attempts to locate
the exit from the actual images; region-relative geometry must corroborate approach
before a reminder can act. Entry, standing and turnback evidence can reject a
confident semantic departure claim. Door position and reminder contents are not
predefined. These reusable evidence components currently feed only the supported
next-departure action; they do not establish arbitrary automatic event understanding.
Successive exit estimates are checked for consistency within a camera session.
Detector misses, uncertain exit grounding and slow inference still cause missed events.
Full-sequence replay caught one of three staged exit proxies, with a late notification,
and produced one false action on indoor activity. Useful advance warning remains unproven. A post-inference continuity guard now
withholds positive results if capture goes stale, the checked image leaves the
retained window, or the scene changes during generation; this can also suppress
correct but slow results.

**Departure recognition is experimental and currently unreliable.** Public-video diagnostics found misses, false positives and delay. This is a single-person doorway prototype, without identity recognition or a guarantee of speaking before departure. Timed/recurring reminders and arbitrary event triggers are unsupported. A running browser page is required for live observation. [R8](docs/research/R8-companion-loop.md) records actual successes and failures.

On Apple Silicon, the selected model is now Qwen3.5-2B in MLX 8-bit format, shared
by visual checks and text decisions. First use loads/downloads its pinned checkpoint.
This replaces the earlier BF16 Qwen3-VL path; historical results below remain results
of that older model. Recognition quality with the new checkpoint is not yet measured. This checkout's measured machine has 16 GiB memory, unlike the earlier 24 GiB benchmark machine. Run model experiments sequentially and preserve disk headroom.

Requires Python 3.12, uv, FFmpeg on PATH, and a browser with MediaRecorder support (Chrome was tested).

```bash
uv sync --python 3.12 --managed-python --extra vision --extra mlx --extra web
uv run --no-sync nyx --data-dir data/manual-demo serve
```

Open **http://127.0.0.1:8000** and press **Start recording**. Approximately every ten seconds, a completed segment saves and starts indexing automatically. Search can run while the camera stays on; select a candidate to replay its source in a separate player. **Pause recording** releases the camera; **Resume recording** reopens it explicitly. **Stop recording** saves the final segment. **Import video** still indexes a local file without inventing its recording time.

Capture is video-only. Continuous segments decode cheap observations at a requested 0.1-second interval and apply the same temporal window before embedding selected before/during/settled/periodic frames. Each independent segment retains an anchor; source frame rates and gaps limit temporal filtering, and anchor/periodic samples can still include a brief disturbance. Fewer similar samples do not establish unchanged object presence. Original video still saves in full; manual imports and CLI indexing keep periodic sampling. Existing indexed sources retain their original sampling policy. The page shows latest saved and searchable sample times separately, a backlog, and pause/interruption history; these timestamps do not guarantee gap-free coverage. Search starts seeing each segment only after indexing completes. The first model load or current decoding/inference batch can delay search; queued search takes priority between small indexing batches.

The saved original-video budget is **1 GiB**, including existing clips. Recording stops on a full backlog, upload failure, quota or low disk space; existing clips are preserved. Thumbnails and the model cache use additional space. Failed uploads stay available for retry/download while the page remains open. A browser exit can lose the unsaved tail. Camera loss or detected suspension stops capture with an interruption warning; merely hiding the tab does not deliberately stop it. Browser/OS recording behavior and clock accuracy still need real hardware testing.

On server restart, saved interrupted work is requeued and live sessions are marked interrupted. The backend alone never opens hardware. A configured voice page starts a new capture/listening session when loaded; the old interrupted session remains in history. Interrupted tails retain searchable clip offsets but no asserted wall-clock time. Original media and inference stay on this laptop; the server binds to localhost. `Ctrl+C` stops it; `serve --port 8001` selects another port. Stop recording and wait for indexing/search to finish to use **Delete clip** beside a source. Confirmation removes its original video, thumbnails and search vectors; unrelated clips remain. Interrupted cleanup stays hidden and can be retried or finished on restart. Nothing expires automatically. Retention duration and the thirty-minute real-camera soak remain open M2 work.

The saved library initially shows fifty sources. **Show older clips** reveals additional sources for playback or explicit deletion; older clips remain searchable throughout.

## Hands-free voice

The intended product starts with the app or future device and wakes when called, like Alexa or Siri. There is no push-to-talk. Activated STT and response TTS use Sarvam; tool decisions now use the same local agent as typed requests. The browser demo requests camera and microphone permissions on page load when Sarvam is configured. Browser/OS permissions and audio autoplay rules still apply; **Enable listening** recovers a blocked audio context or denied startup.

```bash
uv sync --python 3.12 --managed-python --extra vision --extra mlx --extra web --extra voice
uv run --no-sync python -c 'from huggingface_hub import snapshot_download; snapshot_download("Systran/faster-whisper-tiny.en", revision="0d3d19a32d3338f10357c0889762bd8d64bbdeba", allow_patterns=["config.json", "model.bin", "tokenizer.json", "vocabulary.txt"])'
uv run --env-file .env --no-sync nyx --data-dir data/manual-demo serve
```

Set your `SARVAM_API_KEY` in ignored `.env` (permissions `0600`). Never commit it. Open the page, allow permissions, and say **“Hey Nyx, where are my glasses?”** or **“Nyx”**, wait for the short tone, then ask within ten seconds. After an answer, a ten-second active follow-up window lets you ask **“Where did you last see them?”** without repeating the name. After that, say “Hey Nyx” again. The listening indicator shows the active window. Current-view and history tools remain local. Speech replies are English in this first slice; ambiguous dates or unsupported actions trigger clarification.

Current Sarvam models are **Saaras v4 (`saaras:v4`)** for transcription and **Bulbul v4 Flash (`bulbul:v4-flash`)** with `shubh_enhi_companion` for speech.

A pinned **faster-whisper tiny.en** recognizer runs locally on CPU/int8, with local wake probes during speech and completed turns after about 0.55 seconds of silence. This is experimental ASR-based wake recognition, not a custom keyword detector; it can miss the name or activate incorrectly. It accepts Nyx/Nix/Nicks at the start, plus “Hey Nick” as a restricted pronunciation alias; a bare “Nick” or “next” does not activate it. Questions are limited to 24 seconds in the browser. The browser sends microphone samples only to localhost; idle speech is discarded after local checking. Sarvam receives audio only after activation, including speech during the ten-second active follow-up window (and the wake name if spoken in the same utterance), and answer/reminder text for speech. Default agent tool decisions are local. No room-audio archive is created; video segments remain video-only.

**Mute microphone** releases audio tracks while recording continues. **Stop recording** stops the microphone too. **Stop response** discards pending callbacks/audio; in-flight local inference or provider requests may finish. Local wake checks remain available during playback; saying “Hey Nyx” can stop the current response. This has synthetic verification only; actual speaker echo still needs testing. During processing, one bounded utterance is retained rather than silently discarded; in-flight inference is not preempted. Transcripts, tool context, produced answers and source IDs persist in `conversations.sqlite3`; this is conversation history, not visual evidence. Deleting a source marks dependent transcripts as source-unavailable. “Complete” means an answer was produced, not confirmed heard. Transcripts currently remain until manually managed; there is no conversation-deletion UI yet.

[Voice findings](docs/research/R6-handsfree-voice.md) separate provider checks, synthetic browser checks and untested room behavior. The original cold integrated check took about 21 seconds including VLM startup. Voice-configured startup now preloads the visual checker; simple greetings bypass it entirely, and spoken answers are brief while the detailed evidence remains on screen. **Response timing** separates wake/STT/intent/visual/TTS and end-of-speech-to-playback measurements. The M4 p95 target is not met or evaluated statistically. Real pronunciation/noise, echo, repeated wake calls and target-language trials remain open.

## Check visual evidence

Under **Ask about an object**, enter a description such as “black glasses.” Select **Latest sighting** or **Best matching moments**, optionally expand **Limit history by time**, then press **Check history**. It uses the clip selected above; date inputs use this laptop’s timezone. Evidence links replay the original source moment. “Checks and temporal context” shows individual judgments, nearby unverified samples and the actual bounded scope.

Latest mode checks twelve newest dated samples, then up to five semantic fallback candidates if needed. It reports the latest positive within the checked set, not an exhaustive last sighting across all footage. Unknown capture dates are excluded from latest/time-filtered queries. Best-match mode can check an imported clip while keeping its clock time unknown. Empty or uncertain checks never establish absence.

With recording explicitly enabled, **Check current view** captures a fresh video-only snapshot for local inspection. Its time and age are shown; snapshots that become stale in the queue/model load must be retaken. Snapshot answers are ephemeral, not permanently added to history. This button never opens a camera by itself.

Local models serve different jobs: **SigLIP 2 Base** embeds/searches frames; on Apple Silicon, **Qwen3.5-2B MLX 8-bit** loads lazily for visual checks and agent decisions. A lazy **SSDLite MobileNet V3** CPU detector adds independent entity positions (about 13.4 MB of cached weights). Retrieval/detection retain PyTorch/Transformers/Torchvision; generation adds the optional `mlx` extra. The quantized checkpoint uses about 2.7 GB on disk, outside the saved-video budget. The one small-image smoke measured 2.70 GiB peak MLX allocation, not total system memory or a bound for larger inputs. Old Qwen3-VL weights were removed locally; explicit legacy diagnostics would download them again. One worker still serializes model work. See [R8](docs/research/R8-companion-loop.md) for the smoke and unmeasured quality/latency gates.

## Try the baseline

Requires Python 3.12 (uv can select it), uv, and FFmpeg on PATH.

```bash
uv sync --python 3.12 --managed-python --extra vision
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
node --check src/nyx/web/voice.js
node --check src/nyx/web/companion.js
node --check src/nyx/web/audio-worklet.js
uv run --no-sync python experiments/image-text-retrieval/run.py \
  --download-samples --output data/runs/siglip-baseline
```

The test suite uses deterministic local fixtures and FFmpeg, with no model download or provider calls. Use `uv sync --python 3.12 --managed-python --extra web` for the full API suite without model dependencies. Without the web extra, API tests are skipped. The real-model experiment is separate; use a fresh output directory for each run. See [experiment method](experiments/image-text-retrieval/README.md), including the optional crop comparison and household-clip protocol.

An opt-in browser smoke check starts its own temporary localhost server and isolated headless Chrome, using generated camera frames instead of a real webcam. It requires the vision/web extras, installed Chrome and the cached model. Generate the benchmark clip first, then use a fresh output directory:

```bash
HF_HUB_OFFLINE=1 uv run --no-sync python tests/browser_smoke.py \
  --video data/runs/siglip-baseline/scenes.mp4 --visual-answers --output data/runs/web-m3-smoke
```

With `--visual-answers`, it also checks the cached local VLM, dated/unknown-time history, source replay and explicitly requested synthetic snapshots. It checks file import, real-model search, playback offsets, automatic multi-segment indexing, search/replay while recording, pause/resume, denied/interrupted camera behavior, navigation/reload, cancelled/confirmed source deletion and mobile overflow. `--record-seconds 1800` exercises thirty minutes of synthetic capture with periodic search and server RSS/backlog samples; the browser and FFmpeg are excluded from that RSS, and this does not replace a real-camera test. It writes screenshots and results under the output directory; this does not validate actual camera hardware or intended-user usability.

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
