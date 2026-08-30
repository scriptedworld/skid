"""The service's HTTP surface: six operations, reached two ways.

The protocol lives in `skid-mcp`, and what normally crosses the socket is plain
HTTP with no session, no handshake and nothing cached on either side. There is
therefore nothing for a restart to invalidate, which is why the split exists.

**The operations are plain functions and both surfaces call them.** A Flask
route and the compatibility endpoint below dispatch to the same callable, so
they cannot answer differently. Only the shape of the answer differs.

**Validation stays here, with the thing being written.** A voice kokoro does not
have, or a regex that does not compile, is refused before anything reaches the
config file, because the file outlives every restart and an accepted bad value
is a permanent fault.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import wrench
from flask import Flask, Response, jsonify, request

from skid.config import load_config, save_config
from skid.generation import VOICES
from skid.service import Service
from skid.substitution import Kind, Substitution
from skid.tools import ERROR, RESULT, ROUTES, SCHEMAS

COMPILED = {
    tool: wrench.compile_schema(f"skid {tool} arguments", document)
    for tool, document in SCHEMAS.items()
}
"""The tool argument schemas, compiled once, because they are the same per call.

Same library and same shape as the config and the spool, so one thing in skid
decides what a valid structure is and says so the same way.
"""

BAD_REQUEST = 400
"""What a value this service refuses to store comes back as."""

ACCEPTED = 202
"""What a notification gets, since JSON-RPC forbids answering one."""

LEGACY_ENDPOINT = "/mcp"
"""Where the MCP server used to be, and still answers for an older shim.

**Deleting it took the machine silent for hours, which is why it does real work
now rather than returning an error.** A `skid-mcp` from before 2026-08-28 speaks
MCP to this path. First there was nothing here, so Flask answered 404 with an
HTML page, which is not a JSON-RPC message and left every client waiting on a
reply it could not match. Then it answered a JSON-RPC error, which unblocked the
callers and still left them unable to speak, because only the person holding the
session can restart it to pick up a new shim.

So it serves MCP, **statelessly**. No session id is issued or expected, which is
what makes this safe: the wedge that task 40 removed was session state going
stale, and there is none here to go stale.

*Discharges FR-5.3 across the version boundary.*

Retire it once `pgrep -af skid-mcp` shows nothing predating the move. It is not
in `ROUTES` because it is not a tool, and `tests/test_routes.py` subtracts it by
name so removing it is a change something notices.
"""

METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
"""JSON-RPC's codes for a method this does not provide and arguments it refuses."""

PROTOCOL_VERSION = "2024-11-05"
"""What to answer an `initialize` that names no version of its own."""


class Refused(Exception):
    """A value the service will not act on, carrying the reason a caller reads."""


def _kind_of(raw: object) -> Kind:
    """A declared substitution kind, defaulting to literal as the tools do."""
    return "regex" if raw == "regex" else "literal"


def _speech_operations(
    service: Service, config_path: Path
) -> dict[str, Callable[[dict[str, Any]], Any]]:
    """The operations that make skid talk, or report on talking."""

    def speak(body: dict[str, Any]) -> str:
        """Queue an array. Returns once it is on disk, not once it is heard.

        The schema has already required a non-empty name and at least one
        message, so nothing here re-checks the shape.
        """
        name = str(body["name"])
        messages = [str(message) for message in body["messages"]]
        service.submit(name, messages)
        return f"queued {len(messages)} message(s) for {name}"

    def set_voice(body: dict[str, Any]) -> str:
        """Change the voice, refusing one kokoro does not have.

        Which voices exist is kokoro's to say and not a schema's, so this check
        stays here where the list lives.
        """
        voice = str(body["voice"])
        if voice not in VOICES:
            raise Refused(f"unknown voice: {voice!r}")
        config = load_config(config_path)
        config.voice = voice
        save_config(config, config_path)
        return f"voice is now {voice}"

    def status(_: dict[str, Any]) -> dict[str, object]:
        """Queue depth, recent failures, and the voice in use."""
        return service.status()

    return {"speak": speak, "set_voice": set_voice, "status": status}


def _substitution_operations(
    config_path: Path,
) -> dict[str, Callable[[dict[str, Any]], Any]]:
    """The operations that correct how a word is said."""

    def add_substitution(body: dict[str, Any]) -> str:
        """Add an entry at the end of the set, refusing one that will not compile.

        Whether a regular expression compiles is not a thing a schema can say,
        so that check stays here.
        """
        try:
            entry = Substitution(
                kind=_kind_of(body.get("kind")),
                pattern=str(body["pattern"]),
                replacement=str(body["replacement"]),
            )
        except ValueError as exc:
            raise Refused(str(exc)) from exc
        config = load_config(config_path)
        config.substitutions.append(entry)
        save_config(config, config_path)
        return f"{entry.pattern} will be said as {entry.replacement}"

    def remove_substitution(body: dict[str, Any]) -> str:
        """Remove an entry by its exact pattern and kind."""
        pattern = str(body["pattern"])
        kind = _kind_of(body.get("kind"))
        config = load_config(config_path)
        kept = [
            entry
            for entry in config.substitutions
            if not (entry.pattern == pattern and entry.kind == kind)
        ]
        removed = len(config.substitutions) - len(kept)
        config.substitutions = kept
        save_config(config, config_path)
        return f"removed {removed} entr{'y' if removed == 1 else 'ies'}"

    def list_substitutions(_: dict[str, Any]) -> list[dict[str, str]]:
        """Every substitution, in the order they are applied."""
        return [
            {
                "kind": entry.kind,
                "pattern": entry.pattern,
                "replacement": entry.replacement,
            }
            for entry in load_config(config_path).substitutions
        ]

    return {
        "add_substitution": add_substitution,
        "remove_substitution": remove_substitution,
        "list_substitutions": list_substitutions,
    }


def _validated(tool: str, operation: Callable[[dict[str, Any]], Any]) -> Any:
    """Wrap one operation so its arguments are checked before it runs.

    Every caller goes through this, so the plain routes and the MCP endpoint are
    held to the same contract, and it is the contract `tools/list` publishes
    rather than a second one written for display.

    `wrench.ValidationError` is what the file loaders raise for the same
    failure, so one class covers a refused call and a refused file alike. It
    derives from `wrench.Error` and not from `ValueError`: a schema failure can
    be a wrong value or a wrong type, and `ValueError` excludes the second by
    definition, so it is a subclass of neither.

    `wrench.SchemaError` is deliberately not caught. `validate` raises it for a
    document that will not compile or a reference it cannot resolve, which is a
    broken schema here rather than a bad argument from a caller, and 500 is the
    honest answer. That is why only the validate call sits inside the try.
    """

    def checked(body: dict[str, Any]) -> Any:
        try:
            COMPILED[tool].validate(body)
        except wrench.ValidationError as exc:
            raise Refused(str(exc)) from exc
        return operation(body)

    checked.__name__ = tool
    checked.__doc__ = operation.__doc__
    return checked


def build_operations(
    service: Service, config_path: Path
) -> dict[str, Callable[[dict[str, Any]], Any]]:
    """The six operations, each taking its arguments and returning its answer.

    Raising `Refused` is how a bad value is reported, so neither surface has to
    know how the other reports one.
    """
    written = {
        **_speech_operations(service, config_path),
        **_substitution_operations(config_path),
    }
    return {tool: _validated(tool, call) for tool, call in written.items()}


def _body() -> dict[str, Any]:
    """The request's JSON object, or an empty one where it sent nothing.

    `silent=True` so that a malformed body becomes a refusal this module writes
    rather than Flask's own HTML error page, which no client here can read.
    """
    found = request.get_json(silent=True)
    return found if isinstance(found, dict) else {}


def _as_text(value: Any) -> str:
    """One content block's text, for a tool result crossing the MCP endpoint."""
    if isinstance(value, str):
        return value
    return json.dumps(value, indent=2, sort_keys=True)


def _reply(request_id: Any, result: Any) -> dict[str, Any]:
    """A JSON-RPC result carrying the id its caller is waiting on."""
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _failure(request_id: Any, code: int, message: str) -> dict[str, Any]:
    """A JSON-RPC error carrying the id its caller is waiting on.

    The id is the whole point. An error with a null id, or an HTML page, is not
    an answer to anything the client asked, and it waits rather than failing.
    """
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def build_app(service: Service, config_path: Path) -> Flask:
    """Build the HTTP app over a running service.

    Every route answers `{"result": ...}` or, with a 4xx, `{"error": ...}`. The
    script reads the status first and the body second.
    """
    app = Flask("skid")
    operations = build_operations(service, config_path)

    def route_for(tool: str) -> Callable[[], Response | tuple[Response, int]]:
        """One Flask view over one operation."""

        def view() -> Response | tuple[Response, int]:
            body = _body() if request.method == "POST" else {}
            try:
                return jsonify({RESULT: operations[tool](body)})
            except Refused as exc:
                return jsonify({ERROR: str(exc)}), BAD_REQUEST

        view.__name__ = tool
        view.__doc__ = operations[tool].__doc__
        return view

    for tool, (method, path) in ROUTES.items():
        app.add_url_rule(path, view_func=route_for(tool), methods=[method])

    _legacy_mcp_route(app, operations)
    return app


def _tool_call(
    operations: dict[str, Callable[[dict[str, Any]], Any]],
    request_id: Any,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Run one tool for an older shim and answer in MCP's own shape."""
    name = str(params.get("name", ""))
    if name not in operations:
        return _failure(request_id, METHOD_NOT_FOUND, f"no such tool: {name}")
    try:
        answer = operations[name](params.get("arguments") or {})
    except Refused as exc:
        return _reply(
            request_id,
            {"content": [{"type": "text", "text": str(exc)}], "isError": True},
        )
    return _reply(request_id, {"content": [{"type": "text", "text": _as_text(answer)}]})


def _tools_listing(
    operations: dict[str, Callable[[dict[str, Any]], Any]],
) -> dict[str, Any]:
    """The tool surface an older shim asks for, derived from `skid.tools`."""
    return {
        "tools": [
            {
                "name": tool,
                "description": (operations[tool].__doc__ or "").strip(),
                "inputSchema": SCHEMAS[tool],
            }
            for tool in ROUTES
        ]
    }


def _legacy_mcp_route(
    app: Flask, operations: dict[str, Callable[[dict[str, Any]], Any]]
) -> None:
    """Serve MCP to a shim that predates the move, holding no session.

    Retire this once nothing predating the move is running. The drift test in
    `tests/test_routes.py` names the route, so removing it is noticed.
    """

    @app.post(LEGACY_ENDPOINT)
    def legacy_mcp() -> Response | tuple[Response, int]:
        """Answer one JSON-RPC request, or accept a notification.

        A notification has no id and gets 202, because JSON-RPC forbids
        answering one and nothing is waiting on it.
        """
        body = _body()
        request_id = body.get("id")
        method = str(body.get("method", ""))
        if request_id is None:
            return jsonify({}), ACCEPTED

        if method == "initialize":
            asked = (body.get("params") or {}).get("protocolVersion")
            return jsonify(
                _reply(
                    request_id,
                    {
                        "protocolVersion": str(asked or PROTOCOL_VERSION),
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "skid", "version": "0.1.0"},
                    },
                )
            )
        if method == "tools/list":
            return jsonify(_reply(request_id, _tools_listing(operations)))
        if method == "tools/call":
            params = body.get("params") or {}
            return jsonify(_tool_call(operations, request_id, params))
        if method == "ping":
            return jsonify(_reply(request_id, {}))
        return jsonify(_failure(request_id, METHOD_NOT_FOUND, f"unsupported: {method}"))
