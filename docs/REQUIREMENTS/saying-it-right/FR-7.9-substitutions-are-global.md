# FR-7.9, substitutions are global

| ID | Requirement | |
|---|---|---|
| FR-7.9 | Substitutions are **global**. One set applies whatever name submitted the text. | [A] |

A word kokoro says wrongly is a property of kokoro rather than of who sent the
word, so a correction any caller makes helps every caller.

Two engines wanting one word said differently is a case this row declines on
purpose. Adding a per-name layer later costs one
migration of a file and a precedence rule; carrying that rule now would cost
every reader of the substitution set.
