"""The entry point: warm the model, then serve MCP over the socket systemd gave.

skid does not create or bind the socket. systemd creates it, starts skid on the
first connection, and restarts it if it dies, so there is no start protocol
here: no lock file, no stale-path handling, no readiness race between clients.

Run without systemd it binds a socket itself, which is for trying it by hand
rather than the way it is meant to run. **It refuses if something is already
listening there**, because the by-hand path used to unlink whatever it found and
bind over it, which silently takes the socket away from systemd and leaves two
resident models with only one of them reachable.

**The two paths differ in how FR-5.4 is met, and the difference is worth
knowing.** Under systemd the unit sets `SocketMode=0600` on the socket itself.
Run by hand, uvicorn chmods the socket to 0666 after binding it, whatever umask
it was created under, so owner-only access rests entirely on the 0700 directory
holding it. Both are private; only one says so on the socket.
"""

from __future__ import annotations

import os
import socket
import sys
import tempfile
from pathlib import Path

import uvicorn
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette

from skid.config import default_config_path, load_config
from skid.generation import Generator
from skid.server import build_server
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


def notify_ready() -> None:
    """Tell systemd the model is loaded, so active and answerable are one thing.

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
        sock.sendall(b"READY=1")


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


def build() -> tuple[Service, Starlette]:
    """Build the service and the ASGI app, with the model already warm."""
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
    app = build_server(service, config_path).streamable_http_app(
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=["localhost", "localhost:*", "skid"],
        )
    )
    return service, app


def main() -> int:
    """Serve until stopped."""
    service, app = build()
    notify_ready()

    if os.environ.get("LISTEN_FDS"):
        uvicorn.run(app, fd=LISTEN_FD, log_level="warning")
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
        path.unlink(missing_ok=True)
        print(f"no systemd; serving on {path}", file=sys.stderr)
        uvicorn.run(app, uds=str(path), log_level="warning")

    service.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
