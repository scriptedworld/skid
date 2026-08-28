# FR-5.2, the client is an MCP server

| ID | Requirement | |
|---|---|---|
| FR-5.2 | The client is an **MCP server**, reached through the standard Anthropic MCP SDK for Python. | [A] |

MCP is how an agent reaches skid at all, and it is what FR-6.1 and FR-8.1 hang
their tools off.

**The row now says exactly what is true, where it used to be arguable.** `skid`
served MCP over HTTP and `skid-mcp` forwarded bytes to it, so the client was an
MCP *client* and the service was the server. Since 2026-08-28 the protocol stops
at `skid-mcp`: it holds the six tool schemas and the dispatch, and what crosses
the socket is plain HTTP. The client is the MCP server, literally.

Nothing about the row changed to make that so, which is why it is not retired.
What changed is which process satisfies it.

**The SDK is the script's dependency alone.** `mcp` is imported by `client.py`
and by nothing the service loads. Two imports left the service with the move,
one of them present only because the SDK answers 421 to an unknown Host header
over a socket no browser can reach.

FACT 2026-08-28: `mcp` 2.1.1, under Python 3.12.14, which is the interpreter
skid runs on.

    .venv/bin/python -c 'import importlib.metadata as m; print(m.version("mcp"))'

The earlier measurement read 2.0.0 under 3.14.7. That is this machine's default
interpreter and not skid's, so it said the SDK exists somewhere rather than that
it is present for this project. FR-1.7 names the same trap.
