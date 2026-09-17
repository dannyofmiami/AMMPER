"""Import every library module in the `ammper` package.

These are cheap regression tests:

The driver scripts (AMMPER.py, AMMPERCLI.py, AMMPERBulk_aB.py,
AMMPERBulk_GAMMAfinal.py, AMMPERruns_aB.py, AMMPERruns_GAMMAFINAL.py) are
excluded here: they are top-level scripts that call `input()` or run a batch
immediately at import time, not importable libraries. That's a known item 
(wrap them in `main()` for real console-script entry
points) rather than something to paper over in this test.

@author: dannyofmiami
"""

import importlib
import pkgutil

import ammper

_DRIVER_SCRIPTS = {
    "ammper.AMMPER",
    "ammper.AMMPERCLI",
    "ammper.AMMPERBulk_aB",
    "ammper.AMMPERBulk_GAMMAfinal",
    "ammper.AMMPERruns_aB",
    "ammper.AMMPERruns_GAMMAFINAL",
}


def _library_module_names():
    return [
        module_info.name
        for module_info in pkgutil.iter_modules(ammper.__path__, prefix="ammper.")
        if module_info.name not in _DRIVER_SCRIPTS
    ]


def test_package_has_library_modules():
    assert _library_module_names(), "expected ammper package to contain library modules"


def test_every_library_module_imports_cleanly():
    for name in _library_module_names():
        importlib.import_module(name)


def test_entry_point_scripts_resolve_paths_without_repo_root_on_syspath():
    """Regression test for the ammper_paths ModuleNotFoundError bug.

    AMMPER.py, AMMPERCLI.py, AMMPERBulk_aB.py and AMMPERBulk_GAMMAfinal.py
    each do ``from ammper import paths as P`` at import time. That import must
    succeed purely because `ammper` is an installed package, not because
    something upstream inserted the repo root onto sys.path.
    """
    from ammper import paths as P

    assert P.ROOT
