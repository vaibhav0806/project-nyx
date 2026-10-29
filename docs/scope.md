# Scope

## Latest authorization — 2026-10-29

The user authorized merging the companion MVP (completed via PR #1), then working
directly on main on bounded compression/retention MVP work. New recordings may
use a tested lower-bitrate/frame-rate profile. Continuous coverage, existing files
and the 1 GiB stop-without-delete rule remain. No automatic expiry or destructive
recompression. This supersedes older no-merge language for the completed merge;
future publication follows the user's actual instruction.


## Latest authorized exception — 2026-10-28

The user authorized reusing recent saved glasses footage/audio for this fix with
the configured cloud path. Selected frames were tested; originals remain local.
No raw audio archive exists. This exception does not authorize other private media
or developer access to real camera/microphone. Branch publishing was separately
authorized earlier; merging remains unapproved. Captured location statements may
now be retrieved and quoted alongside visual matches, with explicit attribution.


## Current cloud boundary — 2026-10-28

The user approved cloud as the primary MVP path, including OpenRouter reasoning,
vision, multimodal embeddings and activated STT/TTS. This supersedes local-only
visual inference and Sarvam-only language elsewhere in this document. Selected
frames/sequences, bounded conversation context, activated questions and answer
text may reach OpenRouter/model providers. Idle audio and full recording files
remain local. Local wake recognition, activity filtering and the small object
detector remain. Developer tests use synthetic/public fixtures and never open real
hardware; no private household footage is uploaded as part of testing. The supplied
key has a $2 test cap. No push or merge is authorized.


Status: working scope. The user explicitly resumed implementation on 2026-10-19. The first retrieval slice exists; continuous local capture/background retrieval is authorized and implemented. The user has also explicitly authorized M3 temporal retrieval and visual answers; M4 hands-free Sarvam voice is now authorized and implemented as an initial slice; a bounded next-departure action slice was authorized on 2026-10-20.

## First engineering slice

Import a short local video, sample timestamped frames, embed them with a small image/text encoder, store searchable vectors and metadata in SQLite, and display ranked candidate frames with source offsets.

This slice establishes retrieval quality and laptop resource use. Results must be labelled as unverified candidates. It does not yet establish “last seen,” absence, a correct location, or spoken assistance. No live recording or model download is required to review this design.

The current follow-up adds explicitly enabled continuous browser video-only recording, approximately ten-second independently playable segments, automatic local indexing, pause/resume, candidate search during capture and separate source playback. Saved work recovers after server restart. The 1 GiB original-video budget stops capture without deleting existing clips; thumbnails/model cache are additional. Upload failures retain retry/download options while the page remains open. Capture time is unknown for imported media and uncertain interrupted tails. Explicit per-source deletion includes thumbnails/vectors, confirmation and interrupted-cleanup recovery. Automatic expiry remains disabled; retention duration and the thirty-minute real-camera check remain pending.

The current M3 slice adds model-checked historical answers, explicit time bounds/latest ordering, source replay/context and fresh snapshot inspection from an already-enabled camera. Latest answers are bounded to inspected samples with a small older semantic fallback; unknown dates, gaps and unindexed footage remain explicit. Model checks are not guaranteed truth. Snapshots are ephemeral and age-labelled; scheduled reminders and general personal recall remain later work.

## Laptop demo

| Area | Included |
| --- | --- |
| Capture | One camera/view, explicitly enabled continuous local video recording, timestamped segments, pause, gaps, and replay |
| Retrieval | Selected frames/clips indexed for search, candidate ranking, and links to source evidence |
| Interpretation | Fresh inspection and on-demand verification of retrieved candidates; supported landmark guidance |
| Voice | Cloud voice, natural follow-ups, interruptions, microphone controls, and visible conversation state |
| Memory | Durable assistant transcripts, explicitly saved facts, corrections, and source attribution |
| Actions | Simple notes and reminders with interpreted due time, cancellation, and delivery/acknowledgement state |
| Events | Supported scene changes and visits within coverage; user-supplied or confirmed names |
| Controls | Recording indicator, independent microphone mute, history inspection, deletion, retention, and disk cap |
| Evaluation | Real scene tests, uncertain/absent cases, restart recovery, resource measurements, and small intended-user trials |

The proposed development setting is one fixed room/view with five described test objects. This limits evaluation complexity; it does not redefine the long-term product as a desk-object finder. Exact object set and final physical form remain open.

## Recording and memory boundaries

- Video is continuous while recording is enabled. Model analysis is selective and may miss events.
- Store interactions directed to Nyx by default. Archiving all room audio is a separate product decision.
- Keep original recording time separate from import time. An imported clip with unknown capture time has clip offsets and an explicitly unknown wall-clock time.
- Current answers require fresh evidence. Historical answers identify their source time.
- Keep user statements, visual observations, and model inferences distinguishable.
- A failed capture, missing index match, or hidden object does not prove absence or movement.
- Visitor detection alone does not establish identity or intent.
- Source expiry/deletion must propagate to derived thumbnails, vectors, and history entries. Display the actual searchable range.
- The demo has a user-selected 1 GiB original-video budget, stopping without deletion. Manual source-aware deletion is available; retention duration remains open; do not adopt the previous seven-day proposal.
- Cloud voice is acceptable for the prototype. Activated question audio may be sent to Sarvam under the explicit M4 authorization. Idle room audio, images and video remain local; no cloud visual fallback is authorized.

## Hands-free startup and voice boundary

The user explicitly requires automatic camera/microphone startup and activation by “Hey Nyx” or “Nyx,” both in the laptop app and a possible future device. This supersedes the earlier manual-start product choice. The configured page starts capture/listening after browser permissions; loading the server alone does not open browser devices. Tests must use synthetic camera/audio, which is a developer-testing rule, not a product limitation.

The first implementation uses local English ASR-based name detection, bounded ephemeral audio and Sarvam STT/tool routing/TTS after activation. Conversations persist as attributed text and source references. Replies use existing local visual tools, not router-generated facts. Microphone mute and response stop are available. Wake-based playback interruption and a ten-second active follow-up window are implemented with synthetic checks. One speech turn can wait during processing; in-flight inference is not preempted. Robust keyword spotting, actual echo and intended-language/noise evaluation remain open M4 work. Simple greetings and brief conversation bypass vision; visual replies still require local evidence. A next-departure reminder tool is now exposed through the companion loop; timed/recurring reminders remain unsupported.

## Later work

Dedicated hardware follows a working laptop demo and measured resource requirements. Portable capture, multiple cameras, motorized movement, whole-home spatial mapping, smart-home integrations, automatic person identification, and emergency/medical assistance need separate scope and validation.

JEPA research is allowed to inform future temporal features and prediction. It does not block the initial image/text retrieval baseline or imply that arbitrary household next-action prediction already works.

## Completion boundaries

- Documentation prepared is not design approved.
- Design approved is not implementation started.
- Code and deterministic tests are not a real-model benchmark.
- Candidate retrieval is not a verified answer.
- A developer demonstration is not an intended-user trial.
- The laptop demo is not standalone hardware or a deployed product.

Track these states in [Milestones](milestones.md) with evidence.


## Companion/event slice — current authorization

On 2026-10-20 the user authorized conversational tool selection, continuous inexpensive attention and an event-conditioned next-departure reminder. The current local prototype supports typed and spoken requests, contextual query construction, fresh-view checks, bounded recent/history search, correction, cancellation and durable departure requests. Live observation shares the already-running camera and nominates short sequences for local inspection only while a departure request is armed. It does not wait for video segment indexing. A configured page remains necessary; the server cannot open browser hardware.

This is a single-person, fixed-view/main-door experiment. No identity is inferred. A model-positive condition is a fallible inference, not verified departure. Actual public-video checks have misses and false positives; speaking before departure is not established. Show explicit monitoring and delivery states, support cancel/stop, and keep playback separate from acknowledgement. A missed/interrupted event is not automatically replayed after restart. Broader recall, timed/recurring reminders, arbitrary event triggers, interviews, purchases and hardware deployment remain later work. See [R8](research/R8-companion-loop.md).

The temporal follow-up suppresses isolated returned-to-baseline disturbances before
automatic embedding/live inspection, while persistent change can nominate analysis.
Recordings remain complete and independent segments retain anchors/periodic coverage.
Live activity groups into episodes; a separate gate checks the model's exit cues
against eligible active next-departure requests. This is bounded request relevance,
not a general learned event-importance system. Three inspected frames retain exact
timestamps and the whole sequence must follow the request. Entering-person false
triggers remain measured failures. No second reversal-classification call is added.

The user approved this window/action-gate implementation on 2026-10-20 and reaffirmed
that general long-term context/memory is later work. Existing conversation persistence
and bounded recent-turn context remain; no summarization, saved-fact or semantic
conversation-recall layer is added by this follow-up.

The next authorized follow-up separates reusable spatial/temporal evidence from
the one supported action. Exit regions are inferred automatically from the images,
without a fixed doorway rectangle. An independent small object detector supplies
entity positions; generic geometry corroborates direction and can reject standing,
entry or turnback despite a semantic positive. Missing/ambiguous detections abstain.
The authorized continuation uses bounded chronological image-plane tracking with
explicit brief gaps and three observed semantic images. It adds neither identity
recognition nor a home map or arbitrary automatic event understanding. Successive
automatic region estimates are checked for consistency, but an interior doorway can
still be mislabeled. Complete-sequence replay retains misses, a false indoor action
and late notification; recognition and useful-warning gates remain open.

### Guided object-finding MVP

Historical model matches are candidates for user review, not verified identity.
Typed or activated spoken rejection uses the conversational agent; the optional
rejection button uses that same path. The laptop UI can confirm an item in a saved
frame. Confirmations persist as explicitly user-attributed conversation records
with source/time links; source deletion invalidates those links. They do not prove
current location or the latest possible sighting. Voice can ask the review
question, but confirmation currently uses the UI button. Automated identity
matching among similar objects and intended-user household validation remain
open. Camera snapshots remain ephemeral.


## MVP wrap-up — 2026-10-28

The immediate demonstration focuses on guided conversational object finding,
including current inspection, correction, dated history and user review.
Departure reminders remain available as experimental functionality, outside the
dependable MVP promise. See the [demo runbook](mvp-demo.md) and canonical milestones
for measured evidence and remaining real-room validation.
