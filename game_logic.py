"""Dungeon movement, objectives, timing and recorded player performance."""
from __future__ import annotations
from dataclasses import dataclass, field
import time
from typing import List, Set
from maze import Maze, Position
from solver import solve_bfs


@dataclass
class GameStats:
    moves:int=0
    invalid_moves:int=0
    revisits:int=0
    treasures:int=0
    treasure_score:int=0
    hints_used:int=0
    started_at:float=field(default_factory=time.monotonic)
    elapsed:float=0.0
    completed:bool=False
    actual_route:List[Position]=field(default_factory=list)
    optimal_route:List[Position]=field(default_factory=list)
    @property
    def optimal_moves(self): return max(0,len(self.optimal_route)-1)


class Game:
    def __init__(self,maze:Maze,level_number=1,time_limit=900):
        self.maze,self.level_number,self.time_limit=maze,level_number,time_limit
        self.position=maze.start
        self.keys:Set[str]=set()
        if maze.start in maze.keys:self.keys.add(maze.keys[maze.start])
        self.stats=GameStats(actual_route=[maze.start],optimal_route=solve_bfs(maze))
        self.visited={maze.start}
        self.collected_treasures:Set[Position]=set()
        self.paused=False
        self.show_optimal_route=False
        self.show_actual_route=False
        self.result_view=False
        self.pause_selected=0
        self.hint_position=None
        self.message="Find the catacomb key. The gate lies beyond the nave."
        self.message_until=time.monotonic()+6
        self.previous_position=self.position
        self.movement_started=0.0
        self.facing=(0,1)
        self._paused_at=0.0

    @property
    def elapsed(self):
        if self.stats.completed or self.paused:return self.stats.elapsed
        return min(self.time_limit,time.monotonic()-self.stats.started_at)
    @property
    def remaining(self):return max(0,self.time_limit-self.elapsed)
    @property
    def won(self):return self.stats.completed and self.position==self.maze.goal
    @property
    def expired(self):return self.remaining<=0 and not self.won
    @property
    def animated_position(self):
        if not self.movement_started:return self.position
        t=min(1,(time.monotonic()-self.movement_started)/.115)
        if t>=1:return self.position
        return (self.previous_position[0]+(self.position[0]-self.previous_position[0])*t,
                self.previous_position[1]+(self.position[1]-self.previous_position[1])*t)

    @property
    def current_message(self):
        if time.monotonic()<self.message_until:return self.message
        if self.maze.goal in self.maze.neighbours(self.position,self.keys):return "The ancient gate waits ahead."
        return "Find the catacomb key." if not self.keys else "The exit lies beyond the sealed passage."

    def _tell(self,message,duration=3):
        self.message=message; self.message_until=time.monotonic()+duration

    def move(self,dr,dc):
        if self.paused or self.won or self.expired:return False
        target=(self.position[0]+dr,self.position[1]+dc)
        if not self.maze.in_bounds(target) or self.maze.grid[target[0]][target[1]]=='#':
            self.stats.invalid_moves+=1; self._tell("The old stone will not yield.",1.5); return False
        if target in self.maze.doors and self.maze.doors[target] not in self.keys:
            self.stats.invalid_moves+=1; self._tell("The sealed passage requires the catacomb key.",2.5); return False
        self.previous_position=self.position
        self.position=target
        self.movement_started=time.monotonic()
        self.facing=(dr,dc)
        self.hint_position=None
        if target in self.visited:self.stats.revisits+=1
        self.visited.add(target)
        self.stats.moves+=1
        self.stats.actual_route.append(target)
        if target in self.maze.keys and self.maze.keys[target] not in self.keys:
            self.keys.add(self.maze.keys[target]); self._tell("You found the catacomb key! The sealed gate can open.",5)
        if target in self.maze.treasures and target not in self.collected_treasures:
            self.collected_treasures.add(target)
            self.stats.treasures+=1; self.stats.treasure_score+=self.maze.treasures[target]
            self._tell("Treasure recovered from the forgotten crypt.",3)
        if target==self.maze.goal:
            if self.maze.doors and any(token not in self.keys for token in self.maze.doors.values()):
                self._tell("The relic gate remains sealed."); return False
            self.stats.elapsed=self.elapsed; self.stats.completed=True
            self._tell("The ancient relic is yours.",10)
        return True

    def request_hint(self):
        self.stats.hints_used+=1
        route=solve_bfs(self.maze,start=self.position,initial_keys=self.keys)
        if len(route)>1:
            self._tell(f"Follow the faint mark toward {route[1]}.",2)
            return route[1]
        return None

    def toggle_pause(self):
        if not self.paused:
            self.stats.elapsed=self.elapsed; self._paused_at=time.monotonic(); self.paused=True
        else:
            self.stats.started_at+=time.monotonic()-self._paused_at; self.paused=False

    def restart(self):return Game(self.maze,self.level_number,self.time_limit)

    def snapshot(self):
        return {"level":self.level_number,"position":list(self.position),"keys":sorted(self.keys),
                "moves":self.stats.moves,"invalid_moves":self.stats.invalid_moves,"revisits":self.stats.revisits,
                "treasures":self.stats.treasures,"treasure_score":self.stats.treasure_score,
                "hints_used":self.stats.hints_used,"elapsed":self.elapsed,
                "collected_treasures":[list(p) for p in self.collected_treasures],
                "completed":self.stats.completed,"actual_route":[list(p) for p in self.stats.actual_route],
                "optimal_route":[list(p) for p in self.stats.optimal_route],
                "visited":[list(p) for p in self.visited]}

    @classmethod
    def from_snapshot(cls,maze,snapshot,time_limit=900):
        game=cls(maze,int(snapshot.get("level",1)),time_limit)
        position=tuple(snapshot.get("position",maze.start))
        if maze.in_bounds(position) and maze.walkable(position,snapshot.get("keys",[])):
            game.position=position;game.previous_position=position
        game.keys=set(snapshot.get("keys",[]))
        for name in ("moves","invalid_moves","revisits","treasures","treasure_score","hints_used"):
            setattr(game.stats,name,int(snapshot.get(name,0)))
        game.stats.elapsed=float(snapshot.get("elapsed",0))
        game.stats.completed=bool(snapshot.get("completed",False))
        game.stats.actual_route=[tuple(p) for p in snapshot.get("actual_route",[game.position])]
        game.collected_treasures={tuple(p) for p in snapshot.get("collected_treasures",[])}
        game.visited={tuple(p) for p in snapshot.get("visited",game.stats.actual_route)}
        game.stats.started_at=time.monotonic()-game.stats.elapsed
        return game
