# A validator you stop catching stops validating

`routes.py` turns a schema refusal into a 400 by catching what `validate`
raises. wrench changed that from `ValueError` to `wrench.ValidationError`, which
derives from `WrenchError` and not from `ValueError`, so the `except` caught
nothing, the exception reached Flask, and every malformed call got a 500.

Nothing reported an error. The validator still ran and still raised; the
refusal went past the code that gives it meaning. An uncaught validator and one
that passes everything are indistinguishable from anywhere except a test on the
refusal path. Two such tests in `test_routes.py` went red on the next run, and
nothing else would have noticed.

Valid calls were unaffected throughout, so a happy-path test could not have
caught it.

Catch the class the library documents, not the one measured once: the measured
behaviour is a fact about a version. `wrench.SchemaError` is left uncaught here
on purpose, because a document that will not compile is skid's bug and 500 is
the honest answer; widening the catch to `WrenchError` would blame the caller
for it.
