# R34 — Image-grounded voice replies without synchronous memory preparation

Date:2026-11-18. Owner:Codex inline. Status: implemented and verified; user trial pending.
Decision affected: voice latency, utterance image ownership, memory task lifetime.

## Implemented mechanism

Luna6 now receives the timestamped images in its active generation context. Final STT events
request a bounded browser-frame snapshot immediately, before canonical turn acceptance; canonical
turns consume those owned snapshots instead of capturing a later scene. The local12-second,
six-selected-frame contract remains. Multiple finalized segments coalesced by LiveKit retain a
bounded combined sequence. Server ownership checks distinguish those exact frame clocks from
unrelated frames; the same owned images feed memory. Images are not retained in past model chat.
Missing/invalid context yields text-only conversation, not invented visual evidence; the local
context handshake has a750ms bound. This does not preserve the entirety of arbitrarily long speech.

Completed speech still creates durable input in LiveKit's completed-turn hook. It then submits
memory to one bounded application-owned worker instead of awaiting the browser `process_memory`
relay. That worker preserves order and source/transaction validation. Interruption or a new voice
question does not cancel an earlier completed input's save. Later raw speech is excluded from an
earlier input's memory interpretation. A recall tool waits for preceding saves; its cached lookup
acknowledgement can play while waiting. Failures are logged, failed processing is reported with
lookup coverage, and cannot be represented as a successful save. Normal shutdown drains work.
Abrupt process death does not automatically replay unfinished memory inference; raw input remains.

The common personality policy is97 words, version9. It covers basic image recognition, pending
memory and untimed reminders as later recall. Reference checks stay available when needed; unique
personal-instance recognition is outside this slice. Separate Flash-Lite reference work still runs
when the memory component requests it, in the background. No extra AI judge, service or model switch.
Typed API memory preparation remains synchronous; this is the requested spoken-response repair.

## Deterministic verification

The actual installed LiveKit regression fails the old synchronous implementation: a deliberately
blocked memory preparation prevents the first reply. It passes with the new worker: the first
reply completes and a second spoken input is accepted before memory is released. Memory then
commits to its original source and remains recallable after reopening SQLite.

Other coverage: ordered/idempotent submissions, interruption, independent failure/next-input
progress, explicit source withdrawal during inference, recall synchronization, empty first-run
memory context, image context copies/source validity, coalesced frame reuse and rejection of foreign
frame clocks. The actual browser JavaScript probe verifies prompt frame return, preservation after
a20s delayed canonical event and context clearing on stop, as well as prior audio/transcript gates.

Final full suite: **493 passed in31.97s**. **18 actual-JavaScript synthetic transport checks** pass.
Ruff lint/format and JavaScript syntax pass. No hardware/acoustic acceptance is claimed.

## Bounded real-provider checks

The user-authorized selected trial images/text were reused; original media stayed unchanged. The
driver now supports an explicit recipe using the actual shared prompt and native SDK tool objects.
Tools are advertised but any tool invocation stops the acknowledgement-only probe. Actual streamed
text feeds Sarvam PCM exactly as inR33. First audio excludes STT, endpointing, browser and playback.

```sh
uv run --env-file .env --no-sync python -m experiments.companion.multimodal_ack_replay \
  --evidence data/runs/multimodal-conversation-trial-v1/selected-trial-evidence.json \
  --output data/runs/fast-voice-policy9-v4 \
  --recipe experiments/companion/fast_voice_cases.json --max-spend 0.05
```

Setup-v1 failed before inference because the experiment passed JSON tool schemas to an SDK method
requiring native tool objects; corrected the harness, retained the failed artifact. Production
already used native objects. V2 produced scheduling caveats (first PCM6.44s/4.64s). Removing
unsolicited capability flags and narrowing scheduling language inV3 removed the caveat but still
asked when to remind (4.71s/3.41s). These outputs were rejected as the desired wording.

FinalV4 makes the product distinction explicit: untimed reminders mean later recall. Shown-plus-
latest produced a brief category/location-plan acknowledgement with no scheduled delivery or
completed-save claim: first text3.73s, first PCM**4.07s**. Endpoint-only asked for the missing
referent rather than selecting an unrelated object: first text2.74s, first PCM**3.09s**. Neither
needed a separate foreground tool call. No claim that all turns or p95 are2–4s: earlier outliers
remain evidence, and a real browser/user turn has additional stages.

Raw observer totals acrossV2–V4 sum to$0.00243775, conservatively duplicated as inR33. Six TTS
requests synthesized726 text characters; invoice cost was not exposed. Final key metadata:
$6.601774225/$8 cumulative, $1.398225775 remaining. Budget includes prior application indexing.
No more developer inference is needed at this checkpoint. These checks do not measure the memory
worker's real-provider persistence end to end or acoustic interruption; those are manual trial gates.

## Authorized recording cleanup

Capture was interrupted after the user closed the tab. Under their explicit cleanup instruction,
deleted only the20 latest ready clips (3m30s,16,830,988 bytes), all over an hour after the last
activated trial turn and without saved turn/memory source references. Used the normal deletion
API and retained an ignored manifest. All556 retained original-file hashes, selected replay
evidence hashes, conversation rows and saved memory rows matched before/after. No automatic
retention/deletion policy was added. Recording stays stopped until the user reopens/enables it.

## Handoff and remaining limits

Use the updated original8001 data directory for the next user-run spoken trial. Show an item,
make a location note, allow the background task to finish, then ask a new recall question. An
ordinary restart reloads recent chat, so the updated isolated8002 copy is the separate old-memory
test with original turns excluded from recent context. Both services start without hardware.
The new architecture is implemented; it is not a blanket household-accuracy claim. Inspect new
diagnostics after the user trial rather than hiding failures or tuning rules to these examples.

Artifacts: ignored `data/runs/fast-voice-policy9-v*`, selected trial evidence and cleanup manifest.
Source: R33 plus installed LiveKit Agents/OpenAI/Sarvam1.8.10 behavior. Private images, transcripts
and generated replies remain ignored. Runtime has no fixture-specific object/place rules.
