"""Deterministic dungeon dressing: zones, floor decals, wall decor, candles and drip points.

Pure data derived from a ``Maze`` (nothing here touches game state). Decals are flat and
walkable-looking, and wall decor only replaces wall faces, so nothing blocks a route."""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

from maze import Maze

Position = Tuple[int, int]

# (name, (top, left, bottom, right)) of the handcrafted rooms in Maze.handcrafted()
ROOM_ZONES: List[Tuple[str, Tuple[int, int, int, int]]] = [
    ("crypt", (13, 1, 17, 6)),
    ("cellar", (7, 2, 10, 8)),
    ("nave", (3, 8, 8, 15)),
    ("keyroom", (2, 16, 6, 21)),
    ("sanctum", (2, 23, 6, 27)),
    ("reliquary", (11, 10, 13, 14)),
]
CARPET_ROW = {"nave": 5}          # a worn runner down the middle of the nave

# probability per eligible edge cell, by zone
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
DRIP_ZONES = {"cellar", "keyroom", "crypt"}


@dataclass
class Decor:
    zones: Dict[Position, str] = field(default_factory=dict)
    carpet: Set[Position] = field(default_factory=set)
    floor_decals: List[Tuple[Position, str, int]] = field(default_factory=list)
    wall_decor: Dict[Position, str] = field(default_factory=dict)
    candles: List[Position] = field(default_factory=list)
    drip_points: List[Position] = field(default_factory=list)
    runes: Set[Position] = field(default_factory=set)

    def zone_of(self, pos: Position) -> str:
        return self.zones.get(pos, "hall")


def _zone_map(maze: Maze) -> Dict[Position, str]:
    zones: Dict[Position, str] = {}
    handcrafted = (maze.rows, maze.cols) == (19, 29)
    for r in range(maze.rows):
        for c in range(maze.cols):
            if maze.grid[r][c] == "#":
                continue
            zone = "hall"
            if handcrafted:
                for name, (top, left, bottom, right) in ROOM_ZONES:
                    if top <= r <= bottom and left <= c <= right:
                        zone = name
                        break
            zones[(r, c)] = zone
    return zones


def _is_wall(maze: Maze, r: int, c: int) -> bool:
    return not (0 <= r < maze.rows and 0 <= c < maze.cols) or maze.grid[r][c] == "#"


def build_decor(maze: Maze) -> Decor:
    """Place decoration for ``maze``. The same maze always yields the same result."""
    decor = Decor(zones=_zone_map(maze), runes=set(maze.runes))
    special: Set[Position] = {maze.start, maze.goal, maze.entrance, *maze.keys, *maze.doors, *maze.treasures,
                              *maze.torches, *maze.crystals, *maze.runes}
    used: Set[Position] = set()

    # Carpet runner
    for zone, row in CARPET_ROW.items():
        for pos, z in decor.zones.items():
            if z == zone and pos[0] == row and pos not in special:
                decor.carpet.add(pos)

    # Floor decals
    for (r, c), zone in sorted(decor.zones.items()):
        pos = (r, c)
        if pos in special:
            continue
        rng = random.Random(1701 + r * 131 + c * 17)
        north, south = _is_wall(maze, r - 1, c), _is_wall(maze, r + 1, c)
        west, east = _is_wall(maze, r, c - 1), _is_wall(maze, r, c + 1)
        if north and (west != east) and zone != "hall":
            decor.floor_decals.append((pos, "cobweb_nw" if west else "cobweb_ne", 0))
            used.add(pos)
            continue
        if not (north or south or west or east) or pos in decor.carpet:
            continue
        if any((r + dr, c + dc) in used for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            continue
        roll = rng.random()
        acc = 0.0
        for name, weight in FLOOR_WEIGHTS.get(zone, {}).items():
            acc += weight
            if roll < acc:
                decor.floor_decals.append((pos, name, rng.randint(0, 1)))
                used.add(pos)
                break

    # Wall faces (a wall cell with floor to its south)
    placed_in_row: Dict[int, List[int]] = {}
    for r in range(maze.rows):
        for c in range(maze.cols):
            if maze.grid[r][c] != "#" or _is_wall(maze, r + 1, c):
                continue
            below = (r + 1, c)
            if below in maze.doors or below == maze.goal:
                decor.wall_decor[(r, c)] = "arch"
                continue
            zone = decor.zone_of(below)
            rng = random.Random(4099 + r * 97 + c * 29)
            if zone != "reliquary" and any(abs(c - pc) < 2 for pc in placed_in_row.get(r, [])):
                continue
            roll = rng.random()
            acc = 0.0
            for name, weight in WALL_WEIGHTS.get(zone, []):
                acc += weight
                if roll < acc:
                    decor.wall_decor[(r, c)] = name
                    placed_in_row.setdefault(r, []).append(c)
                    break

    # Candles in the reliquary (on floor cells hugging the wall) and drip points
    candidates = [p for p, z in sorted(decor.zones.items())
                  if z == "reliquary" and p not in special and _is_wall(maze, p[0] - 1, p[1])]
    rng = random.Random(77)
    rng.shuffle(candidates)
    for pos in candidates[:3]:
        decor.candles.append(pos)
        used.add(pos)
    drips = [p for p, z in sorted(decor.zones.items()) if z in DRIP_ZONES and p not in special
             and _is_wall(maze, p[0] - 1, p[1])]
    rng = random.Random(91)
    rng.shuffle(drips)
    decor.drip_points = drips[:6]
    return decor
