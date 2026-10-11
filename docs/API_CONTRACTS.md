# API and runtime tool contracts

The authoritative HTTP schema is [`contracts/openapi.yaml`](../contracts/openapi.yaml). Its examples live in [`contracts/examples`](../contracts/examples). This page explains the behavior shared by the four workstreams; it does not supersede field names in OpenAPI.

## Public client API

| Method and path | Purpose | Owner |
| --- | --- | --- |
| `POST /api/v1/task-sessions` | Start a stationary-voice or mobile-capture task session; creation does not authorize or execute an action. | Backend; review ML + Agent + Frontend |
| `POST /api/v1/recognitions` | Multipart `image` upload; return candidate(s) or unknown, always requiring confirmation. | Backend + ML + Agent |
| `POST /api/v1/inventory/items` | Save a user-confirmed name and quantity. | Backend |
| `GET /api/v1/inventory` | Read household inventory. | Backend |
| `PATCH /api/v1/inventory/items/{item_id}` | Set an existing item's quantity. | Backend |
| `POST /api/v1/agent/chat` | Text request, actual assistant/tool result. | Agent + Backend |
| `GET /api/v1/grocery-list` | Read list. | Backend |
| `POST /api/v1/grocery-list/items` | Add an item. | Backend |

All routes are under the private demo boundary. No browser-provided household ID is accepted. The API uses a server-side `HOME_PILOT_HOUSEHOLD_ID` once connected. Return a structured error for validation, unavailable dependencies, and unfinished routes. `501` in the starter means work remains.

The OpenAPI now defines initial task-session creation and response states; see [`task-session-create.json`](../contracts/examples/task-session-create.json) and [`task-session.json`](../contracts/examples/task-session.json). It does not yet define frame/transcript events, task revisions, confirmation, collection-stopped acknowledgement, cancellation, or deduplicated execution. Those lifecycle contracts still require review before integration.

## Internal vision API

`POST /internal/recognize` accepts the same image and returns the `RecognitionResult` schema. It is called only by FastAPI. The vision service can return zero candidates with `unknown: true`. Every response sets `requires_confirmation: true`; scores are optional raw model ranking signals and never confidence percentages. Developer 1 and 2 must agree on the preprocessing and upload limit before integration.

## Recognition coordinator boundary

FastAPI hosts the coordinator and executes its recognition tool through a backend adapter to `/internal/recognize`. The adapter supplies the already validated image from the current request. It does not expose arbitrary URLs, filesystem paths, household IDs, or inventory writes as scan-tool arguments. This is an internal application tool; it does not require a new MCP server.

The per-image recognition building block keeps its existing HTTP schema; the required P0 voice-session flow needs additional schemas. On acceptance, return the vision candidate fields, order, scores, and vision `model_id` unchanged. On coordinator abstention, retain the correlation/model IDs, set `unknown: true`, and return no candidates. Never turn a vision unknown into an unsupported known product. Always retain `requires_confirmation: true`. Record the coordinator model/version separately in evaluation traces; it does not replace the vision `model_id`.

There is no `retake_reason`, evidence bundle, or catalog product ID in the current response. The UI offers generic retake/manual entry for unknown; adding richer messages, OCR evidence, reranked candidates, or multiple model provenance requires a reviewed contract change. Dependency/tool failures use the documented error response (503 publicly for an unavailable dependency), not a fabricated successful prediction. See [RECOGNITION_DESIGN.md](RECOGNITION_DESIGN.md).

## Runtime MCP tools planned for P0

These names are the planned implementation contract for Developer 3; the new addition/history tool payloads need review with Developer 2; the current starter MCP process registers no tools. They are **application** tools, unrelated to GitHub MCP.

| Tool | Input | Result / rule |
| --- | --- | --- |
| `add_inventory_item` | Confirmed product fields, quantity, server-bound task revision/deduplication key; exact schema pending review | Add inventory and an addition event atomically. Require validated confirmation and return actual saved result. |
| `get_last_inventory_addition` | Validated item reference or search term; exact schema pending review | Latest matching addition event with timestamp, no-history, or ambiguity result; no inferred purchase date. |
| `get_inventory` | none | Array of inventory items for trusted demo household. |
| `set_inventory_quantity` | item ID, positive integer quantity | Updated item or explicit error. Cannot choose household. |
| `get_grocery_list` | none | Array of current grocery-list items. |
| `add_grocery_list_item` | name, positive integer quantity | Persisted list item or explicit error. |

The orchestrator first validates the request without tools. For a valid request it exposes `get_grocery_list` and `add_grocery_list_item` to the LLM, validates the selected function and arguments server-side, and calls the matching allowlisted runtime MCP tool. The MCP server validates writes and executes them against SQLite. The actual tool result is returned to the LLM for its response. A tool call is limited to one operation per request. FastAPI creates the SQLite table during startup; configure `HOME_PILOT_DATABASE_PATH` to a persistent disk path in deployments.

The scanned-product `POST /api/v1/inventory/items` route remains user-confirmed; FastAPI must delegate to the same validated MCP addition tool used by the coordinator. This supersedes the former direct-write plan; implementation is pending. The LLM cannot bypass confirmation by choosing a tool. A confirmed voice task may supply that item confirmation only when it explicitly includes identity and quantity. Collecting/clarifying voice sessions cannot invoke mutation tools; confirmed tasks execute only after collection has stopped. The agent may read inventory and manage quantity/list through the allowlisted MCP tools. For every tool, validate inputs server-side, use the trusted household context, and distinguish a tool failure from a successful mutation in the final assistant text.

## Required voice-session contract work

See [VOICE_CAPTURE.md](VOICE_CAPTURE.md). This is an implementation handoff, not an implemented endpoint list. Developer 2 owns the OpenAPI/transport PR with Developers 1, 3, and 4. Define and provide examples for:

- Session creation and state, server-issued session/task IDs, explicit supported action and required arguments, and one active session per client.
- Frame sequence/capture timestamps and recognition references; audio format/chunk order if STT is server-side; transcript sequence/revision and partial-versus-final status.
- Active conversation ID and ordered turns (user, assistant, corrections and tool results), context lifetime, and first-utterance handoff after wake; clients must not share conversation state merely because they share a household.
- Task draft revisions, clarification prompts, product/quantity evidence, and confirmation tied to the exact displayed revision. A partial transcript, silence, or wake event cannot confirm.
- A collection-stopped acknowledgement that gates execution after the client stops task media/STT; stale updates and confirmations must be rejected. A disconnect before this acknowledgement must not execute.
- Cancellation, expiry, dependency errors, request/frame/audio size limits, timeouts, and actual execution success/failure.
- An execution deduplication key bound to session/task revision, plus retry/status semantics that cannot repeat a write after lost acknowledgements. Apply this to inventory writes and MCP actions.

Choose REST/polling, SSE, or WebSocket according to the selected STT path and demonstrate the lifecycle before adding transport complexity. Until that contract lands, frontend fixtures must be marked simulated. Existing `/api/v1/agent/chat` can trigger actions and must not receive interim or unconfirmed voice transcripts. The internal vision service can continue accepting one image per inference; the backend session adapter owns correlation and limits.

## Required inventory-addition history

"When did we last get rice?" means **last added to inventory**, confirmed by the owner. The current migration has only item creation/update timestamps and no addition history; it cannot reliably answer repeated additions.

Developer 2 must add a reviewed event schema/migration, atomically written by the inventory-addition tool. Record trusted household ID, stable item reference, quantity added, server-recorded timestamp, and deduplication identity. Keep events when stock later changes; a quantity correction or grocery-list addition must not count as new stock. Do not infer an addition from arbitrary `updated_at` changes. Matching multiple rice products must return ambiguity for clarification; no event must return no history. Report timestamp/timezone clearly. Purchase dates, backdated events, and receipt ingestion are not implied.

Use the same MCP validation/persistence layer for assistant tasks and existing UI data endpoints. Inventory/list reads, history lookup, and confirmed mutations must agree across stationary and mobile clients. A mobile capture requires its own task/confirmation context and can run without a stationary voice session. Exact tool schemas, response examples, and event migration remain implementation work; no history table or live tools are added by this documentation update.

## Contract change rule

Change OpenAPI, examples, and affected code in one PR. Ask the producer and each consumer to review it. If the public and internal vision shapes diverge later, document the mapping rather than guessing it in each client.
