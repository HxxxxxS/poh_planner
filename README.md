# POH Planner

Constraint-based OSRS house layout generator

---

## Set up

Needs Python 3.11+. OR-Tools is required for the SAT solver.

```
python main.py --help
```

---

## Get started

Four portal chambers, minimal flags:

```
python main.py --room Portal=4
```

Mix different types:

```
python main.py --room Parlour --room Kitchen --room Portal=2
```

Stop after finding a few solutions:

```
python main.py --room Portal=8 --max-solutions 3
```

---

## Pick rooms

25 types are available. List them with descriptions:

```
python main.py --list-rooms
```

Each defines door directions (N/E/S/W), a display symbol, and aliases. Rooms are rotatable during placement.

Specify counts with `--room Name=N` or `--room Name` for one. The garden is always placed at the center.

---

## Choose a solver

Three methods are available via `--method`:

`backtracking` — incremental placement with early pruning. Best for small layouts.

`local` — iterative repair from random starts. Good for medium configs.

`sat` — OR-Tools CP-SAT encoding. Fastest for large or complex layouts. Set a time limit with `--time-limit SECONDS` (default 60s).

```
python main.py --room Portal=5 --room Nexus --room Gallery --method sat
```

---

## Shape the layout

By default any valid arrangement is accepted. Two optimization goals refine the shape:

`--goal compact` — minimize bounding-box area.

`--goal filled` — maximize internal adjacencies. Penalizes branches and thin corridors.

```
python main.py --room Portal=5 --room Kitchen --goal filled
```

---

## Group rooms

Guide certain rooms toward the entrance:

```
python main.py --room Portal=3 --room Kitchen --near-entrance Portal
```

All three solvers use this bias during search, not just as a post-filter.

Rooms also belong to families defined in `rooms.json`. Family members cluster together by default. Override with `--group`:

```
--group garden:weight=15
--group dungeon:exclude=TreasureRoom
--group myfam:5=Kitchen,Bedroom
```

---

## Read the output

Solutions render with ASCII box-drawing characters. The entrance tile uses double-line borders (`╔═╗`). Coordinate axes appear in verbose mode.

Multiple solutions display side by side automatically. Control columns with `--cols`:

```
python main.py --room Portal=4 --max-solutions 10 --cols 2
```

Verbose mode adds grid labels, empty markers, and a summary table:

```
python main.py --room Portal=4 --verbose
```

JSON output for scripting:

```
python main.py --room Portal=4 --json
```

---

## Troubleshoot

"No layout satisfies the constraints" usually means the strict door-facing rule makes your room mix impossible. Every door must face another room, so single-door rooms can only be leaf nodes.

The solver prints a door-type breakdown when this happens. The easiest fix:

```
python main.py --room Portal=4 --allow-exposed
```

This relaxes the rule but still enforces door matching and connectivity.

---

## Test

```
python -m pytest tests/
```
