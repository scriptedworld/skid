# FR-4.8, a queued submission survives a restart

| ID | Requirement | |
|---|---|---|
| FR-4.8 | A submission accepted and not yet started is spoken after the service restarts. Accepting it writes it to disk before the call returns. | [A] |

Stated 2026-08-28. Derived in shape from FR-4.5 and in force from a decision.

**FR-4.5 was a promise backed by memory, which is not a promise.** It says a
submission returns to its caller once the work is queued. Before this row, the
queue was a `deque` in one process, so "queued" meant "accepted by something
that will forget on restart", and the caller had already been told yes.

Restarting is the documented way to deploy an edit under an editable install, so
the loss was routine rather than exceptional.

## What is durable is the text, not the audio

The submission is written at `submit()`, before the call returns. Clips remain a
cache in the runtime directory and may be deleted freely, because losing one
costs regeneration time rather than data.

**A spool of generated audio would not discharge this row.** It protects only
work already generated, and the window this is about is the one between the call
returning yes and the first clip existing. Text at the front door closes it;
audio does not.

## The guarantee is precise, and smaller than nothing is lost

**Accepted and not yet started is never lost.** A submission that was being
spoken when the process died is dropped, the same as one whose player failed,
and for the same reason: FR-4.4 makes a submission indivisible, so there is no
honest place to resume from and replaying means hearing the already-heard clips
again.

An entry is moved aside when it is taken and removed when the attempt ends,
however it ends. Anything found aside at start-up was interrupted, and is
discarded with a line in the log.

## Order is by name, not by time

Entries carry a monotonic sequence in the filename and are taken in
lexicographic order. **Creation time would be generation order rather than
submission order**, which happens to match today only because one submission is
handled at a time, and would diverge the moment two are prepared at once. FR-4.3
and FR-4.4 both depend on this and would break silently and only under load.

The entry is written to a temporary name and renamed into place, so a file at
its final name is a whole file. A `kill -9` mid-write leaves a temporary that
start-up removes rather than a truncated entry that parses to nonsense.

## Restart, not reboot

`$XDG_RUNTIME_DIR`, which is tmpfs. That covers every restart and deploy, and a
reboot starts silent rather than reading back an hour of chatter about work that
finished before it.
