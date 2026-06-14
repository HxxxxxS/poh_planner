from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Tuple

from constraints import (
    ConnectivityConstraint,
    Constraint,
    DoorMatchingConstraint,
    NoExposedDoorsConstraint,
)
from model import Direction, House, Room
from render import format_legend, legend_entries, render_text
from search import LayoutSearch


SCRIPT_DIR = Path(__file__).parent
ROOMS_JSON = SCRIPT_DIR / "rooms.json"


def _door_mask_from_string(value: str) -> Direction:
    mask = Direction(0)
    for symbol in value.upper():
        match symbol:
            case "N":
                mask |= Direction.N
            case "E":
                mask |= Direction.E
            case "S":
                mask |= Direction.S
            case "W":
                mask |= Direction.W
    return mask


def _normalize_name(name: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", " ", name).strip()
    words = [word.title() for word in normalized.split() if word]
    return "".join(words) if words else ""


def _load_room_catalog() -> Tuple[dict[str, Room], dict[str, str]]:
    if not ROOMS_JSON.exists():
        raise FileNotFoundError(f"Missing room catalog {ROOMS_JSON}")
    catalog: dict[str, Room] = {}
    alias_lookup: dict[str, str] = {}
    with open(ROOMS_JSON, encoding="utf-8") as handle:
        raw = json.load(handle)
    for entry in raw:
        name = entry["room"]
        canonical = _normalize_name(name)
        doors = entry.get("doors", "")
        mask = _door_mask_from_string(doors)
        alias_entries = entry.get("aliases") or []
        normalized_aliases: list[str] = []
        seen: set[str] = set()
        canonical_key = canonical.casefold()
        for alias in alias_entries:
            if not alias:
                continue
            normalized_alias = _normalize_name(alias)
            key = normalized_alias.casefold()
            if not normalized_alias or key == canonical_key or key in seen:
                continue
            seen.add(key)
            normalized_aliases.append(normalized_alias)
        legend = entry.get("legend")
        room = Room(
            canonical,
            mask,
            canonical == "Garden",
            display_name=name,
            aliases=(canonical,) + tuple(normalized_aliases),
            legend=legend,
        )
        catalog[canonical] = room
        alias_lookup[canonical.casefold()] = canonical
        for alias in normalized_aliases:
            alias_lookup[alias.casefold()] = canonical
    return catalog, alias_lookup


ROOM_CATALOG, ALIAS_LOOKUP = _load_room_catalog()

DEFAULT_ROOM_COUNTS: dict[str, int] = {
    #    "Parlour": 1,
    #    "Kitchen": 1,
}
CONSTRUCTION_LEVEL_LIMITS: list[tuple[int, int, int]] = [
    (1, 3, 24),
    (15, 4, 24),
    (26, 4, 25),
    (30, 5, 25),
    (32, 5, 26),
    (38, 5, 27),
    (44, 5, 28),
    (45, 6, 28),
    (50, 6, 29),
    (56, 6, 30),
    (60, 7, 30),
    (62, 7, 31),
    (68, 7, 32),
    (74, 7, 33),
    (80, 7, 34),
    (86, 7, 35),
    (92, 7, 36),
    (96, 7, 37),
    (99, 7, 38),
]
DEFAULT_CONSTRUCTION_LEVEL = 99
ENTRANCE_ROOM = ROOM_CATALOG.get(
    "Garden",
    Room(
        "Garden",
        Direction.N | Direction.E | Direction.S | Direction.W,
        allow_exposed_doors=True,
    ),
)


def _door_mask_to_string(value: Direction) -> str:
    parts: list[str] = []
    for symbol, direction in (
        ("N", Direction.N),
        ("E", Direction.E),
        ("S", Direction.S),
        ("W", Direction.W),
    ):
        if bool(value & direction):
            parts.append(symbol)
    return "".join(parts) or "<none>"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate POH layouts with constraint checking."
    )
    parser.add_argument("--width", type=int, default=7, help="House width in tiles.")
    parser.add_argument("--height", type=int, default=7, help="House height in tiles.")
    parser.add_argument(
        "--construction-level",
        type=int,
        default=DEFAULT_CONSTRUCTION_LEVEL,
        help="Construction level to determine max house dimensions and allowed rooms.",
    )
    parser.add_argument(
        "--allow-exposed",
        action="store_true",
        help="Permit doors to face empty tiles (disables the no-exposed-doors rule).",
    )
    parser.add_argument(
        "--room",
        action="append",
        default=[],
        help="Add a room type and optional count (NAME or NAME=COUNT).",
    )
    parser.add_argument(
        "--pin-room",
        action="append",
        default=[],
        help="Force a room type at a coordinate relative to center (X,Y=NAME).",
    )
    parser.add_argument(
        "--entrance",
        default=None,
        help="Override the entrance coordinate relative to center (X,Y).",
    )
    parser.add_argument(
        "--list-rooms",
        action="store_true",
        help="Print usage and list available room types, then exit.",
    )
    parser.add_argument(
        "--max-solutions",
        type=int,
        default=0,
        help="Stop after finding N solutions (0 = find all).",
    )
    return parser


def _resolve_room_name(input_name: str) -> str:
    normalized = _normalize_name(input_name)
    if not normalized:
        raise ValueError("Room name cannot be empty")
    key = normalized.casefold()
    canonical = ALIAS_LOOKUP.get(key)
    if canonical is None:
        raise ValueError(f"Unknown room type: {input_name}")
    return canonical


def build_room_selection(selections: Iterable[str]) -> dict[str, int]:
    counts = dict(DEFAULT_ROOM_COUNTS)
    for token in selections:
        if "=" not in token:
            name = token.strip()
            raw_count = "1"
        else:
            name, raw_count = token.split("=", 1)
            name = name.strip()
            raw_count = raw_count.strip() or "1"
        canonical = _resolve_room_name(name)
        if raw_count == "" or raw_count is None:
            raw_count = "1"
        count = int(raw_count)
        if count < 0:
            raise ValueError("Room count cannot be negative")
        counts[canonical] = count
    return counts


def _limit_for_level(level: int) -> tuple[int, int]:
    size = 3
    rooms = 24
    for threshold, limit_size, limit_rooms in CONSTRUCTION_LEVEL_LIMITS:
        if level >= threshold:
            size = limit_size
            rooms = limit_rooms
    return size, rooms


def _parse_coordinate(token: str) -> tuple[int, int]:
    raw = token.strip()
    if "," not in raw:
        raise ValueError("Coordinates must be X,Y")
    x_raw, y_raw = raw.split(",", 1)
    return int(x_raw.strip()), int(y_raw.strip())


def _relative_to_absolute(
    rel_x: int, rel_y: int, width: int, height: int
) -> tuple[int, int]:
    center_x = (width - 1) // 2
    center_y = (height - 1) // 2
    return center_x + rel_x, center_y + rel_y


def _validate_within_bounds(x: int, y: int, width: int, height: int) -> None:
    if not (0 <= x < width and 0 <= y < height):
        raise ValueError(
            f"Coordinate ({x},{y}) outside house dimensions {width}x{height}"
        )


def build_pinned_rooms(
    tokens: Iterable[str], width: int, height: int, entrance: tuple[int, int]
) -> tuple[dict[Tuple[int, int], Room], Counter[str]]:
    pinned: dict[Tuple[int, int], Room] = {}
    counts: Counter[str] = Counter()
    for token in tokens:
        if "=" not in token:
            raise ValueError("Pinned room must be expressed as X,Y=NAME")
        coord_part, name_part = token.split("=", 1)
        rel_x, rel_y = _parse_coordinate(coord_part)
        x, y = _relative_to_absolute(rel_x, rel_y, width, height)
        _validate_within_bounds(x, y, width, height)
        if (x, y) == entrance:
            raise ValueError("Pinned room cannot share the entrance tile")
        name = name_part.strip()
        if name not in ROOM_CATALOG:
            raise ValueError(f"Unknown pinned room type: {name}")
        if (x, y) in pinned:
            raise ValueError(f"Coordinate ({x},{y}) already pinned")
        pinned[(x, y)] = ROOM_CATALOG[name]
        counts[name] += 1
    return pinned, counts


def expand_rooms(counts: dict[str, int], pinned_counts: Counter[str]) -> list[Room]:
    rooms: list[Room] = []
    for name, total in counts.items():
        pinned = pinned_counts.get(name, 0)
        extra = total - pinned
        if extra < 0:
            raise ValueError("Pinned rooms exceed requested counts")
        base = ROOM_CATALOG[name]
        for _ in range(extra):
            rooms.append(Room(base.name, base.doors, base.allow_exposed_doors))
    return rooms


def build_partial_constraints() -> list[Constraint]:
    return [DoorMatchingConstraint(), ConnectivityConstraint()]


def build_final_constraints(allow_exposed: bool) -> list[Constraint] | None:
    if allow_exposed:
        return None
    return [NoExposedDoorsConstraint()]


def _print_usage_and_rooms(parser: argparse.ArgumentParser) -> None:
    parser.print_help()
    keys = sorted(ROOM_CATALOG.items())
    print("\nAvailable room types (friendly name first, alias keys afterward):\n")
    for _, room in keys:
        display = room.display_name or room.name
        alias_list = [alias for alias in room.aliases if alias != room.name]
        legend = f" [{room.legend}]" if room.legend else ""
        if alias_list:
            print(f"  {display}{legend} ({', '.join(alias_list)})")
        else:
            print(f"  {display}{legend}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.list_rooms:
        _print_usage_and_rooms(parser)
        return
    size_limit, max_rooms = _limit_for_level(args.construction_level)
    if args.width <= 0 or args.height <= 0:
        print("House dimensions must be positive")
        return
    if args.width > size_limit or args.height > size_limit:
        print(
            f"Requested {args.width}x{args.height} exceeds the max {size_limit}x{size_limit} for Construction level {args.construction_level}."
        )
        return
    default_entrance = ((args.width - 1) // 2, (args.height - 1) // 2)
    try:
        if args.entrance:
            entrance_pos = _parse_coordinate(args.entrance)
        else:
            entrance_pos = default_entrance
        _validate_within_bounds(
            entrance_pos[0], entrance_pos[1], args.width, args.height
        )
        pinned_rooms, pinned_counts = build_pinned_rooms(
            args.pin_room, args.width, args.height, entrance_pos
        )
        counts = build_room_selection(args.room)
        for name, pinned_count in pinned_counts.items():
            counts[name] = max(counts.get(name, 0), pinned_count)
        total_rooms = sum(counts.values())
        if total_rooms + 1 > max_rooms:
            print(
                f"Requested {total_rooms + 1} rooms (including the garden) exceeds the allowed {max_rooms} for Construction level {args.construction_level}."
            )
            return
        rooms = expand_rooms(counts, pinned_counts)
    except ValueError as exc:
        print(f"Invalid input: {exc}")
        return
    partial_constraints = build_partial_constraints()
    final_constraints = build_final_constraints(args.allow_exposed)
    preplaced = [(entrance_pos[0], entrance_pos[1], ENTRANCE_ROOM)] + [
        (coord[0], coord[1], room) for coord, room in pinned_rooms.items()
    ]
    search = LayoutSearch(
        args.width,
        args.height,
        rooms,
        partial_constraints,
        final_constraints,
        preplaced,
    )
    start_time = time.monotonic()
    solutions: list[House] = []
    limit = args.max_solutions or None
    for solution in search.find_solutions():
        solutions.append(solution)
        if limit and len(solutions) >= limit:
            break
    elapsed = time.monotonic() - start_time
    if not solutions:
        print("No layout satisfies the constraints.")
        print(f"Elapsed: {elapsed:.2f}s")
        return
    for idx, solution in enumerate(solutions, start=1):
        print(f"Solution {idx}:")
        print(render_text(solution))
        print()
    legend_map: defaultdict[str, set[str]] = defaultdict(set)
    for solution in solutions:
        entries = legend_entries(solution)
        for symbol, names in entries.items():
            legend_map[symbol].update(names)
    legend_lines = format_legend(legend_map)
    if legend_lines:
        print("\n".join(legend_lines))
        print()
    print(f"Elapsed: {elapsed:.2f}s")


if __name__ == "__main__":
    main()
