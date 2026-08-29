# FR-9.14, the installer runs before skid is installed

| ID | Requirement | |
|---|---|---|
| FR-9.14 | The installer runs on a machine that has **never had skid installed**, so it imports only the standard library and nothing from its own package. | [A] |

The first step of the plan is what puts `skid` on PATH. An installer that needed
skid installed could not perform it, and an installer that imported `skid.config`
to find a path would fail on exactly the machine it exists for.

    python3 src/skid/install.py    from a fresh checkout
    skid-install                   afterwards, by name

Both reach the same file. The first is the one that works on a machine that has
never seen skid, and it is the reason this row constrains imports rather than
behaviour.

**Discharged by reading the declaration**, like FR-1.6 and FR-7.6. An import set
has no behaviour to exercise, and a test that imported the module to check what
it imports would pass on a developer's machine either way.
