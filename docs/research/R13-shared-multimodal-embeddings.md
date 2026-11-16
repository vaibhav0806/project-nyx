# R13 — Shared embeddings and experiment order

Date: 2026-11-15. Owner: inline agent. Status: code/primary-source research complete;
new representation benchmarks not run. Decision affected: pilot embedding representation,
raw-audio scope and experiment order.

## Question and hypothesis

Can aligned text/image/video representations improve labeled recall without harming small-object,
temporal or source-attribution behavior? The user approved exploring shared embeddings and adopting
a change only if accuracy warrants it. Hypothesis: better use of the existing aligned encoder,
reference-image nomination and bounded clip representations can improve the current candidate
pipeline. This is a hypothesis, not a measured quality result.

## Method and inputs

Inspected `perception.py`, `statements.py`, `retrieval.py`, `answers.py`, R9/R12, and primary Google,
OpenRouter and Qwen documentation. Queried the unauthenticated OpenRouter embedding-model catalog
on November 15. No model inference, paid request, model download, hardware capture or private-media
upload was performed. No runtime was installed or changed.

## Observed in Nyx and the public catalog

- `CloudEncoder` defaults to `google/gemini-embedding-2`, 768 dimensions, normalizes vectors and
  records a fingerprint. Environment overrides may differ from these code defaults.
- Images and text use the same model through separate input records. Videos currently become
  timestamped frame embeddings, not native video-segment embeddings.
- Statements embed an inferred object description plus the exact transcript as text. Statement
  and visual records remain separate despite their configured common space.
- Text inputs use bare content; query/document task roles are not explicit. Reference-image
  checking happens after text nomination, leaving an additional candidate-generation opportunity.
- The public `/api/v1/embeddings/models` catalog advertised text, image, file, audio and video
  inputs for Gemini Embedding 2. This is advertised metadata, not a successful Nyx video request.
  The model page's prose describes text/images while its provider table lists other modalities;
  verify the wire contract and provider route before relying on native video input.

## Source-reported capabilities

- Google describes aligned text/image/video/audio representations. Its guide recommends task
  instructions for text-only retrieval; adding them to combined multimodal content may hurt.
- Google documents video inputs up to 120 seconds with at most 32 sampled frames; short videos
  use one frame per second. Audio tracks are not processed through that video path.
- Qwen3-VL-Embedding-2B's model card lists text/image/video inputs, instruction support,
  2048-dimensional output and Apache 2.0 licensing. This is a research alternative, not a measured
  local deployment. Its vectors cannot be mixed with Gemini vectors by matching dimensions.

## Inference for Nyx

A shared space supports text-to-frame, image-to-frame and text-to-statement candidates. It does
not establish unique identity, temporal order, truth or calibrated similarity across record types.
Keep modality, source kind, source time, offset, attribution and model/preprocessing fingerprints.
Use per-source candidate budgets before fusion so visual duplicates cannot crowd out statements.

Whole-clip vectors may dilute a brief/small appearance. Preserve exact frame anchors and source
verification even if clip vectors improve event nomination. A sampled-video encoder does not
remove coverage testing. Transcripts represent recognized speech, without preserving non-speech
events or recovering transcription errors. Raw-audio retrieval is unnecessary for this pilot.

## Controlled evaluation

1. Freeze the actual current encoder/fingerprint, dimensions, corpus and query set as baseline.
2. Evaluate/fix sampling coverage before attributing missing events to embedding quality.
3. Compare reference-image nomination and bare versus documented text query/document formatting.
   Do not blindly apply text-only instructions to images/mixed inputs. Include English,
   Hindi/Hinglish, paraphrases and transcript errors.
4. If the current route and remaining budget permit a public-fixture smoke test, compare short
   native video windows, frame candidates and their fusion. Preserve offsets and distinguish
   pooled frames from native video. Include reversed actions and brief placements.
5. Consider dimensions or Qwen only if a representation limitation remains and resources permit.
   Keep any alternative runtime isolated from the application; no new dependency is selected here.

Measure event retention, Recall@12, correct evidence intervals, identity failures, grounded answer
success, abstention and language-specific results. Keep verification budgets fixed and report added
indexing/storage/inference cost. Cached replay is not live provider latency. Tune on development
episodes and freeze the chosen configuration before untouched holdout evaluation.

Version changes to text roles/formatting, preprocessing, video sampling or dimensions in encoder
fingerprints. Use separate development indexes or atomic rebuilds preserving media, IDs and times.
Cache reuse requires matching inputs and fingerprints. Vendor benchmarks do not select a winner.

## Recommendation and sequence

Retain the configured aligned text/image baseline. Evaluate better candidate nomination and short
video representations through the labeled harness; promote only measured useful improvements
without critical attribution, temporal or correction regressions. Defer raw-audio embeddings;
existing activated STT and voice behavior remain separate.

Order: isolate Nyx storage and freeze baseline manifests; address coverage; evaluate candidate
representations; tune retrieval/memory policy; compare Hydra with the same representation; exercise
recovery and polish; freeze and run held-out evaluation. Do not conflate encoder and backend changes.

The November 15 SSH connection with the supplied key succeeded, and a running Hydra container was
observed in another application's stack. No Nyx namespace/service has been created. Isolation must
precede writes. A running vector/graph store does not establish an embedding inference service.

No new provider account or spending is implied. Respect the cumulative test budget, public/synthetic
developer inputs, source preservation and 1 GiB stop-without-delete rule. See the
[engineering design](../superpowers/specs/2026-11-15-memory-reliability-design.md).

## Limitations and primary sources

No new embedding accuracy, language quality, temporal understanding or local throughput was measured.
Catalog modalities are not endpoint verification; public benchmarks do not establish household recall.

- [Google embedding guide](https://aistudio.google.com/docs/embeddings)
- [OpenRouter model](https://openrouter.ai/google/gemini-embedding-2)
- [OpenRouter API](https://openrouter.ai/docs/api/reference/embeddings)
- [Live catalog](https://openrouter.ai/api/v1/embeddings/models)
- [Qwen model card](https://huggingface.co/Qwen/Qwen3-VL-Embedding-2B)
