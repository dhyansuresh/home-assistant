# Tech stack and open choices

The table describes the current scaffold and the implementation now in place. SQLite currently persists grocery-list tool operations; Supabase remains the scaffold default for inventory and hosting is still under review. The stdio MCP deployment is a starter proposal. See [DECISIONS.md](DECISIONS.md) for confirmed requirements and unresolved choices.

| Layer | Chosen for MVP | Implementation note |
| --- | --- | --- |
| Web UI | Next.js, React, TypeScript | Desktop wake/capture state UI, continuous camera stream with sampled frames, live transcript, confirmation and Stop; stationary laptop/iPhone and separate mobile one-photo mode are P0. |
| Voice input | Wake detection + speech-to-text; implementation/provider open | "Hey HomePilot" is required P0. Test microphone permissions, phrase accuracy, continuous utterances, and stop/recovery on the chosen laptop browser and actual iPhone browser. |
| API | Python FastAPI | Owns voice session state, media/transcript correlation, limits, task confirmation and execution deduplication, validated vision calls, and persistence. |
| Vision | Hugging Face SigLIP2 gallery recognition service | `/internal/recognize` and the FastAPI provider are implemented. Configure the gallery/checkpoint and AMD ROCm device, then fine-tune and evaluate the saved checkpoint as required P0. This is a registered-product recognizer, not a general image captioner or safety classifier. |
| Database | SQLite for grocery list; Supabase Postgres scaffold for inventory | SQLite creates `grocery_list_items` on FastAPI startup. Set `HOME_PILOT_DATABASE_PATH` to a persistent deployment path. Other relational data still follows the Supabase scaffold pending an approved hosting decision. |
| Agent | OpenAI selected for P0; current API adapters are Claude, Gemini, and Ollama | The API selects Claude by default for command validation and grocery-list tool calls; `LLM_PROVIDER=gemini` or `LLM_PROVIDER=ollama` selects an alternative. The documented OpenAI P0 decision has no implementation yet. |
| Runtime tools | Python MCP SDK | Separate HomePilot MCP server for inventory/list tools; stdio in the first integration. |
| Developer context | GitHub repo, issues, PRs, official GitHub MCP server | Each developer configures their own connection. |

OpenAI is the selected LLM provider. Exact OpenAI model, fine-tuned vision checkpoint/dataset, ROCm image, GPU type, and hosting targets remain open. The frontend dependencies are locked in `apps/web/package-lock.json`; use `npm ci` for repeatable installation. Python requirements still use starter ranges. Record the team's tested integration choices in `DECISIONS.md` and lock Python versions when implementation begins. Match the ROCm/PyTorch build to the actual AMD cloud environment; avoid assuming any local laptop can run the GPU service.

The dedicated vision model and LLM coordinator have separate responsibilities and evaluation measures; see [RECOGNITION_DESIGN.md](RECOGNITION_DESIGN.md). OCR and catalog tools are optional P1 extensions, with no selected model or existing integration.

Browser speech recognition has limited compatibility and may use a browser-managed remote service. `continuous` controls repeated recognition results; it does not implement wake detection or task completion. Do not select it as the sole P0 path without a working demo-browser test. A browser-local wake detector plus task-only STT is a proposed starting architecture; models/provider, audio routing, and transport remain open. See [VOICE_CAPTURE.md](VOICE_CAPTURE.md) and its primary references.

## Suggested first technical checks

1. Developer 1 records GPU model, VRAM, ROCm version, PyTorch GPU visibility, model checkpoint/license, and baseline inference time.
2. Developer 2 creates the Supabase project, applies/reviews the migration, and verifies server-side data access through the MCP tool layer, with FastAPI as the client boundary. Add a reviewed inventory-addition event migration for last-added history.
3. Developer 3 chooses an OpenAI model, verifies bounded recognition tool calling and task clarification/confirmation with Developers 1 and 2, and tests Python MCP transport and tool outcomes. With Developer 4, select wake detection and STT and document where audio is processed. A text-only LLM can consume structured vision results; direct image inspection would require a multimodal model and a separate evaluation. No multi-agent framework is required for P0.
4. Developer 4 verifies wake activation, continuous camera capture, speech-to-text, permission errors, Stop, and release of task capture before execution. With Developer 2, verify stale-event rejection and session limits. Test the laptop browser and actual iPhone stationary mode, plus separate phone capture over HTTPS, before P0 passes. Verify shared household data over a reachable private backend.

Useful primary references: [Hugging Face SigLIP2 documentation](https://huggingface.co/docs/transformers/model_doc/siglip2), [PyTorch ROCm installation guidance](https://pytorch.org/get-started/locally/), [Supabase database docs](https://supabase.com/docs/guides/database/overview), [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk).
