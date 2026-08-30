---
name: Bug report
about: Something skid did, or did not say
labels: bug
---

## What happened

What you asked skid to say, and what you heard or did not hear.

## What you expected

## How to reproduce it

The `speak` call, the `skid-say` line or the `curl` command, and whether it
happens every time.

## The four commands that answer most of this

    skid-say --status
    systemctl --user status skid.service
    journalctl --user -u skid.service -n 50 --no-pager
    git rev-parse --short HEAD

Paste the output. skid carries no version string and there are no releases yet,
so the commit is what identifies your build.

## Your machine

- Distribution and version:
- Audio: PulseAudio or PipeWire, and which player is configured (`paplay` unless
  you changed it):
- Python that built the tool environment
  (`~/.local/share/uv/tools/skid/bin/python -V`):

## If it is about pronunciation

The exact text submitted, what you heard, and your `substitution` entries from
`~/.config/skid/config.yaml`. Substitutions are tried in file order, so include
the order.

## If nothing is audible at all

Confirm the player works on its own before filing, since skid runs it and does
not open a device itself:

    paplay /usr/share/sounds/alsa/Front_Center.wav
