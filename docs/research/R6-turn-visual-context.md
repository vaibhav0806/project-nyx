# R6 — Linking speech to the demonstrated object

Date: 2026-10-31. Inline developer evaluation on macOS arm64/Python 3.12.
Decision: repair demonstrated-object recall with temporal visual context and stronger grounding.
Status: saved-media and deterministic checks pass; fresh live voice validation remains.

## Observed failure

The latest user test produced correct bottle wording but bad durable links: one target was
stored as a pronoun; another as its destination. Independent statement search did not recover
the bottle claim. Therefore the apparent answer success did not establish durable recall.

Inspection of the exact persisted snapshots showed neither demonstrated object was visible.
The nearby recorded frame for the failed phone lookup likewise lacked the phone. Browser code
captured a snapshot only when an agent tool ran, after final transcription and tool selection.
The identification tool also reused named-object verification instead of reference resolution.
Schema-valid JSON could still contain an unsupported target; the old validator accepted it.

## Implemented change

A local rolling buffer samples existing camera video at 2 fps, retaining up to 12 seconds,
24 frames and 2 million encoded characters. It opens no additional device. When the browser
receives the final transcript event, it freezes up to six chronological frames for that turn.
Frames are copies; ongoing sampling cannot change them. Camera stop clears the rolling buffer.
All voice tools use that same turn window. The final transcript timestamp is the anchor, not
an exact speech-end timestamp; speech-start/end alignment is not claimed. Long utterances,
brief demonstrations falling between selected frames and background-tab throttling remain limits.

The backend bounds frame count, size and age relative to the utterance anchor, and checks voice
turn ownership. These are recent turn-reference frames, not proof of current scene state.
Reference resolution uses Gemini 3.5 Flash by default (`NYX_REFERENCE_MODEL`), while ordinary
named-object verification stays on Flash Lite. It distinguishes target, destination, claim kind,
visual versus explicit textual support, ambiguity, and supporting frame index. Unsupported
pronouns, destination-as-target, invented destinations and invalid frame indices require
clarification. Explicitly named objects may be recorded as textual claims without visual proof.

A resolved visual reference is passed to historical candidate comparison and, when present,
to saved-statement comparison. Embedding/text candidates still require model evidence checks;
category similarity does not prove unique identity. No scenario-specific phone/bottle routing.

New links carry a reference version. Old unverified links are excluded from semantic linked
recall, with named-transcript fallback retained. Two affected live development links were
explicitly repaired from the saved visual windows. Their complete prior rows, including images,
are retained in `statement_revisions`; original transcripts and videos were preserved. Repair
failure leaves the old row intact. Repair does not interrupt pending conversational turns.

## Measured replay results

All full recall replays started with empty agent conversation context and reopened storage
after 30 unrelated turns. They used the actual latest saved recordings and original transcripts.
No raw audio track/file was available for STT replay. Historical search used the original
question cutoff as its replay clock, so relative phrases refer to that historical time.

| Case | Evidence | Result |
| --- | --- | --- |
| Named phone recall | Latest recorded phone statement and visual history; synthetic named query | Correct sighting plus attributed intended destination |
| Shown phone lookup | Actual recorded pronoun question and its earlier camera window | Identify → visual search → statement search → combined completion |
| Named bottle recall | Latest bottle statement and history; original named question meaning | Correct sighting plus attributed intended destination |
| Shown bottle lookup | Recorded bottle frames plus explicitly synthetic pronoun question | Identify → reference comparison → statement search → combined completion |
| Late phone save snapshot alone | Exact original unsupported save snapshot | Clarification, no invented target |
| Late bottle save snapshot alone | Exact original unsupported save snapshot | Clarification, no destination-as-object link |
| Late phone lookup frame alone | Recorded frame near failed lookup snapshot time | Clarification, no invented phone |

The repaired phone link selected a supporting frame 6 seconds before final transcription;
the bottle link selected one 2 seconds before. The isolated replays also passed before repair,
so success did not depend on silently correcting the live database or loading recent chat.
Raw outputs and private transcripts remain ignored under `data/runs/turn-context/`.

## Reproduction and validation

`experiments/companion/saved_statement_replay.py` takes source, turn, cutoff, query and output.
`--lookup-turn` replays an actual demonstrated-object lookup. `--reference-turn` explicitly
constructs a synthetic lookup around recorded reference frames; it is not labeled a live test.
Temporary indexes and local hard links avoid modifying originals or duplicating video storage.
`repair_statement_links.py` explicitly repairs requested existing turn IDs and archives old rows.

Controlled regressions cover an earlier visible frame with an absent final snapshot, temporal
bounds, reference-versus-category checks, unsupported links, atomic repair and source retention.
A Node check verifies frozen frame copies, six-frame sampling and buffer clearing on pause,
without accessing hardware. The existing speech-paced text path is unchanged. Final validation: 378 automated tests
pass, with lint/format, JavaScript syntax and diff checks clean. Provider-key usage after
these replays was about $1.16 of its $2 cap (including earlier work), leaving about $0.84.

## Limits

These examples do not prove arbitrary household accuracy or unique physical object identity.
The model can still misinterpret images or select poor tools. The window is bounded, and the
archived recordings approximate browser frame timing in offline replay. Full LiveKit voice,
wake, interruptions and live final-transcript timing still need another user test.
