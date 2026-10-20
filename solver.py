"""Key-aware BFS shortest path and genuine recursive DFS demonstration."""
from __future__ import annotations
from typing import Dict, FrozenSet, List, Optional, Set, Tuple
from maze import Maze, Position

State = Tuple[Position,FrozenSet[str]]


def _next_state(maze: Maze, position: Position, keys: FrozenSet[str]):
    for nxt in maze.neighbours(position,keys):
        found=maze.keys.get(nxt)
        yield nxt, frozenset(set(keys)|({found} if found else set()))


def solve_bfs(maze: Maze, start: Optional[Position]=None, goal: Optional[Position]=None,
              initial_keys=()) -> List[Position]:
    start=maze.start if start is None else start
    goal=maze.goal if goal is None else goal
    initial=(start,frozenset(initial_keys)|({maze.keys[start]} if start in maze.keys else set()))
    queue=[initial]
    parents: Dict[State,Optional[State]]={initial:None}
    for state in queue:
        position,keys=state
        if position==goal: return _reconstruct(parents,state)
        for nxt,new_keys in _next_state(maze,position,keys):
            candidate=(nxt,new_keys)
            if candidate not in parents:
                parents[candidate]=state
                queue.append(candidate)
    return []


def solve_dfs(maze: Maze, start: Optional[Position]=None, goal: Optional[Position]=None,
              initial_keys=()) -> List[Position]:
    """Recursive depth-first search with explicit path backtracking."""
    start=maze.start if start is None else start
    goal=maze.goal if goal is None else goal
    visited: Set[State]=set()
    path: List[Position]=[]
    initial=frozenset(initial_keys)|({maze.keys[start]} if start in maze.keys else set())
    def visit(position: Position, keys: FrozenSet[str]) -> bool:
        state=(position,keys)
        if state in visited:return False
        visited.add(state); path.append(position)
        if position==goal:return True
        for nxt,new_keys in _next_state(maze,position,keys):
            if visit(nxt,new_keys):return True
        path.pop()
        return False
    return path if visit(start,frozenset(initial)) else []


def _reconstruct(parents,state):
    route=[]
    while state is not None:
        route.append(state[0]); state=parents[state]
    return list(reversed(route))


class MazeSolver:
    bfs=staticmethod(solve_bfs)
    dfs=staticmethod(solve_dfs)
