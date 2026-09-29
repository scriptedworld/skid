# FR-7.8, substitutions persist to the config

| ID | Requirement | |
|---|---|---|
| FR-7.8 | Substitutions live in the config file as well as the tool, and the file is the record. A substitution declared through the MCP tool is written through to it and survives a restart. | [A] |

It answers both halves of the question: the substitutions get a config route,
and the file is authoritative.

A pronunciation set is the more painful thing to lose, so the file is the
record.

FR-8.4 is the ordering that follows from the set living in a file.
