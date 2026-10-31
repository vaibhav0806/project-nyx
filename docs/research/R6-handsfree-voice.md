# R6 — Initial hands-free voice findings

Date: 2026-10-19. Status: first developer smoke, not intended-user or room-noise validation. User selected Sarvam and explicitly wants automatic app/device startup with wake-by-name activation, like Alexa/Siri. Automated tests use synthetic camera/audio; that rule does not restrict product behavior.

## Setup and source-reported contracts

M4 Pro, 24 GB unified memory, Python 3.12.12; faster-whisper 1.2.1 / CTranslate2 4.8.3 CPU int8, two threads. Local wake checkpoint `Systran/faster-whisper-tiny.en`, revision `0d3d19a32d3338f10357c0889762bd8d64bbdeba`. The pinned weights were downloaded to the external Hugging Face cache; inference requires the cached checkpoint and never sends idle speech to a provider.

Activated audio uses [Sarvam STT](https://docs.sarvam.ai/api-reference/speech-to-text/transcribe), `saaras:v4`, automatic language detection and the Nyx keyterm. Replies use [Sarvam TTS](https://docs.sarvam.ai/api-reference/text-to-speech/convert), `bulbul:v4-flash`, Shubh companion (`shubh_enhi_companion`), English (`en-IN`), 16 kHz WAV. [Chat V1](https://docs.sarvam.ai/api/api-guides-tutorials/chat-completion/overview) uses `sarvam-105b` with a forced read-only tool schema and reasoning disabled. These are explicit current selections, not claims that they are the newest models. Tool output, not chat-generated visual claims, supplies answer facts. Supplied credentials stay in ignored private `.env`; no balance/remaining-credit claim has been verified.

## Measured v4 connection check

The user explicitly requested v4 for both speech models after the initial checks. Switched to `saaras:v4` and `bulbul:v4-flash`, with the initial v4-compatible `shubh_enhi_ads` voice, subsequently replaced with the companion persona in the feedback iteration below. No v3 fallback is configured. Added the documented Nyx keyterm to Saaras v4's multipart request.

Ignored artifacts: `data/runs/voice-v4-001/`. Generated “Hey Nyx, where are my glasses?” with Bulbul v4 Flash, decoded it locally and submitted the permitted synthetic speech to Saaras v4. Both local ASR and Sarvam transcribed the name correctly in this clip; routing selected current view / glasses. TTS call: 0.828 s; local recognizer including constructor: 0.686 s; STT: 1.057 s; routing: 0.471 s. These are single-request developer timings, not an accent/noise benchmark, p95 or a complete visual-answer latency measurement. Earlier v3 results below are retained with explicit attribution.

## Earlier v3 synthetic speech check

Before the user selected v4, generated three short phrases with Bulbul v3. Local recognition consumed the generated PCM, without a microphone. Artifacts: ignored `data/runs/voice-001/`.

| Generated phrase | Local ASR text | Wake result | Local recognition |
| --- | --- | --- | --- |
| Hey Nyx, where are my glasses? | Hey Nyx. Where are my glasses? | Name + question | 0.317 s |
| Hey Nyx. | Hey Nyx. | Name only, activates next-question window | 0.220 s |
| What is next on the list? | What is next on the list? | No activation | 0.214 s |

This is three correlated synthetic clips, not a wake accuracy or false-positive-rate benchmark. Sarvam STT rendered the first phrase as “Hanks, where are my glasses?”; the router still selected current view / glasses. Actual accents and pronunciation need testing. A default-reasoning chat request exhausted its 350-token budget before producing a tool call; explicitly disabling reasoning fixed this small routing check. No unbounded retry loop was added.

## Earlier v3 integrated provider and local-vision check

Ignored artifact: `data/runs/voice-integrated-001/results.json`. This used Saaras v3 and Bulbul v3, before the user explicitly selected v4. These timings must not be attributed to v4. Submitted generated “Hey Nyx, where are my glasses?” to the local endpoint, used the real wake recognizer and Sarvam STT/router, inspected a permitted public fixture with the real local Qwen checker, then requested Sarvam speech. The fixture did not establish glasses presence; the tool correctly returned an uncertain answer and the reply preserved that uncertainty. This is one exercised outcome, not a visual accuracy claim.

- Local wake + Sarvam transcription/routing: 1.492 s.
- Snapshot model startup/inspection and job polling: 16.939 s.
- Sarvam response speech: 2.415 s; valid WAV returned, no warning.
- Total after submitting the already-recorded utterance: about 20.85 s. This excludes recording duration and browser silence segmentation, and includes cold visual startup. It is not a warm/p95 latency result and does not satisfy the proposed M4 target.

## Deterministic and browser checks

`tests/test_voice.py` exercises wake-prefix boundaries, idle/silent audio staying local, name-only/name-plus-question activation, expiry, session ownership, bounds, cancelled cloud stages/audio, constrained plan validation, conversation restart/source invalidation and authoritative visual-result matching. The full suite includes existing capture/history/visual tests; see the implementation plan for the latest run count.

`tests/voice_browser_smoke.py` starts a separate temporary server and isolated headless Chrome with synthetic camera/microphone devices. It uses real local wake ASR, with mocked cloud requests and visual judgments. No user's camera or microphone is opened. `data/runs/web-voice-003/` and the v4-generated-speech rerun `data/runs/web-voice-v4-001/` record automatic camera/mic startup, generated wake speech, current-view dispatch, reply playback, video-only recording streams, independent mute, camera stop also muting, conversation reload, permission denial and cleanup of microphone tracks arriving after cancellation. Chrome version: 155.0.8059.80. Provider behavior was exercised separately above.

Re-run with a generated permitted 16 kHz mono PCM WAV containing a wake-prefixed question:

```bash
HF_HUB_OFFLINE=1 uv run --no-sync python tests/voice_browser_smoke.py \
  --audio /path/to/generated-wake-question.wav --output data/runs/web-voice-new
```

## Limits and next decision

- The initial wake path recognized complete speech segments after about 0.8 seconds of silence; the feedback iteration below adds local partial probes and a 0.55-second endpoint. It is not an immediate custom keyword model; background speech can cost CPU and can trigger incorrectly. Nyx/Nix/Nicks prefixes, optional Hey, are accepted; empirical room false-positive/miss rates remain unknown.
- Browser permissions/autoplay can require a click. This is a browser constraint; future device startup should be automatic. Backend startup by itself does not open a browser camera/mic.
- Name-only activation gives a short local tone and a ten-second next-question window. The current version opens a visible ten-second active follow-up window after playback, accepting speech without another name call; that activated follow-up audio may reach Sarvam. Local wake probes can interrupt playback. One utterance can wait during processing, but already-running network/GPU work is not preempted. Actual speaker echo and unrestricted full-duplex behavior remain unvalidated.
- English wake recognition and replies are the first slice. Sarvam's language capabilities are not evidence that Nyx has passed target-language evaluation. The constrained router clarifies ambiguous time references; unrestricted event interpretation is not implemented.
- Conversation completion means answer produced, not confirmed playback/hearing. Conversation text is retained locally; raw mic and generated audio are ephemeral. Source deletion marks references unavailable but does not erase transcript text. A conversation-deletion UI and retention policy remain open.
- Next work: test real voice/room noise and wake-name variants, measure warm current/history latency including silence segmentation, exercise repeated calls and permission recovery, evaluate a trained custom wakeword path if local ASR misses or false triggers are unacceptable. Do not claim Alexa-level robustness from these checks.

## Feedback iteration: missed wake, slow response and visual-only routing

The user supplied a real transcript where “Hey Nyx, what’s up?” became a current-view object lookup for “what’s up.” Read-only inspection confirmed that route in the local conversation database. The original router offered only visual/clarification modes; the browser discarded all audio during busy/playback and used a fixed 0.012 RMS speech threshold. Those mechanisms explain the routing failure and provide plausible causes for missed speech; actual user wake audio was not recorded or analyzed, so no exact microphone/accent diagnosis is claimed.

Changes:

- Add chat/clarify intents with short replies. Common greetings use a local text fast path after activated STT; no visual tool or cloud router is invoked for those greetings. Recent nonvisual chat replies support short conversation context. Visual modes still require a matching fresh/local evidence job and cannot supply their own chat answer.
- Speak short evidence-derived answers, retaining location, historical attribution and uncertainty; detailed model checks and capture times remain in the visual panel. Select Bulbul v4 Flash's `shubh_enhi_companion` persona. Reuse at most sixteen generated reply audios in instance-owned RAM; raw room audio is not archived.
- Lower/adapt speech onset, preserve 350 ms of pre-roll and use 550 ms end silence. Batch 20 ms worklet messages. Add local wake probes during speech/playback, at most one in flight and at most a 2.5-second audio window. Final utterances recheck name-only calls rather than uploading the name to Sarvam. “Hey Nick” is a restricted recognition alias; bare Nick and next do not wake.
- Retain one bounded utterance during processing rather than dropping it. A locally recognized wake call stops playback. A visible ten-second active follow-up window opens after completed playback; repeat the wake name after timeout. This is not a claim of robust full-duplex or speaker-echo cancellation.
- Queue low-priority visual model preload at configured startup. Show microphone level and wake/STT/intent/visual/TTS timing plus end-of-speech-to-playback time. These measurements distinguish waiting for silence, recognition and visual work.

Live routing checks exercised current-object lookup, greeting, last-seen pronoun resolution and brief conversation. With the initially expanded nullable wire schema, valid questions returned empty clarification plans and chat replies were null. A string-only wire schema (empty for absent, normalized to internal null) with explicit examples returned the expected current/chat/latest/chat outcomes in those exercised checks, approximately 0.35–0.44 s each. This observation is scoped to these requests, not a general provider diagnosis.

Synthetic provider artifacts: `data/runs/voice-fixes-002/results.json`. “Hey Nyx, what’s up?” became a chat reply and valid companion speech in **1.365 s after submitting recorded audio**, excluding browser silence/decoding/playback. Wake/STT/intent took 205/369/0 ms and TTS 789 ms in that trial. This is a single synthetic greeting, not a visual-answer latency or p95 result. The generated glasses question routed to current view; the real visual integration check is recorded separately.

Wake comparison: `data/runs/voice-fixes-002/wake-comparison.json`. Three positive generated phrases and one negative phrase were each exercised normally, at 0.15 amplitude and with small added Gaussian noise. On that exact float-input experiment, raw tiny.en detected 9/9 positive variants with 0/3 negative activations, median 0.195 s; base.en detected 6/9 with 0/3 negatives, median 0.401 s. Applying a simple level normalization did not improve the comparison. A preceding quantized-input run missed two positive variants with tiny.en, showing sensitivity to the fixture/perturbations. Keep tiny.en; do not infer real-room wake accuracy from twelve correlated synthetic variants. base.en weights remain an unused experiment cache, not an app model.

Final deterministic/browser validation: 109 tests; `data/runs/web-voice-chat-003/` verifies greeting without a visual request, and `data/runs/web-voice-fixes-003/` verifies object dispatch. Both exercise real local wake recognition, synthetic playback interruption, quieter speech segmentation, a pending utterance while busy, and permission/mute cleanup. Cloud requests and visual judgments are mocked in these browser checks; no actual webcam/microphone was opened. Real-room voice/noise/echo and measured p95 remain open.

Real provider + local Qwen integration after preload: `data/runs/voice-fixes-integrated-001/results.json`. The startup visual preload took 7.688 s in this run. After submitting permitted generated audio, a greeting took 1.948 s including the first local recognizer construction. Two current-view questions on a permitted public fixture produced concise uncertainty plus valid Sarvam speech in 4.678 s and 3.139 s; visual work took 2.736 s and 1.965 s. The repeated identical uncertainty answer reused a RAM speech cache entry on the second trial (1 ms). These samples exclude browser silence/actual playback, are not a controlled speedup comparison, and do not establish p95. First preload still costs startup time; unseen answers may require a fresh TTS call. Detailed evidence stays in the existing visual panel.

## MVP wrap-up voice check — 2026-10-28

The documented four-file tiny.en cache initially failed offline startup under the
locked Hugging Face client: an unrestricted snapshot request also required the
repository README and .gitattributes. Wake loading now restricts the local-only
snapshot to config.json, model.bin, tokenizer.json and vocabulary.txt, matching
setup instructions. A regression checks this partial-cache contract.

`tests/voice_browser_smoke.py --audio data/runs/voice-fixtures/variant-0.wav
--output data/runs/mvp-voice-wake-20261028` passed with Chrome 156.0.8078.48,
actual pinned tiny.en CPU/int8 wake recognition and generated speech. It covers
local wake interruption of playback, current-view dispatch, playback, queued
quiet utterance, mute/stop cleanup, history reload, denied permission and late
permission cleanup. Provider STT/TTS, planner and visual judgments are doubles;
no actual camera/microphone or Sarvam call occurred.

Failures retained: first attempt failed on incomplete cache; after the loader
fix, `question.wav` failed the wake-interruption assertion. Isolated recognition
of its first 2.5 s and full audio returned only “Where are my glasses?” with no
wake name. Variant 2 also omitted the name; variants 0/1/3 retained “Hey Nyx” in
the 2.5 s probe. The variant-0 browser pass does not establish robust wake
recognition across pronunciations, room noise or speaker echo. Those remain open.

## Jev routing check — 2026-10-31

Decision: test whether a small typed gate can bypass the visual agent for general
spoken questions, preserving evidence/actions and contextual follow-ups. Adapted
the voice-only gate and concurrent filler pattern from
[Kairo gateRouting.ts](https://github.com/vaibhav0806/kairo-tutor/blob/main/src/notch/gateRouting.ts)
and its NotchApp caller. Kairo is a workflow reference, not evidence that it uses Jev.

Source-reported: Jev is non-generative and returns typed decisions, so a separate
responder is needed. Verified OpenRouter's [Decisions API](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request)
and [Jev 1.14 listing](https://openrouter.ai/typesafe/jev-1.14) on 2026-10-31.
Use existing OpenRouter credentials, a `noul` question and model `typesafe/jev-1.14`.
The general-answer path uses `openai/gpt-6-luna`. No TypeSafe SDK/account added.

Measured: ten synthetic text cases, sequential calls through `CloudVoice.route`,
on macOS 15.7.2 arm64 with Python 3.12.12. No microphone, camera or household
media. Three general questions (triangle sides, rainbows, small talk) returned
chat in 1.96, 2.38 and 2.20 seconds respectively, including Luna generation.
Seven tool/uncertain cases routed to agent in 0.50–0.61 seconds: last-seen glasses,
departure reminder, ambiguous other pair, contextual blue pair, instruction to
force a true decision while asking for keys, yesterday's conversation, door entry.
All ten matched the intended route. Combined reported API cost: $0.000260552.
Calls retained `provider.data_collection=deny`.

Reproduce with `uv run --env-file .env --no-sync python` and
`CloudVoice().route(question, context)` from `nyx.voice`, timing with
`time.perf_counter()`. Context is a list of prior question/object_query dictionaries;
the blue-pair case used a prior glasses question. Unit tests independently exercise
wire shape, uncertain decisions, invalid probabilities and responder deferral.

Limits: one small development smoke set, no baseline comparison or held-out
calibration; 0.95 is a provisional conservative threshold, not 95% accuracy.
Timings exclude activation, STT, TTS and playback. Jev adds a round trip to tool
requests. Full spoken latency and live-room interruption/echo remain unmeasured.
No claim that questions are answered instantaneously. Revisit the gate if larger
labeled tests show personal questions bypassing evidence or added latency outweighs
savings. Acknowledgement synthesis runs alongside the agent and is cached after
first use; it may fail or arrive too late and be skipped.

## Two-stage streaming checks — 2026-10-31

Decision affected: overlap text generation, sentence synthesis and playback, and
remove acknowledgement synthesis from lookup latency. This supersedes the earlier
Jev route that generated the entire direct reply before returning a plan.

Primary references checked on this date:
- [LiveKit pipeline nodes](https://docs.livekit.io/agents/logic/nodes/): asynchronous LLM/TTS pipeline with sentence adaptation for non-streaming text input.
- [OpenRouter speech tutorial](https://openrouter.ai/blog/tutorials/text-to-speech/): audio/speech returns streamable audio bytes; PCM needs the correct rate/channels.

Implementation: no new framework or SDK. Jev 1.14 classifies route/lookup/language;
Luna streams general replies and Hindi translation. Existing English evidence
answers bypass rewriting. Gemini 3.8 Flash-Lite TTS / Kore emits 24 kHz mono PCM.
Two sentence synthesis requests overlap while output stays ordered. Planner JSON,
visual checks and STT remain complete-result boundaries; idle audio stays local.

Measured on macOS 15.7.2 arm64/Python 3.12.12 using synthetic text only:
- General rainbow question: route 0.488 s; first text 1.385 s; first sentence ready
  1.897 s; first PCM 5.131 s; complete 8.779 s. These times include routing but not
  STT/browser playback. This run preceded two-sentence synthesis concurrency.
- Synthetic phone evidence: initial English rewrite assigned an unknown hand to
  the user. Removed that English rewrite. The final English ready-text path reached
  first PCM in 3.311 s and completed in 3.501 s after context was already available.
- Hindi phone evidence: initial translation also assigned hand ownership. Added
  explicit translation constraints; retest said “किसी के दाहिने हाथ में” and retained
  “मुझे लगता है”. First PCM 4.498 s; completion 4.742 s after context was available.
- English/Hindi lookup routing took 0.876/0.500 s in the earlier synthetic run.
- Prepared all twelve acknowledgement WAVs, six in each language: 1,119,888 bytes
  total under ignored `data/cloud-demo/voice-acknowledgements`. No real recordings
  or microphone/camera inputs were used. Re-running preparation reuses the files.

These are individual smoke measurements, not a baseline/p95 study or a guarantee
of response latency. Actual retrieval time and live browser playout are excluded
from the context-ready figures. Provider first-audio delay remains several seconds.
Hindi grounding/translation quality needs a larger held-out set; a single corrected
example is not a reliability claim. Binary TTS usage was not returned as JSON usage,
so no total spend claim is made for clip preparation.

Deterministic checks cover simultaneous synthesis with a barrier, sentence order,
text arriving while speech starts, English/Hindi boundaries, split PCM samples,
truncated streams, failed synthesis, authorization, duplicate streams, wake/stop
cancellation and transcript completion status. Isolated Chrome uses synthetic PCM
to verify fragmented NDJSON, audio before response completion, cancellation of
scheduled samples, stale-chunk suppression, and no acknowledgement for direct QA.

Reproduce clip preparation with the README command. `tests/test_speech.py` and
`tests/test_conversation_ui.py` exercise the offline pipeline. Live text-only checks
call `CloudVoice.route`, then `speech_events(provider.answer_tokens(...),
provider.speech_chunks, stopped)` with a synthetic checked answer and monotonic
first-event timestamps. No private media is needed.
