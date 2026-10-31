# R6 — Routing speed and durable speech-linked recall

Date: 2026-10-31. Owner: Codex, inline developer evaluation.
Decision: choose a fast tool-selection model without losing grounded recall; preserve
speech-paced display. Status: bounded developer evaluation, household validation pending.

## Method

OpenRouter streamed tool calls using the current LiveKit instruction text and function
schemas extracted from `realtime.py`. Five models, six synthetic cases, two interleaved
repeats each (60 requests). Cases: pronoun lookup, placement statement, historical lookup,
current view, departure reminder and greeting. Follow-up probes supplied a synthetic
object-identification tool result. No microphone/camera access. Python 3.12 on macOS arm64,
locked repository environment; low reasoning for Luna/Gemini, 700 output-token cap.
Raw results remain ignored in `data/runs/voice-routing/`.

Commands: `uv run --env-file .env --no-sync python experiments/companion/voice_routing.py`.
The script validates tool names, declared argument fields and selected scenario semantics.
Timing is request start to complete streamed decision, not audio latency or model-only time.
This is a small provider-routed sample, not a production latency percentile.

## Measured first-decision results

| Model | Median tool decision ready | Observed range | Important failures/limits |
| --- | ---: | ---: | --- |
| GPT-4o mini | 870 ms | 789–1122 ms | Both pronoun requests asked the user to show the object rather than inspecting it |
| GPT-4o | 913 ms | 824–1556 ms | One pronoun lookup skipped inspection; one placement acknowledgement skipped persistence |
| Gemini 3.5 Flash Lite | 1030 ms | 888–1943 ms | Both placement turns identified first; a continuation correctly called persistence |
| GPT-4.1 mini | 1105 ms | 999–1388 ms | Both historical requests omitted history=true; one named current query used generic identification |
| GPT-6 Luna | 1432 ms | 1160–2594 ms | One placement turn identified first; continuation correctly called persistence |

Identification-first placement is a valid intermediate step, not a full task failure.
These scores cannot establish complete two-source recall. GPT-4.1 mini's omitted flag
would invoke current inspection because the function default is false.

A six-case Gemini 3.5 Flash probe took 1838–2705 ms to complete tool decisions. One
follow-up invented a `query` argument for a no-argument persistence tool. The runtime
prompt now explicitly states the no-argument contract; this small probe is not proof
that schema errors are eliminated. The user selected Flash for main/final responses;
it currently also selects spoken tools. No additional classifier stage is installed.
Initial and continuation comparison calls cost about $0.049 total (provider usage reports),
excluding separate recall replays. All use the pre-existing capped test key.

## Durable recall checks

The public single-remote fixture plus a synthetic “this” placement transcript was persisted,
then storage reopened after 30 unrelated turns. The saved claim was retrieved by “remote
control” without recent context. Flash produced the intended distinction: the user planned
to keep it in a location, but the last visual evidence showed it in their hand. First final
answer token measured 3372 ms on that single run. Visual retrieval in this particular probe
was supplied synthetic checked evidence; it was not a complete recorded-video test.

The first extraction returned a JSON array despite JSON-object mode. Added explicit JSON
schema constraints and defensive validation; original transcripts survive malformed output.
An initial final-answer probe with tool-seeking instructions failed to finish. Marking retrieval
complete produced a usable grounded final answer. Neither failed call counts as a pass.
`experiments/companion/statement_recall.py` reproduces the bounded public-fixture test.

Authorized saved-media replay is separate: `saved_statement_replay.py` accepts an existing
turn and capture cutoff, reconstructs its recorded snapshot, and runs the actual typed
agent against an isolated copy of the original index with empty conversational context.
Media uses local hard links solely for reading; originals are not changed. The first replay
attempt used symlinks and correctly hit workspace path containment; it is a test-setup failure.
Results and private exact transcripts remain ignored rather than included in Git.

Two authorized actual-recording replays subsequently passed: one originally used an
unresolved pronoun, the other explicitly named the item and placement. The reconstructed
snapshot resolved the phone, and the actual typed planner chose visual history, independent
statement search, then a combined completion. Recent chat was empty and the original turn
was outside the recent-turn window. Both final Flash answers included the hand sighting and
the attributed intended placement, without claiming placement was visually observed.
The replay clock uses the original question cutoff, so “just now” refers to that historical
replay time. Tests used saved transcripts, not a new STT pass; raw microphone audio is absent.

The first valid-media replay still finished after the visual result and omitted speech.
Made the two-source object-location requirement explicit in the continuation instructions;
the subsequent two replays selected both sources. This is evidence of the fix on these cases,
not a guarantee for arbitrary model decisions. One final answer exhausted the old 700-token
allowance; the streaming answer and LiveKit caps are now 2048, retaining low reasoning and
short-answer instructions. The repeated actual-recording test then completed. No automatic
provider retry or hidden fallback was introduced.

## Display research and check

Applied a 140ms opacity-only fade to newly released text, no delay/translation/blur.
LiveKit playback synchronization remains the only speech reveal clock; reduced motion
skips the fade. A headless Chromium check verified incremental appearance, settled text,
Markdown emphasis and reduced-motion behavior without opening hardware.

Primary references: [Chrome motion guidance](https://developer.chrome.com/docs/modern-web-guidance/guides/ui-behaviors/motion),
[W3C reduced-motion technique](https://www.w3.org/WAI/WCAG22/Techniques/css/C39.html),
[Vercel streaming message components](https://vercel.com/academy/ai-sdk/ai-elements).
No UI framework or animation dependency was added.
Model references: [GPT-4.1 mini](https://openrouter.ai/openai/gpt-4.1-mini/performance),
[Gemini 3.5 Flash](https://openrouter.ai/google/gemini-3.5-flash).

## Limits

A stored object description is model inference, not unique physical identity. Snapshot time
and transcript receipt time are retained separately; exact speech intervals are unavailable.
Legacy named transcripts have bounded lexical fallback; legacy unlinked pronouns are not
silently reprocessed. Long-term ranking/index scale, similar-object identity, contradictions,
actual microphone timing and the full LiveKit voice loop need broader evaluation.
