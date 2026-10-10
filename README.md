# HomePilot

HomePilot is a software-first grocery assistant for a four-person hackathon team. The planned MVP lets someone capture a grocery product with a laptop or USB webcam in a desktop browser, confirm its identity, save it to household inventory, and use a text assistant to manage a grocery list. The computer vision service runs on the team's AMD ROCm GPU; Supabase stores inventory and list data. The assistant uses a separate Python runtime MCP server for household actions.

**Current state:** this repository is a project foundation, not a working end-to-end app. The web page supports webcam preview, single-frame JPEG capture, and image-file selection. iPhone capture is the next interface milestone after the desktop flow works. The API and vision service expose health checks and return `501 Not Implemented` for planned operations. The runtime MCP process has no tools yet. No model, LLM provider, Supabase project, or deployment is connected.

## Read first

1. [MVP scope](docs/MVP_SCOPE.md) and [product brief](docs/PRODUCT.md)
2. [Architecture](docs/ARCHITECTURE.md) and [API contracts](docs/API_CONTRACTS.md)
3. [Team ownership](docs/TEAM.md) and [decisions](docs/DECISIONS.md)
4. [Agent instructions](AGENTS.md) for Codex and other agents; Claude Code also reads [CLAUDE.md](CLAUDE.md)

The API source of truth is [contracts/openapi.yaml](contracts/openapi.yaml). The database starter migration is [supabase/migrations/0001_initial.sql](supabase/migrations/0001_initial.sql).

The [decision log](docs/DECISIONS.md) distinguishes your confirmed requirements from starter proposals awaiting team review. The private single-household demo and stdio MCP transport are proposed defaults. Supabase is the current database default while the team considers other PostgreSQL hosting options.

## Repository map

| Path | Purpose | Initial owner |
| --- | --- | --- |
| `apps/web` | Next.js desktop webcam UI; iPhone capture follows | Developer 4, frontend |
| `services/api` | FastAPI client API, validation, orchestration, Supabase access | Developer 2, backend |
| `services/vision` | ROCm model inference API and evaluation work | Developer 1, ML |
| `services/runtime_mcp` | Python MCP tools used by the HomePilot agent | Developer 3, agent |
| `contracts` | Shared API schema and sample payloads | Developer 2, with all consumers reviewing |
| `supabase` | SQL migrations | Developer 2, with Developer 3 reviewing tool needs |
| `docs` | Shared product and technical decisions | All four |

## Local setup for the starter

Prerequisites: Node.js/npm, Python 3.11+, and Docker only if you choose the optional local GitHub MCP route. Use team-approved runtime versions when implementing integrations; [TECH_STACK.md](docs/TECH_STACK.md) records choices still open.

```bash
cd apps/web
npm ci
npm run dev
```

Open `http://localhost:3000` on your computer. Click **Start webcam**, allow camera access, hold up an item, and click **Capture photo**. Use **Stop webcam** when finished, or select an image file as a fallback. A built-in camera or USB webcam (including a Brio attached to the development computer) can be used; choose the intended device through your browser camera settings. The starter only captures and previews locally. Browser webcam access requires localhost or HTTPS; see [MDN camera access guidance](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia). After the desktop flow passes, test iPhone capture from an HTTPS URL the phone can reach.

In another terminal:

```bash
cd services/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Check `http://localhost:8000/health`. The generated `/docs` page shows only starter routes; use `contracts/openapi.yaml` for the intended API. Planned routes return 501 until their assigned developer implements them. The separate vision stub can be started from `services/vision` with its own `requirements.txt` and `uvicorn app.main:app --reload --port 8001`.

Secrets go in local, ignored `.env` files or each developer's secret manager. The sample [`.env.example`](.env.example) lists server-side settings only. **Never expose the Supabase service role key or an LLM key to the browser.** The repository does not load these settings yet.

## Day one: four parallel tracks

1. As a team, assign the four owners in [TEAM.md](docs/TEAM.md), create a private GitHub repository, protect `main`, and agree on one demo household and a small recognition test set. After applying the SQL migration in a disposable Supabase project, create the demo household with `insert into public.households (name) values ('Hackathon demo') returning id;` and keep the returned ID in server-side configuration. Use issues and PRs for changes to shared contracts.
2. Developer 2 opens the first contract and migration PR. All four review the field names, unknown-product behavior, and confirmation flow before implementing clients.
3. Developer 1 verifies the actual AMD GPU/ROCm/PyTorch environment, then implements `/internal/recognize` against the agreed response shape. Record model version, test images, latency, and unknown results.
4. Developer 3 implements the runtime MCP inventory/list tools and one LLM provider path. Start with in-memory fixtures while the database contract is reviewed, then replace them with the approved Supabase access path.
5. Developer 4 builds desktop webcam capture first, then the confirmation, inventory, grocery list, and chat views against sample responses in `contracts/examples`; swap to the live API as routes land.
6. Integrate in this order: webcam snapshot → candidate; confirm → inventory; chat → MCP tool → persisted grocery list. Rehearse the complete desktop flow, then adapt capture and layout for iPhone using the same image-upload contract.

Each person can use Codex, Claude Code, Cursor, or another coding agent. Agents should read repository docs and the assigned issue on each task; [GitHub MCP setup](docs/DEVELOPMENT_MCP.md) provides live GitHub context but does not synchronize local files or agent memory.

## Working agreement

- Create an issue with owner, acceptance criteria, and dependencies before substantial work.
- Use short-lived branches and PRs. Schema, migration, security boundary, or endpoint changes require review from affected owners.
- Update `contracts/openapi.yaml`, examples, and relevant docs in the same PR as a contract change.
- Run the checks relevant to changed code. For the starter, `python3 -m compileall services` and `python3 -m json.tool contracts/examples/recognition-unknown.json` are dependency-free checks; see [validation](docs/TEAM.md#review-and-validation).
- A 501 response is an explicit unfinished endpoint, not a successful integration.

## After MVP

Only after the complete software workflow is stable should the team prioritize the Raspberry Pi Zero 2 W, its Logitech Brio integration, KLYSTR SPI LCD, audio, and 3D printed enclosure. These robot components are listed in [MVP_SCOPE.md](docs/MVP_SCOPE.md) as post-MVP work and have no current service dependency. Using a webcam on a development computer is part of the initial software work.
