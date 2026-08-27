# skid, Requirements

What must be true of voice output. Stated 2026-08-27 and recorded before
anything is designed, so the spec is derived from these rather than the reverse.

*Derives from:* stated requirements, first-hand. Nothing is built.

Requirements are stated as observable properties: what is true of a run, not how
anything is arranged.

One file per requirement, named for its id and its slug, under a category
directory named for the section it came from. The layout is ruled in
`silo/docs/DECISIONS/requirements-are-a-directory.md`; what goes inside a file is
`../DECISIONS/what-a-requirement-file-carries.md`.

## Status markers

`[A]` traces to something stated first-hand. `[D]` is derived from one. `[A/D]`
is both. `[?]` is an open question, recorded so it is not lost and carrying no
test yet.

Settled means testable, and the exemption is claimed rather than granted by
omission: only `[?]` is exempt from needing a test that cites it.

## The categories

    what-it-speaks-with   kokoro, a file, a player, the default device, the
                          interpreter kokoro will run under
    one-at-a-time         no overlap, the mechanism, the lock, the queue
    who-is-speaking       the name, and announcing it once
    submission-shape      an array, prepared ahead, spoken in order
    warm                  the backend, and the MCP server
    voice-selection       two routes to one setting, and which is the record
    saying-it-right       pronunciation substitutions

**A category is a subject, not a number range.** `FR-7` was the open set rather
than a seventh subject, and a question closes at the id it already carried,
because closing one is a decision against a row that exists. Its file then moves
into the category its answer belongs to. So `one-at-a-time` holds FR-2.1,
FR-2.2, FR-7.2 and FR-7.3.

**Nothing is open.** All nine of FR-7 closed on 2026-08-27, and the `open/`
category is gone rather than kept empty. An empty directory at a standard path
reads as a lost file.
