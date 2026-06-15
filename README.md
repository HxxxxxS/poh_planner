# POH Planner

A constraint-based backtracking solver that generates valid Player-Owned House layouts for Old School RuneScape.

Specify room types and counts, and the solver finds all valid arrangements that satisfy door matching, connectivity, and no-exposed-doors constraints.

---

## Example output:

```
$ source .venv/bin/activate && python main.py --method sat --max-solutions 1 --goal filled \
--pin-room 1,0=Garden --pin-room -1,0=Garden --pin-room 0,1=Garden --pin-room 0,-1=Garden \
--room Portal=5 --room Nexus --room Gallery --room Costume --room Chapel --room Dining \
--room Kitchen --room Skill --room Bedroom=2 --room Study --room Workshop \
--near-entrance Nexus --near-entrance Gallery;

Solution 1:
   ┌─┐┌─┐
   │O││P│
   └ ┘└ ┘
┌─┐┌ ┐┌ ┐┌─┐
│K  N  G  B│
└ ┘└ ┘└ ┘└ ┘
┌ ┐┌ ┐┌ ┐┌ ┐┌─┐┌─┐
│D  G  G  G  A  P│
└ ┘└ ┘└ ┘└ ┘└─┘└─┘
┌ ┐┌ ┐┌ ┐┌ ┐┌─┐
│W││Y  G  H  P│
└ ┘└ ┘└ ┘└ ┘└─┘
┌ ┐┌ ┐┌ ┐┌ ┐
│P││C  B││P│
└─┘└─┘└─┘└─┘

A = Achievement gallery
B = Bedroom
C = Chapel
D = Dining room
G = Garden
H = Hall (skill trophies)
K = Kitchen
N = Portal nexus
O = Costume room
P = Portal chamber
W = Workshop
Y = Study

Elapsed: 0.78s
```

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

Use the SAT solver for large configs (much faster for complex layouts):

```
python main.py --room Portal=5 --room Nexus --room Gallery --method sat
```

Set a time limit for the SAT solver (default 60s):

```
python main.py --room Portal=8 --method sat --time-limit 120
```

Permit doors to face empty tiles (disables the no-exposed-doors rule):

```
python main.py --room Portal=4 --allow-exposed
```

Prefer certain rooms near the entrance (repeatable):

```
python main.py --room Portal=3 --room Kitchen --room Parlour --near-entrance Portal --near-entrance Kitchen
```

The solver biases placement of specified rooms toward the entrance tile (center by default). All three solvers use this during search, not just as a post-filter.

Optimize layout shape:

```
python main.py --room Portal=5 --room Kitchen --goal filled
```

`--goal compact` minimizes bounding-box area; `--goal filled` maximizes internal adjacencies (penalizes branches and thin corridors).

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

**No Exposed Doors** — Doors must not face empty tiles or the grid boundary (disable with `--allow-exposed`). All rooms are subject to this rule — no exemptions.

---

## Architecture

- `model.py` — `Direction` (IntFlag), `Room`, `House` grid
- `constraints.py` — Modular constraint callables
- `search.py` — Backtracking solver with dynamic boundary set
- `local_search.py` — Iterative repair / local search solver
- `sat_search.py` — OR-Tools CP-SAT solver (fastest for large configs)
- `render.py` — ASCII box-drawing layout output
- `main.py` — CLI entry point

The solver uses a flood-fill boundary approach: only cells adjacent to placed rooms are candidate positions, and the empty branch prunes when leaving a cell empty would expose a door.

The `--near-entrance` flag biases search toward placing specified rooms close to the entrance: the backtracking solver prioritizes closer boundary cells and tries near rooms first, the SAT solver weights their distance in its objective, and the local solver places them first during initialization and adds a distance term to its repair cost.

The `--goal compact` and `--goal filled` flags optimize layout shape. `compact` minimizes the bounding-box area; `filled` maximizes internal adjacencies between rooms, pushing the solver toward solid shapes that avoid 1-room-wide branches.

---

## CLI Reference

Generated via `python main.py --help`:

```
usage: main.py [-h] [--width WIDTH] [--height HEIGHT]
               [--construction-level CONSTRUCTION_LEVEL] [--allow-exposed]
               [--room ROOM] [--pin-room PIN_ROOM] [--entrance ENTRANCE]
               [--list-rooms] [--max-solutions MAX_SOLUTIONS]
               [--method {backtracking,local,sat}] [--time-limit TIME_LIMIT]
               [--goal {none,compact,filled}] [--near-entrance NEAR_ENTRANCE]

Generate POH layouts with constraint checking.

options:
  -h, --help            show this help message and exit
  --width WIDTH         House width in tiles.
  --height HEIGHT       House height in tiles.
  --construction-level CONSTRUCTION_LEVEL
                        Construction level to determine max house dimensions
                        and allowed rooms.
  --allow-exposed       Permit doors to face empty tiles (disables the no-
                        exposed-doors rule).
  --room ROOM           Add a room type and optional count (NAME or
                        NAME=COUNT).
  --pin-room PIN_ROOM   Force a room type at a coordinate relative to center
                        (X,Y=NAME).
  --entrance ENTRANCE   Override the entrance coordinate relative to center
                        (X,Y).
  --list-rooms          Print usage and list available room types, then exit.
  --max-solutions MAX_SOLUTIONS
                        Stop after finding N solutions (0 = find all; SAT
                        method defaults to 1).
  --method {backtracking,local,sat}
                        Search algorithm to use (default: backtracking).
  --time-limit TIME_LIMIT
                        Time limit in seconds for SAT solver (default: 60.0).
  --goal {none,compact,filled}
                        Optimization goal (default: none). 'compact' biases
                        toward tightly packed layouts. 'filled' penalizes
                        branches and thin corridors.
  --near-entrance NEAR_ENTRANCE
                        Guide search to place this room type close to the
                        entrance (repeatable).
```

---

## Tests

```
python -m pytest tests/
```

Requires Python 3.11+.
