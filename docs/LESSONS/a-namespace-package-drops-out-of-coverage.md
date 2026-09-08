# A namespace package drops out of coverage without saying so

2026-09-07. Cost: one design revision, caught before any of skid's source moved.
Had it not been caught, the gate would have kept reporting green over modules it
had stopped measuring.

## What the design wanted

Splitting skid into three distributions so the MCP shim stops being rebuilt every
time the service changes. The attractive version keeps every module importable as
`skid.x` by deleting the empty `src/skid/__init__.py` and letting the three
distributions share one PEP 420 namespace package.

It works, in every way that gets checked first. Both tool environments install,
both scripts run, `skid.__path__` spans all three checkouts, editable installs
resolve, mypy passes under `strict`, and not one import in the source or the
suite has to change.

## What it actually does

**coverage.py enumerates unexecuted files in a regular package and not in a
namespace package.** A module no test imports appears at 0% in the first case and
is absent from the report in the second. No warning, no error, no count that
looks wrong.

One tree, one variable, `.ephemera/split-proposal/control`:

    src/ctl/__init__.py present     src/ctl/hit.py    2  0  100%
                                    src/ctl/miss.py   2  2    0%

    src/ctl/__init__.py deleted     src/ctl/hit.py    2  0  100%
                                    (miss.py is not in the report)

Nothing else changed between those two runs. The same `source = ["ctl"]`, the
same suite, the same command.

## Why that is worse than a failing check

Hard rule 5 says never settle a coverage failure by excluding the file, because
coverage is judged per file so a well-tested file cannot carry an untested one.
An exclusion is at least written down and greppable.

This produces the same loss with nothing written down. The file is not excluded;
it is simply never considered. A gate reading per-file percentages sees a shorter
list and has no way to notice that the list got shorter.

The failure needs a module nobody imports, which is exactly the module whose
coverage anyone would want to know about.

## What does not fix it

`source_pkgs = ["skid"]` instead of `source = ["skid"]`. Naming the three source
directories as `source`. Naming them as `source_dirs`. All three were measured
and all three report the same two imported files and nothing else.

## What fixes it

Three distinct import packages, each a regular package with an `__init__.py`, and

    source = ["skid", "skid_mcp", "skid_contract"]

Enumeration returns, and where coverage cannot find a package at all it now says
so instead of shrinking quietly:

    CoverageWarning: Module skid was never imported. (module-not-imported)

That warning is the property worth having. The namespace version had no way to
produce it, because a namespace package is never "not imported": it resolves to
an empty path list and coverage has nothing to complain about.

## The general shape

A packaging change can remove a check without touching the check. Nothing in the
gate's configuration mentioned namespace packages, nothing failed, and the only
symptom was a report with fewer rows than the tree has files.

**Count the rows.** When a layout changes, the question is not whether the
coverage check passes. It is whether it is still looking at the same number of
files, and a per-file gate makes that countable.
