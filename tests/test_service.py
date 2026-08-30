"""The service: the units composed into the order a listener hears.

Written before the implementation and expected to fail by not importing.

These run against the real generator, so they are slower than the unit tests and
use deliberately short text. Composition is what they check: each unit is tested
on its own already, and what is left is whether they are wired in the right
order.

One warm generator is shared across the module, which is not a test convenience
so much as the arrangement FR-5.1 asks for. Building one per test would reload
the model each time.

The greeting test is the reason this file exists. Every row it touches is
satisfied by a design that decides the prefix at queue time, and the audible
behaviour is still wrong.
"""

import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from skid.config import Config, load_config
from skid.generation import Generator
from skid.routes import build_app
from skid.service import PROGRESS_GRACE, Service, Workspace
from skid.substitution import Substitution, apply_substitutions
from skid.tools import ROUTES

# Below the imports rather than above them, because skid imports kokoro lazily,
# so these resolve without it and the skip still fires at collection.
pytest.importorskip(
    "kokoro", reason="the service generates, and generation has no seam"
)


@pytest.fixture(scope="module", name="generator")
def generator_fixture() -> Generator:
    """One warm model for the whole module, as FR-5.1 intends."""
    return Generator()


def _player_that(behaviour: str, tmp_path: Path) -> str:
    """Write a player script with the given body and return its command line."""
    script = tmp_path / "player.sh"
    script.write_text(f"#!/bin/sh\n{behaviour}\n", encoding="utf-8")
    script.chmod(0o755)
    return f"{script} {{file}}"


def _holds_at(nth: int, tmp_path: Path) -> str:
    """A player body that blocks on its `nth` invocation until released.

    The counting is done in the player rather than in the test, which is what
    lets a clip other than the first be the one held. The greeting is always
    invocation one, so holding at two holds a real message, and FR-4.2 is worded
    about a message being spoken.

    A blocking player rather than a sleep in the test: FR-7.5 makes the player a
    command line on purpose, so the seam is already there. Timing a test against
    real generation would be flaky, where asserting which files exist while the
    speaker is held is not.
    """
    count = tmp_path / "played"
    holding = tmp_path / "holding"
    release = tmp_path / "release"
    return (
        f'n=$(cat "{count}" 2>/dev/null || echo 0)\n'
        f"n=$((n + 1))\n"
        f'printf %s "$n" > "{count}"\n'
        f'if [ "$n" -eq {nth} ]; then\n'
        f'  touch "{holding}"\n'
        f'  while [ ! -e "{release}" ]; do sleep 0.05; done\n'
        f"fi"
    )


def _wait_for(path: Path, timeout: float = 300.0) -> bool:
    """Block until `path` exists, reporting whether it turned up."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return True
        time.sleep(0.02)
    return False


def _clips_in(work: Path, wanted: int, timeout: float = 300.0) -> list[str]:
    """Block until `wanted` clips exist, returning whatever is there when it stops.

    It returns rather than asserts, so a bounded generator produces a short list
    the test can assert against instead of an error from a helper.
    """
    deadline = time.monotonic() + timeout
    names: list[str] = []
    while time.monotonic() < deadline:
        names = sorted(path.name for path in work.glob("*.wav"))
        if len(names) >= wanted:
            return names
        time.sleep(0.02)
    return names


def _clip_beyond(work: Path, already: set[str], timeout: float = 300.0) -> str | None:
    """Block until a clip appears that is not in `already`, and name it.

    The question this answers is when a clip was written rather than whether it
    exists, which is the only way to tell generation running alongside playback
    from generation that finished before playback started.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        new = sorted({path.name for path in work.glob("*.wav")} - already)
        if new:
            return new[0]
        time.sleep(0.02)
    return None


@pytest.fixture(name="restored_voice")
def restored_voice_fixture(generator: Generator) -> Iterator[None]:
    """Put the shared generator's voice back after a test that changes it.

    The generator is module-scoped so the model stays warm, which means a test
    that sets the voice sets it for everything after it. Both voices used here
    are `af_*`, so the pipeline is not dropped and the restore is cheap.
    """
    original = generator.voice
    yield
    generator.set_voice(original)


@pytest.fixture(name="service_for")
def service_for_fixture(
    tmp_path: Path, generator: Generator
) -> Iterator[Callable[..., Service]]:
    """Build a started service with a given player, and stop it afterwards."""
    built: list[Service] = []

    def make(
        behaviour: str = "true", substitutions: list[Substitution] | None = None
    ) -> Service:
        service = Service(
            config=Config(
                player=_player_that(behaviour, tmp_path),
                substitutions=list(substitutions or []),
            ),
            generator=generator,
            workspace=Workspace(work_dir=tmp_path / "work", log_path=tmp_path / "log"),
        )
        service.start()
        built.append(service)
        return service

    yield make
    for service in built:
        service.stop()


# COVERS: FR-4.8 | property
def test_a_submission_survives_the_service_going_away(
    tmp_path: Path, generator: Generator
) -> None:
    """The whole point of the spool, end to end through a real service.

    The first service is stopped without ever draining, standing for the process
    that goes away when an edit is deployed. The second is a different object
    over the same directories, standing for the one systemd starts next.

    Not a restart simulated with a flag: two Service instances, and the only
    thing passing between them is what is on disk.
    """
    made = Config(player=_player_that("true", tmp_path))
    first = Service(
        config=made,
        generator=generator,
        workspace=Workspace(work_dir=tmp_path / "work", log_path=tmp_path / "log"),
    )
    first.submit("silo", ["survives"])
    first.stop()

    second = Service(
        config=made,
        generator=generator,
        workspace=Workspace(work_dir=tmp_path / "work", log_path=tmp_path / "log"),
    )
    second.start()
    second.wait_idle(timeout=300)
    second.stop()

    assert [text for _, text in second.spoken] == ["survives"]


# COVERS: FR-4.8 | property
def test_an_accepted_submission_is_on_disk_before_submit_returns(
    tmp_path: Path, generator: Generator
) -> None:
    """FR-4.5 tells the caller yes, and FR-4.8 is what stands behind the yes.

    Asserted without starting the service at all, so nothing can have drained
    it: after `submit` returns and before anything runs, the work is durable.
    """
    service = Service(
        config=Config(player=_player_that("true", tmp_path)),
        generator=generator,
        workspace=Workspace(work_dir=tmp_path / "work", log_path=tmp_path / "log"),
    )

    service.submit("silo", ["written"])

    assert service.status()["pending"] == 1


# COVERS: FR-4.5 | positive
def test_submitting_returns_before_the_clip_is_heard(
    service_for: Callable[..., Service],
) -> None:
    """The agent carries on; it does not wait for its own speech."""
    service = service_for()

    started = time.monotonic()
    service.submit("silo", ["one"])

    assert time.monotonic() - started < 0.5


# COVERS: FR-4.3 | positive
def test_an_array_is_spoken_in_order(service_for: Callable[..., Service]) -> None:
    """Generation may finish out of order; playback may not."""
    service = service_for()

    service.submit("silo", ["one", "two", "three"])
    service.wait_idle(timeout=300)

    assert [text for _, text in service.spoken] == ["one", "two", "three"]


# COVERS: FR-3.5 | regression
def test_a_submission_queued_behind_another_is_not_greeted(
    service_for: Callable[..., Service],
) -> None:
    """The prefix is decided when the clip plays, not when it is queued.

    Both submissions are queued while `silo` is quiet. Deciding at queue time
    would greet both. Deciding at playback means the second finds that silo has
    just finished speaking, which is what a listener experienced.
    """
    service = service_for()

    service.submit("silo", ["one"])
    service.submit("silo", ["two"])
    service.wait_idle(timeout=300)

    assert service.greeted == ["silo"]


# COVERS: FR-3.2 | positive
def test_each_new_name_is_announced_in_its_own_right(
    service_for: Callable[..., Service],
) -> None:
    """A second name speaking is greeted, where the same name speaking again is not.

    `test_the_window_is_per_name` proves the decision function separates names,
    and `test_a_submission_queued_behind_another_is_not_greeted` proves the
    suppression path through the service. Neither proves the firing path: that a
    genuinely different name reaching a running service produces its own
    greeting clip.

    The gap was real, and measured rather than argued. `test_two_submissions_do_not_interleave`
    submits as two names and asserts only the order they are spoken in, so every
    service-level assertion about `greeted` was about a name being *suppressed*.
    Anding the decision with `not self.greeted`, which greets the first name the
    service ever sees and no other, passed all 78 tests with this one deselected
    and failed this one alone.

    The third submission is load-bearing: without it, a service that greets every
    submission regardless of the table also passes.
    """
    service = service_for()

    service.submit("silo", ["one"])
    service.submit("wrench", ["two"])
    service.submit("silo", ["three"])
    service.wait_idle(timeout=300)

    assert service.greeted == ["silo", "wrench"]


# COVERS: FR-4.4 | property
def test_two_submissions_do_not_interleave(service_for: Callable[..., Service]) -> None:
    """A submission is spoken to completion before the next one starts."""
    service = service_for()

    service.submit("silo", ["a", "b"])
    service.submit("wrench", ["c"])
    service.wait_idle(timeout=300)

    assert [name for name, _ in service.spoken] == ["silo", "silo", "wrench"]


# COVERS: FR-4.7 | positive
def test_a_failure_reaches_the_log_and_status(
    service_for: Callable[..., Service], tmp_path: Path
) -> None:
    """The caller is gone by now, so a failure has to be findable elsewhere."""
    service = service_for("exit 1")

    service.submit("silo", ["one"])
    service.wait_idle(timeout=300)

    assert service.status()["recent_failures"]
    assert "player exited 1" in (tmp_path / "log").read_text(encoding="utf-8")


# COVERS: FR-5.4 | property
def test_the_directories_it_creates_are_owner_only(
    tmp_path: Path, generator: Generator
) -> None:
    """The log directory has no 0700 parent to hide behind, and the log carries text.

    `_record_failure` writes the text a caller submitted into the log, so a
    world-readable log directory hands a caller's messages to any local user.
    Measured 2026-08-28 before this test: the live `~/.local/state/skid` was
    0775, and so was the clips directory inside the runtime dir, which FR-5.4
    survived only because systemd's own runtime directory above it is 0700.

    `mkdir(mode=...)` does nothing to a directory that already exists, which is
    why both are pre-created here: creating them fresh would pass either way.
    """
    work = tmp_path / "work"
    state = tmp_path / "state"
    work.mkdir(mode=0o777)
    state.mkdir(mode=0o777)

    service = Service(
        config=Config(player="true {file}"),
        generator=generator,
        workspace=Workspace(work_dir=work, log_path=state / "skid.log"),
    )
    service.start()
    service.stop()

    assert work.stat().st_mode & 0o777 == 0o700
    assert state.stat().st_mode & 0o777 == 0o700


# COVERS: FR-4.2 | property
def test_the_rest_are_prepared_while_one_is_being_spoken(
    service_for: Callable[..., Service], tmp_path: Path
) -> None:
    """Generation and playback overlap, asserted as clips arriving during playback.

    **Which clips exist while the speaker is held is not enough to show this**,
    and an earlier version of this test asserted exactly that and was wrong. A
    service that generated the whole array before playing a note of it satisfies
    that check completely, and it is the one design where the two never overlap.
    Measured: with generation made to take the playback lock, which the module
    docstring says would destroy this row, that version still passed.

    So what is asserted is arrival, not presence. The set of clips is snapshotted
    at the moment the player reports it is holding, and the test then waits for a
    clip that was not in it. A clip appearing after playback demonstrably began
    is overlap, and nothing else produces one.

    The player holds on the first clip so the snapshot is taken as early as
    possible, and the array is long enough that most of it is still unwritten at
    that point. FR-7.3 is the other half: this says they overlap, that one says
    how far ahead generation is allowed to get.
    """
    work = tmp_path / "work"
    service = service_for(_holds_at(1, tmp_path))

    service.submit("silo", ["one", "two", "three", "four", "five", "six"])
    assert _wait_for(tmp_path / "holding"), "the player never reached the first clip"
    already = {path.name for path in work.glob("*.wav")}
    arrived = _clip_beyond(work, already)
    spoken_while_held = list(service.spoken)

    (tmp_path / "release").touch()
    service.wait_idle(timeout=300)

    assert arrived, f"nothing was generated while a clip was playing; had {already}"
    assert not spoken_while_held


# COVERS: FR-7.3 | property
def test_generation_runs_ahead_of_the_speaker_without_a_bound(
    service_for: Callable[..., Service], tmp_path: Path
) -> None:
    """The lock covers playback alone, so generation runs to the end of the array.

    This is the half FR-4.2 does not settle. Holding the speaker on the very
    first clip, *every* remaining clip is on disk, which is what distinguishes
    the chosen design from a lookahead of one: a generator that took the
    playback lock, or fed a queue bounded at one, would sit at `0001.wav` until
    the player let go.

    Unbounded is the decided trade rather than an oversight, and the cost is
    stated in the row: a long array holds every clip it has produced before the
    second one is heard. Asserting the whole set is asserting that cost.
    """
    work = tmp_path / "work"
    service = service_for(_holds_at(1, tmp_path))

    service.submit("silo", ["one", "two", "three", "four"])
    assert _wait_for(tmp_path / "holding"), "the player never reached the greeting"
    generated = _clips_in(work, wanted=5)
    spoken_while_held = list(service.spoken)

    (tmp_path / "release").touch()
    service.wait_idle(timeout=300)

    assert generated == [f"000{index}.wav" for index in range(5)]
    assert not spoken_while_held


# COVERS: FR-6.3 | property
@pytest.mark.usefixtures("restored_voice")
def test_both_routes_reach_one_voice(tmp_path: Path, generator: Generator) -> None:
    """Setting the voice either way changes what the next clip is spoken in.

    The row rules out a third case that neither FR-6.1 nor FR-6.2 can see on its
    own: each route keeping its own copy, with neither of them wrong. Testing
    one route cannot find that, so both are exercised against one running
    service here, and each is asserted at the same observable.

    The tool half is the stronger of the two. `test_the_voice_is_set_through_the
    _tool` already proves the tool reaches the file; what this adds is that the
    file it reaches is the one the running service is generating from, with the
    test never touching the service to say so.

    The player is written into the config file deliberately. `_refresh_config`
    rebuilds the player from whatever it reloads, so a config carrying only a
    voice would hand playback back to the default `paplay` and make the machine
    speak during the suite.
    """
    player = _player_that("true", tmp_path)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(f'voice: af_heart\nplayer: "{player}"\n', encoding="utf-8")
    service = Service(
        config=load_config(config_path),
        generator=generator,
        workspace=Workspace(
            work_dir=tmp_path / "work",
            log_path=tmp_path / "log",
            config_path=config_path,
        ),
    )
    service.start()
    try:
        tools = build_app(service, config_path).test_client()
        tools.post(ROUTES["set_voice"][1], json={"voice": "af_bella"})
        service.submit("silo", ["through the tool"])
        service.wait_idle(timeout=300)
        after_tool = (service.status()["voice"], generator.voice)

        config_path.write_text(f'voice: af_sky\nplayer: "{player}"\n', encoding="utf-8")
        service.submit("silo", ["through the file"])
        service.wait_idle(timeout=300)
        after_file = (service.status()["voice"], generator.voice)
    finally:
        service.stop()

    assert after_tool == ("af_bella", "af_bella")
    assert after_file == ("af_sky", "af_sky")


# COVERS: FR-8.3 | property
def test_a_substitution_does_not_change_what_a_caller_is_told(
    service_for: Callable[..., Service],
) -> None:
    """The substituted form exists between skid and kokoro and nowhere else.

    The first assertion is what keeps this from being vacuous. A service with no
    substitutions at all, or one whose set never fired, would pass the second
    assertion trivially, so the set is checked to actually transform the text
    before anything is submitted.
    """
    entries = [
        Substitution(kind="literal", pattern="kokoro", replacement="coke oh roh")
    ]
    submitted = "kokoro is the engine"
    service = service_for(substitutions=entries)

    service.submit("silo", [submitted])
    service.wait_idle(timeout=300)

    assert apply_substitutions(entries, submitted) != submitted
    assert service.spoken == [("silo", submitted)]


# COVERS: FR-8.3 | property
def test_a_substitution_does_not_reach_the_log(
    tmp_path: Path, generator: Generator
) -> None:
    """A log records what was submitted, not the respelling kokoro was handed.

    `_generate_into` is the only place that both applies substitutions and
    writes a log line carrying text, and it logs `raw` rather than what it
    generated. Reaching that branch needs a generation failure, and there are no
    mocks here, so the failure is arranged in the filesystem instead: the clips
    directory is replaced by a file once the service is running, and generation
    fails on the `mkdir` that precedes writing a clip.

    A file rather than a directory with the write bit taken off, which also
    fails but fails later, inside `wave.open`. That leaves a half-built
    `Wave_write` whose `__del__` raises, and pytest reports the unraisable
    exception as a warning on a test that has otherwise passed. Failing at the
    `mkdir` reaches the same branch and leaves nothing behind.

    A replacement sharing no substring with the pattern, so that finding the
    submitted spelling in the log cannot also be finding the substituted one.
    """
    entries = [
        Substitution(kind="literal", pattern="kokoro", replacement="coke oh roh")
    ]
    submitted = "kokoro is the engine"
    work = tmp_path / "work"
    service = Service(
        config=Config(player=_player_that("true", tmp_path), substitutions=entries),
        generator=generator,
        workspace=Workspace(work_dir=work, log_path=tmp_path / "log"),
    )
    service.start()
    work.rmdir()
    work.write_text("not a directory", encoding="utf-8")
    try:
        service.submit("silo", [submitted])
        service.wait_idle(timeout=300)
    finally:
        service.stop()

    log = (tmp_path / "log").read_text(encoding="utf-8")

    assert apply_substitutions(entries, submitted) != submitted
    assert submitted in log
    assert "coke oh roh" not in log


# COVERS: FR-5.3 | property
def test_an_idle_service_is_progressing(service_for: Callable[..., Service]) -> None:
    """Parked on an empty queue is health, and it is the state skid is usually in.

    A watchdog that treated idle as a stall would restart a working service
    every two minutes all day.
    """
    service = service_for()
    service.wait_idle(timeout=300)

    assert service.is_progressing(time.monotonic())


# COVERS: FR-5.3 | property
def test_a_long_clip_on_the_speaker_is_progressing_not_stuck(
    service_for: Callable[..., Service], tmp_path: Path
) -> None:
    """Playback is health however long it lasts, so the grace does not bound it.

    Measured 2026-08-28: 1196 characters is 76.9 seconds of audio, and nothing
    caps a message's length. A watchdog tuned to clip length would either fire
    mid-sentence or be set so high it never fires. Asserted with the player held
    and the grace set to zero, which is the strongest form: no elapsed time
    whatsoever can make a playing service look stuck.
    """
    service = service_for(_holds_at(1, tmp_path))

    service.submit("silo", ["one"])
    assert _wait_for(tmp_path / "holding"), "the player never started"
    while_playing = service.is_progressing(time.monotonic(), grace=0.0)

    (tmp_path / "release").touch()
    service.wait_idle(timeout=300)

    assert while_playing


# COVERS: FR-5.3 | negative
def test_a_stalled_loop_stops_looking_like_progress(
    tmp_path: Path, generator: Generator
) -> None:
    """Withholding the ping is the mechanism, so this is the case that matters.

    The shape of a wedged service: work accepted, nothing on the speaker, and no
    step taken since. Arranged by submitting to a service that was never
    started, so the serve loop genuinely never runs and nothing has to be broken
    to hold it still.

    Asked about a moment past the grace rather than waiting one out, so the test
    costs nothing and `PROGRESS_GRACE` can change without it becoming slow.
    """
    service = Service(
        config=Config(player=_player_that("true", tmp_path)),
        generator=generator,
        workspace=Workspace(work_dir=tmp_path / "work", log_path=tmp_path / "log"),
    )

    service.submit("silo", ["never spoken"])

    assert not service.is_progressing(time.monotonic() + PROGRESS_GRACE + 1)
