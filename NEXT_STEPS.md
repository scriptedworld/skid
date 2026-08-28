# skid, what is not done

Work lives in `~/.projects/clank/tasks/skid/`. This is what is not yet work: the
open decisions, and the things recent enough to be worth restating.

## The work that is agreed

**Nothing.** The installer landed on 2026-08-28 and the task tree for skid is
empty of anything `.ready`, `.blocked` or `.questions`.

## Owed, and not yet a task

**A cold read of the revised `docs/SPEC.md`.** The spec was reviewed twice at
`fd42bdf` and revised against both, and the only pass over the revision was by
one of its own reviewers checking their findings had landed. They said so
themselves and asked for a reader with no stake in them. That pass still found a
regression, FR-5.3, which is the argument for the one that is missing.

**Nine requirements have no test citing them**: FR-1.5, FR-1.6, FR-1.7, FR-2.2,
FR-4.2, FR-6.3, FR-7.3, FR-7.6 and FR-8.3. Measured 2026-08-28, 38 of 47
covered. Some are properties of the machine rather than of a function, so the
work is deciding what a test for each would read before writing any.

FR-5.3 and FR-5.4 came off that list with the installer, by testing the systemd
units as the data they are. That is the shape to try on the rest before
concluding a requirement is untestable.

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

**Where `docs/MOCKS/` and `docs/SUPPRESSIONS/` would go if ever needed.** Neither
exists, correctly: nothing is mocked and nothing is silenced. There are zero
`noqa` and zero `type: ignore` in `src/` and `tests/` as of 2026-08-28.

## Known and not blocking

**The gate's `analyse` task cannot pass.** `pylint --recursive=y .` walks
`.venv` and does not return; skid's own code lints in 2 seconds. Not skid's to
fix, filed at `clank/inbox/toolbox/pylint-walks-the-virtualenv` with a repro.
Run the rest of the jig and read `result.yaml`.

**`docstrings` passes now**, at 98.9% measured 2026-08-28 over skid's own code.
It read 0.0% the day before, over an empty package. **`traceability` reports 38
of 47**, which is a real number and the gap listed above.

**bandit reports five Low issues and zero High**, all of them `B404` and `B603`
in the installer, which are what running commands looks like to a scanner.
Reading the tail of its output invites the opposite conclusion: the summary
prints severity and then confidence, so `High: 5` is the confidence line. There
are zero `#nosec` in the tree.
