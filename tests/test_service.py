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

pytest.importorskip(
    "kokoro", reason="the service generates, and generation has no seam"
)

from skid.config import Config
from skid.generation import Generator
from skid.service import Service


@pytest.fixture(scope="module")
def generator() -> Generator:
    """One warm model for the whole module, as FR-5.1 intends."""
    return Generator()


def _player_that(behaviour: str, tmp_path: Path) -> str:
    """Write a player script with the given body and return its command line."""
    script = tmp_path / "player.sh"
    script.write_text(f"#!/bin/sh\n{behaviour}\n", encoding="utf-8")
    script.chmod(0o755)
    return f"{script} {{file}}"


@pytest.fixture
def service_for(
    tmp_path: Path, generator: Generator
) -> Iterator[Callable[..., Service]]:
    """Build a started service with a given player, and stop it afterwards."""
    built: list[Service] = []

    def make(behaviour: str = "true") -> Service:
        service = Service(
            config=Config(player=_player_that(behaviour, tmp_path)),
            work_dir=tmp_path / "work",
            log_path=tmp_path / "log",
            generator=generator,
        )
        service.start()
        built.append(service)
        return service

    yield make
    for service in built:
        service.stop()


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
