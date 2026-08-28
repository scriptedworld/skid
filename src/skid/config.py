"""The config file, which is the record.

A setting changed through a tool is written back here, so a restart keeps it and
a person reading the file sees what is in use. That means writing into a file
somebody else owns and edits, so a write preserves their comments, their key
order and the order of their substitution entries. FR-8.4 makes that last one
load-bearing rather than cosmetic.

A missing file is not an error. A file that is present and malformed is, because
defaulting past it would silently discard the record it failed to parse.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomlkit
from tomlkit import TOMLDocument

from skid.substitution import Kind, Substitution

DEFAULT_VOICE = "af_heart"
DEFAULT_PLAYER = "paplay {file}"
DEFAULT_WINDOW_SECONDS = 30


def default_config_path() -> Path:
    """Where the config lives, honouring XDG_CONFIG_HOME."""
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "skid" / "config.toml"


@dataclass
class Config:
    """Every setting, with a default for each so the file says only what differs."""

    voice: str = DEFAULT_VOICE
    player: str = DEFAULT_PLAYER
    greeting_window_seconds: int = DEFAULT_WINDOW_SECONDS
    substitutions: list[Substitution] = field(default_factory=list)
    _document: TOMLDocument | None = field(default=None, repr=False, compare=False)


def _substitutions_from(document: TOMLDocument) -> list[Substitution]:
    """Read the substitution entries in the order the file lists them."""
    entries: list[Substitution] = []
    for raw in document.get("substitution", []):
        kind: Kind = "regex" if raw.get("kind") == "regex" else "literal"
        entries.append(
            Substitution(
                kind=kind,
                pattern=str(raw["pattern"]),
                replacement=str(raw["replacement"]),
            )
        )
    return entries


def load_config(path: Path | None = None) -> Config:
    """Read the config, or return the defaults if there is no file.

    Keeps the parsed document so that a later write can put the values back
    without disturbing anything else in it.
    """
    path = path or default_config_path()
    if not path.exists():
        return Config()

    text = path.read_text(encoding="utf-8")
    try:
        document = tomlkit.parse(text)
    except Exception as exc:
        raise ValueError(f"config is present but will not parse: {path}") from exc

    return Config(
        voice=str(document.get("voice", DEFAULT_VOICE)),
        player=str(document.get("player", DEFAULT_PLAYER)),
        greeting_window_seconds=int(
            document.get("greeting_window_seconds", DEFAULT_WINDOW_SECONDS)
        ),
        substitutions=_substitutions_from(document),
        _document=document,
    )


def _apply(config: Config, document: TOMLDocument) -> None:
    """Put the settings back into the document, keeping what a person wrote.

    Substitution entries are reconciled rather than rewritten. An entry that is
    unchanged keeps the table it came from, and with it any comment somebody put
    beside it; only genuinely new entries are built fresh. That matters because
    FR-8.4 makes the order meaningful, so the file is where a person reasons
    about the set and the comments are where they say why.
    """
    document["voice"] = config.voice
    document["player"] = config.player
    document["greeting_window_seconds"] = config.greeting_window_seconds

    if not config.substitutions and "substitution" not in document:
        return

    existing: dict[tuple[str, str, str], Any] = {}
    for table in document.get("substitution", []):
        key = (
            str(table.get("kind", "literal")),
            str(table["pattern"]),
            str(table["replacement"]),
        )
        existing.setdefault(key, table)

    rebuilt = tomlkit.aot()
    for entry in config.substitutions:
        key = (entry.kind, entry.pattern, entry.replacement)
        kept = existing.get(key)
        if kept is not None:
            rebuilt.append(kept)
            continue
        table = tomlkit.table()
        table["kind"] = entry.kind
        table["pattern"] = entry.pattern
        table["replacement"] = entry.replacement
        rebuilt.append(table)

    document["substitution"] = rebuilt


def save_config(config: Config, path: Path | None = None) -> None:
    """Write the config, preserving whatever a person put around the values.

    Written to a temporary file in the same directory and renamed over the
    original, so a kill part way through cannot leave a truncated config and
    lose the substitution set.
    """
    path = path or default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    document = config._document if config._document is not None else tomlkit.document()
    _apply(config, document)

    handle, temporary = tempfile.mkstemp(dir=path.parent, suffix=".toml")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            out.write(tomlkit.dumps(document))
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
