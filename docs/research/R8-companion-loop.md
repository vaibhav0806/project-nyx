# R8 — Companion decisions, adaptive observation and event requests

Owner: inline implementation session
Status: in progress; prototype implemented, event-recognition acceptance not met
Date: 2026-10-20
Decisions affected: M3/M4 coordination, bounded M5 departure reminders, R3/R4/R6 follow-ups

## Question and decision

Can the existing local models support an agent that selects tools using conversation and observations, while a cheap continuously enabled visual path nominates moments for an active departure reminder?

The user explicitly authorized implementation, local model/media experiments and coherent local commits, with no push. The target is two complete interactions: conversational object finding and a next-departure water-bottle reminder. Broader personal recall, time-based reminders and hardware purchases are not included.

## Environment and resources

Measured checkout machine: Apple M4 arm64, 16 GiB physical memory, macOS 15.7.3, uv-managed Python 3.12.11. The earlier R3/R4/R6 machine had 24 GiB; its resource measurements must not be attributed to this machine. Reuse locked PyTorch 2.14.1, Transformers 4.57.6 and pinned SigLIP/Qwen revisions from R3/R4. No quantization or new inference framework was needed for sequential checks.

The initial system Python lacked SQLite extension loading; the existing vector suite failed before implementation. Switching to uv-managed Python fixed the environment. At start about 26 GiB disk was available. Model cache is about 6.9 GiB including the pinned wake recognizer; the environment about 1 GiB, and initial public/synthetic artifacts tens of MiB. Two accidentally overlapping Qwen experiment processes caused heavy swap pressure and were terminated; those timings are not accepted as controlled comparisons. Subsequent model checks run sequentially. Preserve disk headroom and do not download entire video datasets.

## Implemented behavior

- One local worker runs an agent with at most six decisions and a 90-second budget checked between calls. Already-running inference is not preempted. Tools inspect a fresh view, check bounded recent dated history, widen history, create/list/cancel next-departure requests, clarify or converse. Completed visual answers are drawn from tool results, not free-form final visual claims.
- Planner context contains the last twelve completed turns available in the bounded conversation store, active requests, current time, available inputs, previous actions and compact observations. This is not unlimited conversation memory or general fact recall. Corrections and pronouns can reconstruct descriptive object queries. Deleted source availability remains explicit.
- Present-location requests check an available current view first through an explicit product policy. Historical queries search semantic candidates inside 2/24/168-hour or all-dated windows and check candidates newest-first. This is not exhaustive latest-sighting retrieval. Imported unknown times stay excluded from dated history. The direct baseline search controls remain available.
- NumPy/Pillow block image differences select initial, changed, pre-change, settled and periodic samples. Continuous ten-second clips each retain their own anchor; no cross-file continuity is inferred. Existing periodic CLI/import behavior remains compatible. Skipped thumbnails are removed before embedding; original video retention and the 1 GiB stop-without-deletion rule are unchanged.
- Live observer accepts bounded fresh chronological camera frames from the active capture session, keeps at most six small images, nominates at most one active model check and resets on pause/session changes/gaps. Semantic checks run only for an armed departure request. The local model receives at most three selected images from a burst. It does not wait for completed segment indexing. No identity recognition is added.
- Intentions and notification attempts are separate durable records. Create retries deduplicate by request ID; cancellation survives restart. Delivery claim is atomic; stale events cannot trigger new requests. Unclaimed expired/restarted notifications become missed; interrupted playback is not acknowledged or silently replayed. Text-only display does not count as spoken delivery. The UI exposes state, cancel and acknowledgement.
- Typed and spoken requests share agent tools. Default configured voice uses Sarvam for activated STT and TTS, with local agent decisions; it no longer needs the cloud intent router. Idle speech and all visuals stay local. No hosted-provider calls were made in these experiments.

## Conversational findings

Artifacts: ignored `data/runs/companion-integrated-001` through `004`, raw generation logs beside results. Runs 001/002 exposed failures and are diagnostic, not success evidence. The first multi-model overlap was stopped; do not use it for timing claims.

Measured run 004:

| Case | Observed outcome | Time after API submission |
| --- | --- | --- |
| Current remote lookup | Fresh snapshot checked; source-backed current answer | 7.62 s |
| “Where did you last see it?” | Resolved remote reference; selected recent dated fixture, not ten-day distractor | 19.60 s |
| Departure request | Persistent next-departure request created and read back | 3.82 s |
| Cancel request | Exact active reminder cancelled | 6.03 s |

Seven direct planner development probes matched their action labels after iteration, including descriptive correction, pronoun resolution, fallback and evidence completion. **Action labels are insufficient:** the bare model still proposed an inappropriate clock-time clarification/promise for a timed reminder. The API now intercepts explicit clock-time reminder requests and explains that scheduled reminders are unsupported. Side-effect tools require an explicit user request and preserve request state on replay. Tests exercise the boundaries with deliberately misrouted model decisions.

The temporal fixture is a composite of permitted public stills. Test copies have deliberately assigned synthetic dates for ordering; they are not claims about original public-image capture time. Snapshot input is a synthetic replay. These examples do not establish glasses/keys accuracy, household temporal recall, target-language quality, p95 latency or a usable older-adult experience.

## Adaptive sampling findings

`data/runs/attention-static-001/results.json`: a 120-second synthetic static clip produced 60 candidates at two-second sampling, of which four were selected (0/30/60/90 s). Extraction plus selection took 0.246 s, excluding encoding. This is a 93.3% candidate reduction for one long clip; production ten-second segments retain an anchor each and usually select one of five static candidates (80% reduction). Do not conflate these scopes.

`data/runs/attention-public-001.json`: eleven staged public indoor clips mostly retained all samples; two clips reduced 11→9 and 15→10. Activity, camera movement and illumination often justifiably prevent deduplication. This is not a meaningful-event recall benchmark. A small synthetic changed region is covered by deterministic before/change/settled tests. Compare OpenCV background subtraction only if these measured tradeoffs warrant another dependency; no OpenCV runtime dependency was added in this slice.

## Departure findings and failures

Sources: selected Charades clips, Sigurdsson et al., [Hollywood in Homes](https://arxiv.org/abs/1604.01753). Official archive URL, exact members, hashes and actual downloaded byte counts are in ignored `data/evaluation/charades-*/sources.json`. The ~16 GB archive was accessed using bounded HTTP ranges; only selected clips and its small annotation archive were downloaded. The dataset license permits evaluation elsewhere and restricts commercial use/redistribution. Keep all raw clips, contact sheets and frames local; they are not reusable public product-demo assets.

Contact sheets were inspected before model classification. Labels distinguish clear room-exit proxies, entry, stationary doorway behavior, closet activity and ambiguous off-camera movement. A room exit is not proof of leaving home; some viewpoints are not a fixed living-room CCTV view. The nine reused sequences are development/diagnostic cases, not independent target-home trials.

Findings:

- Initial prompt copied its literal uncertain example, including on positives. Removing the example produced actual descriptions and positive judgments.
- Run `departure-sequences-003` recognized one of three labelled departure proxies, rejected four labelled negatives, and overinterpreted an ambiguous bag-pickup case. Inference was about 5.3–8.1 s per tested burst. These small counts are not a reliable accuracy estimate.
- A shorter-output prompt (`004`) reduced time to roughly 2.8–3.6 s but introduced stationary/closet false positives. It was not adopted as a quality improvement.
- Structured cue-first output (`005`) exposed another failure: plausible descriptions paired with incorrect positive boolean flags, including an entering person. Requiring fields/schema cannot establish semantic truth. The parser rejects missing/malformed flags and a positive paired with false approach/interaction flags, but cannot detect confidently wrong true flags.
- A separate text-only decision experiment over these captions (`event-decision-001`) removed some positives and some false positives, while retaining other errors. It was **not** added to the runtime; another model step is not automatically better verification.

The event/request/delivery wiring works in deterministic browser scenarios. **Actual departure inference is experimental and has not met an acceptance gate.** Current evidence does not establish a dependable anticipatory reminder: misses, false triggers and inference delay can make it late. Further work should evaluate actual chronological motion/door geometry on independently labelled views, potentially a small person-tracking/event path, rather than treating repeated prompt tuning as validation. Cloud vision is not an authorized fallback.

## Verification and open work

Deterministic checks cover persistence/replay, cancellation, atomic claims, stale data, source deletion, recent versus older evidence, request limits, explicit unsupported reminders and snapshots aging during final planning. Isolated browser checks use generated camera inputs and model doubles. The proactive-speech check also exercises synthetic audio playback, separate user acknowledgement and no repeated claim after acknowledgement. Existing voice smoke uses real local ASR on generated speech; one native-synthesized “Nyx” phrase lost its wake prefix, while a tested “Nicks” pronunciation variant passed the complete check. This is a fixture/pronunciation limitation, not a room-accuracy result.

A thirty-minute synthetic recording/search soak is running; append its actual result when complete. Real camera/microphone behavior, speaker echo, independent household and user trials, event recognition quality and latency targets remain open. M1–M5 are not marked complete by these prototype checks.
