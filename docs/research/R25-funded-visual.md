# R25 — Funded visual verification follow-up

Date2026-11-15. Status: development comparison/audit complete; selection/heldout pending.
Owner: inline. Decision: select a safer visual route without worsening other model responsibilities.

The user raised the cumulative OpenRouter ceiling to$5 TOTAL; key metadata verified limit5 and
usage1.970609815 at the new pass start. Per-run guards/settlement headroom remain. No new account,
purchase, private upload or hardware capture. Historical R22 runs retain their original limits.

## Same frozen category/count conditions

R22's40 licensed public photos/80 cases and source-separated48dev/32hold conditions are unchanged.
Actual CloudVerifier uses prompt7 and768px image transport. The completed Flash development run
is a preserved47-case prefix stopped at its$0.25 allowance plus an explicit one-case continuation,
with identical manifest/query/source/model identity checks. Original artifact remains failed;
the completed artifact links its hash and reuses all47 original outputs, not a silent rerun.
Continuation cost is separate. An input/model/label mismatch is rejected by regression tests.

Development: Lite41/48 correct proxy outcomes,6 proxy-unsafe positives; Flash46/48 and2 unsafe.
Median per-image elapsed2145.5ms Lite versus3280.5ms Flash on these runs. No category/count query
regressed in the paired proxy score. These are not spatial/instance/household accuracy labels.

Manual audit checked the newly detected remote in image232088 against the original annotation
bbox[446.6,270.31,28.78,10.88] and enlarged source detail: the small remote is indeed on the window
sill near the orange frame. The larger dark item on the sofa must not be assumed the target.
This confirms that particular location; it does not score all free-form location wording.

## Isolated confirmation on preserved positives

Rather than rerunning the primary and confounding its variation, apply the existing optional
category/location confirmation only to the17 cached Flash-positive judgments. All other outputs
stay untouched. This completed48/48 with46 correct proxy outcomes and1 unsafe: one unsafe
remote-like object was rejected, and one proxy-positive was also withheld.

The withheld proxy-positive (image76416) is a device depicted in a bus advertisement; the second
model identifies it as an iPod rather than a physical mobile phone. That proxy loss may be the
right product behavior. Class annotations do not distinguish every depiction or fine category;
never turn this46/48 into final physical-belonging accuracy. New depiction-condition diagnostics
and heldout verification will precede selection. A global vision-model swap could also slow
departure checks, so explicit object verification must be evaluated as its own responsibility.

Artifacts: data/runs/visual-funded-flash-development (47 complete), *-development-complete,
visual-funded-confirmation-development. Initial Flash reported responsecost$0.2341335; its
last-case continuation and confirmation costs live in their own artifacts. After confirmation,
observed key usage2.236859815/5; settlement may lag. No parallel paid benchmark ran in this phase.

## Physical-scene development diagnostic

Freeze24 public/synthetic cases from eight source-separated COCO photos (12 development,
12 holdout). Each source has its original positive/ambiguity control, a synthetic monitor
showing the full photograph, and a synthetic printed photograph on a wall. The outer scenes
contain no target item, so a claim of physical presence is wrong by construction. No text says
"not real". Sources, derivatives, SHA256, split and conditions are recorded in the ignored
physical-scenes-v1 manifest. Original photograph times are unknown; these are synthetic
boundary tests, not natural household footage or independent new photos.

Measured development: prompt7/old positive gate7/12, five physical-presence false findings;
prompt9/context gate2 reached9/12, three false findings. All four original controls retained
correct proxy behavior. An independent GPT6Luna checker reached9/12 with one depiction false
finding but wrongly withheld two original positive controls: reject that recall tradeoff.
Structured whole-scene gate3 describes the outermost scene before classifying physical/depicted/
unclear context and checking category, attributes and proposed location. It reached11/12, all
four original controls preserved, one printed-remote depiction still falsely accepted. Do not
keep tuning against this tiny diagnostic or claim the remaining failure is solved.

Prompt9/gate3 use general scene reasoning, no fixture IDs, class exceptions, coordinate rules
or expected-answer imports. The gate only withholds a proposed positive; it never replaces its
location. Unsupported, malformed, ambiguous or unclear-context output cannot supply a location;
provider failure propagates without silently reusing an unconfirmed positive. Requested explicit
depictions must retain represented context. Reference-image candidate checks use the same gate
when enabled. Object-only model selection is separate from general/departure vision, and defaults
are unchanged until the broader development/heldout decision. Tests cover role separation,
strict scene context, retained locations and failure handling.

Artifacts: physical-scenes-baseline-development, physical-scenes-selected-development,
physical-scenes-luna-confirmation-development and physical-scenes-context-development under
data/runs. Last observed usage before the new full prompt9 comparison:2.509979915/5. These
successive development trials are not heldout evidence.

## Freeze before heldout

Full prompt9/Flash development completed45/48 proxy outcomes, two proxy-unsafe findings,
with an explicit47+1 continuation under per-run guards. The one lower score than prompt7/Flash
is the correctly rejected advertisement depiction; do not relabel the frozen proxy. Cached
gate3 confirmation reached44/48, one unsafe: it rejected a champagne glass proposed as a cup,
but also withheld two proxy positives (a cordless/mobile-phone category ambiguity and a glass
annotated as cup). It still accepted a measuring-pitcher/cup confusion. These reveal category
boundary limitations, not proof of exact household semantics.

Decision frozen before opening detailed heldout outputs: select prompt9/Flash as the object-only
runtime candidate, leaving general/departure Lite and planner/embeddings unchanged. Keep gate3
opt-in: the broader paired development does not justify its extra latency/abstentions as a new
default. The physical diagnostic's11/12 is insufficient to override this mixed broader result.
Heldout will validate or reject the frozen default candidate; no further prompt calibration on
these data. Evaluate the optional gate diagnostically with preserved first-pass outputs and
original physical controls, without choosing a new default from heldout gains.

## Heldout category decision: reject the default change

Frozen prompt9/Flash completed32/32:27 proxy-correct, four proxy-unsafe positives, versus earlier
Lite/prompt7's27/32 and three unsafe. The cached gate3 diagnostic also reached27/32 with four
unsafe; it changed no final visibility in this split. Thus neither route establishes a heldout
win. Reject the proposed default migration, despite the stronger development score. Do not tune
against the heldout failures. Existing Lite/prompt7 remains the default, with exact original
prompt bytes preserved. New scene instructions requireNYX_VISUAL_SCENE_POLICY=1; stronger object
inference requiresNYX_OBJECT_VISION_MODEL=google/gemini-3.5-flash. Confirmation remains explicitly
opt-in viaNYX_VISUAL_CONFIRMATION=1. These switches enable reproducible alternatives without
quietly changing departure/general vision or the stable baseline.

The default-policy regression was observed RED (prompt9 unexpectedly active), then GREEN after
isolating scene policy.74 focused cloud/verification/answer tests passed. This is evidence-based
rejection, not completion of household visual reliability. Heldout misses include a phone
classified as a spray container and unresolved multiple-item choices. Category/count annotation
limits remain; no runtime fixture exceptions or relabeling were added.

## Bounded next candidate

After rejecting Flash/default gate, evaluate one additional primary model rather than modifying
prompts against the opened heldout errors. The already-configured planner modelGPT6Luna accepts
image input and structured output according to the official
[OpenRouter model catalog](https://openrouter.ai/openai/gpt-6-luna), checked2026-11-15. Its earlier
independent-checker trial was rejected; primary inference is a distinct, unmeasured role.
Compare prompt9/Luna on the frozen48 development cases only, no gate. If development justifies
selection, use newly frozen source-disjoint public images and a fresh Lite baseline for heldout;
the opened32-case heldout cannot serve as fresh selection evidence. Budget guards remain$5 total,
no new account. This is a bounded model comparison, no further fixture-driven prompt tuning.

The frozen physical-scene heldout completed12/12, versus9/12 on its preserved ungated primary
judgments. All four original controls remained proxy-correct and eight synthetic screen/poster
negatives were withheld or absent. This supports the optional gate for this constructed boundary,
not a global default or natural household accuracy. It does not erase the one development
poster false finding or mixed category results. Observed key usage after this diagnostic:
3.073211915/5, settlement may lag. Baseline prompt7 and opt-in prompt9 bytes were checked against
their committed evaluation versions; introducing the config switch did not alter either prompt.
