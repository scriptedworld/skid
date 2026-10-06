# FR-3.9, a submission naming no work is announced by name alone

| ID | Requirement | |
|---|---|---|
| FR-3.9 | A submission that names no work is accepted and spoken, and its greeting is the name alone. | [A] |

A shim lives as long as its session, so after a deploy every session started
before it still calls `speak` without `work` until it clears. Refusing those
would take `speak` away from every running agent at once, which is what the
shim split exists to prevent.
