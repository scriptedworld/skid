# FR-7.3, does the lock cover generation

| ID | Question | |
|---|---|---|
| FR-7.3 | Does the lock cover generation as well as playback, or playback alone? FR-4.2 wants generation to overlap with speech, which means the lock cannot cover both. | [?] |

Open. Carries no test until it closes.

The sharpest of the nine, because getting it wrong is silent: a lock taken
around generation and playback together satisfies FR-2.1 exactly and quietly
serialises what FR-4.2 exists to make parallel. Nothing about the audible output
says which happened.

`clank/tasks/skid/concurrency/10-what-the-lock-covers.questions`
