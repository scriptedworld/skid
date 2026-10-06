"""The service's HTTP surface: six operations, one route each.

The protocol lives in `skid-mcp`, and what crosses the socket is plain HTTP
with no session, no handshake and nothing cached on either side. There is
therefore nothing for a restart to invalidate, which is why the split exists.

Validation stays here, with the thing being written. A voice kokoro does not
have, or a regex that does not compile, is refused before anything reaches the
config file, because the file outlives every restart and an accepted bad value
is a permanent fault.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import wrench
from flask import Flask, Response, jsonify, request

from skid.config import load_config, renderable_voices, save_config
from skid.generation import VOICES
from skid.service import Service
from skid.substitution import Kind, Substitution
from skid_contract.tools import ERROR, RESULT, ROUTES, SCHEMAS

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
        message, so nothing here re-checks the shape. `work` is optional,
        FR-3.9, and a client older than it sends none.
        """
        name = str(body["name"])
        messages = [str(message) for message in body["messages"]]
        work = body.get("work")
        service.submit(name, messages, str(work) if work else None)
        return f"queued {len(messages)} message(s) for {name}"

    def set_voice(body: dict[str, Any]) -> str:
        """Change the voice, refusing one that would not render here, FR-6.5.

        Kokoro knowing a voice is not the same as this machine being able to
        speak it. Thirteen of the 54 need a misaki language pack that is not
        installed, so they pass a membership test against `generation.VOICES`,
        persist, and then every submission fails silently: the caller has already
        been told its message was queued, and the setting survives a restart.

        The config's shortlist is the statement of what renders here, FR-10.1,
        and it is checked first because it is the narrower and truer claim. It is
        a claim about this machine where kokoro's list is a claim about kokoro,
        so it tracks a language pack being installed or removed.

        Falling back to kokoro's list where no shortlist is configured keeps the
        check no weaker than it was. That leaves the original hole open on a
        machine that configures nothing, which nothing here can close without
        building a pipeline inside a tool call.
        """
        voice = str(body["voice"])
        config = load_config(config_path)
        usable = renderable_voices(config)
        if usable:
            if voice not in usable:
                raise Refused(
                    f"voice {voice!r} is not one this machine speaks; "
                    "the voices list in the config names the ones it does"
                )
        elif voice not in VOICES:
            raise Refused(f"unknown voice: {voice!r}")
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

    return app
