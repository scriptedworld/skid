# FR-9.3, nothing is written outside the user's home

| ID | Requirement | |
|---|---|---|
| FR-9.3 | Every path an install writes is **inside the user's own home**, and no step requires root. | [A] |

Needing root makes an installer something to read before running, and few do. It
also bounds FR-9.13: everything skid installs can be removed by whoever
installed it. Every destination is a parameter, so the plan can be pointed at a
temporary directory and asserted.
