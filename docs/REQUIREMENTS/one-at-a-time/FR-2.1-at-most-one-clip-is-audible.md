# FR-2.1, at most one clip is audible

| ID | Requirement | |
|---|---|---|
| FR-2.1 | **At most one clip is audible at any moment.** Two callers submitting at once produce sequential speech, never overlap. | [A] |

Two agents speaking over each other is worse than either waiting.

The requirement forbids overlap and says nothing about what a second submission
does instead. FR-7.2 settles that: it queues.

**It says nothing about what holds the exclusion either, and that is on
purpose.** A mutex, a lock file or anything equivalent will do. The two differ
in what they cover, which is the part worth keeping: a mutex holds against
threads in one process, a lock file against every process that agrees to take
it. Which is needed follows from FR-5.1's backend and from whether anything
outside it ever plays a clip.

What the lock covers is a separate question from what holds it, and FR-7.3
settles that one: playback alone.

This paragraph was FR-2.2 until 2026-08-28. It is guidance rather than a
constraint, so it belongs beside the requirement it qualifies rather than
standing as one. See `## Retired` in `../README.md`.
