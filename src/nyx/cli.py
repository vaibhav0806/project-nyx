import argparse
import json
import math
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

from nyx.memory import Store
from nyx.report import write_gallery
from nyx.retrieval import index_video, search


def _recorded_at(value):
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use an ISO timestamp with timezone") from exc
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("Recording time needs a timezone, e.g. +05:30 or Z")
    return parsed.astimezone(UTC).isoformat()


def _positive_float(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("Value must be positive and finite")
    return number


def _positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("Value must be positive")
    return number


def main():
    parser = argparse.ArgumentParser(description="Nyx local visual-retrieval baseline")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--device", choices=["auto", "mps", "cpu"], default="auto")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Check local runtime without downloading weights")
    index = commands.add_parser("index", help="Copy and index a local video")
    index.add_argument("video", type=Path)
    index.add_argument("--interval", type=_positive_float, default=2)
    index.add_argument("--batch-size", type=_positive_int, default=8)
    index.add_argument("--recorded-at", type=_recorded_at)
    query = commands.add_parser("search", help="Retrieve candidate frames using descriptive text")
    query.add_argument("query")
    query.add_argument("--limit", type=_positive_int, default=5)
    query.add_argument("--video-id")
    query.add_argument("--start", type=float, help="Start offset in seconds within each clip")
    query.add_argument("--end", type=float, help="End offset in seconds within each clip")
    query.add_argument("--html", type=Path, help="Write a self-contained candidate-frame gallery")
    commands.add_parser("list", help="List indexed clips without loading the model")
    serve = commands.add_parser("serve", help="Open the manual local recording/search interface")
    serve.add_argument("--port", type=_positive_int, default=8000)
    args = parser.parse_args()
    if args.command == "search":
        if not args.query.strip():
            parser.error("Search query must not be blank")
        if args.limit > 100:
            parser.error("Search limit must not exceed 100")
    try:
        if args.command == "serve":
            import uvicorn

            from nyx.app import create_app

            uvicorn.run(create_app(args.data_dir, args.device), host="127.0.0.1", port=args.port)
            return
        if args.command == "doctor":
            import sqlite_vec
            import torch

            with sqlite3.connect(":memory:") as db:
                db.enable_load_extension(True)
                sqlite_vec.load(db)
                db.enable_load_extension(False)
                version = db.execute("SELECT vec_version()").fetchone()[0]
            print(
                json.dumps(
                    {
                        "python": sys.version.split()[0],
                        "sqlite": sqlite3.sqlite_version,
                        "sqlite_vec": version,
                        "torch": torch.__version__,
                        "mps_available": torch.backends.mps.is_available(),
                    },
                    indent=2,
                )
            )
            return
        if args.command == "list":
            path = args.data_dir / "index.sqlite3"
            if not path.is_file():
                raise ValueError("No index exists here; run nyx index first")
            with sqlite3.connect(path) as db:
                identity = json.loads(
                    db.execute("SELECT value FROM meta WHERE key='encoder'").fetchone()[0]
                )
            store = Store(args.data_dir, identity["encoder"], identity["dimensions"])
            print(json.dumps(store.list_videos(), indent=2))
            return
        if args.command == "index" and not args.video.is_file():
            raise ValueError(f"Video does not exist: {args.video}")
        if args.command == "search" and not (args.data_dir / "index.sqlite3").is_file():
            raise ValueError("No index exists here; run nyx index first")
        from nyx.perception import SiglipEncoder

        encoder = SiglipEncoder(args.device)
        store = Store(args.data_dir, encoder.fingerprint, encoder.dimensions)
        if args.command == "index":
            output = index_video(
                args.video, store, encoder, args.interval, args.batch_size, args.recorded_at
            )
        else:
            output = {
                "query": args.query,
                "verified": False,
                "results": search(
                    args.query,
                    store,
                    encoder,
                    limit=args.limit,
                    video_id=args.video_id,
                    start=args.start,
                    end=args.end,
                ),
            }
            if args.html:
                output["gallery"] = str(
                    write_gallery(args.query, output["results"], store.root, args.html)
                )
        print(json.dumps(output, indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(1, f"nyx: {exc}\n")


if __name__ == "__main__":
    main()
