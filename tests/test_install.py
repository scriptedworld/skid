"""The installer: the plan it would run, and the units it copies.

Nothing here runs anything. Every destination in `Paths` is a parameter, so the
plan is built against `tmp_path` and asserted as data, and no test in this file
imports `subprocess` or executes a command.

That is the whole testing strategy for an installer, and it is deliberate: the
alternative is a test that writes into the real `~/.config/systemd/user`, and a
test suite that can break the machine it runs on is worse than one that checks
less.

**It got stricter on 2026-08-28.** One test did run `systemd-analyze verify` on
the unit files. That check was right and it was in the wrong place: it only ever
ran on the machine the suite ran on, and it made this file the only test module
shelling out. It is a step in the install plan now, so it runs on whichever
machine is being installed to, and this file asserts the command instead.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from skid.install import (
    ALREADY_EXISTS,
    NO_SUCH_SERVER,
    UNITS,
    Paths,
    Step,
    already_installed,
    confirmed,
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
def test_the_installer_checks_each_unit_before_writing_it(
    unit: str, tmp_path: Path
) -> None:
    """systemd is asked to accept a unit before anything is copied.

    A unit file is data, and a typo in one is not found until the day it is
    loaded. This test used to run `systemd-analyze` itself, which put the check
    in the wrong place twice over: it only ever ran on the machine the suite ran
    on, and it made the test the only thing shelling out.

    Moving it into the plan checks the units on whichever machine is being
    installed to, and lets this assert the command rather than run it.
    """
    plan = _argvs(install_plan(_paths(tmp_path)))
    source = str(CHECKOUT / "share" / "systemd" / "user" / unit)

    assert ("systemd-analyze", "--user", "verify", source) in plan


def test_the_units_are_checked_before_the_first_thing_is_written(
    tmp_path: Path,
) -> None:
    """A unit systemd will reject must be found before the machine is touched.

    Installing one leaves a machine that looks installed and cannot start, and
    the order is the whole content of the guard, so it is asserted as order.
    """
    plan = _argvs(install_plan(_paths(tmp_path)))
    last_check = max(i for i, argv in enumerate(plan) if argv[0] == "systemd-analyze")
    first_write = min(i for i, argv in enumerate(plan) if argv[0] != "systemd-analyze")

    assert last_check < first_write


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


def test_the_install_plan_is_the_sequence_it_owes(tmp_path: Path) -> None:
    """The documented sequence, in order, with the units checked then copied.

    This is the list `docs/PROJECT.md` promised an installer would run. Asserting
    it as data is what stops the two documents drifting apart silently.
    """
    paths = _paths(tmp_path)

    verbs = [argv[:3] for argv in _argvs(install_plan(paths))]

    assert verbs == [
        ("systemd-analyze", "--user", "verify"),
        ("systemd-analyze", "--user", "verify"),
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


def test_a_reinstall_unregisters_before_it_registers(tmp_path: Path) -> None:
    """`claude mcp add` will not replace an entry, so a reinstall removes first.

    Measured 2026-08-28 in an isolated HOME: add against a taken name exits 1
    and leaves the existing entry untouched, whatever command it points at. So
    an installer that only ever adds cannot re-point a registration, and every
    re-run against a moved checkout would leave the old one in place.
    """
    steps = install_plan(_paths(tmp_path), reinstall=True)
    verbs = [step.argv[:3] for step in steps]

    assert verbs.index(("claude", "mcp", "remove")) < verbs.index(
        ("claude", "mcp", "add")
    )


def test_a_first_install_does_not_remove_a_registration_it_never_made(
    tmp_path: Path,
) -> None:
    """Nothing is unregistered on a machine that has never had skid."""
    verbs = [argv[:3] for argv in _argvs(install_plan(_paths(tmp_path)))]

    assert ("claude", "mcp", "remove") not in verbs


def test_both_registration_steps_tolerate_the_state_they_wanted(tmp_path: Path) -> None:
    """Removing what is absent and adding what is present are both exit 1.

    Each is the ordinary outcome of one of the two paths, so each carries the
    message that means the world is already as the step wanted.
    """
    by_verb = {
        step.argv[:3]: step for step in install_plan(_paths(tmp_path), reinstall=True)
    }

    assert by_verb[("claude", "mcp", "remove")].tolerate == NO_SUCH_SERVER
    assert by_verb[("claude", "mcp", "add")].tolerate == ALREADY_EXISTS


def test_an_existing_install_is_found_from_the_filesystem_alone(tmp_path: Path) -> None:
    """What is already here is read off disk, never by asking the MCP client.

    `claude mcp get` and `claude mcp list` health-check the server, which opens
    the socket, which starts the service. An installer must not load a model to
    find out whether it has run before.
    """
    paths = _paths(tmp_path)
    assert already_installed(paths) == []

    paths.units.mkdir(parents=True)
    (paths.units / "skid.socket").write_text("[Socket]\n", encoding="utf-8")
    paths.tool_dir.mkdir(parents=True)

    assert already_installed(paths) == [
        str(paths.units / "skid.socket"),
        str(paths.tool_dir),
    ]


def test_no_terminal_to_ask_on_is_taken_as_no(monkeypatch: pytest.MonkeyPatch) -> None:
    """A script that did not say yes has not said yes.

    Reinstalling replaces files the user owns and re-points their registration.
    Guessing yes because there was nobody to ask is how that surprises somebody.
    """
    monkeypatch.setattr("sys.stdin", io.StringIO("y\n"))

    assert confirmed("Reinstall?") is False
    assert confirmed("Reinstall?", assume_yes=True) is True
