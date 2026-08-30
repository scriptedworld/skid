# skid, what is not done

Every requirement `docs/REQUIREMENTS/` states is built and has a test citing it.
What follows is what is open anyway: one blocker, one known defect, one piece of
planned work, and a set of questions nothing depends on.

## The blocker: skid cannot be installed from a standalone clone

`wrench` handles the config file and the spool, it is unpublished, and both
`pyproject.toml` and `uv.lock` name it by relative path at `../wrench/python`.
Without a wrench checkout beside this one, `uv sync` fails and so does the
installer, which means the suite cannot be run either.

Publishing wrench, or having the bootstrap fetch it, is the prerequisite for
skid going anywhere. Nothing else on this page matters until it is done.

## The known defect: a voice that is named but cannot render

`set_voice` checks the submitted name against kokoro's list of 54 and nothing
else, then persists it. Whether a voice actually renders on a given machine is
not checked, so a name that is in the list and fails to produce audio is
accepted, written to the config, and then every submission fails silently: the
caller has already been told its message was queued, and the setting survives a
restart. Recovering means editing `~/.config/skid/config.yaml` by hand.

That is FR-6.5 unmet, on a row that has a test citing it. The automatic
assignment path cannot reach one of these, because the shortlist in the config
was chosen from voices that produced a sample; the exposed tool can.

## Planned: an MCP forwarder that holds no connection

The largest outstanding piece of work, and it is not started. A new MCP
forwarder passes each call straight through to the backend and keeps nothing
open between calls.

The reason is restarts rather than speed. The backend is socket-activated and
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
because it sees a mark and a row rather than a behaviour.

Three rows here have passed the checker while the behaviour was wrong or the
test could not have caught it. The defect above is one of them, found by
measurement rather than by the suite. So a mark pointing at the wrong row, or a
test too weak to fail, is invisible to the gate and only reading the row against
the test finds it.

Some rows have been probed by breaking the code and confirming the test fails.
Most have not. `docs/TEST_PLAN.md` records which, and records the three rows no
mutation can break, so an unprovable row is stated rather than counted as
covered.

## Designed against an imagined need

Nobody has yet heard skid mispronounce anything in ordinary use. The whole
substitution surface, the first-match-wins ordering, the literal and regex
split, and file order being load-bearing, was designed from argument rather than
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
voice, is the right length. It was chosen rather than measured, and the first
evidence either way will be the shortlist running out or not.
