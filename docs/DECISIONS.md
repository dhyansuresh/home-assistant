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
<<<<<<< Updated upstream
| D-008 | Open | Exact SigLIP2/ViT checkpoint, training approach, and whether fine-tuning improves the baseline. | Developer 1 should bring GPU compatibility and fresh-image evaluation evidence. |
| D-009 | Open | LLM provider/model and deployment targets. | Agent and backend owners should choose one tested path. |
=======
| D-008 | Open details; fine-tuning required by D-018 | Exact SigLIP2/ViT checkpoint, dataset and training approach; measure whether fine-tuning improves the baseline. | Developer 1 should bring GPU compatibility and fresh-image evaluation evidence. |
| D-009 | Superseded by D-020 | OpenAI is the LLM provider; exact model and deployment targets remain open. | Owner selected OpenAI in the scope clarification. |
>>>>>>> Stashed changes
| D-010 | Open | Authentication and authorization for a public release. | The starter does not implement an account system. |
| D-011 | Confirmed requirement | Desktop webcam is the first capture source; iPhone follows after the desktop flow works. | Project owner, 2026-10-10. Makes testing convenient for everyone. A USB Brio attached to a computer is part of this step; robot integration comes later. |
| D-012 | Under review | Supabase is the original database-hosting choice and current scaffold default; another PostgreSQL server is being considered. | Project owner asked about PostgreSQL versus Supabase. Final hosting choice remains open after that discussion. |
| D-013 | Confirmed requirement | Next.js UI, FastAPI backend, Hugging Face SigLIP2/ViT on AMD ROCm, and an LLM agent with Python runtime MCP. | Project owner's original stack request. Exact models and deployment details remain open as recorded above. |
<<<<<<< Updated upstream
=======
| D-014 | Confirmed requirement | Use a dedicated Hugging Face vision model for visual evidence and one LLM coordinator to orchestrate recognition tools. Establish a direct vision baseline first; additional specialist tools/agents are incremental extensions. | Project owner, 2026-10-10, explicitly requested documenting this method after discussing its rationale. Enables independent training, evaluation, and deployment of recognition. Accuracy, speed, and cost advantages require measurement. See [RECOGNITION_DESIGN.md](RECOGNITION_DESIGN.md). This records intended architecture, not a working integration. |
| D-015 | Confirmed requirement | P0 must activate the webcam on "Hey HomePilot" and continuously capture frames and transcribe speech until the task is understood and confirmed; stop task capture/transcription before execution. | Project owner, 2026-10-10, requested this and explicitly chose "Stop when the task is understood and confirmed." Supersedes the earlier manual-only capture rule and P1/excluded status of wake/STT. Desktop microphone software is P0; Raspberry Pi and robot audio remain P2. See [VOICE_CAPTURE.md](VOICE_CAPTURE.md). |
| D-016 | Open | Wake detector, speech-to-text model/provider and processing location, demo browser, session transport, frame rate, and session/call limits. | Developers 2/3/4 with ML input must validate and record one working path. Proposed defaults in VOICE_CAPTURE.md are not confirmed implementation choices. Current OpenAPI does not yet cover voice-session lifecycle. |
| D-017 | Confirmed requirement | Two P0 modes: stationary laptop/iPhone wake conversation and separate phone/iPhone one-photo point-and-click without voice. Both share household data. | Owner scope clarification, 2026-10-10. Retain full active conversation, including follow-ups. Supersedes iPhone-as-P1; continuous capture applies to stationary sessions, one image per tap to mobile mode. |
| D-018 | Superseded by D-020 | OpenAI orchestrates a fine-tuned Hugging Face vision model and uses application runtime MCP for database reads/writes, including identified-product additions. | Owner scope clarification, 2026-10-10. |
| D-019 | Confirmed requirement | "When did we last get rice?" means the last recorded inventory addition. | Owner explicitly selected "Last added to inventory," 2026-10-10. Requires persisted addition history and a lookup tool; current item timestamps alone are insufficient. No purchase-date tracking is implied. |
| D-020 | Confirmed requirement | The orchestrator consumes a provider-neutral LLM interface for conversation turns and function calls. Gemini is the initial provider implementation; backend code validates and executes proposed function calls. | Project owner requested a reusable interface for the separate orchestrator, 2026-10-10. Supersedes D-009 and the provider choice in D-018; other D-018 requirements remain. |
>>>>>>> Stashed changes
