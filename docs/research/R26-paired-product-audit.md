# R26 — Did the reliability branch improve the product?

Date: 2026-11-15. Owner: inline. Status: bounded paired audit complete.
Decision: retain measured retrieval/context improvements; distinguish these from unproven overall
household recognition gains. No new model, prompt or production policy was selected in this pass.

## Method and comparability

Compare stable `cfe8fa4` with the work branch after `3bda9d6`, using the same cached vectors,
inputs, locked Python environment and scoring. Stable source was exported from Git into ignored
`data/experiments/stable-cfe8fa4`; no checkout/main modification. Its pyproject.toml and uv.lock
were byte-identical to current dependency definitions. Runtime source SHA256 is recorded in both
reports. Shared probes select only APIs supported by the imported runtime; no feature is
backported to the baseline. In particular the stable runtime uses flat nomination, while the
branch's semantic latest-history route uses source balancing. This is not an assertion that
ordinary Store.search enables balancing by default.

## Paired public candidate retrieval

Reuse the 16 previously evaluated holdout COCO sources and compatible cached Gemini Embedding 2
768-dimensional vectors. This is regression evidence, not an untouched holdout. Same query/source
labels and repeated-frame crowding condition; actual SQLite search and frame diversity run.

| Condition | Stable mean source Recall@12 | Branch mean source Recall@12 |
| --- | ---: | ---: |
| Uncrowded | 0.888393 | 0.888393 |
| Crowded by a high-scoring irrelevant source | 0.122024 | 0.848214 |

This directly reproduces the retrieval improvement against stable code, rather than comparing
only two flags in current code. It is image-to-image category nomination under simulated repeated
frames/timestamps, not final answers, text-query accuracy, instance identity or household accuracy.
Candidate stores are metadata-only and never provide visual answers. The separate repeated
10k-vector runtime test measured warm median query time 26.30 ms flat versus 99.34 ms balanced:
the quality improvement has a SQL cost, not a universal speed win.

Artifacts: data/runs/paired-{stable,current}-pool-holdout/results.json.

## Past local library — offline, originals preserved

The existing local library has 92 indexed recordings and 1,085 frame rows. Each runtime opens
its own SQLite backup; the original index is read-only and never migrated. The bounded audit
uses the first 24 stored frame vectors as queries, checking exact selected frame IDs, offsets
and timestamps. All 24 query results were identical across runtimes. This tests compatibility
and ranking preservation, not semantic relevance: a stored-vector self query is an easy case.

The first 24 registered recordings were all present, probeable and decoded a first video frame;
all sampled file hashes were unchanged after reading. This is neither full-file decode nor a
whole-library corruption guarantee. No images, audio, transcripts or stored vectors were sent
to a provider. Raw IDs, indexes and reports remain ignored. Source/library names are not published.

The same synthetic deleted-source planner probe ran against both applications: stable still
serialized the unavailable assistant location; current withheld it. Both retained the query
constraint and left the stored input unchanged. This is a proven provider-boundary safety gain,
not a claim that every generated answer is correct.

Artifacts: data/runs/paired-local-{stable,current}/results.json. The reusable
experiments/companion/local_replay_audit.py also records code hashes and these boundary checks.
A synthetic integration test verifies original database/media hashes survive the audit.

## Real-provider report-memory regression

All six previously evaluated report-intent holdout workflows passed again through the actual
resolver, embeddings, typed API, statement tools and citation scorer, with no incomplete cases.
Inputs: experiments/companion/report_intent_workflows.json. Exact source/report attribution is
scored; this is not acoustic or free-form answer-quality evaluation. This run is a regression,
not fresh heldout evidence or a paired stable run. Stable lacks some newer report APIs; blindly
calling newer setup arguments would measure harness incompatibility, not baseline intelligence.

Artifact: data/runs/paired-audit-report-holdout/results.json.

## Fresh public visual diagnostic

Download eight new source-disjoint COCO validation images: exclude all prior 40 image IDs before
calling the existing deterministic licensed-small-object selection with two sources per category.
Selection/labels were frozen before inference. Per-image download bound 2 MiB; actual photos
1,226,690 bytes total. Matching source hashes and image dimensions were checked. License ID 4
(CC BY 2.0) and attribution URLs come from the pinned original annotation metadata; selected
media remain ignored. See [COCO](https://cocodataset.org/#download) and
[terms](https://cocodataset.org/#termsofuse). The previously established bounded mirror download
route is retained; original capture clocks remain unknown.

Committed manifest: experiments/companion/visual_audit_fresh_cases.json. Sixteen predeclared
category/count proxy conditions: four single matches, four ambiguous and eight absent conditions.
Current default Lite/prompt7, no extra confirmation, completed **16/16**, zero proxy-unsafe
positives and no failed requests. No tuning or runtime changes followed these outputs. This
small set does not erase prior category failures, measure exact location/identity or establish
a vision improvement over stable: its default object model/prompt remain the same.

Artifact: data/runs/paired-audit-fresh-visual/results.json. Reproduction:

```sh
NYX_VISUAL_SCENE_POLICY=0 NYX_VISUAL_CONFIRMATION=0 uv run --env-file .env --no-sync python -m experiments.companion.visual_verification_replay --data data/evaluation/coco-audit-fresh --cases experiments/companion/visual_audit_fresh_cases.json --output data/runs/fresh-visual-reproduction --split holdout --model lite --max-spend 0.10
```

## Recovery, checks and cost

Repeated synthetic ten-day replay: all 30 in-window sources eligible, older/future/unknown edges
correctly excluded, all 33 source hashes retained, all six recovery/fault checks passed. Actual
video duration is 330 seconds, not a ten-day soak. Recording cap/storage limitations are unchanged.
Artifact: data/runs/paired-audit-ten-day/results.json.

Fresh verification: 528 tests passed in 25.01 s; the subsequently cleaned fixture registration
also passed focused audit tests. Ruff lint/format, three JavaScript syntax and UI-preservation
checks passed. This pass only changes experiment/test/documentation files. Author review only;
no independent review, hosted CI, PR or merge-readiness claim.

New response-reported costs: report replay $0.037045175, fresh visual $0.0111002. Added to prior
conservative accounting, cumulative estimate is **$3.205437215 / $5 total**. Latest artifact key
metadata reports $3.194337015; settlement may lag. No refill needed.

## Verdict and next product gate

Yes, specific product improvements are demonstrated: crowded retrieval reaches relevant sources
much more often, and unavailable claims are withheld before planning. Existing local-library
queries/media passed bounded compatibility checks, report workflows still pass, and fresh public
photos performed well in this small diagnostic. No universal “strictly better” or household
recognition claim follows. Known can/bottle confusion, wake homophones/false activations, private
household object ground truth, real speech/acoustics and long-duration operation remain open.
Do not promote another prompt/model from aggregate test counts alone or upload personal media
for convenience. The next visual gate needs labeled physical category, attributes, count, location
and identity outcomes on permissioned representative examples, rather than another small prompt
search against already-opened errors.
