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


def render_text(
    house: House,
    entrance_pos: tuple[int, int] | None = None,
    show_labels: bool = False,
    show_empty: bool = False,
) -> str:
    if house.width == 0 or house.height == 0 or not house.cells:
        return "<empty house>"
    xs = [x for x, _ in house.cells.keys()]
    ys = [y for _, y in house.cells.keys()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    ox, oy = entrance_pos if entrance_pos else (0, 0)
    min_dx = min_x - ox
    max_dx = max_x - ox
    min_dy = min_y - oy
    max_dy = max_y - oy

    label_width = max(2, len(str(min_dy)), len(str(max_dy)))
    lines: list[str] = []

    if show_labels:
        hdr = " " * label_width
        for x in range(min_dx, max_dx + 1):
            hdr += str(x).center(3)
        lines.append(hdr)

    for dy in range(min_dy, max_dy + 1):
        y = dy + oy
        row_fragments = ["", "", ""]
        for x in range(min_dx, max_dx + 1):
            abs_x = x + ox
            is_entrance = entrance_pos is not None and (abs_x, y) == entrance_pos
            top, middle, bottom = _render_tile(house, abs_x, y, is_entrance, show_empty)
            row_fragments[0] += top
            row_fragments[1] += middle
            row_fragments[2] += bottom
        blank = " " * label_width
        row_label = str(dy).rjust(label_width) if show_labels else blank
        lines.append(blank + row_fragments[0])
        lines.append(row_label + row_fragments[1])
        lines.append(blank + row_fragments[2])
    return "\n".join(lines)


def render_side_by_side(
    houses: list[House],
    entrance_pos: tuple[int, int] | None = None,
    cols: int = 2,
    gap: int = 4,
    show_labels: bool = False,
    show_empty: bool = False,
    legend: list[str] | None = None,
    legend_gap: int = 4,
) -> str:
    renders = [
        render_text(h, entrance_pos, show_labels, show_empty).split("\n")
        for h in houses
    ]
    max_lines = max(len(r) for r in renders)

    legend_lines: list[str] = []
    legend_w = 0
    if legend:
        legend_lines = list(legend)
        legend_w = max(len(l) for l in legend_lines) if legend_lines else 0
    n_legend = len(legend_lines)
    n_rows = (len(houses) + cols - 1) // cols
    total_lines = max(max_lines, n_legend) if legend_lines else max_lines

    for r in renders:
        while len(r) < total_lines:
            r.append("")
    while len(legend_lines) < total_lines:
        legend_lines.append(" " * legend_w)

    result: list[str] = []
    for i in range(0, len(houses), cols):
        batch = renders[i : i + cols]
        row_idx = i // cols
        for li in range(total_lines):
            parts = [r[li] for r in batch]
            if legend_lines and row_idx == n_rows - 1 and len(batch) < cols:
                parts.append(legend_lines[li])
            result.append((" " * gap).join(parts))
    return "\n".join(result)


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


def layout_dims(house: House) -> tuple[int, int]:
    xs = [x for x, _ in house.cells]
    ys = [y for _, y in house.cells]
    if not xs or not ys:
        return (0, 0)
    return (max(xs) - min(xs) + 1, max(ys) - min(ys) + 1)


def adjacency_count(house: House) -> int:
    count = 0
    for x, y in house.cells:
        for _, nx, ny in house.nearby_coords(x, y):
            if house.has_room(nx, ny):
                count += 1
    return count // 2


def near_entrance_dist(
    house: House, entrance: tuple[int, int], near_rooms: set[str]
) -> int:
    ex, ey = entrance
    total = 0
    for (x, y), room in house.cells.items():
        if room.name in near_rooms:
            total += abs(x - ex) + abs(y - ey)
    return total


def _render_tile(
    house: House, x: int, y: int, is_entrance: bool = False, show_empty: bool = True
) -> tuple[str, str, str]:
    room = house.get_room(x, y)
    if room is None:
        if show_empty:
            return "\u00b7 \u00b7", "   ", "\u00b7 \u00b7"
        return "   ", "   ", "   "

    if is_entrance:
        tl, tr, bl, br = "╔", "╗", "╚", "╝"
        wh, wv = "═", "║"
    else:
        tl, tr, bl, br = "┌", "┐", "└", "┘"
        wh, wv = "─", "│"

    def door(direction: Direction) -> str:
        if has_door(house, room, x, y, direction):
            return " "
        return wh if direction in (Direction.N, Direction.S) else wv

    top = f"{tl}{door(Direction.N)}{tr}"
    middle = f"{door(Direction.W)}{room_symbol(room)}{door(Direction.E)}"
    bottom = f"{bl}{door(Direction.S)}{br}"
    return top, middle, bottom


def has_door(house: House, room: Room, x: int, y: int, direction: Direction) -> bool:
    if not room:
        return False
    if bool(room.doors & direction):
        return True
    neighbor = house.get_room(
        x + direction_vector(direction)[0], y + direction_vector(direction)[1]
    )
    return neighbor is not None and bool(neighbor.doors & _opposite(direction))


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
