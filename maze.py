"""Handcrafted catacomb level and its nested-list logical tile map."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set, Tuple

Position = Tuple[int, int]


@dataclass(frozen=True)
class Level:
    number: int = 1
    name: str = "The Forgotten Catacombs"
    rows: int = 19
    cols: int = 29
    time_limit: int = 900
    key_count: int = 1
    seed: int = 1701
    description: str = "Recover the catacomb key and claim the ancient relic."
    treasure_count: int = 1


LEVELS = (Level(),)
LEVEL_CONFIGS = LEVELS


@dataclass
class Maze:
    rows: int
    cols: int
    walls: Set[Position] = field(default_factory=set)
    start: Position = (1, 1)
    goal: Position = (1, 1)
    keys: Dict[Position, str] = field(default_factory=dict)
    doors: Dict[Position, str] = field(default_factory=dict)
    treasures: Dict[Position, int] = field(default_factory=dict)
    grid: Optional[List[List[str]]] = None
    torches: Set[Position] = field(default_factory=set)
    runes: Set[Position] = field(default_factory=set)
    crystals: Set[Position] = field(default_factory=set)
    entrance: Position = (1, 1)

    def __post_init__(self):
        if self.grid is None:
            self.grid = [['#' if (r,c) in self.walls else '.' for c in range(self.cols)] for r in range(self.rows)]
        else:
            self.rows, self.cols = len(self.grid), len(self.grid[0])
            self.walls = {(r,c) for r in range(self.rows) for c in range(self.cols) if self.grid[r][c] == '#'}

    @classmethod
    def generate(cls, level: Level = LEVELS[0], rng=None) -> "Maze":
        """Return the intentional single level (rng retained for old callers)."""
        return cls.handcrafted()

    @classmethod
    def handcrafted(cls) -> "Maze":
        rows, cols = 19, 29
        grid = [['#' for _ in range(cols)] for _ in range(rows)]

        def room(top, left, bottom, right):
            for r in range(top, bottom+1):
                for c in range(left, right+1): grid[r][c] = '.'

        def hall(a: Position, b: Position):
            r,c=a; er,ec=b
            while r != er:
                grid[r][c]='.'; r += 1 if er>r else -1
            while c != ec:
                grid[r][c]='.'; c += 1 if ec>c else -1
            grid[r][c]='.'

        # Entrance crypt, western cul-de-sac, central nave and an optional reliquary.
        room(13,1,17,6)
        room(7,2,10,8)
        room(3,8,8,15)
        room(2,16,6,21)
        room(2,23,6,27)
        room(11,10,13,14)
        hall((15,3),(10,3)); hall((8,3),(8,8)); hall((7,11),(5,11))
        hall((5,15),(4,16)); hall((4,21),(4,23))
        hall((8,13),(11,13)); hall((13,10),(13,8)); hall((13,8),(12,8))
        # Dead-end branches add deliberate choices without disconnecting rooms.
        hall((9,5),(9,2)); hall((6,9),(6,7)); hall((12,12),(15,12))
        hall((6,8),(6,6)); hall((3,12),(1,12))

        # Thicken the join between nave and key chamber into a sealed partition;
        # only the marked row-four arch connects these rooms.
        for r in range(3,7):
            if r != 4: grid[r][16]='#'

        start, goal, entrance = (15,3), (4,25), (17,3)
        key, door, treasure = (3,19), (4,22), (12,12)
        grid[start[0]][start[1]]='S'; grid[goal[0]][goal[1]]='E'
        grid[key[0]][key[1]]='K'; grid[door[0]][door[1]]='D'; grid[treasure[0]][treasure[1]]='T'
        # A second small cache in the entrance chamber rewards a short detour.
        grid[16][5]='T'
        maze = cls(rows,cols,start=start,goal=goal,keys={key:'catacomb'},
                   doors={door:'catacomb'},treasures={treasure:100,(16,5):35},grid=grid,
                   torches={(14,2),(16,2),(10,6),(5,10),(4,17),(3,25),(12,11)},
                   runes={(8,4),(5,13),(4,20),(12,13)},crystals={(6,11),(4,18),(12,10)},entrance=entrance)
        maze.validate()
        return maze

    def validate(self) -> bool:
        if not self.grid or len(self.grid) != self.rows or any(len(row)!=self.cols for row in self.grid):
            raise ValueError("dungeon grid must be a rectangular nested list")
        for p in (self.start,self.goal,*self.keys,*self.doors,*self.treasures):
            if not self.in_bounds(p): raise ValueError(f"dungeon item out of bounds: {p}")
        if self.start == self.goal or self.start in self.walls or self.goal in self.walls:
            raise ValueError("entrance and exit must be distinct floor tiles")
        from solver import solve_bfs
        if not solve_bfs(self): raise ValueError("the catacomb exit is unreachable")
        if not self.doors or not self.keys or not self.treasures:
            raise ValueError("the level needs a key, locked passage and treasure")
        route=solve_bfs(self)
        key_pos=next(iter(self.keys))
        door_pos=next(iter(self.doors))
        if self.walkable(door_pos,()) or route.index(key_pos)>route.index(door_pos):
            raise ValueError("the final gate must be locked until the catacomb key is collected")
        return True

    def in_bounds(self, position: Position) -> bool:
        return 0 <= position[0] < self.rows and 0 <= position[1] < self.cols

    def to_grid(self) -> List[List[str]]:
        return [row[:] for row in self.grid]

    def walkable(self, position: Position, collected: Iterable[str] = ()) -> bool:
        if not self.in_bounds(position) or self.grid[position[0]][position[1]] == '#': return False
        token=self.doors.get(position)
        return token is None or token in set(collected)

    def neighbours(self, position: Position, collected: Iterable[str] = ()) -> List[Position]:
        return [p for p in ((position[0]-1,position[1]),(position[0]+1,position[1]),
                            (position[0],position[1]-1),(position[0],position[1]+1))
                if self.walkable(p,collected)]


def _reachable(maze: Maze) -> bool:
    from solver import solve_bfs
    return bool(solve_bfs(maze))
