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

import socket
from pathlib import Path

from skid.main import someone_is_listening


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
