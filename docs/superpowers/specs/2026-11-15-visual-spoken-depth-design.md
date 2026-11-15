# Deeper visual and spoken reliability evaluation

User authorized further testing/iterations on 2026-11-15, with general fixes and no case-specific
hardcoding. This continues the approved backend scope; no new approval or subagents are needed.

## Intent and constraints

Improve evidence correctness and spoken turn continuity while preserving contributor UI, stable
main, original recordings, existing storage policy and the cumulative $2 provider-test boundary.
Use public/synthetic inputs only, never physical camera/microphone or private uploads. Work and
regular commits remain on work/memory-reliability; branch-only backup is allowed. SQLite stays.

## Approaches and implementation choice

Compare current Lite verification with the already-used stronger Flash model on the same fixed
inputs. A second positive-corroboration pass is available, but R19's mixed results mean it is a
conditional experiment, not the preferred default. Cropping/detector pipelines would introduce
another failure surface and are deferred unless evidence justifies them. First compare single-pass
quality, latency and cost, then choose conservatively; do not promote from a few repaired cases.

Freeze image-separated development/holdout cases from the forty cached licensed COCO photos,
with category-count/negative/ambiguity labels from pinned annotations. These are proxy labels:
annotations can be incomplete, object counts can include tiny/occluded matches, and apparent
errors require manual review. New verification conditions are held out, not untouched images.
Track wrong positives, safe abstentions, missed positives, ambiguity, failures and latency separately.
Source IDs and original unknown photo times are preserved. No aggregate proves household accuracy.

Separately stress actual spoken SDK/socket/persistence and provider-protocol boundaries under
reordered VAD/transcripts, interruption, tool failure, duplicates, disconnection and restart.
Use synthetic transcripts/audio and injected external transport. Test general English/Hindi/
Hinglish household intentions, corrections and retrieval through the real backend where affordable.
These tests do not establish real acoustic STT/TTS quality. No new Sarvam spending without a
bounded cost allowance under existing authorization. Implement only reproduced general fixes,
with failing regressions first, then run frozen comparisons and full regression/browser checks.

## Success and limitations

Deliver reproducible broader evaluations, important general fixes, an evidence-backed visual
model/default decision and honest remaining gates. Do not edit code with fixture IDs, scene
coordinates, expected answers or object-specific bypass rules. Keep evaluation fixtures out of
runtime imports. Author review only; no independent review or merge-readiness claim.
