# HomePilot runtime MCP starter

This Python server is for the application's LLM to read and change household inventory and grocery-list data, and answer last-added history questions. It is separate from each developer's GitHub MCP connection. It currently provides the grocery-list read and add tools backed by SQLite; inventory and last-added history tools are not implemented.

The API launches this server over stdio for grocery-list tool calls. Both FastAPI and this MCP server use `HOME_PILOT_DATABASE_PATH`; FastAPI creates the table at startup and the server also ensures it exists. Set this variable to a persistent deployment path. No tool accepts a household ID from the model. Validate every write and report actual results.

The server uses the official Python MCP SDK v2 API. After installing `requirements.txt` in a Python 3.11+ environment, `python server.py` starts its stdio transport and waits for an MCP client. FastAPI launches it as a subprocess when the orchestrator invokes a grocery-list tool. It emits no normal output on stdout because that stream carries MCP messages.

To check the SQLite grocery-list tools without starting FastAPI or using the production database, install the API requirements and run `python scripts/grocery_list_mcp.py` from `services/api`. The script uses a temporary database and checks initialization, reads, writes, persistence, and blank-name rejection.

The confirmed design routes assistant-selected database reads/writes through this tool layer, including identified products from either capture mode. Grocery-list actions use SQLite for now. Inventory addition and history still require their reviewed persistence and event-history work before those tools can be claimed.
