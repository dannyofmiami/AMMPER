"""
Backward-compatible shim over `ammper.paths`.

This module used to hold the canonical path-resolution logic, but as a
root-level module it can only be imported when the repository root happens to
be on `sys.path` (e.g. because a caller inserted it manually) — it is not part
of the installed `ammper` package. That broke the entry-point scripts that
were later moved into `src/ammper/` (they run with the script's own directory
on `sys.path[0]`, not the repo root).

The implementation now lives at `src/ammper/paths.py`, which is
importable anywhere the `ammper` package is installed. This file re-exports it
so existing call sites (`import ammper_paths as P`) keep working unchanged.
"""

from ammper.paths import *  # noqa: F401,F403
from ammper.paths import (  # noqa: F401
    AB_EXPERIMENTAL,
    AB_GAMMA_EXPERIMENTAL,
    AMMPER_PKG,
    BIOSENTINEL,
    BULK_AB,
    BULK_GAMMA,
    DATA,
    EXPERIMENTAL,
    FIGURES,
    FLUENCE,
    RADIATION_INPUT,
    RESULTS,
    ROOT,
    SINGLE_RUNS,
    SMAC3_OUTPUT,
    SRC,
    add_src_to_path,
)
