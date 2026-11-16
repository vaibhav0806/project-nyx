# R29 — Complete shown-item household workflow

Date: 2026-11-16. Owner: inline. Status: development selection frozen; heldout pending.
Decision: improve the real show → save → later recall workflow, preserving source/identity limits.

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
