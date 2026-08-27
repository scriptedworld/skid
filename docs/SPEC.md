# skid, the spec

How skid is arranged. `docs/REQUIREMENTS/` says what must be true; this says what
is built so that it is.

Every section names the requirements it discharges. Nothing here restates a
requirement, and where this document and a requirement disagree, the requirement
wins and this is the defect.

## The shape: many clients, one backend

**Two kinds of process.**

    skid-mcp     an MCP server over stdio. One per agent that connects.
    skid-backend one process for the machine. Holds the model, owns playback.

`skid-mcp` holds no model, opens no audio, and makes no decision about order. It
validates a call, forwards it over a socket, and returns what came back.

*Discharges FR-5.2, FR-5.1.*

### Why the split is forced rather than chosen

An MCP server over stdio is started by each client that connects, so several
agents mean several `skid-mcp` processes. Two requirements then land on that
fact from opposite directions:

- **FR-2.1** wants at most one clip audible across every caller, so exclusion
  has to span processes.
- **FR-5.1** wants the model warm, and a model loaded once per client process is
  neither warm nor affordable.

One backend answers both. It is also the "supporting background process" that
`docs/PROJECT.md` records as the reason skid has its own repository, so the
split is the project's premise rather than an implementation convenience.

### What it buys the lock

**Because all playback happens in one process, the exclusion of FR-2.1 is an
in-process mutex.** No lock file, no stale lock after a crash, no protocol
between processes about who holds it.

FR-2.2 leaves the mechanism open and this is the cheapest thing that satisfies
it. It stops being true the moment anything outside the backend plays a clip,
which is the constraint to remember rather than a rule to enforce.

*Discharges FR-2.1, FR-2.2, FR-7.3.*

## The transport

A Unix domain socket at `$XDG_RUNTIME_DIR/skid/backend.sock`, falling back to
`/tmp/skid-$UID/backend.sock`.

Local only, no port to allocate, and filesystem permissions are the access
control. One request, one response, newline-delimited JSON.

**`skid-mcp` starts the backend if the socket is absent** and connects to it if
present, so no separate launch step exists to forget. A start that loses the
race to another client's start is not an error: it connects to the winner.

## What a submission is

    {"name": "silo", "messages": ["first", "second"]}

`name` identifies the submitting engine. `messages` is an array, always, and an
array of one is how a single message is sent.

*Discharges FR-3.1, FR-4.1.*

## The path a submission takes

Inside the backend, in this order:

    1. queue        the submission joins the tail of an unbounded FIFO
    2. greet        decide the prefix, per name
    3. substitute   apply the pronunciation set
    4. generate     kokoro, ahead of playback, unbounded
    5. play         one clip at a time, in order

**A submission is spoken to completion before the next one starts.** FR-4.3
keeps an array in its own order and FR-7.2 makes arrivals queue; neither forbids
taking one message from each waiting submission in turn, which is why FR-4.4
says so.

*Discharges FR-4.3, FR-4.4, FR-7.2.*

### Greeting

The backend holds, per name, the time the last clip for that name finished
playing. A submission whose name has been quiet for 30 seconds by that clock is
prefixed `Hi, [name] here.` on its **first message only**.

The clock is the end of playback rather than the time of submission, because an
unbounded queue can put minutes between the two.

**The table lives in memory and is not persisted.** A backend restart costs one
extra greeting per name, which is the correct amount of engineering for a
30 second window.

*Discharges FR-3.2, FR-3.3, FR-3.4, FR-7.4.*

### Substitution

Entries are read from the config in file order and applied in that order, in a
single left-to-right pass over the text. A replacement is copied to the output
and never re-examined, so no entry can match its own output or another's.

An entry declares its kind:

    [[substitution]]
    kind = "literal"        # or "regex"
    pattern = "kokoro"
    replacement = "koh koh roh"

Substitution happens between the queue and the engine. What a caller submitted
and what any log records is the original text.

*Discharges FR-8.1, FR-8.2, FR-8.3, FR-8.4, FR-8.5, FR-7.7, FR-7.9.*

### Generation

kokoro renders each message to a WAV file in a per-run temporary directory.
Generation runs ahead of playback with no bound: every message of the queued
work may be in flight or already written.

**Generation may complete out of order. Playback may not.** The player takes
clips by index, waiting for the one it needs rather than for whichever finished
first.

A clip's file is deleted once it has played. The temporary directory is removed
when the backend exits.

*Discharges FR-1.1, FR-1.2, FR-4.2, FR-7.3.*

### Playback

    paplay <file>

Run as a subprocess, one at a time, under the mutex. The player is not told
which device to use, so it follows whatever the default sink currently is,
including one that changed after the clip was generated.

A configured player is a command line with `{file}` in it:

    player = "paplay {file}"

skid imports no audio library, opens no device, and sets no volume.

*Discharges FR-1.3, FR-1.4, FR-1.5, FR-7.5.*

## The config file

`$XDG_CONFIG_HOME/skid/config.toml`, defaulting to `~/.config/skid/config.toml`.

    voice = "af_heart"
    player = "paplay {file}"
    greeting_window_seconds = 30

    [[substitution]]
    kind = "literal"
    pattern = "kokoro"
    replacement = "koh koh roh"

**The file is the record.** A setting changed through an MCP tool is written
back to it, so a restart keeps it and a person reading the file sees what is in
use.

**Writing preserves what a person put there.** Comments, key order and the order
of substitution entries survive a write, because FR-8.4 makes entry order
meaningful and a comment is the only place a reason can live. The implementation
uses a style-preserving TOML round trip rather than parse-and-re-emit.

A missing config file is not an error. Defaults apply and the file is created by
the first write, which is FR-6.4.

*Discharges FR-6.2, FR-6.3, FR-6.4, FR-7.1, FR-7.8.*

## The MCP tools

    speak(name, messages)              queue an array. Returns immediately.
    set_voice(voice)                   change the voice, and persist it
    add_substitution(pattern,          add an entry at the end of the set
                     replacement, kind)
    remove_substitution(pattern)       remove by exact pattern
    list_substitutions()               the set, in file order

`speak` returns when the work is queued, not when it has been heard, which is
FR-4.5. A caller that blocked until its speech finished would serialise the
agent behind the audio, which is the opposite of what the queue is for.

*Discharges FR-4.5, FR-6.1, FR-8.1.*

## Failure

**A missing player and a bad file are the two failures this design admits**, and
neither is silent:

- the player exits non-zero, which is reported against that clip and does not
  stop the queue
- generation raises, which is reported against that message and does not stop
  the queue
- the backend is unreachable, which `skid-mcp` returns as a tool error rather
  than hanging

One clip failing does not cancel the rest of its array, and the queue behind it
still runs. A submission that produced no audible output at all is reported as a
whole rather than only as a run of individual failures.

*Discharges FR-1.5, FR-4.6.*

## What runs it

Python 3.12 exactly, and a uv project. kokoro refuses 3.13 and later, and this
machine's default interpreter is 3.14.7, so the pin is load-bearing rather than
conventional.

Linux only in the first pass. The platform-specific surface is one line of
config: the player command.

*Discharges FR-1.6, FR-1.7, FR-7.6.*

## What this deliberately leaves open

- **Voice names.** `af_heart` above is a placeholder. The set kokoro offers has
  not been measured, because kokoro is not installed.
- **Whether the greeting window is settable through a tool** as well as the
  file. FR-3.4 requires only that it is configurable, and FR-7.1 already says
  which route would win.
- **The wire format's evolution.** One request, one response, newline-delimited
  JSON, with no version field until something needs one.
- **How the backend exits.** Idle timeout, explicit shutdown, or never.

Each is an implementation choice that no requirement constrains, recorded here
so that making one does not look like discovering it.

## Not specified here, and why

**Nothing about task states, commit discipline or the gate.** Those are the
global `CLAUDE.md` and `docs/PROJECT.md`.

**No test plan.** That is stage 3 of `silo/docs/PATTERNS/how-a-change-gets-made.md`
and it derives from the requirements, not from this document.
