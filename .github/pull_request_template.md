## What changed

One or two sentences. The reasoning belongs in the file the change touches, not
here.

## The requirement it serves

Which `docs/REQUIREMENTS/` row, or the new row this adds. Behaviour comes from a
requirement first. A change with no observable behaviour, such as a refactor or
a docs pass, says so instead.

## Checks

- [ ] `.venv/bin/python -m pytest -o addopts= -q` passes, and the count is
      stated below
- [ ] every new test carries a `# COVERS: FR-x.y | kind` mark naming a row that
      exists
- [ ] `.venv/bin/python -m ruff check .` is clean
- [ ] `.venv/bin/python -m mypy src tests` reports nothing new beyond kokoro's
      missing `py.typed`
- [ ] no new suppression pragma, or one registered in `docs/SUPPRESSIONS.md`
      with the question and the answer
- [ ] `docs/SPEC.md` updated if the arrangement moved

Test count before and after:

## Anything you could not check

Say so plainly. A check you could not run is worth more written down than
guessed at, and `CONTRIBUTING.md` lists what does not resolve from a clone.
