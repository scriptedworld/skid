# FR-8.5, one pass, and no re-examination

| ID | Requirement | |
|---|---|---|
| FR-8.5 | Substitution is a **single left-to-right scan**. At each position the entries are tried in file order and the first that matches there wins; the scan resumes after the text it produced. No entry examines what any substitution produced. | [D] |

Derived from FR-7.7 and FR-8.4. Regular expressions make three failures
possible, and this closes the two that ordering alone does not:

- **Overlap.** Two entries matching spans that intersect. The scan is at one
  position, so the match that begins earlier wins, and the later entry sees only
  what remains.
- **Self-match.** An entry whose replacement matches its own pattern. Resuming
  after the produced text is what stops it looping.

**Position first, file order second.** That pairing is the whole rule and it was
wrong here until 2026-08-27, when this row said "the earlier entry in the file
wins the overlapping region" while `docs/SPEC.md` said a left-to-right pass.
Those are two different priorities and they disagree on ordinary input: with
`b -> x` first and `ab -> Z` second, applied to `ab`, entry priority gives `ax`
and position priority gives `Z`.

**Not examining output also protects the entries from each other.** An entry
that spells a word phonetically produces letters nobody submitted, and a later
entry matching those letters would fire on something nobody wrote.

**It also rules out applying entries in sequence over the whole text**, entry one
everywhere, then entry two over the result. That reading is a natural one of
FR-8.4's "applied in file order" and it violates this row, because entry two
would see entry one's output.

FR-8.3 keeps all of it off what a caller submitted and what a log records. This
is about the single pass in between.

Corrected after the spec review at `fd42bdf`, which found the contradiction.
