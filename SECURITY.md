# Security

## Reporting

Report a vulnerability privately, through GitHub's private vulnerability
reporting on this repository. Do not open a public issue for one.

## What skid is, in security terms

skid is a single-user desktop service. It runs as your own user under
`systemd --user`, never as root, and it holds no credentials of any kind. The
config file carries a voice name, a shortlist of voices, a player command line,
three timeouts and a list of pronunciation substitutions.

## The trust boundary is the socket, and it is the whole of the access control

skid listens on a unix socket at `$XDG_RUNTIME_DIR/skid/skid.sock`, mode 0600,
inside a directory at mode 0700. There is no TCP port and nothing binds to an
address. Reaching the socket means being the user who owns it.

That single check is deliberate, because reaching the tools is not a small
thing. Anything that can open the socket can:

- make the machine speak arbitrary text aloud, at whatever the system volume is;
- change the voice, and have that written to the config file;
- add and remove pronunciation substitutions, also written to the config;
- read back the substitutions, the current voice, the queue depth, recent
  failures and which name has been assigned which voice.

Treat access to the socket as equivalent to access to the account.

## The player command is code execution, and it is config-only

skid plays a clip by running the command named by `player` in the config,
substituting `{file}`. The command is split with `shlex` and run without a
shell, so there is no shell metacharacter to inject through a filename, but the
command itself is executed as you.

**No tool and no HTTP route can set it.** The only way to change the player is
to write `~/.config/skid/config.yaml`, which already requires the account. So a
config file you did not write is code execution as you, and a config file is
input to be trusted at the same level as a shell profile.

## Two things worth knowing before you run it

**Substitution patterns may be regular expressions**, and `add_substitution`
takes one over the socket and persists it. A pattern that backtracks
catastrophically is applied to every later submission, which is a denial of
service on your own speech output until the entry is removed. Patterns that do
not compile are refused when they are added.

**kokoro fetches its model weights over the network** on first use, into
`~/.cache/huggingface`. That is the only outbound traffic skid causes, and it
happens once.

## What the installer may write

Everything inside `$HOME`, and nothing outside it. The systemd user units, the
tool environment, `~/.local/bin`, and the MCP client registration. Nothing needs
root, and `--dry-run` prints every command before any of it runs. This is a
stated requirement rather than an accident of the implementation, and
`docs/REQUIREMENTS/putting-it-on-a-machine/` holds the rows and the tests.

## Not in scope

Multi-user or shared-machine isolation. skid assumes one user, one set of
speakers, and one account boundary. Running it where several people share an
account gives all of them the socket.
