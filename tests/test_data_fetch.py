"""
Tests for fetching RITRACKS folders from Zenodo (src/ammper/data_fetch.py).

A fake Zenodo serves small zips built in tmp_path, so nothing here touches the network.

@author: dannyofmiami
"""

import hashlib
import io
import zipfile

import pytest
from rich.console import Console

from ammper import data_check, data_fetch, paths


def _make_zip(path, energy, files=None, extra_entries=None):
    files = files or {"Track1/PCEvents.dat": b"events-" + energy.encode()}
    with zipfile.ZipFile(path, "w") as zf:
        for rel, content in files.items():
            zf.writestr(f"{energy}/{rel}", content)
        for name, content in (extra_entries or {}).items():
            zf.writestr(name, content)


@pytest.fixture
def zenodo(tmp_path, monkeypatch):
    """A pinned fake record with energies 150, 20 and 23, served from tmp_path."""
    served = tmp_path / "served"
    served.mkdir()
    files = {}
    for energy in ("150", "20", "23"):
        zip_path = served / f"{energy}.zip"
        _make_zip(zip_path, energy, extra_entries={f"{energy}/.DS_Store": b"junk"})
        data = zip_path.read_bytes()
        files[energy] = {"file": f"{energy}.zip", "size": len(data),
                         "md5": hashlib.md5(data).hexdigest(),
                         "sha256": hashlib.sha256(data).hexdigest()}
    manifest = {"zenodo_doi": "10.5281/zenodo.1234567", "zenodo_record_id": 1234567,
                "tutorial_energies": ["150"], "full_energies": ["150", "20", "23"], "files": files}
    root = tmp_path / "ritracks"
    root.mkdir()
    monkeypatch.setattr(paths, "RADIATION_INPUT", str(root))
    monkeypatch.setattr(paths, "BUNDLED_RITRACKS", str(tmp_path / "no-bundled-data"))
    monkeypatch.setattr(paths, "load_ritracks_manifest", lambda: manifest)
    monkeypatch.setattr(data_fetch.time, "sleep", lambda s: None)

    calls = []

    def fake_download(url, dest_path, advance):
        calls.append(url)
        name = url.rsplit("/files/", 1)[1].split("/")[0]
        data = (served / name).read_bytes()
        with open(dest_path, "wb") as fh:
            fh.write(data)
        advance(len(data))

    monkeypatch.setattr(data_fetch, "_download", fake_download)
    return types_namespace(manifest=manifest, root=root, served=served, calls=calls)


def types_namespace(**kw):
    import types
    return types.SimpleNamespace(**kw)


def _quiet():
    return Console(file=io.StringIO())


# ---- the pinned record and the targets --------------------------------------------------------

def test_file_url_raises_while_the_doi_is_still_a_placeholder():
    with pytest.raises(data_fetch.DatasetNotPublishedError):
        data_fetch._file_url({"zenodo_doi": data_fetch.PLACEHOLDER_DOI}, "150.zip")


def test_file_url_points_at_the_pinned_record():
    manifest = {"zenodo_doi": "10.5281/zenodo.22992522", "zenodo_record_id": 22992522}
    assert data_fetch._file_url(manifest, "150.zip") == (
        "https://zenodo.org/api/records/22992522/files/150.zip/content")


def test_resolve_targets_defaults_to_everything(zenodo):
    assert data_fetch.resolve_targets(None) == ["150", "20", "23"]
    assert data_fetch.resolve_targets(["ALL"]) == ["150", "20", "23"]


def test_resolve_targets_accepts_run_types_and_energies(zenodo, monkeypatch):
    monkeypatch.setattr(data_check, "required_ritracks_energies",
                        lambda radType: {"GCRSim": {"20", "23", "150"}}[radType])
    assert data_fetch.resolve_targets(["gcrsim"]) == ["150", "20", "23"]
    assert data_fetch.resolve_targets(["23.0"]) == ["23"]
    assert data_fetch.resolve_targets(["20", "150"]) == ["150", "20"]


def test_resolve_targets_rejects_unknown_names(zenodo):
    with pytest.raises(data_fetch.UnknownTargetError):
        data_fetch.resolve_targets(["warp-drive"])
    with pytest.raises(data_fetch.UnknownTargetError):
        data_fetch.resolve_targets(["99"])


def test_download_size_comes_from_the_manifest(zenodo):
    expected = zenodo.manifest["files"]["20"]["size"] + zenodo.manifest["files"]["23"]["size"]
    assert data_fetch.download_size(["20", "23"]) == expected


# ---- pulling ------------------------------------------------------------------------------------

def test_pull_fetches_verifies_and_extracts_only_what_was_asked_for(zenodo):
    pulled = data_fetch.pull(_quiet(), ["20"])

    assert pulled == ["20"]
    assert (zenodo.root / "20" / "Track1" / "PCEvents.dat").read_bytes() == b"events-20"
    assert not (zenodo.root / "23").exists() and not (zenodo.root / "150").exists()
    assert zenodo.calls == ["https://zenodo.org/api/records/1234567/files/20.zip/content"]


def test_pull_skips_macos_junk_and_leaves_no_temp_files(zenodo):
    data_fetch.pull(_quiet(), ["20"])

    assert not list((zenodo.root / "20").rglob(".DS_Store"))
    assert sorted(p.name for p in zenodo.root.iterdir()) == ["20"]   # no .pull-* dirs, no .part files


def test_pull_skips_folders_that_are_already_complete(zenodo):
    (zenodo.root / "150" / "Track1").mkdir(parents=True)
    (zenodo.root / "150" / "Track1" / "mine.dat").write_bytes(b"keep me")

    pulled = data_fetch.pull(_quiet(), None)

    assert pulled == ["20", "23"]
    assert (zenodo.root / "150" / "Track1" / "mine.dat").read_bytes() == b"keep me"
    assert not any("150.zip" in url for url in zenodo.calls)


def test_pull_with_nothing_to_do_does_not_touch_the_network(zenodo):
    data_fetch.pull(_quiet(), None)
    zenodo.calls.clear()

    assert data_fetch.pull(_quiet(), None) == []
    assert zenodo.calls == []


def test_pull_replaces_an_empty_leftover_folder(zenodo):
    (zenodo.root / "20").mkdir()          # e.g. from an interrupted manual unzip

    assert data_fetch.pull(_quiet(), ["20"]) == ["20"]
    assert (zenodo.root / "20" / "Track1" / "PCEvents.dat").exists()


def test_pull_reports_progress_to_a_callback(zenodo):
    seen = []
    data_fetch.pull(_quiet(), ["20", "23"], progress_callback=lambda d, t, label: seen.append((d, t, label)))

    total = data_fetch.download_size(["20", "23"])
    assert seen and seen[-1][0] == total and seen[-1][1] == total
    assert {label for _, _, label in seen} == {"20 MeV", "23 MeV"}


def test_a_corrupt_download_is_retried_and_then_refused(zenodo, monkeypatch):
    real = data_fetch._download

    def corrupt(url, dest_path, advance):
        real(url, dest_path, advance)
        with open(dest_path, "ab") as fh:
            fh.write(b"garbage")

    monkeypatch.setattr(data_fetch, "_download", corrupt)

    with pytest.raises(data_fetch.ChecksumMismatchError):
        data_fetch.pull(_quiet(), ["20"])

    assert not (zenodo.root / "20").exists()                       # nothing extracted
    assert [p.name for p in zenodo.root.iterdir()] == []           # partial file cleaned up


def test_a_transient_network_failure_is_retried(zenodo, monkeypatch):
    real = data_fetch._download
    attempts = []

    def flaky(url, dest_path, advance):
        attempts.append(1)
        if len(attempts) == 1:
            raise OSError("connection reset")
        real(url, dest_path, advance)

    monkeypatch.setattr(data_fetch, "_download", flaky)

    assert data_fetch.pull(_quiet(), ["20"]) == ["20"]
    assert len(attempts) == 2


def test_a_zip_that_would_escape_the_target_folder_is_refused(zenodo, tmp_path, monkeypatch):
    evil = zenodo.served / "20.zip"
    _make_zip(evil, "20", extra_entries={"20/../../escaped.txt": b"x"})
    data = evil.read_bytes()
    zenodo.manifest["files"]["20"].update(
        size=len(data), md5=hashlib.md5(data).hexdigest(), sha256=hashlib.sha256(data).hexdigest())

    with pytest.raises(data_fetch.ChecksumMismatchError, match="outside"):
        data_fetch.pull(_quiet(), ["20"])
    assert not (tmp_path / "escaped.txt").exists()


def test_a_zip_with_the_wrong_top_level_folder_is_refused(zenodo):
    wrong = zenodo.served / "20.zip"
    with zipfile.ZipFile(wrong, "w") as zf:
        zf.writestr("21/Track1/PCEvents.dat", b"x")
    data = wrong.read_bytes()
    zenodo.manifest["files"]["20"].update(
        size=len(data), md5=hashlib.md5(data).hexdigest(), sha256=hashlib.sha256(data).hexdigest())

    with pytest.raises(data_fetch.ChecksumMismatchError, match="unexpected entry"):
        data_fetch.pull(_quiet(), ["20"])


# ---- offering to download what a run needs ----------------------------------------------------

def test_ensure_available_does_not_ask_when_nothing_is_missing(zenodo, monkeypatch):
    monkeypatch.setattr(data_check, "required_ritracks_energies", lambda r: set())
    asked = []

    assert data_fetch.ensure_available("Gamma", _quiet(), lambda q: asked.append(q) or True) is True
    assert asked == []


def test_ensure_available_downloads_the_missing_folders_when_the_user_agrees(zenodo, monkeypatch):
    monkeypatch.setattr(data_check, "required_ritracks_energies", lambda r: {"20", "23"})
    asked = []

    assert data_fetch.ensure_available("GCRSim", _quiet(), lambda q: asked.append(q) or True) is True

    assert len(asked) == 1 and "20, 23 MeV" in asked[0] and "Zenodo" in asked[0]
    assert (zenodo.root / "20").is_dir() and (zenodo.root / "23").is_dir()


def test_ensure_available_downloads_nothing_when_the_user_declines(zenodo, monkeypatch):
    monkeypatch.setattr(data_check, "required_ritracks_energies", lambda r: {"20"})

    assert data_fetch.ensure_available("GCRSim", _quiet(), lambda q: False) is False
    assert zenodo.calls == [] and not (zenodo.root / "20").exists()


# ---- status / verify ----------------------------------------------------------------------------

def test_status_reports_presence_per_manifest_energy(zenodo):
    (zenodo.root / "150").mkdir()

    assert data_fetch.status() == {"150": True, "20": False, "23": False}


def test_verify_treats_an_empty_folder_as_missing(zenodo):
    (zenodo.root / "150" / "Track0").mkdir(parents=True)
    (zenodo.root / "150" / "Track0" / "x.dat").write_bytes(b"x")
    (zenodo.root / "20").mkdir()  # present but empty

    assert data_fetch.verify() == {"150": True, "20": False, "23": False}
