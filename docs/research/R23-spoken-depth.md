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

## Explicit object grounding audit

Three failing regressions showed that a model's explicit-text object could be accepted as a
substring of another word (phone/microphone, keys/monkeys, cup/cupboard). Those examples live in
tests only. The backend now requires whole named phrases with Unicode letter/number/combining-
mark boundaries, preserving punctuation, case-insensitive multiword English and Hindi. It also
checks the folded prefix consistently when excluding destination-only names. No object-specific
exception list or replacement is used. Five new phrase/fragment tests and the existing reference,
statement and correction checks pass. A further three failing English/Hindi cases exposed a
prefix-only destination guard rejecting normal destination-first wording. It now excludes only
the actual destination spans, allowing the object anywhere else while keeping destination-only
names invalid. Metadata records explicit-unicode-phrase-v3/destination-spans.

## Actual spoken model and executable tools

Twelve frozen synthetic household utterances, six development/six held out, use actual production
instructions and SDK schemas extracted from the real nested Companion/socket setup. Current
spoken Flash model selects native tools without a forced action. Cases cover current view,
latest reports, unfulfilled intentions, shown pronouns, historical lookup, unsupported clock
reminders, general speech and explicit corrections in English/Hindi/Hinglish.

Initial development first-choice score6/6 hid an unsupported48-hour argument. The backend already
rejects it; the spoken schema advertised any integer. A failing schema-domain test preceded
restricting hours to the existing0/2/24/168/240 domain. SDK null/default handling is preserved.
The harness now uses real SDK argument binding and actual Companion dispatch, with external tool
results injected. Baseline posthoc dispatch gives5/6 executable, not6/6 end-to-end success.

Selected development responses and fresh heldout responses give6/6 executable expected choices
each, with no incomplete model cases. An intermediate harness incorrectly rejected valid SDK
positional bindings and printed2/6; the failing binder regression fixed that, then the exact same
saved model messages were rebound offline (no new inference). Original artifacts remain intact;
corrected development artifact is spoken-depth-native-selected-dev-bound. The correction is not
a fresh rerun and duplicated usage snapshots must not be added. Heldout uses the corrected harness.

These are tool-choice/binding/dispatch results, not complete household semantic answers. External
vision/report results are synthetic. A selected yesterday query widened to168 hours, so exact
calendar-date fidelity is not established by the executable-window score. Current public-photo
recognition and real acoustic/transcription/TTS quality remain separate limits.

## Evidence continuation audit

Four predeclared synthetic tool-evidence continuations use original model-selected native calls:
reported placement versus current evidence, unsuccessful save in Hindi, past visual candidate
plus unfulfilled plan, and correction using an actual returned source ID. The initial phone
reply said 'I saw it' despite unconfirmed identity: temporal/plan distinctions survived, but the
identity qualifier did not. This was an author-review finding beyond a keyword/shape score.

Spoken instruction version2 now explicitly keeps status=candidate as a possible identity until
user confirmation. It supplies no fixture IDs, classes, coordinates or canned final reply.
The same diagnostic replay then said 'what might have been your phone', preserved plan versus
completion, clarified the failed Hindi save and requested the exact returned correction ID.
These are reviewed examples, not broad free-form answer accuracy or fresh heldout evidence.
Two fresh synthetic visual-evidence conversations are evaluated separately before final status.

## Actual local wake inference and rejected ablations

Ten macOS-default-voice audio clips (five utterances at160/210 words/minute) passed through
cached pinned faster-whisper-tiny.en and actual Voice.probe, using the first three seconds.
No speaker playback, microphone, new model download or cloud speech was used. Measured5/10:
one of four intended wake clips activated, four ordinary negatives stayed idle, and both
near-name 'Hey Nick' negatives activated. These are generated English clips, not human rates.

VAD disabled versus enabled, initial prompt removed, and beam5 versus beam1 all retained5/10.
VAD was not the cause of these observed prefix omissions; no such ablation was promoted. The
decoder omitted/changed short Nyx prefixes, and Nick/Nyx phonetic confusion remains. Do not add
'next' or other fixture-derived aliases to manufacture passing cases. Wake operation remains
an explicit product gate requiring a representative acoustic/keyword evaluation and likely a
dedicated wake approach; existing tap activation is unchanged.

Artifacts: data/runs/spoken-depth-native-*, spoken-depth-continuations*, spoken-depth-local-wake,
spoken-depth-wake-{vad,decoder}-diagnostic. Provider snapshot after selected continuations
$1.904111815/2; settlement may lag. No paid Sarvam acoustic experiment was performed.

## Primary references, inspected 2026-11-15

- [Sarvam realtime protocol](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/realtime-streaming)
- [LiveKit Sarvam adapter source/docs](https://docs.livekit.io/reference/python/livekit/plugins/sarvam/index.html)

These are source-reported behaviors; only injected-transport measurements above are local results.
