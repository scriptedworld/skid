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

## State

Nothing is built. `REQUIREMENTS.md` carries what must be true, stated first-hand
on 2026-08-27, with nine open questions recorded rather than guessed.

First pass is Linux only, Python, and a standard uv project.
