from __future__ import annotations

from typing import Iterable, Iterator, Tuple

from model import DIRECTION_VECTORS, FULL_DOOR_MASK, OPPOSITE_DIRECTION, House, Room
from constraints import Constraint, NoExposedDoorsConstraint


def _rotate_coords(
    x: int, y: int, width: int, height: int, rotation: int
) -> tuple[int, int]:
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


def canonical_layout_signature(
    house: House,
) -> tuple[int, int, tuple[Tuple[int, int, str, int], ...]]:
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
            list(final_constraints)
            if final_constraints is not None
            else list(self.partial_constraints)
        )
        self.house = House(width, height)
        self.room_counts: dict[Room, int] = {}
        for room in rooms:
            self.room_counts[room] = self.room_counts.get(room, 0) + 1
        self.unique_rooms = list(self.room_counts.keys())
        if preplaced:
            for x, y, room in preplaced:
                self.house.place_room(x, y, room)
        self.boundary: list[tuple[int, int]] = sorted(self._calc_boundary())
        self._check_exposed = any(
            isinstance(c, NoExposedDoorsConstraint) for c in self.final_constraints
        )

    def _calc_boundary(self) -> set[tuple[int, int]]:
        if not self.house.cells:
            return {(0, 0)}
        boundary: set[tuple[int, int]] = set()
        for (x, y), _ in self.house.iter_rooms():
            for _, nx, ny in self.house.nearby_coords(x, y):
                if not self.house.has_room(nx, ny):
                    boundary.add((nx, ny))
        return boundary

    def _boundary_key(self, pos: tuple[int, int]) -> int:
        x, y = pos
        return -sum(
            1
            for dx, dy in [(0, -1), (1, 0), (0, 1), (-1, 0)]
            if (x + dx, y + dy) in self.house.cells
        )

    def matches_partial(self) -> bool:
        return all(constraint(self.house) for constraint in self.partial_constraints)

    def matches_final(self) -> bool:
        if not self.matches_partial():
            return False
        if not self._all_rooms_placed():
            return False
        return all(constraint(self.house) for constraint in self.final_constraints)

    def find_solutions(self) -> Iterator[House]:
        seen_signatures: set[tuple[int, int, tuple[Tuple[int, int, str, int], ...]]] = (
            set()
        )
        yield from self._backtrack(seen_signatures)

    def _place_room_and_recurse(
        self,
        room: Room,
        x: int,
        y: int,
        seen: set[tuple[int, int, tuple[Tuple[int, int, str, int], ...]]],
    ) -> Iterator[House]:
        self.house.place_room(x, y, room)
        added = self._add_to_boundary(x, y)
        if self.matches_partial():
            yield from self._backtrack(seen)
        self._remove_from_boundary(added)
        self.house.remove_room(x, y)

    def _add_to_boundary(self, x: int, y: int) -> set[tuple[int, int]]:
        added: set[tuple[int, int]] = set()
        for _, nx, ny in self.house.nearby_coords(x, y):
            if not self.house.has_room(nx, ny) and (nx, ny) not in self.boundary:
                added.add((nx, ny))
        self.boundary.extend(added)
        self.boundary.sort(key=self._boundary_key)
        return added

    def _remove_from_boundary(self, coords: set[tuple[int, int]]) -> None:
        if not coords:
            return
        keep = [p for p in self.boundary if p not in coords]
        self.boundary.clear()
        self.boundary.extend(keep)

    def _try_room_placements(
        self,
        base_room: Room,
        x: int,
        y: int,
        seen: set[tuple[int, int, tuple[Tuple[int, int, str, int], ...]]],
    ) -> Iterator[House]:
        if base_room.doors == FULL_DOOR_MASK:
            yield from self._place_room_and_recurse(base_room, x, y, seen)
            return
        seen_masks: set[int] = set()
        for rotation in range(4):
            rotated_room = base_room.rotated(rotation)
            mask = int(rotated_room.doors)
            if mask in seen_masks:
                continue
            seen_masks.add(mask)
            yield from self._place_room_and_recurse(rotated_room, x, y, seen)

    def _would_expose(self, x: int, y: int) -> bool:
        for direction, nx, ny in self.house.nearby_coords(x, y):
            room = self.house.get_room(nx, ny)
            if (
                room is not None
                and not room.allow_exposed_doors
                and bool(room.doors & OPPOSITE_DIRECTION[direction])
            ):
                return True
        return False

    def _all_rooms_placed(self) -> bool:
        return all(count == 0 for count in self.room_counts.values())

    def _backtrack(
        self,
        seen: set[tuple[int, int, tuple[Tuple[int, int, str, int], ...]]],
    ) -> Iterator[House]:
        if self._all_rooms_placed():
            if self.matches_final():
                signature = canonical_layout_signature(self.house)
                if signature not in seen:
                    seen.add(signature)
                    yield self.house.clone()
            return
        if not self.boundary:
            return
        x, y = self.boundary.pop()
        for room in self.unique_rooms:
            count = self.room_counts.get(room, 0)
            if count == 0:
                continue
            self.room_counts[room] = count - 1
            yield from self._try_room_placements(room, x, y, seen)
            self.room_counts[room] = count
        if self.matches_partial():
            if not self._check_exposed or not self._would_expose(x, y):
                yield from self._backtrack(seen)
        self.boundary.append((x, y))
