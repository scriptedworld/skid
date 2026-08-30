# skid's own layer. No template writes this file, and the Justfile imports it
# first, so what is here beats the language layer and the base.
#
# WHY `checks` IS OVERRIDDEN. base.just's `_verdict` runs `bolt <jig> .` with no
# way to pass a flag, and skid's common jig needs `--definitions skid`. Without
# it `traceability` looks for the retired single-file `REQUIREMENTS.md` and
# `suppressions` for `SUPPRESSIONS` at the root, and both fail. Measured: `bolt
# common-quality .` reports those two, and `bolt --definitions skid
# common-quality .` reports success.
#
# This belongs in `_verdict` rather than here. A `_verdict jig *flags:` would
# fix it once for every tree that needs definitions, and this override goes when
# that lands. Reported to the factory rather than only worked around.

# a verdict from a jig that needs flags, otherwise base.just's `_verdict`
_verdict-with jig *flags:
    #!/usr/bin/env bash
    set -euo pipefail
    out=$(bolt {{ flags }} "{{ jig }}" .)
    result=$(printf '%s\n' "$out" | tail -1)
    if [ ! -f "$result" ]; then
        echo "REFUSED: bolt wrote no result for {{ jig }}" >&2
        printf '%s\n' "$out" >&2
        exit 1
    fi
    if grep -q '"success": *true' "$result"; then
        echo "pass  {{ jig }}  $result"
    else
        echo "FAIL  {{ jig }}  $result" >&2
        exit 1
    fi

# everything: quality, tests, coverage, secrets
checks:
    @just _verdict-with common-quality --definitions skid
    @just _verdict python-std-quality
    @just leak-scan
