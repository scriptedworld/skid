---
name: Feature request
about: Something skid should be able to do
labels: enhancement
---

## What you are trying to do

The task, rather than the feature. What are you listening for, and what does not
work today.

## What you have tried

Whether the config gets you part of the way. `docs/config.sample.yaml` lists
every setting with its default.

## Scope worth checking first

Two things skid deliberately does not do, and a request that needs either is a
change of direction rather than a feature:

- it never opens an audio device, so device selection, mixing and volume are the
  operating system's;
- it never overlaps clips, so anything needing two voices at once is out.

`README.md` has the reasoning for both.

## What it would take

If the behaviour is observable, say what would be true of a run once it worked.
That is the form a requirement takes here, and it is what the change would be
built and tested against.
