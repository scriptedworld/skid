# FR-9.3, nothing is written outside the user's home

| ID | Requirement | |
|---|---|---|
| FR-9.3 | Every path an install writes is **inside the user's own home**, and no step requires root. | [A] |

This is the property that makes an installer for this service an ordinary thing
to run. An installer needing root is one a person has to read before trusting,
and few do.

It also bounds the blame. Everything skid installs can be removed by the user
who installed it, which is what FR-9.13 rests on.

**Every destination is a parameter**, so the plan can be pointed at a temporary
directory and the paths asserted. A destination that defaulted to the real home
at the point of use would make this untestable without writing to the tester's
home, which is the same thing as not testing it.
