"""Public fixture + synthetic speech: durable pronoun recall and Flash final answer."""

import json
import tempfile
import time
from pathlib import Path

from PIL import Image

from nyx.cloud import OpenRouter
from nyx.perception import CloudEncoder
from nyx.realtime import INSTRUCTIONS
from nyx.statements import Statements
from nyx.verification import CloudVerifier
from nyx.voice import Conversations


def main():
    with tempfile.TemporaryDirectory() as directory:
        conversations = Conversations(directory)
        turn = conversations.begin("I'm going to keep this in the kitchen.", {})
        client = OpenRouter()
        verifier, encoder = CloudVerifier(client=client), CloudEncoder(client=client)
        saved = Statements(conversations).remember(
            turn,
            verifier,
            encoder,
            Image.open("data/runs/companion-retrieval-fixture/input_frames/007.png"),
            "2026-10-31T16:00:00Z",
        )
        for _ in range(30):
            conversations.begin("Unrelated synthetic conversation", {})
        conversations = Conversations(directory)
        assert turn not in [row["id"] for row in conversations.recent()]
        result = Statements(conversations).recall("remote control", encoder, verifier)
        assert result["matches"] and result["matches"][0]["turn_id"] == turn, result
        started = time.perf_counter()
        parts, first = [], None
        for part in client.stream_text(
            [
                {
                    "role": "system",
                    "content": INSTRUCTIONS
                    + " All required tools have completed. Answer now using only the supplied checked evidence. Do not call tools. At most two sentences.",
                },
                {"role": "user", "content": "Where is my remote?"},
                {
                    "role": "system",
                    "content": "Synthetic checked tool evidence: a remote was seen in your hand in a past recording. Saved statement search: "
                    + json.dumps(result),
                },
            ],
            "google/gemini-3.5-flash",
        ):
            if first is None:
                first = round((time.perf_counter() - started) * 1000)
            parts.append(part)
        report = {
            "saved": saved,
            "recall": result,
            "final_answer": "".join(parts),
            "final_first_token_ms": first,
            "usage": client.usage,
        }
        target = Path("data/runs/voice-routing/durable-recall.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2))
        print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
