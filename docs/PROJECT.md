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

- **The flag goes before the positionals**, or bolt drops it silently and the
  run reports a plausible wrong verdict rather than an error.
- **`bolt.skid.definitions.yaml`** points `requirements` at `docs/REQUIREMENTS`,
  because the jig still defaults to the retired single file.
- **`bin/` holds two links into toolbox**, because the jig resolves its checkers
  against `{config_dir}`, which is this directory.

**The traceability checker reads a directory.** It finds all 45 rows. The
standing story that it could not was a flag being dropped, not a checker
limitation.

**Adopting cost one exclusion.** The linked checkers are Python, so `mypy` and
`pylint` read them as skid's source and failed the gate entirely on toolbox's
code. `pyproject.toml` scopes those tools away from `bin/`, which holds nothing
skid wrote, and says so beside the exclusions. Filed as
`clank/inbox/toolbox/an-adopter-is-graded-on-the-checkers-it-adopts`.

    python-std-quality   8 of 9 pass; tests exits 5 with no tests collected
    common-quality       2 of 3 pass; traceability reports 0 of 45 covered

**Both remaining failures are the same fact**, and stage 4 clears both.
Traceability is the one worth watching: it read 45 real rows, so it is a
measurement rather than a vacuous pass, and it is the check that will hold every
test to a requirement once tests exist.

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

## What is not built

Everything. `src/skid/__init__.py` is empty and `tests/` holds a `.gitkeep`.

Measured 2026-08-27: kokoro is not installed here, so nothing in FR-1 or FR-5
has been run against the real engine.

    python3 -c "import kokoro"    ModuleNotFoundError: No module named 'kokoro'

It cannot be installed against this machine's default interpreter either, which
is 3.14.7. FR-1.7 is the constraint and `pyproject.toml` carries it.

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
