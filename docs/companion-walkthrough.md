# How the current Nyx companion works

Nyx is being built as a physical companion that helps people stay independent as they age. The laptop is the development setting. The current slice concentrates on two interactions: finding an object through conversation, and remembering a request to speak at the next departure.

## Asking a question

```mermaid
flowchart LR
    A[Typed or activated spoken question] --> B[Local agent with recent conversation]
    B --> C{Choose a tool}
    C --> D[Inspect a fresh camera snapshot]
    C --> E[Search recent dated recordings]
    C --> F[Check matching imported footage]
    D --> G[Model judgment with source and time]
    E --> G
    F --> G
    G --> B
    B --> H[Answer from a tool result or ask for clarification]
```

For “Where are my glasses?”, Nyx first checks an available fresh view. If that does not confirm them, the agent can search recent history and widen the time window. “The thin silver reading ones” can refine the query using recent conversation. “Where did you last see them?” can choose historical search directly.

The search encoder compares a text description with indexed visual samples. A close embedding match is only a candidate. The local vision model then checks candidates. Even a model-confirmed result can be wrong, so the answer retains its recording time, source and uncertainty. Unknown dates remain unknown; a matching imported clip cannot establish the latest sighting. No image/audio embedding alignment is required for spoken questions: activated speech is transcribed to text before these tools run.

The agent has a maximum of six decisions. It sees twelve recent completed turns and compact tool results. It does not currently have an unlimited life history or a general saved-fact memory. A previous assistant answer is not fresh visual evidence.

The loop is custom Python, without LangChain. Up to two invalid-decision repairs fit
inside the existing six-decision budget. Repeated identical history queries advance
to the next unused wider window; a revised query can still search the same window.
Current follow-ups such as “Is it still there?” require a fresh view when available;
explicit last-sighting requests use history. Policy adjustments persist in the trace.

## Watching without constant commentary

While recording is enabled, full video segments save locally. Cheap dense observations
pass through a temporal window before frames are embedded. A 0.1-second flash returning
to the original scene is suppressed; a fast placement leaving a lasting change can
qualify. Selected frames preserve before/during/settled evidence and periodic coverage.
Every independent segment retains an anchor, so brief disturbances can still appear
in anchor/periodic samples. Skipping a sample does not prove nothing happened.

A separate live observer uses small recent frames from the same camera. It does not wait for a saved segment to finish indexing. It checks departure cues with the heavier local model only when a departure reminder is armed. A camera change, pause or stale sequence invalidates that burst.

Unchanged or isolated short disturbances skip the model. The first-pass policy needs
at least three observations spanning 0.5 seconds of persistent change; 0.8 seconds of
quiet closes an episode, and a gap over 0.5 seconds resets continuity. Live sampling
targets ten observations per second. Qualified activity can be inspected before it
settles. Continuing activity can be rechecked after three seconds with further change;
a busy worker does not consume a nomination before admission.

For a nominated burst, the first, middle and last frames are the exact images named
in event evidence. A separate action gate checks temporal qualification, model exit
cues and eligible active requests. The complete sequence must come after the request;
the tail of an older event cannot satisfy a new reminder. Pixel change does not
establish meaning, and the model's interpretation can still be wrong.

The grounded-event follow-up adds independent entity positions. A small detector
checks the nominated images; ambiguous/missing people or unsupported translation
skip heavier semantic interpretation. Qwen then attempts to locate the visible
home exit. Generic geometry computes movement toward/away from that region,
stationary positions and reversals. Direction must support the semantic exit cues
before an active request can trigger. Region coordinates come from the images,
without a predefined door location or bottle-specific rule. No personal identity
or 3D physical distance is inferred. These evidence components can serve future
conditions, but only next-departure requests are currently wired as actions.

Real replay blocked an entering-person false claim using observed movement away
from the door. It also missed an exit because of sparse detector gaps. Automatic
exit labels can still be wrong; [R8](research/R8-companion-loop.md) records both.

## Remembering to act

```mermaid
flowchart LR
    A[Remind me to take water when I leave] --> B[Saved next-departure request]
    B --> C[Fresh live sequence checked locally]
    C --> D{Departure inferred?}
    D -->|Unclear| C
    D -->|Yes| E[One pending notification]
    E --> F[Claim and attempt speech]
    F --> G[Played, failed or interrupted]
    G --> H[Separate user acknowledgement]
```

The request survives a restart. Its condition is an observed event, not a clock schedule. Cancel stops future delivery. Displaying text does not count as speaking, and playing speech does not count as the user acknowledging it. Old events are marked missed or interrupted rather than silently replayed after restart.

**The plumbing works, but departure recognition is currently unreliable.** Public-video development cases include missed exits, false triggers and delays. This feature is experimental; a small VLM correctly formatting JSON does not make its interpretation correct. It also does not identify which household member is leaving.

## Where the state lives

| State | Purpose |
| --- | --- |
| Original clips and `capture.sqlite3` | Saved media, segment times, recording interruptions and recovery |
| `index.sqlite3` and selected thumbnails | Searchable sampled observations, offsets, encoder identity and vectors |
| Ephemeral live buffer | At most 64 small frames and six seconds of recent context; three frames per model check; no permanent live-frame archive |
| `conversations.sqlite3` | User/assistant conversation, chosen tools and source references |
| `intentions.sqlite3` | Requested next-departure tasks, notification attempts and acknowledgement state |

`agent.py` chooses actions; `companion.py` connects them to the app. `retrieval.py` and `answers.py` retrieve/check evidence. `attention.py` selects samples, `observation.py` bounds live sequences, and `intentions.py` persists requests and delivery state. They share one local inference worker. Fresh event checks and interactive requests precede queued background indexing; a model call already running cannot be preempted.

Visual processing and media stay local. Optional Sarvam handles activated speech transcription and response synthesis. Without a key, typed conversation still works. A running permitted browser page is required for camera/microphone observation; starting the Python process alone opens no hardware.

See [milestones](milestones.md) for actual status, [R8](research/R8-companion-loop.md) for measurements and failures, and [the README](../README.md) for running the demo. General personal recall, timed/recurring reminders, reliable household event recognition and hardware validation remain open.
