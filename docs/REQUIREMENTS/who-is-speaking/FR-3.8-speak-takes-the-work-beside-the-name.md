# FR-3.8, speak takes the work beside the name

| ID | Requirement | |
|---|---|---|
| FR-3.8 | `speak` accepts an optional `work` argument alongside `name` and `messages`, through the MCP tool, the service's route and `skid-say`. | [A] |

Optional because a caller with nothing to name should not have to invent
something, and because every shim already running predates the argument.
