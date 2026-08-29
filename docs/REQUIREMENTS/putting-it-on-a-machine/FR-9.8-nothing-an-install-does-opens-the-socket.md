# FR-9.8, nothing an install does opens the socket

| ID | Requirement | |
|---|---|---|
| FR-9.8 | No part of installing, verifying or detecting an existing install **opens the socket**. | [A/D] |

Derived from FR-9.7 and stated separately because it binds three places that
would each reach for the socket independently, and one of them is not obvious.

**Verifying.** `is-enabled` and `is-active` ask systemd. Anything that connected
would answer a question about a socket by loading a model.

**Detecting.** `claude mcp get` and `claude mcp list` both health-check the
server they are asked about, and a health check on skid opens the socket. So
"is skid already installed" is asked of the filesystem alone. This is the one
that is easy to get wrong, because the command reads like a query.

An installer must not load a model to find out whether it has run before.
