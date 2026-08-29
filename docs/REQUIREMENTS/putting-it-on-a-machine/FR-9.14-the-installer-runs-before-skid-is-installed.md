# FR-9.14, the installer runs before skid is installed

| ID | Requirement | |
|---|---|---|
| FR-9.14 | The installer runs on a machine that has **never had skid installed**, so it imports only the standard library and nothing from its own package. | [A] |

The first step of the plan is what puts `skid` on PATH, so an installer
importing from its own package could not run on the machine it exists for.
Discharged by reading the import set, like FR-1.6 and FR-7.6, because importing
the module to check would pass on a developer's machine either way.
