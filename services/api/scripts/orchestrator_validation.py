"""Run the orchestrator's current command-validation stage against Gemini.

Run from ``services/api`` after setting ``GEMINI_API_KEY`` in the repository
root ``.env`` file:
    python scripts/orchestrator_validation.py --image-uploaded true "What is this?"
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Allow direct execution as a script from services/api without installation.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.gemini import GeminiProvider
from app.orchestrator import Orchestrator


async def validate(prompt: str, *, image_uploaded: bool):
    orchestrator = Orchestrator(GeminiProvider())
    return await orchestrator.run(prompt, image_uploaded=image_uploaded)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check whether the orchestrator considers a HomePilot command valid."
    )
    parser.add_argument(
        "--image-uploaded",
        choices=("true", "false"),
        required=True,
        help="Whether an image was uploaded",
    )
    parser.add_argument("prompt", nargs="+", help="The user's command prompt")
    args = parser.parse_args()

    try:
        result = asyncio.run(
            validate(" ".join(args.prompt), image_uploaded=args.image_uploaded == "true")
        )
    except Exception as exc:
        print(f"Validation request failed: {exc}", file=sys.stderr)
        return 1

    print(f"Valid: {'yes' if result.valid else 'no'}")
    print(f"Status: {result.status}")
    if result.reason:
        print(f"Reason: {result.reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
