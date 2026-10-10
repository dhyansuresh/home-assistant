# Product brief

## MVP: two ways to use the same household assistant

| Mode | How it works |
| --- | --- |
| Stationary Home Assistant | A laptop or iPhone stays on an open, enabled app screen. It waits for "Hey HomePilot" with the camera off. Wake activation starts continuous camera capture with sampled recognition and speech-to-text. HomePilot uses the whole conversation to understand and clarify the task. Once the task is understood and confirmed, task capture/transcription stop and it executes. |
| Mobile point-and-click | A separate phone/iPhone opens the same household app, points at a product, and takes one photo. No wake phrase or microphone is required. OpenAI coordinates identification through the fine-tuned vision model; the user chooses/confirms the action. This works outside the stationary camera's field of view, with network access to the same backend. |

Both modes are P0. Desktop-first is an implementation sequence, not permission to defer iPhone until after MVP. Native background/locked-screen listening and public multi-household accounts are not part of this browser MVP.

## Supported tasks

| Example | Expected behavior |
| --- | --- |
| "Hey HomePilot, add milk to the list." | Understand milk and the grocery-list action from speech; clarify quantity if needed, confirm the task, stop collection, then add once through runtime MCP. An image match is unnecessary. |
| "Hey HomePilot, when did we last get rice?" | Query the latest recorded inventory-addition event for rice through MCP. Report it as "last added to inventory," not a purchase date. If absent, say no addition is recorded. |
| "Hey HomePilot, show me the grocery list." | Read the complete household grocery list through MCP and display it. No product recognition is necessary. |
| "Hey HomePilot, add this to inventory." | Use relevant captured images and the full conversation to identify the item, clarify quantity, confirm, stop collection, and add it through MCP with a history event. |
| Point phone camera and tap Capture | Submit one image, identify the product, allow correction and action/quantity selection, then apply the confirmed action through the same MCP path. Taking a photo alone does not choose an inventory/list mutation. |

The whole active conversation includes the first command after the wake phrase, follow-up answers, assistant questions, corrections, relevant visual evidence, and actual tool outcomes. It does not require permanent storage of raw audio/video or cross-session conversational memory.

## Recognition and database responsibilities

OpenAI is the LLM orchestrator. It selects a recognition tool, and FastAPI executes that call with the captured image against a fine-tuned Hugging Face model served on AMD ROCm. The recognition result returns as tool evidence. OpenAI then selects allowed runtime MCP tools to retrieve data or carry out a confirmed task. The MCP server validates arguments and accesses PostgreSQL (Supabase is the current default).

Fine-tuning and evaluating the resulting checkpoint are required P0. Exact model/checkpoint and dataset remain open. No accuracy, cost, or speed advantage is assumed. The user remains the authority on product identity and quantity; unknown and correction remain possible.

## Demo story and status

Demonstrate all three named voice examples, a visual "this item" task with a correction, and a separate iPhone one-photo task outside the stationary camera's view. Show the same list/inventory on both devices, a truthful last-added date from stored history, no duplicate writes, and task capture stopping before execution. Test stationary voice mode on both laptop and iPhone.

This is the intended scope. The starter has manual webcam capture and stub services; voice, sessions, OpenAI, fine-tuned inference, MCP tools, and history remain unimplemented. See [MVP_SCOPE.md](MVP_SCOPE.md), [VOICE_CAPTURE.md](VOICE_CAPTURE.md), and [RECOGNITION_DESIGN.md](RECOGNITION_DESIGN.md).
