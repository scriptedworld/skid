# FR-1.3, a subprocess plays the file

| ID | Requirement | |
|---|---|---|
| FR-1.3 | The file is played by running the operating system's audio player, or a user-defined one, as a **subprocess**. | [A] |

FR-7.5 names the player: `paplay` by default, and a user-defined one declared as
a command line.

On this machine `command -v` finds `paplay` (`/usr/bin/pacat`), `aplay` and
`pw-play` (`/usr/bin/pw-cat`), and does not find `ffplay`, `mpv` or `espeak-ng`.
