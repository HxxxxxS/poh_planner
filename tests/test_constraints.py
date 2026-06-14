from __future__ import annotations

from model import Direction, House, Room
from constraints import (
    DoorMatchingConstraint,
    ConnectivityConstraint,
    NoExposedDoorsConstraint,
)


def test_door_matching_success():
    house = House(2, 1)
    room_a = Room("A", Direction.E)
    room_b = Room("B", Direction.W)
    house.place_room(0, 0, room_a)
    house.place_room(1, 0, room_b)
    assert DoorMatchingConstraint()(house)


def test_door_matching_failure():
    house = House(2, 1)
    room_a = Room("A", Direction.E)
    room_b = Room("B", Direction(0))
    house.place_room(0, 0, room_a)
    house.place_room(1, 0, room_b)
    assert not DoorMatchingConstraint()(house)


def test_connectivity_constraint():
    house = House(2, 1)
    room = Room("A", Direction(0))
    house.place_room(0, 0, room)
    assert ConnectivityConstraint()(house)


def test_connectivity_disconnected():
    house = House(2, 2)
    room = Room("A", Direction(0))
    second = Room("B", Direction(0))
    house.place_room(0, 0, room)
    house.place_room(1, 1, second)
    assert not ConnectivityConstraint()(house)


def test_no_exposed_doors_success():
    house = House(2, 1)
    room = Room("A", Direction.E)
    neighbor = Room("B", Direction.W)
    house.place_room(0, 0, room)
    house.place_room(1, 0, neighbor)
    assert NoExposedDoorsConstraint()(house)


def test_no_exposed_doors_failure():
    house = House(2, 1)
    room = Room("A", Direction.E)
    house.place_room(0, 0, room)
    assert not NoExposedDoorsConstraint()(house)
