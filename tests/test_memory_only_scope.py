import hashlib
import sqlite3
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from test_companion import Planner, snapshot
from test_nyx import ColorEncoder

from nyx.agent_tools import tool_schemas
from nyx.app import create_app


def test_departure_tools_are_not_exposed_by_the_shared_agent():
    assert "departure_reminder" not in [row["function"]["name"] for row in tool_schemas()]


def test_departure_polling_is_inactive_without_deleting_existing_history(tmp_path):
    path = tmp_path / "intentions.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE preserved_history(content TEXT)")
        db.execute("INSERT INTO preserved_history VALUES ('Existing reminder data')")
    before = hashlib.sha256(path.read_bytes()).hexdigest()

    class NoObserver(Planner):
        def inspect_departure(self, *args, **kwargs):
            raise AssertionError("Retired departure feature called a model")

    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=NoObserver)
    ) as client:
        state = client.get("/api/companion").json()
        assert state["reminders"] == state["pending"] == []
        assert state["observation"]["state"] == "inactive"
        result = client.post(
            "/api/observe",
            json={
                "session_id": "old-session",
                "captured_at": datetime.now(UTC).isoformat(),
                "image": snapshot(),
            },
        )
        assert result.status_code == 200
        assert result.json()["state"] == "inactive"
        assert client.post("/api/deliveries/old-delivery/claim").status_code == 410
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
