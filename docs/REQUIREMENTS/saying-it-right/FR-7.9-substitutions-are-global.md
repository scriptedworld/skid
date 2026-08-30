# FR-7.9, substitutions are global

| ID | Requirement | |
|---|---|---|
| FR-7.9 | Substitutions are **global**. One set applies whatever name submitted the text. | [A] |

Settled at the id the open question carried.

A word kokoro says wrongly is a property of kokoro rather than of who sent the
word, so a correction any caller makes helps every caller.

The case FR-7.9 raised, two engines wanting one word said differently, is
declined rather than unnoticed. Adding a per-name layer later costs one
migration of a file and a precedence rule; carrying that rule now would cost
every reader of the substitution set.
