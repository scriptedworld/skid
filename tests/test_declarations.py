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
from importlib.metadata import PackageNotFoundError, metadata
from pathlib import Path
from typing import Any

import pytest
import tomllib
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

CHECKOUT = Path(__file__).resolve().parent.parent
"""The real checkout, read from but never written to."""

PACKAGES = {
    "skid": CHECKOUT / "packages" / "skid",
    "skid_mcp": CHECKOUT / "packages" / "skid-mcp",
    "skid_contract": CHECKOUT / "packages" / "skid-contract",
}
"""Each import package, mapped to the distribution directory that declares it.

The two names differ on purpose. A distribution is named with a hyphen and an
import package cannot be, so `skid-mcp` on disk is `skid_mcp` in an import line,
and a test that conflates them passes against a package that is not installed.
"""

FIRST_PARTY = frozenset(PACKAGES)
"""What this repository publishes, so an import of one is not a third party."""

THIRD_PARTY = {
    "skid": {"flask", "kokoro", "numpy", "waitress", "wrench"},
    "skid_mcp": {"httpx", "mcp"},
    "skid_contract": set[str](),
}
"""Every non-stdlib package each side of the socket imports. Measured 2026-09-07.

Written out rather than counted, because which names are in it is the whole
point. Not one is an audio library, and the only route from skid to a device is
the `subprocess` call in `player.py`.

**Stated per package, which is what the split bought.** It used to be one set
over a tree holding both sides, so `mcp` sat beside `kokoro` in a single
assertion and nothing could tell you which process loaded which. Now the shim's
row says httpx and mcp and stops, and it fails the day something on the client
side of the socket reaches for the model.

**`uvicorn` and `starlette` left when the MCP server moved into the stdio
script**, and `flask` and `waitress` arrived in their place. This test is what
noticed: the swap was made in `main.py` and the suite failed here, which is the
row doing its job on a change nobody wrote it for. It did the same again when
`tomlkit` left and `wrench` arrived with the config becoming YAML.

`skid_contract` imports `typing` and nothing else, so its set is empty and that
emptiness is the property: a dependency added to the contract lands in both
environments at once.
"""

ALLOWED_EDGES = {
    "skid": {"skid_contract"},
    "skid_mcp": {"skid_contract"},
    "skid_contract": set[str](),
}
"""Which packages each package may import, and the point is what is absent.

`skid` and `skid_mcp` are the two sides of the socket and neither may import the
other. Both derive from the contract, which imports neither.

An edge added here is a claim that one side of the socket now needs the other in
its process, which is the arrangement
`docs/DECISIONS/the-socket-is-the-package-boundary.md` exists to prevent.
"""

ML_STACK = {"torch", "transformers", "numpy"}
"""What kokoro depending on makes it a Python project rather than a binding."""


def _pyproject(package: str) -> dict[str, Any]:
    """One package's own `pyproject.toml`, parsed.

    Named rather than defaulted, because the root file is a workspace root now
    and declares no `[project]` table at all. A helper that fell back to it
    would raise `KeyError` on every row below and read as a broken test rather
    than as a question asked of the wrong file.
    """
    text = (PACKAGES[package] / "pyproject.toml").read_text(encoding="utf-8")
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


def _imported_roots(package: str) -> set[str]:
    """Every top-level module name imported anywhere in one package's source.

    Parsed rather than imported, so a module that is expensive to load or that
    only imports something on one branch is still counted. `generation.py`
    imports kokoro inside a function for exactly that reason, and importing this
    package to ask the question would load torch to find out that it does.
    """
    source = PACKAGES[package] / "src" / package
    roots: set[str] = set()
    for path in sorted(source.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
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
@pytest.mark.parametrize("package", sorted(PACKAGES))
def test_skid_imports_no_audio_library(package: str) -> None:
    """The output path is a file and a subprocess, asserted at the import set.

    This passes on arrival, and that is not an argument against it. Its value is
    the day somebody reaches for `sounddevice` or `pyaudio` to fix a latency
    complaint: the change is small, it works, and nothing else in the suite
    notices that skid has acquired an audio stack to reason about.

    Asserted as equality rather than as an absence, because a denylist of audio
    libraries only catches the ones somebody thought of.

    Per package rather than over the tree, so the answer says which process
    would load the thing. A tree-wide set cannot distinguish the service
    acquiring an audio library from the shim acquiring one, and the second is
    much the worse of the two.
    """
    third_party = {
        root
        for root in _imported_roots(package)
        if root not in sys.stdlib_module_names and root not in FIRST_PARTY
    }

    assert third_party == THIRD_PARTY[package]


# COVERS: FR-5.2 | property
@pytest.mark.parametrize("package", sorted(PACKAGES))
def test_neither_side_of_the_socket_imports_the_other(package: str) -> None:
    """The split is a property of the import graph, not of the directory names.

    FR-5.2 says the SDK is the script's dependency alone and that nothing the
    service loads reaches it. Three directories and three `pyproject.toml` files
    do not make that true by themselves: one `from skid_mcp.client import ...`
    in `routes.py` would put mcp back in the service's environment and nothing
    else in the suite would notice, because it would work.

    Asserted as equality rather than as an absence, so an edge nobody intended
    fails here rather than being caught by whichever denylist somebody thought
    to write.
    """
    edges = _imported_roots(package) & FIRST_PARTY

    assert edges - {package} == ALLOWED_EDGES[package]


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

    Asserted for every package, because there are three declarations now and one
    file. Three chances to disagree with it is the reason to check all three
    rather than the reason to check the one somebody remembers.
    """
    written = (CHECKOUT / "LICENSE").read_text(encoding="utf-8")

    assert "Apache License" in written
    assert "Version 2.0" in written
    for package in sorted(PACKAGES):
        assert _pyproject(package)["project"]["license"] == "Apache-2.0", package


# COVERS: FR-1.6 | property
def test_linux_is_declared_rather_than_intended() -> None:
    """Scope that only a document states is scope nothing can check.

    The classifier is the declaration FR-1.6 was missing. Widening the row means
    adding a platform here and to the players skid knows how to invoke, which is
    a change with a diff rather than a sentence somebody edits.

    All three packages, because the scope is skid's and not one distribution's.
    A shim that declared itself portable while the service declared Linux would
    be two answers to one question.
    """
    for package in sorted(PACKAGES):
        classifiers = _pyproject(package)["project"]["classifiers"]

        assert "Operating System :: POSIX :: Linux" in classifiers, package


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

    **Every package and not only the one that depends on kokoro.** The shim does
    not import kokoro and could widen its pin without anything breaking, right
    up until the two packages resolve to different interpreters and the contract
    they share is installed twice into environments that cannot both import it.
    One repository, one range.
    """
    kokoro_range = SpecifierSet(str(_kokoro()["Requires-Python"]))

    for package in sorted(PACKAGES):
        skid_range = SpecifierSet(_pyproject(package)["project"]["requires-python"])
        allowed = [version for version in _minor_versions() if version in skid_range]

        assert allowed, f"{package} admits no interpreter: {skid_range}"
        assert [v for v in allowed if v not in kokoro_range] == [], package


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
    inheriting.
    """
    required = _kokoro().get_all("Requires-Dist") or []
    names = {Requirement(str(entry)).name.lower() for entry in required}

    assert ML_STACK <= names, f"kokoro no longer declares the ML stack: {sorted(names)}"
