# FR-8.5, one pass, and no re-examination

| ID | Requirement | |
|---|---|---|
| FR-8.5 | Substitution is a **single left-to-right pass**. Text a substitution produces is not examined by any later entry, and no entry can match its own output. | [D] |

Derived from FR-7.7 and FR-8.4. Regular expressions make three failures
possible, and this row closes the two that ordering does not:

- **Overlap.** Two entries matching spans that intersect. The earlier entry in
  the file wins the overlapping region, and the later one sees only what is
  left.
- **Self-match.** An entry whose replacement matches its own pattern. Without
  this row it loops.

**Not examining output also protects the substitutions from each other.** An
entry that spells a word phonetically produces letters that were never in the
submitted text, and a later entry matching those letters would be firing on
something nobody wrote.

FR-8.3 already keeps all of this off what a caller submitted and what a log
records. This is about the single pass between them.
