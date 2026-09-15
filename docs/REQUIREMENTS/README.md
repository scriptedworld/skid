# skid, Requirements

What must be true of voice output. Recorded before anything was designed, so the
spec is derived from these and not the reverse.

*Derives from:* requirements I stated.

Requirements are stated as observable properties: what is true of a run, not how
anything is arranged.

One file per requirement, named for its id and its slug, under a category
directory named for the section it came from. What goes inside a file is
`../DECISIONS/what-a-requirement-file-carries.md`.

## Status markers

`[A]` traces to something stated first-hand. `[D]` is derived from one. `[A/D]`
is both. `[?]` is an open question, recorded so it is not lost and carrying no
test yet.

Settled means testable, and the exemption is claimed rather than granted by
omission: only `[?]` is exempt from needing a test that cites it.

## The categories

    what-it-speaks-with   kokoro, a file, a player, the default device, the
                          interpreter kokoro will run under
    one-at-a-time         no overlap, the mechanism, the lock, the queue
    who-is-speaking       the name, and announcing it once
    submission-shape      an array, prepared ahead, spoken in order
    warm                  the backend, and the MCP server
    voice-selection       two routes to one setting, and which is the record
    a-voice-per-name      the shortlist, who gets which voice, and for how long
    saying-it-right       pronunciation substitutions
    putting-it-on-a-machine   what an install may write, what it checks first,
                              and what an uninstall takes back

A suite is not a statement of what code owes. Tests assert what the code does,
so a module with tests and no requirements looks covered and cannot report that
anything is missing. The installer is the worked example: fourteen tests, no
rows, and writing the rows found four obligations nothing tested at all, plus a
test citing a row that does not say what the test asserts.

A category is a subject, not a number range. `FR-7` is the open-question set and
not a seventh subject, and a question closes at the id it already carried,
because closing one is a decision against a row that exists. Its file then moves
into the category its answer belongs to. So `one-at-a-time` holds FR-2.1,
FR-7.2 and FR-7.3.

Nothing is open. All nine of FR-7 are closed, and there is no `open/` category;
an empty directory at a standard path reads as a lost file.

## Retired

An id is never reused. A reader meeting one in an old commit, a note or another
project's document finds where it went instead of finding it attached to
something unrelated.

    FR-2.2   the mechanism is unconstrained
             retired 2026-08-28, absorbed into FR-2.1
             46 rows stand where 47 did

Why it went: it read *Exclusion is held by a mutex, a lock file, or an
equivalent. The mechanism is unconstrained; the property is not.* That is a
licence and not an obligation. There is no implementation that satisfies
FR-2.1 and violates it, and "or an equivalent" closes off the attempt by
construction, so no change to the software could ever fail it.

It was written at commissioning, when it was still open whether skid would be
one process or several, to stop FR-2.1 being read as mandating a mechanism. That
question is settled: one service, and a `threading.Lock` in `player.py`.

It was retired under the rule that a decision is a requirement until it isn't,
because it never constrained anything, not because it expired. FR-7.6 is the
contrast: it records a decision that does constrain, rests on a measurement
about kokoro, and is tested by asserting that premise still holds. FR-2.2 rests
on no measurement, so nothing external could ever retire it and nothing internal
could ever violate it.

Its guidance survives as prose in FR-2.1: what holds the lock is a separate
question from what the lock covers.

`docs/TEST_PLAN.md` reached the same conclusion independently, recording FR-2.2
as "constrains nothing and is discharged by FR-2.1 passing with whatever".
