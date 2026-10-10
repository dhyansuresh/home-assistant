# HomePilot runtime MCP starter

This Python server is for the application's LLM to read and change household inventory and grocery-list data. It is separate from each developer's GitHub MCP connection. It currently starts with **zero tools**, so it cannot pretend a write succeeded before Supabase is connected.

Developer 3 should implement the four allowlisted tools in [`docs/API_CONTRACTS.md`](../../docs/API_CONTRACTS.md), using the reviewed database access path and a trusted `HOME_PILOT_HOUSEHOLD_ID` supplied by the API environment. No tool accepts a household ID from the model. Validate every write and report actual results.

The starter uses the official Python MCP SDK v2 API. After installing `requirements.txt` in a Python 3.11+ environment, `python server.py` starts its stdio transport and waits for an MCP client. It emits no normal output. Connecting it to the agent is a separate integration task.
