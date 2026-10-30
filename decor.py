"""Deterministic dungeon dressing: zones, floor decals, wall decor, candles and drip points.

Pure data derived from a ``Maze`` (nothing here touches game state). Decals are flat and
walkable-looking, and wall decor only replaces wall faces, so nothing blocks a route."""
# =============================================================================
# WHAT THIS FILE IS
# -----------------------------------------------------------------------------
# It decides WHAT DECORATION goes WHERE in the dungeon (cobwebs, bones, banners,
# bookshelves, candles, ...). It only produces a list of "put thing X at tile Y";
# the actual pictures live in decor_art.py and the drawing is done by ui.py.
#
# "Deterministic" means the same maze always gets exactly the same decoration.
# That is done by feeding a random number generator a FIXED starting number (a
# "seed") that depends on the tile's position, so the dungeon looks identical on
# every run instead of reshuffling each time.
#
# Decoration never changes how the game plays: floor decals are flat pictures
# you can walk over, and wall decor only replaces the look of wall faces.
# =============================================================================

# Lets type hints refer to names defined later in the file.
from __future__ import annotations

# Python's random number module (we create seeded generators from it).
import random

# dataclass auto-writes __init__ etc.; field() customises a default value.
from dataclasses import dataclass, field

# Only used to describe types to readers/editors; no effect when the game runs.
from typing import Dict, List, Set, Tuple

# The level map class (we only read from it here).
from maze import Maze

# A tile position: (row, column).
Position = Tuple[int, int]

# (name, (top, left, bottom, right)) of the handcrafted rooms in Maze.handcrafted()
# Each room gets its own "zone" name, which selects its colours and decoration.
ROOM_ZONES: List[Tuple[str, Tuple[int, int, int, int]]] = [
    ("crypt", (13, 1, 17, 6)),
    ("cellar", (7, 2, 10, 8)),
    ("nave", (3, 8, 8, 15)),
    ("keyroom", (2, 16, 6, 21)),
    ("sanctum", (2, 23, 6, 27)),
    ("reliquary", (11, 10, 13, 14)),
]
# Zone name -> the row that gets a carpet laid along it.
CARPET_ROW = {"nave": 5}          # a worn runner down the middle of the nave

# probability per eligible edge cell, by zone
# Example: in the "crypt", each eligible floor tile has a 10% chance of bones,
# 7% rubble and 4% blood (the remaining 79% stay plain).
FLOOR_WEIGHTS: Dict[str, Dict[str, float]] = {
    "crypt": {"bones": 0.10, "rubble": 0.07, "blood": 0.04},
    "cellar": {"puddle": 0.14, "moss": 0.16, "rubble": 0.06, "bones": 0.05},
    "nave": {"rubble": 0.06, "bones": 0.03},
    "keyroom": {"bones": 0.16, "blood": 0.08, "rubble": 0.06, "puddle": 0.05},
    "sanctum": {"coins": 0.10, "rubble": 0.03},
    "reliquary": {"coins": 0.08, "rubble": 0.03},
    "hall": {"rubble": 0.06, "bones": 0.03, "moss": 0.04, "puddle": 0.03},
}
# probability per eligible wall face, by zone (checked in order; spacing is enforced)
WALL_WEIGHTS: Dict[str, List[Tuple[str, float]]] = {
    "crypt": [("banner", 0.20), ("skull_niche", 0.20), ("chains", 0.14), ("window", 0.10), ("damaged", 0.14)],
    "cellar": [("chains", 0.20), ("skull_niche", 0.18), ("damaged", 0.20)],
    "nave": [("column", 0.34), ("banner", 0.30), ("window", 0.10)],
    "keyroom": [("skull_niche", 0.26), ("chains", 0.22), ("damaged", 0.22), ("window", 0.08)],
    "sanctum": [("column", 0.36), ("banner", 0.30)],
    "reliquary": [("bookshelf", 0.85)],
    "hall": [("damaged", 0.18), ("chains", 0.08), ("window", 0.06)],
}
# Zones where water drips from the ceiling.
DRIP_ZONES = {"cellar", "keyroom", "crypt"}


@dataclass
class Decor:
    """The finished decoration plan for one maze (just lists/dicts of positions)."""

    # tile -> zone name (e.g. (5, 10) -> "nave")
    zones: Dict[Position, str] = field(default_factory=dict)
    # tiles that get the red carpet picture
    carpet: Set[Position] = field(default_factory=set)
    # (tile, decal name, variant number) for each flat floor decoration
    floor_decals: List[Tuple[Position, str, int]] = field(default_factory=list)
    # wall tile -> overlay name (banner, bookshelf, arch, ...)
    wall_decor: Dict[Position, str] = field(default_factory=dict)
    # floor tiles that hold a candle
    candles: List[Position] = field(default_factory=list)
    # floor tiles where water drips fall
    drip_points: List[Position] = field(default_factory=list)
    # tiles with glowing floor runes
    runes: Set[Position] = field(default_factory=set)

    def zone_of(self, pos: Position) -> str:
        """Zone name of a tile; corridors and anything unlisted count as 'hall'."""
        return self.zones.get(pos, "hall")


def _zone_map(maze: Maze) -> Dict[Position, str]:
    """Label every floor tile with the name of the room it belongs to."""
    zones: Dict[Position, str] = {}
    # The room rectangles only make sense for the 19x29 handcrafted map.
    handcrafted = (maze.rows, maze.cols) == (19, 29)
    # Visit every tile of the map.
    for r in range(maze.rows):
        for c in range(maze.cols):
            # Walls have no zone.
            if maze.grid[r][c] == "#":
                continue
            # Default: a corridor ("hall").
            zone = "hall"
            if handcrafted:
                # Find which room rectangle contains this tile (tuple unpacking splits
                # each rectangle into its four edges).
                for name, (top, left, bottom, right) in ROOM_ZONES:
                    if top <= r <= bottom and left <= c <= right:
                        zone = name
                        # Stop searching once a room matches.
                        break
            zones[(r, c)] = zone
    return zones


def _is_wall(maze: Maze, r: int, c: int) -> bool:
    """True if the tile is a wall OR lies outside the map (outside counts as solid)."""
    return not (0 <= r < maze.rows and 0 <= c < maze.cols) or maze.grid[r][c] == "#"


def build_decor(maze: Maze) -> Decor:
    """Place decoration for ``maze``. The same maze always yields the same result."""
    # Start the plan with the zone labels and the glowing-rune positions from the maze.
    decor = Decor(zones=_zone_map(maze), runes=set(maze.runes))
    # Tiles that must stay clear because something important or already decorative
    # is there. The `*` unpacks each collection's items into this one set.
    special: Set[Position] = {maze.start, maze.goal, maze.entrance, *maze.keys, *maze.doors, *maze.treasures,
                              *maze.torches, *maze.crystals, *maze.runes}
    # Tiles that already received a decoration (used to avoid crowding).
    used: Set[Position] = set()

    # Carpet runner
    # For each zone that should have a carpet...
    for zone, row in CARPET_ROW.items():
        # ...lay it on every tile of that zone along the chosen row (skipping special tiles).
        for pos, z in decor.zones.items():
            if z == zone and pos[0] == row and pos not in special:
                decor.carpet.add(pos)

    # Floor decals
    # Go through the floor tiles in a fixed (sorted) order so results never vary.
    for (r, c), zone in sorted(decor.zones.items()):
        pos = (r, c)
        # Leave important tiles alone.
        if pos in special:
            continue
        # A random generator seeded from the tile position: same tile -> same dice rolls.
        rng = random.Random(1701 + r * 131 + c * 17)
        # Is there a wall directly above/below/left/right of this tile?
        north, south = _is_wall(maze, r - 1, c), _is_wall(maze, r + 1, c)
        west, east = _is_wall(maze, r, c - 1), _is_wall(maze, r, c + 1)
        # A top corner (wall above AND exactly one side wall) gets a cobweb, except in corridors.
        if north and (west != east) and zone != "hall":
            decor.floor_decals.append((pos, "cobweb_nw" if west else "cobweb_ne", 0))
            used.add(pos)
            continue
        # Open floor away from every wall, or a carpet tile, gets nothing.
        if not (north or south or west or east) or pos in decor.carpet:
            continue
        # Do not put a decal right next to another one (avoids a cluttered look).
        if any((r + dr, c + dc) in used for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            continue
        # Roll one random number between 0 and 1 and walk through the zone's
        # probabilities like a roulette wheel: each decal "owns" a slice of the
        # range, and whichever slice the roll lands in is the winner.
        roll = rng.random()
        acc = 0.0
        for name, weight in FLOOR_WEIGHTS.get(zone, {}).items():
            acc += weight
            if roll < acc:
                # variant picks one of two art versions of the same decal.
                decor.floor_decals.append((pos, name, rng.randint(0, 1)))
                used.add(pos)
                break

    # Wall faces (a wall cell with floor to its south)
    # Remembers which columns in each row already have wall decor, to keep them spaced out.
    placed_in_row: Dict[int, List[int]] = {}
    for r in range(maze.rows):
        for c in range(maze.cols):
            # Only wall tiles that have open floor directly beneath them show a front face.
            if maze.grid[r][c] != "#" or _is_wall(maze, r + 1, c):
                continue
            # The floor tile just below this wall.
            below = (r + 1, c)
            # The wall above a gate or the exit gets a carved stone arch.
            if below in maze.doors or below == maze.goal:
                decor.wall_decor[(r, c)] = "arch"
                continue
            # The room the face looks into decides which decoration it can have.
            zone = decor.zone_of(below)
            rng = random.Random(4099 + r * 97 + c * 29)
            # Keep at least one plain wall tile between decorations (except bookshelves,
            # which are meant to line the whole wall).
            if zone != "reliquary" and any(abs(c - pc) < 2 for pc in placed_in_row.get(r, [])):
                continue
            # Same "roulette wheel" pick as for floor decals.
            roll = rng.random()
            acc = 0.0
            for name, weight in WALL_WEIGHTS.get(zone, []):
                acc += weight
                if roll < acc:
                    decor.wall_decor[(r, c)] = name
                    # setdefault creates an empty list for the row the first time.
                    placed_in_row.setdefault(r, []).append(c)
                    break

    # Candles in the reliquary (on floor cells hugging the wall) and drip points
    # Reliquary floor tiles that touch the north wall and are not special.
    candidates = [p for p, z in sorted(decor.zones.items())
                  if z == "reliquary" and p not in special and _is_wall(maze, p[0] - 1, p[1])]
    # Shuffle with a fixed seed (so it is random-looking but identical every run).
    rng = random.Random(77)
    rng.shuffle(candidates)
    # Take the first three shuffled tiles as candle spots.
    for pos in candidates[:3]:
        decor.candles.append(pos)
        used.add(pos)
    # Possible drip spots: tiles in the damp zones that touch the north wall.
    drips = [p for p, z in sorted(decor.zones.items()) if z in DRIP_ZONES and p not in special
             and _is_wall(maze, p[0] - 1, p[1])]
    rng = random.Random(91)
    rng.shuffle(drips)
    # Keep at most six drip points.
    decor.drip_points = drips[:6]
    return decor
