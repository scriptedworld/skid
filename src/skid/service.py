"""The units composed: queue, greeting, substitution, generation, playback.

The order is the whole of this module, and one part of it is not obvious. The
greeting is **generated** with the rest of a submission and **decided** when the
first clip is about to play. Deciding it at queue time would satisfy every row
and still announce a name that had been talking continuously since, because an
unbounded queue can put minutes between queueing and speech.

Generation runs ahead of playback and does not take the playback lock. That is
the whole reason the two are separate threads: one lock over both would satisfy
"at most one clip audible" and silently destroy "the rest are being prepared".
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from skid.config import Config, load_config
from skid.generation import GenerationFailed, Generator
from skid.greeting import QuietTable, greeting_for, should_greet
from skid.player import PlaybackFailed, Player
from skid.queue import Submission, SubmissionQueue
from skid.substitution import apply_substitutions

STOP = None
"""What is put on a queue to say there is nothing more coming.

`None` rather than a sentinel object, so the queues can be typed as holding
`X | None` and the reader needs no runtime check to know what it took.
"""


@dataclass(frozen=True)
class Clip:
    """One generated clip, and the text it was made from."""

    path: Path
    text: str
    is_greeting: bool = False


class Service:
    """One long-lived service: takes submissions, speaks them in order."""

    def __init__(
        self,
        config: Config,
        work_dir: Path,
        log_path: Path,
        generator: Generator | None = None,
        config_path: Path | None = None,
    ) -> None:
        """Compose the units. The generator is shared so the model stays warm."""
        self._config = config
        self._work = work_dir
        self._log_path = log_path
        self._config_path = config_path
        self._config_seen: float | None = None
        self._generator = generator or Generator(config.voice)
        self._player = Player(command=config.player)

        self._incoming: queue.Queue[Submission | None] = queue.Queue()
        self._queue = SubmissionQueue()
        self._table = QuietTable()
        self._failures: list[str] = []
        self._idle = threading.Event()
        self._idle.set()
        self._thread: threading.Thread | None = None

        self.greeted: list[str] = []
        self.spoken: list[tuple[str, str]] = []

    def start(self) -> None:
        """Begin serving. Idempotent enough to call once."""
        self._work.mkdir(parents=True, exist_ok=True)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop serving after the current submission."""
        self._incoming.put(STOP)
        if self._thread is not None:
            self._thread.join(timeout=30)
            self._thread = None

    def submit(self, name: str, messages: list[str]) -> None:
        """Queue an array. Returns once it is queued, not once it is heard."""
        submission = Submission(name=name, messages=list(messages))
        self._queue.put(submission)
        self._idle.clear()
        self._incoming.put(submission)

    def wait_idle(self, timeout: float) -> bool:
        """Block until nothing is waiting or being spoken."""
        return self._idle.wait(timeout=timeout)

    def status(self) -> dict[str, object]:
        """Health, queue depth and recent failures, for a caller that cannot log."""
        return {
            "pending": self._queue.pending(),
            "recent_failures": list(self._failures[-20:]),
            "voice": self._config.voice,
        }

    def _refresh_config(self) -> None:
        """Re-read the config if it has changed since it was last read.

        This is what makes FR-6.3's own observable true: setting the voice by
        either route changes what the next clip is spoken in. Reading once at
        start would give the tool route effect and the file route none, which is
        two routes that do not agree.
        """
        if self._config_path is None or not self._config_path.exists():
            return
        stamp = self._config_path.stat().st_mtime
        if stamp == self._config_seen:
            return
        self._config_seen = stamp
        try:
            self._config = load_config(self._config_path)
        except ValueError as exc:
            self._record_failure(f"config not reloaded: {exc}")
            return
        self._player = Player(command=self._config.player)
        self._generator.set_voice(self._config.voice)

    def _log(self, line: str) -> None:
        """Append one line to the log a person reads when the machine goes quiet."""
        with self._log_path.open("a", encoding="utf-8") as out:
            out.write(f"{time.time():.3f} {line}\n")

    def _record_failure(self, line: str) -> None:
        """Record a failure where both a person and a caller can find it."""
        self._failures.append(line)
        self._log(line)

    def _generate_into(
        self, submission: Submission, clips: queue.Queue[Clip | None], index_base: int
    ) -> None:
        """Generate the greeting and every message, ahead of playback, in order."""
        texts = [(greeting_for(submission.name), True)]
        texts += [(message, False) for message in submission.messages]

        for offset, (raw, is_greeting) in enumerate(texts):
            spoken_text = apply_substitutions(self._config.substitutions, raw)
            path = self._work / f"{index_base + offset:04d}.wav"
            try:
                self._generator.generate(spoken_text, path)
            except (GenerationFailed, OSError) as exc:
                self._record_failure(f"generation failed for {raw!r}: {exc}")
                continue
            clips.put(Clip(path=path, text=raw, is_greeting=is_greeting))
        clips.put(STOP)

    def _speak(self, submission: Submission, index_base: int) -> None:
        """Generate ahead in one thread while playing in this one."""
        clips: queue.Queue[Clip | None] = queue.Queue()
        worker = threading.Thread(
            target=self._generate_into,
            args=(submission, clips, index_base),
            daemon=True,
        )
        worker.start()

        greet: bool | None = None
        while True:
            clip = clips.get()
            if clip is None:
                break

            if greet is None:
                greet = should_greet(
                    self._table,
                    submission.name,
                    now=time.monotonic(),
                    window=float(self._config.greeting_window_seconds),
                )
                if greet:
                    self.greeted.append(submission.name)

            if clip.is_greeting and not greet:
                clip.path.unlink(missing_ok=True)
                continue

            try:
                self._player.play(clip.path)
            except PlaybackFailed as exc:
                self._record_failure(str(exc))
            else:
                if not clip.is_greeting:
                    self.spoken.append((submission.name, clip.text))
            finally:
                clip.path.unlink(missing_ok=True)

        worker.join(timeout=5)
        self._table.record_finished(submission.name, when=time.monotonic())

    def _serve(self) -> None:
        """Take submissions in turn, each spoken to completion before the next."""
        index = 0
        while True:
            if self._incoming.get() is None:
                return
            self._refresh_config()
            submission = self._queue.take()
            try:
                self._speak(submission, index)
            except (GenerationFailed, PlaybackFailed, OSError) as exc:
                self._record_failure(f"submission from {submission.name} failed: {exc}")
            index += len(submission.messages) + 1
            if self._queue.pending() == 0:
                self._idle.set()
