"""The durable queue: a directory, taken in name order, surviving a restart.

Written before the implementation and expected to fail by not importing.

Nothing here mocks anything. A spool is a directory, so these tests make real
directories, write real entries, and in places reach in and corrupt one the way
a `kill -9` would. That is the seam: the thing under test is a filesystem
layout, so the filesystem is the fixture.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skid.queue import Submission
from skid.spool import Spool

FIVE_MINUTES = 300.0


def _spool(tmp_path: Path) -> Spool:
    """A spool rooted in a temporary directory."""
    return Spool(tmp_path / "spool", ttl_seconds=FIVE_MINUTES)


# COVERS: FR-4.8 | positive
def test_a_submission_is_on_disk_before_put_returns(tmp_path: Path) -> None:
    """The durable write is the promise FR-4.5 makes, so it happens first."""
    spool = _spool(tmp_path)

    spool.put(Submission(name="silo", messages=["one"]), now=1000.0)

    assert spool.pending() == 1


# COVERS: FR-4.8 | property
def test_a_spool_is_read_back_after_a_restart(tmp_path: Path) -> None:
    """A fresh Spool over the same directory finds what the old one accepted.

    This is the whole requirement. The second object stands for the process that
    comes back after `systemctl restart`.
    """
    first = _spool(tmp_path)
    first.put(Submission(name="silo", messages=["one", "two"]), now=1000.0)
    first.put(Submission(name="wrench", messages=["three"]), now=1001.0)

    second = _spool(tmp_path)
    second.recover(now=1002.0)

    assert second.pending() == 2
    taken = second.take(now=1002.0)
    assert taken is not None
    assert taken.submission.messages == ["one", "two"]


# COVERS: FR-4.3 | property
def test_entries_are_taken_in_submission_order_not_file_time(tmp_path: Path) -> None:
    """Order is the sequence in the name, because creation time is generation order.

    Every entry here is written with the SAME timestamp, so anything ordering by
    time would be free to return them in any order. The sequence in the filename
    is what makes it deterministic.
    """
    spool = _spool(tmp_path)
    for index in range(12):
        spool.put(Submission(name=f"n{index}", messages=["x"]), now=1000.0)

    order = []
    while (entry := spool.take(now=1000.0)) is not None:
        order.append(entry.submission.name)
        spool.done(entry)

    assert order == [f"n{index}" for index in range(12)]


# COVERS: FR-4.8 | edge
def test_a_half_written_entry_is_never_taken(tmp_path: Path) -> None:
    """A file at its final name is a whole file, because writing renames into place.

    A `kill -9` mid-write leaves a temporary, which start-up removes. Without the
    rename it would leave a truncated entry at the real name that parses to
    nonsense and blocks the queue behind it.
    """
    spool = _spool(tmp_path)
    spool.put(Submission(name="silo", messages=["one"]), now=1000.0)
    (spool.directory / "000999-partial.json.tmp").write_text("{ not json", "utf-8")

    assert spool.pending() == 1
    spool.recover(now=1000.0)

    assert not list(spool.directory.glob("*.tmp"))
    assert spool.pending() == 1


# COVERS: FR-4.8 | property
def test_a_submission_interrupted_mid_speech_is_dropped_not_replayed(
    tmp_path: Path,
) -> None:
    """FR-4.4 makes a submission indivisible, so there is nowhere honest to resume.

    Replaying means hearing the clips already heard again. Taking moves the entry
    aside; anything still aside at start-up was interrupted and is discarded.
    """
    spool = _spool(tmp_path)
    spool.put(Submission(name="silo", messages=["one"]), now=1000.0)
    taken = spool.take(now=1000.0)
    assert taken is not None

    restarted = _spool(tmp_path)
    dropped = restarted.recover(now=1001.0)

    assert dropped.interrupted == 1
    assert restarted.pending() == 0


# COVERS: FR-4.9 | positive
def test_a_submission_older_than_the_window_is_discarded(tmp_path: Path) -> None:
    """Five minutes on, a summary is noise read at somebody who missed it."""
    spool = _spool(tmp_path)
    spool.put(Submission(name="silo", messages=["stale"]), now=1000.0)

    assert spool.take(now=1000.0 + FIVE_MINUTES + 1) is None


# COVERS: FR-4.9 | edge
def test_the_expiry_boundary_is_the_window_itself(tmp_path: Path) -> None:
    """Exactly at the window it still speaks; past it, it does not.

    Stated as a test because five minutes is a value somebody chose, and an
    off-by-one here is silent: the message simply never arrives.
    """
    spool = _spool(tmp_path)
    spool.put(Submission(name="silo", messages=["x"]), now=1000.0)

    assert spool.take(now=1000.0 + FIVE_MINUTES) is not None


# COVERS: FR-4.9 | property
def test_expiry_does_not_block_what_is_behind_it(tmp_path: Path) -> None:
    """A stale head is discarded and the queue carries on, rather than stopping."""
    spool = _spool(tmp_path)
    spool.put(Submission(name="old", messages=["stale"]), now=1000.0)
    spool.put(Submission(name="new", messages=["fresh"]), now=1000.0 + FIVE_MINUTES)

    entry = spool.take(now=1000.0 + FIVE_MINUTES + 1)

    assert entry is not None
    assert entry.submission.name == "new"


# COVERS: FR-4.9 | property
def test_what_expired_is_recorded_rather_than_vanishing(tmp_path: Path) -> None:
    """FR-4.5 told the caller yes, so a submission not spoken owes an explanation."""
    spool = _spool(tmp_path)
    spool.put(Submission(name="silo", messages=["stale"]), now=1000.0)

    discarded = spool.take_expired(now=1000.0 + FIVE_MINUTES + 1)

    assert [entry.submission.name for entry in discarded] == ["silo"]


# COVERS: FR-7.2 | property
def test_nothing_is_rejected_at_the_door(tmp_path: Path) -> None:
    """Depth is unbounded; only age is capped. FR-7.2 stands as written."""
    spool = _spool(tmp_path)

    for index in range(200):
        spool.put(Submission(name=f"n{index}", messages=["x"]), now=1000.0)

    assert spool.pending() == 200


# COVERS: FR-4.8 | edge
def test_a_sequence_continues_across_a_restart(tmp_path: Path) -> None:
    """A fresh spool must not reuse a name still on disk, or it overwrites work."""
    first = _spool(tmp_path)
    first.put(Submission(name="silo", messages=["one"]), now=1000.0)

    second = _spool(tmp_path)
    second.put(Submission(name="wrench", messages=["two"]), now=1000.0)

    assert second.pending() == 2


# COVERS: FR-4.8 | negative
def test_an_entry_that_is_not_readable_is_discarded_not_retried(
    tmp_path: Path,
) -> None:
    """A poison entry that stopped the queue would be worse than losing it.

    The user's answer was that a failure drops the entry, so an entry that
    cannot be parsed at all takes the same path rather than being retried
    forever with everything behind it waiting.
    """
    spool = _spool(tmp_path)
    spool.put(Submission(name="silo", messages=["one"]), now=1000.0)
    entry = next(iter(sorted(spool.directory.glob("*.json"))))
    entry.write_text(json.dumps({"name": "", "messages": []}), encoding="utf-8")

    assert spool.take(now=1000.0) is None
    assert spool.pending() == 0


# COVERS: FR-4.9 | property
def test_downtime_counts_toward_the_window(tmp_path: Path) -> None:
    """A service away ten minutes must not come back and read a ten minute backlog.

    This is when the noise FR-4.9 prevents would be at its worst, and it is the
    case a clock passed only to `take` would miss: recovery happens before the
    serve loop asks for anything.
    """
    before = _spool(tmp_path)
    before.put(Submission(name="silo", messages=["stale"]), now=1000.0)
    before.put(Submission(name="wrench", messages=["also stale"]), now=1001.0)

    after = _spool(tmp_path)
    recovered = after.recover(now=1000.0 + FIVE_MINUTES + 60)

    assert recovered.expired == ("silo", "wrench")
    assert after.pending() == 0


# COVERS: FR-4.8 | positive
def test_recovery_keeps_what_is_still_current(tmp_path: Path) -> None:
    """A short restart loses nothing, which is the whole point of the spool."""
    before = _spool(tmp_path)
    before.put(Submission(name="silo", messages=["fresh"]), now=1000.0)

    after = _spool(tmp_path)
    recovered = after.recover(now=1030.0)

    assert not recovered.expired
    assert after.pending() == 1


# COVERS: FR-5.4 | property
def test_the_directory_is_owner_only(tmp_path: Path) -> None:
    """It holds what agents said, which is not for other local users to read."""
    spool = _spool(tmp_path)

    assert spool.directory.stat().st_mode & 0o777 == 0o700


# COVERS: FR-5.3 | edge
def test_taking_from_an_empty_spool_is_not_an_error(tmp_path: Path) -> None:
    """The common state, and the serve loop asks on every wakeup.

    The citation is a judgement, and the reasoning is here to be overturned.
    This is the spool-level half of what `test_an_idle_service_is_progressing`
    covers at the service level, and that test cites FR-5.3 for the same reason:
    a service parked on an empty queue is healthy, and one that errored on every
    wakeup would be wedged, which is what FR-5.3 rules out.
    """
    assert _spool(tmp_path).take(now=1000.0) is None


# COVERS: FR-4.1 | negative
@pytest.mark.parametrize("messages", [[], ["  "]])
def test_a_spool_refuses_what_the_queue_refuses(
    tmp_path: Path, messages: list[str]
) -> None:
    """Validation stays in Submission; the spool does not get a second opinion."""
    spool = _spool(tmp_path)
    if not messages:
        with pytest.raises(ValueError):
            spool.put(Submission(name="silo", messages=messages), now=1000.0)
    else:
        spool.put(Submission(name="silo", messages=messages), now=1000.0)
        assert spool.pending() == 1
