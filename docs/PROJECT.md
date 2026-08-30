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

It generates a file and runs a player. skid never opens an audio device,
selects one, mixes or sets a volume, because the operating system does all four
better, and the failure surface this buys is a missing player and a bad file.

Nothing ever overlaps. Two agents speaking over each other is worse than either
waiting.

## Layout

    src/skid/           config, generation, greeting, player, spool,
                        substitution, then service, routes and client.
                        tools.py is the route declaration both processes
                        derive from, and imports neither of them.
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

**62 rows, none open, 62 with a test citing them, and every test citing a row.**
Both directions, and the `traceability` task exits 0:

    python3 bin/test-traceability.py --requirements docs/REQUIREMENTS .

The checker holds both directions: every row needs a test, and every test needs
a row. The second is the one worth watching, because a suite can be complete
against the code and say nothing about what the code owes.

A mark can still point at the wrong row, and the checker cannot catch it: it
sees a citation and a requirement that exists. Only reading the row against the
test does.

Four of the last eight are discharged by reading a declaration rather than by
calling anything, which for those rows is the right shape: an import set, a
target platform and an interpreter range have no behaviour to exercise.
`tests/test_declarations.py` holds them. Two of the four are tripwires on
kokoro's own metadata, so they fail when the premise underneath FR-1.7 or FR-7.6
moves.

An id is never reused. `docs/REQUIREMENTS/README.md` lists the retired ones.

## Running it

    systemd   ~/.config/systemd/user/skid.{socket,service}
              socket-activated at $XDG_RUNTIME_DIR/skid/skid.sock, mode 0600
    tool      uv tool install --editable, giving skid, skid-mcp, skid-say
              and skid-install
    client    claude mcp add --scope user skid -- skid-mcp

`skid` is the service: one process, one warm model, six Flask routes served by
waitress on the socket systemd hands it. `skid-mcp` is the MCP server: it holds
the six tool schemas and the dispatch, and no model, no queue and no config.
Without it every session would load kokoro for itself.

    claude <-stdio-> skid-mcp <-plain HTTP-> skid

**What crosses the socket is plain HTTP, and nothing is cached on either side.**
`skid/tools.py` names the six routes, and both processes derive from it, so a
tool cannot exist on one side only.

**The installed tool is editable, so a code edit reaches the running service
only after `systemctl --user restart skid.service`.**

**An editable install carries code, not dependencies.** The tool environment at
`~/.local/share/uv/tools/skid/` is resolved when the tool is installed, so a new
entry in `pyproject.toml` is not there however many times the service restarts.
Measured 2026-08-28: `flask` and `waitress` had been declared and locked for
hours, `uv sync` had put them in `.venv`, the suite was green, and the service
went into a restart loop on `ModuleNotFoundError: No module named 'waitress'`.

    uv tool install --editable . --reinstall

That is the deploy step whenever a dependency changed. `.venv` passing says
nothing about it, because they are two environments.

Say you are deploying before you restart. It is a courtesy rather than a rescue
now: a restart costs a connection refused for as long as the service takes to
come back, and every client reconnects on its next call.

**The wedge is gone rather than handled**, as of 2026-08-28. It existed because
MCP over HTTP kept a session id in the service's memory: a restart forgot it,
the service answered 404 with a null id, and a client that cannot match a null
id to its request waited until its harness gave up at 1800 seconds with no
diagnosis. No session id exists on either side now, so nothing can go stale.
FR-5.3 and `clank/tasks/skid/resilience/40` carry the detail.

`/mcp` serves the protocol to a `skid-mcp` that predates the move, and holds no
session. It answers `initialize`, `tools/list`, `tools/call` and `ping`, returns
a JSON-RPC method-not-found for anything else, and returns 202 to a
notification, which has no id and which JSON-RPC forbids answering. The tools it
publishes come from `skid.tools`, so it cannot drift from the plain routes.

Deleting it once reintroduced the wedge by a new road. An old shim posted there,
Flask answered 404 with an HTML page, and an HTML page is not a JSON-RPC message
either, so the client waited exactly as before: a `status()` call was still
outstanding at 120 seconds on the live socket.

Retire it once no pre-move `skid-mcp` is running, which happens on its own as
sessions clear. `pgrep -af skid-mcp` counts them, and the drift test in
`tests/test_routes.py` names the route, so removing it is a change something
notices.

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

The shell exit status says only that bolt carried the run out. Both jigs exit 0
while failing, so `success` in `result.yaml` is the verdict. `--result-to-exitcode`
asks for the other behaviour where a caller wants it.

**`~/bin/bolt` is the Rust build**, cut over 2026-08-29, and `~/bin/bolt.go`
still reaches the Go one. Three differences a reader will meet:

    task ordinals start at 1        `tests-1` where Go wrote `tests-0`
    evidence is keyed, not a list   "tests-1": {args, result}
    flags may follow the positionals, which Go refuses with usage

The Rust build prints the result path and nothing else, by its FR-10.3, so there
is no summary line to misread. `bolt.go` prints one and it counts every
execution rather than the failures, labelled with the run's verdict, so the same
gate prints `failed: 23` red and `passed: 23` green.

**The gate is wired by symlinks that are deliberately not tracked**, because
they point at `../../toolbox/` and would be dangling links in anybody's clone.
`.gitignore` holds them out and `bolt.skid.definitions.yaml`, which is skid's
own, is tracked. A fresh checkout makes them:

    ln -s ../../toolbox/bin/test-traceability.py bin/
    ln -s ../../toolbox/bin/suppression-register.py bin/
    ln -s ../toolbox/bolt.common-quality.yaml .
    ln -s ../toolbox/bolt.python-std-quality.yaml .
    ln -s ../toolbox/bolt.secrets.yaml .
    mkdir -p adapters/common && ln -s ../../../toolbox/adapters/common/bolt-result.py adapters/common/

The last two are what the common jig started needing when it composed the
secrets jig rather than copying it.

The common jig needs three things it does not state: `--definitions` before the
positionals, `bolt.skid.definitions.yaml` pointing `requirements` at
`docs/REQUIREMENTS`, and `bin/` holding the two links into toolbox.

The two jigs fail differently.

`bolt python-std-quality .`:

    analyse    pylint rates skid 9.59/10, and the findings are skid's own,
               mostly redefined-outer-name from pytest fixtures
    cognitive  complexipy, over the tree rather than the files skid checks
    tests      coverage runs from PATH's python 3.14.7, which cannot import
               skid's dependencies
    types      mypy, the same

The last two are one defect and it is toolbox's: the jig runs Python tools from
PATH, and skid's dependencies live in a 3.12 virtualenv because kokoro's
metadata declares `<3.13`. Filed at `clank/tasks/toolbox/jig-validation/30`.

`bolt --definitions skid common-quality .`:

    complexity     5 functions over lizard's 60-line length bound

`suppressions` and `traceability` pass. The register's index rows have to spell
the pragma as the source does, because the checker reads them with the same
patterns it scans the source with; a row naming only the bandit rule is prose to
it, and the marks behind it read as unregistered. `docs/SUPPRESSIONS.md` carries
the format.

**`complexity` is five length warnings and no complexity ones**, all `length >
60` with cyclomatic complexity of 4 or less: `build_operations` and `build_app`
in `routes.py`, `install_plan`, `build_server`, and `Service.__init__`. Three of
the five are long because they are declaration blocks rather than logic.

Locally, use the project interpreter:

    .venv/bin/python -m pytest -o addopts= -q
    mypy --python-executable .venv/bin/python src tests

**bandit passes with five `#nosec` marks**, all on `subprocess` in `player.py`
and `install.py`, registered in `docs/SUPPRESSIONS.md` with the question and the
answer. No test imports `subprocess`.

## What is decided

The output path, in full: file, subprocess, default device, no direct access.
The part least worth reopening.

The lock covers playback alone, so generation runs ahead of the speaker,
unbounded, and a submission arriving while another plays queues.

**The watchdog measures progress, not liveness**, `WatchdogSec=120`. skid pings
only while the serve loop is getting somewhere, and withholding the ping is the
mechanism: a timer on a thread that is always alive proves the timer runs, which
is the failure being detected. Health is idle, or a clip on the speaker, or a
step within `PROGRESS_GRACE`.

It is not keyed to clip length:

    sample      chars  generate s   audio s   ratio
    short           5        0.38      1.27    3.36
    typical        43        0.49      2.83    5.73
    long          398        3.78     25.62    6.77
    longest      1196       11.35     76.88    6.77

Two numbers come out of this and they are easy to confuse. `ratio` is audio
seconds per second of generation, about 6.8x realtime. The speaking rate is
about 15.5 characters per second of audio, or 155 words a minute.
`docs/LESSONS/a-derived-figure-next-to-its-premise-is-checkable.md`.

So 1196 characters plays for 77 seconds and nothing caps a message. Playback
pings, so the window has to clear one generation step instead. Generation is
linear in length, and the longest clip the 300s ceiling admits takes about 44
seconds to make, well inside `WatchdogSec=120`.

`.ephemera/measure-clip-length.py` regenerates the table.

**The start limit is 10 attempts over 120 seconds**, where systemd's default was
5 over 10. The default latches on fast failures and not slow ones: an import
error stops in 7 seconds, while the spaCy episode restarted 76 times without
tripping it because each attempt outlived the window. Latching is deliberate;
`systemctl --user status skid.service` says failed and `reset-failed` clears it.

**`StartLimit*` goes in `[Unit]`.** systemd moved it in v229, ignores it in
`[Service]` with a warning, and `systemd-analyze verify` still exits 0 either
way, so the exit status cannot tell you which you wrote.

**`paplay` as the player**, with a user-defined one declared as a command line.
It follows the default output device and works on PulseAudio and PipeWire alike.

**A 30 second quiet window**, measured from the end of the last clip spoken for
that name.

**The config file is the record**, for the voice and the substitutions alike. A
setting made through an MCP tool is written through and survives a restart, and
the ordering of substitutions is preserved.

**It is YAML, at `~/.config/skid/config.yaml`, read and written by wrench
against a schema in `skid/schemas.py`.** skid was the last TOML holdout, having
chosen it 83 minutes before the ecosystem decision was recorded. Moved
2026-08-28; no config file existed on this machine, so nothing was migrated.

skid emits wrench's canonical form, quoted keys and sorted names. A person may
write plain unquoted YAML and it loads. `docs/config.sample.yaml` is the
readable version and the place reasons live, since the live file is rewritten
whenever a tool changes a setting.

**A key skid does not know is refused by name.** `voce: af_bella` used to load
and silently keep the default voice. That is a deliberate behaviour change;
FR-6.4 is untouched, so a *missing* config is still not an error.

**Comments are no longer preserved, and FR-7.1's clause for it is retired.** It
was what `tomlkit` was a dependency for. FR-8.4's ordering survives on its own
terms, because a YAML sequence carries order in the decoded structure.

**wrench is a path dependency, and skid cannot be installed without it.** It is
unpublished, so `[tool.uv.sources]` points at `../wrench/python`. That holds on
any machine set up from `dotfiles/repos.live.toml` and not on a standalone
clone. **Publishing wrench, or fetching it in the bootstrap, is a prerequisite
for skid going public.**

It is installed as an ordinary copy rather than editable. wrench used to resolve
its schemas by walking up from `__file__`, which forced an editable install, and
a PEP 660 import hook is something mypy cannot follow, so wrench's `py.typed`
was invisible and every import of it was an error.

**A copy does not track the sibling checkout.** Editing `../wrench/python` no
longer reaches skid's virtualenv, so a wrench change needs

    uv sync --reinstall-package wrench

which is the same shape as the tool environment not tracking `pyproject.toml`.

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
machine's default is 3.14.7. **Linux only, first pass**, declared as a
classifier in `pyproject.toml` so FR-1.6 has something a test can read.

**kokoro's `<3.13` is a declaration, not a ceiling.** Told first-hand
2026-08-28: it runs on 3.13 and 3.14 and has simply not had a release since. So
"kokoro refuses 3.13", which several documents said, is about the metadata
rather than the software.

**The pin stands anyway, because it costs nothing.** Nothing in skid's source
needs an interpreter newer than 3.12, and `uv tool install --editable` reads
`requires-python` and builds the tool environment on 3.12 with no flag, whatever
the machine's default is. Measured 2026-08-28: `python3 -V` gives 3.14.7,
`~/.local/share/uv/tools/skid/bin/python -V` gives 3.12.14, and kokoro imports
there. Installing into an environment holding an interpreter kokoro accepts is
the answer to the declaration, and it is already the arrangement.

## What is not built

Nothing a requirement names. One task is open and ready: the config becoming
YAML.

Measured 2026-08-28: kokoro 0.9.4 and torch 2.13.0 under Python 3.12.14.
`paplay`, `aplay` and `pw-play` are present; `ffplay`, `mpv` and `espeak-ng` are
not.

## Where the work is

`clank/tasks/skid/` for tasks, `clank/inbox/skid/` for findings filed against
skid, `.reviews/` for review reports.

Read `silo/docs/PATTERNS/how-a-change-gets-made.md` before writing anything
here. The spec was reviewed twice at `fd42bdf` and revised; a cold read of the
revision is still owed.
