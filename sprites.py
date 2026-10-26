"""Procedural pixel-art asset generator and cache for MazeQuest.

Everything is drawn on the 18x16 tile grid with hard pixels: limited palette, 1px dark
outlines, three-tone shading and dithered stone, then scaled up with nearest-neighbour."""
from __future__ import annotations
import math
import random
from typing import Dict, List, Optional, Tuple
import pygame
import numpy as np

from decor_art import DecorArt

# Palette Constants
C_VOID = (9, 12, 17)
C_MORTAR = (22, 25, 40)
C_STONE_DARK = (47, 53, 63)
C_STONE_MID = (63, 71, 82)
C_STONE_HI = (96, 106, 120)
C_STONE_RIM = (150, 160, 184)

C_WALL_TOP_SHAD = (24, 28, 44)
C_WALL_TOP = (52, 58, 84)
C_WALL_TOP_HI = (110, 120, 152)

C_WALL_FRONT_BASE = (70, 78, 108)
C_WALL_FRONT_HI = (98, 108, 142)
C_WALL_FRONT_SHAD = (40, 44, 66)

C_GOLD_DARK = (120, 74, 22)
C_GOLD_MID = (206, 134, 38)
C_GOLD_HI = (244, 190, 66)
C_GOLD_LIGHT = (255, 236, 150)

C_CYAN_DEEP = (14, 56, 80)
C_CYAN_MID = (52, 180, 224)
C_CYAN_HI = (110, 238, 252)
C_CYAN_LIGHT = (222, 255, 255)

C_AMBER_FIRE = (236, 88, 24)
C_YELLOW_FIRE = (255, 190, 50)
C_WHITE_FIRE = (255, 244, 190)

OUT = (10, 12, 22)           # sprite outline colour
Color = Tuple[int, ...]


def _shift(c: Color, amount: int) -> Color:
    return tuple(max(0, min(255, v + amount)) for v in c[:3])


def add_outline(surf: pygame.Surface, color: Color = OUT, body_alpha: int = 200) -> pygame.Surface:
    """Return a copy with a 1px outline around opaque pixels (drawn only on empty pixels)."""
    w, h = surf.get_size()
    out = surf.copy()
    solid = [[surf.get_at((x, y)).a >= body_alpha for x in range(w)] for y in range(h)]
    for y in range(h):
        for x in range(w):
            if solid[y][x] or surf.get_at((x, y)).a >= body_alpha:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and solid[ny][nx]:
                    out.set_at((x, y), (*color[:3], 255))
                    break
    return out


def create_pixel_glow(color: Tuple[int, int, int], radius: int, intensity: float = 0.85,
                      levels: int = 6) -> pygame.Surface:
    """Stepped light pool: 2px sampling blocks and quantised brightness bands (pixel-art rings)."""
    size = radius * 2
    step = 2
    coords = (np.arange(size) // step) * step
    y, x = np.meshgrid(coords, coords, indexing="ij")
    dist = np.clip(np.sqrt((x - radius) ** 2 + (y - radius) ** 2) / radius, 0.0, 1.0)
    falloff = np.where(dist < 1.0, (1.0 - dist) ** 1.5, 0.0) * intensity
    falloff = np.ceil(falloff * levels) / levels * (falloff > 0)
    surf = pygame.Surface((size, size))
    surf.fill((0, 0, 0))
    rgb = pygame.surfarray.pixels3d(surf)
    for c in range(3):
        rgb[:, :, c] = np.clip(color[c] * falloff, 0, 255).astype(np.uint8).T
    del rgb
    return surf


# Per-zone colour shift applied to the floor tiles (adds when positive, subtracts when negative)
ZONE_TINTS = {
    "crypt": (-6, -2, 12),
    "cellar": (-8, 6, -2),
    "nave": (8, -4, -8),
    "keyroom": (-12, -12, -2),
    "sanctum": (14, 8, -8),
    "reliquary": (12, 5, -10),
    "hall": (0, 0, 0),
}

FLOOR_LAYOUTS = [
    [(0, 0, 10, 8), (10, 0, 8, 8), (0, 8, 6, 8), (6, 8, 12, 8)],
    [(0, 0, 18, 16)],
    [(0, 0, 9, 8), (9, 0, 9, 8), (0, 8, 4, 8), (4, 8, 9, 8), (13, 8, 5, 8)],
    [(0, 0, 7, 16), (7, 0, 6, 16), (13, 0, 5, 16)],
    [(0, 0, 18, 16)],
    [(0, 0, 18, 6), (0, 6, 10, 10), (10, 6, 8, 10)],
]


class SpriteCache:
    """Pre-renders and caches all pixel-art textures, animations, and lighting."""

    def __init__(self, tile_w: int = 18, tile_h: int = 16) -> None:
        self.tw = tile_w
        self.th = tile_h
        self.wall_shadow = pygame.Surface((tile_w, 4), pygame.SRCALPHA)
        self.wall_shadow.fill((8, 10, 20, 120))
        pygame.draw.line(self.wall_shadow, (8, 10, 20, 64), (0, 2), (tile_w, 2))
        pygame.draw.line(self.wall_shadow, (8, 10, 20, 28), (0, 3), (tile_w, 3))
        self.floor_tiles: List[pygame.Surface] = self._build_floor_tiles()
        self._zone_tiles: Dict[str, List[pygame.Surface]] = {}
        self.decor = DecorArt()
        self._wall_faces: Dict[int, pygame.Surface] = {}
        self._wall_tops: Dict[tuple, pygame.Surface] = {}
        self.hero_walk: Dict[str, List[pygame.Surface]] = {}
        self.hero_idle: Dict[str, List[pygame.Surface]] = {}
        self._build_hero_sprites()
        self.torch_frames: List[pygame.Surface] = self._build_torch_frames()
        self.crystal_frames: List[pygame.Surface] = self._build_crystal_frames()
        self.key_frames: List[pygame.Surface] = self._build_key_frames()
        self.chest_closed = self._build_chest(opened=False)
        self.chest_opened = self._build_chest(opened=True)
        self.chest_frames = [self.chest_closed, self._chest_stage(1), self._chest_stage(2), self.chest_opened]
        self.door_locked = self._build_door(locked=True)
        self.door_unlocked = self._build_door(locked=False)
        self.door_frames = [self.door_locked, self._build_door(locked=True, lift=3),
                            self._build_door(locked=True, lift=7), self.door_unlocked]
        self.exit_pedestal = self._build_exit_pedestal()
        self.relic_frames: List[pygame.Surface] = self._build_relic_frames()

        # Light pools for the banded lightmap
        self.glow_torch = create_pixel_glow((255, 176, 92), 66, 1.0)
        self.glow_crystal = create_pixel_glow((96, 176, 255), 52, 0.95)
        self.glow_exit = create_pixel_glow((255, 208, 100), 54, 1.0)
        self.glow_hint = create_pixel_glow((96, 230, 240), 34, 0.9)
        self.glow_candle = create_pixel_glow((255, 196, 110), 30, 0.95)
        # Dim coloured pools added after the lightmap so lit areas pick up a warm/cool tint
        self.tint_torch = create_pixel_glow((88, 46, 8), 60, 1.0)
        self.tint_crystal = create_pixel_glow((8, 44, 84), 48, 1.0)
        self.tint_exit = create_pixel_glow((84, 62, 8), 50, 1.0)
        self.glow_player = create_pixel_glow((255, 228, 176), 88, 1.0)

        # UI Icons
        self.icons: Dict[str, pygame.Surface] = self._build_ui_icons()

    # ---------------------------------------------------------------- terrain
    def _build_floor_tiles(self) -> List[pygame.Surface]:
        tw, th = self.tw, self.th
        base = (58, 64, 88)
        tiles = []
        for var, layout in enumerate(FLOOR_LAYOUTS):
            rng = random.Random(40 + var)
            t = pygame.Surface((tw, th))
            t.fill(C_MORTAR)
            for (x, y, w, h) in layout:
                tone = rng.randint(-5, 5)
                col = _shift(base, tone)
                r = pygame.Rect(x, y, w - 1, h - 1)
                pygame.draw.rect(t, col, r)
                pygame.draw.line(t, _shift(col, 30), (r.x, r.y), (r.right - 1, r.y))            # lit top
                pygame.draw.line(t, _shift(col, 16), (r.x, r.y), (r.x, r.bottom - 1))           # lit left
                pygame.draw.line(t, _shift(col, -22), (r.x, r.bottom - 1), (r.right - 1, r.bottom - 1))
                pygame.draw.line(t, _shift(col, -14), (r.right - 1, r.y), (r.right - 1, r.bottom - 1))
                # dithered grain
                for _ in range(max(2, w * h // 28)):
                    gx, gy = rng.randint(r.x + 1, max(r.x + 1, r.right - 2)), rng.randint(r.y + 1, max(r.y + 1, r.bottom - 2))
                    t.set_at((gx, gy), _shift(col, rng.choice((-12, 12))))
                if w > 5 and h > 5:      # checker dither in the lower-right corner for a worn edge
                    for dx in range(3):
                        for dy in range(3):
                            if (dx + dy) % 2 == 0:
                                t.set_at((r.right - 2 - dx, r.bottom - 2 - dy), _shift(col, -9))
            if var == 5:                 # hairline crack
                cx, cy = rng.randint(4, 12), rng.randint(1, 4)
                for step in range(7):
                    t.set_at((cx, cy), C_MORTAR)
                    cx += rng.choice((0, 1, -1)) if step % 2 else 0
                    cy += 1
                    if cy >= th - 1:
                        break
            if var == 3:                 # moss in the seams
                for mx, my in ((9, 7), (8, 8), (9, 8), (10, 8), (6, 8), (5, 8)):
                    if mx < tw and my < th:
                        t.set_at((mx, my), rng.choice(((54, 98, 64), (72, 124, 80))))
            if var == 4:                 # glowing rune
                rune, rune_hi = (44, 92, 116), (96, 188, 216)
                pygame.draw.circle(t, rune, (9, 8), 5, 1)
                pygame.draw.line(t, rune, (9, 4), (9, 12))
                pygame.draw.line(t, rune, (5, 8), (13, 8))
                t.set_at((9, 8), rune_hi)
                t.set_at((9, 4), rune_hi)
            tiles.append(t.convert() if pygame.display.get_surface() else t)
        return tiles

    def get_floor_tile(self, r: int, c: int, zone: str = "hall") -> pygame.Surface:
        # Plain slabs dominate; cracked, mossy and runic tiles are occasional accents.
        table = (0, 1, 2, 0, 1, 2, 3, 0, 1, 5, 2, 4)
        idx = table[(r * 11 + c * 17 + 3) % len(table)]
        if zone == "hall" or zone not in ZONE_TINTS:
            return self.floor_tiles[idx]
        tiles = self._zone_tiles.get(zone)
        if tiles is None:
            add = tuple(max(0, v) for v in ZONE_TINTS[zone])
            sub = tuple(max(0, -v) for v in ZONE_TINTS[zone])
            tiles = []
            for tile in self.floor_tiles:
                t = tile.copy()
                if any(add):
                    t.fill(add, special_flags=pygame.BLEND_RGB_ADD)
                if any(sub):
                    t.fill(sub, special_flags=pygame.BLEND_RGB_SUB)
                tiles.append(t)
            self._zone_tiles[zone] = tiles
        return tiles[idx]

    def _wall_face(self, var: int) -> pygame.Surface:
        face = self._wall_faces.get(var)
        if face is not None:
            return face
        tw, th = self.tw, self.th
        rng = random.Random(200 + var)
        s = pygame.Surface((tw, th))
        s.fill(C_MORTAR)
        # Stone cap: lit rim, body, shadow seam
        pygame.draw.rect(s, (92, 100, 132), (0, 0, tw, 3))
        pygame.draw.line(s, C_WALL_TOP_HI, (0, 0), (tw - 1, 0))
        pygame.draw.line(s, (60, 66, 94), (0, 2), (tw - 1, 2))
        pygame.draw.line(s, (26, 30, 48), (0, 3), (tw - 1, 3))
        # Brick courses (staggered)
        rows = [(4, 3), (8, 3), (12, 3)]
        for i, (y0, bh) in enumerate(rows):
            offset = 0 if (i + var) % 2 == 0 else 4
            for bx in range(-9 + offset, tw, 9):
                x0, x1 = max(0, bx), min(tw - 1, bx + 7)
                if x1 < x0:
                    continue
                col = _shift(C_WALL_FRONT_BASE, rng.randint(-7, 7))
                pygame.draw.rect(s, col, (x0, y0, x1 - x0 + 1, bh))
                pygame.draw.line(s, _shift(col, 26), (x0, y0), (x1, y0))
                pygame.draw.line(s, _shift(col, -20), (x0, y0 + bh - 1), (x1, y0 + bh - 1))
                if rng.random() < 0.5:
                    s.set_at((rng.randint(x0, x1), y0 + 1), _shift(col, 14))
        # Base darkening so the wall sits on the floor
        ao = pygame.Surface((tw, 3), pygame.SRCALPHA)
        for i, a in enumerate((40, 80, 130)):
            pygame.draw.line(ao, (8, 10, 20, a), (0, i), (tw, i))
        s.blit(ao, (0, th - 3))
        pygame.draw.line(s, OUT, (0, th - 1), (tw - 1, th - 1))
        s = s.convert() if pygame.display.get_surface() else s
        self._wall_faces[var] = s
        return s

    def _wall_top(self, var: int, north: bool, west: bool, east: bool) -> pygame.Surface:
        key = (var, north, west, east)
        top = self._wall_tops.get(key)
        if top is not None:
            return top
        tw, th = self.tw, self.th
        rng = random.Random(300 + var)
        s = pygame.Surface((tw, th))
        s.fill((26, 30, 48))
        col = _shift(C_WALL_TOP, rng.randint(-4, 4))
        pygame.draw.rect(s, col, (1, 1, tw - 2, th - 2))
        if north:
            pygame.draw.line(s, C_WALL_TOP_HI, (0, 0), (tw - 1, 0))
            pygame.draw.line(s, _shift(col, 20), (1, 1), (tw - 2, 1))
        if west:
            pygame.draw.line(s, (92, 100, 132), (0, 0), (0, th - 1))
        if east:
            pygame.draw.line(s, (20, 24, 38), (tw - 1, 0), (tw - 1, th - 1))
        pygame.draw.line(s, (20, 24, 38), (0, th - 1), (tw - 1, th - 1))
        for _ in range(7):
            s.set_at((rng.randint(2, tw - 3), rng.randint(2, th - 3)), _shift(col, rng.choice((-10, 10))))
        if var % 3 == 0:
            x, y = rng.randint(5, 11), rng.randint(3, 6)
            for k in range(5):
                s.set_at((x + (k % 2), y + k), (22, 26, 42))
        s = s.convert() if pygame.display.get_surface() else s
        self._wall_tops[key] = s
        return s

    def draw_wall(self, surface: pygame.Surface, x: int, y: int, r: int, c: int,
                  is_south_floor: bool, is_north_floor: bool, is_west_floor: bool, is_east_floor: bool,
                  decor: Optional[str] = None) -> None:
        """Blit a masonry block: lit brick face (plus optional decor overlay) if floor lies south,
        otherwise a stone cap."""
        var = (r * 17 + c * 31 + r * c * 3) % 6
        if is_south_floor:
            surface.blit(self._wall_face(var), (x, y))
            if decor and decor in self.decor.wall:
                options = self.decor.wall[decor]
                surface.blit(options[(r + c) % len(options)], (x, y))
            surface.blit(self.wall_shadow, (x, y + self.th))
        else:
            surface.blit(self._wall_top(var, is_north_floor, is_west_floor, is_east_floor), (x, y))

    # ------------------------------------------------------------------- hero
    def _build_hero_sprites(self) -> None:
        """4-directional 18x22 adventurer with outline, 4 walk frames and a 2-frame idle."""
        CLOAK, CLOAK_D, CLOAK_L = (56, 78, 140), (34, 46, 92), (84, 108, 178)
        HOOD, HOOD_L = (70, 94, 160), (108, 134, 205)
        LEATHER, LEATHER_L, LEATHER_D = (160, 108, 60), (210, 152, 88), (100, 64, 36)
        BOOT, BOOT_D = (84, 60, 42), (44, 30, 22)
        FACE, EYE = (14, 16, 30), (150, 245, 255)
        for d in ("down", "up", "right", "left"):
            self.hero_walk[d] = []
            self.hero_idle[d] = []

        def lantern(s: pygame.Surface, x: int, y: int) -> None:
            pygame.draw.line(s, (150, 112, 52), (x, y - 1), (x, y))
            pygame.draw.rect(s, (255, 150, 44), (x - 1, y + 1, 3, 4))
            pygame.draw.rect(s, (255, 214, 120), (x, y + 2, 1, 2))

        for frame in range(4):
            leg = [-1, 0, 1, 0][frame]
            bob = [0, -1, 0, 1][frame]

            # DOWN (front)
            sd = pygame.Surface((18, 22), pygame.SRCALPHA)
            pygame.draw.ellipse(sd, (8, 10, 20, 150), (2, 18, 14, 4))
            pygame.draw.rect(sd, BOOT, (4, 17 + leg, 4, 4))
            pygame.draw.rect(sd, BOOT, (10, 17 - leg, 4, 4))
            pygame.draw.rect(sd, BOOT_D, (4, 20 + leg, 4, 1))
            pygame.draw.rect(sd, BOOT_D, (10, 20 - leg, 4, 1))
            pygame.draw.polygon(sd, CLOAK_D, [(3, 10 + bob), (15, 10 + bob), (16, 18), (2, 18)])
            pygame.draw.polygon(sd, CLOAK, [(4, 10 + bob), (14, 10 + bob), (15, 17), (3, 17)])
            pygame.draw.rect(sd, LEATHER, (6, 10 + bob, 6, 7))
            pygame.draw.line(sd, LEATHER_L, (6, 10 + bob), (11, 10 + bob))
            pygame.draw.line(sd, LEATHER_D, (6, 13 + bob), (11, 13 + bob))
            sd.set_at((8, 13 + bob), C_GOLD_HI)
            sd.set_at((9, 13 + bob), C_GOLD_LIGHT)
            pygame.draw.polygon(sd, HOOD, [(4, 6 + bob), (9, 2 + bob), (14, 6 + bob), (14, 10 + bob), (4, 10 + bob)])
            pygame.draw.polygon(sd, HOOD_L, [(5, 5 + bob), (9, 3 + bob), (13, 5 + bob), (13, 6 + bob), (5, 6 + bob)])
            pygame.draw.rect(sd, FACE, (6, 6 + bob, 6, 4))
            sd.set_at((7, 8 + bob), EYE)
            sd.set_at((10, 8 + bob), EYE)
            lantern(sd, 16, 12 + bob)
            self.hero_walk["down"].append(add_outline(sd))

            # UP (back)
            su = pygame.Surface((18, 22), pygame.SRCALPHA)
            pygame.draw.ellipse(su, (8, 10, 20, 150), (2, 18, 14, 4))
            pygame.draw.rect(su, BOOT, (4, 17 + leg, 4, 4))
            pygame.draw.rect(su, BOOT, (10, 17 - leg, 4, 4))
            pygame.draw.rect(su, BOOT_D, (4, 20 + leg, 4, 1))
            pygame.draw.rect(su, BOOT_D, (10, 20 - leg, 4, 1))
            pygame.draw.polygon(su, CLOAK_D, [(3, 8 + bob), (15, 8 + bob), (16, 18), (2, 18)])
            pygame.draw.polygon(su, CLOAK, [(5, 9 + bob), (13, 9 + bob), (14, 17), (4, 17)])
            pygame.draw.line(su, CLOAK_D, (9, 9 + bob), (9, 18))
            pygame.draw.line(su, CLOAK_L, (6, 10 + bob), (6, 15))
            pygame.draw.polygon(su, HOOD, [(4, 5 + bob), (9, 2 + bob), (14, 5 + bob), (14, 9 + bob), (4, 9 + bob)])
            pygame.draw.polygon(su, HOOD_L, [(6, 4 + bob), (9, 3 + bob), (12, 4 + bob), (11, 6 + bob), (7, 6 + bob)])
            self.hero_walk["up"].append(add_outline(su))

            # RIGHT (profile); LEFT is its mirror
            sr = pygame.Surface((18, 22), pygame.SRCALPHA)
            pygame.draw.ellipse(sr, (8, 10, 20, 150), (2, 18, 14, 4))
            pygame.draw.rect(sr, BOOT, (5 - leg * 2, 17, 4, 4))
            pygame.draw.rect(sr, BOOT, (9 + leg * 2, 17, 4, 4))
            pygame.draw.rect(sr, BOOT_D, (5 - leg * 2, 20, 4, 1))
            pygame.draw.rect(sr, BOOT_D, (9 + leg * 2, 20, 4, 1))
            pygame.draw.rect(sr, CLOAK_D, (3, 10 + bob, 3, 7))
            pygame.draw.rect(sr, CLOAK, (5, 9 + bob, 8, 9))
            pygame.draw.rect(sr, LEATHER, (8, 10 + bob, 4, 6))
            pygame.draw.line(sr, LEATHER_L, (8, 10 + bob), (11, 10 + bob))
            pygame.draw.polygon(sr, HOOD, [(3, 6 + bob), (8, 2 + bob), (13, 5 + bob), (13, 10 + bob), (4, 10 + bob)])
            pygame.draw.polygon(sr, HOOD_L, [(5, 4 + bob), (8, 3 + bob), (11, 5 + bob), (11, 6 + bob), (6, 6 + bob)])
            pygame.draw.rect(sr, FACE, (11, 6 + bob, 3, 4))
            sr.set_at((12, 8 + bob), EYE)
            pygame.draw.line(sr, (150, 112, 52), (12, 12 + bob), (15, 12 + bob))
            pygame.draw.rect(sr, (255, 150, 44), (14, 13 + bob, 3, 4))
            pygame.draw.rect(sr, (255, 214, 120), (15, 14 + bob, 1, 2))
            sr = add_outline(sr)
            self.hero_walk["right"].append(sr)
            self.hero_walk["left"].append(pygame.transform.flip(sr, True, False))

        for d in self.hero_walk:
            self.hero_idle[d] = [self.hero_walk[d][1], self.hero_walk[d][3]]

    # ------------------------------------------------------------------ props
    def _build_torch_frames(self) -> List[pygame.Surface]:
        frames = []
        for f in range(4):
            s = pygame.Surface((18, 20), pygame.SRCALPHA)
            cx, cy = 9, 13
            # iron sconce
            pygame.draw.rect(s, (60, 54, 62), (cx - 2, cy + 2, 4, 6))
            pygame.draw.rect(s, (110, 100, 110), (cx - 3, cy + 1, 6, 2))
            pygame.draw.line(s, (150, 140, 150), (cx - 3, cy + 1), (cx + 2, cy + 1))
            s = add_outline(s)
            tip_x = cx + [-1, 0, 1, 0][f]
            tip_y = cy - 8 - [0, 1, 0, -1][f]
            pygame.draw.polygon(s, OUT, [(cx - 4, cy + 1), (tip_x, tip_y - 1), (cx + 4, cy + 1)])
            pygame.draw.polygon(s, C_AMBER_FIRE, [(cx - 3, cy + 1), (tip_x, tip_y), (cx + 3, cy + 1)])
            pygame.draw.polygon(s, C_YELLOW_FIRE, [(cx - 2, cy + 1), (tip_x, tip_y + 2), (cx + 2, cy + 1)])
            pygame.draw.polygon(s, C_WHITE_FIRE, [(cx - 1, cy + 1), (tip_x, tip_y + 5), (cx + 1, cy + 1)])
            if f % 2 == 0:
                s.set_at((cx + 3, cy - 7 + f), C_YELLOW_FIRE)   # spark
            frames.append(s)
        return frames

    def _build_crystal_frames(self) -> List[pygame.Surface]:
        frames = []
        for f in range(4):
            s = pygame.Surface((18, 20), pygame.SRCALPHA)
            cx, cy = 9, 10
            bob = [-1, 0, 1, 0][f]
            pygame.draw.ellipse(s, (8, 10, 20, 130), (3, 16, 12, 3))
            pygame.draw.polygon(s, (40, 140, 190), [(cx, cy - 7 + bob), (cx + 4, cy - 2 + bob), (cx + 2, cy + 5 + bob),
                                                    (cx, cy + 7 + bob), (cx - 3, cy + 4 + bob), (cx - 3, cy - 3 + bob)])
            pygame.draw.polygon(s, C_CYAN_HI, [(cx, cy - 6 + bob), (cx + 2, cy - 2 + bob), (cx + 1, cy + 4 + bob),
                                               (cx - 1, cy + 2 + bob), (cx - 2, cy - 2 + bob)])
            pygame.draw.polygon(s, C_CYAN_LIGHT, [(cx, cy - 5 + bob), (cx + 1, cy - 2 + bob), (cx, cy + 2 + bob)])
            pygame.draw.polygon(s, (24, 100, 150), [(cx + 2, cy + 1 + bob), (cx + 4, cy - 2 + bob), (cx + 2, cy + 5 + bob)])
            pygame.draw.polygon(s, (60, 180, 226), [(cx + 3, cy + 1 + bob), (cx + 6, cy + 4 + bob), (cx + 4, cy + 7 + bob)])
            pygame.draw.polygon(s, (28, 108, 150), [(cx - 5, cy + 2 + bob), (cx - 2, cy + 5 + bob), (cx - 4, cy + 7 + bob)])
            if f in (1, 2):
                s.set_at((cx + 1, cy - 3 + bob), (255, 255, 255))
                s.set_at((cx + 2, cy - 4 + bob), C_CYAN_LIGHT)
            frames.append(add_outline(s))
        return frames

    def _build_key_frames(self) -> List[pygame.Surface]:
        frames = []
        for f in range(4):
            s = pygame.Surface((18, 18), pygame.SRCALPHA)
            cx, cy = 9, 8
            bob = [-1, 0, 1, 0][f]
            pygame.draw.rect(s, (62, 70, 94), (cx - 5, cy + 5, 10, 3))
            pygame.draw.line(s, (110, 122, 156), (cx - 5, cy + 5), (cx + 4, cy + 5))
            pygame.draw.circle(s, C_GOLD_HI, (cx - 3, cy - 2 + bob), 3, 1)
            pygame.draw.circle(s, C_GOLD_LIGHT, (cx - 3, cy - 3 + bob), 1)
            pygame.draw.line(s, C_GOLD_HI, (cx, cy - 2 + bob), (cx + 5, cy - 2 + bob), 2)
            pygame.draw.line(s, C_GOLD_MID, (cx + 3, cy - 1 + bob), (cx + 3, cy + 1 + bob))
            pygame.draw.line(s, C_GOLD_MID, (cx + 5, cy - 1 + bob), (cx + 5, cy + bob))
            glint = [(cx - 4, cy - 4 + bob), (cx, cy - 3 + bob), (cx + 3, cy - 3 + bob), (cx + 5, cy - 3 + bob)][f]
            s.set_at(glint, (255, 255, 235))
            frames.append(add_outline(s))
        return frames

    def _build_chest(self, opened: bool = False) -> pygame.Surface:
        s = pygame.Surface((18, 16), pygame.SRCALPHA)
        cx, cy = 9, 8
        pygame.draw.ellipse(s, (8, 10, 20, 130), (cx - 8, cy + 3, 16, 5))
        iron, iron_hi = (86, 94, 112), (140, 150, 170)
        if not opened:
            pygame.draw.rect(s, (112, 68, 38), (cx - 7, cy - 4, 14, 9))
            pygame.draw.rect(s, (150, 96, 54), (cx - 7, cy - 4, 14, 3))
            pygame.draw.line(s, (84, 50, 28), (cx - 7, cy + 4), (cx + 6, cy + 4))
            for x in (cx - 7, cx - 4, cx + 3, cx + 6):
                pygame.draw.line(s, iron, (x, cy - 4), (x, cy + 4))
            pygame.draw.line(s, iron_hi, (cx - 7, cy - 4), (cx + 6, cy - 4))
            pygame.draw.rect(s, C_GOLD_HI, (cx - 1, cy - 1, 3, 4))
            s.set_at((cx, cy), C_GOLD_LIGHT)
            s.set_at((cx, cy + 1), (90, 50, 14))
        else:
            pygame.draw.rect(s, (92, 56, 32), (cx - 7, cy, 14, 5))
            pygame.draw.polygon(s, (130, 82, 46), [(cx - 7, cy), (cx - 5, cy - 6), (cx + 6, cy - 6), (cx + 6, cy)])
            pygame.draw.rect(s, (30, 20, 16), (cx - 5, cy - 5, 10, 4))
            pygame.draw.rect(s, C_GOLD_HI, (cx - 5, cy - 1, 10, 3))
            s.set_at((cx - 3, cy - 1), C_GOLD_LIGHT)
            s.set_at((cx + 1, cy), (240, 70, 70))
            s.set_at((cx + 3, cy - 1), (70, 230, 130))
            s.set_at((cx - 1, cy - 2), (255, 255, 220))
        return add_outline(s)

    def _chest_stage(self, stage: int) -> pygame.Surface:
        """Intermediate chest-opening frames (1: lid cracks open, 2: lid raised, gold glinting)."""
        s = pygame.Surface((18, 16), pygame.SRCALPHA)
        cx, cy = 9, 8
        pygame.draw.ellipse(s, (8, 10, 20, 130), (cx - 8, cy + 3, 16, 5))
        iron, iron_hi = (86, 94, 112), (140, 150, 170)
        pygame.draw.rect(s, (112, 68, 38), (cx - 7, cy - 1, 14, 6))
        pygame.draw.line(s, (84, 50, 28), (cx - 7, cy + 4), (cx + 6, cy + 4))
        for x in (cx - 7, cx + 6):
            pygame.draw.line(s, iron, (x, cy - 1), (x, cy + 4))
        lift = 2 if stage == 1 else 5
        pygame.draw.rect(s, (30, 20, 16), (cx - 6, cy - 2, 12, 2))
        pygame.draw.rect(s, C_GOLD_HI, (cx - 5, cy - 2, 10, 1 if stage == 1 else 2))
        top = cy - 4 - lift
        pygame.draw.polygon(s, (130, 84, 46), [(cx - 7, cy - 3), (cx - 6, top), (cx + 5, top), (cx + 6, cy - 3)])
        pygame.draw.line(s, (176, 118, 66), (cx - 6, top), (cx + 5, top))
        for x in (cx - 4, cx + 3):
            pygame.draw.line(s, iron, (x, top), (x, cy - 3))
        if stage == 2:
            s.set_at((cx - 1, cy - 3), C_GOLD_LIGHT)
            s.set_at((cx + 2, cy - 2), (255, 255, 230))
        return add_outline(s)

    def _build_door(self, locked: bool = True, lift: int = 0) -> pygame.Surface:
        tw, th = self.tw, self.th
        s = pygame.Surface((tw, th), pygame.SRCALPHA)
        pygame.draw.rect(s, (62, 68, 96), (0, 0, tw, th))
        pygame.draw.line(s, C_WALL_TOP_HI, (0, 0), (tw - 1, 0))
        pygame.draw.rect(s, (14, 16, 28), (2, 2, tw - 4, th - 2))
        pygame.draw.rect(s, OUT, (0, 0, tw, th), 1)
        if locked:
            bottom = th - 1 - lift                          # the portcullis rises as `lift` grows
            for bar_x in range(4, tw - 3, 3):
                pygame.draw.line(s, (130, 140, 160), (bar_x, 2), (bar_x, bottom))
                s.set_at((bar_x, 2), (200, 210, 225))
            if lift:
                pygame.draw.line(s, C_CYAN_HI, (2, th - 2), (tw - 3, th - 2))
            for crossbar in (6, 11):
                if crossbar < bottom:
                    pygame.draw.line(s, (96, 104, 124), (2, crossbar), (tw - 3, crossbar))
            if not lift:
                pygame.draw.rect(s, OUT, (tw // 2 - 3, th // 2 - 1, 6, 6))
                pygame.draw.rect(s, C_GOLD_HI, (tw // 2 - 2, th // 2, 4, 4))
                s.set_at((tw // 2 - 1, th // 2 + 1), C_GOLD_LIGHT)
        else:
            pygame.draw.rect(s, (30, 100, 140), (3, 3, tw - 6, 3))
            pygame.draw.line(s, C_CYAN_HI, (2, th - 2), (tw - 3, th - 2))
            for bar_x in range(4, tw - 3, 3):
                pygame.draw.line(s, (130, 140, 160), (bar_x, 2), (bar_x, 4))
        return s

    def _build_exit_pedestal(self) -> pygame.Surface:
        tw, th = self.tw, self.th
        s = pygame.Surface((tw, th), pygame.SRCALPHA)
        cx, cy = tw // 2, th // 2
        pygame.draw.circle(s, C_GOLD_MID, (cx, cy), 7, 1)
        pygame.draw.circle(s, C_GOLD_DARK, (cx, cy), 5, 1)
        pygame.draw.line(s, C_GOLD_DARK, (cx - 4, cy), (cx + 4, cy))
        pygame.draw.line(s, C_GOLD_DARK, (cx, cy - 4), (cx, cy + 4))
        for dx, dy in ((0, -7), (7, 0), (0, 7), (-7, 0)):
            s.set_at((cx + dx, cy + dy), C_GOLD_LIGHT)
        return s

    def _build_relic_frames(self) -> List[pygame.Surface]:
        frames = []
        for f in range(4):
            s = pygame.Surface((18, 18), pygame.SRCALPHA)
            cx, cy = 9, 8
            bob = [-1, 0, 1, 0][f]
            pygame.draw.polygon(s, C_GOLD_HI, [(cx - 4, cy - 6 + bob), (cx + 4, cy - 6 + bob),
                                               (cx + 2, cy - 2 + bob), (cx - 2, cy - 2 + bob)])
            pygame.draw.line(s, C_GOLD_LIGHT, (cx - 3, cy - 6 + bob), (cx + 3, cy - 6 + bob))
            pygame.draw.line(s, C_GOLD_MID, (cx, cy - 2 + bob), (cx, cy + 1 + bob))
            pygame.draw.line(s, C_GOLD_HI, (cx - 3, cy + 2 + bob), (cx + 3, cy + 2 + bob), 2)
            s.set_at((cx - 1, cy - 4 + bob), (255, 255, 255))
            s.set_at((cx + 1, cy - 4 + bob), (240, 70, 90))
            glint = [(cx - 5, cy - 5 + bob), (cx + 5, cy - 4 + bob), (cx + 4, cy + 3 + bob), (cx - 5, cy + 1 + bob)][f]
            s.set_at(glint, (255, 255, 235))
            frames.append(add_outline(s))
        return frames

    def _build_ui_icons(self) -> Dict[str, pygame.Surface]:
        icons = {}

        km = pygame.Surface((18, 18), pygame.SRCALPHA)
        pygame.draw.circle(km, (120, 130, 152), (6, 9), 4, 2)
        pygame.draw.line(km, (120, 130, 152), (10, 9), (15, 9), 2)
        pygame.draw.line(km, (120, 130, 152), (13, 9), (13, 12), 2)
        icons["key_missing"] = add_outline(km)

        kf = pygame.Surface((18, 18), pygame.SRCALPHA)
        pygame.draw.circle(kf, C_GOLD_HI, (6, 9), 4, 2)
        pygame.draw.line(kf, C_GOLD_HI, (10, 9), (16, 9), 2)
        pygame.draw.line(kf, C_GOLD_MID, (14, 9), (14, 13), 2)
        kf.set_at((5, 7), C_GOLD_LIGHT)
        icons["key_found"] = add_outline(kf)

        rc = pygame.Surface((18, 18), pygame.SRCALPHA)
        pygame.draw.polygon(rc, C_GOLD_HI, [(4, 3), (13, 3), (11, 9), (6, 9)])
        pygame.draw.line(rc, C_GOLD_LIGHT, (5, 4), (12, 4))
        pygame.draw.line(rc, C_GOLD_MID, (8, 9), (8, 12), 2)
        pygame.draw.line(rc, C_GOLD_HI, (4, 13), (12, 13), 2)
        icons["relic"] = add_outline(rc)

        bt = pygame.Surface((18, 18), pygame.SRCALPHA)
        pygame.draw.rect(bt, (170, 180, 204), (5, 3, 4, 8))
        pygame.draw.polygon(bt, (170, 180, 204), [(5, 11), (13, 11), (13, 14), (5, 14)])
        pygame.draw.line(bt, (110, 120, 146), (5, 14), (13, 14))
        icons["boot"] = add_outline(bt)

        hg = pygame.Surface((18, 18), pygame.SRCALPHA)
        pygame.draw.line(hg, (170, 180, 204), (4, 3), (12, 3), 2)
        pygame.draw.line(hg, (170, 180, 204), (4, 14), (12, 14), 2)
        pygame.draw.polygon(hg, C_GOLD_HI, [(5, 4), (11, 4), (8, 8), (5, 13), (11, 13), (8, 8)])
        hg.set_at((8, 6), C_GOLD_LIGHT)
        icons["hourglass"] = add_outline(hg)

        ps = pygame.Surface((14, 14), pygame.SRCALPHA)
        pygame.draw.rect(ps, C_GOLD_HI, (3, 2, 3, 10))
        pygame.draw.rect(ps, C_GOLD_HI, (8, 2, 3, 10))
        icons["pause"] = add_outline(ps)
        return icons
