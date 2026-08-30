"""`skid-say`: reach skid from a shell, with no MCP client in the way.

**Why this exists.** The MCP route needs a `skid-mcp` the session spawned at
start-up, so a session whose shim predates a deploy cannot speak until it is
restarted, and only a person can do that. That left the machine silent for hours
with a service that was working perfectly, which is a bad way for a voice tool
to fail.

The socket is the interface and MCP is one client of it. This is another, and it
needs nothing but the socket being there.

    skid-say silo "the gate is green"
    skid-say silo "first" "second"      one submission, two messages
    skid-say --status
    skid-say --voice af_bella

Equivalent to a `curl --unix-socket`, which also works and is worth knowing when
this is not installed:

    curl --unix-socket $XDG_RUNTIME_DIR/skid/skid.sock \\
         -H 'Content-Type: application/json' \\
         -d '{"name":"silo","messages":["hello"]}' http://localhost/speak

This carries no state and holds nothing open. It is the same `Backend` the MCP
server dispatches through, so there is one path to the service and not two.
"""

from __future__ import annotations

import argparse
import json
import sys

from skid.client import Backend, Unreachable, socket_path


def build_parser() -> argparse.ArgumentParser:
    """The command line, which is a name and its messages or one query."""
    parser = argparse.ArgumentParser(
        prog="skid-say",
        description="Say something through skid, without an MCP client.",
    )
    parser.add_argument("name", nargs="?", help="who is speaking")
    parser.add_argument("messages", nargs="*", help="what to say, in order")
    parser.add_argument(
        "--status", action="store_true", help="queue depth, failures and voice"
    )
    parser.add_argument("--voice", metavar="VOICE", help="set the voice and persist it")
    return parser


def run(backend: Backend, arguments: argparse.Namespace) -> str:
    """Do the one thing that was asked, and return what to print."""
    if arguments.status:
        return json.dumps(backend.call("status"), indent=2, sort_keys=True)
    if arguments.voice:
        return str(backend.call("set_voice", voice=arguments.voice))
    if not arguments.name or not arguments.messages:
        raise Unreachable("say who is speaking and what to say")
    return str(
        backend.call("speak", name=arguments.name, messages=list(arguments.messages))
    )


def main(argv: list[str] | None = None) -> int:
    """Reach the service over its socket and report what it said.

    `argv` defaults to None, which is what `parse_args` already reads
    `sys.argv` for, so the console script is unchanged. Naming it lets a test
    call this entry point with its own arguments rather than writing over the
    process's, which is the whole seam and it costs nothing.
    """
    arguments = build_parser().parse_args(argv)
    with Backend.over_socket(socket_path()) as backend:
        try:
            print(run(backend, arguments))
        except Unreachable as exc:
            print(f"skid-say: {exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
