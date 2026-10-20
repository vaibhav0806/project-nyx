# Continuous trajectory evidence

The user approved chronological movement tracking, explicit brief gaps, consistent
automatic scene grounding, useful nomination and complete-sequence evaluation.
Execute inline with the existing models and bounded worker; local commits, no push.
General memory, arbitrary event actions and hardware remain deferred.

## Architecture and starting policies

Keep up to six seconds/64 live frames. Nominate activity processing at most once
per second with new visual evidence. Include a 5 Hz sampled tracking window (at
most 32 frames) alongside the existing three preview frames. Run the CPU detector
on that window, caching only timestamped detections for overlapping inputs in the
same camera epoch. Heavy inference still serializes on the current worker: this
is buffered chronological tracking, not a guarantee of uninterrupted real-time
processing while a VLM generation runs. Long inference/capture gaps remain visible.

Associate one unambiguous entity over time. Preserve missed observations as gaps
for at most 0.8 s; do not interpolate positions or identities. Multiple entities,
long gaps and implausible position jumps split the trajectory. Select only real
observations for three semantic images. Keep the full observed trajectory/gaps
and exact selected timestamps as evidence; action direction uses all observations,
including intermediate reversals. Missing recent evidence must abstain.

Automatically inferred regions stay fallible. Compare successive region bounds
within the same view/epoch; contradictory bounds reject the current action and
need subsequent consistent evidence. Unknown latest output stays unknown. Initial
grounding is explicitly provisional, not independently confirmed. No manual region,
clip-specific rule, new model, identity recognition or framework.

## Tasks and verification ledger

- [x] TDD generic trajectory association: dense motion, brief explicit gaps, long gap,
  ambiguous people, substitution/jumps, ordered times, newest evidence and reversals.
- [x] TDD region consistency and dense-window inference, detection reuse, exact three
  semantic samples, all-point direction, and failure/unknown output handling.
- [x] Wire observer/API with bounded dense windows, preserve request/freshness/cancel
  boundaries and exact inspected timestamps. Test fake-model integration and browser.
- [x] Freeze full-sequence protocol and event labels before inference; run actual
  detector/model offline and live replay. Record misses, false actions, coverage and
  timing. Existing public footage remains reused diagnostic evidence, not held-out
  household accuracy. No real hardware or cloud visuals.
- [x] Run full tests, lint/format/JS, package and documentation checks. Update R8,
  decisions, architecture, scope, walkthrough and milestone status; commit locally.

Review focus: buffered tracking latency; observed vs missing positions; late turnback
hidden by sparse selection; source/request time boundaries; camera/epoch reset;
unknown and changing exits; association errors; action timing relative to the event.


Completed evidence: 227 deterministic tests; generated-media browser
`trajectory-browser-002`; offline byte-matched wheel `trajectory-package-001`;
full nine-clip replay `trajectory-full-api-002`. The first replay was aborted due to
invalid reminder setup and shortened context; no inactive clip counts as a pass.
A regression now preserves context across activity episodes, and the harness asserts
armed isolated setup. Actual-model results retain two missed exit proxies, one late
positive and one false indoor action. Recognition, timing and repeated-reminder
conversation weaknesses remain open in R8; this implementation does not close them.
