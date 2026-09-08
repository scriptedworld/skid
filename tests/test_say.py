"""`skid-say`, against the real service, over a real request.

**Why this file exists at all.** `skid-say` was written and deployed on
2026-08-28 because the MCP route was unusable and the machine had been silent
for hours. It went out untested: `coverage report` read `say.py 32 stmts 32
miss 0%`, and neither gate noticed. Traceability read 48 of 48 because it
measures requirement-to-test and every row already had one, and the gate's
coverage task runs from PATH's python, which cannot import skid's dependencies.
Two green numbers over an uncovered file.

**Nothing is stood in for.** `run` is exercised against the actual Flask app
behind `httpx.WSGITransport`, exactly as `tests/test_client.py` does, so a call
goes through the code a socket would reach. `main` is exercised twice over a
real unix socket: once with nothing listening, and once against waitress
serving the real app, which is the arrangement the installed command meets.

**The argument surface is a contract with a person, not with a client.** It is
what somebody types at 2am when nothing else works, so the cases here are the
ones a person gets wrong: no arguments, a name with nothing to say, and
`--status` with a stray positional after it.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
from waitress.server import create_server

from skid.config import load_config
from skid.routes import build_app
from skid.service import Service
from skid.spool import Spool
from skid_mcp.client import Backend, Unreachable
from skid_mcp.say import build_parser, main, run


def _said(backend: Backend, *arguments: str) -> str:
    """Run one command line the way `main` does, and return what it printed."""
    return run(backend, build_parser().parse_args(list(arguments)))


def _queued(tmp_path: Path) -> list[tuple[str, list[str]]]:
    """Every submission on the spool, as the service will find it.

    Read through a second `Spool` over the same directory rather than through
    the service's private one. The service's worker thread is not started by
    the fixture, so nothing is draining the queue underneath this.
    """
    spool = Spool(tmp_path / "spool")
    found = []
    while (entry := spool.take(now=0.0)) is not None:
        found.append((entry.submission.name, list(entry.submission.messages)))
        spool.done(entry)
    return found


# COVERS: FR-4.1 | positive
def test_the_messages_arrive_as_one_array_in_order(
    backend: Backend, tmp_path: Path
) -> None:
    """`skid-say silo "first" "second"` is one submission carrying both.

    The documented two-message form from `say.py`'s own docstring. Asserted as
    one entry rather than two, because the array is what FR-4.2 works ahead on
    and what FR-3.3 announces once instead of per message. Two entries would
    satisfy "both messages arrived" and break both of those.
    """
    _said(backend, "silo", "first", "second")

    assert _queued(tmp_path) == [("silo", ["first", "second"])]


# COVERS: FR-3.1 | positive
def test_the_submission_carries_the_name_from_the_command_line(
    backend: Backend, tmp_path: Path
) -> None:
    """The first positional is who is speaking, not the first thing said."""
    _said(backend, "toolbox", "the gate is green")

    assert _queued(tmp_path) == [("toolbox", ["the gate is green"])]


# COVERS: FR-3.1 | negative
def test_no_arguments_at_all_is_refused_and_nothing_is_sent(
    backend: Backend, service: Service
) -> None:
    """A bare `skid-say` is the commonest thing a person types first.

    Refused locally, so the service never sees a submission naming nobody.
    """
    with pytest.raises(Unreachable, match="say who is speaking"):
        _said(backend)

    assert service.status()["pending"] == 0


# COVERS: FR-4.1 | negative
def test_a_name_with_no_messages_is_refused_and_nothing_is_sent(
    backend: Backend, service: Service
) -> None:
    """`skid-say silo` parses cleanly and says nothing, so it is caught here.

    argparse cannot refuse this: `messages` is `nargs="*"`, so an empty list is
    a valid parse. The refusal is `run`'s, and it happens before the request,
    which is what the pending count asserts.
    """
    with pytest.raises(Unreachable, match="what to say"):
        _said(backend, "silo")

    assert service.status()["pending"] == 0


# COVERS: FR-4.7 | positive
def test_status_reports_the_queue_a_caller_cannot_log(backend: Backend) -> None:
    """`speak` returned at queue time, so `--status` is how a person looks.

    Parsed back rather than matched as text, because what is being asserted is
    that the report crossed intact and carries every field, not how it was
    formatted.

    `assigned` joined the set with FR-10.2. It answers the question a listener
    actually has once names sound different, which is which name is which voice,
    and it is empty until a shortlist is configured.
    """
    reported = json.loads(_said(backend, "--status"))

    assert set(reported) == {"pending", "recent_failures", "voice", "assigned"}
    assert reported["pending"] == 0
    assert reported["assigned"] == {}


# COVERS: FR-4.7 | edge
def test_status_is_answered_even_with_a_stray_positional(
    backend: Backend, service: Service
) -> None:
    """`skid-say --status silo` is a person hedging, and it must not speak.

    `silo` parses into `name` and would be a submission under any other flag.
    `--status` is tested first in `run` deliberately, so the query wins and
    nothing is queued. The alternative, refusing the combination, would be
    stricter and worse: it answers a question nobody asked at the moment
    somebody is trying to find out what is wrong.
    """
    reported = json.loads(_said(backend, "--status", "silo"))

    assert reported["pending"] == 0
    assert service.status()["pending"] == 0


# COVERS: FR-6.3 | positive
def test_setting_the_voice_reaches_the_setting_the_service_reads(
    backend: Backend, config_path: Path
) -> None:
    """A third way in must not become a third copy of the setting.

    `--voice` posts to the same route the MCP tool dispatches to, so it lands
    in the file that FR-7.1 makes the record. Asserted at the file, because
    that is the thing both other routes read.
    """
    _said(backend, "--voice", "af_bella")

    assert load_config(config_path).voice == "af_bella"


# COVERS: FR-6.5 | negative
def test_a_voice_that_would_silence_skid_is_refused_and_not_written(
    backend: Backend, config_path: Path
) -> None:
    """The command line is the last moment the person is present to be told."""
    with pytest.raises(Unreachable, match="af-typo"):
        _said(backend, "--voice", "af-typo")

    assert not config_path.exists()


# COVERS: FR-5.3 | negative
def test_an_unreachable_socket_exits_one_and_names_where_it_looked(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole point of this command is failing usefully when skid is down.

    A real transport against a path nothing is listening on, reached through
    `socket_path` by setting the variable it reads, so what is exercised is
    the entry point rather than a hand-built client. The path is in the message
    because "it did not work" sends a person looking in the wrong place.
    """
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))

    code = main(["silo", "hello"])

    assert code == 1
    assert str(tmp_path / "skid" / "skid.sock") in capsys.readouterr().err


# COVERS: FR-5.3 | positive
def test_the_command_works_end_to_end_over_a_real_socket(
    service: Service,
    config_path: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The arrangement the installed command actually meets, with nothing faked.

    waitress serving the real app on a real unix socket, reached by the real
    entry point through the real `socket_path`. This is the only test that
    exercises the transport `main` builds; every other one here stops at `run`,
    where the transport is the WSGI one.
    """
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    socket = tmp_path / "skid" / "skid.sock"
    socket.parent.mkdir(parents=True, exist_ok=True)

    server = create_server(build_app(service, config_path), unix_socket=str(socket))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        code = main(["--status"])
    finally:
        server.close()
        thread.join(timeout=5)

    assert code == 0
    assert json.loads(capsys.readouterr().out)["pending"] == 0
