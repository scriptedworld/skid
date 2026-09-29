# FR-9.1, an install runs no step by hand

| ID | Requirement | |
|---|---|---|
| FR-9.1 | A checkout becomes a working service by **declared steps alone**. No step is performed by a person following instructions. | [A] |

Steps written as prose cannot be asserted against, so a service installed by
following them works on one machine and is reproducible on none. Declaring them
is what lets FR-9.2 show them and FR-9.5 and FR-9.6 refuse before any of them
runs.
