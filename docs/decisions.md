# Decisions and open choices

Updated: 2026-10-19. This records discussion outcomes and engineering choices. The user explicitly resumed work on 2026-10-19; M1 retrieval and continuous recording/background indexing are authorized. Unmeasured model choices remain experiments.

## Status vocabulary

- **Established:** explicitly supplied or accepted in the discussion.
- **Proposed:** recommendation awaiting review or measurement.
- **Open:** an answer is still needed; record what will resolve it.
- **Superseded:** retained for traceability; no longer the working direction.

## Established direction

| ID | Decision | Basis |
| --- | --- | --- |
| D1 | Mission: extend agency, dignity, and independence as people age; start with older adults at home. | User clarification and approved pitch. |
| D2 | First target is a good laptop demo; standalone hardware follows. | Explicit user direction. |
| D3 | Product includes enabled continuous video recording, live inspection, searchable history, conversation/fact recall, and reminders. | User's feature notes and subsequent scope discussion. |
| D4 | Cloud voice is acceptable; explore local vision. Full offline operation is not required for this prototype. | Explicit user answer. |
| D5 | Investigate a light background perception/retrieval path and on-demand interpretation; keep JEPA research distinct from the retrieval baseline. | Working direction discussed with the user and teammate; exact model remains open. |
| D6 | Resume M1 local visual retrieval after the documentation review. | User explicitly requested “continue working now” on 2026-10-19; supersedes the earlier pause. |
| D8 | Stop continuous recording at a 1 GiB saved original-video budget; preserve existing clips. | Explicit user selection on 2026-10-19. |
| D7 | Work inline; no subagents without explicit user request. | User's personal rules. |

## Proposed technical choices

| ID | Proposal | Why / what must be checked |
| --- | --- | --- |
| P1 | One Python package in `src/nyx/`, with a small browser interface. | Running baseline: packaged plain browser assets; continuous capture now uses the same packaged browser stack. |
| P2 | Python 3.12, uv, FastAPI. | Dependencies installed/locked and validated for the bounded manual interface. |
| P3 | SQLite plus `sqlite-vec`, with original media on disk. | Keep timestamps, sources, vectors, facts and actions local; verify extension support and retrieval behavior. |
| P4 | Small aligned image/text encoder for the first retrieval baseline. | Enables descriptive-query retrieval; compare real small-object scenes before selecting a checkpoint. |
| P5 | Local small VLM for on-demand inspection/verification. | Keep heavier analysis selective; measure quality, latency and working memory. |
| P6 | Fixed-camera, one-room development setting with five described test objects. | Makes evaluation repeatable; final form and coverage need review. |
| P7 | Start with explicit memories and transcript retrieval; introduce a framework or extra indexing only when needed. | Avoid untested memory behavior and additional infrastructure. |

## Open choices

| ID | Question | Resolve through |
| --- | --- | --- |
| O1 | Which three daily-life workflows matter most to intended users? | R1 interviews and role-play. |
| O2 | Preferred language, interaction style, and installation/maintenance needs? | R1/R2 research. |
| O3 | Camera placement, acceptable recording coverage, retention duration and identity handling? (Demo video budget: D8.) | Product review plus R2 findings. |
| O4 | Encoder checkpoint, preprocessing, sampling/crop strategy, and retrieval thresholds? | R3 measured baseline. |
| O5 | VLM checkpoint/runtime and verification quality on retrieved candidates? | R4 measured comparison. |
| O6 | JEPA's useful contribution, Mac compatibility, and prediction task/data requirements? | R5 experiment. |
| O7 | Sarvam selected; target-language performance, interruptions, and tool latency remain open. | R6 trial. |
| O8 | Long-run capture reliability and retention/deletion controls beyond the current continuous slice? | M2 hardware soak and product review; current stack is selected below. |
| O9 | Dedicated hardware and standalone operating budget? | Measured laptop workload, then M7. |

## Superseded assumptions

- Desk object-finding as the full product: the desk is now a development setting within a broader independence mission.
- Cloud vision as the default: the current preference is local vision exploration and cloud voice. Cloud image processing needs its own decision.
- Voice-first implementation order: the next proposed technical experiment proves visual retrieval before voice integration.
- Snapshot-only history and no raw video: the user's scope explicitly includes recording while enabled, with selective indexing.
- Seven-day retention as a settled default: retention and capacity remain open.
- An implementation-ready API/file layout from the earlier generated plans: those details were drafts and must not dictate the design review.

## Recording a new decision

Add a row or short entry with: ID, date, status, decision owner, choice, alternatives considered, supporting evidence, tradeoff, and trigger for revisiting it. Update affected documents and link the relevant research finding. Only mark a proposal established when the user actually accepts it; only mark benchmark claims measured when a result exists.

## M1 implementation selections

- Python 3.12/uv and `src/nyx/` are the running baseline. Vision dependencies are optional; no API/UI framework is needed for the CLI slice.
- SigLIP 2 base at checkpoint `75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2` through PyTorch/Transformers is the first measured encoder. MPS inference works on this machine. This does not close the model-selection question.
- SQLite plus `sqlite-vec` cosine distance provides exact candidate ranking with metadata filters. No ANN scalability claim is made.
- A generated HTML candidate gallery is sufficient for M1 inspection. Live capture, browser interaction, VLM verification and voice remain separate work.
- Only permitted public reference images and synthetic fixtures were used. No live camera, household-media upload, cloud voice, interviews, or purchases were performed.

## Earlier manual interface implementation selections

2026-10-19, engineering calls following the user's request to continue and confirmation that no existing clip is available:

- Start the bounded M2 manual interface to enable M1 household evaluation; both milestones remain in progress. This does not waive the independent-evaluation gate for continuous recording.
- Use optional FastAPI/Uvicorn with packaged plain browser assets. A single local process and inference worker are sufficient; no React/build system or provider abstraction is needed. This refines the proposed root `web/` layout to `src/nyx/web/` so installed packages include the UI. Revisit when actual frontend complexity warrants it.
- Browser capture is video-only, opt-in, maximum two minutes, followed by explicit index/discard. Imported wall-clock time remains unknown; browser capture time uses the browser clock. Stop on track interruption or tab hiding instead of claiming continuous coverage.
- Keep the existing full-frame encoder default: the five-view crop experiment adds work without improving recall@3/@5 on the correlated smoke fixture. Revisit with independent household labels.
- Serve only localhost; source IDs resolve registered evidence and support range playback. Job status is ephemeral and does not imply durable restart recovery. No cloud-media fallback is introduced.

## Continuous recording implementation selections

2026-10-19, following the user's successful manual retrieval demonstration, explicit request to start and 1 GiB budget selection. This supersedes the manual-only boundary above; household accuracy evaluation remains open.

- Keep FastAPI, packaged plain browser assets and the pinned local encoder. Record independent approximately ten-second files and automatically save/index them; do not treat arbitrary MediaRecorder timeslices as playable files.
- Persist capture sessions/segments/events in `capture.sqlite3` separately from the embedding index. Stable segment IDs and staged atomic saves permit idempotent retries and recovery. Preserve saved sources even if a model fails.
- Advance one inference worker in two-image batches; prioritize queued search between them. This bounds contention without introducing another model copy or service. Long model load/decode calls remain nonpreemptible.
- Bound server pending segments to eight; stop browser capture on backpressure or save failure. Keep pending blobs for retry/download only while the page survives. Saved/searchable times and interruptions remain separate from camera-on state.
- Stop at 1 GiB original-video storage without deleting clips. Existing imports count; model cache/thumbnails are additional. Retention duration remains pending; explicit source-aware deletion is implemented in the follow-up below. Revisit sampling/segmentation/limits after a thirty-minute real-camera run and independent household evaluation.
- Do not auto-resume capture after restart. Interrupted tails have unknown wall-clock time while clip offsets remain searchable; hidden-tab recording and real sleep behavior still require hardware evaluation.
- The user requested the pre-automatic-indexing snapshot on GitHub: manual baseline `67fcaf5` is pushed to `main`. The user subsequently tested automatic indexing for 2–3 minutes and explicitly requested this continuous slice be pushed to `main`.

## History control implementation selections

2026-10-19, following the user's request to publish automatic indexing and proceed with next milestone work:

- Publish the tested continuous-indexing slice as `8356aa8` on `main`. Work on the next slice stays on `feat/history-controls` until separately published.
- Add explicit deletion of one source and its derived thumbnails/vectors, with confirmation. Require capture stopped and active inference/upload work finished; this simpler conflict boundary avoids introducing cancellation into the current worker.
- Keep durable deletion intent and ID tombstones in the existing capture journal. Finish interrupted cleanup before requeueing saved work; a retried deleted segment must never reappear. Do not load a vision model to delete footage. Preserve unrelated recordings.
- Preserve increasing frame IDs in SQLite metadata so old thumbnail URLs cannot alias new evidence, including for preexisting indexes. Database free pages/previous downloads are not securely erased.
- Add optional synthetic recording duration with backlog, server-process RSS and periodic search timings. These measurements exclude the browser/FFmpeg and do not close actual-camera or household-accuracy gates. Retention duration remains open and no automatic deletion is enabled.

## M3 implementation selections

2026-10-19, user explicitly requested M3 after discussing retrieval with temporal context:

- Keep the existing Python/MPS stack. Use Qwen3-VL-2B-Instruct at revision `89644892e4d85e24eaac8bacfd4f463576704203` as the initial on-demand checker after the [R4](research/R4-local-verification.md) smoke comparison. Keep SigLIP 2 for retrieval. SmolVLM-500M was benchmarked, not enabled as a fallback; its prompt/schema result does not establish general visual incapability.
- Require Transformers >=4.57.1 for the native Qwen3-VL path; the lock retains tested 4.57.6. No new inference framework or provider abstraction is added.
- Use explicit object/mode/date controls first. Date ordering uses capture start plus decoded offset, never import time. Latest answers cover checked samples only: twelve recent dated frames, with up to five semantic fallback candidates if needed. Full archive recall and natural-language temporal/event reasoning remain open.
- Keep source-linked neighbors as unverified context inside the selected time bounds. Inspect original source frames with the VLM; keep ambiguous/invalid responses uncertain. Landmark text is fallible model output, not independently validated guidance.
- Inspect current view only from an explicit snapshot of an already-enabled camera. Validate time at input, queue exit and model-load completion; display capture time and age. Retain snapshot evidence only in bounded ephemeral job results. Source deletion invalidates affected historical answer jobs.
- Preserve pending M2 history-control changes alongside M3 locally; the GitHub `main` publication remains the authorized continuous-indexing snapshot `8356aa8`. Neither this M3 work nor the history-controls follow-up is implicitly published.

## M4 hands-free voice selections

2026-10-19, user chose Sarvam, supplied credentials and explicitly rejected push-to-talk:

- The product starts camera/microphone with the app or future device and wakes to its name, like Alexa/Siri. This supersedes the previous manual-start/no-auto-resume browser choice. Browser permission/autoplay restrictions are visible recovery states. Automated developer tests use synthetic inputs only; that rule does not change product operation.
- The user subsequently explicitly selected v4 for both speech models. Use existing local visual tools, Sarvam STT (`saaras:v4`), constrained tool routing (`sarvam-105b`, reasoning disabled) and TTS (`bulbul:v4-flash`, now the companion persona). No cloud vision or ambient cloud stream. Credentials are loaded from ignored private `.env` by uv.
- Start with pinned faster-whisper tiny.en CPU/int8 for local utterance-based wake recognition. This can miss or falsely hear the name; it is not a production custom keyword model. Revisit after actual pronunciation/noise measurements. Keep raw audio bounded and ephemeral; video remains video-only.
- Keep plain browser audio and local HTTP transport. One microphone lease, bounded requests, generation cancellation, independent mute and visible transcripts are sufficient for this slice. The initial version paused listening during answers; the feedback follow-up below supersedes that behavior.
- Persist conversation text/tool context/source references in a separate SQLite file. Source deletion marks dependent references unavailable. Conversations are never asserted as fresh visual evidence; raw audio is not retained. Transcript deletion UI remains open.
- [R6](research/R6-handsfree-voice.md) records synthetic/provider evidence and cold integrated latency. The M4 latency and intended-language/user gates remain open. M2/M3/M4 changes remain local until separately published.

### M4 response to voice validation feedback

The user reported missed wake calls, slow reactions and “what’s up?” being treated as an object. Inspection confirmed a visual-only router, fixed speech threshold and unconditional audio discarding while busy/playback. The authorized fix adds a separate conversational intent, a fast common-greeting path after STT, concise evidence-derived spoken answers, Shubh's companion persona, local wake probing during speech/playback, bounded pending audio during processing, and a visible ten-second follow-up window. Idle audio outside activation stays local; activated follow-up speech may reach Sarvam. Existing evidence details remain on screen. Low-priority visual model preload moves cold loading to configured startup. Actual-room wake/echo and p95 latency remain unvalidated.

Keep tiny.en: a small synthetic comparison did not justify switching to base.en, which missed more wake prefixes and was slower on these clips. This is an experiment result, not proof of real-room reliability. The wire routing schema uses strings (empty for absent fields), normalized to internal nulls: live probes with nullable fields returned empty/clarification plans for valid questions, while the revised schema routed the exercised questions correctly. See [R6](research/R6-handsfree-voice.md).

## Publication authorization

2026-10-19: the user explicitly requested that all current work be pushed to GitHub. Publish the combined history controls, visual answers, hands-free Sarvam v4 voice and voice-feedback improvements on `main`. Earlier local-only entries above record development checkpoints and are superseded by this explicit publication request. Keep credentials, recordings, databases, generated artifacts and model weights outside Git. Publishing does not close the remaining M1–M4 validation gates or implement M5.
