from pathlib import Path
from collections import Counter

from model import Direction, House, Room
from main import (
    _door_mask_from_string,
    _door_mask_to_string,
    _limit_for_level,
    _normalize_name,
    _parse_coordinate,
    _parse_group_override,
    _relative_to_absolute,
    _solution_key,
    _unique_rotations,
    _validate_within_bounds,
    build_final_constraints,
    build_partial_constraints,
    build_pinned_rooms,
    build_room_selection,
    expand_rooms,
)
from constraints import (
    DoorMatchingConstraint,
    ConnectivityConstraint,
    NoExposedDoorsConstraint,
)


def test_normalize_name_basic():
    assert _normalize_name("Portal Chamber") == "PortalChamber"


def test_normalize_name_parentheses():
    assert _normalize_name("Hall (skill trophies)") == "HallSkillTrophies"


def test_normalize_name_spaced():
    assert _normalize_name("  spaced  out  ") == "SpacedOut"


def test_normalize_name_empty():
    assert _normalize_name("") == ""


def test_door_mask_from_string_all():
    assert (
        _door_mask_from_string("NESW")
        == Direction.N | Direction.E | Direction.S | Direction.W
    )


def test_door_mask_from_string_partial():
    assert _door_mask_from_string("ES") == Direction.E | Direction.S


def test_door_mask_from_string_empty():
    assert _door_mask_from_string("") == Direction(0)


def test_door_mask_to_string_two():
    assert _door_mask_to_string(Direction.N | Direction.E) == "NE"


def test_door_mask_to_string_empty():
    assert _door_mask_to_string(Direction(0)) == "<none>"


def test_door_mask_to_string_roundtrip():
    for s in ["N", "E", "S", "W", "NE", "NS", "NES", "NESW", ""]:
        assert _door_mask_to_string(_door_mask_from_string(s)) == (s or "<none>")


def test_parse_coordinate_basic():
    assert _parse_coordinate("3,4") == (3, 4)


def test_parse_coordinate_negative():
    assert _parse_coordinate("-1,2") == (-1, 2)


def test_parse_coordinate_spaces():
    assert _parse_coordinate("  -1 ,  2  ") == (-1, 2)


def test_parse_coordinate_invalid():
    try:
        _parse_coordinate("abc")
        assert False
    except ValueError:
        pass


def test_relative_to_absolute_center():
    assert _relative_to_absolute(0, 0, 7, 7) == (3, 3)


def test_relative_to_absolute_positive():
    assert _relative_to_absolute(1, 0, 7, 7) == (4, 3)


def test_relative_to_absolute_negative():
    assert _relative_to_absolute(-1, -1, 7, 7) == (2, 2)


def test_validate_within_bounds_ok():
    _validate_within_bounds(0, 0, 7, 7)
    _validate_within_bounds(6, 6, 7, 7)


def test_validate_within_bounds_fail():
    try:
        _validate_within_bounds(7, 0, 7, 7)
        assert False
    except ValueError:
        pass


def test_unique_rotations_all():
    r = Room("A", Direction.N | Direction.E | Direction.S | Direction.W)
    assert _unique_rotations(r) == [0]


def test_unique_rotations_two():
    r = Room("A", Direction.N | Direction.S)
    assert len(_unique_rotations(r)) == 2
    assert set(_unique_rotations(r)) == {0, 1}


def test_unique_rotations_single():
    r = Room("A", Direction.E)
    assert len(_unique_rotations(r)) == 4


def test_limit_for_level_low():
    assert _limit_for_level(1) == (3, 24)


def test_limit_for_level_mid():
    max_size, max_rooms = _limit_for_level(30)
    assert max_size >= 5
    assert max_rooms >= 25


def test_limit_for_level_max():
    assert _limit_for_level(99) == (7, 38)


def test_limit_for_level_beyond():
    assert _limit_for_level(999) == (7, 38)


def test_parse_group_override_weight():
    assert _parse_group_override("garden:weight=15") == ("weight", "garden", 15)


def test_parse_group_override_exclude():
    op = _parse_group_override("dungeon:exclude=TreasureRoom")
    assert op[0] == "exclude"
    assert op[1] == "dungeon"
    assert op[2] == ["TreasureRoom"]


def test_parse_group_override_new():
    op = _parse_group_override("myfam:5=Kitchen,Bedroom")
    assert op[0] == "new"
    assert op[1] == "myfam"
    assert op[2] == 5
    assert op[3] == ["Kitchen", "Bedroom"]


def test_parse_group_override_invalid():
    try:
        _parse_group_override("badinput")
        assert False
    except ValueError:
        pass


def test_parse_group_override_no_value():
    try:
        _parse_group_override("name:weight")
        assert False
    except ValueError:
        pass


def test_build_room_selection_single():
    counts = build_room_selection(["Kitchen"])
    assert counts.get("Kitchen") == 1


def test_build_room_selection_with_count():
    counts = build_room_selection(["Portal=3", "Kitchen"])
    assert counts.get("PortalChamber") == 3
    assert counts.get("Kitchen") == 1


def test_build_room_selection_unknown():
    try:
        build_room_selection(["FakeRoom"])
        assert False
    except ValueError:
        pass


def test_build_pinned_rooms_basic():
    pinned, counts = build_pinned_rooms(["1,0=PortalChamber"], 7, 7, (3, 3))
    assert (4, 3) in pinned
    assert pinned[(4, 3)].name == "PortalChamber"
    assert counts["PortalChamber"] == 1


def test_build_pinned_rooms_entrance_collision():
    try:
        build_pinned_rooms(["0,0=Portal"], 7, 7, (3, 3))
        assert False
    except ValueError:
        pass


def test_build_pinned_rooms_duplicate():
    try:
        build_pinned_rooms(["1,0=Portal", "1,0=Portal"], 7, 7, (3, 3))
        assert False
    except ValueError:
        pass


def test_expand_rooms_extra():
    rooms = expand_rooms({"PortalChamber": 3}, Counter())
    assert len(rooms) == 3
    assert all(r.name == "PortalChamber" for r in rooms)


def test_expand_rooms_with_pinned():
    rooms = expand_rooms({"Kitchen": 2}, Counter({"Kitchen": 1}))
    assert len(rooms) == 1


def test_expand_rooms_over_pinned():
    try:
        expand_rooms({"Kitchen": 1}, Counter({"Kitchen": 2}))
        assert False
    except ValueError:
        pass


def test_build_partial_constraints():
    result = build_partial_constraints()
    assert len(result) == 2
    assert isinstance(result[0], DoorMatchingConstraint)
    assert isinstance(result[1], ConnectivityConstraint)


def test_build_final_constraints_enabled():
    result = build_final_constraints(False)
    assert result is not None
    assert len(result) == 1
    assert isinstance(result[0], NoExposedDoorsConstraint)


def test_build_final_constraints_disabled():
    assert build_final_constraints(True) is None


def test_solution_key_goal_none():
    h = House(3, 3)
    h.place_room(1, 1, Room("A", Direction(0)))
    assert _solution_key(h, (1, 1), set(), "none") == 0


def test_solution_key_compact_smaller_better():
    h1 = House(3, 3)
    h1.place_room(1, 1, Room("A", Direction(0)))
    h1.place_room(1, 2, Room("B", Direction(1)))
    h2 = House(3, 3)
    h2.place_room(1, 1, Room("A", Direction(0)))
    h2.place_room(2, 2, Room("B", Direction(1)))
    key1 = _solution_key(h1, (1, 1), set(), "compact")
    key2 = _solution_key(h2, (1, 1), set(), "compact")
    assert key1 < key2


def test_solution_key_filled_more_adj_better():
    h1 = House(3, 3)
    h1.place_room(1, 1, Room("A", Direction(0)))
    h1.place_room(1, 2, Room("B", Direction(1)))
    h2 = House(3, 3)
    h2.place_room(1, 1, Room("A", Direction(0)))
    h2.place_room(2, 2, Room("B", Direction(1)))
    key1 = _solution_key(h1, (1, 1), set(), "filled")
    key2 = _solution_key(h2, (1, 1), set(), "filled")
    assert key1 < key2


def test_solution_key_near_entrance_closer_better():
    h1 = House(5, 5)
    h1.place_room(2, 2, Room("Kitchen", Direction(0)))
    h2 = House(5, 5)
    h2.place_room(4, 4, Room("Kitchen", Direction(0)))
    key1 = _solution_key(h1, (2, 2), {"Kitchen"}, "none")
    key2 = _solution_key(h2, (2, 2), {"Kitchen"}, "none")
    assert key1 < key2


def test_solution_key_family_bonus():
    h1 = House(3, 3)
    h1.place_room(
        1,
        1,
        Room("PortalChamber", Direction.S, families=frozenset({"portal", "teleport"})),
    )
    h1.place_room(
        1,
        2,
        Room(
            "PortalNexus",
            Direction.N | Direction.E | Direction.S | Direction.W,
            families=frozenset({"portal", "teleport"}),
        ),
    )
    key = _solution_key(h1, (1, 1), set(), "none")
    assert key < 0
