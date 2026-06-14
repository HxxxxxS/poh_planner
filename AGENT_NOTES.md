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

1. Cache `matches_partial` results based on the current partial layout signature so repeated states are checked faster.
2. Store partial layout signatures with remaining room counts to skip equivalent states without exploring them again.
