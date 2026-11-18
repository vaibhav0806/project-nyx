"""Explicit experiment-only prompt replacement; never adds a runtime mode or extra judge."""

import argparse
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import patch

from experiments.companion import household_workflows, spoken_fresh_evidence
from nyx import reference
from nyx.agent_policy import VISION_MODEL
from nyx.cloud import OpenRouter


def run(args):
    prompt = args.prompt.read_text().strip()
    if not 10 <= len(prompt.split()) <= 150:
        raise ValueError("This diagnostic requires a short explicit prompt")
    settings = {
        "task": args.task,
        "prompt": prompt,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "policy": "Experiment-only module replacement, no runtime switch or additional inference",
        "reasoning_effort": args.effort,
    }
    schema = reference.REFERENCE_SCHEMA
    if args.task == "reference" and args.scene_context:
        schema = {
            **schema,
            "properties": {
                "scene_context": {
                    "type": "string",
                    "description": "What is visible across each complete frame, before selecting a referent.",
                },
                **schema["properties"],
            },
            "required": ["scene_context", *schema["required"]],
        }
    settings["reference_schema"] = schema
    try:
        if args.task == "reference":
            if not args.data or not args.cases:
                raise ValueError("Reference workflows require a frozen fixture and cases")
            original_request = OpenRouter.request
            vision_model = os.environ.get("NYX_VISION_MODEL", VISION_MODEL)

            def request(client, path, payload, **kwargs):
                if payload.get("model") == vision_model:
                    payload = {**payload, "reasoning": {"effort": args.effort, "exclude": True}}
                return original_request(client, path, payload, **kwargs)

            with (
                patch.object(reference, "REFERENCE_INSTRUCTIONS", prompt),
                patch.object(reference, "REFERENCE_SCHEMA", schema),
                patch.object(OpenRouter, "request", request),
            ):
                result = household_workflows.run(
                    args.data, args.cases, args.output, args.split, args.max_spend
                )
        else:
            with patch.object(spoken_fresh_evidence, "INSTRUCTIONS", prompt):
                result = spoken_fresh_evidence.run(
                    args.output, args.max_spend, args.cases, args.effort
                )
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
    parser.add_argument("--effort", choices=["low", "medium"], default="low")
    parser.add_argument("--scene-context", action="store_true")
    print(json.dumps(run(parser.parse_args())))
