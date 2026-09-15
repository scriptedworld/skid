# FR-2.1, at most one clip is audible

| ID | Requirement | |
|---|---|---|
| FR-2.1 | **At most one clip is audible at any moment.** Two callers submitting at once produce sequential speech, never overlap. | [A] |

Two agents speaking over each other is worse than either waiting.

The requirement forbids overlap and says nothing about what a second submission
does instead. FR-7.2 settles that: it queues.

It says nothing about what holds the exclusion either, and that is on purpose.
A mutex, a lock file or anything equivalent will do. What matters is that the
two differ in what they cover: a mutex holds against
threads in one process, a lock file against every process that agrees to take
it. Which is needed follows from FR-5.1's backend and from whether anything
outside it ever plays a clip.

What the lock covers is a separate question from what holds it, and FR-7.3
settles that one: playback alone.

This paragraph absorbed the retired FR-2.2. It is guidance and not a constraint,
so it belongs beside the requirement it qualifies instead of standing as one.
See `## Retired` in `../README.md`.
