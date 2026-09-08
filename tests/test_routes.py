"""The service's HTTP surface, driven as the script drives it.

No protocol and no session here, which is the point of the split: every test is
one request and one answer, and nothing carries over between them. There is
nothing to script and nothing to double, because Flask's own test client calls
the real app over a real request context.

The service behind it is real too, with a player that is a shell script exiting
zero. Only `speak` reaches the engine, and it returns at queue time, so these
stay fast without anything being stood in for.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flask.testing import FlaskClient

from skid.config import load_config
from skid.routes import LEGACY_ENDPOINT
from skid.service import Service
from skid_contract.tools import ERROR, RESULT, ROUTES


def _result(response: Any) -> Any:
    """The successful answer, failing the test if it was a refusal."""
    assert response.status_code == 200, response.get_json()
    return response.get_json()[RESULT]


# COVERS: FR-5.2 | property
def test_every_declared_tool_has_a_route_and_nothing_else_does(
    client: FlaskClient,
) -> None:
    """The script and the service derive from one declaration, asserted as one.

    This is the failure mode the split introduces. When one module owned the
    schemas and the implementations together, a tool could not exist on one side
    only; now it can, and a tool the script offers with no route behind it fails
    at call time in front of a user rather than here.

    Asserted as equality in both directions, so an orphaned route is caught as
    well as an unreachable tool.

    `LEGACY_ENDPOINT` is subtracted rather than added to `ROUTES`, because it is
    not a tool and nothing should build a request from it. It is named here so
    that removing it, which is expected once no old shim is running, makes this
    test the thing that notices.
    """
    declared = set(ROUTES.values())
    served = {
        (method, str(rule))
        for rule in client.application.url_map.iter_rules()
        for method in rule.methods or set()
        if method in ("GET", "POST") and not str(rule).startswith("/static")
    }

    assert served - {("POST", LEGACY_ENDPOINT)} == declared


# COVERS: FR-4.5 | positive
def test_speak_returns_when_the_work_is_queued(client: FlaskClient) -> None:
    """The caller is told yes at queue time, which is what FR-4.5 requires."""
    response = client.post(ROUTES["speak"][1], json={"name": "silo", "messages": ["a"]})

    assert _result(response) == "queued 1 message(s) for silo"


# COVERS: FR-6.1 | positive
def test_the_voice_is_set_over_http(client: FlaskClient, config_path: Path) -> None:
    """A caller changes the voice without a file being edited by hand."""
    client.post(ROUTES["set_voice"][1], json={"voice": "af_bella"})

    assert load_config(config_path).voice == "af_bella"


# COVERS: FR-6.5 | negative
def test_an_unknown_voice_is_refused_and_nothing_is_written(
    client: FlaskClient, config_path: Path
) -> None:
    """One accepted typo silences skid for ever, and the caller is here now.

    The refusal carries skid's own reason, which the MCP surface could not do:
    the SDK wrapped a tool's error as "Error executing tool set_voice", so
    `test_an_unknown_voice_is_refused_and_not_written` had to assert on the tool
    name instead. Plain HTTP gives the reason back to the caller intact.
    """
    response = client.post(ROUTES["set_voice"][1], json={"voice": "af-typo"})

    assert response.status_code == 400
    assert "af-typo" in response.get_json()[ERROR]
    assert not config_path.exists()


# COVERS: FR-8.1 | positive
def test_a_substitution_is_declared_over_http(
    client: FlaskClient, config_path: Path
) -> None:
    """Patterns and their replacements arrive as an ordinary request."""
    client.post(
        ROUTES["add_substitution"][1],
        json={"pattern": "kokoro", "replacement": "koh koh roh", "kind": "literal"},
    )

    entries = load_config(config_path).substitutions
    assert [(e.pattern, e.replacement) for e in entries] == [("kokoro", "koh koh roh")]


# COVERS: FR-7.7 | negative
def test_a_regex_that_will_not_compile_is_refused(
    client: FlaskClient, config_path: Path
) -> None:
    """A stored bad pattern breaks every later submission, not this call."""
    response = client.post(
        ROUTES["add_substitution"][1],
        json={"pattern": "(unclosed", "replacement": "never", "kind": "regex"},
    )

    assert response.status_code == 400
    assert not config_path.exists()


# COVERS: FR-8.4 | positive
def test_entries_keep_the_order_they_were_added(
    client: FlaskClient, config_path: Path
) -> None:
    """File order is application order, so an entry is appended, not sorted in."""
    client.post(
        ROUTES["add_substitution"][1],
        json={"pattern": "zebra", "replacement": "zeh bra"},
    )
    client.post(
        ROUTES["add_substitution"][1],
        json={"pattern": "aardvark", "replacement": "ard vark"},
    )

    patterns = [e.pattern for e in load_config(config_path).substitutions]
    assert patterns == ["zebra", "aardvark"]


# COVERS: FR-7.8 | positive
def test_substitutions_persist_to_the_config(
    client: FlaskClient, config_path: Path
) -> None:
    """A pronunciation set is the painful thing to lose, so it is written down."""
    client.post(
        ROUTES["add_substitution"][1],
        json={"pattern": "mcp", "replacement": "em see pee"},
    )

    assert "em see pee" in config_path.read_text(encoding="utf-8")


# COVERS: FR-7.7 | positive
def test_a_literal_and_a_regex_of_the_same_pattern_are_different_entries(
    client: FlaskClient, config_path: Path
) -> None:
    """Removal takes the kind as well, which is only meaningful if they differ."""
    client.post(
        ROUTES["add_substitution"][1],
        json={"pattern": "a+", "replacement": "literal", "kind": "literal"},
    )
    client.post(
        ROUTES["add_substitution"][1],
        json={"pattern": "a+", "replacement": "regex", "kind": "regex"},
    )

    client.post(
        ROUTES["remove_substitution"][1], json={"pattern": "a+", "kind": "regex"}
    )

    remaining = load_config(config_path).substitutions
    assert [(e.kind, e.replacement) for e in remaining] == [("literal", "literal")]


# COVERS: FR-7.9 | property
def test_the_substitution_set_is_global(client: FlaskClient) -> None:
    """No name scopes the set, so a correction any caller makes helps every caller."""
    client.post(
        ROUTES["add_substitution"][1],
        json={"pattern": "silo", "replacement": "sigh low", "name": "wrench"},
    )

    listed = _result(client.get(ROUTES["list_substitutions"][1]))
    assert listed == [{"kind": "literal", "pattern": "silo", "replacement": "sigh low"}]


# COVERS: FR-4.7 | positive
def test_status_reports_what_a_caller_cannot_log(client: FlaskClient) -> None:
    """speak returned at queue time, so status is how a caller learns anything."""
    reported = _result(client.get(ROUTES["status"][1]))

    assert set(reported) >= {"pending", "recent_failures", "voice"}


# COVERS: FR-5.2 | negative
def test_a_call_that_does_not_match_its_schema_is_refused_by_field(
    client: FlaskClient, service: Service
) -> None:
    """The published schema is the enforced one, checked by wrench.

    An earlier version declared these only to show them in `tools/list`, with
    hand-written checks doing the real work, which is one contract stated twice
    and nothing holding the two together. wrench validates every call against
    the same document a client is handed.

    `messages: []` is the case worth naming: it used to reach `Submission` and
    raise from a dataclass three frames down, and now it is refused at the edge
    naming the field. Nothing is queued either way, which is what is asserted.
    """
    empty = client.post(ROUTES["speak"][1], json={"name": "silo", "messages": []})
    wrong_type = client.post(ROUTES["speak"][1], json={"name": 7, "messages": ["a"]})
    missing = client.post(ROUTES["speak"][1], json={"name": "silo"})

    assert empty.status_code == 400
    assert "messages" in empty.get_json()[ERROR]
    assert wrong_type.status_code == 400
    assert "name" in wrong_type.get_json()[ERROR]
    assert missing.status_code == 400
    assert service.status()["pending"] == 0


# COVERS: FR-5.2 | property
def test_the_published_schema_is_the_enforced_one(client: FlaskClient) -> None:
    """What `tools/list` advertises is what a call is held to, not a copy of it.

    Asserted by taking the schema the endpoint publishes and sending something
    that violates it, so the two cannot drift apart without this failing.
    """
    published = {
        tool["name"]: tool["inputSchema"]
        for tool in client.post(
            LEGACY_ENDPOINT, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        ).get_json()["result"]["tools"]
    }

    assert "voice" in published["set_voice"]["required"]

    refused = client.post(ROUTES["set_voice"][1], json={})

    assert refused.status_code == 400
    assert "voice" in refused.get_json()[ERROR]


# COVERS: FR-6.4 | edge
def test_a_missing_config_is_not_an_error(client: FlaskClient) -> None:
    """Reading the set before anything has written one answers empty, not 500."""
    assert _result(client.get(ROUTES["list_substitutions"][1])) == []


# COVERS: FR-5.3 | regression
def test_an_old_shim_can_still_speak(client: FlaskClient, service: Service) -> None:
    """The case that took the machine silent for hours, closed properly.

    A `skid-mcp` from before the move posts MCP to `/mcp`. Deleting the endpoint
    left Flask answering 404 with an HTML page, which is not a JSON-RPC message,
    so every client waited on a reply it could not match: measured on the live
    socket, a call still outstanding at 120 seconds. Answering a JSON-RPC error
    unblocked them and still left them mute, because only the person holding a
    session can restart it to pick up a new shim.

    So the endpoint does the work. This asserts the whole path an old shim takes:
    a `tools/call` reaching the service, running, and coming back in MCP's shape
    with the caller's own id on it.
    """
    answer = client.post(
        LEGACY_ENDPOINT,
        json={
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "speak",
                "arguments": {"name": "silo", "messages": ["heard again"]},
            },
        },
    ).get_json()

    assert answer["id"] == 7
    assert "queued 1 message(s) for silo" in answer["result"]["content"][0]["text"]
    assert service.status()["pending"] == 1


# COVERS: FR-5.3 | property
def test_the_legacy_endpoint_holds_no_session(client: FlaskClient) -> None:
    """Statelessness is what makes serving the old protocol safe to keep.

    The wedge task 40 removed was a session id going stale in the service's
    memory. Reinstating MCP here would reinstate that too if it issued one, so
    it issues none and expects none: no `mcp-session-id` header out, and a call
    carrying a stale one works anyway.
    """
    first = client.post(
        LEGACY_ENDPOINT, json={"jsonrpc": "2.0", "id": 1, "method": "initialize"}
    )
    with_a_dead_session = client.post(
        LEGACY_ENDPOINT,
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "status", "arguments": {}},
        },
        headers={"mcp-session-id": "disowned-000000000000000000000000"},
    )

    assert "mcp-session-id" not in {key.lower() for key, _ in first.headers}
    assert with_a_dead_session.get_json()["id"] == 2
    assert "error" not in with_a_dead_session.get_json()


# COVERS: FR-5.2 | property
def test_the_legacy_tool_list_matches_the_declared_set(client: FlaskClient) -> None:
    """An old shim asking what exists gets the same six, not a stale list."""
    listed = client.post(
        LEGACY_ENDPOINT, json={"jsonrpc": "2.0", "id": 3, "method": "tools/list"}
    ).get_json()["result"]["tools"]

    assert {tool["name"] for tool in listed} == set(ROUTES)
    assert all(tool["inputSchema"] for tool in listed)


# COVERS: FR-6.5 | negative
def test_a_refusal_reaches_an_old_shim_as_a_tool_error(client: FlaskClient) -> None:
    """A bad value fails the call and says why, rather than failing the transport.

    `isError` rather than a JSON-RPC error, because the call was dispatched and
    the tool refused. A protocol-level error would say the request was malformed,
    which it was not.
    """
    answer = client.post(
        LEGACY_ENDPOINT,
        json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "set_voice", "arguments": {"voice": "af-typo"}},
        },
    ).get_json()

    assert answer["result"]["isError"] is True
    assert "af-typo" in answer["result"]["content"][0]["text"]


# COVERS: FR-5.3 | edge
def test_an_old_shims_notification_gets_no_reply(client: FlaskClient) -> None:
    """Nothing is waiting on a notification, and JSON-RPC forbids answering one."""
    response = client.post(
        LEGACY_ENDPOINT, json={"jsonrpc": "2.0", "method": "notifications/initialized"}
    )

    assert response.status_code == 202
