# FR-1.13, one Python, and a wheel for everything compiled

| ID | Requirement | |
|---|---|---|
| FR-1.13 | All three packages declare the same single Python minor version, and every compiled dependency in the lock installs from a published wheel for it. Today that is **Python 3.14 only**. | [A/D] |

The version is a ruling: 3.14, because the estate runs on 3.15 where a
repository's dependencies allow it and on 3.14 where they do not. The wheel
half is derived from it, since that is what "allow" means in practice.

Against PyPI and the cu126 index, for every locked version, each compiled
dependency has a cp314 wheel, torch 2.14.1+cu126 included. For 3.15, spaCy 3.8.16 and its compiled stack (thinc, blis, cymem,
preshed, murmurhash, srsly), curated-tokenizers, pyyaml and triton publish
none. The tables are in clank, `tasks/skid/dependencies/25-what-runs-on-3-14-and-3-15`.

kokoro 0.9.4 and misaki 0.9.4 declare `requires_python <3.13`. Both are pure
Python, both run on 3.14, and uv enforces only the lower bound of a
dependency's `requires-python`, so the declaration installs nothing and
refuses nothing. No override carries it. A kokoro release that raises its
floor above 3.14 is the case that would bite, and the lock would refuse it.

One version and not a range, so `uv tool install` builds each tool
environment on the interpreter the suite ran on, whatever the machine's
default is. The same version in all three packages, so the two tool
environments cannot resolve the contract they share onto different
interpreters.

The wheel half is what the version rests on. A compiled dependency that
stops publishing a wheel for this version still installs, by building from
source, and a build that succeeds on this machine says nothing about the
next one. So it fails the row rather than passing quietly.

Move the version when the dependencies allow 3.15: re-run the wheel survey,
change all three `requires-python` lines together, and re-lock.
