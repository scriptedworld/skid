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

## The queue

Several agents talk to one skid, so submissions are queued rather than mixed.
The queue is what makes the output listenable, and it guarantees four things.

**A submission is spoken to completion before the next one starts.** Two
sessions cannot interleave into one stream a listener has to untangle. Submit
three messages and all three are heard, in order, before another name is heard
at all.

**Order is the order you submitted in**, not the order clips happened to finish
generating. Generation runs ahead of the speaker while a clip plays, so a long
array is prepared during playback rather than after it, and the sequence a
listener hears is still the sequence that was sent.

**Speaking returns when the work is queued, not when it has been heard.** The
caller carries on. An agent is never blocked behind its own audio, which is the
whole reason the queue exists rather than a convenience.

**The queue is on disk, so it survives the service restarting.** A submission is
written to `$XDG_RUNTIME_DIR/skid/spool` before the call returns, and that write
is the promise. What was accepted and not yet started is still there afterwards.

Two smaller behaviours fall out of it and are worth knowing:

A name that has been quiet for **thirty seconds** is announced before its next
message, measured from the end of the last clip spoken for that name, and
decided when the clip is about to play rather than when it was queued. A queue
can put minutes between the two, and deciding early would announce a name whose
voice is still in the room.

A submission that has waited more than **five minutes** is discarded rather than
spoken, with a line in the log. A status that was worth hearing when it was sent
is usually not worth hearing after the moment has passed. Time the service
spends stopped counts toward it. Both numbers are configurable.

## Saying things

Three ways in, all reaching the same service over the same socket:

    speak(name, messages)                the MCP tool, from an agent
    skid-say silo "the gate is green"    from a shell, no MCP client needed
    an HTTP POST to /speak               from anything that can reach a socket

The third needs nothing installed:

    curl --unix-socket $XDG_RUNTIME_DIR/skid/skid.sock \
         -H 'Content-Type: application/json' \
         -d '{"name":"silo","messages":["hello"]}' http://localhost/speak

`skid-say` runs and exits, which makes it the one that always works: it holds no
state, so it cannot be out of date with the service behind it.

Pronunciation is correctable. kokoro says some words wrongly, and a substitution
in the config file fixes it for every caller at once, applied on the way to the
engine only, so nothing you submitted and nothing the log records is changed.
`docs/config.sample.yaml` has the whole file with every setting explained.

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
true, one file per requirement, 48 of them with none left open, and every one
names the test that discharges it.

First pass is Linux only, Python 3.12 exactly, and a standard uv project.

`docs/PROJECT.md` is what to read before changing anything here.
