# Fast visual conversation and background memory

User approved implementation on2026-11-18 after R33: retain Luna6, let it see utterance images,
respond before expensive memory preparation, preserve test media and hand back a manual trial.
Use the existing Python app and SDK; no model migration, service, UI layout or main changes.

1. Add failing regressions for reply generation while memory is blocked, ordered durable saves
   after interruption/disconnect, lookup synchronization and actual image context ownership.
2. Add one bounded single-worker memory lane owned by the application lifetime. It processes
   completed inputs in order, independently of reply cancellation. Existing source validators
   and atomic writes remain authoritative; failures are logged and visible as failed preparation.
   Only a memory lookup waits for earlier work. Normal shutdown drains completed inputs.
3. Request bounded frames immediately at final STT events, not delayed canonical question events.
   Freeze/retain the selected context in the narrow browser transport; validate it server-side
   and attach images only to the active model-context copy. Use the same frames in background
   memory. Canonical input and existing tool ownership remain separate from transcript previews.
4. Remove the synchronous voice `process_memory` relay. Keep native recall/history tools and
   shared short personality policy; clarify pending saves and ordinary visual acknowledgements
   without expanding into scenario rules. Typed API behavior remains outside this voice-latency
   repair; shared policy/tool definitions stay common.
5. Run focused and full deterministic checks, actual-JavaScript synthetic transport checks and
   a bounded real-provider integration replay using the selected authorized trial evidence if
   needed. Check paid budget before inference; no hardware. Record limits and regular commits.
6. Inspect capture/conversation/source times before deleting a small clearly unrelated tail.
   Preserve trial clips, source links and selected evaluation evidence. Restart the now-idle
   original localhost instance on the verified build, without opening camera/mic, then hand back.

Acceptance: generation starts before a deliberately blocked memory task finishes; another user
turn cannot cancel/misattribute that task; later recall sees committed earlier memory; frame
selection is anchored to raw speech rather than delayed processing. No claim of household or
acoustic acceptance until the user's next trial. R33 timing is not shipped end-to-end timing.
