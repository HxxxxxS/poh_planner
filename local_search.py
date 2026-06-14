from __future__ import annotations

import random
from typing import Iterable, Iterator, Tuple

from model import OPPOSITE_DIRECTION, FULL_DOOR_MASK, House, Room
from constraints import Constraint, ConnectivityConstraint, NoExposedDoorsConstraint


class LocalSearch:
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
        self.rooms = list(rooms)
        self.final = list(final_constraints) if final_constraints is not None else []
        self.preplaced = list(preplaced or [])
        self._fixed: set[tuple[int, int]] = {(x, y) for (x, y, _) in self.preplaced}

    def find_solutions(self) -> Iterator[House]:
        seen: set[frozenset[tuple[int, int, str, int]]] = set()
        for _ in range(50):
            h = self._init_compact()
            if h is None:
                continue
            sol = self._repair(h)
            if sol is None:
                continue
            if not all(c(sol) for c in self.final):
                continue
            sig = frozenset(
                (x, y, r.name, int(r.doors)) for (x, y), r in sol.iter_rooms()
            )
            if sig in seen:
                continue
            seen.add(sig)
            yield sol

    def _init_compact(self) -> House | None:
        h = House(self.width, self.height)
        for x, y, r in self.preplaced:
            h.place_room(x, y, r)
        remaining = list(self.rooms)
        random.shuffle(remaining)
        while remaining:
            boundary: set[tuple[int, int]] = set()
            for (bx, by), _ in h.iter_rooms():
                for _, nx, ny in h.nearby_coords(bx, by):
                    if not h.has_room(nx, ny):
                        boundary.add((nx, ny))
            if not boundary:
                return None
            r = remaining.pop()
            cx, cy = random.choice(list(boundary))
            h.place_room(cx, cy, r.rotated(random.randint(0, 3)))
        return h

    def _count_door_cost(self, h: House) -> int:
        c = 0
        for (x, y), r in h.iter_rooms():
            for d, nx, ny in h.nearby_coords(x, y):
                if not bool(r.doors & d):
                    continue
                n = h.get_room(nx, ny)
                if n is None:
                    if not r.allow_exposed_doors:
                        c += 1
                elif not bool(n.doors & OPPOSITE_DIRECTION[d]):
                    c += 1
        return c

    def _find_exposed(self, h: House) -> list[tuple[int, int, int, int]]:
        result: list[tuple[int, int, int, int]] = []
        for (x, y), r in h.iter_rooms():
            if r.allow_exposed_doors:
                continue
            for d, nx, ny in h.nearby_coords(x, y):
                if bool(r.doors & d) and h.get_room(nx, ny) is None:
                    result.append((x, y, nx, ny))
        return result

    def _find_mismatches(self, h: House) -> list[tuple[int, int, int, int]]:
        result: list[tuple[int, int, int, int]] = []
        for (x, y), r in h.iter_rooms():
            for d, nx, ny in h.nearby_coords(x, y):
                n = h.get_room(nx, ny)
                if n is None:
                    continue
                if bool(r.doors & d) != bool(n.doors & OPPOSITE_DIRECTION[d]):
                    result.append((x, y, nx, ny))
        return result

    def _room_violations(self, h: House, x: int, y: int) -> int:
        r = h.get_room(x, y)
        if r is None:
            return 0
        c = 0
        for d, nx, ny in h.nearby_coords(x, y):
            if not bool(r.doors & d):
                continue
            n = h.get_room(nx, ny)
            if n is None:
                if not r.allow_exposed_doors:
                    c += 1
            elif not bool(n.doors & OPPOSITE_DIRECTION[d]):
                c += 1
        return c

    def _try_repair_move(
        self, h: House, rx: int, ry: int, empty: list, best_only: bool = False
    ) -> bool:
        r = h.get_room(rx, ry)
        if r is None:
            return False
        old_score = self._room_violations(h, rx, ry)
        for _, nx, ny in h.nearby_coords(rx, ry):
            if h.get_room(nx, ny) is not None:
                old_score += self._room_violations(h, nx, ny)

        best_delta = 0
        best_target = None
        for ex, ey in random.sample(empty, min(10, len(empty))):
            h.remove_room(rx, ry)
            h.place_room(ex, ey, r)
            new_score = self._room_violations(h, ex, ey)
            for _, nx, ny in h.nearby_coords(ex, ey):
                if h.get_room(nx, ny) is not None:
                    new_score += self._room_violations(h, nx, ny)
            h.remove_room(ex, ey)
            h.place_room(rx, ry, r)
            delta = new_score - old_score
            if delta < best_delta:
                best_delta = delta
                best_target = (ex, ey)

        if best_target is not None and best_delta < 0:
            ex, ey = best_target
            h.remove_room(rx, ry)
            h.place_room(ex, ey, r)
            empty.remove((ex, ey))
            empty.append((rx, ry))
            return True
        return False

    def _components(self, h: House) -> int:
        if not h.cells:
            return 0
        seen: set[tuple[int, int]] = set()
        n = 0
        for start in h.cells:
            if start in seen:
                continue
            n += 1
            stack = [start]
            while stack:
                p = stack.pop()
                if p in seen:
                    continue
                seen.add(p)
                for _, nx, ny in h.nearby_coords(*p):
                    if h.get_room(nx, ny) is not None and (nx, ny) not in seen:
                        stack.append((nx, ny))
        return n

    def _repair(self, h: House) -> House | None:
        empty = [
            (x, y)
            for x in range(self.width)
            for y in range(self.height)
            if not h.has_room(x, y)
        ]
        movable = [(x, y) for (x, y), _ in h.iter_rooms() if (x, y) not in self._fixed]

        for iteration in range(30000):
            cost = self._count_door_cost(h)
            if cost == 0:
                if self._components(h) > 1:
                    cost = 100
                else:
                    return h

            exposed = self._find_exposed(h)
            mismatches = self._find_mismatches(h)

            if exposed:
                x, y, tx, ty = random.choice(exposed)
                candidates: list[tuple[int, int]] = []
                if (tx, ty) in empty:
                    candidates.append((tx, ty))
                for dx in range(-1, 2):
                    for dy in range(-1, 2):
                        nx, ny = tx + dx, ty + dy
                        if (nx, ny) in movable:
                            candidates.append((nx, ny))
                random.shuffle(candidates)
                for cx, cy in candidates[:5]:
                    if self._try_repair_move(h, cx, cy, empty):
                        break
            elif mismatches:
                x, y, mx, my = random.choice(mismatches)
                for rot in range(1, 4):
                    r = h.get_room(x, y)
                    if r is None:
                        break
                    new_r = r.rotated(rot)
                    h.remove_room(x, y)
                    h.place_room(x, y, new_r)
                    if self._room_violations(h, x, y) == 0:
                        break
                    h.remove_room(x, y)
                    h.place_room(x, y, r)
            else:
                if iteration > 1000 and random.random() < 0.1:
                    rx, ry = random.choice(movable)
                    self._try_repair_move(h, rx, ry, empty)

        return None
