"""The shape of the two structured files skid owns, as JSON Schema.

Both are handed to wrench, which validates on the way in and on the way out.
That is the point: a file skid wrote is checked against the same document a file
a person wrote is checked against, so an encoder bug and a typo fail the same
way and say the same thing.

**Dicts in a module, not files beside it.** wrench reads its own shipped schemas
from its repository root and states as a constraint that the pack must be
installed editable because of it. That is a real cost and it is worth not
repeating: a dict in the source is in the wheel, in the editable install and in
the tool environment, and no path resolution can lose it.

**`additionalProperties: false` on the config is a deliberate behaviour
change.** A key skid does not know used to load and do nothing, so `voce:
af_bella` silently kept the default voice and the only symptom was the wrong
voice. It is now refused by name. FR-6.4 is untouched: a *missing* config is
still not an error, and a malformed one still raises, which is the shape the
change was asked to keep.
"""

from __future__ import annotations

from typing import Any

SUBSTITUTION: dict[str, Any] = {
    "type": "object",
    "properties": {
        "kind": {"enum": ["literal", "regex"]},
        "pattern": {"type": "string", "minLength": 1},
        "replacement": {"type": "string"},
    },
    "required": ["pattern", "replacement"],
    "additionalProperties": False,
}
"""One pronunciation entry.

`kind` is optional because it defaults to literal, which is what the tool does.
`replacement` may be empty, since deleting a sound is a legitimate correction,
but a pattern that matches everywhere is not, so `pattern` has a floor.
"""

CONFIG: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "skid config",
    "type": "object",
    "properties": {
        "voice": {"type": "string", "minLength": 1},
        "player": {"type": "string", "minLength": 1},
        "greeting_window_seconds": {"type": "integer", "minimum": 0},
        "expiry_seconds": {"type": "integer", "minimum": 1},
        "substitution": {"type": "array", "items": SUBSTITUTION},
    },
    "additionalProperties": False,
}
"""Every setting, all optional, because each has a default and the file says
only what differs.

The bounds are the ones a wrong value makes invisible rather than loud. A
`greeting_window_seconds` of 0 greets every message and is a choice; a negative
one is a typo. An `expiry_seconds` of 0 discards every submission before it is
spoken, which looks exactly like skid being broken.

`voice` is only checked for being a non-empty string here. Which voices exist is
kokoro's to say, `generation.VOICES` holds them, and the tool refuses an unknown
one where the caller is still present to be told (FR-6.5).
"""

SPOOL_ENTRY: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "skid spool entry",
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "messages": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "queued_at": {"type": "number", "minimum": 0},
    },
    "required": ["name", "messages", "queued_at"],
    "additionalProperties": False,
}
"""One queued submission.

The required list is what `Submission` already refuses to be built without, said
where a file can be checked against it. `minItems: 1` and the `minLength` on the
name are that constructor's two rules, so a hand-edited entry fails at the file
rather than raising from a dataclass three frames later.

`queued_at` is required rather than defaulted. It used to fall back to 0.0,
which reads as the epoch and makes an entry infinitely expired, so an entry
missing it was silently discarded as too old instead of being reported as
malformed.
"""
