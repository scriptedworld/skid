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

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from flask.testing import FlaskClient

from skid.config import Config, load_config
from skid.routes import build_app
from skid.service import Service
from skid.tools import ERROR, RESULT, ROUTES


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    """A config file path in a directory the test owns."""
    return tmp_path / "config.toml"


@pytest.fixture
def client(tmp_path: Path, config_path: Path) -> Iterator[FlaskClient]:
    """The real app over a real service, with a player that says nothing."""
    script = tmp_path / "player.sh"
    script.write_text("#!/bin/sh\ntrue\n", encoding="utf-8")
    script.chmod(0o755)

    service = Service(
        config=Config(player=f"{script} {{file}}"),
        work_dir=tmp_path / "work",
        log_path=tmp_path / "log",
        config_path=config_path,
    )
    app = build_app(service, config_path)
    app.config["TESTING"] = True
    with app.test_client() as http:
        yield http
    service.stop()


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
    """
    declared = {(method, path) for method, path in ROUTES.values()}
    served = {
        (method, str(rule))
        for rule in client.application.url_map.iter_rules()
        for method in rule.methods or set()
        if method in ("GET", "POST") and not str(rule).startswith("/static")
    }

    assert served == declared


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


# COVERS: FR-6.4 | edge
def test_a_missing_config_is_not_an_error(client: FlaskClient) -> None:
    """Reading the set before anything has written one answers empty, not 500."""
    assert _result(client.get(ROUTES["list_substitutions"][1])) == []
