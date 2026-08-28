# FR-5.3, a call fails rather than hangs

| ID | Requirement | |
|---|---|---|
| FR-5.3 | A call the backend does not answer within a bounded time fails as an error naming the backend. It never hangs. | [D] |

Derived from FR-5.2 and FR-4.5. The client is an MCP server and submitting
returns when the work is queued, so a caller that cannot reach the backend has
to be told, and told quickly, because the agent is waiting on the call.

**One rule covers two cases**, and only the first was ever written down:

- **Absent.** No backend, or one that died. Every caller meets this for the
  whole window between a crash and the next start.
- **Wedged.** Connected and not answering. `docs/SPEC.md` makes the socket path
  appear only once the model has loaded, so path presence means ready, and the
  stronger that assumption is the more a wedged backend costs when it happens.

A timeout naming the backend distinguishes both from a call that failed on its
own merits, which matters because FR-4.7's log lives in the backend and is
exactly what a caller cannot reach when this fires.

## Why it is a row rather than a line of spec

It was a line of spec, at `fd42bdf`: "the backend is unreachable, which
`skid-mcp` returns as a tool error rather than hanging". Rewriting that section
dropped it, and no requirement noticed, because none existed.

    git show fd42bdf:docs/SPEC.md | grep -c unreachable    1
    grep -c unreachable docs/SPEC.md                       0    (before this row)

Found by the verification pass on the revision. It is the same failure FR-4.4
was written for, one document up: a property that only prose held, lost in an
edit nobody could have caught by reading the edit.
