# M4 hands-free voice implementation

User authorized Sarvam voice and supplied a key, then explicitly replaced push-to-talk with automatic camera/microphone startup and activation by “Nyx” or “Hey Nyx.” Execute inline. Nyx is intended to start automatically with the app or future device, listen for its name and activate hands-free, like Alexa or Siri. This supersedes the earlier manual-start product behavior. Automated developer tests use synthetic camera/microphone inputs only; that testing rule does not restrict automatic operation in the product. Keep the current M2/M3 changes and footage intact; no publication is requested.

## Design

- A configured app requests camera/microphone permission on startup, records video-only through the existing pipeline and listens locally. Browser/OS permission or audio-playback restrictions are visible recovery states, not silently bypassed. Stop/mute controls release or disable hardware. No-key/manual-only mode retains the existing camera-off behavior.
- Detect the wake name locally with a small CPU speech recognizer on VAD-bounded utterances. This is an initial ASR-based wake detector, not a custom trained keyword model; document false activation/miss limits and measure the actual alias behavior. Do not send idle room audio to Sarvam or a browser/vendor speech service.
- Keep local raw audio in bounded memory. After wake, submit one bounded spoken question to Sarvam STT. Support “Hey Nyx, where are my glasses?” in one utterance and name-then-question with an activation timeout. No continuous room-audio archive is created.
- Use Sarvam chat to distinguish short conversation from validated read-only visual requests/clarification and preserve short follow-up context. Common greeting intents bypass the cloud router after activated STT. Vision stays local. The browser supplies a fresh current-frame snapshot when explicitly activated by the person's voice; history uses the existing dated tool. Speech output comes from grounded tool results, never unsupported router claims.
- Sarvam TTS reads concise evidence-derived answers or brief conversational replies with its companion persona. Stop response/interruption invalidates late callbacks and stops playback; replay does not become a new microphone question. Visible transcript, tool evidence, listening/thinking/speaking/muted/error states remain available.
- Retain attributed conversation text, object/tool context, timestamps and completion/interruption states locally across restart. Raw microphone audio and generated playback remain ephemeral. Source deletion marks dependent conversation evidence unavailable; transcripts must never become fresh visual facts.
- The API key stays in ignored `.env` with private permissions, loaded into the backend process by uv. It is never returned to the browser, printed, checked into Git or sent to another host. Use only the user's Sarvam credits for small explicit connection checks and real test questions; no ongoing cloud stream before wake.

## Tasks

- [x] Read official Sarvam STT/TTS/chat and local ASR documentation; configure the supplied key without echoing it. Verify a tiny synthetic speech round trip and structured read-only routing.
- [x] Add optional voice dependencies and a pinned local wake recognizer; test wake/false activation, silence, clipping/bounds and name-plus-question using generated permitted speech. Do not claim a robust custom wakeword detector.
- [x] Implement bounded Sarvam adapter and local conversation persistence; deterministic tests for request shape, safe errors, routing validation, follow-up context, source invalidation and restart state.
- [x] Add local audio transport and wake/session state machine, with one active mic session, explicit origin checking, bounded frames/utterances, activation timeout, interruption/mute/close cleanup and no idle cloud calls.
- [x] Integrate auto-start, voice state/transcripts, fresh snapshot/history tool dispatch and speech playback with the existing UI. Preserve manual/no-key mode and existing capture/search/deletion behavior.
- [x] Run deterministic suite, provider smoke checks, synthetic camera/audio browser checks, lint/syntax/build and document actual measurements/limitations. Restart the user's idle local app without touching saved footage; real hardware onset requires their permissions/action, not agent browser tests.

## Evidence / rulings

- Existing Sarvam key stored in ignored `.env` at mode 0600 without displaying its value. Live Sarvam credit balance has not been independently verified.
- Wake audio stays local; Sarvam handles activated utterances only. English is the first reply language; broader target-language evaluation remains open.
- Initial implementation verified: 96 deterministic/API tests; synthetic browser startup/wake/tool/playback/mute/permission checks in `data/runs/web-voice-003`; real Sarvam v3 + local Qwen round trip in `data/runs/voice-integrated-001`, followed by the user-selected v4 speech/recognition/routing check in `data/runs/voice-v4-001`. Current speech models are Saaras v4 and Bulbul v4 Flash; no v3 fallback is enabled. See [R6 findings](../../research/R6-handsfree-voice.md). Existing user media is preserved. First cold integrated answer took about 21 seconds; room/noise, intended-language and spoken barge-in/latency gates remain open. The idle localhost server was restarted with `.env` loaded and voice configuration verified; all 346 pre-update recording/thumbnail files and 51 library entries were preserved. No real camera/microphone was opened by verification. No new commit/push was performed.

## Voice feedback iteration

User explicitly requested better wake recognition, latency and conversation after observing “what’s up?” routed as an object.

- [x] Reproduce routing from the screenshot and inspect fixed-threshold / discarded-audio paths.
- [x] Add separate conversation and clarification intents, a greeting fast path and short evidence-derived speech; keep detailed evidence intact.
- [x] Use Bulbul v4 Flash's Shubh companion persona; preserve Saaras v4 and local-only idle listening.
- [x] Add adaptive speech threshold, local partial wake probes, bounded pending audio, ten-second active follow-up and wake-based playback interruption.
- [x] Add microphone level and measured per-stage/end-of-speech timing. Preload the visual checker at configured startup.
- [x] Compare tiny/base local wake behavior on permitted synthetic clips; keep tiny because base did not improve this fixture.
- [x] Regression tests and synthetic browser checks for greeting/no-camera dispatch, quiet speech, pending input, follow-up, interruption and permission cleanup.
- [x] Final checks, documentation and safe restart of the idle local app: 109 isolated web/API tests, lint/format/JS/build/link checks, conversational and visual synthetic browser runs, real provider + local Qwen integration. All 663 pre-update recording/thumbnail files and 104 library entries were preserved. Voice configuration and visual-model readiness verified without opening real camera/mic. No commit/push performed.

## Publication

The subsequent user request to push all current work authorizes publishing this snapshot to `main`; earlier no-push statements describe validation checkpoints. See [Decisions](../../decisions.md#publication-authorization). Raw local data and credentials remain excluded.
