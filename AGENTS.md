# Role

You are a constraint-solving engineer building a grid-based layout generator for OSRS Player-Owned Houses.

Focus on correctness, clarity, and deterministic behavior.
Problem Model

    House = 2D grid

    Each cell = optional room

    Rooms have doors on: N/E/S/W

N, E, S, W = 1, 2, 4, 8

# Constraints

# Constraints are modular and toggleable.

## Core Rules

    Door Matching

        Adjacent rooms must have matching doors

    No Overlap

        One room per tile

    Connectivity

        All rooms must be reachable

## Optional Rule (default: enabled)

### No Exposed Doors

    Doors must not face empty space

    Can be disabled via config/CLI flag

# Approach

## Use backtracking search:

    Place rooms incrementally

    Validate constraints after each step

    Prune invalid partial layouts early

## Keep iteration deterministic.

# Tech

    Python 3.11+

    Standard library preferred

# Structure

model.py
constraints.py
search.py
render.py
main.py

# Guidelines

## Always

    Enforce constraints through functions (not inline logic)

    Keep solver independent of specific constraints

    Pass --quiet when running main.py from an automated agent to suppress the progress indicator spinner (each tick prints to stderr and fills context windows with noise). Only omit for interactive debugging of the indicator itself.

## Never

    Hardcode constraint assumptions in search logic

    Introduce randomness in core solver

    Push to remote — user handles that manually

# Goal

Generate valid layouts under a configurable set of constraints.
