# R35 — Early saved-memory context and concise spoken recall

Date:2026-11-18. Owner:Codex inline. Status: implemented, verified; user trial pending.

## Change and evidence contract

Each completed spoken input starts a read-only memory prefetch before the image-context wait.
It reuses PersonalMemory recall, at most five records, without a relevance-selection LLM call.
When the compatible corpus fits, no query embedding is needed. Larger pools keep existing
semantic ranking. A single independent read worker avoids waiting behind memory writes;
one in-flight lookup bounds provider work. Foreground prefetch waiting has a250ms budget shared
with image preparation. Slow/failed/busy lookup is marked explicitly; further native recall stays
available. Local source revalidation is separate from that wait budget; large-corpus performance
is not established by the small-corpus timing below.

Generation receives compact saved records (kind, content, clock, IDs and sources), with no raw
quotes/photos/vectors. Corrected/retracted/deleted records and historical cutoffs are rechecked
before every continuation. Supplied-source dependencies remain attached conservatively, even
when an optional record might not be used. Context is labelled optional saved user memory;
current-input saving has a distinct pending/completed label. New memory saving stays ordered in
the background. Retrieval reads a photo-presence flag instead of loading photo BLOBs; inheritance
still loads the actual photo only when writing a derived memory. No source bytes are changed.

The one shared agent policy is93 words/version10: short direct replies, attribution once, useful
memory leads first, further tools when needed. Removed the humor cue after an experimental reply
joked about forgetting. Main spoken/typed Luna6 uses **medium** reasoning after the comparison
below; memory interpretation keeps its existing low setting, and Flash-Lite/Gemini embeddings
are unchanged. No keyword/location routing, new AI judge, frontend change or model migration.

## Deterministic verification

**498 tests passed in31.63s**; **18 actual-JavaScript transport checks** pass. Lint/format and JS
syntax pass. Coverage includes first-generation old memory while the writer is deliberately
blocked, original dialogue excluded from recent chat, source withdrawal, correction/as-of
revalidation, lookup deadline, bounded in-flight reads, lookup outage, further native recall and
actual typed/spoken reasoning-setting wiring. Existing photo inheritance/deletion/restart tests
also pass. The initial new prefetch test failed against the missing old interface before repair.

## User-trial replay method

User explicitly requested repeating their recent real missing-phone question. Snapshot the
isolated trial DB, exclude memories created at/after that question, and use the actual prefetch
implementation to supply its three prior memories. Preparation took0.94ms in the first private
snapshot, with zero embedding/selection calls. Original dialogue/previous assistant answer are
not supplied as chat. The answer's location comes from the saved plan, not an expected-answer
fixture. Two time-aligned images are reconstructed from preserved clips; clocks/hashes stay intact.

Actual LiveKit/OpenAI streaming and Sarvam TTS are used. Native further lookup, when selected,
executes real existing memory/history/vision code against the copied index/media, guarded by the
same provider budget. History excludes frames after the recorded question time. No full video or
idle audio is uploaded; no hardware or real speaker playback. Private artifacts stay ignored.

Initial acknowledgement-only probes stopped on tool calls and did not establish final-answer
quality. The full replay then exposed unnecessary visual searches, verbosity and one unverified
visual suggestion. Those outputs are retained; they are not claimed as successful fast recall.
Changing tool descriptions alone did not eliminate the searches. No runtime hard router was added.

## Measured model results and limits

With low reasoning, the completed three-repeat runs continued visual checking, with first useful
PCM about7.4–14.4s and extra qualifications. Medium effort on the same model/context gave three
direct concise memory replies at3.60–4.21s. A second, exact-final-policy confirmation gave two direct
replies at4.16s/5.00s, plus one extra visual-check turn at10.61s. Thus **5/6 medium recall runs
answered directly from saved memory**, not a guarantee that all recall avoids tool calls.

The direct replies attribute the planned location and suggest checking it, without repeating a
separate sighting disclaimer. Both repeated routing controls selected visual lookup for explicit
recording verification and further memory lookup for an unrelated object absent from early
context:4/4 routing decisions. These controls stop at routing; no successful later finding is
claimed. The final policy also passed one greeting with unrelated memories (2.13s first PCM,
no memory recital/tool) and shown-image/unclear-image controls (5.34s/4.73s, appropriate recognition
or clarification, no scheduling disclaimer). These are single-scene diagnostics, not broad accuracy.

Timing starts at the first model request. Tool paths include subsequent guarded requests; initial
budget checks, STT, endpointing and browser/device playback are excluded. More reasoning can add
latency to a simple image acknowledgement; fewer unnecessary tools helped these memory examples.
The remaining visual-choice outlier and variable visual verification remain open. Do not claim
universal four-second recall, zero added latency, or complete household/acoustic acceptance.

## Reproduce and handoff

```sh
uv run --env-file .env --no-sync python -m experiments.companion.multimodal_ack_replay \
  --evidence data/runs/early-memory-recall-evidence-v2/evidence.json \
  --output data/runs/early-memory-recall-medium-final \
  --recipe experiments/companion/early_memory_cases.json --max-spend 0.10 \
  --reasoning-effort medium
```

Use a new output directory on rerun. Private outputs include rejected trials, exact streamed
replies/tool choices, PCM counts, hashes and budget snapshots. `replay_tools.py` executes actual
native actions against the copied sources; criteria are not passed to the model.

Across this pass, raw observer cost totals$0.09137575, conservatively overstated by duplicated SSE
usage observations; not an exact invoice. Final key metadata$6.72334125/$8, remaining$1.27665875.
TTS invoice cost was unavailable. Developer inference stops here.

A fresh manual-memory copy, `data/early-memory-check-2026-11-18`, preserves all four current
memories/source rows and adds32 neutral markers so every earlier dialogue/recall answer is outside
recent context. No original media copied/deleted, no private model query run automatically there.
This is the next isolated manual check, separate from the original8001 household directory.
