# FR-9.9, an install that cannot start fails

| ID | Requirement | |
|---|---|---|
| FR-9.9 | An install that has produced a service which **cannot start** reports failure, rather than leaving it to the first `speak`. | [A] |

A passing socket does not answer this: it comes up whether or not the
environment behind it can run. kokoro downloads `en_core_web_sm` at start-up
when it is absent, using pip or uv, and neither is on PATH under systemd, which
cost 76 restarts. The check runs the tool's own interpreter, because it asks
about the installed environment rather than the checkout.
