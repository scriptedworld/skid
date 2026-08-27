# FR-1.5, skid never talks to an audio device

| ID | Requirement | |
|---|---|---|
| FR-1.5 | **skid never talks to an audio device directly.** Device handling belongs to the player it invokes. | [A] |

This is what FR-1.2, FR-1.3 and FR-1.4 add up to, stated as its own property so
it can be tested as one: no audio library is imported, no device is opened, no
mixing or volume is done here.

The failure modes it buys are a missing player and a bad file. The ones it
refuses are an audio stack that has to be reasoned about.
