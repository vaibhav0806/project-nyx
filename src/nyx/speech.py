"""Sentence-aware, bounded text-to-audio pipeline and reusable acknowledgement clips."""

import base64
import hashlib
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Thread

ACKNOWLEDGEMENTS = {
    "en": (
        "Let me check that for you.",
        "Let me take a look.",
        "One moment, I’ll check.",
        "I’ll look back for you.",
        "Let me see what I can find.",
        "Just a moment, I’m looking.",
    ),
    "hi": (
        "एक पल, मैं देखती हूँ।",
        "अभी देखकर बताती हूँ।",
        "ज़रा देखने दीजिए।",
        "एक मिनट, मैं ढूँढती हूँ।",
        "रुकिए, मैं देख लेती हूँ।",
        "मैं पिछली रिकॉर्डिंग देखती हूँ।",
    ),
}


def acknowledgement_path(root, model, text):
    voice = "shubh_enhi_companion" if model == "bulbul:v4-flash" else "Kore"
    key = hashlib.sha256(f"{model}/{voice}/24000/v1/{text}".encode()).hexdigest()[:24]
    return Path(root) / "voice-acknowledgements" / f"{key}.wav"


class SentenceBuffer:
    def __init__(self):
        self.pending = ""

    def feed(self, text):
        self.pending += text
        sentences = []
        while self.pending:
            boundary = None
            for match in re.finditer(r'[.!?।][”"\']?(?=\s)', self.pending):
                end = match.end()
                prefix = self.pending[:end]
                if match.group().startswith(".") and re.search(
                    r"\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|St|vs|etc|e\.g|i\.e|[A-Z])\.$", prefix
                ):
                    continue
                boundary = end
                break
            if boundary is None and len(self.pending) > 260:
                # A long clause without punctuation must not starve speech indefinitely.
                boundary = max(self.pending.rfind(c, 100, 240) for c in ",;，； ")
                if boundary < 0:
                    boundary = 240
            if boundary is None:
                break
            sentences.append(self.pending[:boundary].strip())
            self.pending = self.pending[boundary:].lstrip()
        return sentences

    def finish(self):
        tail, self.pending = self.pending.strip(), ""
        return [tail] if tail else []


def speech_events(tokens, synthesize, stopped):
    """Overlap token production with ordered sentence synthesis; apply backpressure."""
    sentences, events = Queue(3), Queue(16)

    def put(queue, value):
        while not stopped.is_set():
            try:
                queue.put(value, timeout=0.1)
                return True
            except Full:
                pass
        return False

    def produce():
        buffer = SentenceBuffer()
        total = 0
        try:
            for text in tokens:
                if stopped.is_set():
                    break
                total += len(text)
                if total > 2200:
                    raise ValueError("Spoken answer exceeded its limit.")
                put(events, {"type": "text", "text": text})
                for sentence in buffer.feed(text):
                    put(sentences, sentence)
            if not stopped.is_set():
                for sentence in buffer.finish():
                    put(sentences, sentence)
                put(sentences, None)
        except Exception:  # noqa: BLE001 - every worker failure must terminate the client stream
            put(
                events,
                {
                    "type": "error",
                    "message": "The answer stream was interrupted. Please try again.",
                },
            )
        finally:
            close = getattr(tokens, "close", None)
            if close:
                close()

    def synthesize_sentence(sentence, audio):
        try:
            for pcm in synthesize(sentence):
                if not put(audio, pcm):
                    return
            put(audio, None)
        except Exception:  # noqa: BLE001 - errors must reach the ordered stream consumer
            put(audio, False)

    def speak():
        pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="nyx-speech")
        pending = []
        exhausted = False
        try:
            while not stopped.is_set():
                while len(pending) < 2 and not exhausted:
                    try:
                        sentence = sentences.get(timeout=0.05 if not pending else 0)
                    except Empty:
                        break
                    if sentence is None:
                        exhausted = True
                    else:
                        audio = Queue(8)
                        pool.submit(synthesize_sentence, sentence, audio)
                        pending.append([sentence, audio, False])
                if not pending:
                    if exhausted:
                        put(events, {"type": "done"})
                        return
                    continue
                current = pending[0]
                if not current[2]:
                    put(events, {"type": "sentence", "text": current[0]})
                    current[2] = True
                try:
                    pcm = current[1].get(timeout=0.05)
                except Empty:
                    continue
                if pcm is False:
                    put(
                        events,
                        {"type": "error", "message": "Speech was interrupted. Please try again."},
                    )
                    return
                if pcm is None:
                    pending.pop(0)
                else:
                    put(
                        events,
                        {
                            "type": "audio",
                            "pcm": base64.b64encode(pcm).decode(),
                            "sample_rate": 24000,
                        },
                    )
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    threads = [Thread(target=produce, daemon=True), Thread(target=speak, daemon=True)]
    for thread in threads:
        thread.start()
    try:
        while not stopped.is_set():
            try:
                event = events.get(timeout=0.25)
            except Empty:
                yield {"type": "heartbeat"}
                continue
            yield event
            if event["type"] in {"done", "error"}:
                break
    finally:
        stopped.set()
        for thread in threads:
            thread.join(timeout=0.2)


def prepare_acknowledgements(root):
    from nyx.voice import CloudVoice

    provider = CloudVoice()

    def prepare(text):
        path = acknowledgement_path(root, provider.tts_model, text)
        if not path.exists():
            audio = base64.b64decode(provider.speak(text))
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_bytes(audio)
            temporary.replace(path)
        return str(path)

    with ThreadPoolExecutor(max_workers=3) as pool:
        return list(
            pool.map(prepare, [text for texts in ACKNOWLEDGEMENTS.values() for text in texts])
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", required=True, metavar="DATA_DIR")
    args = parser.parse_args()
    print(f"Prepared {len(prepare_acknowledgements(args.prepare))} acknowledgement clips.")
