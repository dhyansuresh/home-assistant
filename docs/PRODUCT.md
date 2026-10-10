# Product brief

## Who and what

<<<<<<< Updated upstream
HomePilot helps one household keep a simple grocery inventory and shopping list. In the MVP, a person uses a desktop web page and webcam to capture a grocery item, reviews a model suggestion, and confirms what to save. iPhone capture follows after this desktop flow works. They can inspect inventory and ask a text assistant to add or review grocery-list items.
=======
| Mode | How it works |
| --- | --- |
| Stationary Home Assistant | A laptop or iPhone stays on an open, enabled app screen. It waits for "Hey HomePilot" with the camera off. Wake activation starts continuous camera capture with sampled recognition and speech-to-text. HomePilot uses the whole conversation to understand and clarify the task. Once the task is understood and confirmed, task capture/transcription stop and it executes. |
| Mobile point-and-click | A separate phone/iPhone opens the same household app, points at a product, and takes one photo. No wake phrase or microphone is required. Gemini coordinates identification through the fine-tuned vision model; the user chooses/confirms the action. This works outside the stationary camera's field of view, with network access to the same backend. |
>>>>>>> Stashed changes

## Core jobs

1. **Remember what we have.** A confirmed product and quantity appear in inventory and remain after reload.
2. **Reduce typing.** A photo supplies a candidate name; the user can correct it or enter an unknown product manually.
3. **Make a useful shopping list.** A text request can inspect inventory and add an item through a runtime MCP tool, with the result visible in the list.

## Product principles

- The user remains the authority on product identity and quantity.
- An honest unknown result is better than a confident wrong item.
- A short, reliable end-to-end demo is more valuable than many disconnected features.
- The robot is a future interface to the same application, after the software works.

## Demo story

<<<<<<< Updated upstream
Capture a grocery item with a desktop webcam; review or correct the prediction; save one unit; reload and see it in inventory; ask HomePilot to add another item to the grocery list; see the list update. The demo should also show an unknown photo and manual correction.

Acceptance criteria and exclusions are in [MVP_SCOPE.md](MVP_SCOPE.md).
=======
Gemini is the LLM orchestrator. It selects a recognition tool, and FastAPI executes that call with the captured image against a fine-tuned Hugging Face model served on AMD ROCm. The recognition result returns as tool evidence. Gemini then selects allowed runtime MCP tools to retrieve data or carry out a confirmed task. The MCP server validates arguments and accesses PostgreSQL (Supabase is the current default).

Fine-tuning and evaluating the resulting checkpoint are required P0. Exact model/checkpoint and dataset remain open. No accuracy, cost, or speed advantage is assumed. The user remains the authority on product identity and quantity; unknown and correction remain possible.

## Demo story and status

Demonstrate all three named voice examples, a visual "this item" task with a correction, and a separate iPhone one-photo task outside the stationary camera's view. Show the same list/inventory on both devices, a truthful last-added date from stored history, no duplicate writes, and task capture stopping before execution. Test stationary voice mode on both laptop and iPhone.

This is the intended scope. The starter has manual webcam capture and stub services; voice, sessions, Gemini orchestration, fine-tuned inference, MCP tools, and history remain unimplemented. See [MVP_SCOPE.md](MVP_SCOPE.md), [VOICE_CAPTURE.md](VOICE_CAPTURE.md), and [RECOGNITION_DESIGN.md](RECOGNITION_DESIGN.md).
>>>>>>> Stashed changes
