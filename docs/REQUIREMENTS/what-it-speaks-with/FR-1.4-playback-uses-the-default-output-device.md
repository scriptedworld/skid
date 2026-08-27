# FR-1.4, playback uses the default output device

| ID | Requirement | |
|---|---|---|
| FR-1.4 | Playback uses **the default output device**, whatever that currently is. skid does not select one. | [A] |

Whatever the default is at the moment a clip plays, including a default that
changed since the clip was generated. Following it is the requirement; caching
it is not.

FACT 2026-08-27, `pactl get-default-sink`:
`alsa_output.pci-0000_00_1f.3.analog-stereo`, under PulseAudio on PipeWire 1.4.2.
