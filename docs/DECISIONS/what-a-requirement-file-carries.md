# What a requirement file carries

The general shape of a requirement file is not skid's to state. It binds every
project and lives in silo, at
`docs/DECISIONS/what-a-requirement-file-carries.md`. A full copy would be a
second statement free to drift from that one.

What follows is skid's own part rather than the general rule:

- `docs/REQUIREMENTS/README.md` carries the preamble the retired
  `REQUIREMENTS.md` held, the status markers and what each category covers. The
  promoted decision permits that per repository rather than requiring it.
- The categories are the sections the retired document had, listed in that
  README.

- The `## Retired` record lives in `docs/REQUIREMENTS/README.md`, under a
  `## Retired` heading carrying the id, the date, what absorbed it and why it
  went. FR-2.2, retired at `ed9ee97`, is recorded there. This is skid's answer
  to the promoted decision's open question of where that record lives once
  `REQUIREMENTS.md` is gone.

      grep -A6 '^## Retired' docs/REQUIREMENTS/README.md

A retired id sitting in the README, and not in the category directory it left,
means the directory holds only live rows, so concatenating the tree reproduces
exactly what the checker parses.

Where the retired record belongs is an open question for the general rule and
not for skid, and it is filed as one.
