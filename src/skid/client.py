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

**And that is exactly why the reconnection is quiet about a changed tool
surface, which is the one thing to watch here.** The client never sees the
second `initialize` result: the shim consumes it. So a new instance answering
with different capabilities or a different tool list leaves the client believing
what the old one said, and the shim cannot synthesise a
`notifications/tools/list_changed` to correct it.

That is safe today because the six tools are stable, which is a property of the
tool set and not of this file. The restart being recovered from is a code
deploy, so **the moment a reconnection is most likely to hide a changed surface
is the moment the surface is most likely to have changed.** Renaming a tool and
restarting would leave every reconnected client calling the old name until it
restarts, invisibly rather than loudly. Anyone changing the tool surface should
expect to restart the clients too.

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

HANDSHAKE = ("initialize", "notifications/initialized")
"""The two messages that establish a session, in the order a client sends them.

Replaying these is what rebuilds a session the service has forgotten. Nothing
else is ever replayed, because nothing else is safe to send twice.
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


def _refusal(response: httpx.Response) -> str:
    """The JSON-RPC error message in a 200, or empty if the answer was an answer.

    A transport that succeeded says nothing about whether the protocol did. This
    is the founding mistake of this module pointed at its own recovery path:
    reading the status and not the body is what made a 404 look like a reply.
    """
    for payload in _payloads(response):
        try:
            error = json.loads(payload).get("error")
        except (json.JSONDecodeError, AttributeError):
            continue
        if error:
            return str(error.get("message", error))
    return ""


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
        self._handshake: dict[str, str] = {}

    def disown(self) -> None:
        """Hold an id the service cannot know, which is what a restart leaves.

        Not the same as having no id, and the difference is the whole point: a
        restarted service answers `404 Session not found` to an id it does not
        recognise, where it answers `400 Missing session ID` to no id at all.
        Only the first is the failure this class exists for.

        This is how the failure is reproduced against a real service without
        restarting it and wedging every other client whose shim predates it.
        """
        self._id = "disowned-" + "0" * 24

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
        is enough to become a session again. Everything else is the client's own
        traffic and is never replayed.

        **Keyed by method, so a client that initializes twice replaces rather
        than accumulates.** Appending to a list would replay a stale
        `initialize` alongside the current one, in that order, and the session
        rebuilt from it would be the one the client has already moved on from.
        """
        try:
            method = json.loads(request).get("method")
        except (json.JSONDecodeError, AttributeError):
            return
        if method in HANDSHAKE:
            self._handshake[method] = request

    def _reinitialize(self) -> tuple[bool, str]:
        """Become a new session by replaying the handshake, in the order sent.

        **A 200 is not success, which is the same mistake one layer in.** An
        `initialize` refused at the JSON-RPC layer, a protocol version the
        service will not accept being the obvious case, comes back 200 carrying
        an `error` member. Reading only the status would call that a rebuilt
        session, retry into it, and hand the client `the service answered 404`
        in place of the service's own account of what was wrong.

        Returns whether the session is usable, and what to say if it is not.
        """
        replay = [
            self._handshake[method] for method in HANDSHAKE if method in self._handshake
        ]
        if not replay:
            return False, "no handshake to replay"
        self._id = None
        for request in replay:
            response = self._post(request)
            if response.status_code >= 400:
                return False, f"reconnecting failed with {response.status_code}"
            refusal = _refusal(response)
            if refusal:
                return False, f"reconnecting was refused: {refusal}"
        return True, ""

    def _lost(self, response: httpx.Response) -> bool:
        """Whether this answer means the session is gone rather than the request bad.

        **A status belongs here only if the service is known to emit it before
        dispatching the request**, because `send` replays the request on the
        strength of it. `speak` is not idempotent: a retry that crossed a
        dispatch boundary would make the machine say the same thing twice, and
        nobody would suspect the shim.

        `404 Session not found` qualifies, and is checked in the session manager
        before any tool is reached. A 503 or a connection reset does **not**
        qualify, however much they look like the same kind of trouble, because
        either can arrive after the work has been done.

        `400 Missing session ID` was here and was removed. It is what the
        service says to a shim holding no id at all, and tracing `_id` showed
        that state cannot be reached after the first handshake: `_post` only
        ever widens the id, and nothing clears it outside `_reinitialize`, which
        re-posts immediately. So the branch could only fire before a session had
        ever existed, where there is nothing lost to recover. It was a live test
        over a dead path, which is a green light that means nothing.
        """
        return response.status_code == SESSION_LOST

    def send(self, request: str) -> list[str]:
        """Forward one request, rebuilding the session once if it has been lost.

        The replay is safe because `_lost` admits only statuses the service
        emits before dispatching, so the original request provably did not run.
        Read `_lost` before adding one.
        """
        self._remember(request)
        response = self._post(request)

        if self._lost(response):
            rebuilt, why = self._reinitialize()
            if not rebuilt:
                return _error_for(request, why)
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
