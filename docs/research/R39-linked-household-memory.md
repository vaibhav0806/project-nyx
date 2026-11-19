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
