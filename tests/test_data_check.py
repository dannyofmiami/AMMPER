"""
Adding Tests to AMMPER project
@author: dannyofmiami
"""

import pytest

from ammper import data_check, paths


def _folder_with_data(path):
    path.mkdir(parents=True)
    (path / "Track1").mkdir()
    (path / "Track1" / "PCEvents.dat").write_bytes(b"x")


def test_missing_ritracks_energies_reports_absent_folders(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RADIATION_INPUT", str(tmp_path))
    monkeypatch.setattr(paths, "BUNDLED_RITRACKS", str(tmp_path / "no-bundled-data"))
    _folder_with_data(tmp_path / "150")

    missing = data_check.missing_ritracks_energies(["150", "20", "23"])

    assert missing == ["20", "23"]


def test_an_empty_folder_counts_as_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RADIATION_INPUT", str(tmp_path))
    monkeypatch.setattr(paths, "BUNDLED_RITRACKS", str(tmp_path / "no-bundled-data"))
    (tmp_path / "20").mkdir()          # e.g. left by an interrupted manual unzip

    assert data_check.missing_ritracks_energies(["20"]) == ["20"]


def test_missing_ritracks_energies_empty_when_all_present(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RADIATION_INPUT", str(tmp_path))
    monkeypatch.setattr(paths, "BUNDLED_RITRACKS", str(tmp_path / "no-bundled-data"))
    _folder_with_data(tmp_path / "150")

    assert data_check.missing_ritracks_energies(["150"]) == []


def test_required_ritracks_energies_for_150_mev_proton():
    assert data_check.required_ritracks_energies("150 MeV Proton") == {"150"}


def test_required_ritracks_energies_for_gamma_is_empty():
    assert data_check.required_ritracks_energies("Gamma") == set()


def test_required_ritracks_energies_for_gcrsim_matches_fluence_table():
    # data/fluence/GCRSimFluence_data.txt's proton energies (14 unique values)
    assert data_check.required_ritracks_energies("GCRSim") == {
        "20", "23", "27", "32", "37", "43", "50", "59", "69", "80",
        "100", "150", "250", "1000",
    }


def test_check_ritracks_available_passes_for_150_mev_proton():
    # ritracks/150/ ships in this repo's tutorial subset -- must never raise.
    data_check.check_ritracks_available("150 MeV Proton")


def test_check_ritracks_available_passes_for_gamma():
    # Gamma is synthetic -- needs no RITRACKS data at all.
    data_check.check_ritracks_available("Gamma")


def test_check_ritracks_available_raises_for_gcrsim_without_full_dataset(tmp_path, monkeypatch):
    # simulate a trimmed clone (tutorial subset only) regardless of what is on this machine
    monkeypatch.setattr(paths, "RADIATION_INPUT", str(tmp_path))
    monkeypatch.setattr(paths, "BUNDLED_RITRACKS", str(tmp_path / "no-bundled-data"))
    _folder_with_data(tmp_path / "150")
    with pytest.raises(data_check.MissingRadiationDataError, match="GCRSim") as excinfo:
        data_check.check_ritracks_available("GCRSim")
    # the message names the missing energies and gives the exact, sized shortcut
    assert "20, 23" in str(excinfo.value) and "150" not in str(excinfo.value).split("not present")[0].split("energies")[1]
    assert "ammper data pull gcrsim" in str(excinfo.value) and "MB" in str(excinfo.value)


def test_check_ritracks_available_passes_for_gcrsim_when_the_full_dataset_is_present(
        tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RADIATION_INPUT", str(tmp_path))
    monkeypatch.setattr(paths, "BUNDLED_RITRACKS", str(tmp_path / "no-bundled-data"))
    for energy in data_check.required_ritracks_energies("GCRSim"):
        _folder_with_data(tmp_path / energy)
    data_check.check_ritracks_available("GCRSim")
