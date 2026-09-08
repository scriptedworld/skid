"""Which voice each name speaks in, and for how long it keeps it.

The same shape as `greeting.py`: a table holding what happened, and decisions
that take the time from the caller rather than reading a clock. That is what
lets a test drive six hours in a few lines without sleeping through them.

**The table is memory only**, FR-10.9. Losing it costs one reassignment per
name, and every voice on the shortlist was chosen by ear, so no entry is a worse
outcome than any other.

**Two windows exist and they are not the same window.** `greeting.QuietTable`
holds thirty seconds and decides whether a name is announced; this holds six
hours and decides whether a name keeps its voice. Both happen to be measured
from the end of a clip, which is a coincidence rather than a shared mechanism,
so each keeps its own record and neither can quietly change the other.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

DEFAULT_WINDOW_SECONDS = 6 * 60 * 60
"""Six hours, FR-10.5.

A PREFERENCE. Nothing measured produced it: it is a bet about how long a quiet
session is still a session. Being wrong short takes a voice off a name that is
still working, which is audible; being wrong long leaves a voice unavailable,
which is not.
"""


@dataclass(frozen=True)
class VoiceChoice:
    """One entry on the shortlist: what to call it, what to speak, how to say it.

    `pipeline` is the kokoro phonemiser code, and None means the one the voice id
    implies, which is `generation._lang_code`. Naming it is FR-10.7 and is what
    puts an Italian speaker on the list reading English.
    """

    alias: str
    voice: str
    pipeline: str | None = None


class Assignments:
    """Who holds which voice, and when each name last finished speaking.

    Built from the configured shortlist, FR-10.1. Nothing outside the list is
    ever handed out, so a voice that cannot render cannot reach a caller as long
    as the list was chosen from voices that do.
    """

    def __init__(self, choices: Sequence[VoiceChoice]) -> None:
        """Take the shortlist in file order, which is the order voices are given out."""
        self._choices = list(choices)
        self._held: dict[str, VoiceChoice] = {}
        self._last_heard: dict[str, float] = {}

    @property
    def choices(self) -> list[VoiceChoice]:
        """The shortlist this was built from."""
        return list(self._choices)

    def held(self) -> dict[str, VoiceChoice]:
        """Who currently holds which voice, as a copy.

        What `status` reports, so a person can ask which name sounds like which
        alias rather than working it out by listening.
        """
        return dict(self._held)

    def record_spoken(self, name: str, when: float) -> None:
        """Note that a clip for `name` finished at `when`, refreshing its window.

        FR-10.4. Called at the end of playback rather than at submission, so the
        window measures absence from the speaker rather than absence from the
        queue, which an unbounded queue can put minutes apart.
        """
        self._last_heard[name] = when

    def release_expired(self, now: float, window: float) -> list[str]:
        """Drop every assignment whose name has been quiet for `window`.

        FR-10.3, and it returns what it dropped so a caller can log it. A name
        going quiet is the only evidence skid has that a session ended, because
        a session stops existing without saying so.
        """
        gone = [
            name for name, last in self._last_heard.items() if (now - last) >= window
        ]
        for name in gone:
            self._held.pop(name, None)
            self._last_heard.pop(name, None)
        return gone

    def voice_for(self, name: str, now: float, window: float) -> VoiceChoice | None:
        """The voice `name` speaks in, assigning one if it does not have it yet.

        FR-10.2. Expired assignments are released first, so a name arriving after
        a long quiet spell can be given a voice that has just come free rather
        than doubling up on one that has not.

        None when the shortlist is empty, which is a config with no `voices` and
        means the single `voice` setting applies to everybody, exactly as it did
        before this existed.
        """
        if not self._choices:
            return None

        self.release_expired(now, window)

        held = self._held.get(name)
        if held is not None:
            return held

        chosen = self._pick()
        self._held[name] = chosen
        self._last_heard.setdefault(name, now)
        return chosen

    def _pick(self) -> VoiceChoice:
        """An unheld voice in file order, or the quietest one if all are held.

        FR-10.6. Reuse rather than refusal or a shared default: assignment always
        returns something, and the collision it produces is one this project has
        already accepted, since two sessions sharing a name share a voice anyway.
        """
        taken = {choice.voice for choice in self._held.values()}
        for choice in self._choices:
            if choice.voice not in taken:
                return choice
        return min(self._choices, key=self._last_heard_for_voice)

    def _last_heard_for_voice(self, choice: VoiceChoice) -> float:
        """When a voice was last audible, across every name holding it.

        The most recent of its holders, because a voice two names share was last
        heard when the later of them spoke. Ordering by this and taking the
        minimum gives the voice that has been silent longest.
        """
        heard = [
            self._last_heard.get(name, 0.0)
            for name, held in self._held.items()
            if held.voice == choice.voice
        ]
        return max(heard) if heard else 0.0
