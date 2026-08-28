# skid, what is not done

Work lives in `~/.projects/clank/tasks/skid/`. This is what is not yet work: the
open decisions, and the things recent enough to be worth restating.

## The work that is agreed

**Test the eight uncovered rows.**
`clank/tasks/skid/traceability/10-test-the-eight-testable-rows.ready`. The task
carries a proposed test for each: three read a declaration file, four are
behavioural and two of those share a blocking-player seam, and FR-7.6 is tested
by asserting the measurement it rests on still holds.

Traceability reads 40 of 48. It reaches 48 of 48 when that task lands, with
nothing permanently red and no marker needed in toolbox's checker.

## Landed since this file was last rewritten

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

It is the only thing left in this section. The nine uncovered rows were here
until 2026-08-28 and are now a task and a question, above.

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

**`docstrings` passes now**, at 98.9% measured 2026-08-28 over skid's own code.
It read 0.0% the day before, over an empty package. **`traceability` reports 40
of 48**, which is a real number and the gap listed above.

**bandit reports five Low issues and zero High**, all of them `B404` and `B603`
in the installer and the player, which are what running commands looks like to a
scanner. Reading the tail of its output invites the opposite conclusion: the
summary prints severity and then confidence, so `High: 5` is the confidence
line.

**Both bandit tasks pass now**, by five `#nosec` marks registered in
`docs/SUPPRESSIONS.md`. Per-line rather than a threshold change or a tree-wide
skip, which was the user's choice and is the narrowest of the three: a new
subprocess call still fails the gate until somebody looks at it.
