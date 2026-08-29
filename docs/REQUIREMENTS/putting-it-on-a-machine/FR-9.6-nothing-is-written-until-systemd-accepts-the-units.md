# FR-9.6, nothing is written until systemd accepts the units

| ID | Requirement | |
|---|---|---|
| FR-9.6 | Both unit files are **checked by systemd itself** before either is installed. | [A] |

A unit file is data and a typo in one surfaces the day it is loaded, long after
the install said it worked. Checking first finds it on the machine being
installed to, which a test on one developer's machine does not.

Read the output rather than the status: `systemd-analyze verify` exits 0 while
ignoring a key it does not recognise, and `StartLimit*` in `[Service]` is one.
