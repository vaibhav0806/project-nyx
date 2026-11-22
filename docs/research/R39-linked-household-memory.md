# R39 — Link spoken plans to their supporting images

Date: 2026-11-19. Local macOS development checkout; Python 3.12, locked runtime.
Models: openai/gpt-6-luna (memory and conversation),
google/gemini-3.5-flash-lite (existing reference helper),
google/gemini-embedding-2 (768-dimensional personal-memory vectors).

## Question and decision

Can the existing memory pipeline preserve a demonstrated object's location plan,
including a container's location, without an automatic clarification loop or a
foreground save barrier? The user authorized a bounded replay of the latest trial's
selected images/utterance, with $0.20 available. Raw private material stays ignored.

Keep one ordered background writer. Use the existing reference helper to supply a
basic shown-object description to its single memory interpretation call. Preserve
useful supported parts when identification remains unclear. No new judge, service,
sampling policy, UI change or model promotion.

## Measured diagnosis

The original trial's background interpretation finished in 3,579 ms with a
clarification result and no saved records. Recall about 38 seconds later therefore
had no personal memory to retrieve; visual history found an earlier object-in-hand
frame. This was not an unfinished-save race. Both conversation and memory already
received up to six owned frames, but text metadata misleadingly described visual
availability as false, and the old schema allowed uncertainty to discard an entire
utterance's operations.

The exact ephemeral browser JPEGs were not retained. Replay reconstructed the same
six selected timestamps from saved video at the same 270×480 size. These are
time-aligned reconstructions, not byte-identical original inputs.

Four controlled Luna replays (two with old metadata, two with corrected metadata)
all saved a plan but described a generic small light-colored item. Consequently,
metadata alone is not an established cause. Increasing reasoning effort did not
recover its category. Supplying a generic saved plan and photo alone did not make
later key recall reliably join it to the plan.

The existing Flash-Lite reference helper identified the basic key category from
the same six frames in 2,732 ms. Providing that description to Luna's memory call
preserved the key → purse → cupboard plan. This extra work runs in the background
for voice; it does not precede the conversational acknowledgement.

## Implemented contract

- Memory interpretation returns operations and relevant IDs. Removed the legacy
  visual-access request and clarification fields/second interpretation path.
- Current frames and an optional resolved shown-object description accompany the
  exact user statement. Failed/unclear visual preparation does not veto supported
  text facts; it falls back to the existing image-aware writer.
- Each visual record retains its exact source quote, owned supporting photo,
  timestamp, object description and plan/report distinction. New embeddings include
  the content, source quote and description; existing embeddings remain compatible.
- Early candidates keep source quotes and concise visual metadata, within the
  existing five-record limit and a 6,000-character record budget. Generation can
  receive at most two source-valid supporting photos, explicitly labeled historical.
  Further tool lookup remains available. No write barrier or full-corpus photo read.
- Logs distinguish visual preparation, returned grounding/frame indices, and saved
  IDs. They do not add image bytes, raw statements or provider reasoning.

## Verification

An isolated complete replay used actual reference inference, memory interpretation,
embedding, SQLite/vec persistence, reopened component instances and early retrieval.
The conversational request omitted the original chat and received only the saved
record/quote/photo. Both tested conversational settings answered with the key in
the purse and purse in the cupboard, phrased as the user's plan. The voice-configured
answer began: “You planned to keep the small beige key in your purse”. No speech was
synthesized or played in this replay.

Controls: explicitly naming a phone retained the phone despite a key image; a
greeting saved nothing; no-image/partially identifiable inputs preserved supported
container/location plans without inventing a key or asking a background question.
An earlier full-pipeline attempt failed strict visual-reference validation. Its raw
response was not retained, so the exact malformed field is unknown. Clarified the
schema's grounding/reference relationship, retained strict validation, and captured
the successful pipeline response. This is evidence of improvement, not proof of
perfect model compliance.

Deterministic verification: **554 tests pass in 34.49 s**, Ruff lint/format and
whitespace checks pass. Coverage includes ordering/cancellation, source withdrawal,
owned-frame validation, mixed text/visual provenance, two-photo bounds, photo/quote
delivery to typed and spoken generation without a new camera frame, and graceful
unclear/failed visual preparation. Typed memory preparation does not implicitly
select an appearance constraint for unrelated history searches.

Reported successful replay costs are below $0.01. Key usage moved from
$7.525128625 to $7.53469509 during this pass; that account delta can include delayed
settlement and is not an exact experiment invoice. It remains below the prior $8
work ceiling and the new $0.20 bounded replay authorization. No developer phone
calls, microphone/camera activation or bulk-video upload.

## Limits and activation

Small objects can still be missed or misclassified. Six low-resolution samples do
not establish silent movement tracking. A model can still return an invalid
operation; strict provenance validation must not silently invent a valid one.
Reconstructed-image replay and deterministic tests do not replace a fresh household
and acoustic trial. The original failed trial/history is preserved, not rewritten
with a synthetic corrected result; repeat the statement after activating the build.

Activation: code7981ed1 is running on localhost8001, PID56121/session68988, after
confirming capture interrupted. HTTP200 and unchanged turn/memory/contact rows plus
all six recording hashes verified. No reset, automatic replay into the live database,
or developer hardware activation. Page reload and a new user statement remain required.

## Earlier manual-trial regression — 2026-11-19

After finishing the recorded demo, the user requested testing previous manual data
on the same branch. Replayed four preserved statements with the unchanged code at
7981ed1: the older phone/kitchen plan and bedroom-shelf correction, scissors/kitchen,
an earlier keys/purse/cupboard statement, and the latest keys/container statement.
Twenty-four frames were reconstructed at the recorded browser selection timestamps,
using the existing maximum size and JPEG quality. No resolution or sampling change.

Each isolated workspace received the original statement and up to six preceding user
statements, without old assistant answers or preexisting derived memories. The phone
case also received the actual later correction. Actual background reference inference,
memory interpretation, embeddings and SQLite/vec writes ran before reopening the
components. Recall generation received only early saved candidates and their one
supporting photo: zero old chat messages and zero new camera frames. It used the
current spoken Luna policy, low reasoning and configured priority provider order.
This tests the save/retrieval/model handoff, not acoustic input or browser playback.

Reviewed outputs:

- Phone correction: recalled the bedroom shelf rather than the earlier kitchen plan.
  An offline historical cutoff before the correction still retrieved the kitchen plan.
- Scissors: recalled the red-handled scissors plan for the kitchen.
- Earlier keys: recalled both the key in the purse and purse in the cupboard. The
  writer emitted two linked-by-statement facts; recall combined their supported details.
- Latest keys: recalled both container relationships, but added an unnecessary
  object-in-hand sentence after the plan. Its “try checking there” ending is less
  clear than the desired concise answer. Count memory content as successful and
  wording as a remaining weakness; do not claim all four replies were ideal.

All four completed on their first conversational generation without further lookup.
Completed-response request times were 2,392 / 1,651 / 1,708 / 2,155 ms respectively;
these are non-streaming model request times, not time to first speech. Background
save work took 12,894 ms for the two-statement phone/correction sequence, and
6,095 / 8,967 / 6,823 ms for the remaining cases. It remains independent of spoken
acknowledgement. These four cases are a regression sample, not a latency distribution
or broad household accuracy benchmark.

Offline checks on the actual saved rows verified exact source quotes, owned photo
timestamps, 768-dimensional vectors, correction history and inherited photo context.
Withdrawing the original source in separate audit copies withheld both its memories
and supporting photos in all four cases. Original databases and selected source-video
hashes remained unchanged. Private fixtures, script and raw results stay ignored under
data/runs/manual-regression-2026-11-19; no source/UI/model/prompt change or server
restart was made. Twenty provider requests reported $0.013240725, within a guarded
$0.10 run cap and the existing cumulative ceiling. No audio, hardware or call tests.
The later key snapshot was $7.547935815 cumulative usage, matching the reported
run cost above the $7.53469509 starting usage and remaining below the $8 ceiling.

## Full PR self-review — 2026-11-22

Reviewed the entire PR against current main, including memory persistence/retrieval,
typed and spoken tool handoffs, acknowledgement synthesis, rate-limit recovery,
call-result reporting, tests and documentation. Three concrete issues were repaired:

- Prepared/early candidate photo IDs preceded explicit recall results. Five candidates
  could exclude the requested record before its photo was read; even two earlier
  photos could consume the image budget. Prioritize explicit recall in both interfaces
  while retaining the existing five-ID/two-photo bounds and source validation.
- Spoken generation read explicit photos only from plan.last_tool, so a subsequent
  inspection could replace that result. Read delivered memory results from the bounded
  current-turn tool exchange as well. Do not carry their photos into another request.
- The provider voice-failure error categorically said no response was confirmed,
  although the same result could contain recipient speech. Report the technical
  failure and possible transcript incompleteness without discounting retained speech.

Typed API and actual-SDK synthetic regressions failed under the original photo
selection and passed after the fixes. They use six persisted visual memories and a
requested record outside the five background candidates. Added coverage for an
intervening tool and isolation from the next request. Call tests cover both empty
and nonempty transcripts for each termination category. Updated the README's stale
background-clarification wording.

Full suite: 561 passed in 34.80 s. Lint, format and whitespace checks pass; the final
new-request isolation assertions also pass in both voice cases. No new paid inference,
hardware activation, outbound calls, live-data changes or service restarts. Earlier
four manual-provider replays remain evidence for the unchanged writer/model policy;
the review fixes were verified offline. This is inline self-review, not independent
approval. GitHub review remains pending; no CI workflows are configured.
