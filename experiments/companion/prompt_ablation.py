"""Explicit experiment-only prompt replacement; never adds a runtime mode or extra judge."""

import argparse
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from experiments.companion import household_workflows, spoken_fresh_evidence
from nyx import reference


def run(args):
    prompt = args.prompt.read_text().strip()
    if not 10 <= len(prompt.split()) <= 150:
        raise ValueError("This diagnostic requires a short explicit prompt")
    settings = {
        "task": args.task,
        "prompt": prompt,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "policy": "Experiment-only module replacement, no runtime switch or additional inference",
    }
    try:
        if args.task == "reference":
            if not args.data or not args.cases:
                raise ValueError("Reference workflows require a frozen fixture and cases")
            with patch.object(reference, "REFERENCE_INSTRUCTIONS", prompt):
                result = household_workflows.run(
                    args.data, args.cases, args.output, args.split, args.max_spend
                )
        else:
            with patch.object(spoken_fresh_evidence, "INSTRUCTIONS", prompt):
                result = spoken_fresh_evidence.run(args.output, args.max_spend)
        return result
    finally:
        if args.output.exists():
            (args.output / "ablation.json").write_text(json.dumps(settings, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=["reference", "agent"], required=True)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--data", type=Path)
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--split", choices=["development", "holdout"], default="development")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-spend", type=float, default=0.10)
    print(json.dumps(run(parser.parse_args())))
