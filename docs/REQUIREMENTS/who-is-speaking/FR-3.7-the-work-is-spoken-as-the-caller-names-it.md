# FR-3.7, the work is spoken as the caller names it

| ID | Requirement | |
|---|---|---|
| FR-3.7 | The work in a greeting is exactly the text the caller passed. skid derives no work of its own, from a directory, a roster or anything else. | [A] |

I ruled this to keep it simple. The caller knows what it is working on and
says so: a project, a directory, the home directory, whatever describes it.
skid speaks what it is given.

A derivation was considered and dropped: each shim runs in its session's
working directory, and the roster could turn that into a project name. It
would have tied skid to one machine's layout and named a subagent with its
parent's directory.
