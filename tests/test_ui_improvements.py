"""Tests for the UI correctness/usability improvements."""
import unittest
import pygame
from display_manager import DisplayManager, IW, IH
from game_logic import Game
from maze import Maze
from ui import UI


class TestUIImprovements(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.ui = UI(pygame.Surface((1100, 760)))

    def setUp(self):
        self.ui.hints_enabled = True
        self.ui.hint_cooldown = 0.0
        self.game = Game(Maze.handcrafted(), 1, 900)

    def test_fit_text_never_exceeds_width(self):
        for width in (20, 60, 150):
            fitted = self.ui.fit_text("THE ANCIENT RELIC GATE REMAINS SEALED", self.ui.tiny, width)
            self.assertLessEqual(self.ui.tiny.size(fitted)[0], width)
        self.assertEqual(self.ui.fit_text("OK", self.ui.tiny, 200), "OK")

    def test_hint_button_respects_setting_and_cooldown(self):
        self.ui.dungeon(self.game)
        pos = self.ui.hint_btn_rect.center
        self.assertEqual(self.ui.game_hit(pos), "HINT")
        self.ui.hint_cooldown = 2.0
        self.assertIsNone(self.ui.game_hit(pos))
        self.ui.hint_cooldown = 0.0
        self.ui.hints_enabled = False
        self.assertIsNone(self.ui.game_hit(pos))

    def test_stats_screen_counts_wins_and_losses(self):
        history = [{"completed": True}, {"completed": False}, {"completed": False}]
        self.ui.statistics(history, {})  # must render without error
        self.ui.statistics([], {})

    def test_settings_has_volume_track_and_scaling_row(self):
        self.ui.settings({"volume": 0.5}, selected=3)
        labels = [label for label, _ in self.ui.settings_rects]
        self.assertIn("SCALING", labels)
        self.assertNotIn("ASPECT RATIO", labels)
        track = self.ui.volume_track
        self.assertGreater(track.w, 0)
        self.assertAlmostEqual(self.ui.volume_from_pos(track.inflate(-8, 0).midleft), 0.0, delta=0.06)
        self.assertAlmostEqual(self.ui.volume_from_pos(track.inflate(-8, 0).midright), 1.0, delta=0.06)
        self.assertIsNone(self.ui.volume_from_pos((0, 0)))

    def test_results_renders_for_win_and_loss_with_new_best(self):
        self.game.stats.completed = True
        self.game.position = self.game.maze.goal
        self.ui.results(self.game, None, 2, True)
        self.assertEqual(len(self.ui.result_rects), 3)
        self.game.stats.completed = False
        self.game.stats.started_at -= 10_000
        self.ui.results(self.game, None, 0, False)

    def test_static_layer_cached_per_maze(self):
        self.ui.dungeon(self.game)
        layer = self.ui._static_layer
        self.ui.dungeon(self.game)
        self.assertIs(self.ui._static_layer, layer)
        self.ui.dungeon(Game(Maze.handcrafted(), 1, 900))
        self.assertIsNot(self.ui._static_layer, layer)

    def test_cell_center_matches_origin(self):
        maze = self.game.maze
        ox, oy = self.ui.maze_origin(maze)
        self.assertEqual(self.ui.cell_center(maze, 0, 0), (ox + 9, oy + 8))


class TestDisplayScaleModes(unittest.TestCase):
    def test_fit_mode_fills_window_keeping_aspect(self):
        pygame.init()
        dm = DisplayManager(scale_mode="fit")
        dm.screen = pygame.Surface((1920, 1080))
        dm.update_viewport()
        self.assertGreater(dm.viewport_rect.width, IW * 2)
        self.assertLessEqual(dm.viewport_rect.width, 1920)
        self.assertLessEqual(dm.viewport_rect.height, 1080)
        self.assertAlmostEqual(dm.viewport_rect.width / dm.viewport_rect.height, IW / IH, delta=0.02)
        dm.set_scale_mode("integer")
        self.assertEqual(dm.viewport_rect.size, (IW * 2, IH * 2))


if __name__ == "__main__":
    unittest.main()


class TestHiResLayer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.ui = UI(pygame.Surface((1280, 880)))

    def test_smooth_mode_fills_window_keeping_aspect(self):
        dm = DisplayManager(scale_mode="smooth")
        dm.screen = pygame.Surface((1500, 900))
        dm.update_viewport()
        self.assertGreater(dm.viewport_rect.width, IW * 2)
        self.assertAlmostEqual(dm.viewport_rect.width / dm.viewport_rect.height, IW / IH, delta=0.02)

    def test_face_measures_logical_text_monotonically(self):
        short, longer = self.ui.body.size("Hi")[0], self.ui.body.size("Hi there, delver")[0]
        self.assertGreater(short, 0)
        self.assertGreater(longer, short)

    def test_dim_command_covers_earlier_text(self):
        target = pygame.Surface((1280, 880))
        target.fill((0, 0, 0))
        ui = self.ui
        ui.clear_commands()
        ui.text("WWWWWWWW", (100, 100), ui.huge, (255, 255, 255))
        ui.dim((0, 0, 0, 255))
        ui.render_commands(target, 2.0)
        self.assertEqual(pygame.transform.average_color(target)[:3], (0, 0, 0))
        ui.clear_commands()
        ui.text("WWWWWWWW", (100, 100), ui.huge, (255, 255, 255))
        ui.render_commands(target, 2.0)
        self.assertGreater(sum(pygame.transform.average_color(target)[:3]), 0)
        ui.clear_commands()

    def test_shape_surface_is_cached(self):
        a = self.ui._shape_surface(40, 20, (10, 20, 30), None, 0, 4)
        b = self.ui._shape_surface(40, 20, (10, 20, 30), None, 0, 4)
        self.assertIs(a, b)

    def test_present_flushes_commands_and_fade_progresses(self):
        ui = self.ui
        ui.menu(0, True)
        self.assertEqual(ui._cmds, [])
        ui.start_fade()
        ui.menu(0, True)
        self.assertGreater(ui._fade_end, 0)
