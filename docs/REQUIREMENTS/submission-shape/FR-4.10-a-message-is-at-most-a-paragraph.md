# FR-4.10, a message is at most a paragraph

| ID | Requirement | |
|---|---|---|
| FR-4.10 | A single message is refused above `skid_contract.MESSAGE_CHARS` characters, at the tool, with nothing queued. A caller wanting more sends more messages. | [D] |

Derived from FR-1.9, which bounds how long a player may run, and FR-4.5, which
returns before anything has been spoken.

Those two together made a long message fail silently. A message becomes one clip,
FR-1.9 kills a player at 300 seconds, and at about 15.5 characters per second of
audio that cuts a clip off mid-sentence at roughly 4,660 characters. Nothing
capped a message at submission, so the ceiling was reachable without abuse, and
the caller had already been told its submission was queued.

## Why a refusal rather than a longer bound or a split

Raising FR-1.9 was the obvious move and is wrong: it is a stuck-process detector,
so every second added is a second a genuinely stuck player holds the machine
silent.

Splitting a long message for the caller was considered and refused. It would mean
skid choosing where a sentence ends, and a split in the wrong place is heard.

So the caller is told. A refusal at the tool reaches somebody who can act on it,
which is the same argument FR-6.5 makes about a voice that would silence skid.

## The number is a preference, and the shape of it is not

`MESSAGE_CHARS` is 1000, chosen so that a caller sends a paragraph at a time and
four paragraphs are four messages or four calls. Its docstring carries the
derivation.

What is not a preference is that the limit sits well below the truncation point.
Setting it at 4,660 would place the bound exactly at the failure it exists to
prevent, leaving no margin for a slower voice or a longer pause.

## It caps a message, not a submission

An array may be as long as the caller likes, because each element is its own clip
and each is separately bounded. FR-4.1 keeps the array, FR-4.3 keeps its order
and FR-4.4 speaks it to completion, and none of that changes.
