"""Take a checkout to a working service, and say what it changed.

skid worked on one machine and was reproducible on none, because every step was
run by hand. This is those steps as data: a plan of commands that can be printed
before it is run and asserted against in a test without touching the machine.

**It runs before skid is installed, so it imports nothing but the standard
library and nothing from its own package.** The first step is what puts `skid`
on PATH, so an installer that needed skid installed could not perform it:

    python3 packages/skid/src/skid/install.py    from a fresh checkout
    skid-install                                 afterwards, by name

Both reach this file. The first is the one that works on a machine that has
never seen skid.

**What it writes, all of it inside the user's own home:**

    ~/.local/share/uv/tools/skid/         the service's environment, uv's to manage
    ~/.local/share/uv/tools/skid-mcp/     the MCP shim's environment, likewise
    ~/.local/bin/skid, skid-install,      the four executables
                skid-mcp, skid-say
    ~/.config/systemd/user/               skid.socket and skid.service
    ~/.claude.json                        the MCP registration, via `claude mcp`

**Two tool environments, because skid is two installables.** The service carries
kokoro and torch and the shim carries httpx and mcp, so replacing one does not
rebuild the other and a service restart no longer disturbs the MCP side.
`docs/DECISIONS/the-socket-is-the-package-boundary.md`.

Nothing needs root and nothing is written outside `$HOME`, which is the property
that makes an installer for this service an ordinary thing to run rather than
something to read carefully first. Read it carefully anyway.

**Run against a machine that already has skid, it says so and asks.** Answering
yes reinstalls, which means the registration is removed and added rather than
left alone: `claude mcp add` refuses a name that is taken and does not update
it, so an entry pointing at some other checkout survives every re-run that only
adds. `--yes` answers for a script, `--dry-run` asks nothing and changes nothing,
and no terminal to ask on is taken as no.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess  # nosec B404 - docs/SUPPRESSIONS.md S-1
import sys
from dataclasses import dataclass
from pathlib import Path

UNITS = ("skid.socket", "skid.service")
"""The two unit files, copied verbatim from the checkout."""

SERVER_NAME = "skid"
"""The name skid is registered under with the MCP client."""

ALREADY_EXISTS = "already exists"
"""What `claude mcp add` says when the name is taken.

It exits 1 in that case, measured 2026-08-28, so the exit status alone cannot
tell an installer re-run from a real failure and the message has to be read.
"""

NO_SUCH_SERVER = "No MCP server"
"""What `claude mcp remove` says when there is nothing registered to remove.

A first install and a reinstall run the same removal, and on a machine that has
never seen skid there is nothing there. That is the wanted state, not a failure.
"""


@dataclass(frozen=True)
class Step:
    """One command, with the sentence a person should read while it runs.

    `tolerate` is the substring in the command's own output that means the step
    found the world already in the state it wanted. A step carrying one is
    idempotent by inspection rather than by hope.
    """

    says: str
    argv: tuple[str, ...]
    tolerate: str = ""


@dataclass(frozen=True)
class Paths:
    """Where an install reads from and writes to.

    Every destination is a parameter so a test can point the whole plan at a
    temporary directory. Nothing here defaults to the real home at the point of
    use; `from_environment` is the only place that decides.
    """

    checkout: Path
    units: Path
    bin_dir: Path
    service_tool_dir: Path
    mcp_tool_dir: Path
    """The two tool environments, which are separate on purpose.

    skid is three distributions and two of them install as tools, so that
    replacing the service does not rebuild the MCP shim. Measured 2026-09-07:
    the service's environment is 1.3 GB and the shim's is 33 MB, and reinstalling
    the service leaves the shim's environment byte-for-byte identical.

    Two fields rather than one directory holding both, because uv owns the layout
    under `~/.local/share/uv/tools` and names each environment for its
    distribution. `docs/DECISIONS/the-socket-is-the-package-boundary.md`.
    """

    client_config: Path = Path.home() / ".claude.json"
    """Where the MCP client keeps its registrations, read to decide whether to
    re-register. Defaulted so existing callers are unaffected, and a parameter
    so a test can point it at a temporary file like everything else here."""

    @classmethod
    def from_environment(cls, checkout: Path) -> Paths:
        """The real locations, taken from XDG variables where they are set."""
        config = os.environ.get("XDG_CONFIG_HOME")
        data = os.environ.get("XDG_DATA_HOME")
        config_home = Path(config) if config else Path.home() / ".config"
        data_home = Path(data) if data else Path.home() / ".local" / "share"
        return cls(
            checkout=checkout,
            units=config_home / "systemd" / "user",
            bin_dir=Path.home() / ".local" / "bin",
            service_tool_dir=data_home / "uv" / "tools" / "skid",
            mcp_tool_dir=data_home / "uv" / "tools" / "skid-mcp",
            client_config=Path.home() / ".claude.json",
        )


def _unit_checks(source: Path) -> list[Step]:
    """Ask systemd to accept each unit, before either is copied (FR-9.6).

    **These run after the tool is installed and before the units are written.**
    `skid.service` names `~/.local/bin/skid` in `ExecStart`, and
    `systemd-analyze verify` fails on a command that is not there, so a check
    placed before the tool install cannot pass on a machine that has never had
    skid. It only ever passed because a previous install had left the binary
    behind, and it verified that stale binary rather than the one being
    installed.

    Ordering it after the install makes the `ExecStart` check mean something:
    it verifies the executable this run just produced. FR-9.6 is unchanged,
    because what it protects is a unit reaching `~/.config/systemd/user` before
    systemd has accepted it, and no unit is copied until these pass.
    """
    return [
        Step(
            says=f"check systemd accepts {unit} before installing it",
            argv=("systemd-analyze", "--user", "verify", str(source / unit)),
        )
        for unit in UNITS
    ]


def _unit_copies(source: Path, destination: Path) -> list[Step]:
    """Copy each unit to where `Paths` says, never to a location of its own."""
    return [
        Step(
            says=f"install {unit} into {destination}",
            argv=(
                "install",
                "-D",
                "-m",
                "0644",
                str(source / unit),
                str(destination / unit),
            ),
        )
        for unit in UNITS
    ]


def registration_is_current(config: Path) -> bool:
    """Whether the MCP client already launches skid the way this install wants.

    **The registration names a command on PATH, not a checkout.** It is
    `{"type": "stdio", "command": "skid-mcp"}`, and `~/.local/bin/skid-mcp` is a
    symlink into the tool environment that `uv tool install` re-points. So an
    entry in this shape is already correct for whichever checkout was just
    installed, and removing and re-adding it changes nothing on disk.

    It is not free, though. Re-registering drops every running session's `speak`
    until that session restarts, because a session acquires an MCP server when
    it starts. That is the whole cost of a reinstall for anyone using skid at
    the time, and it buys nothing when the entry is already right.

    Read from the file rather than from `claude mcp get`, for the reason
    `already_installed` gives: the CLI health-checks a server it is asked
    about, a health check opens the socket, and opening the socket starts the
    service. Deciding whether to re-register must not load a model.
    """
    try:
        parsed = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    entry = parsed.get("mcpServers", {}).get(SERVER_NAME)
    if not isinstance(entry, dict):
        return False
    return entry.get("command") == "skid-mcp" and not entry.get("args")


def _unregister() -> Step:
    """Remove the registration, tolerating there being none (FR-9.10)."""
    return Step(
        says=f"unregister {SERVER_NAME} first, because add will not replace it",
        argv=("claude", "mcp", "remove", SERVER_NAME, "--scope", "user"),
        tolerate=NO_SUCH_SERVER,
    )


def _register() -> Step:
    """Register at user scope, tolerating the name already being taken."""
    return Step(
        says=f"register {SERVER_NAME} with the MCP client, at user scope",
        argv=("claude", "mcp", "add", "--scope", "user", SERVER_NAME, "--", "skid-mcp"),
        tolerate=ALREADY_EXISTS,
    )


def install_plan(paths: Paths, *, reinstall: bool = False) -> list[Step]:
    """The commands that take a checkout to a running socket, in order.

    **Two tool installs and not one.** skid is three distributions split by which
    side of the socket a module sits on, and the two that carry console scripts
    install separately so that replacing the service does not rebuild the MCP
    shim. The service goes first because `skid.service` names `~/.local/bin/skid`
    in `ExecStart` and the unit checks below verify it.

    The contract is not installed here and is not missing. It carries no console
    script, so it is a dependency of each of the other two and arrives with them.

    The socket is enabled and started and the service is not. Socket activation
    means the first connection starts it, and starting it here would load the
    model to prove an install worked, which is a minute of nothing for no
    reason. `verify_plan` checks the socket instead, which is the property.

    A reinstall unregisters before it registers, because `claude mcp add`
    refuses a name that is taken and does not update it, so an entry pointing at
    the wrong command survives every re-run that only adds (FR-9.11).

    **Both steps are skipped when the entry is already the one this install
    would write.** FR-9.11 asks that the registration name the checkout being
    installed, and an entry reading `command: skid-mcp` does that for every
    checkout, because the name resolves through a symlink the tool install
    re-points. Re-registering it would change no bytes and would cost every
    running session its `speak`. `registration_is_current` is the test.
    """
    source = paths.checkout / "share" / "systemd" / "user"
    packages = paths.checkout / "packages"
    return [
        Step(
            says=f"install the skid service as a uv tool from {packages / 'skid'}",
            argv=("uv", "tool", "install", "--editable", str(packages / "skid")),
        ),
        Step(
            says=f"install the skid MCP shim as a uv tool from {packages / 'skid-mcp'}",
            argv=("uv", "tool", "install", "--editable", str(packages / "skid-mcp")),
        ),
        *_unit_checks(source),
        *_unit_copies(source, paths.units),
        Step(
            says="reload the user unit files",
            argv=("systemctl", "--user", "daemon-reload"),
        ),
        Step(
            says="enable and start the socket, which does not start the service",
            argv=("systemctl", "--user", "enable", "--now", "skid.socket"),
        ),
        *_registration_steps(paths, reinstall=reinstall),
    ]


def _registration_steps(paths: Paths, *, reinstall: bool) -> list[Step]:
    """The registration steps this run actually owes, which may be none.

    A first install registers. A reinstall whose entry is already correct does
    nothing, so the sessions using skid keep working across it. A reinstall
    whose entry is missing or differently shaped removes and adds.
    """
    if registration_is_current(paths.client_config):
        return []
    return [*([_unregister()] if reinstall else []), _register()]


def uninstall_plan(paths: Paths) -> list[Step]:
    """The commands that take the machine back, in the reverse order.

    The socket is disabled before the units are removed, because systemd cannot
    disable a unit whose file has gone and would leave the symlink behind.
    """
    removals = [str(paths.units / unit) for unit in UNITS]
    return [
        Step(
            says="stop and disable the socket",
            argv=("systemctl", "--user", "disable", "--now", "skid.socket"),
        ),
        Step(
            says="stop the service if it is running",
            argv=("systemctl", "--user", "stop", "skid.service"),
        ),
        Step(says=f"remove the units from {paths.units}", argv=("rm", "-f", *removals)),
        Step(
            says="reload the user unit files",
            argv=("systemctl", "--user", "daemon-reload"),
        ),
        Step(
            says=f"unregister {SERVER_NAME} from the MCP client",
            argv=("claude", "mcp", "remove", SERVER_NAME, "--scope", "user"),
            tolerate="No MCP server",
        ),
        Step(
            says="uninstall the MCP shim",
            argv=("uv", "tool", "uninstall", "skid-mcp"),
        ),
        Step(
            says="uninstall the service",
            argv=("uv", "tool", "uninstall", "skid"),
        ),
    ]


def verify_plan() -> list[Step]:
    """Read-only checks that the install took, none of which connect.

    Connecting is what starts the service, so an installer that proved itself by
    calling `speak` would load a model to answer a question about a socket.
    `is-enabled` and `is-active` answer it without a connection.
    """
    return [
        Step(
            says="the socket is enabled, so it comes back after a reboot",
            argv=("systemctl", "--user", "is-enabled", "skid.socket"),
        ),
        Step(
            says="the socket is listening, so a session can reach skid",
            argv=("systemctl", "--user", "is-active", "skid.socket"),
        ),
    ]


def already_installed(paths: Paths) -> list[str]:
    """What of skid is already on this machine, as the paths that hold it.

    Asked of the filesystem alone. The MCP registration is not checked, because
    `claude mcp get` and `claude mcp list` both health-check the server, and a
    health check on skid opens the socket, and opening the socket is what starts
    the service. An installer must not load a model to find out whether it has
    run before.

    Both tool environments are asked about separately, so a machine holding one
    half is told which half. A run that installed the service and failed before
    the shim leaves exactly that state, and reporting it as "skid is installed"
    would describe a machine that cannot speak.
    """
    found = [str(paths.units / unit) for unit in UNITS if (paths.units / unit).exists()]
    if paths.service_tool_dir.exists():
        found.append(str(paths.service_tool_dir))
    if paths.mcp_tool_dir.exists():
        found.append(str(paths.mcp_tool_dir))
    return found


def confirmed(question: str, *, assume_yes: bool = False) -> bool:
    """Ask, and take silence for no.

    A reinstall replaces files the user owns and re-points their MCP
    registration, so it is asked for rather than assumed. With no terminal to
    ask on there is no answer to read, and guessing yes on behalf of a script is
    how an installer surprises somebody: `--yes` is how a script says yes.
    """
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        print("not a terminal, so nothing was changed. Pass --yes to reinstall.")
        return False
    return input(f"{question} [y/N] ").strip().lower() in {"y", "yes"}


def missing_tools(
    required: tuple[str, ...] = (
        "uv",
        "systemctl",
        "systemd-analyze",
        "install",
        "claude",
    ),
) -> list[str]:
    """Which of the commands the plan runs are not on PATH.

    Checked before anything is written, so a machine without `uv` is told so
    rather than finding out halfway through with the units already copied.
    """
    return [name for name in required if shutil.which(name) is None]


def spacy_model_present(paths: Paths) -> bool:
    """Whether the tool environment can import the spaCy model kokoro needs.

    kokoro downloads `en_core_web_sm` at start-up when it is absent, using pip
    or uv, and under systemd neither is on PATH. That failure cost 76 restarts
    before the model was declared as a dependency. Checking it here is what
    stops the next one, and it is a question about the installed environment
    rather than about the checkout, so the tool's own interpreter answers it.

    **The service's environment and not the shim's.** kokoro is the service's
    dependency alone, so the shim has no spaCy model and is not supposed to.
    Asking the wrong interpreter would report a broken install on every machine.
    """
    python = paths.service_tool_dir / "bin" / "python"
    if not python.exists():
        return False
    finished = subprocess.run(  # nosec B603 - docs/SUPPRESSIONS.md S-1
        [str(python), "-c", "import en_core_web_sm"],
        capture_output=True,
        check=False,
    )
    return finished.returncode == 0


def run(step: Step) -> bool:
    """Run one step, and say whether the world is now as the step wanted.

    A tolerated message is success, and both tolerated messages are about
    something already being in the state the step wanted. `claude mcp add` exits
    1 on a name that is already registered and `claude mcp remove` exits
    non-zero on a name that is not, so reading the status alone would call a
    first install and a reinstall failures in turn.
    """
    finished = subprocess.run(  # nosec B603 - docs/SUPPRESSIONS.md S-1
        step.argv, capture_output=True, text=True, check=False
    )
    output = finished.stdout + finished.stderr
    if finished.returncode == 0:
        return True
    if step.tolerate and step.tolerate in output:
        print(f"    already so: {output.strip().splitlines()[0]}")
        return True
    print(f"    FAILED ({finished.returncode}): {output.strip()}", file=sys.stderr)
    return False


def perform(steps: list[Step], *, dry_run: bool) -> bool:
    """Run every step in order, stopping at the first that fails."""
    for step in steps:
        print(f"  {step.says}")
        print(f"    {' '.join(step.argv)}")
        if dry_run:
            continue
        if not run(step):
            return False
    return True


def report_what_changed(paths: Paths) -> None:
    """Name every file the install touched, because they are the user's."""
    changed = [
        (f"{paths.units}/", "skid.socket and skid.service"),
        (f"{paths.bin_dir}/", "skid, skid-install, skid-mcp and skid-say"),
        (f"{paths.service_tool_dir}/", "the service's environment"),
        (f"{paths.mcp_tool_dir}/", "the MCP shim's environment"),
        (str(paths.client_config), "the MCP registration"),
    ]
    width = max(len(where) for where, _ in changed)
    print("\nWhat this changed, all of it inside your home:")
    for where, what in changed:
        print(f"  {where:<{width}}  {what}")


def ask_about_reinstalling(present: list[str], *, assume_yes: bool) -> bool:
    """Show what is already here and ask whether to replace it."""
    print("skid is already installed. These are here now:\n")
    for path in present:
        print(f"  {path}")
    print(
        "\nReinstalling replaces the units, rebuilds the tool environment, and"
        "\nre-points the MCP registration at this checkout. `claude mcp add` will"
        "\nnot update an entry that exists, so the registration is removed and"
        "\nadded rather than left as it is.\n"
    )
    return confirmed("Reinstall?", assume_yes=assume_yes)


def verify_installed(paths: Paths) -> bool:
    """Check the install took, without connecting to it.

    Two questions, and the second is the one a passing socket does not answer:
    kokoro downloads `en_core_web_sm` at start-up when it is absent, using pip
    or uv, and under systemd neither is on PATH. That cost 76 failed starts
    before the model was declared as a dependency. An install that leaves it
    missing has produced a service that cannot start, and says so here rather
    than at the first `speak`.
    """
    print("\nChecking, without connecting, because connecting starts the service:")
    if not perform(verify_plan(), dry_run=False):
        return False

    if not spacy_model_present(paths):
        print(
            "\nen_core_web_sm is not importable in the tool environment. kokoro will"
            "\ntry to download it at start-up using pip or uv, and neither is on PATH"
            "\nunder systemd, so the service will fail to start. Reinstall the tool.",
            file=sys.stderr,
        )
        return False
    return True


def install(paths: Paths, *, dry_run: bool, assume_yes: bool = False) -> int:
    """Install, verify, and say what a session has to do to see it."""
    absent = missing_tools()
    if absent:
        print(f"not on PATH: {', '.join(absent)}", file=sys.stderr)
        return 1

    present = already_installed(paths)
    if (
        present
        and not dry_run
        and not ask_about_reinstalling(present, assume_yes=assume_yes)
    ):
        print("Left alone. Nothing was changed.")
        return 0

    verb = "Reinstalling" if present else "Installing"
    print(f"\n{verb} skid from {paths.checkout}\n")
    if not perform(install_plan(paths, reinstall=bool(present)), dry_run=dry_run):
        return 1

    if dry_run:
        print("\nDry run: nothing was changed.")
        return 0

    if not verify_installed(paths):
        return 1

    report_what_changed(paths)
    print(
        "\nskid is installed. A Claude Code session picks an MCP server up when it"
        "\nstarts, so sessions already running cannot call `speak` until they are"
        "\nrestarted. That is the session's age, not the service."
    )
    return 0


def uninstall(paths: Paths, *, dry_run: bool) -> int:
    """Take the machine back to not having skid."""
    print("Removing skid\n")
    if not perform(uninstall_plan(paths), dry_run=dry_run):
        return 1
    if dry_run:
        print("\nDry run: nothing was changed.")
        return 0
    print(f"\nRemoved. The config at {Path.home() / '.config' / 'skid'} is left alone.")
    return 0


def parse(argv: list[str] | None = None) -> argparse.Namespace:
    """Read the two options this has."""
    parser = argparse.ArgumentParser(
        prog="skid-install",
        description="Install skid as a socket-activated user service.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the commands without running any of them",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="remove the units, the registration and the tool",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="answer the reinstall question yes, for a script with no terminal",
    )
    return parser.parse_args(argv)


def checkout_root() -> Path:
    """The checkout this file was run from, whichever way it was reached.

    `src/skid/install.py` run directly and `skid-install` run from an editable
    install are the same file on disk, so walking up from it finds the checkout
    in both cases. An editable install is what the service runs, so there is
    always a checkout to find.
    """
    return Path(__file__).resolve().parent.parent.parent


def main(argv: list[str] | None = None) -> int:
    """Install or uninstall, and return what the shell should see."""
    options = parse(argv)
    paths = Paths.from_environment(checkout_root())
    if options.uninstall:
        return uninstall(paths, dry_run=options.dry_run)
    return install(paths, dry_run=options.dry_run, assume_yes=options.yes)


if __name__ == "__main__":
    raise SystemExit(main())
