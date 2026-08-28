# skid, what is not done

Work lives in `~/.projects/clank/tasks/skid/`. This is what is not yet work: the
open decisions, and the things recent enough to be worth restating.

## The one piece of work

**The installer.** `clank/tasks/skid/install/10-write-the-installer.ready`.
skid runs here and nowhere else, because everything was installed by hand on
2026-08-28. `docs/PROJECT.md` lists the five commands it owes.

Everything else in `docs/REQUIREMENTS/` has code and tests.

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

**Two tasks fail honestly** and will keep failing until there is more code:
`docstrings` at 0.0% over one package, and `traceability`, which now reports
real coverage rather than nothing.
