import json
from types import SimpleNamespace

import pytest
from test_statement_corrections import Encoder, begin, verifier

from nyx.agent import validate_action
from nyx.statements import Statements
from nyx.voice import Conversations


def test_latest_report_chooses_newest_known_date_without_discarding_all_report_lookup(tmp_path):
    conversations = Conversations(tmp_path)
    statements = Statements(conversations)
    old = begin(conversations, "My phone is in the kitchen", "2026-11-06T12:00:00Z")
    new = begin(conversations, "I moved my phone to the bag", "2026-11-08T12:00:00Z")
    statements.remember(old, verifier(), Encoder())
    statements.remember(new, verifier("bag"), Encoder())
    model = SimpleNamespace(generate_json=lambda *a, **k: json.dumps({"statement_ids": [old, new]}))
    all_reports = statements.recall("phone", Encoder(), model)
    assert {row["turn_id"] for row in all_reports["matches"]} == {old, new}
    latest = statements.recall("phone", Encoder(), model, selection="latest_report")
    assert [row["turn_id"] for row in latest["matches"]] == [new]
    assert latest["sources"] == [f"transcript:{new}"]
    assert old not in latest["answer"] and "kitchen" not in latest["answer"]


@pytest.mark.parametrize("unknown", [True, False])
def test_latest_report_cannot_invent_order_for_unknown_or_tied_dates(tmp_path, unknown):
    conversations = Conversations(tmp_path)
    statements = Statements(conversations)
    a = begin(conversations, "My phone is in the kitchen", "2026-11-08T12:00:00Z")
    b = begin(conversations, "My phone is in the bag", "2026-11-08T12:00:00Z")
    statements.remember(a, verifier(), Encoder())
    statements.remember(b, verifier("bag"), Encoder())
    if unknown:
        with conversations.connect() as db:
            db.execute("UPDATE turns SET at=NULL WHERE id=?", (b,))
    model = SimpleNamespace(generate_json=lambda *a_, **k: json.dumps({"statement_ids": [a, b]}))
    result = statements.recall("phone", Encoder(), model, selection="latest_report")
    assert result["status"] == "clarify"
    assert len(result["matches"]) == 2


def test_latest_report_tool_intent_is_validated_separately_from_historical_cutoff():
    action = {
        "action": "search_statements",
        "query": "phone",
        "selection": "latest_report",
        "as_of": "2026-11-07T12:00:00Z",
    }
    assert validate_action(action) == action
    for invalid in ["guess", [], None]:
        with pytest.raises(ValueError):
            validate_action({**action, "selection": invalid})


def test_latest_report_selection_and_cutoff_reach_actual_api_storage(tmp_path):
    from fastapi.testclient import TestClient
    from test_app import wait_for_job

    from nyx.app import create_app

    conversations = Conversations(tmp_path)
    statements = Statements(conversations)
    old = begin(conversations, "My phone is in the kitchen", "2026-11-06T12:00:00Z")
    new = begin(conversations, "I moved my phone to the bag", "2026-11-08T12:00:00Z")
    statements.remember(old, verifier(), Encoder())
    statements.remember(new, verifier("bag"), Encoder())
    cited = [old, new]
    model = SimpleNamespace(
        generate_json=lambda *a, **k: json.dumps({"statement_ids": cited}),
        fingerprint={"model": "citation-fixture"},
    )
    with TestClient(
        create_app(tmp_path, encoder_factory=Encoder, verifier_factory=lambda: model)
    ) as client:
        for request_id, cutoff, expected in [
            ("current", None, new),
            ("historical", "2026-11-07T12:00:00Z", old),
        ]:
            action = {"action": "search_statements", "query": "phone", "selection": "latest_report"}
            if cutoff:
                action["as_of"] = cutoff
                cited = [old]
            response = client.post(
                "/api/agent",
                json={
                    "message": "Quote the latest report",
                    "request_id": request_id,
                    "initial_action": action,
                },
            )
            job = wait_for_job(client, response.json()["id"])
            assert job["status"] == "succeeded", job
            assert [row["turn_id"] for row in job["result"]["observations"][0]["matches"]] == [
                expected
            ]
