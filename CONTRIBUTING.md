# Contributing to skid

## Read this before you set up

`uv sync` is all a clone needs. `wrench`, which handles the config file and the
spool, is not on a package registry, so `pyproject.toml` names it by git URL and
`uv` fetches it like any other dependency.

To develop against a local wrench, override the source at the command line
rather than editing `pyproject.toml`, so the committed file keeps working for
everybody else.

## Setting up

Linux, Python 3.12, and `uv`.

    uv sync

That builds `.venv` with the runtime dependencies and the whole quality
toolchain. Use the project interpreter for everything: kokoro declares
`<3.13`, so a system python outside that range cannot import skid's
dependencies at all, and a tool run from PATH reports on the wrong environment
rather than failing honestly.

## Running the suite

    .venv/bin/python -m pytest -o addopts= -q

174 tests, about 30 seconds warm. The first run is slower, because there are no
test doubles: kokoro is installed and tested against, so the run downloads the
model weights and renders real audio. Nothing stands in for the engine or for
the audio path.

Coverage, which is not gated and is measured per file:

    .venv/bin/python -m coverage run -m pytest -o addopts= -q
    .venv/bin/python -m coverage report

## What a change has to carry

**Behaviour comes from a requirement, and the requirement comes first.**
`docs/REQUIREMENTS/<category>/FR-<id>-<slug>.md` is one file per requirement,
stated as an observable property: what is true of a run, not how it is arranged.
`docs/REQUIREMENTS/README.md` describes the categories and the status markers.

**Every test names the requirement it discharges**, in a comment directly above
it:

    # COVERS: FR-4.4 | property

The kinds are `positive`, `negative`, `edge`, `property` and `regression`. A
test citing nothing, or citing a requirement no file defines, fails the
traceability check. So does a requirement no test cites.

**An id is never reused.** Retiring a requirement means recording it under
`## Retired` in `docs/REQUIREMENTS/README.md` with what replaced it, and
repointing or removing every `COVERS:` mark that named it, in the same change.

**Tests live in `tests/`, an external test package**, and are held to the same
length, duplication and complexity bar as the source. Name a fixture separately
from its function, `@pytest.fixture(name="client")` on `client_fixture`, so a
parameter shadowing a module-level name stays a real finding.

**`docs/SPEC.md` says how skid is arranged** and names the requirements each
section discharges. A change that moves the design updates it, and the
requirement wins wherever the two disagree.

## The quality tools

All of them are in the dev group and run from `.venv`:

    .venv/bin/python -m ruff check .
    .venv/bin/python -m mypy src tests
    .venv/bin/python -m pylint src tests
    .venv/bin/python -m bandit -r src

mypy runs strict with `warn_unreachable`. It reports one error, kokoro's missing
`py.typed` marker, and that one is expected. bandit reports the `subprocess`
calls in the player and the installer.

## Suppressions are registered, never silent

A `#nosec`, a `# noqa`, a `# type: ignore` or a mypy override needs a written
question and a written answer in `docs/SUPPRESSIONS.md` before it is added, and
the register spells the pragma exactly as the source does. There are five marks
in the tree, all on `subprocess`, and no mocks. A failing check gets fixed or
asked about; it does not get quieted.

## Commits

Conventional commits. The subject says what changed. The body says what it cost,
counts and verdicts and figures that moved, and points at where the reasoning
lives rather than restating it. A sentence that would survive being moved into
the file belongs in the file.

No AI attribution of any kind: no trailer, no generated-with line, no robot
emoji.

## What you cannot run from a clone

The project's gate is composed from tooling that is not part of this repository.
`bin/` holds symlinks into a sibling checkout, `.gitignore` holds them out, and
the jig files are adopted the same way, so `just checks` and the traceability
checker do not resolve here. `bolt.skid.definitions.yaml` is tracked because it
is skid's own.

That is a gap rather than a policy. The suite, ruff, mypy, pylint and bandit are
the checks a contributor can run today, and they are the ones a change is judged
on.
