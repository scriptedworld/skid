# FR-7.2, an arrival queues

| ID | Requirement | |
|---|---|---|
| FR-7.2 | A submission arriving while another is playing **queues**, unbounded. Nothing is rejected and nothing already queued is replaced. | [A] |

Settled at the id the open question carried.

Nothing submitted is lost, which is the property chosen over bounded latency.
A caller behind a long array waits as long as that array takes, and has no way
to know in advance how long that is.

FR-4.3 keeps order within one submission. This keeps order between them.

Depth is unbounded; age is not. FR-4.9 discards a submission older than a
configured five minutes. That is a cap on a row that promises none, so it is
recorded here as well as in the row that adds it.

FR-4.8 makes the queue durable, so a backlog can outlive the process that filled
it and be old in a way an in-memory queue could not be. "Nothing is rejected" still holds at the door:
nothing is refused on arrival, and what is discarded is discarded on the way out
with a line in the log.
