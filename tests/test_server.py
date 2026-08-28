"""The MCP surface: the tools an agent actually calls.

Written before the implementation and expected to fail by not importing.

Only `speak` needs the engine, and it is not exercised here: the service is
tested on its own. What these check is the surface itself, and the settings
tools, which persist to a file and so can brick skid if they are wrong.

Calls go through `call_tool`, so what is tested is the MCP tool as an agent
reaches it rather than the Python function behind it.
"""

import asyncio
from pathlib import Path
from typing import Any

import pytest

from skid.config import Config, load_config
from skid.server import build_server
from skid.service import Service


def _call(server: Any, tool: str, **arguments: Any) -> Any:
    """Call a tool the way a client does, from a synchronous test."""
    return asyncio.run(server.call_tool(tool, arguments))


@pytest.fixture
def server_and_config(tmp_path: Path) -> tuple[Any, Path]:
    """A server over a real service, with a real config file path."""
    config_path = tmp_path / "config.toml"
    service = Service(
        config=Config(player="true"),
        work_dir=tmp_path / "work",
        log_path=tmp_path / "log",
    )
    return build_server(service, config_path), config_path


# COVERS: FR-5.2 | positive
def test_the_server_exposes_its_tools(server_and_config: tuple[Any, Path]) -> None:
    """An agent can see what skid offers."""
    server, _ = server_and_config

    names = {tool.name for tool in asyncio.run(server.list_tools())}

    assert {"speak", "set_voice", "add_substitution", "status"} <= names


# COVERS: FR-6.1 | positive
def test_the_voice_is_set_through_the_tool(server_and_config: tuple[Any, Path]) -> None:
    """A caller changes the voice without a file being edited."""
    server, config_path = server_and_config

    _call(server, "set_voice", voice="af_bella")

    assert load_config(config_path).voice == "af_bella"


# COVERS: FR-7.1 | positive
def test_a_tool_set_voice_persists(server_and_config: tuple[Any, Path]) -> None:
    """The config file is the record, so the change is there on the next start."""
    server, config_path = server_and_config

    _call(server, "set_voice", voice="am_puck")

    assert "am_puck" in config_path.read_text(encoding="utf-8")


# COVERS: FR-6.5 | negative
def test_an_unknown_voice_is_refused_and_not_written(
    server_and_config: tuple[Any, Path],
) -> None:
    """One accepted typo would silence skid for ever, and the caller is here now.

    The assertion is that it raises and that nothing reached the file. **Not
    that the message says why**: the SDK wraps a tool's error as "Error
    executing tool set_voice", so matching on the reason would be testing the
    SDK's wrapper. An earlier version of this test matched "voice" and passed
    on the tool's own name rather than on anything skid said.
    """
    server, config_path = server_and_config
    _call(server, "set_voice", voice="af_bella")
    before = config_path.read_text(encoding="utf-8")

    with pytest.raises(Exception, match="set_voice"):
        _call(server, "set_voice", voice="af-heart-with-a-typo")

    assert config_path.read_text(encoding="utf-8") == before


# COVERS: FR-8.1 | positive
def test_a_substitution_is_declared_through_the_tool(
    server_and_config: tuple[Any, Path],
) -> None:
    """Patterns and their replacements arrive over MCP."""
    server, config_path = server_and_config

    _call(
        server,
        "add_substitution",
        pattern="kokoro",
        replacement="koh koh roh",
        kind="literal",
    )

    entries = load_config(config_path).substitutions
    assert [(e.pattern, e.replacement) for e in entries] == [("kokoro", "koh koh roh")]


# COVERS: FR-7.8 | positive
def test_substitutions_persist_to_the_config(
    server_and_config: tuple[Any, Path],
) -> None:
    """A pronunciation set is the painful thing to lose, so it is written down."""
    server, config_path = server_and_config

    _call(server, "add_substitution", pattern="mcp", replacement="em see pee")

    assert "em see pee" in config_path.read_text(encoding="utf-8")


# COVERS: FR-8.4 | positive
def test_added_entries_keep_the_order_they_were_added(
    server_and_config: tuple[Any, Path],
) -> None:
    """File order is application order, so an entry is appended, not sorted in."""
    server, config_path = server_and_config

    _call(server, "add_substitution", pattern="zebra", replacement="zeh bra")
    _call(server, "add_substitution", pattern="aardvark", replacement="ard vark")

    patterns = [e.pattern for e in load_config(config_path).substitutions]
    assert patterns == ["zebra", "aardvark"]


# COVERS: FR-7.7 | negative
def test_an_invalid_regex_is_refused_at_the_tool(
    server_and_config: tuple[Any, Path],
) -> None:
    """A stored bad pattern would break every later submission, not this call.

    As above, what is asserted is the refusal and the untouched file. The reason
    is in skid's own exception and the SDK does not surface it in the message.
    """
    server, config_path = server_and_config

    with pytest.raises(Exception, match="add_substitution"):
        _call(
            server,
            "add_substitution",
            pattern="(unclosed",
            replacement="never",
            kind="regex",
        )

    assert not config_path.exists()


# COVERS: FR-7.9 | property
def test_the_substitution_set_is_global(server_and_config: tuple[Any, Path]) -> None:
    """No name scopes the set: a correction any caller makes helps every caller."""
    server, _ = server_and_config

    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    schema = tools["add_substitution"].input_schema

    assert "name" not in schema.get("properties", {})


# COVERS: FR-4.7 | positive
def test_status_reports_what_a_caller_cannot_log(
    server_and_config: tuple[Any, Path],
) -> None:
    """speak returned at queue time, so status is how a caller learns anything."""
    server, _ = server_and_config

    reported = _call(server, "status")

    assert reported is not None
