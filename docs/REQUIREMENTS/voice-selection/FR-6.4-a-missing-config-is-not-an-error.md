# FR-6.4, a missing config is not an error

| ID | Requirement | |
|---|---|---|
| FR-6.4 | A missing config file is not an error. Defaults apply, and the file is created by the first write. | [D] |

Derived from FR-6.2 and FR-7.1. The config file is the record, and a record that
has to exist before anything runs makes a fresh install a configuration exercise
before it is a working one.

Every setting the file carries has a default, so the file says what differs from
them rather than restating them.

Raised by `docs/SPEC.md`.
