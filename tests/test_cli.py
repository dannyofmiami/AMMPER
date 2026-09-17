"""
Adding Tests to AMMPER project
@author: dannyofmiami
"""

import pytest

from ammper import cli


def test_no_command_prints_help_and_returns_0(capsys):
    exit_code = cli.main([])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "usage: ammper" in captured.out


def test_version_flag_exits_zero():
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--version"])
    assert excinfo.value.code == 0


def test_quickstart_maps_flags_to_the_legacy_argv_contract(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cli, "_run_module_as_main", lambda module_name, argv: calls.append((module_name, argv))
    )

    exit_code = cli.main(
        ["quickstart", "--dose", "2.5", "--cell-type", "rad51", "--ros-type", "complex",
         "--name", "my_run"]
    )

    assert exit_code == 0
    assert len(calls) == 1
    module_name, argv = calls[0]
    assert module_name == "ammper.AMMPERBulk_aB"
    # radType, cellType, ROSType, dose, folder -- see README's argument contract
    assert argv == ["AMMPERBulk_aB.py", "a", "b", "b", "2.5", "my_run"]


def test_quickstart_defaults_to_the_fast_zero_dose_run(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cli, "_run_module_as_main", lambda module_name, argv: calls.append((module_name, argv))
    )

    cli.main(["quickstart"])

    _, argv = calls[0]
    assert argv == ["AMMPERBulk_aB.py", "a", "a", "a", str(float(0)), "quickstart"]


def test_run_launches_the_interactive_cli(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cli, "_run_module_as_main", lambda module_name, argv: calls.append((module_name, argv))
    )

    exit_code = cli.main(["run"])

    assert exit_code == 0
    assert calls == [("ammper.AMMPERCLI", ["AMMPERCLI.py"])]


def test_gui_launches_via_runpy_run_path(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cli.runpy, "run_path", lambda path, run_name: calls.append((path, run_name))
    )

    exit_code = cli.main(["gui"])

    assert exit_code == 0
    assert len(calls) == 1
    path, run_name = calls[0]
    assert path.endswith("gui/AMMPERGUI.py") or path.endswith("gui\\AMMPERGUI.py")
    assert run_name == "__main__"


def test_uncaught_exception_is_reported_and_returns_1(monkeypatch, capsys):
    def boom(args):
        raise ValueError("simulated failure")

    monkeypatch.setattr(cli, "cmd_quickstart", boom)

    exit_code = cli.main(["quickstart"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "ValueError: simulated failure" in captured.out
    assert "--debug" in captured.out


def test_debug_flag_reraises_the_exception(monkeypatch):
    def boom(args):
        raise ValueError("simulated failure")

    monkeypatch.setattr(cli, "cmd_quickstart", boom)

    with pytest.raises(ValueError, match="simulated failure"):
        cli.main(["--debug", "quickstart"])


def test_typo_subcommand_gets_a_did_you_mean_suggestion(capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["quickstrat"])

    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "Did you mean 'quickstart'?" in captured.out
    # not argparse's raw jargon
    assert "invalid choice" not in captured.out


def test_bad_choice_value_with_no_close_match_lists_choices(capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["quickstart", "--cell-type", "mutant"])

    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "Choose from: rad51, wt" in captured.out


def test_cell_type_and_ros_type_are_case_insensitive(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cli, "_run_module_as_main", lambda module_name, argv: calls.append((module_name, argv))
    )

    exit_code = cli.main(["quickstart", "--cell-type", "WT", "--ros-type", "BASIC"])

    assert exit_code == 0
    _, argv = calls[0]
    assert argv == ["AMMPERBulk_aB.py", "a", "a", "a", str(float(0)), "quickstart"]


def test_unrecognized_flag_gets_a_friendly_hint(capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["quickstart", "--cel-type", "wt"])

    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "unrecognized arguments" in captured.out
    assert "--help" in captured.out


def test_no_command_falls_back_to_static_help_when_not_a_tty(monkeypatch, capsys):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)

    exit_code = cli.main([])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "usage: ammper" in captured.out


def test_interactive_menu_dispatches_the_chosen_command(monkeypatch):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli.Prompt, "ask", lambda *a, **k: "quickstart")

    calls = []
    monkeypatch.setattr(
        cli, "_run_module_as_main", lambda module_name, argv: calls.append((module_name, argv))
    )

    exit_code = cli.main([])

    assert exit_code == 0
    assert calls and calls[0][0] == "ammper.AMMPERBulk_aB"


def test_interactive_menu_quit_exits_cleanly(monkeypatch, capsys):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli.Prompt, "ask", lambda *a, **k: "quit")

    exit_code = cli.main([])

    assert exit_code == 0


def test_interactive_menu_help_shows_full_help(monkeypatch, capsys):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli.Prompt, "ask", lambda *a, **k: "help")

    exit_code = cli.main([])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "usage: ammper" in captured.out


def test_interactive_menu_eof_is_treated_as_interrupted(monkeypatch, capsys):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)

    def raise_eof(*a, **k):
        raise EOFError

    monkeypatch.setattr(cli.Prompt, "ask", raise_eof)

    exit_code = cli.main([])
    captured = capsys.readouterr()

    assert exit_code == 130
    assert "Interrupted" in captured.out
