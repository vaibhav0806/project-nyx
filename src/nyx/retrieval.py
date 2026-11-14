import math
import shutil
import time
import uuid
from pathlib import Path

from PIL import Image

from nyx.capture import extract_frames
from nyx.perception import compatible_fingerprints


def _check_encoder(store, encoder):
    if (
        not compatible_fingerprints(store.fingerprint, encoder.fingerprint)
        or store.dimensions != encoder.dimensions
    ):
        raise ValueError("The index uses a different encoder")


def index_video(
    video: Path,
    store,
    encoder,
    interval=2.0,
    batch_size=8,
    recorded_at=None,
    *,
    video_id=None,
    name=None,
    adaptive=False,
    capture_session=None,
):
    steps = index_video_batches(
        video,
        store,
        encoder,
        interval,
        batch_size,
        recorded_at,
        video_id=video_id,
        name=name,
        adaptive=adaptive,
        capture_session=capture_session,
    )
    while True:
        try:
            next(steps)
        except StopIteration as done:
            return done.value


def index_video_batches(
    video: Path,
    store,
    encoder,
    interval=2.0,
    batch_size=2,
    recorded_at=None,
    *,
    video_id=None,
    name=None,
    adaptive=False,
    capture_session=None,
):
    _check_encoder(store, encoder)
    if not math.isfinite(interval) or interval <= 0:
        raise ValueError("Sampling interval must be finite and positive")
    if batch_size < 1:
        raise ValueError("Batch size must be positive")
    video = Path(video).resolve()
    if not video.is_file():
        raise ValueError(f"Video does not exist: {video}")
    video_id = video_id or uuid.uuid4().hex
    if len(video_id) != 32 or any(char not in "0123456789abcdef" for char in video_id):
        raise ValueError("Video ID must be a hexadecimal UUID")
    relative_video = Path("recordings") / f"{video_id}{video.suffix}"
    frame_dir = store.root / "frames" / video_id
    copied_video = store.root / relative_video
    copied_video.parent.mkdir(exist_ok=True)
    existing = store.video(video_id)
    if existing:
        if (
            existing["path"] != str(relative_video)
            or existing["recorded_at"] != recorded_at
            or existing["interval_seconds"] != interval
        ):
            raise ValueError("Recording ID metadata differs from the saved source")
        if capture_session is not None:
            with store.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                session = db.execute(
                    "SELECT capture_session FROM videos WHERE id=?", (video_id,)
                ).fetchone()[0]
                if session is not None and session != capture_session:
                    raise ValueError("Recording capture session differs from the saved source")
                db.execute(
                    "UPDATE videos SET capture_session=? WHERE id=?", (capture_session, video_id)
                )
        if existing["status"] == "ready":
            return {
                "video_id": video_id,
                "frame_count": existing["frame_count"],
                "last_sample_seconds": existing["last_sample_seconds"],
                "index_seconds": 0,
                "device": encoder.device,
                "encoder": encoder.fingerprint,
            }
        store.restart_video(video_id)
        shutil.rmtree(frame_dir, ignore_errors=True)
    else:
        store.add_video(
            name or video.name,
            str(relative_video),
            recorded_at,
            interval,
            video_id,
            capture_session=capture_session,
        )
    managed_source = video == copied_video
    started = time.perf_counter()
    try:
        if not managed_source:
            shutil.copyfile(video, copied_video)
        scan_interval = min(interval, 0.1) if adaptive else interval
        frames = extract_frames(copied_video, frame_dir, scan_interval)
        decoded_samples = len(frames)
        if adaptive:
            from nyx.attention import select_activity_frames

            selected = select_activity_frames(frames)
            keep = {path for _, path in selected}
            for _, path in frames:
                if path not in keep:
                    path.unlink()
            frames = selected
        with store.connection() as db:
            db.execute(
                "UPDATE videos SET sampling_policy=? WHERE id=?",
                (
                    f"activity-v2/scan={scan_interval:g}s/0.5s-persistence/coverage=2s"
                    if adaptive
                    else "periodic",
                    video_id,
                ),
            )
        for offset in range(0, len(frames), batch_size):
            batch = frames[offset : offset + batch_size]
            images = []
            for _, path in batch:
                with Image.open(path) as image:
                    images.append(image.convert("RGB"))
            vectors = encoder.encode_images(images)
            store.add_frames(
                video_id,
                [(seconds, str(path.relative_to(store.root))) for seconds, path in batch],
                vectors,
            )
            yield {
                "video_id": video_id,
                "indexed_frames": offset + len(batch),
                "total_frames": len(frames),
            }
        store.finish_video(video_id)
    except Exception as exc:
        store.fail_video(video_id, str(exc))
        shutil.rmtree(frame_dir, ignore_errors=True)
        if not managed_source:
            copied_video.unlink(missing_ok=True)
        raise
    return {
        "video_id": video_id,
        "frame_count": len(frames),
        "decoded_samples": decoded_samples,
        "last_sample_seconds": frames[-1][0],
        "index_seconds": time.perf_counter() - started,
        "device": encoder.device,
        "encoder": encoder.fingerprint,
    }


def search(query, store, encoder, *, reference_image=None, **filters):
    if not query.strip():
        raise ValueError("Search query must not be blank")
    _check_encoder(store, encoder)
    text_rows = store.search(encoder.encode_text(query.strip()), **filters)
    if reference_image is None or not text_rows:
        return text_rows
    image_rows = store.search(encoder.encode_images([reference_image])[0], **filters)
    limit = filters.get("limit", 5)
    return merge_candidates(text_rows, image_rows, limit)


def merge_candidates(text_rows, image_rows, limit):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Candidate limit must be between 1 and 100")
    # Reserve nominations for both routes before ranking: consensus alone can crowd
    # out the sole reference match. Similarity remains a candidate signal, not proof.
    selected, rows, scores, routes = [], {}, {}, {}
    for route, candidates in [("text", text_rows), ("reference_image", image_rows)]:
        for rank, row in enumerate(candidates, 1):
            identifier = row["id"]
            rows.setdefault(identifier, row)
            scores[identifier] = scores.get(identifier, 0) + 1 / (60 + rank)
            routes.setdefault(identifier, []).append(route)
    for rank in range(max(len(text_rows), len(image_rows))):
        for candidates in [text_rows, image_rows]:
            if rank < len(candidates) and candidates[rank]["id"] not in selected:
                selected.append(candidates[rank]["id"])
                if len(selected) == limit:
                    break
        if len(selected) == limit:
            break
    selected.sort(key=lambda identifier: -scores[identifier])
    return [
        {**rows[i], "retrieval_score": scores[i] * 61 / 2, "retrieval_routes": routes[i]}
        for i in selected
    ]


def rebuild_embeddings(store, encoder, batch_size=8):
    """Re-embed saved samples atomically; preserve media, IDs and recording times.

    Run with the app stopped. A failed cloud batch rolls back all vector changes.
    """
    import json

    from nyx.memory import _vector

    if batch_size < 1:
        raise ValueError("Batch size must be positive")
    count = 0
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        rows = db.execute("SELECT id, thumbnail FROM frames ORDER BY id").fetchall()
        for start in range(0, len(rows), batch_size):
            batch = rows[start : start + batch_size]
            images = []
            for row in batch:
                with Image.open(store.root / row["thumbnail"]) as image:
                    images.append(image.convert("RGB"))
            vectors = encoder.encode_images(images)
            if len(vectors) != len(batch):
                raise ValueError("Frame and vector counts differ")
            db.executemany(
                "UPDATE frames SET embedding=? WHERE id=?",
                [
                    (_vector(vector, encoder.dimensions), row["id"])
                    for row, vector in zip(batch, vectors, strict=True)
                ],
            )
            count += len(batch)
        db.execute(
            "UPDATE meta SET value=? WHERE key='encoder'",
            (
                json.dumps(
                    {"encoder": encoder.fingerprint, "dimensions": encoder.dimensions},
                    sort_keys=True,
                ),
            ),
        )
    store.fingerprint = encoder.fingerprint
    store.dimensions = encoder.dimensions
    return {"reembedded_frames": count, "encoder": encoder.fingerprint}
