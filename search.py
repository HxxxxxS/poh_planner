from __future__ import annotations

from typing import Iterable, Iterator, Tuple

from model import DIRECTION_VECTORS, FULL_DOOR_MASK, House, Room
from constraints import Constraint


def _rotate_coords(x: int, y: int, width: int, height: int, rotation: int) -> tuple[int, int]:
    rotation = rotation % 4
    if rotation == 0:
        return x, y
    if rotation == 1:
        return height - 1 - y, x
    if rotation == 2:
        return width - 1 - x, height - 1 - y
    if rotation == 3:
        return y, width - 1 - x
    raise ValueError("unsupported rotation")


def rotate_house(house: House, rotation: int) -> House:
    rotation = rotation % 4
    if rotation == 0:
        return house.clone()
    width = house.width
    height = house.height
    if rotation % 2 == 0:
        new_width = width
        new_height = height
    else:
        new_width = height
        new_height = width
    rotated = House(new_width, new_height)
    for (x, y), room in house.iter_rooms():
        new_x, new_y = _rotate_coords(x, y, width, height, rotation)
        rotated_room = room.rotated(rotation)
        rotated.place_room(new_x, new_y, rotated_room)
    return rotated


def canonical_layout_signature(house: House) -> tuple[int, int, tuple[Tuple[int, int, str, int], ...]]:
    signatures = []
    for rotation in range(4):
        rotated = rotate_house(house, rotation)
        entries = tuple(
            sorted(
                ((x, y, room.name, int(room.doors)))
                for (x, y), room in rotated.iter_rooms()
            )
        )
        signatures.append((rotated.width, rotated.height, entries))
    return min(signatures)


def rotation_variant_count(room: Room) -> int:
    return len({int(room.rotated(rotation).doors) for rotation in range(4)})


class LayoutSearch:
    def __init__(
        self,
        width: int,
        height: int,
        rooms: Iterable[Room],
        partial_constraints: Iterable[Constraint],
        final_constraints: Iterable[Constraint] | None = None,
        preplaced: Iterable[Tuple[int, int, Room]] | None = None,
    ) -> None:
        self.width = width
        self.height = height
        self.partial_constraints = list(partial_constraints)
        self.final_constraints = (
            list(final_constraints) if final_constraints is not None else list(self.partial_constraints)
        )
        self.house = House(width, height)
        self.room_counts: dict[Room, int] = {}
        for room in rooms:
            self.room_counts[room] = self.room_counts.get(room, 0) + 1
        self.unique_rooms = list(self.room_counts.keys())
        if preplaced:
            for x, y, room in preplaced:
                self.house.place_room(x, y, room)
        self.fill_positions = [
            (x, y)
            for y in range(height)
            for x in range(width)
            if not self.house.has_room(x, y)
        ]

    def _has_adjacent_room(self, x: int, y: int) -> bool:
        for _, nx, ny in self.house.nearby_coords(x, y):
            if self.house.has_room(nx, ny):
                return True
        return False

    def matches_partial(self) -> bool:
        return all(constraint(self.house) for constraint in self.partial_constraints)

    def matches_final(self) -> bool:
        if not self.matches_partial():
            return False
        if not self._all_rooms_placed():
            return False
        return all(constraint(self.house) for constraint in self.final_constraints)

    def find_solutions(self) -> Iterator[House]:
        seen_signatures: set[tuple[int, int, tuple[Tuple[int, int, str, int], ...]]] = set()
        yield from self._backtrack(0, seen_signatures)

    def _place_room_and_recurse(
        self, room: Room, x: int, y: int, cell_index: int, seen: set[tuple[int, int, tuple[Tuple[int, int, str, int], ...]]]
    ) -> Iterator[House]:
        self.house.place_room(x, y, room)
        if self.matches_partial():
            yield from self._backtrack(cell_index + 1, seen)
        self.house.remove_room(x, y)

    def _try_room_placements(
        self, base_room: Room, x: int, y: int, cell_index: int, seen: set[tuple[int, int, tuple[Tuple[int, int, str, int], ...]]]
    ) -> Iterator[House]:
        if base_room.doors == FULL_DOOR_MASK:
            yield from self._place_room_and_recurse(base_room, x, y, cell_index, seen)
            return
        seen_masks: set[int] = set()
        for rotation in range(4):
            rotated_room = base_room.rotated(rotation)
            mask = int(rotated_room.doors)
            if mask in seen_masks:
                continue
            seen_masks.add(mask)
            yield from self._place_room_and_recurse(rotated_room, x, y, cell_index, seen)

    def _all_rooms_placed(self) -> bool:
        return all(count == 0 for count in self.room_counts.values())

    def _backtrack(
        self,
        cell_index: int,
        seen: set[tuple[int, int, tuple[Tuple[int, int, str, int], ...]]],
    ) -> Iterator[House]:
        if cell_index == len(self.fill_positions):
            if self.matches_final():
                signature = canonical_layout_signature(self.house)
                if signature not in seen:
                    seen.add(signature)
                    yield self.house.clone()
            return
        x, y = self.fill_positions[cell_index]
        can_place_room = not self.house.cells or self._has_adjacent_room(x, y)
        if can_place_room:
            for room in self.unique_rooms:
                count = self.room_counts.get(room, 0)
                if count == 0:
                    continue
                self.room_counts[room] = count - 1
                yield from self._try_room_placements(room, x, y, cell_index, seen)
                self.room_counts[room] = count
        if self.matches_partial():
            yield from self._backtrack(cell_index + 1, seen)
