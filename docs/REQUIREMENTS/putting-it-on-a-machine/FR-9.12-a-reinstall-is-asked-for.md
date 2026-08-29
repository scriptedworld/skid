# FR-9.12, a reinstall is asked for

| ID | Requirement | |
|---|---|---|
| FR-9.12 | A reinstall is **confirmed by the person running it**. Where there is no terminal to ask on, the answer is no. | [A] |

A reinstall replaces files the user owns and re-points their MCP registration,
so it is asked for rather than assumed.

**No terminal is no, and this is the clause worth stating.** Guessing yes on
behalf of a script is how an installer surprises somebody who piped it into a
shell. A script that wants a reinstall says so with `--yes`, which is a
statement of intent rather than an absence of objection.

What is already present is shown before the question is put, so the answer is
given against the list rather than against the word "reinstall".
