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
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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
    if kind == "snapshot":
        if result.get("status") == "seen":
            return f"I can see {query} {result['judgment'].get('location') or 'in this view'}."
        return f"I can't clearly see {query} in this view."
    if kind == "history":
        evidence = result.get("evidence")
        if evidence:
            when = evidence.get("observed_at")
            when = (
                datetime.fromisoformat(when).astimezone().strftime("%I:%M %p on %d %B")
                if when
                else f"{evidence['offset_seconds']:.0f} seconds into a clip with an unknown recording time"
            )
            location = evidence["judgment"].get("location") or "in the recording"
            return f"The latest sighting I found was {query} {location}, at {when}. I can't confirm it's still there."
        return f"I couldn't confirm {query} in the moments I checked. Other footage may still contain it."
    return result["answer"]


class WakeRecognizer:
    def __init__(self):
        from faster_whisper import WhisperModel
        from huggingface_hub import snapshot_download

        path = snapshot_download(WAKE_MODEL, revision=WAKE_REVISION, local_files_only=True)
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


class Sarvam:
    def __init__(self, key, transport=urlopen):
        self.key = key
        self.transport = transport
        self.audio_cache = {}

    def request(self, path, body, content_type="application/json"):
        request = Request(
            "https://api.sarvam.ai/" + path,
            data=body,
            headers={
                "api-subscription-key": self.key,
                "content-type": content_type,
            },
        )
        try:
            with self.transport(request, timeout=40) as response:
                raw = response.read(8 * 1024**2 + 1)
                if len(raw) > 8 * 1024**2:
                    raise VoiceError("Sarvam response was too large. Try a shorter question.")
                return json.loads(raw)
        except HTTPError as exc:
            raise VoiceError(
                f"Sarvam request failed ({exc.code}). Check the key, credits or provider status."
            ) from None
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            if isinstance(exc, VoiceError):
                raise
            raise VoiceError(
                "Sarvam could not complete the request. Check the connection and retry."
            ) from None

    def transcribe(self, pcm):
        wav = BytesIO()
        with wave.open(wav, "wb") as file:
            file.setnchannels(1)
            file.setsampwidth(2)
            file.setframerate(16000)
            file.writeframes(pcm)
        boundary = uuid.uuid4().hex
        parts = []
        for key, value in {
            "model": "saaras:v4",
            "keyterms": json.dumps(["Nyx"]),
            "language_code": "unknown",
        }.items():
            parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
            )
        parts += [
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="question.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode(),
            wav.getvalue(),
            f"\r\n--{boundary}--\r\n".encode(),
        ]
        result = self.request(
            "speech-to-text", b"".join(parts), f"multipart/form-data; boundary={boundary}"
        )
        text = result.get("transcript")
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 1500:
            raise VoiceError("I could not hear a question. Say Hey Nyx and try again.")
        return text.strip()

    def route(self, transcript, context):
        schema = {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["current", "latest", "relevance", "clarify", "chat", "agent"],
                },
                "object_query": {"type": "string"},
                "reply": {"type": "string"},
                "seen_after": {"type": "string"},
                "seen_before": {"type": "string"},
            },
            "required": ["mode", "object_query", "seen_after", "seen_before", "reply"],
            "additionalProperties": False,
        }
        prompt = (
            "You are Nyx, a friendly, concise voice companion. Decide intent first. "
            "chat = greetings, small talk and ordinary conversation: reply naturally in at most two short sentences. "
            "Never send a greeting such as what's up or how are you to the camera as an object. "
            "current = find a concrete object in the current view. latest = last seen in recorded history. "
            "relevance = best matching past moments. clarify = ambiguous object/time or unsupported action. "
            "For visual modes, reply MUST be an empty string; a local visual tool supplies all observations. "
            "For chat/clarify, object_query and time bounds MUST be empty strings. "
            "No unsupported claims about seeing, hearing, remembering, people or the room in chat replies. "
            "agent = requests to remind on departure, list/cancel departure reminders, or refine an ongoing search. "
            "For agent, reply/object_query/time bounds are empty strings; the local agent chooses tools. "
            "Time-based reminders and general saved-fact recall are not available yet. "
            "For clarify, ask one brief useful question. Don't invent an object. "
            "Object descriptions are in English. Resolve them using prior object queries only. "
            "Dates must be explicit aware ISO times or empty strings; clarify ambiguous dates. "
            "Do not inherit date bounds unless requested. Wake name may be transcribed Nix or Nick. "
            'Examples: Where are my glasses? -> mode=current, object_query=glasses, reply="". '
            'Where did you last see them? (prior object glasses) -> mode=latest, object_query=glasses, reply="". '
            'What is up? -> mode=chat, object_query="", reply="Hey! What can I help with?". '
            'I feel tired today -> mode=chat, object_query="", reply="Want to talk about your day?". '
            "All unspecified time bounds are empty strings."
        )
        payload = {
            "model": "sarvam-105b",
            "messages": [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": json.dumps({"prior_questions": context, "question": transcript}),
                },
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "inspect",
                        "description": "Choose conversation, a visual lookup or a useful clarification",
                        "parameters": schema,
                    },
                }
            ],
            "tool_choice": {"type": "function", "function": {"name": "inspect"}},
            "reasoning_effort": None,
            "max_tokens": 350,
            "temperature": 0,
        }
        result = self.request("v1/chat/completions", json.dumps(payload).encode())
        try:
            calls = result["choices"][0]["message"]["tool_calls"]
            if len(calls) != 1 or calls[0]["function"]["name"] != "inspect":
                raise ValueError
            plan = json.loads(calls[0]["function"]["arguments"])
            for field in ["object_query", "reply", "seen_after", "seen_before"]:
                if plan.get(field) == "":
                    plan[field] = None
            return validate_plan(plan)
        except (KeyError, TypeError, IndexError, ValueError):
            raise VoiceError(
                "Please name an object and ask about the current view or its last sighting."
            ) from None

    def speak(self, text):
        if text in self.audio_cache:
            return self.audio_cache[text]
        payload = {
            "text": text[:2200],
            "language_code": "en-IN",
            "model": "bulbul:v4-flash",
            "speaker": "shubh_enhi_companion",
            "speech_sample_rate": 16000,
            "output_audio_codec": "wav",
        }
        result = self.request("text-to-speech", json.dumps(payload).encode())
        try:
            audio = result["audios"][0]
            raw = base64.b64decode(audio, validate=True)
            if len(raw) > 4 * 1024**2 or not raw.startswith(b"RIFF"):
                raise ValueError
            self.audio_cache[text] = audio
            if len(self.audio_cache) > 16:
                self.audio_cache.pop(next(iter(self.audio_cache)))
            return audio
        except (KeyError, IndexError, TypeError, ValueError):
            raise VoiceError(
                "Speech playback was unavailable. The answer is still shown on screen."
            ) from None


class Conversations:
    def __init__(self, root):
        self.path = Path(root) / "conversations.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS turns
                (id TEXT PRIMARY KEY, at TEXT, transcript TEXT, plan TEXT, answer TEXT,
                sources TEXT, sources_available INTEGER DEFAULT 1, status TEXT)""")
            db.execute("UPDATE turns SET status='interrupted' WHERE status='pending'")

    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def begin(self, transcript, plan):
        identifier = uuid.uuid4().hex
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
            self._cancel()
            self.token = uuid.uuid4().hex
            self.expires = time.monotonic() + 30
            return {"token": self.token}

    def heartbeat(self, token):
        with self.lock:
            self.check(token)
        return {"state": "listening"}

    def _cancel(self):
        self.epoch += 1
        self.awake_until = 0
        self.probed = False
        if self.turn:
            self.conversations.finish(self.turn["id"], status="interrupted")
        self.turn = None

    def cancel(self, token):
        with self.lock:
            self.check(token)
            self._cancel()

    def stop(self, token):
        with self.lock:
            self.check(token)
            self._cancel()
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

    def utterance(self, token, pcm):
        if not 6400 <= len(pcm) <= MAX_PCM or len(pcm) % 2:
            raise VoiceError("Use a spoken question between 0.2 and 25 seconds.")
        if not self.gate.acquire(blocking=False):
            raise VoiceError("Still processing speech. Wait and try again.")
        try:
            with self.lock:
                self.check(token)
                epoch = self.epoch
                if self.turn:
                    raise VoiceError("Wait for the answer or stop the response first.")
                awake = time.monotonic() < self.awake_until
            samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768
            timings = {}
            started = time.perf_counter()
            if np.sqrt(np.mean(samples**2)) < 0.001:
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
                    self.awake_until = time.monotonic() + 10
                    return {"state": "activated"}
                if command is None and not awake:
                    return {"state": "listening"}
                self.awake_until = 0
            started = time.perf_counter()
            transcript = self.provider.transcribe(pcm)
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
                identifier = self.conversations.begin(transcript, plan)
                self.turn = {
                    "id": identifier,
                    "at": datetime.now(UTC).isoformat(),
                    "transcript": transcript,
                    "plan": plan,
                    "timings": timings,
                }
                return {"state": "question", **self.turn}
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
            audio = self.provider.speak(answer)
        except VoiceError as exc:
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
