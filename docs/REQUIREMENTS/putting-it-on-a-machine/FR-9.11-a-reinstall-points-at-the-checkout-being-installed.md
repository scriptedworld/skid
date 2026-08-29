# FR-9.11, a reinstall points at the checkout being installed

| ID | Requirement | |
|---|---|---|
| FR-9.11 | After a reinstall the MCP registration names **the checkout being installed**, not whichever one was installed first. | [A] |

`claude mcp add` refuses a name that is taken and does not update it, so an
entry pointing at a moved checkout survives every re-run that only adds, and the
install reports success while the client launches something else. A reinstall
removes then adds; a first install does not remove.
