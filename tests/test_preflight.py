"""
Tests for the Complex ROS machine pre-flight (src/ammper/preflight.py).

Machine specs are injected, so nothing here depends on the host's real RAM.

@author: dannyofmiami
"""

import importlib
import os
import types

import pytest

from ammper import cli, preflight
from ammper.preflight import (
    GAMMA,
    PROTON,
    ComplexROSCapacityError,
    MachineSpecs,
    check_complex_ros,
    estimate_complex_ros,
    max_safe_proton_dose,
    require_complex_ros_capacity,
)


def _machine(available_gb, total_gb=None):
    return MachineSpecs("Windows", "AMD64", 8, total_gb or available_gb, available_gb)


# Measured on 2026-10-07 (see preflight.py): dose -> peak RSS in GB.
MEASURED_PEAK_GB = {2.5: 1.9, 5.0: 3.7, 10.0: 7.3}


@pytest.mark.parametrize("dose,measured", MEASURED_PEAK_GB.items())
def test_memory_model_tracks_the_measurements_and_errs_high(dose, measured):
    est = estimate_complex_ros(PROTON, dose)
    assert est.peak_gb >= measured                 # never under-promises
    assert est.peak_gb <= measured * 1.2           # but is not wildly pessimistic


def test_estimates_grow_with_dose():
    peaks = [estimate_complex_ros(PROTON, d).peak_gb for d in (2.5, 5, 10, 20, 30)]
    assert peaks == sorted(peaks) and len(set(peaks)) == 5


def test_gamma_fixed_dose_is_about_one_proton_track():
    gamma = estimate_complex_ros(GAMMA, 1.0)
    assert gamma.events == 6401
    assert gamma.peak_gb == pytest.approx(estimate_complex_ros(PROTON, 2.5).peak_gb, rel=0.10)


def test_small_machine_blocks_high_doses_and_allows_low_ones():
    pc = _machine(8)                               # e.g. an 8 GB laptop with ~8 GB free
    assert check_complex_ros(PROTON, 2.5, pc).level == "ok"
    assert check_complex_ros(PROTON, 10, pc).level == "block"
    assert check_complex_ros(PROTON, 30, pc).level == "block"


def test_big_machine_runs_30_gy():
    assert check_complex_ros(PROTON, 30, _machine(64)).level == "ok"


def test_borderline_machine_is_a_warning_not_a_block():
    # 5 Gy needs ~5.1 GB: fits in 8 GB but uses most of it.
    assert check_complex_ros(PROTON, 5, _machine(8)).level == "warn"


def test_block_message_explains_why_and_the_strict_variant_explains_the_override():
    verdict = check_complex_ros(PROTON, 30, _machine(8, total_gb=16))
    assert "swap or crash" in verdict.message
    # the override hint belongs to the strict (raising) variant, not the warning text
    assert preflight.FORCE_ENV_VAR not in verdict.message
    with pytest.raises(ComplexROSCapacityError, match=preflight.FORCE_ENV_VAR):
        require_complex_ros_capacity(PROTON, 30, _machine(8, total_gb=16), env={})


def test_undetectable_memory_warns_only_for_the_higher_doses():
    unknown = MachineSpecs("Linux", "x86_64", 4, None, None)
    assert check_complex_ros(PROTON, 30, unknown).level == "warn"
    assert check_complex_ros(PROTON, 5, unknown).level == "warn"
    assert check_complex_ros(PROTON, 2.5, unknown).level == "ok"   # small runs are not nagged


def test_uncharacterized_runs_warn_small_machines_only():
    assert check_complex_ros("GCRSim", 1, _machine(8)).level == "warn"
    assert check_complex_ros("GCRSim", 1, _machine(64)).level == "ok"
    assert check_complex_ros(PROTON, 7.5, _machine(8)).level == "warn"   # not a tabulated dose
    assert check_complex_ros(PROTON, 7.5, _machine(64)).level == "ok"


def test_require_raises_on_block_and_returns_verdict_otherwise():
    with pytest.raises(ComplexROSCapacityError):
        require_complex_ros_capacity(PROTON, 30, _machine(8), env={})
    assert require_complex_ros_capacity(PROTON, 2.5, _machine(8), env={}).level == "ok"


def test_force_env_var_downgrades_a_block_to_a_warning():
    forced = require_complex_ros_capacity(
        PROTON, 30, _machine(8), env={preflight.FORCE_ENV_VAR: "1"})
    assert forced.level == "warn" and "OVERRIDE" in forced.message
    # only the exact opt-in value counts
    with pytest.raises(ComplexROSCapacityError):
        require_complex_ros_capacity(PROTON, 30, _machine(8), env={preflight.FORCE_ENV_VAR: "yes"})


def test_max_safe_dose_scales_with_free_memory():
    assert max_safe_proton_dose(_machine(4)) == 2.5
    assert max_safe_proton_dose(_machine(16)) == 10.0
    assert max_safe_proton_dose(_machine(64)) == 30.0
    assert max_safe_proton_dose(_machine(1)) == 0.0


def test_detect_machine_returns_sane_values_on_this_host():
    specs = preflight.detect_machine()
    assert specs.cpu_count >= 1 and specs.system
    if specs.available_ram_gb is not None:
        assert 0 < specs.available_ram_gb <= specs.total_ram_gb


def test_warning_text_only_when_the_machine_is_short_of_memory():
    assert preflight.complex_ros_warning(PROTON, 2.5, _machine(64)) is None
    assert "swap or crash" in preflight.complex_ros_warning(PROTON, 30, _machine(8))
    assert preflight.complex_ros_warning(PROTON, 5, _machine(8))  # caution still warns


def test_table_covers_every_characterized_run():
    rows = preflight.complex_ros_table(_machine(8))
    assert [(r[0], r[1]) for r in rows] == [
        (PROTON, 2.5), (PROTON, 5.0), (PROTON, 10.0), (PROTON, 20.0), (PROTON, 30.0), (GAMMA, 1.0)]
    assert {r[3] for r in rows} <= {"ok", "warn", "block"}


# ---- `ammper setup` includes the machine check -------------------------------------------

def _run_setup(monkeypatch, capsys, specs):
    monkeypatch.setattr(preflight, "detect_machine", lambda: specs)
    code = cli.main(["setup"])
    return code, capsys.readouterr().out


def test_setup_warns_on_a_small_machine_without_failing_setup(monkeypatch, capsys):
    baseline = _run_setup(monkeypatch, capsys, _machine(64))[0]
    code, out = _run_setup(monkeypatch, capsys, _machine(4))
    assert "Machine check" in out and "Warning" in out and "too large" in out
    assert code == baseline          # the machine check never changes setup's exit status


def test_setup_reports_a_capable_machine_without_a_warning(monkeypatch, capsys):
    _, out = _run_setup(monkeypatch, capsys, _machine(64))
    assert "Machine check" in out and "Warning" not in out


def test_setup_says_so_when_memory_cannot_be_detected(monkeypatch, capsys):
    _, out = _run_setup(monkeypatch, capsys, MachineSpecs("Linux", "x86_64", 4, None, None))
    assert "could not be detected" in out


def test_doctor_command_is_gone():
    with pytest.raises(SystemExit):
        cli.main(["doctor"])


# ---- GUI Launch warning --------------------------------------------------------------------

class _FakeBox:
    """Stands in for QMessageBox so the dialog logic runs without a display."""
    Warning, Yes, No = 2, 16384, 65536      # ints, like Qt's flags, so `Yes | No` works
    answer = No
    shown = []

    def __init__(self, parent=None):
        self.parent = parent
        self.fields = {}

    def setIcon(self, v): self.fields["icon"] = v
    def setWindowTitle(self, v): self.fields["title"] = v
    def setText(self, v): self.fields["text"] = v
    def setInformativeText(self, v): self.fields["detail"] = v
    def setStandardButtons(self, v): self.fields["buttons"] = v
    def setDefaultButton(self, v): self.fields["default"] = v

    def exec_(self):
        type(self).shown.append(self.fields)
        return type(self).answer


@pytest.fixture
def gui(monkeypatch):
    pytest.importorskip("PyQt5")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.syspath_prepend(os.path.join(os.path.dirname(__file__), "..", "gui"))
    module = importlib.import_module("AMMPERGUI")
    monkeypatch.setattr(module, "QMessageBox", _FakeBox)
    _FakeBox.shown, _FakeBox.answer = [], _FakeBox.No
    return module


def _widget(**kw):
    return types.SimpleNamespace(**{"ROSType": "Complex ROS", "radType": PROTON, "Gy": 30.0, **kw})


def test_gui_never_prompts_for_basic_ros(gui, monkeypatch):
    monkeypatch.setattr(preflight, "detect_machine", lambda: _machine(1))
    assert gui.Widget._confirmComplexROS(_widget(ROSType="Basic ROS")) is True
    assert _FakeBox.shown == []


def test_gui_does_not_prompt_when_the_machine_can_cope(gui, monkeypatch):
    monkeypatch.setattr(preflight, "detect_machine", lambda: _machine(64))
    assert gui.Widget._confirmComplexROS(_widget(Gy=2.5)) is True
    assert _FakeBox.shown == []


def test_gui_warns_and_lets_the_user_decline_or_continue(gui, monkeypatch):
    monkeypatch.setattr(preflight, "detect_machine", lambda: _machine(8))
    assert gui.Widget._confirmComplexROS(_widget()) is False          # default answer: No
    assert len(_FakeBox.shown) == 1
    shown = _FakeBox.shown[0]
    assert shown["default"] == _FakeBox.No and "swap or crash" in shown["detail"]
    _FakeBox.answer = _FakeBox.Yes
    assert gui.Widget._confirmComplexROS(_widget()) is True           # a warning, not a ban


def test_gui_treats_gamma_as_a_fixed_one_gray_run(gui, monkeypatch):
    monkeypatch.setattr(preflight, "detect_machine", lambda: _machine(8))
    # slider dose is ignored for Gamma; a 1 Gy run fits comfortably in 8 GB
    assert gui.Widget._confirmComplexROS(_widget(radType=GAMMA, Gy=30.0)) is True
    assert _FakeBox.shown == []


def test_gui_offers_complex_ros_and_defaults_to_basic(gui):
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])      # noqa: F841 (kept alive for Qt)
    widget = gui.Widget()
    assert widget.radioButton_8.isEnabled() and widget.radioButton_8.text() == "Complex"
    assert widget.ROSType == "Basic ROS"
    widget.radioButton_8.setChecked(True)
    assert widget.ROSType == "Complex ROS"
