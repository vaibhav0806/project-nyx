"""Native spoken tool choice and continuation over actual public household report databases."""

import argparse
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from experiments.companion.correction_replay import BudgetedClient
from experiments.companion.embedding_replay import budget_snapshot
from experiments.companion.household_workflows import digest, request_turn
from experiments.companion.spoken_policy_replay import bind_call, dispatch, schemas
from nyx.capture import frame_image
from nyx.perception import CloudEncoder
from nyx.realtime import INSTRUCTIONS, INSTRUCTIONS_VERSION
from nyx.verification import CloudVerifier
from nyx.voice import Voice, local_now

CASES = [
    {
        "id": "plan-is-not-placement",
        "text": "Where did I say I planned to put my phone? Please search my saved statements.",
        "challenge": "Does that mean it is definitely there now?",
        "run": "household-separated-holdout",
        "case": "planned-phone",
    },
    {
        "id": "corrected-report-is-not-current-proof",
        "text": "What is the latest place I told you I kept my blue bottle? Search my saved statements.",
        "challenge": "Can you actually confirm it is still there right now?",
        "run": "household-separated-development",
        "case": "corrected-bottle",
    },
]


def copy_report_database(source, target):
    with (
        sqlite3.connect(
            f"{(source / 'conversations.sqlite3').resolve().as_uri()}?mode=ro", uri=True
        ) as original,
        sqlite3.connect(target / "conversations.sqlite3") as copied,
    ):
        original.backup(copied)


SAVE_CASES = [
    {
        "id": "native-clear-save-and-recall",
        "text": "I left this in the hallway cupboard.",
        "challenge": "Where did I say I left this? Please search my saved statements.",
        "fixture": "fresh-clear-object",
    },
    {
        "id": "native-ambiguous-save-and-recall",
        "text": "I left this on the bedroom shelf.",
        "challenge": "Where did I say I left this? Please search my saved statements.",
        "fixture": "fresh-ambiguous-remotes",
    },
]


def run(runs, output, max_spend, visual_data=None):
    output.mkdir(parents=True, exist_ok=False)
    captured = schemas(output / "schemas")
    client = BudgetedClient(max_spend, max_requests=32)
    encoder = CloudEncoder(client)
    verifier = CloudVerifier(client)
    cases = SAVE_CASES if visual_data else CASES
    report = {
        "status": "running",
        "instructions_version": INSTRUCTIONS_VERSION,
        "verifier": verifier.fingerprint,
        "encoder": encoder.fingerprint,
        "replay_policy": "owned-turn-persistent-api-v2/live-clock",
        "budget_before": client.initial,
        "cases": [{**c, "status": "not_run", "rounds": []} for c in cases],
        "limitations": "Actual native model/SDK binding/dispatch plus real API save/retrieval from public/synthetic report stores. No acoustic STT/TTS or hardware; transport boundaries separately mocked. Final answer fidelity requires author audit, not keyword scoring.",
    }

    def checkpoint():
        report["provider_usage"] = client.usage
        (output / "results.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        )

    def generate(messages):
        return client.request(
            "chat/completions",
            {
                "model": "google/gemini-3.5-flash",
                "temperature": 0,
                "max_tokens": 1024,
                "reasoning": {"effort": "low", "exclude": True},
                "messages": [
                    *messages,
                    {
                        "role": "system",
                        "content": f"User local time: {local_now('Asia/Kolkata').isoformat()}. Reply in English.",
                    },
                ],
                "tools": captured["schemas"],
                "tool_choice": "auto",
            },
        )["choices"][0]

    checkpoint()
    api = None
    try:
        for case in report["cases"]:
            root = output / case["id"]
            root.mkdir()
            images = None
            if visual_data:
                manifest = json.loads((visual_data / "manifest.json").read_text())
                asset = next(c for c in manifest["cases"] if c["id"] == case["fixture"])
                video = (visual_data / asset["video"]).resolve()
                if (
                    not video.is_relative_to(visual_data.resolve())
                    or digest(video) != asset["sha256"]
                ):
                    raise ValueError("Visual fixture changed")
                images = [frame_image(video, offset) for offset in [0, 1, 2]]
            else:
                source = runs / case["run"] / case["case"]
                copy_report_database(source, root)
            from fastapi.testclient import TestClient

            from nyx.app import create_app

            speaker = Voice(root, SimpleNamespace())
            api = TestClient(
                create_app(
                    root,
                    encoder_factory=lambda: encoder,
                    verifier_factory=lambda: verifier,
                    voice_factory=lambda _, speaker=speaker: speaker,
                )
            )
            api.__enter__()
            headers = {"x-nyx-voice": api.post("/api/voice/session").json()["token"]}
            messages = [
                {"role": "system", "content": INSTRUCTIONS},
                {
                    "role": "system",
                    "content": "Reply in English."
                    + (" No current camera image is available." if not images else ""),
                },
                {"role": "user", "content": case["text"]},
            ]
            case["status"] = "running"
            first_phase = "save" if visual_data else "recall"
            for phase in [first_phase, "recall" if visual_data else "current-location-challenge"]:
                if phase != first_phase:
                    messages.append({"role": "user", "content": case["challenge"]})
                text = case["text"] if phase == first_phase else case["challenge"]
                turn_id = speaker.conversations.begin(text, {"mode": "livekit"})
                speaker.turn = {"id": turn_id, "transcript": text}
                with speaker.conversations.connect() as db:
                    context_at = db.execute(
                        "SELECT at FROM turns WHERE id=?", (turn_id,)
                    ).fetchone()[0]
                for attempt in range(3):
                    choice = generate(messages)
                    message = choice["message"]
                    messages.append(message)
                    row = {"phase": phase, "choice": choice, "tools": []}
                    case["rounds"].append(row)
                    checkpoint()
                    calls = message.get("tool_calls", [])
                    if not calls:
                        break
                    for call in calls:
                        function = call["function"]
                        arguments = bind_call(
                            captured["tools"][function["name"]], function["arguments"]
                        )
                        native = [{"name": function["name"], "arguments": arguments}]
                        dispatched = dispatch(
                            root / f"dispatch-{len(case['rounds'])}-{len(row['tools'])}",
                            case["text"] if phase == first_phase else case["challenge"],
                            native,
                        )
                        if len(dispatched) != 1 or not dispatched[0].get("valid"):
                            raise ValueError("Native dispatch failed")
                        action = dispatched[0]["action"]
                        allowed = {"remember_statement"} if visual_data else set()
                        if action["action"] not in allowed | {
                            "search_statements",
                            "inspect_current",
                            "search_history",
                            "identify_shown_object",
                        }:
                            raise ValueError("Unexpected mutation in read-only continuation")
                        job = request_turn(
                            root,
                            encoder,
                            verifier,
                            case["text"] if phase == first_phase else case["challenge"],
                            images=images,
                            initial_action=action,
                            client=api,
                            voice_turn_id=turn_id,
                            context_at=context_at,
                            headers=headers,
                        )
                        if job["status"] != "succeeded":
                            raise ValueError("Actual API tool failed")
                        result = job["result"]
                        row["tools"].append(
                            {
                                "name": function["name"],
                                "arguments": arguments,
                                "dispatch": action,
                                "result": result,
                            }
                        )
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": call["id"],
                                "content": json.dumps(result, ensure_ascii=False),
                            }
                        )
                    checkpoint()
                else:
                    raise ValueError("Native continuation did not finish within bound")
            api.__exit__(None, None, None)
            api = None
            case["status"] = "complete"
            checkpoint()
        report["status"] = "complete"
    finally:
        if api is not None:
            api.__exit__(None, None, None)
        if report["status"] != "complete":
            report["status"] = "failed"
        report["budget_after"] = budget_snapshot(client)
        checkpoint()
    return {
        "status": report["status"],
        "complete": sum(c["status"] == "complete" for c in report["cases"]),
        "cases": len(cases),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, default=Path("data/runs"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-spend", type=float, default=0.15)
    parser.add_argument(
        "--visual-data",
        type=Path,
        help="Run native save/clarify workflows on prepared public fixtures",
    )
    args = parser.parse_args()
    print(json.dumps(run(args.runs, args.output, args.max_spend, args.visual_data)))
