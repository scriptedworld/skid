# Deleting an endpoint recreated the bug that deleting it was supposed to remove

2026-08-28. Cost: every agent session on the machine lost its voice for about
two hours, with a service that was working perfectly throughout.

## What the change was for

`skid` served MCP over HTTP and kept a session id in memory. A restart forgot
it, the service answered `404 Session not found` with `"id": null`, and a
JSON-RPC client cannot match a null id to the request it is waiting on, so it
waited until something outside gave up. Measured earlier: 1800 seconds.

`resilience/40` moved the MCP server into the stdio script and deleted the
service's `/mcp` endpoint, so no session id exists on either side. That reasoning
was right and the change was right.

## What happened

With nothing at `/mcp`, Flask answered a 404 with an **HTML error page**.

An HTML page is no more matchable to a pending JSON-RPC request than a null id
is. Every already-running client waited exactly as before. A `status()`
call was still outstanding at 120 seconds when I killed it.

**The defect was never "a session id goes stale".** It was "answer a waiting
client with something it cannot match to its request". Removing the session
removed one source of that, and the deletion created another.

## The second mistake, which was mine and worse

I then made `/mcp` answer a JSON-RPC error carrying the request's own id. That
unblocked every caller, and I recorded it as fixed.

It was half a fix. The callers were unblocked **and still could not speak**,
because an MCP stdio server is spawned once at session start and lives as long
as the session. Shims were running from 02:06 through 10:48, up to eleven hours
old. Only the person holding a session can restart it, so "fail cleanly" left
every agent mute until a human intervened.

The endpoint had to do the work, not report that it could not. It serves MCP
statelessly now, `8a05249`.

## What to take from it

**Deleting a protocol surface is a breaking change to every client already
running**, and clients you cannot restart are clients you have to keep serving.
The question before removing one is not "is anything wrong with removing it" but
"what is holding a connection to it right now, and who can restart those".

    pgrep -af skid-mcp
    for p in $(pgrep -f skid-mcp); do ps -o pid=,lstart= -p $p; done

**Name the defect by its effect, not by its mechanism.** Had the original been
written down as "a waiting client gets something it cannot match" rather than "a
session id goes stale", the HTML 404 would have been obviously the same bug. It
was written the second way, and I did not see it.

**"Fails cleanly" is not "works" when the caller cannot be restarted.** A clean
error is the right outcome for a caller that can retry or a person who can act.
For a long-lived process nobody can respawn, it is a better-labelled outage.

**I predicted the clean failure out loud and deployed on it.** I traced the old
recovery path, concluded old shims would report an error, said so out loud,
and was wrong within a minute of the restart. The trace was of the code I had
just deleted; the path that actually ran was Flask's default 404 handler, which
I had not looked at because it was not code anybody wrote.

## Still true

`/mcp` is a compatibility route with a stated end, `routes.LEGACY_ENDPOINT`.
`clank/tasks/skid/resilience/50` retires it, and is `.blocked` on the check
above rather than on a date. **Retiring it on a quiet estate is the same
mistake**: nobody running a shim is not the same as nobody able to.
