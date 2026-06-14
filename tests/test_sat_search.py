from __future__ import annotations

from model import Direction, Room
from sat_search import CpSatSearch
from constraints import (
    DoorMatchingConstraint,
    ConnectivityConstraint,
    NoExposedDoorsConstraint,
)


def test_sat_simple():
    rooms = [Room("A", Direction(0))]
    partial = [DoorMatchingConstraint()]
    search = CpSatSearch(1, 1, rooms, partial, partial)
    assert list(search.find_solutions(time_limit=10))


def test_sat_no_solution():
    rooms = [Room("A", Direction(0)), Room("A", Direction(0))]
    partial = [DoorMatchingConstraint()]
    search = CpSatSearch(1, 1, rooms, partial, partial)
    assert not list(search.find_solutions(time_limit=10))


def test_sat_no_exposed_doors():
    rooms = [Room("A", Direction.E)]
    partial = [DoorMatchingConstraint()]
    final = [NoExposedDoorsConstraint()]
    search = CpSatSearch(1, 1, rooms, partial, final)
    assert not list(search.find_solutions(time_limit=10))


def test_sat_no_exposed_doors_allowed():
    rooms = [Room("A", Direction.E)]
    partial = [DoorMatchingConstraint()]
    search = CpSatSearch(1, 1, rooms, partial, None)
    assert list(search.find_solutions(time_limit=10))


def test_sat_connectivity():
    rooms = [Room("A", Direction(0)), Room("B", Direction(0))]
    partial = [DoorMatchingConstraint(), ConnectivityConstraint()]
    search = CpSatSearch(2, 2, rooms, partial, partial)
    solutions = list(search.find_solutions(time_limit=10))
    assert solutions


def test_sat_preplaced():
    preplaced = Room("A", Direction.E)
    rooms = [Room("B", Direction.W)]
    partial = [DoorMatchingConstraint()]
    search = CpSatSearch(
        2,
        1,
        rooms,
        partial,
        partial,
        preplaced=[(0, 0, preplaced)],
    )
    solutions = list(search.find_solutions(time_limit=10))
    assert solutions
    for house in solutions:
        assert house.get_room(0, 0) == preplaced
        assert house.get_room(1, 0) and house.get_room(1, 0).name == "B"
