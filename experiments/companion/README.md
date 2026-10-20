# Companion and event experiments

These are opt-in local model experiments, separate from deterministic tests. They open no real camera/microphone and call no cloud provider. Use fresh output directories. Raw data, model generations and databases stay under ignored `data/`.

## Conversational tools

Generate the permitted public-image smoke fixture using the existing retrieval experiment, then:

```sh
HF_HUB_OFFLINE=1 uv run --no-sync python experiments/companion/run.py \
  --fixture data/runs/companion-retrieval-fixture \
  --output data/runs/companion-new
```

The script records local planner decisions, raw generations, a current-view request, recent-history follow-up with older distractor footage, departure reminder creation/cancellation, and a separate unknown-time import workspace. Inputs are development cases, not held-out household or language evaluation. An action label match does not establish the correctness of the reply text. The API applies additional policy checks; a bare model may propose unsupported behavior.

For more targeted query construction and actual agent-loop continuation checks:

```sh
HF_HUB_OFFLINE=1 uv run --no-sync python experiments/companion/planner.py \
  --output data/runs/planner-query-new
```

This uses real Qwen decisions with **controlled tool observations**, opening no devices,
retrieving no images and performing no real reminder mutations. It checks descriptive
attributes, corrections, pronouns, current/history policies, widening, undated imports,
no-camera fallback, bounded uncertainty and cancellation ID selection. Raw generations,
actual tool traces, policy adjustments and case checks remain local. Concept checks
are deliberately narrow and still need manual review; ten development cases do not
establish general conversation or household retrieval accuracy. `--cases NAME ...`
selects cases without reusing an output directory.

## Temporal window

```sh
uv run --no-sync python experiments/companion/window.py \
  --manifest data/evaluation/departure-manifest.json \
  --output data/runs/temporal-window-new
```

Omit `--manifest` for generated scenes only. No model loads. The script replays
generated static/flash/placement/motion scenes, then optionally densely decodes the
existing local public clips. It exercises the actual window and observer with a
declared replay clock and immediate admission, recording selected source offsets,
episode IDs and potential model nominations. Public labels describe earlier selected
subsequences, so whole-clip nomination counts are not departure accuracy. Temporary
decoded public frames are removed; originals, hashes and result metadata stay local.

## Selected public video

`fetch_charades.py` reads a central directory and named compressed members using HTTP ranges. It refuses non-range responses, individual ranges/clips over 8 MiB, and more than 32 MiB per run. It never downloads the complete ~16 GB archive. Source URL, selected member paths, hashes and byte counts are recorded beside the clips.

**Charades is evaluation-only here.** Its license allows evaluation elsewhere but restricts commercial use and redistribution. Read `Charades/license.txt` in the official annotations archive before other uses. Do not commit or publish its clips, frames, screenshots or contact sheets. Reference: Sigurdsson et al., *Hollywood in Homes* (2016), https://arxiv.org/abs/1604.01753; official archive URL is in the script. This is not a source of reusable product/demo footage.

```sh
uv run --no-sync python experiments/companion/fetch_charades.py \
  --output data/evaluation/selected-charades --ids 3H0PT BM3UJ VXJS4
```

Inspect and label sequences before model inference. A manifest contains a `cases` array; each case has `name`, `frames` (directory of chronological JPEG samples), `indices` (zero-based), `expected` (`departure`, `no_departure`, or `uncertain`), and `label_note`. Preserve actual decoded offsets separately. Staged room exits do not establish leaving home or sufficiently early real-time reminders.

```sh
HF_HUB_OFFLINE=1 uv run --no-sync python experiments/companion/departure.py \
  --manifest data/evaluation/departure-manifest.json \
  --output data/runs/departure-new
```

Record failures, prompt changes, inference time and raw output. Reusing cases to revise prompts does not produce held-out accuracy. Run model processes sequentially on this 16 GiB machine; simultaneous Qwen processes caused heavy swapping. Current findings are in [R8](../../docs/research/R8-companion-loop.md).

Add `--reverse-check` to diagnose temporal direction sensitivity on every case. It runs
the identical prompt/model on the original and reversed image order, records both raw
outputs and timings, and reports whether a forward positive becomes a clear reversed
negative. This is an experiment only; it does not add a second inference to the app.
The follow-up in R8 rejects that gate because it loses two of three departure proxies
and still retains a stationary-doorway false positive. `motion_selected` separately
reports the inexpensive scene-change nomination; it does not establish departure.

Run that inexpensive gate alone on the manifest and controlled static/noise/local-change
inputs, without loading a model:

```sh
uv run --no-sync python experiments/companion/motion.py \
  --manifest data/evaluation/departure-manifest.json \
  --output data/runs/departure-motion-new
```

All nine current public sequences pass this gate, including the negative cases. Its
purpose is to skip unchanged scenes; it supplies no semantic/direction accuracy claim.

`video_native.py` compares explicitly time-labelled image inputs with Qwen's native timestamped video preprocessing using the **same** prompt and cases. This isolates an input-representation hypothesis; it is not additional independent evaluation. Run one mode at a time:

```sh
HF_HUB_OFFLINE=1 uv run --no-sync python experiments/companion/video_native.py \
  --manifest data/evaluation/departure-manifest.json --mode video \
  --output data/runs/departure-native-new
```

Use `--mode labelled_images` with another fresh output directory for the comparison. Relative timestamps come from the manifest's two-second sampling protocol, not capture clock time.

To exercise the actual request → live-observer → pending-notification API with the
local model, densely replay excerpts at their decoded time intervals:

```sh
HF_HUB_OFFLINE=1 uv run --no-sync python experiments/companion/live.py \
  --manifest data/evaluation/departure-manifest.json --cases 3H0PT BM3UJ \
  --output data/runs/companion-live-new
```

This locates an excerpt using the manifest's prior nominal two-second indices, with
one second before and three after; actual dense decoded offsets drive replay. It
records every admitted observation job, actual sampling gaps, raw judgments and
request/delivery state. Gaps over the window's continuity limit invalidate context.
This records errors rather than asserting every case passes. No saved segment must
finish first. It starts no device, uses an explicit replay clock rather than an
original capture date, disables voice and makes no speech/advance-warning claim.
The earlier sparse two-second replay cannot establish subsecond persistence and is
superseded by this protocol for current code.

## Browser wiring

```sh
uv run --no-sync python tests/companion_browser_smoke.py --output data/runs/companion-browser-new
```

This check uses generated camera frames and deterministic model boundaries. It validates wiring, not recognition quality. The existing voice/browser checks and longer recording smoke remain separate; see the README for their commands and limitations.

Add `--speech` to exercise generated reminder audio, played state, separate acknowledgement and no repeated claim. After the longer synthetic recording smoke has **stopped its server**, verify the same workspace through a process restart:

```sh
HF_HUB_OFFLINE=1 uv run --no-sync python experiments/companion/restart.py \
  --workspace data/runs/continuous-soak-20261020/workspace \
  --output data/runs/continuous-restart-new
```

This checks source persistence, recovered indexing, semantic candidate search and HTTP range playback. It starts no browser or hardware and does not verify that a retrieved object is present.

For an existing **synthetic** recording-smoke workspace, add `--check-library-deletion` to exercise multi-page library access, cancelled/confirmed deletion of its `scenes.mp4` fixture, preservation of other clips, reload and mobile layout in isolated Chrome with hardware requests disabled. This flag actually deletes that synthetic import. Do not use it on a personal workspace. Long recording measurements are saved separately before subsequent lifecycle checks, so a later harness failure does not erase the completed phase's evidence.
