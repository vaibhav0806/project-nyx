# R24 — Broader wake activation comparison

Date2026-11-15. Status: offline development/heldout evaluation in progress. Owner: inline.
Decision: replace or adjust current wake recognition only with a measured gain, no new aliases.

## Primary research and approach

Sherpa-ONNX provides open-vocabulary keyword spotting without training a model for each phrase;
engine code is Apache2.0. Porcupine needs an AccessKey and custom console artifact; OpenWakeWord
needs a custom Nyx model, and its supplied models have different licensing from its Apache code.
Evaluate Sherpa first in an isolated environment, not a runtime replacement. Official sources:
[Sherpa keyword method](https://k2-fsa.github.io/sherpa/onnx/kws/index.html),
[published models](https://k2-fsa.github.io/sherpa/onnx/kws/pretrained_models/index.html),
[engine license](https://github.com/k2-fsa/sherpa-onnx/blob/master/LICENSE),
[OpenWakeWord](https://github.com/dscripka/openWakeWord),
[Porcupine setup](https://picovoice.ai/docs/quick-start/porcupine-python/).

## Data, versions and boundaries

Model: sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20, chunk16 int8 encoder/joiner and fp32decoder.
The32,885,699-byte archive SHA256 is68447f4fbc67e70eee3a93961f36e81e98f47aef73ce7e7ca00885c6cd3616a6.
Keyword phonemes for Nyx/hey/hi/okay come from the model's own English lexicon, including NYX;
no newly accepted names or test-specific utterance substitutions. Published engine license is
not an assertion that every possible downstream model/dataset has identical terms; raw assets
stay ignored, not bundled or redistributed. The prior model/runtime remains active during tests.

Isolated data/experiments/wake-env: Python3.12.11, sherpa-onnx2.0.1, soundfile0.14.0,
pyarrow26.0.1, NumPy2.5.4. App dependency files are unchanged. Downloaded assets are bounded;
about18GiB free was verified before downloading the32.9MB model and9.2MB speech sample.

Frozen233-case manifest:80 development and153 heldout. Synthetic sources use Samantha/Daniel
only for development and Rishi/Moira only for holdout, at150/205 words/minute, clean/15dB Gaussian
noise variants, with200ms leading/500ms trailing silence. Different utterance text across splits.
Wake variants, ordinary speech, near names and literal homophones are scored separately.
All variants of a voice/source stay in the same split. These are four TTS voices, not humans.

Public negatives:73 LibriSpeech read-speech clips from one speaker1272, entirely held out,
481.035seconds. Source: hf-internal-testing/librispeech_asr_dummy, pinned parquet SHA256
4e69a06fa5edc90921e5e7e39a7084881f8b3ed9c805c574f4f39c6fde27c603. LibriSpeech is attributed to
Vassil Panayotov etal, derived from LibriVox and distributed CC-BY4.0 by
[OpenSLR12](https://www.openslr.org/12). The mirror card lists73 examples but no independent
license grant; provenance is the original corpus. No transcript/audio is committed.

Use frozen source hashes, actual RMS gate and overlapping750ms probes up to3s, plus the final
available endpoint. This is a clip-level any-hit experiment, not independent false alarms/hour.
Extra endpoint, artificial silence/noise and one public speaker limit representativeness. Raw
source audio, source identity and split labels are preserved. Scorer/window tests passed after
RED missing-module tests. Failed/not-run cases remain in denominators.

## Initial development observations

Whisper:80 cases,63 correct, wake31/32,16 false activations (8near-name/8homophone), ordinary0.
Sherpa threshold0.25/score1:51/80, wake14/32,11 false (3near-name/8homophone), ordinary0.
Threshold0.10 did not change those outcomes. Do not promote this recall regression. Decoder
score2 is a development-only calibration trial; heldout remains sealed until selection.

The broader Whisper recall is much higher than R23's first ten clips. The original result must
not be generalized to human or everyday performance. A separate leading-silence ablation on
the old ten clips improved intended detections1/4→3/4 without fixing near-name confusion;
adding trailing silence did not help. A generic200ms internal-head-padding candidate is being
tested on the frozen broader development set before any runtime change. No alias expansion.

Inference runs overlapped on the CPU during initial comparisons; do not turn their timing into
a standalone latency claim without a sequential measurement. Dataset manifest and results live
under data/evaluation/wake-expanded-v1 and data/runs/wake-expanded-*.

## Frozen wake selection before holdout

Score2/threshold0.25 keyword calibration reached17/32 wakes but14 false activations; it still
does not match Whisper recall, so the keyword route is not selected. Head-padding development
kept31/32 wakes and reduced one near-name false activation (16→15), with no individual query
regression versus Whisper. Combined with the old ten-clip diagnostic1/4→3/4 wake recovery,
freeze200ms internal leading silence as the candidate for heldout comparison. It changes no
aliases, wake phrases, input coverage or recording bytes. Do not add trailing silence: that
development diagnostic did not help. Baseline/head heldout runs started after this selection;
their detailed results remain out of tuning. Model cache, thresholds and source hashes stay fixed.

## Heldout decision

Both153-case runs completed with no failed inference. Baseline:136 correct, wake31/32,
16 false activations (8homophone/7near-name/1public-speech), ordinary0. Head padding:133 correct,
same31/32 wake recall,19 false activations (8homophone/8near-name/3public-speech), ordinary0.
Reject head padding as a default: the small development gain did not generalize. Do not tune it
on these heldout clips, add aliases, or hide the public-speaker errors. Current wake implementation
stays unchanged. The233-case source/voice evidence is broader than R23, still not human-positive
or room-acoustic acceptance. Dedicated acoustic/intent calibration and homophone limitations
remain product work; paid credits do not resolve acoustically identical names by themselves.
