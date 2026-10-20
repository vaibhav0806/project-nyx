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
