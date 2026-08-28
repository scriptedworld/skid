"""The service's HTTP surface: six routes on the socket systemd hands over.

This is what the MCP server used to be. The protocol now stops at the stdio
script, and what crosses the socket is plain HTTP with no session, no handshake
and nothing cached on either side. There is therefore nothing for a restart to
invalidate, which is the whole reason the split exists: the wedge class is
removed rather than recovered from.

**Validation stays here, with the thing being written.** A voice kokoro does not
have, or a regex that does not compile, is refused before anything reaches the
config file, because the file outlives every restart and an accepted bad value
is a permanent fault. The tool call is the last moment the caller is present to
be told, and a 400 carrying a reason is how it is told.

The service owns no schemas. What a tool's arguments are is the script's to
declare, and what the arguments mean is here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, request

from skid.config import load_config, save_config
from skid.generation import VOICES
from skid.service import Service
from skid.substitution import Kind, Substitution
from skid.tools import ERROR, RESULT, ROUTES

BAD_REQUEST = 400
"""What a value this service refuses to store comes back as."""


def _body() -> dict[str, Any]:
    """The request's JSON object, or an empty one where it sent nothing.

    `silent=True` so that a malformed body becomes a refusal this module writes
    rather than Flask's own HTML error page, which an MCP client cannot read.
    """
    found = request.get_json(silent=True)
    return found if isinstance(found, dict) else {}


def _kind_of(raw: object) -> Kind:
    """A declared substitution kind, defaulting to literal as the tools do."""
    return "regex" if raw == "regex" else "literal"


def build_app(service: Service, config_path: Path) -> Flask:
    """Build the HTTP app over a running service.

    Every route answers `{"result": ...}` or, with a 4xx, `{"error": ...}`. The
    script reads the status first and the body second.
    """
    app = Flask("skid")

    def ok(value: Any) -> Response:
        """One shape for every successful answer, including an empty one."""
        return jsonify({RESULT: value})

    def refuse(detail: str) -> tuple[Response, int]:
        """A refusal the caller is still present to be told about."""
        return jsonify({ERROR: detail}), BAD_REQUEST

    @app.post(ROUTES["speak"][1])
    def speak() -> Response:
        """Queue an array. Returns once it is on disk, not once it is heard."""
        body = _body()
        name = str(body.get("name", ""))
        messages = [str(message) for message in body.get("messages", [])]
        service.submit(name, messages)
        return ok(f"queued {len(messages)} message(s) for {name}")

    @app.post(ROUTES["set_voice"][1])
    def set_voice() -> Response | tuple[Response, int]:
        """Change the voice, refusing one kokoro does not have."""
        voice = str(_body().get("voice", ""))
        if voice not in VOICES:
            return refuse(f"unknown voice: {voice!r}")
        config = load_config(config_path)
        config.voice = voice
        save_config(config, config_path)
        return ok(f"voice is now {voice}")

    @app.post(ROUTES["add_substitution"][1])
    def add_substitution() -> Response | tuple[Response, int]:
        """Add an entry at the end of the set, refusing a pattern that will not compile."""
        body = _body()
        try:
            entry = Substitution(
                kind=_kind_of(body.get("kind")),
                pattern=str(body.get("pattern", "")),
                replacement=str(body.get("replacement", "")),
            )
        except ValueError as exc:
            return refuse(str(exc))
        config = load_config(config_path)
        config.substitutions.append(entry)
        save_config(config, config_path)
        return ok(f"{entry.pattern} will be said as {entry.replacement}")

    @app.post(ROUTES["remove_substitution"][1])
    def remove_substitution() -> Response:
        """Remove an entry by its exact pattern and kind."""
        body = _body()
        pattern = str(body.get("pattern", ""))
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
        return ok(f"removed {removed} entr{'y' if removed == 1 else 'ies'}")

    @app.get(ROUTES["list_substitutions"][1])
    def list_substitutions() -> Response:
        """Every substitution, in the order they are applied."""
        return ok(
            [
                {
                    "kind": entry.kind,
                    "pattern": entry.pattern,
                    "replacement": entry.replacement,
                }
                for entry in load_config(config_path).substitutions
            ]
        )

    @app.get(ROUTES["status"][1])
    def status() -> Response:
        """Queue depth, recent failures, and the voice in use."""
        return ok(service.status())

    return app
