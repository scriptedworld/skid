# FR-7.5, which player

| ID | Question | |
|---|---|---|
| FR-7.5 | Which player, and how is a user-defined one declared? `paplay` and `aplay` are present here; `ffplay`, `mpv` and `paplay`'s usual companions are not. | [?] |

Open. Carries no test until it closes.

FACT 2026-08-27, `command -v`, correcting the row's parenthetical: `paplay`,
`aplay` and `pw-play` are present. `paplay` is `pacat` and `pw-play` is
`pw-cat`. The server is PulseAudio 15.0.0 on PipeWire 1.4.2, so `paplay` reaches
PipeWire through the compatibility layer and `pw-play` reaches it directly.

`clank/tasks/skid/playback/10-which-player-and-how-one-is-declared.questions`
