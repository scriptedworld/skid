# FR-9.6, nothing is written until systemd accepts the units

| ID | Requirement | |
|---|---|---|
| FR-9.6 | Both unit files are **checked by systemd itself** before either is installed. | [A] |

A unit file is data, and a typo in one is not found until the day it is loaded,
which is long after the install said it worked. Checking them first finds it
now, and finds it **on the machine being installed to** rather than only on the
one the tests happened to run on.

That last clause is the whole reason the check is a step in the plan rather than
a test. As a test it ran once, on one machine, and told nobody anything about
theirs.

**Reading the output is required, not the exit status.** `systemd-analyze
verify` exits 0 while ignoring a key it does not recognise: `StartLimit*` moved
to `[Unit]` in v229 and is silently dropped in `[Service]`. See hard rule 6.
