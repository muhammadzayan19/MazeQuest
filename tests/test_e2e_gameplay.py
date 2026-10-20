"""End-to-end integration test simulating actual user sessions in MazeQuest."""
import unittest
import pygame
import time
from maze import Maze
from game_logic import Game
from display_manager import DisplayManager, IW, IH
from sound import SoundManager
from ui import UI
from solver import solve_bfs


class TestEndToEndGameplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_fullscreen_and_windowed_transitions_without_crash(self):
        dm = DisplayManager(fullscreen=False, window_size=(1100, 760))
        screen = dm.init_display()
        self.assertFalse(dm.is_fullscreen)
        self.assertEqual(dm.screen.get_size(), (1100, 760))

        # Toggle to fullscreen
        is_full = dm.toggle_fullscreen()
        self.assertTrue(is_full)
        self.assertTrue(dm.is_fullscreen)
        # Verify viewport is valid
        self.assertGreater(dm.viewport_rect.width, 0)
        self.assertGreater(dm.viewport_rect.height, 0)

        # Toggle back to windowed
        is_full = dm.toggle_fullscreen()
        self.assertFalse(is_full)
        self.assertFalse(dm.is_fullscreen)
        self.assertEqual(dm.screen.get_size(), (1100, 760))

    def test_resolution_resizing_preserves_aspect_ratio_and_visibility(self):
        dm = DisplayManager(fullscreen=False, window_size=(1100, 760))
        dm.init_display()

        test_resolutions = [
            (800, 600),     # 4:3 small
            (1280, 720),    # 16:9 standard
            (1600, 900),    # 16:9 large
            (1920, 1080),   # 16:9 Full HD
            (1920, 1200),   # 16:10
            (1100, 760),    # 16:11 native-like
        ]

        ui = UI(dm.screen, display_mgr=dm)
        game = Game(Maze.handcrafted(), 1, 900)

        for w, h in test_resolutions:
            dm.handle_resize((w, h))
            self.assertEqual(dm.screen.get_size(), (w, h))

            # Viewport must never exceed window bounds
            self.assertLessEqual(dm.viewport_rect.width, w)
            self.assertLessEqual(dm.viewport_rect.height, h)
            # Letterbox margins must be non-negative
            self.assertGreaterEqual(dm.viewport_rect.x, 0)
            self.assertGreaterEqual(dm.viewport_rect.y, 0)
            # Aspect ratio of viewport must match internal resolution
            aspect_ratio = dm.viewport_rect.width / dm.viewport_rect.height
            self.assertAlmostEqual(aspect_ratio, IW / IH, delta=0.03)

            # Render dungeon at this resolution - must execute without error
            ui.dungeon(game)
            ui.menu(0)
            ui.settings({"fullscreen": False, "sound": True, "show_hints": True})
            ui.results(game)

    def test_complete_gameplay_flow(self):
        """Simulate player entering dungeon, walking, collecting key & treasure, reaching exit."""
        game = Game(Maze.handcrafted(), 1, 900)
        dm = DisplayManager(fullscreen=False, window_size=(1100, 760))
        dm.init_display()
        ui = UI(dm.screen, display_mgr=dm)

        # 1. Check start
        self.assertEqual(game.position, game.maze.start)
        self.assertFalse(game.won)
        self.assertEqual(len(game.keys), 0)

        # 2. Test invalid move into wall
        wall_r = game.position[0] + 1
        wall_c = game.position[1]
        if game.maze.grid[wall_r][wall_c] == '#':
            self.assertFalse(game.move(1, 0))
            self.assertEqual(game.stats.invalid_moves, 1)

        # 3. Solve shortest path to key
        key_pos = next(iter(game.maze.keys))
        to_key = solve_bfs(game.maze, start=game.position, goal=key_pos, initial_keys=game.keys)
        self.assertTrue(to_key)
        for step in to_key[1:]:
            self.assertTrue(game.move(step[0] - game.position[0], step[1] - game.position[1]))
            ui.dungeon(game)

        # Key must now be collected
        self.assertIn("catacomb", game.keys)

        # 4. Walk to treasure
        treasure_pos = (12, 12)
        to_treasure = solve_bfs(game.maze, start=game.position, goal=treasure_pos, initial_keys=game.keys)
        for step in to_treasure[1:]:
            self.assertTrue(game.move(step[0] - game.position[0], step[1] - game.position[1]))

        self.assertIn(treasure_pos, game.collected_treasures)
        self.assertGreaterEqual(game.stats.treasures, 1)

        # 5. Walk through unlocked door to exit
        to_goal = solve_bfs(game.maze, start=game.position, goal=game.maze.goal, initial_keys=game.keys)
        for step in to_goal[1:]:
            self.assertTrue(game.move(step[0] - game.position[0], step[1] - game.position[1]))

        # Must win
        self.assertTrue(game.won)
        self.assertEqual(game.position, game.maze.goal)

        # Render results screen
        ui.results(game)
        self.assertTrue(len(ui.result_rects) >= 3)


if __name__ == "__main__":
    unittest.main()
