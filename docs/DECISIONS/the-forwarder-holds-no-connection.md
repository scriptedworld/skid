# The forwarder holds no connection

**This is planned and not built.** What runs today is `skid-mcp` as
`src/skid/client.py` describes it. Nothing in this file describes current
behaviour except the section that says it does.

## The decision

skid gets a new MCP forwarder that passes each call straight through to the
systemd-managed backend and keeps nothing open between calls. Forward the bytes,
answer, hold nothing.

## Why, and it is about restarts rather than speed

The backend is socket-activated and systemd restarts it. A client holding a
long-lived connection turns a clean restart into a broken client: the connection
it is holding refers to a process that no longer exists, and the caller finds
out on its next call rather than at the moment of the restart.

Every consumer then needs reconnection logic, and that logic runs only when
something has already gone wrong. It is the least exercised path in the system
and the one that has to work under the worst conditions. Removing the held
connection removes the path.

Forwarding per call makes a restart invisible to the caller. There is nothing to
go stale, so there is nothing to recover.

This follows the shape the project already committed to rather than changing
direction. FR-9.7 has an install enable the socket and not the service, so the
first connection is what starts the backend; FR-5.2 makes the client an MCP
server in its own process. Holding no connection is what those two imply once
the backend can restart underneath a caller.

## The same reasoning has already been applied once, to session state

Removing the MCP session from the service was this argument about state. The
service kept a session id, a restart forgot it, and a client that could not
match the answer to its request waited until something outside it gave up. The
fix was to hold no session rather than to recover from a lost one.

That left the state gone and the connection still held. This is the other half.

## What is true today, and it is measured

`Backend.over_socket` builds one `httpx.Client` per `skid-mcp` process and holds
it for the life of the stdio loop, closing it on the way out. httpx pools
connections, so the process keeps one open and reuses it:

    .venv/bin/python -c "
    from skid.client import Backend, socket_path
    b = Backend.over_socket(socket_path())
    p = b._http._transport._pool
    b.call('status'); print(len(p.connections), [str(c) for c in p.connections])
    b.call('status'); print(len(p.connections), [str(c) for c in p.connections])
    b.close()"

    1 ["<HTTPConnection ['http://localhost:80', HTTP/1.1, IDLE, Request Count: 1]>"]
    1 ["<HTTPConnection ['http://localhost:80', HTTP/1.1, IDLE, Request Count: 2]>"]

One connection, reused, idle between calls. So "holds nothing between calls" in
`client.py` and `docs/SPEC.md` is a statement about state and it is accurate
about state. The connection is the thing it does not cover, and this decision is
about the connection.

## What is not established

Whether a pooled idle connection actually breaks the caller's next call after a
backend restart has not been measured here. Two documents say a restart costs a
connection refused for as long as the service takes to come back,
`docs/PROJECT.md` and the `client.py` module docstring, and neither was written
against a held connection. A stale pooled connection more usually fails as a
broken pipe on the next write than as a refusal.

Settling it costs one restart and two calls: make a call, restart the service,
call again, and read what the second one raises. It was not done here because
the service is shared and other callers were using it.

That measurement does not change this decision. It changes how the current
behaviour is described, and it is worth taking before anybody writes the
forwarder, because it establishes what the forwarder is fixing rather than
assuming it.
