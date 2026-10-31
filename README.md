# Nyx

**Your everyday memory companion.**

Nyx helps you find the things you put down and recall the moments you might otherwise forget. Ask a question out loud, and Nyx looks through the current camera view or saved visual history, then answers in simple, natural language.

> “Hey Nyx, when did you last see my glasses?”
>
> “I think I saw them about half an hour ago, beside your laptop.”
>
> *An example of the experience. Actual answers depend on what Nyx captured and can find.*

The goal is simple: spend less time searching and more time getting on with your day.

[How it works](#how-it-works) · [Privacy and control](#privacy-and-control) · [Run Nyx](#run-nyx) · [Product and engineering docs](#product-and-engineering-docs)

## Why Nyx exists

A phone left somewhere between rooms. Glasses put down during a conversation. A small detail that felt obvious a few minutes ago.

These moments interrupt everyday life. For older adults, repeated difficulty finding things can also mean relying on someone else for tasks they want to handle themselves.

Nyx is being built to support that independence. Its starting point is practical help at home: let someone ask about their surroundings in their own words and get an answer they can act on. No need to remember a filename, scroll through recordings, or learn a set of commands.

**The mission is to help people live on their own terms for longer.** Older adults living at home are the starting audience; the interaction is designed to be useful to anyone who could use a little help remembering everyday moments.

## What you can do with Nyx

### Find something in front of you

Ask, “Can you see my phone?” Nyx checks the current view and describes what it can identify using ordinary places and landmarks. If it cannot find the item clearly, it can ask for more detail.

### Look back for a last sighting

Ask, “Where did you last see my glasses?” Nyx searches saved observations, checks candidate matches, and gives a spoken answer with a rounded time such as “about thirty minutes ago.”

A small **View source** button lets you inspect the supporting image and replay the surrounding recorded moment. The source is there when you need it; the main screen stays focused on the conversation.

### Keep the conversation going

Ask follow-up questions, describe the object more precisely, or say that a match is wrong. Nyx can use that context to continue the search. You can interrupt a reply instead of waiting for it to finish.

### Speak in English or Hindi

Say **“Hey Nyx”**, tap the microphone, or choose **Type instead**. Nyx follows the detected speech language for its response and voice. Replies use short, familiar words, with a calm, relaxed personality and a little dry wit when it fits.

The interface stays quiet: three dots while waiting, text paced with speech, and a few clear controls for talking, muting, and viewing sources.

## How it works

1. **Capture useful context.** While recording is enabled, Nyx saves video locally and indexes selected, timestamped frames in the background.
2. **Listen when activated.** Local wake recognition detects “Hey Nyx.” Activated speech is transcribed, including a short follow-up window.
3. **Choose the right response.** General questions can receive a direct reply. Questions about objects and past sightings trigger a visual lookup.
4. **Check the evidence.** Search identifies candidate moments; visual checks help determine what the answer can say.
5. **Answer aloud.** Nyx streams its reply and speech, with supporting sources available separately.

Nyx also saves activated conversation transcripts. When relevant, a history lookup can attach something you said to a visual finding. A statement such as “I’m going to keep this in the kitchen” is an intention you expressed—not proof that the object reached the kitchen.

That distinction matters: a useful memory companion should tell you whether an answer comes from a sighting or from something you told it.

## Current release

Nyx currently runs as a local browser application connected to a Python service. It supports one person and one camera view, with continuous recording, background indexing, visual search, source replay, and realtime voice conversation.

The following limits are part of the current product:

- **Coverage is limited to what the camera captured and what storage retains.** Indexing uses sampled frames; a search cannot account for every instant or anything outside the camera’s view.
- **A past sighting is not a current location.** Objects may have moved, and similar-looking items can produce incorrect matches.
- **Transcripts persist, but recall is still bounded.** Matching a spoken placement statement to the right sighting can miss relevant information. General, dependable long-term personal memory is not implemented yet.
- **Next-departure reminders are experimental.** Nyx can work with requests such as “Remind me to take my bottle when I leave,” but departure detection can miss events or trigger incorrectly. Clock-based and recurring reminders are not available.
- **Real-home reliability is still being evaluated.** Room noise, speaker echo, wake recognition, object visibility, and response latency need broader testing with intended users.

The [milestone tracker](docs/milestones.md) and [research findings](docs/research/README.md) distinguish implemented behavior from measured results and planned capabilities.

## Privacy and control

Nyx stores recordings and its searchable history on your device. It uses cloud models for parts of understanding and conversation.

| Data | How Nyx handles it |
| --- | --- |
| Full recordings | Stored locally. The current recordings contain video, not a continuous room-audio archive. |
| Selected images | Sent to model providers through OpenRouter for embeddings and visual interpretation. |
| Idle microphone audio | Processed locally for wake recognition and discarded. |
| Activated speech | Sent to Sarvam for transcription. Transcripts are saved locally. |
| Conversation and answer text | Relevant context goes to the language model; answer text goes to Sarvam for speech generation. |
| Credentials | Kept on the server, outside the browser and Git. |

A configured page requests camera and microphone permissions and starts recording and local wake listening. **Mute mic**, recording pause/stop, response interruption, source review, and explicit deletion are available in the interface.

Saved video has a **1 GiB storage budget**. Capture stops at the limit; Nyx does not automatically delete older clips to make room. Frames, thumbnails, and databases use additional disk space. Deleting a clip removes its dependent search data and marks affected source references unavailable.

OpenRouter requests disallow providers collecting data for training. This is not a guarantee of zero retention. See the [scope and data boundaries](docs/scope.md) for details.

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

- [Product design](docs/design.md): mission, interaction principles, and Nyx's personality.
- [Scope](docs/scope.md): current capabilities, data boundaries, and planned work.
- [Architecture](docs/architecture.md): capture, retrieval, conversation, and speech.
- [Milestones](docs/milestones.md): implementation status and validation evidence.
- [Research](docs/research/README.md): experiments, measurements, limitations, and open questions.
- [Repository guide](docs/repository.md): where the application and supporting work live.
