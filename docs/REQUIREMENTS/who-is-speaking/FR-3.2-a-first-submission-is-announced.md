# FR-3.2, a first submission is announced

| ID | Requirement | |
|---|---|---|
| FR-3.2 | If a submission is the **first within `x` seconds** for its name and its work together, the spoken output is prefixed `Hi, [name] here, in [work].`, or `Hi, [name] here.` where the submission names no work. | [A] |

The window is per name and work, so one agent talking continuously does not
suppress another agent's announcement, and a name that starts speaking on new
work is announced again however recently it spoke. I asked for the work in the
line because, with sessions running across projects, a name alone no longer
says where. FR-3.7 says what the work is.

`x` is FR-3.4, and FR-7.4 sets it to 30 seconds from the end of the last clip
spoken for that name and work.
