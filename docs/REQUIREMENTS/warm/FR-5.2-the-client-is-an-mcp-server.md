# FR-5.2, the client is an MCP server

| ID | Requirement | |
|---|---|---|
| FR-5.2 | The client is an **MCP server**, reached through the standard Anthropic MCP SDK for Python. | [A] |

MCP is how an agent reaches skid at all, and it is what FR-6.1 and FR-8.1 hang
their tools off.

FACT 2026-08-27: the SDK is installed, `mcp` 2.0.0, under Python 3.14.7.

    python3 -m pip show mcp
