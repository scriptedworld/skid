"""What a submission is: an array of messages from one named caller.

It knows nothing about clips, audio, players or queueing. A submission is
handled whole rather than a message at a time, which is what stops two callers
interleaving into one stream a listener has to untangle, and `Spool` is what
keeps them in order.

**The queue used to be here and is a directory now.** FR-4.8 made it durable, so
`skid.spool.Spool` is the queue and an in-memory one beside it would be two
queues disagreeing rather than one working.
"""

from __future__ import annotations

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
