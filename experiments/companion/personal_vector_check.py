"""Offline vec0 parity/scale check and optional replay of saved manual-trial candidates.

No inference, capture or media uploads. Private results must stay under ignored data/runs.
"""

import argparse
import hashlib
import json
import sqlite3
import statistics
import subprocess
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from nyx.background_memory import BackgroundMemory
from nyx.personal_memory import PersonalMemory
from nyx.voice import Conversations


def forbidden(*args, **kwargs):
    raise AssertionError("Offline verification must not perform inference")


def baseline_class():
    source = subprocess.run(
        ["git", "show", "4feac67:src/nyx/personal_memory.py"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    namespace = {}
    # Trusted, pinned repository code; this baseline is never part of the application.
    exec(compile(source, "baseline-personal-memory", "exec"), namespace)  # noqa: S102
    return namespace["PersonalMemory"]


def timed(call, repeats=5):
    durations, result = [], None
    for _ in range(repeats):
        start = time.perf_counter()
        result = call()
        durations.append((time.perf_counter() - start) * 1000)
    return result, round(statistics.median(durations), 3)


def scale(count, baseline):
    rng = np.random.default_rng(20261118)
    vectors = rng.normal(size=(count, 768)).astype(np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    query = rng.normal(size=768).astype(np.float32)
    query /= np.linalg.norm(query)
    encoder = SimpleNamespace(
        dimensions=768,
        fingerprint={"model": "offline-scale", "dimensions": 768},
        encode_text=lambda _: query,
    )
    with tempfile.TemporaryDirectory(prefix="nyx-vector-scale-") as root:
        conversations = Conversations(Path(root))
        PersonalMemory(conversations, encoder, forbidden)
        turn = conversations.begin("The item is on the shelf.", {})
        with conversations.connect() as db:
            db.executemany(
                "INSERT INTO memories(id,turn_id,content,kind,quotes,embedding,encoder,visual) VALUES (?,?,?,?,?,?,?,?)",
                [
                    (
                        str(i),
                        turn,
                        "Item on shelf",
                        "report",
                        json.dumps([{"turn_id": turn, "text": "The item"}]),
                        vector.tobytes(),
                        json.dumps(encoder.fingerprint),
                        "{}",
                    )
                    for i, vector in enumerate(vectors)
                ],
            )
        start = time.perf_counter()
        memory = PersonalMemory(conversations, encoder, forbidden)
        migration_ms = round((time.perf_counter() - start) * 1000, 3)
        old = baseline(conversations, encoder, forbidden)
        expected, old_ms = timed(lambda: old.recall("item"))
        actual, new_ms = timed(lambda: memory.recall("item"))
        ids = lambda value: [r["id"] for r in value["matches"]]
        assert ids(actual) == ids(expected)
        lane = BackgroundMemory(
            SimpleNamespace(conversations=conversations, personal_memory=lambda: memory)
        )
        try:
            lane.prefetch("query", "item").result(timeout=10)
            _, early_ms = timed(lambda: lane.early_context("query"))
        finally:
            lane.close()
        return {
            "records": count,
            "dimensions": 768,
            "top5_parity": True,
            "baseline_recall_median_ms": old_ms,
            "vec0_recall_median_ms": new_ms,
            "selected_context_median_ms": early_ms,
            "additive_backfill_ms": migration_ms,
        }


def manual(source, baseline):
    path = source.resolve() / "conversations.sqlite3"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    evidence = json.loads((source / "evidence.json").read_text())
    with tempfile.TemporaryDirectory(prefix="nyx-manual-vector-") as root:
        with (
            sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True) as original,
            sqlite3.connect(Path(root) / "conversations.sqlite3") as copy,
        ):
            original.backup(copy)
        conversations = Conversations(Path(root), recover_pending=False)
        with conversations.connect() as db:
            before = [tuple(r) for r in db.execute("SELECT * FROM memories ORDER BY id")]
            fingerprint = json.loads(
                db.execute("SELECT encoder FROM memories LIMIT 1").fetchone()[0]
            )
        encoder = SimpleNamespace(
            fingerprint=fingerprint, dimensions=fingerprint["dimensions"], encode_text=forbidden
        )
        memory = PersonalMemory(conversations, encoder, forbidden)
        expected = baseline(conversations, encoder, forbidden).recall(
            evidence["utterance"], rank_all=False
        )
        lane = BackgroundMemory(
            SimpleNamespace(conversations=conversations, personal_memory=lambda: memory)
        )
        try:
            start = time.perf_counter()
            actual = lane.prefetch("manual-replay", evidence["utterance"]).result(timeout=5)
            context = lane.early_context("manual-replay")
            elapsed = round((time.perf_counter() - start) * 1000, 3)
        finally:
            lane.close()
        assert {r["id"] for r in actual["matches"]} == {r["id"] for r in expected["matches"]}
        with conversations.connect() as db:
            assert before == [tuple(r) for r in db.execute("SELECT * FROM memories ORDER BY id")]
        assert digest == hashlib.sha256(path.read_bytes()).hexdigest()
        return {
            "source": str(source),
            "query": evidence["utterance"],
            "records": context["records"],
            "prepare_ms": elapsed,
            "candidate_parity": True,
            "memory_rows_unchanged": True,
            "original_database_unchanged": True,
            "inference_requests": 0,
            "limitations": "Retrieval/context replay only; no new LLM, STT, TTS or image-recognition measurement.",
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manual", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    baseline = baseline_class()
    result = {
        "baseline": "4feac67",
        "method": "Offline, five warm repeats; precomputed synthetic query excludes provider latency.",
        "scale": [scale(n, baseline) for n in (1000, 10000)],
    }
    if args.manual:
        result["manual"] = manual(args.manual, baseline)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "scale": result["scale"],
                "manual": {
                    k: v
                    for k, v in result.get("manual", {}).items()
                    if k not in {"query", "records"}
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
