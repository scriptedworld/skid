"""The durable queue: a directory of submissions, taken in name order.

**What is durable is the text, not the audio.** A submission is written here at
`submit()`, before the call returns, which is what gives FR-4.5's promise
something behind it. Clips stay a cache elsewhere and may be deleted freely,
because losing one costs regeneration time rather than data.

A spool of generated audio would not do. It protects only work already
generated, and the window this exists to close is the one between the call
returning yes and the first clip existing.

**Order is the sequence in the filename, never the file's timestamp.** Creation
time is generation order, which matches submission order today only because one
submission is handled at a time, and would diverge silently the moment two are
prepared at once. FR-4.3 and FR-4.4 both rest on this.

    000042-silo.json          waiting
    taken/000042-silo.json    being spoken right now
    000043-wrench.json.tmp    half written, removed at start-up

**Written to a temporary name and renamed into place**, so a file at its final
name is a whole file. A `kill -9` mid-write leaves a `.tmp` rather than a
truncated entry that parses to nonsense and blocks everything behind it.

**Taken means moved, not copied.** An entry lives under `taken/` while it is
being spoken and is removed when the attempt ends, however it ends. Anything
still there at start-up was interrupted by a crash, and is discarded rather than
replayed: FR-4.4 makes a submission indivisible, so there is no honest place to
resume from and replaying means hearing the already-heard clips again.

The guarantee is therefore precise and smaller than "nothing is lost". Accepted
and not yet started is never lost; being spoken when the process died is dropped.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from skid.queue import Submission

TAKEN = "taken"
"""Where an entry lives while it is being spoken."""

SUFFIX = ".json"
PARTIAL = ".tmp"

DEFAULT_TTL_SECONDS = 300.0
"""Five minutes, FR-4.9, and a PREFERENCE rather than a measurement.

A judgement about how long a summary stays worth hearing. Ten times the greeting
window is a coincidence: the two answer different questions and neither
constrains the other.
"""


@dataclass(frozen=True)
class Entry:
    """One submission on disk, and where it currently is."""

    submission: Submission
    path: Path
    queued_at: float


@dataclass(frozen=True)
class Recovered:
    """What start-up found and threw away, so it can be logged rather than lost."""

    interrupted: int = 0
    partial: int = 0
    unreadable: int = 0
    expired: tuple[str, ...] = ()
    """The names whose submissions aged out while the service was down.

    Names rather than a count, because these are the only kind a caller was
    told yes about and a log line naming who is worth more than a number.
    """


class Spool:
    """Arrivals wait their turn on disk. Nothing is rejected and nothing replaced."""

    def __init__(
        self, directory: Path, ttl_seconds: float = DEFAULT_TTL_SECONDS
    ) -> None:
        """Create the spool owner-only, and continue any sequence already there."""
        self.directory = directory
        self._taken = directory / TAKEN
        self._ttl = ttl_seconds
        for path in (self.directory, self._taken):
            path.mkdir(parents=True, exist_ok=True)
            path.chmod(0o700)

    def _next_sequence(self) -> int:
        """One past the highest name on disk, so a restart never overwrites work.

        Read from the directory rather than kept in memory, because the process
        that held the counter is exactly the one that has just gone away.
        """
        highest = -1
        for path in self.directory.glob(f"*{SUFFIX}"):
            head = path.name.split("-", 1)[0]
            if head.isdigit():
                highest = max(highest, int(head))
        return highest + 1

    def put(self, submission: Submission, now: float) -> Path:
        """Write a submission to disk and return once it is there.

        Validation belongs to `Submission`, which refuses an empty name or no
        messages in its own constructor. The spool does not get a second opinion.
        """
        sequence = self._next_sequence()
        safe = "".join(c if c.isalnum() else "_" for c in submission.name)[:40]
        final = self.directory / f"{sequence:06d}-{safe}{SUFFIX}"
        partial = final.with_suffix(SUFFIX + PARTIAL)

        payload = {
            "name": submission.name,
            "messages": submission.messages,
            "queued_at": now,
        }
        partial.write_text(json.dumps(payload), encoding="utf-8")
        partial.chmod(0o600)
        os.rename(partial, final)
        return final

    def pending(self) -> int:
        """How many submissions are waiting, not counting one being spoken."""
        return len(list(self.directory.glob(f"*{SUFFIX}")))

    def _read(self, path: Path) -> Entry | None:
        """Parse one entry, or None if it is not one.

        An entry that cannot be read is not retried. A failure drops a
        submission, and an entry nothing can parse takes the same path rather
        than blocking everything behind it forever.
        """
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            submission = Submission(name=payload["name"], messages=payload["messages"])
        except (json.JSONDecodeError, OSError, KeyError, TypeError, ValueError):
            return None
        return Entry(
            submission=submission,
            path=path,
            queued_at=float(payload.get("queued_at", 0.0)),
        )

    def _waiting(self) -> list[Path]:
        """Every waiting entry, in submission order."""
        return sorted(self.directory.glob(f"*{SUFFIX}"))

    def _expired(self, entry: Entry, now: float) -> bool:
        """Whether this has waited past the window. At the window it still speaks."""
        return (now - entry.queued_at) > self._ttl

    def take_expired(self, now: float) -> list[Entry]:
        """Remove and return everything too old to speak, for the caller to log.

        FR-4.5 told the caller its submission was accepted, so one that will not
        be spoken owes an explanation rather than vanishing.
        """
        discarded: list[Entry] = []
        for path in self._waiting():
            entry = self._read(path)
            if entry is None:
                path.unlink(missing_ok=True)
                continue
            if self._expired(entry, now):
                path.unlink(missing_ok=True)
                discarded.append(entry)
        return discarded

    def take(self, now: float) -> Entry | None:
        """Move the next speakable submission aside and return it.

        Expired and unreadable entries are dropped on the way past rather than
        stopping the scan, so neither can block what is behind it.
        """
        for path in self._waiting():
            entry = self._read(path)
            if entry is None or self._expired(entry, now):
                path.unlink(missing_ok=True)
                continue
            aside = self._taken / path.name
            os.rename(path, aside)
            return Entry(
                submission=entry.submission, path=aside, queued_at=entry.queued_at
            )
        return None

    def done(self, entry: Entry) -> None:
        """Remove an entry whose attempt has ended, however it ended."""
        entry.path.unlink(missing_ok=True)

    def recover(self, now: float) -> Recovered:
        """Clear what a crash left behind, and say what was thrown away.

        Three kinds, and only the first is a submission somebody was promised:

        - **interrupted**, found under `taken/`, dropped rather than replayed
        - **partial**, a `.tmp` from a write that did not finish, which was
          never a whole entry and was never acknowledged
        - **unreadable**, an entry at a real name that will not parse
        - **expired**, which aged out while the service was down

        The last one is why this takes a clock. Downtime counts toward the
        window: a service that was away for ten minutes must not come back and
        read out a ten minute old backlog, which is exactly the noise FR-4.9
        exists to prevent and exactly when it would be worst.
        """
        interrupted = 0
        for path in self._taken.glob(f"*{SUFFIX}"):
            path.unlink(missing_ok=True)
            interrupted += 1

        partial = 0
        for path in self.directory.glob(f"*{PARTIAL}"):
            path.unlink(missing_ok=True)
            partial += 1

        unreadable = 0
        for path in self._waiting():
            if self._read(path) is None:
                path.unlink(missing_ok=True)
                unreadable += 1

        expired = tuple(entry.submission.name for entry in self.take_expired(now))

        return Recovered(
            interrupted=interrupted,
            partial=partial,
            unreadable=unreadable,
            expired=expired,
        )
