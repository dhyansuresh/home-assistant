"""Exercise orchestrator validation with deterministic provider doubles.

Run from ``services/api`` without arguments, API keys, or external services:
    python scripts/orchestrator_validation.py

The script runs valid, invalid, and malformed LLM-response cases and reports
whether the orchestrator handled each case as expected.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Sequence

# Allow direct execution as a script from services/api without installation.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.llm_interface import FunctionDefinition, LLMResponse, Message
from app.orchestrator import CommandValidationError, Orchestrator
from app.vlm_interface import VLMRequest, VLMResponse

TEST_IMAGE_DESCRIPTION = "A grocery product is clearly distinguishable."
TEST_IMAGE = VLMRequest(image=b"test image bytes", content_type="image/png")


class TestLLMProvider:
    """Return a configured response and capture the orchestrator's context."""

    def __init__(self, *, response_content: str, calls: list[str]) -> None:
        self.response_content = response_content
        self.calls = calls
        self.user_payload: dict[str, object] | None = None

    async def complete(
        self,
        messages: Sequence[Message],
        *,
        functions: Sequence[FunctionDefinition] = (),
        temperature: float | None = None,
    ) -> LLMResponse:
        self.calls.append("llm")
        if functions or temperature != 0:
            raise AssertionError("expected deterministic validation without tool calls")
        user_message = next(message for message in messages if message.role == "user")
        self.user_payload = json.loads(user_message.content)
        return LLMResponse(content=self.response_content, model="test-llm")


class TestVLMProvider:
    """Return a fixed description and record that the image reached the VLM boundary."""

    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.received_request: VLMRequest | None = None

    async def describe(self, request: VLMRequest) -> VLMResponse:
        self.calls.append("vlm")
        self.received_request = request
        return VLMResponse(description=TEST_IMAGE_DESCRIPTION)


async def run_case(
    *,
    name: str,
    prompt: str,
    llm_response: str,
    expected_valid: bool | None,
) -> bool:
    calls: list[str] = []
    llm_provider = TestLLMProvider(response_content=llm_response, calls=calls)
    vlm_provider = TestVLMProvider(calls)
    orchestrator = Orchestrator(llm_provider, vlm_provider)

    try:
        result = await orchestrator.run(prompt, image=TEST_IMAGE)
    except CommandValidationError:
        if expected_valid is not None:
            print(f"{name}: FAIL — the orchestrator rejected a well-formed decision")
            return False
        expected_outcome = "rejected malformed response"
        print(f"{name}: PASS — {expected_outcome}")
    except Exception as exc:
        print(f"{name}: FAIL — unexpected {type(exc).__name__}: {exc}")
        return False
    else:
        if expected_valid is None:
            print(f"{name}: FAIL — malformed response was accepted")
            return False
        expected_status = "in_progress" if expected_valid else "rejected"
        if result.valid is not expected_valid or result.status != expected_status:
            print(
                f"{name}: FAIL — expected valid={expected_valid}, status={expected_status}; "
                f"got valid={result.valid}, status={result.status}"
            )
            return False
        reason = f", reason={result.reason}" if result.reason else ""
        print(f"{name}: PASS — valid={str(result.valid).lower()}, status={result.status}{reason}")

    if calls != ["vlm", "llm"]:
        print(f"{name}: FAIL — expected VLM then LLM calls, got {calls}")
        return False
    if vlm_provider.received_request != TEST_IMAGE:
        print(f"{name}: FAIL — image was not passed to the VLM interface")
        return False
    expected_context = {
        "prompt": prompt,
        "image_uploaded": True,
        "image_description": TEST_IMAGE_DESCRIPTION,
    }
    if llm_provider.user_payload != expected_context:
        print(f"{name}: FAIL — unexpected LLM context: {llm_provider.user_payload}")
        return False
    return True


async def main() -> int:
    cases = (
        {
            "name": "valid",
            "prompt": "Add the shown product to my grocery list",
            "llm_response": json.dumps({"valid": True, "reason": None}),
            "expected_valid": True,
        },
        {
            "name": "invalid",
            "prompt": "Buy a car",
            "llm_response": json.dumps(
                {"valid": False, "reason": "Car purchases are outside HomePilot's scope."}
            ),
            "expected_valid": False,
        },
        {
            "name": "malformed",
            "prompt": "Add the shown product to my grocery list",
            "llm_response": '{"valid": "yes", "reason": null}',
            "expected_valid": None,
        },
    )
    results = [await run_case(**case) for case in cases]
    passed = sum(results)
    print(f"\nSummary: {passed}/{len(results)} cases passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
