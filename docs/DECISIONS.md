# Decisions and proposals

This log gives teammates and their coding agents a shared record of what was requested, why the starter was shaped this way, and what still needs a decision. An entry does not imply the feature is implemented.

The original starter mixed explicit project requirements with choices proposed by the assistant and labeled both "Accepted." That overstated team approval. The statuses below correct that distinction as of 2026-10-10.

- **Confirmed requirement:** explicitly requested by the project owner in this conversation.
- **Starter proposal:** an assistant-selected default reflected in the current files, pending team review. It can change; update affected docs, contracts, and code together.
- **Open / Under review:** a choice that has not been finalized.

When the team accepts or changes a proposal, record the date, decision maker, reason, and affected components. Agents must not promote a proposal to a confirmed team decision without evidence of that decision.

| ID | Status | Choice | Source / reason / consequence |
| --- | --- | --- | --- |
| D-001 | Confirmed requirement | Software-first MVP; Raspberry Pi robot work follows the software MVP. Development-computer webcams are in scope. | Project owner's original brief and webcam-first revision. |
| D-002 | Confirmed requirement | Shared repository foundation with `AGENTS.md`, `CLAUDE.md`, project docs, contracts, and GitHub templates for four developers using mixed agents. | Project owner's foundation request. Provides common project context. |
| D-003 | Confirmed requirement | Developer GitHub MCP and the application's Python runtime MCP are separate systems. | Project owner explicitly requested this distinction. Their credentials and available actions stay separate. |
| D-004 | Starter proposal | One private demo household selected by server configuration. | Assistant proposed reducing initial account-management work. Team must decide authentication and access control before public access. |
| D-005 | Starter proposal | User confirms or edits scanned products before inventory is written. | Assistant proposed protection against wrong or unknown model predictions. This is reflected in the current contract and acceptance criteria. |
| D-006 | Starter proposal | OpenAPI defines the HTTP contract; versioned SQL migrations define persistence. | Assistant selected these formats for consistent handoffs between the four workstreams. |
| D-007 | Starter proposal | Run runtime MCP over stdio beside the API/agent for the first integration. | Assistant selected a simple local transport. Team should review it against the actual deployment plan. |
| D-008 | Open | Exact SigLIP2/ViT checkpoint, training approach, and whether fine-tuning improves the baseline. | Developer 1 should bring GPU compatibility and fresh-image evaluation evidence. |
| D-009 | Open | LLM provider/model and deployment targets. | Agent and backend owners should choose one tested path. |
| D-010 | Open | Authentication and authorization for a public release. | The starter does not implement an account system. |
| D-011 | Confirmed requirement | Desktop webcam is the first capture source; iPhone follows after the desktop flow works. | Project owner, 2026-10-10. Makes testing convenient for everyone. A USB Brio attached to a computer is part of this step; robot integration comes later. |
| D-012 | Under review | Supabase is the original database-hosting choice and current scaffold default; another PostgreSQL server is being considered. | Project owner asked about PostgreSQL versus Supabase. Final hosting choice remains open after that discussion. |
| D-013 | Confirmed requirement | Next.js UI, FastAPI backend, Hugging Face SigLIP2/ViT on AMD ROCm, and an LLM agent with Python runtime MCP. | Project owner's original stack request. Exact models and deployment details remain open as recorded above. |
