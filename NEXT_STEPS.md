# skid, what is not done

Work lives in `~/.projects/clank/tasks/skid/`. This is what is not yet work: the
open decisions, and the things recent enough to be worth restating.

## The work that is agreed

**The installer.** `clank/tasks/skid/install/10-write-the-installer.ready`.
skid runs here and nowhere else, because everything was installed by hand on
2026-08-28. `docs/PROJECT.md` lists the five commands it owes.

Everything else in `docs/REQUIREMENTS/` has code and tests.

## Owed, and not yet a task

**A cold read of the revised `docs/SPEC.md`.** The spec was reviewed twice at
`fd42bdf` and revised against both, and the only pass over the revision was by
one of its own reviewers checking their findings had landed. They said so
themselves and asked for a reader with no stake in them. That pass still found a
regression, FR-5.3, which is the argument for the one that is missing.

**Eleven requirements have no test citing them**: FR-1.5, FR-1.6, FR-1.7,
FR-2.2, FR-4.2, FR-5.3, FR-5.4, FR-6.3, FR-7.3, FR-7.6 and FR-8.3. Measured
2026-08-28, 36 of 47 covered. Some are properties of the machine or of the
systemd units rather than of a function, so the work is deciding what a test for
each would read before writing any.

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

**`docstrings` passes now**, at 98.7% measured 2026-08-28 over skid's own code.
It read 0.0% the day before, over an empty package. **`traceability` reports 36
of 47**, which is a real number and the gap listed above.
