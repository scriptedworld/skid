"""The tool surface, named once so two components cannot disagree about it.

The MCP server lives in the stdio script, so the script owns the tool schemas
and the service owns the implementations. The split takes the session state a
restart invalidates out of the picture entirely, and it introduces a failure
mode that one module holding both could not have: a tool added on one side and
not the other.

This is the one declaration, and both sides derive from it. The script builds
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

from typing import Any

MESSAGE_CHARS = 1000
"""Characters one message may carry, refused above it.

A message becomes one clip, and a clip is what the player's own bound applies
to. At about 15.5 characters per second of audio this is roughly 65 seconds of
speech, inside `player.DEFAULT_TIMEOUT` of 300 seconds with a margin of four and
a half, so a message that passes here cannot be the one that gets cut off.

The quantity is characters of a single message, not of a submission. An array is
spoken as one submission and may be as long as the caller likes; each element is
its own clip and each is bounded.

Chosen rather than measured. The intent is that a caller sends a paragraph at a
time, and four paragraphs are four messages or four calls, so this is set high
enough to pass any real paragraph and low enough to refuse a wall of text. A
number derived from the timeout instead would be about 4,660, which is the point
at which speech is silently truncated, and setting a limit at the failure it
exists to prevent leaves no margin at all.
"""

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

SCHEMAS: dict[str, dict[str, Any]] = {
    "speak": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "minLength": 1},
            "messages": {
                "type": "array",
                "items": {"type": "string", "maxLength": MESSAGE_CHARS},
                "minItems": 1,
            },
        },
        "required": ["name", "messages"],
    },
    "set_voice": {
        "type": "object",
        "properties": {"voice": {"type": "string", "minLength": 1}},
        "required": ["voice"],
    },
    "add_substitution": {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "minLength": 1},
            "replacement": {"type": "string"},
            "kind": {"enum": ["literal", "regex"], "default": "literal"},
        },
        "required": ["pattern", "replacement"],
    },
    "remove_substitution": {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "minLength": 1},
            "kind": {"enum": ["literal", "regex"], "default": "literal"},
        },
        "required": ["pattern"],
    },
    "list_substitutions": {"type": "object", "properties": {}},
    "status": {"type": "object", "properties": {}},
}
"""What each tool takes. Enforced, not merely advertised.

`routes.py` compiles these with wrench and validates every incoming call against
them, so a request that does not match is refused with a message naming the
field. The same documents are what `tools/list` publishes, which is what makes
the advertisement honest: a client is told the contract that will actually be
applied to it.

Publishing them while hand-written checks in the operations did the real work
would be two statements of one contract with nothing keeping them together.

`additionalProperties` is deliberately not set. A key skid does not know is
ignored here, where in the config file it is refused. The difference is who is
harmed: an unknown config key is a typo that silently keeps a default and leaves
a person staring at a file that appears to say otherwise, while an unknown
argument is a client sending a field skid has no use for, and refusing it breaks
a caller to no purpose. `test_the_substitution_set_is_global` depends on this,
sending `name` to prove the set is not scoped by it.

`skid-mcp` still derives its own schemas from function signatures through the
SDK, so the surface is stated twice while that is true.
`tests/test_client.py` asserts the two agree on names, required fields and
property names; titles and the SDK's generated wrapper name mean nothing to a
caller and are not compared. The duplication goes when the shim stops being an
MCP server and becomes a forwarder.
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
