# FR-9.10, a step that finds what it wanted has succeeded

| ID | Requirement | |
|---|---|---|
| FR-9.10 | A step that finds the world **already in the state it wanted** has succeeded. Running an install twice is not a failure. | [A] |

An installer that cannot be re-run is one nobody re-runs. The exit status cannot
carry this: `claude mcp add` exits 1 on a name already registered and
`claude mcp remove` exits non-zero on one that is not, so a first install and a
re-run would each be called a failure in turn. Each such step names the output
substring that means already-so.
