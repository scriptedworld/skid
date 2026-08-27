# FR-7.2, an arrival queues

| ID | Requirement | |
|---|---|---|
| FR-7.2 | A submission arriving while another is playing **queues**, unbounded. Nothing is rejected and nothing already queued is replaced. | [A] |

Settled 2026-08-27, at the id the open question carried.

Nothing submitted is lost, which is the property chosen over bounded latency.
A caller behind a long array waits as long as that array takes, and has no way
to know in advance how long that is.

FR-4.3 keeps order within one submission. This keeps order between them.
