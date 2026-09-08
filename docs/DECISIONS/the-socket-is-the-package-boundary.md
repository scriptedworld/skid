# The socket is the package boundary

**Built 2026-09-07.** What this replaced was one distribution named `skid`
declaring four console scripts, and "What one package cost" measures that state
rather than the current one.

**One thing here is written rather than measured**, and it is marked where it
appears: installing from a git URL now needs `#subdirectory=packages/skid`, which
is written from the layout because the split has not been pushed.

## The decision

skid becomes three distributions in one checkout, split by which side of the
socket a module sits on:

    distribution    import package    depends on            installs as a tool
    skid-contract   skid_contract     nothing               no
    skid-mcp        skid_mcp          httpx, mcp            yes
    skid            skid              kokoro, torch, spacy  yes
                                      flask, waitress, wrench

Two of them install as tools, so `uv tool install` builds two environments that
are replaced independently. The third has no console script and installs as a
dependency of each side, so `uv tool list` still shows two entries.

## What one package cost

Measured 2026-09-07, `du -sh ~/.local/share/uv/tools/skid`:

    1.3 GB      the one tool environment, holding all four scripts
    738 MB      torch inside it
    123 MB      spacy
    59 MB       transformers

`client.py` imported `os`, `pathlib`, `typing`, `httpx`, `mcp.server.mcpserver`
and the route declaration. `tools.py` imported `typing` alone. Neither reached
kokoro, torch, spacy or generation, and neither could:

    grep -nE '^(import|from) ' packages/skid-mcp/src/skid_mcp/client.py \
                               packages/skid-contract/src/skid_contract/tools.py

So `uv tool install --editable . --reinstall`, the documented deploy step
whenever a service dependency moves, rebuilt a 1.3 GB environment in which the
MCP shim was 33 MB that did not change and could not have. Replacing the part
that makes noise disturbed the part that talks to the client, for nothing.

Reinstalling is what drops every running session's `speak` until that session
restarts. Today a change to `generation.py` is enough to cause it.

## The layout

    skid/
        pyproject.toml              the workspace root. No [project] table.
                                    Keeps every tool's configuration.
        packages/
            skid-contract/
                pyproject.toml
                src/skid_contract/__init__.py
                src/skid_contract/tools.py
            skid-mcp/
                pyproject.toml
                src/skid_mcp/__init__.py
                src/skid_mcp/client.py
                src/skid_mcp/say.py
            skid/
                pyproject.toml
                src/skid/           main, service, routes, generation, player,
                                    queue, spool, config, schemas, assignment,
                                    greeting, substitution, install
        tests/                      one suite, at the root, unchanged in shape
        share/ docs/ just/ bin/     unchanged

Sibling projects in one repository is the established shape here rather than a
new pattern. wrench holds `go/`, `python/` and `rust/` that way, and skid already
consumes it so:

    wrench @ git+https://github.com/scriptedworld/wrench.git#subdirectory=python

They sit under `packages/` rather than at the root because skid's root already
carries `docs/`, `share/`, `just/`, `bin/` and `tests/`, and because all three
are Python, where wrench's top level names languages.

## Three import packages, not one shared namespace

The tempting version of this change keeps every module importable as `skid.x`,
by dropping `src/skid/__init__.py` and letting three distributions share one PEP
420 namespace package. It works: it installs, it runs, both tool environments
resolve `skid.__path__` across the checkouts, and not one import in the source or
the suite has to change.

**It was built and rejected, because coverage.py does not enumerate unexecuted
files in a namespace package.** A module no test imports vanishes from the report
entirely rather than appearing at 0%, silently and with no warning. That is hard
rule 5's failure arriving without anybody writing an exclusion.

Measured on one tree with one file as the only variable,
`.ephemera/split-proposal/control`:

    with src/ctl/__init__.py        src/ctl/miss.py    2   2   0%
    with it deleted                 not in the report at all

`source_pkgs` does not fix it and naming the source directories does not fix it.
With three distinct import packages the enumeration returns, and where coverage
cannot see a package it now says so:

    CoverageWarning: Module skid was never imported. (module-not-imported)

The cost of the rejected version was zero import edits. The cost of this one is
the import lines in `routes.py`, `client.py` and `say.py`, plus the tests that
import them. That is the right trade: a silent hole in the gate is worth more
than a handful of import lines.

`docs/LESSONS/a-namespace-package-drops-out-of-coverage.md` carries the
measurement.

## Where tools.py goes, and why it gets its own distribution

`tools.py` names the six routes and both processes derive from it, so a tool
cannot exist on one side only. That is the whole reason it exists. It is 5.4 KB
and imports `typing`.

There are three places it could go and only one of them is right.

**Not the service side.** `client.py` imports it, so the shim would depend on the
service distribution and the shim's environment would carry torch. That is the
arrangement being removed.

**Not the client side, though this is the tempting one.** `routes.py` imports it,
so the service would depend on `skid-mcp`. The weight is affordable, mcp and
httpx being around 11 MB against 1.3 GB. The coupling is not. It inverts what
this project already decided, that the socket is the interface and MCP is one
client of it, and it means a change to `client.py` invalidates the service
environment. Splitting to stop one side disturbing the other, then wiring the
disturbance back in the opposite direction, buys half of what was asked for.

**Its own distribution, which is what it already is in every sense except
packaging.** Both sides depend on the contract, neither depends on the other, and
a contract change correctly invalidates both environments, because a contract
change is exactly the case where both sides must move together. The dependency
graph then says what `docs/PROJECT.md` already says in prose.

The cost is one more `pyproject.toml` declaring no dependencies.

## What each pyproject declares

**`packages/skid-contract/pyproject.toml`.** Name, version, the Python pin, an
empty dependency list, hatchling, `packages = ["src/skid_contract"]`.

**`packages/skid-mcp/pyproject.toml`.**

    dependencies = ["httpx", "mcp>=2.0", "skid-contract"]

    [project.scripts]
    skid-mcp = "skid_mcp.client:main"
    skid-say = "skid_mcp.say:main"

    [tool.uv.sources]
    skid-contract = { workspace = true }

`skid-say` lands here, and this is the snag the split has to answer rather than
step over. It is a second HTTP client of the socket, not an MCP thing, so a split
by protocol into `skid-mcp` and `skid-http` leaves it with no home and drops it
in the heavy package it does not need. Splitting by which side of the socket a
module sits on gives it one. The distribution name `skid-mcp` is then slightly
narrow for what it holds, and it stays, because it is the name already on PATH,
on the MCP registration and in every document. This paragraph is the record of
what it actually contains.

**`packages/skid/pyproject.toml`.** Everything the current file declares about
the service: the licence, the Linux classifier, `requires-python`, kokoro, torch
with its CPU index, the spaCy model wheel, flask, waitress, wrench,
`allow-direct-references`, and

    [project.scripts]
    skid = "skid.main:main"
    skid-install = "skid.install:main"

    [tool.uv.sources]
    wrench = { git = "https://github.com/scriptedworld/wrench.git", subdirectory = "python" }
    torch = [{ index = "pytorch-cpu" }]
    skid-contract = { workspace = true }

`httpx` and `mcp` leave it. Nothing the service imports reaches either.

**The root `pyproject.toml`** keeps every tool configuration it has today,
because those are read from the file rather than from a project, and adds

    [tool.uv.workspace]
    members = ["packages/*"]

It loses its `[project]` table and becomes a virtual workspace root. Coverage
names the three import packages rather than one:

    source = ["skid", "skid_mcp", "skid_contract"]

`install.py` stays with the service distribution. It installs both tools and
belongs to neither side, but the service is the thing that has to be installed
and started, `skid-install` is already delivered by the `skid` tool, and moving
it would mean a third tool install to get the installer. The documented bootstrap
becomes

    python3 packages/skid/src/skid/install.py

It imports nothing but the standard library and nothing from its own package, so
the deeper path costs it nothing.

## How install.py installs two tools

One step becomes two in `install_plan`:

    Step(says=f"install the skid service as a uv tool from {checkout}",
         argv=("uv", "tool", "install", "--editable", str(checkout / "packages" / "skid")))
    Step(says=f"install the skid MCP shim as a uv tool from {checkout}",
         argv=("uv", "tool", "install", "--editable", str(checkout / "packages" / "skid-mcp")))

and one becomes two in `uninstall_plan`, with `uv tool uninstall skid-mcp` before
`uv tool uninstall skid`.

`Paths.tool_dir` becomes `service_tool_dir` and `mcp_tool_dir`, both still
derived from `XDG_DATA_HOME` in `from_environment` and both still parameters so a
test can point them at a temporary directory. `already_installed` reports
whichever of the two exists, so a machine holding one half is told which half.

The MCP registration is untouched. It names `skid-mcp` as a command on PATH, and
`~/.local/bin/skid-mcp` is a symlink into whichever tool environment provides it.
`registration_is_current` reads the same entry and answers the same way.

This is the part of the change that is tested as data. `install_plan` returns a
list of `Step` and `tests/test_install.py` asserts against that list without
touching the machine, which is the shape the file was built for.

## What it costs

**The shim's environment falls from 1.3 GB to 33 MB**, which is 40 times
smaller. Measured on the real `packages/skid-mcp`, installed with
`UV_TOOL_DIR` pointed at a throwaway directory so the live install was not
touched:

    uv tool install --editable ./packages/skid-mcp
    du -sh <tooldir>/skid-mcp                        33M
    du -sh ~/.local/share/uv/tools/skid              1.3G

It holds no torch, kokoro, flask, spacy, transformers or nvidia package, and both
`skid-mcp` and `skid-say` run from it with the service package absent. **33 MB is
a fresh install and it grows to 39 MB once the bytecode caches are written**, so
quote whichever answers the question being asked; the 5.8 MB difference is
`__pycache__`.

**Measure one environment per `du` invocation, or the number is wrong.** uv
hardlinks package files out of `~/.cache/uv` into every environment it builds,
and `du` counts a shared inode once, so asking about two environments in one
command charges everything to whichever it walks first:

    du -sh proto real       ->  134M proto, 1.5M real
    du -sh real             ->  33M

Same files, same instant, two answers, and 1.5M is the one that looks like a
result. Both figures in this document are from a `du` given one directory. The
comparison is still fair, because the service's 1.3 GB is measured the same way
and hardlinks from the same cache; what neither figure is, is the marginal disk
a second environment costs, which is much smaller than either.

**A service reinstall stops touching the shim.** Measured by fingerprinting every
path and mtime under the shim's tool environment, running
`uv tool install --editable --reinstall` on the service, and fingerprinting
again. The two hashes are equal. This one was measured on the prototype in
`.ephemera/split-proposal/proto` rather than on the real packages, because doing
it for real means reinstalling the running service.

**A contract edit still reaches both running tools without a reinstall.** Both
sides install the contract editable, as a `.pth` file naming the checkout, so
this keeps current behaviour rather than trading it away. Verified by editing the
file and re-running the installed script.

**The service's environment is unchanged in practice.** It loses httpx and mcp,
around 11 MB of 1.3 GB. This split is not a diet for the service. It is a fence
between the service and the shim.

**One suite, one dev environment, unchanged commands.** A bare `uv run` at a
virtual workspace root installs every member. Verified from a cold start with no
lock file and no virtualenv, so `just test` and the gate's
`uv run coverage run -m pytest` need no flag added.

**mypy needs nothing added.** With three distinct import packages a bare
recursive `mypy .` resolves all three source roots under `strict`. The namespace
version needed `explicit_package_bases` and `mypy_path` to be checked at all.

**What was rewritten rather than moved.** `tests/test_declarations.py` read the
root `pyproject.toml` and `src/skid`, asserting the licence, the classifier,
`requires-python` and the third-party import set once for a tree that held both
sides. Those are per-package assertions now. The rows they discharge did not
move, and the split gave them more to say: the import set is asserted per
distribution, so a torch import appearing in `client.py` fails a test rather than
merely being untrue, and a new test asserts that neither side of the socket
imports the other at all.

**What it does not fix.** The three pre-existing branch-coverage failures in
`install.py`, `main.py` and `routes.py`. `main.py` and `routes.py` are untouched
and unchanged at 56.2% and 77.8%. `install.py` is modified by this change and
went from 76.1% to 77.1%, the new test covering more branches than it added.

**One thing this change got wrong first, recorded because the fix is not
obvious.** `already_installed` was rewritten as a list comprehension over the two
tool directories, which read well and dropped `install.py` to 75.0%, below the
baseline. A comprehension with a filter carries fewer branch arcs than two `if`
statements, so the same behaviour measured worse. It is two `if` statements.

## The alternative, and why two packages is not enough

Two distributions split by protocol, `skid-mcp` and `skid-http`, was the shape
first floated. It fails on `skid-say`, which is an HTTP client of the socket and
not an MCP thing, so under that split it belongs to `skid-http` alongside kokoro
and torch, and a command that needs nothing but a socket path drags in 738 MB of
tensors.

Two distributions split by side of the socket works, and the only question it
leaves is where the contract goes, which the section above answers. The third
distribution exists to keep both answers to that question from being wrong.

## The evidence

    .ephemera/split-proposal/proto/              the three-package prototype
    .ephemera/split-proposal/control/            the coverage control experiment
    .ephemera/split-proposal/real/               the real shim, installed isolated
    .ephemera/split-proposal/gate-before.txt     the gate as it stood
    .ephemera/split-proposal/gate-after.txt      the gate after

The prototype is not skid's code. It is skid's dependency graph and skid's import
shape with stand-in module bodies, built to answer the packaging questions before
any of skid's source moved. Every claim about sizes above is from `real/`, which
is the actual package; the prototype answers only the two questions that would
have meant reinstalling the running service to ask.

The gate said the same three things before and after, and nothing else:
`install.py`, `main.py` and `routes.py` below the branch minimum. Read
`result.yaml` in each run directory rather than the summary line, because both
jigs exit 0 while failing.
