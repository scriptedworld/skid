"""Substitution semantics: what is replaced, in what order, and only once.

These tests are written before the implementation and are expected to fail by
not importing. The failure names what is missing, which is the point of writing
them first.

The cases here are the ones the spec review turned up, where FR-8.5 and an
earlier draft of the spec disagreed about which of two matching entries wins.
"""

import pytest
from skid.substitution import Substitution, apply_substitutions


# COVERS: FR-8.2 | positive
def test_a_replacement_need_not_be_a_word() -> None:
    """A phonetic spelling is a valid replacement, because it is heard."""
    entries = [
        Substitution(kind="literal", pattern="kokoro", replacement="koh koh roh")
    ]

    assert apply_substitutions(entries, "kokoro speaks") == "koh koh roh speaks"


# COVERS: FR-8.4 | positive
def test_entries_apply_in_file_order() -> None:
    """The first entry that matches at a position wins, and file order is that order."""
    entries = [
        Substitution(kind="literal", pattern="mcp", replacement="em see pee"),
        Substitution(kind="literal", pattern="mcp", replacement="wrong"),
    ]

    assert apply_substitutions(entries, "mcp") == "em see pee"


# COVERS: FR-8.4 | regression
def test_reordering_the_file_changes_the_result() -> None:
    """Order is the only priority, so swapping two entries swaps which one wins.

    This is what makes FR-8.4's promise real: a person fixes an interaction
    between two entries by moving a line, and nothing else decides it.
    """
    first = Substitution(kind="literal", pattern="mcp", replacement="em see pee")
    second = Substitution(kind="literal", pattern="mcp", replacement="mick pee")

    assert apply_substitutions([first, second], "mcp") == "em see pee"
    assert apply_substitutions([second, first], "mcp") == "mick pee"


# COVERS: FR-8.5 | property
def test_a_replacement_is_not_re_examined() -> None:
    """What one entry produces is never matched by another, nor by itself.

    Without this the second entry would fire on the first's output, and an entry
    whose replacement contains its own pattern would not terminate.
    """
    entries = [
        Substitution(kind="literal", pattern="a", replacement="bb"),
        Substitution(kind="literal", pattern="b", replacement="c"),
    ]

    assert apply_substitutions(entries, "a") == "bb"


# COVERS: FR-8.5 | regression
def test_overlapping_entries_take_the_earlier_position() -> None:
    """Position is the primary order; file order only breaks ties at a position.

    The case that caught the contradiction. FR-8.5 said the earlier entry in the
    file wins an overlapping region, while the spec said a left-to-right scan.
    They disagree here: entry priority gives `ax`, position gives `Z`.
    """
    entries = [
        Substitution(kind="regex", pattern="b", replacement="x"),
        Substitution(kind="literal", pattern="ab", replacement="Z"),
    ]

    assert apply_substitutions(entries, "ab") == "Z"


# COVERS: FR-7.7 | positive
def test_both_kinds_are_supported() -> None:
    """An entry declares whether its pattern is a literal or a regular expression."""
    entries = [
        Substitution(
            kind="literal", pattern="v1.2", replacement="version one point two"
        ),
        Substitution(kind="regex", pattern=r"\bFR-(\d+)", replacement=r"requirement"),
    ]

    spoken = apply_substitutions(entries, "v1.2 covers FR-4")

    assert spoken == "version one point two covers requirement"


# COVERS: FR-7.7 | negative
def test_an_invalid_regex_is_refused() -> None:
    """A pattern that does not compile is rejected where it is declared.

    It must not reach the substitution set, because a stored bad pattern would
    break every later submission rather than the call that made it.
    """
    with pytest.raises(ValueError):
        Substitution(kind="regex", pattern="(unclosed", replacement="never")


# COVERS: FR-8.2 | edge
def test_a_literal_matches_on_word_boundaries() -> None:
    """A literal does not fire inside a longer word it was not aimed at."""
    entries = [Substitution(kind="literal", pattern="cat", replacement="kat")]

    assert apply_substitutions(entries, "concatenate the cat") == "concatenate the kat"


# COVERS: FR-8.2 | edge
def test_a_literal_is_case_insensitive() -> None:
    """kokoro says a word wrongly whatever case it was written in."""
    entries = [
        Substitution(kind="literal", pattern="kokoro", replacement="koh koh roh")
    ]

    assert apply_substitutions(entries, "Kokoro") == "koh koh roh"


# COVERS: FR-8.5 | edge
def test_an_empty_set_leaves_the_text_alone() -> None:
    """No entries is not a special case, and it is the common one."""
    assert apply_substitutions([], "nothing to do here") == "nothing to do here"
