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


def visual_window(source, at):
    frames = []
    with sqlite3.connect(f"file:{source / 'capture.sqlite3'}?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        for seconds in (10, 8, 6, 4, 2, 0):
            stamp = (aware_time(at) - timedelta(seconds=seconds)).isoformat()
            row = db.execute(
                "SELECT * FROM segments WHERE timing_uncertain=0 AND julianday(recorded_at)<=julianday(?) AND julianday(ended_at)>=julianday(?)",
                (stamp, stamp),
            ).fetchone()
            if row and (source / row["path"]).exists():
                image = frame_image(
                    source / row["path"],
                    (aware_time(stamp) - aware_time(row["recorded_at"])).total_seconds(),
                )
                frames.append({"image": image, "captured_at": stamp})
    return frames


def main():
    parser = argparse.ArgumentParser()
    for name in ("source", "turn", "before", "query", "output"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--lookup-turn")
    parser.add_argument(
        "--reference-turn",
        help="Synthetic shown-object lookup using the recorded visual window of this turn",
    )
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
    frames = visual_window(source, original["at"])
    lookup = None
    if args.lookup_turn:
        with sqlite3.connect(f"file:{source / 'conversations.sqlite3'}?mode=ro", uri=True) as db:
            db.row_factory = sqlite3.Row
            lookup = dict(
                db.execute("SELECT * FROM turns WHERE id=?", (args.lookup_turn,)).fetchone()
            )
        lookup_frames = visual_window(source, lookup["at"])
    if args.reference_turn:
        with sqlite3.connect(f"file:{source / 'conversations.sqlite3'}?mode=ro", uri=True) as db:
            stamp = db.execute(
                "SELECT at FROM turns WHERE id=?", (args.reference_turn,)
            ).fetchone()[0]
        lookup = {"transcript": "Where did I keep this before?", "at": args.before}
        lookup_frames = visual_window(source, stamp)
    client = OpenRouter()
    encoder, verifier = CloudEncoder(client=client), CloudVerifier(client=client)
    report = {
        "original_turn": args.turn,
        "synthetic_lookup_reference_turn": args.reference_turn,
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
            turn, verifier, encoder, image, snapshot_at, frames=frames
        )
        for _ in range(30):
            conversations.begin("Unrelated synthetic conversation", {})
        conversations = Conversations(root)
        assert turn not in [r["id"] for r in conversations.recent()]
        report["recent_context_empty"] = True

        selected_reference = None

        def tool(action):
            nonlocal selected_reference
            if action["action"] == "identify_shown_object" and lookup:
                from nyx.reference import resolve_reference

                reference = resolve_reference(verifier, lookup["transcript"], lookup_frames)
                report["lookup_reference"] = reference
                if reference["status"] == "resolved" and reference["source"] == "visual":
                    selected_reference = lookup_frames[reference["frame_index"]]["image"]
                return {
                    "kind": "reference",
                    "status": "complete" if reference["status"] == "resolved" else "clarify",
                    "answer": json.dumps(reference),
                }
            if action["action"] == "search_statements":
                return Statements(conversations).recall(
                    action["query"], encoder, verifier, reference_image=selected_reference
                )
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
                        reference_image=selected_reference,
                    )
                )
                result["answer"] = spoken_answer(result, now=aware_time(args.before))
                return result
            raise ValueError("Replay supports saved visual and statement retrieval only")

        report["agent"] = consume(
            agent_steps(
                lookup["transcript"] if lookup else "Where is my " + args.query + "?",
                [],
                verifier.decide,
                tool,
                available={"current_view": bool(lookup), "history": True, "dated_history": True},
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
