# FR-1.9, playback that does not end is ended

| ID | Requirement | |
|---|---|---|
| FR-1.9 | A player that has not exited within a bounded time is killed. The clip is recorded as failed and the lock is released. | [D] |

Derived from FR-2.1 and FR-4.6. A player that neither plays nor exits holds the
playback lock forever, and FR-2.1 is then satisfied in the worst possible way:
nothing is ever audible again.

**Everything else compounds it.** FR-4.5 keeps accepting submissions, FR-7.2
refuses to reject them, and FR-7.3 keeps generating ahead of a playhead that has
stopped. The machine grows a queue and a pile of clips and says nothing.

The case is ordinary rather than exotic: a Bluetooth sink disappearing mid-clip,
or the sound server restarting under a running player.

The bound is longer than any clip skid produces, so it is a stuck-process
detector rather than a playback policy.

Raised by the spec review at `fd42bdf`.
