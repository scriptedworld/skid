"""The tool surface, named once so two components cannot disagree about it.

After the MCP server moved into the stdio script, the script owns the tool
schemas and the service owns the implementations. That split is worth having,
because it takes the session state a restart invalidates out of the picture
entirely, but it introduces a failure mode that did not exist when one module
held both: a tool added on one side and not the other.

**This is the one declaration, and both sides derive from it.** The script builds
its requests from these routes and the service registers exactly these paths, so
the set cannot drift. `tests/test_routes.py` asserts the two agree, which is what
turns "cannot drift" from an intention into something that fails.

Schemas stay with the decorated functions in `client.py` rather than being
restated here. A JSON schema written twice is the drift this module exists to
prevent, and the SDK derives one from the signature that is already there.

Nothing here imports `mcp`, `flask` or `skid.service`. It is read by the script,
which has the SDK and no service, and by the service, which has neither the SDK
nor stdio.
"""

from __future__ import annotations

ROUTES: dict[str, tuple[str, str]] = {
    "speak": ("POST", "/speak"),
    "set_voice": ("POST", "/voice"),
    "add_substitution": ("POST", "/substitutions"),
    "remove_substitution": ("POST", "/substitutions/remove"),
    "list_substitutions": ("GET", "/substitutions"),
    "status": ("GET", "/status"),
}
"""Every tool, and the HTTP method and path that carries it.

`remove_substitution` is a POST to its own path rather than a DELETE on
`/substitutions`, because it identifies an entry by a pattern and a kind
together and a body on a DELETE is poorly specified and worse supported.

The two reads are GETs so that a proxy, a log or a person with `curl` can tell
them apart from the four that change something.
"""

RESULT = "result"
"""The member carrying a successful answer, so an empty one is still a shape."""

ERROR = "error"
"""The member carrying a refusal, which the script turns back into a tool error.

Present only on a 4xx or 5xx. A caller reads the status first and this second,
which is the lesson `client.py` learnt the expensive way: a transport that
succeeded says nothing about whether the request did.
"""


def method_and_path(tool: str) -> tuple[str, str]:
    """How to reach `tool`, raising rather than inventing a route for a typo."""
    try:
        return ROUTES[tool]
    except KeyError:
        raise KeyError(f"no route declared for tool {tool!r}") from None
