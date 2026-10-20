"""Refined dark-fantasy retro RPG interface, HUD, lighting, and rendering for MazeQuest."""
from __future__ import annotations
import math
import time
from typing import Any, Dict, List, Optional, Tuple
import pygame

from display_manager import IW, IH, DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT, DisplayManager
from particles import ParticleSystem
from sound import SoundManager
from sprites import (
    C_VOID, C_STONE_DARK, C_STONE_MID, C_STONE_HI, C_STONE_RIM,
    C_GOLD_DARK, C_GOLD_MID, C_GOLD_HI, C_GOLD_LIGHT,
    C_CYAN_DEEP, C_CYAN_MID, C_CYAN_HI, C_CYAN_LIGHT,
    SpriteCache
)

WIDTH: int = DEFAULT_WINDOW_WIDTH
HEIGHT: int = DEFAULT_WINDOW_HEIGHT
FPS: int = 60

# Palette Tokens for UI
INK = (235, 230, 215)
MUTED = (145, 155, 165)
GOLD = (240, 185, 65)
CYAN = (90, 225, 245)
DARK = (10, 13, 18)
PANEL_BG = (17, 21, 28)
PANEL_BORDER = (90, 72, 44)
HOVER_BG = (35, 42, 54)


class UI:
    """Commercial-quality retro RPG user interface and renderer."""

    MENU_BUTTONS = ["ENTER THE DUNGEON", "CONTINUE", "SETTINGS", "STATISTICS", "QUIT"]
    PAUSE_OPTIONS = ["RESUME EXPEDITION", "RESTART LEVEL", "SETTINGS", "SAVE & MENU", "QUIT"]

    def __init__(self, screen: pygame.Surface, sound_mgr: Optional[SoundManager] = None, display_mgr: Optional[DisplayManager] = None) -> None:
        self.screen = screen
        self.display_mgr = display_mgr
        self.sound_mgr = sound_mgr or SoundManager()
        # Tests and screenshot tooling may construct UI before opening a
        # display; avoid requiring a display pixel format in that case.
        canvas = pygame.Surface((IW, IH))
        self.canvas = canvas.convert() if pygame.display.get_surface() else canvas
        self.sprites = SpriteCache(tile_w=18, tile_h=16)
        self.particles = ParticleSystem(max_particles=120)

        # Crisp font system
        self._init_fonts()

        # Timers and state tracking
        self.tick = 0
        self.last_time = time.monotonic()
        self.ambient_ember_timer = 0.0
        self.anim_time = 0.0
        self.last_player_pos = None

        # Interactive hitboxes (internal coordinates)
        self.menu_rects: List[Tuple[str, pygame.Rect]] = []
        self.result_rects: List[Tuple[str, pygame.Rect]] = []
        self.settings_rects: List[Tuple[str, pygame.Rect]] = []
        self.pause_rects: List[Tuple[str, pygame.Rect]] = []
        self.stats_rects: List[Tuple[str, pygame.Rect]] = []

        # In-game HUD hitboxes
        self.pause_btn_rect = pygame.Rect(565, 8, 65, 26)
        self.settings_btn_rect = pygame.Rect(500, 8, 58, 26)
        self.hint_btn_rect = pygame.Rect(565, IH - 36, 65, 26)
        self._pause_dim = pygame.Surface((IW, IH), pygame.SRCALPHA)
        self._pause_dim.fill((6, 8, 12, 175))

    def _init_fonts(self) -> None:
        """Initialize compact, crisp fonts with system fallbacks."""
        pygame.font.init()
        # Monospace faces keep counters aligned and read closer to a classic
        # pixel-game UI when rendered without antialiasing at the low canvas
        # resolution.
        font_names = ["dejavusansmono", "liberationmono", "monospace",
                      "liberationsans", "dejavusans", "notosans", "cantarell", "arial"]
        chosen = None
        for name in font_names:
            if name in pygame.font.get_fonts():
                chosen = name
                break

        def make_font(size: int, bold: bool = False) -> pygame.font.Font:
            if chosen:
                try:
                    return pygame.font.SysFont(chosen, size, bold=bold)
                except Exception:
                    pass
            return pygame.font.Font(None, size + 2)

        self.huge = make_font(38, bold=True)
        self.large = make_font(24, bold=True)
        self.title = make_font(20, bold=True)
        self.body = make_font(15, bold=False)
        self.body_bold = make_font(15, bold=True)
        self.small = make_font(13, bold=False)
        self.small_bold = make_font(13, bold=True)
        self.tiny = make_font(11, bold=False)

    def text(self, value: Any, pos: Tuple[int, int], font: Optional[pygame.font.Font] = None,
             color: Tuple[int, int, int] = INK, shadow: bool = True, center: bool = False) -> pygame.Rect:
        """Render antialiased crisp text with subtle drop shadow."""
        font = font or self.body
        val_str = str(value)
        # Render without antialiasing so system fonts share the game's crisp pixel scale.
        s = font.render(val_str, False, color)
        w, h = s.get_size()
        x, y = int(pos[0]), int(pos[1])
        if center:
            x -= w // 2
            y -= h // 2
        if shadow:
            sh = font.render(val_str, False, (8, 10, 14))
            self.canvas.blit(sh, (x + 1, y + 1))
        self.canvas.blit(s, (x, y))
        return pygame.Rect(x, y, w, h)

    def draw_panel(self, rect: pygame.Rect, title: str = "", subtitle: str = "") -> None:
        """Render an ornate dark-fantasy gothic stone frame with bronze beveling."""
        # Panel background
        pygame.draw.rect(self.canvas, PANEL_BG, rect)
        # Inner slate border
        pygame.draw.rect(self.canvas, (26, 32, 42), (rect.x + 2, rect.y + 2, rect.w - 4, rect.h - 4), 1)
        # Outer bronze/gold border
        pygame.draw.rect(self.canvas, PANEL_BORDER, rect, 2)
        # Decorative corner accents
        for cx, cy in [(rect.x, rect.y), (rect.right - 4, rect.y),
                       (rect.x, rect.bottom - 4), (rect.right - 4, rect.bottom - 4)]:
            pygame.draw.rect(self.canvas, C_GOLD_HI, (cx, cy, 4, 4))

        if title:
            self.text(title, (rect.centerx, rect.y + 20), self.large, GOLD, center=True)
        if subtitle:
            self.text(subtitle, (rect.centerx, rect.y + 40), self.small, MUTED, center=True)

    def draw_stone_frame(self, rect: pygame.Rect, fill: Tuple[int, int, int] = PANEL_BG,
                         accent: Tuple[int, int, int] = PANEL_BORDER) -> None:
        """Draw a compact pixel-stone frame with a readable inset bevel."""
        pygame.draw.rect(self.canvas, (8, 11, 16), rect)
        inner = rect.inflate(-2, -2)
        pygame.draw.rect(self.canvas, fill, inner)
        pygame.draw.line(self.canvas, (112, 119, 130),
                         (rect.x + 3, rect.y + 2), (rect.right - 4, rect.y + 2))
        pygame.draw.line(self.canvas, (56, 63, 75),
                         (rect.x + 2, rect.y + 3), (rect.x + 2, rect.bottom - 4))
        pygame.draw.line(self.canvas, (11, 14, 20),
                         (rect.x + 3, rect.bottom - 3), (rect.right - 3, rect.bottom - 3))
        pygame.draw.line(self.canvas, accent,
                         (rect.x + 4, rect.y + 1), (rect.right - 5, rect.y + 1))
        pygame.draw.rect(self.canvas, accent, rect, 1)
        for x, y in ((rect.x, rect.y), (rect.right - 3, rect.y),
                     (rect.x, rect.bottom - 3), (rect.right - 3, rect.bottom - 3)):
            pygame.draw.rect(self.canvas, C_GOLD_HI, (x, y, 3, 3))

    def draw_button(self, rect: pygame.Rect, label: str, active: bool = False,
                    hover: bool = False, hotkey: str = "", small: bool = False) -> None:
        """Render a gothic stone button with beveled edges and glow feedback."""
        bg_col = HOVER_BG if (active or hover) else (18, 22, 30)
        border_col = C_GOLD_HI if (active or hover) else (78, 68, 52)
        text_col = C_GOLD_LIGHT if (active or hover) else INK

        # Slight 1px press offset if active
        y_off = 1 if (active and not hover) else 0

        pygame.draw.rect(self.canvas, bg_col, (rect.x, rect.y + y_off, rect.w, rect.h))
        pygame.draw.rect(self.canvas, border_col, (rect.x, rect.y + y_off, rect.w, rect.h), 2 if (active or hover) else 1)
        pygame.draw.line(self.canvas, (45, 54, 70), (rect.x + 2, rect.y + 2 + y_off), (rect.right - 3, rect.y + 2 + y_off))

        # Text with cursor indicators
        btn_font = self.small_bold if small else self.body_bold
        prefix = "› " if (active or hover) else ""
        suffix = " ‹" if (active or hover) else ""
        display_text = f"{prefix}{label}{suffix}"
        self.text(display_text, (rect.centerx, rect.centery + y_off), btn_font, text_col, center=True)

        if hotkey:
            self.text(hotkey, (rect.right - 26, rect.centery + y_off), self.tiny, MUTED, center=True)

    def present(self) -> None:
        """Output the rendered canvas to the screen."""
        if self.display_mgr:
            self.display_mgr.present(self.canvas)
        else:
            scaled = pygame.transform.scale(self.canvas, self.screen.get_size())
            self.screen.blit(scaled, (0, 0))
            if pygame.display.get_surface():
                pygame.display.flip()
        self.tick += 1

    # -------------------------------------------------------------------------
    # MAIN MENU SCREEN
    # -------------------------------------------------------------------------
    def menu(self, selected: int = 0, can_continue: bool = False, mouse: Optional[Tuple[int, int]] = None) -> None:
        now = time.monotonic()
        dt = max(0.001, min(0.1, now - self.last_time))
        self.last_time = now

        self.canvas.fill((7, 9, 14))

        # Atmospheric crypt backdrop with stone arches and flagstones
        pygame.draw.rect(self.canvas, (18, 22, 30), (0, 160, IW, IH - 160))
        # Archway perspective
        pygame.draw.polygon(self.canvas, (28, 34, 44),
                            [(120, IH), (120, 180), (160, 120), (240, 80), (400, 80), (480, 120), (520, 180), (520, IH)])
        pygame.draw.polygon(self.canvas, (11, 14, 20),
                            [(150, IH), (150, 190), (180, 140), (250, 105), (390, 105), (460, 140), (490, 190), (490, IH)])

        # Floor flagstone perspective lines
        for x in range(0, IW + 40, 40):
            pygame.draw.line(self.canvas, (28, 32, 40), (x, 260), (x - 20, IH))
        for y in range(260, IH, 24):
            pygame.draw.line(self.canvas, (24, 28, 36), (0, y), (IW, y))

        # Animated torches flanking the sanctum
        torch_frame = (self.tick // 8) % 4
        torch_img = self.sprites.torch_frames[torch_frame]
        for tx, ty in [(155, 175), (485, 175), (280, 130), (360, 130)]:
            self.canvas.blit(self.sprites.glow_torch, (tx - 44, ty - 44), special_flags=pygame.BLEND_RGB_ADD)
            self.canvas.blit(torch_img, (tx - 9, ty - 10))
            if self.tick % 14 == 0:
                self.particles.emit_torch_embers(tx, ty - 6, count=1)

        # Update and draw ambient drifting embers
        self.particles.update(dt)
        self.particles.draw(self.canvas)

        # Grand title on a carved stone plaque.
        title_y = 38
        title_rect = pygame.Rect(IW // 2 - 174, 28, 348, 91)
        self.draw_stone_frame(title_rect, (14, 18, 25), (113, 82, 39))
        self.text("MAZEQUEST", (IW // 2 + 2, title_y + 2), self.huge, (66, 46, 25), center=True)
        self.text("MAZEQUEST", (IW // 2, title_y), self.huge, (245, 205, 110), center=True)
        self.text("THE FORGOTTEN CATACOMBS", (IW // 2, title_y + 36), self.small_bold, CYAN, center=True)
        pygame.draw.line(self.canvas, (105, 76, 38), (title_rect.x + 28, 98),
                         (title_rect.right - 28, 98))
        self.text("A DUNGEON OF STONE • LIGHT • AND LOST RELICS",
                  (IW // 2, 108), self.tiny, MUTED, center=True)

        # Menu Buttons
        labels = self.MENU_BUTTONS[:]
        if not can_continue:
            labels.remove("CONTINUE")

        self.menu_rects = []
        btn_w, btn_h = 240, 32
        start_y = 145
        gap_y = 39

        for i, label in enumerate(labels):
            bx = IW // 2 - btn_w // 2
            by = start_y + i * gap_y
            rect = pygame.Rect(bx, by, btn_w, btn_h)
            self.menu_rects.append((label, rect))

            hover = rect.collidepoint(mouse) if mouse else False
            active = (i == selected) or hover

            self.draw_button(rect, label, active=active, hover=hover)

        # Bottom instructions
        self.text("WASD / ARROWS   •   ENTER TO DESCEND   •   F11 FULLSCREEN",
                  (IW // 2, IH - 22), self.tiny, MUTED, center=True)
        self.present()

    def menu_hit(self, pos: Tuple[int, int]) -> Optional[str]:
        if pos[0] < 0 or pos[1] < 0:
            return None
        return next((label for label, rect in self.menu_rects if rect.collidepoint(pos)), None)

    # -------------------------------------------------------------------------
    # SETTINGS SCREEN
    # -------------------------------------------------------------------------
    def settings(self, settings_dict: Dict[str, Any], selected: int = 0, mouse: Optional[Tuple[int, int]] = None) -> None:
        self.canvas.fill((9, 12, 17))
        panel_rect = pygame.Rect(80, 35, IW - 160, IH - 70)
        self.draw_panel(panel_rect, "EXPEDITION SETTINGS", "Display, Audio, and Gameplay Configuration")

        is_fullscreen = settings_dict.get("fullscreen", False)
        sound_on = settings_dict.get("sound", True)
        hints_on = settings_dict.get("show_hints", True)

        if self.display_mgr and self.display_mgr.screen:
            display_size = self.display_mgr.screen.get_size() if is_fullscreen else self.display_mgr.window_size
        else:
            display_size = (DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        items = [
            ("DISPLAY MODE", f"FULLSCREEN {display_size[0]}x{display_size[1]}" if is_fullscreen else f"WINDOWED {display_size[0]}x{display_size[1]}"),
            ("ASPECT RATIO", "PIXEL-PERFECT 16:11"),
            ("SOUND EFFECTS", "ENABLED" if sound_on else "MUTED"),
            ("SHOW HINTS", "ENABLED" if hints_on else "DISABLED"),
            ("BACK TO MENU", "")
        ]

        self.settings_rects = []
        row_y = 115
        for i, (label, val) in enumerate(items):
            rect = pygame.Rect(panel_rect.x + 36, row_y + i * 42, panel_rect.w - 72, 34)
            self.settings_rects.append((label, rect))

            hover = rect.collidepoint(mouse) if mouse else False
            active = (i == selected) or hover

            if label == "BACK TO MENU":
                self.draw_button(rect, label, active=active, hover=hover)
            else:
                bg = HOVER_BG if active else (20, 24, 32)
                border = C_GOLD_HI if active else (50, 60, 74)
                pygame.draw.rect(self.canvas, bg, rect)
                pygame.draw.rect(self.canvas, border, rect, 2 if active else 1)
                self.text(f"› {label}" if active else f"  {label}", (rect.x + 14, rect.centery), self.body_bold, GOLD if active else INK, center=False)
                # Value badge aligned to right
                val_col = CYAN if "FULLSCREEN" in val or "ENABLED" in val else MUTED
                val_surf = self.small_bold.render(f"[{val}]", True, val_col)
                self.canvas.blit(val_surf, (rect.right - val_surf.get_width() - 14, rect.centery - val_surf.get_height() // 2))

        self.text("NAVIGATE: UP/DOWN / WASD   •   TOGGLE: ENTER / SPACE   •   ESC: BACK",
                  (IW // 2, panel_rect.bottom - 22), self.tiny, MUTED, center=True)
        self.present()

    def settings_hit(self, pos: Tuple[int, int]) -> Optional[str]:
        if pos[0] < 0 or pos[1] < 0:
            return None
        return next((label for label, rect in self.settings_rects if rect.collidepoint(pos)), None)

    # -------------------------------------------------------------------------
    # STATISTICS SCREEN
    # -------------------------------------------------------------------------
    def statistics(self, history: List[Dict[str, Any]], bests: Dict[str, Any], mouse: Optional[Tuple[int, int]] = None) -> None:
        self.canvas.fill((9, 12, 17))
        panel_rect = pygame.Rect(60, 30, IW - 120, IH - 60)
        self.draw_panel(panel_rect, "CATACOMB CHRONICLE", f"Total Expeditions Completed: {len(history)}")

        best = bests.get("1", {})
        best_time_str = f"{best['time']:.1f}s" if "time" in best else "—"
        best_moves_str = f"{best['moves']} moves" if "moves" in best else "—"
        relic_runs = sum(1 for run in history if run.get("treasures", 0) > 0)

        # Overview stat cards
        cards = [
            ("BEST ESCAPE TIME", best_time_str, CYAN),
            ("SHORTEST ATTEMPT", best_moves_str, GOLD),
            ("RELIC EXPEDITIONS", f"{relic_runs} successful", (100, 230, 160)),
            ("TOTAL EXPEDITIONS", str(len(history)), INK)
        ]

        card_w = (panel_rect.w - 56) // 2
        for i, (label, val, col) in enumerate(cards):
            cx = panel_rect.x + 24 + (i % 2) * (card_w + 8)
            cy = 105 + (i // 2) * 56
            r = pygame.Rect(cx, cy, card_w, 48)
            pygame.draw.rect(self.canvas, (22, 27, 36), r)
            pygame.draw.rect(self.canvas, (45, 54, 70), r, 1)
            self.text(label, (r.x + 12, r.y + 12), self.tiny, MUTED)
            self.text(val, (r.x + 12, r.y + 28), self.body_bold, col)

        # Recent runs ledger
        ledger_y = 230
        self.text("RECENT DELVES", (panel_rect.x + 24, ledger_y), self.small_bold, GOLD)
        pygame.draw.line(self.canvas, (55, 65, 80), (panel_rect.x + 24, ledger_y + 16), (panel_rect.right - 24, ledger_y + 16))

        recent = history[-4:] if history else []
        if not recent:
            self.text("No completed expeditions recorded yet. Enter the dungeon to begin.",
                      (panel_rect.x + 24, ledger_y + 34), self.small, MUTED)
        else:
            for idx, run in enumerate(reversed(recent)):
                ry = ledger_y + 26 + idx * 22
                t_str = f"{run.get('elapsed', 0):.1f}s"
                m_str = f"{run.get('moves', 0)} moves"
                tr_str = f"Relics: {run.get('treasures', 0)}/2"
                self.text(f"Delve #{len(history)-idx}", (panel_rect.x + 24, ry), self.tiny, INK)
                self.text(t_str, (panel_rect.x + 130, ry), self.tiny, CYAN)
                self.text(m_str, (panel_rect.x + 220, ry), self.tiny, GOLD)
                self.text(tr_str, (panel_rect.x + 320, ry), self.tiny, MUTED)

        # Back button
        back_rect = pygame.Rect(IW // 2 - 80, panel_rect.bottom - 42, 160, 28)
        self.stats_rects = [("RETURN TO MENU", back_rect)]
        hover = back_rect.collidepoint(mouse) if mouse else False
        self.draw_button(back_rect, "RETURN TO MENU", active=hover, hover=hover, small=True)

        self.present()

    def statistics_hit(self, pos: Tuple[int, int]) -> Optional[str]:
        if pos[0] < 0 or pos[1] < 0:
            return None
        return next((label for label, rect in self.stats_rects if rect.collidepoint(pos)), None)

    # -------------------------------------------------------------------------
    # IN-GAME DUNGEON VIEW
    # -------------------------------------------------------------------------
    def dungeon(self, game: Any, mouse: Optional[Tuple[int, int]] = None) -> None:
        now = time.monotonic()
        dt = max(0.001, min(0.1, now - self.last_time))
        self.last_time = now
        self.anim_time += dt

        self.canvas.fill((9, 12, 17))
        maze = game.maze
        tw, th = self.sprites.tw, self.sprites.th

        # Centering offsets
        ox = (IW - maze.cols * tw) // 2
        oy = 44 + (IH - 88 - maze.rows * th) // 2

        # 1. Floor pass. Unwalkable cells remain in the logical grid, but the
        # far side of a solid wall is void in the rendered world. Showing those
        # remote cells made the dungeon look like a square board instead of a
        # carved-out ruin.
        for r in range(maze.rows):
            for c in range(maze.cols):
                if maze.grid[r][c] != '#':
                    tile = self.sprites.get_floor_tile(r, c)
                    self.canvas.blit(tile, (ox + c * tw, oy + r * th))

        # 2. Footstep particle spawning on player movement
        player = game.animated_position
        cur_pos_discrete = (int(round(player[0])), int(round(player[1])))
        if self.last_player_pos is not None and cur_pos_discrete != self.last_player_pos:
            px = ox + cur_pos_discrete[1] * tw + tw // 2
            py = oy + cur_pos_discrete[0] * th + th - 2
            self.particles.emit_footstep(px, py)
            self.sound_mgr.play("step")
        self.last_player_pos = cur_pos_discrete

        # 3. Depth-Ordered Wall and Entity Pass
        torch_frame = int(self.anim_time * 7) % 4
        crystal_frame = int(self.anim_time * 5) % 4
        key_frame = int(self.anim_time * 5) % 4
        relic_frame = int(self.anim_time * 5) % 4

        for r in range(maze.rows):
            for c in range(maze.cols):
                x, y = ox + c * tw, oy + r * th
                p = (r, c)
                code = maze.grid[r][c]

                # Walls
                if code == '#':
                    is_south = (r + 1 < maze.rows and maze.grid[r + 1][c] != '#')
                    is_north = (r - 1 >= 0 and maze.grid[r - 1][c] != '#')
                    is_west = (c - 1 >= 0 and maze.grid[r][c - 1] != '#')
                    is_east = (c + 1 < maze.cols and maze.grid[r][c + 1] != '#')
                    # Render the wall skin that bounds a room or passage; skip
                    # bulk stone buried behind it so the dungeon silhouette
                    # meets the surrounding darkness cleanly.
                    if is_south or is_north or is_west or is_east:
                        self.sprites.draw_wall(self.canvas, x, y, r, c, is_south, is_north, is_west, is_east)

                # Dungeon Props
                if p in maze.torches:
                    self.canvas.blit(self.sprites.torch_frames[torch_frame], (x, y - 4))
                    if self.tick % 16 == (r + c) % 16:
                        self.particles.emit_torch_embers(x + 9, y - 2, count=1)

                if p in maze.crystals:
                    self.canvas.blit(self.sprites.crystal_frames[crystal_frame], (x, y - 4))
                    if self.tick % 24 == (r * 3 + c) % 24:
                        self.particles.emit_crystal_dust(x + 9, y + 4, count=1)

                if p in maze.treasures:
                    is_collected = (p in game.collected_treasures)
                    chest = self.sprites.chest_opened if is_collected else self.sprites.chest_closed
                    self.canvas.blit(chest, (x, y))

                if p in maze.keys:
                    if maze.keys[p] not in game.keys:
                        self.canvas.blit(self.sprites.key_frames[key_frame], (x, y))

                if p in maze.doors:
                    locked = (maze.doors[p] not in game.keys)
                    door_img = self.sprites.door_locked if locked else self.sprites.door_unlocked
                    self.canvas.blit(door_img, (x, y))

                if p == maze.goal:
                    self.canvas.blit(self.sprites.exit_pedestal, (x, y))
                    self.canvas.blit(self.sprites.relic_frames[relic_frame], (x, y - 2))

                if p == maze.entrance:
                    pygame.draw.rect(self.canvas, (32, 26, 22), (x + 3, y + 3, 12, 10))
                    pygame.draw.line(self.canvas, (55, 45, 38), (x + 3, y + 3), (x + 14, y + 3))

                if p == game.hint_position:
                    self.canvas.blit(self.sprites.glow_hint, (x + tw // 2 - 28, y + th // 2 - 28), special_flags=pygame.BLEND_RGB_ADD)
                    pygame.draw.rect(self.canvas, CYAN, (x + 3, y + 2, tw - 6, th - 4), 1)

        # 4. Smooth Lighting Glow Pass
        # Torches
        for r, c in maze.torches:
            tx, ty = ox + c * tw + tw // 2, oy + r * th + th // 2
            # Subtle flicker pulse
            flicker = 1.0 + 0.08 * math.sin(self.anim_time * 8 + r * 3 + c * 5)
            self.canvas.blit(self.sprites.glow_torch, (tx - 44, ty - 44), special_flags=pygame.BLEND_RGB_ADD)

        # Crystals
        for r, c in maze.crystals:
            cx, cy = ox + c * tw + tw // 2, oy + r * th + th // 2
            self.canvas.blit(self.sprites.glow_crystal, (cx - 38, cy - 38), special_flags=pygame.BLEND_RGB_ADD)

        # Goal Relic
        gx, gy = ox + maze.goal[1] * tw + tw // 2, oy + maze.goal[0] * th + th // 2
        self.canvas.blit(self.sprites.glow_exit, (gx - 36, gy - 36), special_flags=pygame.BLEND_RGB_ADD)

        # Player soft lantern light
        px = ox + int(player[1] * tw + tw // 2)
        py = oy + int(player[0] * th + th // 2)
        self.canvas.blit(self.sprites.glow_player, (px - 22, py - 22), special_flags=pygame.BLEND_RGB_ADD)

        # Place the adventurer after light compositing so nearby torch glow
        # cannot wash out the hood, face, and lantern pixels.
        self._draw_hero(game, ox, oy, tw, th)

        # 5. Route Trails (BFS Shortest Path or Player Path)
        if game.show_optimal_route or game.show_actual_route:
            self._draw_routes(game, ox, oy, tw, th)

        # 6. Particles Pass
        self.particles.update(dt)
        self.particles.draw(self.canvas)

        # 7. In-Game HUD Pass
        self._draw_hud(game, mouse)

        # 8. Pause Modal (if active)
        if game.paused:
            self._draw_pause_overlay(game, mouse)

        self.present()

    def _draw_hero(self, game: Any, ox: int, oy: int, tw: int, th: int) -> None:
        """Render the hero with directional walk/idle animations."""
        player = game.animated_position
        x = ox + player[1] * tw + (tw - 18) // 2
        y = oy + player[0] * th + th - 22

        dr, dc = game.facing
        if dr < 0:
            dir_name = "up"
        elif dr > 0:
            dir_name = "down"
        elif dc < 0:
            dir_name = "left"
        else:
            dir_name = "right"

        is_moving = (time.monotonic() - game.movement_started < 0.22)
        if is_moving:
            step_frame = int(self.anim_time * 9) % 4
            sprite = self.sprites.hero_walk[dir_name][step_frame]
        else:
            idle_frame = int(self.anim_time * 2.5) % 2
            sprite = self.sprites.hero_idle[dir_name][idle_frame]

        self.canvas.blit(sprite, (int(x), int(y)))

    def _draw_routes(self, game: Any, ox: int, oy: int, tw: int, th: int) -> None:
        """Draw optimal BFS energy path and/or player actual path."""
        if game.show_actual_route:
            # Player actual trail in subtle magenta/violet
            actual = game.stats.actual_route
            for idx in range(len(actual) - 1):
                p1, p2 = actual[idx], actual[idx + 1]
                x1, y1 = ox + p1[1] * tw + tw // 2, oy + p1[0] * th + th // 2
                x2, y2 = ox + p2[1] * tw + tw // 2, oy + p2[0] * th + th // 2
                pygame.draw.line(self.canvas, (180, 85, 170), (x1, y1), (x2, y2), 2)

        if game.show_optimal_route:
            # Energetic glowing cyan pulse along BFS route
            route = game.stats.optimal_route
            pulse_progress = (self.tick % 75) / 75.0
            pulse_idx = int(pulse_progress * len(route))

            for idx in range(len(route) - 1):
                p1, p2 = route[idx], route[idx + 1]
                x1, y1 = ox + p1[1] * tw + tw // 2, oy + p1[0] * th + th // 2
                x2, y2 = ox + p2[1] * tw + tw // 2, oy + p2[0] * th + th // 2
                pygame.draw.line(self.canvas, (35, 140, 175), (x1, y1), (x2, y2), 3)
                pygame.draw.line(self.canvas, C_CYAN_HI, (x1, y1), (x2, y2), 1)

            # Pulsing energy dot traveling along the path
            if 0 <= pulse_idx < len(route):
                pp = route[pulse_idx]
                px, py = ox + pp[1] * tw + tw // 2, oy + pp[0] * th + th // 2
                pygame.draw.circle(self.canvas, C_CYAN_LIGHT, (px, py), 4)

            # On-screen route banner
            banner_rect = pygame.Rect(IW // 2 - 170, 48, 340, 22)
            pygame.draw.rect(self.canvas, (12, 16, 24), banner_rect)
            pygame.draw.rect(self.canvas, CYAN, banner_rect, 1)
            self.text(f"OPTIMAL BFS ROUTE: {len(route)-1} STEPS   [V] EXIT VIEW",
                      (IW // 2, 59), self.tiny, CYAN, center=True)

    def _draw_hud(self, game: Any, mouse: Optional[Tuple[int, int]] = None) -> None:
        """Render the upper and lower retro RPG HUD panels."""
        # Top Header Bar
        top_h = 42
        self.draw_stone_frame(pygame.Rect(8, 6, IW - 16, top_h - 8),
                              (17, 21, 28), (96, 73, 40))

        # Title / Level Name
        self.text("THE FORGOTTEN CATACOMBS", (18, 10), self.small_bold, GOLD)
        self.text("LEVEL 1  /  SANCTUM ROUTE", (18, 25), self.tiny, MUTED)

        # Elapsed Timer (Hourglass icon)
        self.canvas.blit(self.sprites.icons["hourglass"], (235, 11))
        m = int(game.elapsed // 60)
        s = int(game.elapsed % 60)
        time_color = GOLD if game.remaining < 30 else INK
        self.text(f"TIME  {m:02d}:{s:02d}", (257, 14), self.small_bold, time_color)

        # Move Counter (Boot icon)
        self.canvas.blit(self.sprites.icons["boot"], (390, 11))
        self.text(f"MOVES  {game.stats.moves:03d}", (412, 14), self.small_bold, INK)

        # Pause Button
        pause_hover = self.pause_btn_rect.collidepoint(mouse) if mouse else False
        settings_hover = self.settings_btn_rect.collidepoint(mouse) if mouse else False
        self.draw_button(self.settings_btn_rect, "SET", active=settings_hover, hover=settings_hover, small=True)
        pause_hover = self.pause_btn_rect.collidepoint(mouse) if mouse else False
        self.draw_button(self.pause_btn_rect, "PAUSE", active=pause_hover, hover=pause_hover, small=True)

        # Bottom Footer Bar
        bot_h = 42
        bot_y = IH - bot_h
        self.draw_stone_frame(pygame.Rect(8, bot_y + 3, IW - 16, bot_h - 7),
                              (17, 21, 28), (96, 73, 40))

        # Key Status
        has_key = bool(game.keys)
        key_icon = self.sprites.icons["key_found"] if has_key else self.sprites.icons["key_missing"]
        self.canvas.blit(key_icon, (18, bot_y + 11))
        key_label = "KEY ACQUIRED" if has_key else "KEY MISSING"
        self.text(key_label, (40, bot_y + 14), self.tiny, GOLD if has_key else MUTED)

        # Relic / Treasure Count
        self.canvas.blit(self.sprites.icons["relic"], (168, bot_y + 11))
        self.text(f"RELICS {game.stats.treasures}/2", (190, bot_y + 14), self.tiny, (110, 230, 160) if game.stats.treasures == 2 else INK)

        # Narrative Message Ticker
        msg = game.current_message
        msg_col = CYAN if ("key" in msg.lower() or "gate" in msg.lower()) else INK
        msg_rect = pygame.Rect(300, bot_y + 8, 240, 26)
        self.draw_stone_frame(msg_rect, (12, 16, 22), (35, 52, 62))
        self.text(msg, (msg_rect.centerx, msg_rect.centery), self.tiny, msg_col, center=True)

        # Hint Button
        hint_hover = self.hint_btn_rect.collidepoint(mouse) if mouse else False
        self.draw_button(self.hint_btn_rect, "HINT", active=hint_hover, hover=hint_hover, small=True)

    def _draw_pause_overlay(self, game: Any, mouse: Optional[Tuple[int, int]] = None) -> None:
        """Render the modal pause dialog."""
        # Dim backdrop
        self.canvas.blit(self._pause_dim, (0, 0))

        # Ornate modal box
        box_w, box_h = 320, 230
        box_x = IW // 2 - box_w // 2
        box_y = IH // 2 - box_h // 2
        modal_rect = pygame.Rect(box_x, box_y, box_w, box_h)
        self.draw_panel(modal_rect, "EXPEDITION PAUSED", "Select an Action to Proceed")

        self.pause_rects = []
        btn_w, btn_h = 240, 28
        start_y = box_y + 64
        gap_y = 32

        for i, opt in enumerate(self.PAUSE_OPTIONS):
            bx = IW // 2 - btn_w // 2
            by = start_y + i * gap_y
            rect = pygame.Rect(bx, by, btn_w, btn_h)
            self.pause_rects.append((opt, rect))

            hover = rect.collidepoint(mouse) if mouse else False
            active = (i == game.pause_selected) or hover
            self.draw_button(rect, opt, active=active, hover=hover, small=True)

    def game_hit(self, pos: Tuple[int, int]) -> Optional[str]:
        if pos[0] < 0 or pos[1] < 0:
            return None
        if self.hint_btn_rect.collidepoint(pos):
            return "HINT"
        if self.pause_btn_rect.collidepoint(pos):
            return "PAUSE"
        if self.settings_btn_rect.collidepoint(pos):
            return "SETTINGS"
        return None

    def pause_hit(self, pos: Tuple[int, int]) -> Optional[str]:
        if pos[0] < 0 or pos[1] < 0:
            return None
        return next((opt for opt, rect in self.pause_rects if rect.collidepoint(pos)), None)

    # -------------------------------------------------------------------------
    # LEVEL RESULTS SCREEN
    # -------------------------------------------------------------------------
    def results(self, game: Any, mouse: Optional[Tuple[int, int]] = None) -> None:
        self.canvas.fill((9, 12, 17))
        panel_rect = pygame.Rect(60, 25, IW - 120, IH - 50)
        title = "ANCIENT RELIC CLAIMED!" if game.won else "EXPEDITION LOST IN THE DARK"
        sub = "The Forgotten Catacombs — Sanctum Breached" if game.won else "The ancient depths have claimed another soul."
        self.draw_panel(panel_rect, title, sub)

        s = game.stats
        detour = max(0, s.moves - s.optimal_moves)
        efficiency = "S" if detour <= 2 else "A" if detour <= 8 else "B" if detour <= 16 else "C"

        # Stat cards
        stats_data = [
            ("EXPEDITION TIME", f"{game.elapsed:.1f} seconds", CYAN),
            ("SUCCESSFUL STEPS", f"{s.moves} moves", INK),
            ("SHORTEST BFS ROUTE", f"{s.optimal_moves} moves", GOLD),
            ("EXPLORATION DETOUR", f"+{detour} moves", (240, 140, 100) if detour > 10 else INK),
            ("RELICS RECOVERED", f"{s.treasures} / 2 found", (100, 230, 160)),
            ("EXPEDITION RANK", f"RANK {efficiency}", GOLD if efficiency in ('S', 'A') else INK)
        ]

        card_w = (panel_rect.w - 56) // 2
        for idx, (label, val, col) in enumerate(stats_data):
            cx = panel_rect.x + 24 + (idx % 2) * (card_w + 8)
            cy = 88 + (idx // 2) * 44
            r = pygame.Rect(cx, cy, card_w, 38)
            pygame.draw.rect(self.canvas, (22, 27, 36), r)
            pygame.draw.rect(self.canvas, (45, 54, 70), r, 1)
            self.text(label, (r.x + 10, r.y + 8), self.tiny, MUTED)
            self.text(val, (r.x + 10, r.y + 22), self.small_bold, col)

        # Graphical Comparison Bar
        bar_y = 232
        self.text("PATH EFFICIENCY COMPARISON", (panel_rect.x + 24, bar_y), self.tiny, MUTED)
        bar_w = panel_rect.w - 48

        # BFS base bar
        pygame.draw.rect(self.canvas, (25, 32, 42), (panel_rect.x + 24, bar_y + 16, bar_w, 14))
        # Optimal fill
        opt_w = min(bar_w, int(bar_w * (s.optimal_moves / max(1, s.moves))))
        pygame.draw.rect(self.canvas, (35, 140, 175), (panel_rect.x + 24, bar_y + 16, opt_w, 14))
        # Actual moves bar
        pygame.draw.rect(self.canvas, (180, 85, 170), (panel_rect.x + 24 + opt_w, bar_y + 16, bar_w - opt_w, 14))
        self.text(f"BFS OPTIMAL: {s.optimal_moves}", (panel_rect.x + 28, bar_y + 18), self.tiny, (220, 255, 255))
        if detour > 0:
            self.text(f"DETOUR: +{detour}", (panel_rect.right - 100, bar_y + 18), self.tiny, (255, 220, 240))

        # Action Buttons
        self.result_rects = []
        actions = [("VIEW OPTIMAL PATH", 160), ("PLAY AGAIN", 130), ("RETURN TO MENU", 140)]
        total_w = sum(w for _, w in actions) + 20
        start_x = IW // 2 - total_w // 2
        btn_y = panel_rect.bottom - 46

        curr_x = start_x
        for label, w in actions:
            r = pygame.Rect(curr_x, btn_y, w, 30)
            self.result_rects.append((label, r))
            hover = r.collidepoint(mouse) if mouse else False
            self.draw_button(r, label, active=hover, hover=hover, small=True)
            curr_x += w + 10

        self.present()

    def result_hit(self, pos: Tuple[int, int]) -> Optional[str]:
        if pos[0] < 0 or pos[1] < 0:
            return None
        return next((label for label, rect in self.result_rects if rect.collidepoint(pos)), None)
