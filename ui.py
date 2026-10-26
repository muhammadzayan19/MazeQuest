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
from end_scene import EndScene
from decor import build_decor
from menu_scene import MenuScene
from particles import ParticleSystem
from sound import SoundManager
from sprites import C_GOLD_HI, C_CYAN_HI, C_CYAN_LIGHT, SpriteCache
from widgets import INK, MUTED, GOLD, CYAN, GREEN, RED, PANEL_BORDER, SKULL, SPARKLE, STAR, Painter

WIDTH: int = DEFAULT_WINDOW_WIDTH
HEIGHT: int = DEFAULT_WINDOW_HEIGHT
FPS: int = 60

TILE_W, TILE_H = 18, 16
HINT_COOLDOWN = 3.0          # seconds between hints (enforced by main)
FADE_SECONDS = 0.25
LEGEND_SECONDS = 8.0
LOW_TIME_SECONDS = 30
FOG_RADIUS = 7                # tiles the hero can see when fog of war is on
AMBIENT = (150, 158, 186)    # lightmap floor: how dark unlit areas get (never fully black)

SCALING_LABELS = {"smooth": "SMOOTH", "integer": "SHARP PIXELS", "fit": "SHARP FILL"}

RANKS = {
    "S": ("FLAWLESS DELVER", "Barely a step wasted."),
    "A": ("SEASONED EXPLORER", "You know these halls well."),
    "B": ("CAREFUL WANDERER", "A few detours, but you made it."),
    "C": ("TENACIOUS SURVIVOR", "You crawled out of the catacombs."),
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
        self._menu_scene = MenuScene(self.sprites)
        self._end_scene = EndScene()
        self._results_t0 = 0.0
        self._results_last = -10.0
        self._results_game: Any = None

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
        self.settings_btn_rect = pygame.Rect(482, 9, 76, 26)
        self.hint_btn_rect = pygame.Rect(565, IH - 36, 65, 26)

        # Cached overlays / layers
        self._vignette = self._build_vignette((200, 30, 20), 150, 28)
        self._edge_shade = self._build_vignette((0, 0, 0), 110, 46)
        self._fade_end = 0.0
        self._torch_glows = self._build_torch_glows()
        self._lightmap = pygame.Surface((IW, IH))
        self._static_maze: Optional[Maze] = None
        self._static_layer: Optional[pygame.Surface] = None
        self._props: List[Tuple[int, int]] = []
        self._legend_game: Any = None
        # Decor, reaction and atmosphere state
        self._decor_maze: Optional[Maze] = None
        self._decor = None
        self._lights: Dict[str, Any] = {}
        self._los_cache: Dict[tuple, set] = {}
        self._player_light: Tuple[Optional[tuple], List[pygame.Surface]] = (None, [])
        self._tracked: Any = None
        self._known_keys = 0
        self._known_treasures: set = set()
        self._chest_t: Dict[Tuple[int, int], float] = {}
        self._door_t: Optional[float] = None
        self._popups: List[list] = []
        self._flash: Tuple[float, Tuple[int, int, int]] = (-10.0, (255, 236, 170))
        self._prints: List[list] = []
        self._bump: Tuple[int, int, float] = (0, 0, -10.0)
        self._motes: List[list] = []
        self._bats: List[list] = []
        self._bat_clock = 12.0
        self._drops: List[list] = []
        self._drip_clock = 1.0
        self._seen: set = set()
        self.fog_enabled = False
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
        """Dust puff and a fading footprint at the cell the hero just left."""
        ox, oy = self.maze_origin(maze)
        self.particles.emit_footstep(ox + c * TILE_W + TILE_W // 2, oy + r * TILE_H + TILE_H - 2)
        side = 4 if len(self._prints) % 2 else -4
        self._prints.append([ox + c * TILE_W + TILE_W // 2 + side, oy + r * TILE_H + TILE_H - 5, self.anim_time])
        if len(self._prints) > 40:
            del self._prints[0]

    def bump(self, dr: int, dc: int) -> None:
        """Walked into a wall: nudge the hero and kick up a little dust."""
        self._bump = (dr, dc, self.anim_time)

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
        self.blink = int(self.anim_time * 2) % 2 == 0
        return dt

    @staticmethod
    def _hit(rects: List[Tuple[str, pygame.Rect]], pos: Tuple[int, int]) -> Optional[str]:
        if pos[0] < 0 or pos[1] < 0:
            return None
        return next((label for label, rect in rects if rect.collidepoint(pos)), None)

    # -------------------------------------------------------------------------
    # MAIN MENU SCREEN
    # -------------------------------------------------------------------------
    def menu(self, selected: int = 0, can_continue: bool = False, mouse: Optional[Tuple[int, int]] = None,
             bests: Optional[Dict[str, Any]] = None, history: Optional[List[Dict[str, Any]]] = None,
             continue_info: str = "") -> None:
        dt = self._step_clock()
        self._begin_frame((7, 9, 14))
        scene = self._menu_scene
        scene.draw(self.canvas, self.anim_time)
        self._ember_clock += dt
        if self._ember_clock >= 0.12:
            self._ember_clock = 0.0
            tx, ty = scene.torches[self._ember_rr % len(scene.torches)]
            self._ember_rr += 1
            self.particles.emit_torch_embers(tx, ty - 10, count=1)
        self.particles.update(dt)
        self.particles.draw(self.canvas)

        # Logo plaque: stepped gold extrusion, hard shadow, blinking sparkles
        cx = IW // 2
        plaque = pygame.Rect(cx - 176, 12, 352, 100)
        self.draw_stone_frame(plaque, (16, 19, 32), (176, 132, 58), shadow=True)
        self.shape(plaque.inflate(-10, -10), None, (70, 56, 40), 1, 0, bevel=False)
        for off in (3, 2, 1):
            self.text("MAZEQUEST", (cx + off, 46 + off), self.huge, (96, 54, 14), shadow=False, center=True)
        self.text("MAZEQUEST", (cx, 46), self.huge, (255, 206, 76), shadow=False, center=True)
        if int(self.anim_time * 3) % 4 < 2:
            self.bitmap(SPARKLE, {"X": (255, 250, 220)}, (cx + 142, 28))
        else:
            self.bitmap(SPARKLE, {"X": (255, 250, 220)}, (cx - 150, 58))
        self.text("THE FORGOTTEN CATACOMBS", (cx, 82), self.body_bold, CYAN, center=True)
        for dx in range(-110, 110, 6):
            self.shape(pygame.Rect(cx + dx, 94, 3, 1), (120, 92, 50), None, 0, 0, bevel=False)
        self.text("A DUNGEON OF STONE * LIGHT * AND LOST RELICS", (cx, 103), self.small, MUTED, center=True)

        # Menu buttons (numbered for quick pick)
        labels = [b for b in self.MENU_BUTTONS if can_continue or b != "CONTINUE"]
        self.menu_rects = []
        btn_w, btn_h, start_y, gap_y = 292, 28, 128, 34
        for i, label in enumerate(labels):
            rect = pygame.Rect(cx - btn_w // 2, start_y + i * gap_y, btn_w, btn_h)
            self.menu_rects.append((label, rect))
            detail = continue_info if (label == "CONTINUE" and continue_info) else ""
            self.draw_button(rect, label, active=(i == selected), hotkey=str(i + 1), detail=detail)

        # Records strip
        history = history or []
        best = (bests or {}).get("1", {})
        wins = sum(1 for run in history if run.get("completed"))
        info = pygame.Rect(cx - btn_w // 2, start_y + 5 * gap_y - 2, btn_w, 24)
        self.shape(info, (12, 15, 26), (70, 82, 118), 1, 0, bevel=False)
        if "time" in best:
            txt = f"BEST {best['time']:.1f} SEC  -  WINS {wins}/{len(history)}"
        else:
            txt = "NO RECORDS YET - BEGIN YOUR DELVE"
        self.text(self.fit_text(txt, self.small_bold, info.w - 12), info.center, self.small_bold, GOLD, center=True)

        # Footer
        if self.blink:
            self.text("PRESS ENTER TO DESCEND", (cx, 368), self.body_bold, GOLD, center=True)
        self.text("W/S OR ARROWS: MOVE   ENTER: SELECT   1-5: QUICK PICK   F11: FULLSCREEN",
                  (cx, IH - 30), self.small, MUTED, center=True)
        self.text("V1.1", (IW - 8 - self.small.size("V1.1")[0], IH - 14), self.small, MUTED)
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
        scaling = settings_dict.get("scaling", "integer")
        volume = max(0.0, min(1.0, float(settings_dict.get("volume", 0.7))))

        if self.display_mgr and self.display_mgr.screen:
            display_size = self.display_mgr.screen.get_size() if is_fullscreen else self.display_mgr.window_size
        else:
            display_size = (DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        items = [
            ("DISPLAY MODE", f"{'FULLSCREEN' if is_fullscreen else 'WINDOWED'}  {display_size[0]} x {display_size[1]}", is_fullscreen),
            ("SCALING", SCALING_LABELS.get(scaling, "SHARP PIXELS"), scaling == "smooth"),
            ("SOUND EFFECTS", "ENABLED" if sound_on else "MUTED", sound_on),
            ("VOLUME", f"{round(volume * 100)} PCT", sound_on),
            ("SHOW HINTS", "ENABLED" if hints_on else "DISABLED", hints_on),
            ("FOG OF WAR", "ON" if settings_dict.get("fog", False) else "OFF", settings_dict.get("fog", False)),
            ("BACK TO MENU", "", False),
        ]

        self.settings_rects = []
        self.volume_track = pygame.Rect(0, 0, 0, 0)
        row_y = 98
        for i, (label, val, on) in enumerate(items):
            rect = pygame.Rect(panel_rect.x + 32, row_y + i * 38, panel_rect.w - 64, 32)
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
        best_time_str = f"{best['time']:.1f} SEC" if "time" in best else "-"
        best_moves_str = f"{best['moves']} moves" if "moves" in best else "-"
        wins = sum(1 for run in history if run.get("completed"))
        losses = len(history) - wins
        win_rate = f"{round(100 * wins / len(history))} PCT" if history else "-"

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
                self.text(f"{run.get('elapsed', 0):.1f} SEC", (panel_rect.x + 130, ry), self.small, CYAN)
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
    # ------------------------------------------------------------ line of sight
    @staticmethod
    def _clear_line(maze: Maze, a: Tuple[int, int], b: Tuple[int, int]) -> bool:
        """True if no wall lies strictly between cells ``a`` and ``b`` (Bresenham)."""
        (r0, c0), (r1, c1) = a, b
        dr, dc = abs(r1 - r0), abs(c1 - c0)
        sr, sc = (1 if r1 > r0 else -1), (1 if c1 > c0 else -1)
        err = dc - dr
        r, c = r0, c0
        while (r, c) != (r1, c1):
            if (r, c) != (r0, c0) and maze.grid[r][c] == "#":
                return False
            e2 = 2 * err
            if e2 > -dr:
                err -= dr
                c += sc
            if e2 < dc:
                err += dc
                r += sr
        return True

    def _visible_cells(self, maze: Maze, origin: Tuple[int, int], radius: int) -> set:
        key = (id(maze), origin, radius)
        cached = self._los_cache.get(key)
        if cached is not None:
            return cached
        orr, oc = origin
        vis = set()
        for r in range(max(0, orr - radius), min(maze.rows, orr + radius + 1)):
            for c in range(max(0, oc - radius), min(maze.cols, oc + radius + 1)):
                if (r - orr) ** 2 + (c - oc) ** 2 <= radius * radius and self._clear_line(maze, origin, (r, c)):
                    vis.add((r, c))
        if len(self._los_cache) > 600:
            self._los_cache.clear()
        self._los_cache[key] = vis
        return vis

    def _masked_glow(self, maze: Maze, glow: pygame.Surface, cell: Tuple[int, int], radius: int) -> pygame.Surface:
        """Copy of a light pool with every tile that has no line of sight to ``cell`` blacked out."""
        vis = self._visible_cells(maze, cell, radius)
        g = glow.copy()
        gw, gh = g.get_size()
        for dr in range(-radius - 1, radius + 2):
            for dc in range(-radius - 1, radius + 2):
                if (cell[0] + dr, cell[1] + dc) in vis:
                    continue
                g.fill((0, 0, 0), (gw // 2 + dc * TILE_W - TILE_W // 2, gh // 2 + dr * TILE_H - TILE_H // 2,
                                   TILE_W, TILE_H))
        return g

    @staticmethod
    def _dimmed(glow: pygame.Surface, steps: int = 6) -> List[pygame.Surface]:
        out = []
        for k in range(steps):
            level = int(255 * (0.74 + 0.26 * k / max(1, steps - 1)))
            g = glow.copy()
            g.fill((level, level, level), special_flags=pygame.BLEND_RGB_MULT)
            out.append(g)
        return out

    def _setup_maze(self, maze: Maze) -> None:
        """Per-maze caches: decor placement and wall-aware light pools."""
        self._decor_maze = maze
        self._decor = build_decor(maze)
        self._los_cache.clear()
        sp = self.sprites
        self._lights = {
            "torches": {p: self._dimmed(self._masked_glow(maze, sp.glow_torch, p, 5)) for p in maze.torches},
            "crystals": {p: self._masked_glow(maze, sp.glow_crystal, p, 4) for p in maze.crystals},
            "exit": self._masked_glow(maze, sp.glow_exit, maze.goal, 4),
            "candles": {p: self._masked_glow(maze, sp.glow_candle, p, 2) for p in self._decor.candles},
        }
        import random as _random
        r = _random.Random(11)
        ox, oy = self.maze_origin(maze)
        floor = [(rr, cc) for rr in range(maze.rows) for cc in range(maze.cols) if maze.grid[rr][cc] != "#"]
        self._motes = []
        for _ in range(40):
            rr, cc = r.choice(floor)
            self._motes.append([ox + cc * TILE_W + r.uniform(0, TILE_W), oy + rr * TILE_H + r.uniform(0, TILE_H),
                                r.uniform(-3, 3), r.uniform(-2, 2), r.uniform(0, 6.28)])

    def _static_for(self, maze: Maze) -> pygame.Surface:
        """Zone-tinted floors, carpet, decals, walls with decor and the entrance, rendered once per maze."""
        if self._static_maze is maze and self._static_layer is not None:
            return self._static_layer
        self._setup_maze(maze)
        decor, art = self._decor, self.sprites.decor
        tw, th = TILE_W, TILE_H
        ox, oy = self.maze_origin(maze)
        layer = pygame.Surface((IW, IH))
        layer.fill((9, 12, 17))
        # Cells behind solid stone stay void so the ruin has a carved-out silhouette.
        for r in range(maze.rows):
            for c in range(maze.cols):
                if maze.grid[r][c] != '#':
                    tile = self.sprites.get_floor_tile(r, c, decor.zone_of((r, c)))
                    layer.blit(tile, (ox + c * tw, oy + r * th))
        for (r, c) in decor.carpet:
            layer.blit(art.carpet, (ox + c * tw, oy + r * th))
        for (r, c), name, variant in decor.floor_decals:
            options = art.floor[name]
            layer.blit(options[variant % len(options)], (ox + c * tw, oy + r * th))
        for r in range(maze.rows):
            for c in range(maze.cols):
                if maze.grid[r][c] != '#':
                    continue
                south = r + 1 < maze.rows and maze.grid[r + 1][c] != '#'
                north = r - 1 >= 0 and maze.grid[r - 1][c] != '#'
                west = c - 1 >= 0 and maze.grid[r][c - 1] != '#'
                east = c + 1 < maze.cols and maze.grid[r][c + 1] != '#'
                if south or north or west or east:
                    self.sprites.draw_wall(layer, ox + c * tw, oy + r * th, r, c, south, north, west, east,
                                           decor.wall_decor.get((r, c)))
        ex, ey = ox + maze.entrance[1] * tw, oy + maze.entrance[0] * th
        pygame.draw.rect(layer, (32, 26, 22), (ex + 3, ey + 3, 12, 10))
        pygame.draw.line(layer, (55, 45, 38), (ex + 3, ey + 3), (ex + 14, ey + 3))
        if pygame.display.get_surface():
            layer = layer.convert()
        self._static_maze, self._static_layer = maze, layer
        self._props = sorted(set(maze.torches) | set(maze.crystals) | set(maze.treasures)
                             | set(maze.keys) | set(maze.doors) | {maze.goal})
        return layer

    def _track_events(self, game: Any, ox: int, oy: int) -> None:
        """Detect pickups and the gate opening from game state; spawn popups, flashes and effects."""
        maze = game.maze
        tw, th = TILE_W, TILE_H
        doors_open = bool(maze.doors) and all(tok in game.keys for tok in maze.doors.values())
        if self._tracked is not game:
            self._tracked = game
            self._known_keys = len(game.keys)
            self._known_treasures = set(game.collected_treasures)
            self._chest_t = {p: -99.0 for p in game.collected_treasures}
            self._door_t = -99.0 if doors_open else None
            self._seen = set(game.visited)
            self._prints.clear()
            self._popups.clear()
            self._drops.clear()
            return
        hero = (ox + int(game.position[1] * tw + tw // 2), oy + int(game.position[0] * th))
        if len(game.keys) > self._known_keys:
            self._known_keys = len(game.keys)
            self._popups.append(["+KEY", hero[0], hero[1], self.anim_time, GOLD])
            self._flash = (self.anim_time, (255, 226, 150))
        for p in set(game.collected_treasures) - self._known_treasures:
            self._known_treasures.add(p)
            self._chest_t[p] = self.anim_time
            self._popups.append([f"+{maze.treasures.get(p, 0)}", ox + p[1] * tw + tw // 2, oy + p[0] * th,
                                 self.anim_time, GREEN])
            self._flash = (self.anim_time, (255, 236, 170))
        if doors_open and self._door_t is None:
            self._door_t = self.anim_time
            self.sound_mgr.play("unlock")
            for (dr_, dc_) in maze.doors:
                dx, dy = ox + dc_ * tw + tw // 2, oy + dr_ * th + th // 2
                self.particles.emit_unlock_flash(dx, dy, count=18)
                self._popups.append(["GATE OPEN", dx, oy + dr_ * th - 4, self.anim_time, CYAN])

    def dungeon(self, game: Any, mouse: Optional[Tuple[int, int]] = None) -> None:
        dt = self._step_clock()
        self.clear_commands()
        maze = game.maze
        tw, th = TILE_W, TILE_H
        ox, oy = self.maze_origin(maze)
        t = self.anim_time
        self.canvas.blit(self._static_for(maze), (0, 0))
        decor, art = self._decor, self.sprites.decor
        self._track_events(game, ox, oy)

        if self._legend_game is not game:
            self._legend_game, self._legend_t0 = game, t

        # 1) Props that only reflect light, with open/unlock animations
        for p in self._props:
            r, c = p
            x, y = ox + c * tw, oy + r * th
            if p in maze.treasures:
                stage = min(3, int((t - self._chest_t[p]) / 0.1)) if p in self._chest_t else 0
                self.canvas.blit(self.sprites.chest_frames[stage], (x, y))
            if p in maze.doors:
                stage = 0 if self._door_t is None else min(3, int((t - self._door_t) / 0.14))
                self.canvas.blit(self.sprites.door_frames[stage], (x, y))
            if p == maze.goal:
                self.canvas.blit(self.sprites.exit_pedestal, (x, y))

        # Puddle shimmer, footprints, dust motes and drips are drawn before lighting so shadows dim them
        for (r, c), name, variant in decor.floor_decals:
            if name == "puddle":
                px = ox + c * tw + 6 + int(t * 5 + r + c) % 7
                self.canvas.set_at((px, oy + r * th + 9), (172, 214, 250))
        for pr in list(self._prints):
            age = t - pr[2]
            if age > 3.0:
                self._prints.remove(pr)
                continue
            shade = (22, 22, 28) if age < 1.0 else (13, 13, 17) if age < 2.0 else (6, 6, 9)
            self.canvas.fill(shade, (int(pr[0]), int(pr[1]), 2, 3), special_flags=pygame.BLEND_RGB_SUB)
        for m in self._motes:
            m[0] += m[2] * dt
            m[1] += m[3] * dt
            mc, mr = int((m[0] - ox) // tw), int((m[1] - oy) // th)
            if not (0 <= mr < maze.rows and 0 <= mc < maze.cols) or maze.grid[mr][mc] == "#":
                m[2], m[3] = -m[2], -m[3]          # drift back into the open floor
                m[0] += m[2] * dt * 2
                m[1] += m[3] * dt * 2
            elif int(t * 2 + m[4]) % 3:
                self.canvas.fill((130, 126, 108), (int(m[0]), int(m[1]), 1, 1), special_flags=pygame.BLEND_RGB_ADD)
        self._drip_clock -= dt
        if decor.drip_points and self._drip_clock <= 0:
            self._drip_clock = 1.4 + (hash((int(t), 7)) % 100) / 60.0
            dr_, dc_ = decor.drip_points[int(t * 3) % len(decor.drip_points)]
            self._drops.append([ox + dc_ * tw + 5 + (dr_ * 7 + dc_) % 8, oy + dr_ * th + 1, 0.0, oy + dr_ * th + th - 3, -1.0])
        for d in list(self._drops):
            if d[4] < 0:
                d[2] += 120 * dt
                d[1] += d[2] * dt
                self.canvas.fill((120, 160, 220), (int(d[0]), int(d[1]), 1, 2), special_flags=pygame.BLEND_RGB_ADD)
                if d[1] >= d[3]:
                    d[4] = t
            else:
                age = t - d[4]
                if age > 0.5:
                    self._drops.remove(d)
                    continue
                w = 2 + int(age * 12)
                rect = pygame.Rect(int(d[0]) - w // 2, int(d[3]), w, max(1, w // 3))
                pygame.draw.ellipse(self.canvas, (60, 84, 120), rect, 1)

        # 2) Banded lightmap: ambient plus wall-aware light pools, multiplied over the scene
        lm = self._lightmap
        lm.fill(AMBIENT)
        for i, p in enumerate(sorted(maze.torches)):
            flicker = int((math.sin(t * 8 + p[0] * 3 + p[1] * 5) + 1) / 2 * 5.99)
            self._add_light(lm, self._lights["torches"][p][flicker], ox + p[1] * tw + tw // 2, oy + p[0] * th + th // 2)
        for p, glow in self._lights["crystals"].items():
            self._add_light(lm, glow, ox + p[1] * tw + tw // 2, oy + p[0] * th + th // 2)
        self._add_light(lm, self._lights["exit"], ox + maze.goal[1] * tw + tw // 2, oy + maze.goal[0] * th + th // 2)
        for p, glow in self._lights["candles"].items():
            self._add_light(lm, glow, ox + p[1] * tw + tw // 2, oy + p[0] * th + th // 2)
        if game.hint_position:
            self._add_light(lm, self.sprites.glow_hint, ox + game.hint_position[1] * tw + tw // 2,
                            oy + game.hint_position[0] * th + th // 2)
        player = game.animated_position
        px, py = ox + int(player[1] * tw + tw // 2), oy + int(player[0] * th + th // 2)
        cell = (int(round(player[0])), int(round(player[1])))
        if self._player_light[0] != (id(maze), cell):
            self._player_light = ((id(maze), cell),
                                  self._dimmed(self._masked_glow(maze, self.sprites.glow_player, cell, 6), 4))
        lantern = self._player_light[1][int((math.sin(t * 9) + math.sin(t * 5.3) + 2) / 4 * 3.99)]
        self._add_light(lm, lantern, px, py)
        self.canvas.blit(lm, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        for r, c in maze.torches:
            self._add_light(self.canvas, self.sprites.tint_torch, ox + c * tw + tw // 2, oy + r * th + th // 2)
        for r, c in maze.crystals:
            self._add_light(self.canvas, self.sprites.tint_crystal, ox + c * tw + tw // 2, oy + r * th + th // 2)
        self._add_light(self.canvas, self.sprites.tint_exit, ox + maze.goal[1] * tw + tw // 2,
                        oy + maze.goal[0] * th + th // 2)

        # 3) Emissive props stay fully bright on top of the lighting
        torch_frame = int(t * 7) % len(self.sprites.torch_frames)
        crystal_frame = key_frame = relic_frame = int(t * 5) % 4
        for p in self._props:
            r, c = p
            x, y = ox + c * tw, oy + r * th
            if p in maze.torches:
                self.canvas.blit(self.sprites.torch_frames[torch_frame], (x, y - 4))
            if p in maze.crystals:
                self.canvas.blit(self.sprites.crystal_frames[crystal_frame % len(self.sprites.crystal_frames)], (x, y - 4))
            if p in maze.keys and maze.keys[p] not in game.keys:
                self.canvas.blit(self.sprites.key_frames[key_frame % len(self.sprites.key_frames)], (x, y))
            if p == maze.goal:
                self.canvas.blit(self.sprites.relic_frames[relic_frame % len(self.sprites.relic_frames)], (x, y - 2))
        for (r, c) in decor.runes:
            level = int((math.sin(t * 2.2 + r + c) + 1) / 2 * 3.99)
            self.canvas.blit(art.rune_pulses[level], (ox + c * tw, oy + r * th), special_flags=pygame.BLEND_RGB_ADD)
        for (r, c) in decor.candles:
            self.canvas.blit(art.candle_frames[int(t * 6 + r + c) % 2], (ox + c * tw, oy + r * th))
        if game.hint_position:
            hr, hc = game.hint_position
            x, y = ox + hc * tw, oy + hr * th
            pygame.draw.rect(self.canvas, CYAN, (x + 2, y + 1, tw - 4, th - 2), 1)
            if self.blink:
                pygame.draw.rect(self.canvas, (220, 255, 255), (x + 4, y + 3, tw - 8, th - 6), 1)

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

        # Hero goes after the lighting so it never gets darkened.
        self._draw_hero(game, ox, oy, tw, th)
        self._draw_bats(dt, ox, oy, maze)

        if game.show_optimal_route or game.show_actual_route:
            self._draw_routes(game, ox, oy, tw, th)

        self.particles.update(dt)
        self.particles.draw(self.canvas)

        if self.fog_enabled:
            self._draw_fog(game, cell, ox, oy)

        # Floating pickup text, edge shading, red vignette when time is nearly gone
        for pop in list(self._popups):
            age = t - pop[3]
            if age > 1.2:
                self._popups.remove(pop)
                continue
            color = pop[4] if int(age * 10) % 2 == 0 else (255, 255, 235)
            self.text(pop[0], (pop[1], pop[2] - 8 - age * 16), self.small_bold, color, center=True)
        self.blit(self._edge_shade, (0, 0))
        flash_age = t - self._flash[0]
        if flash_age < 0.2:
            self.dim((*self._flash[1], int(52 * (1 - flash_age / 0.2))))
        if not game.paused and not game.stats.completed and game.remaining < LOW_TIME_SECONDS:
            self.blit(self._vignette, (0, 0), int(150 + 100 * math.sin(t * 4)))

        self._draw_hud(game, mouse)

        if not game.paused and not game.show_optimal_route and t - self._legend_t0 < LEGEND_SECONDS:
            self._draw_legend_banner()
        if game.paused:
            self._draw_pause_overlay(game, mouse)
        self.present()

    def _draw_bats(self, dt: float, ox: int, oy: int, maze: Maze) -> None:
        """An occasional pair of bats flutters across the dungeon (purely decorative)."""
        t = self.anim_time
        self._bat_clock -= dt
        if self._bat_clock <= 0 and not self._bats:
            self._bat_clock = 22.0 + (int(t) * 7) % 14
            going_right = int(t) % 2 == 0
            base_y = oy + (int(t * 3) % max(1, maze.rows - 4) + 2) * TILE_H
            for i in range(2):
                self._bats.append([-14 - i * 22 if going_right else IW + 14 + i * 22, base_y + i * 9,
                                   (70 if going_right else -70), i * 1.3])
        for bat in list(self._bats):
            bat[0] += bat[2] * dt
            if bat[0] < -30 or bat[0] > IW + 30:
                self._bats.remove(bat)
                continue
            y = bat[1] + math.sin(t * 3 + bat[3]) * 6
            frame = self.sprites.decor.bat_frames[int(t * 10 + bat[3]) % 2]
            self.canvas.blit(frame, (int(bat[0]), int(y)))

    def _draw_fog(self, game: Any, cell: Tuple[int, int], ox: int, oy: int) -> None:
        """Fog of war: unexplored cells black, remembered cells dimmed, cells in sight clear."""
        maze = game.maze
        visible = self._visible_cells(maze, cell, FOG_RADIUS)
        self._seen |= visible
        dim = pygame.Surface((TILE_W, TILE_H + 6), pygame.SRCALPHA)
        dim.fill((6, 8, 16, 150))
        snap = self.canvas.copy()
        self.canvas.fill((7, 9, 14), (0, 40, IW, IH - 80))
        for pos in self._seen:
            r, c = pos
            x, y = ox + c * TILE_W, oy + r * TILE_H
            area = (x, y - 6, TILE_W, TILE_H + 6)
            self.canvas.blit(snap, (x, y - 6), area)
            if pos not in visible:
                self.canvas.blit(dim, (x, y - 6))

    @staticmethod
    def _add_light(lightmap: pygame.Surface, glow: pygame.Surface, cx: int, cy: int) -> None:
        lightmap.blit(glow, (cx - glow.get_width() // 2, cy - glow.get_height() // 2), special_flags=pygame.BLEND_RGB_ADD)

    def _draw_legend_banner(self) -> None:
        rect = pygame.Rect(IW // 2 - 214, 48, 428, 22)
        self.shape(rect, (12, 16, 24, 215), (120, 92, 50), 1, 6)
        self.text("WASD: MOVE    H: HINT    T: TRAIL    V: ROUTE    P: PAUSE",
                  rect.center, self.tiny, MUTED, center=True)

    def _draw_hero(self, game: Any, ox: int, oy: int, tw: int, th: int) -> None:
        """Render the hero with directional walk/idle animations."""
        player = game.animated_position
        sw, sh = self.sprites.hero_walk["down"][0].get_size()
        x = ox + player[1] * tw + (tw - sw) // 2
        y = oy + player[0] * th + th - sh

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
        bdr, bdc, bt = self._bump
        age = self.anim_time - bt
        off_x = off_y = 0
        if 0 <= age < 0.14:
            push = math.sin(math.pi * age / 0.14) * 2
            off_x, off_y = round(bdc * push), round(bdr * push)
            if age < 0.03:
                self.particles.emit_footstep(x + 9 + bdc * 8, y + 20 + bdr * 4)
        self.canvas.blit(sprite, (int(x) + off_x, int(y) + off_y))

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
        """Render the upper and lower HUD bars with large, high-contrast readouts."""
        level = LEVELS[min(len(LEVELS), max(1, game.level_number)) - 1]
        relic_total = len(game.maze.treasures)

        self.draw_stone_frame(pygame.Rect(8, 5, IW - 16, 36), (18, 22, 34), (132, 100, 52), shadow=True)
        self.text(level.name.upper(), (20, 15), self.small_bold, GOLD, vcenter=True)
        self.text(f"LEVEL {game.level_number}", (20, 28), self.small, MUTED, vcenter=True)

        # Countdown: red and blinking in the final seconds
        minutes, seconds = divmod(int(math.ceil(game.remaining)), 60)
        low = game.remaining < LOW_TIME_SECONDS
        time_color = (RED if self.blink else (255, 190, 170)) if low else INK
        self.blit(self.sprites.icons["hourglass"], (214, 12))
        self.text("TIME", (238, 11), self.small, MUTED)
        self.text(f"{minutes:02d}:{seconds:02d}", (238, 31), self.body_bold, time_color, vcenter=True)

        self.blit(self.sprites.icons["boot"], (334, 12))
        self.text("MOVES", (358, 11), self.small, MUTED)
        self.text(f"{game.stats.moves:03d}", (358, 31), self.body_bold, INK, vcenter=True)

        for rect, label in ((self.settings_btn_rect, "OPTIONS"), (self.pause_btn_rect, "PAUSE")):
            hover = rect.collidepoint(mouse) if mouse else False
            self.draw_button(rect, label, hover=hover, small=True)

        # Footer
        bot_y = IH - 41
        self.draw_stone_frame(pygame.Rect(8, bot_y, IW - 16, 36), (18, 22, 34), (132, 100, 52), shadow=True)
        mid = bot_y + 18
        has_key = bool(game.keys)
        self.blit(self.sprites.icons["key_found" if has_key else "key_missing"], (18, mid - 9))
        self.text("KEY FOUND" if has_key else "NO KEY", (40, mid), self.small_bold, GOLD if has_key else MUTED, vcenter=True)

        self.blit(self.sprites.icons["relic"], (120, mid - 9))
        done = game.stats.treasures == relic_total and relic_total > 0
        self.text(f"RELICS {game.stats.treasures}/{relic_total}", (142, mid), self.small_bold,
                  GREEN if done else INK, vcenter=True)

        msg = game.current_message
        msg_col = CYAN if ("key" in msg.lower() or "gate" in msg.lower()) else INK
        msg_rect = pygame.Rect(236, bot_y + 4, 318, 28)
        self.shape(msg_rect, (12, 15, 26), (60, 84, 104), 1, 1)
        lines = self.wrap_text(msg, self.small, msg_rect.w - 12, 2)
        for i, line in enumerate(lines):
            y = msg_rect.centery + (i - (len(lines) - 1) / 2) * 11
            self.text(line, (msg_rect.centerx, y), self.small, msg_col, center=True)

        if self.hints_enabled:
            wait = self.hint_cooldown
            hover = self.hint_btn_rect.collidepoint(mouse) if mouse else False
            label = f"HINT {math.ceil(wait)}" if wait > 0 else "HINT"
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
        dt = self._step_clock()
        self._begin_frame()
        won = bool(game.won)

        # Replay the reveal animation whenever the screen is (re)entered
        if self._results_game is not game or self.anim_time - self._results_last > 0.5:
            self._results_t0, self._results_game = self.anim_time, game
        self._results_last = self.anim_time
        age = self.anim_time - self._results_t0

        self._end_scene.draw(self.canvas, self.anim_time, dt, won)
        self.blit(self._edge_shade, (0, 0))

        level = LEVELS[min(len(LEVELS), max(1, game.level_number)) - 1]
        s = game.stats
        relic_total = len(game.maze.treasures)
        detour = max(0, s.moves - s.optimal_moves)
        rank = "S" if detour <= 2 else "A" if detour <= 8 else "B" if detour <= 16 else "C"
        cx = IW // 2

        # Banner
        banner = pygame.Rect(cx - 190, 12, 380, 66)
        self.draw_stone_frame(banner, (16, 19, 32) if won else (24, 10, 20),
                              (176, 132, 58) if won else (160, 54, 62), shadow=True)
        title = "VICTORY!" if won else "DEFEATED"
        for off in (3, 2, 1):
            self.text(title, (cx + off, 36 + off), self.huge, (96, 54, 14) if won else (84, 18, 28),
                      shadow=False, center=True)
        self.text(title, (cx, 36), self.huge, (255, 206, 76) if won else (255, 104, 92), shadow=False, center=True)
        sub = f"{level.name.upper()} - SANCTUM BREACHED" if won else "THE DARK CLAIMED ANOTHER SOUL"
        self.text(self.fit_text(sub, self.small, banner.w - 20), (cx, 65), self.small, MUTED, center=True)
        if won:
            pos = (cx + 150, 22) if int(self.anim_time * 3) % 4 < 2 else (cx - 158, 48)
            self.bitmap(SPARKLE, {"X": (255, 250, 220)}, pos)

        # Main panel
        panel = pygame.Rect(60, 88, 520, 220)
        self.draw_panel(panel)

        # Rank emblem: letter (or skull), earned stars
        emblem = pygame.Rect(76, 102, 100, 94)
        self.draw_stone_frame(emblem, (14, 17, 28), (176, 132, 58) if won else (160, 54, 62), shadow=True)
        if won:
            letter_col = GOLD if rank in "SA" else INK
            if age < 0.3:
                letter, letter_col = "?", MUTED
            else:
                letter = rank
            self.text(letter, (emblem.centerx, emblem.y + 38), self.giant, letter_col, center=True)
        else:
            self.bitmap(SKULL, {"X": (238, 232, 216), "o": (22, 10, 22)}, (emblem.centerx - 27, emblem.y + 12), 5)
        earned = {"S": 3, "A": 2, "B": 1, "C": 0}[rank] if won else 0
        for i in range(3):
            lit = i < earned and age > 0.5 + 0.3 * i
            colors = {"X": GOLD, "h": (255, 244, 190)} if lit else {"X": (50, 56, 80), "h": (50, 56, 80)}
            self.bitmap(STAR, colors, (emblem.centerx - 33 + i * 24, emblem.y + 72), 2)

        # Rank title, flavour, new-best badge
        if won:
            rank_title, flavour = RANKS[rank]
        else:
            rank_title, flavour = "FALLEN", "Time ran out. The dark remembers."
        self.text(rank_title, (192, 108), self.body_bold, GOLD if won else RED)
        for i, line in enumerate(self.wrap_text(flavour, self.small, 376, 2)):
            self.text(line, (192, 132 + i * 11), self.small, MUTED)
        if new_best and age > 0.9:
            badge = pygame.Rect(panel.right - 16 - 96, 102, 96, 20)
            self.shape(badge, (92, 68, 22), GOLD, 2, 5, glow=GOLD if self.blink else None)
            self.text("NEW BEST!", badge.center, self.small_bold, (255, 232, 150), center=True)

        # Path efficiency bar (fills in during the reveal)
        track = pygame.Rect(192, 168, 376, 10)
        self.text("PATH EFFICIENCY", (192, 156), self.tiny, MUTED)
        opt_w = int(track.w * min(1.0, s.optimal_moves / max(1, s.moves)) * min(1.0, max(0.0, (age - 0.2) / 0.8)))
        self.draw_bar(track, track.w, (180, 85, 170))
        self.draw_bar(track, opt_w, (50, 160, 200), track_color=(0, 0, 0, 0))
        self.text(f"OPTIMAL {s.optimal_moves}", (192, 186), self.tiny, (120, 210, 236))
        if detour > 0:
            lbl = f"DETOUR +{detour}"
            self.text(lbl, (track.right - self.tiny.size(lbl)[0], 186), self.tiny, (232, 150, 222))

        # Stat cards (numbers count up)
        f = min(1.0, max(0.0, (age - 0.1) / 0.9))
        cards = [
            ("EXPEDITION TIME", f"{game.elapsed * f:.1f} SEC", CYAN),
            ("STEPS TAKEN", f"{int(s.moves * f)}", INK),
            ("SHORTEST ROUTE", f"{int(s.optimal_moves * f)}", GOLD),
            ("EXTRA STEPS", f"+{int(detour * f)}", (255, 160, 100) if detour > 10 else INK),
            ("RELICS FOUND", f"{s.treasures} / {relic_total}", GREEN),
            ("HINTS USED", str(s.hints_used), INK),
        ]
        for i, (label, val, col) in enumerate(cards):
            r = pygame.Rect(72 + (i % 3) * 168, 204 + (i // 3) * 48, 160, 40)
            self.draw_stat_card(r, label, val, col, self.body_bold)

        # Action buttons (keyboard focus and hover share one highlight)
        self.result_rects = []
        total_w = sum(w for _, w in self.RESULT_ACTIONS) + 10 * (len(self.RESULT_ACTIONS) - 1)
        curr_x = cx - total_w // 2
        for i, (label, w) in enumerate(self.RESULT_ACTIONS):
            r = pygame.Rect(curr_x, 320, w, 32)
            self.result_rects.append((label, r))
            self.draw_button(r, label, active=(i == selected), small=True)
            curr_x += w + 10
        self.text("LEFT / RIGHT: SELECT   ENTER: CONFIRM   V: ROUTE   R: REPLAY", (cx, 368),
                  self.small, MUTED, center=True)
        self.present()

    def result_hit(self, pos: Tuple[int, int]) -> Optional[str]:
        return self._hit(self.result_rects, pos)
