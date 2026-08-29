# FR-9.13, an uninstall removes what an install created

| ID | Requirement | |
|---|---|---|
| FR-9.13 | An uninstall removes **everything an install created**, and leaves nothing systemd still refers to. | [A] |

The list is FR-9.4's, which is what makes this checkable by a person rather than
only by a test: the paths an install named are the paths an uninstall must
account for.

**The socket is disabled before the unit files are removed.** systemd cannot
disable a unit whose file has gone, so the reverse order leaves the enabling
symlink behind, pointing at nothing, and the machine is not back where it
started. The ordering is the mechanism; the property is that nothing is left.

The two plans are held against each other rather than each against a list
written by hand, so a step added to one and not the other is caught.
