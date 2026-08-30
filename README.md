# skid

skid gives a program a voice. It takes a line of text over a socket and speaks
it aloud on the machine's own speakers, so you can hear what something is doing
instead of watching a log for it.

It was built for coding agents that run for hours without being watched. Several
of them share one skid, each with a name, and it keeps them from talking over
each other.

Named for Skidd McMarx, who is loud, has a voice everyone recognises, and does
not do anything else.

## How it works

Text arrives as an array of messages. kokoro turns each into an audio file, and
a subprocess plays them through the operating system's own player on the default
output device, one at a time. skid never opens an audio device itself.

Every caller gives a name. The first thing heard from a name in a while is
prefixed `Hi, <name> here.`, so you know who is speaking without every message
in a run announcing itself.

A long-running process holds the model in memory, so speaking does not wait for
kokoro to load.

## The queue

Several callers share one set of speakers, so submissions are queued rather than
mixed. Four things are guaranteed, and together they are what makes the output
listenable.

A submission is spoken to completion before the next one starts, so two callers
cannot interleave into one stream you have to untangle. Submit three messages
and all three are heard, in order, before another name is heard at all.

Order is the order you submitted in, not the order clips finished generating.
Generation runs ahead of the speaker while a clip plays, so a long array is
prepared during playback rather than after it.

Speaking returns when the work is queued, not when it has been heard. The caller
carries on rather than blocking behind its own audio, which is the reason the
queue exists at all.

The queue is on disk, so it survives the service restarting. A submission is
written to `$XDG_RUNTIME_DIR/skid/spool` before the call returns, and that write
is the promise: what was accepted and not yet started is still there afterwards.

Two smaller behaviours fall out of it. A name quiet for thirty seconds is
announced before its next message, timed from the end of the last clip spoken
for that name and decided as the clip is about to play, because a queue can put
minutes between the two. A submission that has waited more than five minutes is
discarded with a line in the log, since a status worth hearing when it was sent
is usually not worth hearing later. Downtime counts toward that. Both numbers
are configurable.

## Talking to it

Three ways in, all reaching the same service over the same socket:

    speak(name, messages)                 the MCP tool, from an agent
    skid-say build "the tests passed"     from a shell, no MCP client needed
    an HTTP POST to /speak                from anything that can reach a socket

The third needs nothing installed:

    curl --unix-socket $XDG_RUNTIME_DIR/skid/skid.sock \
         -H 'Content-Type: application/json' \
         -d '{"name":"build","messages":["hello"]}' http://localhost/speak

`skid-say` runs and exits, holding no state, so it cannot fall out of step with
the service behind it. It also takes `--status` for the queue depth and recent
failures, and `--voice` to change the voice and keep it.

kokoro mispronounces some words. A substitution in the config file corrects one
for every caller at once, applied on the way to the engine only, so neither what
you submitted nor what the log records is altered. `docs/config.sample.yaml` is
the whole file with every setting explained.

## What it deliberately does not do

It never opens an audio device. Generating a file and running a player is the
whole output path, which leaves device selection, mixing and volume where the
operating system already handles them. The failure modes are a missing player
and a bad file rather than an audio stack.

It never overlaps clips. One is audible at a time, held by a lock, because two
callers speaking over each other is worse than either waiting.

## Installing

Linux, with `uv`, `systemctl`, `systemd-analyze`, `install` and `claude` on
PATH. From a checkout:

    python3 src/skid/install.py

That installs skid as a uv tool, puts the two systemd user units in place,
enables the socket and registers skid with the MCP client. Everything it writes
is inside your home, it checks the units and the tools before writing anything,
and it names each file when it finishes. `--dry-run` prints the commands without
running them and `--uninstall` reverses all of it.

Run it where skid is already installed and it shows what is there and asks.
Answering yes re-points the MCP registration at this checkout, because
`claude mcp add` refuses a name that is taken and will not update it, so the
registration is removed and added rather than left as it is. `--yes` answers for
a script, and no terminal to ask on is taken as no.

It enables the socket without starting the service. Socket activation means the
first connection does that, and starting it early would load a model to prove
that two files were copied.

A session already running cannot call skid. An MCP client picks a server up when
it starts, so `speak` appears in sessions started after the install.

## State

It works and runs as a service. `docs/REQUIREMENTS/` holds what must be true,
one file per requirement, each naming the test that discharges it.

Linux only for now, Python 3.12 exactly, and an ordinary uv project.
`docs/PROJECT.md` is what to read before changing anything here.
