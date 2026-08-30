# FR-1.4, playback uses the default output device

| ID | Requirement | |
|---|---|---|
| FR-1.4 | Playback uses **the default output device**, whatever that currently is. skid does not select one. | [A] |

Whatever the default is at the moment a clip plays, including a default that
changed since the clip was generated. Following it is the requirement; caching
it is not.

`pactl get-default-sink` is what the player follows, under PulseAudio on
PipeWire. The sink it names changes as devices come and go, which is the reason
this row exists and the reason no sink name is recorded here.
