# -*- coding: utf-8 -*-
"""
Fetches RITRACKS radiation-track folders from Zenodo.

The full dataset (49 proton-energy folders, ~3.8GB on disk) is published as one
zip per proton energy (~1.3GB to download in total), so a clone only needs the
150 MeV Proton tutorial folder (data/radiation_input/ritracks/150/, ~11MB) and can
fetch just the folders a heavier run needs: GCRSim needs 14 of them (~119MB) and
Deep Space needs 10 (~193MB). The record is pinned in
data/radiation_input/MANIFEST.json (version DOI, plus each zip's size and sha256),
and every download is checked against that before anything is extracted.

Stdlib only (urllib.request/hashlib/zipfile) -- deliberately not adding a
new dependency (e.g. requests) for this.

@author: dannyofmiami
"""

import hashlib
import http.client
import os
import shutil
import tempfile
import time
import urllib.request
import zipfile

from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from ammper import data_check
from ammper import paths as P

PLACEHOLDER_DOI = "TODO-pending-deposit"

_CHUNK_SIZE = 1024 * 1024
_ATTEMPTS = 4
_JUNK_NAMES = {".DS_Store"}       # macOS leftovers inside the published zips
_JUNK_DIRS = {"__MACOSX"}

# Short names accepted by `ammper data pull`, mapped to the run type that defines them.
TARGET_ALIASES = {
    "proton": "150 MeV Proton",
    "gcrsim": "GCRSim",
    "deep-space": "Deep Space",
    "deepspace": "Deep Space",
}


class DatasetNotPublishedError(Exception):
    """Raised by `ammper data pull` while MANIFEST.json still has a placeholder DOI."""


class ChecksumMismatchError(Exception):
    """Raised when a download doesn't match the size/sha256 pinned in MANIFEST.json,
    or a zip doesn't have the expected layout -- refuse to extract it."""


class UnknownTargetError(ValueError):
    """Raised for a `ammper data pull` target that is neither a run type nor an energy."""


def _check_published(manifest):
    if manifest.get("zenodo_doi", PLACEHOLDER_DOI) == PLACEHOLDER_DOI:
        raise DatasetNotPublishedError(
            "The full RITRACKS dataset isn't published yet -- "
            "data/radiation_input/MANIFEST.json still has a placeholder "
            "Zenodo DOI. Until it is published the data is only in this "
            "repository (see CONTRIBUTING.md)."
        )


def _file_url(manifest, filename):
    """Download URL for one file of the pinned Zenodo record."""
    _check_published(manifest)
    # A Zenodo DOI is "10.5281/zenodo.<record id>"; the manifest also stores the id.
    record_id = manifest.get("zenodo_record_id") or manifest["zenodo_doi"].rsplit(".", 1)[-1]
    return f"https://zenodo.org/api/records/{record_id}/files/{filename}/content"


def resolve_targets(targets, manifest=None):
    """The energy folders to fetch for `ammper data pull` arguments.

    Nothing (or "all") means every folder in the manifest. Otherwise each argument is a
    run-type name (gcrsim, deep-space, proton) or a proton energy that is in the manifest.
    """
    manifest = manifest or P.load_ritracks_manifest()
    known = manifest["full_energies"]
    if not targets or [t.lower() for t in targets] == ["all"]:
        return list(known)
    wanted = set()
    for raw in targets:
        key = raw.strip().lower()
        if key in TARGET_ALIASES:
            wanted |= set(data_check.required_ritracks_energies(TARGET_ALIASES[key]))
            continue
        try:
            value = float(key)
        except ValueError:
            value = None
        match = [n for n in known if value is not None and abs(float(n) - value) < 1e-6]
        if not match:
            raise UnknownTargetError(
                f"'{raw}' is not a run type (gcrsim, deep-space, proton, all) or a "
                "proton energy in the dataset. Run `ammper data status` to list them."
            )
        wanted.add(match[0])
    return [n for n in known if n in wanted]


def download_size(energies, manifest=None):
    """Bytes to download for these energy folders, from the manifest."""
    files = (manifest or P.load_ritracks_manifest()).get("files", {})
    return sum(files.get(e, {}).get("size", 0) for e in energies)


def _hash_file(path, algorithm):
    digest = hashlib.new(algorithm)
    with open(path, "rb") as fh:
        while chunk := fh.read(_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_download(path, entry):
    """Raise ChecksumMismatchError unless the file matches the manifest's size and hash."""
    actual_size = os.path.getsize(path)
    if actual_size != entry["size"]:
        raise ChecksumMismatchError(
            f"{entry['file']}: downloaded {actual_size} bytes, expected {entry['size']} "
            "-- the download was cut short or the Zenodo record changed."
        )
    algorithm, expected = ("sha256", entry["sha256"]) if entry.get("sha256") else ("md5", entry["md5"])
    actual = _hash_file(path, algorithm)
    if actual != expected:
        raise ChecksumMismatchError(
            f"{entry['file']}: {algorithm} {actual} does not match the expected {expected} "
            "-- the download is corrupted or the Zenodo record changed. Not extracting."
        )


def _download(url, dest_path, advance):
    """Stream `url` to dest_path, calling advance(nbytes) as data arrives."""
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 - fixed zenodo.org host
        with open(dest_path, "wb") as out:
            while chunk := response.read(_CHUNK_SIZE):
                out.write(chunk)
                advance(len(chunk))


def _extract_energy(zip_path, energy):
    """Extract one energy zip into RADIATION_INPUT/<energy>/, all or nothing.

    The zip must contain a single top-level <energy>/ folder. Members are checked for path
    traversal and macOS junk is skipped. Extraction happens in a temp folder that is moved
    into place only when complete, so an interrupted pull never leaves a half-filled folder.
    """
    root = P.RADIATION_INPUT
    os.makedirs(root, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix=".pull-", dir=root)
    try:
        tmp_root = os.path.realpath(tmp)
        with zipfile.ZipFile(zip_path) as zf:
            members = []
            for info in zf.infolist():
                parts = info.filename.split("/")
                if parts[0] in _JUNK_DIRS or parts[-1] in _JUNK_NAMES:
                    continue
                if parts[0] != energy:
                    raise ChecksumMismatchError(
                        f"{energy}.zip has an unexpected entry '{info.filename}' "
                        f"(expected everything under '{energy}/') -- refusing to extract."
                    )
                target = os.path.realpath(os.path.join(tmp, info.filename))
                if not (target == tmp_root or target.startswith(tmp_root + os.sep)):
                    raise ChecksumMismatchError(
                        f"{energy}.zip entry '{info.filename}' would extract outside the "
                        "target folder -- refusing to extract."
                    )
                members.append(info)
            for info in members:
                zf.extract(info, tmp)
        extracted = os.path.join(tmp, energy)
        if not os.path.isdir(extracted) or not os.listdir(extracted):
            raise ChecksumMismatchError(f"{energy}.zip contained no data for '{energy}/'.")
        dest = P.radiation_input(energy)
        if os.path.isdir(dest):
            shutil.rmtree(dest)       # only ever an empty/partial folder: pull skips complete ones
        os.replace(extracted, dest)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _fetch_verified(url, entry, dest_path, advance, retry_message=None):
    """Download to dest_path and verify; retry a few times on network errors or a bad file."""
    last_error = None
    for attempt in range(1, _ATTEMPTS + 1):
        sent = []
        try:
            _download(url, dest_path, lambda n: (sent.append(n), advance(n)))
            _verify_download(dest_path, entry)
            return
        except (OSError, http.client.HTTPException, ChecksumMismatchError) as exc:
            last_error = exc
            advance(-sum(sent))               # take this attempt's progress back out
            if os.path.exists(dest_path):
                os.remove(dest_path)
            if attempt < _ATTEMPTS:
                if retry_message:
                    retry_message(entry["file"], attempt, exc)
                time.sleep(min(2 * attempt, 6))
    raise last_error


def pull(console, targets=None, force=False, progress_callback=None):
    """Download, verify and extract RITRACKS energy folders from Zenodo.

    `targets` are run types or energies (see resolve_targets); default is everything.
    Folders that are already complete are skipped unless force=True. Returns the energies
    that were downloaded. `progress_callback(done_bytes, total_bytes, label)`, if given, is
    called as data arrives (the GUI uses it to drive its own progress dialog).
    """
    manifest = P.load_ritracks_manifest()
    _check_published(manifest)
    energies = resolve_targets(targets, manifest)
    present = verify()
    todo = [e for e in energies if force or not present.get(e)]
    if not todo:
        console.print("[green]Already present:[/green] nothing to download.")
        return []

    total = download_size(todo, manifest)
    console.print(
        f"[cyan]Downloading {len(todo)} energy folder(s), {total / 1e6:.0f} MB[/cyan] "
        f"from Zenodo (doi:{manifest['zenodo_doi']}) ...\n"
    )
    os.makedirs(P.RADIATION_INPUT, exist_ok=True)
    with Progress(
        TextColumn("[cyan]{task.description}[/cyan]"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Downloading", total=total)
        done = [0]

        def advance(nbytes, label=""):
            done[0] += nbytes
            progress.update(task, advance=nbytes)
            if progress_callback:
                progress_callback(done[0], total, label)

        for energy in todo:
            entry = manifest["files"][energy]
            part = os.path.join(P.RADIATION_INPUT, f".{entry['file']}.part")
            progress.update(task, description=f"{energy} MeV")
            try:
                _fetch_verified(
                    _file_url(manifest, entry["file"]), entry, part,
                    lambda n, label=f"{energy} MeV": advance(n, label),
                    retry_message=lambda name, attempt, exc: progress.console.print(
                        f"[yellow]{exc if name in str(exc) else f'{name}: {exc}'} "
                        f"-- retrying ({attempt}/{_ATTEMPTS - 1})[/yellow]"),
                )
                _extract_energy(part, energy)
            finally:
                if os.path.exists(part):
                    os.remove(part)
    return todo


def ensure_available(radType, console, ask, progress_callback=None):
    """Make `radType` runnable, offering to download whatever RITRACKS folders are missing.

    `ask(question) -> bool` is how the caller asks the user (the CLI uses a yes/no prompt,
    the GUI a dialog). Returns True if the data is present (already, or after downloading),
    False if the user declined. Network and checksum errors from the download propagate.
    """
    missing = data_check.missing_ritracks_energies(data_check.required_ritracks_energies(radType))
    if not missing:
        return True
    megabytes = download_size(missing) / 1e6
    question = (
        f"{radType} needs {len(missing)} RITRACKS folder(s) that are not on this machine "
        f"({', '.join(missing)} MeV).\nDownload them now from Zenodo (~{megabytes:.0f} MB, "
        "this can take several minutes)?"
    )
    if not ask(question):
        return False
    pull(console, missing, progress_callback=progress_callback)
    return True


def status():
    """{folder_name: is_present} for every energy folder in the manifest."""
    manifest = P.load_ritracks_manifest()
    return {
        name: os.path.isdir(P.radiation_input(name))
        for name in manifest["full_energies"]
    }


def verify():
    """{folder_name: is_present_and_non_empty} for every energy folder in
    the manifest -- the same cheap presence/non-empty check `ammper setup`
    already uses elsewhere, not a full per-file hash."""
    manifest = P.load_ritracks_manifest()
    results = {}
    for name in manifest["full_energies"]:
        path = P.radiation_input(name)
        results[name] = os.path.isdir(path) and bool(os.listdir(path))
    return results
