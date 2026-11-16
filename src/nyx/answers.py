import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

from nyx.capture import frame_image
from nyx.memory import aware_time
from nyx.retrieval import search
from nyx.verification import unavailable_source_judgment


def diverse_candidates(rows, limit, spacing_seconds=4):
    """Nominate distinct nearby moments; keep deferred neighbors if needed."""
    chosen, deferred = [], []

    def nearby_moment(row, other):
        if row["video_id"] == other["video_id"]:
            return abs(row["offset_seconds"] - other["offset_seconds"]) < spacing_seconds
        if (
            row.get("capture_session")
            and row.get("capture_session") == other.get("capture_session")
            and row.get("observed_at")
            and other.get("observed_at")
        ):
            return (
                abs(
                    (
                        aware_time(row["observed_at"]) - aware_time(other["observed_at"])
                    ).total_seconds()
                )
                < spacing_seconds
            )
        return False

    for row in rows:
        nearby = any(nearby_moment(row, other) for other in chosen)
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
    reference_image=None,
    reference_candidates=None,
    source_balanced=None,
):
    if mode not in {"latest", "relevance"}:
        raise ValueError("Choose latest or relevance history")
    if reference_candidates is None:
        reference_candidates = os.environ.get("NYX_REFERENCE_CANDIDATES", "0") == "1"
    if source_balanced is None:
        source_balanced = os.environ.get("NYX_SOURCE_BALANCED_CANDIDATES", "1") == "1"
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
        reference_image=reference_image if reference_candidates else None,
        source_balanced=bool(source_balanced and semantic_latest and mode == "latest"),
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
            reference_image=reference_image if reference_candidates else None,
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
            try:
                return frame_image(source, candidate["offset_seconds"])
            except (ValueError, OSError, subprocess.TimeoutExpired):
                return None

        if reference_image is not None:

            def inspect_reference(candidate):
                image = decode(candidate)
                if image is None:
                    return unavailable_source_judgment()
                return verifier.inspect_reference(image, reference_image, object_query)

            with ThreadPoolExecutor(
                max_workers=len(batch), thread_name_prefix="nyx-reference"
            ) as pool:
                judgments = list(
                    pool.map(
                        inspect_reference,
                        batch,
                    )
                )
            timings["reference_checks_ms"] = round((time.perf_counter() - phase) * 1000)
        elif callable(getattr(verifier, "inspect_frames", None)):
            frames = []
            for candidate in batch:
                source = (store.root / candidate["video_path"]).resolve()
                if not source.is_relative_to(store.root):
                    raise ValueError("Source must remain inside the local workspace")
                frames.append((source, candidate["offset_seconds"]))
            judgments = verifier.inspect_frames(frames, object_query)
            timings["frame_checks_ms"] = timings.get("frame_checks_ms", 0) + round(
                (time.perf_counter() - phase) * 1000
            )
        else:
            if len(batch) > 1:
                with ThreadPoolExecutor(
                    max_workers=len(batch), thread_name_prefix="nyx-decode"
                ) as pool:
                    images = list(pool.map(decode, batch))
            else:
                images = [decode(batch[0])]
            timings["decode_ms"] += round((time.perf_counter() - phase) * 1000)
            phase = time.perf_counter()
            available_images = [image for image in images if image is not None]
            verified = list(
                (
                    verifier.inspect_batch(available_images, object_query)
                    if batch_size > 1
                    else [verifier.inspect(available_images[0], object_query)]
                )
                if available_images
                else []
            )
            if len(verified) != len(available_images):
                raise ValueError("Verification result count does not match source frames")
            verified = iter(verified)
            judgments = [
                next(verified) if image is not None else unavailable_source_judgment()
                for image in images
            ]
            timings["verification_ms"] += round((time.perf_counter() - phase) * 1000)
        timings["vision_requests"] += sum(
            not judgment.get("source_unavailable") for judgment in judgments
        ) + sum(judgment.get("confirmation_requests", 0) for judgment in judgments)
        for candidate, judgment in zip(batch, judgments, strict=True):
            item = {
                **evidence_links(candidate),
                "judgment": judgment,
                "model_checked": not judgment.get("source_unavailable", False),
            }
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
    unavailable_count = sum(row["judgment"].get("source_unavailable", False) for row in checked)
    if unavailable_count:
        answer += " Some saved source frames could not be read."
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
            "reference_nomination": bool(reference_candidates and reference_image is not None),
            "source_balanced_nomination": bool(
                source_balanced and semantic_latest and mode == "latest"
            ),
            "diversity_seconds": 4 if semantic_latest else 0,
            "video_id": video_id,
            "excluded_frame_ids": list(excluded_frame_ids),
            "candidate_limit": 17 if mode == "latest" and not semantic_latest else limit,
            "candidates_retrieved": len(candidates),
            "checked_count": len(checked),
            "unavailable_frame_count": unavailable_count,
            "model_checked_count": len(checked) - unavailable_count,
            "fallback_used": mode == "latest" and len(checked) > recent_count,
            "seen_after": seen_after,
            "seen_before": seen_before,
            "known_time_only": mode == "latest" or bool(seen_after or seen_before),
            "note": "Only sampled frames were checked: up to 12 newest frames, then up to 5 semantic fallback candidates if needed in latest mode. This is not an exhaustive last-sighting search. Unknown clock times are excluded from latest/time-filtered history. Neighbors are context, not verified sightings. Gaps and unindexed footage may remain.",
        },
    }
