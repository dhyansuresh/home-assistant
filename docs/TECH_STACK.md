# Tech stack and open choices

The table describes the current scaffold. Supabase remains the database default while hosting is under review. The stdio MCP deployment is a starter proposal. See [DECISIONS.md](DECISIONS.md) for confirmed requirements and unresolved choices.

| Layer | Chosen for MVP | Implementation note |
| --- | --- | --- |
| Web UI | Next.js, React, TypeScript | Desktop webcam preview/snapshot via `getUserMedia`, image-file fallback, then iPhone capture; browser uses FastAPI only. |
| API | Python FastAPI | Validates requests, calls vision, coordinates agent, owns persistence boundary. |
| Vision | Hugging Face SigLIP2 or ViT with PyTorch on AMD ROCm | Establish a baseline on the actual allocated GPU before fine-tuning. |
| Database | Supabase Postgres | Server-side access for one demo household; SQL migration under version control. |
<<<<<<< Updated upstream
| Agent | One LLM provider selected by Developer 3 | Provider and model are open choices; keep credentials server-side. |
| Runtime tools | Python MCP SDK | Separate HomePilot MCP server for inventory/list tools; stdio in the first integration. |
| Developer context | GitHub repo, issues, PRs, official GitHub MCP server | Each developer configures their own connection. |

No exact model checkpoint, ROCm image, GPU type, LLM provider, or hosting vendor is selected by this foundation. The frontend dependencies are locked in `apps/web/package-lock.json`; use `npm ci` for repeatable installation. Python requirements still use starter ranges. Record the team's tested integration choices in `DECISIONS.md` and lock Python versions when implementation begins. Match the ROCm/PyTorch build to the actual AMD cloud environment; avoid assuming any local laptop can run the GPU service.
=======
| Agent | Provider-neutral Python interface in `services/api/app/llm_interface.py`; Gemini adapter in `services/api/app/gemini.py` | Common message, function-definition, and response types for the separate orchestrator. Gemini is the initial provider; the agent loop is not implemented. |
| Runtime tools | Python MCP SDK | Separate HomePilot MCP server for inventory/list tools; stdio in the first integration. |
| Developer context | GitHub repo, issues, PRs, official GitHub MCP server | Each developer configures their own connection. |

The orchestrator uses a provider-neutral interface, with Gemini as the initial provider. The exact Gemini model, fine-tuned vision checkpoint/dataset, ROCm image, GPU type, and hosting targets remain open. The frontend dependencies are locked in `apps/web/package-lock.json`; use `npm ci` for repeatable installation. Python requirements still use starter ranges. Record the team's tested integration choices in `DECISIONS.md` and lock Python versions when implementation begins. Match the ROCm/PyTorch build to the actual AMD cloud environment; avoid assuming any local laptop can run the GPU service.

The dedicated vision model and LLM coordinator have separate responsibilities and evaluation measures; see [RECOGNITION_DESIGN.md](RECOGNITION_DESIGN.md). OCR and catalog tools are optional P1 extensions, with no selected model or existing integration.

Browser speech recognition has limited compatibility and may use a browser-managed remote service. `continuous` controls repeated recognition results; it does not implement wake detection or task completion. Do not select it as the sole P0 path without a working demo-browser test. A browser-local wake detector plus task-only STT is a proposed starting architecture; models/provider, audio routing, and transport remain open. See [VOICE_CAPTURE.md](VOICE_CAPTURE.md) and its primary references.
>>>>>>> Stashed changes

## Suggested first technical checks

1. Developer 1 records GPU model, VRAM, ROCm version, PyTorch GPU visibility, model checkpoint/license, and baseline inference time.
<<<<<<< Updated upstream
2. Developer 2 creates the Supabase project, applies/reviews the migration, and verifies server-side access from FastAPI only.
3. Developer 3 chooses one LLM provider and verifies the Python MCP SDK transport and tool result handling with fixtures before connecting persistence.
4. Developer 4 verifies webcam preview, snapshot, permission errors, and Stop on a development computer, then confirms JPEG upload format/size with Developer 2. Validate on localhost or HTTPS. After desktop integration, test iPhone capture over HTTPS.
=======
2. Developer 2 creates the Supabase project, applies/reviews the migration, and verifies server-side data access through the MCP tool layer, with FastAPI as the client boundary. Add a reviewed inventory-addition event migration for last-added history.
3. Developer 3 chooses a Gemini model, verifies bounded recognition tool calling and task clarification/confirmation with Developers 1 and 2, and tests Python MCP transport and tool outcomes. With Developer 4, select wake detection and STT and document where audio is processed. A text-only LLM can consume structured vision results; direct image inspection would require a multimodal model and a separate evaluation. No multi-agent framework is required for P0.
4. Developer 4 verifies wake activation, continuous camera capture, speech-to-text, permission errors, Stop, and release of task capture before execution. With Developer 2, verify stale-event rejection and session limits. Test the laptop browser and actual iPhone stationary mode, plus separate phone capture over HTTPS, before P0 passes. Verify shared household data over a reachable private backend.
>>>>>>> Stashed changes

Useful primary references: [Hugging Face SigLIP2 documentation](https://huggingface.co/docs/transformers/model_doc/siglip2), [PyTorch ROCm installation guidance](https://pytorch.org/get-started/locally/), [Supabase database docs](https://supabase.com/docs/guides/database/overview), [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk).
