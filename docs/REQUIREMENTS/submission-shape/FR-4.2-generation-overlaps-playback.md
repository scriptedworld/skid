# FR-4.2, generation overlaps playback

| ID | Requirement | |
|---|---|---|
| FR-4.2 | While one message is being spoken, **the rest are being prepared**. Generation and playback overlap. | [A] |

This and FR-2.1 together are what FR-7.3 is about: one lock cannot cover
generation and playback both without serialising the thing this requirement
exists to make parallel.
