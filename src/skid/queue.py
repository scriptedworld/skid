"""The submission queue: unbounded, first in first out, taken whole.

It holds submissions and knows nothing about clips, audio or players. A
submission is taken whole rather than a message at a time, which is what stops
two callers interleaving into one stream a listener has to untangle.

Unbounded is a choice with a stated cost: a caller behind a long array waits as
long as that array takes, and has no way to know in advance how long that is.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class Submission:
    """An array of messages from one named caller."""

    name: str
    messages: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Refuse a submission that names nobody or says nothing."""
        if not self.name.strip():
            raise ValueError("a submission carries a name identifying its sender")
        if not self.messages:
            raise ValueError("a submission carries at least one message")


class SubmissionQueue:
    """Arrivals wait their turn. Nothing is rejected and nothing is replaced."""

    def __init__(self) -> None:
        """Start empty, which is the common state."""
        self._waiting: deque[Submission] = deque()

    def put(self, submission: Submission) -> None:
        """Add a submission to the tail."""
        self._waiting.append(submission)

    def take(self) -> Submission:
        """Remove and return the submission at the head, whole."""
        return self._waiting.popleft()

    def pending(self) -> int:
        """How many submissions are waiting."""
        return len(self._waiting)
