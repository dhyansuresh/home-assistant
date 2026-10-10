"""Send one prompt through the provider-neutral LLM interface and print reply.

Run from services/api after configuring the repository-root .env:
    python scripts/llm_prompt.py "What is HomePilot?"
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Allow direct execution as a script from services/api without installation.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.gemini import GeminiProvider
from app.llm_interface import Message


async def send_prompt(prompt: str) -> str:
    provider = GeminiProvider()
    response = await provider.complete([Message(role="user", content=prompt)])
    return response.content


def main() -> int:
    parser = argparse.ArgumentParser(description="Send one prompt through the LLMProvider interface.")
    parser.add_argument("prompt", help="Prompt text to send")
    args = parser.parse_args()

    try:
        answer = asyncio.run(send_prompt(args.prompt))
    except Exception as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1

    print(answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
