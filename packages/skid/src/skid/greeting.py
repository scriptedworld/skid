"""Who gets announced, and against which clock.

The decision is a pure function of a table, a name, the work it named and a
time, so that the rule about *when* it is evaluated lives with the caller
rather than in here. That matters: the caller must pass the time at playback,
not at submission, because an unbounded queue can put minutes between the two.

The window belongs to a name and its work together, FR-3.2, so a name heard a
moment ago on one piece of work is announced again when it speaks on another.
The work is whatever the caller named, FR-3.7, and is spoken as given.

The table is memory only. A restart costs at most one extra greeting per name,
which is the right amount of engineering for a thirty second window.
"""

from __future__ import annotations


def greeting_for(name: str, work: str | None = None) -> str:
    """The line spoken before a name's first message in a while."""
    if not name.strip():
        raise ValueError("a submission carries a name identifying its sender")
    if work:
        return f"Hi, {name} here, in {work}."
    return f"Hi, {name} here."


class QuietTable:
    """When each name, on each piece of work, last finished being audible."""

    def __init__(self) -> None:
        """Start with nobody having spoken, which is also the state after a restart."""
        self._finished: dict[tuple[str, str | None], float] = {}

    def record_finished(self, name: str, when: float, work: str | None = None) -> None:
        """Note that a clip for `name` on `work` finished playing at `when`."""
        self._finished[(name, work)] = when

    def last_finished(self, name: str, work: str | None = None) -> float | None:
        """When `name` last finished speaking on `work`, or None if it has not."""
        return self._finished.get((name, work))


def should_greet(
    table: QuietTable,
    name: str,
    now: float,
    window: float,
    work: str | None = None,
) -> bool:
    """Whether `name` on `work` should be announced, given when it last spoke.

    `now` is the moment the clip is about to be played. Passing the submission
    time instead would announce a name whose voice is still in the room.
    """
    last = table.last_finished(name, work)
    if last is None:
        return True
    return (now - last) >= window
