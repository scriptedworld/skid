"""The entry point's one decision: whether the socket path is already somebody's.

Nothing here starts a service. `someone_is_listening` is a question about a
path, so these tests make real unix sockets in `tmp_path` and ask about them.

**The bug this is written against.** Run by hand, skid unlinked whatever was at
the socket path and bound its own. Under socket activation that takes the path
away from systemd, which goes on believing it owns a socket nobody can reach.
Measured 2026-08-28: a by-hand instance started at 00:54 was still resident at
03:18 holding 1.73 GB, listening on an inode the path no longer resolved to,
reachable by nobody and reported by nothing.
"""

from __future__ import annotations

import os
import socket
import stat
import threading
import time
from pathlib import Path

import pytest

from skid.config import Config
from skid.generation import Generator
from skid.main import (
    bound_socket,
    build,
    ensure_runtime_dir,
    inherited_socket,
    keep_pinging,
    notify,
    notify_ready,
    runtime_dir,
    someone_is_listening,
    state_dir,
    watchdog_interval,
)
from skid.service import Service, Workspace


# COVERS: FR-5.4 | negative
def test_a_path_with_nothing_there_is_free(tmp_path: Path) -> None:
    """No file means no owner, which is the ordinary first start."""
    assert someone_is_listening(tmp_path / "skid.sock") is False


# COVERS: FR-5.4 | property
def test_a_socket_someone_is_listening_on_is_not_free(tmp_path: Path) -> None:
    """A live server owns its path, and skid must not bind over it.

    This is the case that cost 1.73 GB and two hours: the old code unlinked
    exactly this and carried on.
    """
    path = tmp_path / "skid.sock"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as held:
        held.bind(str(path))
        held.listen(1)

        assert someone_is_listening(path) is True


# COVERS: FR-5.4 | edge
def test_a_socket_file_nobody_is_listening_on_is_stale(tmp_path: Path) -> None:
    """A leftover file from a process that died is safe to replace.

    The distinction is the whole function. Refusing on the mere presence of a
    file would make a crash require manual cleanup before skid could start,
    which is the failure mode socket activation was adopted to delete.
    """
    path = tmp_path / "skid.sock"
    holder = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    holder.bind(str(path))
    holder.listen(1)
    holder.close()

    assert path.exists()
    assert someone_is_listening(path) is False


# COVERS: FR-5.4 | edge
def test_an_ordinary_file_at_the_path_is_not_a_listener(tmp_path: Path) -> None:
    """Whatever this is, it is not a server, and connecting is how we know."""
    path = tmp_path / "skid.sock"
    path.write_text("not a socket", encoding="utf-8")

    assert someone_is_listening(path) is False


# COVERS: FR-5.4 | positive
def test_the_runtime_directory_is_owner_only_however_it_was_left(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The mode is asserted on every start, not only on the one that creates it.

    `mkdir(mode=...)` does nothing to a directory that already exists, and the
    service makes its clips directory inside this one, so whichever ran first
    would decide the mode. Measured 2026-08-28 before the chmod existed: 0775.
    This starts from a wrong mode on purpose, because starting from absent
    would pass either way.
    """
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    already = tmp_path / "skid"
    already.mkdir()
    already.chmod(0o775)

    made = ensure_runtime_dir()

    assert made == tmp_path / "skid"
    assert stat.S_IMODE(made.stat().st_mode) == 0o700


# COVERS: FR-5.4 | property
def test_the_runtime_directory_follows_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """XDG_RUNTIME_DIR decides, and its absence falls back to a per-user path.

    The fallback carries the uid, because a shared temporary directory with a
    fixed name is another user's to create first.
    """
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    assert runtime_dir() == tmp_path / "skid"

    monkeypatch.delenv("XDG_RUNTIME_DIR")
    assert str(os.getuid()) in str(runtime_dir())
    assert runtime_dir().name == "skid"


# COVERS: FR-5.4 | property
def test_the_state_directory_follows_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The log is what a person reads when it goes quiet, so where it lands matters."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    assert state_dir() == tmp_path / "skid"

    monkeypatch.delenv("XDG_STATE_HOME")
    assert state_dir() == Path.home() / ".local" / "state" / "skid"


# COVERS: FR-5.1 | property
@pytest.mark.parametrize(
    ("name", "usec", "pid", "expected"),
    [
        ("unset", None, None, None),
        ("empty", "", None, None),
        ("ours", "10000000", None, 5.0),
        ("ours by pid", "10000000", "self", 5.0),
        ("inherited by a child", "10000000", "1", None),
    ],
)
def test_the_watchdog_interval_is_half_what_the_unit_asked_for(
    name: str,
    usec: str | None,
    pid: str | None,
    expected: float | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Half of WATCHDOG_USEC, and nothing at all for a process that only inherited it.

    systemd sets these for the main process and children inherit them, so a
    forked process pinging would keep the service alive on its parent's behalf.
    The pid check is what stops that, and `inherited by a child` is the case it
    exists for.
    """
    monkeypatch.delenv("WATCHDOG_USEC", raising=False)
    monkeypatch.delenv("WATCHDOG_PID", raising=False)
    if usec is not None:
        monkeypatch.setenv("WATCHDOG_USEC", usec)
    if pid is not None:
        monkeypatch.setenv("WATCHDOG_PID", str(os.getpid()) if pid == "self" else pid)

    assert watchdog_interval() == expected, name


# COVERS: FR-5.1 | positive
def test_readiness_reaches_the_socket_systemd_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """READY=1 arrives on a real datagram socket at NOTIFY_SOCKET.

    A real socket is bound here rather than the send being intercepted: the
    thing worth knowing is that the datagram arrives at the path systemd named,
    and only an actual socket can answer that.
    """
    address = tmp_path / "notify.sock"
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as listener:
        listener.bind(str(address))
        listener.settimeout(2.0)
        monkeypatch.setenv("NOTIFY_SOCKET", str(address))

        notify_ready()

        assert listener.recv(64) == b"READY=1"


# COVERS: FR-5.1 | negative
def test_nothing_is_sent_and_nothing_raised_when_systemd_is_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run by hand there is no NOTIFY_SOCKET, and that is not an error."""
    monkeypatch.delenv("NOTIFY_SOCKET", raising=False)

    notify(b"READY=1")


# COVERS: FR-5.4 | positive
def test_a_socket_bound_by_hand_is_owner_only(
    tmp_path: Path,
) -> None:
    """skid sets the mode because skid owns the bind.

    Letting the server create the socket from a path produced an 0666 socket
    whose privacy came entirely from the directory above it.
    """
    path = tmp_path / "skid.sock"

    sock = bound_socket(path)
    try:
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert someone_is_listening(path) is True
    finally:
        sock.close()


# COVERS: FR-5.4 | edge
def test_binding_replaces_a_stale_socket_file(tmp_path: Path) -> None:
    """A leftover file is unlinked, which is safe once nobody is listening on it."""
    path = tmp_path / "skid.sock"
    path.write_text("stale", encoding="utf-8")

    sock = bound_socket(path)
    try:
        assert someone_is_listening(path) is True
    finally:
        sock.close()


# COVERS: FR-9.7 | property
def test_the_inherited_socket_is_taken_as_an_object_not_rebound(
    tmp_path: Path,
) -> None:
    """Socket activation hands over a bound, listening socket, and skid serves it.

    A real listening socket is put on fd 3, which is what systemd does, so this
    exercises the same handover rather than describing it. Nothing here binds
    and nothing unlinks a path systemd owns.
    """
    path = tmp_path / "skid.sock"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(path))
    listener.listen()

    saved = os.dup(3) if _fd_open(3) else None
    try:
        os.dup2(listener.fileno(), 3)
        taken = inherited_socket()
        try:
            assert taken.family == socket.AF_UNIX
            assert taken.getsockname() == str(path)
        finally:
            taken.detach()
    finally:
        if saved is not None:
            os.dup2(saved, 3)
            os.close(saved)
        listener.close()


def _fd_open(fd: int) -> bool:
    """Whether `fd` is currently open, so the test can put it back as it found it."""
    try:
        os.fstat(fd)
    except OSError:
        return False
    return True


# COVERS: FR-5.1 | edge
def test_readiness_reaches_an_abstract_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    """systemd may name an abstract socket, which starts `@` and binds at NUL.

    The leading `@` is a convention in the variable, not part of the address, so
    it is rewritten to a NUL byte before connecting. A real abstract socket is
    bound here, because that rewrite is the only thing this branch does and a
    path socket would not exercise it.
    """
    address = f"\0skid-test-{os.getpid()}"
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as listener:
        listener.bind(address)
        listener.settimeout(2.0)
        monkeypatch.setenv("NOTIFY_SOCKET", "@" + address[1:])

        notify(b"READY=1")

        assert listener.recv(64) == b"READY=1"


# COVERS: FR-5.1 | positive
def test_building_warms_the_model_and_returns_a_servable_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`build` produces a started service and an app, with the model already loaded.

    **Slow and real.** This loads kokoro, which is the point: FR-5.1 is that a
    backend holds the model warm so a message does not pay start-up, and a test
    that skipped the load would assert the opposite of the requirement.

    Every directory it touches is redirected through the environment, which is
    what `runtime_dir`, `state_dir` and `default_config_path` already read, so
    nothing here is replaced and nothing is written outside `tmp_path`.
    """
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    (tmp_path / "run").mkdir()

    service, app = build()
    try:
        assert app.name
        assert service.is_progressing(time.monotonic()) is True
        assert (tmp_path / "run" / "skid").is_dir()
    finally:
        service.stop()


# COVERS: FR-5.1 | property
def test_the_watchdog_pings_only_while_the_service_is_getting_somewhere(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ping is withheld, not timed, and an idle service still counts as healthy.

    **Withholding is the whole mechanism.** A thread that pinged
    unconditionally would prove only that the thread runs, which is the failure
    the watchdog exists to detect, so `Service.is_progressing` is what decides.

    A real Service is built and a real datagram socket receives the ping.
    Nothing is substituted: the generator is constructed but never warmed, so
    no model is loaded and the service is still the real one.
    """
    address = tmp_path / "notify.sock"
    service = Service(
        config=Config(),
        generator=Generator(Config().voice),
        workspace=Workspace(
            work_dir=tmp_path / "clips",
            log_path=tmp_path / "skid.log",
            config_path=tmp_path / "config.yaml",
        ),
    )
    service.start()

    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as listener:
        listener.bind(str(address))
        listener.settimeout(3.0)
        monkeypatch.setenv("NOTIFY_SOCKET", str(address))

        pinger = threading.Thread(
            target=keep_pinging, args=(service, 0.05), daemon=True
        )
        pinger.start()
        try:
            assert listener.recv(64) == b"WATCHDOG=1"
        finally:
            service.stop()


# The withheld-ping branch of `keep_pinging` is NOT covered, deliberately.
#
# `is_progressing` is false only when the loop is not idle, nothing is playing,
# AND the last step was longer ago than PROGRESS_GRACE. A stopped service does
# not qualify: measured 2026-09-07, `service.start()` then `service.stop()`
# still reports progressing, because idle is set and idle is health.
#
# Reaching it needs a genuinely wedged serve loop. The two ways to fake one are
# replacing `is_progressing` and writing `service._loop.progressed` by hand, and
# both assert that the caller believes what the test told it rather than that
# the watchdog withholds when the service is stuck.
#
# It is the branch most worth having and the one this suite cannot honestly
# reach from outside. What would settle it is a seam that lets a real Service be
# put in a stuck state, which is a change to Service rather than to its tests.
