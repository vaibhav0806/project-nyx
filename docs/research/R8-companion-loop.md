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

Artifacts: ignored `data/runs/companion-integrated-001` through `006`, raw generation logs beside results. Runs 001/002 exposed failures and are diagnostic, not success evidence. The first multi-model overlap was stopped; do not use it for timing claims.

Measured run 004:

| Case | Observed outcome | Time after API submission |
| --- | --- | --- |
| Current remote lookup | Fresh snapshot checked; source-backed current answer | 7.62 s |
| “Where did you last see it?” | Resolved remote reference; selected recent dated fixture, not ten-day distractor | 19.60 s |
| Departure request | Persistent next-departure request created and read back | 3.82 s |
| Cancel request | Exact active reminder cancelled | 6.03 s |

Run 005 repeats these workflows with planner prompt version 4: current lookup 9.05 s, recent follow-up 23.34 s, request creation 5.11 s and cancellation 8.73 s. A separate workspace containing only an undated import used `search_matches`, checked the remote at offset 14 s, and explicitly answered with unknown recording time (27.95 s). These are single development trials under the session's actual machine load, not controlled latency comparisons or p95 estimates. They reinforce that historical visual checking still has substantial latency.

Planner version 5 removes a redundant generation after a completed tool result: the existing single-task completion policy selects that authoritative observation directly. Uncertain observations still go through the model for further tool selection. Run 006 passed the same five workflows: current 8.31 s, recent history 18.55 s, request 3.09 s, cancellation 5.43 s and unknown-date match 7.73 s. Recorded planner JSON generations decreased from 18 to 12 across this particular set of direct probes and workflows. Visual generations are separate. Machine load differs, so the elapsed-time differences are not a controlled speedup claim; visual-answer latency remains open.

Seven direct planner development probes matched their action labels after iteration, including descriptive correction, pronoun resolution, fallback and evidence completion. **Action labels are insufficient:** the bare model still proposed an inappropriate clock-time clarification/promise for a timed reminder. The API now intercepts explicit clock-time reminder requests and explains that scheduled reminders are unsupported. Side-effect tools require an explicit user request and preserve request state on replay. Tests exercise the boundaries with deliberately misrouted model decisions.

The temporal fixture is a composite of permitted public stills. Test copies have deliberately assigned synthetic dates for ordering; they are not claims about original public-image capture time. Snapshot input is a synthetic replay. These examples do not establish glasses/keys accuracy, household temporal recall, target-language quality, p95 latency or a usable older-adult experience.

## Adaptive sampling findings

`data/runs/attention-static-001/results.json`: a 120-second synthetic static clip produced 60 candidates at two-second sampling, of which four were selected (0/30/60/90 s). Extraction plus selection took 0.246 s, excluding encoding. This is a 93.3% candidate reduction for one long clip; production ten-second segments retain an anchor each and usually select one of five static candidates (80% reduction). Do not conflate these scopes.

`data/runs/attention-public-001.json`: eleven staged public indoor clips mostly retained all samples; two clips reduced 11→9 and 15→10. Activity, camera movement and illumination often justifiably prevent deduplication. This is not a meaningful-event recall benchmark. A small synthetic changed region is covered by deterministic before/change/settled tests. Compare OpenCV background subtraction only if these measured tradeoffs warrant another dependency; no OpenCV runtime dependency was added in this slice.

## Departure findings and failures

Sources: selected Charades clips, Sigurdsson et al., [Hollywood in Homes](https://arxiv.org/abs/1604.01753). Official archive URL, exact members, hashes and actual downloaded byte counts are in ignored `data/evaluation/charades-*/sources.json`. The ~16 GB archive was accessed using bounded HTTP ranges; only selected clips and its small annotation archive were downloaded. The dataset license permits evaluation elsewhere and restricts commercial use/redistribution. Keep all raw clips, contact sheets and frames local; they are not reusable public product-demo assets.

Contact sheets were inspected before model classification. Development labels were assigned in this session, not by independent household annotators. Labels distinguish clear room-exit proxies, entry, stationary doorway behavior, closet activity and ambiguous off-camera movement. A room exit is not proof of leaving home; some viewpoints are not a fixed living-room CCTV view. The nine reused sequences are development/diagnostic cases, not independent target-home trials.

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

Initial completed implementation suite: **152 passed**, with lint, formatting and JavaScript syntax checks passing. The final offline wheel build (`package-check-final-001`) contains the new modules and browser assets, with ten key files byte-checked against current source. `delivery-outcomes-002` also passed a simulated browser playback denial: it reported failed delivery, while normal playback and separate acknowledgement still worked. These checks use provider/model doubles and do not establish actual Sarvam or browser permission behavior. The follow-up below records newer checks.

Deterministic checks cover persistence/replay, cancellation, atomic claims, stale data, source deletion, recent versus older evidence, request limits, explicit unsupported reminders and snapshots aging during final planning. Isolated browser checks use generated camera inputs and model doubles. The proactive-speech check also exercises synthetic audio playback, separate user acknowledgement and no repeated claim after acknowledgement. Existing voice smoke uses real local ASR on generated speech; one native-synthesized “Nyx” phrase lost its wake prefix, while a tested “Nicks” pronunciation variant passed the complete check. This is a fixture/pronunciation limitation, not a room-accuracy result.

The first thirty-minute synthetic recording/search exercise had 182 ready captured segments before its later deletion failure, with no indexing failures. Deletion failed because the browser rendered only the newest 50 sources, hiding the older imported clip. It did not finish the full browser scenario or write its performance arrays; `continuous-soak-20261020/INCOMPLETE.txt` records this limitation. `continuous-restart-001` subsequently found all 183 saved sources, returned five semantic candidates and served 100 bytes through HTTP 206 range playback after process restart.

The library now provides **Show older clips**. A 51-source browser regression failed before the fix and passed after it (`library-regression-after-002`). A concurrent heavy-model/browser run hit an acknowledgement UI timeout although SQLite recorded acknowledgement; the isolated repeat passed. Do not treat the failed run as success evidence or claim concurrent responsiveness. The browser harness now saves recording-phase measurements before later lifecycle checks.

### Completed recording phase and separate lifecycle verification

`continuous-soak-20261020-002/recording-results.json` records the completed 1800.04-second phase: 179 indexed captured segments, no indexing failures, 112 repeated candidate searches, and a maximum observed indexing backlog of one. Browser search round-trip median was 0.325 s, p95 with the lower empirical quantile method 1.154 s and maximum 3.971 s. These are candidate-search UI checks, not vision-checked answers. The originals occupied 5.02 MiB including the imported fixture; alternating synthetic canvas frames compress unusually well, so this does not estimate household retention duration. Server-process RSS samples ranged 36.1–594.2 MiB; these exclude browser, FFmpeg, GPU accounting and other system memory.

The subsequent lifecycle script over-clicked the asynchronous pagination control and waited for an already-hidden button. This was a harness synchronization failure; the whole thirty-minute browser script did not pass. It now waits for additional rows after each click. Follow-up `continuous-restart-002` verified the retained large library: all 182 sources survived restart, search/range playback worked, cancelled deletion preserved the import, confirmed deletion removed that synthetic import while retaining the other 181 sources, and reload/mobile checks passed. `continuous-lifecycle-final-001` separately passed the complete short capture/search/pause/resume/interruption/deletion/reload scenario. `delivery-pagination-final-001` passed three-page access to 151 synthetic library entries together with cancellation, playback denial, normal delivery and acknowledgement. Keep these outcomes separate from the failed long harness's overall status.

Active requests also remain visible even when older than the thirty-entry recent history, so the browser does not silently stop monitoring a still-armed request. Deterministic persistence tests cover this boundary. Real camera/microphone behavior, speaker echo, independent household and user trials, event recognition quality and latency targets remain open. M1–M5 are not marked complete by these prototype checks.

A delayed-response browser regression (`late-delivery-before-001`) reproduced cancellation succeeding while an already-produced audio response was still in transit, followed by unwanted playback. The browser now invalidates a pending delivery on local cancellation, Stop, observed cross-tab cancellation, camera stop, new question or wake interruption. `late-delivery-after-001` passed: the cancelled response started no audio, a subsequent request played once, and acknowledgement remained separate. This does not claim instantaneous knowledge of cancellation in another browser before its updated state arrives.

Final `companion-voice-final-001` passed the isolated full voice/browser scenario with real local wake ASR on generated speech, deterministic agent/visual boundaries and mocked Sarvam. It checked wake interruption during playback, a retained utterance while busy, microphone mute/late permission cleanup, recording stop and persisted conversation reload. No real camera/microphone, room echo or hosted provider was exercised.

## Departure follow-up — 2026-10-20

**Question:** Can a small temporal consistency check remove false triggers while
retaining the existing exit examples? Separately, can event admission avoid old or
unchanged evidence without adding a model? A successful reversal check would justify
evaluating a second-stage gate; losing exits or retaining false triggers rejects it.

**Method:** Same nine reused development sequences, chronological images then the
same images reversed, identical pinned Qwen/checkpoint/prompt and greedy generation.
No new data, independent labels, hardware or provider calls. Command:

```sh
HF_HUB_OFFLINE=1 uv run --no-sync python experiments/companion/departure.py \
  --manifest data/evaluation/departure-manifest.json --reverse-check \
  --output data/runs/departure-direction-001
```

Runtime: same M4/16 GiB/macOS 15.7.3, Python 3.12.11, PyTorch 2.14.1,
Transformers 4.57.6, Pillow 12.3.0 and NumPy 2.5.4. Inputs/prompt are unchanged from
`departure-sequences-005`. Raw generations and results remain local. Later cases
slowed substantially under memory pressure; timings are not a controlled comparison.

| Development label | Cases | Forward positives | Reversed positives | Forward-positive/reversed-clear-negative |
| --- | --- | --- | --- | --- |
| Room-exit proxy | 3 | 3 | 2 | 1 |
| Negative | 4 | 3 | 2 | 1 |
| Ambiguous | 2 | 1 | 1 | 0 |

**Measured:** The hypothetical reversal gate loses two exit proxies while retaining
the stationary-doorway false positive. Entry and closet activity are incorrectly
positive in both directions. **Recommendation:** reject the extra runtime generation;
scene plausibility and consistent JSON do not establish temporal direction.

### Implemented resource and event-boundary fixes

- An unchanged initial burst previously invoked the model, and periodic nominations
  could do so again. Live inspection now requires observable change relative to its
  anchor, using existing block/mean thresholds. This also catches controlled slow
  cumulative changes that individually fall below the adjacent-frame threshold.
  Original recording and historical periodic coverage remain unchanged.
- The live buffer passed up to six images/timestamps while Qwen silently selected
  three images. Selection now happens in the observer, before inference, so event
  evidence names exactly the first/middle/last inspected images and times.
- Checking only the last frame's time let a reminder use an event that started before
  the request. Full sequence time validation now leaves that request armed; an older
  eligible request can still trigger. Malformed/unordered times or an event timestamp
  disagreeing with the final frame cannot claim a delivery. Existing point-event
  callers without sequence evidence retain their point-time check.

These regressions failed before their fixes. **163 tests pass**, including a
two-minute simulated quiet sequence spanning periodic nominations and subsequent
resumption on change. This is a replay-clock test, not two minutes of real hardware.
`departure-hardening-browser-001` passes generated-camera speech cancellation,
normal playback, acknowledgement, denied playback, source pagination and controls;
model/provider boundaries remain deterministic doubles. Lint/format checks pass.

`departure-motion-gate-001/results.json`, generated by the documented `motion.py`
command, admits all nine public sequences and correctly handles four controlled
static/noise/cumulative/local-change inputs. Per-sequence gate time was approximately
0.2–4.6 ms in these individual measurements. It saves quiet-scene inference but removes
none of the moving public false positives. Thresholds can miss subtle real activity;
this is not a semantic classifier or a validated event-recall benchmark.

The separate `departure-hardening-live-001` API replay encountered heavy system memory
pressure. The exit-proxy and entering-person checks finished about 40.0 and 33.3 seconds
after their final frames. Both model outputs were positive, and both freshness checks
rejected the stale evidence without creating notifications; each request remained
armed until experiment cleanup. This is failure/resource evidence, not successful
anticipatory assistance or a recognition fix. No other applications were stopped and
no stale-evidence threshold was relaxed. Resource optimization is deferred in favor
of functionality, following the user's clarification.

**Next recognition question:** compare explicit exit geometry plus chronological
person motion with the current VLM on independently labelled fixed-camera sequences.
The present work does not establish departure reliability, lower visual-answer p95,
real-camera behavior or audible warning before an exit. M3–M5 remain in progress.

## Temporal window and stronger conversation checks — 2026-10-20

The user approved the temporal-window/action-gate approach and requested execution,
while deferring general long-term memory. The implementation keeps the existing
models, runtime and local-media boundary. No new model, framework, hosted call or
hardware capture was used. Runtime/checkpoints remain as listed above.

### Window method and decision

**Hypothesis:** elapsed-time persistence should suppress a controlled 0.1 s disturbance
returning to the baseline while preserving a fast placement whose resulting scene
persists. Qualification should precede expensive embedding/vision. Passing those
checks justifies integrating this nomination layer; it does not establish event meaning.

`activity.py` compares tiny grayscale blocks with both a stable reference and the
previous observation. Three supporting observations and 0.5 s persistent change
qualify an episode. It settles after 0.8 s without adjacent-frame change; gaps over
0.5 s reset continuity. These are first-pass engineering values, not tuned household
thresholds. Live observation targets 10 Hz with at most 64 images/six seconds, and
three exact frames go to the VLM. Continuing changed activity can recheck after three
seconds. Busy-worker nominations are consumed only after admission and expire after
eight seconds if never admitted.

Automatic saved-segment indexing requests 0.1 s decoded observations, selects
before/during/settled frames plus periodic coverage, and embeds only those samples.
Actual source offsets remain authoritative; the original video is preserved. Each
segment/discontinuity retains an anchor, so a brief disturbance can still appear in
an anchor or periodic sample. Low source frame rate limits what can be established.
The denser scan is a functionality change, not a claim of fewer embeddings than
the earlier sparse two-second policy.

Command and local artifact:

```sh
uv run --no-sync python experiments/companion/window.py \
  --manifest data/evaluation/departure-manifest.json \
  --output data/runs/temporal-window-replay-001
```

This uses a declared replay clock and immediate nomination admission, with no VLM.

| Generated scene | Cheap observations | Indexed samples | Live nominations | Episodes |
| --- | --- | --- | --- | --- |
| Static, 120 s including endpoint | 1201 | 5 | 0 | 0 |
| 0.1 s flash returning to baseline | 41 | 1 anchor | 0 | 0 |
| Fast placement with lasting result | 41 | 5 | 1 | 1 |
| Continuing motion | 101 | 7 | 4 | 1 |

**Measured:** nine existing public clips supplied 2191 decoded observations, 278
selected frames and 98 potential live nominations. These whole-clip counts are not
departure scores: previous labels describe selected subsequences, and negatives also
contain qualifying visual activity. The cheap window does not distinguish entry,
closet activity or phone use. Source paths/hashes and exact offsets are in the local
result; temporary dense public frames were removed after measurement.

### Separate action eligibility and actual live replay

The new `departure_action` gate requires temporal qualification, unambiguous model
departure/approach/exit-interaction fields, and an eligible armed request. Only its
request IDs can be claimed atomically; cancellation is checked again at persistence.
Episode ID, timing, interpretation and gate reason accompany delivery evidence. This
implements relevance to the existing next-departure request, not general-purpose
event importance or identity recognition.

```sh
HF_HUB_OFFLINE=1 uv run --no-sync python experiments/companion/live.py \
  --manifest data/evaluation/departure-manifest.json --cases 3H0PT BM3UJ \
  --output data/runs/temporal-window-live-001
```

This now uses dense source excerpts at actual decoded intervals, not the old
two-second frame replay. Nominal old manifest indices locate the development excerpt;
the saved offsets and replay times are explicit, not original capture clock times.
Voice is disabled. Every admitted model job is recorded, including jobs completed
before the final replay frame.

- `3H0PT`: two model checks succeeded. The first judged no departure; a later check
  judged departure and created one pending notification. This does not measure whether
  speech could finish before an exit.
- `BM3UJ`: one model check incorrectly described the entering person as preparing to
  exit and created one pending notification. **The action gate cannot correct mutually
  consistent but semantically wrong model flags. Recognition remains unreliable.**
- Maximum observed replay gaps were 0.201/0.214 s, below the continuity reset limit.
  These are two reused development excerpts, not independent household trials.

### What conversation/search testing actually covers

The implementation is a custom Python model/tool/observation loop, without LangChain.
Before this follow-up, deterministic tests covered tools, attribution, cancellation,
limits and replay; real-model evidence comprised seven direct action-label probes and
five narrow integrated workflows. Those checks did **not** sufficiently exercise
query attributes or repeated inconclusive tool results.

The new `experiments/companion/planner.py` runs the actual local Qwen planner and agent
loop with controlled tool observations. It checks query concepts/contradictory
attributes, actual tool paths, search windows, bounded completion and authoritative
answers. It retrieves no images and performs no real reminder mutations.

```sh
HF_HUB_OFFLINE=1 uv run --no-sync python experiments/companion/planner.py \
  --output data/runs/planner-query-loop-004
```

Development runs are retained locally: `001` passed 7/10 checks, `002` 6/10, `003`
7/10 and `004` 10/10. Earlier scoring allowed an honest uncertain answer without
requiring broad search; final scoring also requires multiple distinct windows in
the all-inconclusive case. These are iterative development runs with changing
policies/scoring, not a controlled accuracy trend or independent test set.

Observed failures drove the changes: the model repeated current inspection after an
inconclusive result; repeated a checked history window; chose history for “Is it still
there?”; tried a missing camera; and copied a schema placeholder during an unsuccessful
remaining-action prompt experiment. Full candidate JSON templates were removed from
remaining-action guidance. Query placeholders are rejected. Up to two decision repairs
remain inside six total decisions. Explicit current/history/no-camera policies and
recorded repeated-window broadening prevent those errors silently becoming answers.
A revised query can still revisit a time window. A completed authoritative tool at
the final decision is returned without an extra generation.

Latest run `004` passed the following narrow checks:

- Blue-bottle description retained; thin/silver/reading-glasses correction retained,
  with the old black attribute removed.
- Historical pronoun resolved; “still there” checked a fresh view despite an old
  assistant answer; an imported red mug used undated best-match search.
- Inconclusive current check continued through two-hour then 24-hour history; missing
  camera used history; all-inconclusive checks widened and returned uncertainty.
- Cancellation selected the provided request ID; gratitude used chat without search.

One all-inconclusive case still needed a bounded malformed-decision repair. Concept
matching is narrow and not a semantic correctness oracle. Ten development cases,
controlled sightings and prior public-image integration do not establish dependable
household retrieval, arbitrary conversations or general personal memory.

Conversation text/trace persists in SQLite; the planner sees at most twelve completed
turns from the recent twenty. There is no saved-fact/correction/summarization layer or
semantic recall over older conversations. Long-term memory remains deferred as asked.

### Verification and recommendation

**192 deterministic tests pass**, including actual generated-video FFmpeg/indexing,
flash suppression, persistent placement, time/gap boundaries, episode grouping,
busy-worker recovery, cancellation/camera-stop/stale-inference action rejection,
query/tool policy repairs, source attribution and persistence. A request-boundary
test had relied on two wall-clock calls being distinct; it now uses an explicit
replay clock so its before/after ordering is deterministic.

`temporal-window-browser-001` passed generated-camera flash suppression (no vision
job or notification), subsequent sustained activity, synthetic speech, cancellation,
acknowledgement, denied playback and library controls. Model/voice boundaries are
doubles there; actual Qwen behavior is reported separately above.

Inline review reproduced 4:3 live snapshots being rejected because only width was
bounded (`temporal-window-4x3-before-001`). Bounding both dimensions preserves aspect
ratio and passes the repeated full generated-camera scenario
(`temporal-window-4x3-after-001`). The exact 0.5 s sampling boundary also has a passing
float-rounding regression. Final lint/format/JavaScript checks and local Markdown
links pass. The final offline wheel (`temporal-window-package-final-001`) includes
byte-matched current versions of all nine changed runtime modules/assets. Building
uses the cached isolated backend; an initial no-isolation invocation lacked hatchling
in the runtime environment and was corrected without changing project dependencies.

**Recommendation:** retain the temporal/action wiring and auditable continuation
policies. Next recognition work needs explicit exit geometry and chronological person
motion on independently labelled fixed-camera sequences. Do not promote the present
VLM to dependable departure assistance or close M1–M5 acceptance gates from these
prototype checks. General memory and RAM optimization remain deferred.

## Automatic region grounding and independent spatial evidence — 2026-10-20

**Question/decision:** Can reusable entity/region motion corroborate semantic cues
without encoding the bottle, doorway position or diagnostic clip? The user approved
this recognition slice and explicitly rejected scenario-specific workarounds.

### Method and runtime

Keep the earlier M4/16 GiB Mac, Python 3.12.11 and Qwen revision above, unquantized
on MPS. Measured versions: Torch 2.14.1, Torchvision 0.29.1, Transformers 4.57.6,
Pillow 12.3.0. Departure prompt v4 additionally asks for a stable exit region in
0..1000 image coordinates and uncertainty about exterior status. Generation is
bounded to 280 new tokens. Invalid/truncated responses abstain; no model repair
call is added to event checks.

Use existing Torchvision on CPU for independent SSDLite320 MobileNet V3 Large
COCO_V1 detections. Official source-reported weight size is 13.4 MB; measured cache
file is 14,069,355 bytes, SHA256
`a79551df90c79834bcd3bb3845ef9d966b5449a3a9b2833ae8404778ca5d65d2`.
One score >=0.6 detection per inspected image is required. Unsupported translation
skips semantic inference; a missed detection is not evidence of absence.

Generic geometry uses bottom-center positions, normalized to actual image size.
It distinguishes movement toward/away from a region, stationary positions and
reversal. A 0.08 displacement/contraction, 0.03 reversal tolerance and 0.06
diagnostic proximity are global starting policies. They are not calibrated physical
distances or probabilities. No room coordinates, clip IDs or reminder object names
occur in this evidence layer. The existing action still specifically implements
next-departure requests; generic evidence is not arbitrary event understanding.

`grounding.py` freezes the manifest/protocol before inference, records selected file
hashes and raw responses, and reverses the same trajectory for geometry diagnostics.
Nine previously used Charades sequences remain development inputs, not held-out
accuracy. Labels are staged room-exit proxies, not confirmed home departures.
No new household footage, real devices, cloud vision or paid calls were used.

### Measured results and rejected approaches

`grounded-events-001` first demanded proximity of the footpoint to the inferred door
rectangle. That policy produced no actions, including an otherwise supported
approach. Image-plane box distance is not reliable physical distance, so the final
gate uses observed direction to corroborate separately checked interaction. The
policy-only replay is retained as `grounded-policy-review-001`; it is not another
model run or an independent evaluation.

`grounded-events-002` reran the actual models with final code and the same manifest:

| Cases | Action result | Important observation |
| --- | --- | --- |
| Three exit proxies | 1/3 actions | 3H0PT supported; CUCBN detector coverage missing; YF6FL exit/direction uncertain |
| Four negatives | 0/4 false actions | Includes entry, closet, stationary doorway and indoor activity |
| Two ambiguous cases | 0/2 actions | Unknown exit or missing entity evidence |

The VLM still confidently called the closet an exterior exit and asserted departure;
its independently observed geometry was stationary and blocked the action. It also
invents interaction in an indoor activity. An exterior label is a model inference,
not proof of a house's layout. Five semantic calls in the final run took about
7.9–9.2 s per sequence including detector overhead; four early-abstention cases
took about 0.11–0.15 s. The static doorway skipped semantic inference after the
generic translation check was added.

`grounded-detector-001` measured roughly 0.10–0.12 s per three images after loading.
The fair live-dimension comparison `grounded-detector-comparison-001` uses the same
640×360-bounded images, common cutoff and CPU: SSDLite about 0.11–0.13 s, Faster
R-CNN MobileNet V3 Large FPN about 0.90–1.18 s. The latter recovered some small
subjects but introduced extra detections and retained a miss; complete single-person
coverage did not improve consistently. Counts are not accuracy measurements.
**Do not promote that larger detector or add a fallback.** Its measured cached
weights use 77,844,807 bytes; both experimental downloads total under 100 MB.

### Actual API replay and its limits

`grounded-events-live-001` exposed an eight-second semantic check occupying the
worker on an initially seated subject. The generic entity-position check now skips
that work. An offline selected sequence succeeding does not establish live success.

`grounded-events-live-002` uses the actual observer, API, models and fresh replay
clock. Both cases admitted three successful jobs with maximum sample gaps about
0.20/0.13 s, below the continuity limit:

- **BM3UJ entry:** the later Qwen response confidently says the person exits, despite
  entry labels. Independent distances increase across the sequence, producing
  `away`; no notification is created and the request stays armed. Earlier jobs
  abstain on missing detections. This directly exercises disagreement rejection,
  rather than treating abstention alone as proof of direction recognition.
- **3H0PT exit proxy:** no notification. Initially stationary boxes and later missing
  detections prevent a complete trajectory. This is a miss, not a success. The
  successful selected-image result does not survive sparse live selection.

`grounded-events-live-drain-001` repeats the exit replay with six seconds of clearly
labelled synthetic final-image hold so pending checks can drain. It still admits
three successful checks and produces no notification; the miss is not fixed by
waiting longer. Repeated source images are not extra footage or assertions about
what happened after recording. Source offsets and replay admission times are
recorded separately. No audible delivery or advance-warning success is established.

### Verification, limits and recommendation

**217 deterministic tests pass.** They exercise reflected/vertical layouts, reverse
motion, standing, turnback/pass-by, missing/multiple entities, malformed coordinates,
model-supplied fake geometry being overwritten, pre-semantic stationary rejection,
and the real action/API boundary preserving armed requests. Existing tests retain
freshness, gaps, cancellation, request ordering and durable delivery checks.

`grounded-events-browser-001` passes the generated 4:3 camera flow: brief flash
suppression, sustained activity, synthetic speech, cancellation, acknowledgement,
denied playback and older library controls, without browser errors. Its model/voice
boundaries are doubles. Final lint/format and JavaScript syntax pass. The offline
wheel `grounded-events-package-001` has byte-matched current `events.py`,
`observation.py`, `verification.py` and `web/companion.js`.

**Inference/recommendation:** keep reusable evidence and the independent direction
guard. It prevents a measured semantic false positive; it does not establish reliable
recognition or an improvement in overall recall. The observed tradeoff is stronger
rejection with missed events. Sparse localization, model region errors, occlusion,
perspective, camera movement and possible subject substitution remain limitations.
Next recognition work needs chronological tracking with explicit gaps on independently
labelled complete fixed-camera sequences, including actual positive approaches and
entry/visitor/turnback negatives. Measure missed/false actions and useful warning
time; preserve the current failure evidence. No M1–M5 acceptance gate is closed.

Sources (checked 2026-10-20): [official SSDLite model/weights](https://docs.pytorch.org/vision/master/models/generated/torchvision.models.detection.ssdlite320_mobilenet_v3_large.html),
[official Faster R-CNN MobileNet V3 FPN model/weights](https://docs.pytorch.org/vision/main/models/generated/torchvision.models.detection.fasterrcnn_mobilenet_v3_large_fpn.html).
Raw generations, hashes, SQLite state and protocol files remain local in the named
`data/runs/` directories; restrictive Charades source material is not redistributed.

## R8 continuation: buffered chronological tracking — 2026-10-20

**Question/decision:** can bounded dense observations, explicit short misses and
consistent region estimates improve the live path without a larger model or a
scenario-specific rule? Keep reusable evidence if the integration is sound; judge
recognition and timing separately. Do not promote a reliability claim from plumbing.

**Method:** same M4/16 GiB, macOS 15.7.3, Python 3.12.11; Torch 2.14.1,
Torchvision 0.29.1, Transformers 4.57.6, Pillow 12.3.0. Same pinned Qwen3-VL-2B
on MPS and CPU SSDLite COCO_V1 at 0.6. No new weights, framework, quantization or
cloud call. Up to six seconds of observations, roughly 5 Hz detector sampling,
explicit 0.8 s association gaps, three actual semantic images, full associated
motion for direction. Changed exit estimates reject the current action; initial
estimates remain provisional. One worker still serializes model work.

Contact sheets for all nine reused Charades clips were inspected before freezing
`full-trajectory-protocol-001.json`. Its SHA256 is
`60ecba608e3992b0106cdd37a31dd16c9058f44e8f2bb0fc0eb18c244adb3be1`.
The protocol includes coarse approach/crossing brackets from adjacent roughly
2-second contact-sheet samples. These are staged room-exit proxies, not verified
home departures or held-out household data. Full clips replay at actual decoded
offsets through the actual API; clocks are explicitly replay clocks. Six seconds
of labelled synthetic final-image repetition allow pending work to drain. Source
hashes and runtime were frozen before model inference. Voice and hardware are off.

The first attempt, `trajectory-full-api-001`, was aborted. Episode boundaries still
trimmed tracking context, and repeated setup in one conversation eventually caused
the real planner to choose cancellation instead of arming the requested reminder.
Some later clips therefore had no active request and no checks. They are invalid
negative trials, not passes. Full-window retention now has a regression test. The
harness isolates conversations/workspaces and asserts an armed request per case.
**The product's repeated reminder/cancellation conversation weakness is still open.**
Scenario isolation fixes evaluation validity, not that model behavior.

### Measured complete-sequence results

`trajectory-full-api-002` completed all nine clips with armed requests. All 79
admitted jobs succeeded; 19 invoked semantic inference. Maximum replay sample gaps
per clip ranged from 0.105 to 0.218 s, below the 0.5 s capture continuity boundary.
Every notification was counted even if it expired before the final status read.

| Clip | Frozen interpretation | Jobs / semantic checks | Created notifications | Outcome |
| --- | --- | --- | --- | --- |
| 3H0PT | Exit proxy; crossing 14.15–16.17 s | 7 / 1 | 0 | Miss; translation/region direction not established |
| CUCBN | Exit proxy; crossing 12.01–14.01 s | 9 / 0 | 0 | Miss; detector continuity insufficient |
| BM3UJ | Entry, then indoor activity | 13 / 2 | 0 | No false action; away motion and changed region reject semantic checks |
| MZ3X9 | Indoor negative through 24 s, later ambiguous interior exit | 9 / 2 | 1 | False action on indoor evidence at 18.74–19.74 s |
| VXJS4 | Stationary doorway activity | 11 / 3 | 0 | No false action |
| LZ07A | Bag activity, no visible exit | 5 / 3 | 0 | Abstains on ambiguous scene |
| YF6FL | Exit proxy; crossing 26.03–28.03 s | 11 / 3 | 1 | Evidence at 22.13–26.23 s; notification available at 36.14 s |
| W86WR | Disappears offscreen, no supported crossing | 8 / 1 | 0 | Abstains on ambiguous scene |
| FPJ9D | Indoor activity with camera movement | 6 / 4 | 0 | Control only; not valid fixed-camera tracking accuracy |

One of three exit proxies produced a notification, two were missed. The positive
notification became available about **8.11 s after the end of the crossing bracket**;
this is not useful advance warning. The MZ3X9 false action was available at 29.74 s,
but its inspected evidence was from the earlier negative interval. The model called
an interior doorway an exterior exit. Delayed availability must not relabel that
negative evidence as the later ambiguous event. No audible delivery was measured.

**Inferred limitations:** dense tracking recovers more chronology, but detector
misses and clipped/jittering boxes still prevent reliable association. Region
consistency does not prove exterior status, and a first wrong estimate can qualify.
The full-window geometry can also reject genuine approaches when jitter creates a
reversal. Slow semantic checks occupy the worker while new activity occurs; buffered
capture is not continuously processed motion and latest movement is not rechecked
at notification creation. This run does not establish an overall recall improvement
over selected-frame experiments, which used a different protocol.

### Verification and next decision

**227 deterministic tests pass.** New checks cover brief gaps without invented
positions, long gaps, multiple subjects/jumps, ordered timestamps, cumulative
turnbacks, cache isolation, exact semantic image attribution, changing/unknown
regions and full retained context across activity episodes. Existing request,
freshness, camera-stop, cancellation and delivery lifecycle checks remain green.
`trajectory-browser-002` passes generated 4:3 camera, brief flash suppression,
sustained activity, synthetic speech, cancellation, acknowledgement, denied playback
and older-library access with no browser errors. Lint, formatting, JavaScript syntax
and offline wheel build pass; packaged runtime files byte-match the source.

**Recommendation:** retain the bounded evidence plumbing but keep recognition
experimental. Next work should target automatic exterior/scene grounding and
response latency, with current movement checked before committing a late action.
Use independently labelled fixed-camera sequences, including actual approaching,
entry, visitor and turnback cases, before adjusting geometric policies. Current
multiple-person and turnback coverage is deterministic, not complete real-video
validation. General memory and arbitrary action types remain deferred. No M1–M5
acceptance gate is closed. Raw clips, contact sheets, generations, hashes and results
remain ignored locally; restrictive Charades media is not redistributed.

## Resource pause, continuity veto and Qwen3.5 smoke — 2026-10-20

The user paused heavy inference after laptop memory pressure, then selected the
vision-enabled Qwen3.5-2B 8-bit build and authorized **one short loading/image test**.
Video replays and broad real-model evaluation remain paused. The first continuity
replay timed out during loading; the second was explicitly terminated with the
running test process. Neither supplies completed recognition results.

The post-inference continuity veto is implemented: before creating a notification,
require the exact last semantic image still in the same epoch's retained buffer,
latest capture within 0.5 s, and no persistent or currently unsettled new activity.
Stable scenes and completed brief flashes remain eligible. A persistent change
followed by return still invalidates the old judgment. Tests exercise this during
blocked API inference. This can suppress slow true positives; it fixes neither
latency nor the interior-door misclassification. New evidence must earn a new result.

### Measured single-image smoke

`qwen35-8bit-smoke-001` used a generated 224×224 white image with one red square,
requesting a JSON color response with a 32-token maximum. It used the actual Nyx
`LocalVerifier` and the MLX adapter, offline after the checkpoint download. Thinking
was disabled. A parent subprocess enforced a 120-second timeout; MLX allocation was
limited to 6 GiB with a 128 MiB cache during this test. These limits apply to MLX,
not all process/system RAM. No camera, microphone, video replay or hosted inference.

- Checkpoint: `mlx-community/Qwen3.5-2B-8bit`, revision
  `562fb8ea19bbe7565a3ddf5b7d49899ea2c88d2b`.
- Config: qwen3_5 vision encoder; affine 8-bit group-size-64 quantization.
- Runtime: mlx-vlm 0.4.1, MLX 0.32.4, Transformers 5.20.2, Python 3.12.11;
  same M4/16 GiB machine.
- Load: **5.620 s**. Generation: **2.909 s**. Output: `{"color": "red"}`.
- Reported MLX peak: **2,895,864,550 bytes (2.70 GiB)**. Process max RSS:
  1,286,471,680 bytes. These counters cover different memory accounting; neither
  alone is total system memory. Larger images/context/multiple images can cost more.
- The model process exited after this one test. No text-agent or multi-image real
  inference was run. These paths have adapter boundary tests only.

**234 deterministic tests pass** in the updated locked environment. This includes
ordered image/text conversion, text-only input routing, pinned loading, disabled
thinking, shared generation and continuity-veto integration. The offline wheel
includes the new runtime. Full new-model recognition, multi-image semantics,
conversation quality and latency benchmarks remain unmeasured. Do not apply earlier
Qwen3-VL metrics to this checkpoint or treat this smoke as a comparative benchmark.
The browser was not relaunched during the resource pause; JavaScript syntax passes.

The user requested cache cleanup when switching. After successful smoke, the HF
cache tool removed only `model/Qwen/Qwen3-VL-2B-Instruct`, reporting **4.3 GB freed**.
The new checkpoint remains cached; retrieval/speech/detector assets and recordings
were preserved. Explicit legacy diagnostic use would download the old weights again.
The small rejected detector comparison cache remains outside this model replacement.

**Source-reported:** [official Qwen3.5-2B](https://huggingface.co/Qwen/Qwen3.5-2B),
[MLX conversion](https://huggingface.co/mlx-community/Qwen3.5-2B-8bit), and
[mlx-vlm 0.4.1](https://pypi.org/project/mlx-vlm/0.4.1/) (checked 2026-10-20).
The config and published runtime source were inspected before integration. The
selected path supports vision; published broad quality claims are not Nyx results.

## Conversation repair and correction wiring — 2026-10-20

**Implemented:** the previously observed mistaken cancellation on a new reminder
request is now rejected during decision validation, allowing bounded repair before
any tool executes. Authorization is rechecked immediately at execution. Negated
cancellation, cancellation mentioned inside another request, nonexistent/inactive IDs,
non-reminder targets and ambiguous multiple/duplicate reminder messages cannot mutate
an intention through this route. Direct UI controls remain available by exact ID.

Remaining planner search windows are scoped to the last resolved object query;
searching one object no longer excludes recent windows for a different object.
Prompt v9 instructs the model to prioritize the newest correction, retain compatible
user attributes and avoid copying old location answers into the object description.
The frontend distinguishes checking, stopped camera updates, expired evidence,
changed scene and an unsettled new change, while hiding an old cue during a new check.

**Method/limitation:** only deterministic scripted planners and fake inference
boundaries were exercised. Regression cases force a wrong cancellation followed by
repair, explicit/negated/ambiguous cancellation, a corrected object query revisiting
recent history and unchanged query attributes during time widening. These tests prove
control flow and context/argument retention, not Qwen's natural-language understanding.
The original shared-conversation real-model failure has not been rerun. No inference,
model download or browser launch was performed in this continuation. Reminder-message
semantic deduplication and general long-term memory are not added.

Verification: **246 deterministic tests pass**; after the final interrupted-status
adjustment, all 34 companion API tests pass again. Ruff, formatting and JavaScript
syntax pass. The offline `conversation-repair-package-001` wheel contains the current
agent, verifier, companion and UI files. Browser interaction was not rerun during
the memory-constrained pause. No new model accuracy measurement is claimed.

## Two-flow MVP check — 2026-10-20

**Scope:** focus on object finding with corrections/history and a next-departure
reminder; defer feature expansion and general memory. `mvp_objects.py` exercises
the actual API, CPU SigLIP and the pinned Qwen3.5 MLX 8-bit model. It reuses the
public-image synthetic video, imported with explicitly simulated dates (one hour
and ten days earlier). The image has two remote controls on a couch: this is an
ambiguity/correction diagnostic, not a glasses or household accuracy benchmark.
No devices, cloud calls or new downloads. Same M4/16 GiB runtime as above.

**Measured:** `mvp-object-001` failed indexing because Transformers 5 returns a
pooled output object where the encoder expected a tensor. Both image and text
paths now extract `pooler_output`, retaining compatibility with tensor outputs.
The rerun, `mvp-object-002`, successfully indexed both imports. Current-view and
correction turns completed in 6.00 s and 4.11 s, respectively, but both answered
“I can see television remote control visible location or empty string.” The
verifier copied its schema placeholder and described two remotes while marking
the result unambiguous. The correction “on the left” was absent from the tool
query. API job success therefore did **not** mean product success.

A parent watchdog checked system memory pressure every three seconds and stopped
only the owned experiment process below a 25% free metric (observed 22%), before
the history turn completed. It also enforced a 180-second time budget. Recorded
MLX peak after the two turns was 4,169,108,456 bytes (3.88 GiB), not whole-process
or system RAM. The process exited; no departure replay followed. These results
do not establish history ordering, corrected reference resolution or useful
departure timing with the new model.

**Implemented after the run:** visual prompt v2 describes fields without literal
placeholder values. Parsing rejects the observed placeholders and visible claims
with empty locations as uncertain. Regression tests cover these malformed answers
and both SigLIP output formats. This blocks the observed malformed evidence; it
does not fix all ambiguity or prove the revised prompt improves real recognition.
The model was not rerun after this fix. Attribute retention remains an open model
quality failure; no scenario-specific query rewrite was added.

**Next decision:** resume the small object/correction/history check when memory
headroom permits, then one positive and one negative departure replay. Use those
results to choose the smallest reliability fix. Neither MVP flow is accepted yet.

Verification: **251 deterministic tests pass**, Ruff and formatting pass, edited
document links resolve, and the offline wheel matches the changed runtime files.
These checks do not substitute for the pending real-model flow validation.

## Approved current-only retry — 2026-10-20

The user explicitly approved the proposed two-turn model check. Run
`mvp-current-003` used `mvp_objects.py --current-only`, offline cached Qwen3.5
2B MLX 8-bit, with no video imports, embedding indexing, devices or voice. The
parent watchdog sampled the system free-memory metric every three seconds, with
a 25% cutoff and 180-second timeout. Metrics were 52%, 46%, then 22%; the
watchdog terminated the owned child at 6.09 seconds (exit -15). No turn finished
and no results file was written. This does not measure model quality or latency.

Process inspection confirmed the experiment exited. The free-memory metric
recovered to 48% in the subsequent check. These percentages are the macOS
`memory_pressure` metric, not a measurement of model allocation or literal free
RAM. No model peak was captured. Do not infer a memory leak or precise model
footprint from this interrupted run. The cutoff was not loosened and no retry
was launched. Logs/watchdog samples remain local under ignored `data/runs/`.

Current/correction validation still requires more headroom or a separately agreed
runtime change. History and departure validation remain pending. No application
code changed in this run.

## Current-only retry with approved 10% cutoff — 2026-10-20

The user explicitly approved lowering the watchdog cutoff to 10% and rerunning
the small test. `mvp-current-004` used the same current-only fixture, pinned
Qwen3.5 2B MLX 8-bit, visual prompt v2 and planner prompt v9. No history imports,
embedding indexing, devices, voice or cloud calls. The 180-second timeout and
three-second memory sampling remained in place.

**Measured:** process exited normally in 15.05 seconds. Sampled free-memory
metrics were 60%, 59%, 29%, 30%, 27%; the watchdog did not trigger. These discrete
samples do not establish the instantaneous minimum or show that lowering the
cutoff caused success (this run started with more headroom). Reported MLX peak
was 4,177,850,684 bytes (3.89 GiB), not total process/system RAM. After exit the
system metric was 50%, and process inspection found no experiment process.

- Current question completed in 8.83 seconds, including initial model loading.
  Query: `television remote control`. Answer: “I can see television remote control
  left side of the pink surface, near the first cat.”
- Correction completed in 4.48 seconds. User: “I mean the remote on the left of
  the picture.” The tool query remained `television remote control`, and the
  answer was identical. Both traces used inspect_current then finish, with no
  decision errors.

**Manual interpretation:** the location corresponds to the visible left remote.
No schema placeholder was emitted in this run. However, the image has two remotes
and the generic first request received an unqualified single-object answer. The
correction's spatial attribute was still dropped. A coincidentally matching answer
is not evidence of correction understanding, and this one reused development
image does not establish recognition reliability.

No further inference followed. The next reliability work should address how the
planner retains user attributes and how visual verification handles multiple
matches, without adding a hand-coded rule for this image or object. History and
departure tests remain pending. No application code changed for this measurement.

## Query attributes and clarification handling — 2026-10-20

The user authorized improving query construction, asking about ambiguity, and
small sequential inference checks. All runs used the pinned Qwen3.5 2B MLX 8-bit
checkpoint, offline cached assets, no devices/cloud/voice, and a parent watchdog
with the approved 10% cutoff, three-second sampling and 180-second timeout.

**Implemented:** planner instructions explicitly preserve spatial/appearance
attributes, use the latest request before older context, and prefer inspection
of a usable description. Planner v12 sends only prior transcripts, answers and
source-availability flags, with the latest message last; stored plans remain
in the database. Visual prompt v5 inventories candidates and reports an integer
`matching_count`. A visible answer requires exactly one match. Multiple matches
or an ambiguity flag produce uncertain visual evidence with an ambiguity marker.
Missing/invalid counts cannot confirm a location. This is consistency checking of
model output, not an independent detector or a guarantee that the count is right.

Current inspection and historical verification now return a clarification question
for ambiguity. History stops before selecting another, possibly older match. The
agent finishes that tool result without another generation or automatic wider
search. The direct snapshot API and voice formatting retain the question. No new
agent framework, model, object-specific rewrite or long-term memory was added.

**Real planner check:** `planner-v10-001` exercised five cases with real decisions
and controlled successful tool results, not real visual search. All five passed
concept/path checks: right-hand remote, backpack underneath a desk, switching
from blue bottle to red mug, thin silver reading glasses, and a historical pronoun
for a blue bottle. Queries were manually inspected. Total process time 18.05 s;
lowest sampled memory metric 21%. These are development cases, and this five-case
set was not rerun after the later v11/v12 input changes.

**Integrated image checks:** all reused the two-remotes public image. The follow-up
was changed to the RIGHT remote, so repeating a left-hand answer would not pass.
Each run used fresh isolated conversation state and no history imports.

| Run | Visual/planner prompt | Process time | Observed behavior |
| --- | --- | --- | --- |
| mvp-current-005 | v3/v10 | 12.09 s | First answer chose left; follow-up asked which right remote instead of inspecting. |
| mvp-current-006 | v4/v11 | 15.05 s | Described two remotes yet claimed a visible unambiguous location; follow-up asked another question. |
| mvp-current-007 | v5/v11 | 15.05 s | Generic request correctly produced a clarification; spatial follow-up still asked again. |
| mvp-current-008 | v5/v12 | 12.30 s | Generic request clarified; right-hand follow-up repeated the clarification without an inspection. |

The final run's first turn took 9.14 s including model load; the correction took
2.22 s. Reported MLX peak was 3,973,347,408 bytes (3.70 GiB), not total process or
system RAM. Lowest sampled free-memory metric was 29%. All four processes exited
normally; no watchdog triggered. Differences between runs are not a controlled
memory comparison. No more inference followed.

**Conclusion:** ambiguity-to-question wiring now works on this development image.
The multi-turn correction flow is still failing: an answer to a clarification
must become a refined inspection query, but the model currently repeats the
question. The earlier isolated five-case pass does not establish integrated
conversation reliability. Next evaluation should explicitly include assistant
clarification → user attribute → tool use, with other objects and images. Do not
mark object finding, historical retrieval or departure MVP acceptance complete.

Verification: **261 deterministic tests pass**; lint, format, local document
links and byte-matched offline wheel pass. Browser interaction was not rerun.

## Integrated follow-ups, visual filtering and departure replays — 2026-10-20

The user requested completing the discussed work. Tests remained sequential,
local/offline, using the existing public media and synthetic browser inputs. All
real-model runs used the same pinned Qwen3.5 2B MLX 8-bit checkpoint and watchdog
(10% free-memory metric cutoff, three-second sampling, 180-second timeout). No
new weights, real device capture, provider calls or uploads. All runs exited
normally; no watchdog fired.

**Final implementation:** planner v17 replaces the long, overlapping instructions
with a shorter tool policy. It treats an answer to a clarification as a refined
query. Prior conversation includes the last `previous_tool_query` from existing
stored steps, alongside user/assistant text and source availability. Missing
query hints are omitted. This is descriptive context, never fresh visual proof;
there is no new memory store or hard-coded object-attribute extraction.

Visual prompt v6 explicitly filters candidates by user attributes BEFORE counting
matches, and requests valid JSON without list bullets. The existing single-match
validation stays intact. Tool-schema repair now names the exact allowed fields,
extra fields to remove and missing fields. The first explicit last-seen request
uses dated history before an undated-match tool when dated history exists; only
undated footage still follows the labelled unknown-time path. That final policy
change was verified deterministically after the last integrated run.

### Conversation measurements

`planner-v13-001`: five targeted real planner cases passed, including answers to
clarification questions. Controlled tool outputs do not measure vision accuracy.
Full v15 and v16 suites each passed **13/16** development checks. Failures included
lost spatial attributes, a copied concrete prompt example, invalid undated-search
fields, and—in v15—attempting to finish a gratitude turn without an observation.
Concrete query examples were removed and repair feedback improved. Final v17
targeted rerun passed **4/5**: clarification answer, spatial correction, imported
search and gratitude passed; a historical pronoun with no stored prior-query hint
still dropped the qualifier and selected matches. The later first-window policy
fix addresses routing, not that lost attribute. The full suite was not rerun on
v17; do not report a final full-suite pass.

Actual API runs imported the same synthetic slideshow with simulated dates one
hour and ten days earlier. Current/correction requests used the two-remotes still;
history had no current snapshot. Raw results remain under ignored data/runs.

| Run | Planner/visual | Process time | Result |
| --- | --- | --- | --- |
| mvp-full-009 | v13/v5 | 30.11 s | Clarified generic request, inspected right-hand correction, lost qualifier in history. |
| mvp-full-010 | v14/v5 | 33.11 s | Same history qualifier failure despite extra prompt instruction. |
| mvp-full-011 | v15/v5 | 33.09 s | Stored-query hint preserved history qualifier; vision still called right-hand correction ambiguous. |
| mvp-full-012 | v17/v6 | 57.53 s | Clarified generic request, inspected right-hand query, retained it in 2-hour historical search. |

The final three turns took 9.66 s, 7.87 s and 25.39 s respectively. MLX reported
3,812,391,998 bytes peak (3.55 GiB), not total process/system memory. The final
query was `television remote control on the right of the picture`. History chose
the recent import at offset 16 s with timestamp attribution. **Manual review:**
that frame is a small centered crop of the original LEFT remote. It cannot
substantiate the requested right-hand object's last sighting, and the generated
location “right of the picture” is not supported by that centered crop. Thus
conversation/query/time wiring improved, but historical visual attribution still
fails. Similarity and a model-confirmed description are not physical identity.

### Isolated visual checks

New `visual_queries.py` freezes four public-fixture cases before inference: generic
two-remotes image should clarify, right-hand query should select one, a clear
single-remote crop should be visible, empty image should be not-visible. It saves
input hashes, raw generations and parsed judgments after every case.
`visual-v5-001` passed 2/4: the specific query counted both remotes, and the empty
image produced invalid JSON with list bullets (safely parsed as uncertain).
`visual-v6-002` passed **4/4**, including the right-hand location between the cats
and correct empty-image rejection. These reused development images are not
held-out accuracy, and the integrated small-crop historical failure above remains.

### Real departure checks

`departure-v13-001` replayed complete public Charades clips 3H0PT (staged room-exit
proxy) and BM3UJ (room entry); `departure-v15-002` replayed YF6FL (another staged
exit). Each actual API request successfully armed its own reminder. Capture used
decoded source offsets, with six seconds of explicitly synthetic final-frame
repetition to drain work. Voice was disabled; no audible-delivery claim.

| Clip | Jobs | Semantic checks | Notifications | Interpretation |
| --- | --- | --- | --- | --- |
| 3H0PT | 8 | 1 | 0 | Missed exit proxy; most jobs lacked a supported person trajectory. |
| BM3UJ | 14 | 3 | 0 | Two false semantic exit claims were blocked by the independent movement-toward-exit check. |
| YF6FL | 12 | 4 | 0 | Missed exit proxy; semantic checks did not establish exit interaction. |

The two replay processes took 72.21 s and 45.14 s. Two positive proxies missed;
no false notification on this one entry clip. This is neither useful advance
warning nor household validation. These are staged room exits, not verified
home exits. Do not weaken direction/continuity checks to turn them into successes.
Departure recognition remains an open MVP blocker.

Final verification: **265 deterministic tests pass**, lint/format and offline
packaging pass. The synthetic browser speech check passes with no browser errors:
100 ms flash suppression, sustained activity, pending-audio cancellation, spoken
delivery/acknowledgement, playback-denial failure reporting and library paging.
Its first attempt failed because it expected obsolete raw state labels and the
old Cancel accessible name; the harness was updated to existing readable labels
and rerun successfully. These are fake model/audio/device boundaries, not real
recognition or Sarvam performance. All owned experiment processes exited.

## Guided historical finding — 2026-10-20

**Decision under test:** can the selected local model reliably compare a current
reference object with historical candidates, or should the MVP require review?
`reference-probe-001` used the two-remotes public still as reference, selecting
the right remote, against the original scene, mirrored scene, and a crop of the
OTHER remote. Actual two-image generation used the pinned Qwen3.5 2B MLX 8-bit
runtime and a 240-token cap. The prompt required distinctive matching appearance,
allowed position changes and uncertainty for lookalikes. Source fixture and
runtime are unchanged from preceding tests. `reference_probe.py` preserves the
method; raw generations remain local.

All three responses were JSON arrays rather than the required object, so the
strict parser returned uncertain. Raw generations nevertheless claimed visible
matches in all three cases, including the wrong remote. Do not interpret parser
rejection as evidence of successful identity discrimination or simply unwrap the
array to accept the wrong match. The process took 21.08 s; the lowest sampled
free-memory metric was 17%. This probe rejected automatic reference matching for
the present MVP; no such matcher was added to the application.

**Implemented instead:** historical hits become reviewable candidates. The main
reply asks whether the image contains the intended item and does not promote a
model location guess into a fact. Rejecting skips the frame on the next bounded
search while retaining query/source/time filters. Confirmation uses the saved
frame's own timestamp, is explicitly user-attributed, persists in existing
conversation storage and is idempotent. Deleting the source invalidates replay.
No new models, snapshot retention, identity store, or memory subsystem.

**Actual-model workflow:** `mvp-review-013` ran the current → correction → history
requests using the same public slideshow and explicitly simulated old/recent
recording dates. The first three turns took 8.32 s, 5.89 s and 19.29 s. They
produced clarification, a current visible result, then a historical candidate.
A simulated reviewer used known fixture provenance: offsets 14/16 crop the wrong
remote, while 0/8 contain the intended right remote (mirrored at 8). The model's
first candidate at offset 16 was rejected. The next candidate was offset 8 and
was explicitly confirmed through the real API. These fixture rules exist ONLY
in the experiment, never application routing or identity decisions.

The entire process took 78.40 s, including imports/indexing, model work and the
review loop. Reported MLX peak was 3,812,473,918 bytes (3.55 GiB), excluding other
process/system allocations. Lowest sampled free-memory metric was 20%. The same
10% cutoff, three-second watchdog and 180-second limit were used; it exited
normally. This demonstrates a guided workflow with an oracle reviewer; it is
not an autonomous-accuracy pass, actual intended-user study or a speed guarantee.

**Browser verification:** `match-review-browser-002` used synthetic camera/audio
and deterministic model boundaries, plus the public-image synthetic slideshow.
It passed candidate rejection, confirmation, conversation reload, source-image
display, speech/cancellation/acknowledgement, playback failure reporting, brief
flash suppression and library paging, with no browser errors. The first attempt
had a test polling failure while indexing was still running; explicit bounded
job polling fixed the harness and the rerun passed. No real devices or provider
calls. All owned experiment/browser processes exited.

Final verification: **269 deterministic tests pass**; lint, formatting, JavaScript
syntax and offline packaging checks pass. The packaged runtime and web assets
match the working source. Synthetic browser review coverage is recorded above;
no additional inference was required for final checks.

**Next identity experiment (proposed, not measured):** compare object-crop
embeddings for the intended remote across views against the other remote and
background distractors. Existing full-frame SigLIP retrieval already ranks
candidates; it does not establish individual-object identity. Measure whether
crop similarity separates same-item views from lookalikes before adding a
reference-ranking path or replacing explicit review. The failed VLM probe does
not establish that embedding-based matching will fail.


## Agent-driven rejection follow-up — 2026-10-20

**Decision under test:** can conversational feedback enter the normal bounded
agent loop and let the selected small planner choose how to continue, without a
hardcoded rejection phrase/router? The API persists candidate frame/query/time
references with existing conversation plans. The browser supplies the currently
shown reference for both typed and activated spoken requests; the server resolves
frame metadata from the index. The optional rejection button sends an ordinary
agent message. Both search actions accept model-selected frame exclusions, skipped
before visual inference. Confirmation and cheap background change detection are
unchanged. No additional model, dependency or memory subsystem was introduced.

`experiments/companion/planner.py` adds five controlled feedback cases: casual
rejection, rejection with a new identifying detail, an unrelated new object,
a second rejection phrasing, and thanks. Actual pinned Qwen3.5-2B MLX 8-bit
performs planning; tools return controlled observations. Thus this measures
query/tool decisions, not actual vision or retrieval. The machine/runtime/model
are unchanged from the preceding guided-finding run. Runs were offline, sequential,
under the existing 10% memory-metric cutoff and 180-second parent watchdog.

Measured development iterations:

| Run | Planner prompt | Focused result | Main failure |
| --- | --- | --- | --- |
| rejection-planner-001 | 18 | 1/3 | Failed to include all rejected IDs |
| rejection-planner-002 | 19 | 1/3 | Lost new detail; stale exclusions on new task |
| rejection-planner-003 | 20 | 2/3 | Rejection incorrectly used current view |
| rejection-planner-004 | 21 | 3/5 | Lost detail; stale exclusions on new task |
| rejection-planner-005 | 22 | 3/5 | New task and thanks incorrectly continued history |
| rejection-planner-006 | 23 | 3/5 | Lost detail; stale exclusions on new task |
| rejection-planner-007 | 24, discarded | 2/5 | Request-summary wrapper lost rejected-object context |

Final code retains **v23**, with compact review context, optional search exclusions,
and ordinary action JSON. The attempted request-summary wrapper was removed; it
was not an improvement. Final successes: "nah man its not this item" and "That's
somebody else's. Keep looking please." both searched history for the blue mug with
IDs 40 and 42 excluded. Thanks produced chat. Failures: "mine has a white handle"
retained only "blue mug"; switching to a red backpack in the camera incorrectly
searched history and retained old exclusions. These are development cases, not
held-out accuracy estimates. No claim that arbitrary feedback is dependable.

All seven runs exited normally; elapsed times were 15.06, 15.07, 15.05, 21.15,
21.07, 21.44 and 27.12 seconds. Lowest sampled memory metrics ranged from 19–22%;
no cutoff fired. No visual media/provider calls or downloads were needed.

**Integration evidence:** 277 deterministic tests pass. They verify saved candidate
context across restart, agent-selected exclusions through the actual API, a direct
history result's reference flowing into a normal agent request with a current
camera fixture, strict argument bounds and prompt context. The planner is mocked
in these integration tests; they do not substitute for the failures above.
`agent-review-browser-002` passed button rejection followed by typed rejection,
nonrepeating images, explicit confirmation/reload, synthetic speech and existing
activity/cancellation checks, with no browser errors. All devices/model/provider
boundaries in this browser check are synthetic. Lint, formatting, JS syntax and
offline packaging pass. Owned model/browser processes exited.

Recommendation: keep feedback agent-driven and retain the measured failures as
regressions for the next planner improvement. Do not mask them with object-specific
or phrase-specific routing, and do not claim this resolves lookalike recognition.


## Retrieval continuation and evaluation preparation — 2026-10-28

**Code finding:** exclusions were applied after retrieval LIMIT, so rejection could
exhaust the same initial ranked candidates while additional eligible frames existed.
The correction applies parameterized frame-ID exclusions within SQLite, before
ranking/LIMIT, on both history retrieval paths. Per-request inference bounds,
source/time filters and model-controlled decisions remain unchanged. Synthetic
24-frame regression fixtures cover relevance, chronological latest and semantic
latest selection beyond the original retrieval window. No semantic accuracy claim.

`feedback_cases.json` adds six previously unrun conversation scenarios for the
existing actual-planner/controlled-tool harness. `--case-file` keeps them separate
from the older development examples. They test new identifying details, switching
objects, continuing history, thanks/stopping, and time widening without rejection.
Scoring now explicitly fails stale/unrequested exclusions and cannot count a lack
of searches as a successful rejection. Scoring regression tests use no model.

Decision criterion for the next model run: retain the current planner unless an
alternative improves correction and task switching without breaking rejection,
non-rejection follow-ups or greetings. Once these cases influence tuning, treat
them as development examples rather than held-out evidence. They have not yet
been executed with a model; the previous v23 3/5 result stands.

Verification: 281 deterministic tests pass; 2 PyTorch-dependent tests skip because
only the locked Python 3.12 web/test environment was restored (the previous local
virtual environment was absent). Tests now explicitly mark the optional dependency.
No new model weights, inference, browser/device capture or external-provider calls.


## Actual feedback evaluation and rejected alternatives — 2026-10-28

**Question:** do the newly prepared conversations expose the previous failure
modes, and can a small change to input formatting, the review tool interface or
reasoning improve them? Restored the existing pinned MLX Qwen3.5-2B 8-bit revision
and locked runtime (Python 3.12.11, mlx-vlm 0.4.1, MLX 0.32.4, Transformers 5.20.2)
on the same 16 GiB Mac. Only public model weights were downloaded; text planning
stayed local. Tools returned controlled observations, not real image findings.

Scoring was strengthened after manual inspection: an explicit request for older
footage must widen the previous two-hour window; a continuing search must retain
previous exclusions without adding the displayed candidate unless rejected.
Original result files remain local alongside separately rescored reports. The
following figures use the tightened criteria consistently:

| Local run suffix (20261028) | Method | Result | Elapsed | Minimum free-memory metric |
| --- | --- | --- | --- | --- |
| feedback-baseline | Application planner v23 | 3/6 | 33.21 s | 23% |
| feedback-natural | Same prompt, latest message in separate user turn | 3/6 | 21.21 s | 21% |
| feedback-review | Experimental v25: model chooses new/continue/reject; executor carries IDs | 3/6 | 18.16 s | 24% |
| feedback-compact | Experimental v26: same review interface, shorter prompt and prior hours | 3/6 | 18.24 s | 23% |
| feedback-thinking | v26 with 1024-token reasoning, no forced thinking limit | Stopped, no completed cases | 75.40 s | 35% |
| feedback-thinking-bounded | v26 with 256-token thinking budget plus 240 output tokens | 1/3 targeted cases | 48.40 s | 27% |

The baseline retained glasses attributes but failed to widen time, copied glasses
exclusions to a wallet search, and treated time widening as candidate rejection.
The natural-message variant did not fix these. Review-choice interfaces helped
some switches but lost corrections or prior exclusions. The compact variant
selected history for an explicit live-camera request. Limited reasoning still
lost the red-frame attribute and misrouted a stop request. The unbounded probe
was manually terminated (exit -15) after reasoning did not finish; this was not a
memory-cutoff event. All other processes exited normally under the three-second
sampling, 10% cutoff, 180-second parent watchdog. No process remains loaded.

**Manual quality caveat:** automated path scores are not enough. The baseline's
stop/thanks answer promised to keep watching without creating a monitoring task.
The compact variant returned an incoherent first-person correction on that case,
even though its chat action passed the path check. Therefore 3/6 is a structural
check count, not an end-to-end conversational success rate. These cases have now
influenced experiments and are development cases, not a held-out benchmark.

**Decision:** keep the existing v23 application planner. Do not ship the altered
review interface, shorter prompt or reasoning settings without a demonstrated
improvement. The rejected code diff is retained locally under ignored runs;
`planner.py` retains opt-in natural-message and bounded-thinking probes for future
comparisons, with raw generation logs. No application thinking mode was enabled.

**Concrete repair:** while inspecting the tool path, found that existing policy
redirection from search_matches to search_history rebuilt arguments and discarded
model-selected exclusions. The executor now preserves exclusions when changing
between history search tools. This is tool plumbing, not deterministic detection
of user feedback. A targeted regression proves excluded IDs reach the tool.

Final verification: 285 deterministic tests pass with restored optional vision
dependencies, plus lint/format and documentation links. No browser, household,
voice-provider or image-recognition evaluation occurred in this follow-up.
Recommendation: compare a more capable text planner rather than repeatedly tuning
this small model on the same examples. Vision and text planning need not use the
same model; such a comparison is proposed, not yet implemented or measured.
