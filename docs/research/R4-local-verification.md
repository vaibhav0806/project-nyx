# R4 — Local visual verification and temporal answers

Owner: Codex, inline user-authorized M3 implementation
Status: In progress; first local feasibility results
Date: 2026-10-19
Decision affected: P5 / O5 and M3

## Question and method

Can an on-demand local VLM check retrieved source frames, preserve temporal attribution and return visible/not-visible/uncertain observations on this Mac?

Measured on M4 Pro / 24 GB unified memory with existing Python 3.12, PyTorch 2.14.1 / Transformers 4.57.6 and MPS. `experiments/visual-verification/run.py` compares two native Transformers models using the same prompt, strict JSON validation, at most 768 pixels on the long side and 180 generated tokens. Safetensors only; remote code disabled; revisions pinned below. Cached runs used `HF_HUB_OFFLINE=1`. No household media was uploaded or real room camera activated.

Six cases reuse the permitted R3 fixture: remote in the cats image, remote absent from coffee, keys absent from cats, coffee present, camera present, and remotes covered in the edited cats image. Sources/digests are in the input fixture's `dataset.json`. These are correlated edited public-image inputs, not six independent household scenes.

```bash
HF_HUB_OFFLINE=1 uv run --no-sync python experiments/visual-verification/run.py \
  --frames data/runs/siglip-crops-005/input_frames \
  --output data/runs/m3-verification-002.json
```

Use a new output file per run. Raw outputs remain ignored local artifacts. The fixture can be regenerated using the R3 experiment; see its README.

## Measured findings

| Model | Pinned revision | Validated visibility result | Cached load | Inference range |
| --- | --- | --- | --- | --- |
| Qwen3-VL-2B-Instruct | `89644892e4d85e24eaac8bacfd4f463576704203` | 6/6 labels matched: three visible, three not visible | 4.11s | 1.84–3.08s |
| SmolVLM-500M-Instruct | `a7da5b986cb59b408707209984f360a5f4ad7e47` | All six resolved to the conservative uncertain fallback; no usable positive/negative judgments | 1.63s | 1.40–4.41s |

The Smol result concerns this prompt/parser combination. Raw generated strings were not retained by this harness, so formatting and ambiguity failures cannot be separated from underlying visual performance. It is not a claim of 0% visual accuracy or a reason to dismiss all smaller models. A future comparison should retain raw strings and test model-specific prompting separately.

Post-inference MPS samples reached 3.98 GiB allocated / 4.72 GiB driver memory for Qwen, and 0.96 / 3.54 GiB for Smol. These are observed post-inference maxima in the sequential comparison, not true peaks, total system memory or the combined live-app footprint. Initial run Qwen inference ranged 1.96–5.57s; the second run above benefited from warm system/model caches. No percentile or long-run stability claim is made.

## Implemented product path

- Keep SigLIP 2 for background embeddings and native Qwen3-VL-2B for on-demand checks; the Smol model is only a benchmark candidate. No extra inference framework or cloud vision is introduced.
- Observation time is capture start plus decoded frame offset. Explicit aware time bounds use normalized UTC values; inclusive boundaries are covered by tests, avoiding SQLite floating date arithmetic. Unknown import/interrupted-tail clock times remain unknown.
- Latest mode checks up to twelve newest dated samples first, then up to five older semantic candidates if needed, ordered by time and deduplicated. This fallback lets an older relevant observation survive a recent window with no object; it does not establish an exhaustive latest sighting. The answer states its checked scope. Relevance mode checks up to five similarity candidates and can report unknown clock time.
- The VLM inspects original source frames at the selected offsets. Source-linked neighboring samples within four seconds are offered as unverified context, within the selected time bounds. No motion, identity continuity or persistence through a gap is inferred from them.
- Current-view inspection uses an explicitly requested snapshot from the already-enabled browser camera. Bytes/pixels are bounded; snapshots older than fifteen seconds or more than two seconds ahead are rejected. Freshness is rechecked after queueing/model load. An answer shows capture time and age and never guarantees the scene stayed unchanged during inference.
- Snapshot image/answer data is ephemeral in the bounded job result, not permanently saved as new history. Historical answer jobs are invalidated when a checked source is deleted. Model judgments can still be wrong; schema validation only prevents malformed/ambiguous output from becoming a positive confirmation.

## Verification and remaining work

Deterministic tests cover exact time boundaries, offset/date ordering, unknown dates, recent scan plus older fallback, malformed/ambiguous judgments, actual source decoding, scoped neighboring context, deletion invalidation, stale queued/model-load snapshots and bounded interactive work. Real-model browser checks exercise a dated remote query bounded to 10:00:13–10:00:15 UTC and replay at 00:14, an unknown-date query that stays uncertain, and an explicitly captured synthetic current-view snapshot. See the [M3 plan](../superpowers/plans/2026-10-19-visual-answers.md) for final checks and artifacts.

The public-image labels only score visibility. Landmark descriptions, duplicate-object ambiguity, occlusion, small objects, camera movement, complete last-sighting recall and intended-user outcomes have not been independently validated. Natural-language relative-time/event interpretation is not implemented: this UI uses explicit mode and date bounds. M3 remains in progress until labelled household/uncertainty trials establish useful behavior. M1/M2 household and actual-camera soak gates also remain open.

## Primary sources

- [Qwen model and usage](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct)
- [Transformers Qwen3-VL documentation](https://huggingface.co/docs/transformers/v4.57.1/model_doc/qwen3_vl)
- [SmolVLM model and usage](https://huggingface.co/HuggingFaceTB/SmolVLM-500M-Instruct)
