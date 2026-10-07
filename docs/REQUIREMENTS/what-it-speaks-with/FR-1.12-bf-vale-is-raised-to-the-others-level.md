# FR-1.12, bf_vale is raised to the others' level

| ID | Requirement | |
|---|---|---|
| FR-1.12 | bf_vale's audio is multiplied by 1.25 before it is written, and no other voice's is changed. | [A] |

I asked for bf_vale's level to be raised to match the rest. 1.25 is the
measured ratio, rounded down: on the v1.1-zh model, the mean RMS of six other
voices over three sentences each was 1.264 times bf_vale's. Its loudest
sample at this gain is 0.32 of full scale, so nothing clips.

A gain on the samples is the whole of it. skid still sets no volume and opens
no device, FR-1.5.
