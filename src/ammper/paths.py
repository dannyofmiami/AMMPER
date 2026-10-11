"""
Path resolution for the reorganized AMMPER tree (August 2026).

`ammper_paths` — this module lives inside the installed
`ammper` package, so it resolves correctly wherever the package is imported
from, unlike a root-level module (which only importable when the repository
root happens to be on `sys.path`). The root-level `ammper_paths.py` is kept as
a thin backward-compatible shim over this module.

Import this module instead of hardcoding paths. It works no matter which
directory a script is launched from, because everything is resolved relative
to this file's own location rather than the process working directory:

    from ammper import paths as P
    df = pd.read_csv(P.ab_experimental("AlamarblueRawdataWTKGy.csv"))
    for root, dirs, files in os.walk(P.bulk_aB("WT_Basic_0")):
        ...

Two layouts, one API
--------------------
* **In a clone** (``pip install -e .`` from a checkout): everything is under the repository root,
  exactly as before. Downloads and results go in the repo (``data/radiation_input/ritracks/``,
  ``results/``).
* **Installed** (a wheel, ``pip install .``): the read-only files the app needs ship *inside* the
  package (``ammper/data``: fluence tables, apoptosis data, the dataset manifest and the 150 MeV
  RITRACKS folder; ``ammper/gui``: the GUI, fonts and images). Anything the app writes or
  downloads goes to a user-writable folder: ``$AMMPER_HOME`` if set, else ``~/ammper``
  (``~/ammper/results``, ``~/ammper/data/radiation_input/ritracks``, ...).

OLD -> NEW path map:
    abFinalPlots/                    -> data/experimental/alamarblue/
    aBGAMMA/                         -> data/experimental/alamarblue_gamma/
    Biosentineldata/                 -> data/experimental/biosentinel/
    radiationData/                   -> data/radiation_input/ritracks/
    *Fluence*_data.txt               -> data/fluence/
    Results_Bulk_aB/                 -> results/bulk_aB/
    Results_Bulk_GAMMAFINAL/         -> results/bulk_gamma/
    Results/                         -> results/single_runs/
    smac3_output/                    -> results/smac3_output/

@author: dannyofmiami    
"""

import json
import os
import sys

PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(PKG_DIR))

#: True when running from a checkout of the repository (including ``pip install -e .``).
IN_CLONE = (os.path.isfile(os.path.join(_REPO_ROOT, "pyproject.toml"))
            and os.path.isdir(os.path.join(_REPO_ROOT, "analysis")))

#: The user-writable root: the repo in a clone, else $AMMPER_HOME or ~/ammper.
#: (Named ROOT for backward compatibility: in a clone it is the repository root, as before.)
if IN_CLONE:
    ROOT = _REPO_ROOT
else:
    ROOT = os.path.abspath(os.path.expanduser(os.environ.get("AMMPER_HOME") or "~/ammper"))

SRC = os.path.dirname(PKG_DIR)
AMMPER_PKG = PKG_DIR

#: Read-only files that ship inside the package (same in a clone and in an installed wheel).
BUNDLED_DATA = os.path.join(PKG_DIR, "data")
GUI_DIR = os.path.join(PKG_DIR, "gui")

DATA = os.path.join(ROOT, "data")
EXPERIMENTAL = os.path.join(DATA, "experimental")                 # manuscript analysis inputs (clone only)
AB_EXPERIMENTAL = os.path.join(EXPERIMENTAL, "alamarblue")
AB_GAMMA_EXPERIMENTAL = os.path.join(EXPERIMENTAL, "alamarblue_gamma")
BIOSENTINEL = os.path.join(EXPERIMENTAL, "biosentinel")

#: Downloaded RITRACKS folders (writable). The 150 MeV tutorial folder ships bundled instead.
RADIATION_INPUT = os.path.join(DATA, "radiation_input", "ritracks")
BUNDLED_RITRACKS = os.path.join(BUNDLED_DATA, "radiation_input", "ritracks")
FLUENCE = os.path.join(BUNDLED_DATA, "fluence")
APOPTOSIS_DATA = os.path.join(BUNDLED_DATA, "experimental", "Apoptosis_Data.txt")
RITRACKS_MANIFEST = os.path.join(BUNDLED_DATA, "radiation_input", "MANIFEST.json")

RESULTS = os.path.join(ROOT, "results")
BULK_AB = os.path.join(RESULTS, "bulk_aB")
BULK_GAMMA = os.path.join(RESULTS, "bulk_gamma")
SINGLE_RUNS = os.path.join(RESULTS, "single_runs")
SMAC3_OUTPUT = os.path.join(RESULTS, "smac3_output")

FIGURES = os.path.join(ROOT, "figures")


def _join(base, *parts):
    return os.path.join(base, *parts) if parts else base


def ab_experimental(*parts):
    """alamarBlue plate-reader CSVs (proton experiments)."""
    return _join(AB_EXPERIMENTAL, *parts)


def ab_gamma_experimental(*parts):
    """alamarBlue plate-reader data for the gamma experiments."""
    return _join(AB_GAMMA_EXPERIMENTAL, *parts)


def biosentinel(*parts):
    """BioSentinel/LEIA source spreadsheets."""
    return _join(BIOSENTINEL, *parts)


def radiation_input(*parts):
    """RITRACKS-generated proton track data, keyed by proton energy.

    Looks in the writable download folder first, then in the data bundled with the package
    (the 150 MeV tutorial folder), and returns the first that exists. If neither has it, the
    writable path is returned (that is where ``ammper data pull`` would put it).
    """
    for root in (RADIATION_INPUT, BUNDLED_RITRACKS):
        candidate = _join(root, *parts)
        if parts and os.path.exists(candidate):
            return candidate
    return _join(RADIATION_INPUT, *parts)


def apoptosis_data():
    """The apoptosis dose-response table read by the ROS damage model."""
    return APOPTOSIS_DATA


def fluence(*parts):
    """Deep-space and GCRSim fluence tables."""
    return _join(FLUENCE, *parts)


def load_ritracks_manifest():
    """The RITRACKS dataset manifest: every energy folder that exists in
    the full (Zenodo) dataset, which one ships with the package as the tutorial
    subset, and the pinned Zenodo record plus per-folder size/checksum. See CONTRIBUTING.md."""
    with open(RITRACKS_MANIFEST) as fh:
        return json.load(fh)


def bulk_aB(*parts):
    """Simulation output for the alamarBlue proton runs."""
    return _join(BULK_AB, *parts)


def bulk_gamma(*parts):
    """Simulation output for the exploratory gamma runs."""
    return _join(BULK_GAMMA, *parts)


def single_runs(*parts):
    """Simulation output for individual (non-bulk) runs."""
    return _join(SINGLE_RUNS, *parts)


def figures(*parts):
    """Output directory for generated figures; created on demand."""
    target = _join(FIGURES, *parts)
    directory = target if not parts else os.path.dirname(target)
    if directory:
        os.makedirs(directory, exist_ok=True)
    return target


def add_src_to_path():
    """Make the bare intra-package simulation imports resolve."""
    for path in (SRC, AMMPER_PKG):
        if path not in sys.path:
            sys.path.insert(0, path)


def ensure_writable_home():
    """Create the user-writable root (a no-op in a clone). Returns it."""
    os.makedirs(ROOT, exist_ok=True)
    return ROOT


add_src_to_path()
