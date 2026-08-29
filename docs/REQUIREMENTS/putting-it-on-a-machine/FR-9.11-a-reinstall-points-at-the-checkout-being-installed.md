# FR-9.11, a reinstall points at the checkout being installed

| ID | Requirement | |
|---|---|---|
| FR-9.11 | After a reinstall the MCP registration names **the checkout being installed**, not whichever one was installed first. | [A] |

Measured 2026-08-28: `claude mcp add` refuses a name that is taken and does not
update it. So an entry pointing at an old or moved checkout survives every re-run
that only adds, and the install reports success while the client goes on
launching something else.

A reinstall therefore removes the registration and adds it, and the removal
tolerates there being nothing to remove, which is FR-9.10.

**A first install does not remove.** The two plans differ by exactly that step,
so a fresh machine is not asked to unregister something it never had.
