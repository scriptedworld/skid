# skid, the spec

How skid is arranged. `docs/REQUIREMENTS/` says what must be true; this says what
is built so that it is.

Every section names the requirements it discharges. Nothing here restates a
requirement, and where this document and a requirement disagree, the requirement
wins and this is the defect.

Revised 2026-08-27 after two independent cold reviews of `fd42bdf`. What changed
is recorded in `clank/tasks/skid/first-build/`.

## The shape: many clients, one backend

**Two kinds of process.**

    skid-mcp     an MCP server over stdio. One per agent that connects.
    skid-backend one process for the machine. Holds the model, owns playback.

`skid-mcp` holds no model, opens no audio, and makes no decision about order. It
validates a call, forwards it over a socket, and returns what came back.

*Discharges FR-5.2, FR-5.1.*

### Why one backend, which is a choice and not a necessity

An MCP server over stdio is started by each client that connects, so several
agents mean several `skid-mcp` processes, and exclusion has to reach across
them.

**The requirements do not compel a backend.** FR-2.2 permits a lock file
explicitly, "against every process that agrees to take it", and a design with no
backend at all satisfies every settled row: each `skid-mcp` loads kokoro itself
and holds a lock file around playback. It meets FR-2.1, FR-4.4, FR-7.2, FR-7.3
and FR-4.2. It is slower and it is not forbidden.

**The one row it fails is FR-5.1, which says of itself that it is "wanted rather
than required".** So a backend is what FR-5.1 asks for, and FR-5.1 is a want. An
argument that the design is forced would have to rest on that want, and it
cannot.

What the backend is chosen for, beyond the warm model:

- **One writer for the config**, which is what makes FR-7.1 and FR-7.8's
  write-through safe without a second locking scheme.
- **One place FR-4.4 is true**, rather than a cross-process protocol about whose
  submission is next.
- **One place a failure is visible**, which FR-4.7 requires.

Those are good reasons. They are not necessity, and the earlier draft of this
section claimed necessity, which is a claim that stops anyone reconsidering the
design later.

**The appeal to the repository boundary is withdrawn as an argument.**
`docs/PROJECT.md` records that skid has its own tree because it is an MCP with a
supporting background process, and FR-5.1 records that the requirement and the
boundary are one decision seen twice. Citing the boundary as a second reason
counts one decision twice.

*Discharges FR-2.1, FR-2.2, FR-5.1.*

### What it buys the lock

**Because all playback happens in one process, the exclusion of FR-2.1 is an
in-process mutex.** No cross-process protocol about who is speaking.

That much follows. **What does not follow is freedom from stale state**, which
an earlier draft claimed. See the start protocol below: the socket path is
filesystem state that outlives the process holding it, so skid has stale-state
handling to do, and the honest claim is that the exclusion of playback is free
rather than that staleness is gone.

The mutex is sufficient only while every clip is played by the one backend.

*Discharges FR-2.1, FR-2.2, FR-7.3.*

## Starting the backend, and the socket

    $XDG_RUNTIME_DIR/skid/          directory, mode 0700, ownership checked
        backend.sock                the socket
        backend.lock                held only during start

Falling back to `/tmp/skid-$UID/` when `XDG_RUNTIME_DIR` is unset. **The
directory is created 0700 and its ownership is verified before use**, because
`/tmp` is world-writable and a path another user pre-created would otherwise be
trusted.

**A socket file outlives the process that bound it.** Measured 2026-08-27:
after `SIGKILL` the path remains, a fresh bind gets `EADDRINUSE`, and a client
gets `ECONNREFUSED`. So presence of the path is not evidence of a live backend,
and "start it if the socket is absent" would leave skid permanently silent after
any crash.

**The start protocol.**

    1. connect to backend.sock. On success, done.
    2. On ENOENT or ECONNREFUSED, take an exclusive flock on backend.lock.
    3. Holding the lock, connect once more. Another client may have won while
       this one waited; if it answers, done.
    4. Still nothing: unlink any stale backend.sock, spawn the backend, and
       wait for the path to appear, with a timeout.
    5. Release the lock.

**The backend binds to a temporary name, loads the model, and only then renames
the socket into place.** The rename is atomic, so the path appearing means the
backend is ready, and a client never connects to a socket whose process is still
loading torch and possibly downloading weights. The wait in step 4 is bounded and
generous for that reason.

Yes, this is a lock file. It serialises start-up, not playback, and it is the
part of stale-state handling the earlier draft claimed to have avoided.

**A pathname socket is chosen over an abstract one, and the trade is access
control against staleness.** A Linux abstract socket, whose name begins with a
NUL, is not a filesystem entry and has no staleness at all. Measured
2026-08-27: bind to `"\0skid"` in one process, and while it is held a second
bind gets `EADDRINUSE`; `SIGKILL` that process and a fresh bind to the same name
succeeds, with nothing left behind to unlink and no path on disk to find.

It also has no path, and therefore no file permissions. Access would be scoped
to the network namespace, which on an ordinary machine means any local user can
connect and make the speakers talk, and can write entries into the config
through the tools.

**Owner-only access is worth more here than avoiding a start protocol**, so the
socket keeps its path under a 0700 directory and the start protocol above
handles the staleness that comes with it. Socket activation, letting the init
system own the name and the lifetime, is the third option and is more machinery
than skid needs while it is one user's tool on one machine.

**How the backend is spawned matters, because `skid-mcp` speaks JSON-RPC on its
stdout.** The child is detached into its own session, its stdin is `/dev/null`,
and its stdout and stderr go to the log named under Failure. It never inherits
`skid-mcp`'s streams: one torch warning or one progress bar written into that
pipe corrupts the client's protocol. Detaching is also what stops the shared
backend dying with whichever agent happened to start it.

Requests are newline-delimited JSON, one request, one response. Each carries a
protocol version, because a backend that never exits will meet an upgraded
`skid-mcp`.

*Discharges FR-5.1, FR-2.1.*

## What a submission is

    {"name": "silo", "messages": ["first", "second"]}

`name` identifies the submitting engine. `messages` is an array, always, and an
array of one is how a single message is sent. `skid-mcp` rejects an absent name,
an empty array and a non-string message before anything is queued.

*Discharges FR-3.1, FR-4.1.*

## The path a submission takes

Inside the backend:

    1. queue        the submission joins the tail of an unbounded FIFO
    2. substitute   apply the pronunciation set
    3. generate     kokoro, ahead of playback, unbounded
    4. play         one clip at a time, in order, deciding the greeting here

**A submission is spoken to completion before the next one starts**, which is
FR-4.4. Nothing interleaves.

**Greeting is decided at step 4, not step 1**, which is FR-3.5 and is the
correction that reordered this list.

*Discharges FR-4.3, FR-4.4, FR-7.2.*

### Greeting

The backend holds, per name, the time the last clip for that name finished
playing. In memory only, so a restart costs at most one extra greeting per name.

**The decision is made when the submission reaches the front of the queue.** A
name quiet for 30 seconds by that clock is prefixed `Hi, [name] here.` Both
endpoints of the comparison are then at playback, which is the point: an
unbounded queue can put minutes between queueing and speech, and deciding at
queue time would announce a name that has been talking continuously ever since.

**The greeting is generated as a clip of its own**, at the same time as the
submission's first message, and at playback it is either played or discarded.
That keeps FR-7.3's lookahead unbounded and FR-4.2 intact, at the cost of one
short clip per submission that is usually thrown away. Deciding at playback and
then generating would stall the lookahead for exactly the message it matters
most for.

A greeting clip is never the thing FR-4.6 reports as a failed message. If the
first message fails, the greeting is discarded with it rather than announcing a
name that then says nothing.

*Discharges FR-3.2, FR-3.3, FR-3.4, FR-3.5, FR-3.6, FR-7.4.*

### Substitution

**One left-to-right scan.** At each position the entries are tried in file
order, the first that matches there wins, its replacement is emitted, and the
scan resumes after the emitted text. Nothing re-examines what a substitution
produced.

**Position is the primary order and file order is the tie-break at a position.**
Applying each entry across the whole text in turn is a different algorithm that
would let entry two see entry one's output, and it is not what this is.

An entry declares its kind:

    [[substitution]]
    kind = "literal"        # or "regex"
    pattern = "kokoro"
    replacement = "koh koh roh"

A literal matches on word boundaries, case-insensitively. A regex is compiled
when it is declared and refused if it does not compile, so an entry that would
break every later submission never reaches the record. A replacement is literal
text in both kinds: no backreferences, because the substitution is heard rather
than read and a backreference has no audible purpose worth the ambiguity.

Substitution happens between the queue and the engine. What a caller submitted,
and what the log records, is the original text.

*Discharges FR-8.1, FR-8.2, FR-8.3, FR-8.4, FR-8.5, FR-7.7, FR-7.9.*

### Generation

kokoro renders each message to a WAV file in a working directory under the
runtime directory. **The stdlib `wave` module writes the file**, from the numpy
array kokoro returns, so that FR-1.5's first test clause stays literally true:
no audio library is imported. `soundfile` would fail that clause, being
libsndfile.

**Generation runs ahead of playback without bound in queue depth, and one
message at a time.** One warm model is shared, nothing establishes that a kokoro
pipeline is safe to call concurrently, and a single worker running ahead of the
player satisfies FR-4.2 completely. "Unbounded" is about how far ahead, not how
many at once.

A clip's file is deleted once it has played or been discarded. The working
directory is removed when the backend exits.

*Discharges FR-1.1, FR-1.2, FR-4.2, FR-7.3.*

### Playback

    paplay <file>

Run as a subprocess, one at a time, under the mutex. The player is not told
which device to use, so it follows whatever the default sink currently is.

A configured player is a command line with `{file}` in it, split with
`shlex.split` and executed without a shell:

    player = "paplay {file}"

**Two contracts on a configured player, and skid enforces neither.** It must not
exit before its clip is inaudible, or the mutex is released early and clips
overlap (FR-1.8). And a player that has not exited within a bounded time is
killed, the clip recorded as failed and the lock released (FR-1.9), because
otherwise one stuck subprocess silences the machine for ever while the queue
grows behind it.

skid imports no audio library, opens no device, and sets no volume.

*Discharges FR-1.3, FR-1.4, FR-1.5, FR-1.8, FR-1.9, FR-7.5.*

## The config file

`$XDG_CONFIG_HOME/skid/config.toml`, defaulting to `~/.config/skid/config.toml`.

    voice = "af_heart"
    player = "paplay {file}"
    greeting_window_seconds = 30

    [[substitution]]
    kind = "literal"
    pattern = "kokoro"
    replacement = "koh koh roh"

**The file is the record**, and the backend is its only writer.

**When it is read.** The backend checks the file's mtime before each submission
is processed and re-reads it when it has changed. That is what makes FR-6.3's
own observable true for both routes: setting the voice by either one changes
what the next clip is spoken in. Reading once at start would give the tool route
effect and the file route none, which is two routes that do not agree.

**How it is written.** Read, modify, then write a temporary file in the same
directory, flush it, and rename over the original. The rename is atomic, so a
kill during a write cannot leave a truncated config and lose the substitution
set. The read-modify-write is done under the same mtime check, so a hand edit
made since the last read is not silently discarded.

**Writing preserves what a person put there**: comments, key order and the order
of substitution entries, because FR-8.4 makes entry order meaningful and a
comment is the only place a reason can live. That means a style-preserving TOML
round trip rather than parse-and-re-emit.

A missing config file is not an error. Defaults apply and the file is created by
the first write. A config file that is present but malformed **is** an error, and
it is reported rather than silently replaced by defaults, because overwriting it
would destroy the record it failed to parse.

*Discharges FR-6.2, FR-6.3, FR-6.4, FR-7.1, FR-7.8.*

## The MCP tools

    speak(name, messages)              queue an array. Returns when queued.
    set_voice(voice)                   change the voice, and persist it
    add_substitution(pattern,          add an entry at the end of the set
                     replacement, kind)
    remove_substitution(pattern, kind) remove by exact pattern and kind
    list_substitutions()               the set, in file order
    status()                           health, queue depth, recent failures

`speak` returns when the work is queued, not when it has been heard, which is
FR-4.5. A caller that blocked until its speech finished would be serialised
behind the audio, which is the opposite of what the queue is for.

**Every value a tool would persist is validated first.** A voice not among those
kokoro offers, or a regex that does not compile, is refused and nothing is
written. The tool call is the last moment the caller is still there to be told,
and the record outlives every restart, so an unvalidated write is a permanent
silent fault (FR-6.5).

`remove_substitution` takes the kind as well as the pattern, because a literal
`a` and a regex `a` are different entries.

*Discharges FR-4.5, FR-6.1, FR-6.5, FR-8.1.*

## Failure

**Failures are recorded in two places**, because the caller is gone by the time
most of them happen:

    log      $XDG_STATE_HOME/skid/skid.log, default ~/.local/state/skid/
    tool     status(), which returns recent failures and queue depth

A person debugging silence reads the log. An agent cannot, so it asks. FR-4.7
requires both and FR-4.6's word "reported" means this.

**What the design admits, which is more than the output path's two.** FR-1.5
buys a failure surface of a missing player and a bad file. The design around it
adds:

- a player that hangs, killed by FR-1.9 and reported
- a player that returns early, which breaks FR-2.1 silently and which skid
  cannot detect (FR-1.8)
- disk exhaustion, because FR-7.3 generates ahead without bound into files and
  FR-7.2 queues without bound behind it
- a config file present but malformed
- the model failing to load or download

**Disk exhaustion is the one that degrades worst**, and it is named rather than
designed away: FR-7.3's unboundedness was chosen with its cost stated. Every
message then fails in turn while the queue keeps churning through work that
cannot succeed, which is why it is reported per message and counted in
`status()`.

One clip failing does not cancel the rest of its array, and the queue behind it
still runs. A submission that produced no audible output at all is reported as a
whole rather than only as a run of individual failures.

*Discharges FR-1.5, FR-4.6, FR-4.7.*

## Concurrency

The backend is threaded, not asyncio. Three roles:

    accept    one thread per connection, short-lived: parse, enqueue, reply
    generate  one worker, running ahead of the player
    play      one, holding the mutex for the duration of each subprocess

kokoro is torch and generation blocks. Under asyncio without an executor it
would stall the event loop, which would stall accepts, which would break
FR-4.5's promise that submitting returns immediately.

`skid-mcp` is whatever the MCP SDK requires, and holds no state worth
synchronising.

*Discharges FR-4.5, FR-4.2.*

## What runs it

Python 3.12 exactly, and a uv project. kokoro refuses 3.13 and later, and this
machine's default interpreter is 3.14.7, so the pin is load-bearing rather than
conventional.

Dependencies: `kokoro`, the Anthropic MCP SDK for Python, a style-preserving
TOML library, and numpy, which arrives with kokoro. **Whether the MCP SDK
supports 3.12 is the open risk in the pin**: it was measured present under
3.14.7, which says it exists rather than that it installs here. Confirm it before
anything else is built, because FR-1.7 and FR-5.2 disagree if it does not.

Linux only in the first pass. The platform-specific surface is one line of
config: the player command.

*Discharges FR-1.6, FR-1.7, FR-7.6, FR-5.2.*

## What this deliberately leaves open

- **Voice names.** `af_heart` is a placeholder. The set kokoro offers has not
  been measured, because kokoro is not installed.
- **Whether the greeting window is settable through a tool** as well as the
  file. FR-3.4 requires only that it is configurable, and FR-7.1 says which
  route would win.
- **How the backend exits.** Idle timeout, explicit shutdown, or never.
  **This is not unconstrained**: an idle timeout that unloads the model makes
  FR-5.1's warm model sometimes-warm, and whatever is chosen has to keep the
  mtime re-read of FR-6.3 working.
- **The bound in FR-1.9**, which wants to be longer than any clip skid produces
  and is not measurable until kokoro is installed.

Recorded so that making one of these later does not look like discovering it.

## Not specified here, and why

**Nothing about task states, commit discipline or the gate.** Those are the
global `CLAUDE.md` and `docs/PROJECT.md`.

**No test plan.** That is stage 3 of `silo/docs/PATTERNS/how-a-change-gets-made.md`
and it derives from the requirements, not from this document.
