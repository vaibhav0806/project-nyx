import base64
import json
import re
import sqlite3
import time
import traceback
import uuid
import wave
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from threading import Lock

import numpy as np

WAKE_MODEL = "Systran/faster-whisper-tiny.en"
WAKE_REVISION = "0d3d19a32d3338f10357c0889762bd8d64bbdeba"
MAX_PCM = 16000 * 2 * 25


class VoiceError(ValueError):
    pass


def wake_command(text):
    match = re.match(
        r"^\s*(?:(?:hey|hi|okay)[\s,]+(?:nyx|nix|nicks|nick)|(?:nyx|nix|nicks))\b[\s,.!?:;-]*(.*)$",
        text,
        re.IGNORECASE,
    )
    return match.group(1).strip() if match else None


def conversational_plan(text):
    text = wake_command(text) if wake_command(text) is not None else text
    text = re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()
    text = " ".join(text.split())
    replies = {
        "hi": "Hey! What's on your mind?",
        "hey": "Hey! What's on your mind?",
        "hello": "Hey! What's on your mind?",
        "whats up": "Hey! I'm here. What can I help with?",
        "what is up": "Hey! I'm here. What can I help with?",
        "how are you": "I'm here and ready to help. How are you doing?",
        "how are you doing": "I'm here and ready to help. How are you doing?",
        "thanks": "You're welcome!",
        "thank you": "You're welcome!",
        "what can you do": "You can ask me about what's in view, or where I last saw an object.",
    }
    if text in replies:
        return {
            "mode": "chat",
            "reply": replies[text],
            "object_query": None,
            "seen_after": None,
            "seen_before": None,
        }
    return None


def spoken_answer(result):
    kind = result.get("kind")
    query = result.get("object_query", "that object")
    if result.get("status") == "confirmed":
        return result["answer"]
    if result.get("status") == "clarify":
        return "Which one do you mean? Please describe its color, position, or another distinguishing detail."
    if kind == "snapshot":
        if result.get("status") == "seen":
            return f"I can see {query} {result['judgment'].get('location') or 'in this view'}."
        return f"I can't clearly see {query} in this view."
    if kind == "history" and result.get("spoken_context"):
        return result["answer"]
    if kind == "history":
        evidence = result.get("evidence")
        if evidence:
            when = evidence.get("observed_at")
            when = (
                datetime.fromisoformat(when).astimezone().strftime("%I:%M %p on %d %B")
                if when
                else f"{evidence['offset_seconds']:.0f} seconds into a clip with an unknown recording time"
            )
            qualifier = (
                "A possible match I found was"
                if result.get("scope", {}).get("mode") == "relevance"
                else "The latest possible match I found was"
            )
            return f"{qualifier} in footage from {when}. Is this the item you mean? Please check the image; I have not verified its identity or current location."
        return f"I couldn't confirm {query} in the moments I checked. Other footage may still contain it."
    return result["answer"]


class WakeRecognizer:
    def __init__(self):
        from faster_whisper import WhisperModel
        from huggingface_hub import snapshot_download

        path = snapshot_download(
            WAKE_MODEL,
            revision=WAKE_REVISION,
            local_files_only=True,
            allow_patterns=["config.json", "model.bin", "tokenizer.json", "vocabulary.txt"],
        )
        self.model = WhisperModel(path, device="cpu", compute_type="int8", cpu_threads=2)

    def __call__(self, pcm):
        samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768
        segments, _ = self.model.transcribe(
            samples,
            language="en",
            beam_size=1,
            condition_on_previous_text=False,
            vad_filter=True,
            initial_prompt="Nyx. Hey Nyx.",
        )
        return " ".join(
            s.text.strip() for s in segments if s.no_speech_prob < 0.6 and s.avg_logprob > -1
        )


def validate_plan(plan):
    if not isinstance(plan, dict) or set(plan) - {
        "mode",
        "object_query",
        "seen_after",
        "seen_before",
        "reply",
    }:
        raise VoiceError(
            "Could not interpret that question. Please name an object and say now or last seen."
        )
    if plan.get("mode") not in {"current", "latest", "relevance", "clarify", "chat", "agent"}:
        raise VoiceError(
            "That request is outside the visual demo. Ask where an object is or was last seen."
        )
    if plan["mode"] in {"chat", "clarify"}:
        reply = plan.get("reply")
        if reply is not None and (not isinstance(reply, str) or not 1 <= len(reply.strip()) <= 350):
            raise VoiceError("Please try that again in a shorter sentence.")
        if plan["mode"] == "chat" and not reply:
            raise VoiceError("Could you say a little more?")
    elif plan.get("reply"):
        raise VoiceError("Visual questions must be answered from checked evidence.")
    if plan["mode"] in {"chat", "clarify"} and any(
        plan.get(key) is not None for key in ["object_query", "seen_after", "seen_before"]
    ):
        raise VoiceError("Conversation replies cannot contain visual lookup fields.")
    query = plan.get("object_query")
    if plan["mode"] not in {"clarify", "chat", "agent"} and (
        not isinstance(query, str) or not 1 <= len(query.strip()) <= 200
    ):
        raise VoiceError("Please name the object you want me to look for.")
    bounds = []
    for field in ["seen_after", "seen_before"]:
        value = plan.get(field)
        if value is not None:
            try:
                date = datetime.fromisoformat(value)
                if date.tzinfo is None:
                    raise ValueError
                plan[field] = date.astimezone(UTC).isoformat()
                bounds.append(date)
            except (ValueError, TypeError) as exc:
                raise VoiceError(
                    "Please clarify the date and time for that history question."
                ) from exc
    if len(bounds) == 2 and bounds[0] > bounds[1]:
        raise VoiceError("The start time must be before the end time.")
    if plan["mode"] == "current" and bounds:
        raise VoiceError("Use a history question to search a past time.")
    return plan


class CloudVoice:
    def __init__(self, client=None):
        import os

        from nyx.cloud import OpenRouter

        self.client = client or OpenRouter()
        self.stt_model = os.environ.get("NYX_STT_MODEL", "openai/gpt-4o-mini-transcribe")
        self.tts_model = "google/gemini-3.8-flash-lite-tts"
        self.audio_cache = {}

    def transcribe(self, pcm):
        wav = BytesIO()
        with wave.open(wav, "wb") as file:
            file.setnchannels(1)
            file.setsampwidth(2)
            file.setframerate(16000)
            file.writeframes(pcm)
        try:
            result = self.client.request(
                "audio/transcriptions",
                {
                    "model": self.stt_model,
                    "input_audio": {
                        "data": base64.b64encode(wav.getvalue()).decode(),
                        "format": "wav",
                    },
                },
            )
            text = result.get("text")
            if not isinstance(text, str) or not 1 <= len(text.strip()) <= 1500:
                raise ValueError("I could not hear a question. Say Hey Nyx and try again.")
            return text.strip()
        except ValueError as exc:
            raise VoiceError(str(exc)) from None

    def speak(self, text):
        if text in self.audio_cache:
            return self.audio_cache[text]
        try:
            pcm = self.client.request(
                "audio/speech",
                {
                    "model": self.tts_model,
                    "input": text[:2200],
                    "voice": "Kore",
                    "instructions": "Speak warmly and clearly.",
                    "response_format": "pcm",
                },
                binary=True,
            )
            if not pcm or len(pcm) % 2 or len(pcm) > 4 * 1024**2:
                raise ValueError(
                    "Speech response was invalid. The answer is still shown on screen."
                )
            wav = BytesIO()
            with wave.open(wav, "wb") as file:
                file.setnchannels(1)
                file.setsampwidth(2)
                file.setframerate(24000)
                file.writeframes(pcm)
            audio = base64.b64encode(wav.getvalue()).decode()
            self.audio_cache[text] = audio
            if len(self.audio_cache) > 16:
                self.audio_cache.pop(next(iter(self.audio_cache)))
            return audio
        except ValueError as exc:
            raise VoiceError(str(exc)) from None


class Conversations:
    def __init__(self, root):
        self.path = Path(root) / "conversations.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS turns
                (id TEXT PRIMARY KEY, at TEXT, transcript TEXT, plan TEXT, answer TEXT,
                sources TEXT, sources_available INTEGER DEFAULT 1, status TEXT)""")
            db.execute("UPDATE turns SET status='interrupted' WHERE status='pending'")
            db.execute("""CREATE TABLE IF NOT EXISTS diagnostics
                (id INTEGER PRIMARY KEY, at TEXT NOT NULL, event TEXT NOT NULL,
                 attempt_id TEXT, turn_id TEXT, details TEXT NOT NULL)""")

    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def event(self, event, *, attempt_id=None, turn_id=None, **details):
        """Bounded local diagnostics. Callers must never pass audio, tokens or idle text."""
        encoded = json.dumps(details, ensure_ascii=False)
        if len(encoded) > 32000:
            raise ValueError("Diagnostic event is too large")
        with self.connect() as db:
            db.execute(
                "INSERT INTO diagnostics(at,event,attempt_id,turn_id,details) VALUES (?,?,?,?,?)",
                (datetime.now(UTC).isoformat(), event, attempt_id, turn_id, encoded),
            )
            db.execute("DELETE FROM diagnostics WHERE id <= (SELECT MAX(id)-2000 FROM diagnostics)")

    def diagnostics(self, limit=100):
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM diagnostics ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [{**dict(row), "details": json.loads(row["details"])} for row in reversed(rows)]

    def begin(self, transcript, plan, identifier=None):
        identifier = identifier or uuid.uuid4().hex
        with self.connect() as db:
            db.execute(
                "INSERT INTO turns VALUES (?,?,?,?,?,?,?,?)",
                (
                    identifier,
                    datetime.now(UTC).isoformat(),
                    transcript,
                    json.dumps(plan),
                    None,
                    "[]",
                    1,
                    "pending",
                ),
            )
        return identifier

    def finish(self, identifier, answer=None, sources=(), status="complete"):
        with self.connect() as db:
            db.execute(
                "UPDATE turns SET answer=?, sources=?, status=? WHERE id=?",
                (answer, json.dumps(list(sources)), status, identifier),
            )

    def update_plan(self, identifier, plan):
        with self.connect() as db:
            db.execute("UPDATE turns SET plan=? WHERE id=?", (json.dumps(plan), identifier))

    def recent(self):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM turns ORDER BY rowid DESC LIMIT 20").fetchall()
        return [
            {
                **dict(row),
                "plan": json.loads(row["plan"]),
                "sources": json.loads(row["sources"]),
                "sources_available": bool(row["sources_available"]),
            }
            for row in reversed(rows)
        ]

    def invalidate(self, source):
        with self.connect() as db:
            db.execute(
                """UPDATE turns SET sources_available=0 WHERE id IN
                (SELECT turns.id FROM turns, json_each(turns.sources) WHERE json_each.value=?)""",
                (source,),
            )


class Voice:
    def __init__(self, root, provider, recognizer=None, *, agent_mode=False):
        self.provider = provider
        self.recognizer = recognizer
        self.agent_mode = agent_mode
        self.conversations = Conversations(root)
        self.lock = Lock()
        self.gate = Lock()
        self.token = None
        self.expires = 0
        self.awake_until = 0
        self.probed = False
        self.turn = None
        self.epoch = 0

    def check(self, token):
        if not token or token != self.token or time.monotonic() > self.expires:
            raise VoiceError("Voice session ended. Enable listening again.")
        self.expires = time.monotonic() + 30

    def start(self):
        with self.lock:
            if self.token and time.monotonic() < self.expires:
                raise VoiceError("Another tab is listening. Mute it before starting here.")
            self._cancel("session_started")
            self.conversations.event("voice_session_started")
            self.token = uuid.uuid4().hex
            self.expires = time.monotonic() + 30
            return {"token": self.token}

    def heartbeat(self, token):
        with self.lock:
            self.check(token)
        return {"state": "listening"}

    def _cancel(self, reason="internal"):
        self.conversations.event(
            "voice_cancelled",
            reason=reason,
            epoch=self.epoch,
            turn_id=self.turn["id"] if self.turn else None,
        )
        self.epoch += 1
        self.awake_until = 0
        self.probed = False
        if self.turn:
            self.conversations.event("turn_cancelled", turn_id=self.turn["id"])
            self.conversations.finish(self.turn["id"], status="interrupted")
        self.turn = None

    def cancel(self, token, reason="cancel_endpoint"):
        with self.lock:
            self.check(token)
            self._cancel(reason)

    def stop(self, token, reason="session_stopped"):
        with self.lock:
            self.check(token)
            self._cancel(reason)
            self.token = None

    def recognize(self, pcm):
        if self.recognizer is None:
            try:
                self.recognizer = WakeRecognizer()
            except (ImportError, OSError, RuntimeError):
                raise VoiceError(
                    "Local wake model unavailable. Install the voice extra and cache the pinned tiny.en checkpoint; see README."
                ) from None
        return self.recognizer(pcm)

    def probe(self, token, pcm):
        if not 6400 <= len(pcm) <= 96000 or len(pcm) % 2:
            raise VoiceError("Wake samples must be between 0.2 and 3 seconds.")
        if not self.gate.acquire(blocking=False):
            return {"state": "busy"}
        try:
            with self.lock:
                self.check(token)
                epoch = self.epoch
                if self.turn:
                    return {"state": "busy"}
                if time.monotonic() < self.awake_until:
                    return {"state": "activated"}
            if (
                np.sqrt(np.mean((np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768) ** 2))
                < 0.001
            ):
                return {"state": "listening"}
            command = wake_command(self.recognize(pcm))
            if command is not None:
                self.conversations.event(
                    "wake_detected", source="probe", duration_seconds=len(pcm) / 32000
                )
            with self.lock:
                self.check(token)
                if epoch != self.epoch:
                    raise VoiceError("Speech was cancelled.")
                if command is not None:
                    self.awake_until = time.monotonic() + 10
                    self.probed = True
                    return {"state": "activated"}
            return {"state": "listening"}
        finally:
            self.gate.release()

    def listen(self, token, identifier):
        with self.lock:
            self.check(token)
            rows = self.conversations.recent()
            if (
                self.turn
                or not rows
                or rows[-1]["id"] != identifier
                or rows[-1]["status"] != "complete"
            ):
                raise VoiceError("That conversation is no longer active.")
            self.awake_until = time.monotonic() + 10
            self.probed = False
        return {"state": "activated", "seconds": 10}

    def utterance(self, token, pcm, attempt_id=None):
        attempt_id = str(uuid.UUID(attempt_id)) if attempt_id else str(uuid.uuid4())
        identifier = None
        stage = "activation"
        if not 6400 <= len(pcm) <= MAX_PCM or len(pcm) % 2:
            raise VoiceError("Use a spoken question between 0.2 and 25 seconds.")
        if not self.gate.acquire(blocking=False):
            with self.lock:
                self.check(token)
            self.conversations.event("utterance_rejected", attempt_id=attempt_id, reason="busy")
            raise VoiceError("Still processing speech. Wait and try again.")
        try:
            with self.lock:
                self.check(token)
                epoch = self.epoch
                self.conversations.event(
                    "utterance_received", attempt_id=attempt_id, duration_seconds=len(pcm) / 32000
                )
                if self.turn:
                    raise VoiceError("Wait for the answer or stop the response first.")
                awake = time.monotonic() < self.awake_until
            samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768
            timings = {}
            started = time.perf_counter()
            if np.sqrt(np.mean(samples**2)) < 0.001:
                self.conversations.event(
                    "utterance_ignored", attempt_id=attempt_id, reason="silence"
                )
                return {"state": "listening"}
            recognize = not awake or self.probed
            local = self.recognize(pcm) if recognize else ""
            command = wake_command(local) if recognize else None
            self.probed = False
            timings["wake_ms"] = round((time.perf_counter() - started) * 1000)
            with self.lock:
                self.check(token)
                if epoch != self.epoch:
                    raise VoiceError("Speech was cancelled.")
                if command == "":
                    self.conversations.event("wake_only", attempt_id=attempt_id)
                    self.awake_until = time.monotonic() + 10
                    return {"state": "activated"}
                if command is None and not awake:
                    self.conversations.event(
                        "utterance_ignored", attempt_id=attempt_id, reason="wake_not_recognized"
                    )
                    return {"state": "listening", "reason": "wake_not_recognized"}
                activation_deadline = self.awake_until
                self.awake_until = 0
            started = time.perf_counter()
            stage = "transcription"
            self.conversations.event(
                "transcription_started",
                attempt_id=attempt_id,
                model=getattr(self.provider, "stt_model", type(self.provider).__name__),
                activation="wake" if command is not None else "followup",
            )
            transcript = self.provider.transcribe(pcm)
            identifier = self.conversations.begin(
                transcript, {"mode": "unresolved", "attempt_id": attempt_id}
            )
            self.conversations.event(
                "transcription_completed",
                attempt_id=attempt_id,
                turn_id=identifier,
                transcript=transcript,
                elapsed_ms=round((time.perf_counter() - started) * 1000),
            )
            timings["stt_ms"] = round((time.perf_counter() - started) * 1000)
            with self.lock:
                self.check(token)
                if epoch != self.epoch:
                    raise VoiceError("Speech was cancelled.")
            context = [
                {
                    "question": row["transcript"],
                    "object_query": row["plan"].get("object_query"),
                    **(
                        {"reply": row["answer"]}
                        if row["plan"]["mode"] in {"chat", "clarify"}
                        else {}
                    ),
                }
                for row in self.conversations.recent()[-4:]
                if row["status"] == "complete"
            ]
            started = time.perf_counter()
            stage = "routing"
            plan = validate_plan(
                conversational_plan(transcript)
                or (
                    {"mode": "agent"}
                    if self.agent_mode
                    else self.provider.route(transcript, context)
                )
            )
            timings["intent_ms"] = round((time.perf_counter() - started) * 1000)
            with self.lock:
                self.check(token)
                if epoch != self.epoch:
                    raise VoiceError("Speech was cancelled.")
                self.conversations.update_plan(identifier, plan)
                self.conversations.event(
                    "voice_turn_ready",
                    attempt_id=attempt_id,
                    turn_id=identifier,
                    plan=plan,
                    timings=timings,
                )
                self.turn = {
                    "id": identifier,
                    "at": datetime.now(UTC).isoformat(),
                    "transcript": transcript,
                    "plan": plan,
                    "timings": timings,
                }
                return {"state": "question", **self.turn}
        except Exception as exc:
            if stage == "transcription" and identifier is None:
                with self.lock:
                    if epoch == self.epoch:
                        self.awake_until = max(
                            self.awake_until, locals().get("activation_deadline", 0)
                        )
            self.conversations.event(
                "utterance_failed",
                attempt_id=attempt_id,
                turn_id=identifier,
                stage=stage,
                error_type=type(exc).__name__,
                failure_site=[
                    f"{frame.name}:{frame.lineno}"
                    for frame in traceback.extract_tb(exc.__traceback__)
                ][-8:],
            )
            if identifier:
                self.conversations.finish(identifier, status="interrupted")
            raise
        finally:
            self.gate.release()

    def reply(self, token, identifier, result):
        if not self.gate.acquire(blocking=False):
            raise VoiceError("A speech response is already being prepared.")
        try:
            return self._reply(token, identifier, result)
        finally:
            self.gate.release()

    def _reply(self, token, identifier, result):
        with self.lock:
            self.check(token)
            if not self.turn or self.turn["id"] != identifier:
                raise VoiceError("This response was cancelled or already completed.")
            epoch = self.epoch
            answer = spoken_answer(result)
            sources = [row["video_id"] for row in result.get("checked", [])]
        audio = None
        warning = None
        started = time.perf_counter()
        try:
            self.conversations.event(
                "speech_started",
                turn_id=identifier,
                model=getattr(self.provider, "tts_model", type(self.provider).__name__),
            )
            audio = self.provider.speak(answer)
            self.conversations.event(
                "speech_generated",
                turn_id=identifier,
                elapsed_ms=round((time.perf_counter() - started) * 1000),
            )
        except VoiceError as exc:
            self.conversations.event(
                "speech_failed", turn_id=identifier, error_type=type(exc).__name__
            )
            warning = str(exc)
        with self.lock:
            self.check(token)
            if epoch != self.epoch:
                raise VoiceError("This response was cancelled.")
            self.conversations.finish(identifier, answer, sources)
            self.turn = None
        return {
            "answer": answer,
            "audio": audio,
            "warning": warning,
            "timings": {"tts_ms": round((time.perf_counter() - started) * 1000)},
        }
