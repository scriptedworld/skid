# A validator you stop catching stops validating, and looks fine doing it

2026-08-28. A dependency changed which exception it raises. skid caught the old
class, the new one was not a subclass of it, and every schema refusal escaped
the wrapper that turns a refusal into a 400.

## What happened

`skid/routes.py` validates every tool call against the same document
`tools/list` publishes:

    try:
        COMPILED[tool].validate(body)
    except ValueError as exc:
        raise Refused(str(exc)) from exc

`ValueError` was correct when it was written, and the docstring above it said
so, with the date it was measured. wrench then landed `190b810`, making every
error crossing its boundary a `WrenchError`:

    ValidationError -> WrenchError -> Exception

`ValueError` is not in that chain. So the `except` caught nothing, `Refused` was
never raised, the exception reached Flask, and a call missing a required field
got a 500 where skid's contract says 400.

## Why this shape is worth a lesson

**The check did not start failing. It stopped happening.** Nothing in skid
reported an error. The validator still ran, still found the problem, and still
raised: the refusal simply went past the code that gives it meaning. From
anywhere except a test that asserts the refusal, an uncaught validator is
indistinguishable from one that passes everything.

That is the same family as
`deleting-an-endpoint-recreated-the-bug-it-removed.md`. Both are failures whose
symptom is an absence, and an absence is what nobody is looking at.

## What caught it

Two tests in `tests/test_routes.py` that assert a bad call is refused *by field*,
written when the schemas moved from being advertised to being enforced. They
went red inside a minute of running the suite. Nothing else in the project would
have noticed, and the service would have answered 500s until somebody sent a
malformed call by hand.

**A test that asserts the happy path would not have caught this.** Valid calls
were unaffected throughout. Only the refusal path was dead.

## What to do about it

**Catch the class the library documents, not the class you measured once.** The
measured behaviour is a fact about a version. `wrench.ValidationError` is what
wrench says it raises; `ValueError` was what it happened to raise.

**Assert the refusal, not only the acceptance.** For every check that turns a
bad input into an error, there is a test whose failure means the check stopped
running. Without one the check is unverified from the day it is written.

**Where an exception is deliberately not caught, say so.** `wrench.SchemaError`
is left to escape here on purpose: `validate` raises it for a document that will
not compile, which is a broken schema in this repository rather than a bad
argument from a caller, and 500 is the honest answer. A reader who does not know
that will eventually widen the catch to `WrenchError` and turn skid's own bug
into a 400 blamed on the caller.

## What it cost, and what it did not

An hour, and no user-visible failure: the break existed only between wrench
landing the change and the next run of skid's suite. Fixed at `f6c94b7`.

The wrench session measured the blast radius afterwards and skid is the only
Python consumer of wrench in the estate, so nothing else was carrying the same
catch. That was luck rather than design, and it is the reason the same failure
is worth recognising by shape rather than by remembering this instance.
