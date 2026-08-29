"""The fixtures more than one test file needs, and nothing else.

**Why these are here rather than copied.** `config_path` and `service` were
written out verbatim in `test_routes`, `test_client` and then `test_say`, and
pylint's duplicate-code found the first pair before the third arrived. Three
statements of one service are three things to keep in step, and the failure is
quiet: a file whose copy has drifted still passes, against a service that is no
longer the one the others test.

**Nothing here is a double.** The service is real, with a player that is a
shell script exiting zero, and the transports are real requests into the real
Flask app. Only `speak` reaches the engine and it returns at queue time, so
these stay fast without anything being stood in for.

The worker thread is deliberately not started. A test that wants the queue
drained starts it; every other one can read the spool knowing nothing is moving
underneath it.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from flask.testing import FlaskClient

from skid.client import Backend
from skid.config import Config
from skid.routes import build_app
from skid.service import Service


@pytest.fixture(name="config_path")
def config_path_fixture(tmp_path: Path) -> Path:
    """A config file path in a directory the test owns."""
    return tmp_path / "config.yaml"


@pytest.fixture(name="service")
def service_fixture(tmp_path: Path, config_path: Path) -> Iterator[Service]:
    """A real service with a player that says nothing and exits zero."""
    script = tmp_path / "player.sh"
    script.write_text("#!/bin/sh\ntrue\n", encoding="utf-8")
    script.chmod(0o755)

    built = Service(
        config=Config(player=f"{script} {{file}}"),
        work_dir=tmp_path / "work",
        log_path=tmp_path / "log",
        config_path=config_path,
    )
    yield built
    built.stop()


@pytest.fixture(name="client")
def client_fixture(service: Service, config_path: Path) -> Iterator[FlaskClient]:
    """The real app over that service, called as a client calls it."""
    app = build_app(service, config_path)
    app.config["TESTING"] = True
    with app.test_client() as http:
        yield http


@pytest.fixture(name="backend")
def backend_fixture(service: Service, config_path: Path) -> Iterator[Backend]:
    """A backend over the real app, reached through a real WSGI request."""
    app = build_app(service, config_path)
    transport = httpx.WSGITransport(app=app)
    with httpx.Client(transport=transport, base_url="http://localhost") as http:
        yield Backend(http, "/wsgi/skid.sock")
