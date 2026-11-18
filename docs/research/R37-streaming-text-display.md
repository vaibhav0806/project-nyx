# R37 — Stable streaming text and listening timeout

2026-11-18, Codex inline. User authorized a narrow streaming-text display repair and
requested references from established UI frameworks. Layout/styles/audio timing remain unchanged.

## Diagnosis and change

`renderAnswer` replaced all answer HTML on every update, remounting settled paragraphs and
formatted nodes. Transcript updates also replaced text nodes with `textContent`. Browser
identity checks reproduced both mechanisms before the repair.

Apply Streamdown's stable-block principle within the existing plain-JavaScript/markdown-it
renderer: reconcile rendered children, preserve unchanged elements, update text from the first
changed character and retain real speech-recognition corrections. Markdown is still parsed by
the existing library; only the displayed DOM update changes. No new parser, UI framework or
dependency. Per-update animation wrappers are no longer recreated. Spoken text stays paced by
playback; no second smoothing delay. Typed reveal timing and reduced-motion behavior remain.

References (accessed2026-11-18): [Streamdown memoization](https://streamdown.ai/docs/memoization)
documents stable unchanged blocks. [AI SDK smoothStream](https://ai-sdk.dev/docs/reference/ai-sdk-core/smooth-stream)
documents buffering/chunk delays; Nyx already receives playback-synchronized spoken text.

## Verification

14/14 actual-Chrome synthetic checks pass: paragraph/text identity, completed blocks, evolving
Markdown, formatted-node identity, link changes, HTML escaping, Hindi text, transcript node
identity/corrections, canonical-final preview identity, synchronized speech and new-turn reset.
Run `experiments/companion/stream_text_checks.js` via script evaluation on a NEW isolated page
at `/markdown-it.js`; its fixture loads definitions only, excluding app/hardware startup.
The test refuses the live application route. Test pages closed afterward; no private media,
hardware activation or paid inference. JS syntax checks and67 nearby API tests pass5.85s.
This is DOM behavior proof, not a new acoustic or subjective visual acceptance result.

## User-trial logs and timeout explanation

Trial diagnostics report no failed/error events, kitchen-plan recall playback2411ms after accepted
transcript, and bedroom-shelf correction saved3603ms. Other playback samples range3303–7112ms;
do not generalize the one recall to all-turn latency. Completed/interrupted turns are retained.

Cloud audio activates for30s initially. User/agent activity keeps an activated stream open; an
idle follow-up window is10s after listening resumes. Expiry returns to local wake detection,
not microphone shutdown, history deletion or video stop. Browser heartbeats run every10s and
renew a separate30s session lease. Video rotates10s segments but has no idle stop; the latest
capture session is paused explicitly by the user. Budget/failure/browser shutdown can stop capture.
No timeout values changed. Extending follow-up to30s is a possible user decision, not implemented.
