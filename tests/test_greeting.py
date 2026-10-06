"""The quiet window: who gets announced, and against which clock.

The decision is deliberately a pure function of a table, a name and a time, so
that FR-3.5's rule about *when* it is evaluated can be tested by passing the
time the caller would pass. The pipeline placement itself needs a running
backend and is covered separately.
"""

import pytest

from skid.greeting import QuietTable, greeting_for, should_greet

WINDOW = 30.0


# COVERS FR-3.2 | positive
def test_a_name_not_heard_recently_is_greeted() -> None:
    """The first thing heard from a name in a while announces itself."""
    table = QuietTable()

    assert should_greet(table, "silo", now=1000.0, window=WINDOW) is True


# COVERS FR-3.2 | positive
def test_the_greeting_names_the_speaker() -> None:
    """A listener learns who is talking without the message saying so."""
    assert greeting_for("silo") == "Hi, silo here."


# COVERS FR-3.2 | positive
def test_the_greeting_names_the_work() -> None:
    """With sessions across projects, the name alone no longer says where."""
    assert greeting_for("ramona", "omnikey") == "Hi, ramona here, in omnikey."


# COVERS FR-3.7 | property
def test_the_work_is_spoken_exactly_as_given() -> None:
    """skid speaks what it is given, so a path or a phrase arrives untouched."""
    for work in ["the home directory", "~/.projects/skid", "OmniKey"]:
        assert greeting_for("ramona", work) == f"Hi, ramona here, in {work}."


# COVERS FR-3.9 | positive
def test_no_work_is_the_name_alone() -> None:
    """A caller that names nothing is introduced as it always was."""
    assert greeting_for("ramona", None) == "Hi, ramona here."


# COVERS FR-3.2 | property
def test_a_name_on_new_work_is_greeted_inside_the_window() -> None:
    """The window belongs to the name and the work together.

    Five seconds after ramona finished in omnikey she is quiet there and new in
    skid, and her name alone would have said nothing about the move.
    """
    table = QuietTable()
    table.record_finished("ramona", when=1000.0, work="omnikey")

    assert (
        should_greet(table, "ramona", now=1005.0, window=WINDOW, work="omnikey")
        is False
    )
    assert should_greet(table, "ramona", now=1005.0, window=WINDOW, work="skid") is True


# COVERS FR-3.3 | positive
def test_a_name_heard_moments_ago_is_not_greeted() -> None:
    """The prefix identifies a speaker, not a message."""
    table = QuietTable()
    table.record_finished("silo", when=1000.0)

    assert should_greet(table, "silo", now=1005.0, window=WINDOW) is False


# COVERS FR-7.4 | edge
def test_the_window_boundary_is_the_window_itself() -> None:
    """Exactly at the window the name is still quiet; past it, it is not.

    Stated as a test because 30 seconds is a value somebody chose, and an
    off-by-one here is inaudible until somebody notices a greeting that should
    not have come.
    """
    table = QuietTable()
    table.record_finished("silo", when=1000.0)

    assert should_greet(table, "silo", now=1029.9, window=WINDOW) is False
    assert should_greet(table, "silo", now=1030.1, window=WINDOW) is True


# COVERS FR-3.2 | property
def test_the_window_is_per_name() -> None:
    """One agent talking continuously does not suppress another's announcement."""
    table = QuietTable()
    table.record_finished("silo", when=1000.0)

    assert should_greet(table, "silo", now=1005.0, window=WINDOW) is False
    assert should_greet(table, "wrench", now=1005.0, window=WINDOW) is True


# COVERS FR-7.4 | regression
def test_the_clock_is_the_end_of_speech_not_the_submission() -> None:
    """The table records when a clip finished, which is what a listener heard.

    Under FR-7.2's unbounded queue the two can differ by minutes. Recording the
    submission time here would announce a name whose voice was still in the
    room, which is the failure FR-7.4 names.
    """
    table = QuietTable()
    table.record_finished("silo", when=1200.0)

    assert should_greet(table, "silo", now=1210.0, window=WINDOW) is False


# COVERS FR-3.6 | positive
def test_a_fresh_table_greets_everyone() -> None:
    """The table is memory only, so a restart costs one greeting per name.

    Asserting the cost rather than a benefit: this is the behaviour chosen over
    persisting thirty seconds of state to disk.
    """
    table = QuietTable()
    table.record_finished("silo", when=1000.0)

    assert should_greet(QuietTable(), "silo", now=1005.0, window=WINDOW) is True


# COVERS FR-3.4 | positive
def test_a_shorter_window_greets_sooner() -> None:
    """The window is configurable, and the decision honours whatever it is."""
    table = QuietTable()
    table.record_finished("silo", when=1000.0)

    assert should_greet(table, "silo", now=1005.0, window=2.0) is True
    # Both directions, because the True one alone holds whatever the window is:
    # asserted that way, this passed against a `should_greet` that ignored the
    # window entirely and greeted every time.
    assert should_greet(table, "silo", now=1005.0, window=10.0) is False


# COVERS FR-3.1 | negative
def test_an_empty_name_is_refused() -> None:
    """A name identifies the submitting engine, so there has to be one."""
    with pytest.raises(ValueError):
        greeting_for("")
