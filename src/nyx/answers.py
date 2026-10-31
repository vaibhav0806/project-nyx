import time
from concurrent.futures import ThreadPoolExecutor

from nyx.capture import frame_image
from nyx.memory import aware_time
from nyx.retrieval import search


def diverse_candidates(rows, limit, spacing_seconds=4):
    """Nominate distinct nearby moments; keep deferred neighbors if needed."""
    chosen, deferred = [], []
    for row in rows:
        nearby = any(
            row["video_id"] == other["video_id"]
            and abs(row["offset_seconds"] - other["offset_seconds"]) < spacing_seconds
            for other in chosen
        )
        if nearby:
            deferred.append(row)
        else:
            chosen.append(row)
        if len(chosen) == limit:
            break
    return (chosen + deferred)[:limit]


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
    excluded_frame_ids=(),
):
    if mode not in {"latest", "relevance"}:
        raise ValueError("Choose latest or relevance history")
    started = time.perf_counter()
    timings = {"decode_ms": 0, "verification_ms": 0}
    limit = 12 if mode == "latest" else 5
    candidates = search(
        object_query,
        store,
        encoder,
        limit=64 if semantic_latest else limit,
        video_id=video_id,
        seen_after=seen_after,
        seen_before=seen_before,
        order="relevance" if semantic_latest and mode == "latest" else mode,
        known_time_only=semantic_latest,
        excluded_frame_ids=excluded_frame_ids,
    )
    if semantic_latest and mode == "latest":
        candidates = diverse_candidates(candidates, limit)
        candidates.sort(key=lambda row: row["observed_at"], reverse=True)
    recent_count = len(candidates)
    if mode == "latest" and not semantic_latest:
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
            excluded_frame_ids=excluded_frame_ids,
        )
        candidates.extend(
            sorted(
                (row for row in fallback if row["id"] not in known_ids),
                key=lambda row: row["observed_at"],
                reverse=True,
            )
        )
    timings["retrieval_ms"] = round((time.perf_counter() - started) * 1000)
    checked = []
    selected = None
    verifier = None
    verifier = verifier_factory() if candidates else None
    batch_size = (
        getattr(verifier, "history_concurrency", 3)
        if callable(getattr(verifier, "inspect_batch", None))
        else 1
    )
    stop = False
    ambiguous = False
    timings["vision_requests"] = 0
    for start in range(0, len(candidates), batch_size):
        batch = candidates[start : start + batch_size]
        phase = time.perf_counter()

        def decode(candidate):
            source = (store.root / candidate["video_path"]).resolve()
            if not source.is_relative_to(store.root):
                raise ValueError("Source must remain inside the local workspace")
            return frame_image(source, candidate["offset_seconds"])

        if len(batch) > 1:
            with ThreadPoolExecutor(
                max_workers=len(batch), thread_name_prefix="nyx-decode"
            ) as pool:
                images = list(pool.map(decode, batch))
        else:
            images = [decode(batch[0])]
        timings["decode_ms"] += round((time.perf_counter() - phase) * 1000)
        phase = time.perf_counter()
        judgments = (
            verifier.inspect_batch(images, object_query)
            if batch_size > 1
            else [verifier.inspect(images[0], object_query)]
        )
        timings["verification_ms"] += round((time.perf_counter() - phase) * 1000)
        timings["vision_requests"] += len(images) if batch_size > 1 else 1
        for candidate, judgment in zip(batch, judgments, strict=True):
            item = {**evidence_links(candidate), "judgment": judgment, "model_checked": True}
            checked.append(item)
            if not stop and judgment.get("ambiguous"):
                stop = True
                ambiguous = True
            elif not stop and judgment["visibility"] == "visible":
                selected = item
                stop = True
        yield {"checked": len(checked), "candidate_limit": limit}
        if stop:
            break
    answer = f"I couldn't confirm {object_query} in the sampled frames checked. This does not prove it wasn't there."
    if ambiguous:
        answer = "Which one do you mean? Please describe its color, position, or another distinguishing detail."
    if selected:
        when = (
            selected["observed_at"]
            or f"clip offset {selected['offset_seconds']:.2f}s (capture clock time unknown)"
        )
        qualifier = (
            "Latest visual candidate within the checked frames"
            if mode == "latest"
            else "Visual candidate"
        )
        answer = f"{qualifier}, recorded at {when}. Is this the item you mean? I have not verified its identity or current location."
        selected["context"] = [
            row
            for row in store.frame_context(selected["id"])
            if (not seen_after or aware_time(row["observed_at"]) >= aware_time(seen_after))
            and (not seen_before or aware_time(row["observed_at"]) <= aware_time(seen_before))
        ]
    return {
        "kind": "history",
        "timings": timings,
        "object_query": object_query,
        "status": "clarify" if ambiguous else "candidate" if selected else "uncertain",
        "answer": answer,
        "evidence": selected,
        "checked": checked,
        "verifier": verifier.fingerprint if verifier else None,
        "scope": {
            "mode": mode,
            "candidate_pool_limit": 64 if semantic_latest else limit,
            "diversity_seconds": 4 if semantic_latest else 0,
            "video_id": video_id,
            "excluded_frame_ids": list(excluded_frame_ids),
            "candidate_limit": 17 if mode == "latest" and not semantic_latest else limit,
            "candidates_retrieved": len(candidates),
            "checked_count": len(checked),
            "fallback_used": mode == "latest" and len(checked) > recent_count,
            "seen_after": seen_after,
            "seen_before": seen_before,
            "known_time_only": mode == "latest" or bool(seen_after or seen_before),
            "note": "Only sampled frames were checked: up to 12 newest frames, then up to 5 semantic fallback candidates if needed in latest mode. This is not an exhaustive last-sighting search. Unknown clock times are excluded from latest/time-filtered history. Neighbors are context, not verified sightings. Gaps and unindexed footage may remain.",
        },
    }
