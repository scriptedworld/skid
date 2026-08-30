# FR-5.2, the client is an MCP server

| ID | Requirement | |
|---|---|---|
| FR-5.2 | The client is an **MCP server**, reached through the standard Anthropic MCP SDK for Python. | [A] |

MCP is how an agent reaches skid at all, and it is what FR-6.1 and FR-8.1 hang
their tools off.

The protocol stops at `skid-mcp`, which holds the six tool schemas and the
dispatch, and what crosses the socket to the service is plain HTTP. So the
client is the MCP server, literally rather than by reading.

The SDK is the script's dependency alone: `mcp` is imported by `client.py` and
by nothing the service loads.

    .venv/bin/python -c 'import importlib.metadata as m; print(m.version("mcp"))'
    2.1.1

Ask skid's own interpreter rather than the machine's. `python3` here is 3.14.7
and carries a different `mcp`, so asking it says the SDK exists somewhere rather
than that it is present for this project. FR-1.7 names the same trap.
