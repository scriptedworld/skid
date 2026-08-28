# skid, suppressions

Every `#nosec`, `noqa`, `type: ignore` or equivalent in this repository, with
the question that was asked and the answer that was given. **A suppression that
is not here is a defect**, because the register is the only thing standing
between a silenced check and nobody remembering why.

A file rather than a directory, which is what `NEXT_STEPS.md` anticipated. One
class of suppression is one entry, and a directory holding a single file buys
nothing until there are several.

## S-1, bandit's subprocess findings

**Seven marks covering eight findings, three rules, three files.** `B404` for
importing `subprocess`, `B603` for calling it without `shell=True`, and `B607`
for naming a program without an absolute path. The counts differ because the
test's one call site trips two rules at once.

    src/skid/install.py     B404   import subprocess
    src/skid/install.py     B603   the spaCy model check
    src/skid/install.py     B603   running one step of the plan
    src/skid/player.py      B404   import subprocess
    src/skid/player.py      B603   playing a clip
    tests/test_install.py   B404   import subprocess
    tests/test_install.py   B603, B607   systemd-analyze verify

Line numbers are deliberately not recorded. They go stale on the next edit and a
stale line number is worse than none, because it sends a reader to the wrong
call. `grep -rn nosec src/ tests/` is the current list and it is one command.

### The question put, 2026-08-28

> The gate's `security` task fails on bandit findings, all Low severity, all
> "you are using subprocess". They are inherent to the design: FR-1.3 says a
> subprocess plays the file, FR-7.5 makes the player a user-configured command
> line, and the installer runs commands. There is nothing to fix, so every
> option is a form of suppression. Raise the severity threshold, skip `B404` and
> `B603` tree-wide in `pyproject.toml`, or mark the individual call sites?

### The answer

> `#nosec` those subprocess warnings and ensure they are in SUPPRESSIONS.

Per-line marks, which is the narrowest of the three and the only one where **a
new subprocess call still fails the gate until somebody looks at it**. A
threshold change would stop enforcing every Low finding estate-wide; a tree-wide
skip would stop enforcing these two rules at any severity, including on code
nobody has written yet. Both were offered and neither was chosen.

The cost, stated because it is real: this spends skid's zero-suppression record.
Before today the tree carried no `nosec`, no `noqa` and no `type: ignore`.

### Which calls are forced, and which was chosen

Asked directly: why are there this many? Six of the seven are forced by the
design and one is a convenience, and the convenience is worth naming rather than
being covered by the general argument.

**Forced, because the work is running another program:**

    player.py       plays a clip                FR-1.3, and the whole design
    install.py      uv tool install             an external tool
    install.py      systemctl --user ...        an external tool
    install.py      claude mcp add / remove     an external tool
    install.py      checks en_core_web_sm       a DIFFERENT interpreter, so an
                                                in-process import cannot answer
    test_install.py systemd-analyze verify      an external tool

**Chosen:** the unit files are copied with `install -D -m 0644` where
`shutil.copy`, `mkdir` and `chmod` would do. It buys one thing, which is that
every step of the plan is an argv, so `--dry-run` prints exactly what will run
and the tests assert the sequence as data. A Python copy would make one step
describable only in prose and the plan no longer uniform.

**Removing it would not remove a single mark**, which is the honest reason it
stays. `install.py` shells out to `uv`, `systemctl` and `claude` regardless, so
it keeps its `B404` on the import and its `B603` on `run`. The count is driven
by which modules run programs at all, not by how many programs each one runs.

So the suppression is not paying for the convenience. If it were, the convenience
would go.

### Why the findings cannot be fixed

**They are correct and describe the design accurately.** skid's entire
output path is generate a file and run a player:

- **FR-1.3** a subprocess plays the file
- **FR-1.4** playback uses the default output device, which is what a player
  reaching the OS gets and what skid would lose by touching a device itself
- **FR-1.5** skid never talks to an audio device, stated on its own so it can be
  tested as one
- **FR-7.5** the player is `paplay` by default and a user-declared command line
  otherwise

`B603` asks whether the argument vector is untrusted. It is not. `player.py`
builds it from the configured command through `shlex.split`, which is the
mechanism FR-7.5 requires and a person's own config file rather than input from
a caller. `install.py` builds each `argv` as a literal tuple in `install_plan`,
asserted by `test_install.py` as data. Nothing reaching `subprocess` comes from
an MCP caller.

`B607` in the test is `systemd-analyze` by name. That is deliberate: the test
skips when it is not on PATH, so hard-coding a path would make the test assert
against a location rather than against the tool.

**Not shell=True, which is what would make these findings real.** No shell is
involved anywhere. The suppression says "we run subprocesses on purpose", not
"we are not worried about injection".

### What would make this entry wrong

A `subprocess` call whose argv comes from an MCP caller, or a `shell=True`
anywhere. Neither exists. If either appears, this entry does not cover it and
the new call site needs its own question rather than a copied mark.
