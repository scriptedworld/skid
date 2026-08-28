"""Playback: running a configured command, one at a time, and giving up on it.

Written before the implementation and expected to fail by not importing.

The player takes a path and runs a command line. It does not know what audio is,
so these tests hand it ordinary files and configure real scripts as the player.
Nothing here is a double: FR-7.5 makes the player a command line on purpose, and
that is the seam.
"""

import time
from pathlib import Path

import pytest
from skid.player import PlaybackFailed, Player


def _recording_player(script: Path, log: Path) -> str:
    """Write a player that records when it started and stopped, and return it."""
    script.write_text(
        "#!/bin/sh\n"
        f'echo "start $(date +%s.%N)" >> {log}\n'
        "sleep 0.2\n"
        f'echo "end $(date +%s.%N)" >> {log}\n',
        encoding="utf-8",
    )
    script.chmod(0o755)
    return f"{script} {{file}}"


# COVERS: FR-1.3 | positive
def test_the_player_runs_as_a_subprocess(tmp_path: Path) -> None:
    """A file is played by running a command, not by opening a device."""
    seen = tmp_path / "seen"
    script = tmp_path / "player.sh"
    script.write_text(f'#!/bin/sh\necho "$1" > {seen}\n', encoding="utf-8")
    script.chmod(0o755)
    clip = tmp_path / "clip.wav"
    clip.write_bytes(b"not really audio")

    Player(command=f"{script} {{file}}").play(clip)

    assert seen.read_text(encoding="utf-8").strip() == str(clip)


# COVERS: FR-1.4 | negative
def test_no_device_is_named_on_the_command(tmp_path: Path) -> None:
    """skid does not select an output device, so it passes none.

    Whatever the default sink is at the moment the clip plays is what the player
    finds, including one that changed since the clip was generated.
    """
    seen = tmp_path / "seen"
    script = tmp_path / "player.sh"
    script.write_text(f'#!/bin/sh\necho "$@" > {seen}\n', encoding="utf-8")
    script.chmod(0o755)
    clip = tmp_path / "clip.wav"
    clip.write_bytes(b"x")

    Player(command=f"{script} {{file}}").play(clip)

    assert seen.read_text(encoding="utf-8").split() == [str(clip)]


# COVERS: FR-2.1 | property
def test_two_clips_never_overlap(tmp_path: Path) -> None:
    """At most one clip is audible, tested as no two playbacks overlapping.

    Simultaneity cannot be heard by a suite. What is observable is that the
    player process is never running twice at once, which the recording script
    reports by timestamping its start and its end.
    """
    log = tmp_path / "log"
    player = Player(command=_recording_player(tmp_path / "player.sh", log))
    clip = tmp_path / "clip.wav"
    clip.write_bytes(b"x")

    player.play_all([clip, clip, clip])

    events = [
        line.split() for line in log.read_text(encoding="utf-8").split("\n") if line
    ]
    kinds = [kind for kind, _ in events]
    assert kinds == ["start", "end", "start", "end", "start", "end"]


# COVERS: FR-1.9 | edge
def test_a_player_that_never_exits_is_killed(tmp_path: Path) -> None:
    """A stuck player must not hold the lock for ever and silence the machine."""
    clip = tmp_path / "clip.wav"
    clip.write_bytes(b"x")
    player = Player(command="sh -c 'sleep 600'", timeout=0.5)

    started = time.monotonic()
    with pytest.raises(PlaybackFailed):
        player.play(clip)

    assert time.monotonic() - started < 30


# COVERS: FR-4.6 | negative
def test_one_failing_clip_does_not_stop_the_rest(tmp_path: Path) -> None:
    """A clip that cannot be played is reported and skipped, and the queue runs on."""
    seen = tmp_path / "seen"
    script = tmp_path / "player.sh"
    script.write_text(
        f'#!/bin/sh\ncase "$1" in *bad*) exit 1 ;; esac\necho "$1" >> {seen}\n',
        encoding="utf-8",
    )
    script.chmod(0o755)
    good = tmp_path / "good.wav"
    bad = tmp_path / "bad.wav"
    for clip in (good, bad):
        clip.write_bytes(b"x")

    outcomes = Player(command=f"{script} {{file}}").play_all([good, bad, good])

    assert [outcome.ok for outcome in outcomes] == [True, False, True]
    assert seen.read_text(encoding="utf-8").count(str(good)) == 2


# COVERS: FR-1.8 | negative
def test_a_player_returning_early_overlaps_and_skid_does_not_prevent_it(
    tmp_path: Path,
) -> None:
    """The documented limit: exclusion is only as good as the player's exit.

    FR-7.5 allows any command line, so a player that backgrounds itself releases
    the lock while its audio is still going. skid cannot detect that, and this
    test asserts the limit rather than a guarantee skid does not provide.
    """
    log = tmp_path / "log"
    script = tmp_path / "player.sh"
    script.write_text(
        f'#!/bin/sh\n( echo "start $(date +%s.%N)" >> {log}; sleep 0.3;'
        f' echo "end $(date +%s.%N)" >> {log} ) &\n',
        encoding="utf-8",
    )
    script.chmod(0o755)
    clip = tmp_path / "clip.wav"
    clip.write_bytes(b"x")

    Player(command=f"{script} {{file}}").play_all([clip, clip])
    time.sleep(0.6)

    kinds = [
        line.split()[0] for line in log.read_text(encoding="utf-8").split("\n") if line
    ]
    assert kinds == ["start", "start", "end", "end"]
