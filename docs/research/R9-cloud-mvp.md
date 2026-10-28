# R9 — Cloud MVP inference

Date: 2026-10-28. Owner: inline implementation. Status: cloud integration implemented;
controlled evaluation passed, household and departure reliability remain unproven.

## Question and decision

Can cloud inference replace the constrained local stack while improving agent
feedback handling and preserving evidence, interruption and storage behavior?
The user approved OpenRouter as the primary path, image embeddings/reindexing and
activated STT/TTS, supplied a key with a $2 cap, and authorized local commits only.
Tests use synthetic audio/images and the existing public-image slideshow. No real
camera/microphone or private household footage was used.

**Measured recommendation:** use GPT-5.4 Mini for the planner and GPT-5.4 for visual
inspection, Gemini Embedding 2 (768 dimensions), GPT-4o Mini Transcribe and Gemini
3.8 Flash Lite TTS (Kore, 24 kHz mono PCM wrapped in WAV). Keep local Whisper tiny.en
CPU/int8 wake recognition, activity filtering, small MobileNet detection and storage.
No local LLM/VLM fallback is retained. Hosted model IDs are not immutable checkpoint
hashes; these results establish behavior on this date, not future provider identity.

## Environment and method

Apple Silicon laptop, macOS, Python 3.12.11; dependencies locked in `uv.lock`.
`uv sync --extra web --extra voice --extra vision` removed MLX, mlx-vlm and
Transformers from the actual environment. Cloud transport uses standard-library
HTTPS with a 45-second timeout, bounded responses and no application retry.
Every request sets `provider.data_collection=deny`; this does not guarantee zero
retention. Secrets and raw artifacts stay in ignored local storage.

The model catalog and key limit were checked directly using OpenRouter's API.
Raw catalog snapshots are `data/runs/openrouter-{models,embeddings-models,speech,transcription}.json`.
Provider wire formats were checked against official documentation:
[modalities](https://openrouter.ai/docs/guides/overview/multimodal/overview),
[embeddings](https://openrouter.ai/docs/api_reference/embeddings),
[STT](https://openrouter.ai/docs/guides/overview/multimodal/stt),
[TTS](https://openrouter.ai/docs/guides/overview/multimodal/tts).
These are source-reported contracts; the checks below exercised actual endpoints.

## Measured results

| Check | Result | Local evidence |
| --- | --- | --- |
| Initial API smoke | Planner, synthetic square vision, 768-d image/text embeddings and TTS passed; individual calls about 1.7–3.0 s | `cloud-initial-smoke.json` |
| Speech round trip | Generated “Hello. Where are my reading glasses?” transcribed correctly | `cloud-stt-smoke.json` |
| Existing planner regression | **21/21**, up from preceding local runtime 17/21 | `cloud-planner-final/results.json` |
| Feedback/transfer cases | **10/10**, up from local 5/10 | first 10 cases of `cloud-feedback-final/results.json` |
| Additional development cases | **12/12**, up from local 5/12 | remaining cases of `cloud-feedback-final/results.json` |
| Guided real-model finding API flow | **7/7** with full GPT-5.4 vision | `cloud-mvp-strong-vision/results.json` |
| Synthetic index rebuild | 24 frames re-embedded; original recording hashes and video metadata unchanged; 3 searches worked | `cloud-rebuild.json` |
| Companion browser flow | Pass: fake devices, rejection/confirmation, brief-flash filtering, proactive speech/acknowledgement, cancellation and playback denial | `cloud-browser/results.json` |
| Voice browser integration | Pass: real local wake on synthetic speech, playback interruption, mute, permission failures and reload; cloud boundaries mocked | `cloud-voice-browser-wake/results.json` |
| Real cloud voice API chain | Pass: local wake → real STT → agent → vision → TTS; 9.11 s to generated audio | `cloud-voice-integrated/results.json` |

All artifact paths above are under ignored `data/runs/`. Planner tests use actual
model decisions but controlled tool observations, not actual household retrieval.
Their sets have been used during development and are not untouched holdouts.
The voice API test uses a drawn pair of spectacles and synthetic speech, produces a
WAV but does not play it through physical speakers. Its timing excludes browser
capture/end-of-speech/playback and is not an end-to-end latency percentile.

The finding flow uses `data/runs/companion-retrieval-fixture/scenes.mp4`: a 24-second,
twelve-scene slideshow from public cats/remotes, coffee, camera and parrot images,
with mirrored, cropped and covered variants. Source URLs/hashes are in its
`dataset.json` and earlier R8. Two imports simulate older/recent recording dates.
The test checks ambiguity, spatial correction, dated history, conversational
rejection, user confirmation, object switching and stopping. A fixture oracle
rejects crops of the wrong remote and confirms frames containing the requested
item. This is simulated user review, not autonomous similar-object recognition.

## Failures investigated and changes retained

The first cloud planner achieved 19/21 and 7/10 feedback. It received the previous
query but lacked the previous tool/window, and could lose prior exclusions on a
time-only follow-up. The retained prompt/context changes expose the previous tool,
preserve attributes on rejection, distinguish identity rejection from older-time
requests, and clarify singular references to multiple objects. No phrase-based
scenario dispatch or extra review model was introduced. Final prompt version is 41.

GPT-5.4 Mini vision twice reached only 6/7 guided-flow checks: the user-confirmation
step was not reached because a decoded mirrored image was judged ambiguous even
with a right-side qualifier. One earlier run also dropped that qualifier after
rejection. Small comparisons with full GPT-5.4 and Gemini 3.8 Flash showed better
spatial disambiguation on those frames. Full GPT-5.4 was retained for vision and
passed the complete flow; the planner stays Mini. The comparisons are tiny
purposeful diagnostics, not evidence of broad model superiority. Full GPT-5.4 still
accepts a crop of the wrong physical item as a visual candidate; user review remains
necessary. See `cloud-vision-comparison.json`, `cloud-video-frame-check.json` and
`cloud-video-vision-comparison.json`.

The first voice browser invocation used `question.wav`, which says only “Where are
my glasses?” and therefore cannot satisfy the wake-name interruption assertion.
Local ASR confirmed the missing wake name. Rerunning with the existing synthetic
`variant-1.wav` (“Hey Nyx …”) passed. No product workaround was added.

One planner harness invocation failed before inference because removed local-only
arguments were still referenced in report metadata; that setup error was repaired.
The initial cloud suite and early MVP runs remain as failed evidence, not replaced
by final successes.

The final installed-environment suite passed **324 tests** in 7.13 s. Ruff lint/format,
JavaScript syntax and offline source/wheel builds passed. The new tests cover cloud
wire contracts, response/credit errors without secret leaks or automatic retries,
model selection, invalid vectors, voice formats/cache and atomic rebuild rollback.

## Resource and product limits

At the final live-test check, key usage was **$0.33120771**, leaving **$1.66879229**
of the $2 cap (`cloud-spend.json`). This is aggregate experimental spend, not a
per-user/month estimate. Continuous indexing and repeated vision checks can
accumulate costs; cheap activity filtering remains important. No new model weights
were downloaded. Retired local Qwen/SigLIP weight cleanup is recorded in
`cloud-model-cleanup.json`: **4,163,711,307 bytes** of retired weights removed;
Whisper/detector caches are retained.

Original recordings stay local and the 1 GiB stop-without-delete budget remains.
The tested reindex used a copy of the synthetic prior workspace; private old
libraries were not silently uploaded or rewritten. `nyx reindex` is explicit and
atomic; network/invalid-vector failures roll back both vectors and fingerprint.

Cloud outages/credit errors stop agent execution with an actionable failure instead
of treating them as bad model decisions and retrying. Cancelled browser/voice turns
do not play late results, but a sent provider request may still complete and bill.

Household accuracy, small/occluded objects, intended-user evaluation, real acoustic
echo, standalone hardware and reliable timely departure detection remain open.
No merge/push or CI/review readiness is asserted by these local checks.

## Speech-linked finding and surrounding replay — 2026-10-28

Historical matches now replay up to ten seconds before and after the sighting,
across available segments in the same reliably timed capture session. Gaps are
not reconstructed. Imported or uncertain recordings use clip-local bounds.

The history tool searches captured user transcripts by object words or within
90 seconds of the sighting (30 candidates). The visual model selects at most two
existing transcript IDs. Exact quotes are attributed separately from visual
findings; intended placement is not confirmed placement. This bounded feature
is not general long-term semantic memory. Listen now (30 seconds) bypasses missed
wake activation; ignored wake attempts now display a warning. Idle audio is not
archived, so missed statements cannot be recovered.

Verification: 334 deterministic tests and companion/voice synthetic browser checks
passed. User-authorized saved glasses footage replayed three segments totaling
20 seconds and stopped correctly in the browser. Full cloud API retrieval passed
with that footage and a synthetic location statement in an isolated database.
The actual saved transcripts had no placement statement and yielded no false
citation. No real camera/microphone opened. Private artifacts remain ignored in
`data/runs/glasses-context-evaluation/`. Wake accuracy remains an open limitation;
these results do not establish perfect household accuracy or merge readiness.

## Bounded latency improvements — 2026-10-29

Measured previous real-user flow: question receipt to speech playback was about
55 seconds; history tool execution occupied roughly 46 seconds. Old diagnostics
cannot split that interval into individual provider calls or queue delays.

Ingestion now runs in a separate single worker from interactive jobs, allowing
one ingestion request and one interactive request to overlap. Model initialization
is synchronized; SQLite writes remain short transactions. No extra speculative
vision calls, new model downloads or broader worker pool. Capture embeddings use
batches of eight selected images instead of two. Text embeddings use a 64-entry
per-encoder in-memory LRU, removing repeated calls for identical queries while
returning independent arrays. The model/embedding identity is unchanged.

Text answers display before TTS finishes. Jobs expose initial queue and accumulated
work time, history results split retrieval/decode/verification/context time, and
server logs record cloud endpoint/model/outcome/duration without payloads or keys.

Deterministic tests explicitly hold ingestion blocked while searches and observation
finish. A synthetic no-op scheduling probe completed in 0.03 ms while ingestion
was blocked: this proves isolation, not real cloud response latency. No new paid
model benchmark was run. A fresh real-provider test is needed to quantify the
end-to-end improvement; provider latency and sequential visual checks remain.
