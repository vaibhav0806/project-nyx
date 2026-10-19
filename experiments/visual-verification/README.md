# Local visual verification comparison

Compare pinned Qwen3-VL-2B and SmolVLM-500M on the same permitted R3 frames and strict structured visibility contract. This tests local runtime and schema viability; it is not household accuracy or location/identity validation.

Install the existing vision extra and generate the R3 fixture first. Models download to the normal external Hugging Face cache on first use; media is processed locally. Qwen is the application baseline; Smol is comparison-only. See [R4](../../docs/research/R4-local-verification.md) for revisions, measurements and caveats.

```bash
uv sync --extra vision --extra web
uv run --no-sync python experiments/visual-verification/run.py \
  --frames data/runs/siglip-crops-005/input_frames \
  --output data/runs/m3-verification-new.json
```

Choose a fresh output file. Add `HF_HUB_OFFLINE=1` after downloading both pinned checkpoints to verify cached execution. JSON records model/revision, load/inference times, validated results and post-inference MPS allocations; these memory samples are not true peaks. Generated raw strings are not retained, so conservative parser failures cannot be separated from visual errors in this first harness.

The result determines whether a model is usable for the current on-demand checking path. Smaller-model prompt tuning and independent labelled household trials are follow-ups. Never add personal footage to this fixture or Git.
