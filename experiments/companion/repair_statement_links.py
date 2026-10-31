"""Explicitly authorized repair from saved video; archives old links, retains originals.

Pass --source and one or more --turn IDs. Calls cloud models on selected saved media.
"""

import argparse
import json
from pathlib import Path

from saved_statement_replay import visual_window

from nyx.cloud import OpenRouter
from nyx.perception import CloudEncoder
from nyx.statements import Statements
from nyx.verification import CloudVerifier
from nyx.voice import Conversations


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--turn", action="append", required=True)
    args = parser.parse_args()
    conversations = Conversations(args.source, recover_pending=False)
    client = OpenRouter()
    verifier, encoder = CloudVerifier(client=client), CloudEncoder(client=client)
    store = Statements(conversations)
    for identifier in args.turn:
        with conversations.connect() as db:
            row = db.execute("SELECT at FROM turns WHERE id=?", (identifier,)).fetchone()
            saved = db.execute(
                "SELECT resolver FROM statements WHERE turn_id=?", (identifier,)
            ).fetchone()
        if not row or not saved:
            raise ValueError("Repair requires an existing transcript and saved link")
        if json.loads(saved["resolver"] or "{}").get("reference_version") == 2:
            print(json.dumps({"turn_id": identifier, "status": "already_verified"}))
            continue
        frames = visual_window(args.source, row["at"])
        result = store.remember(identifier, verifier, encoder, frames=frames, repair=True)
        print(json.dumps({"turn_id": identifier, "result": result}), flush=True)


if __name__ == "__main__":
    main()
