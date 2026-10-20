import tempfile
import unittest
from pathlib import Path

from game_logic import Game
from maze import LEVELS,Maze
from save_data import load_state,save_state
from solver import solve_bfs,solve_dfs


class CatacombTests(unittest.TestCase):
    def setUp(self):
        self.maze=Maze.handcrafted()

    def test_handcrafted_nested_layout_and_landmarks(self):
        self.assertEqual(len(LEVELS),1)
        self.assertEqual(LEVELS[0].name,"The Forgotten Catacombs")
        grid=self.maze.to_grid()
        self.assertEqual(len(grid),self.maze.rows)
        self.assertTrue(all(len(row)==self.maze.cols for row in grid))
        self.assertTrue(self.maze.validate())
        self.assertGreaterEqual(len(self.maze.torches),5)
        self.assertGreaterEqual(len(self.maze.runes),3)
        self.assertGreaterEqual(len(self.maze.crystals),2)
        self.assertEqual(len(self.maze.treasures),2)
        dead_ends=[(r,c) for r in range(self.maze.rows) for c in range(self.maze.cols)
                   if self.maze.walkable((r,c),{"catacomb"}) and len(self.maze.neighbours((r,c),{"catacomb"}))==1]
        self.assertGreaterEqual(len(dead_ends),2)

    def test_locked_gate_requires_key_and_solver_collects_it_first(self):
        door=next(iter(self.maze.doors))
        key=next(iter(self.maze.keys))
        self.assertFalse(self.maze.walkable(door,()))
        self.assertTrue(self.maze.walkable(door,{"catacomb"}))
        route=solve_bfs(self.maze)
        self.assertLess(route.index(key),route.index(door))
        self.assertEqual(route[0],self.maze.start)
        self.assertEqual(route[-1],self.maze.goal)
        game=Game(self.maze);game.position=(4,21)
        self.assertFalse(game.move(0,1))
        self.assertEqual(game.stats.invalid_moves,1)

    def test_collision_key_treasure_and_completion(self):
        game=Game(self.maze)
        game.position=(1,12)
        start=game.position
        wall=(0,12)
        self.assertFalse(game.move(wall[0]-start[0],wall[1]-start[1]))
        self.assertEqual(game.stats.invalid_moves,1)
        treasure=next(iter(self.maze.treasures))
        self._walk_to(game,treasure)
        self.assertEqual(game.stats.treasures,1)
        self.assertIn(treasure,game.collected_treasures)
        self._walk_to(game,self.maze.goal)
        self.assertTrue(game.won)
        self.assertIn("catacomb",game.keys)
        self.assertGreater(game.stats.moves,0)

    def test_bfs_is_shortest_and_dfs_is_recursive_exploration(self):
        bfs=solve_bfs(self.maze)
        dfs=solve_dfs(self.maze)
        self.assertTrue(bfs); self.assertTrue(dfs)
        self.assertEqual(len(bfs),36)
        self.assertGreaterEqual(len(dfs),len(bfs))
        self.assertGreater(len(set(dfs)),20)
        for a,b in zip(bfs,bfs[1:]):self.assertEqual(abs(a[0]-b[0])+abs(a[1]-b[1]),1)

    def test_elapsed_pause_and_snapshot_resume(self):
        game=Game(self.maze)
        step=solve_bfs(self.maze)[1]
        game.move(step[0]-game.position[0],step[1]-game.position[1])
        game.toggle_pause(); elapsed=game.elapsed
        game.toggle_pause()
        restored=Game.from_snapshot(self.maze,game.snapshot())
        self.assertEqual(restored.position,game.position)
        self.assertEqual(restored.stats.moves,1)
        self.assertEqual(restored.stats.actual_route,game.stats.actual_route)
        self.assertAlmostEqual(restored.elapsed,elapsed,delta=.1)
        self.assertIn(restored.position,restored.visited)
        self.assertIsNotNone(restored.request_hint())

    def test_json_save_restore_and_corrupt_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"state.json"
            game=Game(self.maze)
            payload={"version":3,"current":game.snapshot(),"history":[],"personal_bests":{},"settings":{"sound":True,"show_hints":True}}
            save_state(path,payload)
            saved=load_state(path)
            self.assertEqual(Game.from_snapshot(self.maze,saved["current"]).position,self.maze.start)
            path.write_text("{broken",encoding="utf-8")
            self.assertIsNone(load_state(path)["current"])

    def _walk_to(self,game,target):
        route=solve_bfs(game.maze,start=game.position,goal=target,initial_keys=game.keys)
        self.assertTrue(route)
        for nxt in route[1:]:
            self.assertTrue(game.move(nxt[0]-game.position[0],nxt[1]-game.position[1]))


if __name__=="__main__":unittest.main()
