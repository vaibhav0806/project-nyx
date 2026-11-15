# R23 — Spoken utterance and household-tool reliability

Date: 2026-11-15. Status: protocol regressions/fixes implemented; expanded workflow testing ongoing.
Owner: inline implementation. Decision: repair general turn-boundary faults without UI changes.

## Root cause and protocol experiment

The custom Sarvam adapter emitted every transcript.final immediately, even when vad.speech_end
had not arrived. It also emitted duplicate finals as new user input. That could interrupt a
previous response or repeat a memory action. Five failing English/Hindi protocol tests reproduced
these errors, including a final at graceful session end. The actual LiveKit SpeechStream runs
against injected websocket messages and synthetic PCM; this is transport/turn behavior, not
acoustic STT accuracy. Sarvam's current primary docs describe both VAD and final events; current
LiveKit realtime adapter source explicitly buffers early finals until an utterance boundary.
The installed SDK supports the older protocol, so its different final/EOS sequence was not copied.

The custom adapter now buffers an early final until the observed end, next start or graceful
session.end, commits one final per utterance, and suppresses duplicate integer utterance indices
in a bounded64-entry deque. Identical words in distinct utterances remain distinct. Empty/null
transcripts and duplicate end events do not create extra turns. No phrase-specific matching or
guessed acoustic timestamps. Unexpected missing boundaries/connection failures are not evidence
of completed speech. This is bounded protocol handling, not a new endpointing timeout policy.

Eight new protocol cases plus twelve existing realtime tests pass. Broader household tool and
interruption/source tests follow before final verification. No real microphone or paid Sarvam
audio was used, and acoustic/transcription/TTS quality remains unmeasured here.

## Primary references, inspected 2026-11-15

- [Sarvam realtime protocol](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/realtime-streaming)
- [LiveKit Sarvam adapter source/docs](https://docs.livekit.io/reference/python/livekit/plugins/sarvam/index.html)

These are source-reported behaviors; only injected-transport measurements above are local results.
