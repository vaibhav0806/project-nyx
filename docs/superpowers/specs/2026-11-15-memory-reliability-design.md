# Memory quality and demo reliability

Date: 2026-11-15. Status: workstreams agreed; research/preparation requested before implementation.
Precise scoring/embedding/backend configurations remain conditional on experiments. No new
runtime behavior from this design is implemented yet.

The user agreed to the reliability, labeled replay, retrieval, repository reconciliation and
demo-polish direction, and prefers trying a teammate's self-hosted HydraDB instance over buying
hosted Hydra access. The precise scoring policy and backend choice below remain proposals.

## Outcome

Produce a tested engineering candidate in a target 24–48 hour push for the November 20
prerecorded presentation. Improve the real product's ability to retain useful moments, retrieve
the right evidence and explain dated or conflicting information. Optimize for the older-adult
independence mission; the laptop/room remains a development setting.

This target is not a measured delivery estimate or evidence of unattended ten-day reliability.
Fast implementation and replay can accelerate development; elapsed-time soak coverage must be
reported separately. A native capture rewrite, local-model migration and new hardware are
follow-on work, not dependencies of this recording.

## Existing foundation

Main contains `cfe8fa4`: turn-owned source accumulation, obsolete-result rejection, persistent
same-turn candidate review, spoken exclusions/earlier-than controls and 240-hour history lookup.
Fresh November 15 verification: 384 deterministic tests passed, plus lint, format, JavaScript
syntax and local Markdown links. These tests do not establish retrieval quality.

Known gaps from [R12](../../research/R12-product-reliability.md):

- A small synthetic object visible at 3.0–5.9 seconds is absent from selected index samples.
- History nominates 64 semantic candidates, diversifies within each video and verifies at most
  12 in the semantic-latest path. Repeated adjacent clips can crowd out different events.
- Reference-image checking starts after text-based candidate nomination.
- Saved user statements lack explicit cross-turn correction/supersession semantics.
- Capture/index/voice recovery and long-running coverage are not proven as a combined system.

## Approaches

1. **Nyx-owned policy, optional self-hosted retrieval — recommended.** Retain SQLite/source files
   as the authoritative evidence store, implement and evaluate the memory rules in Nyx, and
   test the teammate's Hydra deployment as a bounded retrieval backend once capabilities are
   known. Server access does not block coverage or policy experiments. Tradeoff: any external
   derivative index needs stable IDs, deletion checks and reproducible synchronization.
2. **Hydra-first migration.** Make the server and its memory/retrieval behavior the first
   dependency, then move the application onto it. This may reuse more functionality if the
   deployment includes the full service, but currently has unknown API, feature, operational
   and evidence-preservation behavior. It is not the recommended path for this deadline.

The user has already chosen a preference for self-hosted access over purchasing hosted Hydra
access. This proposal does not reopen that choice. It distinguishes ownership of Nyx's memory
semantics from the eventual retrieval backend.

## 1. Reproducible labeled replay

Build an opt-in harness under `experiments/companion/` using the real application retrieval and
selection functions. Keep deterministic policy/storage assertions in `tests/`; model runs stay
separate. Do not create a second application implementation in the experiment.

Each manifest case identifies source digest, source-relative offsets, capture-time provenance,
explicit replay clock, object identity/description, query intent, expected evidence interval(s),
expected outcome and coverage gaps. Unknown original dates remain unknown. Assigned replay
dates live in separate fields and are never described as original capture dates.

Target roughly 100–120 queries, split by source episode/session into development and held-out
sets before tuning. Freeze case IDs and hashes. Existing development clips are regression
fixtures, not newly held-out evidence. If the available corpus is smaller, report its actual
size and limits rather than padding it with near-duplicate queries.

Include brief/small appearances, lookalikes, changed descriptions, repeated scenes, before/after
bounds, day-nine positives, outside-window/future/undated sources, explicit statement corrections,
ambiguous contradictions, deletion, restart and genuinely unanswerable questions. Query variants
from the same episode stay in one split. Give each question an evidence set so recall metrics
can represent multiple relevant sources.

Report separately:

- Event retention: did the selected samples overlap the labeled useful interval?
- Candidate recall at fixed budgets, including Recall@12 for the current verification budget.
- Verified evidence accuracy and final grounded answer success; report raw counts per intent.
- False confident answers, correct abstentions, attribution and correction success.
- p50/p95 end-to-end useful answer latency, provider failures and per-success cost, with the
  sample count and timing boundary. Cached/offline replay timing is not live provider latency.

Run deterministic/synthetic and cached-artifact comparisons first. A budget ledger must include
failed calls and earlier spending before any paid benchmark: the previous $2 test authorization
is a total limit, not a fresh allowance per experiment. Private recordings are not new cloud
benchmark inputs by default. Use permitted public/synthetic fixtures for automated verification.

## 2. Retain and nominate useful moments

Compare the existing activity selector against periodic coverage plus activity-selected samples.
Test a small number of explicit sampling intervals, starting with the existing two-second
periodic baseline. Measure event retention, indexed frame count, decode/index time and embedding
cost. A sampling floor reduces risk; it does not guarantee retention of shorter appearances.
Preserve original recordings and exact offsets.

Then compare cross-segment episode diversity and reference-image candidate nomination. Group
only where capture-session continuity and timestamps support it; adjacent import order does not
establish one real event. Keep a text candidate route when no reference image exists. Keyword
search applies to actual transcripts/available textual metadata, not directly to image vectors.
Any generated captions are derived, attributed hypotheses and their ingestion cost is measured.

Compare each addition independently at the same candidate and verification budget, encoder,
verifier, replay clock and frozen case set before evaluating combinations.

### Shared embedding representation trial

The user also approved exploring a shared embedding space, conditional on accuracy. The code
already defaults to Gemini Embedding 2 for image and text inputs; video is represented by
sampled frames. Keep this as baseline and compare reference-image nomination, explicit text
query/document roles and short native-video representations where the transport is verified.
See [R13](../../research/R13-shared-multimodal-embeddings.md) for source research and test design.

Transcripts cover the pilot's speech-content retrieval; raw-audio embeddings and non-speech sound
memory are outside this slice. A shared space preserves distinct timestamped visual observations
and attributed statements. Keep source-kind candidate budgets and source verification. Do not
collapse them into one untyped memory or infer equal confidence from equal similarity scores.

Evaluate representation changes before tuning decay, and hold the representation fixed when
comparing SQLite and Hydra. Version input roles/formatting, dimensions and sampling in embedding
fingerprints. Preserve recordings and rebuild only a separate development index or atomically
replace derived vectors. Qwen3-VL-Embedding-2B is a research alternative, not a chosen dependency.

## 3. Nyx memory policy v1

Own a transparent, versioned policy tailored to Nyx. Calling it Nyx-specific engineering does
not establish original research or a performance improvement. Select behavior using the replay
results, with a no-decay baseline always included.

### Separate memory properties

- **Novelty:** a distinct event, a duplicate observation, a reported fact update, or unresolved
  identity. Embedding distance alone cannot distinguish a paraphrase from a changed placement.
  Novelty may guide consolidation/indexing experiments; it is not proof or a search boost by default.
- **Temporal validity:** an explicit correction can supersede an earlier report for present-state
  recall while preserving both for history. An unlinked contradiction stays unresolved. An aged
  sighting remains valid evidence that the object was seen then, even when its current location
  is unknown. Missing observations do not imply a move or disappearance.
- **Freshness:** age since the relevant source observation/report, with a configurable half-life
  by memory kind. Source time and ingestion time remain separate. Useful access does not create
  a new sighting. Unknown source age is represented as unknown.
- **Retrieval priority:** relevance to this question, optionally adjusted by freshness after scope
  and validity checks. Importance, confidence and factual truth are not interchangeable scores.

### Proposed retrieval equation

For an eligible candidate:

```text
freshness = 2 ^ (−source_age / half_life)
priority  = relevance × (1 + query_recency_weight × freshness)
```

This is a proposed Nyx experiment, not Hydra's hosted formula. Relevance must be a documented,
normalized signal from candidate fusion; do not add raw cosine and keyword scores on unrelated
scales. Compare rank fusion and the current vector route before choosing its definition.

Apply source-availability, time/scope, exclusions and correction rules before ranking. A new
unrelated record cannot enter through a freshness boost. Invalid/future timestamps never become
fresh by clamping their age to zero. Unknown age gets no freshness boost in general search and
cannot satisfy a dated sighting query.

Use these distinct intent policies:

| Question | Policy |
| --- | --- |
| Current location | Prefer eligible recent matching evidence; state dated evidence and coverage uncertainty. A candidate is not proof of present location. |
| Last seen | Nominate diverse relevant moments; verify identity, then order matches by source time. Do not let an age score substitute for matching. |
| Explicit historical interval | Filter to that interval; disable a global preference for today's records. |
| What did I tell you? | Retrieve attributed user reports with correction/validity history; do not present a report as visual confirmation. |

All available evidence inside the ten-day horizon stays eligible for appropriate questions.
Low priority never authorizes deleting, expiring or silently excluding the only relevant source.
Decay initially changes experimental ranking only, not retention/storage admission.

Tune a small preregistered grid on development data: decay off; candidate half-lives of 1, 3, 7
and 30 days; recency weights of 0, 0.25 and 0.5 where the intent permits. These are experimental
values, not learned facts or approved production defaults. Freeze the selected policy before
held-out evaluation. Log policy version and component scores for failure inspection.

Replay ranking variants against saved compatible embeddings and verified labels first. Reuse
model artifacts only when the exact query, evidence, model and prompt fingerprints match; this
is not a fresh live inference measurement. Do not multiply paid verification calls across the
whole tuning grid. If a held-out failure is used to tune behavior, that case becomes development
data and a new untouched holdout is needed for the next generalization claim.

Leave retrieval-frequency reinforcement off initially. A shortlisted record or the assistant's
own repeated answer is not independent evidence of usefulness. An optional later experiment may
use bounded boosts from explicit confirmed usefulness, with recorded provenance.

### Correction storage

Keep original turns and observations immutable. Add only the minimal attributed correction links
needed for cross-turn reports, validating referenced IDs and preserving unresolved cases. The
existing `statement_revisions` repair archive is not automatically a semantic correction history.
Any additive migration must be idempotent, preserve source links and survive failed writes.
Compute age/priority at query time using the explicit clock, not a permanently stored stale score.

## 4. Hydra access and capability trial

Read-only check on November 15: `ssh -G era` found no effective host/user mapping beyond SSH
defaults; `ssh` failed because `era` did not resolve, before reaching authentication. No Tailscale
client was found in PATH or the usual application paths. This does not establish that the server
is down or which VPN/Headscale route it requires. Request the SSH command/address and any jump
host information; receive any required secret through the private secret tool, never chat.

Subsequent check: the user supplied an SSH command using an existing private key. That connection
succeeded, and read-only Docker inventory identified a running Hydra container in another
application's stack. No password search was required, and no server changes were made. A separate
Nyx database/graph namespace, or separate service/storage if namespace isolation is insufficient,
is authorized and must precede fixture writes. Isolation has not yet been created. The earlier
DNS failure concerned the bare alias, not the supplied host route.

Once access works, inspect version, running service names, declared API, authentication and health
without printing environment secrets or accessing unrelated data. Identify graph/vector/keyword/
memory capabilities and embedding compatibility rather than assuming the hosted memory API exists.
No restarts, upgrades, global settings or deletion of teammate data are part of this trial.

Use an isolated Nyx evaluation namespace for an explicitly scoped subsequent write trial with
public/synthetic fixture records. Store no private footage there. Require stable Nyx source IDs,
recording offsets/times, model fingerprints, deletion/availability checks and bounded timeouts.
Read results back and validate source IDs against Nyx's authoritative store before verification.
If needed capabilities are absent, finish the local policy/benchmark work and report the exact
missing server layer rather than implementing a speculative platform or purchasing hosted access.

Compare the current backend and Hydra on the same compatible embeddings/corpus and budgets where
possible. If encoders or ingestion differ, report a system comparison, not an isolated database
speedup. Measure network latency and unavailable/stale-index behavior. No automatic deployment
switch follows from a successful connection. Self-hosting Hydra does not remove Nyx's separate
cloud inference calls.

## 5. Recovery, UI and admission gates

Exercise interruption/late results, restart, indexing backlog/retry, provider failure, network
loss, deleted sources and storage full with synthetic inputs. Distinguish capture, saved media,
indexing and voice health in the UI; preserve pending work and actionable recovery information.
Expose the evidence timestamp, source playback, correction and uncertainty in the demo path.
Source deletion and new turns must invalidate obsolete review state.

Promotion requires all deterministic invariants passing, no new attribution/time-bound/deletion
or explicit-correction regressions, no new known confident wrong-answer failure, and a measured
held-out improvement in the targeted failure class at a stated resource budget. Report aggregate
and per-class tradeoffs; an average gain does not excuse a serious regression. If no clear gain
is established, retain the baseline and report the experiment, not an improvement claim.

Target sequence: baseline/labels and coverage first; candidate retrieval and memory-policy
ablations next; recovery, bounded server integration if justified, and demo polish next; frozen
held-out evaluation and recording rehearsal last. A full ten-day soak continues separately.

The [pilot boundaries](../../pilot.md) still apply: one Python application, source preservation,
1 GiB saved-video stop without deletion, no automatic expiry/recompression, no hardware access
in automated tests and no unapproved spending. Stage footage must be owned/permitted for that
use; existing Charades evaluation material must not appear in published demonstration footage.

## Primary references

- [Hydra query contract](https://docs.hydradb.com/essentials/v2/query)
- [Hydra published design](https://benchmarks.hydradb.com/hydradb)
- [Hydra research paper, experimental decay section](https://benchmarks.hydradb.com/reports/hydradb.pdf)
- [Public graph engine](https://github.com/hydra-db/hydradb)
- [Ego4D episodic-memory tasks](https://ego4d-data.org/docs/benchmarks/episodic-memory/)
- [ATM-Bench](https://github.com/JingbiaoMei/ATM-Bench)

## Inline design review

Reviewed against the existing attention/history/statement boundaries. Historical explicit queries
must retain old evidence; unknown/future dates must not get a freshness boost; an index failure
must not imply event absence; correction links must not rewrite observations; remote candidates
must still resolve to available local sources. Keep the external backend conditional on capability
evidence and preserve the local benchmark route. This is an inline author review, not independent
review or evidence that any proposed behavior already works.
