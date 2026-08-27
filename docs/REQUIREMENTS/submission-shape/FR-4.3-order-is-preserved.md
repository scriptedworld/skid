# FR-4.3, order is preserved

| ID | Requirement | |
|---|---|---|
| FR-4.3 | Order is preserved: an array is spoken in the order given. | [D] |

Derived from FR-4.1. An array whose order is not kept is a set, and nothing
about submitting several messages at once implies giving up their sequence.

Generation may finish out of order under FR-4.2. Playback may not.
