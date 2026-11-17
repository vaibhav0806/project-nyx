# R31 — Does Nyx preserve completed speech across interruptions?

Owner: Codex inline. Date: 2026-11-17. Runtime: Python 3.12, LiveKit Agents 1.8.10.
Status: turn ownership and audio-gate repairs verified synthetically; live household acceptance open.

## Authorized audio-transport repair

The user explicitly approved the narrow `voice.js` transport exception. Browser and server gates
now retain an already activated stream while the user is speaking or the agent is thinking or
speaking. LiveKit's user-state event reaches the browser; completing speech renews the idle
follow-up window. Accepted input renews the existing lease. Mic stop/session cancellation clears activation,
and stale state events cannot start a fresh unactivated stream. No layout, styling, wording,
provider/model, prompt or build-system migration.

The actual browser script is executed in a Node VM with synthetic PCM:11 checks pass for initial
privacy, activated streaming, thinking, playback/interruption input, user speech, follow-up/idle,
old connection events, mute and connection reset. The corresponding server regression proves
expired deadlines do not cut active speech/replies and cancellation is not undone by state events.
Both client/server regressions failed on the original gates. The actual-SDK pending-memory race
replay also asserts that native user speech state is sent through Nyx's socket contract.

Full deterministic suite: **483 pass in28.77s**. Ruff lint/format114 Python files, JavaScript
syntax and the standalone Node check pass. No private input upload, paid inference, real browser,
camera/microphone or playback is used. Once capture became interrupted with a page-closed reason,
the8001 process shut down normally and restarted on edc12ef (PID44647). All154 saved clips retain
their hashes and all4 stored conversation turns retain their content/status. The served voice.js
bytes match the committed repair. Existing capture remains honestly marked interrupted; no final
delivery uncertainty is erased. The user must reload their page before acceptance; do not call
this a successful new household trial or a measured acoustic/latency improvement.

## Question and decision

The real household trial produced one completed greeting, three interrupted turns and zero
saved memories. Determine whether memory/vision quality or conversation transport first prevented
the object report from completing. Use the framework's lifecycle rather than more prompt rules.

## Observed trial evidence

Read the existing trial database and server diagnostics without replaying personal inputs to
providers. The placement input started memory processing, then another final transcript arrived
about 0.4 seconds later. Nyx replaced the active turn; the API cancelled its pending memory job.
The job's active-owner check refused the write. A later presence-check input also got no reply.
The persisted placement transcript lacks the kitchen destination described by the user. No raw
microphone archive exists to determine exactly what transcription omitted. This is not evidence
that visual recognition or storage successfully ran and then forgot a saved placement.

## Confirmed mechanism and repair

Nyx used the per-segment `user_input_transcribed` event to create and replace durable turns.
Memory preparation then ran inside the interruptible `llm_node`. LiveKit distinguishes those
events from its completed-user-turn hook. Its installed implementation serializes completed-turn
hooks and interrupts obsolete reply generation. Use `on_user_turn_completed` for owned input and
memory preparation; keep `llm_node` responsible for context projection and generation.

The repair moves existing work to that hook and binds the SDK message ID to the persisted turn.
It removes the redundant prepared-turn set and question-send task. Raw transcript events only
retain the detected language. No new model, prompt, judge, worker or memory algorithm is added.
Explicit cancellation still invalidates active API jobs; source validation remains unchanged.

## Reproduction and results

- A focused regression proves raw STT segments cannot create or replace durable input. A later
  raw final arriving during interpretation leaves the accepted plan's owner intact.
- An actual installed `AgentSession`, Nyx STT adapter/socket and SQLite replay holds memory RPC
  pending while a second synthetic utterance arrives. Committed baseline `2ce71c1` fails the
  ownership assertion. The repaired path saves the first kitchen plan and answers the follow-up.
  Only provider packets, model replies and audio output are substituted; no network or hardware.
- The existing native dispatch experiment now awaits the completed-turn helper. An initial full
  run exposed that outdated caller (480 pass, one fail); after correcting it, **481 tests pass
  in 29.41 seconds**. Ruff lint and format checks pass for 113 Python files.

Evidence is local under `data/runs/voice-turn-lifecycle-20261117/`; private trial text/media is not
committed. No paid inference or private upload was needed. Existing recordings remain untouched.

## Separate audio-gate finding

Running the unchanged `voice.js` audio-gate function in a Node VM with synthetic PCM confirms it
forwards before the wake deadline and stops afterward, including while `working` is true. The
server also checks a fixed awake deadline. Neither gate presently follows user speaking activity.
This can terminate audio delivery without a completed conversational turn; the exact contribution
to this user's missing words is still inferred, not established from archived audio.

The client repair originally required an exception to the standing `src/nyx/web/` restriction.
The user granted it and the patch above is applied. Keep UI layout/styling/wording unchanged.
The change follows framework activity rather than increasing a fixed timer. No claim of full
acoustic or household acceptance.

## Primary references

[LiveKit pipeline hooks](https://docs.livekit.io/agents/logic/nodes/) place per-turn context work
in `on_user_turn_completed`. [Turn handling](https://docs.livekit.io/agents/logic/turns/) documents
framework-owned speech boundaries and interruptions. Installed source was checked alongside the
documentation; source-reported framework support alone is not proof of Nyx integration quality.
