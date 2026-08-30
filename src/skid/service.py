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
from dataclasses import dataclass, field
from pathlib import Path

from skid.assignment import Assignments
from skid.config import Config, load_config
from skid.generation import GenerationFailed, Generator
from skid.greeting import QuietTable, greeting_for, should_greet
from skid.player import PlaybackFailed, Player
from skid.queue import Submission
from skid.spool import Entry, Spool
from skid.substitution import apply_substitutions

WAKE = object()
"""Put on the wakeup queue to say there is something in the spool.

It carries nothing. The spool is the queue, and this only says to go and look,
so one wakeup can cover several entries and a restart needs none at all.
"""

PROGRESS_GRACE = 60.0
"""How long the serve loop may go without a step before it is called stuck.

It has to clear one generation step, because playback pings and a clip on the
speaker is health however long it runs. Speech is about 15.5 characters per
second of audio and generation runs at about 6.8 times realtime, so the 300
second playback ceiling in `player.py` is roughly 4,660 characters and takes
about 44 seconds to generate.

That is inside this grace and not by much: 60 against 44 is a margin of about a
third, where an earlier reading of the measurement put it at twice.
`.ephemera/measure-clip-length.py` regenerates the figures.
"""

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


@dataclass(frozen=True)
class Workspace:
    """Where a service keeps its things.

    Every path is a parameter and none defaults to a real location, so a test
    points the whole service at a temporary directory. `install.Paths` is the
    same idea for the installer.

    The spool sits beside `work_dir` rather than inside it, because clips are a
    cache and the queue is not: clearing one must not clear the other.
    """

    work_dir: Path
    log_path: Path
    config_path: Path | None = None


@dataclass
class Parts:
    """The units a service is composed of.

    Mutable because `_refresh_config` rebuilds the player when the command
    changes, and re-voices the generator rather than replacing it, which is what
    keeps the model warm across a config reload.
    """

    generator: Generator
    player: Player
    spool: Spool
    table: QuietTable
    assignments: Assignments


@dataclass
class Loop:
    """The serve loop's own state, separate from what it operates on.

    `incoming` carries wakeups rather than work: the spool is the queue, so one
    wakeup can cover several entries and a restart needs none at all.
    """

    incoming: queue.Queue[object | None]
    idle: threading.Event
    progressed: float
    thread: threading.Thread | None = None


@dataclass
class Record:
    """What the service has done, for a caller or a test to read.

    Not persisted. `failures` is what `status` reports and the log holds the
    same lines durably, which is FR-4.7's two destinations.
    """

    greeted: list[str] = field(default_factory=list)
    spoken: list[tuple[str, str]] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


class Service:
    """One long-lived service: takes submissions, speaks them in order."""

    def __init__(
        self,
        config: Config,
        workspace: Workspace,
        generator: Generator | None = None,
    ) -> None:
        """Compose the units. The generator is shared so the model stays warm."""
        self._config = config
        self._config_seen: float | None = None
        self._workspace = workspace
        self._parts = Parts(
            generator=generator or Generator(config.voice),
            player=Player(command=config.player),
            spool=Spool(
                workspace.work_dir.parent / "spool",
                ttl_seconds=float(config.expiry_seconds),
            ),
            table=QuietTable(),
            assignments=Assignments(config.voices),
        )
        self._loop = Loop(
            incoming=queue.Queue(),
            idle=threading.Event(),
            progressed=time.monotonic(),
        )
        self._loop.idle.set()
        self._record = Record()

    @property
    def greeted(self) -> list[str]:
        """Names announced so far, in the order they were announced."""
        return self._record.greeted

    @property
    def spoken(self) -> list[tuple[str, str]]:
        """Every name and text actually played, in the order heard."""
        return self._record.spoken

    def start(self) -> None:
        """Begin serving. Idempotent enough to call once.

        **Both directories are made owner-only, and the log's is the one that
        needs it.** `mkdir(mode=...)` does nothing to a directory that already
        exists, which is why the mode is set separately: measured 2026-08-28,
        the live clips directory was 0775 and `~/.local/state/skid` was 0775.

        The clips directory sits inside systemd's own 0700 runtime directory, so
        FR-5.4 held there by accident. The log directory has no such parent, and
        the log records the text a caller submitted whenever generation fails,
        so it was readable by any local user.
        """
        for directory in (self._workspace.work_dir, self._workspace.log_path.parent):
            directory.mkdir(parents=True, exist_ok=True)
            directory.chmod(0o700)
        self._recover()
        self._loop.thread = threading.Thread(target=self._serve, daemon=True)
        self._loop.thread.start()
        if self._parts.spool.pending():
            self._loop.idle.clear()
            self._loop.incoming.put(WAKE)

    def _recover(self) -> None:
        """Clear what a crash left in the spool, and say so where a person reads.

        Everything discarded here was accepted by a `submit` that returned yes,
        so a silent clean-up would make FR-4.5 a lie in exactly the case nobody
        would notice.
        """
        found = self._parts.spool.recover(now=time.time())
        for name in found.expired:
            self._record_failure(
                f"discarded on start-up, older than the window: {name}"
            )
        if found.interrupted:
            self._record_failure(
                f"discarded {found.interrupted} submission(s) interrupted mid-speech"
            )
        if found.partial or found.unreadable:
            self._record_failure(
                f"removed {found.partial} half-written and "
                f"{found.unreadable} unreadable spool entries"
            )

    def stop(self) -> None:
        """Stop serving after the current submission."""
        self._loop.incoming.put(STOP)
        if self._loop.thread is not None:
            self._loop.thread.join(timeout=30)
            self._loop.thread = None

    def submit(self, name: str, messages: list[str]) -> None:
        """Queue an array. Returns once it is on disk, not once it is heard.

        **The write is the promise.** FR-4.5 says this returns when the work is
        queued, and FR-4.8 makes queued mean durable, so the entry is on disk
        before the caller is told yes. What goes on `_incoming` afterwards is a
        wakeup and carries nothing: the spool is the queue.
        """
        submission = Submission(name=name, messages=list(messages))
        self._parts.spool.put(submission, now=time.time())
        self._loop.idle.clear()
        self._loop.incoming.put(WAKE)

    def wait_idle(self, timeout: float) -> bool:
        """Block until nothing is waiting or being spoken."""
        return self._loop.idle.wait(timeout=timeout)

    def _progress(self) -> None:
        """Note that the serve loop got somewhere. Called at each step it takes."""
        self._loop.progressed = time.monotonic()

    def is_progressing(self, now: float, grace: float = PROGRESS_GRACE) -> bool:
        """Whether the serve loop is working or waiting, rather than stuck.

        **Progress, not liveness.** A timer on a thread that is always alive
        proves the timer runs. What the watchdog needs to know is that the loop
        in `_serve` is not wedged, and there are three ways for it to be fine:

            idle        nothing queued, so the loop is parked on `_incoming`
            playing     a clip is on the speaker, bounded by FR-1.9's timeout
            recent      it stepped within `grace`

        Generation is the only step that takes real time without touching any of
        the first two, which is what `grace` covers. Measured 2026-08-28: 1196
        characters generated in 10.9 seconds, and a clip long enough to reach
        the player's own 300s ceiling is about 1950 characters and roughly 30
        seconds of generation. The default is twice that.

        Wrong in this direction is a watchdog that fires late. Wrong in the
        other restarts a service that is speaking and cuts a clip mid-sentence.
        """
        if self._loop.idle.is_set():
            return True
        if self._parts.player.playing_since() is not None:
            return True
        return (now - self._loop.progressed) < grace

    def status(self) -> dict[str, object]:
        """Health, queue depth and recent failures, for a caller that cannot log."""
        return {
            "pending": self._parts.spool.pending(),
            "recent_failures": list(self._record.failures[-20:]),
            "voice": self._config.voice,
            "assigned": {
                name: choice.alias
                for name, choice in self._parts.assignments.held().items()
            },
        }

    def _refresh_config(self) -> None:
        """Re-read the config if it has changed since it was last read.

        This is what makes FR-6.3's own observable true: setting the voice by
        either route changes what the next clip is spoken in. Reading once at
        start would give the tool route effect and the file route none, which is
        two routes that do not agree.

        **Assignments are rebuilt only when the shortlist itself changed.** Every
        `set_voice` call rewrites the config and lands here, and rebuilding
        unconditionally would take every name's voice away whenever anybody
        touched an unrelated setting. Comparing the lists is enough because
        `VoiceChoice` is frozen, so equality is by value.
        """
        if (
            self._workspace.config_path is None
            or not self._workspace.config_path.exists()
        ):
            return
        stamp = self._workspace.config_path.stat().st_mtime
        if stamp == self._config_seen:
            return
        self._config_seen = stamp
        try:
            self._config = load_config(self._workspace.config_path)
        except ValueError as exc:
            self._record_failure(f"config not reloaded: {exc}")
            return
        self._parts.player = Player(command=self._config.player)
        self._parts.generator.set_voice(self._config.voice)
        if self._parts.assignments.choices != self._config.voices:
            self._parts.assignments = Assignments(self._config.voices)

    def _log(self, line: str) -> None:
        """Append one line to the log a person reads when the machine goes quiet."""
        with self._workspace.log_path.open("a", encoding="utf-8") as out:
            out.write(f"{time.time():.3f} {line}\n")

    def _record_failure(self, line: str) -> None:
        """Record a failure where both a person and a caller can find it."""
        self._record.failures.append(line)
        self._log(line)

    def _apply_voice(self, name: str) -> None:
        """Point the generator at the voice `name` speaks in, FR-10.2.

        **This cannot be allowed to raise.** It runs at the top of the generation
        thread, and that thread signals the end of its work by putting STOP on
        the queue the player is blocked reading. An exception here would skip the
        STOP and leave playback waiting on a queue nothing will ever fill, which
        is a wedged service rather than a failed submission.

        So a voice the config names and kokoro does not know is recorded and
        stepped over, leaving whatever the generator already had. That is the
        FR-6.5 shape reaching us from the file rather than from a tool: the tool
        route refuses it where the caller is present, and a hand-edited file has
        nobody standing there to be told.
        """
        choice = self._parts.assignments.voice_for(
            name,
            now=time.monotonic(),
            window=float(self._config.assignment_window_seconds),
        )
        wanted = self._config.voice if choice is None else choice.voice
        pipeline = None if choice is None else choice.pipeline
        try:
            self._parts.generator.set_voice(wanted, pipeline)
        except ValueError as exc:
            self._record_failure(f"voice not applied for {name}: {exc}")

    def _generate_into(
        self, submission: Submission, clips: queue.Queue[Clip | None], index_base: int
    ) -> None:
        """Generate the greeting and every message, ahead of playback, in order."""
        self._apply_voice(submission.name)
        texts = [(greeting_for(submission.name), True)]
        texts += [(message, False) for message in submission.messages]

        for offset, (raw, is_greeting) in enumerate(texts):
            spoken_text = apply_substitutions(self._config.substitutions, raw)
            path = self._workspace.work_dir / f"{index_base + offset:04d}.wav"
            try:
                self._parts.generator.generate(spoken_text, path)
            except (GenerationFailed, OSError) as exc:
                self._record_failure(f"generation failed for {raw!r}: {exc}")
                continue
            clips.put(Clip(path=path, text=raw, is_greeting=is_greeting))
            self._progress()
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
                    self._parts.table,
                    submission.name,
                    now=time.monotonic(),
                    window=float(self._config.greeting_window_seconds),
                )
                if greet:
                    self._record.greeted.append(submission.name)

            if clip.is_greeting and not greet:
                clip.path.unlink(missing_ok=True)
                continue

            try:
                self._parts.player.play(clip.path)
            except PlaybackFailed as exc:
                self._record_failure(str(exc))
            else:
                if not clip.is_greeting:
                    self._record.spoken.append((submission.name, clip.text))
            finally:
                clip.path.unlink(missing_ok=True)
                self._progress()

        worker.join(timeout=5)
        finished = time.monotonic()
        self._parts.table.record_finished(submission.name, when=finished)
        self._parts.assignments.record_spoken(submission.name, when=finished)

    def _serve(self) -> None:
        """Take submissions in turn, each spoken to completion before the next.

        One wakeup can cover several entries, because a restart finds a spool
        already holding work and nobody sends a wakeup per entry for it. So the
        loop drains rather than taking one and waiting again.

        **The entry is removed when the attempt ends, however it ends.** A
        failure drops the submission, which is what makes a poison entry
        impossible: an entry removed only on success would be retried forever
        and everything behind it would wait.
        """
        index = 0
        while True:
            if self._loop.incoming.get() is None:
                return
            self._progress()
            self._refresh_config()
            for entry in self._expired_now():
                self._record_failure(
                    f"discarded, older than the window: {entry.submission.name}"
                )
            while (taken := self._parts.spool.take(now=time.time())) is not None:
                submission = taken.submission
                try:
                    self._speak(submission, index)
                except (GenerationFailed, PlaybackFailed, OSError) as exc:
                    self._record_failure(
                        f"submission from {submission.name} failed: {exc}"
                    )
                finally:
                    self._parts.spool.done(taken)
                    self._progress()
                index += len(submission.messages) + 1
            self._loop.idle.set()

    def _expired_now(self) -> list[Entry]:
        """Whatever has aged out since the last look, for the log."""
        return self._parts.spool.take_expired(now=time.time())
