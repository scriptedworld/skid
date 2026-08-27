# FR-7.7, a pattern declares its kind

| ID | Requirement | |
|---|---|---|
| FR-7.7 | Each substitution entry **declares whether its pattern is a literal or a regular expression**. Both kinds are supported. | [A] |

Settled 2026-08-27, at the id the open question carried.

The literal kind covers FR-8.2's stated purpose with no rules to learn. The
regular expression kind is there for what a literal cannot reach, and it is
opt-in per entry rather than the default reading of every pattern.

## What it obliges, and where each obligation went

Supporting regular expressions brings three problems that literals do not have.
Naming them is what stops them being discovered by being bitten:

- **Ordering.** FR-8.4. The set lives in a file and is applied in file order, so
  reordering is editing the file.
- **Overlap and self-match.** FR-8.5. One pass, left to right, and what a
  replacement produces is not examined again.

Neither rule is specific to regular expressions. Stating them once means the two
kinds behave the same way, so an entry's kind changes what it matches and
nothing about when it runs.
