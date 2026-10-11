# HomePilot runtime MCP starter

This Python server is for the application's LLM to read and change household inventory and grocery-list data, and answer last-added history questions. It is separate from each developer's GitHub MCP connection. It currently starts with **zero tools**, so it cannot pretend a write succeeded before Supabase is connected.

Developer 3 should implement the planned allowlisted tools (including inventory addition and last-added history) in [`docs/API_CONTRACTS.md`](../../docs/API_CONTRACTS.md), using the reviewed database access path and a trusted `HOME_PILOT_HOUSEHOLD_ID` supplied by the API environment. No tool accepts a household ID from the model. Validate every write and report actual results.

The starter uses the official Python MCP SDK v2 API. After installing `requirements.txt` in a Python 3.11+ environment, `python server.py` starts its stdio transport and waits for an MCP client. It emits no normal output. Connecting it to the agent is a separate integration task.

The confirmed design routes assistant-selected database reads/writes through this tool layer, including identified products from either capture mode. Addition tools must atomically record inventory-addition events and deduplicate retries. The current migration has no event history; coordinate its addition with Developer 2 before claiming history queries work.
