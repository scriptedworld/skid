# skid, what is not done

Work lives in `~/.projects/clank/tasks/skid/`. This is what is not yet work: the
open decisions, and the things recent enough to be worth restating.

## The work that is agreed

Three ready tasks in `clank/tasks/skid/`, all fully specified.

**The MCP server moves into the stdio script.**
`resilience/40-the-mcp-server-moves-into-the-stdio-script.ready`. Designed with
the user 2026-08-28. The script becomes the MCP server and the service becomes
six plain HTTP routes, so no session id exists on either side and the wedge
class has nothing to go stale. Flask and waitress are chosen and declared;
waitress because it takes an already-bound socket, proved on the live socket
rather than assumed.

It supersedes much of `de3abb5` and `40eea92`, which recover from the wedge
rather than removing it, so that recovery code is not worth polishing. A smaller
fallback needing no service change is recorded in the same task: a fresh MCP
session per tool call, measured at two round trips of 0.00s each.

**The config becomes YAML, and wrench validates it and the spool.**
`data-files/10-validate-with-wrench-and-a-schema.ready`. Decided 2026-08-28 with
the user, who approved wrench's canonical form including its quoted keys.
`silo/docs/DECISIONS/yaml-everywhere-validated-against-the-decoded-structure.md`
says every structured file in the ecosystem is YAML; skid chose TOML 83 minutes
before that was recorded, so it predates it and is now the outlier.

Nothing blocks it: **no config file exists on this machine**, so there is
nothing to migrate. It drops `tomlkit` rather than adding a dependency, and
retires FR-7.8's comment clause and `docs/SPEC.md:289` with it.

**The systemd watchdog and the restart limit.**
`resilience/20-the-watchdog-and-the-restart-limit.ready`. `WatchdogUSec=0`
today, so a wedged service is undetected, and the start limit is systemd's
default, so five failures in ten seconds leaves it dead until somebody runs
`reset-failed`. Neither value was chosen.

Traceability reads 48 of 48, with nothing permanently red and no marker needed
in toolbox's checker.

## Not settled by use

**Nobody has heard skid mispronounce anything.** FACT 2026-08-28, from the user:
total real use is a handful of messages from silo and skid itself. So the
substitution surface, first-match-wins ordering, the literal-and-regex split and
FR-8.4 making file order load-bearing, is designed against an imagined need.

Treat those rows as settled by argument, not by evidence. The first real
mispronunciation somebody reaches for the config to fix is worth more than any
of the reasoning behind them.

## Landed since this file was last rewritten

**Traceability closed at 48 of 48.** Nine tests over the last eight rows, and
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

**One HTTP service under systemd, not two processes.** Decided 2026-08-27 with
the user. It deleted a start protocol that had a lock file, a stale-socket
unlink and a bind-then-rename, which was the part of the spec nobody had run.
`docs/SPEC.md` carries the reasoning.

**A unix socket rather than a TCP port**, because reaching skid's tools means
making the machine speak and rewriting its config. FR-5.4.

**No mocks anywhere.** Decided by the user when the question was put: install
kokoro and test against the real engine. The seams made it a non-question in the
end, because the queue and the player are units that never touch audio.

## Open, and needing a decision

**Whether to widen the interpreter pin past 3.12.** Told first-hand 2026-08-28:
kokoro runs on 3.13 and 3.14 and has simply not had a release since, so its
declared `<3.13` is stale metadata rather than a real ceiling.

That does not make the pin wrong. A resolver enforces what is declared, so
installing skid on 3.13 means overriding another project's stated range, and
FR-1.7 as written requires skid to sit inside what kokoro declares rather than
inside what it is known to tolerate. Widening is therefore a decision with two
halves: whether to carry a resolver override, and whether FR-1.7 should be
reworded to speak about support rather than declaration.

Nothing is blocked on it. `test_skid_runs_only_where_kokoro_does` asserts the
containment that holds today and fails on the day kokoro re-declares, which is
the day this gets easy.

Several documents say kokoro "refuses" 3.13. That is true of the metadata and
not of the software, and `docs/PROJECT.md` now says so.

## Open, and small

**Whether the greeting window is settable through a tool** as well as the config
file. FR-3.4 requires only that it is configurable, and FR-7.1 already says which
route would win. Nothing depends on it.

**The bound in FR-1.9**, the time after which a stuck player is killed. It wants
to be longer than any clip skid produces, and no clip length has been measured
beyond the 1.75 seconds of one short sentence.

**`docs/SUPPRESSIONS.md` exists now**, carrying one entry: five `#nosec` marks
covering eight bandit findings about `subprocess`, with the question that was
put and the answer that was given. A file rather than the `docs/SUPPRESSIONS/`
directory this line used to anticipate, because one class of suppression is one
entry.

**Nothing is mocked**, and `docs/MOCKS/` still does not exist, correctly. There
are zero `noqa` and zero `type: ignore` in `src/` and `tests/`.

## Known and not blocking

**The gate's `analyse` task cannot pass.** `pylint --recursive=y .` walks
`.venv` and does not return; skid's own code lints in 2 seconds. Not skid's to
fix, filed at `clank/inbox/toolbox/pylint-walks-the-virtualenv` with a repro.
Run the rest of the jig and read `result.yaml`.

**`docstrings` passes now**, at 99.3% measured 2026-08-28 over skid's own code.
It read 0.0% the day before, over an empty package. **`traceability` reports 48
of 48**, and every mark cites a row `REQUIREMENTS.md` defines: checked in both
directions, so no test cites a row that does not exist or one that is retired.

**bandit reports five Low issues and zero High**, all of them `B404` and `B603`
in the installer and the player, which are what running commands looks like to a
scanner. Reading the tail of its output invites the opposite conclusion: the
summary prints severity and then confidence, so `High: 5` is the confidence
line.

**Both bandit tasks pass now**, by five `#nosec` marks registered in
`docs/SUPPRESSIONS.md`. Per-line rather than a threshold change or a tree-wide
skip, which was the user's choice and is the narrowest of the three: a new
subprocess call still fails the gate until somebody looks at it.
