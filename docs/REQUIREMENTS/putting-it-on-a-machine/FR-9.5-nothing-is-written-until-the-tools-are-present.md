# FR-9.5, nothing is written until the tools are present

| ID | Requirement | |
|---|---|---|
| FR-9.5 | An install checks that **every command its plan runs is on PATH** before it writes anything, and stops naming what is missing. | [A] |

Half an install is worse than none. A machine without `uv` that has already had
its unit files copied looks installed to anyone reading `~/.config/systemd/user`
and cannot start.

The pair with FR-9.6 is the shape rather than the specific check: **everything
that can be known before mutating is known before mutating.** Both refuse in the
one state where refusing is free.
