"""

Randomness is neutralized so every ROS event that falls inside the window registers as a cell hit AND a nucleus hit

@author: dannyofmiami
"""

import random

import numpy as np
import pytest

from ammper.cellDefinition import Cell

CELL_POS = [32, 32, 32]


def _ros_event(dx=0, dy=0, dz=0):
    # [Posx, Posy, Posz, C_H2O2, C_OH, cellHit]; plenty of OH so any hit damages
    return np.array([[CELL_POS[0] + dx, CELL_POS[1] + dy, CELL_POS[2] + dz, 0.0, 50.0, 0.0]])


@pytest.fixture(autouse=True)
def _always_hit(monkeypatch):
    # uniform(100, 0) <= 52.36 and <= 7.4 both hold when it returns 0
    monkeypatch.setattr(random, "uniform", lambda a, b: 0.0)


def _damaged_wt(event):
    cell = Cell("wt", list(CELL_POS), 1, 0, 0, 0, 0)
    cell.cellROS(5, 2, event, "150 MeV Proton")
    return cell.health != 1


def _damaged_rad51(event):
    cell = Cell("rad51", list(CELL_POS), 1, 0, 0, 0, 0)
    cell.cellROS_rad51(5, 2, event, "150 MeV Proton")
    return cell.health != 1


@pytest.mark.parametrize("damaged", [_damaged_wt, _damaged_rad51], ids=["wt", "rad51"])
class TestLegacyZWindow:
    @pytest.mark.parametrize("dz", [0, -1, -2])
    def test_events_at_or_below_the_cell_count(self, damaged, dz):
        assert damaged(_ros_event(dz=dz))

    @pytest.mark.parametrize("dz", [1, 2])
    def test_events_above_the_cell_are_ignored_legacy_behavior(self, damaged, dz):
        # In a symmetric +/-2 window these WOULD count. They must not in v2.
        assert not damaged(_ros_event(dz=dz))

    def test_events_below_the_window_are_ignored(self, damaged):
        assert not damaged(_ros_event(dz=-3))

    @pytest.mark.parametrize("dx,dy", [(2, 0), (-2, 0), (0, 2), (0, -2)])
    def test_x_and_y_windows_stay_symmetric(self, damaged, dx, dy):
        assert damaged(_ros_event(dx=dx, dy=dy))
