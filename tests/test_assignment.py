"""Who gets which voice, and for how long they keep it.

The same shape as `test_greeting`: the decisions take their clock from the
caller, so six hours is a number passed in rather than a wait. Nothing here
reaches kokoro, because assignment is a question about a table and a list.

The voice ids are real ones from the shortlist, so a reader can tell at a glance
that `if_sara` carrying `pipeline="a"` is the case FR-10.7 exists for.
"""

from __future__ import annotations

from skid.assignment import DEFAULT_WINDOW_SECONDS, Assignments, VoiceChoice

WINDOW = 6 * 60 * 60.0

SHORTLIST = [
    VoiceChoice(alias="Ashley", voice="af_alloy"),
    VoiceChoice(alias="Brian", voice="am_echo"),
    VoiceChoice(alias="Wendy", voice="if_sara", pipeline="a"),
]


def assigned(table: Assignments, name: str, now: float) -> VoiceChoice:
    """The voice for a name, refusing None so a reader and a checker agree.

    `voice_for` returns None only for an empty shortlist, which one test covers
    deliberately and no other one reaches. Asserting it here rather than in each
    caller keeps that fact in one place.
    """
    choice = table.voice_for(name, now=now, window=WINDOW)
    assert choice is not None
    return choice


# COVERS: FR-10.1 | property
def test_only_a_configured_voice_is_ever_assigned() -> None:
    """The pool is the config's list, so nothing kokoro offers leaks into it.

    Asserted over more names than there are voices, because the interesting case
    is the one where assignment has to reuse and could otherwise reach past the
    list for something free.
    """
    assignments = Assignments(SHORTLIST)
    allowed = {choice.voice for choice in SHORTLIST}

    handed_out = {
        assigned(assignments, f"agent-{index}", now=1000.0).voice for index in range(10)
    }

    assert handed_out <= allowed


# COVERS: FR-10.1 | edge
def test_an_empty_shortlist_assigns_nobody() -> None:
    """No `voices` in the config means the single `voice` setting still rules.

    The way skid behaved before assignment existed, kept reachable so adding the
    feature does not force a config on anybody.
    """
    assignments = Assignments([])

    assert assignments.voice_for("silo", now=1000.0, window=WINDOW) is None


# COVERS: FR-10.2 | positive
def test_a_name_keeps_the_same_voice_across_submissions() -> None:
    """The point of the feature: silo sounds like silo the second time too."""
    assignments = Assignments(SHORTLIST)

    first = assignments.voice_for("silo", now=1000.0, window=WINDOW)
    second = assignments.voice_for("silo", now=1200.0, window=WINDOW)

    assert first == second


# COVERS: FR-10.2 | property
def test_two_names_speaking_together_get_different_voices() -> None:
    """Distinctness is the whole purpose, so a shared voice while both are live
    would satisfy 'a name keeps one voice' and defeat the requirement."""
    assignments = Assignments(SHORTLIST)

    silo = assigned(assignments, "silo", now=1000.0)
    wrench = assigned(assignments, "wrench", now=1000.0)

    assert silo.voice != wrench.voice


# COVERS: FR-10.3 | positive
def test_an_assignment_is_released_once_its_name_goes_quiet() -> None:
    """A session that ended stops holding a voice, which is what frees the pool.

    Checked by the voice becoming available again rather than by reading the
    table, because availability is the observable the requirement is about.
    """
    assignments = Assignments(SHORTLIST)
    held = assignments.voice_for("gone", now=1000.0, window=WINDOW)

    released = assignments.release_expired(now=1000.0 + WINDOW + 1, window=WINDOW)

    assert released == ["gone"]
    assert len(assignments.held()) == 0
    assert (
        assignments.voice_for("fresh", now=1000.0 + WINDOW + 2, window=WINDOW) == held
    )


# COVERS: FR-10.3 | edge
def test_a_name_inside_the_window_keeps_its_voice() -> None:
    """The boundary is the window itself, so a name one second short still holds."""
    assignments = Assignments(SHORTLIST)
    assignments.voice_for("silo", now=1000.0, window=WINDOW)

    assert assignments.release_expired(now=1000.0 + WINDOW - 1, window=WINDOW) == []
    assert len(assignments.held()) == 1


# COVERS: FR-10.4 | positive
def test_speaking_refreshes_the_window() -> None:
    """A session talking steadily for longer than the window keeps its voice.

    Without the refresh this is the failure: the assignment would be a lease
    running from when it was granted, and a busy session would lose its voice
    mid-conversation.
    """
    assignments = Assignments(SHORTLIST)
    held = assignments.voice_for("silo", now=1000.0, window=WINDOW)

    assignments.record_spoken("silo", when=1000.0 + WINDOW - 10)
    later = 1000.0 + WINDOW + 10

    assert assignments.release_expired(now=later, window=WINDOW) == []
    assert assignments.voice_for("silo", now=later, window=WINDOW) == held


# COVERS: FR-10.5 | positive
def test_the_assignment_window_is_six_hours() -> None:
    """A value somebody chose, so it is stated where changing it breaks a test."""
    assert DEFAULT_WINDOW_SECONDS == 6 * 60 * 60


# COVERS: FR-10.6 | positive
def test_an_exhausted_shortlist_reuses_the_quietest_voice() -> None:
    """Assignment never refuses, and the collision lands on the oldest voice.

    Three voices are held and each has spoken at a different time. The fourth
    name has to double up, and the requirement says which one it doubles up on.
    """
    assignments = Assignments(SHORTLIST)
    for index, name in enumerate(["first", "second", "third"]):
        assignments.voice_for(name, now=1000.0, window=WINDOW)
        assignments.record_spoken(name, when=2000.0 + index * 100)

    quietest = assignments.voice_for("first", now=3000.0, window=WINDOW)
    overflow = assignments.voice_for("fourth", now=3000.0, window=WINDOW)

    assert overflow == quietest


# COVERS: FR-10.6 | property
def test_assignment_never_returns_nothing_while_the_list_has_entries() -> None:
    """Refusal was one of the options and was not chosen, so a name always sings."""
    assignments = Assignments(SHORTLIST)

    everybody = [
        assignments.voice_for(f"agent-{index}", now=1000.0 + index, window=WINDOW)
        for index in range(len(SHORTLIST) * 3)
    ]

    assert all(choice is not None for choice in everybody)


# COVERS: FR-10.7 | positive
def test_a_choice_carries_the_pipeline_it_declared() -> None:
    """Sara's timbre with English pronunciation, which is what was chosen by ear.

    The absence of a pipeline is a distinct value from naming one, because None
    means 'the id decides' and `generation` resolves it.
    """
    assignments = Assignments(SHORTLIST)

    by_alias = {choice.alias: choice for choice in assignments.choices}

    assert by_alias["Wendy"].pipeline == "a"
    assert by_alias["Ashley"].pipeline is None


# COVERS: FR-10.9 | property
def test_a_fresh_table_holds_nothing() -> None:
    """A restart reassigns, which is what not persisting means from outside.

    There is no file to assert the absence of, so the observable is that a table
    built from the same config knows nobody.
    """
    assignments = Assignments(SHORTLIST)
    assignments.voice_for("silo", now=1000.0, window=WINDOW)

    restarted = Assignments(SHORTLIST)

    assert len(assignments.held()) == 1
    assert len(restarted.held()) == 0
