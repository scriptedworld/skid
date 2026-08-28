# FR-5.3, a call fails rather than hangs

| ID | Requirement | |
|---|---|---|
| FR-5.3 | Every request produces either a JSON-RPC response carrying that request's own id, or an error naming skid. There is no third outcome, and no request waits without a bound. | [D] |

Derived from FR-5.2 and FR-4.5. The client is an MCP server and submitting
returns when the work is queued, so a caller that cannot reach the backend has
to be told, and told quickly, because the agent is waiting on the call.

**Stated as a property rather than a list, because the list was the defect.**
An earlier wording enumerated two cases, absent and wedged, and read as complete
to everyone who met it, including the reviews that produced it. The case that
actually bit was in neither:

- **Absent.** Largely answered by socket activation: a connection starts the
  service and systemd restarts it if it dies, so a crash costs a wait rather
  than a refusal. The bound still matters, because starting includes loading a
  model.
- **Wedged.** Running and not answering, which nothing removes. `Type=notify`
  separates "started" from "ready" and makes it less likely; a process can still
  stop answering after both. Measured 2026-08-28, `WatchdogUSec=0`, so nothing
  detects it yet.
- **Answering with something that is not an answer.** The service is healthy
  and replies in under ten milliseconds; the reply just does not belong to the
  question. No timeout can catch this, because nothing is slow.

The third is why the row is a property now. Any enumeration invites a reader to
check their case against the list and stop; a rule makes a new shape fail the
requirement without anybody having predicted it.

## How the third one arrived

The MCP session lives in the service's memory, so restarting the service left
`skid-mcp` holding an id the new process had never heard of. It answered
`404 Session not found` with `"id": null`, the shim forwarded it verbatim, and
a JSON-RPC client cannot match a null id to the request it is waiting on. Three
sessions hung, one for five minutes, with no error for anyone to read.

**A reply that matches no pending request is worse than no reply**, because the
client's bookkeeping is correct and the conclusion it draws from it is wrong.

**It does not literally wait forever, and the true figure is worse for this
row rather than better.** Measured 2026-08-28 by the agent-support session, whose
call ended after the full half hour:

    MCP server "skid" tool "status" sent no response or progress for 1800s;
    aborting.

So a third party's backstop bounds the call. **That does not satisfy this
requirement, and the difference is the whole point of stating it as a property.**
An abort at 1800 seconds carrying no diagnosis is the failure being survived by
somebody else, not a call that failed as an error naming the backend. The
harness timeout fires identically whether the service is wedged, slow or absent,
because it has nothing to distinguish them with. The shim does.

**And half an hour is indistinguishable from slow work.** `TIMEOUT = 300.0` in
`client.py` is long precisely because a cold start loads a model, so a caller
cannot tell a wedged session from kokoro warming up. The window in which anyone
would investigate sits entirely inside the window in which the symptom looks
normal. A bound alone therefore buys nothing; **the property is a bounded time
that produces a diagnosis**, and 1800 seconds with none is the ceiling any
answer has to beat to be worth anything.

Restarting is the documented way to deploy an edit under an editable install, so
this fired on an ordinary action rather than a rare fault, and the service came
back healthy every time.

Answered in `client.py`: the shim caches the handshake, rebuilds the session
when the service says it is gone, and retries once. What it cannot recover
becomes a JSON-RPC error carrying the request's own id, because a client can
report an error and cannot report silence.

A timeout naming the service distinguishes all three from a call that failed on
its own merits, which matters because FR-4.7's log lives inside skid and is
exactly what a caller cannot reach when this fires.

## Why it is a row rather than a line of spec, twice over

It was a line of spec, at `fd42bdf`: "the backend is unreachable, which
`skid-mcp` returns as a tool error rather than hanging". Rewriting that section
dropped it, and no requirement noticed, because none existed.

    git show fd42bdf:docs/SPEC.md | grep -c unreachable    1
    grep -c unreachable docs/SPEC.md                       0    (before this row)

Found by the verification pass on the revision. It is the same failure FR-4.4
was written for, one document up: a property that only prose held, lost in an
edit nobody could have caught by reading the edit.
