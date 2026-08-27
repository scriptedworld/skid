# FR-5.1, a backend holds the model warm

| ID | Requirement | |
|---|---|---|
| FR-5.1 | A **backend process holds the model warm**, so a message does not pay model start-up before it is spoken. Wanted rather than required. | [A] |

Wanted rather than required, stated that way first-hand. A first pass that loads
the model per submission satisfies everything else here and is slower.

**Dropping it costs more than the start-up time.** An MCP with a supporting
background process is the criterion by which skid gets its own tree, so this
requirement and the repository boundary are one decision seen twice.
`../../PROJECT.md` carries it.

The cost it avoids is unmeasured, because kokoro is not installed
(FR-1.1). Measuring cold start against warm is what would turn this into a
number worth defending.
