# Guided object-finding demo

The current MVP is a local, guided finding experience: ask about an object,
clarify which one, search recorded moments, then reject or confirm a possible
match. It is ready for guided developer testing. Household reliability and
intended-user acceptance remain open; [milestones](milestones.md) is the status source.

## Start

Requires Apple Silicon for the selected MLX model, Python 3.12, uv, FFmpeg and Chrome.
From the repository root:

```bash
uv sync --locked --python 3.12 --extra web --extra vision --extra mlx
uv run --no-sync nyx --data-dir data/manual-demo serve
```

Open http://127.0.0.1:8000. Typed conversation needs no API key or Docker.
First model use downloads pinned weights; allow disk and memory headroom.
The current model is Qwen3.5-2B 8-bit; SigLIP2 supplies candidate retrieval.
Run one model experiment at a time. The server alone does not open hardware.

## Try one complete interaction

1. Start recording with browser permission, or import a permitted short video.
   Wait for searchable samples; saved and searchable times are separate.
2. In **Talk to Nyx**, ask where an item is. An enabled camera provides a fresh
   view. Without one, ask about recorded footage.
3. If asked which item, describe a visible distinguishing feature or position.
4. Ask where it was seen in recorded footage. Review the returned image and its
   source time; imported footage can have unknown capture time.
5. Say “Nah, that is not the item I meant. Please keep looking” or use
   **Not this item**. The agent chooses its next search or clarification.
6. Choose **This is the item** only after reviewing the image. The result says
   **Confirmed by you**, preserves the recording time and survives reload.
   This confirms the historical image, not the object's present location.
7. Change the task or say to stop. Use **Stop response** for immediate output
   cancellation; an already running model call may finish.

If a follow-up loses details, restate the object and time explicitly. Similar
items and small objects can still confuse the model. Direct candidate search
and source playback remain available for review. Uncertainty is a valid result;
missing evidence does not establish absence.

## Voice and stopping

Follow [the README voice setup](../README.md#hands-free-voice) for the optional
voice extra, pinned tiny.en wake files and Sarvam key. Wake recognition is local
CPU/int8; activated STT and TTS use Sarvam, with playback in the browser.
Idle audio and visual media stay local. Voice-configured startup requests camera
and microphone permissions automatically. Synthetic tests cover interruption;
real room echo, pronunciation and provider latency still need evaluation.

**Pause recording** releases the camera. **Mute microphone** releases audio tracks.
**Stop recording** also stops listening. Stop capture, let pending work finish,
and press Ctrl+C in the terminal to release the server and loaded models.
Original saved videos stop at 1 GiB; existing clips are never automatically
purged. Explicit clip deletion removes its indexed evidence too.

## What has actually been demonstrated

The public two-cats/two-remotes fixture passed seven real-model API flow checks:
ambiguity, spatial correction, recent history, conversational rejection,
explicit confirmation, task switch and stop. A simulated reviewer rejected a
wrong crop before selecting the intended item. A blank-image check returned
uncertainty. These are development examples, not a household accuracy score.
See [R8](research/R8-companion-loop.md) for commands, timings and failures.

The combined feedback set still scores 5/10; details and temporal instructions
can be lost. Departure reminders remain an explicitly experimental
section: misses, false positives and late delivery prevent a dependable reminder
claim. General long-term memory, scheduled reminders, hardware and intended-user
evaluation are later work. No broader milestone is declared complete by this demo.
