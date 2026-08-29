# FR-9.7, an install enables the socket and not the service

| ID | Requirement | |
|---|---|---|
| FR-9.7 | An install **enables and starts the socket**, and does not start the service. | [A] |

Socket activation means the first connection starts the service, so starting it
during an install would load the model to prove that copying two files worked.
That is a minute of nothing, and it makes the install's cost depend on the
model rather than on the work.

Enabling the socket is the part that must happen, because it is what brings skid
back after a reboot.
