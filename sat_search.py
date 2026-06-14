from __future__ import annotations

from typing import Iterable, Iterator

from ortools.sat.python import cp_model

from model import (
    DIRECTION_ORDER,
    DIRECTION_VECTORS,
    FULL_DOOR_MASK,
    Direction,
    House,
    Room,
)
from constraints import (
    Constraint,
    ConnectivityConstraint,
    NoExposedDoorsConstraint,
)


def _get_neighbors(x: int, y: int, width: int, height: int) -> list[tuple[int, int]]:
    res: list[tuple[int, int]] = []
    for dx, dy in DIRECTION_VECTORS.values():
        nx, ny = x + dx, y + dy
        if 0 <= nx < width and 0 <= ny < height:
            res.append((nx, ny))
    return res


class CpSatSearch:
    def __init__(
        self,
        width: int,
        height: int,
        rooms: Iterable[Room],
        partial_constraints: Iterable[Constraint],
        final_constraints: Iterable[Constraint] | None = None,
        preplaced: Iterable[tuple[int, int, Room]] | None = None,
        goal: str = "none",
        near_rooms: set[str] | None = None,
        entrance_pos: tuple[int, int] | None = None,
    ) -> None:
        self.width = width
        self.height = height
        self._compact = goal in ("compact", "filled")
        self._filled = goal == "filled"
        self._near_rooms = near_rooms or set()
        self._entrance = entrance_pos
        partial = list(partial_constraints)
        self._partial = partial
        self.final = (
            list(final_constraints) if final_constraints is not None else list(partial)
        )
        self._check_exposed = any(
            isinstance(c, NoExposedDoorsConstraint) for c in self.final
        )
        self._require_connectivity = any(
            isinstance(c, ConnectivityConstraint) for c in self.final + partial
        )
        seen: set[type] = set()
        self._all_checkers: list[Constraint] = []
        for c in self.final + partial:
            if type(c) not in seen:
                self._all_checkers.append(c)
                seen.add(type(c))
        self.preplaced = list(preplaced or [])
        self._rooms = list(rooms)
        self._counts: dict[Room, int] = {}
        for r in self._rooms:
            self._counts[r] = self._counts.get(r, 0) + 1
        for _, _, r in self.preplaced:
            self._counts[r] = self._counts.get(r, 0) + 1
        self._unique = sorted(self._counts.keys(), key=lambda r: r.name)

    def find_solutions(
        self, time_limit: float = 60.0, max_solutions: int = 1
    ) -> Iterator[House]:
        model = cp_model.CpModel()
        K = len(self._unique)
        cells = [(x, y) for x in range(self.width) for y in range(self.height)]

        tv: dict[tuple[int, int], cp_model.IntVar] = {}
        rv: dict[tuple[int, int], cp_model.IntVar] = {}
        for x, y in cells:
            tv[x, y] = model.NewIntVar(0, K, f"t_{x}_{y}")
            rv[x, y] = model.NewIntVar(0, 3, f"r_{x}_{y}")

        self._add_preplaced(model, tv, rv)
        self._add_count_constraints(model, tv, cells)
        self._add_adjacent_constraints(model, tv, rv, K)
        self._add_edge_constraints(model, tv, rv, K)
        self._add_no_isolated(model, tv, cells)
        if self._require_connectivity:
            total = len(self._rooms) + len(self.preplaced)
            self._add_connectivity(model, tv, cells, total)

        if self._filled:
            self._add_filled_objective(model, tv, cells)
        elif self._compact or self._near_rooms:
            self._add_compactness_objective(model, tv, cells)

        all_vars: list[cp_model.IntVar] = []
        for x in range(self.width):
            for y in range(self.height):
                all_vars.append(tv[x, y])
                all_vars.append(rv[x, y])

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit

        found = 0
        while not max_solutions or found < max_solutions:
            status = solver.Solve(model)
            if status != cp_model.OPTIMAL and status != cp_model.FEASIBLE:
                break
            house = self._build_house(solver, tv, rv, cells)
            if house is not None and all(c(house) for c in self._all_checkers):
                yield house
                found += 1
            model.AddForbiddenAssignments(
                all_vars,
                [tuple(solver.Value(v) for v in all_vars)],
            )

    def _build_house(
        self,
        solver: cp_model.CpSolver,
        tv: dict[tuple[int, int], cp_model.IntVar],
        rv: dict[tuple[int, int], cp_model.IntVar],
        cells: list[tuple[int, int]],
    ) -> House | None:
        house = House(self.width, self.height)
        for x, y in cells:
            ti = solver.Value(tv[x, y])
            if ti == 0:
                continue
            room = self._unique[ti - 1]
            rot = solver.Value(rv[x, y])
            r = room if room.doors == FULL_DOOR_MASK else room.rotated(rot)
            try:
                house.place_room(x, y, r)
            except ValueError:
                return None
        return house

    def _add_no_isolated(
        self,
        model: cp_model.CpModel,
        tv: dict[tuple[int, int], cp_model.IntVar],
        cells: list[tuple[int, int]],
    ) -> None:
        for x, y in cells:
            occ = model.NewBoolVar(f"occ_{x}_{y}")
            model.Add(tv[x, y] != 0).OnlyEnforceIf(occ)
            model.Add(tv[x, y] == 0).OnlyEnforceIf(occ.Not())
            nocc: list[cp_model.IntVar] = []
            for nx, ny in _get_neighbors(x, y, self.width, self.height):
                b = model.NewBoolVar(f"n_{x}_{y}_{nx}_{ny}")
                model.Add(tv[nx, ny] != 0).OnlyEnforceIf(b)
                model.Add(tv[nx, ny] == 0).OnlyEnforceIf(b.Not())
                nocc.append(b)
            if nocc:
                model.Add(sum(nocc) >= 1).OnlyEnforceIf(occ)

    def _add_connectivity(
        self,
        model: cp_model.CpModel,
        tv: dict[tuple[int, int], cp_model.IntVar],
        cells: list[tuple[int, int]],
        total_rooms: int,
    ) -> None:
        occ: dict[tuple[int, int], cp_model.IntVar] = {}

        for x, y in cells:
            b = model.NewBoolVar(f"cocc_{x}_{y}")
            model.Add(tv[x, y] != 0).OnlyEnforceIf(b)
            model.Add(tv[x, y] == 0).OnlyEnforceIf(b.Not())
            occ[x, y] = b

        # Entrance cell (preplaced or center) is the root of connectivity
        if self.preplaced:
            ex, ey = self.preplaced[0][0], self.preplaced[0][1]
        else:
            ex, ey = cells[0]
        model.Add(occ[ex, ey] == 1)

        # BFS reachability encoding: reachable[t][c] = occ[c] AND
        #   (reachable[t-1][c] OR any neighbor reachable[t-1])
        # Layer 0: only the entrance
        T = total_rooms
        layers: list[dict[tuple[int, int], cp_model.IntVar]] = []

        r0: dict[tuple[int, int], cp_model.IntVar] = {}
        for x, y in cells:
            r = model.NewBoolVar(f"rch_0_{x}_{y}")
            if (x, y) == (ex, ey):
                model.Add(r == 1)
            else:
                model.Add(r == 0)
            r0[x, y] = r
        layers.append(r0)

        for t in range(1, T + 1):
            cur: dict[tuple[int, int], cp_model.IntVar] = {}
            for x, y in cells:
                r = model.NewBoolVar(f"rch_{t}_{x}_{y}")
                prev = layers[t - 1]

                sources: list[cp_model.IntVar] = [prev[x, y]]
                for nx, ny in _get_neighbors(x, y, self.width, self.height):
                    sources.append(prev[nx, ny])

                # r = occ AND (any source)
                # r <= occ
                model.Add(r <= occ[x, y])
                # r <= sum(sources) — if all sources 0, r must be 0
                model.Add(r <= sum(sources))
                # r >= occ + source - 1 for each source — forward propagation
                for s in sources:
                    model.Add(r >= occ[x, y] + s - 1)

                cur[x, y] = r
            layers.append(cur)

        # Every occupied cell must be reachable within T BFS steps
        final = layers[T]
        for x, y in cells:
            model.Add(final[x, y] == 1).OnlyEnforceIf(occ[x, y])

    def _add_preplaced(
        self,
        model: cp_model.CpModel,
        tv: dict[tuple[int, int], cp_model.IntVar],
        rv: dict[tuple[int, int], cp_model.IntVar],
    ) -> None:
        for x, y, room in self.preplaced:
            idx = self._type_idx(room)
            model.Add(tv[x, y] == idx)
            model.Add(rv[x, y] == 0)

    def _type_idx(self, room: Room) -> int:
        for i, r in enumerate(self._unique, start=1):
            if r == room:
                return i
        return 0

    def _add_count_constraints(
        self,
        model: cp_model.CpModel,
        tv: dict[tuple[int, int], cp_model.IntVar],
        cells: list[tuple[int, int]],
    ) -> None:
        for i, room in enumerate(self._unique, start=1):
            total = self._counts[room]
            flags: list[cp_model.IntVar] = []
            for x, y in cells:
                b = model.NewBoolVar(f"cnt_{room.name}_{x}_{y}")
                model.Add(tv[x, y] == i).OnlyEnforceIf(b)
                model.Add(tv[x, y] != i).OnlyEnforceIf(b.Not())
                flags.append(b)
            model.Add(sum(flags) == total)

    def _add_adjacent_constraints(
        self,
        model: cp_model.CpModel,
        tv: dict[tuple[int, int], cp_model.IntVar],
        rv: dict[tuple[int, int], cp_model.IntVar],
        K: int,
    ) -> None:
        for x in range(self.width):
            for y in range(self.height):
                if x + 1 < self.width:
                    self._forbid_pairs(
                        model,
                        tv[x, y],
                        rv[x, y],
                        tv[x + 1, y],
                        rv[x + 1, y],
                        K,
                        Direction.E,
                        Direction.W,
                    )
                if y + 1 < self.height:
                    self._forbid_pairs(
                        model,
                        tv[x, y],
                        rv[x, y],
                        tv[x, y + 1],
                        rv[x, y + 1],
                        K,
                        Direction.S,
                        Direction.N,
                    )

    def _forbid_pairs(
        self,
        model: cp_model.CpModel,
        t1: cp_model.IntVar,
        r1: cp_model.IntVar,
        t2: cp_model.IntVar,
        r2: cp_model.IntVar,
        K: int,
        d1: Direction,
        d2: Direction,
    ) -> None:
        bad: list[tuple[int, ...]] = []
        for ti in range(K + 1):
            for ri in range(4):
                h1 = self._has_door(ti, ri, d1)
                for tj in range(K + 1):
                    for rj in range(4):
                        if self._conflict(ti, ri, tj, rj, h1, d2):
                            bad.append((ti, ri, tj, rj))
        if bad:
            model.AddForbiddenAssignments([t1, r1, t2, r2], bad)

    def _add_edge_constraints(
        self,
        model: cp_model.CpModel,
        tv: dict[tuple[int, int], cp_model.IntVar],
        rv: dict[tuple[int, int], cp_model.IntVar],
        K: int,
    ) -> None:
        if not self._check_exposed:
            return
        for y in range(self.height):
            self._forbid_cell_edge(model, tv, rv, 0, y, Direction.W, K)
            self._forbid_cell_edge(model, tv, rv, self.width - 1, y, Direction.E, K)
        for x in range(self.width):
            self._forbid_cell_edge(model, tv, rv, x, 0, Direction.N, K)
            self._forbid_cell_edge(model, tv, rv, x, self.height - 1, Direction.S, K)

    def _forbid_cell_edge(
        self,
        model: cp_model.CpModel,
        tv: dict[tuple[int, int], cp_model.IntVar],
        rv: dict[tuple[int, int], cp_model.IntVar],
        x: int,
        y: int,
        d: Direction,
        K: int,
    ) -> None:
        bad: list[tuple[int, int]] = []
        for ti in range(1, K + 1):
            if self._allow_exposed(ti):
                continue
            for ri in range(4):
                if self._has_door(ti, ri, d):
                    bad.append((ti, ri))
        if bad:
            model.AddForbiddenAssignments([tv[x, y], rv[x, y]], bad)

    def _add_compactness_objective(
        self,
        model: cp_model.CpModel,
        tv: dict[tuple[int, int], cp_model.IntVar],
        cells: list[tuple[int, int]],
    ) -> None:
        if self._entrance:
            ex, ey = self._entrance
        elif self.preplaced:
            ex, ey = self.preplaced[0][0], self.preplaced[0][1]
        else:
            ex, ey = cells[0]

        # Map near-entrance room names to type indices
        near_types: dict[int, str] = {}
        for i, room in enumerate(self._unique, start=1):
            if room.name in self._near_rooms:
                near_types[i] = room.name

        terms: list[cp_model.LinearExpr] = []
        for x, y in cells:
            dist = abs(x - ex) + abs(y - ey)
            b = model.NewBoolVar(f"cobj_{x}_{y}")
            model.Add(tv[x, y] != 0).OnlyEnforceIf(b)
            model.Add(tv[x, y] == 0).OnlyEnforceIf(b.Not())
            terms.append(b * dist)

            # Extra weight for near-entrance room types
            for ti in near_types:
                nb = model.NewBoolVar(f"near_{near_types[ti]}_{x}_{y}")
                model.Add(tv[x, y] == ti).OnlyEnforceIf(nb)
                model.Add(tv[x, y] != ti).OnlyEnforceIf(nb.Not())
                terms.append(nb * dist * 5)

        model.Minimize(sum(terms))

    def _add_filled_objective(
        self,
        model: cp_model.CpModel,
        tv: dict[tuple[int, int], cp_model.IntVar],
        cells: list[tuple[int, int]],
    ) -> None:
        occ: dict[tuple[int, int], cp_model.IntVar] = {}
        for x, y in cells:
            b = model.NewBoolVar(f"focc_{x}_{y}")
            model.Add(tv[x, y] != 0).OnlyEnforceIf(b)
            model.Add(tv[x, y] == 0).OnlyEnforceIf(b.Not())
            occ[x, y] = b
        terms: list[cp_model.LinearExpr] = []
        for x, y in cells:
            for nx, ny in _get_neighbors(x, y, self.width, self.height):
                if (x, y) < (nx, ny):
                    b = model.NewBoolVar(f"fadj_{x}_{y}_{nx}_{ny}")
                    model.Add(b <= occ[x, y])
                    model.Add(b <= occ[nx, ny])
                    model.Add(b >= occ[x, y] + occ[nx, ny] - 1)
                    terms.append(-b)
        if self._near_rooms and self._entrance:
            ex, ey = self._entrance
            near_types = {
                i: r.name
                for i, r in enumerate(self._unique, start=1)
                if r.name in self._near_rooms
            }
            for x, y in cells:
                dist = abs(x - ex) + abs(y - ey)
                for ti in near_types:
                    nb = model.NewBoolVar(f"fnear_{near_types[ti]}_{x}_{y}")
                    model.Add(tv[x, y] == ti).OnlyEnforceIf(nb)
                    model.Add(tv[x, y] != ti).OnlyEnforceIf(nb.Not())
                    terms.append(nb * dist * 5)
        model.Minimize(sum(terms))

    def _has_door(self, type_idx: int, rot: int, d: Direction) -> bool:
        if type_idx == 0:
            return False
        room = self._unique[type_idx - 1]
        if room.doors == FULL_DOOR_MASK:
            return True
        idx = DIRECTION_ORDER.index(d)
        mask = int(room.doors)
        rotated = ((mask >> (4 - rot)) | (mask << rot)) & 0xF
        return bool(rotated & (1 << idx))

    def _allow_exposed(self, type_idx: int) -> bool:
        if type_idx == 0:
            return True
        return self._unique[type_idx - 1].allow_exposed_doors

    def _conflict(
        self,
        ti: int,
        ri: int,
        tj: int,
        rj: int,
        h1: bool,
        d2: Direction,
    ) -> bool:
        if ti != 0 and tj != 0:
            h2 = self._has_door(tj, rj, d2)
            return h1 != h2
        if not self._check_exposed:
            return False
        if ti != 0 and h1 and not self._allow_exposed(ti):
            return True
        if tj != 0:
            h2 = self._has_door(tj, rj, d2)
            if h2 and not self._allow_exposed(tj):
                return True
        return False
