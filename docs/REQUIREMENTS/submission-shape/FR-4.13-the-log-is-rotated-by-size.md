# FR-4.13, the log is rotated by size

| ID | Requirement | |
|---|---|---|
| FR-4.13 | When the log would pass 1 MiB it is moved aside as `skid.log.1`, older files shift up one, and at most three old files are kept. | [A] |

I said we can rotate them out once every submission is logged, since the log
then grows with use rather than only with failure.

The sizes are a preference, not a measurement. A line is about 80 bytes, so
1 MiB holds around thirteen thousand lines, and four files cover weeks at the
rate the team speaks. skid rotates its own log because it is the only writer,
and a separate logrotate setup would be a second thing to install for a file
one process owns.
