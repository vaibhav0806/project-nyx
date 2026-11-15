"""Bounded synthetic multi-day indexing/fault replay. No devices or provider inference."""

import argparse
import hashlib
import json
import math
import platform
import resource
import shutil
import statistics
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from nyx.memory import Store
from nyx.recording import CaptureJournal
from nyx.retrieval import index_video, index_video_batches


def estimate_capacity(
    *,
    days=10,
    bit_rate=1000000,
    budget_bytes=1024**3,
    sample_seconds=2,
    dimensions=768,
    thumbnail_bytes=None,
):
    values = [days, bit_rate, budget_bytes, sample_seconds, dimensions]
    if any(not math.isfinite(x) or x <= 0 for x in values):
        raise ValueError("Capacity inputs must be finite and positive")
    if thumbnail_bytes is not None and (not math.isfinite(thumbnail_bytes) or thumbnail_bytes < 0):
        raise ValueError("Invalid thumbnail size")
    samples = math.ceil(days * 86400 / sample_seconds)
    return {
        "nominal_video_bytes": days * 86400 * bit_rate / 8,
        "sample_floor_count": samples,
        "raw_vector_bytes": samples * dimensions * 4,
        "projected_thumbnail_bytes": samples * thumbnail_bytes
        if thumbnail_bytes is not None
        else None,
        "nominal_budget_hours": budget_bytes * 8 / bit_rate / 3600,
    }


def score_window(expected, actual):
    missing, extra = set(expected) - set(actual), set(actual) - set(expected)
    return {
        "correct": not missing and not extra,
        "missing": sorted(missing),
        "unexpected": sorted(extra),
    }


class LoadEncoder:
    """Fast deterministic load boundary; no semantic/model throughput claim."""

    dimensions = 768
    device = "synthetic-load"

    def __init__(self):
        self.fail_once = False

    @property
    def fingerprint(self):
        return {"model": "synthetic-rgb-load", "dimensions": self.dimensions}

    def encode_images(self, images):
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("Synthetic provider outage")
        colors = np.array([np.asarray(image).mean(axis=(0, 1)) for image in images]) + 1
        vectors = np.tile(colors, (1, 256))
        return (vectors / np.linalg.norm(vectors, axis=1, keepdims=True)).astype(np.float32)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    if shutil.disk_usage(output).free < 256 * 1024**2:
        raise ValueError("Insufficient disk headroom for bounded replay")
    sources = output / "fixtures"
    sources.mkdir()
    for name, source in [
        ("static", "color=c=gray:s=640x360:r=10:d=10"),
        ("moving", "testsrc2=size=640x360:rate=10:duration=10"),
    ]:
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-n",
                "-f",
                "lavfi",
                "-i",
                source,
                "-an",
                "-c:v",
                "libx264",
                "-b:v",
                "1000000",
                "-pix_fmt",
                "yuv420p",
                str(sources / f"{name}.mp4"),
            ],
            check=True,
            timeout=30,
        )
    root = output / "workspace"
    encoder = LoadEncoder()
    store = Store(root, encoder.fingerprint, encoder.dimensions)
    journal = CaptureJournal(root)
    clock = datetime.now(UTC)
    report = {
        "status": "running",
        "evaluation_at": clock.isoformat(),
        "segments": [],
        "faults": {},
        "python": platform.python_version(),
        "encoder": encoder.fingerprint,
        "limitations": "Ten logical days with large explicit gaps, not ten elapsed days or continuous coverage. Generated video only. Decoder/selection/storage are real; embeddings are a synthetic load boundary, not model quality/throughput or provider resilience.",
        "provider_requests": 0,
    }
    start = time.perf_counter()

    def checkpoint():
        (output / "results.json").write_text(json.dumps(report, indent=2) + "\n")

    def index(segment):
        journal.mark(segment["id"], "indexing")
        try:
            indexed = index_video(
                root / segment["path"],
                store,
                encoder,
                recorded_at=None if segment["timing_uncertain"] else segment["recorded_at"],
                video_id=segment["id"],
                capture_session=segment["session_id"],
                adaptive=True,
            )
        except RuntimeError:
            journal.mark(segment["id"], "failed", "Synthetic provider outage")
            raise
        journal.mark(segment["id"], "ready", last_sample_seconds=indexed["last_sample_seconds"])
        return indexed

    try:
        for day in range(10):
            at = clock - timedelta(days=9 - day, minutes=1)
            session = journal.start(at.isoformat())
            for part in range(3):
                began = at + timedelta(seconds=part * 12)
                ended = began + timedelta(seconds=10)
                source = sources / ("moving.mp4" if part == 1 else "static.mp4")
                segment = journal.begin_segment(
                    session["id"], part, began.isoformat(), ended.isoformat(), ".mp4"
                )
                shutil.copyfile(source, journal.partial_path(segment["id"]))
                segment = journal.finish_upload(segment["id"], source.stat().st_size)
                original_hash = digest(root / segment["path"])
                if day == 4 and part == 1:
                    journal.mark(segment["id"], "indexing")
                    steps = index_video_batches(
                        root / segment["path"],
                        store,
                        encoder,
                        batch_size=1,
                        recorded_at=segment["recorded_at"],
                        video_id=segment["id"],
                        capture_session=session["id"],
                        adaptive=True,
                    )
                    next(steps)
                    steps.close()
                    journal = CaptureJournal(root)
                    journal.recover()
                    report["faults"]["interrupted_index_requeued"] = (
                        journal.segment(segment["id"])["state"] == "queued"
                    )
                if day == 5 and part == 0:
                    encoder.fail_once = True
                    try:
                        index(segment)
                    except RuntimeError:
                        retry = journal.begin_segment(
                            session["id"], part, began.isoformat(), ended.isoformat(), ".mp4"
                        )
                        report["faults"]["explicit_outage_retry_queued"] = (
                            retry["state"] == "queued"
                        )
                elapsed = time.perf_counter()
                indexed = index(segment)
                report["segments"].append(
                    {
                        "id": segment["id"],
                        "synthetic_at": began.isoformat(),
                        "expected_in_window": True,
                        "profile": source.stem,
                        "samples": indexed["frame_count"],
                        "index_ms": (time.perf_counter() - elapsed) * 1000,
                        "bytes_preserved": original_hash == digest(root / segment["path"]),
                    }
                )
                checkpoint()
            journal.transition(
                session["id"],
                "stopped",
                (at + timedelta(seconds=36)).isoformat(),
                "Synthetic replay day ended; gaps are not coverage",
            )
        for label, days, uncertain in [
            ("older", 11, False),
            ("future", -1, False),
            ("unknown", 3, True),
        ]:
            at = clock - timedelta(days=days)
            session = journal.start(at.isoformat())
            segment = journal.begin_segment(
                session["id"],
                0,
                at.isoformat(),
                (at + timedelta(seconds=10)).isoformat(),
                ".mp4",
                uncertain,
            )
            source = sources / "static.mp4"
            shutil.copyfile(source, journal.partial_path(segment["id"]))
            segment = journal.finish_upload(segment["id"], source.stat().st_size)
            original_hash = digest(root / segment["path"])
            indexed = index(segment)
            report["segments"].append(
                {
                    "id": segment["id"],
                    "synthetic_at": at.isoformat(),
                    "case": label,
                    "expected_in_window": False,
                    "samples": indexed["frame_count"],
                    "bytes_preserved": original_hash == digest(root / segment["path"]),
                }
            )
            journal.transition(
                session["id"],
                "stopped",
                (at + timedelta(seconds=10)).isoformat(),
                "Synthetic edge case",
            )
        store = Store(root, encoder.fingerprint, encoder.dimensions)
        query = np.tile([0, 1, 0], 256)
        actual = [
            row["id"]
            for row in report["segments"]
            if store.search(
                query,
                limit=1,
                video_id=row["id"],
                known_time_only=True,
                source_balanced=True,
                seen_after=(clock - timedelta(days=10)).isoformat(),
                seen_before=clock.isoformat(),
            )
        ]
        expected = [row["id"] for row in report["segments"] if row["expected_in_window"]]
        report["window"] = score_window(expected, actual)
        segment = journal.segment(report["segments"][0]["id"])
        saved = root / segment["path"]
        held = saved.with_suffix(".held")
        saved.replace(held)
        report["faults"]["missing_source_detected"] = (
            journal.snapshot()["unavailable_segment_count"] == 1
        )
        held.replace(saved)
        report["faults"]["source_restore_detected"] = (
            journal.snapshot()["unavailable_segment_count"] == 0
        )

        budget_root = output / "budget-stop"
        (budget_root / "recordings").mkdir(parents=True)
        full = budget_root / "recordings" / "preserved.mp4"
        shutil.copyfile(sources / "static.mp4", full)
        before = digest(full)
        try:
            CaptureJournal(budget_root, budget_bytes=full.stat().st_size).start(clock.isoformat())
        except ValueError:
            report["faults"]["budget_stops_without_delete"] = digest(full) == before
        backlog = CaptureJournal(output / "backlog", max_pending=1)
        session = backlog.start(clock.isoformat())
        backlog.begin_segment(
            session["id"], 0, clock.isoformat(), (clock + timedelta(seconds=10)).isoformat(), ".mp4"
        )
        try:
            backlog.begin_segment(
                session["id"],
                1,
                (clock + timedelta(seconds=10)).isoformat(),
                (clock + timedelta(seconds=20)).isoformat(),
                ".mp4",
            )
        except ValueError:
            report["faults"]["backlog_refused"] = True

        thumbnails = [path.stat().st_size for path in (root / "frames").rglob("*.jpg")]
        report["capacity"] = estimate_capacity(thumbnail_bytes=statistics.mean(thumbnails))
        report["resources"] = {
            "generated_video_seconds": 330,
            "video_bytes": journal.video_bytes(),
            "sample_count": len(thumbnails),
            "mean_thumbnail_bytes": statistics.mean(thumbnails),
            "index_database_bytes": (root / "index.sqlite3").stat().st_size,
            "elapsed_seconds": time.perf_counter() - start,
        }
        scale = Store(output / "scale", encoder.fingerprint, encoder.dimensions)
        video = scale.add_video(
            "metadata scale only",
            "not-playable.mp4",
            (clock - timedelta(days=3)).isoformat(),
            2,
            capture_session="synthetic-scale",
        )
        vector = np.tile([1, 1, 1], 256).astype(np.float32)
        scale.add_frames(
            video,
            [(2 * i, "not-playable.jpg") for i in range(10000)],
            np.repeat(vector[None, :], 10000, axis=0),
        )
        scale.finish_video(video)
        report["scale_queries"] = {}
        for name, balanced in [("flat", False), ("balanced", True)]:
            timings = []
            for _ in range(5):
                began = time.perf_counter()
                scale.search(query, limit=64, known_time_only=True, source_balanced=balanced)
                timings.append((time.perf_counter() - began) * 1000)
            report["scale_queries"][name] = {
                "frames": 10000,
                "runs_ms": timings,
                "median_ms": statistics.median(timings),
            }
        report["resources"]["peak_process_rss_mib"] = resource.getrusage(
            resource.RUSAGE_SELF
        ).ru_maxrss / (1024**2 if platform.system() == "Darwin" else 1024)
        report["checks_passed"] = (
            report["window"]["correct"]
            and len(report["faults"]) == 6
            and all(report["faults"].values())
            and all(segment["bytes_preserved"] for segment in report["segments"])
        )
        if not report["checks_passed"]:
            raise ValueError("Runtime replay checks failed; inspect saved artifact")
        report["status"] = "complete"
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError):
        report["status"] = "failed"
        raise
    finally:
        checkpoint()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.output)
    print(
        json.dumps(
            {
                key: report[key]
                for key in ["status", "window", "faults", "resources", "capacity", "scale_queries"]
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
