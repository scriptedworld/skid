# FR-4.12, every played submission is logged

| ID | Requirement | |
|---|---|---|
| FR-4.12 | When a submission has finished playing, the log records the name, the work if any, and how many of its messages were played. | [A] |

Derived from the same request as FR-4.11. Accepted and played are separate
lines because they fail separately: a submission can be accepted and then
expire in the queue, FR-4.9, or have every clip fail, FR-4.6. A count of
played messages below the count accepted is the gap a person reading the log
is looking for.

Played means the player ran and exited cleanly. Whether anybody heard it is
still not something skid can know, `docs/PROJECT.md` says why.
