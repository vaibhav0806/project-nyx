# R38 — Interim stability, language admission and mixed WebSocket traffic

2026-11-18. Codex inline. User reported a slow-connection disconnect, unsupported script in
their transcript and continued volatile interim text after the DOM repair. This authorizes the
narrow voice transport/transcription repair; preserve layout, recording and existing sources.

## Findings and implementation

1. The browser compared total WebSocket buffered bytes to an audio-only96kB threshold. A
   legitimate150kB image message reproduced an immediate false audio disconnect. Recent raw
   finals were followed by session stops14/32ms later, consistent with frame-freeze uploads;
   old client telemetry cannot establish the original queued byte composition. Writes now track
   audio/control bytes in FIFO order, accounting for partial drain. Genuine96kB stalled audio
   still stops; no threshold inflation or unbounded PCM buffering. New safe byte-count telemetry
   distinguishes future audio congestion from media traffic.

2. Recognition was `language_code=auto`, not a two-language decoder lock. Sarvam's terminology
   prompt and codemix setting apply to finals; neither restricts interim languages. Its documented
   API exposes one explicit language or auto, not an English+Hindi allowlist. Keep the selected
   provider/model and add application admission: accept en/hi labels and Latin/Devanagari letters.
   Reject other labels/scripts rather than silently deleting words. Unsupported finals emit an
   empty boundary plus a repeat notice, never a nonempty agent/memory input. Genuine English/Hindi
   code switching remains valid. The notice survives idle-listening transitions and clears on
   new supported speech/activation. This is an admission guard, not measured improvement to
   acoustic recognition, nor proof of semantic language identification from a shared script.

3. Stable DOM alone cannot stop an ASR engine revising hypotheses. Backend transcript messages
   now separate provider-final segments from interim draft. Preview uses agreement between
   consecutive hypotheses, emitting whole agreed words and holding a displayed draft through
   interim rewinds. Provider finals remain authoritative and can correct that draft once; no
   stabilization changes durable input, agent timing or memory. This can lag a hypothesis update
   and is not equivalent to acoustically verified words. Legacy message handling remains compatible.

## Primary references

- [LiveKit transcription semantics](https://docs.livekit.io/agents/multimodality/text/): separate
  interim/final segments, replace provisional text when final arrives.
- [LiveKit realtime playground](https://github.com/livekit-examples/realtime-playground/blob/main/agent/main.py):
  segment IDs and explicit final flags in an open-source application.
- [Whisper-Streaming implementation](https://github.com/ufal/whisper_streaming/blob/main/whisper_online.py):
  agreement between successive hypotheses as a stabilization pattern. Nyx borrows the display
  principle; it does not add Whisper or copy the inference pipeline.
- [Sarvam realtime reference](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/realtime-streaming):
  language/stream modes, partial/final semantics and hint limitations. Accessed2026-11-18.

## Verification and deployment boundary

Failing-first checks reproduced mixed-traffic disconnect, interim rewind and unsupported-language
admission.26 actual-Chrome synthetic checks pass, including partial FIFO drain, real audio
congestion, segmented final/draft assembly, final corrections, persistent rejection notice and
the earlier Markdown/DOM checks. Protocol regressions cover English/Hindi/code-switching acceptance,
unsupported language/script rejection and notification without a new durable turn. Existing18
Node transport checks remain passing after updating their browser-global mocks.

Full suite:512 passed34.23s; Ruff/format/JS syntax pass. No provider inference, hardware activation or
private-media upload. Existing user evidence remains unchanged. New acoustic recognition and
subjective smoothness need user testing; constant/zero-delay captions are not promised.

Backend restart is deferred while capture is recording, under the repository's preservation
boundary. A browser refresh alone does not enable the new backend transcript fields/language
guard. Pause capture/close the user tab before restarting; retain the same household data root.
