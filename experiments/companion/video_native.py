"""Compare time-labelled images and native timestamped video with the SAME prompt."""

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from transformers.video_utils import VideoMetadata

from nyx.observation import departure_judgment
from nyx.verification import DEPARTURE_PROMPT, LocalVerifier


def native_video(model, images, interval):
    messages = [
        {"role": "user", "content": [{"type": "video"}, {"type": "text", "text": DEPARTURE_PROMPT}]}
    ]
    text = model.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    video = np.stack([np.asarray(image) for image in images])
    metadata = VideoMetadata(
        total_num_frames=len(images),
        fps=1 / interval,
        duration=len(images) * interval,
        frames_indices=list(range(len(images))),
    )
    inputs = model.processor(
        text=[text],
        videos=[video],
        videos_kwargs={
            "video_metadata": [metadata],
            "do_sample_frames": False,
            "size": {"shortest_edge": 128 * 32 * 32, "longest_edge": 4 * 640 * 360},
        },
        return_tensors="pt",
    ).to(model.device)
    with torch.inference_mode():
        generated = model.model.generate(**inputs, max_new_tokens=140, do_sample=False)
    return model.processor.decode(
        generated[0][inputs["input_ids"].shape[-1] :], skip_special_tokens=True
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=["video", "labelled_images"], required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    model = LocalVerifier()
    results = {
        "mode": args.mode,
        "model": model.fingerprint,
        "prompt": DEPARTURE_PROMPT,
        "generation_max_new_tokens": 140,
        "relative_sample_interval_seconds": 2,
        "cases": [],
    }
    for case in json.loads(args.manifest.read_text())["cases"]:
        paths = sorted(Path(case["frames"]).glob("*.jpg"))
        images = [Image.open(paths[index]).convert("RGB") for index in case["indices"]]
        for image in images:
            image.thumbnail((640, 360))
        started = time.perf_counter()
        if args.mode == "video":
            raw = native_video(model, images, 2)
        else:
            content = []
            for index, image in enumerate(images):
                content.extend(
                    [
                        {
                            "type": "text",
                            "text": f"Chronological frame {index + 1}, relative time {index * 2} seconds:",
                        },
                        {"type": "image", "image": image},
                    ]
                )
            content.append({"type": "text", "text": DEPARTURE_PROMPT})
            raw = model.generate_json([{"role": "user", "content": content}], 140)
        judgment = departure_judgment(raw)
        row = {**case, "raw": raw, "judgment": judgment, "seconds": time.perf_counter() - started}
        results["cases"].append(row)
        print(
            json.dumps(
                {
                    "name": case["name"],
                    "expected": case["expected"],
                    "judgment": judgment,
                    "seconds": row["seconds"],
                }
            ),
            flush=True,
        )
        (args.output / "results.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
