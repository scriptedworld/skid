# skid

skid gives a program a voice. It takes text over a unix socket and speaks it
aloud on the machine's own speakers, so you can hear what something is doing
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
in a run announcing itself. Where you list voices in the config, each name is
also assigned one of its own and keeps it while it goes on talking.

A long-running process holds the model in memory, so speaking does not wait for
kokoro to load.

## The queue

Several callers share one set of speakers, so submissions are queued rather than
mixed. A submission is spoken to completion before the next one starts, in the
order you submitted rather than the order clips finished generating, so two
callers cannot interleave into one stream you have to untangle.

Speaking returns when the work is queued, not when it has been heard, which is
the reason the queue exists at all. The queue is a directory on disk, so what
was accepted and not yet started survives the service restarting, and a
submission that has waited more than five minutes is discarded rather than
spoken late. `docs/SPEC.md` has the rest.

## Talking to it

Three ways in, all reaching the same service over the same socket:

    speak(name, messages)                 the MCP tool, from an agent
    skid-say build "the tests passed"     from a shell, no MCP client needed
    an HTTP POST to /speak                from anything that can reach a socket

There are six tools, one HTTP route each: speaking, the queue status, setting
the voice, and adding, removing and listing pronunciation substitutions.
`docs/SPEC.md` names the routes and their shapes.

The HTTP route needs nothing installed:

    curl --unix-socket $XDG_RUNTIME_DIR/skid/skid.sock \
         -H 'Content-Type: application/json' \
         -d '{"name":"build","messages":["hello"]}' http://localhost/speak

`skid-say` runs and exits, holding no state, so it cannot fall out of step with
the service behind it. It also takes `--status` and `--voice`.

kokoro mispronounces some words. A substitution in the config corrects one for
every caller at once, applied on the way to the engine only, so neither what you
submitted nor what the log records is altered. `docs/config.sample.yaml` is the
whole file with every setting explained.

## What it deliberately does not do

It never opens an audio device. Generating a file and running a player is the
whole output path, which leaves device selection, mixing and volume where the
operating system already handles them. The failure modes are a missing player
and a bad file rather than an audio stack.

It never overlaps clips. One is audible at a time, held by a lock, because two
callers speaking over each other is worse than either waiting.

It is not a network service. The socket is owner-only, mode 0600, and there is
no port to bind. See `SECURITY.md`.

## What is not ready

There has been no release and no tag. skid runs as a service and is used daily,
and these are the things a stranger would otherwise find out by running it:

- wrench is fetched from git rather than a registry, so an install reaches the
  network for it and a pinned release is not available to pin to;
- `set_voice` accepts any of kokoro's 54 voice names, including the thirteen
  Japanese and Chinese ones a standard install cannot render, writes it to the
  config, and then everything fails quietly until you edit the file back by
  hand;
- Linux only, and the pronunciation substitutions have been designed rather
  than worn in;
- the MCP path is going to change: a forwarder that holds no connection to the
  backend is planned but not built, so build against the current one knowing
  that.

`NEXT_STEPS.md` has the rest, including what a green test run does not prove.

## What it needs, and what it costs

Linux with a systemd user session, Python 3.12, `uv`, and a player on PATH.
`paplay` is the default and works on PulseAudio and PipeWire alike; any command
taking a file argument can be named in the config instead.

Python 3.12 exactly, because kokoro declares `<3.13`. `uv tool install` reads
that and builds the tool environment on 3.12 whatever your default interpreter
is, so it costs you nothing to arrange.

It is a machine learning stack and it is not small. The installed tool
environment is about 5 GB, mostly torch. The warm service holds a few gigabytes
resident, since that is what a loaded model costs, and the first run downloads
about 340 MB of kokoro weights into `~/.cache/huggingface`. The first call after
a start waits for the model to load; every call after that does not.

    du -sh ~/.local/share/uv/tools/skid

## Installing

**No sibling checkout is needed.** skid uses wrench for config and spool
handling, and since wrench is not on a package registry `pyproject.toml` names it
by git URL, which uv fetches like any other dependency. To develop against a
local wrench instead, override the source rather than editing that line —
`pyproject.toml` says how.

The install is one command from a checkout:

    python3 src/skid/install.py

That installs skid as a uv tool, puts the two systemd user units in place,
enables the socket and registers skid with an MCP client. Everything it writes
is inside your home, it checks the units and the tools before writing anything,
and it names each file it changed. `--dry-run` prints the commands without
running them and `--uninstall` reverses all of it.

The service is socket-activated, so the first connection starts it. An MCP
client picks a server up when it starts, so `speak` appears in sessions started
after the install and not in one already running. `docs/PROJECT.md` covers
reinstalling and deploying a change.

## The documentation

    docs/REQUIREMENTS/   what must be true, one file per requirement, each
                         naming the test that discharges it
    docs/SPEC.md         how skid is arranged, and why one service
    docs/TEST_PLAN.md    one test named per requirement
    docs/config.sample.yaml   every setting with its default and its reasons
    docs/running-in-a-container.md  Debian and container prerequisites, and the
                         audio problem a container has and a host does not
    docs/DECISIONS/      one file per decision
    docs/LESSONS/        what went wrong once, written up so it does not twice
    CONTRIBUTING.md      how to run the suite and what a change has to carry
    SECURITY.md          the trust boundary, and how to report a hole

`docs/PROJECT.md` is what to read before changing anything here.

## Licence

Apache 2.0. `LICENSE` carries the terms and `NOTICE` the attribution.
