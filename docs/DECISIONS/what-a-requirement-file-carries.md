# What a requirement file carries

**The decision lives in `silo/docs/DECISIONS/what-a-requirement-file-carries.md`,
where it binds every repository.** Read it there. A full copy here would be a
second statement free to drift from it.

It was decided in skid on 2026-08-27, because skid migrated first and the shape
had to be something. silo verified it and promoted it at `92e93df`, against
skid `f8c5660`.

What is skid's own rather than the estate's:

- `docs/REQUIREMENTS/README.md` carries the preamble the retired
  `REQUIREMENTS.md` held, the status markers and what each category covers. The
  promoted decision permits that per repository rather than requiring it.
- The categories are the sections the retired document had, listed in that
  README.

~~skid has retired no requirement, so the open question in the promoted
decision, where the `## Retired` record lives once `REQUIREMENTS.md` is gone, is
not one skid can settle by measurement. The first repository here to retire an
id inherits it.~~

**Retested 2026-08-30 and false.** skid retired FR-2.2 at `884b0cd`, which was
already true when the line above was written and stayed unread for two days.

FACT 2026-08-30: **the `## Retired` record lives in
`docs/REQUIREMENTS/README.md`**, under a `## Retired` heading carrying the id,
the date, what absorbed it and why it went. That is skid answering the promoted
decision's open question by having done it, rather than by arguing about it.

    grep -A6 '^## Retired' docs/REQUIREMENTS/README.md

The choice has held through one more category being added, `a-voice-per-name` on
2026-08-30, taking the set to 71 rows across ten families. A retired id sitting
in the README rather than in the category directory it left means the directory
holds only live rows, so concatenating the tree reproduces exactly what the
checker parses.

Filed to silo at `clank/inbox/silo/where-the-retired-requirement-record-lives`,
because the open question is theirs to close.
