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

- One local worker runs an agent with at most six decisions and a 90-second budget checked between calls. Already-running inference is not preempted. One invalid decision can receive a correction within the same limit; completion must reference an observation in this request. Tools inspect a fresh view, check bounded recent dated history, widen history, create/list/cancel next-departure requests, clarify or converse. Completed visual answers are drawn from tool results, not free-form final visual claims.
- Planner context contains the last twelve completed turns available in the bounded conversation store, active requests, current time, available inputs, previous actions and compact observations. This is not unlimited conversation memory or general fact recall. Corrections and pronouns can reconstruct descriptive object queries. Deleted source availability remains explicit.
- Present-location requests check an available current view first through an explicit product policy. Historical queries search semantic candidates inside 2/24/168-hour or all-dated windows and check candidates newest-first. This is not exhaustive latest-sighting retrieval. Imported unknown times stay excluded from dated history; a separate best-match tool can check them without claiming a latest sighting. The direct baseline search controls remain available.
- NumPy/Pillow block image differences select initial, changed, pre-change, settled and periodic samples. Continuous ten-second clips each retain their own anchor; no cross-file continuity is inferred. Existing periodic CLI/import behavior remains compatible. Skipped thumbnails are removed before embedding; original video retention and the 1 GiB stop-without-deletion rule are unchanged.
- Live observer accepts bounded fresh chronological camera frames from the active capture session, keeps at most six small images, nominates at most one active model check and resets on pause/session changes/gaps. Semantic checks run only for an armed departure request. The local model receives at most three selected images from a burst. It does not wait for completed segment indexing. Fresh event checks receive interactive queue priority before background indexing, without preempting a running call. No identity recognition is added.
- Intentions and notification attempts are separate durable records. Create retries deduplicate by request ID; cancellation survives restart. Delivery claim is atomic; stale events cannot trigger new requests. Unclaimed expired/restarted notifications become missed; interrupted playback is not acknowledged or silently replayed. Text-only display does not count as spoken delivery. The UI exposes state, cancel and acknowledgement.
- Typed and spoken requests share agent tools. Default configured voice uses Sarvam for activated STT and TTS, with local agent decisions; it no longer needs the cloud intent router. Idle speech and all visuals stay local. No hosted-provider calls were made in these experiments.

## Conversational findings

Artifacts: ignored `data/runs/companion-integrated-001` through `005`, raw generation logs beside results. Runs 001/002 exposed failures and are diagnostic, not success evidence. The first multi-model overlap was stopped; do not use it for timing claims.

Measured run 004:

| Case | Observed outcome | Time after API submission |
| --- | --- | --- |
| Current remote lookup | Fresh snapshot checked; source-backed current answer | 7.62 s |
| “Where did you last see it?” | Resolved remote reference; selected recent dated fixture, not ten-day distractor | 19.60 s |
| Departure request | Persistent next-departure request created and read back | 3.82 s |
| Cancel request | Exact active reminder cancelled | 6.03 s |

Run 005 repeats these workflows with planner prompt version 4: current lookup 9.05 s, recent follow-up 23.34 s, request creation 5.11 s and cancellation 8.73 s. A separate workspace containing only an undated import used `search_matches`, checked the remote at offset 14 s, and explicitly answered with unknown recording time (27.95 s). These are single development trials under the session's actual machine load, not controlled latency comparisons or p95 estimates. They reinforce that historical visual checking still has substantial latency.

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

### Chronological input comparison

The same nine cases and cue-first prompt were also run with explicit time-labelled images and native timestamped video input. Native preprocessing uses the installed Transformers `VideoMetadata`, a two-second relative interval, three selected frames, 640×360 image bounds and 140 generated-token limit; no additional model was downloaded. This follows the supported [Qwen3-VL video interface](https://huggingface.co/docs/transformers/v4.57.1/model_doc/qwen3_vl), with the actual installed runtime still 4.57.6. These are relative replay times, not original capture clock times.

| Representation / artifact | Positive judgments on 3 departure proxies | False positives on 4 negatives | Positives on 2 ambiguous sequences | Observed inference range |
| --- | --- | --- | --- | --- |
| Existing unlabelled images / `departure-sequences-005` | 3 | 3 | 1 | 3.95–5.56 s |
| Time-labelled images / `departure-labelled-001` | 3 | 2 | 1 | 4.02–5.46 s |
| Native video / `departure-native-001` | 2 | 1 | 0 | 3.76–6.03 s |

Native video rejected entry and stationary-doorway cases but still falsely promoted closet activity and missed one exit. Labelled images still overinterpreted entry and bag pickup. No representation met acceptance, and none was promoted to replace the runtime path. Different session load and repeated development cases prevent a controlled speed or general accuracy claim. Native temporal input is a useful next evaluation candidate, not a demonstrated fix.

### Actual live API replay

`companion-live-001`/`002` replay the labelled 3H0PT exit proxy and BM3UJ entry frames two seconds apart, using the actual request, capture-session, observer, local model and persistent notification APIs. They open no camera and disable the voice provider. In run 002 the exit proxy created one pending notification 3.93 s after the final frame; the entering-person case also incorrectly created a pending notification after 4.68 s. This demonstrates a real false trigger in the integrated path. It establishes neither audible delivery nor sufficient advance warning before departure.

Run 001 also exposed an agent error on the second request: it selected `finish` with observation 0 before any tool ran. The new one-correction rule rejected that decision and the repeated run created the requested reminder after repair. Deterministic tests retain the invalid-completion case. This is bounded repair, not a guarantee that small-model decisions are correct.

The event/request/delivery wiring works in deterministic browser scenarios. **Actual departure inference is experimental and has not met an acceptance gate.** Current evidence does not establish a dependable anticipatory reminder: misses, false triggers and inference delay can make it late. Further work should evaluate actual chronological motion/door geometry on independently labelled views, potentially a small person-tracking/event path, rather than treating repeated prompt tuning as validation. Cloud vision is not an authorized fallback.

## Verification and open work

Deterministic checks cover persistence/replay, cancellation, atomic claims, stale data, source deletion, recent versus older evidence, request limits, explicit unsupported reminders and snapshots aging during final planning. Isolated browser checks use generated camera inputs and model doubles. The proactive-speech check also exercises synthetic audio playback, separate user acknowledgement and no repeated claim after acknowledgement. Existing voice smoke uses real local ASR on generated speech; one native-synthesized “Nyx” phrase lost its wake prefix, while a tested “Nicks” pronunciation variant passed the complete check. This is a fixture/pronunciation limitation, not a room-accuracy result.

The first thirty-minute synthetic recording/search phase reached 182 ready captured segments with no indexing failures. Its later deletion check failed because the browser rendered only the newest 50 sources, hiding the older imported clip. It did not finish the full browser scenario or write its performance arrays; `continuous-soak-20261020/INCOMPLETE.txt` records this limitation. `continuous-restart-001` subsequently found all 183 saved sources, returned five semantic candidates and served 100 bytes through HTTP 206 range playback after process restart.

The library now provides **Show older clips**. A 51-source browser regression failed before the fix and passed after it (`library-regression-after-002`). A concurrent heavy-model/browser run hit an acknowledgement UI timeout although SQLite recorded acknowledgement; the isolated repeat passed. Do not treat the failed run as success evidence or claim concurrent responsiveness. The browser harness now saves recording-phase measurements before later lifecycle checks. A corrected thirty-minute repeat is running under `continuous-soak-20261020-002`; append its actual result when complete.

Active requests also remain visible even when older than the thirty-entry recent history, so the browser does not silently stop monitoring a still-armed request. Deterministic persistence tests cover this boundary. Real camera/microphone behavior, speaker echo, independent household and user trials, event recognition quality and latency targets remain open. M1–M5 are not marked complete by these prototype checks.
