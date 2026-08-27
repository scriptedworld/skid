# FR-6.3, both routes reach one setting

| ID | Requirement | |
|---|---|---|
| FR-6.3 | Both routes reach the same setting. Neither is a separate copy. | [D] |

Derived from FR-6.1 and FR-6.2. Two routes to one named thing that do not agree
is a defect however it is arrived at, and the observable property is that
setting the voice by either route changes what the next clip is spoken in.

Which route is the record when they disagree is FR-7.1, and it is the config
file. This requirement rules out the third case on its own, where each route
keeps a copy and neither is wrong.
