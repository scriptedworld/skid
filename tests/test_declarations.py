"""What skid declares about itself, and the outside premises it rests on.

Four rows are discharged here by reading a file rather than by calling a
function, and for these that is the right shape rather than a compromise. A row
about an import set, a target platform or an interpreter version has no
behaviour to exercise: the declaration is the property, so the test reads the
declaration. Reaching for a behavioural test on one of them produces something
vacuous. `test_install.py` established the shape, asserting a plan as data.

Two of them are tripwires on something outside skid. FR-1.7 and FR-7.6 both rest
on measurements of kokoro that were true when they were taken, and a measurement
expires. Reading kokoro's own installed metadata means the day it moves is the
day these fail, which is the day each row is up for re-examination rather than
for having its numbers edited in place.

Nothing here imports skid. These are properties of the distribution and of its
source text, and importing the package would test the interpreter running the
suite instead of the file that declares the answer.
"""

from __future__ import annotations

import ast
import sys
import tomllib
from importlib.metadata import PackageNotFoundError, metadata
from pathlib import Path
from typing import Any

import pytest
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

CHECKOUT = Path(__file__).resolve().parent.parent
"""The real checkout, read from but never written to."""

SOURCE = CHECKOUT / "src" / "skid"

THIRD_PARTY = {"flask", "httpx", "kokoro", "mcp", "numpy", "waitress", "wrench"}
"""Every non-stdlib package skid's own source imports. Measured 2026-08-28.

Written out rather than counted, because which names are in it is the whole
point. Not one is an audio library, and the only route from skid to a device is
the `subprocess` call in `player.py`.

**`uvicorn` and `starlette` left when the MCP server moved into the stdio
script**, and `flask` and `waitress` arrived in their place. This test is what
noticed: the swap was made in `main.py` and the suite failed here, which is the
row doing its job on a change nobody wrote it for. It did the same again when
`tomlkit` left and `wrench` arrived with the config becoming YAML.

`mcp` is still here because `client.py` is the MCP server now. It is the
script's dependency alone, and nothing the service imports reaches it.
"""

ML_STACK = {"torch", "transformers", "numpy"}
"""What kokoro depending on makes it a Python project rather than a binding."""


def _pyproject() -> dict[str, Any]:
    """skid's own `pyproject.toml`, parsed."""
    text = (CHECKOUT / "pyproject.toml").read_text(encoding="utf-8")
    return tomllib.loads(text)


def _kokoro() -> Any:
    """kokoro's installed distribution metadata.

    Skipped rather than failed where kokoro is absent, because the row this
    serves is about what kokoro declares and an uninstalled kokoro declares
    nothing. A machine that runs skid has it.

    Typed `Any` because what `metadata()` returns is `PackageMetadata`, which
    lives in `importlib.metadata._meta` and is not exported. Reaching into a
    private module to name a type is worse than the two `str()` calls at the
    use sites, which is where the values are pinned down.
    """
    try:
        return metadata("kokoro")
    except PackageNotFoundError as absent:
        # `pytest.skip()` raises this, and raising it directly is what makes
        # every path here either return or raise.
        raise pytest.skip.Exception(
            "kokoro is not installed, so its declarations cannot be read"
        ) from absent


def _imported_roots() -> set[str]:
    """Every top-level module name imported anywhere in skid's own source.

    Parsed rather than imported, so a module that is expensive to load or that
    only imports something on one branch is still counted. `generation.py`
    imports kokoro inside a function for exactly that reason.
    """
    roots: set[str] = set()
    for source in sorted(SOURCE.glob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
    return roots


def _minor_versions() -> list[Version]:
    """Python versions to test a specifier against, as both specifiers are written."""
    return [Version(f"3.{minor}") for minor in range(8, 30)]


# COVERS: FR-1.5 | property
def test_skid_imports_no_audio_library() -> None:
    """The output path is a file and a subprocess, asserted at the import set.

    This passes on arrival, and that is not an argument against it. Its value is
    the day somebody reaches for `sounddevice` or `pyaudio` to fix a latency
    complaint: the change is small, it works, and nothing else in the suite
    notices that skid has acquired an audio stack to reason about.

    Asserted as equality rather than as an absence, because a denylist of audio
    libraries only catches the ones somebody thought of.
    """
    third_party = {
        root
        for root in _imported_roots()
        if root not in sys.stdlib_module_names and root != "skid"
    }

    assert third_party == THIRD_PARTY


# COVERS: FR-1.6 | property
def test_the_licence_is_declared_and_matches_the_file_beside_it() -> None:
    """A licence has two halves and only one of them was here.

    `LICENSE` is the written half and was correct. `pyproject.toml` is the
    machine-readable half, which is what a package index reads, and it declared
    nothing at all: a published wheel would have said its terms were unknown
    while the repository beside it carried Apache 2.0.

    Asserted together rather than separately, because the failure worth catching
    is not either being absent. It is the two disagreeing, which is the state
    that looks fine from whichever one you happen to read.
    """
    declared = _pyproject()["project"]["license"]
    written = (CHECKOUT / "LICENSE").read_text(encoding="utf-8")

    assert declared == "Apache-2.0"
    assert "Apache License" in written
    assert "Version 2.0" in written


# COVERS: FR-1.6 | property
def test_linux_is_declared_rather_than_intended() -> None:
    """Scope that only a document states is scope nothing can check.

    The classifier is the declaration FR-1.6 was missing. Widening the row means
    adding a platform here and to the players skid knows how to invoke, which is
    a change with a diff rather than a sentence somebody edits.
    """
    classifiers = _pyproject()["project"]["classifiers"]

    assert "Operating System :: POSIX :: Linux" in classifiers


# COVERS: FR-1.7 | property
def test_skid_runs_only_where_kokoro_does() -> None:
    """skid's interpreter range sits inside kokoro's, read from kokoro itself.

    Not a check that the range is `>=3.12,<3.13`, which would be the row copied
    rather than tested. What FR-1.7 requires is a containment, and the outer
    range belongs to somebody else and moves without warning.

    **This is a tripwire on what kokoro DECLARES, which is not the same as what
    kokoro SUPPORTS.** Told first-hand 2026-08-28: kokoro runs fine on 3.13 and
    3.14 and has simply not had a release since, so `<3.13` is stale packaging
    metadata rather than a real ceiling. The declaration is still what a
    resolver enforces, so it is still what skid has to sit inside to install at
    all, and it is still the thing that moves when the situation changes.

    So it fails on the day kokoro re-declares, not on the day it gains support.
    FR-1.7 names that as the day to retire the row rather than edit the version
    in place, so what skid was pinned to stays legible.
    """
    skid_range = SpecifierSet(_pyproject()["project"]["requires-python"])
    kokoro_range = SpecifierSet(str(_kokoro()["Requires-Python"]))

    allowed = [version for version in _minor_versions() if version in skid_range]

    assert allowed, f"skid's range admits no interpreter: {skid_range}"
    assert [v for v in allowed if v not in kokoro_range] == []


# COVERS: FR-7.6 | property
def test_kokoro_is_still_a_python_project() -> None:
    """A decision row is tested by asserting its premise, not its consequence.

    The consequence, that skid is written in Python, is tautological: this suite
    is Python and could not run otherwise. The premise is a measurement, and
    measurements expire. FR-7.6's premise is that kokoro is a Python project
    rather than a binding over something compiled, and what settles that is what
    it depends on.

    It fails on the day kokoro becomes a thin wrapper over a compiled runtime,
    which is the day the choice of language is worth re-examining rather than
    inheriting. Ruled at `clank/tasks/skid/traceability/20`.
    """
    required = _kokoro().get_all("Requires-Dist") or []
    names = {Requirement(str(entry)).name.lower() for entry in required}

    assert ML_STACK <= names, f"kokoro no longer declares the ML stack: {sorted(names)}"
