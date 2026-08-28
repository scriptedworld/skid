# FR-7.2, an arrival queues

| ID | Requirement | |
|---|---|---|
| FR-7.2 | A submission arriving while another is playing **queues**, unbounded. Nothing is rejected and nothing already queued is replaced. | [A] |

Settled 2026-08-27, at the id the open question carried.

Nothing submitted is lost, which is the property chosen over bounded latency.
A caller behind a long array waits as long as that array takes, and has no way
to know in advance how long that is.

FR-4.3 keeps order within one submission. This keeps order between them.

**Amended 2026-08-28: depth is unbounded, age is not.** FR-4.9 discards a
submission older than a configured five minutes. That is a cap and this row said
there would be none, so it is recorded here rather than only in the row that
adds it.

The trade did not change so much as get sharper. FR-4.8 made the queue durable,
so a backlog can now outlive the process that filled it and be old in a way an
in-memory queue could not be. "Nothing is rejected" still holds at the door:
nothing is refused on arrival, and what is discarded is discarded on the way out
with a line in the log.
