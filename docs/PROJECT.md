# skid, the project

Voice output for the agents. An MCP server that takes an array of text and
speaks it: kokoro generates an audio file, a subprocess plays it on the default
output device, one clip at a time.

Named for Skidd McMarx, who is loud, has a voice everyone recognises, and does
nothing else.

## What it is for

Hearing which agent is saying what, without reading. Every submission carries
the name of the engine that sent it, and a name quiet for a while announces
itself once before its next message.

**Generate a file, run a player.** skid never opens an audio device, selects
one, mixes or sets a volume. The operating system does all four better, and the
failure surface this buys is a missing player and a bad file.

**No overlap, ever.** Two agents speaking over each other is worse than either
waiting.

## Layout

    src/skid/           config, generation, greeting, player, spool,
                        substitution, then server, service and client.
                        install.py stands apart: stdlib only, so it can run
                        before skid is installed
    tests/              one file per module, external test package
    share/systemd/user/ skid.socket and skid.service, the real units
    bin/                two links into toolbox, which the common jig resolves
                        against this directory
    docs/SPEC.md          how skid is arranged
    docs/TEST_PLAN.md     one test named per requirement
    docs/REQUIREMENTS/    one file per requirement, under a category directory
    docs/SUPPRESSIONS.md  every #nosec, with the question and the answer
    docs/DECISIONS/       one file per decision

## Requirements

`docs/REQUIREMENTS/<category>/<id>-<slug>.md`, ruled in
`silo/docs/DECISIONS/requirements-are-a-directory.md`. Each row is kept
verbatim, so concatenating the tree reproduces the document the checker parses.

**48 rows, none open, 40 with a test citing them.** The eight without are
FR-1.5, FR-1.6, FR-1.7, FR-4.2, FR-6.3, FR-7.3, FR-7.6 and FR-8.3, each with a
proposed test at
`clank/tasks/skid/traceability/10-test-the-eight-testable-rows.ready`.

An id is never reused. `docs/REQUIREMENTS/README.md` lists the retired ones.

## Running it

    systemd   ~/.config/systemd/user/skid.{socket,service}
              socket-activated at $XDG_RUNTIME_DIR/skid/skid.sock, mode 0600
    tool      uv tool install --editable, giving skid, skid-mcp, skid-install
    client    claude mcp add --scope user skid -- skid-mcp

`skid` is the service: one process, one warm model, MCP over HTTP on the socket
systemd hands it. `skid-mcp` is a stdio shim holding no model, no queue and no
config, bridging the two because MCP clients speak stdio and an http URL cannot
name a unix socket. Without it every session would load kokoro for itself.

**The installed tool is editable, so a code edit reaches the running service
only after `systemctl --user restart skid.service`.**

**Say you are deploying before you do that.** A restart wedges every client
whose shim predates skid `de3abb5`: the shim holds an MCP session id the new
process has never heard of, gets a 404 with a null id, and the caller waits
until its harness gives up at 1800 seconds with no diagnosis. FR-5.3 has the
detail. A shim spawned after `de3abb5` rebuilds its session and is unaffected,
so this stops mattering once every session has been through one restart.

### Installing

    python3 src/skid/install.py       from a checkout
    skid-install                      afterwards, by name

Both are `src/skid/install.py`. `--dry-run` prints the commands without running
them, `--uninstall` reverses everything, `--yes` answers the reinstall prompt
for a script. It verifies the units with `systemd-analyze` before writing
anything, enables the socket without starting the service, and names every file
it changed.

### A session acquires skid at its next clear

A client picks an MCP server up when a session starts, so a session already
running when `claude mcp add` happens has no `speak` however healthy the service
is. `claude mcp list` does not answer this: it reports that the server is up,
not that the asking session can reach it.

**A `/clear` is enough; a full restart is not needed.** Measured 2026-08-28: on
five of seven live clients the shim process was far newer than the client, and
this session's client predated the socket by three-quarters of a day yet
acquired the tools and spoke.

**That a clear is what respawns the shim is inferred from that correlation, not
observed.** One wedged session clearing and then calling `status()` would settle
it.

## The queue is a directory

`$XDG_RUNTIME_DIR/skid/spool`, one JSON file per submission, written before
`submit` returns and taken in filename order. `docs/SPEC.md` has the detail.

The text is durable and the audio is a cache. Order comes from a sequence in the
filename, not a timestamp, because a timestamp records generation order. An
entry moves to `taken/` while it plays and is removed when the attempt ends
however it ends, so a failing entry cannot block the queue; anything found in
`taken/` at start-up was interrupted and is discarded rather than replayed.

Submissions expire after five minutes, `expiry_seconds` in the config. Downtime
counts toward it.

## The gate

    bolt python-std-quality .
    bolt --definitions skid common-quality .

**Read `result.yaml` in the run directory, never the runner's summary line**,
and read all of it: the reasons list is longer than a truncated grep shows.

The common jig needs three things it does not state: `--definitions` before the
positionals, `bolt.skid.definitions.yaml` pointing `requirements` at
`docs/REQUIREMENTS`, and `bin/` holding the two links into toolbox.

Three tasks fail as of 2026-08-28:

    analyse   pylint rates skid 9.59/10, and the findings are skid's own,
              mostly redefined-outer-name from pytest fixtures
    tests     coverage runs from PATH's python 3.14.7, which cannot import
              skid's dependencies
    types     mypy, the same

The last two are one defect and it is toolbox's: the jig runs Python tools from
PATH, and skid's dependencies live in a 3.12 virtualenv because kokoro refuses
3.13. Filed at `clank/tasks/toolbox/jig-validation/30`.

Locally, use the project interpreter:

    .venv/bin/python -m pytest -o addopts= -q
    mypy --python-executable .venv/bin/python src tests

**bandit passes with five `#nosec` marks**, all on `subprocess` in `player.py`
and `install.py`, registered in `docs/SUPPRESSIONS.md` with the question and the
answer. No test imports `subprocess`.

## What is decided

**The output path**, in full: file, subprocess, default device, no direct
access. The part least worth reopening.

**The concurrency shape.** The lock covers playback alone, so generation runs
ahead of the speaker, unbounded. A submission arriving while another plays
queues.

**`paplay` as the player**, with a user-defined one declared as a command line.
It follows the default output device and works on PulseAudio and PipeWire alike.

**A 30 second quiet window**, measured from the end of the last clip spoken for
that name.

**The config file is the record**, for the voice and the substitutions alike. A
setting made through an MCP tool is written through and survives a restart, and
comments and ordering in the file are preserved.

**Substitutions are global**, each declaring itself literal or regular
expression, applied in one left-to-right pass whose output no later entry
examines. File order is the order.

**One HTTP service under systemd, not two processes.** Decided 2026-08-27. It
deleted a start protocol with a lock file, a stale-socket unlink and a
bind-then-rename.

**A unix socket, not a TCP port**, since reaching skid's tools means making the
machine speak and rewriting its config.

**No mocks.** kokoro is installed and tested against.

**Python 3.12 exactly**, because kokoro declares `<3.13,>=3.10` and this
machine's default is 3.14.7. **Linux only, first pass.**

## What is not built

Nothing a requirement names. Four tasks are open and all four ready: the MCP
server moving into the stdio script, the config becoming YAML, the systemd
watchdog and start limit, and the eight uncovered rows.

Measured 2026-08-28: kokoro 0.9.4 and torch 2.13.0 under Python 3.12.14.
`paplay`, `aplay` and `pw-play` are present; `ffplay`, `mpv` and `espeak-ng` are
not.

## Where the work is

`clank/tasks/skid/` for tasks, `clank/inbox/skid/` for findings filed against
skid, `.reviews/` for review reports.

Read `silo/docs/PATTERNS/how-a-change-gets-made.md` before writing anything
here. The spec was reviewed twice at `fd42bdf` and revised; a cold read of the
revision is still owed.
