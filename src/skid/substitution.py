"""Pronunciation substitutions, applied on the way to the engine.

One left-to-right scan. At each position the entries are tried in file order and
the first that matches there wins; the scan then resumes after the text that
substitution produced, so nothing re-examines what a replacement emitted.

Position is the primary order and file order breaks ties at a position. Applying
each entry across the whole text in turn is a different algorithm, and it would
let one entry match another's output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

Kind = Literal["literal", "regex"]

_WORD = re.compile(r"\w")


def _anchored(kind: Kind, pattern: str) -> re.Pattern[str]:
    """Compile a pattern so it can be tried at a single position.

    A literal is escaped and fenced with word boundaries, so it does not fire
    inside a longer word it was not aimed at. The fence is only added where the
    adjacent character is a word character, because `\\b` next to punctuation
    asserts the opposite of what is wanted.
    """
    if kind == "regex":
        return re.compile(pattern, re.IGNORECASE)

    body = re.escape(pattern)
    prefix = r"\b" if pattern and _WORD.match(pattern[0]) else ""
    suffix = r"\b" if pattern and _WORD.match(pattern[-1]) else ""
    return re.compile(f"{prefix}{body}{suffix}", re.IGNORECASE)


@dataclass
class Substitution:
    """One entry: a pattern of a declared kind, and what is said instead.

    The replacement is heard rather than read, so it need not be a real spelling
    and is used literally. A regex that does not compile is refused here, where
    the caller is still present to be told, rather than when it is next applied.
    """

    kind: Kind
    pattern: str
    replacement: str
    _compiled: re.Pattern[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Compile the pattern, refusing one that cannot be."""
        if self.kind not in ("literal", "regex"):
            raise ValueError(f"unknown substitution kind: {self.kind!r}")
        try:
            self._compiled = _anchored(self.kind, self.pattern)
        except re.error as exc:
            raise ValueError(f"pattern does not compile: {self.pattern!r}") from exc

    def match_at(self, text: str, position: int) -> re.Match[str] | None:
        """Return a match starting exactly at `position`, or None."""
        return self._compiled.match(text, position)


def apply_substitutions(entries: list[Substitution], text: str) -> str:
    """Apply the set to `text` in a single left-to-right scan.

    At each position the entries are tried in order and the first that matches
    there wins. The scan resumes after the replacement, so no entry can match
    its own output or another's.
    """
    if not entries:
        return text

    out: list[str] = []
    position = 0
    while position < len(text):
        for entry in entries:
            found = entry.match_at(text, position)
            if found is not None and found.end() > position:
                out.append(entry.replacement)
                position = found.end()
                break
        else:
            out.append(text[position])
            position += 1
    return "".join(out)
