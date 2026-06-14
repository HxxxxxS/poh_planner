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
   - Respects `allow_exposed_doors` flag (Garden is exempt)

4. **`--max-solutions` CLI flag**:
   - Stops enumeration after N solutions (default 0 = all)
   - Prevents hanging on large solution spaces

# Future Ideas

## 1. Heuristic room ordering

Sort `unique_rooms` by `rotation_variant_count` ascending so rooms with fewer
unique door rotations are tried first at each cell. This is a succeed-first
heuristic — NESW rooms (1 variant) build a connected core fast, followed by
2-door rooms (2 variants), then constrained rooms like Portal/Costume (4 variants).

```
Garden(1), Nexus(1), SkillHall(1) → AchievementGallery(2), Workshop(2) → Portal(4), Bedroom(4) ...
```

Change in `_backtrack`:

```python
for room in sorted(self.unique_rooms, key=rotation_variant_count):
```

Simpler rooms produce fewer rotation attempts per placement and fail
door-matching less often, so valid partial layouts accumulate faster.

## 2. Boundary capacity check

Before recursing on the empty branch, compare remaining room counts against
boundary size. If `remaining_rooms > len(boundary)`, even filling every
remaining cell can't accommodate all rooms — prune immediately.

O(1) check at the top of `_backtrack`:

```python
if sum(self.room_counts.values()) > len(self.boundary):
    return
```

Note: this is a conservative check because placing rooms in boundary cells
adds ~2-3 new cells to the boundary. In practice it only triggers when the
boundary is nearly empty or room counts are large relative to the frontier.
Still, it catches deep empty chains that would otherwise iterate hundreds of
cells before failing.

## 3. Memoization of explored states

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

## 4. Symmetry breaking for identical rooms

With `room_counts = {Portal: 5}`, the search explores all C(20,5) ways
to choose which boundary cells get portals — 15,504 combinations for
portals alone. Each combination is equally valid for finding any solution.

The count-based `room_counts` dict already prevents per-copy permutation
(5! ordering of identical portal instances is not explored). But the
search still explores all K-sized subsets of boundary cells for each
room type with count K.

**Lexicographic cell ordering**: enforce that multiple copies of the
same room type must be placed in strictly increasing cell coordinates.
Track `first_cell[room_name]` and require subsequent copies to occupy
lexicographically greater `(x, y)` positions. This eliminates redundant
subset exploration without losing completeness.

**When it matters**: large counts of the same room type (e.g.,
`Portal=5`, `Bedroom=2`). For singleton types (count=1), no change.

**Practical note**: the user's 20-room, 12-type case benefits most from
this because the 7 single-door / 3-door room types each have count 1
(no symmetry gain), but `Portal=5` and `Bedroom=2` see significant
reductions. Also `Garden=4` (4 copies, 1 variant each, full door mask).

## 5. `--max-solutions` is the most impactful optimization

The CLI currently does `list(search.find_solutions())` which collects
ALL solutions before printing. For a 20-room search space where valid
layouts are found early, `--max-solutions 5` would return output in
seconds — the search stops after finding 5 solutions instead of
exhausting the tree.

This is already implemented and available. Users with large room
configs should always use it unless they explicitly need exhaustive
enumeration.
