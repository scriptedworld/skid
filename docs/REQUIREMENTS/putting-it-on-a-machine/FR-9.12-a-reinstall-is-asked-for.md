# FR-9.12, a reinstall is asked for

| ID | Requirement | |
|---|---|---|
| FR-9.12 | A reinstall is **confirmed by the person running it**. Where there is no terminal to ask on, the answer is no. | [A] |

It replaces files the user owns and re-points their registration. With no
terminal there is no answer to read, and guessing yes on behalf of a script is
how an installer surprises somebody; `--yes` is how a script says yes.
