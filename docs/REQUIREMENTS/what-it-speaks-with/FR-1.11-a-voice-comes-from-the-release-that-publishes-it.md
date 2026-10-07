# FR-1.11, a voice comes from the release that publishes it

| ID | Requirement | |
|---|---|---|
| FR-1.11 | af_maple, af_sol and bf_vale are loaded from `hexgrad/Kokoro-82M-v1.1-zh`, and every other voice from `hexgrad/Kokoro-82M`. | [D] |

Derived from FR-1.10 and FR-10.1. kokoro fetches a voice pack from the
model's own repository, and v1.1-zh publishes only those three English voices
and a hundred Chinese ones. Left to kokoro, every other voice on the shortlist
would fail to load. Both releases' packs have the same shape and run on the
v1.1-zh model.
