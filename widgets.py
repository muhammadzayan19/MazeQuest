"""Pixel-art UI painting. Widgets queue draw commands in logical 640x440 coordinates;
the commands are rendered at the window's native resolution on top of the scaled
world with hard edges only (bitmap font, stepped corners, no anti-aliasing or blur)."""
from __future__ import annotations
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
import pygame

from sprites import C_GOLD_HI, C_GOLD_LIGHT

Color = Tuple[int, ...]

# Pixel-theme palette (all text colours keep >= 4.5:1 contrast on the panel fills)
INK: Color = (240, 236, 222)
MUTED: Color = (178, 188, 204)
GOLD: Color = (255, 200, 70)
GOLD_LIGHT: Color = C_GOLD_LIGHT
CYAN: Color = (110, 230, 250)
GREEN: Color = (120, 240, 160)
RED: Color = (255, 112, 92)
ORANGE: Color = (255, 160, 100)
DARK: Color = (9, 11, 20)
PANEL_FILL: Color = (22, 26, 38)
PANEL_BG: Color = PANEL_FILL
PANEL_BORDER: Color = (132, 100, 52)
BTN_FILL: Color = (36, 42, 62)
BTN_BORDER: Color = (104, 92, 70)
BTN_LIT: Color = (78, 62, 30)
HOVER_BG: Color = (44, 50, 72)
SHADOW: Color = (4, 6, 10)

FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"

ARROW_R = [
    "oo.......",
    "oXo......",
    "oXXo.....",
    "oXXXo....",
    "oXXXXo...",
    "oXXXo....",
    "oXXo.....",
    "oXo......",
    "oo.......",
]
STAR = [
    "....h....",
    "....X....",
    "...XXX...",
    "XXXXXXXXX",
    ".XXXXXXX.",
    "..XXXXX..",
    "..XXXXX..",
    ".XXX.XXX.",
    ".XX...XX.",
]
SKULL = [
    "..XXXXXXX..",
    ".XXXXXXXXX.",
    "XXXXXXXXXXX",
    "XXooXXXooXX",
    "XooooXooooX",
    "XXooXXXooXX",
    "XXXXXoXXXXX",
    ".XXXXXXXXX.",
    "..XoXoXoX..",
    "..XXXXXXX..",
]
SPARKLE = [
    "..X..",
    "..X..",
    "XXXXX",
    "..X..",
    "..X..",
]


def lighten(c: Color, amount: int) -> Color:
    return tuple(min(255, v + amount) for v in c[:3])


def darken(c: Color, amount: int) -> Color:
    return tuple(max(0, v - amount) for v in c[:3])


def mix(a: Color, b: Color, t: float) -> Color:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def luminance(c: Color) -> float:
    def lin(v: int) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(v) for v in c[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: Color, b: Color) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


class Face:
    """A bitmap font on an 8px design grid. Drawn crisp: the pixel size snaps to multiples of 8."""

    def __init__(self, path: Optional[Path], size: int) -> None:
        self.path = path
        self.size_px = size
        self._fonts: Dict[int, pygame.font.Font] = {}
        self._caps: Dict[int, Tuple[int, int]] = {}
        box = self.font(size).render("H", False, (255, 255, 255)).get_bounding_rect()
        self.cap_top = box.y
        self.cap_h = max(1, box.h)

    def font(self, px: int) -> pygame.font.Font:
        f = self._fonts.get(px)
        if f is None:
            if self.path is not None and self.path.exists():
                f = pygame.font.Font(str(self.path), px)
            else:
                f = pygame.font.SysFont("consolas,couriernew,monospace", px, bold=True)
            self._fonts[px] = f
        return f

    def size(self, text: str) -> Tuple[int, int]:
        return self.font(self.size_px).size(text)

    def px_for(self, scale: float) -> int:
        """Pixel size for a render scale, snapped to the 8px grid (never noticeably larger than ideal)."""
        return 8 * max(1, int(self.size_px * scale / 8 + 0.1))

    def caps_px(self, px: int) -> Tuple[int, int]:
        box = self._caps.get(px)
        if box is None:
            r = self.font(px).render("H", False, (255, 255, 255)).get_bounding_rect()
            box = self._caps[px] = (r.y, max(1, r.h))
        return box


def _notched(x0: int, y0: int, x1: int, y1: int, n: int) -> List[Tuple[int, int]]:
    """Rectangle polygon with stepped (pixel) corners; (x1, y1) are inclusive coordinates."""
    if n <= 0:
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return [(x0 + n, y0), (x1 - n, y0), (x1 - n, y0 + n), (x1, y0 + n), (x1, y1 - n), (x1 - n, y1 - n),
            (x1 - n, y1), (x0 + n, y1), (x0 + n, y1 - n), (x0, y1 - n), (x0, y0 + n), (x0 + n, y0 + n)]


class Painter:
    """Owns the fonts and the draw-command queue; renders it at native resolution."""

    canvas: pygame.Surface

    def __init__(self, canvas: pygame.Surface) -> None:
        self.canvas = canvas
        self._cmds: List[tuple] = []
        self._text_cache: Dict[tuple, pygame.Surface] = {}
        self._blit_cache: Dict[tuple, Tuple[pygame.Surface, pygame.Surface]] = {}
        self._dim_cache: Dict[tuple, pygame.Surface] = {}
        self._cache_scale = 0.0
        self.blink = True            # toggled by the UI each half second
        self._init_fonts()

    # ------------------------------------------------------------------ fonts
    def _init_fonts(self) -> None:
        """Silkscreen for UI text and Press Start 2P for the logo (both on an 8px grid)."""
        pygame.font.init()
        sil = FONT_DIR / "Silkscreen-Regular.ttf"
        silb = FONT_DIR / "Silkscreen-Bold.ttf"
        ps = FONT_DIR / "PressStart2P.ttf"
        self.giant = Face(ps, 48)
        self.huge = Face(ps, 32)
        self.large = Face(silb, 16)
        self.title = Face(silb, 16)
        self.body = Face(sil, 16)
        self.body_bold = Face(silb, 16)
        self.small = Face(sil, 8)
        self.small_bold = Face(silb, 8)
        self.tiny = Face(sil, 8)

    # ----------------------------------------------------------- command queue
    def clear_commands(self) -> None:
        self._cmds = []

    def fit_text(self, value: Any, font: Face, max_w: int) -> str:
        """Truncate with '..' so rendered text never exceeds max_w logical pixels."""
        val = str(value)
        if font.size(val)[0] <= max_w:
            return val
        while val and font.size(val + "..")[0] > max_w:
            val = val[:-1]
        return val + ".."

    def wrap_text(self, value: Any, font: Face, max_w: int, max_lines: int = 2) -> List[str]:
        """Greedy word-wrap into at most ``max_lines`` lines; the last line is truncated if needed."""
        lines: List[str] = []
        cur = ""
        for word in str(value).split():
            trial = f"{cur} {word}".strip()
            if font.size(trial)[0] <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
        if len(lines) > max_lines:
            lines = lines[:max_lines - 1] + [" ".join(lines[max_lines - 1:])]
        return [self.fit_text(line, font, max_w) for line in lines]

    def text(self, value: Any, pos: Tuple[float, float], font: Optional[Face] = None,
             color: Color = INK, shadow: bool = True, center: bool = False,
             vcenter: bool = False) -> None:
        """Queue text. ``pos`` is the top-left of the capitals, their centre if ``center``,
        or left-aligned with the capitals vertically centred on ``pos[1]`` if ``vcenter``."""
        mode = "center" if center else "vcenter" if vcenter else "top"
        self._cmds.append(("text", str(value), font or self.body, tuple(color[:3]), pos[0], pos[1], mode, shadow))

    def shape(self, rect: pygame.Rect, fill: Any, border: Optional[Color] = None, bw: int = 1,
              radius: int = 0, shadow: bool = False, glow: Optional[Color] = None, bevel: bool = True) -> None:
        """Queue a pixel box with stepped corners. ``radius`` is mapped to a 0-3px corner notch.
        ``fill`` is a colour (3- or 4-tuple), a ``(top, bottom)`` pair (averaged) or None."""
        if fill is not None and isinstance(fill[0], tuple):
            fill = mix(fill[0], fill[1], 0.5)
        notch = 0 if radius <= 0 else min(3, 1 + radius // 5)
        self._cmds.append(("shape", pygame.Rect(rect), fill, border, bw, notch, shadow, glow, bevel))

    def line(self, color: Color, p1: Tuple[float, float], p2: Tuple[float, float], width: float = 1) -> None:
        self._cmds.append(("line", tuple(color), p1, p2, width))

    def poly(self, color: Color, points: List[Tuple[float, float]]) -> None:
        self._cmds.append(("poly", tuple(color), list(points)))

    def blit(self, surf: pygame.Surface, pos: Tuple[float, float], alpha: int = 255,
             size: Optional[Tuple[int, int]] = None) -> None:
        """Queue a surface, nearest-scaled. ``size`` is its logical size (default: its pixel size)."""
        self._cmds.append(("blit", surf, pos, alpha, size))

    def dim(self, color: Tuple[int, int, int, int]) -> None:
        """Translucent full-screen overlay that covers everything queued before it."""
        self._cmds.append(("dim", tuple(color)))

    def bitmap(self, rows: Sequence[str], colors: Dict[str, Color], pos: Tuple[float, float],
               scale: int = 1) -> None:
        """Queue a tiny pixel-art bitmap; each character maps to a colour ('.' and ' ' are empty).
        ``scale`` enlarges each bitmap pixel to scale x scale logical pixels."""
        self._cmds.append(("bitmap", tuple(rows), dict(colors), pos[0], pos[1], scale))

    # --------------------------------------------------------------- rendering
    def _text_surface(self, text: str, face: Face, px: int, color: Color) -> pygame.Surface:
        key = (text, id(face), px, color)
        surf = self._text_cache.get(key)
        if surf is None:
            if len(self._text_cache) > 1500:
                self._text_cache.clear()
            surf = self._text_cache[key] = face.font(px).render(text, False, color)
        return surf

    def render_commands(self, target: pygame.Surface, scale: float) -> None:
        """Draw every queued command onto ``target`` (the scaled world) at ``scale``."""
        s = scale
        if abs(s - self._cache_scale) > 1e-6:
            self._blit_cache.clear()
            self._text_cache.clear()
            self._cache_scale = s
        tw, th = target.get_size()
        one = max(1, round(s))
        for cmd in self._cmds:
            kind = cmd[0]
            if kind == "text":
                _, value, face, color, x, y, mode, shadow = cmd
                if not value:
                    continue
                px = face.px_for(s)
                surf = self._text_surface(value, face, px, color)
                cap_top, cap_h = face.caps_px(px)
                X, Y = x * s, y * s
                if mode == "center":
                    X -= surf.get_width() / 2
                    Y -= cap_top + cap_h / 2
                elif mode == "vcenter":
                    Y -= cap_top + cap_h / 2
                else:
                    Y -= cap_top
                X, Y = round(X), round(Y)
                if shadow:
                    target.blit(self._text_surface(value, face, px, SHADOW), (X + one, Y + one))
                target.blit(surf, (X, Y))
            elif kind == "shape":
                self._render_shape(target, s, one, cmd)
            elif kind == "line":
                _, color, p1, p2, width = cmd
                pygame.draw.line(target, color, (round(p1[0] * s), round(p1[1] * s)),
                                 (round(p2[0] * s), round(p2[1] * s)), max(1, round(width * s)))
            elif kind == "poly":
                _, color, pts = cmd
                pygame.draw.polygon(target, color, [(round(px * s), round(py * s)) for px, py in pts])
            elif kind == "blit":
                _, surf, pos, alpha, size = cmd
                lw, lh = size or surf.get_size()
                w, h = max(1, round(lw * s)), max(1, round(lh * s))
                key = (id(surf), w, h)
                entry = self._blit_cache.get(key)
                if entry is None:
                    entry = self._blit_cache[key] = (surf, pygame.transform.scale(surf, (w, h)))
                scaled = entry[1]
                scaled.set_alpha(alpha)
                target.blit(scaled, (round(pos[0] * s), round(pos[1] * s)))
            elif kind == "bitmap":
                _, rows, colors, x, y, k = cmd
                for ry, row in enumerate(rows):
                    for rx, ch in enumerate(row):
                        col = colors.get(ch)
                        if col is None:
                            continue
                        x0, y0 = round((x + rx * k) * s), round((y + ry * k) * s)
                        pygame.draw.rect(target, col, (x0, y0, round((x + (rx + 1) * k) * s) - x0,
                                                       round((y + (ry + 1) * k) * s) - y0))
            elif kind == "dim":
                _, color = cmd
                key = (tw, th, color)
                surf = self._dim_cache.get(key)
                if surf is None:
                    if len(self._dim_cache) > 20:
                        self._dim_cache.clear()
                    surf = self._dim_cache[key] = pygame.Surface((tw, th), pygame.SRCALPHA)
                    surf.fill(color)
                target.blit(surf, (0, 0))

    @staticmethod
    def _render_shape(target: pygame.Surface, s: float, one: int, cmd: tuple) -> None:
        _, rect, fill, border, bw, notch, shadow, glow, bevel = cmd
        x0, y0 = round(rect.x * s), round(rect.y * s)
        x1, y1 = max(x0 + 1, round(rect.right * s)) - 1, max(y0 + 1, round(rect.bottom * s)) - 1
        n = round(notch * s)
        bp = max(1, round(bw * s)) if border is not None else 0
        if shadow:
            off = round(2 * s)
            pygame.draw.polygon(target, SHADOW, _notched(x0 + off, y0 + off, x1 + off, y1 + off, n))
        if glow is not None:
            for infl, f in ((3, 0.35), (1.5, 0.7)):
                g = round(infl * s)
                pygame.draw.polygon(target, tuple(int(c * f) for c in glow[:3]), _notched(x0 - g, y0 - g, x1 + g, y1 + g, n + g))
        if fill is not None and len(fill) == 4 and fill[3] < 255:
            w, h = x1 - x0 + 1, y1 - y0 + 1
            tmp = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.polygon(tmp, fill, _notched(0, 0, w - 1, h - 1, n))
            if border is not None:
                pygame.draw.polygon(tmp, (*border[:3], 255), _notched(0, 0, w - 1, h - 1, n), bp)
            target.blit(tmp, (x0, y0))
            return
        if border is not None:
            pygame.draw.polygon(target, border[:3], _notched(x0, y0, x1, y1, n), 0 if fill is not None else bp)
        if fill is not None:
            ix0, iy0, ix1, iy1 = x0 + bp, y0 + bp, x1 - bp, y1 - bp
            if ix1 > ix0 and iy1 > iy0:
                pygame.draw.polygon(target, fill[:3], _notched(ix0, iy0, ix1, iy1, max(0, n - bp) if n else 0))
                if bevel and ix1 - ix0 > 4 * one and iy1 - iy0 > 4 * one:
                    # light top/left and dark bottom/right edges give the chunky pixel-bevel look
                    pygame.draw.rect(target, lighten(fill, 26), (ix0 + n, iy0, ix1 - ix0 + 1 - 2 * n, one))
                    pygame.draw.rect(target, lighten(fill, 14), (ix0, iy0 + n, one, iy1 - iy0 + 1 - 2 * n))
                    pygame.draw.rect(target, darken(fill, 30), (ix0 + n, iy1 + 1 - one, ix1 - ix0 + 1 - 2 * n, one))
                    pygame.draw.rect(target, darken(fill, 18), (ix1 + 1 - one, iy0 + n, one, iy1 - iy0 + 1 - 2 * n))

    # ---------------------------------------------------------------- widgets
    def draw_panel(self, rect: pygame.Rect, title: str = "", subtitle: str = "") -> None:
        """Pixel panel: hard shadow, bronze frame, inner line, gold corner studs, dashed divider."""
        self.shape(rect, PANEL_FILL, PANEL_BORDER, 2, 9, shadow=True)
        self.shape(rect.inflate(-10, -10), None, (44, 52, 78), 1, 0)
        for cx, cy in ((rect.x + 4, rect.y + 4), (rect.right - 7, rect.y + 4),
                       (rect.x + 4, rect.bottom - 7), (rect.right - 7, rect.bottom - 7)):
            self.shape(pygame.Rect(cx, cy, 3, 3), C_GOLD_HI, None, 0, 0, bevel=False)
        if title:
            self.text(self.fit_text(title, self.large, rect.w - 40), (rect.centerx, rect.y + 22),
                      self.large, GOLD, center=True)
        if subtitle:
            for dx in range(-56, 56, 6):
                self.shape(pygame.Rect(rect.centerx + dx, rect.y + 36, 3, 1), PANEL_BORDER, None, 0, 0, bevel=False)
            self.text(self.fit_text(subtitle, self.small, rect.w - 40), (rect.centerx, rect.y + 47),
                      self.small, MUTED, center=True)

    def draw_stone_frame(self, rect: pygame.Rect, fill: Color = PANEL_FILL,
                         accent: Color = PANEL_BORDER, shadow: bool = False) -> None:
        """Compact framed plate."""
        self.shape(rect, fill, accent, 2, 5, shadow=shadow)

    def draw_button(self, rect: pygame.Rect, label: str, active: bool = False,
                    hover: bool = False, small: bool = False, disabled: bool = False,
                    hotkey: str = "", detail: str = "") -> None:
        """Pixel button. Selected: gold frame, stepped glow and a blinking arrow cursor."""
        lit = (active or hover) and not disabled
        if lit:
            self.shape(rect, BTN_LIT, GOLD, 2, 5, glow=GOLD)
        elif disabled:
            self.shape(rect, (26, 29, 38), (56, 60, 72), 1, 5)
        else:
            self.shape(rect, BTN_FILL, BTN_BORDER, 1, 5)

        font = self.small_bold if small else self.body_bold
        pad = 8 if small else 24
        label = self.fit_text(label, font, rect.w - 2 * pad)
        color = GOLD_LIGHT if lit else ((130, 136, 148) if disabled else INK)
        self.text(label, rect.center, font, color, center=True)
        if lit and self.blink:
            self.bitmap(ARROW_R, {"X": GOLD_LIGHT, "o": (60, 40, 10)}, (rect.x + 8, rect.centery - 4))
        elif lit:
            self.bitmap(ARROW_R, {"X": GOLD, "o": (60, 40, 10)}, (rect.x + 10, rect.centery - 4))
        if hotkey:
            badge = pygame.Rect(rect.right - 22, rect.centery - 7, 15, 14)
            self.shape(badge, (14, 17, 26), (112, 104, 84) if not lit else GOLD, 1, 0, bevel=False)
            self.text(hotkey, badge.center, self.small_bold, MUTED if not lit else GOLD_LIGHT, center=True)
        if detail:
            right = rect.right - (28 if hotkey else 10)
            self.text(detail, (right - self.small.size(detail)[0], rect.centery), self.small, MUTED, vcenter=True)

    def draw_stat_card(self, rect: pygame.Rect, label: str, value: str, color: Color,
                       value_font: Optional[Face] = None) -> None:
        """Label-over-value card used by the statistics and results screens."""
        self.shape(rect, (28, 34, 50), (70, 82, 118), 1, 1)
        value_font = value_font or self.small_bold
        self.text(self.fit_text(label, self.tiny, rect.w - 16), (rect.x + 8, rect.y + 7), self.tiny, MUTED)
        self.text(self.fit_text(value, value_font, rect.w - 16),
                  (rect.x + 8, rect.bottom - 7 - value_font.cap_h), value_font, color)

    def draw_bar(self, track: pygame.Rect, fill_w: int, fill_color: Color,
                 track_color: Color = (10, 13, 22)) -> None:
        """Segmented pixel progress bar."""
        self.shape(track, track_color, (70, 82, 118), 1, 0, bevel=False)
        if fill_w > 0:
            inner = pygame.Rect(track.x + 1, track.y + 1, max(1, min(fill_w, track.w) - 2), track.h - 2)
            self.shape(inner, fill_color, None, 0, 0, bevel=False)
            self.shape(pygame.Rect(inner.x, inner.y, inner.w, 1), lighten(fill_color, 50), None, 0, 0, bevel=False)
