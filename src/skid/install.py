"""Take a checkout to a working service, and say what it changed.

skid worked on one machine and was reproducible on none, because every step was
run by hand. This is those steps as data: a plan of commands that can be printed
before it is run and asserted against in a test without touching the machine.

**It runs before skid is installed, so it imports nothing but the standard
library and nothing from its own package.** The first step is what puts `skid`
on PATH, so an installer that needed skid installed could not perform it:

    python3 src/skid/install.py              from a fresh checkout
    skid-install                             afterwards, by name

Both reach this file. The first is the one that works on a machine that has
never seen skid.

**What it writes, all of it inside the user's own home:**

    ~/.local/share/uv/tools/skid/     the tool environment, uv's to manage
    ~/.local/bin/skid, skid-mcp       the two executables
    ~/.config/systemd/user/           skid.socket and skid.service
    ~/.claude.json                    the MCP registration, via `claude mcp`

Nothing needs root and nothing is written outside `$HOME`, which is the property
that makes an installer for this service an ordinary thing to run rather than
something to read carefully first. Read it carefully anyway.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
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
    tool_dir: Path

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
            tool_dir=data_home / "uv" / "tools" / "skid",
        )


def install_plan(paths: Paths) -> list[Step]:
    """The commands that take a checkout to a running socket, in order.

    The socket is enabled and started; the service is not. Socket activation
    means the first connection starts it, and starting it here would load the
    model to prove an install worked, which is a minute of nothing for no
    reason. `verify_plan` checks the socket instead, which is the property.
    """
    units = paths.checkout / "share" / "systemd" / "user"
    copies = [
        Step(
            says=f"install {unit} into {paths.units}",
            argv=(
                "install",
                "-D",
                "-m",
                "0644",
                str(units / unit),
                str(paths.units / unit),
            ),
        )
        for unit in UNITS
    ]
    return [
        Step(
            says=f"install skid as a uv tool from {paths.checkout}",
            argv=("uv", "tool", "install", "--editable", str(paths.checkout)),
        ),
        *copies,
        Step(
            says="reload the user unit files",
            argv=("systemctl", "--user", "daemon-reload"),
        ),
        Step(
            says="enable and start the socket, which does not start the service",
            argv=("systemctl", "--user", "enable", "--now", "skid.socket"),
        ),
        Step(
            says=f"register {SERVER_NAME} with the MCP client, at user scope",
            argv=(
                "claude",
                "mcp",
                "add",
                "--scope",
                "user",
                SERVER_NAME,
                "--",
                "skid-mcp",
            ),
            tolerate=ALREADY_EXISTS,
        ),
    ]


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
        Step(says="uninstall the uv tool", argv=("uv", "tool", "uninstall", "skid")),
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


def missing_tools(
    required: tuple[str, ...] = ("uv", "systemctl", "install", "claude"),
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
    """
    python = paths.tool_dir / "bin" / "python"
    if not python.exists():
        return False
    finished = subprocess.run(
        [str(python), "-c", "import en_core_web_sm"],
        capture_output=True,
        check=False,
    )
    return finished.returncode == 0


def run(step: Step) -> bool:
    """Run one step, and say whether the world is now as the step wanted.

    A tolerated message is success. `claude mcp add` exits 1 on a name that is
    already registered, which is the ordinary outcome of running the installer
    twice, so reading the status alone would report a re-run as a failure.

    It does not update an entry that is already there, so a registration
    pointing at the wrong command stays wrong and is reported rather than
    silently replaced. Removing an entry from a file a person owns is their
    call, and the message names the command that does it.
    """
    finished = subprocess.run(step.argv, capture_output=True, text=True, check=False)
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
        (f"{paths.bin_dir}/", "skid and skid-mcp"),
        (f"{paths.tool_dir}/", "the tool environment"),
        (str(Path.home() / ".claude.json"), "the MCP registration"),
    ]
    width = max(len(where) for where, _ in changed)
    print("\nWhat this changed, all of it inside your home:")
    for where, what in changed:
        print(f"  {where:<{width}}  {what}")


def install(paths: Paths, *, dry_run: bool) -> int:
    """Install, verify, and say what a session has to do to see it."""
    absent = missing_tools()
    if absent:
        print(f"not on PATH: {', '.join(absent)}", file=sys.stderr)
        return 1

    print(f"Installing skid from {paths.checkout}\n")
    if not perform(install_plan(paths), dry_run=dry_run):
        return 1

    if dry_run:
        print("\nDry run: nothing was changed.")
        return 0

    print("\nChecking, without connecting, because connecting starts the service:")
    if not perform(verify_plan(), dry_run=False):
        return 1

    if not spacy_model_present(paths):
        print(
            "\nen_core_web_sm is not importable in the tool environment. kokoro will"
            "\ntry to download it at start-up using pip or uv, and neither is on PATH"
            "\nunder systemd, so the service will fail to start. Reinstall the tool.",
            file=sys.stderr,
        )
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
    return install(paths, dry_run=options.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
