"""The installer: the plan it would run, and the units it copies.

Nothing here installs anything. Every destination in `Paths` is a parameter, so
the plan is built against `tmp_path` and asserted as data, and the only commands
these tests actually run are `systemd-analyze verify`, which parses a file and
changes nothing.

That is the whole testing strategy for an installer, and it is deliberate: the
alternative is a test that writes into the real `~/.config/systemd/user`, and a
test suite that can break the machine it runs on is worse than one that checks
less.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from skid.install import (
    ALREADY_EXISTS,
    UNITS,
    Paths,
    Step,
    install_plan,
    missing_tools,
    uninstall_plan,
    verify_plan,
)

CHECKOUT = Path(__file__).resolve().parent.parent
"""The real checkout, read from but never written to."""


def _paths(tmp_path: Path) -> Paths:
    """A Paths pointing everything writable at a temporary directory."""
    return Paths(
        checkout=CHECKOUT,
        units=tmp_path / "systemd" / "user",
        bin_dir=tmp_path / "bin",
        tool_dir=tmp_path / "tools" / "skid",
    )


def _argvs(steps: list[Step]) -> list[tuple[str, ...]]:
    """Just the commands, for asserting a plan without its prose."""
    return [step.argv for step in steps]


# COVERS: FR-5.4 | property
@pytest.mark.parametrize("unit", UNITS)
def test_the_units_in_the_checkout_parse(unit: str) -> None:
    """systemd accepts both units as written, so an install cannot ship a typo.

    A unit file is data, and a typo in one is not found until the day it is
    loaded. This is the cheapest check that says the file is a unit.
    """
    if shutil.which("systemd-analyze") is None:
        pytest.skip("systemd-analyze is not on PATH")

    finished = subprocess.run(
        [
            "systemd-analyze",
            "--user",
            "verify",
            str(CHECKOUT / "share" / "systemd" / "user" / unit),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert finished.returncode == 0, finished.stderr


# COVERS: FR-5.4 | property
def test_the_socket_is_owner_only() -> None:
    """The socket unit declares 0600, which is the whole of skid's access control.

    Reaching skid's tools means making the machine speak and rewriting its
    config. Nothing in the code enforces that; this line in this file does, so
    it is asserted here rather than trusted to survive an edit.
    """
    socket = (CHECKOUT / "share" / "systemd" / "user" / "skid.socket").read_text(
        encoding="utf-8"
    )

    assert "SocketMode=0600" in socket


# COVERS: FR-5.3 | property
def test_the_service_is_notify_so_active_means_answerable() -> None:
    """systemd is told the model is warm, not merely that the process started.

    A cold start loads kokoro for tens of seconds. Under `Type=simple` systemd
    would call that started, and the first caller would wait on a service it had
    been told was ready. FR-5.3 names this as what makes a wedged backend less
    likely, so the unit is where that half of the requirement lives.
    """
    service = (CHECKOUT / "share" / "systemd" / "user" / "skid.service").read_text(
        encoding="utf-8"
    )

    assert "Type=notify" in service


def test_the_install_plan_is_the_five_commands_it_owes(tmp_path: Path) -> None:
    """The documented sequence, in order, with the units copied between.

    This is the list `docs/PROJECT.md` promised an installer would run. Asserting
    it as data is what stops the two documents drifting apart silently.
    """
    paths = _paths(tmp_path)

    verbs = [argv[:3] for argv in _argvs(install_plan(paths))]

    assert verbs == [
        ("uv", "tool", "install"),
        ("install", "-D", "-m"),
        ("install", "-D", "-m"),
        ("systemctl", "--user", "daemon-reload"),
        ("systemctl", "--user", "enable"),
        ("claude", "mcp", "add"),
    ]


def test_the_plan_copies_both_units_into_the_given_directory(tmp_path: Path) -> None:
    """Both unit files are copied, and to where Paths says rather than to home."""
    paths = _paths(tmp_path)

    destinations = [
        argv[-1] for argv in _argvs(install_plan(paths)) if argv[0] == "install"
    ]

    assert destinations == [str(paths.units / unit) for unit in UNITS]


def test_the_plan_starts_the_socket_and_not_the_service(tmp_path: Path) -> None:
    """Socket activation means the first connection starts the service.

    Starting it here would load a model to prove that copying two files worked.
    """
    plan = _argvs(install_plan(_paths(tmp_path)))

    assert [argv for argv in plan if "--now" in argv] == [
        ("systemctl", "--user", "enable", "--now", "skid.socket")
    ]
    assert not any("skid.service" in argv for argv in plan)


def test_registering_tolerates_a_name_that_is_already_taken(tmp_path: Path) -> None:
    """`claude mcp add` exits 1 on an existing name, so a re-run must read the message.

    Measured 2026-08-28 against an isolated HOME: the first add exits 0, and a
    second exits 1 saying the server already exists. Without the tolerated
    message, running the installer twice would report a failure.
    """
    add = [
        step
        for step in install_plan(_paths(tmp_path))
        if step.argv[:3] == ("claude", "mcp", "add")
    ]

    assert len(add) == 1
    assert add[0].tolerate == ALREADY_EXISTS


def test_verification_never_connects() -> None:
    """Checking the install must not be what starts the service.

    `is-enabled` and `is-active` ask systemd. Anything that opened the socket
    would answer the same question by loading a model.
    """
    assert _argvs(verify_plan()) == [
        ("systemctl", "--user", "is-enabled", "skid.socket"),
        ("systemctl", "--user", "is-active", "skid.socket"),
    ]


def test_uninstalling_disables_before_it_removes_the_files(tmp_path: Path) -> None:
    """systemd cannot disable a unit whose file has gone, and leaves the symlink.

    The order is the whole content of this step, so it is asserted as order.
    """
    verbs = _argvs(uninstall_plan(_paths(tmp_path)))
    disable = next(
        i
        for i, argv in enumerate(verbs)
        if argv[:3] == ("systemctl", "--user", "disable")
    )
    remove = next(i for i, argv in enumerate(verbs) if argv[0] == "rm")

    assert disable < remove


def test_uninstalling_reverses_everything_the_install_created(tmp_path: Path) -> None:
    """Each thing the install adds has something in the uninstall that removes it."""
    paths = _paths(tmp_path)
    undone = " ".join(" ".join(argv) for argv in _argvs(uninstall_plan(paths)))

    assert "uv tool uninstall skid" in undone
    assert "claude mcp remove skid" in undone
    for unit in UNITS:
        assert str(paths.units / unit) in undone


def test_a_machine_without_the_tools_is_told_before_anything_is_written() -> None:
    """A missing `uv` is found first, not halfway through with units copied."""
    assert missing_tools(("definitely-not-a-command",)) == ["definitely-not-a-command"]
    assert missing_tools(("sh",)) == []
