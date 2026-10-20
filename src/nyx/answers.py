from nyx.capture import frame_image
from nyx.memory import aware_time
from nyx.retrieval import search


def evidence_links(row):
    return {
        **row,
        "thumbnail_url": f"/api/frames/{row['id']}",
        "media_url": f"/api/videos/{row['video_id']}/media",
    }


def history_steps(
    object_query,
    store,
    encoder,
    verifier_factory,
    mode="latest",
    video_id=None,
    seen_after=None,
    seen_before=None,
    semantic_latest=False,
):
    if mode not in {"latest", "relevance"}:
        raise ValueError("Choose latest or relevance history")
    limit = 12 if mode == "latest" else 5
    candidates = search(
        object_query,
        store,
        encoder,
        limit=limit,
        video_id=video_id,
        seen_after=seen_after,
        seen_before=seen_before,
        order="relevance" if semantic_latest and mode == "latest" else mode,
        known_time_only=semantic_latest,
    )
    if semantic_latest and mode == "latest":
        candidates.sort(key=lambda row: row["observed_at"], reverse=True)
    recent_count = len(candidates)
    if mode == "latest":
        known_ids = {row["id"] for row in candidates}
        fallback = search(
            object_query,
            store,
            encoder,
            limit=5,
            video_id=video_id,
            seen_after=seen_after,
            seen_before=seen_before,
            known_time_only=True,
        )
        candidates.extend(
            sorted(
                (row for row in fallback if row["id"] not in known_ids),
                key=lambda row: row["observed_at"],
                reverse=True,
            )
        )
    checked = []
    selected = None
    verifier = None
    for candidate in candidates:
        verifier = verifier or verifier_factory()
        source = (store.root / candidate["video_path"]).resolve()
        if not source.is_relative_to(store.root):
            raise ValueError("Source must remain inside the local workspace")
        image = frame_image(source, candidate["offset_seconds"])
        judgment = verifier.inspect(image, object_query)
        item = {**evidence_links(candidate), "judgment": judgment, "model_checked": True}
        checked.append(item)
        yield {"checked": len(checked), "candidate_limit": limit}
        if judgment.get("ambiguous"):
            break
        if judgment["visibility"] == "visible":
            selected = item
            break
    answer = f"I couldn't confirm {object_query} in the sampled frames checked. This does not prove it wasn't there."
    ambiguous = bool(checked and checked[-1]["judgment"].get("ambiguous"))
    if ambiguous:
        answer = "Which one do you mean? Please describe its color, position, or another distinguishing detail."
    if selected:
        when = (
            selected["observed_at"]
            or f"clip offset {selected['offset_seconds']:.2f}s (capture clock time unknown)"
        )
        location = selected["judgment"]["location"] or "unclear"
        qualifier = (
            "Latest model-confirmed sighting within the checked frames"
            if mode == "latest"
            else "Model-confirmed candidate"
        )
        answer = f"{qualifier}: {object_query}, at {when}. Reported location: {location.strip()}. I can't confirm it's still there."
        selected["context"] = [
            row
            for row in store.frame_context(selected["id"])
            if (not seen_after or aware_time(row["observed_at"]) >= aware_time(seen_after))
            and (not seen_before or aware_time(row["observed_at"]) <= aware_time(seen_before))
        ]
    return {
        "kind": "history",
        "object_query": object_query,
        "status": "clarify" if ambiguous else "seen" if selected else "uncertain",
        "answer": answer,
        "evidence": selected,
        "checked": checked,
        "verifier": verifier.fingerprint if verifier else None,
        "scope": {
            "mode": mode,
            "candidate_limit": 17 if mode == "latest" else limit,
            "candidates_retrieved": len(candidates),
            "checked_count": len(checked),
            "fallback_used": mode == "latest" and len(checked) > recent_count,
            "seen_after": seen_after,
            "seen_before": seen_before,
            "known_time_only": mode == "latest" or bool(seen_after or seen_before),
            "note": "Only sampled frames were checked: up to 12 newest frames, then up to 5 semantic fallback candidates if needed in latest mode. This is not an exhaustive last-sighting search. Unknown clock times are excluded from latest/time-filtered history. Neighbors are context, not verified sightings. Gaps and unindexed footage may remain.",
        },
    }
