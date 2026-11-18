"""Application-owned, ordered memory work; spoken reply cancellation does not cancel input."""

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock


class BackgroundMemory:
    def __init__(self, workspace):
        self.workspace = workspace
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="nyx-memory")
        self.reader = ThreadPoolExecutor(max_workers=1, thread_name_prefix="nyx-memory-read")
        self.lock = Lock()
        self.pending = {}
        self.early = {}
        self.reading = None

    def prefetch(self, turn_id, query):
        """Read candidates independently of writes; never queue up slow semantic requests."""
        with self.lock:
            if turn_id in self.early:
                return self.early[turn_id]
            task = None
            if self.reading is None or self.reading.done():
                task = self.reader.submit(self._candidates, query)
                self.reading = task
            self.early[turn_id] = task
            while len(self.early) > 8:
                del self.early[next(iter(self.early))]
            return task

    def _candidates(self, query):
        return self.workspace.personal_memory().recall(query, limit=5, select=False, rank_all=False)

    def early_context(self, turn_id, *, as_of=None):
        """Only completed reads; recheck validity and corrections on each generation."""
        from nyx.personal_memory import PersonalMemory

        context = {
            "kind": "saved_user_memories",
            "status": "unavailable",
            "records": [],
            "sources": [],
        }
        with self.lock:
            task = self.early.get(turn_id)
        if task is None or task.cancelled():
            return context
        if not task.done():
            return {**context, "status": "pending"}
        if task.exception() is not None:
            return {**context, "status": "failed"}
        wanted = {row["id"] for row in task.result()["matches"]}
        if not wanted:
            return {**context, "status": "retrieved"}
        rows, _ = PersonalMemory._read_rows(
            self.workspace.conversations, as_of=as_of, identifiers=wanted
        )
        by_id = {row["id"]: row for row in rows}
        records = [
            {
                key: by_id[row["id"]][key]
                for key in ("id", "turn_id", "at", "kind", "content", "sources")
            }
            for row in task.result()["matches"]
            if row["id"] in by_id
        ]
        return {
            **context,
            "status": "retrieved",
            "records": records,
            "sources": sorted({source for row in records for source in row["sources"]}),
        }

    def turn_context(self, turn_id):
        """Background uncertainty is an internal outcome, not a delayed user question."""
        from nyx.personal_memory import PersonalMemory

        context = PersonalMemory.turn_context(self.workspace.conversations, turn_id)
        if context and context["status"] == "clarify":
            return {
                **context,
                "status": "unresolved",
                "answer": "No new memory saved: the input could not be resolved reliably.",
                "visual": {},
            }
        return context

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
        status = task.result()["status"]
        return {"status": "unresolved" if status == "clarify" else status}

    def wait(self, turn_id, *, timeout=90):
        """Explicit audit/test synchronization; ordinary memory reads never call this."""
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
        self.reader.shutdown(wait=True, cancel_futures=True)
        self.executor.shutdown(wait=True)
