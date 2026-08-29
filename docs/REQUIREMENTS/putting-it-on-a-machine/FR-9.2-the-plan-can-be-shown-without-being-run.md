# FR-9.2, the plan can be shown without being run

| ID | Requirement | |
|---|---|---|
| FR-9.2 | The whole plan can be **shown before it is run**, and showing it changes nothing on the machine. | [A] |

An installer is a thing a person is asked to trust with their home directory.
Showing exactly what will run, before anything runs, is what makes that
trust checkable rather than requested.

Derived nothing and constrains directly: a dry run that performed even one step
would be worse than none, because it would be a promise of safety that is not
kept.
