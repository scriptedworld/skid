"""A stdio front end for the one running service.

MCP clients configure a command and speak JSON-RPC over its stdin and stdout.
skid serves MCP over HTTP on a unix socket instead, because that is what keeps
it a single warm process and owner-only (FR-5.1, FR-5.4). This bridges the two:
one line in, one POST, one line out.

**It holds nothing that matters.** No model, no queue, no config. Every client
that starts one is talking to the same service, which is the whole point: a
stdio server per client would load kokoro per client. It does hold the session
id and the handshake that established it, and that is what the next paragraph is
about.

**The session lives in the service's memory, so a restart forgets it.** The
service then answers every later request `404 Session not found` with a null
id, which is not a response to anything the client asked, so a client that was
handed it would wait for its answer forever. Measured 2026-08-28: restarting the
service left calls from three sessions outstanding, one of them for five
minutes, with no error for anyone to read.

So the shim caches the handshake and replays it when the service says the
session is gone, and a restart costs a reconnection instead. Restarting is the
documented way to deploy an edit under an editable install, so this is an
ordinary event rather than a rare one.

**Anything it cannot recover becomes a JSON-RPC error carrying the request's own
id.** That is what FR-5.3 is really asking for. The row names an absent backend
and a wedged one; the case that bit was a backend answering promptly with
something that was not an answer, and silence is the one outcome a client cannot
report.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import IO, Any

import httpx

ENDPOINT = "/mcp"
HOST = "http://localhost"
TIMEOUT = 300.0
"""Long enough to cover a cold start that loads the model."""

SESSION_HEADER = "mcp-session-id"
"""Where the service puts the session id, and where it expects it back."""

SESSION_LOST = 404
"""What the service answers for a session id it has never heard of.

Measured 2026-08-28 against the live socket. The body is
`{"jsonrpc": "2.0", "id": null, "error": {"code": -32600,
"message": "Session not found"}}`, and the null id is why forwarding it hangs a
client rather than failing it.
"""

SESSION_MISSING = 400
"""What the service answers when no session id is sent at all.

Measured 2026-08-28: `Bad Request: Missing session ID`. Recoverable only when
the shim really had no id to send, because the same status covers an ordinary
malformed request.
"""

INTERNAL_ERROR = -32603
"""JSON-RPC's code for a server-side failure, used for what skid cannot recover."""


def socket_path() -> Path:
    """The socket the service listens on."""
    base = os.environ.get("XDG_RUNTIME_DIR")
    root = Path(base) if base else Path("/run/user") / str(os.getuid())
    return root / "skid" / "skid.sock"


def _payloads(response: httpx.Response) -> list[str]:
    """Pull JSON-RPC messages out of a response, plain or server-sent events."""
    body = response.text
    if not body.strip():
        return []
    if "text/event-stream" in response.headers.get("content-type", ""):
        return [
            line[len("data:") :].strip()
            for line in body.splitlines()
            if line.startswith("data:")
        ]
    return [body.strip()]


def _request_id(request: str) -> Any:
    """The id the client is waiting on, or None for a notification.

    A malformed line has no id either, and gets the same treatment: nothing is
    written back, because there is nothing that could be waiting for it.
    """
    try:
        return json.loads(request).get("id")
    except (json.JSONDecodeError, AttributeError):
        return None


def _error_for(request: str, detail: str) -> list[str]:
    """A JSON-RPC error the client can match to its own request, or nothing.

    Answering a notification is forbidden by JSON-RPC, and a client waiting on
    nothing cannot be unblocked, so a message with no id gets no reply.
    """
    request_id = _request_id(request)
    if request_id is None:
        return []
    error = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": INTERNAL_ERROR, "message": f"skid: {detail}"},
    }
    return [json.dumps(error)]


class Session:
    """One MCP session over the socket, rebuilt when the service forgets it."""

    def __init__(self, http: httpx.Client) -> None:
        """Start with no session and no handshake to replay."""
        self._http = http
        self._id: str | None = None
        self._handshake: list[str] = []

    def forget(self) -> None:
        """Drop the session id, as the service does when it restarts.

        The next request then gets `404 Session not found` and the recovery in
        `send` takes over, so this is how the failure is reproduced against a
        real service without restarting it and wedging every other client whose
        shim predates this file.
        """
        self._id = None

    def _post(self, request: str) -> httpx.Response:
        """Send one request, carrying the session id if there is one."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._id:
            headers[SESSION_HEADER] = self._id
        response = self._http.post(ENDPOINT, content=request, headers=headers)
        self._id = response.headers.get(SESSION_HEADER, self._id)
        return response

    def _remember(self, request: str) -> None:
        """Keep the handshake messages, which are what rebuild a lost session.

        `initialize` and the `notifications/initialized` that follows it are the
        only two a client sends before it can do anything, so caching those two
        lines is enough to become a session again. Everything else is the
        client's own traffic and is never replayed.
        """
        try:
            method = json.loads(request).get("method")
        except (json.JSONDecodeError, AttributeError):
            return
        if method in ("initialize", "notifications/initialized"):
            self._handshake.append(request)

    def _reinitialize(self) -> bool:
        """Become a new session by replaying the handshake. False if it fails."""
        if not self._handshake:
            return False
        self._id = None
        for request in self._handshake:
            if self._post(request).status_code >= 400:
                return False
        return True

    def _lost(self, response: httpx.Response, had_session: bool) -> bool:
        """Whether this answer means the session is gone rather than the request bad.

        Two shapes, and the second is narrow on purpose. A restart leaves the
        shim holding an id the service has never heard of, which is `404 Session
        not found`. A shim holding no id at all is told `400 Bad Request:
        Missing session ID`, and re-handshaking is the right answer to that too.

        The `had_session` guard is what keeps the 400 case from swallowing an
        ordinary malformed request, which is the same status for a different
        reason.
        """
        if response.status_code == SESSION_LOST:
            return True
        return response.status_code == SESSION_MISSING and not had_session

    def send(self, request: str) -> list[str]:
        """Forward one request, rebuilding the session once if it has been lost."""
        self._remember(request)
        had_session = self._id is not None
        response = self._post(request)

        if self._lost(response, had_session) and self._reinitialize():
            response = self._post(request)

        if response.status_code >= 400:
            return _error_for(request, f"the service answered {response.status_code}")
        return _payloads(response)


def pump(http: httpx.Client, stdin: IO[str], stdout: IO[str], path: str | Path) -> int:
    """Forward every line of stdin to the service and its answers to stdout."""
    session = Session(http)
    for line in stdin:
        request = line.strip()
        if not request:
            continue
        try:
            replies = session.send(request)
        except httpx.HTTPError as exc:
            sys.stderr.write(f"skid is not reachable at {path}: {exc}\n")
            return 1
        for reply in replies:
            stdout.write(reply + "\n")
            stdout.flush()
    return 0


def main() -> int:
    """Bridge this process's stdio to the service on the socket."""
    path = socket_path()
    transport = httpx.HTTPTransport(uds=str(path))
    with httpx.Client(transport=transport, base_url=HOST, timeout=TIMEOUT) as http:
        return pump(http, sys.stdin, sys.stdout, path)


if __name__ == "__main__":
    raise SystemExit(main())
