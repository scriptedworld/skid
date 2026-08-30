"""The config file, which is the record.

A setting changed through a tool is written back here, so a restart keeps it and
a person reading the file sees what is in use.

**YAML, read and written by wrench against a schema.** Every structured file in
the ecosystem is YAML, and skid was the outlier: it chose TOML 83 minutes before
that was recorded, so it predates the decision rather than having ignored it.

**Nothing preserves comments any more, and that is the change rather than a
regression.** `tomlkit` was here because the file is one a person owns and edits,
and a parse-and-re-emit would discard what they wrote around the values. What
that argument was really protecting is the place a reason can live, and
`docs/config.sample.yaml` is that place now: the live file carries values and
the sample carries the explanations. So the live file is emitted canonically,
which is quoted keys and sorted names, and FR-7.8's comment clause is retired.

**Order still matters and still survives**, FR-8.4. A YAML list keeps its order
in the decoded structure, so the substitution set round-trips in file order
without anything preserving formatting. That row lost its reason for naming the
file and none of its substance.

A missing file is not an error. A file that is present and malformed is, because
defaulting past it would silently discard the record it failed to parse, and now
the message says which key and why rather than only that it would not parse.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import wrench

from skid import schemas
from skid.assignment import DEFAULT_WINDOW_SECONDS as DEFAULT_ASSIGNMENT_WINDOW_SECONDS
from skid.assignment import VoiceChoice
from skid.substitution import Kind, Substitution

DEFAULT_VOICE = "af_heart"
DEFAULT_PLAYER = "paplay {file}"
DEFAULT_WINDOW_SECONDS = 30

DEFAULT_EXPIRY_SECONDS = 300
"""Five minutes, FR-4.9. How long a queued submission stays worth speaking.

A PREFERENCE rather than a measurement: a judgement about how long a summary
stays current, not a property of the machine. Being ten times the greeting
window is a coincidence, since the two answer different questions and neither
constrains the other.
"""

SCHEMA = wrench.compile_schema("skid config", schemas.CONFIG)
"""Compiled once at import, because it is the same document for every read."""


def default_config_path() -> Path:
    """Where the config lives, honouring XDG_CONFIG_HOME."""
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "skid" / "config.yaml"


@dataclass
class Config:
    """Every setting, with a default for each so the file says only what differs."""

    voice: str = DEFAULT_VOICE
    player: str = DEFAULT_PLAYER
    greeting_window_seconds: int = DEFAULT_WINDOW_SECONDS
    expiry_seconds: int = DEFAULT_EXPIRY_SECONDS
    substitutions: list[Substitution] = field(default_factory=list)
    voices: list[VoiceChoice] = field(default_factory=list)
    assignment_window_seconds: int = DEFAULT_ASSIGNMENT_WINDOW_SECONDS


def _substitutions_from(document: dict[str, Any]) -> list[Substitution]:
    """Read the substitution entries in the order the file lists them.

    The schema has already said these are objects with the two required keys, so
    nothing here re-checks the shape. That is the point of validating on the way
    in: one place decides what a valid file is.
    """
    entries: list[Substitution] = []
    for raw in document.get("substitution") or []:
        kind: Kind = "regex" if raw.get("kind") == "regex" else "literal"
        entries.append(
            Substitution(
                kind=kind,
                pattern=str(raw["pattern"]),
                replacement=str(raw["replacement"]),
            )
        )
    return entries


def _voices_from(document: dict[str, Any]) -> list[VoiceChoice]:
    """Read the voice shortlist in file order, refusing a repeated alias.

    File order is the order voices are handed out, so it is kept for the reason
    FR-8.4 keeps the substitution order: a list a person wrote means what its
    order says.

    **The alias check is here rather than in the schema**, FR-10.8. JSON Schema
    compares whole entries for uniqueness, so two rows sharing an alias and
    differing in voice pass it. Naming the offender is the point: an ambiguous
    alias is one nothing about either row looks wrong for.
    """
    entries: list[VoiceChoice] = []
    seen: set[str] = set()
    for raw in document.get("voices") or []:
        alias = str(raw["alias"])
        if alias in seen:
            raise ValueError(f"two voices share the alias {alias!r}")
        seen.add(alias)
        pipeline = raw.get("pipeline")
        entries.append(
            VoiceChoice(
                alias=alias,
                voice=str(raw["voice"]),
                pipeline=str(pipeline) if pipeline is not None else None,
            )
        )
    return entries


def load_config(path: Path | None = None) -> Config:
    """Read the config, or return the defaults if there is no file.

    **A missing file and an unreadable one are different**, FR-6.4. wrench says
    which: `ReadError` covers both, so the absence is checked first and anything
    else that fails to read is a real fault and is raised.

    A shape wrench refuses becomes a `ValueError` naming the key, because the
    caller here is `Service._refresh_config` and a tool, neither of which should
    have to know what library read the file.
    """
    path = path or default_config_path()
    if not path.exists():
        return Config()

    try:
        document = wrench.load_yaml_file(path, SCHEMA, wrench.LOCAL_FILE)
    except (wrench.ParseError, wrench.ValidationError) as exc:
        raise ValueError(f"config is present but not usable: {exc}") from exc

    return Config(
        voice=str(document.get("voice", DEFAULT_VOICE)),
        player=str(document.get("player", DEFAULT_PLAYER)),
        greeting_window_seconds=int(
            document.get("greeting_window_seconds", DEFAULT_WINDOW_SECONDS)
        ),
        expiry_seconds=int(document.get("expiry_seconds", DEFAULT_EXPIRY_SECONDS)),
        substitutions=_substitutions_from(document),
        voices=_voices_from(document),
        assignment_window_seconds=int(
            document.get("assignment_window_seconds", DEFAULT_ASSIGNMENT_WINDOW_SECONDS)
        ),
    )


def _as_document(config: Config) -> dict[str, object]:
    """The settings as the structure the schema describes.

    Every value is written, including one that equals its default. The file is
    the record, so a reader should see what is in use rather than having to know
    which defaults applied. `substitution` and `voices` are omitted when empty,
    because an empty list in the file says less than its absence.

    A `pipeline` equal to the voice id's own letter is still written when it was
    written, and an entry that never named one still does not. The field says
    which phonemiser was *asked for*, and defaulting it on the way out would
    turn a deliberate choice into an accident of the id.
    """
    document: dict[str, object] = {
        "voice": config.voice,
        "player": config.player,
        "greeting_window_seconds": config.greeting_window_seconds,
        "expiry_seconds": config.expiry_seconds,
        "assignment_window_seconds": config.assignment_window_seconds,
    }
    if config.voices:
        document["voices"] = [
            {"alias": choice.alias, "voice": choice.voice}
            if choice.pipeline is None
            else {
                "alias": choice.alias,
                "voice": choice.voice,
                "pipeline": choice.pipeline,
            }
            for choice in config.voices
        ]
    if config.substitutions:
        document["substitution"] = [
            {
                "kind": entry.kind,
                "pattern": entry.pattern,
                "replacement": entry.replacement,
            }
            for entry in config.substitutions
        ]
    return document


def save_config(config: Config, path: Path | None = None) -> None:
    """Write the config, validated on the way out as well as the way in.

    **Validated on write is the half worth having.** A tool that stored a shape
    the schema refuses would produce a file skid could never read again, and the
    caller would be told the write succeeded. Checking the document before it
    reaches the disk means a bug in skid fails where a bad file would.

    The temporary-and-rename is wrench's, its FR-6.3, so a kill part way through
    leaves the old config rather than a truncated one.
    """
    path = path or default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    wrench.save_yaml_file(_as_document(config), path, SCHEMA, wrench.LOCAL_FILE)
