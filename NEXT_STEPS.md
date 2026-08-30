# skid, what is not done

Work lives in `~/.projects/clank/tasks/skid/`. This is what is not yet work: the
open decisions, and the things recent enough to be worth restating.

## The work that is agreed

**Nothing is `.ready`.** Every row a requirement names is built and the
resilience tasks are complete and deployed. Five tasks stand in
`clank/tasks/skid/`, and none of them is waiting on somebody to pick it up:

    interfaces/20    .questions   a forwarder shim in Go or Rust
    playback/20      .questions   how long a stuck player is given
    traceability/40  .planning    a cited row is not an implemented row
    interfaces/30    .planning    the entry points are barely covered
    resilience/50    .blocked     retire /mcp, gated on a process check

**`traceability/40` is the one that changes what the others are worth.** The
gate reads 62 of 62 in both directions, which proves every row has a citing test
and not that the code satisfies it. bolt found three settled requirements its own
code did not satisfy, each with a citing test, and skid has met the shape once:
FR-4.2's first test passed against the mutation it was written to catch.

`traceability/30` closed 2026-08-28. It asked whether the installer was inside
the requirement set or outside it, and the answer was inside: **otherwise there
is no way to know the right things were tested.** FR-9.1 to FR-9.14 in
`putting-it-on-a-machine`, and writing them found four obligations with no test
at all.

**`resilience/50` is blocked on a measurement, not a date.** Every running
`skid-mcp` must postdate the 2026-08-28 deploy before `/mcp` can go, and
deleting it early takes the voice off every session holding an older shim.
`docs/LESSONS/deleting-an-endpoint-recreated-the-bug-it-removed.md` is what
happened the first time. Checked 2026-08-28 at 18:47 and it is **not** clear:
eight of the nine shims running started between 02:06 and 10:48, before the
10:51 deploy.

    for p in $(pgrep -f skid-mcp); do ps -o pid=,lstart= -p $p; done

What is below is what is open rather than what is agreed: one decision skid
cannot take alone, two questions nothing depends on, and a surface nobody has
tested by using it.

## Open, and skid cannot settle it alone

**wrench must be published, or fetched by the bootstrap, before skid goes
public.** skid depends on it by relative path, `../wrench/python`, because
wrench is unpublished.

That holds on any machine set up from `dotfiles/repos.live.toml`, and a
standalone clone of skid **cannot install at all**.

wrench's own record says its install is not reproducible from any manifest, and
that gap is now skid's problem too: a machine rebuilt from `dotfiles/bin/setup`
gets every tool, no wrench, and a service that will not start.

wrench ships `py.typed` and its public API is annotated, so its calls are
type-checked here rather than skipped. `types` reports one error, kokoro, which
ships no marker of its own.

## Not settled by use

**Nobody has heard skid mispronounce anything.** Total real use so far is a
handful of messages, from silo and from skid itself. So the
substitution surface, first-match-wins ordering, the literal-and-regex split and
FR-8.4 making file order load-bearing, is designed against an imagined need.

Treat those rows as settled by argument, not by evidence. The first real
mispronunciation somebody reaches for the config to fix is worth more than any
of the reasoning behind them.

## Landed since this file was last rewritten

**The config is YAML and wrench validates it and the spool**, `3639f7c`,
deployed. Both structured files are read, written and validated against a schema
in `skid/schemas.py`.

What it bought is in the errors. `greeting_window_seconds: thirty` used to load
and fail somewhere downstream; `voce: af_bella` used to load and silently keep
the default voice. Both are refused by name at the file now. Writes are
validated too, so a tool cannot store a shape skid could never read back.

`spool.py` lost its catch-all, which took `OSError` alongside four shape errors
and so dropped a submission silently when the real fault was the disk. wrench
separates the file being wrong from the disk being wrong.

FR-7.1's comment clause is retired; FR-8.4's ordering is not, because a YAML
sequence carries order in the decoded structure. `tomlkit` is gone.

**The watchdog and the start limit**, `6ca9a7a`, deployed and live:
`WatchdogUSec=2min` where it was 0, and the start limit 10 over 120s where it
was systemd's 5 over 10.

The watchdog measures progress rather than liveness, and withholding the ping is
the mechanism. Health is idle, a clip on the speaker, or a step within 60
seconds. It is not keyed to clip length, because playback pings and a clip can
legitimately run 77 seconds.

Two things caught by writing them wrong first. `StartLimit*` moved to `[Unit]`
in systemd v229 and is ignored in `[Service]` with a warning while
`systemd-analyze verify` exits 0 either way, so the test asserts the section
rather than the key. And that test failed on its own first draft, because a
comment in the unit contains the literal `[Service]` and split the section
early.

**The MCP server moved into the stdio script**, `0eef559`, and is deployed and
serving. `skid-mcp` holds the six schemas and the dispatch; the service is six
Flask routes served by waitress on the socket systemd manages. No session id
exists on either side, so the wedge class has nothing to go stale.
`skid/tools.py` is the one declaration both derive from.

**Two things the deploy taught that no test could have.**

An editable install carries code but not dependencies. `flask` and `waitress`
had been declared and locked for hours and `.venv` had them, and the service
still went into a restart loop on `ModuleNotFoundError`. The tool environment is
resolved at install time: `uv tool install --editable . --reinstall` is the
deploy step whenever a dependency changed.

Deleting `/mcp` reintroduced the wedge by a new road, `437dd2b`. An old shim
posts there, Flask answered 404 with an HTML page, and an HTML page is no more
matchable to a pending request than a null id was, so the client waited. I had
traced the recovery path, predicted a clean failure and said so before
deploying; the first call after the restart was still outstanding at 120
seconds. `/mcp` serves the protocol again, statelessly, so an old shim can still
speak through it.

**Retire the `/mcp` route** once `pgrep -af skid-mcp` shows nothing predating
the move. Not urgent, and the drift test names it so removing it is noticed.

**Fixtures are named separately from their functions**, `5aa64be`. pylint's
`redefined-outer-name` catches a parameter shadowing a module-level name, which
is a real bug, and pytest's injection requires exactly that collision, so every
test using a fixture was a finding and a genuine one would have been invisible
among them. `@pytest.fixture(name="client")` on `client_fixture` removes the
collision rather than the check, so it needs no suppression. W0621 went 20 to 0
and pylint 9.45 to 9.79, and a deliberately shadowed name added afterwards was
still reported.

**Traceability is closed in both directions, 62 of 62.** Nine tests over the
last eight rows, and
`pyproject.toml` gained the Linux classifier FR-1.6 needed so the row had a
declaration to read. Four rows read a declaration, four are behavioural, and
FR-8.3 took two because its row names two surfaces.

The behavioural ones were checked by breaking the code rather than by watching
them pass. FR-7.3 was run against a clip queue capped at one and reported three
clips where five were due. FR-4.2's first version was run against generation
made to take the playback lock and **passed**, which is the failure the task
warned about: presence of a later clip is not overlap, because a service that
generates the whole array before playing satisfies it. Rewritten to assert
arrival against a snapshot, it fails that mutation.

**The durable queue**, FR-4.8 and FR-4.9. The queue is a directory now:
`$XDG_RUNTIME_DIR/skid/spool`, one entry per submission, written before `submit`
returns and taken in filename order. `SubmissionQueue` is gone, because two
queues would disagree.

Proved against the live service rather than only in tests: a real `speak` call,
then `kill -9` on the service, and the submission was still on disk afterwards.
It had already started playing, so the restart discarded it rather than replaying
it and said so in the log, which is the decided behaviour and not a bug.

## Owed, and not yet a task

**A cold read of the revised `docs/SPEC.md`.** The spec was reviewed twice at
`fd42bdf` and revised against both, and the only pass over the revision was by
one of its own reviewers checking their findings had landed. They said so
themselves and asked for a reader with no stake in them. That pass still found a
regression, FR-5.3, which is the argument for the one that is missing.

**A doc review**, `.reviews/doc-review.md`, scored 24 of 35 on 2026-08-28 and
is gitignored so it does not ship. Its three worst findings are fixed: PROJECT.md
went 559 lines to 192, the pytest command it printed now runs, and an inference
it called "Measured" is marked as one. What is left from it is small.

## Decided recently enough to restate

**One HTTP service under systemd, not two processes.** Decided deliberately. It
deleted a start protocol that had a lock file, a stale-socket
unlink and a bind-then-rename, which was the part of the spec nobody had run.
`docs/SPEC.md` carries the reasoning.

**A unix socket rather than a TCP port**, because reaching skid's tools means
making the machine speak and rewriting its config. FR-5.4.

**No mocks anywhere.** Settled when the question was put: install
kokoro and test against the real engine. The seams made it a non-question in the
end, because the queue and the player are units that never touch audio.

## Settled, and cheaper than it reads

**The 3.12 pin costs nothing, so widening it is not work waiting to be done.**
Told first-hand 2026-08-28: kokoro runs on 3.13 and 3.14 and has simply not had
a release since, so its declared `<3.13` is stale metadata rather than a real
ceiling. That makes the wording wrong in a few places and the situation fine.

**Nothing in skid's source needs an interpreter newer than 3.12.** No
free-threading, no 3.13 or 3.14 syntax, nothing from a newer stdlib. So sitting
on the older interpreter is a free choice rather than a concession, and the
right answer if kokoro's declaration ever does become binding is the one already
in place: install into an environment holding the interpreter kokoro accepts.

**That is what happens today, with no flag.** `uv tool install --editable` reads
`requires-python` from `pyproject.toml`, fetches 3.12 and builds the tool
environment on it, whatever the machine's default is. Measured 2026-08-28:

    python3 -V                                        3.14.7
    ~/.local/share/uv/tools/skid/bin/python -V         3.12.14
    ...bin/python -c 'import kokoro'                   imports

So the pin is the mechanism rather than an obstacle to one, and
`test_skid_runs_only_where_kokoro_does` asserts the containment that holds today
and fails on the day kokoro re-declares, which is the day to revisit the wording
of FR-1.7 rather than to carry a resolver override now.

Several documents say kokoro "refuses" 3.13. That is true of the metadata and
not of the software, and `docs/PROJECT.md` now says so.

## Open, and small

**Whether the greeting window is settable through a tool** as well as the config
file. FR-3.4 requires only that it is configurable, and FR-7.1 already says which
route would win. Nothing depends on it.

**The bound in FR-1.9**, the time after which a stuck player is killed, is
measured against real clips rather than guessed. About 15.5 characters per
second of audio, so the 300 second default admits about 4,660 characters and
cuts off anything longer mid-sentence. That is an essay rather than a summary,
so it is not reached by accident often.

Whether that is the right ceiling is the open half. Nothing caps a message's
length at submission, so the choice is between raising the bound, capping the
message, or accepting that an essay gets truncated. Nothing depends on it: the
watchdog does not, because playback pings regardless of length.

    chars  generate s  audio s        .ephemera/measure-clip-length.py
        5        0.35     1.27
      398        3.83    25.62
     1196       10.85    76.88

**`docs/SUPPRESSIONS.md` exists now**, carrying one entry: five `#nosec` marks
covering eight bandit findings about `subprocess`, with the question that was
put and the answer that was given. A file rather than the `docs/SUPPRESSIONS/`
directory this line used to anticipate, because one class of suppression is one
entry.

**Nothing is mocked**, and `docs/MOCKS/` still does not exist, correctly. There
are zero `noqa` and zero `type: ignore` in `src/` and `tests/`.

## Known and not blocking

**The package is at 78% and two entry points are most of the gap.** Measured
2026-08-28 with `.venv/bin/python -m coverage report`:

    src/skid/main.py       97 stmts   60 miss   35%
    src/skid/install.py   148 stmts   84 miss   36%
    TOTAL                 979 stmts  186 miss   78%

`say.py` was the third and is now 100%. **Nothing is watching this number.**
Traceability now reads 62 of 62 in both directions and says nothing about
coverage, because it measures requirement-to-test and test-to-requirement rather
than line-to-test: `install.py` sits at 36% with all fourteen of its rows
covered. The gate's `coverage` task runs Python tools from PATH, which cannot
import skid's dependencies, so it has never reported on this project.
`interfaces/30` holds
the decision about what to do, which is not simply "write more tests": both
files are entry points a test process does not reach by importing them, and
hard rule 5 bears on it in Go's spelling.

**The gate's `analyse` task cannot pass.** `pylint --recursive=y .` walks
`.venv` and does not return; skid's own code lints in 2 seconds. Not skid's to
fix, filed at `clank/inbox/toolbox/pylint-walks-the-virtualenv` with a repro.
Run the rest of the jig and read `result.yaml`.

With `--ignore=.venv,venv` skid's own code rates **9.83/10**, measured
2026-08-28 after the test fixtures moved into `tests/conftest.py`, which cleared
both `duplicate-code` findings.

**`docstrings` passes now**, at 99.4% measured 2026-08-28 over skid's own code.
It read 0.0% the day before, over an empty package. **`traceability` reports 48
of 48**, and every mark cites a row `REQUIREMENTS.md` defines: checked in both
directions, so no test cites a row that does not exist or one that is retired.

**`types` reports one error**, kokoro, which ships no `py.typed`. Nothing is
suppressed, because a mypy override needs a human's answer under hard rule 4.

wrench is fully typed and resolves, so its calls are checked. Its path
parameters take `str | os.PathLike[str]`, which is what skid passes.

**bandit reports five Low issues and zero High**, all of them `B404` and `B603`
in the installer and the player, which are what running commands looks like to a
scanner. Reading the tail of its output invites the opposite conclusion: the
summary prints severity and then confidence, so `High: 5` is the confidence
line.

**Both bandit tasks pass now**, by five `#nosec` marks registered in
`docs/SUPPRESSIONS.md`. Per-line rather than a threshold change or a tree-wide
skip, which is the narrowest of the three: a new
subprocess call still fails the gate until somebody looks at it.
