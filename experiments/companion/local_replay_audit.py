"""Read-only past-library audit and copied-index query replay; no inference or media upload."""

import argparse
import hashlib
import inspect
import json
import sqlite3
import subprocess
from pathlib import Path

import numpy as np

from nyx.memory import Store
from nyx.verification import CloudVerifier


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def source_context():
    model = object.__new__(CloudVerifier)
    payloads = []

    def capture(messages, *args):
        payloads.append(json.loads(messages[-1]["content"]))
        return '{"action":"clarify","message":"Which item?"}'

    model.generate_decision = capture
    state = {
        "message": "Where is it?",
        "conversation": [
            {
                "transcript": "Find my green phone",
                "answer": "It was beside the deleted orange vase.",
                "sources_available": False,
                "plan": {
                    "steps": [{"action": "search_history", "query": "green phone", "hours": 2}]
                },
            }
        ],
    }
    model.decide(state)
    serialized = json.dumps(payloads)
    return {
        "invalidated_claim_withheld": "deleted orange vase" not in serialized,
        "query_constraint_preserved": "green phone" in serialized,
        "saved_input_unchanged": state["conversation"][0]["answer"]
        == "It was beside the deleted orange vase.",
    }


def run(data, output, limit=24, full_decode=False):
    if not 1 <= limit <= 256:
        raise ValueError("Bounded sample size must be 1–256")
    data = data.resolve()
    output.mkdir(parents=True, exist_ok=False)
    copy = output / "copied-index"
    copy.mkdir()
    with (
        sqlite3.connect(f"{(data / 'index.sqlite3').as_uri()}?mode=ro", uri=True) as original,
        sqlite3.connect(copy / "index.sqlite3") as target,
    ):
        original.backup(target)
    with sqlite3.connect(copy / "index.sqlite3") as db:
        db.row_factory = sqlite3.Row
        identity = json.loads(
            db.execute("SELECT value FROM meta WHERE key='encoder'").fetchone()[0]
        )
        counts = {
            table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ["videos", "frames"]
        }
        sources = [
            dict(row)
            for row in db.execute(
                "SELECT id,path,status,recorded_at FROM videos ORDER BY recorded_at,id LIMIT ?",
                (limit,),
            )
        ]
        queries = [
            dict(row)
            for row in db.execute("SELECT id,embedding FROM frames ORDER BY id LIMIT ?", (limit,))
        ]
    store = Store(copy, identity["encoder"], identity["dimensions"])
    report = {
        "application_source_sha256": digest(Path(inspect.getfile(Store))),
        "verifier_source_sha256": digest(Path(inspect.getfile(CloudVerifier))),
        "scope": "Existing local library, copied index, stored-vector self queries; media stays local. Decode depth is recorded by full_video_decode. Audio and semantic/identity accuracy are excluded.",
        "full_video_decode": full_decode,
        "library_counts": counts,
        "context": source_context(),
        "queries": [],
        "media": [],
    }
    for row in queries:
        vector = np.frombuffer(row["embedding"], dtype=np.float32)
        hits = store.search(vector, limit=5)
        report["queries"].append(
            {
                "query_frame_id": row["id"],
                "hits": [
                    {
                        "id": hit["id"],
                        "observed_at": hit["observed_at"],
                        "offset_seconds": hit["offset_seconds"],
                    }
                    for hit in hits
                ],
            }
        )
    for row in sources:
        path = (data / row["path"]).resolve()
        result = {
            "id": row["id"],
            "registered_status": row["status"],
            "capture_time_known": row["recorded_at"] is not None,
        }
        if not path.is_relative_to(data) or not path.is_file():
            result["status"] = "unavailable"
        else:
            before = digest(path)
            probe = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "json",
                    str(path),
                ],
                check=False,
                capture_output=True,
                timeout=15,
            )
            decode = subprocess.run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-v",
                    "error",
                    *(["-xerror", "-err_detect", "explode"] if full_decode else []),
                    "-i",
                    str(path),
                    *([] if full_decode else ["-frames:v", "1"]),
                    "-an",
                    "-f",
                    "null",
                    "-",
                ],
                check=False,
                capture_output=True,
                timeout=120 if full_decode else 15,
            )
            result.update(
                status="readable"
                if probe.returncode == decode.returncode == 0
                else "decode_failed",
                bytes=path.stat().st_size,
                bytes_preserved=before == digest(path),
            )
        report["media"].append(result)
        (output / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    (output / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=24)
    parser.add_argument(
        "--full-decode",
        action="store_true",
        help="Strictly decode all video frames in each sampled recording; audio excluded",
    )
    args = parser.parse_args()
    result = run(args.data, args.output, args.limit, args.full_decode)
    print(
        json.dumps(
            {
                "library_counts": result["library_counts"],
                "queries": len(result["queries"]),
                "media_statuses": {
                    status: sum(r["status"] == status for r in result["media"])
                    for status in ["readable", "unavailable", "decode_failed"]
                },
                "context": result["context"],
            }
        )
    )
