import asyncio
import json

import pytest
from livekit import rtc

from nyx import realtime


def replay(monkeypatch, packets):
    class Socket:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def send(self, data):
            pass

        def __aiter__(self):
            return self

        async def __anext__(self):
            await asyncio.sleep(0)
            if packets:
                return json.dumps(packets.pop(0))
            raise StopAsyncIteration

    monkeypatch.setenv("SARVAM_API_KEY", "fixture")
    monkeypatch.setattr(realtime, "connect", lambda *args, **kwargs: Socket())

    async def run():
        provider = realtime.RealtimeSTT(lambda *args, **kwargs: None)
        try:
            async with provider.stream() as stream:
                stream.push_frame(rtc.AudioFrame(bytes(640), 16000, 1, 320))
                async with asyncio.timeout(2):
                    return [event async for event in stream]
        finally:
            await provider.aclose()

    return asyncio.run(run())


@pytest.mark.parametrize(
    "text,language",
    [("I will put my glasses in the drawer.", "en-IN"), ("चाबी अभी बैग में नहीं रखी है।", "hi-IN")],
)
@pytest.mark.parametrize("final_first", [False, True])
def test_final_is_committed_once_after_speech_boundary(monkeypatch, text, language, final_first):
    final = {"event": "transcript.final", "text": text, "language": language, "utterance_idx": 0}
    end = {"event": "vad.speech_end"}
    packets = [
        {"event": "vad.speech_start"},
        *([final, end] if final_first else [end, final]),
        final,
        {"event": "session.end"},
    ]
    events = replay(monkeypatch, packets)
    assert [event.type.value for event in events] == [
        "start_of_speech",
        "end_of_speech",
        "final_transcript",
    ]
    assert events[-1].alternatives[0].text == text
    assert events[-1].alternatives[0].language == language


def test_graceful_terminal_boundary_keeps_pending_final(monkeypatch):
    events = replay(
        monkeypatch,
        [
            {"event": "vad.speech_start"},
            {"event": "transcript.final", "text": "Mera remote kahan hai?", "language": "hi-IN"},
            {"event": "session.end"},
        ],
    )
    assert [event.type.value for event in events] == [
        "start_of_speech",
        "end_of_speech",
        "final_transcript",
    ]


def test_identical_words_in_new_utterances_are_not_deduplicated(monkeypatch):
    packets = []
    for index in range(2):
        packets.extend(
            [
                {"event": "vad.speech_start"},
                {"event": "vad.speech_end"},
                {"event": "transcript.final", "text": "Where are my keys?", "utterance_idx": index},
            ]
        )
    events = replay(monkeypatch, packets)
    assert sum(event.type.value == "final_transcript" for event in events) == 2


def test_repeated_boundary_and_empty_payloads_do_not_create_turns(monkeypatch):
    events = replay(
        monkeypatch,
        [
            {"event": "vad.speech_start"},
            {"event": "transcript.final", "text": None},
            {"event": "transcript.final", "text": "  "},
            {"event": "vad.speech_end"},
            {"event": "vad.speech_end"},
            {"event": "session.end"},
        ],
    )
    assert [event.type.value for event in events] == ["start_of_speech", "end_of_speech"]


def test_new_start_flushes_pending_previous_final_before_next_turn(monkeypatch):
    events = replay(
        monkeypatch,
        [
            {"event": "vad.speech_start"},
            {"event": "transcript.final", "text": "I put it in the bag.", "utterance_idx": 0},
            {"event": "vad.speech_start"},
            {"event": "transcript.final", "text": "I put it in the bag.", "utterance_idx": 0},
            {"event": "vad.speech_end"},
            {
                "event": "transcript.final",
                "text": "Actually, I meant the drawer.",
                "utterance_idx": 1,
            },
        ],
    )
    assert [event.type.value for event in events] == [
        "start_of_speech",
        "end_of_speech",
        "final_transcript",
    ] * 2
    assert [
        event.alternatives[0].text for event in events if event.type.value == "final_transcript"
    ] == ["I put it in the bag.", "Actually, I meant the drawer."]


def test_late_final_after_next_speech_start_does_not_drop_the_next_utterance(monkeypatch):
    events = replay(
        monkeypatch,
        [
            {"event": "vad.speech_start"},
            {"event": "vad.speech_end"},
            {"event": "vad.speech_start"},
            {"event": "transcript.final", "text": "The keys are on the table.", "utterance_idx": 0},
            {"event": "vad.speech_end"},
            {
                "event": "transcript.final",
                "text": "Actually, they are in the bag.",
                "utterance_idx": 1,
            },
        ],
    )
    finals = [
        event.alternatives[0].text for event in events if event.type.value == "final_transcript"
    ]
    assert finals == ["The keys are on the table.", "Actually, they are in the bag."]
