# FR-4.6, one failure does not cancel an array

| ID | Requirement | |
|---|---|---|
| FR-4.6 | A message that cannot be generated or played is reported and skipped. The rest of its array is still spoken, and the queue behind it still runs. | [D] |

Derived from FR-4.1 and FR-4.5. Text arrives in arrays and the caller has
already been told the work was accepted, so a failure part way through has
nobody to return to and must not take the rest of the array with it.

**Silence is the failure mode this rules out.** One bad clip stopping the queue
means every later submission from every caller is lost to a fault none of them
caused, and nothing about a quiet machine says which.

A submission that produced no audible output at all is worth reporting as a
whole, rather than only as a run of individual failures.

Raised by `docs/SPEC.md`.
