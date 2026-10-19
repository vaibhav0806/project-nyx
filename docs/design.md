# Product design

Status: working design, 2026-10-19; the user reviewed the package and resumed the first implementation milestone. Product intent comes from the working discussion and approved application pitch; implementation choices are tracked separately in [Decisions](decisions.md).

## Mission

Nyx exists to extend the years people can live with agency, dignity, and independence.

We’re building a personal AI companion that sees, listens, and remembers, so people can keep living on their own terms as they age. Older adults living at home are the starting audience. The prototype runs on a laptop before dedicated hardware.

## Experience

The person speaks naturally to Nyx about their surroundings, past events, earlier conversations, or something they want to remember or do. Nyx uses the relevant evidence and responds aloud. Follow-up questions carry context across a conversation; durable memory carries useful information across sessions.

| Situation | Intended behavior |
| --- | --- |
| “Where are my glasses?” | Inspect a fresh view and describe a supported location using landmarks. Clarify if multiple pairs are ambiguous. |
| “Where did you last see them?” | Search retained history, verify candidate sightings, and return a timestamped source moment. |
| “Did someone come by this afternoon?” | Retrieve supported visit events within camera coverage; name a person only from supplied or confirmed identity information. |
| “What did I ask you yesterday?” | Retrieve the relevant assistant conversation with its time and source. |
| “Remember that the documents are in the blue drawer.” | Save an attributed fact, allow correction, and retrieve it in a later session. |
| “Remind me to call my daughter at six.” | Resolve the intended time, read it back, save the reminder, and report its actual delivery state. |

These are full-product design scenarios. The current repository demonstrates recorded-frame candidate retrieval only. Final workflow priorities and preferred language need research with intended users.

## Product principles

**Independence:** support the person's choices and daily routines. Test the experience with older adults themselves; relatives' feedback complements their perspective.

**Conversation:** voice is the main interaction. Keep answers short enough to act on, support clarification, and make interruption possible. The browser interface exists for setup, controls, evidence inspection, and development.

**Grounded memory:** connect answers to what Nyx saw, heard in an assistant interaction, or was explicitly told. Keep these source types distinct. Similarity search finds candidates; verification establishes what an answer can claim.

**Continuity:** persist useful history, conversations, saved facts, and reminders across sessions and restarts. Show actual retained coverage and gaps.

**Control:** recording is explicitly enabled and visibly indicated. Provide microphone mute, recording pause, inspection, deletion, and storage limits as part of the experience.

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
