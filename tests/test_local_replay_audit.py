import importlib.util
import shutil
from pathlib import Path

import pytest
from test_nyx import ColorEncoder

from nyx.memory import Store

pytest_plugins = ["test_nyx"]

spec = importlib.util.spec_from_file_location(
    "local_replay_audit",
    Path(__file__).resolve().parents[1] / "experiments/companion/local_replay_audit.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
digest, run = module.digest, module.run


@pytest.mark.parametrize("full_decode", [False, True])
def test_audit_uses_copy_and_preserves_original_database_and_media(tmp_path, video, full_decode):
    root = tmp_path / "library"
    store = Store(root, ColorEncoder.fingerprint, 3)
    source = root / "fixture.mp4"
    shutil.copyfile(video, source)
    identifier = store.add_video("synthetic", "fixture.mp4", None, 2)
    store.add_frames(identifier, [(0, "missing-thumbnail.jpg")], [[1, 0, 0]])
    store.finish_video(identifier)
    before = {path: digest(path) for path in [source, root / "index.sqlite3"]}
    result = run(root, tmp_path / "audit", full_decode=full_decode)
    assert result["full_video_decode"] is full_decode
    assert result["queries"][0]["hits"][0]["id"] == 1
    assert result["media"][0]["status"] == "readable"
    assert result["media"][0]["bytes_preserved"]
    assert result["context"]["invalidated_claim_withheld"]
    assert all(digest(path) == value for path, value in before.items())


def test_actual_memory_conversion_is_offline_lossless_and_only_touches_copy(tmp_path):
    import json

    from test_personal_memory import Encoder

    from nyx.voice import Conversations

    root = tmp_path / "private-library"
    conversations = Conversations(root)
    turn = conversations.begin("Private fixture statement", {})
    with conversations.connect() as db:
        db.execute(
            "CREATE TABLE statements(turn_id TEXT PRIMARY KEY, object_description TEXT, kind TEXT, captured_at TEXT, image BLOB, embedding BLOB, encoder TEXT, resolver TEXT)"
        )
        db.execute(
            "INSERT INTO statements VALUES (?,?,?,?,?,?,?,?)",
            (
                turn,
                "object",
                "reported_placement",
                None,
                b"private-photo",
                Encoder().encode_text("").tobytes(),
                json.dumps(Encoder.fingerprint),
                "{}",
            ),
        )
    before = digest(root / "conversations.sqlite3")
    output = tmp_path / "audit"
    output.mkdir()
    result = module.memory_conversion(root, output)
    assert result == {
        "status": "complete",
        "original_statement_count": 1,
        "memory_count": 1,
        "vectors_and_photos_preserved": True,
        "legacy_rows_unchanged": True,
        "original_database_unchanged": True,
        "inference_requests": 0,
    }
    assert "private-photo" not in json.dumps(result) and "Private fixture" not in json.dumps(result)
    assert digest(root / "conversations.sqlite3") == before
