# FR-6.5, a setting that would silence skid is refused

| ID | Requirement | |
|---|---|---|
| FR-6.5 | A value submitted through a tool is validated before it is written. A setting that would stop skid speaking is refused, and nothing is persisted. | [D] |

Derived from FR-7.1 and FR-7.8, which make the config the record, and FR-4.5,
which returns before anything has been spoken.

Those two together make an unvalidated write permanent and invisible. A
voice name with a typo is accepted, written to the record, and then every
generation fails. Each failure is skipped under FR-4.6, the caller has already
been told its submission was accepted, and the record survives every restart. One
call silences the machine until a person finds the file.

An invalid regular expression in a substitution does the same.

Refusing at the tool is the only point where the caller is still there to be
told.

## A real voice that will not render here is the same failure

A typo is the easy half. Thirteen of kokoro's 54 voices need a misaki language
pack that is not installed, so they are real names that pass a membership test
against `generation.VOICES` and then render nothing. The outcome is identical to
the typo, and the name looks correct in the file afterwards.

So the shortlist is what a voice is measured against. FR-10.1 makes it the
statement of which voices are available here, which is a claim about this
machine where kokoro's list is a claim about kokoro, and it follows a language
pack being installed or removed without anything being edited.

FR-10.7 makes `(voice, pipeline)` the pair that has to render, so a voice
accepted because the shortlist lists it is spoken through the pipeline that
entry declares. Inferring one from the voice id's first letter would reach the
phonemiser the entry was written to avoid.

Where no shortlist is configured the check falls back to kokoro's list, which is
no weaker than it was and no stronger. Closing that would mean building a
pipeline inside a tool call, which is what FR-5.1 keeps out of the request path.

This is about values that break skid, not about taste. FR-7.5 already allows
a player that breaks FR-1.4, and FR-1.8 a player that breaks FR-2.1. A setting
whose effect is silence is a different thing from a setting whose effect is
disliked.

Raised by the spec review at `fd42bdf`.
