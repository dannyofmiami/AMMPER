"""
GUI progress screen: the bar must not depend on the OS theme, and a long Complex ROS step
must say so instead of looking frozen.

@author: dannyofmiami
"""

import importlib
import os
import types

import pytest


@pytest.fixture
def gui(monkeypatch):
    pytest.importorskip("PyQt5")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.syspath_prepend(os.path.join(os.path.dirname(__file__), "..", "gui"))
    return importlib.import_module("AMMPERGUI")


def test_progress_bar_is_styled_so_it_is_not_gray_when_the_window_is_inactive(gui):
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])      # noqa: F841 (kept alive for Qt)
    widget = gui.Widget()
    sheet = widget.styleSheet()
    assert "QProgressBar::chunk" in sheet and "#001f98" in sheet
    assert widget.progressBar.isTextVisible() is False


def test_complex_ros_step_announces_the_pause_then_returns_the_engine_result(gui, monkeypatch):
    labels = []
    sim = types.SimpleNamespace(label_2=types.SimpleNamespace(setText=labels.append))
    sentinel = object()
    monkeypatch.setattr(gui, "_genROS_engine", lambda rad_data, cells: sentinel)
    monkeypatch.setattr(gui, "_running_sim", sim)
    monkeypatch.setattr(gui.QApplication, "processEvents", staticmethod(lambda *a: None))

    assert gui.genROS("radData", "cells") is sentinel          # same result as the engine
    assert len(labels) == 1 and "Complex ROS" in labels[0] and "pause" in labels[0]


def test_ros_wrapper_does_nothing_extra_outside_a_gui_run(gui, monkeypatch):
    monkeypatch.setattr(gui, "_genROS_engine", lambda rad_data, cells: "result")
    monkeypatch.setattr(gui, "_running_sim", None)
    assert gui.genROS(1, 2) == "result"
