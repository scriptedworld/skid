# skid

Voice output for the agents. An MCP server that takes text and speaks it.

Named for Skidd McMarx, who is loud, has a voice everyone recognises, and does
not do anything else.

## What it is

Text arrives as an array. kokoro turns it into audio files. A subprocess plays
them through the operating system's own player on the default output device,
one at a time, and skid never touches an audio device itself.

Each caller gives a name. The first thing heard from a name in a while is
prefixed `Hi, [name] here.`, so a listener knows who is talking without every
message in a chain announcing itself.

A backend process keeps the model warm, so a message does not wait on start-up
before it is spoken.

## What it deliberately does not do

**No direct device access.** Generating a file and running a player is the whole
output path. That keeps device selection, mixing and volume where the operating
system already handles them, and it means the failure modes are a missing player
and a bad file rather than an audio stack.

**No overlap.** One clip is audible at a time, held by a lock. Two agents
speaking over each other is worse than either waiting.

## Installing

One command, from a checkout, on a Linux machine with `uv`, `systemctl` and
`claude` on PATH:

    python3 src/skid/install.py

It installs skid as a uv tool, puts the two systemd user units in place, enables
the socket, and registers skid with the MCP client. Everything it writes is
inside your home and it names each file when it finishes. `--dry-run` prints the
commands without running any of them, and `--uninstall` reverses all of it.

**Run it where skid is already installed and it shows you what is there and
asks.** Answering yes reinstalls, which re-points the MCP registration at this
checkout: `claude mcp add` refuses a name that is taken and will not update it,
so the registration is removed and added rather than left as it is. `--yes`
answers for a script, and no terminal to ask on is taken as no.

It enables the socket but does not start the service, because socket activation
means the first connection does that, and starting it early loads a model to
prove that two files were copied.

**A session already running cannot call skid.** A Claude Code client picks an
MCP server up when it starts, so `speak` appears in sessions started after the
install. That is the session's age rather than anything wrong with the service.

## State

It works and it runs as a service. `docs/REQUIREMENTS/` carries what must be
true, one file per requirement, 47 of them with none left open.

First pass is Linux only, Python 3.12 exactly, and a standard uv project.

`docs/PROJECT.md` is what to read before changing anything here.
