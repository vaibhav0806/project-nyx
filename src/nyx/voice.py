import base64
import json
import re
import sqlite3
import time
import uuid
import wave
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from threading import Lock
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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


def local_now(timezone=None):
    if not timezone:
        return datetime.now().astimezone()
    try:
        return datetime.now(ZoneInfo(timezone))
    except (ZoneInfoNotFoundError, ValueError):
        raise VoiceError(
            "Your timezone wasn't recognized. Refresh the page and try again."
        ) from None


def clock_reply(text, now):
    text = wake_command(text) if wake_command(text) is not None else text
    if re.fullmatch(
        r"(?:please[ ,]+)?(?:what(?:'s| is) the (?:current )?time|what time is it|tell me (?:the )?time)"
        r"(?:\s+(?:right now|now))?(?:[ ,]+(?:please|nyx|ma'am|mam))?[?.! ]*",
        text.strip(),
        re.IGNORECASE,
    ):
        return f"It's {now.strftime('%I:%M %p').lstrip('0').lower()}."
    return None


def relative_time(value, now=None):
    if not value:
        return None
    observed = datetime.fromisoformat(value)
    if observed.tzinfo is None:
        return None
    seconds = ((now or datetime.now(UTC)) - observed).total_seconds()
    if seconds < -60:
        return None
    if seconds < 90:
        return "just now"
    minutes = seconds / 60
    if minutes < 3:
        return "a couple of minutes ago"
    if minutes < 10:
        return "a few minutes ago"
    if minutes < 55:
        return f"about {int((minutes + 2.5) // 5) * 5} minutes ago"
    if minutes < 90:
        return "about an hour ago"
    hours = int((minutes + 30) // 60)
    if hours < 24:
        return f"about {hours} hours ago"
    days = max(1, int((hours + 12) // 24))
    return "about a day ago" if days == 1 else f"about {days} days ago"


def personal_wording(text):
    text = re.sub(r"\bthe (?:user|person)['’]s\b", "your", text, flags=re.IGNORECASE)
    return re.sub(r"\bthe (?:user|person)\b", "you", text, flags=re.IGNORECASE)


def spoken_location(location):
    if not location:
        return ""
    location = personal_wording(location)
    location = re.sub(
        r"\bthe ((?:right |left )?hands?)\b", r"your \1", location, flags=re.IGNORECASE
    )
    location = re.sub(
        r"\b(?:near|at|in|on|towards?)\s+(?:the\s+)?"
        r"(?:(?:upper|lower|top|bottom|left|right|middle|center|centre)\s*)+"
        r"(?:corner|side|part|portion)?\s+(?:of\s+)?(?:the\s+)?(?:image|frame|picture|photo|view)\b",
        "",
        location,
        flags=re.IGNORECASE,
    ).strip(" ,.;")
    if re.fullmatch(
        r"(?:(?:near|in|on|at|towards?) )?(?:the )?(?:center|centre|foreground|background|middle|top|bottom|left|right)",
        location,
        re.IGNORECASE,
    ):
        return ""
    return re.sub(r"^held\s+(?=in\b)", "", location, flags=re.IGNORECASE)


def spoken_answer(result, *, now=None):
    kind = result.get("kind")
    query = personal_wording(result.get("object_query", "that object"))
    if result.get("status") == "confirmed":
        return result["answer"]
    if result.get("status") == "clarify":
        return "Which one do you mean? What does it look like?"
    if kind == "snapshot":
        if result.get("status") == "seen":
            location = spoken_location(result["judgment"].get("location"))
            return f"I can see {query}{' ' + location if location else ''}."
        return f"I can't clearly see {query} in this view."
    if kind == "history":
        evidence = result.get("evidence")
        if evidence:
            when = relative_time(evidence.get("observed_at"), now)
            noun = (
                query
                if re.match(r"^(?:a|an|the|you|your|that|those|someone)\b", query, re.IGNORECASE)
                else f"your {query}"
            )
            location = spoken_location(evidence.get("judgment", {}).get("location"))
            if query.lower().startswith("you ") and location.lower() == "in front of you":
                location = ""
            place = f", {location.rstrip('.')}" if location else ""
            answer = (
                f"I think I saw {noun} {when}{place}."
                if when
                else (f"I think I saw {noun}{place}, but I don't know when that was.")
            )
            statements = result.get("spoken_context") or []
            if statements:
                answer += " " + " ".join(f"You said, “{row['text']}”" for row in statements)
            return answer
        return f"I haven't found {query} yet. I can look further back."
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


class CloudVoice:
    def __init__(self, client=None):
        import os

        from nyx.cloud import OpenRouter

        self.client = client or OpenRouter()
        self.tts_model = os.environ.get(
            "NYX_TTS_MODEL",
            "bulbul:v4-flash"
            if os.environ.get("SARVAM_API_KEY")
            else "google/gemini-3.8-flash-lite-tts",
        )
        self.speech_client = self.client
        if self.tts_model == "bulbul:v4-flash":
            from nyx.cloud import SarvamSpeech

            self.speech_client = SarvamSpeech()
        self.audio_cache = {}
        self.audio_lock = Lock()

    def speech_payload(self, text):
        if self.tts_model == "bulbul:v4-flash":
            return {
                "model": self.tts_model,
                "text": text[:2200],
                "speaker": "ritu_hi_conversation"
                if re.search(r"[\u0900-\u097f]", text)
                else "ritu_en_reels",
                "language_code": "hi-IN" if re.search(r"[\u0900-\u097f]", text) else "en-IN",
                "output_audio_codec": "linear16",
                "speech_sample_rate": 24000,
            }
        return {
            "model": self.tts_model,
            "input": text[:2200],
            "voice": "Kore",
            "instructions": "Speak warmly and clearly.",
            "response_format": "pcm",
        }

    def cache_speech(self, text, pcm):
        wav = BytesIO()
        with wave.open(wav, "wb") as file:
            file.setnchannels(1)
            file.setsampwidth(2)
            file.setframerate(24000)
            file.writeframes(pcm)
        audio = base64.b64encode(wav.getvalue()).decode()
        with self.audio_lock:
            self.audio_cache[text] = audio
            if len(self.audio_cache) > 16:
                self.audio_cache.pop(next(iter(self.audio_cache)))
        return audio

    def speak(self, text):
        cached = self.audio_cache.get(text)
        if cached:
            return cached
        try:
            if self.tts_model == "bulbul:v4-flash":
                pcm = b"".join(self.speech_client.stream_pcm(self.speech_payload(text)))
            else:
                pcm = self.client.request(
                    "audio/speech",
                    self.speech_payload(text),
                    binary=True,
                )
            if not pcm or len(pcm) % 2 or len(pcm) > 4 * 1024**2:
                raise ValueError(
                    "Speech response was invalid. The answer is still shown on screen."
                )
            return self.cache_speech(text, pcm)
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
        self.root = Path(root)
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
        if self.turn and not any(
            row["id"] == self.turn["id"] and row["status"] == "complete"
            for row in self.conversations.recent()
        ):
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
