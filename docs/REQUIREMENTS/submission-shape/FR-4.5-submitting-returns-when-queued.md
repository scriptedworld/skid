# FR-4.5, submitting returns when queued

| ID | Requirement | |
|---|---|---|
| FR-4.5 | A submission returns to its caller once the work is queued, not once it has been heard. | [D] |

Derived from FR-7.2. An unbounded queue means the wait before a submission is
audible is unbounded, so a call that returned when the speech finished would put
that wait on the caller.

**The point of speaking is that the agent carries on.** A caller blocked until
its own audio finished would be serialised behind the thing meant to run beside
it, and two agents speaking would take turns working rather than turns talking.

The cost is that a caller learns its submission was accepted rather than that it
was heard. FR-1.5's two failure modes therefore surface in the backend rather
than at the call, which is what FR-4.6 is about.

Raised by `docs/SPEC.md`.

**"Queued" means written to disk, since 2026-08-28.** FR-4.8 makes the durable
write the thing this row returns after, which is what gives the promise
something behind it. Before that, queued meant accepted by a `deque` in one
process, so a restart lost work a caller had already been told was accepted.

The call is one small write slower and considerably more truthful.
