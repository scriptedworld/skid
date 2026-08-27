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

CLAIM. It serves every agent and belongs to none of them, so it sits beside them
rather than inside one. It is also a program with its own requirements, its own
tests and its own gate, which is the same argument that took infobot out of
silo.

Nobody has stated this in so many words. Ask before treating it as settled.

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

**skid is the first repository on the layout**, so what goes inside a file was
decided here: `docs/DECISIONS/what-a-requirement-file-carries.md`. The row is
kept verbatim, so concatenating the tree reproduces the document the checker
parses today. FACT 2026-08-27: the 32 rows are byte-identical to the retired
`REQUIREMENTS.md` at `aafb459`.

    diff <(git show aafb459:REQUIREMENTS.md | grep '^| FR-' | sort -V) \
         <(grep -h '^| FR-' docs/REQUIREMENTS/*/*.md | sort -V)

`docs/REQUIREMENTS/README.md` carries the status markers and what each category
holds.

## The gate

**Nothing gates skid, and nothing can today.** FACT 2026-08-27: every jig in
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

**Python, and the MCP SDK for Python.** FACT 2026-08-27: `mcp` 2.0.0 is
installed, under Python 3.14.7. Whether kokoro forces the language is FR-7.6 and
open, and the first pass is Python either way.

**Linux only, first pass.**

## What is open

Nine questions, `FR-7.1` to `FR-7.9`, in `docs/REQUIREMENTS/open/`. Each is a
requirement with an id rather than a line of prose, so closing one is a decision
against a row that exists. Each is queued in `clank/tasks/skid/` as `.questions`,
which is the queue they get answered from.

**The sharpest is FR-7.3, what the lock covers.** FR-2.1 forbids overlap and
FR-4.2 wants the rest of an array prepared while one clip speaks, so one lock
around generation and playback both satisfies the first and silently destroys
the second. Nothing about the audible output would say which was built.

FR-7.1 and FR-7.8 are one question asked twice, so they are queued as one task:
when a setting is reachable by an MCP tool and by editing the config, which one
is the record.

## What is not built

Everything. `src/skid/__init__.py` is empty and `tests/` holds a `.gitkeep`.

FACT 2026-08-27: kokoro is not installed here, so nothing in FR-1 or FR-5 has
been measured against the real engine.

    python3 -c "import kokoro"    ModuleNotFoundError: No module named 'kokoro'

Players, measured the same day with `command -v`: `paplay` (which is `pacat`),
`aplay` and `pw-play` (which is `pw-cat`) are present; `ffplay`, `mpv` and
`espeak-ng` are not. The server is PulseAudio 15.0.0 on PipeWire 1.4.2 and the
default sink is `alsa_output.pci-0000_00_1f.3.analog-stereo`.

**skid is in no manifest.** FACT 2026-08-27: `grep -rn skid
~/.projects/dotfiles/repos.*.toml` returns nothing, so nothing on this machine
knows skid exists. `repos.*.toml` is dotfiles', so it is filed as
`clank/inbox/dotfiles/skid-is-in-no-manifest/` with the entry to paste.

Read `silo/docs/PATTERNS/how-a-change-gets-made.md` before writing any of it.
Stage 1 is a spec, which does not exist, and several of the open questions have
to close before one can be written.
