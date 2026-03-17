from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntFlag
from typing import Dict, Iterable, Iterator, Tuple


class Direction(IntFlag):
    N = 1
    E = 2
    S = 4
    W = 8


DIRECTION_ORDER = [Direction.N, Direction.E, Direction.S, Direction.W]

DIRECTION_VECTORS: Dict[Direction, Tuple[int, int]] = {
    Direction.N: (0, -1),
    Direction.E: (1, 0),
    Direction.S: (0, 1),
    Direction.W: (-1, 0),
}

FULL_DOOR_MASK = Direction.N | Direction.E | Direction.S | Direction.W

OPPOSITE_DIRECTION: Dict[Direction, Direction] = {
    Direction.N: Direction.S,
    Direction.E: Direction.W,
    Direction.S: Direction.N,
    Direction.W: Direction.E,
}


@dataclass(frozen=True)
class Room:
    name: str
    doors: Direction
    allow_exposed_doors: bool = False
    display_name: str | None = None
    aliases: tuple[str, ...] = field(default_factory=tuple)
    legend: str | None = None

    def __post_init__(self) -> None:
        if self.display_name is None:
            object.__setattr__(self, "display_name", self.name)
        if not self.aliases:
            object.__setattr__(self, "aliases", (self.name,))

    def rotated(self, rotation: int) -> "Room":
        normalized_rotation = rotation % 4
        if normalized_rotation == 0:
            return self
        rotated_doors = rotate_mask(self.doors, normalized_rotation)
        return Room(
            self.name,
            rotated_doors,
            self.allow_exposed_doors,
            self.display_name,
            self.aliases,
            self.legend,
        )


@dataclass
class House:
    width: int
    height: int
    cells: Dict[Tuple[int, int], Room] = field(default_factory=dict)

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def get_room(self, x: int, y: int) -> Room | None:
        return self.cells.get((x, y))

    def has_room(self, x: int, y: int) -> bool:
        return (x, y) in self.cells

    def place_room(self, x: int, y: int, room: Room) -> None:
        if not self.in_bounds(x, y):
            raise ValueError("coordinates out of bounds")
        if (x, y) in self.cells:
            raise ValueError("space already occupied")
        self.cells[(x, y)] = room

    def remove_room(self, x: int, y: int) -> None:
        self.cells.pop((x, y), None)

    def has_door(self, x: int, y: int, direction: Direction) -> bool:
        room = self.get_room(x, y)
        if room is None:
            return False
        return bool(room.doors & direction)

    def iter_rooms(self) -> Iterator[Tuple[Tuple[int, int], Room]]:
        yield from self.cells.items()

    def clone(self) -> "House":
        return House(self.width, self.height, dict(self.cells))

    def nearby_coords(self, x: int, y: int) -> Iterable[Tuple[Direction, int, int]]:
        for direction, vector in DIRECTION_VECTORS.items():
            nx = x + vector[0]
            ny = y + vector[1]
            if self.in_bounds(nx, ny):
                yield direction, nx, ny


def rotate_mask(mask: Direction, rotation: int) -> Direction:
    rotation = rotation % 4
    if rotation == 0:
        return mask
    result = Direction(0)
    for direction in DIRECTION_ORDER:
        if mask & direction:
            idx = DIRECTION_ORDER.index(direction)
            rotated = DIRECTION_ORDER[(idx + rotation) % 4]
            result |= rotated
    return result
