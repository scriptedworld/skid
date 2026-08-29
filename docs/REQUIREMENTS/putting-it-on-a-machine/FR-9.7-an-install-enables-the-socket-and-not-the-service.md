# FR-9.7, an install enables the socket and not the service

| ID | Requirement | |
|---|---|---|
| FR-9.7 | An install **enables and starts the socket**, and does not start the service. | [A] |

The first connection starts the service, so starting it during an install would
load the model to prove that two files copied. Enabling is the part that must
happen: it is what brings skid back after a reboot.
