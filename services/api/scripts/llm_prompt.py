"""Ask the local Ollama model one question through the LLM interface and print the answer.

Run from services/api with Ollama running:
    python scripts/llm_prompt.py "What is HomePilot?"
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.llm_interface import Message  # noqa: E402
from app.ollama import OllamaProvider  # noqa: E402


async def ask(question: str) -> str:
    reply = await OllamaProvider().complete([Message(role="user", content=question)])
    return reply.content


def main() -> int:
    parser = argparse.ArgumentParser(description="Send one prompt to the configured LLM.")
    parser.add_argument("prompt")
    question = parser.parse_args().prompt
    try:
        print(asyncio.run(ask(question)))
    except Exception as problem:
        print(f"Request failed: {problem}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
