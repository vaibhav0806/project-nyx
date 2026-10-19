# Companion and event experiments

These are opt-in local model experiments, separate from deterministic tests. They open no real camera/microphone and call no cloud provider. Use fresh output directories. Raw data, model generations and databases stay under ignored `data/`.

## Conversational tools

Generate the permitted public-image smoke fixture using the existing retrieval experiment, then:

```sh
HF_HUB_OFFLINE=1 uv run --no-sync python experiments/companion/run.py \
  --fixture data/runs/companion-retrieval-fixture \
  --output data/runs/companion-new
```

The script records local planner decisions, raw generations, a current-view request, recent-history follow-up with older distractor footage, and departure reminder creation/cancellation. Inputs are development cases, not held-out household or language evaluation. An action label match does not establish the correctness of the reply text. The API applies additional policy checks; a bare model may propose unsupported behavior.

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

## Browser wiring

```sh
uv run --no-sync python tests/companion_browser_smoke.py --output data/runs/companion-browser-new
```

This check uses generated camera frames and deterministic model boundaries. It validates wiring, not recognition quality. The existing voice/browser checks and longer recording smoke remain separate; see the README for their commands and limitations.
