# A validator you stop catching stops validating

`routes.py` turns a schema refusal into a 400 by catching what `validate`
raises. wrench changed that from `ValueError` to `wrench.ValidationError`, which
derives from `wrench.Error` and not from `ValueError`, so the `except` caught
nothing, the exception reached Flask, and every malformed call got a 500.

Nothing reported an error. The validator still ran and still raised; the
refusal went past the code that gives it meaning. An uncaught validator and one
that passes everything are indistinguishable from anywhere except a test on the
refusal path. Two such tests in `test_routes.py` went red on the next run, and
nothing else would have noticed. Valid calls were unaffected throughout, so a
happy-path test could not have caught it.

`except ValueError` was never a statement about wrench's contract, only about
what one version happened to raise. Nor could wrench have fixed it by
subclassing: `{"count": -1}` fails on a minimum and `{"count": "three"}` fails
on a type, `ValueError` excludes the second by definition, so a validation
failure is a subclass of neither.

`wrench.SchemaError` is left uncaught here on purpose, because a document that
will not compile is skid's bug and 500 is the honest answer; widening to
`wrench.Error` would blame the caller for it.
