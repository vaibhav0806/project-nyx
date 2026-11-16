# R15 — Sampling coverage floor

Date: 2026-11-15. Owner: inline implementation. Status: coverage fix and offline condition replay
implemented; real household quality and continuous ten-day coverage remain unproven.
Decision affected: adaptive indexing sampling policy.

## Method

Reproduced R12's missed 25×13-pixel object at 1280×720, visible from source offset 3.0 to 5.9 seconds.
Added tests before changing selection: the original selector returned no sample in that interval.
Compare activity-only selection with activity plus an independent two-second sample floor, using
the actual application selector. The floor selects only real decoded inputs; gaps are not filled.
Live proactive activity qualification is unchanged.

`experiments/companion/memory_replay.py` validates explicit capture/replay times, interval bounds,
source digests, split separation by source/group, hashed permitted frame streams and manifest-local
paths. Unknown capture dates are not replaced by replay dates. CLI defaults to development-only
execution and refuses existing output directories. The source recipe hash is a synthetic recipe
digest, not a real recording hash.

Generated 100 synthetic ten-second conditions with varied small-region size/position/contrast and
appearance duration (0.2–3.0 seconds), including 20 no-event conditions. Images are deterministic
templates sampled at 0.1 seconds; ground-truth visibility comes from the rendering recipe, not a
model's judgment. Split 60 development / 40 held-out conditions by distinct recipes. This tests
sampling mechanics; the generated distribution is not independent real-world validation.

## Measured results

| Split/policy | Positive events retained | Total selected samples, including no-event cases |
| --- | --- | --- |
| Development: activity only | 1/48 | 64 |
| Development: five-second floor + activity | 14/48 | 124 |
| Development: two-second floor + activity | 32/48 | 303 |
| Held-out: activity only | 3/32 | 60 |
| Held-out: selected two-second floor + activity | 23/32 | 219 |

Selected two seconds on development coverage/resource tradeoff before running the held-out split.
Did not use held-out results to change the policy. The nine remaining held-out misses show that
a two-second floor cannot guarantee retaining shorter events. No semantic retrieval, final answer
accuracy, live latency or API cost was measured by this replay. It made no provider requests.
The small-object R12 regression now retains its actual offset-4.0-second sample.

## Runtime change and resource limits

New adaptive imports record `activity-v2/scan=0.1s/0.5s-persistence/coverage=2s`.
Existing recordings/indexes are not rebuilt or deleted. The periodic floor increases derived
frame count: a static 60-second test keeps 30 frames versus the old two. Real ten-second capture
segments typically start with their own initial sample, so those ratios do not establish an
all-day cost estimate. Extra embedding calls/storage are a real tradeoff requiring further
measurement; no automatic paid replay or storage-budget increase is introduced.

The legacy selector remains available with `coverage_interval=None` for comparisons. Keeping a
frame establishes availability for later retrieval, not object identity, event truth or a reminder.
Source video remains subject to the same 1 GiB stop-without-delete cap.

## Reproduction

Python 3.12.11, macOS arm64, existing locked Pillow/NumPy runtime, no new model dependencies.
Private outputs under ignored `data/runs/`:

```sh
uv run --no-sync python experiments/companion/memory_replay.py --output data/runs/memory-replay-dev-2s
uv run --no-sync python experiments/companion/memory_replay.py --manifest data/runs/memory-replay-dev-2s/manifest.json --coverage-interval 5 --output data/runs/memory-replay-dev-5s
uv run --no-sync python experiments/companion/memory_replay.py --manifest data/runs/memory-replay-dev-2s/manifest.json --split holdout --output data/runs/memory-replay-holdout-2s
```

These output names already exist in this run; use fresh names when reproducing. Deterministic
tests cover source-byte preservation, actual source offsets, coverage, legacy comparison,
manifest time separation, split leakage, interval scoring, digest tampering and path escape.
