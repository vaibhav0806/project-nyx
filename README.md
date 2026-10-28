# Nyx

**Personal intelligence for a longer, independent life.**

Nyx is a conversational companion intended to help older adults stay independent.
The development target is a laptop with one camera view. It connects current images,
saved visual history, conversation and experimental departure reminders.

## Current MVP

Cloud inference through **OpenRouter** is the primary path. There is no local
LLM/VLM fallback. The custom Python agent chooses tools, constructs contextual
queries, reviews observations, and asks for clarification. No LangChain is needed.

- **Reasoning:** `openai/gpt-5.4-mini`; **vision:** `openai/gpt-5.4`.
- **Image/text embeddings:** `google/gemini-embedding-2`, 768 dimensions.
- **Activated transcription:** `openai/gpt-4o-mini-transcribe`.
- **Speech:** `google/gemini-3.8-flash-lite-tts`, Kore voice.
- **Local:** Whisper tiny.en CPU/int8 wake recognition, inexpensive activity
  filtering, small MobileNet person detector, recording files and SQLite storage.

Selected frames are sent to OpenRouter/model providers for embedding and visual
interpretation. Conversation context is sent for agent decisions. Activated speech
(including the ten-second follow-up window) is sent for transcription, and answer
text for speech. Idle audio stays local and is discarded. Full recordings stay on
the device; no room-audio archive is created. Requests disallow providers collecting
data for training; this is **not** a guarantee of zero retention. No automatic retry
or silent local fallback hides an outage or exhausted API credits.

The focused experience is **guided object finding**: ask, clarify, inspect the
source image, reject a wrong match conversationally, and confirm with **This is the
item**. Similarity is a candidate, not proof of identity or current location.
Temporal queries retain recording times, coverage gaps and strict before-frame
bounds. See [milestones](docs/milestones.md) for measured results and outstanding
validation. Cloud migration does not establish household accuracy.

**Departure reminders remain experimental.** Activity filtering and trajectory
checks precede selected-frame interpretation. Recognition can miss events or
notify too late. General personal memory, clock-based reminders and standalone
hardware remain later work. Conversation history persists, but only bounded recent
context reaches the agent.

## Setup

Requires Python 3.12, uv, FFmpeg and a browser with MediaRecorder support.

```bash
uv sync --python 3.12 --managed-python --extra web --extra voice --extra vision
```

The `vision` extra is only for the small local event detector; embeddings and
reasoning do not load Torch/Transformers/MLX models. The optional `voice` extra
provides local wake recognition. Cache its pinned checkpoint once:

```bash
uv run --no-sync python -c 'from huggingface_hub import snapshot_download; snapshot_download("Systran/faster-whisper-tiny.en", revision="0d3d19a32d3338f10357c0889762bd8d64bbdeba", allow_patterns=["config.json", "model.bin", "tokenizer.json", "vocabulary.txt"])'
```

Create ignored `.env` with `OPENROUTER_API_KEY=...`, restrict its permissions to
`0600`, and set a credit limit on the key. Never commit or expose it to the browser.

```bash
uv run --env-file .env --no-sync nyx --data-dir data/cloud-demo serve
```

Open **http://127.0.0.1:8000**. A configured page requests camera/microphone permission
and starts capture and local wake listening automatically. The server process alone
does not open hardware. **Mute microphone**, **Pause recording**, **Stop recording**,
and **Stop response** remain available. “Hey Nyx” can interrupt playback; in-flight
provider calls may finish, but cancelled results are not played. Real-room echo and
wake accuracy still need testing.

Say “Hey Nyx, where are my glasses?” or use **Talk to Nyx**. Review the displayed
evidence. Say “That is not the right item” to let the agent search again, or supply
more detail. Historical results show actual recording time when known, not import
time. Unknown-date clips cannot establish a latest sighting.

## Storage and rebuilding an old index

Original video storage has a **1 GiB** budget: capture stops at the limit and never
automatically deletes saved clips. Selected samples/thumbnails use additional disk.
Use explicit **Delete clip** to remove a source and its dependent vectors; source
references become unavailable. Failed saves and coverage gaps remain visible.

An old SigLIP index cannot be queried using cloud vectors. With Nyx stopped:

```bash
uv run --env-file .env --no-sync nyx --data-dir data/manual-demo reindex
```

This uploads saved sample images, replaces vectors and encoder metadata in one
transaction, and preserves source files, frame IDs, timestamps and references. A
failed batch rolls back the entire rebuild. It does not silently rebuild on startup.
Alternatively choose a fresh development directory; there are no production users
or compatibility requirements. Do not use private household footage in automated
developer tests.

```bash
uv run --env-file .env --no-sync nyx --data-dir data/cloud-demo index /path/to/permitted.mp4 --interval 2
uv run --env-file .env --no-sync nyx --data-dir data/cloud-demo search "a television remote control"
uv run --no-sync nyx --data-dir data/cloud-demo list
uv run --env-file .env --no-sync nyx doctor
```

Optional server settings: `NYX_REASONING_MODEL`, `NYX_VISION_MODEL`, `NYX_EMBEDDING_MODEL`,
`NYX_EMBEDDING_DIMENSIONS`, `NYX_STT_MODEL`. Changing embedding model
or dimensions requires rebuilding. TTS is pinned to the tested Gemini Kore,
24 kHz mono PCM contract.

## Verification

```bash
uv run --no-sync pytest -q
uv run --no-sync ruff check src tests experiments
uv run --no-sync ruff format --check src tests experiments
node --check src/nyx/web/app.js
node --check src/nyx/web/voice.js
node --check src/nyx/web/companion.js
```

Automated unit/API tests use synthetic fixtures and fake inference, without API
spending or model downloads. Real cloud evaluation is separate and costs credits:

```bash
uv run --env-file .env --no-sync python experiments/companion/planner.py --output data/runs/cloud-planner-new
```

[Cloud findings](docs/research/R9-cloud-mvp.md) distinguish measured cloud results,
controlled-tool planner tests and browser integration from household validation.
Older research experiments use dependencies removed from the current runtime;
reproduce them at their recorded historical commits, not as a second supported stack.
See [architecture](docs/architecture.md), [scope](docs/scope.md), and
[milestones](docs/milestones.md) for the current contracts.
