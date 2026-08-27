# FR-8.3, substitution changes nothing recorded

| ID | Requirement | |
|---|---|---|
| FR-8.3 | Substitution happens on the way to the engine and changes nothing a caller submitted or a log records. | [D] |

Derived from FR-8.2. A replacement that is not a real spelling would make a log
unreadable and a caller's own text wrong, so the substituted form exists between
skid and kokoro and nowhere else.
