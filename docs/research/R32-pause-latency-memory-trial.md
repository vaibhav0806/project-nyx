# R32 — Paused speech, latency and memory outside recent chat

Owner: Codex inline. Date: 2026-11-18. LiveKit Agents1.8.10, Python3.12.
Status: focused repairs verified; visual latency and real household acceptance remain open.

The second real trial saved two records: an object-showing report and a later location plan.
It therefore improved on the earlier zero-memory trial, but did not establish reliable recall.
Private inputs remain offline during developer evaluation; no new hardware was activated.

## Measured diagnosis

| Stage | Observed time |
| --- | --- |
| First memory preparation |20.13s |
| Visual request included in that preparation |14.05s |
| Continuation memory preparation |4.45s |
| Final conversational generation |1.84s |
| Continuation acceptance to first playback |6.18s |

Interactive queue time was0ms; indexing ran on its separate worker. The first slow completed-turn
hook delayed acceptance/display of the continuation. The visual request includes provider/network
time; the logs do not isolate model compute from provider queuing. Do not attribute14s to indexing
or promise it was eliminated. Dependent visual identification remains on the critical path.

## Implemented repairs and proof

- Forward partial/final speech as a display-only preview immediately. Append segments until a
  reply starts; canonical input/tool ownership stays separate. Later accepted input retains the
  combined display rather than replacing its first part. No layout/styling changes.
- Use LiveKit dynamic endpointing with0.5s minimum and3s maximum. An actual-SDK replay with a
  controlled0.2s pause now yields one completed input; the previous zero-delay setup yielded two.
- Ingest skips query embedding if every compatible memory fits the candidate pool. Source/vector
  validation remains; bounded larger pools and ordinary recall still use semantic ranking.
- Interrupted assistant output does not invalidate completed user input. An isolated copy exposed
  inconsistent availability checks; the new regression preserves input while withholding the
  interrupted answer, and still invalidates both after explicit source withdrawal.

Full suite:487 passed35.85s. Actual browser JavaScript replay:14 audio/transcript checks. Lint,
format and JavaScript syntax pass. No post-change acoustic or total-latency gain is claimed.

## Genuine memory-only trial

`data/memory-only-check-2026-11-17` contains a copy of the two memories and their original source
rows, plus32 neutral synthetic filler turns. Both20-turn recent storage context and12-turn model
context exclude the original source turns; the memory component's six recent inputs are also
fillers. Source rows, vectors and images are retained for attribution. Originals are unchanged.
The updated isolated service is at http://127.0.0.1:8002 (PID56599); the preceding8001 recording
process is left untouched while active. Only metadata/served-JS checks were made automatically.
No private model query was run automatically. The user can keep the object out of view and ask
where they said they planned to keep it. A normal restart alone also reloads recent conversation
and does not distinguish durable retrieval from chat context.

## Reply wording: rejected candidates retained

Three short prompt candidates were evaluated sequentially using only synthetic text/receipts.
The first retained the unrequested alert disclaimer. The second improved casual acknowledgements
but inadequately qualified a Hindi timed-alert request. The third still produced a disclaimer in
one ordinary location case and awkward mixed-script Hindi. None is promoted. The shared runtime
policy stays atversion8. Do not add more prompt variants to this checkpoint.
Response-reported total cost across the four runs is$0.005189; provider key metadata after the last
run was$6.02137985/$8. That cumulative figure includes the user's running application; it is not
all benchmark spending. No more developer inference is planned here.

Raw evidence is ignored under `data/runs/voice-pause-memory-20261118`, `reply-style-*` and the
isolated memory-check directory. Frozen synthetic conditions and the bounded driver are in
`experiments/companion/reply_style*`. Failures are retained, not relabeled as passes.

Primary references: [LiveKit endpointing](https://docs.livekit.io/reference/agents/turn-handling-options/),
[turn tuning](https://docs.livekit.io/agents/logic/turns/tuning/), and
[latency metrics](https://docs.livekit.io/testing/observability/data/). Installed SDK behavior was
checked directly; documentation is not treated as proof of Nyx's acoustic quality.
