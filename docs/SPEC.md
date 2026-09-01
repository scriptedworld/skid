# skid, the spec

How skid is arranged. `docs/REQUIREMENTS/` says what must be true; this says what
is built so that it is.

Every section names the requirements it discharges. Nothing here restates a
requirement, and where this document and a requirement disagree, the requirement
wins and this is the defect.

## The shape: one service, and a script that speaks the protocol

**One long-lived process**, `skid`, reached over HTTP by every agent through a
per-client stdio script, `skid-mcp`.

    claude <-stdio-> skid-mcp <-plain HTTP-> skid

    transport   plain HTTP, on a unix socket at
                $XDG_RUNTIME_DIR/skid/skid.sock, mode 0600
    lifetime    systemd socket activation: started on first connection,
                restarted if it dies
    server      waitress, handed the socket systemd already bound
    app         flask, six routes named in skid/tools.py

`skid` holds the model, owns playback, and is the only writer of the config.
`skid-mcp` is the MCP server: it holds the six tool schemas and the dispatch,
and it holds nothing that survives a call.

**Nothing is cached on either side of the socket, which is the point.** MCP over
HTTP puts a session id in the service's memory, and a restart forgot it: the
service then answered every later request `404 Session not found` with a null
id, which a JSON-RPC client cannot match to anything it asked, so it waited
until something outside gave up. Measured 2026-08-28 at 1800 seconds. Removing
the session removes the failure rather than recovering from it.

**The cost is a new failure mode, and it is guarded.** With the schemas in one
process and the implementations in another, a tool can exist on one side only.
`skid/tools.py` is the single declaration both derive from, and
`tests/test_routes.py` asserts the route set and the tool set are equal in both
directions.

*Discharges FR-5.2, FR-5.1.*

### Why one process, which is a choice and not a necessity

**An HTTP transport is what makes one process possible.** An MCP server over
stdio is started per client, so several agents would mean several servers, and
exclusion would have to reach across them. Over HTTP the agents are clients of
one server, and the question does not arise.

**The requirements do not compel this.** FR-2.1 constrains the property and not
the mechanism, so a lock file is permitted, and a design of N stdio servers
each loading kokoro and taking a lock file around playback satisfies FR-2.1,
FR-4.4, FR-7.2, FR-7.3 and FR-4.2. It is slower and it is not forbidden. The one
row it fails is FR-5.1, which says of itself that it is "wanted rather than
required", so an argument that this design is forced would rest on a want.

**What that want costs, measured 2026-08-28.** The warm service holds 1.66 GB,
of which 1.31 GB is private and dirty and so cannot be shared with a second
instance. N stdio servers is therefore 1.31 GB per session: 12.2 GB across the
nine sessions running that day, against 2.0 GB for one service and nine 35 MB
shims, on a machine with 20 GB free. Cold start is 6.2 seconds.

So the design is still not forced and the alternative is no longer cheap to
wave at. FR-5.1 carries the commands.

What one process is chosen for:

- **The warm model**, FR-5.1, held by the only process there is.
- **One writer for the config**, which makes FR-7.1 and FR-7.8's write-through
  safe without a second locking scheme.
- **One place FR-4.4 is true**, rather than a protocol about whose submission is
  next.
- **One place a failure is visible**, which FR-4.7 requires.
- **No start protocol at all**, because systemd owns the socket and the
  lifetime. An earlier draft carried a lock file, a stale-socket unlink and a
  bind-then-rename to make the path mean ready. All of it is gone, and it was
  the part of this document nobody had run.

**The appeal to the repository boundary is not an argument.** `docs/PROJECT.md`
records that skid has its own tree because it is an MCP with a supporting
background process, and FR-5.1 records that the requirement and the boundary are
one decision seen twice. Citing the boundary as a second reason counts one
decision twice. The criterion still holds under this shape, and more plainly: a
persistent service is the background process.

*Discharges FR-2.1, FR-5.1.*

### What it buys the lock

**Because all playback happens in one process, the exclusion of FR-2.1 is an
in-process mutex.** No cross-process protocol about who is speaking.

**Stale state is systemd's problem now, not skid's.** An earlier draft claimed
freedom from it and had to be corrected, because a socket path outlives the
process that bound it: measured 2026-08-27, after `SIGKILL` the path remains, a
fresh bind gets `EADDRINUSE` and a client gets `ECONNREFUSED`. Under socket
activation the init system owns the socket's existence, so skid neither creates
nor cleans it.

The mutex is sufficient only while every clip is played by this process.

*Discharges FR-2.1, FR-7.3.*

## The socket, and who owns it

    ~/.config/systemd/user/skid.socket     ListenStream, SocketMode=0600
    ~/.config/systemd/user/skid.service    Type=notify, Restart=on-failure

    $XDG_RUNTIME_DIR/skid/skid.sock        the socket systemd creates

**skid does not create, bind or clean up the socket.** systemd creates it,
passes the listening file descriptor in on `$LISTEN_FDS`, starts skid on the
first connection, and restarts it if it dies. A client's first call after a
crash waits for the restart rather than meeting a dead path.

That deletes the whole start protocol an earlier draft carried: no lock file, no
stale-socket unlink, no bind-then-rename, no readiness race. **It was the part of
this document nobody had run**, and it is gone rather than tested.

### Why a unix socket rather than a TCP port

HTTP would ordinarily mean `127.0.0.1:<port>`, and every MCP client understands
that. **A localhost port is reachable by every process on the machine**, so any
local user could make the speakers talk, read the substitution set, and rewrite
the voice through the tools.

A unix socket has a path, and therefore has an owner and a mode. `SocketMode=0600`
in the unit file is the whole of the access control, and systemd applies it
before skid exists.

**A Linux abstract socket was considered and rejected on the same axis.**
Measured 2026-08-27: bind to `"\0skid"`, a second bind gets `EADDRINUSE` while
it is held, and after `SIGKILL` a fresh bind to the same name succeeds with
nothing left on disk. No staleness at all, and no path, so no permissions
either. Access would be scoped to the network namespace, which is the exposure
a TCP port has.

Socket activation gets the lifetime benefit that made the abstract socket
attractive, without giving up the mode bit.

*Discharges FR-5.1, FR-2.1, FR-5.4.*

### Not started by a client

Nothing about skid is spawned by an agent, so none of the stdio hazards of an
earlier draft apply: no inherited JSON-RPC stream to corrupt with a torch
warning, no detaching, no `/dev/null` for stdin. skid's stdout and stderr are
the service's, and journald takes them.

`Type=notify` means skid tells systemd when the model is loaded, so "the service
is active" and "skid can answer" are the same statement.

## What a submission is

    {"name": "silo", "messages": ["first", "second"]}

`name` identifies the submitting engine. `messages` is an array, always, and an
array of one is how a single message is sent. The tool rejects an absent name,
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

### Assignment

The backend holds, per name, which voice it speaks in and when its last clip
finished. In memory only, like the greeting table and for the same reason: a
restart costs one reassignment, and every voice on the shortlist was chosen by
ear, so no entry is a worse outcome than another.

**The pool is the config's `voices` list and nothing else.** An empty list means
assignment is off and the single `voice` setting speaks for everybody, which is
how skid behaved before this existed and is what an unconfigured machine gets.

**A name is given a voice the first time it speaks and keeps it.** Expired
assignments are released first, so a name arriving after a long quiet spell can
be handed something that has just come free rather than doubling up on a voice
still in use. Unheld voices go out in file order.

**When every voice is held, the one whose last clip is oldest goes out again.**
Assignment never refuses and never falls back to a single default, because
overflow names all sounding like the default is a larger collision than two
names sharing one voice. Two sessions using one name already share a voice, so
this reaches an accepted outcome by another road.

**The window is six hours, refreshed at the end of every clip.** Measured from
speech rather than from submission for the reason the greeting is: what a
listener experienced is when the clip finished. Until a name has spoken it runs
from when the voice was assigned, which is seconds earlier.

**A voice may name the pipeline it is generated through.** A kokoro voice is a
speaker and a pipeline is a phonemiser, and the two are separable; omitting it
means the code the voice id's first letter implies. That is what puts `if_sara`
on the list as an English speaker with an Italian accent rather than as an
Italian phonemiser reading English badly.

**Pipelines are cached rather than dropped on a change, and share one model.**
Assignment moves between voices on most submissions, so rebuilding each time
would pay model start-up constantly. The first pipeline built creates the model
and every later one is handed the same instance, so the cache costs a front end
rather than a second 1.6 GB.

**The assignment is applied at the top of the generation thread**, before any
clip is made, so a whole submission including its greeting is one voice. That
code cannot be allowed to raise: the thread signals completion by putting a
sentinel on the queue playback is blocked reading, so an exception before the
loop would leave playback waiting forever. A voice the config names and kokoro
does not know is recorded as a failure and stepped over.

`status` reports the current map as `assigned`, name to alias, which is how a
person asks who sounds like whom rather than working it out by listening.

*Discharges FR-10.1 through FR-10.9.*

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

**Measured end to end on this machine, 2026-08-27, before any of skid existed.**
`KPipeline(lang_code='a')` with `voice='af_heart'` on "Hi, silo here." returned
42000 samples, 1.75 seconds, written by `wave` as **mono, 16-bit, 24000 Hz** and
played by `paplay` on the default sink. So the output path of FR-1.1 through
FR-1.5 is known to work as specified rather than assumed to.

kokoro returns float samples; the writer scales to signed 16-bit little-endian.
That conversion is the whole of what sits between the engine and the file.

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

`$XDG_CONFIG_HOME/skid/config.yaml`, defaulting to `~/.config/skid/config.yaml`.

    "greeting_window_seconds": 30
    "player": "paplay {file}"
    "substitution":
      - "kind": "literal"
        "pattern": "kokoro"
        "replacement": "koh koh roh"
    "voice": "af_heart"

**YAML, read and written by wrench against a schema in `skid/schemas.py`.**
Every structured file in the ecosystem is YAML; skid chose TOML 83 minutes
before that was recorded, so it predates the decision rather than having ignored
it, and moved on 2026-08-28.

The form above is wrench's canonical output, quoted keys and sorted names. A
person may write plain unquoted YAML and it loads; what skid *emits* is
canonical. `docs/config.sample.yaml` is the readable version.

**The schema is validated on the way in and on the way out.** A key skid does
not know is refused by name rather than ignored, so `voce: af_bella` fails at
start-up instead of silently keeping the default voice. Validating the write is
what stops a tool storing a shape skid could never read back.

**The file is the record**, and the backend is its only writer.

**When it is read.** The backend checks the file's mtime before each submission
is processed and re-reads it when it has changed. That is what makes FR-6.3's
own observable true for both routes: setting the voice by either one changes
what the next clip is spoken in. Reading once at start would give the tool route
effect and the file route none, which is two routes that do not agree.

**How it is written.** wrench writes bytes to a temporary file beside the target
and renames it into place, its own FR-6.3, so a kill during a write cannot leave
a truncated config and lose the substitution set. skid no longer hand-rolls
that. The read-modify-write is done under the same mtime check, so a hand edit
made since the last read is not silently discarded.

**Writing preserves the order of substitution entries**, because FR-8.4 makes it
meaningful. A YAML sequence carries its order in the decoded structure, so this
needs nothing that preserves formatting.

**It does not preserve comments, and that clause is retired.** It existed
because a comment was the only place a reason could live, which is what made a
style-preserving round trip worth a dependency. `docs/config.sample.yaml` is
that place now, and the live file carries values alone. FR-7.1 records the
retirement.

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
- **the backend absent or wedged**, which every caller meets for the whole
  window between a crash and the next start

**Every call has a bounded wait**, and exceeding it is a tool error naming the
service rather than the call (FR-5.3). Socket activation removes the absent
case, since a connection starts the service, but it does not remove the wedged
one: a process that is running and not answering still leaves a client waiting,
and `Type=notify` makes that less likely rather than impossible.

That sentence existed at `fd42bdf`, was lost when this section was rewritten,
and nothing noticed because no requirement held it. FR-5.3 is now the row that
does.

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

The HTTP surface is the six plain routes named in `skid/tools.py`, served on the
socket systemd hands over. The service imports no MCP SDK; the protocol lives in
`skid-mcp`.

*Discharges FR-4.5, FR-4.2.*

## The queue is a directory

`$XDG_RUNTIME_DIR/skid/spool`, one JSON file per submission, taken in
lexicographic name order.

    000042-silo.json          waiting
    taken/000042-silo.json    being spoken right now
    000043-wrench.json.tmp    half written, removed at start-up

**The text is what is durable, not the audio.** The entry is written before
`submit` returns, which is what puts something behind FR-4.5's promise: before
this the queue was a `deque`, so "queued" meant accepted by something that
forgets on restart, and the caller had already been told yes. Clips stay a cache
under `clips/` and may be deleted freely, because losing one costs regeneration
time rather than data.

A spool of generated audio would not do it. It protects only work already
generated, and the window this closes is the one between the call returning and
the first clip existing.

**Order is the sequence in the name, never the file's timestamp.** Creation time
is generation order, which matches submission order today only because one
submission is handled at a time, and would diverge silently the moment two are
prepared at once. FR-4.3 and FR-4.4 both rest on it.

**Written to `.tmp` and renamed into place**, so a file at its final name is a
whole file. A `kill -9` mid-write leaves a temporary that start-up removes,
rather than a truncated entry that parses to nonsense and blocks the queue.

**Taken means moved.** An entry lives under `taken/` while it is spoken and is
removed when the attempt ends, however it ends. That is what makes a poison
entry impossible: removing only on success would retry a bad entry forever with
everything behind it waiting. Anything still under `taken/` at start-up was
interrupted, and is discarded rather than replayed, because FR-4.4 makes a
submission indivisible and replaying means re-hearing what was already heard.

So the guarantee is precise and smaller than "nothing is lost": accepted and not
yet started is never lost; being spoken when the process died is dropped.

**Restart, not reboot.** tmpfs, so a reboot starts silent rather than reading
back an hour of chatter about work that finished before it.

**Age is capped where depth is not.** A submission older than
`expiry_seconds`, five minutes by default, is discarded with a line in the log
rather than spoken. Downtime counts toward it, so a service away for ten minutes
does not come back and read a ten minute old backlog. A thousand submissions
inside the window are all spoken: age is what makes a message not worth hearing,
and depth is not.

*Discharges FR-4.8, FR-4.9, FR-7.2, FR-4.3.*

## What runs it

Python 3.12 exactly, and a uv project. kokoro **declares** `<3.13,>=3.10`, and
this machine's default interpreter is 3.14.7, so the pin is load-bearing rather
than conventional.

**The declaration is not a ceiling.** Told first-hand 2026-08-28: kokoro runs on
3.13 and 3.14 and has simply not had a release since. A resolver still enforces
what is declared, and nothing in skid needs a newer interpreter, so the pin
costs nothing and stays.

Dependencies: `kokoro`, `flask` and `waitress` for the service, the Anthropic
MCP SDK for Python for the script alone, `httpx` between them, `wrench` for the
config and the spool, and numpy, which arrives with kokoro.

wrench is not on a package registry, so `[tool.uv.sources]` names it by git URL
and `uv` fetches it like any other dependency. That resolves on a standalone
clone, which the relative path it replaced did not.

It is installed as an ordinary copy. An editable install was once required, and
a PEP 660 import hook is something mypy cannot follow, so wrench's `py.typed`
was invisible and every import of it was an error.

kokoro 0.9.4 and its torch stack install and run under 3.12.14, and the WAV
writer is the stdlib's.

**The MCP SDK under 3.12 was the open risk in the pin and is now settled.**
Measured 2026-08-28 on skid's own interpreter: `mcp` 2.1.1 under 3.12.14. The
earlier reading of 2.0.0 under 3.14.7 was this machine's default rather than
skid's, so it said the SDK exists rather than that it is present here.

**waitress rather than gunicorn**, because it serves a socket that is already
bound and listening, which is exactly what socket activation hands over.
`waitress.serve(app, sockets=[sock])`, proved against a real unix socket rather
than assumed; `waitress.serve(app, **kw)` hides the parameter from signature
inspection and `Adjustments` is where it is visible.

### Installed as a uv tool

skid is installed with `uv tool install`, so it gets its own environment and its
own pinned interpreter rather than depending on whatever `python3` means on the
machine. That is what makes FR-1.7's pin hold in practice rather than only in
`pyproject.toml`.

The installer also writes the two systemd user units and reloads the daemon.
Those units are what own the socket and the lifetime, so an install that skipped
them would leave a service nothing starts.

Nothing about this is built yet.

Linux only in the first pass, and the systemd dependence makes that sharper than
it was: the platform-specific surface is now the player command **and** the
service manager.

*Discharges FR-1.6, FR-1.7, FR-7.6, FR-5.2.*

## What this deliberately leaves open

- ~~**Voice names.**~~ **Settled by measurement 2026-08-27.** kokoro 0.9.4
  offers 54 voices, listed by `hexgrad/Kokoro-82M` under `voices/`, named
  `<lang><gender>_<name>`: `af_` and `am_` American, `bf_` and `bm_` British,
  then `e`, `f`, `h`, `i`, `j`, `p` and `z` for the other languages. `af_heart`
  turned out to be a real voice rather than the placeholder it was written as.
  FR-6.5's validation checks against that set.
- **Whether the greeting window is settable through a tool** as well as the
  file. FR-3.4 requires only that it is configurable, and FR-7.1 says which
  route would win.
- **How the backend exits.** Idle timeout, explicit shutdown, or never.
  **This is not unconstrained**: an idle timeout that unloads the model makes
  FR-5.1's warm model sometimes-warm, and whatever is chosen has to keep the
  mtime re-read of FR-6.3 working.
- **Which remedy the bound in FR-1.9 wants.** Speech runs at about 15.5
  characters per second of audio, so the 300 second bound clears roughly 4,660
  characters and cuts off anything longer, and nothing caps a message at
  submission. `NEXT_STEPS.md` states the three options open to it.

Recorded so that making one of these later does not look like discovering it.

## Not specified here, and why

**Nothing about task states, commit discipline or the gate.** Those are the
global `CLAUDE.md` and `docs/PROJECT.md`.

**No test plan.** `docs/TEST_PLAN.md` is a separate stage and derives from the
requirements, not from this document.
