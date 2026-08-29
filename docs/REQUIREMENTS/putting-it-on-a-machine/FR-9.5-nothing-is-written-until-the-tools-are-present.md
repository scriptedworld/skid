# FR-9.5, nothing is written until the tools are present

| ID | Requirement | |
|---|---|---|
| FR-9.5 | An install checks that **every command its plan runs is on PATH** before writing anything, and stops naming what is missing. | [A] |

Half an install is worse than none: a machine without `uv` whose units are
already copied looks installed and cannot start. With FR-9.6, everything
knowable before mutating is known before mutating.
