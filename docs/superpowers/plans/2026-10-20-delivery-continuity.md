# Reject superseded live evidence before creating a reminder

Authorized continuation after the full-trajectory failures. Keep the current models
and worker. A positive semantic result must not create a notification from evidence
that has been superseded during generation.

Reuse the bounded observer buffer and shared ActivityWindow. At positive-result
completion require the exact last inspected frame to remain in the same camera
epoch, a latest capture no older than 0.5 seconds, and no newly qualified persistent
change since that image. An unfinished change waits for new evidence. A completed
brief returned-to-baseline flash alone does not invalidate an otherwise continuous
scene. Persist the guard's actual checked-through time and reason separately from
semantic image times; unchanged pixels do not establish continued person presence.

This is a conservative rejection guard, not a new recognition model. Lost window,
capture gaps and sustained scene change leave the request armed. Normal subsequent
activity can nominate another check. No inference loop, cloud call, extra model,
manual doorway coordinates or per-video rule. Slow generation can now suppress all
otherwise positive results: reducing latency remains necessary, not solved here.

Verification: deterministic stable/flash/persistent-change/return/epoch/window/stale
capture cases; an actual API check blocked during generation while new frames arrive;
full tests, generated browser flow, and a real-model replay of the previous late
positive and false indoor action. Reused clips are targeted regressions, not new
accuracy evidence. Keep the false exterior-door inference documented even if the
new age/continuity guard prevents a notification. Local commit only; no push.

## Resource pause and model follow-up

The user paused model runs after memory pressure on 2026-10-20. Both the model
replay and full-test processes were terminated and their exit verified. The targeted
observation/API suite passed 39 tests before the pause; a further stale-capture test
and full-suite verification remain pending. First real replay timed out loading the
model; the second was interrupted. Neither supplies completed recognition evidence.
Heavy inference stays paused until resumed; lightweight code/docs research is allowed.

Current runtime is Qwen3-VL-2B-Instruct, BF16 on MPS (FP32 on CPU), not quantized.
User requested newer Qwen vision models and suggested 8-bit or dynamic 6-bit builds.
Metadata checked 2026-10-20, without downloading/loading weights:

- https://huggingface.co/Qwen/Qwen3.5-4B : official newer vision-capable model.
- https://huggingface.co/mlx-community/Qwen3.5-2B-8bit : candidate first low-memory
  comparison, revision 562fb8ea19bbe7565a3ddf5b7d49899ea2c88d2b.
- https://huggingface.co/mlx-community/Qwen3.5-4B-8bit : larger comparison only if
  headroom permits, revision 1704583a86670ba531b7f2c92530a2f725cfd45b.
- https://huggingface.co/unsloth/Qwen3.5-4B-GGUF : revision
  e87f176479d0855a907a41277aca2f8ee7a09523 lists Q6_K, Q8_0,
  UD-Q6_K_XL and UD-Q8_K_XL plus vision projectors. This is an alternative runtime
  path, not a drop-in replacement for current Transformers/MPS loading.

Proposed selection: first measure the newer 2B 8-bit model with the same image and
conversation cases, then consider 4B if quality warrants its cost. Model-card claims
are source-reported, not Nyx measurements. Check multi-image processing, JSON/text
output and thinking-mode controls before integration. Quantized weight size does
not equal peak runtime memory. No benchmark or new runtime is installed yet.

User explicitly authorizes removing obsolete model downloads when switching models.
Inventory cache paths first; download only one candidate, keep the baseline through
validation, then remove Nyx's unused weights using cache-aware deletion. Preserve
shared/in-use models, application data and recordings. If disk cannot hold a temporary
comparison, report the tradeoff rather than deleting an unverified dependency.

Subsequent user decision: selected Qwen3.5-2B 8-bit, then permitted one image smoke.
Implemented the lazy MLX adapter and installed its locked dependencies. The single
smoke passed (5.62 s load, 2.91 s generation, 2.70 GiB MLX peak); process exited.
Removed the old Qwen3-VL cache with HF cache tooling, freeing 4.3 GB. Full deterministic
suite now passes 234 tests. Real-video continuity and new-model quality evaluation
remain paused, not completed. R8 and milestones distinguish these boundaries.
