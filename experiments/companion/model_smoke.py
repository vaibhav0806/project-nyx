"""One synthetic image only; no capture, replay or household accuracy claim."""

import argparse
import json
import resource
import time
from pathlib import Path

import mlx.core as mx
from PIL import Image, ImageDraw

from nyx.verification import LocalVerifier

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
mx.set_memory_limit(6 * 1024**3)
mx.set_cache_limit(128 * 1024**2)
image = Image.new("RGB", (224, 224), "white")
ImageDraw.Draw(image).rectangle((48, 48, 176, 176), fill="red")
model = LocalVerifier()
start = time.perf_counter()
raw = model.generate_json(
    [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {
                    "type": "text",
                    "text": "What color is the square? Reply only as JSON with one key: color.",
                },
            ],
        }
    ],
    32,
)
result = {
    "model": model.fingerprint,
    "load_seconds": model.load_seconds,
    "generation_seconds": time.perf_counter() - start,
    "raw": raw,
    "mlx_peak_bytes": mx.get_peak_memory(),
    "process_max_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    "scope": "One synthetic-image smoke; no video or household accuracy claim",
}
(args.output / "result.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result), flush=True)
assert json.loads(raw)["color"].lower() == "red"
