# R33 — One image-grounded conversational call

Owner: Codex inline. Date: 2026-11-18. Status: bounded comparison complete; no runtime promotion.
Decision affected: foreground acknowledgement model and utterance-frame ownership.

## Question and method

Can one conversational model recognize a basic shown object and stream a short spoken response,
without waiting for separate visual interpretation and memory preparation? The user explicitly
authorized selected images and utterances from their recent localhost trial for this comparison.
Unique personal-object identity is outside this experiment's scope.

The exact saved shown-object image and a preserved-video reconstruction near final speech were
used. Originals were untouched; only selected JPEGs and corresponding text went to providers.
No full video, idle audio, unrelated private data or hardware capture was used. The second frame
no longer shows the object. Inputs contain no prior assistant answer or saved object label.

Frozen recipe: `experiments/companion/multimodal_ack_cases.json`. Driver:
`experiments/companion/multimodal_ack_replay.py`. Command:

```sh
uv run --env-file .env --no-sync python -m experiments.companion.multimodal_ack_replay \
  --evidence data/runs/multimodal-conversation-trial-v1/selected-trial-evidence.json \
  --output data/runs/multimodal-conversation-streaming-v1 --max-spend 0.15
```

Twenty sequential requests: three shown-image repetitions per model, then one earlier-plus-latest
and one endpoint-only case per model. Model order shuffled with fixed seed20261118. One frozen
short prompt, no wording sweep. Actual LiveKit Agents/OpenAI/Sarvam1.8.10, Python3.12; image
inputs bounded to640px, low reasoning,512 completion-token limit, retries disabled. LiveKit text
chunks feed actual Sarvam `bulbul:v4-flash` streaming TTS using `shalini_en_companion`, en-IN,
24kHz mono PCM. No playback. All20 requests returned text and PCM.

Timing starts at outgoing model HTTP request, after the budget check. First audio means valid
PCM received, not speaker playback; excludes STT, endpointing, browser transport and memory.
Fresh clients per row; results are not end-to-end product timings or provider compute timings.

## Measured latency

Shown-image columns are medians of three repetitions; sequence columns are single measurements.

| Model ID | Shown: first text | Shown: first PCM | Shown PCM range | Earlier + latest PCM | Endpoint-only PCM |
| --- | ---: | ---: | ---: | ---: | ---: |
| google/gemini-3.5-flash |2.46s |2.80s |2.39–3.24s |13.06s |3.20s |
| google/gemini-3.5-flash-lite |1.94s |2.29s |1.31–10.02s |2.72s |1.71s |
| openai/gpt-5.6-luna |3.07s |3.52s |2.87–3.75s |1.64s |2.76s |
| openai/gpt-6-luna |3.42s |4.02s |2.28–4.17s |3.29s |1.98s |

Do not compare these reduced acknowledgements with the prior20.13s preparation as equivalent
work. This experiment excludes reference matching, memory writes and native tools. It shows a
possible shorter foreground path, not an implemented latency improvement. Observed outliers
also reject a blanket claim that multimodal calls are always fast.

## Manual response review

All12 shown-image replies correctly named the basic smartphone category. All four earlier-plus-
latest replies recognized it and described the location as a plan rather than an observed
placement. None explicitly claimed it was still held in the latest frame.

Endpoint-only: Flash, Luna5.6 and Luna6 asked for clarification rather than naming the unseen
object. Flash-Lite instead confidently selected a background refrigerator as the intended
referent and associated it with the planned location. That is an incorrect grounding result.

Wording is not fully accepted: some replies add appearance commentary, Luna5.6 asserts
nonplacement more strongly than the evidence warrants, and some memory/reminder wording could
imply a commitment whose persistence/delivery was not exercised. Do not call the whole workflow
passed because category recognition succeeded. No timed notification was tested.

## Frame-selection diagnosis

Current `companion.js` captures every500ms, retains12s (up to24frames/2MB), and uniformly samples
up to six frames when `voice.js` receives a canonical question event. The main conversational
model still receives text/tool outputs rather than these images directly.

In the observed continuation, canonical acceptance/frame freezing occurred19.787s after the
raw final transcript. Its six selected frames were all later than the utterance and excluded
the shown object. The saved first frame showed it clearly; the reconstructed endpoint already
did not. The location plan inherited the earlier source record rather than recovering the object
from its own delayed frame window. A rolling buffer alone does not prevent this timing error.

Proposed minimal change: preserve the utterance's earlier and latest frames when speech events
occur, before slow downstream work; give that same owned evidence to the conversational call
and asynchronous memory preparation. Do not select only the final frame or extend retention
blindly to hide delayed ownership. This proposal is not yet implemented.

## Limits, cost and recommendation

One English scene, only three repeated positives per model and single sequence/negative cases.
Relative frame labels explicitly say earlier/latest and mention possible lowering; this helps
the model and is not a blind temporal-reasoning test. No clutter cohort, acoustic interruptions,
native tool selection, persistence, recall or user listening acceptance was evaluated. The
endpoint is reconstructed from video, not the exact original browser JPEG.

The observer recorded40 usage entries for20 calls, in20 identical adjacent pairs. Its raw summed
cost is$0.0409782 (conservative duplicated total); counting one entry per pair is$0.0204891.
Retain raw evidence; do not present the doubled total as an exact invoice. Key metadata changed
from$6.41265005 to$6.45102095 during the run, then$6.47447075/$8 at reconciliation. Running app
activity/settlement prevents assigning that entire difference to this benchmark. TTS made20
requests,1866 characters; its monetary cost was not exposed. No additional inference is needed
for this comparison.

Keep the current Luna6 production choice while reviewing integration: it passed these basic
grounding checks, and retaining it avoids a model migration based on a tiny timing sample.
Luna5.6 is another viable candidate; Flash-Lite's speed is insufficient reason to select it
despite the incorrect referent, and Flash had a13s outlier. Separate foreground conversation
from expensive memory work, then measure actual first playback and durable later recall together.
No production architecture/model switch, source mutation, UI change, PR or main change here.

Private artifacts remain ignored under `data/runs/multimodal-conversation-*`; recipe/evidence
hashes, exact replies, streamed chunks, versions and timing are retained there. Findings are
anonymized here; no private images or utterances are committed.
