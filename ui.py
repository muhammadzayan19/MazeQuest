"""Dark-fantasy RPG screens, HUD, lighting and dungeon rendering for MazeQuest.

The pixel-art world is drawn on a 640x440 canvas. Everything else (text, panels,
buttons, bars) is queued as hi-res commands by ``widgets.Painter`` and rendered at
the window's native resolution, so the interface stays smooth at any size."""
from __future__ import annotations
import math
import time
from typing import Any, Dict, List, Optional, Tuple
import pygame

from display_manager import IW, IH, DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT, DisplayManager
from maze import LEVELS, Maze
from particles import ParticleSystem
from sound import SoundManager
from sprites import C_GOLD_HI, C_CYAN_HI, C_CYAN_LIGHT, SpriteCache
from widgets import INK, MUTED, GOLD, CYAN, GREEN, RED, PANEL_BORDER, Painter

WIDTH: int = DEFAULT_WINDOW_WIDTH
HEIGHT: int = DEFAULT_WINDOW_HEIGHT
FPS: int = 60

TILE_W, TILE_H = 18, 16
HINT_COOLDOWN = 3.0          # seconds between hints (enforced by main)
FADE_SECONDS = 0.25
LEGEND_SECONDS = 8.0
LOW_TIME_SECONDS = 30

SCALING_LABELS = {"smooth": "SMOOTH", "integer": "SHARP PIXELS", "fit": "SHARP FILL"}

RANKS = {
    "S": ("FLAWLESS DELVER", "Barely a step wasted."),
    "A": ("SEASONED EXPLORER", "You know these halls well."),
    "B": ("CAREFUL WANDERER", "A few detours, but you made it."),
    "C": ("LOST IN THE DARK", "The catacombs nearly swallowed you."),
}


class UI(Painter):
    """Renders every screen: world on the pixel canvas, interface as hi-res commands."""

    MENU_BUTTONS = ["ENTER THE DUNGEON", "CONTINUE", "SETTINGS", "STATISTICS", "QUIT"]
    PAUSE_OPTIONS = ["RESUME EXPEDITION", "RESTART LEVEL", "SETTINGS", "SAVE & MENU", "QUIT"]
    RESULT_ACTIONS = [("VIEW OPTIMAL PATH", 168), ("PLAY AGAIN", 128), ("RETURN TO MENU", 148)]

    def __init__(self, screen: pygame.Surface, sound_mgr: Optional[SoundManager] = None,
                 display_mgr: Optional[DisplayManager] = None) -> None:
        self.screen = screen
        self.display_mgr = display_mgr
        self.sound_mgr = sound_mgr or SoundManager()
        # Tests and screenshot tooling may construct UI before opening a
        # display; avoid requiring a display pixel format in that case.
        canvas = pygame.Surface((IW, IH))
        super().__init__(canvas.convert() if pygame.display.get_surface() else canvas)
        self.sprites = SpriteCache(tile_w=TILE_W, tile_h=TILE_H)
        self.particles = ParticleSystem(max_particles=120)

        # Timers and state tracking
        self.tick = 0
        self.last_time = time.monotonic()
        self.anim_time = 0.0
        self._ember_clock = 0.0
        self._crystal_clock = 0.0
        self._ember_rr = 0
        self._crystal_rr = 0

        # Settings-driven state (main keeps these current)
        self.hints_enabled = True
        self.hint_cooldown = 0.0

        # Interactive hitboxes (internal coordinates)
        self.menu_rects: List[Tuple[str, pygame.Rect]] = []
        self.result_rects: List[Tuple[str, pygame.Rect]] = []
        self.settings_rects: List[Tuple[str, pygame.Rect]] = []
        self.pause_rects: List[Tuple[str, pygame.Rect]] = []
        self.stats_rects: List[Tuple[str, pygame.Rect]] = []
        self.volume_track = pygame.Rect(0, 0, 0, 0)

        # In-game HUD hitboxes
        self.pause_btn_rect = pygame.Rect(565, 9, 65, 26)
        self.settings_btn_rect = pygame.Rect(488, 9, 70, 26)
        self.hint_btn_rect = pygame.Rect(565, IH - 36, 65, 26)

        # Cached overlays / layers
        self._vignette = self._build_vignette((200, 30, 20), 150, 28)
        self._edge_shade = self._build_vignette((0, 0, 0), 110, 46)
        self._fade_end = 0.0
        self._torch_glows = self._build_torch_glows()
        self._static_maze: Optional[Maze] = None
        self._static_layer: Optional[pygame.Surface] = None
        self._props: List[Tuple[int, int]] = []
        self._legend_game: Any = None
        self._legend_t0 = 0.0

    # ------------------------------------------------------------ construction
    @staticmethod
    def _build_vignette(color: Tuple[int, int, int], peak: int, depth: int) -> pygame.Surface:
        """Soft screen-edge shading (alpha falls off quadratically towards the centre)."""
        surf = pygame.Surface((IW, IH), pygame.SRCALPHA)
        for i in range(depth):
            alpha = int(peak * (1 - i / depth) ** 2)
            pygame.draw.rect(surf, (*color, alpha), (i, i, IW - 2 * i, IH - 2 * i), 1)
        return surf

    def _build_torch_glows(self) -> List[pygame.Surface]:
        """Pre-dimmed copies of the torch glow so torches can flicker cheaply."""
        glows = []
        for k in range(6):
            level = int(255 * (0.74 + 0.26 * k / 5))
            g = self.sprites.glow_torch.copy()
            g.fill((level, level, level), special_flags=pygame.BLEND_RGB_MULT)
            glows.append(g)
        return glows

    # --------------------------------------------------------------- geometry
    def maze_origin(self, maze: Maze) -> Tuple[int, int]:
        """Top-left canvas pixel of the maze, centred between the HUD bars."""
        return ((IW - maze.cols * TILE_W) // 2, 44 + (IH - 88 - maze.rows * TILE_H) // 2)

    def cell_center(self, maze: Maze, r: float, c: float) -> Tuple[int, int]:
        ox, oy = self.maze_origin(maze)
        return (ox + int(c * TILE_W + TILE_W // 2), oy + int(r * TILE_H + TILE_H // 2))

    # ---------------------------------------------------------- feedback hooks
    def footstep(self, maze: Maze, r: int, c: int) -> None:
        """Dust puff at the feet of a cell the hero just left."""
        ox, oy = self.maze_origin(maze)
        self.particles.emit_footstep(ox + c * TILE_W + TILE_W // 2, oy + r * TILE_H + TILE_H - 2)

    def pickup_burst(self, maze: Maze, r: int, c: int, count: int = 20) -> None:
        x, y = self.cell_center(maze, r, c)
        self.particles.emit_pickup_burst(x, y, count=count)

    def start_fade(self) -> None:
        """Fade in from black (called on screen changes)."""
        self._fade_end = self.anim_time + FADE_SECONDS

    def _begin_frame(self, fill: Tuple[int, int, int] = (9, 12, 17)) -> None:
        self.clear_commands()
        self.canvas.fill(fill)

    def present(self) -> None:
        """Scale the world, draw the queued hi-res interface over it, and show the frame."""
        fade = self._fade_end - self.anim_time
        if fade > 0:
            self.dim((0, 0, 0, int(255 * min(1.0, fade / FADE_SECONDS))))
        if self.display_mgr:
            self.display_mgr.present(self.canvas, self.render_commands)
        else:
            size = self.screen.get_size()
            try:
                scaled = pygame.transform.smoothscale(self.canvas, size)
            except ValueError:
                scaled = pygame.transform.scale(self.canvas, size)
            self.render_commands(scaled, size[0] / IW)
            self.screen.blit(scaled, (0, 0))
            if pygame.display.get_surface():
                pygame.display.flip()
        self.clear_commands()
        self.tick += 1

    def _step_clock(self) -> float:
        now = time.monotonic()
        dt = max(0.001, min(0.1, now - self.last_time))
        self.last_time = now
        self.anim_time += dt
        return dt

    @staticmethod
    def _hit(rects: List[Tuple[str, pygame.Rect]], pos: Tuple[int, int]) -> Optional[str]:
        if pos[0] < 0 or pos[1] < 0:
            return None
        return next((label for label, rect in rects if rect.collidepoint(pos)), None)

    # -------------------------------------------------------------------------
    # MAIN MENU SCREEN
    # -------------------------------------------------------------------------
    def menu(self, selected: int = 0, can_continue: bool = False, mouse: Optional[Tuple[int, int]] = None) -> None:
        dt = self._step_clock()
        self._begin_frame((7, 9, 14))

        # Atmospheric crypt backdrop: dusk gradient, stone arches and flagstones
        for y in range(0, 200):
            t = y / 200
            pygame.draw.line(self.canvas, (int(15 - 8 * t), int(19 - 10 * t), int(32 - 18 * t)), (0, y), (IW, y))
        pygame.draw.rect(self.canvas, (18, 22, 30), (0, 160, IW, IH - 160))
        pygame.draw.polygon(self.canvas, (28, 34, 44),
                            [(120, IH), (120, 180), (160, 120), (240, 80), (400, 80), (480, 120), (520, 180), (520, IH)])
        pygame.draw.polygon(self.canvas, (11, 14, 20),
                            [(150, IH), (150, 190), (180, 140), (250, 105), (390, 105), (460, 140), (490, 190), (490, IH)])
        for x in range(0, IW + 40, 40):
            pygame.draw.line(self.canvas, (28, 32, 40), (x, 260), (x - 20, IH))
        for y in range(260, IH, 24):
            pygame.draw.line(self.canvas, (24, 28, 36), (0, y), (IW, y))

        # Animated torches flanking the sanctum
        torches = [(155, 175), (485, 175), (280, 130), (360, 130)]
        torch_img = self.sprites.torch_frames[int(self.anim_time * 7) % 4]
        for tx, ty in torches:
            self.canvas.blit(self.sprites.glow_torch, (tx - 44, ty - 44), special_flags=pygame.BLEND_RGB_ADD)
            self.canvas.blit(torch_img, (tx - 9, ty - 10))
        self._ember_clock += dt
        if self._ember_clock >= 0.23:
            self._ember_clock = 0.0
            tx, ty = torches[self._ember_rr % len(torches)]
            self._ember_rr += 1
            self.particles.emit_torch_embers(tx, ty - 6, count=1)
        self.particles.update(dt)
        self.particles.draw(self.canvas)
        self.blit(self._edge_shade, (0, 0))

        # Title on a carved plaque
        title_rect = pygame.Rect(IW // 2 - 190, 18, 380, 106)
        self.draw_stone_frame(title_rect, (15, 19, 27), (128, 96, 48), shadow=True)
        self.text("MAZEQUEST", (IW // 2, 54), self.huge, (250, 208, 112), center=True)
        self.text("THE FORGOTTEN CATACOMBS", (IW // 2, 85), self.small_bold, CYAN, center=True)
        self.line((118, 88, 44), (title_rect.x + 36, 98), (title_rect.right - 36, 98))
        self.text("A DUNGEON OF STONE  •  LIGHT  •  AND LOST RELICS", (IW // 2, 109), self.tiny, MUTED, center=True)

        labels = [b for b in self.MENU_BUTTONS if can_continue or b != "CONTINUE"]
        self.menu_rects = []
        btn_w, btn_h, start_y, gap_y = 300, 32, 146, 39
        for i, label in enumerate(labels):
            rect = pygame.Rect(IW // 2 - btn_w // 2, start_y + i * gap_y, btn_w, btn_h)
            self.menu_rects.append((label, rect))
            self.draw_button(rect, label, active=(i == selected))

        self.text("WASD / ARROWS: MOVE      ENTER: SELECT      F11: FULLSCREEN",
                  (IW // 2, IH - 20), self.tiny, MUTED, center=True)
        self.present()

    def menu_hit(self, pos: Tuple[int, int]) -> Optional[str]:
        return self._hit(self.menu_rects, pos)

    # -------------------------------------------------------------------------
    # SETTINGS SCREEN
    # -------------------------------------------------------------------------
    def settings(self, settings_dict: Dict[str, Any], selected: int = 0, mouse: Optional[Tuple[int, int]] = None) -> None:
        self._step_clock()
        self._begin_frame()
        panel_rect = pygame.Rect(80, 35, IW - 160, IH - 70)
        self.draw_panel(panel_rect, "EXPEDITION SETTINGS", "Display, audio and gameplay")

        is_fullscreen = settings_dict.get("fullscreen", False)
        sound_on = settings_dict.get("sound", True)
        hints_on = settings_dict.get("show_hints", True)
        scaling = settings_dict.get("scaling", "smooth")
        volume = max(0.0, min(1.0, float(settings_dict.get("volume", 0.7))))

        if self.display_mgr and self.display_mgr.screen:
            display_size = self.display_mgr.screen.get_size() if is_fullscreen else self.display_mgr.window_size
        else:
            display_size = (DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        items = [
            ("DISPLAY MODE", f"{'FULLSCREEN' if is_fullscreen else 'WINDOWED'}  {display_size[0]} x {display_size[1]}", is_fullscreen),
            ("SCALING", SCALING_LABELS.get(scaling, "SMOOTH"), scaling == "smooth"),
            ("SOUND EFFECTS", "ENABLED" if sound_on else "MUTED", sound_on),
            ("VOLUME", f"{round(volume * 100)}%", sound_on),
            ("SHOW HINTS", "ENABLED" if hints_on else "DISABLED", hints_on),
            ("BACK TO MENU", "", False),
        ]

        self.settings_rects = []
        self.volume_track = pygame.Rect(0, 0, 0, 0)
        row_y = 98
        for i, (label, val, on) in enumerate(items):
            rect = pygame.Rect(panel_rect.x + 32, row_y + i * 42, panel_rect.w - 64, 34)
            self.settings_rects.append((label, rect))
            active = (i == selected)

            if label == "BACK TO MENU":
                self.draw_button(rect, label, active=active)
                continue

            if active:
                self.shape(rect, ((60, 51, 34), (36, 31, 23)), GOLD, 2, 7, glow=GOLD)
                cy = rect.centery
                self.poly(GOLD, [(rect.x + 11, cy - 4), (rect.x + 11, cy + 4), (rect.x + 17, cy)])
            else:
                self.shape(rect, ((30, 36, 48), (21, 26, 35)), (58, 68, 86), 1, 7)
            self.text(label, (rect.x + 26, rect.centery), self.body_bold, GOLD if active else INK, vcenter=True)
            val_col = CYAN if on else MUTED
            val_w = self.small_bold.size(val)[0]
            self.text(val, (rect.right - 16 - val_w, rect.centery), self.small_bold, val_col, vcenter=True)
            if label == "VOLUME":
                track = pygame.Rect(rect.right - 16 - 40 - 14 - 120, rect.centery - 4, 120, 8)
                self.draw_bar(track, int(track.w * volume), val_col if sound_on else MUTED)
                self.shape(pygame.Rect(track.x + int(track.w * volume) - 4, rect.centery - 7, 8, 14),
                           INK, (30, 34, 42), 1, 4)
                self.volume_track = track.inflate(10, 18)

        self.text("UP / DOWN: SELECT      ENTER: TOGGLE      LEFT / RIGHT: ADJUST      ESC: BACK",
                  (IW // 2, panel_rect.bottom - 20), self.tiny, MUTED, center=True)
        self.present()

    def settings_hit(self, pos: Tuple[int, int]) -> Optional[str]:
        return self._hit(self.settings_rects, pos)

    def volume_from_pos(self, pos: Tuple[int, int]) -> Optional[float]:
        """Volume (0..1, 5% steps) for a click on the slider track, else None."""
        track = self.volume_track
        if track.w == 0 or not track.collidepoint(pos):
            return None
        inner = track.inflate(-10, 0)
        frac = max(0.0, min(1.0, (pos[0] - inner.x) / max(1, inner.w)))
        return round(frac * 20) / 20

    # -------------------------------------------------------------------------
    # STATISTICS SCREEN
    # -------------------------------------------------------------------------
    def statistics(self, history: List[Dict[str, Any]], bests: Dict[str, Any], mouse: Optional[Tuple[int, int]] = None) -> None:
        self._step_clock()
        self._begin_frame()
        panel_rect = pygame.Rect(60, 30, IW - 120, IH - 60)
        self.draw_panel(panel_rect, "CATACOMB CHRONICLE", f"Expeditions recorded: {len(history)}")

        best = bests.get("1", {})
        best_time_str = f"{best['time']:.1f}s" if "time" in best else "-"
        best_moves_str = f"{best['moves']} moves" if "moves" in best else "-"
        wins = sum(1 for run in history if run.get("completed"))
        losses = len(history) - wins
        win_rate = f"{round(100 * wins / len(history))}%" if history else "-"

        cards = [
            ("BEST ESCAPE TIME", best_time_str, CYAN),
            ("SHORTEST ATTEMPT", best_moves_str, GOLD),
            ("VICTORIES", f"{wins} won / {losses} lost", GREEN),
            ("WIN RATE", win_rate, INK),
        ]
        card_w = (panel_rect.w - 56) // 2
        for i, (label, val, col) in enumerate(cards):
            r = pygame.Rect(panel_rect.x + 24 + (i % 2) * (card_w + 8), 92 + (i // 2) * 56, card_w, 48)
            self.draw_stat_card(r, label, val, col, self.body_bold)

        ledger_y = 218
        self.text("RECENT DELVES", (panel_rect.x + 24, ledger_y), self.small_bold, GOLD)
        self.line((64, 74, 92), (panel_rect.x + 24, ledger_y + 14), (panel_rect.right - 24, ledger_y + 14))
        recent = history[-5:]
        if not recent:
            self.text("No expeditions recorded yet. Enter the dungeon to begin.",
                      (panel_rect.x + 24, ledger_y + 32), self.small, MUTED)
        else:
            for idx, run in enumerate(reversed(recent)):
                ry = ledger_y + 30 + idx * 20
                won = bool(run.get("completed"))
                self.text(f"Delve #{len(history) - idx}", (panel_rect.x + 24, ry), self.small, INK)
                self.text(f"{run.get('elapsed', 0):.1f}s", (panel_rect.x + 130, ry), self.small, CYAN)
                self.text(f"{run.get('moves', 0)} moves", (panel_rect.x + 210, ry), self.small, GOLD)
                self.text(f"Relics {run.get('treasures', 0)}", (panel_rect.x + 310, ry), self.small, MUTED)
                self.text("WON" if won else "LOST", (panel_rect.x + 410, ry), self.small_bold,
                          GREEN if won else (240, 140, 100))

        back_rect = pygame.Rect(IW // 2 - 90, panel_rect.bottom - 42, 180, 28)
        self.stats_rects = [("RETURN TO MENU", back_rect)]
        self.draw_button(back_rect, "RETURN TO MENU", active=True, small=True)
        self.present()

    def statistics_hit(self, pos: Tuple[int, int]) -> Optional[str]:
        return self._hit(self.stats_rects, pos)

    # -------------------------------------------------------------------------
    # IN-GAME DUNGEON VIEW
    # -------------------------------------------------------------------------
    def _static_for(self, maze: Maze) -> pygame.Surface:
        """Floor, walls and entrance rendered once per maze; only props animate."""
        if self._static_maze is maze and self._static_layer is not None:
            return self._static_layer
        tw, th = TILE_W, TILE_H
        ox, oy = self.maze_origin(maze)
        layer = pygame.Surface((IW, IH))
        layer.fill((9, 12, 17))
        # Cells behind solid stone stay void so the ruin has a carved-out silhouette.
        for r in range(maze.rows):
            for c in range(maze.cols):
                if maze.grid[r][c] != '#':
                    layer.blit(self.sprites.get_floor_tile(r, c), (ox + c * tw, oy + r * th))
        for r in range(maze.rows):
            for c in range(maze.cols):
                if maze.grid[r][c] != '#':
                    continue
                south = r + 1 < maze.rows and maze.grid[r + 1][c] != '#'
                north = r - 1 >= 0 and maze.grid[r - 1][c] != '#'
                west = c - 1 >= 0 and maze.grid[r][c - 1] != '#'
                east = c + 1 < maze.cols and maze.grid[r][c + 1] != '#'
                if south or north or west or east:
                    self.sprites.draw_wall(layer, ox + c * tw, oy + r * th, r, c, south, north, west, east)
        ex, ey = ox + maze.entrance[1] * tw, oy + maze.entrance[0] * th
        pygame.draw.rect(layer, (32, 26, 22), (ex + 3, ey + 3, 12, 10))
        pygame.draw.line(layer, (55, 45, 38), (ex + 3, ey + 3), (ex + 14, ey + 3))
        if pygame.display.get_surface():
            layer = layer.convert()
        self._static_maze, self._static_layer = maze, layer
        self._props = sorted(set(maze.torches) | set(maze.crystals) | set(maze.treasures)
                             | set(maze.keys) | set(maze.doors) | {maze.goal})
        return layer

    def dungeon(self, game: Any, mouse: Optional[Tuple[int, int]] = None) -> None:
        dt = self._step_clock()
        self.clear_commands()
        maze = game.maze
        tw, th = TILE_W, TILE_H
        ox, oy = self.maze_origin(maze)
        self.canvas.blit(self._static_for(maze), (0, 0))

        if self._legend_game is not game:
            self._legend_game, self._legend_t0 = game, self.anim_time

        # Animated props (iterating only the cells that hold one)
        torch_frame = int(self.anim_time * 7) % 4
        crystal_frame = key_frame = relic_frame = int(self.anim_time * 5) % 4
        for p in self._props:
            r, c = p
            x, y = ox + c * tw, oy + r * th
            if p in maze.torches:
                self.canvas.blit(self.sprites.torch_frames[torch_frame], (x, y - 4))
            if p in maze.crystals:
                self.canvas.blit(self.sprites.crystal_frames[crystal_frame], (x, y - 4))
            if p in maze.treasures:
                chest = self.sprites.chest_opened if p in game.collected_treasures else self.sprites.chest_closed
                self.canvas.blit(chest, (x, y))
            if p in maze.keys and maze.keys[p] not in game.keys:
                self.canvas.blit(self.sprites.key_frames[key_frame], (x, y))
            if p in maze.doors:
                locked = maze.doors[p] not in game.keys
                self.canvas.blit(self.sprites.door_locked if locked else self.sprites.door_unlocked, (x, y))
            if p == maze.goal:
                self.canvas.blit(self.sprites.exit_pedestal, (x, y))
                self.canvas.blit(self.sprites.relic_frames[relic_frame], (x, y - 2))
        if game.hint_position:
            hr, hc = game.hint_position
            x, y = ox + hc * tw, oy + hr * th
            self.canvas.blit(self.sprites.glow_hint, (x + tw // 2 - 28, y + th // 2 - 28),
                             special_flags=pygame.BLEND_RGB_ADD)
            pygame.draw.rect(self.canvas, CYAN, (x + 3, y + 2, tw - 6, th - 4), 1)

        # Ambient particles, spawned on a timer so the rate is frame-rate independent
        self._ember_clock += dt
        torches = sorted(maze.torches)
        if torches and self._ember_clock >= 0.27:
            self._ember_clock = 0.0
            r, c = torches[self._ember_rr % len(torches)]
            self._ember_rr += 1
            self.particles.emit_torch_embers(ox + c * tw + 9, oy + r * th - 2, count=1)
        self._crystal_clock += dt
        crystals = sorted(maze.crystals)
        if crystals and self._crystal_clock >= 0.4:
            self._crystal_clock = 0.0
            r, c = crystals[self._crystal_rr % len(crystals)]
            self._crystal_rr += 1
            self.particles.emit_crystal_dust(ox + c * tw + 9, oy + r * th + 4, count=1)

        # Lighting glow pass
        for r, c in maze.torches:
            tx, ty = ox + c * tw + tw // 2, oy + r * th + th // 2
            flicker = int((math.sin(self.anim_time * 8 + r * 3 + c * 5) + 1) / 2 * 5.99)
            self.canvas.blit(self._torch_glows[flicker], (tx - 44, ty - 44), special_flags=pygame.BLEND_RGB_ADD)
        for r, c in maze.crystals:
            cx, cy = ox + c * tw + tw // 2, oy + r * th + th // 2
            self.canvas.blit(self.sprites.glow_crystal, (cx - 38, cy - 38), special_flags=pygame.BLEND_RGB_ADD)
        gx, gy = ox + maze.goal[1] * tw + tw // 2, oy + maze.goal[0] * th + th // 2
        self.canvas.blit(self.sprites.glow_exit, (gx - 36, gy - 36), special_flags=pygame.BLEND_RGB_ADD)
        player = game.animated_position
        px, py = ox + int(player[1] * tw + tw // 2), oy + int(player[0] * th + th // 2)
        self.canvas.blit(self.sprites.glow_player, (px - 22, py - 22), special_flags=pygame.BLEND_RGB_ADD)

        # Hero goes after the light so torch glow cannot wash out the sprite.
        self._draw_hero(game, ox, oy, tw, th)

        if game.show_optimal_route or game.show_actual_route:
            self._draw_routes(game, ox, oy, tw, th)

        self.particles.update(dt)
        self.particles.draw(self.canvas)

        # Edge shading, plus a pulsing red vignette when time is nearly gone
        self.blit(self._edge_shade, (0, 0))
        if not game.paused and not game.stats.completed and game.remaining < LOW_TIME_SECONDS:
            self.blit(self._vignette, (0, 0), int(150 + 100 * math.sin(self.anim_time * 4)))

        self._draw_hud(game, mouse)

        if not game.paused and not game.show_optimal_route and self.anim_time - self._legend_t0 < LEGEND_SECONDS:
            self._draw_legend_banner()
        if game.paused:
            self._draw_pause_overlay(game, mouse)
        self.present()

    def _draw_legend_banner(self) -> None:
        rect = pygame.Rect(IW // 2 - 214, 48, 428, 22)
        self.shape(rect, (12, 16, 24, 215), (120, 92, 50), 1, 6)
        self.text("WASD: MOVE    H: HINT    T: TRAIL    V: ROUTE    P: PAUSE",
                  rect.center, self.tiny, MUTED, center=True)

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

        if time.monotonic() - game.movement_started < 0.22:
            sprite = self.sprites.hero_walk[dir_name][int(self.anim_time * 9) % 4]
        else:
            sprite = self.sprites.hero_idle[dir_name][int(self.anim_time * 2.5) % 2]
        self.canvas.blit(sprite, (int(x), int(y)))

    def _draw_routes(self, game: Any, ox: int, oy: int, tw: int, th: int) -> None:
        """Draw optimal BFS energy path and/or player actual path."""
        def centre(p: Tuple[int, int]) -> Tuple[int, int]:
            return ox + p[1] * tw + tw // 2, oy + p[0] * th + th // 2

        if game.show_actual_route:
            actual = game.stats.actual_route
            for idx in range(len(actual) - 1):
                pygame.draw.line(self.canvas, (180, 85, 170), centre(actual[idx]), centre(actual[idx + 1]), 2)

        if game.show_optimal_route:
            route = game.stats.optimal_route
            for idx in range(len(route) - 1):
                p1, p2 = centre(route[idx]), centre(route[idx + 1])
                pygame.draw.line(self.canvas, (35, 140, 175), p1, p2, 3)
                pygame.draw.line(self.canvas, C_CYAN_HI, p1, p2, 1)

            pulse_idx = int((self.anim_time % 1.25) / 1.25 * len(route))
            if 0 <= pulse_idx < len(route):
                pygame.draw.circle(self.canvas, C_CYAN_LIGHT, centre(route[pulse_idx]), 4)

            banner = pygame.Rect(IW // 2 - 170, 48, 340, 24)
            self.shape(banner, (12, 16, 24, 225), CYAN, 1, 6)
            self.text(f"OPTIMAL ROUTE: {len(route) - 1} STEPS      [V] EXIT VIEW",
                      banner.center, self.tiny, CYAN, center=True)

    def _draw_hud(self, game: Any, mouse: Optional[Tuple[int, int]] = None) -> None:
        """Render the upper and lower HUD bars."""
        level = LEVELS[min(len(LEVELS), max(1, game.level_number)) - 1]
        relic_total = len(game.maze.treasures)

        self.draw_stone_frame(pygame.Rect(8, 5, IW - 16, 36), (17, 21, 29), (110, 84, 46), shadow=True)
        self.text(level.name.upper(), (20, 17), self.small_bold, GOLD, vcenter=True)
        self.text(f"Level {game.level_number}", (20, 30), self.tiny, MUTED, vcenter=True)

        # Countdown: red and pulsing in the final seconds
        self.blit(self.sprites.icons["hourglass"], (232, 16))
        minutes, seconds = divmod(int(math.ceil(game.remaining)), 60)
        low = game.remaining < LOW_TIME_SECONDS
        if low:
            time_color = (255, 150, 130) if int(self.anim_time * 3) % 2 == 0 else RED
        else:
            time_color = INK
        self.text(f"TIME  {minutes:02d}:{seconds:02d}", (254, 23), self.small_bold, time_color, vcenter=True)

        self.blit(self.sprites.icons["boot"], (386, 16))
        self.text(f"MOVES  {game.stats.moves:03d}", (408, 23), self.small_bold, INK, vcenter=True)

        for rect, label in ((self.settings_btn_rect, "OPTIONS"), (self.pause_btn_rect, "PAUSE")):
            hover = rect.collidepoint(mouse) if mouse else False
            self.draw_button(rect, label, hover=hover, small=True)

        # Footer
        bot_y = IH - 41
        self.draw_stone_frame(pygame.Rect(8, bot_y, IW - 16, 36), (17, 21, 29), (110, 84, 46), shadow=True)
        mid = bot_y + 18
        has_key = bool(game.keys)
        self.blit(self.sprites.icons["key_found" if has_key else "key_missing"], (20, mid - 7))
        self.text("Key found" if has_key else "No key", (42, mid), self.small, GOLD if has_key else MUTED, vcenter=True)

        self.blit(self.sprites.icons["relic"], (130, mid - 7))
        done = game.stats.treasures == relic_total and relic_total > 0
        self.text(f"Relics {game.stats.treasures}/{relic_total}", (152, mid), self.small,
                  GREEN if done else INK, vcenter=True)

        msg = game.current_message
        msg_col = CYAN if ("key" in msg.lower() or "gate" in msg.lower()) else INK
        msg_rect = pygame.Rect(236, bot_y + 5, 318, 26)
        self.shape(msg_rect, ((11, 15, 21), (16, 21, 29)), (46, 66, 78), 1, 6)
        self.text(self.fit_text(msg, self.small, msg_rect.w - 16), msg_rect.center, self.small, msg_col, center=True)

        if self.hints_enabled:
            wait = self.hint_cooldown
            hover = self.hint_btn_rect.collidepoint(mouse) if mouse else False
            label = f"HINT  {math.ceil(wait)}" if wait > 0 else "HINT"
            self.draw_button(self.hint_btn_rect, label, hover=hover, small=True, disabled=wait > 0)

    def _draw_pause_overlay(self, game: Any, mouse: Optional[Tuple[int, int]] = None) -> None:
        """Render the modal pause dialog over a dimmed screen."""
        self.dim((6, 8, 12, 175))
        box_w, box_h = 340, 270
        box_x, box_y = IW // 2 - box_w // 2, IH // 2 - box_h // 2
        self.draw_panel(pygame.Rect(box_x, box_y, box_w, box_h), "EXPEDITION PAUSED", "Choose an action")

        self.pause_rects = []
        btn_w, btn_h, gap_y = 252, 28, 33
        start_y = box_y + 66
        for i, opt in enumerate(self.PAUSE_OPTIONS):
            rect = pygame.Rect(IW // 2 - btn_w // 2, start_y + i * gap_y, btn_w, btn_h)
            self.pause_rects.append((opt, rect))
            self.draw_button(rect, opt, active=(i == game.pause_selected), small=True)
        self.text("H: HINT     T: TRAIL     V: ROUTE     F5: SAVE", (IW // 2, box_y + box_h - 18),
                  self.tiny, MUTED, center=True)

    def game_hit(self, pos: Tuple[int, int]) -> Optional[str]:
        if pos[0] < 0 or pos[1] < 0:
            return None
        if self.hints_enabled and self.hint_cooldown <= 0 and self.hint_btn_rect.collidepoint(pos):
            return "HINT"
        if self.pause_btn_rect.collidepoint(pos):
            return "PAUSE"
        if self.settings_btn_rect.collidepoint(pos):
            return "SETTINGS"
        return None

    def pause_hit(self, pos: Tuple[int, int]) -> Optional[str]:
        return self._hit(self.pause_rects, pos)

    # -------------------------------------------------------------------------
    # LEVEL RESULTS SCREEN
    # -------------------------------------------------------------------------
    def results(self, game: Any, mouse: Optional[Tuple[int, int]] = None, selected: int = 0,
                new_best: bool = False) -> None:
        self._step_clock()
        self._begin_frame()
        panel_rect = pygame.Rect(60, 25, IW - 120, IH - 50)
        level = LEVELS[min(len(LEVELS), max(1, game.level_number)) - 1]
        title = "ANCIENT RELIC CLAIMED!" if game.won else "EXPEDITION LOST IN THE DARK"
        sub = f"{level.name} - Sanctum Breached" if game.won else "The ancient depths claim another soul."
        self.draw_panel(panel_rect, title, sub)

        s = game.stats
        relic_total = len(game.maze.treasures)
        detour = max(0, s.moves - s.optimal_moves)
        rank = "S" if detour <= 2 else "A" if detour <= 8 else "B" if detour <= 16 else "C"

        stats_data = [
            ("EXPEDITION TIME", f"{game.elapsed:.1f} seconds", CYAN),
            ("SUCCESSFUL STEPS", f"{s.moves} moves", INK),
            ("SHORTEST ROUTE", f"{s.optimal_moves} moves", GOLD),
            ("EXPLORATION DETOUR", f"+{detour} moves", (240, 140, 100) if detour > 10 else INK),
            ("RELICS RECOVERED", f"{s.treasures} / {relic_total} found", GREEN),
            ("HINTS USED", str(s.hints_used), INK),
        ]
        card_w = (panel_rect.w - 56) // 2
        for idx, (label, val, col) in enumerate(stats_data):
            r = pygame.Rect(panel_rect.x + 24 + (idx % 2) * (card_w + 8), 82 + (idx // 2) * 46, card_w, 42)
            self.draw_stat_card(r, label, val, col)

        # Path efficiency bar, labels kept clear of the fill
        bar_x, bar_w, bar_y = panel_rect.x + 24, panel_rect.w - 48, 228
        self.text("PATH EFFICIENCY", (bar_x, bar_y), self.tiny, MUTED)
        track = pygame.Rect(bar_x, bar_y + 11, bar_w, 12)
        opt_w = min(bar_w, int(bar_w * (s.optimal_moves / max(1, s.moves))))
        self.draw_bar(track, bar_w, (180, 85, 170))
        self.draw_bar(track, opt_w, (40, 150, 186), track_color=(0, 0, 0, 0))
        self.text(f"Optimal: {s.optimal_moves}", (bar_x, track.bottom + 6), self.tiny, (110, 200, 228))
        if detour > 0:
            lbl = f"Detour: +{detour}"
            self.text(lbl, (track.right - self.tiny.size(lbl)[0], track.bottom + 6), self.tiny, (222, 140, 212))

        # Rank emblem
        emblem = pygame.Rect(bar_x, 282, 64, 56)
        self.draw_stone_frame(emblem, (16, 20, 28), (128, 96, 48), shadow=True)
        letter = rank if game.won else "X"
        self.text(letter, emblem.center, self.huge, GOLD if (game.won and rank in "SA") else INK, center=True)
        if game.won:
            rank_title, flavour = RANKS[rank]
        else:
            rank_title, flavour = "FALLEN", "Time ran out. The dark remembers."
        self.text(rank_title, (emblem.right + 16, emblem.y + 12), self.body_bold, GOLD if game.won else RED)
        self.text(flavour, (emblem.right + 16, emblem.y + 34), self.small, MUTED)
        if new_best:
            badge = pygame.Rect(panel_rect.right - 24 - 104, emblem.y + 10, 104, 26)
            pulse = int(self.anim_time * 3) % 2 == 0
            self.shape(badge, ((92, 68, 22), (56, 40, 12)), GOLD, 2, 8, glow=GOLD if pulse else None)
            self.text("NEW BEST!", badge.center, self.small_bold, (255, 226, 140), center=True)

        # Action buttons (keyboard focus and hover share one highlight)
        self.result_rects = []
        total_w = sum(w for _, w in self.RESULT_ACTIONS) + 10 * (len(self.RESULT_ACTIONS) - 1)
        curr_x = IW // 2 - total_w // 2
        btn_y = panel_rect.bottom - 64
        for i, (label, w) in enumerate(self.RESULT_ACTIONS):
            r = pygame.Rect(curr_x, btn_y, w, 32)
            self.result_rects.append((label, r))
            self.draw_button(r, label, active=(i == selected), small=True)
            curr_x += w + 10
        self.text("LEFT / RIGHT: SELECT      ENTER: CONFIRM      V: ROUTE      R: REPLAY",
                  (IW // 2, panel_rect.bottom - 20), self.tiny, MUTED, center=True)
        self.present()

    def result_hit(self, pos: Tuple[int, int]) -> Optional[str]:
        return self._hit(self.result_rects, pos)
