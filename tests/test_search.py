from model import Direction, House, Room
from search import LayoutSearch, canonical_layout_signature, rotation_variant_count, rotate_house
from constraints import DoorMatchingConstraint, ConnectivityConstraint, NoExposedDoorsConstraint


class NeverMatchingConstraint:
    def __call__(self, house: House) -> bool:
        return False


def test_rotation_variant_count():
    room = Room("A", Direction.N | Direction.S)
    assert rotation_variant_count(room) == 2


def test_layout_search_simple():
    rooms = [Room("A", Direction.E)]
    house = House(1, 1)
    constraint = DoorMatchingConstraint()
    search = LayoutSearch(1, 1, rooms, [constraint], [constraint])
    assert list(search.find_solutions())


def test_layout_search_adjacency():
    rooms = [Room("A", Direction.E), Room("B", Direction.W)]
    search = LayoutSearch(1, 2, rooms, [ConnectivityConstraint()], [ConnectivityConstraint()])
    solutions = list(search.find_solutions())
    assert solutions
    assert all(house.get_room(0, 0) for house in solutions)


def test_layout_search_solution_count():
    rooms = [Room("A", Direction.S), Room("B", Direction.N)]
    partial_constraints = [DoorMatchingConstraint(), ConnectivityConstraint()]
    final_constraints = partial_constraints + [NoExposedDoorsConstraint()]
    search = LayoutSearch(1, 2, rooms, partial_constraints, final_constraints)
    solutions = list(search.find_solutions())
    assert len(solutions) == 10
    assert all(len(house.cells) == len(rooms) for house in solutions)


def test_rotate_house_round_trip():
    house = House(2, 1)
    house.place_room(0, 0, Room("A", Direction.E))
    house.place_room(1, 0, Room("B", Direction.W))
    rotated = rotate_house(house, 1)
    restored = rotate_house(rotated, 3)
    assert canonical_layout_signature(house) == canonical_layout_signature(restored)


def test_canonical_layout_signature_rotation_invariant():
    house = House(1, 2)
    house.place_room(0, 0, Room("A", Direction.S))
    house.place_room(0, 1, Room("B", Direction.N))
    original = canonical_layout_signature(house)
    rotated = rotate_house(house, 2)
    assert canonical_layout_signature(rotated) == original


def test_layout_search_preplaced_rooms():
    preplaced_room = Room("A", Direction.E)
    rooms = [Room("B", Direction.W)]
    search = LayoutSearch(
        2,
        1,
        rooms,
        [DoorMatchingConstraint()],
        [DoorMatchingConstraint()],
        preplaced=[(0, 0, preplaced_room)],
    )
    solutions = list(search.find_solutions())
    assert solutions
    assert all(house.get_room(0, 0) is preplaced_room for house in solutions)
    assert all(house.get_room(1, 0) and house.get_room(1, 0).name == "B" for house in solutions)


def test_layout_search_partial_constraint_blocks():
    rooms = [Room("A", Direction(0))]
    constraint = NeverMatchingConstraint()
    search = LayoutSearch(1, 1, rooms, [constraint], [constraint])
    assert not list(search.find_solutions())
