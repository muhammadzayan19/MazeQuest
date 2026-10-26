"""Pixel-art backdrop for the start screen: dusk sky, moon, ruined skyline, stone gate and fog."""
from __future__ import annotations
import math
import random
from typing import List, Tuple
import pygame

from display_manager import IW, IH

Color = Tuple[int, int, int]

HORIZON = 262
SKY_TOP: Color = (6, 8, 22)
SKY_LOW: Color = (70, 38, 84)
STONE: Color = (62, 66, 90)
STONE_DARK: Color = (44, 47, 68)
STONE_HI: Color = (88, 94, 124)
PASSAGE_DEEP: Color = (9, 11, 22)
PASSAGE_FAR: Color = (52, 38, 70)
TORCH_POS = [(130, 214), (510, 214)]


def _mix(a: Color, b: Color, t: float) -> Color:
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def _sky_color(y: int) -> Color:
    return _mix(SKY_TOP, SKY_LOW, min(1.0, (y / HORIZON)) ** 1.35)


def gradient_color(stops: List[Tuple[float, Color]], t: float) -> Color:
    """Piecewise-linear colour at ``t`` (0..1) across ``stops`` of (position, colour)."""
    t = max(0.0, min(1.0, t))
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        if t <= p1:
            return _mix(c0, c1, (t - p0) / max(1e-6, p1 - p0))
    return stops[-1][1]


def draw_banded_sky(bg: pygame.Surface, stops: List[Tuple[float, Color]], height: int,
                    ease: float = 1.0, band: int = 10) -> None:
    """Banded sky with a two-row checker dither between bands (classic pixel gradient)."""
    def col(y: int) -> Color:
        return gradient_color(stops, min(1.0, y / height) ** ease)

    for b in range(0, height // band + 1):
        y0 = b * band
        pygame.draw.rect(bg, col(y0 + band // 2), (0, y0, IW, band))
    for b in range(1, height // band + 1):
        y0 = b * band
        above, below = col(y0 - band // 2), col(y0 + band // 2)
        for row in range(2):
            for x in range(row % 2, IW, 2):
                bg.set_at((x, y0 - 2 + row), below)
            for x in range((row + 1) % 2, IW, 2):
                bg.set_at((x, y0 + row), above)


class MenuScene:
    """Draws the animated start-screen scene onto the 640x440 world canvas."""

    BAND = 10

    def __init__(self, sprites) -> None:
        self.sprites = sprites
        rng = random.Random(77)
        self.stars: List[Tuple[int, int, float, float, bool]] = [
            (rng.randint(4, IW - 4), rng.randint(4, 170), rng.uniform(0, 6.28), rng.uniform(1.0, 3.2), rng.random() < 0.18)
            for _ in range(80)]
        self.windows: List[Tuple[int, int, float]] = []
        self.torches = TORCH_POS
        self.bg = self._build_background(rng)
        self.fog = [self._build_fog(rng, 120, 36), self._build_fog(rng, 90, 30)]

    # ------------------------------------------------------------------ build
    def _build_background(self, rng: random.Random) -> pygame.Surface:
        bg = pygame.Surface((IW, IH))
        self._draw_sky(bg)
        self._draw_moon(bg, 566, 64)
        self._draw_skyline(bg, rng)
        self._draw_floor(bg)
        self._draw_gate(bg)
        return bg.convert() if pygame.display.get_surface() else bg

    def _draw_sky(self, bg: pygame.Surface) -> None:
        draw_banded_sky(bg, [(0.0, SKY_TOP), (1.0, SKY_LOW)], HORIZON, ease=1.35, band=self.BAND)

    def _draw_moon(self, bg: pygame.Surface, cx: int, cy: int) -> None:
        sky = _sky_color(cy)
        pygame.draw.circle(bg, (238, 234, 205), (cx, cy), 24)
        pygame.draw.circle(bg, (212, 208, 178), (cx - 8, cy + 6), 5)
        pygame.draw.circle(bg, (212, 208, 178), (cx + 7, cy - 9), 4)
        pygame.draw.circle(bg, (218, 214, 184), (cx + 10, cy + 10), 3)
        pygame.draw.circle(bg, _sky_color(cy), (cx + 11, cy - 4), 20)   # crescent cut-out
        pygame.draw.circle(bg, (238, 234, 205), (cx, cy), 24, 1)

    def _draw_skyline(self, bg: pygame.Surface, rng: random.Random) -> None:
        col, col_far = (19, 16, 40), (30, 24, 56)
        # far hills
        pts = [(0, HORIZON)]
        x = 0
        while x <= IW:
            pts.append((x, HORIZON - 14 - int(10 * math.sin(x / 61.0) + 6 * math.sin(x / 23.0))))
            x += 16
        pts.append((IW, HORIZON))
        pygame.draw.polygon(bg, col_far, pts)
        # ruined towers
        for x in list(range(-6, 100, 34)) + list(range(548, IW + 20, 34)):
            w = rng.choice([22, 26, 30])
            h = rng.randint(54, 112)
            top = HORIZON - h
            pygame.draw.rect(bg, col, (x, top, w, h))
            for cx in range(x, x + w - 2, 8):
                if rng.random() < 0.85:
                    pygame.draw.rect(bg, col, (cx, top - 5, 4, 5))
            if rng.random() < 0.5:
                pygame.draw.polygon(bg, col, [(x - 2, top), (x + w // 2, top - 22), (x + w + 2, top)])
            for _ in range(rng.randint(1, 3)):
                wx, wy = x + rng.randint(4, w - 7), top + rng.randint(10, max(11, h - 16))
                pygame.draw.rect(bg, (34, 28, 60), (wx, wy, 3, 5))
                self.windows.append((wx, wy, rng.uniform(0, 6)))
        pygame.draw.rect(bg, col, (0, HORIZON - 4, IW, 6))

    def _draw_floor(self, bg: pygame.Surface) -> None:
        """Perspective flagstones receding to the horizon."""
        h = IH - HORIZON
        pygame.draw.rect(bg, (26, 24, 40), (0, HORIZON, IW, h))
        ys = [HORIZON]
        k = 1
        while ys[-1] < IH:
            ys.append(int(HORIZON + 5 * k * k * 0.55 + 6 * k))
            k += 1
        for i in range(len(ys) - 1):
            shade = (32, 29, 48) if i % 2 == 0 else (27, 25, 42)
            pygame.draw.rect(bg, shade, (0, ys[i], IW, ys[i + 1] - ys[i]))
            pygame.draw.line(bg, (14, 13, 26), (0, ys[i]), (IW, ys[i]))
            pygame.draw.line(bg, (44, 40, 64), (0, ys[i] + 1), (IW, ys[i] + 1))
        for x in range(-480, IW + 480, 64):
            pygame.draw.line(bg, (14, 13, 26), (IW // 2 + (x - IW // 2) * 0.06, HORIZON), (x, IH))

    def _draw_gate(self, bg: pygame.Surface) -> None:
        """Brick archway framing the menu: outer stone, dark passage, keystone and plinths."""
        outer = pygame.Rect(92, 98, 456, 342)
        radius = 170
        gate = pygame.Surface(outer.size, pygame.SRCALPHA)
        pygame.draw.rect(gate, STONE, gate.get_rect(), border_top_left_radius=radius, border_top_right_radius=radius)
        course = 14
        for row, y in enumerate(range(0, outer.h, course)):
            pygame.draw.line(gate, STONE_DARK, (0, y), (outer.w, y))
            pygame.draw.line(gate, STONE_HI, (0, y + 1), (outer.w, y + 1))
            for x in range(course if row % 2 else 0, outer.w, course * 2):
                pygame.draw.line(gate, STONE_DARK, (x, y), (x, y + course))
        mask = pygame.Surface(outer.size, pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(),
                         border_top_left_radius=radius, border_top_right_radius=radius)
        gate.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        bg.blit(gate, outer.topleft)
        pygame.draw.rect(bg, (30, 32, 48), outer, 2, border_top_left_radius=radius, border_top_right_radius=radius)

        # passage opening with banded depth
        opening = pygame.Rect(168, 150, 304, 290)
        pygame.draw.rect(bg, PASSAGE_DEEP, opening, border_top_left_radius=152, border_top_right_radius=152)
        steps = 7
        for i in range(steps):
            inset = 8 + i * 16
            r = pygame.Rect(opening.x + inset, opening.y + inset, opening.w - 2 * inset, opening.h - inset)
            rad = max(4, 152 - inset)
            pygame.draw.rect(bg, _mix(PASSAGE_DEEP, PASSAGE_FAR, (i / (steps - 1)) ** 1.4), r,
                             border_top_left_radius=rad, border_top_right_radius=rad)
        pygame.draw.rect(bg, (30, 32, 48), opening, 2, border_top_left_radius=152, border_top_right_radius=152)
        pygame.draw.rect(bg, STONE_HI, opening.inflate(6, 6), 1, border_top_left_radius=155, border_top_right_radius=155)

        # keystone and plinths
        key = [(300, 98), (340, 98), (334, 140), (306, 140)]
        pygame.draw.polygon(bg, STONE_HI, key)
        pygame.draw.polygon(bg, STONE_DARK, key, 2)
        for px in (92, 472):
            pygame.draw.rect(bg, STONE_DARK, (px - 6, 410, 100, 30))
            pygame.draw.line(bg, STONE_HI, (px - 6, 410), (px + 93, 410), 2)
        # wall sconces behind the torches
        for tx, ty in TORCH_POS:
            pygame.draw.rect(bg, (30, 28, 40), (tx - 5, ty + 6, 10, 18))
            pygame.draw.rect(bg, (92, 78, 60), (tx - 6, ty + 4, 12, 4))

    def _build_fog(self, rng: random.Random, height: int, count: int) -> pygame.Surface:
        surf = pygame.Surface((IW, height), pygame.SRCALPHA)
        for _ in range(count):
            w, h = rng.randint(30, 90), rng.choice([4, 6, 8])
            x, y = rng.randint(0, IW), rng.randint(0, height - h)
            a = rng.randint(16, 30)
            for off in (-IW, 0, IW):
                pygame.draw.rect(surf, (150, 160, 205, a), (x + off, y, w, h))
        return surf

    # ------------------------------------------------------------------- draw
    def draw(self, canvas: pygame.Surface, t: float) -> None:
        canvas.blit(self.bg, (0, 0))
        for x, y, phase, speed, big in self.stars:
            v = math.sin(t * speed + phase)
            if v > 0.1:
                canvas.set_at((x, y), (255, 255, 255))
                if big and v > 0.7:
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        canvas.set_at((x + dx, y + dy), (190, 200, 240))
            elif v > -0.4:
                canvas.set_at((x, y), (150, 160, 200))
        for wx, wy, phase in self.windows:
            if int(t * 3 + phase) % 7:
                pygame.draw.rect(canvas, (255, 196, 90), (wx, wy, 3, 5))
        # drifting fog (two speeds, wraps seamlessly)
        for fog, y, speed in ((self.fog[0], 238, 7.0), (self.fog[1], 330, 15.0)):
            off = int(t * speed) % IW
            canvas.blit(fog, (off, y))
            canvas.blit(fog, (off - IW, y))
        # torches
        frame = self.sprites.torch_frames[int(t * 7) % len(self.sprites.torch_frames)]
        for tx, ty in self.torches:
            glow = self.sprites.tint_torch
            canvas.blit(glow, (tx - glow.get_width() // 2, ty - glow.get_height() // 2),
                        special_flags=pygame.BLEND_RGB_ADD)
            canvas.blit(frame, (tx - frame.get_width() // 2, ty - frame.get_height() // 2 - 2))
