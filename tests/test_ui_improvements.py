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

    def test_text_colours_meet_contrast(self):
        from widgets import (contrast, INK, MUTED, GOLD, CYAN, GREEN, RED, ORANGE, GOLD_LIGHT,
                             PANEL_FILL, BTN_FILL, BTN_LIT, DARK)
        for col in (INK, MUTED, GOLD, CYAN, GREEN, RED, ORANGE):
            for bg in (PANEL_FILL, BTN_FILL, DARK, (28, 34, 50)):
                self.assertGreaterEqual(contrast(col, bg), 4.5, (col, bg))
        self.assertGreaterEqual(contrast(GOLD_LIGHT, BTN_LIT), 4.5)

    def test_fonts_snap_to_eight_pixel_grid(self):
        for face in (self.ui.huge, self.ui.body, self.ui.small):
            for scale in (1, 1.5, 2, 2.37, 3):
                px = face.px_for(scale)
                self.assertEqual(px % 8, 0)
                self.assertGreaterEqual(px, 8)

    def test_widgets_render_hard_edged_pixels(self):
        target = pygame.Surface((1280, 880))
        target.fill((0, 0, 0))
        ui = self.ui
        ui.clear_commands()
        ui.draw_button(pygame.Rect(100, 100, 200, 30), "PLAY", active=True)
        ui.render_commands(target, 2.0)
        ui.clear_commands()
        colours = {tuple(target.get_at((x, y))[:3]) for x in range(180, 640) for y in range(180, 280)}
        self.assertLess(len(colours), 24)      # flat fills and bevels only: no gradients or anti-aliasing

    def test_wrap_text_stays_inside_box(self):
        lines = self.ui.wrap_text("The sealed passage requires the catacomb key to open", self.ui.small, 120, 2)
        self.assertLessEqual(len(lines), 2)
        for line in lines:
            self.assertLessEqual(self.ui.small.size(line)[0], 120)

    def test_end_scene_draws_both_variants(self):
        from end_scene import EndScene
        canvas = pygame.Surface((640, 440))
        scene = EndScene()
        for won in (True, False, True):
            scene.draw(canvas, 1.0, 0.016, won)
            self.assertGreater(sum(pygame.transform.average_color(canvas)[:3]), 0)

    def test_results_reveal_animation_restarts_on_entry(self):
        game = Game(Maze.handcrafted(), 1, 900)
        game.stats.completed = True
        game.position = game.maze.goal
        self.ui.results(game, None, 0, True)
        first = self.ui._results_t0
        self.ui.results(game, None, 0, True)
        self.assertEqual(self.ui._results_t0, first)          # same visit keeps animating
        self.ui.anim_time += 5
        self.ui.results(game, None, 0, True)
        self.assertGreater(self.ui._results_t0, first)        # re-entering replays the reveal

    def test_decor_is_deterministic_and_never_on_special_cells(self):
        from decor import build_decor
        maze = Maze.handcrafted()
        a, b = build_decor(maze), build_decor(maze)
        self.assertEqual(a.floor_decals, b.floor_decals)
        self.assertEqual(a.wall_decor, b.wall_decor)
        special = {maze.start, maze.goal, maze.entrance, *maze.keys, *maze.doors, *maze.treasures,
                   *maze.torches, *maze.crystals, *maze.runes}
        for pos, name, _ in a.floor_decals:
            self.assertNotIn(pos, special, name)
            self.assertNotEqual(maze.grid[pos[0]][pos[1]], "#")
        for (r, c), name in a.wall_decor.items():
            self.assertEqual(maze.grid[r][c], "#")
            self.assertNotEqual(maze.grid[r + 1][c], "#")        # only wall faces get overlays
        self.assertTrue(a.candles and a.drip_points and a.carpet)

    def test_line_of_sight_stops_at_walls(self):
        maze = Maze.handcrafted()
        ui = self.ui
        self.assertTrue(ui._clear_line(maze, (15, 3), (15, 3)))
        self.assertTrue(ui._clear_line(maze, (13, 3), (16, 3)))        # open crypt
        self.assertFalse(ui._clear_line(maze, (15, 3), (5, 11)))       # through solid rock
        vis = ui._visible_cells(maze, (15, 3), 6)
        self.assertIn((15, 3), vis)
        self.assertNotIn((5, 11), vis)

    def test_pickups_spawn_popups_and_animations(self):
        game = Game(Maze.handcrafted(), 1, 900)
        ui = self.ui
        ui._tracked = None
        ui.dungeon(game)
        self.assertEqual(ui._popups, [])
        game.keys.add("catacomb")
        treasure = next(iter(game.maze.treasures))
        game.collected_treasures.add(treasure)
        ui.dungeon(game)
        texts = [p[0] for p in ui._popups]
        self.assertIn("+KEY", texts)
        self.assertIn("GATE OPEN", texts)
        self.assertTrue(any(t.startswith("+") and t[1:].isdigit() for t in texts))
        self.assertIn(treasure, ui._chest_t)
        self.assertIsNotNone(ui._door_t)

    def test_bump_and_footprints_are_tracked(self):
        ui = self.ui
        ui.bump(0, 1)
        self.assertEqual(ui._bump[:2], (0, 1))
        before = len(ui._prints)
        ui.footstep(Maze.handcrafted(), 15, 3)
        self.assertEqual(len(ui._prints), before + 1)

    def test_fog_of_war_hides_unexplored_cells(self):
        game = Game(Maze.handcrafted(), 1, 900)
        ui = self.ui
        ui._tracked = None
        ui.fog_enabled = True
        try:
            ui.dungeon(game)
            ui.dungeon(game)
            self.assertIn(game.position, ui._seen)
            self.assertNotIn(game.maze.goal, ui._seen)               # far room stays unexplored
        finally:
            ui.fog_enabled = False

    def test_present_flushes_commands_and_fade_progresses(self):
        ui = self.ui
        ui.menu(0, True)
        self.assertEqual(ui._cmds, [])
        ui.start_fade()
        ui.menu(0, True)
        self.assertGreater(ui._fade_end, 0)
