# FR-4.9, queued speech expires

| ID | Requirement | |
|---|---|---|
| FR-4.9 | A submission older than the configured age is discarded rather than spoken, and the discard is recorded. Default five minutes. | [A] |

Stated 2026-08-28, and it amends a settled trade rather than filling a gap.

**FR-7.2 and FR-7.3 say nothing is dropped and nothing is capped.** An age limit
is a cap, and it is taken deliberately: a durable queue can outlive the process
that filled it, so a backlog can now be old in a way an in-memory one never was.

Speech is time-sensitive in a way text is not. A summary about work finished
five minutes ago is still current; the same summary an hour later is noise read
at somebody who has missed the moment it was about, and it delays everything
behind it while being spoken.

**Nothing vanishes silently.** A discarded submission is logged where FR-4.7's
log lives, so the promise FR-4.5 makes stays honest: a caller was told the work
was accepted, and if it is not spoken there is a record saying why.

## Five minutes is a preference

Nothing measures it and nothing could. It is a judgement about how long a
summary stays worth hearing, not a property of the machine, so it is a
`PREFERENCE` rather than a `FACT` and a later reader should leave it alone
rather than correct it toward a default.

It lives in the config file beside the greeting window (FR-3.4, FR-7.1), so it
is changeable without a release and by either route FR-6.3 requires.

**It is ten times the greeting window's thirty seconds, and that is a
coincidence.** The two answer different questions, neither constrains the other,
and the ratio is not a rule to preserve if either moves.

## What it does not do

It does not bound the queue's depth. FR-7.2's "unbounded" stands: a thousand
submissions in five minutes are all spoken. Age is the only cap, because age is
what makes a message not worth hearing, and depth is not.
