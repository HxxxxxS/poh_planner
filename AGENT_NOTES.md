# Optimizations Completed

1. **Dynamic boundary set** (replaces static fill_positions):
   - Only explores cells adjacent to placed rooms (flood-fill from garden)
   - Boundary sorted by adjacency count (most-connected cells first)
   - Automatically prunes when boundary empties before all rooms placed

2. **Short-circuit on all rooms placed**:
   - Once all rooms are placed, immediately check final constraints and yield
   - Avoids iterating through remaining empty cells

3. **Incremental exposed door check**:
   - When a boundary cell is left permanently empty, checks if adjacent rooms have doors facing it
   - If so, prunes immediately instead of waiting for final constraint

4. **`--max-solutions` CLI flag**:
   - Stops enumeration after N solutions (default 0 = all)
   - Prevents hanging on large solution spaces

5. **Heuristic room ordering**:
   - `unique_rooms` sorted by `rotation_variant_count` ascending (`search.py:86`)
   - NESW rooms (1 variant) tried first, then 2-door, then constrained
   - Fewer rotation attempts per placement, faster partial layout accumulation

6. **Boundary capacity check** (`search.py:249`):
   - Before the empty branch, checks `remaining_rooms <= len(boundary)`
   - Prunes when remaining rooms can't physically fit in the remaining cells
   - Catches deep empty chains that would iterate many cells before failing

7. **OR-Tools CP-SAT solver** (`sat_search.py`):
   - Third search method: `--method sat` with `--time-limit SECONDS` (default 60)
   - Encodes rooms as per-cell type + rotation variables with BoolVar constraints
   - BFS reachability connectivity (linear BoolVars, fast) replaces slow IntVar distance encoding
   - Edge constraints forbid outward-facing doors on grid boundaries
   - 21-room NoExposedDoors config: **100 solutions in ~68s** (12 types, 7×7 grid)
   - See `sat_search.py` for encoding details

8. **`--near-entrance` active bias**:
   - All three solvers now receive entrance position and actively bias placement
   - Backtracking: boundary cells closer to entrance are tried first; near rooms come first in room iteration
   - SAT: distance-from-entrance weighted ×5 in minimization objective
   - Local: near rooms placed first in `_init_compact`; distance added to repair cost
   - Was previously only a post-hoc sort

9. **`--goal filled` shape optimization**:
   - New goal type that maximizes internal adjacencies between rooms
   - Backtracking: same boundary heuristic as `compact` (cells with more neighbors first)
   - SAT: BoolVar per adjacent cell pair for "both occupied", `Maximize(sum)`
   - Local: picks most-connected boundary cell in `_init_compact`; tracks best-by-adjacency in `_repair`
   - Post-hoc sort subtracts adjacency count so more-filled layouts sort first
   - Effectively penalizes 1-room-wide branches and thin corridors

10. **Output rendering improvements** (`render.py`, `main.py`):
    - **Entrance marker**: Garden tiles use double-line box-drawing chars (╔═╗/╚═╝/║)
    - **Coordinate axes**: Row numbers on left, column numbers in header
    - **Summary line per solution**: `Solution N (W×H, adj: N, near-dist: N)`
    - **Progress indicator**: `\rFound N solutions...` to stderr during search
    - **`--verbose` / `-v`**: Summary table of all solutions + extended stats footer
    - **`--json`**: Machine-readable JSON output with rooms, positions, doors, metrics
    - **`--side-by-side [N]`**: Multiple layouts printed horizontally (optional column count)
    - Metrics helpers: `layout_dims`, `adjacency_count`, `near_entrance_dist`
    - `adjacency_count` fixed to return single-counted edges (÷2)

11. **Family-based room clustering** (`rooms.json`, `model.py`, `main.py`, `search.py`, `sat_search.py`, `local_search.py`):
    - Rooms can belong to named families with configurable weight/strength
    - Families are defined in `rooms.json` (e.g., garden weight=10, portal weight=8, dungeon weight=6, hall weight=5, teleport weight=3)
    - CLI `--group NAME:weight=W` overrides weight, `--group NAME:exclude=Room` removes members, `--group NAME:W=Room1,Room2` creates ad-hoc families
    - Backtracking: `_boundary_key` sorts cells adjacent to active-family members first; room ordering prioritizes incomplete families
    - SAT: `_add_family_terms` creates BoolVars per family per adjacent pair, weighted by family weight in the objective
    - Local: `_init_compact` places family rooms consecutively; `_family_cost` adds proximity penalty to repair loop
    - Rooms can belong to multiple families (e.g., Portal chamber is both portal and teleport)
    - Families with <2 total members are skipped (no clustering possible)
    - Merge resolution: `rooms.json` defaults → CLI overrides stack on top

12. **Fixed pre-existing bug**: `product(*[[]])` evaluates to `product([])` which yields zero iterations, causing the `else` branch in `main()` (backtracking/local solvers without pinned rooms) to never execute. Fixed by using `configs: list[tuple] = [()]` as the default rotation set when no pinned rooms exist.

# Future Ideas

## ~~ 1. Symmetry breaking for identical rooms ~~

**Considered and rejected** — analysis shows zero benefit for the backtracking solver.

The idea: enforce that K copies of the same room type are placed in
strictly increasing cell coordinates to avoid redundant subset exploration.

**Why it doesn't help**: the count-based `room_counts` dict (already in place)
eliminates K! permutation symmetry, reducing P(N,K) to C(N,K). The sorted
boundary + deterministic cell visitation already ensures each cell subset
is visited at most once. Each occupancy map uniquely determines the search
path to reach it — the boundary is a pure function of the occupancy map
(`_calc_boundary`), so two different paths can't arrive at the same map.

For the SAT solver, symmetry breaking constraints are a standard technique
but wouldn't justify the encoding complexity — the solver already finds
100 solutions in ~68s for the hardest tested config.

## 1. Memoization of explored states

Store `(placed_cells_signature, remaining_counts)` in a set at the top of
`_backtrack`. If the same combination is re-entered through a different
search path, skip.

Key design:

```python
def _state_key(self) -> tuple:
    placed = frozenset(
        (x, y, room.name, int(room.doors))
        for (x, y), room in self.house.iter_rooms()
    )
    remaining = tuple(
        (room.name, self.room_counts[room]) for room in self.unique_rooms
    )
    return (placed, remaining)
```

**Caveat**: with the dynamic boundary set, the cell visit order is
deterministic (sorted by adjacency count). Two paths that arrive at the
same `(placed_rooms, remaining_counts)` must have made identical
empty-cell decisions, which is unlikely in practice. Hit rate may be low.

Alternative target: cache `matches_partial()` results keyed by
`(placed_sig, remaining)`. Since `matches_partial` is called at every
node and iterates all rooms, even a modest cache hit rate would save
time. Requires a lightweight signature — avoid the full
`canonical_layout_signature` at intermediate nodes since it normalizes
rotations (which is wasteful for cache lookups that could use a simpler
positional key).

Likely not worth implementing unless profiling shows redundant calls.
