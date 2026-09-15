# What a requirement file carries

The general shape of a requirement file is not skid's to state: it was settled
here first, because skid migrated first and the shape had to be something, and
then promoted to where it binds every project. A full copy would be a second
statement free to drift from that one.

What follows is skid's own part rather than the general rule:

- `docs/REQUIREMENTS/README.md` carries the preamble the retired
  `REQUIREMENTS.md` held, the status markers and what each category covers. The
  promoted decision permits that per repository rather than requiring it.
- The categories are the sections the retired document had, listed in that
  README.

- The `## Retired` record lives in `docs/REQUIREMENTS/README.md`, under a
  `## Retired` heading carrying the id, the date, what absorbed it and why it
  went. skid retired FR-2.2 at `884b0cd`, so this answers the promoted
  decision's open question, where that record lives once `REQUIREMENTS.md` is
  gone, by having done it.

      grep -A6 '^## Retired' docs/REQUIREMENTS/README.md

A retired id sitting in the README, and not in the category directory it left,
means the directory holds only live rows, so concatenating the tree reproduces
exactly what the checker parses. That has held through adding a category,
`a-voice-per-name`, which took the set to 71 rows across ten families.

Where the retired record belongs is an open question for the general rule and
not for skid, and it is filed as one.
