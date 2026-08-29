# FR-9.10, a step that finds what it wanted has succeeded

| ID | Requirement | |
|---|---|---|
| FR-9.10 | A step that finds the world **already in the state it wanted** has succeeded. Running an install twice is not a failure. | [A] |

An installer that cannot be re-run is one nobody re-runs, so it stops being the
way skid is installed and the hand-run steps come back.

**The exit status cannot carry this, so the output is read.** Measured
2026-08-28: `claude mcp add` exits 1 when the name is already registered, and
`claude mcp remove` exits non-zero when there is nothing to remove. A first
install and a re-run would each be called a failure, in turn, by anything
reading only the status.

Each such step declares the substring in the command's own output that means
already-so, which makes it **idempotent by inspection rather than by hope**: a
reader can see which steps tolerate what, and a step with no tolerance is one
that genuinely must succeed.
