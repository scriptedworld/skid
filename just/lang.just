# The Python half for skid.
#
# EVERY RECIPE RUNS THROUGH uv, AND THAT IS LOAD-BEARING RATHER THAN A HABIT.
# skid pins `requires-python = ">=3.12,<3.13"` because kokoro declares
# `<3.13,>=3.10`, while `python3` on this machine is 3.14.7. So a bare `pytest`
# or `mypy` runs against an interpreter that cannot import this project's
# dependencies.
#
# skid's own pyproject records what that costs: the `types` task reports thirty
# phantom errors from PATH and one real one from the venv. Filed against the jig
# against the jig.
#
# So `just test` here means `uv run pytest`, and the jig calls in `checks` are
# the exception: those run bolt, which invokes the checkers from PATH by design,
# and changing that is toolbox's to do rather than this file's.
#
# NOTHING HERE IS BUILT OR DEPLOYED. skid installs as console scripts into the
# environment, so clean has nothing dangerous to remove. The four entry points
# are skid, skid-mcp, skid-say and skid-install.

# everything: quality, tests, coverage, secrets
checks:
    @just _verdict common-quality --definitions skid
    @just _verdict python-std-quality
    @just leak-scan

# the suite
test:
    uv run pytest

# COVERAGE IS MEASURED AND NOT ENFORCED, which is the jig's state rather than a
# choice made here: bolt.python-std-quality.yaml produces coverage.xml and its
# own footer says the per-file threshold waits on an adapter that reads
# Cobertura XML. An aggregate is refused there, per hard rule 5.

# the suite with coverage, and the minimum enforced
coverage:
    #!/usr/bin/env bash
    set -euo pipefail
    uv run coverage run -m pytest
    uv run coverage report
    uv run coverage xml -o coverage.xml
    echo "coverage: measured, NOT enforced. No per-file threshold exists yet."

# formatting verified, nothing written
format-check:
    uv run ruff format --check .
    uv run ruff check .

# formatting written
format:
    uv run ruff format .
    uv run ruff check --fix .

# may be a no-op
build:
    @echo "build: python needs no build step; see dist"

# whatever this language distributes
dist:
    uv build

# EDITABLE, so the package resolves from the tree rather than from a copy.
#
# `skid-install` is a different thing from this recipe and both are needed:
# this one puts the package in the environment, that one performs skid's own
# first-run installation. `python3 src/skid/install.py` is the documented first
# run because the console script is only reachable after it.

# put the built artefact where it is used from
install:
    uv pip install -e .

# remove run directories and build output
clean:
    rm -rf .bolt-* dist build coverage.xml .coverage
    rm -rf .ruff_cache .mypy_cache .pytest_cache .complexipy_cache
    find . -name '*.egg-info' -type d -prune -exec rm -rf {} +
    find . -name __pycache__ -type d -prune -exec rm -rf {} +
