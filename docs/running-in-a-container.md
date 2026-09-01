# Running skid in a container

skid is a good fit for a container everywhere except the last inch: it has to
reach a speaker, and a container has none. That is the whole difficulty and
everything below is about it.

**This is guidance, not a shipped image.** The Containerfile here is short
enough to read and has not been through the gate. Treat it as a starting point.

## What it needs

    Python 3.12          kokoro declares <3.13
    uv                   to install from the git source
    a player on PATH     `paplay` by default, any command taking a file
    about 5 GB           the tool environment, mostly torch
    about 340 MB more    kokoro's weights, on first run

No systemd. The service binds its own socket when `LISTEN_FDS` is unset, so
socket activation is an option on a host and not a requirement.

## The audio problem, and the two honest answers

A container has no sound device. Passing one through is possible and is more
trouble than it is worth here, because the host already has a sound server.

**Reach the host's sound server.** PulseAudio and PipeWire both expose a unix
socket, and `paplay` will use it:

    -v $XDG_RUNTIME_DIR/pulse:/run/pulse:ro
    -e PULSE_SERVER=unix:/run/pulse/native

That keeps device selection, mixing and volume on the host, which is what skid
does on a host anyway: it never opens an audio device itself.

**Or generate in the container and play outside it.** Set `player` in the config
to a command that hands the file to the host. This is the better shape if the
container is on another machine, and it makes skid a generation service with
playback somebody else's problem.

## A Containerfile to start from

    FROM debian:bookworm-slim

    RUN apt-get update && apt-get install -y --no-install-recommends \
            python3 ca-certificates curl pulseaudio-utils git \
        && rm -rf /var/lib/apt/lists/*

    RUN curl -LsSf https://astral.sh/uv/install.sh | sh
    ENV PATH="/root/.local/bin:${PATH}"

    RUN uv tool install --python 3.12 \
            git+https://github.com/scriptedworld/skid.git

    ENV XDG_RUNTIME_DIR=/run/skid
    RUN mkdir -p /run/skid && chmod 700 /run/skid

    CMD ["skid"]

`uv` fetches Python 3.12 itself, so the base image's Python version does not
have to match.

## Running it

    podman run --rm \
      -v $XDG_RUNTIME_DIR/pulse:/run/pulse:ro \
      -e PULSE_SERVER=unix:/run/pulse/native \
      -v skid-cache:/root/.cache/huggingface \
      -v $XDG_RUNTIME_DIR/skid:/run/skid \
      skid

**Mount the model cache.** Without `skid-cache`, every start downloads the
weights again.

**Mount the runtime directory** if a client outside the container needs the
socket. skid creates it mode 0700 and keeps it that way, which is the trust
boundary `SECURITY.md` describes; a bind mount does not change who can open it,
but it does put it where another user's container could see the path exists.

## What to check before believing it works

The failure this arrangement produces is silence, and skid's own known defect is
that a submission which cannot render still reports as queued. So test the
audible path rather than the exit status:

    skid-say container "hello from the container"

and hear it. A clean exit is not evidence.

## Debian without a container

The same prerequisites, minus the image:

    apt-get install -y python3 curl ca-certificates pulseaudio-utils git
    curl -LsSf https://astral.sh/uv/install.sh | sh
    uv tool install --python 3.12 git+https://github.com/scriptedworld/skid.git

`python3 src/skid/install.py` from a clone does more than that: it installs the
systemd user units, enables the socket and registers the MCP server. That path
wants a systemd user session, which a minimal Debian install may not have
running.

## What is verified here and what is not

**Verified**, on the machine this was written on:

    the sound server exposes a socket    pipewire-pulse, $XDG_RUNTIME_DIR/pulse/native
    skid runs without systemd            it binds its own socket when LISTEN_FDS is unset
    the git source installs              uv resolves wrench from GitHub, 174 tests pass

**Not verified.** The image has not been built, no clip has been played from
inside a container, and none of the Debian steps has been run on a clean
install. A QEMU install test is what would settle the second half, and building
the image once would settle the first.

Both are worth doing before anyone relies on this page, and the reason it says
so is that a setup document nobody has run is the failure this project already
records elsewhere.
