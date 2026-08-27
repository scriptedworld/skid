# FR-8.4, the set is a file, and file order is the order

| ID | Requirement | |
|---|---|---|
| FR-8.4 | The substitutions are written to a file, and are applied **in the order they appear in it**. Changing the order means reordering the file. | [A] |

Stated 2026-08-27, when FR-7.7 admitted regular expressions and made ordering
something that has to be decided.

**The order is visible and editable in the same place the entries are.** No
priority field, no sort by specificity, no implicit rule about which of two
matching patterns wins. The file is read top to bottom, so a person fixing an
interaction between two entries fixes it by moving a line.

That is also what makes FR-7.8's write-through obligation concrete: an entry
added by the MCP tool lands at a position in a file somebody may reorder later.
