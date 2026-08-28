"""skid-mcp, the MCP server, against the real service over a real request.

**Nothing here is scripted or stood in for.** The tools are the ones a client
calls, the backend is `httpx` over a WSGI transport, and behind it is the actual
Flask app over an actual `Service`. Flask being WSGI is what makes that possible
without a socket: the request goes through the same code a socket would reach.

The previous version of this file could not do that. It tested a byte-forwarder
against a hand-written service that scripted 404s, because the thing under test
was session recovery and a session is a thing you have to break on purpose. There
is no session now, so there is nothing to script.

**What is gone, and deliberately.** Nine tests covered `Session._id`,
`_handshake`, `_lost` and `_reinitialize`: replaying a handshake, retrying once,
carrying the new session and not the dead one, and refusing to replay for
anything but a 404. All of it was recovery from a session the service forgot,
and no session exists on either side now. Their requirement, FR-5.3, is covered
here by the case that actually remains: a service that cannot be reached fails
the call instead of hanging it.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from skid.client import Backend, Unreachable, build_server
from skid.config import Config, load_config
from skid.routes import build_app
from skid.service import Service
from skid.tools import ROUTES

NOWHERE = Path("/nowhere/skid.sock")
"""A socket path nothing is listening on, which is what an absent service is."""


@pytest.fixture(name="config_path")
def config_path_fixture(tmp_path: Path) -> Path:
    """A config file path in a directory the test owns."""
    return tmp_path / "config.yaml"


@pytest.fixture(name="service")
def service_fixture(tmp_path: Path, config_path: Path) -> Iterator[Service]:
    """A real service with a player that says nothing and exits zero."""
    script = tmp_path / "player.sh"
    script.write_text("#!/bin/sh\ntrue\n", encoding="utf-8")
    script.chmod(0o755)

    built = Service(
        config=Config(player=f"{script} {{file}}"),
        work_dir=tmp_path / "work",
        log_path=tmp_path / "log",
        config_path=config_path,
    )
    yield built
    built.stop()


@pytest.fixture(name="backend")
def backend_fixture(service: Service, config_path: Path) -> Iterator[Backend]:
    """A backend over the real app, reached through a real WSGI request."""
    app = build_app(service, config_path)
    transport = httpx.WSGITransport(app=app)
    with httpx.Client(transport=transport, base_url="http://localhost") as http:
        yield Backend(http, "/wsgi/skid.sock")


@pytest.fixture(name="server")
def server_fixture(backend: Backend) -> Any:
    """The MCP server over that backend, as a client meets it."""
    return build_server(backend)


def _call(server: Any, tool: str, **arguments: Any) -> Any:
    """Call a tool the way a client does, from a synchronous test."""
    return asyncio.run(server.call_tool(tool, arguments))


# COVERS: FR-5.2 | positive
def test_the_script_is_the_mcp_server_and_offers_every_tool(server: Any) -> None:
    """The protocol stops here now, so this is where the tool surface lives.

    Asserted as the whole set against `skid.tools`, so a tool added to the
    routes and not to this process is caught, and so is the reverse. That pair
    is the failure mode the split introduced.
    """
    names = {tool.name for tool in asyncio.run(server.list_tools())}

    assert names == set(ROUTES)


# COVERS: FR-5.2 | positive
def test_a_tool_call_reaches_the_service_and_returns_its_answer(
    server: Any, service: Service
) -> None:
    """One call, one request, one answer, with no handshake in front of it."""
    _call(server, "speak", name="silo", messages=["one", "two"])

    assert service.status()["pending"] == 1


# COVERS: FR-4.4 | property
def test_a_call_is_executed_once(server: Any, service: Service) -> None:
    """Nothing is ever replayed, because there is no session to lose.

    The old shim retried a request when the service said the session was gone,
    which was safe only because a 404 arrived before dispatch. That invariant
    was guarded by a docstring, and a later `_lost` admitting a 503 would have
    made the machine say the same thing twice. Removing the session removes the
    invariant, and this asserts the property it was protecting.
    """
    _call(server, "speak", name="silo", messages=["once"])

    assert service.status()["pending"] == 1


# COVERS: FR-5.3 | negative
def test_an_unreachable_service_fails_the_call_rather_than_hanging() -> None:
    """The failure FR-5.3 names, against a socket nothing is listening on.

    A real transport over a real absent path, so what is exercised is what a
    client meets when the service is down: an error, promptly, naming where it
    looked. The case this replaces waited 1800 seconds and said nothing.
    """
    transport = httpx.HTTPTransport(uds=str(NOWHERE))
    with httpx.Client(transport=transport, base_url="http://localhost") as http:
        backend = Backend(http, NOWHERE)

        with pytest.raises(Unreachable, match=str(NOWHERE)):
            backend.call("status")


# COVERS: FR-5.3 | negative
def test_a_refusal_carries_the_services_own_reason(backend: Backend) -> None:
    """A value the service will not store fails the call and says why.

    Asserted at the backend rather than through `call_tool`, because the SDK
    wraps a tool's exception as "Error executing tool set_voice" and matching on
    the reason there would be testing the wrapper. What skid is responsible for
    is that the reason exists, crosses the socket intact, and names the value
    that was refused.
    """
    with pytest.raises(Unreachable, match="af-typo"):
        backend.call("set_voice", voice="af-typo")


# COVERS: FR-6.5 | negative
def test_an_unknown_voice_fails_the_call(server: Any, config_path: Path) -> None:
    """The tool call is the last moment the caller is present to be told."""
    with pytest.raises(Exception, match="set_voice"):
        _call(server, "set_voice", voice="af-typo")

    assert not config_path.exists()


# COVERS: FR-6.1 | positive
def test_setting_the_voice_through_the_tool_reaches_the_config(
    server: Any, config_path: Path
) -> None:
    """The tool route ends at the file, with plain HTTP in the middle."""
    _call(server, "set_voice", voice="af_bella")

    assert load_config(config_path).voice == "af_bella"


# COVERS: FR-7.9 | property
def test_the_substitution_set_is_global(server: Any) -> None:
    """No name scopes the set: a correction any caller makes helps every caller."""
    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    schema = tools["add_substitution"].input_schema

    assert "name" not in schema.get("properties", {})


# COVERS: FR-8.1 | positive
def test_a_substitution_is_declared_through_the_tool(
    server: Any, config_path: Path
) -> None:
    """Patterns and their replacements arrive over MCP and land in the file."""
    _call(
        server,
        "add_substitution",
        pattern="kokoro",
        replacement="koh koh roh",
        kind="literal",
    )

    entries = load_config(config_path).substitutions
    assert [(e.pattern, e.replacement) for e in entries] == [("kokoro", "koh koh roh")]


# COVERS: FR-4.7 | positive
def test_status_reports_what_a_caller_cannot_log(server: Any) -> None:
    """speak returned at queue time, so status is how a caller learns anything."""
    reported = _call(server, "status")

    assert reported is not None
