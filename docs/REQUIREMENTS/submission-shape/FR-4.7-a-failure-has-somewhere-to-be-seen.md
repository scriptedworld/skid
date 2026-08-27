# FR-4.7, a failure has somewhere to be seen

| ID | Requirement | |
|---|---|---|
| FR-4.7 | A failure is recorded where both a person and a caller can find it: a log a person can read, and a tool a caller can ask. | [D] |

Derived from FR-4.6, which requires a failure to be **reported** and does not
say to whom. Without a destination the word discharges nothing, and FR-4.5 has
already closed the obvious channel by returning when the work was queued rather
than when it was heard.

**The failure this closes is the one FR-4.6 was written for.** If the player
disappears, every clip fails, every caller still receives success, and the
machine is silent with nothing anywhere saying why. A report with no destination
produces exactly the outcome of no report at all.

Both halves are needed. A person debugging silence reads a log. An agent cannot
read a log as part of its own work, so it needs to be able to ask.

Raised by the spec review at `fd42bdf`.
