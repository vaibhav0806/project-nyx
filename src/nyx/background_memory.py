"""Application-owned, ordered memory work; spoken reply cancellation does not cancel input."""

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock


class BackgroundMemory:
    def __init__(self, workspace):
        self.workspace = workspace
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="nyx-memory")
        self.lock = Lock()
        self.pending = {}

    def submit(self, turn_id, frames):
        with self.lock:
            if turn_id in self.pending:
                return self.pending[turn_id]
            if sum(not task.done() for task in self.pending.values()) >= 32:
                raise ValueError(
                    "Memory processing is busy; this input remains in conversation history"
                )
            for identifier, task in list(self.pending.items()):
                if len(self.pending) < 64:
                    break
                if task.done():
                    del self.pending[identifier]
            task = self.executor.submit(self._process, turn_id, frames)
            self.pending[turn_id] = task
            return task

    def _process(self, turn_id, frames):
        from nyx.reference import resolve_reference

        conversations = self.workspace.conversations
        started = time.perf_counter()
        conversations.event("background_memory_started", turn_id=turn_id)

        def available():
            return conversations.source_availability([turn_id], input_only=True).get(turn_id, False)

        def observe():
            if not available():
                raise ValueError("User input is unavailable")
            with conversations.connect() as db:
                transcript = db.execute(
                    "SELECT transcript FROM turns WHERE id=?", (turn_id,)
                ).fetchone()[0]
            result = resolve_reference(self.workspace.visual_verifier(), transcript, frames)
            if result.get("status") == "resolved":
                result["image"] = frames[result["frame_index"]]["image"]
            return result

        try:
            result = self.workspace.personal_memory().process(
                turn_id, observe=observe if frames else None, active=available
            )
            conversations.event(
                "background_memory_completed",
                turn_id=turn_id,
                status=result["status"],
                elapsed_ms=round((time.perf_counter() - started) * 1000),
            )
            return result
        except Exception as error:
            conversations.event(
                "background_memory_failed",
                turn_id=turn_id,
                error_type=type(error).__name__,
                elapsed_ms=round((time.perf_counter() - started) * 1000),
            )
            raise

    def status(self, turn_id):
        with self.lock:
            task = self.pending.get(turn_id)
        if task is None:
            return {"status": "unavailable"}
        if not task.done():
            return {"status": "pending"}
        if task.exception() is not None:
            return {"status": "failed"}
        return {"status": task.result()["status"]}

    def wait(self, turn_id, *, timeout=90):
        """A recall barrier through this input, without blocking ordinary conversation."""
        with self.lock:
            tasks = list(self.pending.items())
            boundary = next(
                (i + 1 for i, (key, _) in enumerate(tasks) if key == turn_id), len(tasks)
            )
            tasks = tasks[:boundary]
        deadline = time.monotonic() + timeout
        failed = []
        for identifier, task in tasks:
            try:
                task.result(timeout=max(0, deadline - time.monotonic()))
            except TimeoutError:
                raise
            except Exception:  # noqa: BLE001 — report failed jobs without stopping following inputs
                failed.append(identifier)
        return failed

    def close(self):
        self.executor.shutdown(wait=True)
