# Grounded temporal event evidence

The user authorized the next recognition slice and explicitly asked for automatic,
reusable behavior rather than a hard-coded bottle scenario. Execute inline with
local commits and no push. This refines the existing bounded departure action;
arbitrary user-defined event actions and personal memory are still later work.

## Design and engineering choices

Separate activity nomination, visible entities/regions, chronological spatial
relations, semantic interpretation and action eligibility. Use the existing worker
and Qwen. Try automatic exit localization from the actual images; no predefined
door position, clip ID, object name or mandatory user-drawn rectangle. An ambiguous
exit must cause abstention. A semantic label cannot establish a home's layout.

Use Torchvision's existing optional dependency for an independent, small SSDLite
person detector (COCO_V1 checkpoint, about 13.4 MB source-reported). Run it only on
the three nominated images, lazily on CPU. Normalize boxes to image coordinates.
Compute generic movement toward/away from an automatically grounded region from
the observed trajectory. Initially require one detection in every inspected image;
do not associate ambiguous people, infer identity or fill in missed detections.
This is sparse geometric evidence, not dense tracking or an absence detector.

Use geometry alongside semantic exit/interaction judgments. Preserve boxes,
coordinates, direction, detector/model versions, exact frame times and rejection
reasons with the event evidence. No semantic output alone may bypass this gate.
Global displacement/tolerance settings are starting policies, not tuned per clip.
Detection misses and unclear house-exit semantics will reduce recall; measure them.

## Work and acceptance

- [x] Write failing tests for reusable region-relative movement in different layouts,
  reverse motion, standing, turnback, pass-by, missing/multiple detections, invalid
  coordinates and chronological order. Implement the smallest geometry module.
- [x] Test detector-output normalization and strict region parsing at the inference
  boundary. Add the lazy detector and automatic region output to local inspection.
- [x] Require grounded approach evidence at the action boundary; test a confident
  semantic false positive being rejected, including real API persistence/cancellation.
- [x] Run a frozen labelled development protocol through the actual detector/Qwen,
  recording failures, misses and timing as well as positives. No per-case exceptions.
  Existing public clips remain diagnostic; do not label reused inputs held-out data.
- [x] Run full deterministic checks, generated-media browser flow and package checks.
  Update decisions, architecture, scope, walkthrough, milestones and R8 with measured
  results. Commit coherent work locally; do not claim general event understanding.

Review focus: entering vs approaching, stationary model-positive hallucination,
ambiguous exterior vs interior door, detector misses/extra people, malformed/outside
boxes, projected image motion vs real intent, stale or cancelled events. Independently
labelled household sequences and advance-warning evaluation remain required.

## Execution evidence and rulings

217 deterministic tests pass; lint/format, JavaScript syntax, generated-media browser
speech flow and offline packaged runtime verification pass. Actual Qwen/detector
development replay: one action on three exit proxies, zero on four negatives and
zero on two ambiguous inputs. Actual live entry disagreement is rejected by geometry;
actual live exit is still missed by detector gaps, including a synthetic drain tail.
These are measured limitations, not completed recognition acceptance.

Reject physical footpoint/door-box proximity as an action requirement; use direction
to corroborate separate interaction. Skip semantic inference on unsupported entity
translation so initially stationary frames do not occupy the model. A measured larger
detector added latency/ambiguity without consistently fixing coverage; retain the
small detector. No per-clip or fixed-room rules. See [R8](../../research/R8-companion-loop.md)
for raw-artifact names, rejected alternatives and remaining evaluation work.
