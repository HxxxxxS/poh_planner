# POH Planner

A constraint-based backtracking solver that generates valid Player-Owned House layouts for Old School RuneScape.

Specify room types and counts, and the solver finds all valid arrangements that satisfy door matching, connectivity, and no-exposed-doors constraints.

---

## Usage

List available room types:

```
python main.py --list-rooms
```

Basic layout with 4 portal chambers:

```
python main.py --room Portal=4
```

Mix different room types:

```
python main.py --room Parlour --room Kitchen --room Portal=2 --room SkillHall=1
```

Stop after finding a few solutions:

```
python main.py --room Portal=8 --max-solutions 3
```

Permit doors to face empty tiles (disables the no-exposed-doors rule):

```
python main.py --room Portal=4 --allow-exposed
```

---

## Rooms

25 room types are defined in `rooms.json`, each with:

- Door directions (N/E/S/W)
- Friendly name and aliases
- A legend symbol for display

Rooms are referenced by name or alias:

```
python main.py --room Portal --room QuestHall --room Achievement
```

Each door configuration is a bitmask (N=1, E=2, S=4, W=8). Rooms are rotatable during placement.

---

## Constraints

**Door Matching** — Adjacent rooms must have matching doors in the shared direction.

**Connectivity** — All rooms must form a single connected component.

**No Exposed Doors** — Doors must not face empty tiles (disable with `--allow-exposed`). Rooms can opt out via `allow_exposed_doors` flag (e.g., the Garden entrance).

---

## Architecture

- `model.py` — `Direction` (IntFlag), `Room`, `House` grid
- `constraints.py` — Modular constraint callables
- `search.py` — Backtracking solver with dynamic boundary set
- `render.py` — ASCII box-drawing layout output
- `main.py` — CLI entry point

The solver uses a flood-fill boundary approach: only cells adjacent to placed rooms are candidate positions, and the empty branch prunes when leaving a cell empty would expose a door.

---

## Tests

```
python -m pytest tests/
```

Requires Python 3.11+.
