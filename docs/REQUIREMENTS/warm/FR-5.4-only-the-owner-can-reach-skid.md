# FR-5.4, only the owner can reach skid

| ID | Requirement | |
|---|---|---|
| FR-5.4 | Only the user skid runs as can reach it. Another local user cannot make it speak, read its substitutions, or change its settings. | [D] |

Derived from FR-6.1, FR-8.1 and FR-7.1. The MCP tools change a persistent
record and drive an output device, so reaching them is not a read-only
capability: it is making the machine talk and rewriting a file the owner keeps.

**It is stated because the transport decides it, and the transport changed.**
Over a localhost TCP port every process on the machine can connect, which is the
usual shape for an HTTP service and the wrong one here. Over a unix socket with
mode 0600 the check is the filesystem's and happens before skid runs.

A Linux abstract socket fails this row for the same reason a port does: no path,
so no owner and no mode. That is why it was rejected despite having no
staleness, and `docs/SPEC.md` carries the measurement.

**Not a claim about a hostile machine.** It is the difference between a service
that is private by construction and one that is private because nothing else
happened to connect.
