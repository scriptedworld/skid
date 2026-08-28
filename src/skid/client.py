"""A stdio front end for the one running service.

MCP clients configure a command and speak JSON-RPC over its stdin and stdout.
skid serves MCP over HTTP on a unix socket instead, because that is what keeps
it a single warm process and owner-only (FR-5.1, FR-5.4). This bridges the two:
one line in, one POST, one line out.

**It holds nothing.** No model, no queue, no config. Every client that starts
one is talking to the same service, which is the whole point: a stdio server per
client would load kokoro per client.

If the service is not running, `skid` under systemd socket activation starts on
the first connection. Without systemd there is nothing to start it, and this
says so rather than hanging.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

ENDPOINT = "/mcp"
HOST = "http://localhost"
TIMEOUT = 300.0
"""Long enough to cover a cold start that loads the model."""


def socket_path() -> Path:
    """The socket the service listens on."""
    base = os.environ.get("XDG_RUNTIME_DIR")
    root = Path(base) if base else Path("/run/user") / str(os.getuid())
    return root / "skid" / "skid.sock"


def _payloads(response: httpx.Response) -> list[str]:
    """Pull JSON-RPC messages out of a response, plain or server-sent events."""
    body = response.text
    if not body.strip():
        return []
    if "text/event-stream" in response.headers.get("content-type", ""):
        return [
            line[len("data:") :].strip()
            for line in body.splitlines()
            if line.startswith("data:")
        ]
    return [body.strip()]


def main() -> int:
    """Forward stdin to the service and its answers back to stdout."""
    path = socket_path()
    transport = httpx.HTTPTransport(uds=str(path))
    session: str | None = None

    with httpx.Client(transport=transport, base_url=HOST, timeout=TIMEOUT) as http:
        for line in sys.stdin:
            request = line.strip()
            if not request:
                continue

            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            }
            if session:
                headers["mcp-session-id"] = session

            try:
                response = http.post(ENDPOINT, content=request, headers=headers)
            except httpx.HTTPError as exc:
                sys.stderr.write(f"skid is not reachable at {path}: {exc}\n")
                return 1

            session = response.headers.get("mcp-session-id", session)
            for payload in _payloads(response):
                sys.stdout.write(payload + "\n")
                sys.stdout.flush()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
