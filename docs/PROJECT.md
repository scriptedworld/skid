# skid, the project

Voice output for the agents. An MCP server that takes an array of text and
speaks it: kokoro generates an audio file, a subprocess plays it on the default
output device, one clip at a time.

The name is Skidd McMarx, who is loud, has a voice everyone recognises, and does
not do anything else.

## What it is FOR

Hearing which agent is saying what, without reading. Every submission carries
the name of the engine that sent it, and a name that has been quiet for a while
announces itself once before its next message, so a listener can follow a chain
without every line introducing itself.

**The output path is the whole design.** Generate a file, run a player. skid
never opens an audio device, selects one, mixes or sets a volume, because the
operating system already does all four and does them better. What **the output
path** buys is a failure surface of two items: a player that is not there, and a
file that is bad. `docs/REQUIREMENTS/what-it-speaks-with/FR-1.5-skid-never-talks-to-an-audio-device.md`
is the property stated on its own so it can be tested as one.

**That is the output path's surface, not the whole design's.** The queue, the
lookahead and the configurable player each add failures of their own, and
`docs/SPEC.md` names them under Failure. An earlier draft of both documents
generalised the two to the whole system, which is the kind of sentence that stops
anyone looking for a third case.

**No overlap, ever.** Two agents speaking over each other is worse than either
waiting.

## Why it is its own repository

Stated 2026-08-27, heard by the silo session and relayed here rather than to me
directly:

> Because it's an MCP with a supporting background process ... and I believe
> that deserves it's own tree.

**That is a criterion rather than an observation about skid.** An MCP with a
supporting background process gets its own tree, and what makes skid one is the
warm backend of FR-5.1.

So the requirement and the repository boundary are one decision seen twice, and
**dropping the backend would weaken the case for the tree.** FR-5.1 is wanted
rather than required, which is exactly the kind of thing that gets dropped for
being optional, and this is what it would cost.

It turns on shape, not on audience. Serving every agent and belonging to none
would put wrench and toolbox here on the same reasoning, and they are separate
for other reasons.

**The reasoning runs one way only, and `docs/SPEC.md` used to run it back.** The
criterion was stated first-hand, so the boundary rests on it and not on anything
skid decided. The spec then cited the boundary as a second reason for the
backend, which is one decision counted twice, and that appeal is withdrawn.
Both cold reviews of `fd42bdf` caught it independently.

## Layout

    src/skid/           the package. Empty: nothing is built.
    tests/              empty, and stage 4 of how a change gets made is where
                        it stops being empty
    docs/PROJECT.md     this file
    docs/SPEC.md        how skid is arranged, so that the requirements hold
    docs/REQUIREMENTS/  one file per requirement, under a category directory
    docs/DECISIONS/     one file per decision
    pyproject.toml      uv project, hatchling, Python >= 3.12
    README.md           what a person arriving cold needs

## Requirements are a directory

`docs/REQUIREMENTS/<category>/<id>-<slug>.md`, ruled in
`silo/docs/DECISIONS/requirements-are-a-directory.md`. skid adopted it at
commissioning rather than carrying a `REQUIREMENTS.md` to migrate later, which
it could do because nothing gates it.

**skid was the first repository on the layout**, so what goes inside a file was
decided here and then promoted to bind every repository:
`silo/docs/DECISIONS/what-a-requirement-file-carries.md`, silo `92e93df`.
`docs/DECISIONS/what-a-requirement-file-carries.md` is a pointer to it and holds
only what is skid's own.

The row is kept verbatim, so concatenating the tree reproduces the document the
checker parses today. **The migration moved all 32 rows byte-identically**,
which is a claim about the migration commit rather than about the tree now:

    diff <(git show aafb459:REQUIREMENTS.md   | grep '^| FR-' | sort -V) \
         <(git grep -h '^| FR-' f8c5660 -- docs/REQUIREMENTS | sort -V)

The tree has moved since and the current rows are not that set. Ten of the 32
were `[?]` and were rewritten as settled statements at the same ids as they
closed, and thirteen rows have been added, so 45 rows now stand where 32 did.

`docs/REQUIREMENTS/README.md` carries the status markers and what each category
holds.

## The gate

`bolt.python-std-quality.yaml` is linked to toolbox's and adopted. The link is
gitignored: a committed copy would be a second statement of one file.

    bolt python-std-quality .

**Read `result.yaml` in the run directory, never the runner's summary line.**
Measured 2026-08-27, the first run here: `success: false`, with two reasons,
`docstrings exited 1` and `tests exited 5`. The summary printed
`failed: 9 execution(s)`, which is the number of executions in the run and not
the number that failed; seven of the nine report `success: true` in their own
`output.yaml`.

**Both failures are true and neither is the gate's fault.** pytest exits 5 when
it collects no tests, and there are none. Docstring coverage is measured over a
package holding one empty file.

**Green tasks over one empty file are a vacuous pass, not coverage.** ruff,
mypy, pylint, bandit, vulture and complexipy read `src/skid/__init__.py` and
find nothing wrong with it because there is nothing in it. The language gate
becomes meaningful with the first code, not before.

`traceability` is the exception and the reason the common jig is worth having
early: it reads the 45 requirement rows whether or not any code exists, so it
fails honestly today rather than passing over nothing.

The jigs were unrunnable earlier the same day, refused by wrench's schema for
naming a task `id`, and toolbox's port landed between that measurement and this
one.

**Both jigs are adopted.** The common one needs three things the jig does not
say, all of them recorded in
`clank/tasks/skid/gate/20-adopt-the-common-jig.complete`:

    bolt --definitions skid common-quality .

- **The flag goes before the positionals.** Written after them it becomes a
  positional, and bolt refuses with usage and exit 1, writing no run directory
  at all.
- **`bolt.skid.definitions.yaml`** points `requirements` at `docs/REQUIREMENTS`,
  because the jig still defaults to the retired single file.
- **`bin/` holds two links into toolbox**, because the jig resolves its checkers
  against `{config_dir}`, which is this directory.

**The traceability checker reads a directory.** It finds all 45 rows, and the
silo session confirmed the same checker against a single-file repository, so the
standing story that it could not is spent.

**Adopting cost one exclusion.** The linked checkers are Python, so `mypy` and
`pylint` read them as skid's source and failed the gate entirely on toolbox's
code. `pyproject.toml` scopes those tools away from `bin/`, which holds nothing
skid wrote, and says so beside the exclusions. Filed as
`clank/inbox/toolbox/an-adopter-is-graded-on-the-checkers-it-adopts`.

    python-std-quality   7 of 9 pass; docstrings 0.0%, tests exits 5
    common-quality       2 of 3 pass; traceability reports 0 of 45 covered

Measured 2026-08-27 against bolt `v0.0.0-20260827201109-7604557974a5`, reading
`result.yaml` from a named `--output-dir`.

**All three failures are the same fact: there is no code yet.** Stage 4 clears
them and none is worked around. In particular `docstrings` is left failing
rather than answered with a module docstring written to move the number, which
would be gaming a measurement rather than passing it.

**`docstrings` is the worked example of a borrowed pass.** It reported 88.9% and
passed until toolbox excluded the adopted paths. The 88.9% was toolbox's two
checker scripts, reached through `bin/`. skid's own code scores 0.0%, and both
numbers are one command apart:

    interrogate --fail-under 80 -e .venv -e venv -e build -e dist .
      -> PASSED, 88.9%          reading toolbox's checkers

    interrogate --fail-under 80 -e .venv -e venv -e build -e dist \
                -e .ephemera -e bin -e adapters .
      -> FAILED, 0.0%           reading skid's

A green task that was measuring somebody else's repository is exactly what the
vacuous-pass warning is about, and it took another project fixing its jig to
surface it here.

**Traceability is the one check that is not vacuous today.** It reads 45 real
rows whether or not code exists, so its failure is a measurement, and it is what
will hold every test to a requirement once tests exist.

## Where the work is

`clank/tasks/skid/`, and findings filed against skid arrive in
`clank/inbox/skid/`. Nothing about task states or claiming is restated here; the
global `CLAUDE.md` carries it.

## What is decided

**The output path**, in full, and it is the part least worth reopening: file,
subprocess, default device, no direct access. Every requirement in
`what-it-speaks-with` is stated first-hand.

**One clip at a time**, with the mechanism deliberately left open.

**The concurrency shape**, settled 2026-08-27. The lock covers playback alone,
so generation runs ahead of the speaker, and it runs ahead unbounded (FR-7.3).
A submission arriving while another plays queues, also unbounded (FR-7.2).

Nothing is dropped and nothing is capped, which is the trade that was chosen
with its cost stated: a long array holds every clip it has generated before the
second one is heard, and a caller behind one waits as long as it takes with no
way to know how long that is.

**`paplay` as the player**, with a user-defined one declared as a command line
(FR-7.5). It follows the default output device, which FR-1.4 requires, and it
works on PulseAudio and PipeWire machines alike.

**A 30 second quiet window**, measured from the end of the last clip spoken for
that name (FR-7.4). Short by choice: a name that pauses re-announces rather than
being assumed to still hold the floor.

**The config file is the record** for the voice and for the pronunciation
substitutions alike (FR-7.1, FR-7.8). A setting made through an MCP tool is
written through and survives a restart. The obligation that comes with it is
writing into a file a person owns, so comments and ordering in it are to be
preserved rather than normalised away.

**Substitutions are global, and an entry declares its own kind**, literal or
regular expression (FR-7.9, FR-7.7). The two rules that admitting regular
expressions forces are settled with them: the set is a file and file order is
the order, so reordering is editing the file (FR-8.4), and substitution is one
left-to-right pass whose output no later entry examines (FR-8.5).

**Python, because kokoro is a Python project** (FR-7.6). Measured 2026-08-27
from PyPI: kokoro 0.9.4 depends on torch, transformers, huggingface-hub, numpy,
misaki and loguru, so the package is the implementation rather than a binding
over one. Staying in one language was the stated preference, and FR-5.2's MCP
SDK for Python is a second reason that does not rest on the same measurement.

**Python 3.12, exactly** (FR-1.7). kokoro declares `requires_python
<3.13,>=3.10`, so `pyproject.toml` pins `>=3.12,<3.13` rather than leaving a
floor that resolves to an interpreter kokoro refuses. This machine's default is
3.14.7, which is not it.

That dates the other measurement: `mcp` 2.0.0 was found installed under 3.14.7,
which says the SDK exists rather than that it is present for this project.

**Linux only, first pass.**

## What is open

**No requirement is open.** All nine of FR-7 were recorded at commissioning and
all nine closed on 2026-08-27. Each closed at the id it already carried, so
nothing was retired and no id was reused, and `docs/REQUIREMENTS/open/` is gone
rather than kept empty.

45 requirements, none marked `[?]`.

**`docs/SPEC.md` answered the design questions this section used to list**: where
the config lives and in what format, what the MCP tool surface is, and how the
backend is started and reached. Read it there rather than here.

Writing it raised four properties nothing had stated, which are now requirements
rather than spec prose: FR-4.4 that submissions do not interleave, FR-4.5 that
submitting returns when queued, FR-4.6 that one failure does not cancel an
array, and FR-6.4 that a missing config is not an error.

**Reviewing it raised six more**, which is the same mechanism working again on a
document that had already been through it: FR-1.8 that a player must not return
before its clip is inaudible, FR-1.9 that one which never returns is killed,
FR-3.5 that the greeting is decided at playback, FR-3.6 that the quiet table is
not persisted, FR-4.7 that a failure has somewhere to be seen, and FR-6.5 that a
setting which would silence skid is refused.

Each of the ten names what raised it. FR-8.5 was corrected rather than added: it
had asserted entry priority while the spec asserted positional priority, and the
two disagree on ordinary input.

**The coverage check runs both ways and is clean.** Every requirement is cited
by the spec, and the spec cites nothing that is not a requirement:

    diff <(grep -ho 'FR-[0-9]\+\.[0-9]\+' docs/SPEC.md | sort -uV) \
         <(grep -ho '^| FR-[0-9.]*' docs/REQUIREMENTS/*/*.md | sed 's/| //' | sort -V)

What the spec still leaves open is listed in the spec itself, and none of it is
a question for anyone else to answer.

## How it runs, as of 2026-08-28

**skid is a live service on this machine and every Claude Code session can
reach it.**

    systemd   ~/.config/systemd/user/skid.{socket,service}
              socket-activated at $XDG_RUNTIME_DIR/skid/skid.sock, mode 0600
    tool      uv tool install --editable, giving `skid` and `skid-mcp`
    client    claude mcp add --scope user skid -- skid-mcp

    claude mcp list        skid: skid-mcp  - Connected

`skid` is the service: one process, one warm model, MCP over HTTP on the socket
systemd hands it. `skid-mcp` is a stdio shim holding no model, no queue and no
config, because MCP clients speak stdio and an http URL cannot name a unix
socket. One line in, one POST, one line out. Without it every session would load
kokoro for itself, which is what FR-5.1 exists to prevent.

### A session older than the registration cannot call it

**Registering an MCP server does not reach sessions that are already running.**
A client picks the server up when it starts, so a session that predates
`claude mcp add` has no `speak` however healthy the service is.

Confirmed first-hand 2026-08-28 by the session that did the registering: it
could not call its own tool afterwards, and the silo session hit the same thing
independently.

**`claude mcp list` does not answer this.** It says the server is up, not that
the asking session can reach it. So the diagnosis for "skid is running and I
cannot speak" is almost always the session's age rather than the service, and
the fix is restarting the client rather than anything here.

It has an unfortunate shape worth naming: the sessions with most worth saying
are the long-running ones, and those are exactly the ones that cannot say it
until they restart.

### The installer does not exist, and that is the gap that matters

The units at `share/systemd/user/` are the real ones, and they were installed by
hand. **So skid works here and is reproducible nowhere**, and the difference
between those two states lived only in a session until this paragraph.

What an installer owes, in order:

    uv tool install --editable <checkout>
    cp share/systemd/user/skid.{socket,service} ~/.config/systemd/user/
    systemctl --user daemon-reload
    systemctl --user enable --now skid.socket
    claude mcp add --scope user skid -- skid-mcp

Queued as `clank/tasks/skid/`. Nothing else stands between skid and another
machine.

## What deploying it taught, which the tests could not

Three things that only appeared when it ran as a service, all now fixed and all
worth keeping because each would have been found again:

**kokoro downloads a spaCy model at start-up** using pip or uv, and neither is
on PATH under systemd. The service failed to start 76 times before
`en_core_web_sm` was declared as a dependency. A service must not need a package
installer to start.

**The MCP SDK returns 421 on an unknown Host header**, even over a unix socket
where no browser can reach it. The allowed hosts are declared rather than the
protection disabled, because scoping a guard and switching it off are not the
same act.

**`mkdir(mode=0o700)` does nothing to a directory that already exists**, and the
service created the runtime directory before `main` could set its mode, so it
came out 0775 holding a 0666 socket. Only systemd's own 0700 runtime directory
kept FR-5.4 true. Under the unit the socket is `srw-------` because systemd sets
it; run by hand, uvicorn chmods it to 0666 whatever the umask, so the 0700
directory carries the property instead.

## What is not built

The installer, above. Everything else in the requirements has code and tests.

Measured 2026-08-28: kokoro 0.9.4 and torch 2.13.0 are installed under Python
3.12.14, and the whole path has been run end to end and heard: an MCP client
over the socket called `speak`, and the machine said it.

Players, measured the same day with `command -v`: `paplay` (which is `pacat`),
`aplay` and `pw-play` (which is `pw-cat`) are present; `ffplay`, `mpv` and
`espeak-ng` are not. The server is PulseAudio 15.0.0 on PipeWire 1.4.2 and the
default sink is `alsa_output.pci-0000_00_1f.3.analog-stereo`.

**skid is in no manifest.** Measured 2026-08-27: `grep -rn skid
~/.projects/dotfiles/repos.*.toml` returns nothing, so nothing on this machine
knows skid exists. `repos.*.toml` is dotfiles', so it is filed as
`clank/inbox/dotfiles/skid-is-in-no-manifest/` with the entry to paste.

Read `silo/docs/PATTERNS/how-a-change-gets-made.md` before writing any of it.
Stages 1 and 2 are done and **stage 1 has been reviewed twice**, by the wrench
session and by a cold subagent, independently and without contact. Both read
`fd42bdf`. The spec was revised against the union of their findings and the
revision has not itself been reviewed.

**Stage 3, the test plan, is next.** It derives from the requirements rather
than from the spec, so it is not waiting on a second review pass.

The two reviews converged on four findings and each found what the other missed,
which is the argument for two rather than one. Where they agreed, the confidence
is real: neither could have primed the other.

Stage 4 is tests written to fail, and the gate runs against them before there is
an implementation. That is the point at which the seven currently vacuous checks
start reading something.
