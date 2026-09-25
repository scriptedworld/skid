# A same-size edit reuses the stale bytecode

Mutation testing here means editing the source, running the suite, and reading
whether a test caught it. Clear `__pycache__` between mutations or the answer
describes code that is no longer on disk.

Python validates a cached `.pyc` against the source's mtime in whole seconds and
its size. A mutation that changes neither reuses the stale bytecode, so the suite
runs the unmutated code and reports a pass. The mutation looks uncaught in
exactly the way a missing assertion does.

`return 1` to `return 0` is the shape to watch: same length, and fast enough to
land inside the same mtime second as the edit before it.

    find . -name __pycache__ -prune -exec rm -rf {} +

Run that between every mutation, not once at the start. The cost of forgetting is
a test that appears not to cover something it covers, or a test that appears to
cover something it does not, and both send the next change in the wrong
direction.

`PYTHONDONTWRITEBYTECODE=1` avoids it for a whole mutation session and is the
better habit where several mutations run in a row.
