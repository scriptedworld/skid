# FR-3.6, the quiet table is not persisted

| ID | Requirement | |
|---|---|---|
| FR-3.6 | The per-name record of when a name last finished speaking is held in memory only. A restart costs at most one extra greeting per name. | [D] |

Derived from FR-3.2 and FR-7.4, which are both satisfied whether the table
survives a restart or not, and which sound different when it does not.

The choice is stated as a requirement rather than left in the spec because it is
audible. Thirty seconds of state is not worth a file, and the cost of losing it
is one greeting that a listener would have heard anyway on any other day.

Raised by the spec review at `fd42bdf`, as the fifth property the reverse trace
turned up.
