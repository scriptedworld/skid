# FR-3.5, the greeting is decided at playback

| ID | Requirement | |
|---|---|---|
| FR-3.5 | Whether a submission is prefixed is decided **when it reaches the front of the queue to be played**, not when it is queued. | [D] |

Derived from FR-3.2, FR-7.2, FR-7.3 and FR-7.4, each of which is satisfied by a
design that gets this wrong.

FR-7.4 measures the window from the end of the last clip spoken for that name,
and says why: an unbounded queue can put minutes between submission and speech,
and measuring from submission would announce a name whose voice was still
audibly in the room.

**Moving which clock is read does not help if it is read at the wrong time.** A
name that submits a long array and then one more message is quiet at the moment
the second is queued, and still talking when it plays.

This is the same shape as FR-4.4: every row satisfied, the audible behaviour
wrong, and the gap living between the rows rather than in any of them.

**It constrains FR-4.2**, because the prefix is text kokoro has to render, so
the first clip of a submission cannot be prepared ahead until the decision is
made. `docs/SPEC.md` resolves that by generating the greeting as a clip of its
own, which keeps the lookahead unbounded and makes the decision a choice about
whether to play a clip that already exists.

Raised by the spec review at `fd42bdf`.
