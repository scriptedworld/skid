# FR-2.2, the mechanism is unconstrained

| ID | Requirement | |
|---|---|---|
| FR-2.2 | Exclusion is held by a mutex, a lock file, or an equivalent. The mechanism is unconstrained; the property is not. | [A] |

An in-process mutex and a lock file differ in what they cover: a mutex holds
against threads in one process, a lock file against every process that agrees to
take it. Which is needed follows from FR-5.1's backend and from whether anything
outside it ever plays a clip.

What the lock covers is a separate question from what holds it, and it is the
sharper one. FR-7.3.
