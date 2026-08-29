# FR-9.13, an uninstall removes what an install created

| ID | Requirement | |
|---|---|---|
| FR-9.13 | An uninstall removes **everything an install created**, and leaves nothing systemd still refers to. | [A] |

The socket is disabled before the unit files go, because systemd cannot disable
a unit whose file has gone and leaves the enabling symlink behind. The two plans
are held against each other, so a step added to one and not the other is caught.
