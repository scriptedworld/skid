# FR-7.1, a tool-set voice persists

| ID | Requirement | |
|---|---|---|
| FR-7.1 | **The config file is the record.** A voice set through the MCP tool is written through to it and survives a restart. | [A] |

Settled at the id the open question carried. It answers FR-6.3's
remaining half: both routes reach one setting, and the file is the one that
holds it.

FR-7.8 is the same answer for the pronunciation substitutions.

## What it obliges

Writing to a file a person owns and edits. The ordering in it is the writer's to
preserve, not to normalise away, which is a real cost of putting the record
there and not in a file skid owns alone. FR-8.4 is that ordering, and it
survives on its own terms: a YAML list keeps its order in the decoded structure,
so nothing has to preserve formatting to honour it.

It does not oblige preserving comments. That would need a style-preserving round
trip, and comments are not the only place a reason can live:
`docs/config.sample.yaml` carries the explanations and the live file carries
values, so the live file is emitted canonically.
