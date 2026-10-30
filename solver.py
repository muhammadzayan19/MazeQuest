"""Key-aware BFS shortest path and genuine recursive DFS demonstration."""
# =============================================================================
# WHAT THIS FILE IS
# -----------------------------------------------------------------------------
# Path-finding. Given the maze, it answers "what is a route from here to the
# exit?". Two classic algorithms are provided:
#
#   BFS (breadth-first search)  - explores outward like ripples in a pond, one
#       step at a time. The FIRST time it reaches the goal it has used the
#       fewest possible steps, so it returns the SHORTEST route. The game uses it
#       for hints, the "optimal route" overlay and the results ranking.
#   DFS (depth-first search)    - follows one corridor as far as it can, and only
#       backs up ("backtracks") when it hits a dead end. It finds A route, not
#       necessarily the shortest. It is included to demonstrate the algorithm.
#
# "Key-aware" means the search remembers which keys it has collected, because a
# locked gate is only passable once its key has been picked up. So the thing the
# search tracks is not just WHERE it is, but WHERE it is plus WHICH KEYS it has.
# =============================================================================

# Lets type hints refer to names defined later in the file.
from __future__ import annotations

# Only for describing types to readers/editors; no effect when the game runs.
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

# Maze is the level map; Position is "a (row, column) pair".
from maze import Maze, Position

# A search "state" = (where we are, the keys we hold). A frozenset is a set that
# cannot change, which means it can be used inside a tuple that is itself used as
# a dictionary key or stored in another set (regular sets cannot).
State = Tuple[Position, FrozenSet[str]]


def _next_state(maze: Maze, position: Position, keys: FrozenSet[str]):
    """Generate every state reachable in ONE step from (position, keys)."""
    # maze.neighbours gives the up/down/left/right tiles we are allowed to enter
    # (not walls, and not gates we lack the key for).
    for nxt in maze.neighbours(position, keys):
        # Is there a key lying on the tile we step onto? (None if not.)
        found = maze.keys.get(nxt)
        # `yield` hands back one result at a time instead of building a whole list.
        # New keys = the old keys plus the key found here (if any), as a frozenset.
        yield nxt, frozenset(set(keys) | ({found} if found else set()))


def solve_bfs(maze: Maze, start: Optional[Position] = None, goal: Optional[Position] = None,
              initial_keys=()) -> List[Position]:
    """Return the shortest list of tiles from start to goal, or [] if impossible."""
    # Use the maze's own start/goal unless the caller supplied different ones
    # (hints start from where the hero currently stands).
    start = maze.start if start is None else start
    goal = maze.goal if goal is None else goal
    # The starting state: our start tile plus any keys already held, plus a key
    # lying on the start tile itself (if there is one).
    initial = (start, frozenset(initial_keys) | ({maze.keys[start]} if start in maze.keys else set()))
    # The queue of states still to explore. A normal list is enough because the
    # `for` loop below keeps reading items appended while it runs.
    queue = [initial]
    # For every state we reach, remember which state we came from. This lets us
    # rebuild the route afterwards, and doubles as the "already seen" record.
    # The starting state has no parent (None).
    parents: Dict[State, Optional[State]] = {initial: None}
    # Process states in the order they were discovered (first in, first out).
    for state in queue:
        position, keys = state
        # Reached the goal: because BFS expands by distance, this is the shortest way.
        if position == goal:
            return _reconstruct(parents, state)
        # Look at every state one step away.
        for nxt, new_keys in _next_state(maze, position, keys):
            candidate = (nxt, new_keys)
            # Only explore a state the first time we see it; this stops endless loops.
            if candidate not in parents:
                # Remember how we got here, and schedule it for exploring.
                parents[candidate] = state
                queue.append(candidate)
    # The queue ran dry without ever reaching the goal: there is no route.
    return []


def solve_dfs(maze: Maze, start: Optional[Position] = None, goal: Optional[Position] = None,
              initial_keys=()) -> List[Position]:
    """Recursive depth-first search with explicit path backtracking."""
    # Default to the maze's own start and goal, as in solve_bfs.
    start = maze.start if start is None else start
    goal = maze.goal if goal is None else goal
    # States already tried, so we never repeat the same (tile, keys) combination.
    visited: Set[State] = set()
    # The route being built right now. Tiles are added while going forward and
    # removed again when backing out of a dead end (backtracking).
    path: List[Position] = []
    # Keys held at the start, plus a key lying on the start tile if present.
    initial = frozenset(initial_keys) | ({maze.keys[start]} if start in maze.keys else set())

    # A function defined inside another function can use the outer variables
    # (maze, goal, visited, path). "Recursive" means visit() calls itself.
    def visit(position: Position, keys: FrozenSet[str]) -> bool:
        state = (position, keys)
        # Already explored this exact state: give up on this branch.
        if state in visited:
            return False
        # Mark it explored and add the tile to the current path.
        visited.add(state)
        path.append(position)
        # Found the goal: tell every caller up the chain to stop searching.
        if position == goal:
            return True
        # Try each neighbouring state in turn, going deeper before trying the next.
        for nxt, new_keys in _next_state(maze, position, keys):
            if visit(nxt, new_keys):
                return True
        # Every option from here was a dead end: undo this tile and report failure
        # so the caller tries a different direction.
        path.pop()
        return False

    # Start the search; if it succeeded, `path` holds the route, otherwise [].
    return path if visit(start, frozenset(initial)) else []


def _reconstruct(parents, state):
    """Walk backwards through the `parents` record to list the route start -> goal."""
    route = []
    # Follow the parent links from the goal state back to the start (whose parent is None).
    while state is not None:
        route.append(state[0])
        state = parents[state]
    # We collected the tiles goal-first, so flip the list around.
    return list(reversed(route))


class MazeSolver:
    """A tiny namespace that exposes the two functions as MazeSolver.bfs / MazeSolver.dfs."""

    # staticmethod = a plain function stored on a class (it gets no `self`).
    bfs = staticmethod(solve_bfs)
    dfs = staticmethod(solve_dfs)
