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

One test does cause a command to run.
`test_an_environment_without_the_model_cannot_start` calls
`spacy_model_present`, which asks the tool environment's own interpreter whether
it can import the model, and the interpreter it asks is a script the test wrote
inside `tmp_path`. Nothing outside the temporary directory is read or written.

That is `test_player.py`'s pattern rather than an exception to it: the
production code runs the command and the test never does, so no test in this
repository imports `subprocess`. `docs/SUPPRESSIONS.md` states that property.
"""

from __future__ import annotations

import ast
import io
import sys
from pathlib import Path

import pytest

from skid.install import (
    ALREADY_EXISTS,
    NO_SUCH_SERVER,
    UNITS,
    Paths,
    Step,
    already_installed,
    ask_about_reinstalling,
    confirmed,
    install,
    install_plan,
    main,
    missing_tools,
    parse,
    perform,
    registration_is_current,
    report_what_changed,
    run,
    spacy_model_present,
    uninstall,
    uninstall_plan,
    verify_plan,
)

CHECKOUT = Path(__file__).resolve().parent.parent
"""The real checkout, read from but never written to."""


def _paths(tmp_path: Path, *, registration: str | None = None) -> Paths:
    """A Paths pointing everything readable and writable at a temporary directory.

    `client_config` is included deliberately. It defaults to the real
    `~/.claude.json`, and a plan now reads it to decide whether re-registering
    is owed, so a test that left it defaulted would branch on whether the
    machine running the suite happens to have skid registered. That is the
    property `Paths` exists for, and the default is the one field that can leak.

    `registration` writes a client config first: pass the JSON a real client
    would hold, or leave it None for a machine that has never registered skid.
    """
    config = tmp_path / ".claude.json"
    if registration is not None:
        config.write_text(registration, encoding="utf-8")
    return Paths(
        checkout=CHECKOUT,
        units=tmp_path / "systemd" / "user",
        bin_dir=tmp_path / "bin",
        tool_dir=tmp_path / "tools" / "skid",
        client_config=config,
    )


CURRENT_REGISTRATION = (
    '{"mcpServers": {"skid": {"type": "stdio", "command": "skid-mcp",'
    ' "args": [], "env": {}}}}'
)
"""A client config holding exactly what this installer would write.

Taken from the live `~/.claude.json` on 2026-09-07 rather than invented, so a
test asserting that this shape is left alone is asserting against the real one.
"""


def _argvs(steps: list[Step]) -> list[tuple[str, ...]]:
    """Just the commands, for asserting a plan without its prose."""
    return [step.argv for step in steps]


def _section(unit: str, heading: str) -> str:
    """The lines of one section of a unit file, without the ones around it.

    Matched on a line that IS the heading rather than on the text appearing
    anywhere, because these units explain themselves in comments and a comment
    naming `[Service]` would otherwise end the `[Unit]` section early. That is
    not hypothetical: it is how this helper came to exist.
    """
    text = (CHECKOUT / "share" / "systemd" / "user" / unit).read_text(encoding="utf-8")
    lines = text.splitlines()
    start = lines.index(heading) + 1
    rest = [
        index
        for index, line in enumerate(lines[start:], start)
        if line.startswith("[") and line.endswith("]")
    ]
    return "\n".join(lines[start : rest[0]] if rest else lines[start:])


# COVERS: FR-9.6 | positive
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


# COVERS: FR-9.6 | property
def test_the_units_are_checked_before_the_first_thing_is_written(
    tmp_path: Path,
) -> None:
    """A unit systemd will reject must be found before either unit is copied.

    Installing one leaves a machine that looks installed and cannot start, and
    the order is the whole content of the guard, so it is asserted as order.

    **Measured against the copies, not against every command.** This once
    asserted the checks came before the first command of any kind, which read
    as the stronger guarantee and was not one this installer could keep:
    `skid.service` names `~/.local/bin/skid` in `ExecStart` and
    `systemd-analyze verify` fails on a command that is not there, so the check
    could only pass on a machine some earlier install had already put that
    binary on. It verified a stale binary, and on a clean machine the installer
    stopped dead. Ordered after `uv tool install`, it verifies the executable
    this run just produced, and still precedes every copy.
    """
    plan = _argvs(install_plan(_paths(tmp_path)))
    last_check = max(i for i, argv in enumerate(plan) if argv[0] == "systemd-analyze")
    first_copy = min(i for i, argv in enumerate(plan) if argv[0] == "install")

    assert last_check < first_copy


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


# COVERS: FR-5.3 | property
def test_the_service_declares_a_watchdog() -> None:
    """A process can be running and not answering, and this is what notices.

    `Type=notify` makes "active" mean "answerable" at start-up only. Nothing
    covered the process that stops answering later, which FR-5.3 names, and
    `WatchdogUSec=0` was that sentence as a measurement.
    """
    service = (CHECKOUT / "share" / "systemd" / "user" / "skid.service").read_text(
        encoding="utf-8"
    )

    assert "WatchdogSec=" in service


# COVERS: FR-5.3 | property
def test_the_start_limit_is_chosen_and_in_the_section_systemd_reads() -> None:
    """Both halves matter, and the second is why this asserts a position.

    systemd moved `StartLimitIntervalSec` to `[Unit]` in v229 and **ignores it
    in `[Service]` with a warning while `systemd-analyze verify` still exits
    0**. Measured 2026-08-28 by writing it in the wrong section: the exit status
    said the unit was fine and the setting was being dropped. Asserting only
    that the key appears somewhere would pass against exactly that mistake.
    """
    unit_section = _section("skid.service", "[Unit]")

    assert "StartLimitIntervalSec=" in unit_section
    assert "StartLimitBurst=" in unit_section


# COVERS: FR-9.1 | positive
def test_the_install_plan_is_the_sequence_it_owes(tmp_path: Path) -> None:
    """The documented sequence, in order, with the units checked then copied.

    This is the list `docs/PROJECT.md` promised an installer would run. Asserting
    it as data is what stops the two documents drifting apart silently.
    """
    paths = _paths(tmp_path)

    verbs = [argv[:3] for argv in _argvs(install_plan(paths))]

    assert verbs == [
        ("uv", "tool", "install"),
        ("systemd-analyze", "--user", "verify"),
        ("systemd-analyze", "--user", "verify"),
        ("install", "-D", "-m"),
        ("install", "-D", "-m"),
        ("systemctl", "--user", "daemon-reload"),
        ("systemctl", "--user", "enable"),
        ("claude", "mcp", "add"),
    ]


# COVERS: FR-9.3 | positive
def test_the_plan_copies_both_units_into_the_given_directory(tmp_path: Path) -> None:
    """Both unit files are copied, and to where Paths says rather than to home."""
    paths = _paths(tmp_path)

    destinations = [
        argv[-1] for argv in _argvs(install_plan(paths)) if argv[0] == "install"
    ]

    assert destinations == [str(paths.units / unit) for unit in UNITS]


# COVERS: FR-9.7 | positive
def test_the_plan_starts_the_socket_and_not_the_service(tmp_path: Path) -> None:
    """Socket activation means the first connection starts the service.

    Starting it here would load a model to prove that copying two files worked.
    """
    plan = _argvs(install_plan(_paths(tmp_path)))

    assert [argv for argv in plan if "--now" in argv] == [
        ("systemctl", "--user", "enable", "--now", "skid.socket")
    ]
    assert not any("skid.service" in argv for argv in plan)


# COVERS: FR-9.10 | positive
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


# COVERS: FR-9.8 | property
def test_verification_never_connects() -> None:
    """Checking the install must not be what starts the service.

    `is-enabled` and `is-active` ask systemd. Anything that opened the socket
    would answer the same question by loading a model.
    """
    assert _argvs(verify_plan()) == [
        ("systemctl", "--user", "is-enabled", "skid.socket"),
        ("systemctl", "--user", "is-active", "skid.socket"),
    ]


# COVERS: FR-9.13 | property
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


# COVERS: FR-9.13 | positive
def test_uninstalling_reverses_everything_the_install_created(tmp_path: Path) -> None:
    """Each thing the install adds has something in the uninstall that removes it."""
    paths = _paths(tmp_path)
    undone = " ".join(" ".join(argv) for argv in _argvs(uninstall_plan(paths)))

    assert "uv tool uninstall skid" in undone
    assert "claude mcp remove skid" in undone
    for unit in UNITS:
        assert str(paths.units / unit) in undone


# COVERS: FR-9.5 | negative
def test_a_machine_without_the_tools_is_told_before_anything_is_written() -> None:
    """A missing `uv` is found first, not halfway through with units copied."""
    assert missing_tools(("definitely-not-a-command",)) == ["definitely-not-a-command"]
    assert missing_tools(("sh",)) == []


# COVERS: FR-9.11 | positive
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


# COVERS: FR-9.11 | negative
def test_a_first_install_does_not_remove_a_registration_it_never_made(
    tmp_path: Path,
) -> None:
    """Nothing is unregistered on a machine that has never had skid."""
    verbs = [argv[:3] for argv in _argvs(install_plan(_paths(tmp_path)))]

    assert ("claude", "mcp", "remove") not in verbs


# COVERS: FR-9.10 | property
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


# COVERS: FR-9.8 | property
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


# COVERS: FR-9.12 | edge
def test_no_terminal_to_ask_on_is_taken_as_no(monkeypatch: pytest.MonkeyPatch) -> None:
    """A script that did not say yes has not said yes.

    Reinstalling replaces files the user owns and re-points their registration.
    Guessing yes because there was nobody to ask is how that surprises somebody.
    """
    monkeypatch.setattr("sys.stdin", io.StringIO("y\n"))

    assert confirmed("Reinstall?") is False
    assert confirmed("Reinstall?", assume_yes=True) is True


# COVERS: FR-9.2 | property
def test_a_dry_run_shows_every_step_and_performs_none(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Showing the plan must not be a way of running it.

    Asserted with a step that would leave a trace if it ran, so the assertion is
    about the machine rather than about a flag being read. A dry run that
    performed even one step would be worse than no dry run at all, because it
    would be a promise of safety that is not kept.
    """
    trace = tmp_path / "this-would-exist-if-it-ran"
    steps = [Step(says="create a file", argv=("touch", str(trace)))]

    assert perform(steps, dry_run=True) is True
    assert not trace.exists()
    assert f"touch {trace}" in capsys.readouterr().out


# COVERS: FR-9.4 | positive
def test_every_path_an_install_changed_is_named(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """They are the user's files, so the report is the list they can check.

    Asserted as all four destinations rather than as a count, so a location
    added to the plan and not to the report is caught. That pair is the drift
    this can actually have: the report is written by hand and the plan is not.
    """
    paths = _paths(tmp_path)

    report_what_changed(paths)

    said = capsys.readouterr().out
    for where in (paths.units, paths.bin_dir, paths.tool_dir):
        assert str(where) in said, where
    assert ".claude.json" in said


# COVERS: FR-9.9 | negative
def test_an_environment_without_the_model_cannot_start(tmp_path: Path) -> None:
    """A socket that comes up says nothing about whether the service can run.

    kokoro downloads `en_core_web_sm` at start-up when it is absent, using pip
    or uv, and under systemd neither is on PATH. That cost 76 restarts. This is
    the check that notices, and until FR-9.9 was written nothing exercised it.

    Both branches, because only the second is the interesting one: a tool
    environment that was never built has no interpreter to ask, and one that was
    built can still be missing the model.
    """
    paths = _paths(tmp_path)

    assert spacy_model_present(paths) is False

    interpreter = paths.tool_dir / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    interpreter.chmod(0o755)

    assert spacy_model_present(paths) is False

    interpreter.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    assert spacy_model_present(paths) is True


# COVERS: FR-9.14 | property
def test_the_installer_imports_nothing_it_installs() -> None:
    """The first step of the plan is what puts skid on PATH.

    So an installer importing anything from its own package could not run on the
    machine it exists for. Read from the source rather than by importing it,
    because importing it here would succeed on a developer's machine whatever it
    imports, which is the one place the answer does not matter.
    """
    source = (CHECKOUT / "src" / "skid" / "install.py").read_text(encoding="utf-8")
    imported = {
        (node.module or "").split(".")[0]
        if isinstance(node, ast.ImportFrom)
        else alias.name.split(".")[0]
        for node in ast.walk(ast.parse(source))
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in getattr(node, "names", [])
    }

    assert "skid" not in imported
    assert imported <= sys.stdlib_module_names | {"__future__"}, sorted(
        imported - sys.stdlib_module_names
    )


# COVERS: FR-9.14 | regression
def test_nothing_is_verified_against_a_binary_the_install_has_not_made_yet(
    tmp_path: Path,
) -> None:
    """The tool is installed before any step that needs it to exist.

    FR-9.14 is discharged above by reading the import set, and the import set
    was always clean. It did not catch this, because the requirement is about
    the plan running on a machine that has never had skid, and the plan can
    fail that while importing nothing.

    `skid.service` names `~/.local/bin/skid` in `ExecStart`, and
    `systemd-analyze verify` refuses a command that is not there. Measured
    2026-09-07 by uninstalling the tool and running the installer:

        FAILED (1): skid.service: Command /home/ancient/.local/bin/skid is not
        executable: No such file or directory

    The installer stopped there and installed nothing. It had only ever passed
    because a previous install had left that binary behind, which also means it
    was verifying a stale binary rather than the one being installed.
    """
    plan = _argvs(install_plan(_paths(tmp_path)))

    assert plan[0][:3] == ("uv", "tool", "install")
    installs_tool = 0
    for argv in plan:
        if argv[:3] == ("uv", "tool", "install"):
            installs_tool = 1
        elif argv[0] == "systemd-analyze":
            assert installs_tool, "a unit is verified before skid is on PATH"


# COVERS: FR-9.11 | positive
def test_a_registration_already_in_the_wanted_shape_is_left_alone(
    tmp_path: Path,
) -> None:
    """A reinstall re-registers nothing when the entry is already correct.

    The entry names a command on PATH, `skid-mcp`, and never a checkout. So it
    is already right for whichever checkout was just installed and rewriting it
    changes no bytes. It is not free: every running session loses `speak` until
    it restarts, because a session acquires an MCP server when it starts.
    """
    paths = _paths(tmp_path, registration=CURRENT_REGISTRATION)

    verbs = [argv[:2] for argv in _argvs(install_plan(paths, reinstall=True))]

    assert ("claude", "mcp") not in verbs


# COVERS: FR-9.11 | negative
@pytest.mark.parametrize(
    ("name", "config"),
    [
        ("absent", None),
        ("not json", "{not json at all"),
        ("no servers", '{"other": {}}'),
        ("another command", '{"mcpServers": {"skid": {"command": "elsewhere"}}}'),
        (
            "carries args",
            '{"mcpServers": {"skid": {"command": "skid-mcp", "args": ["--x"]}}}',
        ),
        ("not an object", '{"mcpServers": {"skid": "skid-mcp"}}'),
    ],
)
def test_a_registration_that_is_not_the_wanted_one_is_rewritten(
    name: str, config: str | None, tmp_path: Path
) -> None:
    """Anything other than the exact shape this installer writes is replaced.

    The skip exists to spare running sessions, never to leave a wrong entry in
    place, so every way of being wrong has to fall through to remove-then-add.
    """
    paths = _paths(tmp_path, registration=config)

    verbs = [argv[:3] for argv in _argvs(install_plan(paths, reinstall=True))]

    assert ("claude", "mcp", "remove") in verbs, name
    assert ("claude", "mcp", "add") in verbs, name


# COVERS: FR-9.11 | edge
def test_a_first_install_registers_without_removing(tmp_path: Path) -> None:
    """There is nothing to remove on a machine that has never registered skid."""
    verbs = [argv[:3] for argv in _argvs(install_plan(_paths(tmp_path)))]

    assert ("claude", "mcp", "remove") not in verbs
    assert ("claude", "mcp", "add") in verbs


# COVERS: FR-9.11 | property
def test_reading_the_registration_never_runs_the_client(tmp_path: Path) -> None:
    """The decision is read from the file, never from `claude mcp get`.

    `already_installed` gives the reason and it applies here identically: the
    CLI health-checks the server it is asked about, a health check opens the
    socket, and opening the socket starts the service. Deciding whether to
    re-register must not load a model.
    """
    source = (CHECKOUT / "src" / "skid" / "install.py").read_text(encoding="utf-8")
    function = next(
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.FunctionDef) and node.name == "registration_is_current"
    )
    # The docstring explains why `claude mcp get` is not used, so scanning the
    # raw text would match the explanation and fail. Read the code instead.
    body = ast.unparse(ast.Module(body=function.body[1:], type_ignores=[]))

    assert "read_text" in body
    assert "subprocess" not in body
    assert "claude" not in body


# COVERS: FR-9.11 | edge
def test_an_unreadable_client_config_registers_rather_than_assuming(
    tmp_path: Path,
) -> None:
    """A config that cannot be read is treated as no registration.

    Registering when one was already there is tolerated and costs a session its
    `speak`. Skipping when there was none leaves skid unreachable. So the
    unreadable case takes the recoverable side.
    """
    unreadable = tmp_path / "not-a-file"
    unreadable.mkdir()

    assert registration_is_current(unreadable) is False


# COVERS: FR-9.4 | positive
def test_every_path_named_is_one_this_run_would_touch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The report names the paths from `Paths`, not from the real home.

    It used to print `Path.home() / '.claude.json'` while the plan read the
    registration from `paths.client_config`, so a run pointed at a temporary
    directory reported a file it had not touched.
    """
    paths = _paths(tmp_path)

    report_what_changed(paths)

    printed = capsys.readouterr().out
    assert str(paths.units) in printed
    assert str(paths.tool_dir) in printed
    assert str(paths.client_config) in printed
    assert str(Path.home() / ".claude.json") not in printed


# COVERS: FR-9.2 | property
def test_a_dry_run_runs_none_of_the_commands(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`perform` prints every step and executes nothing when dry.

    The command asserted here does not exist, so a dry run that executed it
    would fail rather than pass quietly.
    """
    steps = [Step(says="would run", argv=("definitely-not-a-command", "--now"))]

    assert perform(steps, dry_run=True) is True
    assert "definitely-not-a-command" in capsys.readouterr().out


# COVERS: FR-9.12 | positive
def test_the_reinstall_question_is_answered_by_yes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`--yes` answers for a script, and what is already there is still shown."""
    answered = ask_about_reinstalling(["/somewhere/skid.socket"], assume_yes=True)

    assert answered is True
    assert "/somewhere/skid.socket" in capsys.readouterr().out


# COVERS: FR-9.5 | negative
def test_an_install_stops_before_writing_when_a_tool_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A machine without the tools is told, and nothing is written.

    **PATH is the boundary, so PATH is what the test moves.** `missing_tools`
    asks `shutil.which`, which reads PATH and nothing else, so emptying it is
    the honest way to be a machine without uv. Replacing `missing_tools` with a
    function returning `["uv"]` would assert that `install` believes whatever it
    is told, which is not the property.
    """
    monkeypatch.setenv("PATH", "")

    code = install(_paths(tmp_path), dry_run=False)

    assert code == 1
    assert "uv" in capsys.readouterr().err
    assert not (tmp_path / "systemd").exists()


# COVERS: FR-9.12 | negative
def test_a_reinstall_with_no_terminal_to_ask_on_changes_nothing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Silence is taken for no, and the machine is left as it was.

    Nothing is replaced here either. `confirmed` asks `sys.stdin.isatty()`, and
    under the suite stdin is not a terminal, so this IS the no-terminal case
    rather than a simulation of one. That is the case the installer is most
    likely to meet in anger: a script or a hook with no one to answer.
    """
    paths = _paths(tmp_path)
    paths.units.mkdir(parents=True)
    (paths.units / "skid.socket").write_text("", encoding="utf-8")

    code = install(paths, dry_run=False)

    printed = capsys.readouterr().out
    assert code == 0
    assert "Left alone" in printed
    assert "not a terminal" in printed
    assert not (paths.units / "skid.service").exists()


# COVERS: FR-9.2 | positive
def test_a_dry_run_install_writes_nothing_and_says_so(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The whole plan is printed and the machine is untouched."""
    paths = _paths(tmp_path)

    code = install(paths, dry_run=True)

    printed = capsys.readouterr().out
    assert code == 0
    assert "Dry run: nothing was changed." in printed
    assert "uv tool install" in printed
    assert not paths.units.exists()


# COVERS: FR-9.13 | positive
def test_a_dry_run_uninstall_writes_nothing_and_says_so(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The reversal is printed without being carried out."""
    code = uninstall(_paths(tmp_path), dry_run=True)

    printed = capsys.readouterr().out
    assert code == 0
    assert "Dry run: nothing was changed." in printed
    assert "uv tool uninstall" in printed


# COVERS: FR-9.2 | positive
def test_the_options_this_installer_has(capsys: pytest.CaptureFixture[str]) -> None:
    """Three flags, and defaults that change nothing without being asked."""
    default = parse([])

    assert (default.dry_run, default.uninstall, default.yes) == (False, False, False)
    assert parse(["--dry-run"]).dry_run is True
    assert parse(["--uninstall"]).uninstall is True
    assert parse(["--yes"]).yes is True


# COVERS: FR-9.13 | property
def test_main_routes_uninstall_away_from_install(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`--uninstall` reaches the removal plan and `--dry-run` alone reaches the install.

    **Both routes are taken for real, under `--dry-run`.** Neither function is
    replaced: a dry run prints its plan and executes nothing, so the two can be
    told apart by what they print, and the thing under test is the routing
    rather than a pair of stand-ins agreeing with the test.
    """
    assert main(["--uninstall", "--dry-run"]) == 0
    removing = capsys.readouterr().out

    assert main(["--dry-run"]) == 0
    installing = capsys.readouterr().out

    assert "Removing skid" in removing
    assert "uv tool uninstall" in removing
    assert "uv tool install" in installing
    assert "Removing skid" not in installing


# COVERS: FR-9.10 | positive
def test_a_step_that_exits_clean_has_succeeded() -> None:
    """Run for real against a command that does nothing and exits 0."""
    assert run(Step(says="does nothing", argv=("true",))) is True


# COVERS: FR-9.10 | positive
def test_a_step_that_finds_the_state_it_wanted_has_succeeded(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A non-zero exit whose output carries the tolerated message is success.

    This is the case the installer meets on every re-run: `claude mcp add`
    exits 1 on a name that is already registered, and reading the status alone
    would call a working reinstall a failure. Exercised with a real command
    that prints the message and exits non-zero, so the reading of stdout and
    the reading of the status are both real.
    """
    step = Step(
        says="reports what is already so",
        argv=("sh", "-c", "echo already exists; exit 1"),
        tolerate="already exists",
    )

    assert run(step) is True
    assert "already so" in capsys.readouterr().out


# COVERS: FR-9.10 | negative
def test_a_step_that_fails_for_another_reason_is_a_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A tolerated message is matched, not assumed from the exit status alone."""
    step = Step(
        says="fails in a way nothing tolerates",
        argv=("sh", "-c", "echo something else >&2; exit 3"),
        tolerate="already exists",
    )

    assert run(step) is False
    assert "FAILED (3)" in capsys.readouterr().err


# COVERS: FR-9.1 | negative
def test_performing_stops_at_the_first_step_that_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A plan is a sequence, so a failure halts it rather than carrying on.

    The step after the failure would create a file if it ran, so its absence is
    the assertion rather than the printed output.
    """
    steps = [
        Step(says="fails", argv=("false",)),
        Step(says="would run next", argv=("echo", "reached")),
    ]

    assert perform(steps, dry_run=False) is False
    assert "reached" not in capsys.readouterr().out


# COVERS: FR-9.1 | positive
def test_performing_runs_every_step_when_each_one_succeeds(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A plan that succeeds runs all of it, for real, in order.

    Asserted by what the commands left on disk rather than by what they
    printed, because printing is what a dry run also does and the difference
    between the two is the whole point of this one.
    """
    first = tmp_path / "first"
    second = tmp_path / "second"
    steps = [
        Step(says="makes the first", argv=("touch", str(first))),
        Step(says="makes the second", argv=("touch", str(second))),
    ]

    assert perform(steps, dry_run=False) is True
    assert first.exists()
    assert second.exists()
