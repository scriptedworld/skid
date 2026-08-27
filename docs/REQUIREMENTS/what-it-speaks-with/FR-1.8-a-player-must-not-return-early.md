# FR-1.8, a player must not return early

| ID | Requirement | |
|---|---|---|
| FR-1.8 | A configured player must not exit before its clip is inaudible. **FR-2.1 holds only for players that meet this.** | [D] |

Derived from FR-2.1 and FR-7.5, which pull against each other and were never
made to say so.

Exclusion is the player subprocess running under the lock, so the lock is
released when the player exits. A command that returns before its audio finishes,
one that backgrounds itself, or one that hands off to a daemon releases the lock
early and two clips overlap. That is the one thing FR-2.1 forbids.

**FR-7.5 deliberately allows any command line**, so skid cannot enforce this and
does not try. It is stated for the same reason FR-7.5 already states the other
one: `aplay` is signed off as the user's choice to break FR-1.4 with. Nothing had
signed off breaking FR-2.1, so it read as impossible rather than as permitted.

Raised by the spec review at `fd42bdf`.
