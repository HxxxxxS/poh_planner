from __future__ import annotations

from typing import Callable

from model import House, OPPOSITE_DIRECTION


Constraint = Callable[[House], bool]


class DoorMatchingConstraint:
    def __call__(self, house: House) -> bool:
        for (x, y), room in house.iter_rooms():
            for direction, nx, ny in house.nearby_coords(x, y):
                neighbor = house.get_room(nx, ny)
                if neighbor is None:
                    continue
                current_has = bool(room.doors & direction)
                neighbor_has = bool(neighbor.doors & OPPOSITE_DIRECTION[direction])
                if current_has != neighbor_has:
                    return False
        return True


class ConnectivityConstraint:
    def __call__(self, house: House) -> bool:
        if house.cells:
            start = next(iter(house.cells))
            visited = set()
            stack = [start]
            while stack:
                cx, cy = stack.pop()
                if (cx, cy) in visited:
                    continue
                visited.add((cx, cy))
                for direction, nx, ny in house.nearby_coords(cx, cy):
                    if house.get_room(cx, cy) and house.get_room(nx, ny):
                        stack.append((nx, ny))
            return len(visited) == len(house.cells)
        return True


class NoExposedDoorsConstraint:
    def __call__(self, house: House) -> bool:
        for (x, y), room in house.iter_rooms():
            for direction, nx, ny in house.nearby_coords(x, y):
                if bool(room.doors & direction) and house.get_room(nx, ny) is None:
                    return False
        return True
