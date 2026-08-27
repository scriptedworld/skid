# FR-1.7, skid runs on an interpreter kokoro supports

| ID | Requirement | |
|---|---|---|
| FR-1.7 | skid runs on a Python version kokoro supports. Today that is **Python 3.12 only**. | [D] |

Derived from FR-1.1 and measured 2026-08-27. A requirement to generate speech
with kokoro is a requirement to run where kokoro runs.

    curl -sS https://pypi.org/pypi/kokoro/json    requires_python <3.13,>=3.10

Against skid's own `requires-python = ">=3.12"`, the intersection is 3.12 alone,
and `pyproject.toml` says so rather than leaving a range that resolves to an
interpreter kokoro refuses.

**This machine's default interpreter is 3.14.7, which kokoro does not support.**
So skid does not run on the interpreter a bare `python3` reaches here, and uv
fetches 3.12 for it.

It also dates one measurement elsewhere: `mcp` 2.0.0 was measured installed
under 3.14.7, which is not the interpreter skid will use. That says the SDK
exists, not that it is present for this project.

Retire this row when kokoro supports a newer Python, rather than editing the
version in place, so that what it was pinned to stays legible.
