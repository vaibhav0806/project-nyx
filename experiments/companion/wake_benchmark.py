"""Offline speaker-separated synthetic/public wake evaluation; no microphone or cloud calls."""

import argparse
import hashlib
import json
import subprocess
import time
from io import BytesIO
from pathlib import Path

import numpy as np

VOICES = {"development": ["Samantha", "Daniel"], "holdout": ["Rishi", "Moira"]}
TEXTS = {
    "development": [
        ("wake", "Hey Nyx, where are my keys?"),
        ("wake", "Nyx, please help me."),
        ("wake", "Hi Nyx, can you see the blue bottle?"),
        ("wake", "Okay Nyx, where did I leave my glasses?"),
        ("ordinary", "Where is my phone?"),
        ("ordinary", "I'll put the keys by the door."),
        ("near_name", "Hey Nick, please help me."),
        ("near_name", "What's next on the list?"),
        ("homophone", "The Knicks play tonight."),
        ("homophone", "Nick's keys are on the table."),
    ],
    "holdout": [
        ("wake", "Hey Nyx, did I leave the remote on the sofa?"),
        ("wake", "Nyx, I need some assistance."),
        ("wake", "Hi Nyx, where is the medicine box?"),
        ("wake", "Okay Nyx, remember my wallet is in the drawer."),
        ("ordinary", "Have you seen the remote control?"),
        ("ordinary", "My wallet belongs in the cupboard."),
        ("near_name", "Hey Nick, where is the bottle?"),
        ("near_name", "Tell me what comes next."),
        ("homophone", "The Knicks won the game yesterday."),
        ("homophone", "Nick's bottle is beside the sink."),
    ],
}


def probe_windows(sample_count):
    if sample_count < 0:
        raise ValueError("Invalid sample count")
    ends = list(range(12000, sample_count + 1, 12000))
    if sample_count >= 9600 and (not ends or ends[-1] != sample_count):
        ends.append(sample_count)
    return [(max(0, end - 48000), end) for end in ends]


def summarize(rows):
    positives = [row for row in rows if row["expected"]]
    negatives = [row for row in rows if not row["expected"]]
    return {
        "total": len(rows),
        "correct": sum(
            row["status"] == "complete" and row["detected"] == row["expected"] for row in rows
        ),
        "failed": sum(row["status"] != "complete" for row in rows),
        "wake_recall": sum(
            row["status"] == "complete" and row["detected"] is True for row in positives
        )
        / len(positives)
        if positives
        else None,
        "false_wakes": sum(row["detected"] is True for row in negatives),
        "negative_seconds": sum(row["seconds"] for row in negatives),
        "false_by_kind": {
            kind: sum(row["detected"] is True for row in negatives if row["kind"] == kind)
            for kind in sorted({row["kind"] for row in negatives})
        },
    }


def prepare(root, sources):
    import pyarrow.parquet as pq
    import soundfile as sf

    root.mkdir(parents=True, exist_ok=False)
    rows = []
    rng = np.random.default_rng(20261115)

    def save(samples, **metadata):
        path = root / (metadata["id"] + ".wav")
        sf.write(path, np.clip(samples, -0.99, 0.99), 16000, subtype="PCM_16")
        rows.append(
            {
                **metadata,
                "file": path.name,
                "seconds": len(samples) / 16000,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )

    for split, voices in VOICES.items():
        for voice in voices:
            for rate in [150, 205]:
                for number, (kind, text) in enumerate(TEXTS[split]):
                    stem = f"{voice}-{rate}-{number}"
                    aiff, wav = root / (stem + ".aiff"), root / (stem + ".source.wav")
                    subprocess.run(
                        ["say", "-v", voice, "-r", str(rate), "-o", str(aiff), text],
                        check=True,
                        timeout=30,
                    )
                    subprocess.run(
                        [
                            "ffmpeg",
                            "-nostdin",
                            "-hide_banner",
                            "-loglevel",
                            "error",
                            "-n",
                            "-i",
                            str(aiff),
                            "-ar",
                            "16000",
                            "-ac",
                            "1",
                            str(wav),
                        ],
                        check=True,
                        timeout=30,
                    )
                    samples, sr = sf.read(wav, dtype="float32")
                    if sr != 16000 or samples.ndim != 1:
                        raise ValueError("Unexpected generated audio format")
                    samples = np.concatenate([np.zeros(3200), samples, np.zeros(8000)])
                    for profile in ["clean", "noise15"]:
                        selected = samples.copy()
                        if profile != "clean":
                            selected += rng.normal(
                                0, np.sqrt(np.mean(samples**2)) / np.sqrt(10**1.5), len(samples)
                            )
                        save(
                            selected,
                            id=stem + "-" + profile,
                            split=split,
                            kind=kind,
                            expected=kind == "wake",
                            voice=voice,
                            rate=rate,
                            text=text,
                            profile=profile,
                            source="macOS synthetic speech",
                        )
    table = pq.read_table(sources / "librispeech-dummy.parquet")
    for record in table.to_pylist():
        if "NYX" in record["text"].upper().split():
            raise ValueError("Public negative contains target word")
        samples, sr = sf.read(BytesIO(record["audio"]["bytes"]), dtype="float32")
        if sr != 16000 or samples.ndim != 1:
            raise ValueError("Unexpected public sample format")
        save(
            samples,
            id="libri-" + record["id"],
            split="holdout",
            kind="public_speech",
            expected=False,
            speaker_id=record["speaker_id"],
            source="LibriSpeech via hf-internal-testing/librispeech_asr_dummy; CC-BY-4.0",
        )
    manifest = {
        "version": 1,
        "source_manifest_sha256": hashlib.sha256(
            (sources / "sources.json").read_bytes()
        ).hexdigest(),
        "cases": rows,
        "limitations": "Synthetic voices separated across splits; public negatives from one LibriSpeech speaker held out entirely. Clip-level any detection on overlapping 3s probes at750ms plus final endpoint. Not an independently calibrated false-alarm/hour or human wake acceptance benchmark. Homophones remain separately labeled; no fixture-derived aliases.",
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return {
        "cases": len(rows),
        "public_seconds": sum(row["seconds"] for row in rows if row["kind"] == "public_speech"),
    }


def run(root, sources, output, split, engine, threshold):
    import soundfile as sf

    manifest = json.loads((root / "manifest.json").read_text())
    cases = [row for row in manifest["cases"] if row["split"] == split]
    for row in cases:
        path = (root / row["file"]).resolve()
        if (
            not path.is_relative_to(root.resolve())
            or hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]
        ):
            raise ValueError("Source identity differs from frozen public/synthetic manifest")
    output.mkdir(parents=True, exist_ok=False)
    if engine == "whisper":
        from nyx.voice import WakeRecognizer, wake_command

        recognizer = WakeRecognizer()

        def detect(samples):
            return (
                wake_command(
                    recognizer((samples * 32768).clip(-32768, 32767).astype("<i2").tobytes())
                )
                is not None
            )
    else:
        import sherpa_onnx

        model = sources / "sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20"
        kws = sherpa_onnx.KeywordSpotter(
            tokens=str(model / "tokens.txt"),
            encoder=str(model / "encoder-epoch-13-avg-2-chunk-16-left-64.int8.onnx"),
            decoder=str(model / "decoder-epoch-13-avg-2-chunk-16-left-64.onnx"),
            joiner=str(model / "joiner-epoch-13-avg-2-chunk-16-left-64.int8.onnx"),
            keywords_file=str(sources / "keywords-nyx.txt"),
            num_threads=2,
            keywords_threshold=threshold,
        )

        def detect(samples):
            stream = kws.create_stream()
            stream.accept_waveform(16000, samples)
            stream.accept_waveform(16000, np.zeros(10600, dtype=np.float32))
            stream.input_finished()
            found = False
            while kws.is_ready(stream):
                kws.decode_stream(stream)
                if kws.get_result(stream):
                    found = True
                    kws.reset_stream(stream)
            return found

    rows = []
    report = {
        "engine": engine,
        "threshold": threshold if engine == "sherpa" else None,
        "split": split,
        "manifest_sha256": hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest(),
        "cases": rows,
        "limitations": manifest["limitations"],
    }
    for case in cases:
        samples, sr = sf.read(root / case["file"], dtype="float32")
        if sr != 16000:
            raise ValueError("Invalid sample rate")
        started = time.perf_counter()
        detections = []
        times = []
        for start, end in probe_windows(len(samples)):
            window = samples[start:end]
            began = time.perf_counter()
            hit = detect(window) if np.sqrt(np.mean(window**2)) >= 0.001 else False
            times.append(round((time.perf_counter() - began) * 1000, 3))
            if hit:
                detections.append(round(end / 16000, 3))
        rows.append(
            {
                **case,
                "status": "complete",
                "detected": bool(detections),
                "detection_end_seconds": detections,
                "probe_ms": times,
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
            }
        )
        report["summary"] = summarize(rows)
        (output / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    return report["summary"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--split", choices=["development", "holdout"], default="development")
    parser.add_argument("--engine", choices=["whisper", "sherpa"], default="sherpa")
    parser.add_argument("--threshold", type=float, default=0.25)
    args = parser.parse_args()
    print(
        json.dumps(
            prepare(args.data, args.sources)
            if args.prepare
            else run(args.data, args.sources, args.output, args.split, args.engine, args.threshold)
        )
    )
