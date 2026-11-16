# Wake activation and funded visual validation

The user asked to keep improving reliability and explicitly raised OpenRouter to$5 TOTAL.
No new approval gate or subagents: implementation details are delegated within the existing
backend/public-synthetic scope. Keep work/memory-reliability, regular commits and optional
branch backup. Preserve main, UI, recordings,1 GiB stop-without-delete, no hardware/private uploads.

## Choice and alternatives

Evaluate Sherpa-ONNX open-vocabulary keyword spotting first, using small published models and
an isolated experiment environment. It accepts custom phrases without vendor registration or
training a classifier. Compare against current Whisper wake inference. OpenWakeWord is another
possible route but Nyx needs a custom model/data and included model licensing differs from code;
Porcupine needs an AccessKey/custom console model. Neither is silently installed as the app default.
This is a research choice, not a measured quality claim or approved runtime migration yet.

Expand speech conditions beyond one TTS voice: speaker-separated synthetic development/holdout,
normal speech/near-name negatives, rate/noise/window variations, and a bounded licensed public
speech negative sample. Freeze labels/splits before comparisons. Preserve original audio and
separate exact/Nyx variants from confusable names, reporting false activation separately from
misses, latency and CPU. Do not add fixture-derived aliases or claim synthetic tests prove human
acceptance. Any selected detector must preserve wake/idle privacy and existing backend contracts.

Finish the wider real visual-model comparison on R22's fixed source/case labels and perform
development-selected then heldout checks. Keep source/count proxy caveats and manually audit
errors. Preserve the option to keep current defaults if a replacement does not establish a win.
No private dataset upload or account purchase. Cumulative guard=$5 with per-run limits/settlement
reserve. Freeze changes, regressions, full checks and findings before branch-only publication.
