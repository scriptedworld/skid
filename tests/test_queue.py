"""A submission: what one is, and what it refuses to be.

`SubmissionQueue` used to live here and was deleted on 2026-08-28. FR-4.8 made
the queue durable, so the queue is a directory now and `Spool` is it; keeping an
in-memory one beside it would have been two queues, which is the bug rather than
the belt and braces.

Its tests moved rather than went. `test_spool.py` covers the queue properties
FR-7.2 and FR-4.3 against the thing that is actually the queue, and what remains
here is the part that was never about queueing: a submission validating itself.

Leaving the class in would have been worse than deleting it. Nothing but its own
tests used it, so the suite would have gone on passing over code no running skid
could reach, which is the vacuous pass `docs/PROJECT.md` warns about.
"""

import pytest

from skid.queue import Submission


# COVERS: FR-4.1 | positive
def test_text_arrives_as_an_array() -> None:
    """A submission carries a list of messages, not one string."""
    submission = Submission(name="silo", messages=["one", "two"])

    assert submission.messages == ["one", "two"]


# COVERS: FR-4.3 | positive
def test_the_messages_of_a_submission_keep_their_order() -> None:
    """Order within a submission is the caller's, and nothing reorders it."""
    submission = Submission(name="silo", messages=["first", "second", "third"])

    assert submission.messages == ["first", "second", "third"]


# COVERS: FR-4.1 | edge
def test_an_array_of_one_is_not_a_special_case() -> None:
    """The common call is one message, and it takes the same path as ten."""
    submission = Submission(name="silo", messages=["alone"])

    assert submission.messages == ["alone"]


# COVERS: FR-3.1 | negative
def test_a_submission_without_a_name_is_refused() -> None:
    """Every submission carries the name of the engine that sent it."""
    with pytest.raises(ValueError):
        Submission(name="   ", messages=["one"])


# COVERS: FR-4.1 | negative
def test_a_submission_saying_nothing_is_refused() -> None:
    """An empty array is a caller mistake, and silence is not a thing to queue."""
    with pytest.raises(ValueError):
        Submission(name="silo", messages=[])
