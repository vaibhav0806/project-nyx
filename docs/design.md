# Product design

## Companion character — 2026-10-31

Nyx is calm, attentive, practical and lightly warm. Speak directly to the listener,
lead with what helps, and stop when the question is answered. Use natural contractions;
avoid forced jokes, pet names, repeated enthusiasm and internal labels such as “the user”.
Personality comes from helpful timing and clear language, not adding “Yeah” to every reply.
For this personal demo, the user explicitly permits “you/your” for the described user and
otherwise unattributed hands. Explicitly different people stay distinct. This assumption
changes presentation only, not stored evidence or identity recognition.

Examples: “I think I saw your phone about 50 minutes ago, in your hand.”
“I think I saw you using a phone about 50 minutes ago.” “I haven't found it yet.”
Keep evidence uncertainty brief; never invent a hand location from “in front of the user”.
See [R7 personality findings](research/R7-instinct-ux.md).

## Natural companion wording — 2026-10-31

Keep answers conversational: “I think I saw your phone about 35 minutes ago, on the table.” Use checked location details, rounded relative times and short uncertainty where needed. Do not recite “please check the image”, “not verified”, or “approximately”; do not address the user as “bro”. Quote a remembered statement as “You said…” rather than claiming its intended action happened. Clock answers use the browser local timezone without saying UTC by default.


## Approved conversation UI — 2026-10-31

The main experience is a conversation, not a recording dashboard. Show the current question
and Nyx’s actual answer in large text on a charcoal background. A central control switches
between talking and stopping; adjacent controls mute the microphone or reveal text input.
“View source” opens supporting evidence only when requested. Camera status and a pause/resume
action remain visible; settings contain recording management, history and diagnostics.
No illustrative Paper answers are shipped as real findings. Uncertainty remains part of the
actual answer. Desktop and narrow mobile layouts use the same flow without gradients.


## Current implementation direction — 2026-10-28

Cloud inference is the primary MVP path. Keep capture, wake recognition,
inexpensive observation and evidence storage on-device; use OpenRouter for agent
reasoning, selected-image interpretation/embeddings and activated speech. The
mission and evidence/uncertainty principles remain unchanged. Older references
to local model checks describe the preceding prototype, not the current runtime.


Status: working design, 2026-10-19; the user reviewed the package and resumed the first implementation milestone. Product intent comes from the working discussion and approved application pitch; implementation choices are tracked separately in [Decisions](decisions.md).

## Mission

Nyx exists to extend the years people can live with agency, dignity, and independence.

We’re building a personal AI companion that sees, listens, and remembers, so people can keep living on their own terms as they age. Older adults living at home are the starting audience. The prototype runs on a laptop before dedicated hardware.

## Experience

Nyx starts with the app or future device, listens locally for “Hey Nyx” or its name, and activates hands-free, like Alexa or Siri. Camera and microphone startup are automatic after required permissions, with visible controls. The person speaks naturally to Nyx about their surroundings, past events, earlier conversations, or something they want to remember or do. Nyx uses the relevant evidence and responds aloud. Follow-up questions carry context across a conversation; durable memory carries useful information across sessions.

| Situation | Intended behavior |
| --- | --- |
| “Where are my glasses?” | Inspect a fresh view and describe a supported location using landmarks. Clarify if multiple pairs are ambiguous. |
| “Where did you last see them?” | Search retained history, verify candidate sightings, and return a timestamped source moment. |
| “Did someone come by this afternoon?” | Retrieve supported visit events within camera coverage; name a person only from supplied or confirmed identity information. |
| “What did I ask you yesterday?” | Retrieve the relevant assistant conversation with its time and source. |
| “Remember that the documents are in the blue drawer.” | Save an attributed fact, allow correction, and retrieve it in a later session. |
| “Remind me to call my daughter at six.” | Resolve the intended time, read it back, save the reminder, and report its actual delivery state. |
| “Remind me to take my water bottle when I go out.” | Retain an active intention, observe supported departure cues, and speak at the useful moment; distinguish failed, missed and acknowledged delivery. |

These are full-product design scenarios. The current repository demonstrates continuous candidate retrieval, bounded local model checks and an initial hands-free voice slice; full-product workflows remain staged. Final workflow priorities and preferred language need research with intended users.

## Product principles

**Independence:** support the person's choices and daily routines. Test the experience with older adults themselves; relatives' feedback complements their perspective.

**Conversation:** voice is the main interaction. Keep answers short enough to act on, support clarification, and make interruption possible. The browser interface exists for setup, controls, evidence inspection, and development.

**Grounded memory:** connect answers to what Nyx saw, heard in an assistant interaction, or was explicitly told. Keep these source types distinct. Similarity search finds candidates; verification establishes what an answer can claim.

**Continuity:** persist useful history, conversations, saved facts, and reminders across sessions and restarts. Show actual retained coverage and gaps.

**Control:** camera recording and wake listening start with the configured app and are visibly indicated; provide a way to stop them. Provide microphone mute, recording pause, inspection, deletion, and storage limits as part of the experience.

## First demonstration

Show an object in a fixed scene, interact with Nyx, move the object out of view, then ask about its last sighting. Retrieve and display the relevant recording moment. Restart the session and recall a saved fact or conversation, then deliver a requested reminder.

The first engineering slice proves only recorded-frame retrieval. The full laptop demonstration adds visual verification, current inspection, voice, and personal memory in stages; see [Milestones](milestones.md).

## What must be learned

- Which recurring situations matter enough to justify this device?
- Where can a camera observe useful events without disrupting the home?
- Which languages, response styles, and controls work for intended users?
- What can the perception/retrieval pipeline recover reliably, especially for small objects?
- Who installs and maintains Nyx, and who would choose or pay for it?

Research assignments and evidence standards live in [Research](research/README.md). Boundaries live in [Scope](scope.md).


## Companion slice authorized on 2026-10-20

The user chose two bounded interactions: conversational object finding (including corrections, current inspection and recent history) and a continuing next-departure reminder. A tool-using loop carries requests through observations; continuous inexpensive visual attention can activate work for an existing intention without another spoken question. A fixed camera seeing the main door is the initial departure setting. This is a direction for a useful small demo, not a requirement to solve every household task before testing.

The implementation and its measured failures are recorded in [R8](research/R8-companion-loop.md). Event inference is experimental; scheduled reminders, broad personal recall and intended-user evaluation remain open. Device selection follows measured workload; no purchase is authorized by this slice.


Object-finding feedback should be conversational: a user can say that a proposed
match is wrong, add a distinguishing detail, or change what they are looking for.
The agent uses that feedback to choose the next search or question. Review buttons
are optional shortcuts, not the required way to reject a candidate.
