"""Comprehensive tests for DisplayManager, letterboxing, coordinate mapping, UI, and particles."""
import unittest
import pygame
from display_manager import DisplayManager, IW, IH
from particles import ParticleSystem, Particle
from sound import SoundManager
from ui import UI
from maze import Maze
from game_logic import Game


class TestDisplayAndLetterboxing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_display_manager_viewport_calculation_16_9(self):
        dm = DisplayManager(fullscreen=False, window_size=(1920, 1080))
        # Mock screen surface
        dm.screen = pygame.Surface((1920, 1080))
        dm.update_viewport()

        # Pixel-perfect rendering uses the largest whole-number scale that fits.
        self.assertEqual(dm.scale, 2)
        self.assertEqual(dm.viewport_rect.size, (IW * 2, IH * 2))
        self.assertAlmostEqual(dm.viewport_rect.width / dm.viewport_rect.height, IW / IH, delta=0.01)
        self.assertGreater(dm.viewport_rect.x, 0)
        self.assertGreater(dm.viewport_rect.y, 0)

        # Coordinate mapping inside viewport
        mid_screen = (dm.viewport_rect.centerx, dm.viewport_rect.centery)
        internal_pos = dm.screen_to_internal(mid_screen)
        self.assertAlmostEqual(internal_pos[0], IW // 2, delta=2)
        self.assertAlmostEqual(internal_pos[1], IH // 2, delta=2)

        # Clicks outside viewport (in pillarbox margins)
        margin_click = (10, 540)
        self.assertEqual(dm.screen_to_internal(margin_click), (-1, -1))

    def test_display_manager_viewport_calculation_4_3(self):
        dm = DisplayManager(fullscreen=False, window_size=(1024, 768))
        dm.screen = pygame.Surface((1024, 768))
        dm.update_viewport()

        self.assertEqual(dm.scale, 1)
        self.assertEqual(dm.viewport_rect.size, (IW, IH))
        self.assertAlmostEqual(dm.viewport_rect.width / dm.viewport_rect.height, IW / IH, delta=0.01)
        self.assertGreater(dm.viewport_rect.x, 0)
        self.assertGreater(dm.viewport_rect.y, 0)

        # Top margin click
        self.assertEqual(dm.screen_to_internal((512, 10)), (-1, -1))

    def test_fullscreen_toggle_state(self):
        dm = DisplayManager(fullscreen=False, window_size=(1100, 760))
        self.assertFalse(dm.is_fullscreen)
        # Mock screen
        dm.screen = pygame.Surface((1100, 760))
        # Toggle to fullscreen
        dm.set_fullscreen(True)
        self.assertTrue(dm.is_fullscreen)
        # Toggle back to windowed
        dm.set_fullscreen(False)
        self.assertFalse(dm.is_fullscreen)


class TestParticleSystem(unittest.TestCase):
    def test_particle_lifecycle_and_emission(self):
        ps = ParticleSystem(max_particles=50)
        self.assertEqual(len(ps.particles), 0)

        ps.emit_torch_embers(100, 100, count=4)
        self.assertEqual(len(ps.particles), 4)

        ps.emit_pickup_burst(100, 100, count=10)
        self.assertEqual(len(ps.particles), 14)

        # Update advances life
        ps.update(0.1)
        self.assertTrue(all(p.life < p.max_life for p in ps.particles))

        # Full expiration
        ps.update(3.0)
        self.assertEqual(len(ps.particles), 0)


class TestSoundManagerGracefulFallback(unittest.TestCase):
    def test_sound_manager_does_not_crash(self):
        sm = SoundManager(enabled=True)
        # These should run cleanly even if no audio hardware is attached
        sm.play("click")
        sm.play("step")
        sm.play("pickup")
        sm.play("key")
        sm.play("unlock")
        sm.play("bump")
        sm.play("win")

        # When disabled, plays nothing
        sm.enabled = False
        sm.play("click")


class TestUIRenderingAndHitDetection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.screen = pygame.Surface((1100, 760))
        cls.ui = UI(cls.screen)
        cls.game = Game(Maze.handcrafted(), 1, 900)

    def test_menu_hitboxes(self):
        self.ui.menu(0, can_continue=True)
        self.assertTrue(len(self.ui.menu_rects) >= 4)
        enter_rect = next(rect for label, rect in self.ui.menu_rects if label == "ENTER THE DUNGEON")
        self.assertEqual(self.ui.menu_hit((enter_rect.centerx, enter_rect.centery)), "ENTER THE DUNGEON")
        self.assertIsNone(self.ui.menu_hit((-1, -1)))

    def test_hud_hitboxes(self):
        self.ui.dungeon(self.game)
        pause_pos = (self.ui.pause_btn_rect.centerx, self.ui.pause_btn_rect.centery)
        self.assertEqual(self.ui.game_hit(pause_pos), "PAUSE")
        settings_pos = (self.ui.settings_btn_rect.centerx, self.ui.settings_btn_rect.centery)
        self.assertEqual(self.ui.game_hit(settings_pos), "SETTINGS")
        hint_pos = (self.ui.hint_btn_rect.centerx, self.ui.hint_btn_rect.centery)
        self.assertEqual(self.ui.game_hit(hint_pos), "HINT")

    def test_settings_hitboxes(self):
        settings = {"fullscreen": False, "sound": True, "show_hints": True}
        self.ui.settings(settings, selected=0)
        disp_rect = next(rect for label, rect in self.ui.settings_rects if label == "DISPLAY MODE")
        self.assertEqual(self.ui.settings_hit((disp_rect.centerx, disp_rect.centery)), "DISPLAY MODE")

    def test_results_hitboxes(self):
        self.ui.results(self.game)
        play_rect = next(rect for label, rect in self.ui.result_rects if label == "PLAY AGAIN")
        self.assertEqual(self.ui.result_hit((play_rect.centerx, play_rect.centery)), "PLAY AGAIN")


if __name__ == "__main__":
    unittest.main()
