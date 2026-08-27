# FR-7.5, paplay by default, and a configurable command

| ID | Requirement | |
|---|---|---|
| FR-7.5 | The default player is **`paplay`**. A user-defined player is declared as a **command line with the file path substituted into it**. | [A] |

Settled 2026-08-27, at the id the open question carried. It gives FR-1.3 its
player and FR-1.6 its one platform-specific value.

`paplay` follows the default output device, which is what FR-1.4 requires, and
it is present on a PulseAudio machine and a PipeWire one alike. Measured
2026-08-27: `paplay` is `/usr/bin/pacat`, and the server here is PulseAudio
15.0.0 on PipeWire 1.4.2.

A command line rather than a name from a fixed list, so a player nobody
anticipated needs no change here to work.

`aplay` is present and talks to ALSA rather than following the default sink, so
configuring it would not satisfy FR-1.4. That is the user's choice to make and
skid does not prevent it.
