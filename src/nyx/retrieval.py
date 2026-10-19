import math
import shutil
import time
import uuid
from pathlib import Path

from PIL import Image

from nyx.capture import extract_frames


def _check_encoder(store, encoder):
    if store.fingerprint != encoder.fingerprint or store.dimensions != encoder.dimensions:
        raise ValueError("The index uses a different encoder")


def index_video(video: Path, store, encoder, interval=2.0, batch_size=8, recorded_at=None):
    _check_encoder(store, encoder)
    if not math.isfinite(interval) or interval <= 0:
        raise ValueError("Sampling interval must be finite and positive")
    if batch_size < 1:
        raise ValueError("Batch size must be positive")
    video = Path(video).resolve()
    if not video.is_file():
        raise ValueError(f"Video does not exist: {video}")
    name = uuid.uuid4().hex
    relative_video = Path("recordings") / f"{name}{video.suffix}"
    frame_dir = store.root / "frames" / name
    copied_video = store.root / relative_video
    copied_video.parent.mkdir(exist_ok=True)
    video_id = store.add_video(video.name, str(relative_video), recorded_at, interval)
    started = time.perf_counter()
    try:
        shutil.copyfile(video, copied_video)
        frames = extract_frames(copied_video, frame_dir, interval)
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
        store.finish_video(video_id)
    except Exception as exc:
        store.fail_video(video_id, str(exc))
        shutil.rmtree(frame_dir, ignore_errors=True)
        copied_video.unlink(missing_ok=True)
        raise
    return {
        "video_id": video_id,
        "frame_count": len(frames),
        "last_sample_seconds": frames[-1][0],
        "index_seconds": time.perf_counter() - started,
        "device": encoder.device,
        "encoder": encoder.fingerprint,
    }


def search(query, store, encoder, **filters):
    if not query.strip():
        raise ValueError("Search query must not be blank")
    _check_encoder(store, encoder)
    return store.search(encoder.encode_text(query.strip()), **filters)
