"""The config file: defaults, reading, and writing without destroying it.

Written before the implementation and expected to fail by not importing.

The write tests are the ones worth having. FR-7.1 and FR-7.8 make this file the
record, and the obligation that comes with that is writing into a file a person
owns and edits, so the comments and the ordering in it are not ours to discard.
"""

from pathlib import Path

import pytest

from skid.config import Config, load_config, save_config


# COVERS: FR-6.4 | edge
def test_a_missing_config_uses_defaults(tmp_path: Path) -> None:
    """A fresh install speaks without anyone writing a config first."""
    config = load_config(tmp_path / "config.toml")

    assert config.voice
    assert config.player


# COVERS: FR-7.5 | positive
def test_paplay_is_the_default_player(tmp_path: Path) -> None:
    """paplay follows the default sink, which is what FR-1.4 requires."""
    config = load_config(tmp_path / "config.toml")

    assert config.player == "paplay {file}"


# COVERS: FR-7.4 | positive
def test_the_window_defaults_to_thirty_seconds(tmp_path: Path) -> None:
    """Thirty seconds is short by choice: a name that pauses re-announces."""
    config = load_config(tmp_path / "config.toml")

    assert config.greeting_window_seconds == 30


# COVERS: FR-6.2 | positive
def test_the_voice_is_read_from_the_config(tmp_path: Path) -> None:
    """A person sets the voice by editing the file, with no agent involved."""
    path = tmp_path / "config.toml"
    path.write_text('voice = "af_bella"\n', encoding="utf-8")

    assert load_config(path).voice == "af_bella"


# COVERS: FR-3.4 | positive
def test_the_window_is_read_from_the_config(tmp_path: Path) -> None:
    """The window is configurable, and 30 seconds is only its default."""
    path = tmp_path / "config.toml"
    path.write_text("greeting_window_seconds = 5\n", encoding="utf-8")

    assert load_config(path).greeting_window_seconds == 5


# COVERS: FR-6.4 | positive
def test_the_first_write_creates_the_file(tmp_path: Path) -> None:
    """The file is created by the first write rather than required up front."""
    path = tmp_path / "nested" / "config.toml"

    save_config(Config(voice="af_bella"), path)

    assert path.exists()
    assert load_config(path).voice == "af_bella"


# COVERS: FR-7.1 | property
def test_writing_preserves_comments(tmp_path: Path) -> None:
    """A comment is the only place a reason can live, so a write keeps it.

    This is the obligation that came with making the file the record: skid
    writes into a file a person owns, and a parse-and-re-emit would silently
    discard everything they wrote around the values.
    """
    path = tmp_path / "config.toml"
    path.write_text(
        '# chosen because it is easiest to hear across the room\nvoice = "af_bella"\n',
        encoding="utf-8",
    )

    config = load_config(path)
    config.voice = "af_heart"
    save_config(config, path)

    written = path.read_text(encoding="utf-8")
    assert "easiest to hear across the room" in written
    assert "af_heart" in written


# COVERS: FR-8.4 | property
def test_writing_preserves_the_order_of_substitutions(tmp_path: Path) -> None:
    """Entry order decides which substitution wins, so a write must not sort it."""
    path = tmp_path / "config.toml"
    path.write_text(
        "[[substitution]]\n"
        'kind = "literal"\n'
        'pattern = "zebra"\n'
        'replacement = "zeh bra"\n'
        "\n"
        "[[substitution]]\n"
        'kind = "literal"\n'
        'pattern = "aardvark"\n'
        'replacement = "ard vark"\n',
        encoding="utf-8",
    )

    config = load_config(path)
    save_config(config, path)

    reread = load_config(path)
    assert [entry.pattern for entry in reread.substitutions] == ["zebra", "aardvark"]


# COVERS: FR-6.4 | negative
def test_a_malformed_config_is_an_error_and_is_not_replaced(tmp_path: Path) -> None:
    """Missing is fine; unparseable is not, and overwriting it would destroy it.

    FR-6.4 covers a file that is absent. A file that is present and broken is a
    different case, and defaulting past it would silently discard the
    substitution set FR-7.8 calls the more painful thing to lose.
    """
    path = tmp_path / "config.toml"
    original = 'voice = "af_bella'
    path.write_text(original, encoding="utf-8")

    with pytest.raises(ValueError):
        load_config(path)

    assert path.read_text(encoding="utf-8") == original
