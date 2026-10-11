"""Offline check of the orchestrator's scope gate, using stand-in vision and LLM providers.

The scope check runs first on the user's words alone; the photo only reaches the vision model
later, if the LLM asks for it with the recognize_photo tool.

Run from services/api (no API keys, Ollama or vision service needed):
    python scripts/orchestrator_validation.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.llm_interface import FunctionDefinition, LLMResponse, Message  # noqa: E402
from app.orchestrator import CommandValidationError, Orchestrator  # noqa: E402
from app.vlm_interface import VLMRequest, VLMResponse  # noqa: E402

PHOTO = VLMRequest(image=b"stand-in photo", content_type="image/png")
EVIDENCE = "Rank 1: a registered grocery product."


class StandInVision:
    def __init__(self, log: list[str]) -> None:
        self.log, self.seen = log, None

    async def describe(self, request: VLMRequest) -> VLMResponse:
        self.log.append("vision")
        self.seen = request
        return VLMResponse(description=EVIDENCE)


class StandInLLM:
    """Answers the scope check with a fixed reply and records what it was sent."""

    def __init__(self, reply: str, log: list[str]) -> None:
        self.reply, self.log, self.sent = reply, log, None

    async def complete(self, messages: Sequence[Message], *, functions: Sequence[FunctionDefinition] = (),
                       temperature: float | None = None) -> LLMResponse:
        self.log.append("llm")
        if functions or temperature != 0:
            raise AssertionError("the scope check must run at temperature 0 without tools")
        self.sent = json.loads(next(m.content for m in messages if m.role == "user"))
        return LLMResponse(content=self.reply)


async def case(label: str, prompt: str, reply: str, expect: str) -> bool:
    """``expect`` is "in_progress", "rejected", or "error" for an answer that must be refused."""
    log: list[str] = []
    llm, vision = StandInLLM(reply, log), StandInVision(log)
    try:
        result = await Orchestrator(llm, vision).run(prompt, image=PHOTO)
        outcome = result.status
    except CommandValidationError:
        outcome = "error"
    problems = []
    if outcome != expect:
        problems.append(f"expected {expect}, got {outcome}")
    if log[:1] != ["llm"] or "vision" in log:
        problems.append(f"call order {log}: the scope check must come first, without vision")
    if vision.seen is not None:
        problems.append("the scope check must not send the photo to the vision provider")
    if llm.sent != {"prompt": prompt, "image_uploaded": True}:
        problems.append(f"unexpected LLM input {llm.sent}")
    print(f"{label}: {'FAIL — ' + '; '.join(problems) if problems else 'PASS — ' + outcome}")
    return not problems


async def main() -> int:
    results = [
        await case("in scope", "Add the pictured product to my grocery list",
                   json.dumps({"valid": True, "reason": None}), "in_progress"),
        await case("out of scope", "Buy me a car",
                   json.dumps({"valid": False, "reason": "Buying cars is not a grocery task."}), "rejected"),
        await case("fenced JSON", "Show my grocery list",
                   '```json\n{"valid": true, "reason": null}\n```', "in_progress"),
        await case("malformed", "Add the pictured product to my grocery list",
                   '{"valid": "yes", "reason": null}', "error"),
    ]
    print(f"\nSummary: {sum(results)}/{len(results)} cases passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
