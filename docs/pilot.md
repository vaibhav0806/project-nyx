# Ten-day pilot

Approved direction: 2026-11-03. The user selected all three reliability workstreams
and a **last ten days** searchable-history target for the pilot.

## Experience and boundaries

One person in one camera-covered room can ask about current belongings, dated sightings
and object-location statements, correct a match, change a reported placement, interrupt,
and resume after restart. English and Hindi/Hinglish remain supported. Answers distinguish
observed sightings, reported placements and intentions, with explicit gaps and uncertainty.

Ten days means the trailing **240 hours of available evidence**. This is a searchable-history
target, not permission to expire/delete after ten days. Older saved sources remain available
through explicit all-history search. Unknown capture times cannot establish a dated sighting.
No continuous room-audio archive is introduced.

## Integrated design

1. **Trust each turn:** own evidence and source dependencies by stable turn/tool IDs. Preserve
   the visual candidate across other tools in the same turn. Expose rejected-frame and strict
   earlier-than constraints to speech. Reject late old-turn results. Keep LiveKit speech
   management and shared typed action policies.
2. **Remember the moment:** evaluate event retention, retrieval and final answers separately.
   Compare periodic coverage plus activity selection, cross-segment episodes, reference/crop
   retrieval and denser source inspection. Add attributed claim corrections without rewriting
   observed history. Admit changes against a held-out ten-day replay set.
3. **Work every day:** separate capture, saved-media, indexing and voice health. Test reconnect,
   restart, backlog, full storage and intervention. Evaluate native capture and local inference
   against the same tasks before selecting hardware. The cloud prototype remains the implemented
   runtime until a measured replacement is selected.

Keep one Python application and SQLite; refactor ownership incrementally. Retain browser capture
and authenticated local transport while building shared turn behavior. No provider registry,
distributed system or replacement database is needed for this slice.

## Capacity decision

The development cap remains **1 GiB, stop without deletion**. At nominal 1 Mbps, ten continuous
days require about **108 GB (100.6 GiB)** of video before overhead. Actual browser output varies;
frames, databases, statement images and free-disk headroom are additional. This is arithmetic,
not a reservation or measured pilot capacity.

A continuous ten-day pilot needs an explicit capacity choice or an approved different source
retention policy. Preserve existing recordings and the cap until that choice. Ten-day lookup
alone does not establish ten-day captured coverage. No purchases, destructive recompression
or automatic expiry are authorized by the horizon selection.

## Evaluation and delivery

Replay permitted/synthetic evidence over ten days: a day-nine positive, an outside-window
source, lookalikes, ambiguity, correction, rejection, earlier-than lookup, deletion and restart.
Exercise actual spoken-tool wiring with fake providers/media. Paid inference and intended-user
validation remain separate. Measure event retention, candidate recall, useful correct answers,
abstention, source attribution, correction success, p50/p95 first useful spoken audio,
per-success cost and intervention frequency. Count failed/incomplete runs.

The [foundation plan](superpowers/plans/2026-11-03-pilot-foundation.md) covers turn-evidence
bugs, spoken search controls and the ten-day query contract. Later memory, capture/recovery
and local-device work remains authorized direction; [milestones](milestones.md) records actual
delivery. Capacity selection gates continuous ten-day recording. [R12](research/R12-product-reliability.md)
contains the underlying assessment; its proposed thresholds are not measured reliability.

Foundation implementation is complete locally with 384 deterministic tests passing: source
dependencies and review survive multiple spoken tools, late old-turn results are rejected,
spoken search receives candidate metadata and accepts exclusions/earlier-than bounds, and
240-hour queries retrieve dated day-nine evidence. This establishes neither ten-day continuous
coverage nor household recall quality. No storage cap or inference provider was changed.
