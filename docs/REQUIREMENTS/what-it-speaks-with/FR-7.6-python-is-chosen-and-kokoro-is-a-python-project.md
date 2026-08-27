# FR-7.6, Python is chosen, and kokoro is a Python project

| ID | Requirement | |
|---|---|---|
| FR-7.6 | skid is written in **Python**, because kokoro is a Python project and one language is preferred to two. | [A/D] |

Settled 2026-08-27, at the id the open question carried. The rule was stated
first-hand, the fact it turns on was measured, and the answer is what the two
give together.

## The rule

Stay in one language if kokoro is a Python project. If it were only a binding
over something else, another language would be considered, probably Rust.

## The measurement

    curl -sS https://pypi.org/pypi/kokoro/json

    requires_dist   huggingface-hub, loguru, misaki[en]>=0.9.4, numpy, torch,
                    transformers
    repository      https://github.com/hexgrad/kokoro
    version         0.9.4

**kokoro is a Python project, not a binding.** Its dependencies are Python
libraries and the model runs on PyTorch, so the Python package is the
implementation rather than a wrapper around one.

ONNX, which the original question raised, is a portable format a trained model
can be exported to and then run from other languages. Exports of this model do
exist as separate projects. That makes a port *possible* rather than *free*, and
it is not what this package is.

FR-5.2's MCP SDK for Python is a second and independent reason, so nothing here
rests on one measurement.

## What the measurement also forced

kokoro declares `requires_python <3.13,>=3.10`, which is why FR-1.7 exists.
