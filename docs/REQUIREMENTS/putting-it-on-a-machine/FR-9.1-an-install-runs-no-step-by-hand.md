# FR-9.1, an install runs no step by hand

| ID | Requirement | |
|---|---|---|
| FR-9.1 | A checkout becomes a working service by **declared steps alone**. No step is performed by a person following instructions. | [A] |

skid worked on one machine and was reproducible on none, because every step was
run by hand and the record of them was prose. Prose cannot be asserted against,
so the installer and the document describing it drifted with nothing to notice.

The steps being declared is what lets FR-9.2 show them, FR-9.5 and FR-9.6 refuse
before running any, and a test hold the sequence without touching the machine.
