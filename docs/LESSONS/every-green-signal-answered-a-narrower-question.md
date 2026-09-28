# Every green signal answered a narrower question

skid was installed, running, socket-activated, restarting cleanly, reporting an
empty `recent_failures` and draining its queue to zero. It had been inaudible for
weeks, and none of those signals was lying.

It ran on lazlo and the person sat at oslo. Every clip generated correctly, played
correctly, and went into an empty room.

## What each signal actually answered

    systemctl is-active      the process is up
    recent_failures empty    no clip failed to generate or play
    pending 0                the queue drained
    a RUNNING sink           audio reached a device
    skid-say exit 0          the submission was accepted

None of them answers *did a person hear this*. That question has no instrument
here, and adding one would mean skid knowing about the listener, which FR-1.5
deliberately keeps it out of.

## The failure mode is agreement, not error

`pending: 0` was read as proof twice in one session, once on each side of the
fix. A drained queue is consistent with the clip playing to the right speaker and
equally consistent with it playing to a speaker nobody is near. Reading it as the
first is not a mistake in the measurement, it is a question substituted for a
narrower one that happens to be cheap.

This is the same shape the project already recorded in `docs/PROJECT.md` as the
four-way set, where `claude mcp list` answers about a fresh connection and a probe
answers about the probe's own session. That set was written about other people's
tools and applied to skid itself without anybody noticing.

## What to do

**Ask the person.** It is one sentence and it is the only instrument that exists.
Where the answer is "no", the next check is whether a socket the audio depends on
is present, not whether the service is healthy:

    ls -l /run/user/1000/pulse-oslo

Notice when a check is cheap. A signal that costs nothing to read is usually
answering something narrower than the thing being asked, because the expensive
part of the real question is what was dropped to make it cheap.

Say which question a green result answered, in the sentence that reports it.
"The queue drained" invites no wrong conclusion. "It works" invites exactly one.
