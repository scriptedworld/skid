# FR-7.8, substitutions persist to the config

| ID | Requirement | |
|---|---|---|
| FR-7.8 | Substitutions live in the config file as well as the tool, and the file is the record. A substitution declared through the MCP tool is written through to it and survives a restart. | [A] |

Settled 2026-08-27, at the id the open question carried, and it answers both
halves: the substitutions get a config route, and the file is authoritative.

A pronunciation set is the more painful thing to lose, which is what the
question said and what the answer follows.

FR-8.4 is the ordering that follows from the set living in a file.
