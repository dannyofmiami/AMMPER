"""
Adding Tests to AMMPER project
@author: dannyofmiami
"""

import numpy as np

from ammper.cellDefinition import Cell


def make_cell(position, health=1):
    return Cell(UUID="test-uuid", position=position, health=health,
                birthGen=0, deathGen=0, numSSBs=0, numDSBs=0)


def test_init_sets_all_attributes():
    c = make_cell([4, 4, 4])
    assert c.position == [4, 4, 4]
    assert c.health == 1
    assert c.birthGen == 0
    assert c.deathGen == 0
    assert c.numSSBs == 0
    assert c.numDSBs == 0


def test_avail_units_lists_every_empty_neighbor_in_bounds():
    N = 8
    T = np.zeros((N, N, N))
    c = make_cell([4, 4, 4])

    available = c.availUnits(T, N)

    # placeholder plus the 8 in-bounds neighbors at offsets {-4, 0} per axis
    # (offset +4 pushes position 4 -> 8, which is out of bounds for N=8)
    assert available[0] == [-1, -1, -1]
    assert len(available) == 9
    for x in (0, 4):
        for y in (0, 4):
            for z in (0, 4):
                assert [x, y, z] in available


def test_avail_units_excludes_occupied_neighbors():
    N = 8
    T = np.zeros((N, N, N))
    T[0, 0, 0] = 1  # occupy one of the neighbor cells
    c = make_cell([4, 4, 4])

    available = c.availUnits(T, N)

    assert [0, 0, 0] not in available
    assert len(available) == 8


def test_brownian_move_relocates_into_an_available_neighbor():
    N = 8
    T = np.zeros((N, N, N))
    T[4, 4, 4] = 1  # cell occupies its own current slot
    c = make_cell([4, 4, 4])

    c.brownianMove(T, N, g=0)

    assert c.position != [4, 4, 4]
    assert c.position[0] in (0, 4)
    assert c.position[1] in (0, 4)
    assert c.position[2] in (0, 4)


def test_brownian_move_stays_put_when_saturated():
    N = 8
    T = np.zeros((N, N, N))
    for x in (0, 4):
        for y in (0, 4):
            for z in (0, 4):
                T[x, y, z] = 1  # occupy every neighbor
    c = make_cell([4, 4, 4])

    c.brownianMove(T, N, g=0)

    assert c.position == [4, 4, 4]


def test_cell_repl_returns_self_when_saturated():
    N = 8
    T = np.zeros((N, N, N))
    for x in (0, 4):
        for y in (0, 4):
            for z in (0, 4):
                T[x, y, z] = 1
    c = make_cell([4, 4, 4])

    result = c.cellRepl(T, N, g=0)

    assert result is c


def test_cell_repl_creates_a_new_cell_with_a_fresh_uuid():
    N = 8
    T = np.zeros((N, N, N))
    c = make_cell([4, 4, 4])

    child = c.cellRepl(T, N, g=3)

    assert child is not c
    assert child.UUID != c.UUID
    assert child.health == 1
    assert child.birthGen == 3
