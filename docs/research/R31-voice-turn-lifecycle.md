# R31 — Does Nyx preserve completed speech across interruptions?

Owner: Codex inline. Date: 2026-11-17. Runtime: Python 3.12, LiveKit Agents 1.8.10.
Status: turn-ownership repair verified synthetically; household and audio-gate acceptance open.

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

The client repair requires a narrow audio-transport edit under `src/nyx/web/`, currently forbidden
by the standing no-edit instruction. Prepare a concrete proposal and obtain that exception before
applying it. Keep UI layout/styling/wording unchanged. Do not disguise a timer increase or a prompt
change as reliable speech-boundary handling. No claim of full acoustic or household acceptance.

## Primary references

[LiveKit pipeline hooks](https://docs.livekit.io/agents/logic/nodes/) place per-turn context work
in `on_user_turn_completed`. [Turn handling](https://docs.livekit.io/agents/logic/turns/) documents
framework-owned speech boundaries and interruptions. Installed source was checked alongside the
documentation; source-reported framework support alone is not proof of Nyx integration quality.
