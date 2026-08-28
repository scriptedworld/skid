"""Who gets announced, and against which clock.

The decision is a pure function of a table, a name and a time, so that the rule
about *when* it is evaluated lives with the caller rather than in here. That
matters: the caller must pass the time at playback, not at submission, because
an unbounded queue can put minutes between the two.

The table is memory only. A restart costs at most one extra greeting per name,
which is the right amount of engineering for a thirty second window.
"""

from __future__ import annotations


def greeting_for(name: str) -> str:
    """The line spoken before a name's first message in a while."""
    if not name.strip():
        raise ValueError("a submission carries a name identifying its sender")
    return f"Hi, {name} here."


class QuietTable:
    """When each name last finished being audible."""

    def __init__(self) -> None:
        """Start with nobody having spoken, which is also the state after a restart."""
        self._finished: dict[str, float] = {}

    def record_finished(self, name: str, when: float) -> None:
        """Note that a clip for `name` finished playing at `when`."""
        self._finished[name] = when

    def last_finished(self, name: str) -> float | None:
        """When `name` last finished speaking, or None if it has not."""
        return self._finished.get(name)


def should_greet(table: QuietTable, name: str, now: float, window: float) -> bool:
    """Whether `name` should be announced, given what it last did and when.

    `now` is the moment the clip is about to be played. Passing the submission
    time instead would announce a name whose voice is still in the room.
    """
    last = table.last_finished(name)
    if last is None:
        return True
    return (now - last) >= window
