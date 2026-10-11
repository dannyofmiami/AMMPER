"""
GUI: when a radiation type needs RITRACKS folders that are not on disk, the Launch button offers to
download them (with a progress dialog) instead of failing.

Qt's dialogs are replaced with stand-ins so the logic runs without a display.

@author: dannyofmiami
"""

import importlib
import os
import types

import pytest


class _Box:
    Warning, Yes, No = 2, 16384, 65536
    answer = Yes
    questions, warnings = [], []

    @staticmethod
    def question(parent, title, text, buttons, default):
        _Box.questions.append((title, text, buttons, default))
        return _Box.answer

    @staticmethod
    def warning(parent, title, text):
        _Box.warnings.append((title, text))


class _Progress:
    created = []

    def __init__(self, label, cancel, lo, hi, parent=None):
        self.value, self.label_text, self.closed = None, label, False
        _Progress.created.append(self)

    def setWindowTitle(self, t): pass
    def setWindowModality(self, m): pass
    def setMinimumDuration(self, ms): pass
    def setLabelText(self, t): self.label_text = t
    def setValue(self, v): self.value = v
    def close(self): self.closed = True


@pytest.fixture
def gui(monkeypatch):
    pytest.importorskip("PyQt5")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.syspath_prepend(os.path.join(os.path.dirname(__file__), "..", "gui"))
    module = importlib.import_module("AMMPERGUI")
    monkeypatch.setattr(module, "QMessageBox", _Box)
    monkeypatch.setattr(module, "QProgressDialog", _Progress)
    monkeypatch.setattr(module.QApplication, "processEvents", staticmethod(lambda *a: None))
    _Box.answer, _Box.questions, _Box.warnings = _Box.Yes, [], []
    _Progress.created = []
    return module


def _widget(rad_type="GCRSim"):
    return types.SimpleNamespace(radType=rad_type)


def test_no_dialog_when_the_data_is_already_there(gui, monkeypatch):
    monkeypatch.setattr(gui.data_fetch, "ensure_available", lambda *a, **k: True)

    assert gui.Widget._ensureRadiationData(_widget()) is True
    assert _Box.warnings == [] and _Progress.created == []


def test_the_download_offer_defaults_to_yes_and_names_what_will_be_fetched(gui, monkeypatch):
    seen = {}

    def fake_ensure(rad_type, console, ask, progress_callback=None):
        seen["rad_type"] = rad_type
        seen["answer"] = ask("GCRSim needs 13 folders (20, 23 MeV).\nDownload them now (~119 MB)?")
        return True

    monkeypatch.setattr(gui.data_fetch, "ensure_available", fake_ensure)

    assert gui.Widget._ensureRadiationData(_widget()) is True
    title, text, buttons, default = _Box.questions[0]
    assert seen == {"rad_type": "GCRSim", "answer": True}
    assert "119 MB" in text and "only has to be done once" in text
    assert buttons == _Box.Yes | _Box.No and default == _Box.Yes


def test_declining_keeps_the_user_on_setup_with_a_clear_message(gui, monkeypatch):
    _Box.answer = _Box.No
    monkeypatch.setattr(gui.data_fetch, "ensure_available",
                        lambda rad_type, console, ask, progress_callback=None: ask("download?"))

    assert gui.Widget._ensureRadiationData(_widget("Deep Space")) is False
    title, text = _Box.warnings[0]
    assert title == "Missing radiation data" and "Deep Space" in text and "ammper data pull" in text


def test_progress_dialog_follows_the_download_and_is_closed(gui, monkeypatch):
    def fake_ensure(rad_type, console, ask, progress_callback=None):
        progress_callback(30_000_000, 120_000_000, "20 MeV")
        progress_callback(120_000_000, 120_000_000, "1000 MeV")
        return True

    monkeypatch.setattr(gui.data_fetch, "ensure_available", fake_ensure)

    assert gui.Widget._ensureRadiationData(_widget()) is True
    dialog = _Progress.created[0]
    assert len(_Progress.created) == 1
    assert dialog.value == 100 and "1000 MeV" in dialog.label_text and "120 of 120 MB" in dialog.label_text
    assert dialog.closed is True


@pytest.mark.parametrize("error", [OSError("timed out"), None])
def test_a_failed_download_is_reported_not_raised(gui, monkeypatch, error):
    error = error or gui.data_fetch.ChecksumMismatchError("checksum mismatch")

    def boom(*a, **k):
        raise error

    monkeypatch.setattr(gui.data_fetch, "ensure_available", boom)

    assert gui.Widget._ensureRadiationData(_widget()) is False
    assert _Box.warnings[0][0] == "Could not download radiation data"
    assert str(error) in _Box.warnings[0][1]
