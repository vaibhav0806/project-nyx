# Nyx

**Your own space. Your own routine. A little help from Nyx.**

Nyx is a personal AI companion that **sees, listens, and talks with you**, helping older adults live independently at home. Through a camera, microphone, and speaker, it sees the space around you, listens when you ask for help, and answers aloud in simple, natural language.

Say **“Hey Nyx, where did you last see my glasses?”** Nyx looks through what it captured and tells you what it finds. Ask a follow-up, ask an everyday question, or simply have a conversation—without scrolling through recordings or learning special commands.

Nyx brings awareness of your surroundings into the conversation, so help is grounded in your everyday life. You ask in your own words and get an answer you can act on.

[Features](#features) · [The experience](#the-experience) · [Security and privacy](#security-and-privacy) · [Run Nyx](#run-nyx)

## Independence, in everyday moments

A pair of glasses put down somewhere. A phone moved during a conversation. A detail you want to remember without asking someone else.

Nyx puts help within reach through a simple conversation. It is designed around older adults at home, especially those living alone, with the person's choices and routines at the center. Family can help with setup; the experience belongs to the person using it.

**The promise is simple: help me remember what happened around me.**

## Features

| What Nyx helps with | Try asking |
| --- | --- |
| **Find everyday belongings** — check the camera view for an object and get a useful location. | “Can you see my phone?” |
| **Look back at past sightings** — search saved visual history for when and where an item appeared. | “Where did you last see my glasses?” |
| **Bring conversation into recall** — use saved statements as context for a visual finding. | “Where did I say I would keep it?” |
| **Answer everyday questions** — ask naturally, without triggering an unnecessary visual search. | “What does that mean?” |
| **Keep the conversation going** — clarify, correct a match, ask a follow-up, or interrupt. | “No, I meant the other pair.” |
| **Talk in English or Hindi** — receive a reply in the detected speech language. | “Hey Nyx, what's up?” |
| **Check the source** — inspect the supporting image and replay the recorded moment. | Select **View source**. |

Nyx also includes an experimental next-departure reminder: “Remind me to take my bottle when I leave.” Event detection can miss or misread a departure; this is separate from a scheduled alarm.

## The experience

### A conversation, not a dashboard

Voice is the main interaction. Say “Hey Nyx,” tap the microphone, or choose **Type instead**. Nyx answers in short, familiar words, with a calm, attentive personality and a little dry wit when it fits.

The screen stays quiet: text paced with speech, a few clear controls, and supporting sources tucked behind **View source**. You can interrupt, mute, or pause recording without digging through a recording dashboard.

### Memory with context

Nyx connects saved visual moments with timestamps and relevant conversation. A reply distinguishes a sighting from something you said: “You told me you were going to keep it in the kitchen” means a remembered statement, not proof of a placement.

A last sighting describes the past. An object can move afterward. Nyx's answers are bounded by camera coverage, sampled observations, and retained history; conversation matching can miss relevant statements. Sources let you check an answer for yourself.

### Easy to talk to, not clever to listen to

Simple spoken language. Natural relative times. No technical vocabulary to learn, no need to read to follow the conversation, and no jokes at someone's expense for forgetting something.

## How it works

1. **Observe:** the browser records video while capture is enabled and indexes timestamped frames in the background.
2. **Listen:** local wake recognition detects “Hey Nyx” and activates the conversation.
3. **Understand:** general questions receive a direct response; questions about belongings and past sightings trigger a lookup.
4. **Check:** visual checks evaluate retrieved candidates before composing an answer.
5. **Respond:** Nyx streams speech and text, keeping source review available alongside the conversation.

This repository runs Nyx through a browser and a Python service, using one camera view. Recordings, indexes, and transcripts persist in the selected data directory across restarts. The [product vision](product.md) defines the complete product experience; [milestones](docs/milestones.md) document implementation and validation.

## Security and privacy

**Full video recordings stay on your device. You control recording, listening, and saved history.**

The configuration in this repository combines local storage and wake recognition with cloud inference. Its data flow is explicit:

| Data | Where it goes |
| --- | --- |
| Full video recordings | Stored locally; not uploaded as full recording files. There is no continuous room-audio archive. |
| Selected images | Sent through OpenRouter for embeddings and visual interpretation. |
| Idle microphone audio | Processed locally for wake recognition and discarded. |
| Activated speech | Sent to Sarvam for transcription; transcripts are stored locally. |
| Conversation and answer text | Relevant context goes to the language model; answer text goes to Sarvam for speech. |
| API credentials | Kept server-side, outside the browser and Git. |

Microphone mute, recording pause/stop, response interruption, source inspection, and explicit deletion are available in the interface. Camera and microphone access require browser permissions.

Saved video has a **1 GiB storage budget**. Capture stops at the limit without automatically deleting older clips. Frames, thumbnails, and databases use additional space. Deleting a clip also removes its dependent search data and invalidates affected source references.

OpenRouter requests disallow providers collecting data for training; this is not a zero-retention guarantee. See [scope and data boundaries](docs/scope.md) for the operating details.

## Run Nyx

### Requirements

- Python 3.12 and [uv](https://docs.astral.sh/uv/).
- FFmpeg, including `ffprobe`.
- A browser with camera, microphone, AudioWorklet, and MediaRecorder support. Chrome is used for the browser checks.
- OpenRouter and Sarvam API keys with available credit. Cloud inference incurs usage charges.

### 1. Install

```bash
git clone https://github.com/vaibhav0806/project-nyx.git
cd project-nyx
uv sync --python 3.12 --managed-python --extra web --extra voice --extra vision
```

Cache the pinned local wake-recognition model once:

```bash
uv run --no-sync python -c 'from huggingface_hub import snapshot_download; snapshot_download("Systran/faster-whisper-tiny.en", revision="0d3d19a32d3338f10357c0889762bd8d64bbdeba", allow_patterns=["config.json", "model.bin", "tokenizer.json", "vocabulary.txt"])'
```

### 2. Configure

Create an ignored `.env` file in the repository root:

```dotenv
OPENROUTER_API_KEY=your_openrouter_key
SARVAM_API_KEY=your_sarvam_key
NYX_TTS_MODEL=bulbul:v4-flash
```

Keep this file private and out of Git. On macOS or Linux:

```bash
chmod 600 .env
```

### 3. Start

Prepare the twelve reusable English/Hindi acknowledgement clips, then start Nyx:

```bash
uv run --env-file .env --no-sync python -m nyx.speech --prepare data/cloud-demo
uv run --env-file .env --no-sync nyx --data-dir data/cloud-demo serve
```

Open **http://127.0.0.1:8000** and allow camera and microphone access. Say **“Hey Nyx, where are my glasses?”** or use **Type instead**.

The data directory holds saved recordings, indexes, and transcripts across restarts. Reuse the same directory to keep that history. Starting the server alone does not activate the camera or microphone; the browser page manages hardware access.

## Built with

| Layer | Technology |
| --- | --- |
| Application | Python, FastAPI, and a browser interface |
| Voice conversation | LiveKit Agents with custom audio input/output over the local browser WebSocket |
| Speech recognition and synthesis | Sarvam Saaras v4 realtime STT and Bulbul v4 Flash TTS, with Shalini Companion presets |
| Language and visual understanding | Models accessed through OpenRouter |
| Search and persistence | SQLite, sqlite-vec, timestamped frame embeddings, and local recording files |
| Local activation and observation | Whisper wake recognition, activity filtering, and a small person detector |

LiveKit manages conversational turns, interruptions, streaming speech, and playback-paced text. No separate LiveKit room server or LiveKit account is required for this configuration. Speech/text alignment is estimated rather than exact word timing.

See the [architecture](docs/architecture.md) for the pipeline and [decisions](docs/decisions.md) for why it is built this way.

## Development

Run the deterministic checks:

```bash
uv run --no-sync pytest -q
uv run --no-sync ruff check src tests experiments
uv run --no-sync ruff format --check src tests experiments
node --check src/nyx/web/app.js
node --check src/nyx/web/voice.js
node --check src/nyx/web/companion.js
```

Browser tests use an installed Chrome. Automated developer verification uses synthetic inputs; real-provider evaluations are separate and can incur charges. Keep recordings, transcripts, generated audio, and credentials out of commits.

<details>
<summary>Index tools, migrations, and diagnostics</summary>

Import permitted footage, search indexed frames, inspect saved sources, or check the runtime:

```bash
uv run --env-file .env --no-sync nyx --data-dir data/cloud-demo index /path/to/permitted.mp4 --interval 2
uv run --env-file .env --no-sync nyx --data-dir data/cloud-demo search "a television remote control"
uv run --no-sync nyx --data-dir data/cloud-demo list
uv run --env-file .env --no-sync nyx doctor
```

Imported footage needs a known capture time to support a dated last-sighting claim. Import time is not substituted for capture time; use the CLI's `--recorded-at` option when appropriate.

Changing the embedding model or dimensions requires an index rebuild. Stop Nyx first, then run:

```bash
uv run --env-file .env --no-sync nyx --data-dir data/cloud-demo reindex
```

Reindexing sends saved sample images to the configured provider and replaces vectors in a transaction. Source files, frame IDs, timestamps, and references are preserved; a failed batch rolls back the rebuild.

The local `conversations.sqlite3` database retains activated transcripts and the latest 2,000 diagnostic events. The authenticated `/api/voice/diagnostics` endpoint exposes recent events for troubleshooting. Diagnostics can identify transcription, retrieval, or playback failures; they cannot recover idle speech that was never captured.

</details>

## Product and engineering docs

- [Product vision](product.md): audience, promise, and the complete product definition.
- [Product design](docs/design.md): mission, interaction principles, and Nyx's personality.
- [Scope](docs/scope.md): capabilities, data boundaries, and permissions.
- [Architecture](docs/architecture.md): capture, retrieval, conversation, and speech.
- [Milestones](docs/milestones.md): implementation status and validation evidence.
- [Research](docs/research/README.md): experiments, measurements, limitations, and open questions.
- [Repository guide](docs/repository.md): where the application and supporting work live.
