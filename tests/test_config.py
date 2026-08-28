"""The config file: defaults, reading, and writing what a person can read back.

The write tests are the ones worth having. FR-7.1 and FR-7.8 make this file the
record, and the obligation that comes with that is writing into a file somebody
owns and edits, so the ordering in it is not ours to discard.

**The comment half of that obligation is retired**, 2026-08-28, with the move
from TOML to YAML. `docs/config.sample.yaml` is where a reason lives now, and
the live file is emitted canonically. `test_writing_preserves_comments` went
with it; what replaced it asserts the thing that still has to be true, which is
that a person's ordering survives a write.
"""

from pathlib import Path

import pytest
import wrench

from skid.config import Config, load_config, save_config
from skid.substitution import Substitution

CHECKOUT = Path(__file__).resolve().parent.parent
"""The real checkout, read from but never written to."""


def _write(path: Path, text: str) -> Path:
    """Write a config file as a person would, and return the path."""
    path.write_text(text, encoding="utf-8")
    return path


# COVERS: FR-6.4 | edge
def test_a_missing_config_uses_defaults(tmp_path: Path) -> None:
    """A fresh install speaks without anyone writing a config first."""
    config = load_config(tmp_path / "config.yaml")

    assert config.voice
    assert config.player


# COVERS: FR-7.5 | positive
def test_paplay_is_the_default_player(tmp_path: Path) -> None:
    """paplay follows the default sink, which is what FR-1.4 requires."""
    config = load_config(tmp_path / "config.yaml")

    assert config.player == "paplay {file}"


# COVERS: FR-7.4 | positive
def test_the_window_defaults_to_thirty_seconds(tmp_path: Path) -> None:
    """Thirty seconds is short by choice: a name that pauses re-announces."""
    config = load_config(tmp_path / "config.yaml")

    assert config.greeting_window_seconds == 30


# COVERS: FR-6.2 | positive
def test_the_voice_is_read_from_the_config(tmp_path: Path) -> None:
    """A person sets the voice by editing the file, with no agent involved.

    Written unquoted, which is how a person writes YAML rather than how wrench
    emits it. Both have to load, or the file is only editable by skid.
    """
    path = _write(tmp_path / "config.yaml", "voice: af_bella\n")

    assert load_config(path).voice == "af_bella"


# COVERS: FR-3.4 | positive
def test_the_window_is_read_from_the_config(tmp_path: Path) -> None:
    """The window is configurable, and 30 seconds is only its default."""
    path = _write(tmp_path / "config.yaml", "greeting_window_seconds: 5\n")

    assert load_config(path).greeting_window_seconds == 5


# COVERS: FR-6.4 | positive
def test_the_first_write_creates_the_file(tmp_path: Path) -> None:
    """The file is created by the first write rather than required up front."""
    path = tmp_path / "nested" / "config.yaml"

    save_config(Config(voice="af_bella"), path)

    assert path.exists()
    assert load_config(path).voice == "af_bella"


# COVERS: FR-7.1 | property
def test_a_written_config_reads_back_as_what_was_written(tmp_path: Path) -> None:
    """The record is only a record if skid can read its own writing.

    What this replaced asserted that a comment survived a write, which was
    `tomlkit`'s job and is retired. The obligation that outlived it is smaller
    and more important: a value set through a tool has to be there on the next
    start, whatever the file looks like in between.
    """
    path = tmp_path / "config.yaml"
    written = Config(voice="af_bella", expiry_seconds=42, greeting_window_seconds=7)

    save_config(written, path)

    assert load_config(path) == written


# COVERS: FR-8.4 | property
def test_writing_preserves_the_order_of_substitutions(tmp_path: Path) -> None:
    """Entry order decides which substitution wins, so a write must not sort it.

    `zebra` before `aardvark` on purpose: alphabetical order would reverse them,
    so a writer that sorted the list would fail this rather than pass by luck.
    Note that wrench sorts the *keys* of a mapping, which is why this asserts a
    sequence and not the file's bytes.
    """
    path = _write(
        tmp_path / "config.yaml",
        "substitution:\n"
        "  - kind: literal\n"
        "    pattern: zebra\n"
        "    replacement: zeh bra\n"
        "  - kind: literal\n"
        "    pattern: aardvark\n"
        "    replacement: ard vark\n",
    )

    save_config(load_config(path), path)

    reread = load_config(path)
    assert [entry.pattern for entry in reread.substitutions] == ["zebra", "aardvark"]


# COVERS: FR-6.4 | negative
def test_a_malformed_config_is_an_error_and_is_not_replaced(tmp_path: Path) -> None:
    """Missing is fine; unparseable is not, and overwriting it would destroy it.

    FR-6.4 covers a file that is absent. A file that is present and broken is a
    different case, and defaulting past it would silently discard the
    substitution set FR-7.8 calls the more painful thing to lose.
    """
    original = "voice: [unclosed\n"
    path = _write(tmp_path / "config.yaml", original)

    with pytest.raises(ValueError):
        load_config(path)

    assert path.read_text(encoding="utf-8") == original


# COVERS: FR-6.4 | negative
def test_a_config_of_the_wrong_shape_says_which_key_is_wrong(tmp_path: Path) -> None:
    """The schema's whole return: a message naming the key, not "will not parse".

    `greeting_window_seconds: thirty` used to load, because nothing checked the
    type, and then failed somewhere downstream where the config was long out of
    sight. The message now carries the path into the document.
    """
    path = _write(tmp_path / "config.yaml", "greeting_window_seconds: thirty\n")

    with pytest.raises(ValueError, match="greeting_window_seconds"):
        load_config(path)


# COVERS: FR-6.4 | negative
def test_a_misspelt_key_is_refused_rather_than_ignored(tmp_path: Path) -> None:
    """A deliberate behaviour change, and the reason the schema is worth having.

    `voce: af_bella` used to load fine and do nothing. The only symptom was skid
    speaking in the wrong voice, with a config file in front of you that appears
    to say otherwise. It is refused by name now.
    """
    path = _write(tmp_path / "config.yaml", "voce: af_bella\n")

    with pytest.raises(ValueError, match="voce"):
        load_config(path)


# COVERS: FR-6.2 | property
def test_the_sample_config_is_a_config_skid_can_read() -> None:
    """The sample is the only place the shape is written down for a person.

    It is prose that looks like configuration, which is exactly the kind of file
    that drifts from what the software accepts and is never run. Loading it here
    means a key renamed in the schema and not in the sample fails the suite.

    Every value in it is a default, so the loaded config equals a default one
    apart from the substitutions it demonstrates.
    """
    sample = CHECKOUT / "docs" / "config.sample.yaml"

    config = load_config(sample)

    assert config == Config(
        substitutions=[
            Substitution(kind="literal", pattern="kokoro", replacement="koh koh roh"),
            Substitution(
                kind="regex",
                pattern=r"\bFR-([0-9]+)\.([0-9]+)\b",
                replacement=r"requirement \1 point \2",
            ),
        ]
    )


# COVERS: FR-7.1 | negative
def test_a_config_skid_could_not_read_back_is_refused_on_write(
    tmp_path: Path,
) -> None:
    """Validated on the way out, so a bug here fails where a bad file would.

    A tool that stored a shape the schema refuses would leave a file skid can
    never read again, and would tell the caller the write succeeded. The write
    path checks the same document the read path does.
    """
    path = tmp_path / "config.yaml"

    with pytest.raises(wrench.ValidationError):
        save_config(Config(expiry_seconds=0), path)

    assert not path.exists()
