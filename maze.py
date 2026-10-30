"""Handcrafted catacomb level and its nested-list logical tile map."""
# =============================================================================
# WHAT THIS FILE IS
# -----------------------------------------------------------------------------
# The level itself. The dungeon is stored as a "grid": a list of rows, where each
# row is a list of single-character tiles, so grid[row][column] is one tile.
#
#   '#'  wall                  '.'  floor
#   'S'  hero start            'E'  exit (the relic)
#   'K'  key                   'D'  locked gate (door)
#   'T'  treasure chest
#
# Positions everywhere in the game are (row, column) pairs. Row 0 is the TOP of
# the map and column 0 is the LEFT, so moving DOWN increases the row number.
#
# This file also answers simple questions about the map: "is this tile inside
# the map?", "can the hero walk here?", "which neighbouring tiles are open?".
# =============================================================================

# Lets type hints refer to names defined later in the file.
from __future__ import annotations

# dataclass auto-generates __init__ etc. for classes that mostly hold data;
# field() customises how one attribute gets its starting value.
from dataclasses import dataclass, field

# Only used to describe types to readers/editors; no effect when the game runs.
from typing import Dict, Iterable, List, Optional, Set, Tuple

# A tile position: (row, column).
Position = Tuple[int, int]


# frozen=True makes Level read-only after creation (its values cannot be changed
# by accident). It is just a bundle of settings describing a level.
@dataclass(frozen=True)
class Level:
    number: int = 1
    name: str = "The Forgotten Catacombs"
    rows: int = 19
    cols: int = 29
    # Seconds allowed to finish (900 = 15 minutes).
    time_limit: int = 900
    key_count: int = 1
    seed: int = 1701
    description: str = "Recover the catacomb key and claim the ancient relic."
    treasure_count: int = 1


# The game has a single level; a tuple (an unchangeable list) holds it. The second
# name is kept for older code that used the other spelling.
LEVELS = (Level(),)
LEVEL_CONFIGS = LEVELS


@dataclass
class Maze:
    """The map plus everything placed on it (keys, gates, chests, decorations)."""

    # Size of the map in tiles.
    rows: int
    cols: int
    # Set of wall positions (a set = unordered, no duplicates, fast lookups).
    walls: Set[Position] = field(default_factory=set)
    # Where the hero begins and where the exit is.
    start: Position = (1, 1)
    goal: Position = (1, 1)
    # {position: key name} for keys lying on the floor.
    keys: Dict[Position, str] = field(default_factory=dict)
    # {position: name of the key that opens it} for locked gates.
    doors: Dict[Position, str] = field(default_factory=dict)
    # {position: gold value} for treasure chests.
    treasures: Dict[Position, int] = field(default_factory=dict)
    # The tile grid described at the top of the file (None = build one from `walls`).
    grid: Optional[List[List[str]]] = None
    # Positions of decorative things. They do not affect the rules, only how the
    # level looks: wall torches, glowing floor runes and glowing crystals.
    torches: Set[Position] = field(default_factory=set)
    runes: Set[Position] = field(default_factory=set)
    crystals: Set[Position] = field(default_factory=set)
    # The doorway tile drawn at the bottom of the entrance crypt.
    entrance: Position = (1, 1)

    def __post_init__(self):
        """Runs automatically right after the dataclass sets the fields above."""
        if self.grid is None:
            # No grid was supplied: make one that is '#' where a wall position is
            # listed and '.' (floor) everywhere else. This is a "list comprehension":
            # a compact loop that builds a list.
            self.grid = [['#' if (r, c) in self.walls else '.' for c in range(self.cols)] for r in range(self.rows)]
        else:
            # A grid was supplied: trust it for the size, and rebuild the set of wall
            # positions from it so `walls` and `grid` always agree.
            self.rows, self.cols = len(self.grid), len(self.grid[0])
            self.walls = {(r, c) for r in range(self.rows) for c in range(self.cols) if self.grid[r][c] == '#'}

    @classmethod
    def generate(cls, level: Level = LEVELS[0], rng=None) -> "Maze":
        """Return the intentional single level (rng retained for old callers)."""
        # There is only one handcrafted level, so every request returns it.
        return cls.handcrafted()

    @classmethod
    def handcrafted(cls) -> "Maze":
        """Build the one hand-designed dungeon (a classmethod: called as Maze.handcrafted())."""
        # The map is 19 rows tall and 29 columns wide.
        rows, cols = 19, 29
        # Start with solid rock everywhere; rooms and halls are then carved out of it.
        grid = [['#' for _ in range(cols)] for _ in range(rows)]

        # A helper defined inside the method so it can see (and change) `grid`.
        def room(top, left, bottom, right):
            """Carve a rectangular room: set every tile in the rectangle to floor."""
            for r in range(top, bottom + 1):
                for c in range(left, right + 1):
                    grid[r][c] = '.'

        def hall(a: Position, b: Position):
            """Carve an L-shaped corridor from a to b: vertically first, then horizontally."""
            # Unpack the two positions into row/column numbers.
            r, c = a
            er, ec = b
            # Walk the row toward the destination row, carving floor as we go.
            # (`1 if er>r else -1` steps down if the target is lower, else up.)
            while r != er:
                grid[r][c] = '.'
                r += 1 if er > r else -1
            # Then walk the column toward the destination column.
            while c != ec:
                grid[r][c] = '.'
                c += 1 if ec > c else -1
            # Carve the final tile too.
            grid[r][c] = '.'

        # Entrance crypt, western cul-de-sac, central nave and an optional reliquary.
        # Each call is room(top row, left col, bottom row, right col).
        room(13, 1, 17, 6)      # entrance crypt (where the hero starts)
        room(7, 2, 10, 8)       # western cellar
        room(3, 8, 8, 15)       # central nave
        room(2, 16, 6, 21)      # key chamber
        room(2, 23, 6, 27)      # exit room
        room(11, 10, 13, 14)    # reliquary
        # Corridors joining the rooms (each hall() goes from the first tile to the second).
        hall((15, 3), (10, 3))
        hall((8, 3), (8, 8))
        hall((7, 11), (5, 11))
        hall((5, 15), (4, 16))
        hall((4, 21), (4, 23))
        hall((8, 13), (11, 13))
        hall((13, 10), (13, 8))
        hall((13, 8), (12, 8))
        # Dead-end branches add deliberate choices without disconnecting rooms.
        hall((9, 5), (9, 2))
        hall((6, 9), (6, 7))
        hall((12, 12), (15, 12))
        hall((6, 8), (6, 6))
        hall((3, 12), (1, 12))

        # Thicken the join between nave and key chamber into a sealed partition;
        # only the marked row-four arch connects these rooms.
        # Column 16 is turned back into wall for rows 3..6, except row 4 (the opening).
        for r in range(3, 7):
            if r != 4:
                grid[r][16] = '#'

        # Fixed positions for the special tiles (row, column).
        start, goal, entrance = (15, 3), (4, 25), (17, 3)
        key, door, treasure = (3, 19), (4, 22), (12, 12)
        # Stamp the special letters into the grid.
        grid[start[0]][start[1]] = 'S'
        grid[goal[0]][goal[1]] = 'E'
        grid[key[0]][key[1]] = 'K'
        grid[door[0]][door[1]] = 'D'
        grid[treasure[0]][treasure[1]] = 'T'
        # A second small cache in the entrance chamber rewards a short detour.
        grid[16][5] = 'T'
        # Create the Maze object with everything placed on it:
        #   keys={key:'catacomb'}        the key is named "catacomb"
        #   doors={door:'catacomb'}      the gate needs that same key
        #   treasures={...}              chest -> gold value (100 and 35)
        #   torches/runes/crystals       decoration positions
        maze = cls(rows, cols, start=start, goal=goal, keys={key: 'catacomb'},
                   doors={door: 'catacomb'}, treasures={treasure: 100, (16, 5): 35}, grid=grid,
                   torches={(14, 2), (16, 2), (10, 6), (5, 10), (4, 17), (3, 25), (12, 11)},
                   runes={(8, 4), (5, 13), (4, 20), (12, 13)}, crystals={(6, 11), (4, 18), (12, 10)}, entrance=entrance)
        # Double-check the design is sane (raises an error if not), then return it.
        maze.validate()
        return maze

    def validate(self) -> bool:
        """Check the level is playable; raise ValueError with a reason if it is not."""
        # The grid must exist and every row must have exactly `cols` tiles.
        if not self.grid or len(self.grid) != self.rows or any(len(row) != self.cols for row in self.grid):
            raise ValueError("dungeon grid must be a rectangular nested list")
        # Every special position (start, goal, keys, doors, chests) must be on the map.
        # The `*` unpacks the dictionaries' keys (their positions) into this tuple.
        for p in (self.start, self.goal, *self.keys, *self.doors, *self.treasures):
            if not self.in_bounds(p):
                raise ValueError(f"dungeon item out of bounds: {p}")
        # Start and exit must be different tiles and neither may be inside a wall.
        if self.start == self.goal or self.start in self.walls or self.goal in self.walls:
            raise ValueError("entrance and exit must be distinct floor tiles")
        # Imported here (not at the top) to avoid a circular import: solver.py also
        # imports this file.
        from solver import solve_bfs
        # There must be some route from start to exit (an empty list means none).
        if not solve_bfs(self):
            raise ValueError("the catacomb exit is unreachable")
        # The level must contain at least one key, one gate and one chest.
        if not self.doors or not self.keys or not self.treasures:
            raise ValueError("the level needs a key, locked passage and treasure")
        # The shortest route (the BFS already accounts for needing the key).
        route = solve_bfs(self)
        # Take the first key and first gate from their dictionaries.
        key_pos = next(iter(self.keys))
        door_pos = next(iter(self.doors))
        # The gate must be closed to a hero with no keys, and the route must pick up
        # the key BEFORE it reaches the gate (otherwise the gate would be pointless).
        if self.walkable(door_pos, ()) or route.index(key_pos) > route.index(door_pos):
            raise ValueError("the final gate must be locked until the catacomb key is collected")
        return True

    def in_bounds(self, position: Position) -> bool:
        """True if the position lies inside the map rectangle."""
        # A chained comparison: 0 <= row < rows AND 0 <= column < cols.
        return 0 <= position[0] < self.rows and 0 <= position[1] < self.cols

    def to_grid(self) -> List[List[str]]:
        """Return a copy of the grid (each row copied so changes cannot affect the original)."""
        return [row[:] for row in self.grid]

    def walkable(self, position: Position, collected: Iterable[str] = ()) -> bool:
        """Can the hero stand on this tile, given the keys in `collected`?"""
        # Off the map, or a wall: never walkable.
        if not self.in_bounds(position) or self.grid[position[0]][position[1]] == '#':
            return False
        # If this tile is a gate, look up which key it needs (None if it is no gate).
        token = self.doors.get(position)
        # Walkable if it is not a gate, or if we hold the key that opens it.
        return token is None or token in set(collected)

    def neighbours(self, position: Position, collected: Iterable[str] = ()) -> List[Position]:
        """The tiles directly up, down, left and right that the hero may step onto."""
        # Build the four candidate tiles (up, down, left, right), then keep only
        # the ones that pass the walkable() check.
        return [p for p in ((position[0] - 1, position[1]), (position[0] + 1, position[1]),
                            (position[0], position[1] - 1), (position[0], position[1] + 1))
                if self.walkable(p, collected)]


def _reachable(maze: Maze) -> bool:
    """Helper: True if the exit can be reached (kept for older callers)."""
    # Imported here to avoid the circular import mentioned in validate().
    from solver import solve_bfs
    # bool([]) is False and bool([...tiles...]) is True.
    return bool(solve_bfs(maze))
