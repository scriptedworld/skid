# FR-9.8, nothing an install does opens the socket

| ID | Requirement | |
|---|---|---|
| FR-9.8 | No part of installing, verifying or detecting an existing install **opens the socket**. | [A/D] |

Derived from FR-9.7. Verifying asks systemd, with `is-enabled` and `is-active`.
Detecting asks the filesystem, because `claude mcp get` and `claude mcp list`
health-check the server and that opens the socket. An installer must not load a
model to find out whether it has run before.
