# skid, what is not done

Every requirement `docs/REQUIREMENTS/` states is built and has a test citing it.
What follows is what is open anyway: three pieces of planned work, one known
defect, and a set of questions nothing depends on.

## Open: a voice belongs to a name, and is chosen rather than allocated

A voice is assigned from a pool as names arrive, so which one a name gets
depends on who spoke first and it does not survive the assignment expiring. A
name should hold a voice because somebody picked it for that name.

Two halves. **The assignment becomes data, not an allocation**: a name
maps to a voice in the config, and the pool stays as the fallback for a name
nobody has chosen for. And **the choice becomes settable over MCP**, which
`set_voice` cannot express today: it takes a voice and no name, so it changes
the default for everybody instead of one caller's voice.

## Open where nothing is configured: a voice that cannot render

`set_voice` measures a voice against the shortlist, which FR-10.1 makes the
statement of what renders on this machine, so the thirteen of kokoro's 54 that
need an uninstalled misaki language pack are refused with the caller still there
to be told. FR-10.7's pair is carried too: a voice accepted because the shortlist
lists it is spoken through the pipeline that entry declares.

What is open is the machine that configures no shortlist. The check falls back to
kokoro's list there, which is no weaker than it was and no stronger, and closing
it would mean building a pipeline inside a tool call. FR-6.5 records that.

## Planned: an MCP forwarder that holds no connection

The largest outstanding piece of work, and it is not started. A new MCP
forwarder passes each call straight through to the backend and keeps nothing
open between calls, which is the shape `skid-say` already has and the reason it
cannot fall out of step with the service behind it.

The reason is restarts, not speed. The backend is socket-activated and
systemd restarts it, so a client holding a long-lived connection turns a clean
restart into a broken client, and every consumer then needs reconnection logic
that runs only when something has already gone wrong. Forwarding per call makes
a restart invisible to the caller, because there is nothing to go stale.

Today's `skid-mcp` holds no session, which was removed deliberately, and does
hold a pooled connection: one `httpx.Client` per process, reused across calls.
So the existing statements that it holds nothing between calls are about state
and are accurate about state.
`docs/DECISIONS/the-forwarder-holds-no-connection.md` carries the reasoning, the
measurement, and the one thing about the current behaviour that has not been
measured.

## What a green traceability run does and does not prove

The checker reads both directions: every requirement has a test citing it, and
every test cites a requirement that exists. That proves the citations are
complete. It does not prove the code satisfies the requirement, and it cannot,
because it sees a mark and a row, not a behaviour.

Three rows here have passed the checker while the behaviour was wrong or the
test could not have caught it. The defect above is one of them, found by
measurement and not by the suite. So a mark pointing at the wrong row, or a
test too weak to fail, is invisible to the gate and only reading the row against
the test finds it.

Some rows have been probed by breaking the code and confirming the test fails.
Most have not. `docs/TEST_PLAN.md` records which, and records the three rows no
mutation can break, so an unprovable row is stated rather than counted as
covered.

## Designed against an imagined need

Nobody has yet heard skid mispronounce anything in ordinary use. The whole
substitution surface, the first-match-wins ordering, the literal and regex
split, and file order being load-bearing, was designed from argument and not
from a case that came up.

Treat those as settled by reasoning, not by evidence. The first real
mispronunciation somebody reaches for the config to fix is worth more than any
of it.

## A long message is cut off, and the ceiling is a guess

A player that has run for 300 seconds is killed, which is what stops one stuck
process silencing the machine while the queue grows behind it. Speech runs at
about 15.5 characters per second of audio, so that ceiling admits roughly 4,660
characters and truncates anything longer mid-sentence.

Nothing caps a message at submission, so the choice is between raising the
bound, capping the message, and accepting the truncation. An essay is not
something anyone sends by accident often, and nothing else depends on the
answer. The watchdog does not: playback pings regardless of clip length.

## The legacy protocol route

`/mcp` serves the MCP protocol statelessly, for clients built before the
protocol moved into the stdio script. It looks like dead code and is not.
Deleting it once reintroduced the exact hang it had been removing, because a
client that gets an HTML 404 where it expected a JSON-RPC message waits rather
than failing. `docs/LESSONS/deleting-an-endpoint-recreated-the-bug-it-removed.md`
is the write-up.

It can go once no client old enough to need it is still running. A drift test in
`tests/test_routes.py` names the route, so removing it is a change something
notices.

## Two entry points are barely covered

The package sits at 78 percent, and `main.py` and `install.py` are most of the
gap at about 35 percent each. Both are entry points a test process does not
reach by importing them, so the answer is not simply more unit tests. Nothing is
watching the number: traceability measures requirement to test, not line to
test, and `install.py` has all fourteen of its requirements covered at 36
percent of its lines.

## Open and small

Whether the greeting window should be settable through a tool as well as through
the config file. FR-3.4 requires only that it is configurable and FR-7.1 already
says which route would win, so nothing is blocked on deciding.

Whether the voice assignment window, six hours of quiet before a name loses its
voice, is the right length. It was chosen, not measured, and the first
evidence either way will be the shortlist running out or not.
