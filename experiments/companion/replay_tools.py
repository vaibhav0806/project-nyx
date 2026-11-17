"""Real native tool execution against an explicitly selected, local replay snapshot."""

from datetime import datetime, timedelta

from PIL import Image

from nyx.agent import _model_tool_result
from nyx.agent_tools import bind_tool_action
from nyx.answers import history_steps
from nyx.memory import Store
from nyx.perception import CloudEncoder
from nyx.personal_memory import PersonalMemory
from nyx.reference import resolve_reference
from nyx.verification import CloudVerifier
from nyx.voice import Conversations


class ReplayTools:
    def __init__(self, root, guard, evidence):
        self.root, self.evidence = root, evidence
        self.encoder = CloudEncoder(client=guard)
        self.verifier = CloudVerifier(client=guard)
        self.memory = PersonalMemory(Conversations(root), self.encoder, self.verifier.memory_reply)
        self.store = Store(root, self.encoder.fingerprint, self.encoder.dimensions)

    def execute(self, name, arguments):
        action = bind_tool_action(name, arguments)
        kind = action["action"]
        if kind == "recall_memory":
            return self.memory.recall(action["query"], as_of=action.get("as_of"), select=True)
        if kind in {"search_history", "search_matches"}:
            at = datetime.fromisoformat(self.evidence["replay_at"])
            hours = action.get("hours", 0)
            lower = (at - timedelta(hours=hours)).isoformat() if hours else None
            upper = at.isoformat()
            if action.get("before_frame_id") is not None:
                frame = next(
                    row
                    for row in self.store.frame_context(action["before_frame_id"])
                    if row["id"] == action["before_frame_id"]
                )
                upper = min(
                    at, datetime.fromisoformat(frame["observed_at"]) - timedelta(microseconds=1)
                ).isoformat()
            steps = history_steps(
                action["query"],
                self.store,
                self.encoder,
                lambda: self.verifier,
                seen_after=lower,
                seen_before=upper,
                mode="latest" if kind == "search_history" else "relevance",
                semantic_latest=kind == "search_history",
                excluded_frame_ids=action.get("excluded_frame_ids", []),
            )
            while True:
                try:
                    next(steps)
                except StopIteration as done:
                    return _model_tool_result(done.value)
        if kind == "inspect_current":
            row = self.evidence["endpoint_image"]
            with Image.open(self.root / row["path"]) as image:
                judgment = self.verifier.inspect(image.convert("RGB"), action["query"])
            return {
                "kind": "snapshot",
                "identity_verified": False,
                "judgment": judgment,
                "captured_at": row.get("captured_at") or row["at"],
                "scope": {
                    "note": "Historical replay of the selected endpoint frame; not a new live capture."
                },
            }
        if kind == "identify_shown_object":
            frames = []
            for key in ("shown_image", "endpoint_image"):
                row = self.evidence[key]
                with Image.open(self.root / row["path"]) as image:
                    frames.append(
                        {
                            "image": image.convert("RGB"),
                            "captured_at": row.get("captured_at") or row["at"],
                        }
                    )
            return resolve_reference(self.verifier, self.evidence["utterance"], frames)
        raise ValueError("Unsupported replay tool action")
