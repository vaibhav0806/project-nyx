"""Explicitly authorized saved-media replay; isolated database, originals read-only.

Requires --source, --turn, --before, --query and --output. Uploads selected saved
frames and the chosen transcript to the configured cloud providers.
"""

import argparse
import json
import os
import shutil
import sqlite3
import tempfile
from datetime import timedelta
from pathlib import Path

from nyx.agent import agent_steps
from nyx.answers import history_steps
from nyx.capture import frame_image
from nyx.cloud import OpenRouter
from nyx.memory import Store, aware_time
from nyx.perception import CloudEncoder
from nyx.statements import Statements
from nyx.verification import CloudVerifier
from nyx.voice import Conversations, spoken_answer


def consume(generator):
    while True:
        try:
            next(generator)
        except StopIteration as done:
            return done.value


def main():
    parser = argparse.ArgumentParser()
    for name in ("source", "turn", "before", "query", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    source = Path(args.source).resolve()
    with sqlite3.connect(f"file:{source / 'conversations.sqlite3'}?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        original = dict(db.execute("SELECT * FROM turns WHERE id=?", (args.turn,)).fetchone())
    snapshot_at = json.loads(original["plan"])["current_snapshot_at"]
    with sqlite3.connect(f"file:{source / 'capture.sqlite3'}?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        segment = dict(
            db.execute(
                "SELECT * FROM segments WHERE timing_uncertain=0 AND julianday(recorded_at)<=julianday(?) AND julianday(ended_at)>=julianday(?)",
                (snapshot_at, snapshot_at),
            ).fetchone()
        )
    offset = (aware_time(snapshot_at) - aware_time(segment["recorded_at"])).total_seconds()
    image = frame_image(source / segment["path"], offset)
    client = OpenRouter()
    encoder, verifier = CloudEncoder(client=client), CloudVerifier(client=client)
    report = {
        "original_turn": args.turn,
        "snapshot_at": snapshot_at,
        "segment": segment["id"],
        "offset": offset,
    }
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        with (
            sqlite3.connect(f"file:{source / 'index.sqlite3'}?mode=ro", uri=True) as old,
            sqlite3.connect(root / "index.sqlite3") as new,
        ):
            old.backup(new)
        for name in ("recordings", "frames"):
            shutil.copytree(source / name, root / name, copy_function=os.link)
        store = Store(root, encoder.fingerprint, encoder.dimensions)
        conversations = Conversations(root)
        turn = conversations.begin(original["transcript"], {"mode": "authorized_replay"})
        with conversations.connect() as db:
            db.execute("UPDATE turns SET at=? WHERE id=?", (original["at"], turn))
        report["remember"] = Statements(conversations).remember(
            turn, verifier, encoder, image, snapshot_at
        )
        for _ in range(30):
            conversations.begin("Unrelated synthetic conversation", {})
        conversations = Conversations(root)
        assert turn not in [r["id"] for r in conversations.recent()]
        report["recent_context_empty"] = True

        def tool(action):
            if action["action"] == "search_statements":
                return Statements(conversations).recall(action["query"], encoder, verifier)
            if action["action"] == "search_history":
                lower = (
                    (aware_time(args.before) - timedelta(hours=action["hours"])).isoformat()
                    if action["hours"]
                    else None
                )
                result = consume(
                    history_steps(
                        action["query"],
                        store,
                        encoder,
                        lambda: verifier,
                        seen_after=lower,
                        seen_before=args.before,
                        semantic_latest=True,
                    )
                )
                result["answer"] = spoken_answer(result, now=aware_time(args.before))
                return result
            raise ValueError("Replay supports saved visual and statement retrieval only")

        report["agent"] = consume(
            agent_steps(
                "Where is my " + args.query + "?",
                [],
                verifier.decide,
                tool,
                available={"current_view": False, "history": True, "dated_history": True},
            )
        )
        evidence = report["agent"]["answer"]
        report["flash_answer"] = "".join(
            client.stream_text(
                [
                    {
                        "role": "system",
                        "content": "You are Nyx. All retrieval is complete. Answer naturally in at most two short sentences, using only supplied evidence. Preserve uncertainty, dates, and the distinction between what was seen and what the user planned. No tools or invented locations.",
                    },
                    {"role": "user", "content": "Where is my " + args.query + "?"},
                    {"role": "system", "content": "Checked tool evidence: " + evidence},
                ],
                "google/gemini-3.5-flash",
            )
        )
        report["usage"] = client.usage
        observations = report["agent"].get("observations", [])
        report["checks"] = {
            "object_link_saved": report["remember"]["status"] == "complete",
            "visual_evidence_found": any(r.get("evidence") for r in observations),
            "original_statement_recalled": any(
                m.get("turn_id") == turn for r in observations for m in r.get("matches", [])
            ),
            "both_sources_cited": any(
                "statement_observation" in a for a in report["agent"]["steps"]
            ),
        }
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2))
    assert all(report["checks"].values()), report["checks"]
    print(
        json.dumps(
            {
                "remember": report["remember"],
                "answer": report["flash_answer"],
                "actions": report["agent"]["steps"],
                "output": str(target),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
