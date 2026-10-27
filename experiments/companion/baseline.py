"""Run common retrieval/visual probes with either checkout's Python environment.

Use a copied synthetic workspace, never an actual user's library. Run each process
sequentially under the memory watchdog. Results are observations, not accuracy scores.
"""

import argparse
import json
import resource
import time
from pathlib import Path

from PIL import Image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["retrieval", "visual"])
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workspace", type=Path)
    args = parser.parse_args()
    if args.mode == "retrieval" and args.workspace is None:
        parser.error("retrieval requires --workspace")
    if args.output.exists():
        parser.error("Choose a new output file")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = {"mode": args.mode, "scope": "Reused public fixture, no hardware or provider"}
    started = time.monotonic()
    try:
        if args.mode == "retrieval":
            from nyx.memory import Store
            from nyx.perception import SiglipEncoder
            from nyx.retrieval import index_video, search

            encoder = SiglipEncoder()
            report.update(fingerprint=encoder.fingerprint, load_seconds=time.monotonic() - started)
            store = Store(args.workspace, encoder.fingerprint, encoder.dimensions)
            if not store.list_videos():
                report["index"] = index_video(
                    args.fixture / "scenes.mp4", store, encoder, recorded_at="2026-10-20T10:00:00Z"
                )
            report["queries"] = {}
            for query in [
                "television remote control",
                "cat on the left",
                "television remote control on the right",
            ]:
                before = time.monotonic()
                hits = search(query, store, encoder, limit=5)
                report["queries"][query] = {
                    "seconds": time.monotonic() - before,
                    "hits": [
                        {
                            key: hit[key]
                            for key in ["id", "offset_seconds", "observed_at", "similarity"]
                        }
                        for hit in hits
                    ],
                }
            report["videos"] = store.list_videos()
        else:
            from nyx.verification import LocalVerifier

            model = LocalVerifier()
            report.update(
                model=model.fingerprint, load_seconds=time.monotonic() - started, cases=[]
            )
            for name, file, query in [
                ("ambiguous", "000.png", "television remote control"),
                ("right", "000.png", "television remote control on the right of the picture"),
                ("single", "007.png", "television remote control"),
                ("empty", "009.png", "television remote control"),
            ]:
                before = time.monotonic()
                with Image.open(args.fixture / "input_frames" / file) as image:
                    judgment = model.inspect(image, query)
                report["cases"].append(
                    {"name": name, "judgment": judgment, "seconds": time.monotonic() - before}
                )
                args.output.write_text(json.dumps(report, indent=2))
        report["completed"] = True
    except (ValueError, OSError, RuntimeError) as error:
        report.update(completed=False, error=repr(error))
    report["rss_peak_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report["seconds"] = time.monotonic() - started
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)
    if not report["completed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
