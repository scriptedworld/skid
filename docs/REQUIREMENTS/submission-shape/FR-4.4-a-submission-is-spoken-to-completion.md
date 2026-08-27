# FR-4.4, a submission is spoken to completion

| ID | Requirement | |
|---|---|---|
| FR-4.4 | A submission is spoken to completion before the next one begins. Two submissions never interleave. | [D] |

Derived from FR-4.3 and FR-7.2, and stated separately because neither implies
it. FR-4.3 keeps one array in its own order and says nothing about a second
array; FR-7.2 makes an arrival queue and says nothing about where in the queue
its messages sit.

Without this row, "queued" is compatible with taking one message from each
waiting submission in turn, which preserves both orders and makes a listener
follow two speakers at once.

Raised by `docs/SPEC.md`, which asserted it as a design choice before any
requirement said it.
