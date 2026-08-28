"""The entry point: warm the model, then serve MCP over the socket systemd gave.

skid does not create or bind the socket. systemd creates it, starts skid on the
first connection, and restarts it if it dies, so there is no start protocol
here: no lock file, no stale-path handling, no readiness race between clients.

Run without systemd it binds a socket itself, which is for trying it by hand
rather than the way it is meant to run. **It refuses if something is already
listening there**, because the by-hand path used to unlink whatever it found and
bind over it, which silently takes the socket away from systemd and leaves two
resident models with only one of them reachable.

**Both paths now say 0600 on the socket itself.** Under systemd the unit sets
`SocketMode=0600`. Run by hand, skid binds the socket and chmods it, which it
can do because it owns the bind: waitress is handed an already-listening socket
rather than a path. The previous arrangement let uvicorn create the socket and
chmod it to 0666, so owner-only access rested entirely on the 0700 directory
above it (FR-5.4).

**What crosses this socket is plain HTTP, not MCP.** The protocol lives in
`skid-mcp`, so nothing here holds a session and a restart invalidates nothing.
Two SDK imports left with it, one of them present only because the MCP SDK
answers 421 to an unknown Host header over a socket no browser can reach.
"""

from __future__ import annotations

import os
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

import waitress
from flask import Flask

from skid.config import default_config_path, load_config
from skid.generation import Generator
from skid.routes import build_app
from skid.service import Service

LISTEN_FD = 3
"""The first file descriptor systemd passes, by its own convention."""


def runtime_dir() -> Path:
    """Where the socket and the working clips live."""
    base = os.environ.get("XDG_RUNTIME_DIR")
    root = Path(base) if base else Path(tempfile.gettempdir()) / f"skid-{os.getuid()}"
    return root / "skid"


def ensure_runtime_dir() -> Path:
    """Create the runtime directory owner-only, and make sure it stays that way.

    `mkdir(mode=...)` does nothing to a directory that already exists, and the
    service creates its clips directory inside this one, so whichever ran first
    would decide the mode. Measured 2026-08-28 before this existed: the
    directory came out 0775 and the socket 0666, and only systemd's own 0700
    runtime directory above it kept FR-5.4 true.
    """
    path = runtime_dir()
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(0o700)
    return path


def state_dir() -> Path:
    """Where the log lives, which is what a person reads when it goes quiet."""
    base = os.environ.get("XDG_STATE_HOME")
    root = Path(base) if base else Path.home() / ".local" / "state"
    return root / "skid"


def watchdog_interval() -> float | None:
    """How often to ping, from `WATCHDOG_USEC`, or None if systemd wants none.

    Half of what the unit asked for, which is what systemd's own documentation
    recommends, so the value lives in `skid.service` and is not restated here.
    A unit with no `WatchdogSec` sets nothing and gets no pinging thread.

    `WATCHDOG_PID` is checked because systemd sets these for the main process
    and they are inherited by children; ignoring it would have a forked process
    keeping the service alive on its parent's behalf.
    """
    raw = os.environ.get("WATCHDOG_USEC")
    owner = os.environ.get("WATCHDOG_PID")
    if not raw or (owner and int(owner) != os.getpid()):
        return None
    return int(raw) / 2_000_000


def notify(message: bytes) -> None:
    """Send one datagram to systemd, and say nothing when there is nobody there.

    Written by hand rather than taken as a dependency: it is one datagram, and
    skid is silent about it when there is no NOTIFY_SOCKET, which is the case
    when it is run by hand.
    """
    address = os.environ.get("NOTIFY_SOCKET")
    if not address:
        return
    if address.startswith("@"):
        address = "\0" + address[1:]
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
        sock.connect(address)
        sock.sendall(message)


def keep_pinging(service: Service, interval: float) -> None:
    """Ping while the service is getting somewhere, and stop when it is not.

    **Not a timer.** Withholding the ping is the whole mechanism: a thread that
    pings unconditionally proves only that the thread runs, which is the failure
    this is supposed to detect. `Service.is_progressing` is what decides, and it
    counts idle and playback as health.
    """
    while True:
        time.sleep(interval)
        if service.is_progressing(time.monotonic()):
            notify(b"WATCHDOG=1")


def notify_ready() -> None:
    """Tell systemd the model is loaded, so active and answerable are one thing."""
    notify(b"READY=1")


def someone_is_listening(path: Path) -> bool:
    """Whether a live server already holds this socket, as opposed to a stale file.

    Run by hand, skid used to unlink whatever was at the path and bind its own.
    Under socket activation that **takes the path away from systemd**, which goes
    on believing it owns a socket nobody can reach, and the by-hand process
    becomes the service without anything saying so.

    Measured 2026-08-28: a by-hand instance started at 00:54 was still resident
    at 03:18, holding 1.73 GB and listening on an inode the path no longer
    resolved to. Nothing could reach it and nothing reported it.

    Connecting is the only honest test. A socket file that refuses a connection
    is stale and safe to replace; one that accepts is somebody's.
    """
    if not path.exists():
        return False
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
        probe.settimeout(1.0)
        try:
            probe.connect(str(path))
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            return False
    return True


def build() -> tuple[Service, Flask]:
    """Build the service and the HTTP app, with the model already warm."""
    ensure_runtime_dir()
    config_path = default_config_path()
    config = load_config(config_path)

    generator = Generator(config.voice)
    generator.warm()

    service = Service(
        config=config,
        work_dir=runtime_dir() / "clips",
        log_path=state_dir() / "skid.log",
        generator=generator,
        config_path=config_path,
    )
    service.start()
    return service, build_app(service, config_path)


def inherited_socket() -> socket.socket:
    """The listening socket systemd created and passed as fd 3.

    Taken as an object rather than a number because waitress serves sockets that
    are already bound and listening, which is exactly what socket activation
    hands over. Nothing here binds, and nothing unlinks a path systemd owns.
    """
    return socket.socket(fileno=LISTEN_FD)


def bound_socket(path: Path) -> socket.socket:
    """Bind and listen on `path` ourselves, owner-only, for the by-hand path.

    The mode is set here because skid owns the bind. Letting the server create
    the socket from a path is what produced an 0666 socket whose privacy came
    entirely from the directory above it.
    """
    path.unlink(missing_ok=True)
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(str(path))
    path.chmod(0o600)
    sock.listen()
    return sock


def main() -> int:
    """Serve until stopped."""
    service, app = build()

    if os.environ.get("LISTEN_FDS"):
        sock = inherited_socket()
    else:
        path = ensure_runtime_dir() / "skid.sock"
        if someone_is_listening(path):
            print(
                f"skid is already serving on {path}. Refusing to take it over."
                "\nStop it first with: systemctl --user stop skid.socket skid.service",
                file=sys.stderr,
            )
            service.stop()
            return 1
        print(f"no systemd; serving on {path}", file=sys.stderr)
        sock = bound_socket(path)

    notify_ready()

    interval = watchdog_interval()
    if interval is not None:
        threading.Thread(
            target=keep_pinging, args=(service, interval), daemon=True
        ).start()

    waitress.serve(app, sockets=[sock], clear_untrusted_proxy_headers=True)

    service.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
