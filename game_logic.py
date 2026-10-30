"""Dungeon movement, objectives, timing and recorded player performance."""
# =============================================================================
# WHAT THIS FILE IS
# -----------------------------------------------------------------------------
# This is the "brain" of one play-through. It knows where the hero stands, which
# keys and treasures have been collected, how much time is left, and whether the
# player has won. It does NOT draw anything: the screen code (ui.py) only *reads*
# the values stored here and paints them. Keeping the rules separate from the
# drawing means the game logic can be tested without opening a window.
#
# Two classes live here:
#   GameStats - a small record of numbers (moves, treasures, hints, ...).
#   Game      - the actual rules: moving, picking things up, the timer, hints,
#               pausing, and saving/loading a game in progress.
# =============================================================================

# Lets type hints refer to classes that are defined later in the file.
from __future__ import annotations

# "dataclass" auto-writes boilerplate (__init__, etc.) for classes that mostly
# just hold data. "field" lets us customise how one of those values starts.
from dataclasses import dataclass, field

# The standard clock. time.monotonic() counts seconds forward and never jumps
# backwards (unlike the wall clock), which makes it safe for measuring durations.
import time

# Only used to describe types for readers and editors; they do nothing at runtime.
from typing import List, Set

# Maze is the level map; Position is the type "a (row, column) pair of ints".
from maze import Maze, Position

# solve_bfs finds the shortest route through the maze (used for hints and ranking).
from solver import solve_bfs


# The decorator below turns the class into a "dataclass": Python builds the
# constructor for us from the list of attributes written underneath.
@dataclass
class GameStats:
    """Numbers recorded about one run; shown on the results and statistics screens."""

    # How many successful steps the hero has taken.
    moves: int = 0
    # How many times the player walked into a wall or a locked gate (failed moves).
    invalid_moves: int = 0
    # How many steps landed on a tile that had already been visited.
    revisits: int = 0
    # How many treasure chests have been opened.
    treasures: int = 0
    # Sum of the gold value of the opened chests.
    treasure_score: int = 0
    # How many times the hint button was used.
    hints_used: int = 0
    # The clock reading (in seconds) when the run began. default_factory means
    # "call time.monotonic() each time a new GameStats is made" so every run gets
    # its own start time (a plain default would be evaluated only once).
    started_at: float = field(default_factory=time.monotonic)
    # Seconds elapsed, frozen when the game is paused or finished.
    elapsed: float = 0.0
    # True once the hero has reached the unlocked exit.
    completed: bool = False
    # Every tile the hero actually walked through, in order (the player's path).
    # default_factory=list gives each GameStats its own empty list.
    actual_route: List[Position] = field(default_factory=list)
    # The shortest possible route, computed once by breadth-first search.
    optimal_route: List[Position] = field(default_factory=list)

    # A property lets you write stats.optimal_moves like a variable even though
    # it is calculated on demand from the route above.
    @property
    def optimal_moves(self):
        # A route of N tiles needs N-1 steps. max(0, ...) avoids a negative
        # number when the route list is empty.
        return max(0, len(self.optimal_route) - 1)


class Game:
    """The state and rules of one play-through of the dungeon."""

    def __init__(self, maze: Maze, level_number=1, time_limit=900):
        # Remember the level map, which level this is, and the time allowed
        # (900 seconds = 15 minutes). Three values are assigned in one line.
        self.maze, self.level_number, self.time_limit = maze, level_number, time_limit
        # The hero's current tile, as (row, column). It begins on the start tile.
        self.position = maze.start
        # The set of key names the hero holds (e.g. {"catacomb"}). A set has no
        # duplicates and is fast to check "is X in here?".
        self.keys: Set[str] = set()
        # If a key happens to lie on the start tile, pick it up immediately.
        if maze.start in maze.keys:
            self.keys.add(maze.keys[maze.start])
        # Create the stats record. It starts with the start tile as the first step
        # of the walked route, and with the shortest route precomputed by BFS.
        self.stats = GameStats(actual_route=[maze.start], optimal_route=solve_bfs(maze))
        # All tiles the hero has stood on (a set: order does not matter here).
        self.visited = {maze.start}
        # Positions of the chests already opened.
        self.collected_treasures: Set[Position] = set()
        # True while the pause menu is open (the clock stops and moves are blocked).
        self.paused = False
        # Flags the screen reads to decide whether to draw the two route overlays:
        # the shortest route, and the route the player actually took.
        self.show_optimal_route = False
        self.show_actual_route = False
        # True when the player is looking at the shortest route from the results screen.
        self.result_view = False
        # Which line of the pause menu is highlighted (0 = the first).
        self.pause_selected = 0
        # The tile a hint is currently pointing at, or None when no hint is shown.
        self.hint_position = None
        # The text in the message bar at the bottom of the screen.
        self.message = "Find the catacomb key. The gate lies beyond the nave."
        # Until this clock time the message above is shown (here: for 6 seconds).
        self.message_until = time.monotonic() + 6
        # Where the hero was before the latest step. The screen uses it to slide the
        # sprite smoothly from the old tile to the new one.
        self.previous_position = self.position
        # When the latest step began (0.0 means "no step yet"); used for that slide.
        self.movement_started = 0.0
        # The direction the hero faces as (row change, column change): (0, 1) = right.
        self.facing = (0, 1)
        # The clock reading when pause began, so the paused time can be subtracted later.
        self._paused_at = 0.0

    # ------------------------------------------------------------------ timing
    @property
    def elapsed(self):
        """Seconds the run has taken so far."""
        # When paused or finished, the time is frozen at the stored value.
        if self.stats.completed or self.paused:
            return self.stats.elapsed
        # Otherwise: now minus the start time, but never more than the time limit.
        return min(self.time_limit, time.monotonic() - self.stats.started_at)

    @property
    def remaining(self):
        """Seconds left before the timer runs out (never below zero)."""
        return max(0, self.time_limit - self.elapsed)

    @property
    def won(self):
        """True only if the run is complete AND the hero is standing on the exit."""
        return self.stats.completed and self.position == self.maze.goal

    @property
    def expired(self):
        """True when the time has run out and the player has not already won."""
        return self.remaining <= 0 and not self.won

    @property
    def animated_position(self):
        """Where to DRAW the hero: a point part-way between the old and new tile.

        The real position jumps a whole tile instantly; this value glides over
        about a tenth of a second so movement looks smooth on screen.
        """
        # No step has happened yet, so just use the real position.
        if not self.movement_started:
            return self.position
        # t is progress from 0.0 (just started) to 1.0 (finished). The slide takes
        # 0.115 seconds, and min(1, ...) stops t from going past 1.
        t = min(1, (time.monotonic() - self.movement_started) / .115)
        # Slide finished: the drawn position equals the real one.
        if t >= 1:
            return self.position
        # Linear interpolation ("lerp"): start + (end - start) * progress, done
        # separately for the row and the column.
        return (self.previous_position[0] + (self.position[0] - self.previous_position[0]) * t,
                self.previous_position[1] + (self.position[1] - self.previous_position[1]) * t)

    @property
    def current_message(self):
        """The text to show in the message bar right now."""
        # A recent event message (like "You found the key!") wins while its time lasts.
        if time.monotonic() < self.message_until:
            return self.message
        # If the exit is one step away AND reachable with the keys held, tease it.
        if self.maze.goal in self.maze.neighbours(self.position, self.keys):
            return "The ancient gate waits ahead."
        # Otherwise give a gentle reminder of the objective, depending on the key.
        return "Find the catacomb key." if not self.keys else "The exit lies beyond the sealed passage."

    def _tell(self, message, duration=3):
        """Show a message for `duration` seconds (a leading underscore = internal helper)."""
        self.message = message
        self.message_until = time.monotonic() + duration

    # ---------------------------------------------------------------- movement
    def move(self, dr, dc):
        """Try to step one tile by (dr, dc) = (row change, column change).

        Returns True if the hero actually moved, False if the move was refused.
        """
        # Ignore input while paused, after winning, or after time ran out.
        if self.paused or self.won or self.expired:
            return False
        # The tile the hero wants to enter: current tile plus the direction.
        target = (self.position[0] + dr, self.position[1] + dc)
        # Refuse if the target is off the map or is a wall ('#' in the grid).
        if not self.maze.in_bounds(target) or self.maze.grid[target[0]][target[1]] == '#':
            # Count it as a failed move and show a short message.
            self.stats.invalid_moves += 1
            self._tell("The old stone will not yield.", 1.5)
            return False
        # Refuse if the target is a locked gate and the matching key is not held.
        if target in self.maze.doors and self.maze.doors[target] not in self.keys:
            self.stats.invalid_moves += 1
            self._tell("The sealed passage requires the catacomb key.", 2.5)
            return False
        # --- The move is allowed, so update the hero's state. ---
        # Remember the old tile (for the sliding animation) then switch to the new one.
        self.previous_position = self.position
        self.position = target
        # Note when the step began, and which way the hero now faces.
        self.movement_started = time.monotonic()
        self.facing = (dr, dc)
        # Moving makes any displayed hint out of date, so clear it.
        self.hint_position = None
        # If this tile was visited before, count a revisit (a sign of backtracking).
        if target in self.visited:
            self.stats.revisits += 1
        self.visited.add(target)
        # Count the step and record the tile in the walked route.
        self.stats.moves += 1
        self.stats.actual_route.append(target)
        # Key pickup: there is a key here and the hero does not hold that key yet.
        if target in self.maze.keys and self.maze.keys[target] not in self.keys:
            self.keys.add(self.maze.keys[target])
            self._tell("You found the catacomb key! The sealed gate can open.", 5)
        # Treasure pickup: a chest here that has not been opened yet.
        if target in self.maze.treasures and target not in self.collected_treasures:
            self.collected_treasures.add(target)
            # Count the chest and add its gold value to the score.
            self.stats.treasures += 1
            self.stats.treasure_score += self.maze.treasures[target]
            self._tell("Treasure recovered from the forgotten crypt.", 3)
        # Reaching the exit tile finishes the level, but only if every gate is open.
        if target == self.maze.goal:
            # `any(...)` is True if at least one gate's key is missing.
            if self.maze.doors and any(token not in self.keys for token in self.maze.doors.values()):
                self._tell("The relic gate remains sealed.")
                return False
            # Freeze the final time and mark the run as complete.
            self.stats.elapsed = self.elapsed
            self.stats.completed = True
            self._tell("The ancient relic is yours.", 10)
        # The step succeeded.
        return True

    # ------------------------------------------------------------------- hints
    def request_hint(self):
        """Work out the next step toward the exit; returns that tile (or None)."""
        # Using a hint is recorded in the stats.
        self.stats.hints_used += 1
        # Shortest route from the hero's CURRENT tile with the keys held right now.
        route = solve_bfs(self.maze, start=self.position, initial_keys=self.keys)
        # route[0] is where we already are, so route[1] is the next tile to walk to.
        if len(route) > 1:
            self._tell(f"Follow the faint mark toward {route[1]}.", 2)
            return route[1]
        # No route (or already there): there is nothing to point at.
        return None

    # ------------------------------------------------------------------- pause
    def toggle_pause(self):
        """Pause if running, resume if paused, keeping the timer fair."""
        if not self.paused:
            # Pausing: store the elapsed time so the clock can stop, remember when
            # the pause began, and flag the game as paused.
            self.stats.elapsed = self.elapsed
            self._paused_at = time.monotonic()
            self.paused = True
        else:
            # Resuming: push the start time forward by however long we were paused.
            # That way the paused period is not counted against the player.
            self.stats.started_at += time.monotonic() - self._paused_at
            self.paused = False

    def restart(self):
        """Return a brand-new game on the same level (the old object is left unchanged)."""
        return Game(self.maze, self.level_number, self.time_limit)

    # ------------------------------------------------------------ save / load
    def snapshot(self):
        """Pack the current progress into a plain dict that can be saved as JSON."""
        # JSON cannot store tuples or sets, so positions become lists, and the
        # key set becomes a sorted list.
        return {"level": self.level_number, "position": list(self.position), "keys": sorted(self.keys),
                "moves": self.stats.moves, "invalid_moves": self.stats.invalid_moves, "revisits": self.stats.revisits,
                "treasures": self.stats.treasures, "treasure_score": self.stats.treasure_score,
                "hints_used": self.stats.hints_used, "elapsed": self.elapsed,
                "collected_treasures": [list(p) for p in self.collected_treasures],
                "completed": self.stats.completed, "actual_route": [list(p) for p in self.stats.actual_route],
                "optimal_route": [list(p) for p in self.stats.optimal_route],
                "visited": [list(p) for p in self.visited]}

    # A classmethod receives the class itself (`cls`) instead of an instance, so
    # it works like an alternative constructor: Game.from_snapshot(...).
    @classmethod
    def from_snapshot(cls, maze, snapshot, time_limit=900):
        """Rebuild a Game from a dict made by snapshot(); tolerant of missing fields."""
        # Start from a fresh game, then overwrite it with the saved values.
        # `.get(name, default)` returns the default if the saved file lacks that field.
        game = cls(maze, int(snapshot.get("level", 1)), time_limit)
        # JSON gives a list, so convert back to a (row, column) tuple.
        position = tuple(snapshot.get("position", maze.start))
        # Only trust the saved position if it is on the map and walkable with the
        # saved keys (protects against corrupted or edited save files).
        if maze.in_bounds(position) and maze.walkable(position, snapshot.get("keys", [])):
            game.position = position
            game.previous_position = position
        # Restore the held keys as a set.
        game.keys = set(snapshot.get("keys", []))
        # Copy the simple whole-number stats one by one. setattr(obj, "name", value)
        # sets obj.name = value using a name held in a string.
        for name in ("moves", "invalid_moves", "revisits", "treasures", "treasure_score", "hints_used"):
            setattr(game.stats, name, int(snapshot.get(name, 0)))
        # Restore the time already used and whether the run was finished.
        game.stats.elapsed = float(snapshot.get("elapsed", 0))
        game.stats.completed = bool(snapshot.get("completed", False))
        # Rebuild the walked route, opened chests and visited tiles as tuples.
        game.stats.actual_route = [tuple(p) for p in snapshot.get("actual_route", [game.position])]
        game.collected_treasures = {tuple(p) for p in snapshot.get("collected_treasures", [])}
        game.visited = {tuple(p) for p in snapshot.get("visited", game.stats.actual_route)}
        # Pretend the run began `elapsed` seconds ago so the timer carries on from
        # where the player left off.
        game.stats.started_at = time.monotonic() - game.stats.elapsed
        return game
