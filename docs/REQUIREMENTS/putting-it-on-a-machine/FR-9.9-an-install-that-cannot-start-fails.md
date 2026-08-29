# FR-9.9, an install that cannot start fails

| ID | Requirement | |
|---|---|---|
| FR-9.9 | An install that has produced a service which **cannot start** reports failure, rather than reporting success and leaving it to the first `speak`. | [A] |

A passing socket does not answer this. The socket is systemd's and comes up
whether or not the tool environment behind it can run.

**The case this is written from cost 76 restarts.** kokoro downloads
`en_core_web_sm` at start-up when it is absent, using pip or uv, and under
systemd neither is on PATH. The service failed, systemd restarted it, and each
attempt outlived the default start limit's window, so nothing latched and
nothing said why. The model is a declared dependency now, and this row is what
notices when an install has nonetheless produced an environment without it.

**The check runs the tool's own interpreter**, because it is a question about
the installed environment rather than about the checkout. The two are different
environments and only one of them runs the service.
