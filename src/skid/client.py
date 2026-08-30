"""skid-mcp: the MCP server, and the only thing in skid that speaks the protocol.

MCP clients configure a command and talk JSON-RPC over its stdin and stdout, so
this process is where the protocol belongs. It holds the six tool schemas and
the dispatch; the service holds the model, the queue and the config, and what
crosses the socket between them is plain HTTP.

**It holds nothing that survives a call.** No model, no queue, no config, and
now no session either. Every client that starts one is talking to the same
service, which is the point: a stdio server per client would load kokoro per
client (FR-5.1).

**The session is what used to be here, and removing it is why this file was
rewritten.** MCP over HTTP puts a session id in the service's memory. A restart
forgot it, the service answered every later request `404 Session not found` with
a null id, and a JSON-RPC client cannot match that to the request it is waiting
on, so it waited until something outside gave up. Measured 2026-08-28: a call
left to run its course was aborted by the MCP client's own backstop after
**1800 seconds** carrying no diagnosis.

`de3abb5` and `40eea92` recovered from that by caching the handshake and
replaying it. This removes the thing being recovered from: no session id exists
on either side, so nothing can go stale, and a restart costs a connection refused
for as long as the service takes to come back.

**What went with it.** The replay, and the invariant it rested on that nothing
but a docstring guarded: the retry was safe only because `404` arrived before
dispatch, and admitting a `503` would have made the machine speak twice. Also
the quiet reconnection that could hide a changed tool surface, since there is no
reconnection. And two SDK imports left the service, one of them there only
because the SDK answers 421 on an unknown Host header over a socket no browser
can reach.

**A call fails rather than hangs, which is FR-5.3 and is now nearly free.** A
service that is absent, refusing or slow produces an httpx error or a status,
and either becomes a tool error naming the socket. There is no state in which
this process is waiting on something it cannot describe.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer

from skid.tools import ERROR, RESULT, method_and_path

HOST = "http://localhost"
"""A name for the URL, since a unix socket has no host and httpx wants one."""

TIMEOUT = 300.0
"""Long enough to cover a cold start that loads the model.

It bounds a request rather than a session now, so a slow answer is the only
thing it can be waiting for. Under the old arrangement this was also the window
in which a wedged session looked like slow work.
"""


def socket_path() -> Path:
    """The socket the service listens on."""
    base = os.environ.get("XDG_RUNTIME_DIR")
    root = Path(base) if base else Path("/run/user") / str(os.getuid())
    return root / "skid" / "skid.sock"


class Unreachable(Exception):
    """The service could not be reached, or refused what was asked.

    One exception for both because a caller can act on neither: the tool failed
    and the message says why. The SDK turns it into a tool error carrying the
    calling request's own id, which is what a client can match.
    """


class Backend:
    """Plain HTTP to the service, holding nothing between calls."""

    def __init__(self, http: httpx.Client, path: Path | str) -> None:
        """Take the client and the socket path, which is only used in messages."""
        self._http = http
        self._path = path

    def call(self, tool: str, **arguments: Any) -> Any:
        """Make one request for `tool` and return what the service answered.

        Raises `Unreachable` for a transport failure and for a refusal alike.
        The status is read before the body, which is the lesson this file learnt
        expensively: a transport that succeeded says nothing about whether the
        request did.
        """
        method, path = method_and_path(tool)
        try:
            if method == "GET":
                response = self._http.get(path)
            else:
                response = self._http.post(path, json=arguments)
        except httpx.HTTPError as exc:
            raise Unreachable(f"skid is not reachable at {self._path}: {exc}") from exc

        body = self._decoded(response)
        if response.status_code >= 400:
            detail = body.get(ERROR) or f"the service answered {response.status_code}"
            raise Unreachable(str(detail))
        return body.get(RESULT)

    def _decoded(self, response: httpx.Response) -> dict[str, Any]:
        """The answer's JSON object, or an empty one if it did not send one.

        A body that will not parse is not an error by itself: the status is what
        says whether the request succeeded, and a 500 from something upstream of
        the app would carry HTML rather than a reason.
        """
        try:
            found = response.json()
        except ValueError:
            return {}
        return found if isinstance(found, dict) else {}


def _speech_tools(server: MCPServer, backend: Backend) -> None:
    """Register the tools that make skid talk or report on talking."""

    @server.tool()
    def speak(name: str, messages: list[str]) -> str:
        """Say an array of messages, in order, in the voice skid is set to.

        Returns once the work is queued, not once it has been heard. Nothing is
        rejected and nothing already queued is replaced.
        """
        return str(backend.call("speak", name=name, messages=messages))

    @server.tool()
    def set_voice(voice: str) -> str:
        """Change the voice, and write it to the config file.

        Refuses a voice kokoro does not have rather than storing it, because a
        stored bad voice fails every later submission and survives a restart.
        """
        return str(backend.call("set_voice", voice=voice))

    @server.tool()
    def status() -> dict[str, Any]:
        """Queue depth, recent failures, and the voice in use.

        `speak` returns at queue time, so a caller that wants to know whether
        anything was actually heard asks here. A person reads the log instead.
        """
        reported = backend.call("status")
        return dict(reported) if reported else {}


def _substitution_tools(server: MCPServer, backend: Backend) -> None:
    """Register the tools that correct how a word is said."""

    @server.tool()
    def add_substitution(pattern: str, replacement: str, kind: str = "literal") -> str:
        """Add a pronunciation substitution to the end of the set.

        The set is global and applies whatever name submitted the text, and the
        order entries appear in the file is the order they are applied in. A
        regular expression that does not compile is refused.
        """
        return str(
            backend.call(
                "add_substitution",
                pattern=pattern,
                replacement=replacement,
                kind=kind,
            )
        )

    @server.tool()
    def remove_substitution(pattern: str, kind: str = "literal") -> str:
        """Remove an entry by its exact pattern and kind.

        The kind is needed as well as the pattern, because a literal `a` and a
        regular expression `a` are different entries.
        """
        return str(backend.call("remove_substitution", pattern=pattern, kind=kind))

    @server.tool()
    def list_substitutions() -> list[dict[str, str]]:
        """Every substitution, in the order they are applied."""
        listed = backend.call("list_substitutions")
        return list(listed) if listed else []


def build_server(backend: Backend) -> MCPServer:
    """Build the MCP server over a backend, declaring the six tools.

    The schemas are derived from the tool signatures, so the arguments a client
    sees and the arguments sent to the service are one declaration. What each
    route is, is `skid.tools`; what each tool means is in the two registrars
    above; what it does is the service's.
    """
    server = MCPServer("skid")
    _speech_tools(server, backend)
    _substitution_tools(server, backend)
    return server


def main() -> int:
    """Serve MCP on this process's stdio, reaching the service over the socket."""
    path = socket_path()
    transport = httpx.HTTPTransport(uds=str(path))
    with httpx.Client(transport=transport, base_url=HOST, timeout=TIMEOUT) as http:
        build_server(Backend(http, path)).run("stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
