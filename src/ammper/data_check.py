# -*- coding: utf-8 -*-
"""
Checks whether the RITRACKS radiation-track data a simulation needs is
present on disk.

A clone may carry only the 150 MeV Proton tutorial subset
(data/radiation_input/ritracks/150/) -- GCRSim and Deep Space each need
most or all of the full dataset (see CONTRIBUTING.md), which is then
fetched separately via `ammper data pull`. Without this check,
a missing energy folder surfaces as a raw FileNotFoundError deep inside
genTraverse_groundTesting/genTraverse_deepSpace's np.genfromtxt call, or,
in the GUI's case, as an unhandled exception inside a button-click handler
that leaves the window looking "stuck" with no visible error at all.

@author: dannyofmiami
"""

import os

import numpy as np

from ammper import paths as P


class MissingRadiationDataError(Exception):
    """Raised when a simulation needs RITRACKS data that isn't on disk."""


def _folder_name_for_energy(value, known_folder_names):
    """Resolve a numeric proton energy (as read from a fluence table) to
    the ritracks/<name>/ folder it corresponds to, matching by value
    rather than string formatting -- the fluence tables and the folder
    names don't always format the same float identically (e.g. a table
    row of "357.10" for the folder named "357.1")."""
    target = float(value)
    for name in known_folder_names:
        if abs(float(name) - target) < 1e-6:
            return name
    # Not in the manifest (shouldn't happen for real fluence-table values,
    # but don't crash the availability check itself over it).
    return str(int(target)) if target.is_integer() else str(target)


def required_ritracks_energies(radType):
    """Which ritracks/<name>/ folders this radType needs, derived from the
    same fluence tables the simulation itself reads (P.fluence(...)) --
    not hardcoded a second time, so it can't drift from the real
    dependency."""
    if radType == "150 MeV Proton":
        return {"150"}
    if radType not in ("GCRSim", "Deep Space"):
        return set()

    known = P.load_ritracks_manifest()["full_energies"]
    if radType == "GCRSim":
        raw = np.genfromtxt(P.fluence("GCRSimFluence_data.txt"), skip_header=1)
    else:
        # The CLI/GUI only ever load the 0.1-month table today.
        raw = np.genfromtxt(P.fluence("DeepSpaceFluence0.1months_data.txt"))
    return {_folder_name_for_energy(v, known) for v in raw[:, 0]}


def _has_data(name):
    path = P.radiation_input(name)
    return os.path.isdir(path) and bool(os.listdir(path))


def missing_ritracks_energies(folder_names):
    """Which of these ritracks/<name>/ folders aren't on disk (a folder with nothing in
    it counts as missing)."""
    return sorted((n for n in folder_names if not _has_data(n)), key=float)


# `ammper data pull <target>` shortcut for each run type that needs extra folders.
PULL_TARGETS = {"GCRSim": "gcrsim", "Deep Space": "deep-space"}


def pull_hint(radType, missing):
    """The exact command to fix a missing-data error, with what it will download."""
    files = P.load_ritracks_manifest().get("files", {})
    megabytes = sum(files.get(name, {}).get("size", 0) for name in missing) / 1e6
    command = f"ammper data pull {PULL_TARGETS.get(radType, '')}".strip()
    size = f" (~{megabytes:.0f} MB)" if megabytes else ""
    return (f"Run `{command}` to download just the {len(missing)} missing folder(s)"
            f"{size} from Zenodo, then retry.")


def check_ritracks_available(radType):
    """Raise MissingRadiationDataError if radType can't run with the
    RITRACKS data currently on disk."""
    missing = missing_ritracks_energies(required_ritracks_energies(radType))
    if missing:
        raise MissingRadiationDataError(
            f"Missing RITRACKS data for {radType}: proton energies "
            f"{', '.join(missing)} MeV are not present under "
            f"{P.RADIATION_INPUT}.\n"
            + pull_hint(radType, missing)
        )
