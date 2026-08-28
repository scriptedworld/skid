"""The stdio shim: forwarding, and surviving a service that forgot the session.

Written before the fix and expected to fail. No service is involved: the shim
talks over an `httpx` transport, so a `MockTransport` scripts the responses and
the tests assert what the shim sends and what it writes back.

**The bug these are written against.** The MCP session lives in the service's
memory. A restart forgets it, the service answers every later request with 404
and `"id": null`, and the shim forwarded that verbatim. A JSON-RPC client cannot
match a response whose id is null to the request it is waiting on, so it waits
forever. Measured 2026-08-28: a call outstanding for five minutes, and three
retries in the journal.
"""

from __future__ import annotations

import io
import json
from typing import Any

import httpx
import pytest

from skid.client import SESSION_HEADER, Session, pump

INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {"protocolVersion": "2024-11-05", "capabilities": {}},
}
INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}
SPEAK = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {"name": "speak", "arguments": {"name": "silo", "messages": ["hi"]}},
}

DEAD_SESSION = {
    "jsonrpc": "2.0",
    "id": None,
    "error": {"code": -32600, "message": "Session not found"},
}
"""What the service really returns for a session it has never heard of.

Measured 2026-08-28 against the live socket, HTTP 404. The null id is the whole
defect: it is not a response to anything the client asked.
"""


def _lines(*messages: dict[str, Any]) -> io.StringIO:
    """Requests as the MCP client would write them, one JSON object per line."""
    return io.StringIO("".join(json.dumps(message) + "\n" for message in messages))


def _replies(out: io.StringIO) -> list[dict[str, Any]]:
    """What the shim wrote back, parsed."""
    return [json.loads(line) for line in out.getvalue().splitlines() if line.strip()]


class Service:
    """A scripted service that can be told to forget its session once."""

    def __init__(self, *, forget_after: int | None = None) -> None:
        """`forget_after` is how many requests to answer before going amnesiac."""
        self.seen: list[tuple[str | None, dict[str, Any]]] = []
        self.sessions = 0
        self._forget_after = forget_after

    def last_session(self) -> str | None:
        """The session id the most recent request arrived with."""
        return self.seen[-1][0] if self.seen else None

    def handler(self, request: httpx.Request) -> httpx.Response:
        """Answer one request, recording the session id it arrived with."""
        body = json.loads(request.content)
        session = request.headers.get(SESSION_HEADER)
        self.seen.append((session, body))

        if body.get("method") == "initialize":
            self.sessions += 1
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": body["id"], "result": {"serverInfo": {}}},
                headers={SESSION_HEADER: f"session-{self.sessions}"},
            )
        if body.get("id") is None:
            return httpx.Response(202, content=b"")

        if self._forget_after is not None and len(self.seen) > self._forget_after:
            self._forget_after = None
            return httpx.Response(404, json=DEAD_SESSION)

        return httpx.Response(
            200, json={"jsonrpc": "2.0", "id": body["id"], "result": {"ok": True}}
        )


def _run(service: Service, *messages: dict[str, Any]) -> tuple[int, io.StringIO]:
    """Pump the messages through a shim wired to the scripted service."""
    out = io.StringIO()
    with httpx.Client(
        transport=httpx.MockTransport(service.handler), base_url="http://localhost"
    ) as http:
        code = pump(http, _lines(*messages), out, path="/nowhere/skid.sock")
    return code, out


# COVERS: FR-5.2 | positive
def test_a_request_is_forwarded_and_its_answer_returned() -> None:
    """The ordinary path, which nothing covered before this file existed."""
    service = Service()

    code, out = _run(service, INITIALIZE, INITIALIZED, SPEAK)

    assert code == 0
    assert [reply["id"] for reply in _replies(out)] == [1, 2]


# COVERS: FR-5.2 | positive
def test_the_session_id_is_carried_on_later_requests() -> None:
    """The service hands one back at initialize and expects it thereafter."""
    service = Service()

    _run(service, INITIALIZE, INITIALIZED, SPEAK)

    assert [session for session, _ in service.seen] == [None, "session-1", "session-1"]


# COVERS: FR-5.3 | regression
def test_a_forgotten_session_is_rebuilt_and_the_request_retried() -> None:
    """A restart must cost a reconnection, not a client that waits forever.

    The service answers the handshake, then forgets. The shim has to notice the
    404, replay the handshake it cached, and send the original request again, so
    that the client gets the answer it was waiting for and never learns a
    restart happened.
    """
    service = Service(forget_after=2)

    code, out = _run(service, INITIALIZE, INITIALIZED, SPEAK)

    assert code == 0
    assert _replies(out)[-1] == {"jsonrpc": "2.0", "id": 2, "result": {"ok": True}}
    assert service.sessions == 2


# COVERS: FR-5.3 | regression
def test_the_retry_carries_the_new_session_and_not_the_dead_one() -> None:
    """Retrying with the id the service just rejected is a loop, not a recovery."""
    service = Service(forget_after=2)

    _run(service, INITIALIZE, INITIALIZED, SPEAK)

    assert service.last_session() == "session-2"


# COVERS: FR-5.3 | edge
def test_a_shim_holding_no_session_at_all_handshakes_rather_than_erroring() -> None:
    """The service answers 400 for a missing id, which re-handshaking fixes.

    Narrower than the 404 path on purpose: 400 is also what an ordinary
    malformed request gets, so this recovers only when the shim really had no id
    to send. Measured 2026-08-28, the live service says
    `Bad Request: Missing session ID`.
    """
    sent: list[str | None] = []

    def demand_session(request: httpx.Request) -> httpx.Response:
        """Refuse anything without a session, and issue one at initialize."""
        sent.append(request.headers.get(SESSION_HEADER))
        body = json.loads(request.content)
        if body.get("method") == "initialize":
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": body["id"], "result": {}},
                headers={SESSION_HEADER: "fresh"},
            )
        if request.headers.get(SESSION_HEADER) is None:
            return httpx.Response(
                400, json={"jsonrpc": "2.0", "id": None, "error": {"code": -32600}}
            )
        return httpx.Response(
            200, json={"jsonrpc": "2.0", "id": body["id"], "result": {}}
        )

    out = io.StringIO()
    with httpx.Client(
        transport=httpx.MockTransport(demand_session), base_url="http://localhost"
    ) as http:
        session = Session(http)
        session.send(json.dumps(INITIALIZE))
        session.forget()
        replies = session.send(json.dumps(SPEAK))

    assert [json.loads(reply)["id"] for reply in replies] == [2]
    assert sent[-1] == "fresh"
    assert out.getvalue() == ""


# COVERS: FR-5.3 | property
def test_the_handshake_is_replayed_only_when_the_session_is_lost() -> None:
    """Re-initializing on every request would make each call cost two round trips."""
    service = Service(forget_after=2)

    _run(service, INITIALIZE, INITIALIZED, SPEAK, SPEAK, SPEAK)

    assert service.sessions == 2


# COVERS: FR-5.3 | negative
def test_an_error_the_shim_cannot_recover_carries_the_requests_own_id() -> None:
    """A client can report an error. It cannot report silence.

    This is the property FR-5.3 is really asking for, and the reason the row's
    two named cases were not enough: the backend answered promptly here, with
    something that was not an answer to the question asked.
    """

    def refuse(_request: httpx.Request) -> httpx.Response:
        """Fail every request in a way no reconnection would fix."""
        return httpx.Response(500, json={"jsonrpc": "2.0", "id": None, "error": {}})

    out = io.StringIO()
    with httpx.Client(
        transport=httpx.MockTransport(refuse), base_url="http://localhost"
    ) as http:
        pump(http, _lines(SPEAK), out, path="/nowhere/skid.sock")

    (reply,) = _replies(out)
    assert reply["id"] == 2
    assert "skid" in reply["error"]["message"]


# COVERS: FR-5.3 | edge
def test_a_notification_that_fails_gets_no_reply() -> None:
    """JSON-RPC forbids answering a message that carried no id."""

    def refuse(_request: httpx.Request) -> httpx.Response:
        """Fail the notification."""
        return httpx.Response(500, json={"error": {}})

    out = io.StringIO()
    with httpx.Client(
        transport=httpx.MockTransport(refuse), base_url="http://localhost"
    ) as http:
        pump(http, _lines(INITIALIZED), out, path="/nowhere/skid.sock")

    assert _replies(out) == []


# COVERS: FR-5.3 | negative
def test_an_unreachable_socket_exits_naming_the_path(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Today's behaviour, kept under test while everything around it changes."""

    def unreachable(_request: httpx.Request) -> httpx.Response:
        """There is no service at the other end."""
        raise httpx.ConnectError("no such file")

    with httpx.Client(
        transport=httpx.MockTransport(unreachable), base_url="http://localhost"
    ) as http:
        code = pump(http, _lines(SPEAK), io.StringIO(), path="/nowhere/skid.sock")

    assert code == 1
    assert "/nowhere/skid.sock" in capsys.readouterr().err
