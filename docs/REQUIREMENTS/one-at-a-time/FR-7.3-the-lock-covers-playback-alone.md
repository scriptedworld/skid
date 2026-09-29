# FR-7.3, the lock covers playback alone

| ID | Requirement | |
|---|---|---|
| FR-7.3 | The lock covers **playback alone**. Generation runs ahead of the speaker without taking it, and without a bound on how far ahead it runs. | [A] |

Covering generation as well would satisfy FR-2.1 and destroy FR-4.2, and it
would do it silently: the speech comes out correct, sequential and slow, and
nothing about listening to it says the preparation was serialised too.

## Unbounded is chosen, and what it costs

Depth was the open half, and the answer is that generation runs as far ahead as
it can. A long array therefore holds every clip it has produced before the
second one is heard, and with FR-7.2's unbounded queue nothing caps the total.

That cost is part of the choice, so it is not an oversight to design around
later.
