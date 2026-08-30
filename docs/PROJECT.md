# skid, the project

Voice output for the agents. An MCP server that takes an array of text and
speaks it: kokoro generates an audio file, a subprocess plays it on the default
output device, one clip at a time.

Named for Skidd McMarx, who is loud, has a voice everyone recognises, and does
nothing else.

Read this before changing anything here. `README.md` is the front door,
`docs/SPEC.md` says how skid is arranged, and `CONTRIBUTING.md` has the commands
for running the suite and the checkers.

## What it is for

Hearing which agent is saying what, without reading. Every submission carries
the name of the engine that sent it, and a name quiet for a while announces
itself once before its next message.

It generates a file and runs a player. skid never opens an audio device, selects
one, mixes or sets a volume, because the operating system does all four better,
and the failure surface this buys is a missing player and a bad file.

Nothing ever overlaps. Two agents speaking over each other is worse than either
waiting.

## Layout

    src/skid/           config, generation, greeting, assignment, player,
                        spool, substitution, then service, routes and client.
                        tools.py is the route declaration both processes
                        derive from, and imports neither of them.
                        install.py stands apart: stdlib only, so it can run
                        before skid is installed
    tests/              one file per module, external test package
    share/systemd/user/ skid.socket and skid.service, the real units
    bin/                links to the adopted checkers, untracked
    docs/SPEC.md          how skid is arranged
    docs/TEST_PLAN.md     one test named per requirement
    docs/REQUIREMENTS/    one file per requirement, under a category directory
    docs/SUPPRESSIONS.md  every #nosec, with the question and the answer
    docs/DECISIONS/       one file per decision
    docs/LESSONS/         what went wrong once, so it does not twice

`docs/REQUIREMENTS/README.md` describes the categories, the status markers and
the retirement rule. Every row has a test citing it and every test cites a row
that exists, which proves the citations are complete and proves nothing about
whether the code satisfies the row. `NEXT_STEPS.md` carries what that gap has
already cost.

## Running it

    systemd   ~/.config/systemd/user/skid.{socket,service}
              socket-activated at $XDG_RUNTIME_DIR/skid/skid.sock, mode 0600
    tool      uv tool install --editable, giving skid, skid-mcp, skid-say
              and skid-install
    client    claude mcp add --scope user skid -- skid-mcp

`skid` is the service: one process, one warm model, six Flask routes served by
waitress on the socket systemd hands it. `skid-mcp` is the MCP server, holding
the six tool schemas and the dispatch, and no model, no queue and no config.
Without it every session would load kokoro for itself.

    claude <-stdio-> skid-mcp <-plain HTTP-> skid

What crosses the socket is plain HTTP and nothing is cached on either side.
`skid/tools.py` names the six routes and both processes derive from it, so a
tool cannot exist on one side only.

### Deploying a change

The installed tool is editable, so a code edit reaches the running service only
after `systemctl --user restart skid.service`.

**An editable install carries code, not dependencies.** The tool environment is
resolved when the tool is installed, so a new entry in `pyproject.toml` is not
there however many times the service restarts. Measured the hard way: `flask`
and `waitress` were declared and locked, `uv sync` had put them in `.venv`, the
suite was green, and the service went into a restart loop on
`ModuleNotFoundError: No module named 'waitress'`.

    uv tool install --editable . --reinstall

That is the deploy step whenever a dependency changed. `.venv` passing says
nothing about it, because they are two environments.

wrench is installed as an ordinary copy rather than editable, so editing the
sibling checkout does not reach skid's virtualenv:

    uv sync --reinstall-package wrench

A restart costs a connection refused for as long as the service takes to come
back, and every client reconnects on its next call.

### A session acquires skid at its next clear

A client picks an MCP server up when a session starts, so a session already
running when `claude mcp add` happens has no `speak` however healthy the service
is. `claude mcp list` does not answer this: it reports that the server is up,
not that the asking session can reach it.

A `/clear` is enough and a full restart is not needed. That a clear is what
respawns the shim is inferred from the correlation rather than observed; one
wedged session clearing and then calling `status()` would settle it.

### The legacy protocol route

`/mcp` serves the MCP protocol to a `skid-mcp` that predates the move into the
stdio script, and holds no session. It answers `initialize`, `tools/list`,
`tools/call` and `ping`, returns a JSON-RPC method-not-found for anything else,
and returns 202 to a notification, which has no id and which JSON-RPC forbids
answering. The tools it publishes come from `skid.tools`, so it cannot drift.

Deleting it once reintroduced the hang it had removed. An old client posted
there, Flask answered 404 with an HTML page, and an HTML page is no more
matchable to a pending request than the null session id had been, so the client
waited. Retire it once no client old enough to need it is running.
`docs/LESSONS/deleting-an-endpoint-recreated-the-bug-it-removed.md`.

## The gate

`CONTRIBUTING.md` lists what a contributor can run. The composed gate is a step
beyond that and it is not self-contained: the jig files and the two checkers in
`bin/` are links into a sibling `toolbox` checkout, held out by `.gitignore`
because they would be dangling links in anybody's clone.
`bolt.skid.definitions.yaml` is tracked, because it is skid's own and it is what
points the checker at a requirements directory.

**Read `result.yaml` in the run directory, never the runner's summary line**,
and read all of it: the reasons list is longer than a truncated grep shows. The
shell exit status says only that the run was carried out. Both jigs exit 0 while
failing, so `success` in `result.yaml` is the verdict.

One failing task is skid's own. pylint rates this code 10.00/10 and still exits
non-zero on a single finding, the lazy kokoro import in `generation.py`. The
import cannot move to the top without loading torch at module import, which
breaks FR-5.1 and the stdlib-only chain `install.py` depends on, so clearing it
needs a registered suppression rather than an edit.

The register's index rows have to spell the pragma as the source does, because
the checker reads them with the same patterns it scans the source with. A row
naming only the bandit rule is prose to it, and the marks behind it read as
unregistered.

## What is decided

The output path, in full: file, subprocess, default device, no direct access.
The part least worth reopening.

The lock covers playback alone, so generation runs ahead of the speaker,
unbounded, and a submission arriving while another plays queues.

**The watchdog measures progress, not liveness**, `WatchdogSec=120`. skid pings
only while the serve loop is getting somewhere, and withholding the ping is the
mechanism: a timer on a thread that is always alive proves the timer runs, which
is the failure being detected. Health is idle, or a clip on the speaker, or a
step within the grace period. It is not keyed to clip length, because playback
pings and a clip can legitimately run 77 seconds. `docs/SPEC.md` carries the
measurements behind that, and
`docs/LESSONS/a-derived-figure-next-to-its-premise-is-checkable.md` the two
rates it is easy to confuse.

**The start limit is 10 attempts over 120 seconds**, where systemd's default was
5 over 10. The default latches on fast failures and not on slow ones: an import
error stops in 7 seconds, while the spaCy episode restarted 76 times without
tripping it because each attempt outlived the window. Latching is deliberate;
`systemctl --user status skid.service` says failed and `reset-failed` clears it.

**`StartLimit*` goes in `[Unit]`.** systemd moved it in v229, ignores it in
`[Service]` with a warning, and `systemd-analyze verify` exits 0 either way, so
the exit status cannot tell you which you wrote.

**`paplay` as the player**, with a user-defined one declared as a command line.
It follows the default output device and works on PulseAudio and PipeWire alike.

**A 30 second quiet window**, measured from the end of the last clip spoken for
that name.

**A voice per name, drawn from a shortlist in the config.** The key is the name
`speak` already carries, so no session id comes back. A name keeps its voice
while it keeps talking and loses it after six hours of quiet; when every voice
is held the one silent longest is given out again, rather than refusing or
falling back to one shared default. The voice sits alongside FR-3.2's spoken
greeting rather than replacing it.

The shortlist is 28 voices chosen by ear from samples, English only and both
Englishes. Five are Spanish, French or Italian speakers carrying `pipeline: a`,
which is the other half of the decision: a kokoro voice is a speaker and a
pipeline is a phonemiser, they are separable, and skid used to weld them
together by reading the voice id's first letter. Those five are on the list as
English speakers with an accent.

Each entry carries an `alias`, an ordinary first name matching the sex in the
voice id. It is read and never spoken, so it only has to be distinguishable on
the page. `status` reports the live map as `assigned`.

**The config file is the record**, for the voice and the substitutions alike. A
setting made through an MCP tool is written through and survives a restart, and
the ordering of substitutions is preserved.

**It is YAML, at `~/.config/skid/config.yaml`, read and written by wrench**
against a schema in `skid/schemas.py`. skid emits wrench's canonical form,
quoted keys and sorted names, and a person may write plain unquoted YAML and it
loads. `docs/config.sample.yaml` is the readable version and the place reasons
live, since the live file is rewritten whenever a tool changes a setting.

**A key skid does not know is refused by name.** `voce: af_bella` used to load
and silently keep the default voice. FR-6.4 is untouched, so a missing config is
still not an error. One consequence to remember before rolling back: a config
holding keys an older checkout does not know is refused rather than ignored, and
a refusal at start-up is a service that will not start.

**Substitutions are global**, each declaring itself literal or regular
expression, applied in one left-to-right pass whose output no later entry
examines. File order is the order.

**One HTTP service under systemd, not two processes.** It deleted a start
protocol with a lock file, a stale-socket unlink and a bind-then-rename, which
was the part of the design nobody had run.

**A unix socket, not a TCP port**, since reaching skid's tools means making the
machine speak and rewriting its config. `SECURITY.md` states the boundary.

**No mocks.** kokoro is installed and tested against.

**Python 3.12 exactly**, because kokoro declares `<3.13,>=3.10`. **Linux only,
first pass**, declared as a classifier in `pyproject.toml` so FR-1.6 has
something a test can read.

**kokoro's `<3.13` is a declaration, not a ceiling.** It runs on 3.13 and 3.14
and has simply not had a release since, so "kokoro refuses 3.13" is about the
metadata rather than the software. The pin stands anyway, because it costs
nothing: nothing in skid's source needs a newer interpreter, and
`uv tool install --editable` reads `requires-python` and builds the tool
environment on 3.12 with no flag, whatever the machine's default is. Installing
into an environment holding an interpreter kokoro accepts is the answer to the
declaration, and it is already the arrangement.

**wrench is a path dependency, and skid cannot be installed without it.** It is
unpublished, so `[tool.uv.sources]` points at a sibling checkout. It is not
editable: wrench used to resolve its schemas by walking up from `__file__`,
which forced an editable install, and a PEP 660 import hook is something mypy
cannot follow, so wrench's `py.typed` was invisible and every import of it was
an error. Publishing wrench, or fetching it in the bootstrap, is the
prerequisite for skid going public. `NEXT_STEPS.md` carries what it blocks.

## What is not built

Nothing a requirement names. `NEXT_STEPS.md` holds what is open anyway: the
wrench blocker, one known defect, and the questions nothing depends on.
