# GitHub MCP for coding agents

This is a **developer context** connection. It lets each teammate's agent inspect the current GitHub repository, issues, and PRs. It does not keep agent context synchronized automatically and does not replace fetching current code. HomePilot's **runtime MCP** is the Python server under `services/runtime_mcp`; it is used by the application's LLM for household inventory and grocery-list actions. Do not give the runtime server GitHub credentials or expose developer MCP tools to users.

## Codex example

Each developer configures their own Codex environment. The example file is [`config/codex-github-mcp.example.toml`](../config/codex-github-mcp.example.toml). Copy its table into your **personal** `~/.codex/config.toml` rather than committing a live project `.codex/config.toml`:

```toml
[mcp_servers.github]
url = "https://api.githubcopilot.com/mcp/"
bearer_token_env_var = "GITHUB_PAT_TOKEN"
http_headers = { "X-MCP-Toolsets" = "repos,issues,pull_requests", "X-MCP-Readonly" = "true" }
```

Create a fine-grained GitHub personal access token restricted to the team's repository and the read permissions needed for code, issues, and PRs. Provide it as `GITHUB_PAT_TOKEN` in the environment visible to Codex. Do not paste it into TOML, source files, issue text, screenshots, or a committed `.env`. A desktop app launched outside a terminal may not inherit that terminal's exported variables; check its actual environment/secret setup if the server cannot authenticate. The example is read-only and enables repository, issue, and PR toolsets. Developers can use their agent's native GitHub integration instead if it offers the same scoped, current access.

Verify with `codex mcp list`, then ask Codex to read an issue or PR from the intended repo. Check the result is current, and fetch/pull local code before editing. If the connection fails, consult the current [Codex MCP documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli) and [GitHub MCP Codex installation guide](https://github.com/github/github-mcp-server/blob/main/docs/installation-guides/install-codex.md). GitHub documents [read-only mode and toolsets](https://github.com/github/github-mcp-server/blob/main/docs/server-configuration.md).

## Shared context routine

At task start, read the scope, architecture, assigned issue, and relevant open PRs. At a contract change, update OpenAPI and examples in the PR and request review from affected owners. After merge, fetch current code and reread the changed contract. MCP retrieval is a snapshot of GitHub state, not automatic memory or a substitute for review.
