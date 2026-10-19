# M3 temporal retrieval and visual answers

Execute inline with the existing Python/browser stack, no subagents. User explicitly requested M3 on 2026-10-19. Preserve all existing local M2 changes and recordings; no publication, automatic camera activation or cloud media.

**Goal:** Inspect visual candidates on demand, answer with evidence and time, and distinguish fresh snapshots from historical sightings.

**Approach:** Use real capture start plus decoded frame offset for observation time. Explicit timezone-aware bounds and newest-first scanning implement temporal context; imports/uncertain capture tails keep unknown clock time. A lazy local VLM checks one image at a time on the existing worker and yields between images. Heavy inference stays off the API loop. Model outputs are fallible and labelled model-checked, never established ground truth.

## Tasks

- [x] Temporal storage/retrieval: add aware `seen_after`, `seen_before`, `order` filters and computed `observed_at`, preserving existing offset filters. Latest mode scans chronologically, not a similarity shortlist reordered after truncation. Return explicit inspected/candidate limits and coverage caveats; unknown clock times are excluded from wall-clock/latest scans, not silently dated by import time.
- [x] Local verifier: benchmark pinned Qwen3-VL-2B-Instruct and SmolVLM-500M-Instruct on identical permitted frames. Use native Transformers, safetensors, no remote code, bounded pixels/output. Strict structured visible/not-visible/uncertain output; invalid output stays uncertain. Read original source frames at evidence offsets. Location text must remain qualified model output.
- [x] Historical answers: `POST /api/answer` object description, latest/relevance mode, optional video and aware time bounds. Check a bounded set, retain per-image judgments/source links and model identity, select latest positive only within checked known-time history. Neighbors provide temporal context without implying an object moved or stayed put across gaps. Do not infer absence from no positive match.
- [x] Fresh inspection: `POST /api/inspect` receives an explicitly captured, video-only snapshot from the already enabled browser camera, aware capture time, bounded image bytes/pixels. Reject old/future/queued-expired snapshots. Return exact inspected image/time in the bounded ephemeral job result; do not save snapshots to permanent history. State current answers at snapshot time and age, not guaranteed present location.
- [x] UI: explicit object description, history mode/time bounds and current-view action; evidence-linked answer panel, uncertainties and inspected coverage. Keep existing candidate Search, capture and deletion controls. Clear answer state on deletion and never reopen camera automatically.
- [x] Verification: RED/GREEN deterministic time/ranking/unknown-time/gap/invalid-model tests; API error/busy/recovery/deletion tests; real-model permitted-image benchmark and synthetic-camera browser check. Update R4 and canonical docs with exact evidence/limits, and retain M1/M2 hardware/household gates.

## Engineering calls

- Use existing PyTorch/Transformers rather than introducing MLX/provider infrastructure. Compare 2B and 500M local models before choosing; a two-model smoke comparison is not a household benchmark.
- Latest mode inspects twelve newest dated samples first, then up to five older semantic candidates if needed, deduplicated and ordered by observation time. It stops at the first positive and explicitly reports the bounded scope; this cannot guarantee the archive’s true last sighting. Relevance mode checks up to five similarity candidates. No similarity score is treated as a presence probability.
- Ask for an object description and explicit mode/bounds in this developer UI. Unrestricted natural-language temporal parsing and identity continuity across duplicate objects remain later improvements.
- Snapshot evidence is ephemeral and returned with its answer, not silently added to the saved video budget. Reload/pruned jobs lose it; history answers stay tied to managed sources and clear on deletion.
- Queued searches have priority; VLM work yields after each image. In-flight model generation/load cannot be preempted, so report latency/backlog honestly. No permanent verifier-result cache is needed for this slice.

## Evidence

- Two pinned models ran locally on MPS. [R4](../../research/R4-local-verification.md) records the six-case public-image comparison, exact latencies and memory caveats. Qwen matched six visibility labels; Smol resolved all six to conservative uncertainty under this prompt/parser contract. No independent household/location/identity accuracy is established.
- Deterministic and API suite: 73 tests pass, including time-bound/context ordering, unknown dates, older semantic fallback, structured uncertainty, source deletion invalidation and snapshot expiry during queue/model load. Tests were observed RED before the corresponding implementation/fix.
- Real-model browser check includes local-time bounds converted to UTC, an unknown-date query remaining uncertain, a dated remote observation at 00:14 with source replay, explicit synthetic snapshot evidence while capture continues, and the prior capture/pause/recovery/deletion/no-auto-camera/mobile checks. Artifacts: ignored `data/runs/web-m3-005/`; final run passed, including date-bounded context, exact source replay, current snapshot and mobile checks. Lint, formatting, JavaScript syntax, isolated tests, package build and documentation links passed.
- Ruling: added an older semantic fallback after a regression showed twelve recent samples alone could miss a known older object. The answer still reports checked scope rather than absolute last sighting. Context samples now obey the same date bounds.
- Ruling: use Python UTC observation-time calculation registered with SQLite; Julian-day arithmetic failed an inclusive-boundary test due to floating precision.
- Native Transformers >=4.57.1 is declared and the lock retains tested 4.57.6. No remote code, cloud image processing or actual room-camera activation was used.
- M3 remains in progress for independent household/uncertainty, location and duplicate-object evaluation. M1/M2 actual-camera gates stay open; no new work is pushed without publication instruction.
