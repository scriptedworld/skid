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
operating system already does all four and does them better. What that buys is
a failure surface of two items: a player that is not there, and a file that is
bad. `docs/REQUIREMENTS/what-it-speaks-with/FR-1.5-skid-never-talks-to-an-audio-device.md`
is the property stated on its own so it can be tested as one.

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

## Layout

    src/skid/           the package. Empty: nothing is built.
    tests/              empty, and stage 4 of how a change gets made is where
                        it stops being empty
    docs/PROJECT.md     this file
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
checker parses today. Measured 2026-08-27, the 32 rows are byte-identical to the
retired `REQUIREMENTS.md` at `aafb459`.

    diff <(git show aafb459:REQUIREMENTS.md | grep '^| FR-' | sort -V) \
         <(grep -h '^| FR-' docs/REQUIREMENTS/*/*.md | sort -V)

`docs/REQUIREMENTS/README.md` carries the status markers and what each category
holds.

## The gate

**Nothing gates skid, and nothing can today.** Measured 2026-08-27: every jig in
toolbox is refused by the bolt on PATH before a single task runs.

    bolt python-std-quality .
    bolt: wrench: validating bolt.python-std-quality.yaml: jsonschema validation
    failed with 'https://scriptedworld.github.io/wrench/jig.schema.json#'
    - at '/tasks/0': missing property 'name'

`~/bin/bolt` resolves to `~/.projects/bolt/bin/bolt` and runs, which is the new
bolt built from `bolt.go`: it names tasks `name`, composes by nested jig tasks,
and takes one jig per run as `bolt <jig> <directory>`. The toolbox jigs are
written for the bolt before it, using `id`, `{configdir}` and `-c` overlays. All
four of them fail the same way, so this is not skid's adoption being wrong.

Already tracked as `clank/tasks/toolbox/port-the-jigs/10-port-to-the-new-jig-format.planning`,
and skid's own adoption waits on it at
`clank/tasks/skid/gate/10-adopt-the-python-jig.blocked`.

**No jig is linked here in the meantime.** A link to a jig the runner refuses is
a gate that reports an error on every run, which reads as a broken project
rather than an unported jig.

When the port lands, the second half is `traceability`: the checker takes
`--requirements REQUIREMENTS.md` and cannot read a directory, which is the whole
of `clank/inbox/toolbox/traceability-must-read-a-directory`. So the language jig
is adoptable before the common one.

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

**Python, and the MCP SDK for Python.** Measured 2026-08-27: `mcp` 2.0.0 is
installed, under Python 3.14.7. Whether kokoro forces the language is FR-7.6 and
open, and the first pass is Python either way.

**Linux only, first pass.**

## What is open

**Five, in `docs/REQUIREMENTS/open/`.** Nine were recorded at commissioning and
FR-7.2 to FR-7.5 closed on 2026-08-27. Each is a requirement with an id rather
than a line of prose, so closing one is a decision against a row that exists,
and the file then moves out of `open/` into the category its answer belongs to.

Each open one is queued in `clank/tasks/skid/` as `.questions`, which is the
queue they get answered from.

    FR-7.1  does a tool-set voice persist to the config
    FR-7.6  is Python forced by kokoro, or chosen
    FR-7.7  are substitutions literal or regular expressions
    FR-7.8  do substitutions live in the config as well as the tool
    FR-7.9  are substitutions global or per name

FR-7.1 and FR-7.8 are one question asked twice, so they are queued as one task:
when a setting is reachable by an MCP tool and by editing the config, which one
is the record.

**None of the five blocks a spec for the core path**, which is what FR-7.2 to
FR-7.5 were holding. FR-7.7 and FR-7.9 block the pronunciation tool, and FR-7.1
with FR-7.8 blocks anything that persists a setting.

## What is not built

Everything. `src/skid/__init__.py` is empty and `tests/` holds a `.gitkeep`.

Measured 2026-08-27: kokoro is not installed here, so nothing in FR-1 or FR-5
has been run against the real engine.

    python3 -c "import kokoro"    ModuleNotFoundError: No module named 'kokoro'

Players, measured the same day with `command -v`: `paplay` (which is `pacat`),
`aplay` and `pw-play` (which is `pw-cat`) are present; `ffplay`, `mpv` and
`espeak-ng` are not. The server is PulseAudio 15.0.0 on PipeWire 1.4.2 and the
default sink is `alsa_output.pci-0000_00_1f.3.analog-stereo`.

**skid is in no manifest.** Measured 2026-08-27: `grep -rn skid
~/.projects/dotfiles/repos.*.toml` returns nothing, so nothing on this machine
knows skid exists. `repos.*.toml` is dotfiles', so it is filed as
`clank/inbox/dotfiles/skid-is-in-no-manifest/` with the entry to paste.

Read `silo/docs/PATTERNS/how-a-change-gets-made.md` before writing any of it.
Stage 1 is a spec, which does not exist, and several of the open questions have
to close before one can be written.
