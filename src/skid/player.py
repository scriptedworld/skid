"""Playback: run a configured command over a file, one at a time.

skid imports no audio library, opens no device and sets no volume. It runs a
command line and waits for it, which is the whole output path.

Exclusion is that wait. It is only as good as the player's exit, so a command
that returns before its audio finishes releases the lock early and clips
overlap. skid cannot detect that and does not pretend to.
"""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

DEFAULT_TIMEOUT = 300.0
"""Longer than any clip skid produces: a stuck-process detector, not a policy."""


class PlaybackFailed(Exception):
    """A clip could not be played, whether it refused, failed or never ended."""


@dataclass(frozen=True)
class Outcome:
    """What happened to one clip."""

    clip: Path
    ok: bool
    reason: str = ""


class Player:
    """Runs the configured player, one clip at a time."""

    def __init__(self, command: str, timeout: float = DEFAULT_TIMEOUT) -> None:
        """Take the command line and the bound after which a player is killed."""
        if not command.strip():
            raise ValueError("a player command is required")
        self._command = command
        self._timeout = timeout
        self._lock = Lock()

    def _argv(self, clip: Path) -> list[str]:
        """Split the command and put the clip where the placeholder is.

        Split first, then substitute, so a path containing spaces stays one
        argument rather than becoming several.
        """
        return [
            token.replace("{file}", str(clip)) for token in shlex.split(self._command)
        ]

    def play(self, clip: Path) -> None:
        """Play one clip, holding the lock until the player exits.

        Raises PlaybackFailed if the player refuses, fails, or has to be killed
        for outlasting the timeout. Killing it is what stops one stuck player
        silencing the machine for ever while the queue grows behind it.
        """
        with self._lock:
            try:
                finished = subprocess.run(
                    self._argv(clip),
                    timeout=self._timeout,
                    check=False,
                    capture_output=True,
                )
            except subprocess.TimeoutExpired as exc:
                raise PlaybackFailed(
                    f"player did not exit within {self._timeout}s: {clip}"
                ) from exc
            except OSError as exc:
                raise PlaybackFailed(f"player could not be run: {exc}") from exc

        if finished.returncode != 0:
            raise PlaybackFailed(f"player exited {finished.returncode}: {clip}")

    def play_all(self, clips: list[Path]) -> list[Outcome]:
        """Play each clip in order, reporting failures rather than stopping.

        One clip failing does not cancel the rest, because the caller was told
        its submission was accepted and is no longer there to be told otherwise.
        """
        outcomes: list[Outcome] = []
        for clip in clips:
            try:
                self.play(clip)
            except PlaybackFailed as exc:
                outcomes.append(Outcome(clip=clip, ok=False, reason=str(exc)))
            else:
                outcomes.append(Outcome(clip=clip, ok=True))
        return outcomes
