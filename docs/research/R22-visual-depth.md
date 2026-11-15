# R22 — Broader category and ambiguity verification

Date: 2026-11-15. Status: frozen baseline comparisons in progress. Owner: inline implementation.
Decision: whether a general visual-model/prompt change improves evidence enough for selection.

Runtime: Python3.12.11, macOS15.7.3 arm64, Pillow12.3.0 and NumPy2.5.4 in the locked environment.
Starting application branch head e8be0e7; frozen comparison manifest committedfc5da3e. Individual
artifacts preserve actual model/prompt fingerprints and source hashes rather than inferring
them from the current code after rejected candidates were reverted.

## Method

Eighty frozen cases from the same forty licensed public COCO photos used in R16; forty positive
category queries and forty annotation-negative category queries. Image-separated development48 /
holdout32. Exact per-image category instance counts from the pinned annotations distinguish
single from multiple targets. These are new verification conditions on previously used images,
not untouched household data. All source hashes remain fixed; original photo times are unknown.
Run actual CloudVerifier, unchanged prompt and 768px transport, Lite versus existing stronger Flash
one pass at a time. No fake judgment, new embedding model or new provider. The prior positive
corroboration experiment is available but not a presumed improvement. Score single visible with
location, multi uncertain, negative not-visible/uncertain; failures stay in the denominator.

Annotation-negative and count labels are proxies, not exhaustive visual truth. Manually audit
development disagreements; retain original proxy scores and audit notes rather than relabeling
to manufacture a win. Positive location wording and instance identity are not scored. A stronger
default needs safer findings without an unexplained recall regression, followed by heldout
comparison; cost and latency remain explicit. No new fixture-specific runtime rules.

## Initial observed development baseline

Lite completed48/48:41 correct proxy outcomes, six proxy-unsafe positives and one single-target
miss. Manual inspection confirms bottle/jar/cafetiere and cup/jug/wine-glass category broadening;
the missing remote is visible on the sofa. Image7574's cup-negative annotation is questionable
because drinking containers are present; retain it as a label caveat, not a definite hallucination.
Image20553's claimed remote on the bottle table is unsupported on inspection. Image13659 again
confuses a jar/container with a bottle. Flash comparison is still running, so no selection yet.

Initial budget snapshot1.644318515/2; Lite final observed1.673231715/2, settlement may lag.
Artifacts remain ignored under data/runs/visual-depth-*. Frozen manifest/scorer/runner are in
experiments/companion/visual_verification_cases.json, visual_cases.py and visual_verification_replay.py.
The scorer passed9 deterministic tests after the initial absent-module RED.

```sh
NYX_VISUAL_CONFIRMATION=0 uv run --env-file .env --no-sync python -m experiments.companion.visual_verification_replay --data data/evaluation/coco-small --cases experiments/companion/visual_verification_cases.json --output data/runs/visual-depth-lite-dev --model lite --max-spend 0.10
```

Replace model/output for a fresh comparison; never overwrite a prior run.

## Rejected/incomplete development alternatives

Flash hit its per-run guard after17/48 cases:17 correct run outcomes,31 not-run cases remain in
the denominator. Its reported response cost was$0.080166 (guard reserves$0.02 inside$0.10); the
early subset mostly covers remotes/bottles, not all four categories. Do not call this17/17
whole-corpus accuracy or promote from the incomplete run.

A general prompt8 candidate required diagnostic category support rather than similar purpose
or shape; no fixture IDs, class lists or coordinates. It stopped after47/48 at its$0.06 guard:
39 correct proxy outcomes,7 unsafe proxies, one not-run. Reported responsecost$0.0402806.
It did not show the required improvement and was reverted to prompt7. Original JSON preserves
the candidate fingerprint/outputs. This is one trial, not proof that all prompt work is useless.
Lite baseline holdout completed32/32, aggregate27correct/3unsafe; the aggregate was printed but
detailed heldout outcomes were not used to modify the candidate. No selected visual change has
been promoted. A safe negative/clarification remains preferable to an unsupported positive, but
strict proxy counts alone do not establish natural-language category correctness.

Latest observed key snapshot after these experiments1.821041415/2, settlement may lag. Remaining
budget is prioritized for actual spoken-model tool-policy checks; no cap increase or new key.
