# FR-5.1, a backend holds the model warm

| ID | Requirement | |
|---|---|---|
| FR-5.1 | A **backend process holds the model warm**, so a message does not pay model start-up before it is spoken. Wanted rather than required. | [A] |

Wanted rather than required, stated that way first-hand. A first pass that loads
the model per submission satisfies everything else here and is slower.

**Dropping it costs more than the start-up time.** An MCP with a supporting
background process is the criterion by which skid gets its own tree, so this
requirement and the repository boundary are one decision seen twice.
`../../PROJECT.md` carries it.

## Measured 2026-08-28, where this used to say unmeasured

**Time.** A first call against a cold socket waits **6.2 seconds** while kokoro
loads. Warm, the same call returns in milliseconds. That is what every
submission would pay if the model were loaded per submission.

**Memory, which is the larger number and was not anticipated here.** One warm
service holds **1.66 GB** RSS, and **1.31 GB** of it is private and dirty: model
weights and torch arenas, which no second process can share. Only the 0.34 GB of
mapped libraries would be.

    ps -o rss= -p $(systemctl --user show skid.service -p MainPID --value)
    grep -E '^(Rss|Pss|Private)' /proc/<pid>/smaps_rollup

A stdio server per client, which `docs/SPEC.md` records as permitted and slower,
therefore costs **1.31 GB per session**. Against the nine sessions running when
this was measured, that is **12.2 GB** where the current shape uses **2.0 GB**,
one service plus nine 35 MB shims, on a machine with 20 GB available.

**So "wanted rather than required" is still the right wording and no longer the
whole story.** Nothing here is violated by loading per submission. What it costs
is six seconds a message and, at estate scale, most of the machine's free
memory. The row stays as it is; the reason to keep it is now a figure.
