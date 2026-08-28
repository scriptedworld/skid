"""The MCP surface: what an agent calls, and what it may change.

Every tool that changes a setting validates before it writes. The config file is
the record and it outlives every restart, so an accepted bad value is permanent,
and `speak` has already told the caller its work was queued by the time anything
would go wrong. The tool call is the last moment the caller is there to be told.

Nothing here holds state. The service owns the queue and the model; this
translates calls into it and settings into the file the service re-reads.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from skid.config import load_config, save_config
from skid.generation import VOICES
from skid.service import Service
from skid.substitution import Kind, Substitution


def build_server(service: Service, config_path: Path) -> MCPServer:
    """Build the MCP server over a running service."""
    server = MCPServer("skid")

    @server.tool()
    def speak(name: str, messages: list[str]) -> str:
        """Say an array of messages, in order, in the voice skid is set to.

        Returns once the work is queued, not once it has been heard. Nothing is
        rejected and nothing already queued is replaced.
        """
        service.submit(name, messages)
        return f"queued {len(messages)} message(s) for {name}"

    @server.tool()
    def set_voice(voice: str) -> str:
        """Change the voice, and write it to the config file.

        Refuses a voice kokoro does not have rather than storing it, because a
        stored bad voice fails every later submission and survives a restart.
        """
        if voice not in VOICES:
            raise ValueError(f"unknown voice: {voice!r}")
        config = load_config(config_path)
        config.voice = voice
        save_config(config, config_path)
        return f"voice is now {voice}"

    @server.tool()
    def add_substitution(pattern: str, replacement: str, kind: str = "literal") -> str:
        """Add a pronunciation substitution to the end of the set.

        The set is global and applies whatever name submitted the text, and the
        order entries appear in the file is the order they are applied in. A
        regular expression that does not compile is refused here.
        """
        declared: Kind = "regex" if kind == "regex" else "literal"
        entry = Substitution(kind=declared, pattern=pattern, replacement=replacement)
        config = load_config(config_path)
        config.substitutions.append(entry)
        save_config(config, config_path)
        return f"{pattern} will be said as {replacement}"

    @server.tool()
    def remove_substitution(pattern: str, kind: str = "literal") -> str:
        """Remove an entry by its exact pattern and kind.

        The kind is needed as well as the pattern, because a literal `a` and a
        regular expression `a` are different entries.
        """
        declared: Kind = "regex" if kind == "regex" else "literal"
        config = load_config(config_path)
        kept = [
            entry
            for entry in config.substitutions
            if not (entry.pattern == pattern and entry.kind == declared)
        ]
        removed = len(config.substitutions) - len(kept)
        config.substitutions = kept
        save_config(config, config_path)
        return f"removed {removed} entr{'y' if removed == 1 else 'ies'}"

    @server.tool()
    def list_substitutions() -> list[dict[str, str]]:
        """Every substitution, in the order they are applied."""
        return [
            {
                "kind": entry.kind,
                "pattern": entry.pattern,
                "replacement": entry.replacement,
            }
            for entry in load_config(config_path).substitutions
        ]

    @server.tool()
    def status() -> dict[str, Any]:
        """Queue depth, recent failures, and the voice in use.

        `speak` returns at queue time, so a caller that wants to know whether
        anything was actually heard asks here. A person reads the log instead.
        """
        return service.status()

    return server
