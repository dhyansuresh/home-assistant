# Tech stack and open choices

The table describes the current scaffold. Supabase remains the database default while hosting is under review. The stdio MCP deployment is a starter proposal. See [DECISIONS.md](DECISIONS.md) for confirmed requirements and unresolved choices.

| Layer | Chosen for MVP | Implementation note |
| --- | --- | --- |
| Web UI | Next.js, React, TypeScript | Desktop webcam preview/snapshot via `getUserMedia`, image-file fallback, then iPhone capture; browser uses FastAPI only. |
| API | Python FastAPI | Validates requests, calls vision, coordinates agent, owns persistence boundary. |
| Vision | Hugging Face SigLIP2 or ViT with PyTorch on AMD ROCm | Establish a baseline on the actual allocated GPU before fine-tuning. |
| Database | Supabase Postgres | Server-side access for one demo household; SQL migration under version control. |
| Agent | One LLM provider selected by Developer 3 | Provider and model are open choices; keep credentials server-side. |
| Runtime tools | Python MCP SDK | Separate HomePilot MCP server for inventory/list tools; stdio in the first integration. |
| Developer context | GitHub repo, issues, PRs, official GitHub MCP server | Each developer configures their own connection. |

No exact model checkpoint, ROCm image, GPU type, LLM provider, or hosting vendor is selected by this foundation. The frontend dependencies are locked in `apps/web/package-lock.json`; use `npm ci` for repeatable installation. Python requirements still use starter ranges. Record the team's tested integration choices in `DECISIONS.md` and lock Python versions when implementation begins. Match the ROCm/PyTorch build to the actual AMD cloud environment; avoid assuming any local laptop can run the GPU service.

## Suggested first technical checks

1. Developer 1 records GPU model, VRAM, ROCm version, PyTorch GPU visibility, model checkpoint/license, and baseline inference time.
2. Developer 2 creates the Supabase project, applies/reviews the migration, and verifies server-side access from FastAPI only.
3. Developer 3 chooses one LLM provider and verifies the Python MCP SDK transport and tool result handling with fixtures before connecting persistence.
4. Developer 4 verifies webcam preview, snapshot, permission errors, and Stop on a development computer, then confirms JPEG upload format/size with Developer 2. Validate on localhost or HTTPS. After desktop integration, test iPhone capture over HTTPS.

Useful primary references: [Hugging Face SigLIP2 documentation](https://huggingface.co/docs/transformers/model_doc/siglip2), [PyTorch ROCm installation guidance](https://pytorch.org/get-started/locally/), [Supabase database docs](https://supabase.com/docs/guides/database/overview), [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk).
