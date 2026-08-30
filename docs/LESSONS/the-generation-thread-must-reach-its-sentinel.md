# The generation thread must reach its sentinel

Playback blocks on `clips.get()` and stops only when it takes `STOP`. `STOP` is
put by `_generate_into`, at the end, in the other thread. So **any exception
raised in that thread before the loop is a wedged service**, not a failed
submission: the player waits on a queue nothing will ever fill, the serve loop
never returns, and `wait_idle` never comes back.

Met 2026-08-30 while adding per-name voice assignment. `_apply_voice` runs at
the top of `_generate_into`, and it calls `Generator.set_voice`, which raises
`ValueError` for a voice kokoro does not know. A config naming
`voice: jf_alpha` would have hung the machine rather than skipping a clip.

**Nothing in the type system or the tests would have caught it.** The failure
needs a config a person hand-edited, so no test that builds its own config
reaches it, and a hang reads as a slow test rather than as a defect.

## What to do

Put the work that can fail **inside** the loop's `try`, where the existing
handler already converts a failure into a skipped clip and a recorded line. Or,
where it genuinely has to run first, make it total:

    try:
        self._parts.generator.set_voice(wanted, pipeline)
    except ValueError as exc:
        self._record_failure(f"voice not applied for {name}: {exc}")

That leaves the generator on whatever it already had, which is a wrong voice for
one submission rather than silence for every submission after it.

**The general shape: a thread that signals completion out of band owes that
signal on every path.** A `finally` putting `STOP` would be the structural fix
and is worth considering if a third thing ever needs to run before the loop.

## Why the defensive version is not over-engineering

FR-6.5 refuses a bad voice at the tool, where the caller is present to be told.
It cannot refuse one that arrives by a person editing the config file, because
nobody is standing there. The two routes to the same setting have different
audiences, and the file route is the one with no error path back to a human.
`docs/REQUIREMENTS/voice-selection/FR-6.5-a-setting-that-would-silence-skid-is-refused.md`
covers the tool half only.
