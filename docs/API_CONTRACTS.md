# API and runtime tool contracts

The authoritative HTTP schema is [`contracts/openapi.yaml`](../contracts/openapi.yaml). Its examples live in [`contracts/examples`](../contracts/examples). This page explains the behavior shared by the four workstreams; it does not supersede field names in OpenAPI.

## Public client API

| Method and path | Purpose | Owner |
| --- | --- | --- |
| `POST /api/v1/recognitions` | Multipart `image` upload; return candidate(s) or unknown, always requiring confirmation. | Backend + ML |
| `POST /api/v1/inventory/items` | Save a user-confirmed name and quantity. | Backend |
| `GET /api/v1/inventory` | Read household inventory. | Backend |
| `PATCH /api/v1/inventory/items/{item_id}` | Set an existing item's quantity. | Backend |
| `POST /api/v1/agent/chat` | Text request, actual assistant/tool result. | Agent + Backend |
| `GET /api/v1/grocery-list` | Read list. | Backend |
| `POST /api/v1/grocery-list/items` | Add an item. | Backend |

All routes are under the private demo boundary. No browser-provided household ID is accepted. The API uses a server-side `HOME_PILOT_HOUSEHOLD_ID` once connected. Return a structured error for validation, unavailable dependencies, and unfinished routes. `501` in the starter means work remains.

Webcam and later iPhone capture both submit a single still image in the multipart `image` field. The webcam preview stays in the browser; no video stream is sent to the backend. This source change requires no HTTP schema change.

## Internal vision API

`POST /internal/recognize` accepts the same image and returns the `RecognitionResult` schema. It is called only by FastAPI. The vision service can return zero candidates with `unknown: true`. Every response sets `requires_confirmation: true`; scores are optional raw model ranking signals and never confidence percentages. Developer 1 and 2 must agree on the preprocessing and upload limit before integration.

## Runtime MCP tools planned for P0

These names are an implementation contract for Developer 3; the current starter MCP process registers no tools. They are **application** tools, unrelated to GitHub MCP.

| Tool | Input | Result / rule |
| --- | --- | --- |
| `get_inventory` | none | Array of inventory items for trusted demo household. |
| `set_inventory_quantity` | item ID, positive integer quantity | Updated item or explicit error. Cannot choose household. |
| `get_grocery_list` | none | Array of current grocery-list items. |
| `add_grocery_list_item` | name, positive integer quantity | Persisted list item or explicit error. |

The scanned-product `POST /inventory/items` route is user-confirmed and goes through FastAPI, not through an LLM-selected write. The agent may read inventory and manage quantity/list through the allowlisted MCP tools. For every tool, validate inputs server-side, use the trusted household context, and distinguish a tool failure from a successful mutation in the final assistant text.

## Contract change rule

Change OpenAPI, examples, and affected code in one PR. Ask the producer and each consumer to review it. If the public and internal vision shapes diverge later, document the mapping rather than guessing it in each client.
