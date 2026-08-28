"""The submission queue: what goes in comes out, in order, and nothing is dropped.

Written before the implementation and expected to fail by not importing.

The queue holds submissions. It does not know what a clip is, so none of this
needs audio, a generator or a player.
"""

from skid.queue import Submission, SubmissionQueue


# COVERS: FR-7.2 | edge
def test_an_empty_queue_has_nothing_waiting() -> None:
    """The starting state, and the common one."""
    assert SubmissionQueue().pending() == 0


# COVERS: FR-4.1 | positive
def test_one_submission_goes_in_and_comes_out() -> None:
    """An array is submitted whole and taken whole."""
    queue = SubmissionQueue()
    submission = Submission(name="silo", messages=["first", "second"])

    queue.put(submission)

    assert queue.pending() == 1
    assert queue.take() == submission
    assert queue.pending() == 0


# COVERS: FR-7.2 | positive
def test_submissions_come_out_in_the_order_they_went_in() -> None:
    """An arrival queues behind what is already waiting."""
    queue = SubmissionQueue()
    first = Submission(name="silo", messages=["a"])
    second = Submission(name="wrench", messages=["b"])

    queue.put(first)
    queue.put(second)

    assert queue.take() == first
    assert queue.take() == second


# COVERS: FR-4.4 | property
def test_a_submission_is_taken_whole_rather_than_a_message_at_a_time() -> None:
    """Two submissions never interleave, which is what taking whole ones means.

    Taking one message from each waiting submission in turn would satisfy
    FR-4.3 and FR-7.2 both, and make a listener follow two speakers at once.
    """
    queue = SubmissionQueue()
    queue.put(Submission(name="silo", messages=["a1", "a2", "a3"]))
    queue.put(Submission(name="wrench", messages=["b1"]))

    assert queue.take().messages == ["a1", "a2", "a3"]
    assert queue.take().messages == ["b1"]


# COVERS: FR-4.3 | positive
def test_the_messages_of_a_submission_keep_their_order() -> None:
    """An array is spoken in the order given."""
    submission = Submission(name="silo", messages=["one", "two", "three"])

    assert submission.messages == ["one", "two", "three"]


# COVERS: FR-7.2 | property
def test_nothing_is_rejected_however_much_is_waiting() -> None:
    """The queue is unbounded: arrivals wait, they are never turned away.

    Unboundedness has no value to assert, so what is tested is the absence of a
    cap. A hundred is not a magic number; it is more than any bound anyone
    would have chosen silently.
    """
    queue = SubmissionQueue()

    for index in range(100):
        queue.put(Submission(name="silo", messages=[str(index)]))

    assert queue.pending() == 100


# COVERS: FR-4.1 | edge
def test_an_array_of_one_is_not_a_special_case() -> None:
    """A single message is sent as an array of one, like everything else."""
    queue = SubmissionQueue()
    queue.put(Submission(name="silo", messages=["only"]))

    assert queue.take().messages == ["only"]
