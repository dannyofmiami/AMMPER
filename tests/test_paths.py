"""
Adding Tests to AMMPER project
@author: dannyofmiami
"""

import os

from ammper import paths


def test_root_points_at_the_repository():
    assert os.path.isfile(os.path.join(paths.ROOT, "pyproject.toml"))


def test_ab_experimental_joins_under_the_alamarblue_dir():
    assert paths.ab_experimental("foo.csv") == os.path.join(
        paths.AB_EXPERIMENTAL, "foo.csv"
    )


def test_bulk_ab_joins_under_the_bulk_ab_results_dir():
    assert paths.bulk_aB("WT_Basic_0") == os.path.join(paths.BULK_AB, "WT_Basic_0")


def test_figures_creates_the_target_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "FIGURES", str(tmp_path / "figs"))

    out = paths.figures("panel", "plot.png")

    assert out == str(tmp_path / "figs" / "panel" / "plot.png")
    assert os.path.isdir(str(tmp_path / "figs" / "panel"))
