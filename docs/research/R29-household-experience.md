# R29 — Complete shown-item household workflow

Date: 2026-11-16. Owner: inline. Status: comparisons complete; separated workflow remains opt-in after an unsafe heldout save.
Decision: default retains the merged joint claim/identity decision plus the additional conservative
ambiguity check. The separated reference6 pipeline and identity-save handoff are **opt-in only**
(`NYX_HOUSEHOLD_REFERENCE_POLICY=separated`); default is `joint`. The final two-phone unsafe save
prevented default promotion. Planning, answer attribution and empty-recall fixes remain active.
This is an engineering/validation pass with an open household acceptance gate, not product completion.

## Scope and inputs

PR2 merged at bdb7ad0. Work continues only on work/memory-reliability from that merge, with no
main/UI changes. Existing private recordings remain offline; all model evaluation uses public
or synthetic evidence under the cumulative $5 cap. No microphone/camera, new provider or account.

Eight source-separated workflows use known public COCO crops in short edited videos: object
shown twice, absent in the last frame. Three actual FFmpeg-decoded frames feed the validated
utterance-window API. Each turn uses a fresh TestClient/app, and32 synthetic filler turns evict
recent chat before later recall. Planner, resolver, embeddings, SQLite report/correction storage
and citation verification execute through /api/agent without forced initial actions. Four
workflow development cases cover shown-item recall, a normal move, correction and ambiguous cups;
four heldout cases cover Hindi, intention, movement and ambiguity on disjoint photo sources.

These are edited public-image workflows, not natural household-video accuracy, acoustic testing
or physical proof of a placement. Original photo clocks are unknown; frame timestamps are
explicit simulated replay clocks. Ground truth identifies the report and demonstrated crop,
not unique physical identity outside the source. Cases/scorer/scripts are committed under
experiments/companion/household_workflows.*; raw videos/replies remain ignored under data/.

## Early diagnostic corrections

The first development wording “I'm keeping this…” is ambiguous between intention and completed
placement. Preserve its original v1 result; don't count its kind label as a model defect. V2 uses
“I put this…” for that development case and reruns the immutable merged application against the
same corrected inputs. The baseline export has identical dependency definitions and records
planner47. Heldout content/outcomes were not used for these changes.

The initial composite scorer checked only the last expected report, so a normal-move case could
pass despite losing its first save. A failing scorer regression exposed that error. Scorer2
requires every positive save, its claim kind and visual/prior-report provenance, plus the exact
correction edge when requested and exact cited recall IDs. Derived rescored-v2.json reports link
original artifacts by hash; no original outputs were replaced or rerun to improve scores.

## Traced failures and development changes

1. Valid utterance images existed for tools but the planner was not told they were available
   without a separate current snapshot. RED API-state regressions preceded the new truthful
   turn_visual_context/frame_count metadata, explicitly distinct from current_view.
2. The joint vision/report resolver sometimes identified an object but returned kind=none and
   no destination for a clear placement utterance. A prompt-only clarification did not establish
   a gain and was rejected. Keep its run as counterevidence.
3. Separate claim classification from visual identity. A text-only schema extracts reported
   placement versus intention and an exact destination substring. Questions, negations and
   hypothetical/unclear claims refuse before image inference. Only after a valid claim does
   identity resolution run; ambiguous identity still refuses. This adds an inference request,
   not a relaxed identity/placement validator. Transcript-derived claim_source is recorded.
4. A successful intermediate reference plus a saved-statement completion previously leaked
   internal “Use this description…” handoff text into the answer. A failing agent regression
   preceded selecting the actual report answer for that combination. Reference resolution is
   not a sighting/location; unresolved references must not be hidden by that selection.

An isolated real text-only probe classified8/8 English/Hindi claims, plans and negative controls
correctly; this is a small component diagnostic, not independent household acceptance.

## Freeze before heldout

Strict scorer2 on matched V2 development: merged baseline1/4; window-metadata candidate2/4;
prompt-only candidate1/4 (rejected); separated claim/identity candidate4/4, including every save,
normal move, correction edge, recall ID/citation and ambiguous-object refusal. Development runs
are not independent unseen accuracy estimates. Model variation between repetitions is visible.
Freeze independent-text-v1 / reference prompt4, planner48 and the truthful reference-completion
repair before opening heldout results. Existing underlying model/embedding choices stay unchanged.

Artifacts: household-baseline-development (v1 diagnostic), household-baseline-v2-development,
household-selected-v2-development, household-selected-v3-development (rejected prompt trial),
household-claim-separation-probe and household-separated-development, all under data/runs.
The original run scores precede the stricter scorer; use their hashed rescored sidecars for
composite comparisons. Final answers require author audit separate from source-ID scoring.

## First heldout and unsafe repetition

Frozen reference4 scored3/4 versus merged baseline1/4 on the same four heldout workflows.
Hindi placement, future intention and normal movement passed. The ambiguous pair refused its
save, but lookup chose one object and returned an empty report search with status=complete.
A deterministic regression changed empty statement recall to uncertain; absence of a report
is not evidence of an object's absence.

A diagnostic repetition of that known ambiguous case then SAVED a report against one arbitrarily
selected cup (0/1). This is a stochastic identity failure and blocks an unqualified success claim.
The original heldout results remain unchanged; repetitions are diagnostic, not fresh heldout data.

## Independent reference check and second selection freeze

A candidate independent visual check sees the utterance and chronological frames without the
primary model's proposed description. It must explicitly agree that one referent is singled out;
equally plausible targets without distinguishing words/holding/pointing cues require clarification.
It uses the existing Lite vision route, while the primary reference resolver remains Flash.
Malformed responses or provider failures propagate before embedding/persistence; the original
transcript survives. Explicitly named text-only reports do not claim visual identity and skip it.
This adds up to one vision call to visual saves/lookups, not a new model/provider or a category
exception list. Fingerprints record reference5 / independent-unique-v1.

On original DEV windows, the independent component probe accepted all three clear controls and
refused the ambiguous pair (4/4). A newly frozen four-case source-separated confirmation corpus
then passed its two development cases (one clear object, one ambiguous pair). Core workflow
regression scored2/4: shown-item recall and ambiguity passed; the primary resolver refused the
first phone save before the new check; the added check withheld bottle recall because another
partially visible bottle was in the background. Both bottle saves and its correction edge passed.
The conservative check therefore has an observed false clarification cost. Do not report4/4 core
workflow accuracy or claim every dimension improved. Keep the safe refusal rather than arbitrary
object assignment, and measure clear-object retention separately from ambiguity rejection.

Freeze the exact independent-unique-v1 prompt and existing primary model before opening the two
fresh confirmation heldout outcomes. No additional prompt/model selection will use their results.
The new source IDs are disjoint from original household source groups; these are fresh household
conditions over previously available public photos, not photographs unseen in all prior tasks.
Artifacts: household-empty-state-regression, household-ambiguity-check-probe,
household-confirmed-development and household-confirmed-core-development under data/runs.

## Second selection outcomes and remaining issue

Fresh confirmation heldout scored1/2. The ambiguous pair was refused without a saved link; the
clear phone failed its save because the PRIMARY resolver returned unresolved before the new
check ran. Lookup later identified the phone, but truthfully returned uncertain with no report.
This is a missed memory, not a successful workflow. No checker prompt was adjusted on these cases.
The fresh ambiguity case did not reach the checker; it cannot demonstrate incremental checker
benefit. Actual conditional vetoes are traced separately in the original regression artifacts.

The natural Charades LZ07A clip diagnostic passed1/1 both before and after the added check.
Frames at22/24 seconds show a brown handbag; it is absent at28 seconds. The associated cabinet
statement is synthetic, not a claim that the video proves that destination. Each API turn
restarts and recall follows32 unrelated turns. The original clip is research-only, kept ignored;
it is not cleared as a demo or redistribution asset. One clip is not a natural-video benchmark.

Native spoken-boundary replay completed2/2 cases using the actual tool schemas, SDK binding and
dispatch, actual API retrieval over copied public/synthetic report databases, and native model
continuation. The plan reply explicitly stayed a plan; the corrected report named the new
location, then refused to confirm current presence without visual evidence. Dispatch transport
uses a mocked acknowledgement before the actual API evidence is supplied to the real model.
No STT/TTS acoustics, microphone, room noise or human listening was tested.

Offline existing-library replay strictly decoded all92 videos; all source hashes stayed unchanged.
It exercised256 stored-vector queries and source/context invalidation in a copied index. This is
preservation/compatibility evidence, not household semantic or identity labels. No private media
or stored vectors were uploaded. Synthetic Chrome boundaries also passed without UI changes.

## Identity-only contract hypothesis

Tracing the clear missed saves showed that the nominally independent identity stage still
requests claim kind and destination in its schema/prompt. Those outputs are discarded in favor
of the preceding text stage, yet still burden the identity task. A failing contract regression
requires an identity-only schema. Candidate selection will use existing development workflows
and a new source-separated six-case corpus; two development and four heldout conditions are
frozen before inference. Preserve all prior failures and report later repeats as regressions.

## Third selection freeze: identity-only schema

Reference6 asks only object_description/source/frame_index/ambiguity at the identity stage;
claim kind/destination are supplied exclusively by the independent text stage (or none/empty
for lookup). The downstream response shape, stored source metadata and validators stay intact.
A failing identity-only contract test now passes; a lookup cannot leak a placement claim from
an identity response. No checker prompt, model, embedding, threshold or correction policy changed.

Core development regression passed4/4. The new development pair scored1/2: ambiguity was refused;
the single phone crop saved under a frame-like description but recall was withheld by the checker,
which reported another plausible object. Preserve this failure, including inconsistent category
names. A single annotated crop can include background objects; its expected-target protocol is
not a human proof of an unambiguous physical referent. Do not retroactively change the label or
count that case as a success. These results do not establish general category recognition gains.

Freeze reference6 / independent-text-v1 / independent-unique-v1 before running the four new
identity heldout conditions. Selection favors a coherent separated contract and conservative
association; mixed clear-control results and extra inference remain explicit limitations.
The earlier reference5 known-holdout regression passed4/4, including a recorded checker veto
of a primary-model arbitrary selection. That is diagnostic reproduction, not fresh accuracy.

## Third heldout: improvement with an unresolved unsafe case

Frozen identity-only selection scored3/4 on new sources: Hindi completed placement and future
intention controls passed, and the ambiguous bottle pair was refused. The two-phone composite
FAILED: both primary and independent model described it as one held phone or multiple views of
one phone; a report was saved and later cited rather than asking which item. This is a measured
unsafe association under the predeclared two-source protocol. It remains a release/household
acceptance issue. No prompt was tuned on these outputs and the failed case stays in the denominator.
An independent check reduces some arbitrary assignments; it does not establish independent
errors or guarantee correct physical identity. Do not call the branch universally household-ready
or claim the added checker eliminates false associations. Main remains untouched.

## Natural cross-view and spoken-save validation

The final reference6 natural diagnostic passed1/1 with distinct source offsets: save22/23/28s,
recall24/25s. No exact save frame was reused for recall. The observed brown bag/purse report was
retrieved with its exact source after restart/context eviction. This is the same short scene,
not cross-day identity, person recognition or physical confirmation of the synthetic destination.

The first native save/recall harness trial saved the clear item, then exceeded its three-round
continuation bound. Investigation found a harness mismatch: its single frozen initial system
clock preceded the newly saved report, and the model supplied that as an as_of cutoff. Actual
Companion.llm_node refreshes local time on every generation. Keep the failed artifact and repair
the harness to mirror that behavior; do not count a stale-clock experiment as a product regression
or silently expand continuation bounds. The refreshed-clock run is separate. Original utterances,
models, tools, images and production instructions remain unchanged.

## Same-utterance identity handoff repair

The refreshed-clock native trial completed execution but its clear-item workflow FAILED: initial
identification succeeded, remember_statement re-ran recognition and clarified, and no memory was
saved. Ambiguous-object save/recall correctly clarified. Completion status alone is not a pass.
A user-facing intermediate update confused those two; it was explicitly corrected after audit.

A failing real authenticated API regression exposed the duplicate identity work. Reuse a checked
server-owned identity only for the identical active turn, transcript, context timestamp, frame
capture timestamps, dimensions/mode and pixel hashes. A new turn, changed pixels/clocks or later
identity refusal invalidates it; the bounded eight-entry cache is not durable general memory.
The text claim still has to pass separately, destination/object guards remain, and an identity
without its independent unique-referent check is refused. Stored reference metadata records
same-owned-window-v1. No client-supplied identity field is trusted or exposed.

The native harness also needed a persistent authenticated API session and real owned turn per
utterance to model this boundary. A regression caught accidental creation of a separate unowned
API client. Preserve failed protocol trials (409 and a missing experiment import) without counting
them as model-quality comparisons. The final harness supplies the actual native-selected action,
fixed per-turn frames/clocks, signed session header and fresh local-time prompt per generation.
No forced first action, extra continuation rounds or fixture-specific application behavior.

Final owned-turn native diagnostic passed both authored outcomes (2/2): clear item identified,
saved with same-owned-window provenance, then recalled with attributed wording; ambiguous pair
asked which item at save and lookup and created zero links. Actual SQLite inspection found exactly
one clear-case link and no ambiguous link. This is a repeated development diagnostic, not unseen
speech or acoustic acceptance. It does not fix the separate heldout two-phone misidentification.

Artifacts: household-native-save-clarify (stale clock), household-native-save-live-clock (clear
workflow miss), household-native-owned-turn-handoff / household-native-owned-turn-final (protocol
failures), household-native-owned-turn-verified (final owned-turn diagnostic). All remain ignored.

## Matched baseline audit and default decision

The immutable merged bdb7ad0 application scored1/4 on the same final identity holdout (planner47,
identical dependencies). It created no links in all four cases. Its two-phone failure was an empty
search marked complete, not an unsafe saved link. The separated candidate scored3/4 but created
one incorrect link where baseline refused. This is a safety regression despite the higher composite
score. Do not describe the comparison as strictly better or publish it as a solved household flow.

Retain separated claim/identity/handoff only behind the explicit backend policy flag. Default
joint preserves the exact merged primary schema, prompt and placement flag; a local AST/literal
comparison verified both schema and prompt equality. The independent uniqueness check can only
withhold an otherwise-valid result; it cannot override a joint refusal or fill its missing claim.
Default-policy tests verify that even an apparently valid cached identity cannot promote a refused
placement, while a negative independent check still vetoes a joint positive. Invalid policy values
fail before inference. No object/fixture exceptions, threshold tuning or new model/provider.

Final default on the four identity holdout cases scored3/4: Hindi placement and both ambiguity
conditions passed; the future-plan cup remained a missed save. Both ambiguity cases created no
links. This is a known-case regression comparison after selection, not a new unseen estimate.
Positive claim failures and nondeterminism remain; the default does not promise complete household
recall. Underlying primary decisions are unchanged, and extra checking adds cost/clarifications.

## Final default regression, verification and accounting

Core development with the final default scored1/4, equal to the strict matched baseline1/4:
ambiguity passed, while the three positive workflows missed at least one save or recall. Do not
substitute the opt-in pipeline's4/4 for this default result. The default is more conservative,
not a completed show/remember household experience. The opt-in path is useful engineering work,
but its unsafe heldout association and broader naming instability prevent promotion.

Final verification:577 deterministic tests passed in24.81s; Ruff lint/format (185 files), four
application JavaScript syntax checks, changed-document local links and whitespace passed.
Synthetic Chrome speech/cancellation/playback-failure/library/candidate/reminder boundaries
passed with zero page errors. Full offline local video decode/hash and256 stored-vector checks
remain preservation evidence only. Author review found no UI, dependency, source-media or main
changes. No hosted CI/independent-review/merge-ready claim; no new PR or merge was requested.

Runtime: macOS Darwin24.6.0 arm64, Python3.12.11, FFmpeg8.1. Exact cloud model/encoder identifiers,
prompt policies, source/manifest hashes, per-stage replies and usage are in ignored results.json
artifacts; scripts/cases/tests and these anonymized findings are committed. Public COCO licensing/
source metadata follow [R22](R22-visual-depth.md); Charades download and research-only restrictions
follow [R8](R8-companion-loop.md). Edited photo crops are not true household identity labels.

Cumulative OpenRouter usage verified **$4.73185091/$5 total**, matching conservative accounting:
pre-household anchor$3.205437215 plus every household*/results.json provider_usage cost, including
failed/rejected/protocol trials. Remaining$0.26814909. No refill/account purchase or paid acoustic
route. Paid tests stopped with headroom. No private media/vectors were uploaded and no capture
hardware activated.

Reproduction uses experiments.companion.household_workflows with the committed case manifests;
--prepare verifies cached source/annotation hashes and produces ignored fixtures without model
calls. Actual /api/agent runs accept --data/--cases/--split/--output/--max-spend. For the experimental
selection set NYX_HOUSEHOLD_REFERENCE_POLICY=separated explicitly; default joint is intentionally
different. Native replay uses experiments.companion.household_spoken_replay --visual-data against
prepared public fixtures. Every paid run needs cumulative-budget headroom and a new output directory.

Next release work: source-labeled user-assisted disambiguation/confirmation for similar items,
new independent physical-object/video groups, and acoustic/real-user acceptance. Do not keep tuning
prompts against the exposed phone pair or promise that two agreeing models establish identity.
The broader household goal remains open; the default and experimental limits are deliberate.
