"""Procedural pixel-art asset generator and cache for MazeQuest."""
from __future__ import annotations
import math
import random
from typing import Dict, List, Optional, Tuple
import pygame
import numpy as np

# Palette Constants
C_VOID = (9, 12, 17)
C_MORTAR = (20, 23, 29)
C_STONE_DARK = (54, 58, 66)
C_STONE_MID = (64, 70, 78)
C_STONE_HI = (86, 93, 105)
C_STONE_RIM = (100, 110, 124)

C_WALL_TOP_SHAD = (20, 24, 31)
C_WALL_TOP = (33, 39, 48)
C_WALL_TOP_HI = (55, 65, 78)

C_WALL_FRONT_BASE = (27, 32, 40)
C_WALL_FRONT_HI = (44, 52, 64)
C_WALL_FRONT_SHAD = (24, 28, 34)

C_GOLD_DARK = (105, 65, 20)
C_GOLD_MID = (195, 125, 35)
C_GOLD_HI = (240, 185, 65)
C_GOLD_LIGHT = (255, 235, 150)

C_CYAN_DEEP = (12, 48, 64)
C_CYAN_MID = (45, 175, 215)
C_CYAN_HI = (95, 235, 250)
C_CYAN_LIGHT = (220, 255, 255)

C_AMBER_FIRE = (245, 95, 25)
C_YELLOW_FIRE = (255, 215, 65)
C_WHITE_FIRE = (255, 250, 210)


def create_pixel_glow(color: Tuple[int, int, int], radius: int, intensity: float = 0.85) -> pygame.Surface:
    """Build a stepped, low-resolution light pool suited to pixel-art scenes."""
    size = radius * 2
    # Sample in two-pixel blocks. A smooth full-resolution gradient reads as
    # blur once the whole game is enlarged; stepped spatial sampling keeps the
    # light edge crisp without introducing harsh concentric brightness rings.
    step = 2
    coords = (np.arange(size) // step) * step
    y, x = np.meshgrid(coords, coords, indexing="ij")
    dist = np.sqrt((x - radius) ** 2 + (y - radius) ** 2) / radius
    dist = np.clip(dist, 0.0, 1.0)
    falloff = np.where(dist < 1.0, (1.0 - dist) ** 1.8, 0.0) * intensity
    surf = pygame.Surface((size, size))
    surf.fill((0, 0, 0))
    rgb = pygame.surfarray.pixels3d(surf)
    for c in range(3):
        rgb[:, :, c] = (color[c] * falloff).astype(np.uint8).T
    del rgb
    return surf


class SpriteCache:
    """Pre-renders and caches all pixel-art textures, animations, and lighting."""

    def __init__(self, tile_w: int = 18, tile_h: int = 16) -> None:
        self.tw = tile_w
        self.th = tile_h
        self.wall_shadow = pygame.Surface((tile_w, 4), pygame.SRCALPHA)
        self.wall_shadow.fill((10, 13, 18, 150))
        self.floor_tiles: List[pygame.Surface] = self._build_floor_tiles()
        self.hero_walk: Dict[str, List[pygame.Surface]] = {}
        self.hero_idle: Dict[str, List[pygame.Surface]] = {}
        self._build_hero_sprites()
        self.torch_frames: List[pygame.Surface] = self._build_torch_frames()
        self.crystal_frames: List[pygame.Surface] = self._build_crystal_frames()
        self.key_frames: List[pygame.Surface] = self._build_key_frames()
        self.chest_closed = self._build_chest(opened=False)
        self.chest_opened = self._build_chest(opened=True)
        self.door_locked = self._build_door(locked=True)
        self.door_unlocked = self._build_door(locked=False)
        self.exit_pedestal = self._build_exit_pedestal()
        self.relic_frames: List[pygame.Surface] = self._build_relic_frames()

        # Lighting glows
        self.glow_torch = create_pixel_glow((255, 140, 25), 28, 0.40)
        self.glow_crystal = create_pixel_glow((35, 180, 245), 24, 0.40)
        self.glow_exit = create_pixel_glow((245, 195, 55), 24, 0.44)
        self.glow_hint = create_pixel_glow((60, 210, 230), 20, 0.42)
        self.glow_player = create_pixel_glow((220, 150, 50), 12, 0.24)

        # UI Icons
        self.icons: Dict[str, pygame.Surface] = self._build_ui_icons()

    def _build_floor_tiles(self) -> List[pygame.Surface]:
        tw, th = self.tw, self.th
        tiles = []
        for var in range(6):
            t = pygame.Surface((tw, th))
            t.fill(C_STONE_DARK)
            if var == 0:
                # Two large offset flagstones
                pygame.draw.line(t, C_MORTAR, (0, 7), (tw-1, 7))
                pygame.draw.line(t, C_MORTAR, (8, 0), (8, 7))
                pygame.draw.line(t, C_MORTAR, (11, 8), (11, th-1))
                pygame.draw.line(t, C_STONE_HI, (0, 0), (7, 0))
                pygame.draw.line(t, C_STONE_HI, (0, 0), (0, 6))
                pygame.draw.line(t, C_STONE_HI, (9, 0), (tw-1, 0))
                pygame.draw.line(t, C_STONE_HI, (0, 8), (10, 8))
                pygame.draw.line(t, C_STONE_HI, (12, 8), (tw-1, 8))
            elif var == 1:
                # Hairline fracture slab
                pygame.draw.line(t, C_MORTAR, (0, 8), (tw-1, 8))
                pygame.draw.line(t, C_MORTAR, (10, 0), (10, th-1))
                pygame.draw.line(t, C_STONE_HI, (0, 0), (tw-1, 0))
                pygame.draw.line(t, C_MORTAR, (3, 2), (6, 5))
                pygame.draw.line(t, C_MORTAR, (6, 5), (5, 7))
                pygame.draw.line(t, C_STONE_HI, (4, 2), (7, 5))
            elif var == 2:
                # Wide worn slab with beveled edges
                pygame.draw.rect(t, C_STONE_MID, (1, 1, tw-2, th-2))
                pygame.draw.line(t, C_STONE_HI, (1, 1), (tw-2, 1))
                pygame.draw.line(t, C_STONE_HI, (1, 1), (1, th-2))
                pygame.draw.line(t, C_MORTAR, (tw-2, 1), (tw-2, th-2))
                pygame.draw.line(t, C_MORTAR, (1, th-2), (tw-2, th-2))
                t.set_at((5, 5), C_STONE_HI)
                t.set_at((12, 9), C_STONE_HI)
            elif var == 3:
                # Small pavers with mossy seams
                pygame.draw.line(t, C_MORTAR, (0, 7), (tw-1, 7))
                pygame.draw.line(t, C_MORTAR, (9, 0), (9, th-1))
                pygame.draw.line(t, C_STONE_HI, (0, 0), (8, 0))
                pygame.draw.line(t, C_STONE_HI, (10, 0), (tw-1, 0))
                pygame.draw.line(t, C_STONE_HI, (0, 8), (8, 8))
                pygame.draw.line(t, C_STONE_HI, (10, 8), (tw-1, 8))
                t.set_at((9, 6), (42, 68, 45))
                t.set_at((8, 7), (35, 58, 38))
                t.set_at((9, 8), (48, 76, 50))
            elif var == 4:
                # Ancient faint runic engraving
                pygame.draw.rect(t, C_STONE_DARK, (0, 0, tw, th))
                pygame.draw.line(t, C_STONE_HI, (0, 0), (tw-1, 0))
                pygame.draw.circle(t, (42, 58, 68), (9, 8), 4, 1)
                pygame.draw.line(t, (42, 58, 68), (9, 5), (9, 11))
                pygame.draw.line(t, (42, 58, 68), (6, 8), (12, 8))
            else:
                # Weathered slate paver
                pygame.draw.line(t, C_MORTAR, (0, 9), (tw-1, 9))
                pygame.draw.line(t, C_MORTAR, (6, 0), (6, 9))
                pygame.draw.line(t, C_MORTAR, (13, 9), (13, th-1))
                pygame.draw.line(t, C_STONE_HI, (0, 0), (tw-1, 0))
                t.set_at((3, 4), C_STONE_HI)
                t.set_at((14, 4), C_STONE_HI)
            tiles.append(t)
        return tiles

    def get_floor_tile(self, r: int, c: int) -> pygame.Surface:
        idx = (r * 11 + c * 17 + 3) % len(self.floor_tiles)
        return self.floor_tiles[idx]

    def _build_hero_sprites(self) -> None:
        """Create 4-directional 18x22 adventurer with walk and idle frames."""
        dirs = ["down", "up", "right", "left"]
        for d in dirs:
            self.hero_walk[d] = []
            self.hero_idle[d] = []

        # Right-facing base frames (Walk: 4 frames, Idle: 2 frames)
        for frame in range(4):
            leg_off = [-1, 0, 1, 0][frame]
            bob = [0, -1, 0, 1][frame]
            
            # --- DOWN (South / Front) ---
            sd = pygame.Surface((18, 22), pygame.SRCALPHA)
            pygame.draw.ellipse(sd, (11, 14, 20, 160), (2, 17, 14, 5))
            # Boots
            pygame.draw.rect(sd, (38, 28, 22), (4, 18 + leg_off, 4, 4))
            pygame.draw.rect(sd, (38, 28, 22), (10, 18 - leg_off, 4, 4))
            pygame.draw.rect(sd, (22, 16, 12), (4, 20 + leg_off, 4, 2))
            pygame.draw.rect(sd, (22, 16, 12), (10, 20 - leg_off, 4, 2))
            # Cloak body
            pygame.draw.polygon(sd, (28, 34, 46), [(3, 10+bob), (15, 10+bob), (16, 18), (2, 18)])
            # Leather tunic
            pygame.draw.rect(sd, (94, 62, 38), (6, 10+bob, 6, 7))
            pygame.draw.line(sd, (150, 102, 58), (6, 10+bob), (11, 10+bob))
            sd.set_at((8, 14+bob), C_GOLD_HI)
            sd.set_at((9, 14+bob), C_GOLD_HI)
            # Hood
            pygame.draw.polygon(sd, (38, 46, 62), [(4, 6+bob), (9, 2+bob), (14, 6+bob), (14, 10+bob), (4, 10+bob)])
            pygame.draw.polygon(sd, (54, 64, 86), [(5, 5+bob), (9, 3+bob), (13, 5+bob), (13, 7+bob), (5, 7+bob)])
            pygame.draw.rect(sd, (18, 22, 28), (6, 6+bob, 6, 4))
            # Eyes
            sd.set_at((7, 8+bob), (140, 230, 245))
            sd.set_at((10, 8+bob), (140, 230, 245))
            self.hero_walk["down"].append(sd)

            # --- UP (North / Back) ---
            su = pygame.Surface((18, 22), pygame.SRCALPHA)
            pygame.draw.ellipse(su, (11, 14, 20, 160), (2, 17, 14, 5))
            pygame.draw.rect(su, (38, 28, 22), (4, 18 + leg_off, 4, 4))
            pygame.draw.rect(su, (38, 28, 22), (10, 18 - leg_off, 4, 4))
            pygame.draw.polygon(su, (28, 34, 46), [(3, 8+bob), (15, 8+bob), (16, 18), (2, 18)])
            pygame.draw.polygon(su, (42, 50, 68), [(5, 9+bob), (13, 9+bob), (14, 17), (4, 17)])
            pygame.draw.line(su, (20, 24, 34), (9, 9+bob), (9, 18))
            pygame.draw.polygon(su, (38, 46, 62), [(4, 5+bob), (9, 2+bob), (14, 5+bob), (14, 9+bob), (4, 9+bob)])
            pygame.draw.polygon(su, (54, 64, 86), [(6, 4+bob), (9, 3+bob), (12, 4+bob), (11, 7+bob), (7, 7+bob)])
            su.set_at((9, 1+bob), (54, 64, 86))
            self.hero_walk["up"].append(su)

            # --- RIGHT (East / Profile) ---
            sr = pygame.Surface((18, 22), pygame.SRCALPHA)
            pygame.draw.ellipse(sr, (11, 14, 20, 160), (2, 17, 14, 5))
            pygame.draw.rect(sr, (38, 28, 22), (5 - leg_off*2, 18, 4, 4))
            pygame.draw.rect(sr, (38, 28, 22), (9 + leg_off*2, 18, 4, 4))
            pygame.draw.rect(sr, (82, 54, 34), (3, 10+bob, 3, 6))
            pygame.draw.rect(sr, (28, 34, 46), (5, 9+bob, 8, 9))
            pygame.draw.rect(sr, (94, 62, 38), (8, 10+bob, 4, 6))
            pygame.draw.polygon(sr, (38, 46, 62), [(3, 6+bob), (8, 2+bob), (13, 5+bob), (13, 10+bob), (4, 10+bob)])
            pygame.draw.polygon(sr, (54, 64, 86), [(5, 4+bob), (8, 3+bob), (11, 5+bob), (11, 8+bob), (6, 8+bob)])
            pygame.draw.rect(sr, (18, 22, 28), (11, 6+bob, 3, 3))
            sr.set_at((12, 7+bob), (140, 230, 245))
            # Adventurer's lantern
            pygame.draw.line(sr, (120, 90, 40), (12, 12+bob), (15, 12+bob))
            pygame.draw.rect(sr, (220, 160, 40), (14, 13+bob, 3, 4))
            sr.set_at((15, 14+bob), (255, 240, 180))
            self.hero_walk["right"].append(sr)

            # --- LEFT: Flip Right ---
            sl = pygame.transform.flip(sr, True, False)
            self.hero_walk["left"].append(sl)

        # Idle frames: frame 0 and gentle breath frame 1
        for d in dirs:
            self.hero_idle[d] = [self.hero_walk[d][1], self.hero_walk[d][3]]

    def _build_torch_frames(self) -> List[pygame.Surface]:
        frames = []
        for f in range(4):
            s = pygame.Surface((18, 20), pygame.SRCALPHA)
            cx, cy = 9, 12
            # Wall sconce bracket
            pygame.draw.rect(s, (32, 28, 24), (cx - 2, cy + 2, 4, 6))
            pygame.draw.line(s, (75, 55, 40), (cx - 3, cy + 2), (cx + 3, cy + 2))
            # Animated flame shape
            tip_x = cx + [-1, 0, 1, 0][f]
            tip_y = cy - 7 - [1, 2, 1, 0][f]
            pygame.draw.polygon(s, C_AMBER_FIRE, [(cx - 3, cy + 1), (tip_x, tip_y), (cx + 3, cy + 1)])
            pygame.draw.polygon(s, C_YELLOW_FIRE, [(cx - 2, cy + 1), (tip_x, tip_y + 2), (cx + 2, cy + 1)])
            pygame.draw.polygon(s, C_WHITE_FIRE, [(cx - 1, cy + 1), (tip_x, tip_y + 4), (cx + 1, cy + 1)])
            frames.append(s)
        return frames

    def _build_crystal_frames(self) -> List[pygame.Surface]:
        frames = []
        for f in range(4):
            s = pygame.Surface((18, 20), pygame.SRCALPHA)
            cx, cy = 9, 10
            bob = [-1, 0, 1, 0][f]
            # Primary central shard
            pygame.draw.polygon(s, (35, 130, 170), [(cx, cy - 7 + bob), (cx + 4, cy - 2 + bob), (cx + 2, cy + 5 + bob),
                                                    (cx, cy + 7 + bob), (cx - 3, cy + 4 + bob), (cx - 3, cy - 3 + bob)])
            pygame.draw.polygon(s, C_CYAN_HI, [(cx, cy - 6 + bob), (cx + 2, cy - 2 + bob), (cx + 1, cy + 4 + bob),
                                               (cx - 1, cy + 2 + bob), (cx - 2, cy - 2 + bob)])
            pygame.draw.polygon(s, C_CYAN_LIGHT, [(cx, cy - 5 + bob), (cx + 1, cy - 2 + bob), (cx, cy + 2 + bob)])
            # Specular gleam moving
            if f in (1, 2):
                s.set_at((cx + 1, cy - 3 + bob), (255, 255, 255))
            # Flanking side crystals
            pygame.draw.polygon(s, (50, 170, 210), [(cx + 3, cy + 1 + bob), (cx + 6, cy + 4 + bob), (cx + 4, cy + 7 + bob)])
            pygame.draw.polygon(s, (25, 95, 130), [(cx - 5, cy + 2 + bob), (cx - 2, cy + 5 + bob), (cx - 4, cy + 7 + bob)])
            frames.append(s)
        return frames

    def _build_key_frames(self) -> List[pygame.Surface]:
        frames = []
        for f in range(4):
            s = pygame.Surface((18, 18), pygame.SRCALPHA)
            cx, cy = 9, 8
            bob = [-1, 0, 1, 0][f]
            # Stone pedestal
            pygame.draw.rect(s, (40, 46, 56), (cx - 5, cy + 5, 10, 3))
            pygame.draw.line(s, (68, 78, 94), (cx - 5, cy + 5), (cx + 4, cy + 5))
            # Ornate floating golden key
            # Key bow (head)
            pygame.draw.circle(s, C_GOLD_HI, (cx - 3, cy - 2 + bob), 3, 1)
            # Shaft
            pygame.draw.line(s, C_GOLD_HI, (cx, cy - 2 + bob), (cx + 5, cy - 2 + bob))
            # Bit teeth
            pygame.draw.line(s, C_GOLD_HI, (cx + 3, cy - 2 + bob), (cx + 3, cy + 1 + bob))
            pygame.draw.line(s, C_GOLD_HI, (cx + 5, cy - 2 + bob), (cx + 5, cy + bob))
            # Sparkling glint
            glint = [(cx - 3, cy - 3 + bob), (cx, cy - 3 + bob), (cx + 3, cy - 3 + bob), (cx + 5, cy - 3 + bob)][f]
            s.set_at(glint, C_GOLD_LIGHT)
            frames.append(s)
        return frames

    def _build_chest(self, opened: bool = False) -> pygame.Surface:
        s = pygame.Surface((18, 16), pygame.SRCALPHA)
        cx, cy = 9, 8
        pygame.draw.ellipse(s, (11, 14, 20, 150), (cx - 8, cy + 3, 16, 5))
        if not opened:
            # Dark oak body
            pygame.draw.rect(s, (95, 58, 32), (cx - 7, cy - 4, 14, 9))
            # Iron strapping
            pygame.draw.line(s, (55, 62, 70), (cx - 7, cy - 4), (cx + 6, cy - 4))
            pygame.draw.line(s, (55, 62, 70), (cx - 7, cy + 4), (cx + 6, cy + 4))
            pygame.draw.line(s, (55, 62, 70), (cx - 4, cy - 4), (cx - 4, cy + 4))
            pygame.draw.line(s, (55, 62, 70), (cx + 3, cy - 4), (cx + 3, cy + 4))
            # Golden lock
            pygame.draw.rect(s, C_GOLD_HI, (cx - 1, cy - 1, 2, 3))
            s.set_at((cx, cy), C_GOLD_LIGHT)
        else:
            # Opened chest
            pygame.draw.rect(s, (75, 45, 25), (cx - 7, cy, 14, 5))
            pygame.draw.polygon(s, (105, 65, 36), [(cx - 7, cy), (cx - 5, cy - 6), (cx + 6, cy - 6), (cx + 6, cy)])
            # Overflowing gold and jewels
            pygame.draw.rect(s, C_GOLD_HI, (cx - 5, cy - 1, 10, 3))
            s.set_at((cx - 3, cy - 1), C_GOLD_LIGHT)
            s.set_at((cx + 1, cy), (235, 65, 65)) # Ruby
            s.set_at((cx + 3, cy - 1), (65, 220, 120)) # Emerald
        return s

    def _build_door(self, locked: bool = True) -> pygame.Surface:
        tw, th = self.tw, self.th
        s = pygame.Surface((tw, th), pygame.SRCALPHA)
        # Stone arch
        pygame.draw.rect(s, (32, 36, 44), (0, 0, tw, th))
        pygame.draw.line(s, (65, 75, 90), (0, 0), (tw - 1, 0))
        # Inner passage opening
        pygame.draw.rect(s, (14, 17, 22), (2, 2, tw - 4, th - 2))
        if locked:
            # Portcullis iron bars
            for bar_x in range(4, tw - 3, 3):
                pygame.draw.line(s, (100, 108, 120), (bar_x, 2), (bar_x, th - 1))
            pygame.draw.line(s, (75, 82, 92), (2, 6), (tw - 3, 6))
            # Glowing golden runic padlock
            pygame.draw.rect(s, C_GOLD_HI, (tw // 2 - 2, th // 2, 4, 4))
            s.set_at((tw // 2, th // 2 + 1), C_GOLD_LIGHT)
        else:
            # Raised portcullis with glowing magical threshold
            pygame.draw.rect(s, (30, 90, 120), (3, 3, tw - 6, 3))
            pygame.draw.line(s, C_CYAN_HI, (2, th - 2), (tw - 3, th - 2))
        return s

    def _build_exit_pedestal(self) -> pygame.Surface:
        tw, th = self.tw, self.th
        s = pygame.Surface((tw, th), pygame.SRCALPHA)
        cx, cy = tw // 2, th // 2
        # Inscribed sacred floor rune circle
        pygame.draw.circle(s, C_GOLD_MID, (cx, cy), 6, 1)
        pygame.draw.line(s, C_GOLD_DARK, (cx - 4, cy), (cx + 4, cy))
        pygame.draw.line(s, C_GOLD_DARK, (cx, cy - 4), (cx, cy + 4))
        return s

    def _build_relic_frames(self) -> List[pygame.Surface]:
        frames = []
        for f in range(4):
            s = pygame.Surface((18, 18), pygame.SRCALPHA)
            cx, cy = 9, 8
            bob = [-1, 0, 1, 0][f]
            # Ancient Golden Chalice / Holy Relic
            pygame.draw.polygon(s, C_GOLD_HI, [(cx - 4, cy - 6 + bob), (cx + 4, cy - 6 + bob),
                                               (cx + 2, cy - 2 + bob), (cx - 2, cy - 2 + bob)])
            pygame.draw.line(s, C_GOLD_MID, (cx, cy - 2 + bob), (cx, cy + 1 + bob))
            pygame.draw.line(s, C_GOLD_HI, (cx - 3, cy + 2 + bob), (cx + 3, cy + 2 + bob))
            # Specular gleam
            s.set_at((cx - 1, cy - 5 + bob), C_GOLD_LIGHT)
            s.set_at((cx, cy - 5 + bob), (255, 255, 255))
            frames.append(s)
        return frames

    def _build_ui_icons(self) -> Dict[str, pygame.Surface]:
        icons = {}
        # Key missing icon (dim silhouette)
        km = pygame.Surface((18, 18), pygame.SRCALPHA)
        pygame.draw.circle(km, (70, 78, 88), (6, 9), 4, 1)
        pygame.draw.line(km, (70, 78, 88), (10, 9), (15, 9))
        pygame.draw.line(km, (70, 78, 88), (13, 9), (13, 12))
        icons["key_missing"] = km

        # Key found icon (golden glowing key)
        kf = pygame.Surface((18, 18), pygame.SRCALPHA)
        pygame.draw.circle(kf, C_GOLD_HI, (6, 9), 4, 2)
        pygame.draw.line(kf, C_GOLD_HI, (10, 9), (16, 9), 2)
        pygame.draw.line(kf, C_GOLD_HI, (14, 9), (14, 13), 2)
        kf.set_at((5, 8), C_GOLD_LIGHT)
        icons["key_found"] = kf

        # Relic / Chalice icon
        rc = pygame.Surface((18, 18), pygame.SRCALPHA)
        pygame.draw.polygon(rc, C_GOLD_HI, [(4, 4), (13, 4), (11, 9), (6, 9)])
        pygame.draw.line(rc, C_GOLD_MID, (8, 9), (8, 12))
        pygame.draw.line(rc, C_GOLD_HI, (5, 13), (12, 13))
        icons["relic"] = rc

        # Boot / Step icon
        bt = pygame.Surface((18, 18), pygame.SRCALPHA)
        pygame.draw.rect(bt, C_STONE_RIM, (5, 4, 4, 7))
        pygame.draw.polygon(bt, C_STONE_RIM, [(5, 11), (13, 11), (13, 14), (5, 14)])
        icons["boot"] = bt

        # Hourglass / Timer icon
        hg = pygame.Surface((18, 18), pygame.SRCALPHA)
        pygame.draw.line(hg, C_STONE_RIM, (5, 4), (12, 4))
        pygame.draw.line(hg, C_STONE_RIM, (5, 13), (12, 13))
        pygame.draw.polygon(hg, C_GOLD_MID, [(5, 4), (12, 4), (9, 9), (5, 13), (12, 13)])
        icons["hourglass"] = hg

        # Pause icon
        ps = pygame.Surface((14, 14), pygame.SRCALPHA)
        pygame.draw.rect(ps, C_GOLD_HI, (3, 2, 3, 10))
        pygame.draw.rect(ps, C_GOLD_HI, (8, 2, 3, 10))
        icons["pause"] = ps

        return icons

    def draw_wall(self, surface: pygame.Surface, x: int, y: int, r: int, c: int,
                  is_south_floor: bool, is_north_floor: bool, is_west_floor: bool, is_east_floor: bool) -> None:
        """Render architectural 2.5D stone masonry wall blocks with depth shading."""
        tw, th = self.tw, self.th
        # Coordinate-seeded variation keeps adjoining stones from reading as a
        # perfectly uniform checker while remaining stable between frames.
        grain = (r * 17 + c * 31 + r * c * 3) % 5
        shade = (-3, -1, 0, 2, 4)[grain]
        top = tuple(max(0, min(255, channel + shade)) for channel in C_WALL_TOP)
        front = tuple(max(0, min(255, channel + shade)) for channel in C_WALL_FRONT_BASE)
        if is_south_floor:
            # Vertical South-Facing Wall Face
            # Stone cap (top 5px)
            pygame.draw.rect(surface, top, (x, y, tw, 5))
            pygame.draw.line(surface, C_WALL_TOP_HI, (x, y), (x + tw - 1, y))
            pygame.draw.line(surface, C_WALL_TOP_SHAD, (x, y + 4), (x + tw - 1, y + 4))

            # Vertical Brick Face (lower 11px)
            pygame.draw.rect(surface, front, (x, y + 5, tw, 11))
            # Horizontal mortar course
            pygame.draw.line(surface, C_MORTAR, (x, y + 10), (x + tw - 1, y + 10))
            # Staggered vertical mortar joints
            joint = 5 + ((r + c) % 3) * 3
            pygame.draw.line(surface, C_MORTAR, (x + joint, y + 5), (x + joint, y + 9))
            pygame.draw.line(surface, C_MORTAR, (x + ((joint + 7) % tw), y + 10), (x + ((joint + 7) % tw), y + 15))
            # Highlight edges on top of bricks
            pygame.draw.line(surface, C_WALL_FRONT_HI, (x, y + 5), (x + tw - 1, y + 5))
            pygame.draw.line(surface, C_WALL_FRONT_HI, (x, y + 11), (x + tw - 1, y + 11))
            # Bottom shadow seam touching floor
            pygame.draw.line(surface, C_MORTAR, (x, y + th - 1), (x + tw - 1, y + th - 1))

            # Translucent drop shadow onto the floor tile below
            surface.blit(self.wall_shadow, (x, y + th))
        else:
            # Wall Top / Interior Masonry Cap
            pygame.draw.rect(surface, C_WALL_TOP_SHAD, (x, y, tw, th))
            pygame.draw.rect(surface, top, (x + 1, y + 1, tw - 2, th - 2))

            if is_north_floor:
                pygame.draw.line(surface, C_WALL_TOP_HI, (x, y), (x + tw - 1, y))
            if is_west_floor:
                pygame.draw.line(surface, C_WALL_TOP_HI, (x, y), (x, y + th - 1))
            if is_east_floor:
                pygame.draw.line(surface, C_WALL_TOP_SHAD, (x + tw - 1, y), (x + tw - 1, y + th - 1))

            # Masonry block borders
            pygame.draw.line(surface, C_MORTAR, (x, y + th - 1), (x + tw - 1, y + th - 1))
            pygame.draw.line(surface, C_MORTAR, (x + tw - 1, y), (x + tw - 1, y + th - 1))
            # Subtle stone grain
            surface.set_at((x + 4 + grain % 5, y + 5), C_WALL_TOP_HI)
            surface.set_at((x + 11, y + 9 + grain % 4), C_WALL_TOP_SHAD)
            if grain == 0:
                pygame.draw.line(surface, C_WALL_TOP_SHAD, (x + 7, y + 3), (x + 9, y + 5))
