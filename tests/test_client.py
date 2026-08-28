"""The stdio shim: forwarding, and surviving a service that forgot the session.

Written before the fix and expected to fail. No service is involved: the shim
talks over an `httpx` transport, so a `MockTransport` scripts the responses and
the tests assert what the shim sends and what it writes back.

**The bug these are written against.** The MCP session lives in the service's
memory. A restart forgets it, the service answers every later request with 404
and `"id": null`, and the shim forwarded that verbatim. A JSON-RPC client cannot
match a response whose id is null to the request it is waiting on, so it waits
until something outside gives up. Measured 2026-08-28: three retries in the
journal, and the one call left to run its course was aborted by the MCP client's
own backstop after 1800 seconds carrying no diagnosis, which is the failure
being survived by a third party rather than reported.
"""

from __future__ import annotations

import io
import json
from typing import Any

import httpx
import pytest

from skid.client import SESSION_HEADER, pump

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
        self.executed: list[str] = []
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

        if body.get("method") == "tools/call":
            self.executed.append(body["params"]["name"])
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
    """A restart must cost a reconnection, not a call nobody can diagnose.

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


# COVERS: FR-4.4 | property
def test_a_recovered_request_is_executed_once_and_not_twice() -> None:
    """The retry must never make the machine say the same thing twice.

    `speak` is not idempotent, and this is the property the whole retry rests
    on: recovery fires only for statuses the service emits *before* dispatching,
    so the request being replayed provably did not run. A future `_lost` that
    admitted a 503 or a connection reset would break this silently, and the
    resulting duplicate speech would not look like a shim bug to anybody.

    Asserting the reply arrived is not enough, which is why this exists
    separately: the service running `speak` twice and answering once passes that
    check and fails this one.
    """
    service = Service(forget_after=2)

    _run(service, INITIALIZE, INITIALIZED, SPEAK)

    assert service.executed == [SPEAK["params"]["name"]]


# COVERS: FR-5.3 | negative
def test_a_reconnection_refused_at_the_protocol_layer_reports_what_it_said() -> None:
    """A 200 carrying an error is not a rebuilt session, and its message is the good one.

    The service explains itself in the `initialize` response: a protocol version
    it will not accept, say. Reading only the status would call that success,
    retry into a session that never existed, and hand the client a vague
    complaint about the status of the retry instead of the service's own
    account. That is this module's founding mistake pointed at its own recovery
    path.
    """

    handshakes: list[int] = []

    def refuse_handshake(request: httpx.Request) -> httpx.Response:
        """Answer the first handshake, then refuse to rebuild at the JSON-RPC layer."""
        body = json.loads(request.content)
        if body.get("method") == "initialize":
            handshakes.append(1)
            if len(handshakes) > 1:
                return httpx.Response(
                    200,
                    json={
                        "jsonrpc": "2.0",
                        "id": body["id"],
                        "error": {"code": -32602, "message": "unsupported protocol"},
                    },
                )
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": body["id"], "result": {}},
                headers={SESSION_HEADER: "session-1"},
            )
        if body.get("id") is None:
            return httpx.Response(202, content=b"")
        return httpx.Response(404, json=DEAD_SESSION)

    out = io.StringIO()
    with httpx.Client(
        transport=httpx.MockTransport(refuse_handshake), base_url="http://localhost"
    ) as http:
        pump(
            http, _lines(INITIALIZE, INITIALIZED, SPEAK), out, path="/nowhere/skid.sock"
        )

    (failure,) = [reply for reply in _replies(out) if "error" in reply]
    assert failure["id"] == 2
    assert "unsupported protocol" in failure["error"]["message"]


def test_initializing_twice_replays_the_current_handshake_not_both() -> None:
    """A cached handshake that accumulates would rebuild a session already left behind.

    Keyed by method rather than appended, so a client that re-initializes
    replaces what is replayed. Appending would send the stale `initialize`
    first and the session would be rebuilt from the wrong one.
    """
    service = Service(forget_after=4)
    second = {**INITIALIZE, "id": 9, "params": {"protocolVersion": "later"}}

    _run(service, INITIALIZE, INITIALIZED, second, SPEAK)

    replayed = [body for _, body in service.seen if body.get("method") == "initialize"]
    assert [body["params"].get("protocolVersion") for body in replayed[-1:]] == [
        "later"
    ]


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
