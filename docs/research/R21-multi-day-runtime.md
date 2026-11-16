# R21 — Multi-day replay, capacity and recovery

Date: 2026-11-15. Status: bounded synthetic replay/checks complete locally; actual long-duration
cloud/hardware operation unmeasured. Owner: inline implementation. Decision: storage requirements
are separate from the ten-day query horizon; preserve the existing recording cap for this pass.

## Method

`experiments/companion/runtime_replay.py` generated two ten-second 640×360, 10 fps, video-only
MP4 profiles with FFmpeg/libx264: a static gray scene and moving `testsrc2`. Nominal encoder target
1 Mbps. Thirty clips occupy three known short intervals per simulated day over ten calendar days,
with large explicit gaps. Three additional clips have older-than-ten-days, future and unknown
capture-time conditions. These are labeled synthetic capture clocks, not reassigned household or
public-photo capture dates. Total generated/copy source duration is **330 seconds**, not ten days.

Actual capture journal, frame decoding, activity/coverage selection, indexing, SQLite vectors,
time filtering, restart/retry and source-byte checks execute. A deterministic 768-d RGB projection
replaces inference for load testing; it does not measure semantic accuracy, cloud throughput,
network availability or on-device model performance. No hardware, private media or provider calls.

```sh
uv run --no-sync python -m experiments.companion.runtime_replay --output data/runs/ten-day-runtime-v2
```

Fresh output directory required. Python 3.12.11, macOS arm64, locked application/Pillow/NumPy
environment and installed FFmpeg. V1 preceded the final aggregate failure guard; V2 reran that
guard and passed. Raw generated clips, databases and JSON metrics stay in ignored `data/`.

## Measured results

- All 30 in-window sources were eligible after reopen. The three older/future/unknown sources
  were excluded from the dated ten-day lookup; no missing or unexpected source IDs.
- All 33 original byte hashes survived indexing/recovery. Six fault checks passed: interrupted
  index requeued, explicit failed-index retry queued, missing source detected, restored source
  recognized, full budget stopped without deletion, and backlog refused additional work.
- Saved source files: 11,218,031 bytes. Selected JPEGs: 215, mean 12,575.6 bytes. Main index
  database: 933,888 bytes. Replay indexing elapsed 3.495 s; synthetic embedding computation is
  included, real inference is excluded. Peak Python-process RSS 141.39 MiB excludes FFmpeg
  children and real model processes. These are fixture measurements, not daily operating estimates.
- Separate metadata-only scale corpus: 10,000 768-d frame vectors. Five measured queries per
  route: flat median 26.64 ms; balanced median 92.24 ms. Source balancing has real SQL/window
  overhead. This small, warm corpus does not establish ten-day query latency or Hydra performance.

## Storage math, not a ten-day-in-1-GiB requirement

At a nominal 1,000,000 bits/s, ten continuous days project to **108 GB decimal** of raw video;
1 GiB covers about **2.386 hours** at that rate. Actual variable bitrate depends on scene/codec;
these generated clips are not a household compression benchmark.

A continuous two-second floor projects 432,000 samples over ten days. Float32 768-d vectors alone
require 1,327,104,000 bytes, before SQLite/metadata overhead. Using this fixture's mean JPEG size
would add about 5.433 GB of thumbnails, but real scenes can differ and activity can add samples.
The video cap does not include those derived files. These components must be budgeted separately.

The product does **not** need ten days of continuous footage inside 1 GiB. Ten days is a search
target. The existing cap remains a non-destructive pilot guardrail, not a capacity promise. A
larger configured budget, recording duty cycle or later retention choice should follow actual
device/disk measurements and an explicit user decision; no cap increase or expiry was applied.

## Failure found while testing

A truncated saved capture was still advertised as complete recorded/searchable coverage and
served through the saved-media route. Failing journal/API tests reproduced this. Availability
now requires the registered byte count, coverage excludes incomplete files and reports an
`unavailable_segment_count`, and both media/thumbnail routes refuse incomplete captured sources.
Bytes are preserved. Restoring the original file restores availability without rewriting dates.
This is a presence/size check, not a cryptographic checksum or same-size-corruption detector.
Imported videos lack a capture-journal byte count and retain their existing file/decode checks.

## Recommendation and limitations

Keep the bounded recovery/integrity guards, original recordings and current cap. Treat the
logical timeline as a repeatable backend test with gaps, not a ten-day soak. Provider STT/TTS,
real-model continuous indexing cost, hardware sleep/reconnect behavior and representative daily
storage still require separate measurement. The 10k-vector overhead is acceptable evidence for
this bounded local route, not proof of full-corpus performance. See
[R19](R19-recall-context.md) and [R18](R18-backend-recovery.md).
