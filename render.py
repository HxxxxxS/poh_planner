from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from model import Direction, House, Room


def room_symbol(room: Room) -> str:
    if room is None:
        return "?"
    if room.legend and room.legend.strip():
        return room.legend
    if room.name:
        return room.name[0]
    return "?"


def render_text(house: House) -> str:
    if house.width == 0 or house.height == 0 or not house.cells:
        return "<empty house>"
    xs = [x for x, _ in house.cells.keys()]
    ys = [y for _, y in house.cells.keys()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    lines: list[str] = []
    for y in range(min_y, max_y + 1):
        row_fragments = ["", "", ""]
        for x in range(min_x, max_x + 1):
            top, middle, bottom = _render_tile(house, x, y)
            row_fragments[0] += top
            row_fragments[1] += middle
            row_fragments[2] += bottom
        lines.extend(row_fragments)
    return "\n".join(lines)


def legend_entries(house: House) -> dict[str, set[str]]:
    entries: dict[str, set[str]] = defaultdict(set)
    for room in house.cells.values():
        symbol = room_symbol(room)
        if not symbol.strip():
            continue
        name = room.display_name or room.name
        if not name:
            continue
        entries[symbol].add(name)
    return entries


def format_legend(entries: dict[str, Iterable[str]]) -> list[str]:
    lines: list[str] = []
    for symbol in sorted(entries):
        names = sorted(entries[symbol])
        if not names:
            continue
        lines.append(f"{symbol} = {' / '.join(names)}")
    return lines


def _render_tile(house: House, x: int, y: int) -> tuple[str, str, str]:
    room = house.get_room(x, y)
    if room is None:
        return "   ", "   ", "   "

    def door(direction: Direction) -> str:
        return " " if has_door(house, room, x, y, direction) else _wall_segment(direction)

    top = f"┌{door(Direction.N)}┐"
    middle = (
        f"{door(Direction.W)}"
        f"{room_symbol(room)}"
        f"{door(Direction.E)}"
    )
    bottom = f"└{door(Direction.S)}┘"
    return top, middle, bottom


def has_door(house: House, room: Room, x: int, y: int, direction: Direction) -> bool:
    if not room:
        return False
    if bool(room.doors & direction):
        return True
    neighbor = house.get_room(x + direction_vector(direction)[0], y + direction_vector(direction)[1])
    return neighbor is not None and bool(neighbor.doors & _opposite(direction))


def _wall_segment(direction: Direction) -> str:
    return "─" if direction in (Direction.N, Direction.S) else "│"


def direction_vector(direction: Direction) -> tuple[int, int]:
    return {
        Direction.N: (0, -1),
        Direction.E: (1, 0),
        Direction.S: (0, 1),
        Direction.W: (-1, 0),
    }[direction]


def _opposite(direction: Direction) -> Direction:
    mapping = {
        Direction.N: Direction.S,
        Direction.E: Direction.W,
        Direction.S: Direction.N,
        Direction.W: Direction.E,
    }
    return mapping[direction]
