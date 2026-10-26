"""Pixel art for dungeon dressing: floor decals, wall overlays, candles, runes and bats (18x16 tiles)."""
from __future__ import annotations
import random
from typing import Dict, List
import pygame

TW, TH = 18, 16
OUT = (10, 12, 22)
BONE, BONE_D = (226, 218, 194), (150, 142, 122)


def _surf(w: int = TW, h: int = TH) -> pygame.Surface:
    return pygame.Surface((w, h), pygame.SRCALPHA)


def _px(s: pygame.Surface, pts, color) -> None:
    for x, y in pts:
        if 0 <= x < s.get_width() and 0 <= y < s.get_height():
            s.set_at((x, y), color)


# ------------------------------------------------------------------ floor decals
def cobweb() -> pygame.Surface:
    """Top-left corner cobweb (mirror it for the right corner)."""
    s = _surf()
    web, web_d = (214, 220, 238, 190), (160, 168, 192, 140)
    for end in ((12, 0), (9, 5), (5, 9), (0, 12), (7, 7)):
        pygame.draw.line(s, web_d, (0, 0), end)
    for r in (4, 8):
        pts = [(r, 0), (int(r * 0.85), int(r * 0.45)), (int(r * 0.5), int(r * 0.85)), (0, r)]
        pygame.draw.lines(s, web, False, pts)
    s.set_at((0, 0), (240, 244, 255, 230))
    return s


def bones(variant: int) -> List[pygame.Surface]:
    out = []
    for v in range(2):
        s = _surf()
        if v == 0:                                          # skull and a crossed bone
            pygame.draw.rect(s, BONE, (5, 6, 6, 5))
            pygame.draw.rect(s, BONE_D, (5, 10, 6, 1))
            _px(s, [(6, 8), (9, 8)], OUT)
            _px(s, [(7, 10), (9, 10)], OUT)
            pygame.draw.line(s, BONE, (2, 13), (9, 11))
            pygame.draw.line(s, BONE_D, (2, 14), (9, 12))
            _px(s, [(2, 12), (1, 13), (2, 14)], BONE)
        else:                                               # scattered ribs and a long bone
            pygame.draw.line(s, BONE, (3, 9), (14, 8))
            pygame.draw.line(s, BONE_D, (3, 10), (14, 9))
            _px(s, [(2, 8), (2, 10), (15, 7), (15, 9)], BONE)
            for x in (6, 9, 12):
                pygame.draw.line(s, BONE, (x, 11), (x + 1, 13))
        out.append(s)
    return out


def rubble() -> List[pygame.Surface]:
    out = []
    for v in range(2):
        rng = random.Random(30 + v)
        s = _surf()
        for _ in range(4):
            x, y = rng.randint(2, 12), rng.randint(7, 12)
            w, h = rng.randint(2, 4), rng.randint(2, 3)
            pygame.draw.rect(s, (96, 102, 126), (x, y, w, h))
            pygame.draw.line(s, (140, 148, 172), (x, y), (x + w - 1, y))
            pygame.draw.line(s, (52, 56, 76), (x, y + h - 1), (x + w - 1, y + h - 1))
        out.append(s)
    return out


def blood() -> pygame.Surface:
    s = _surf()
    rng = random.Random(8)
    for _ in range(16):
        s.set_at((rng.randint(4, 13), rng.randint(5, 12)), rng.choice(((122, 26, 40, 230), (84, 14, 28, 230))))
    pygame.draw.rect(s, (112, 22, 36, 230), (7, 8, 4, 2))
    return s


def puddle() -> List[pygame.Surface]:
    out = []
    for v in range(2):
        s = _surf()
        w = 10 + v * 2
        pygame.draw.ellipse(s, (22, 38, 68, 235), (9 - w // 2, 7, w, 6))
        pygame.draw.ellipse(s, (54, 84, 134, 255), (9 - w // 2, 7, w, 6), 1)
        _px(s, [(7 - v, 9), (8 - v, 9), (11, 10)], (150, 196, 244, 255))
        out.append(s)
    return out


def moss() -> List[pygame.Surface]:
    out = []
    for v in range(2):
        rng = random.Random(60 + v)
        s = _surf()
        for _ in range(22):
            x, y = rng.randint(1, 15), rng.randint(2, 13)
            if rng.random() < 0.8 - abs(x - 8) * 0.04:
                s.set_at((x, y), rng.choice(((46, 94, 58, 255), (70, 128, 80, 255), (34, 70, 46, 255))))
        out.append(s)
    return out


def coins() -> List[pygame.Surface]:
    out = []
    for v in range(2):
        rng = random.Random(90 + v)
        s = _surf()
        for _ in range(5):
            x, y = rng.randint(3, 13), rng.randint(6, 12)
            pygame.draw.rect(s, (230, 170, 52), (x, y, 2, 2))
            s.set_at((x, y), (255, 236, 150))
            s.set_at((x + 1, y + 1), (150, 96, 24))
        out.append(s)
    return out


def carpet() -> pygame.Surface:
    s = pygame.Surface((TW, TH))
    s.fill((124, 30, 44))
    pygame.draw.line(s, (170, 44, 58), (0, 3), (TW - 1, 3))
    pygame.draw.line(s, (84, 18, 32), (0, TH - 4), (TW - 1, TH - 4))
    for y in (1, TH - 2):
        pygame.draw.line(s, (214, 160, 60), (0, y), (TW - 1, y))
    pygame.draw.line(s, (150, 100, 36), (0, 2), (TW - 1, 2))
    pygame.draw.line(s, (150, 100, 36), (0, TH - 3), (TW - 1, TH - 3))
    pygame.draw.polygon(s, (214, 160, 60), [(9, 4), (13, 8), (9, 12), (5, 8)])
    pygame.draw.polygon(s, (124, 30, 44), [(9, 6), (11, 8), (9, 10), (7, 8)])
    for x in (0, TW - 1):
        s.set_at((x, 8), (214, 160, 60))
    return s.convert() if pygame.display.get_surface() else s


def rune_pulses() -> List[pygame.Surface]:
    """Opaque black-background glyphs at 4 intensities, meant for additive blending."""
    out = []
    for level in range(4):
        k = 0.35 + 0.2 * level
        col = (int(90 * k), int(210 * k), int(250 * k))
        s = pygame.Surface((TW, TH))
        pygame.draw.circle(s, col, (9, 8), 6, 1)
        pygame.draw.line(s, col, (9, 3), (9, 13))
        pygame.draw.line(s, col, (4, 8), (14, 8))
        pygame.draw.line(s, col, (5, 4), (13, 12))
        pygame.draw.line(s, col, (13, 4), (5, 12))
        s.set_at((9, 8), (int(255 * k), int(255 * k), int(255 * k)))
        out.append(s)
    return out


def candles() -> List[pygame.Surface]:
    out = []
    for f in range(2):
        s = _surf()
        pygame.draw.rect(s, (70, 62, 66), (6, 12, 6, 2))
        pygame.draw.rect(s, (224, 216, 192), (8, 8, 3, 5))
        pygame.draw.line(s, (252, 246, 224), (8, 8), (8, 12))
        pygame.draw.line(s, (150, 140, 118), (10, 9), (10, 12))
        flame = [(9, 7), (9, 6)] if f == 0 else [(9, 7), (10, 6)]
        pygame.draw.rect(s, (255, 150, 40), (8, 6, 3, 2))
        _px(s, flame, (255, 232, 140))
        s.set_at((9, 5), (255, 190, 60))
        out.append(s)
    return out


# ------------------------------------------------------------------ wall overlays
def banner(color: str) -> pygame.Surface:
    s = _surf()
    base, hi, lo = {"red": ((150, 36, 46), (196, 72, 72), (96, 22, 34)),
                    "blue": ((44, 78, 156), (84, 122, 206), (28, 48, 104))}[color]
    pygame.draw.line(s, (110, 80, 44), (3, 3), (14, 3), 2)
    pygame.draw.polygon(s, base, [(5, 4), (12, 4), (12, 12), (8, 15), (5, 12)])
    pygame.draw.line(s, hi, (5, 4), (5, 12))
    pygame.draw.line(s, lo, (12, 4), (12, 12))
    pygame.draw.polygon(s, (230, 180, 70), [(8, 6), (10, 8), (8, 10), (6, 8)])
    pygame.draw.polygon(s, base, [(8, 7), (9, 8), (8, 9), (7, 8)])
    _px(s, [(3, 3), (14, 3)], (200, 170, 100))
    return s


def skull_niche() -> pygame.Surface:
    s = _surf()
    pygame.draw.rect(s, (8, 10, 20), (5, 4, 8, 9))
    pygame.draw.rect(s, (52, 58, 84), (5, 4, 8, 9), 1)
    pygame.draw.line(s, (96, 104, 136), (5, 4), (12, 4))
    pygame.draw.rect(s, BONE, (7, 6, 5, 4))
    pygame.draw.rect(s, BONE_D, (8, 10, 3, 1))
    _px(s, [(8, 8), (10, 8)], OUT)
    _px(s, [(9, 9)], BONE_D)
    return s


def chains() -> pygame.Surface:
    s = _surf()
    for x, off in ((5, 0), (12, 1)):
        for y in range(3, 12):
            s.set_at((x, y), (132, 140, 158, 255) if (y + off) % 2 else (72, 78, 94, 255))
        pygame.draw.rect(s, (96, 102, 120), (x - 1, 12, 3, 2), 1)
        s.set_at((x, 2), (60, 64, 80, 255))
    pygame.draw.line(s, (60, 64, 80), (3, 2), (14, 2))
    return s


def window() -> pygame.Surface:
    s = _surf()
    pygame.draw.rect(s, (66, 74, 104), (5, 2, 8, 11))
    pygame.draw.rect(s, (8, 10, 24), (6, 3, 6, 9))
    for y in range(3, 12):
        t = 1 - (y - 3) / 8
        pygame.draw.line(s, (int(20 + 70 * t), int(34 + 100 * t), int(70 + 130 * t)), (6, y), (11, y))
    for x in (7, 9, 11):
        pygame.draw.line(s, (96, 104, 128), (x, 3), (x, 11))
    pygame.draw.line(s, (140, 150, 176), (5, 2), (12, 2))
    return s


def damaged() -> pygame.Surface:
    s = _surf()
    pygame.draw.polygon(s, (8, 10, 20), [(7, 6), (11, 5), (12, 9), (9, 11), (6, 9)])
    pygame.draw.polygon(s, (24, 28, 44), [(8, 7), (10, 6), (11, 9), (9, 10)])
    for pts in (((6, 9), (3, 12), (4, 15)), ((11, 5), (14, 4), (15, 2))):
        pygame.draw.lines(s, (22, 26, 42), False, pts)
    _px(s, [(5, 15), (9, 14), (11, 15)], (96, 102, 126))
    return s


def arch() -> pygame.Surface:
    s = _surf()
    stone, hi, lo = (104, 112, 146), (150, 160, 194), (52, 58, 84)
    pygame.draw.rect(s, stone, (0, 0, TW, 6))
    pygame.draw.line(s, hi, (0, 0), (TW - 1, 0))
    pygame.draw.polygon(s, hi, [(7, 0), (11, 0), (10, 5), (8, 5)])
    pygame.draw.polygon(s, lo, [(7, 0), (11, 0), (10, 5), (8, 5)], 1)
    for x0, x1 in ((1, 4), (4, 6), (12, 14), (14, 17)):
        pygame.draw.line(s, lo, (x0, 5), (x1, 0))
    pygame.draw.line(s, lo, (0, 5), (TW - 1, 5))
    pygame.draw.rect(s, (14, 16, 28), (2, 6, TW - 4, 10))
    return s


def column() -> pygame.Surface:
    s = _surf()
    shaft = [(0, 40, 4), (1, 90, 14), (2, 130, 22), (3, 150, 28), (4, 116, 18), (5, 70, 10)]
    pygame.draw.rect(s, (14, 16, 28), (0, 0, TW, TH))
    for i in range(4, 14):
        t = (i - 4) / 9
        col = (int(110 - 50 * t), int(118 - 50 * t), int(150 - 60 * t))
        pygame.draw.line(s, col, (i, 3), (i, 13))
    pygame.draw.line(s, (170, 180, 214), (5, 3), (5, 13))
    pygame.draw.line(s, (60, 64, 92), (9, 3), (9, 13))
    pygame.draw.rect(s, (120, 130, 164), (2, 0, 14, 3))              # capital
    pygame.draw.line(s, (190, 200, 232), (2, 0), (15, 0))
    pygame.draw.rect(s, (70, 76, 104), (2, 2, 14, 1))
    pygame.draw.rect(s, (96, 104, 138), (2, 13, 14, 3))              # base
    pygame.draw.line(s, (50, 56, 80), (2, 15), (15, 15))
    return s


def bookshelf() -> pygame.Surface:
    s = pygame.Surface((TW, TH), pygame.SRCALPHA)
    wood, wood_d = (108, 70, 40), (62, 38, 22)
    pygame.draw.rect(s, wood_d, (0, 0, TW, TH))
    pygame.draw.rect(s, (22, 16, 14), (1, 1, TW - 2, TH - 3))
    rng = random.Random(5)
    palette = [(150, 44, 52), (60, 90, 160), (60, 130, 90), (200, 160, 70), (120, 70, 150), (180, 100, 50)]
    for y0, y1 in ((2, 7), (9, 14)):
        x = 2
        while x < TW - 2:
            w = rng.choice((1, 2, 2, 3))
            if x + w > TW - 2:
                break
            if rng.random() < 0.1:
                x += w
                continue
            top = y0 + rng.choice((0, 0, 1))
            col = rng.choice(palette)
            pygame.draw.rect(s, col, (x, top, w, y1 - top))
            pygame.draw.line(s, tuple(min(255, v + 40) for v in col), (x, top), (x, y1 - 1))
            x += w
        pygame.draw.line(s, wood, (1, y1), (TW - 2, y1))
        pygame.draw.line(s, (150, 104, 62), (1, y1), (TW - 2, y1))
    pygame.draw.rect(s, wood, (0, 0, TW, 1))
    pygame.draw.line(s, (180, 130, 80), (0, 0), (TW - 1, 0))
    return s


def bat_frames() -> List[pygame.Surface]:
    out = []
    for f in range(2):
        s = _surf(11, 6)
        c = (22, 18, 34, 255)
        pygame.draw.rect(s, c, (4, 2, 3, 3))
        _px(s, [(4, 1), (6, 1)], c)
        if f == 0:
            pygame.draw.polygon(s, c, [(4, 3), (0, 0), (1, 4), (3, 4)])
            pygame.draw.polygon(s, c, [(6, 3), (10, 0), (9, 4), (7, 4)])
        else:
            pygame.draw.polygon(s, c, [(4, 3), (0, 5), (2, 3), (3, 2)])
            pygame.draw.polygon(s, c, [(6, 3), (10, 5), (8, 3), (7, 2)])
        _px(s, [(4, 2), (6, 2)], (255, 70, 60, 255))
        out.append(s)
    return out


class DecorArt:
    """All decoration sprites, built once."""

    def __init__(self) -> None:
        web = cobweb()
        self.floor: Dict[str, List[pygame.Surface]] = {
            "cobweb_nw": [web],
            "cobweb_ne": [pygame.transform.flip(web, True, False)],
            "bones": bones(0),
            "rubble": rubble(),
            "blood": [blood()],
            "puddle": puddle(),
            "moss": moss(),
            "coins": coins(),
        }
        self.carpet = carpet()
        self.rune_pulses = rune_pulses()
        self.candle_frames = candles()
        self.wall: Dict[str, List[pygame.Surface]] = {
            "banner": [banner("red"), banner("blue")],
            "skull_niche": [skull_niche()],
            "chains": [chains()],
            "window": [window()],
            "damaged": [damaged()],
            "arch": [arch()],
            "column": [column()],
            "bookshelf": [bookshelf()],
        }
        self.bat_frames = bat_frames()
