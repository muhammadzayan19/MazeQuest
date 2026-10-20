"""Hi-res UI painting. Widgets queue draw commands in logical 640x440 coordinates;
the commands are rendered at the window's native resolution on top of the scaled
world, so text and chrome stay smooth at any window size."""
from __future__ import annotations
import math
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import pygame

from sprites import C_GOLD_HI, C_GOLD_LIGHT

Color = Tuple[int, ...]

# Palette tokens for UI
INK: Color = (238, 232, 216)
MUTED: Color = (160, 170, 184)
GOLD: Color = (244, 190, 70)
CYAN: Color = (96, 226, 246)
GREEN: Color = (104, 232, 164)
RED: Color = (238, 88, 72)
DARK: Color = (10, 13, 18)
PANEL_BG: Color = (17, 21, 28)
PANEL_BORDER: Color = (118, 90, 48)
HOVER_BG: Color = (40, 46, 60)

FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"
_REF = 4  # measurement fonts are built at 4x so logical metrics are sub-pixel accurate


def _lerp(a: Color, b: Color, t: float) -> Color:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def lighten(c: Color, amount: int) -> Color:
    return tuple(min(255, v + amount) for v in c[:3])


class Face:
    """A font at a logical size; renders at ``size * scale`` pixels, measures in logical units."""

    def __init__(self, loader: Callable[[int], pygame.font.Font], size: int) -> None:
        self.size_px = size
        self._loader = loader
        self._fonts: Dict[int, pygame.font.Font] = {}
        self._caps: Dict[int, Tuple[int, int]] = {}
        self._ref = self.font(size * _REF)
        box = self._ref.render("H", True, (255, 255, 255)).get_bounding_rect()
        self.cap_top = box.y / _REF
        self.cap_h = max(1.0, box.h / _REF)

    def font(self, px: int) -> pygame.font.Font:
        f = self._fonts.get(px)
        if f is None:
            f = self._fonts[px] = self._loader(max(1, px))
        return f

    def size(self, text: str) -> Tuple[int, int]:
        w, h = self._ref.size(text)
        return (math.ceil(w / _REF), math.ceil(h / _REF))

    def caps_px(self, px: int) -> Tuple[int, int]:
        box = self._caps.get(px)
        if box is None:
            r = self.font(px).render("H", True, (255, 255, 255)).get_bounding_rect()
            box = self._caps[px] = (r.y, max(1, r.h))
        return box


def _file_loader(path: Path, bold: bool = False) -> Callable[[int], pygame.font.Font]:
    def load(px: int) -> pygame.font.Font:
        f = pygame.font.Font(str(path), px)
        if bold:
            f.set_bold(True)
        return f
    return load


def _system_loader(bold: bool) -> Callable[[int], pygame.font.Font]:
    names = ["segoeui", "arial", "dejavusans", "liberationsans", "notosans"]
    chosen = next((n for n in names if n in pygame.font.get_fonts()), None)

    def load(px: int) -> pygame.font.Font:
        if chosen:
            try:
                return pygame.font.SysFont(chosen, px, bold=bold)
            except Exception:
                pass
        return pygame.font.Font(None, px + 4)
    return load


class Painter:
    """Owns the fonts and the draw-command queue; renders it at native resolution."""

    canvas: pygame.Surface

    def __init__(self, canvas: pygame.Surface) -> None:
        self.canvas = canvas
        self._cmds: List[tuple] = []
        self._text_cache: Dict[tuple, pygame.Surface] = {}
        self._shape_cache: Dict[tuple, pygame.Surface] = {}
        self._blit_cache: Dict[tuple, Tuple[pygame.Surface, pygame.Surface]] = {}
        self._dim_cache: Dict[tuple, pygame.Surface] = {}
        self._cache_scale = 0.0
        self._init_fonts()

    # ------------------------------------------------------------------ fonts
    def _init_fonts(self) -> None:
        """Cinzel for headings and buttons, Alegreya Sans for reading text."""
        pygame.font.init()
        cinzel = FONT_DIR / "Cinzel.ttf"
        reg = FONT_DIR / "AlegreyaSans-Regular.ttf"
        med = FONT_DIR / "AlegreyaSans-Medium.ttf"
        if cinzel.exists() and reg.exists() and med.exists():
            head, body, body_med = _file_loader(cinzel, True), _file_loader(reg), _file_loader(med)
        else:
            head, body, body_med = _system_loader(True), _system_loader(False), _system_loader(False)
        self.huge = Face(head, 38)
        self.large = Face(head, 20)
        self.title = Face(head, 17)
        self.body_bold = Face(head, 14)
        self.small_bold = Face(head, 11)
        self.body = Face(body, 15)
        self.small = Face(body, 12)
        self.tiny = Face(body_med, 11)

    # ----------------------------------------------------------- command queue
    def clear_commands(self) -> None:
        self._cmds = []

    def fit_text(self, value: Any, font: Face, max_w: int) -> str:
        """Truncate with an ellipsis so rendered text never exceeds max_w logical pixels."""
        val = str(value)
        if font.size(val)[0] <= max_w:
            return val
        while val and font.size(val + "...")[0] > max_w:
            val = val[:-1]
        return val + "..."

    def text(self, value: Any, pos: Tuple[float, float], font: Optional[Face] = None,
             color: Color = INK, shadow: bool = True, center: bool = False,
             vcenter: bool = False) -> None:
        """Queue text. ``pos`` is the top-left of the capitals, their centre if ``center``,
        or left-aligned with the capitals vertically centred on ``pos[1]`` if ``vcenter``."""
        mode = "center" if center else "vcenter" if vcenter else "top"
        self._cmds.append(("text", str(value), font or self.body, tuple(color[:3]), pos[0], pos[1], mode, shadow))

    def shape(self, rect: pygame.Rect, fill: Any, border: Optional[Color] = None, bw: int = 1,
              radius: int = 0, shadow: bool = False, glow: Optional[Color] = None) -> None:
        """Queue a rounded rectangle. ``fill`` is a colour, ``(top, bottom)`` gradient or None."""
        self._cmds.append(("shape", pygame.Rect(rect), fill, border, bw, radius, shadow, glow))

    def line(self, color: Color, p1: Tuple[float, float], p2: Tuple[float, float], width: float = 1) -> None:
        self._cmds.append(("line", tuple(color), p1, p2, width))

    def poly(self, color: Color, points: List[Tuple[float, float]]) -> None:
        self._cmds.append(("poly", tuple(color), list(points)))

    def blit(self, surf: pygame.Surface, pos: Tuple[float, float], alpha: int = 255) -> None:
        self._cmds.append(("blit", surf, pos, alpha))

    def dim(self, color: Tuple[int, int, int, int]) -> None:
        """Translucent full-screen overlay that covers everything queued before it."""
        self._cmds.append(("dim", tuple(color)))

    # --------------------------------------------------------------- rendering
    def _shape_surface(self, w: int, h: int, fill: Any, border: Optional[Color], bw: int, radius: int) -> pygame.Surface:
        key = (w, h, fill, border, bw, radius)
        surf = self._shape_cache.get(key)
        if surf is not None:
            return surf
        ss = 2 if w * h <= 500_000 else 1
        W, H = w * ss, h * ss
        base = pygame.Surface((W, H), pygame.SRCALPHA)
        if fill is None:
            base.fill((0, 0, 0, 0))
        elif isinstance(fill[0], tuple):
            top, bot = fill
            for y in range(H):
                pygame.draw.line(base, _lerp(top, bot, y / max(1, H - 1)), (0, y), (W, y))
        else:
            base.fill(fill if len(fill) == 4 else (*fill, 255))
        r = min(radius * ss, min(W, H) // 2)
        if r > 0:
            mask = pygame.Surface((W, H), pygame.SRCALPHA)
            mask.fill((0, 0, 0, 0))
            pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, W, H), border_radius=r)
            base.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        if border is not None and bw > 0:
            pygame.draw.rect(base, border, (0, 0, W, H), width=min(bw * ss, min(W, H) // 2), border_radius=r)
        if ss > 1:
            base = pygame.transform.smoothscale(base, (w, h))
        if len(self._shape_cache) > 500:
            self._shape_cache.clear()
        self._shape_cache[key] = base
        return base

    def _text_surface(self, text: str, face: Face, px: int, color: Color) -> pygame.Surface:
        key = (text, id(face), px, color)
        surf = self._text_cache.get(key)
        if surf is None:
            if len(self._text_cache) > 1500:
                self._text_cache.clear()
            surf = self._text_cache[key] = face.font(px).render(text, True, color)
        return surf

    def render_commands(self, target: pygame.Surface, scale: float) -> None:
        """Draw every queued command onto ``target`` (the scaled world) at ``scale``."""
        s = scale
        if abs(s - self._cache_scale) > 1e-6:
            self._shape_cache.clear()
            self._blit_cache.clear()
            self._text_cache.clear()
            self._cache_scale = s
        tw, th = target.get_size()
        for cmd in self._cmds:
            kind = cmd[0]
            if kind == "text":
                _, value, face, color, x, y, mode, shadow = cmd
                if not value:
                    continue
                px = max(1, round(face.size_px * s))
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
                if shadow:
                    off = max(1, round(s * 0.8))
                    target.blit(self._text_surface(value, face, px, (6, 8, 12)), (round(X) + off, round(Y) + off))
                target.blit(surf, (round(X), round(Y)))
            elif kind == "shape":
                _, rect, fill, border, bw, radius, shadow, glow = cmd
                x0, y0 = round(rect.x * s), round(rect.y * s)
                w, h = max(1, round(rect.right * s) - x0), max(1, round(rect.bottom * s) - y0)
                rp = min(round(radius * s), min(w, h) // 2)
                bp = max(1, round(bw * s)) if border is not None else 0
                if shadow:
                    for infl, alpha in ((7, 18), (4, 28), (2, 40)):
                        ip = round(infl * s)
                        target.blit(self._shape_surface(w + 2 * ip, h + 2 * ip, (0, 0, 0, alpha), None, 0, rp + ip),
                                    (x0 - ip, y0 - ip + round(3 * s)))
                if glow is not None:
                    for infl, alpha in ((6, 18), (3, 34)):
                        ip = round(infl * s)
                        target.blit(self._shape_surface(w + 2 * ip, h + 2 * ip, (*glow[:3], alpha), None, 0, rp + ip),
                                    (x0 - ip, y0 - ip))
                target.blit(self._shape_surface(w, h, fill, border, bp, rp), (x0, y0))
            elif kind == "line":
                _, color, p1, p2, width = cmd
                pygame.draw.line(target, color, (round(p1[0] * s), round(p1[1] * s)),
                                 (round(p2[0] * s), round(p2[1] * s)), max(1, round(width * s)))
            elif kind == "poly":
                _, color, pts = cmd
                pygame.draw.polygon(target, color, [(round(px * s), round(py * s)) for px, py in pts])
            elif kind == "blit":
                _, surf, pos, alpha = cmd
                w, h = max(1, round(surf.get_width() * s)), max(1, round(surf.get_height() * s))
                key = (id(surf), w, h)
                entry = self._blit_cache.get(key)
                if entry is None:
                    entry = self._blit_cache[key] = (surf, pygame.transform.smoothscale(surf, (w, h)))
                scaled = entry[1]
                scaled.set_alpha(alpha)
                target.blit(scaled, (round(pos[0] * s), round(pos[1] * s)))
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

    # ---------------------------------------------------------------- widgets
    def draw_panel(self, rect: pygame.Rect, title: str = "", subtitle: str = "") -> None:
        """Dark-fantasy panel: gradient fill, bronze rim, soft shadow, gold corner studs."""
        self.shape(rect, ((28, 33, 45), (14, 17, 24)), PANEL_BORDER, 2, 9, shadow=True)
        self.shape(rect.inflate(-10, -10), None, (255, 255, 255, 16), 1, 6)
        for cx, cy in ((rect.x + 7, rect.y + 7), (rect.right - 7, rect.y + 7),
                       (rect.x + 7, rect.bottom - 7), (rect.right - 7, rect.bottom - 7)):
            self.shape(pygame.Rect(cx - 2, cy - 2, 4, 4), C_GOLD_HI, None, 0, 2)
        if title:
            self.text(self.fit_text(title, self.large, rect.w - 40), (rect.centerx, rect.y + 22),
                      self.large, GOLD, center=True)
        if subtitle:
            self.line((120, 92, 50), (rect.centerx - 56, rect.y + 36), (rect.centerx + 56, rect.y + 36))
            self.text(self.fit_text(subtitle, self.small, rect.w - 40), (rect.centerx, rect.y + 47),
                      self.small, MUTED, center=True)

    def draw_stone_frame(self, rect: pygame.Rect, fill: Color = PANEL_BG,
                         accent: Color = PANEL_BORDER, shadow: bool = False) -> None:
        """Compact framed plate with a faint top highlight."""
        self.shape(rect, (lighten(fill, 9), fill), accent, 2, 6, shadow=shadow)
        self.shape(pygame.Rect(rect.x + 4, rect.y + 3, rect.w - 8, 1), (255, 255, 255, 34), None, 0, 0)

    def draw_button(self, rect: pygame.Rect, label: str, active: bool = False,
                    hover: bool = False, small: bool = False, disabled: bool = False) -> None:
        """Rounded gradient button. ``active``/``hover`` share one highlight (gold rim, glow, chevrons)."""
        lit = (active or hover) and not disabled
        radius = 5 if small else 7
        if lit:
            self.shape(rect, ((74, 61, 38), (40, 33, 22)), GOLD, 2, radius, glow=GOLD)
        elif disabled:
            self.shape(rect, ((26, 29, 35), (19, 21, 26)), (52, 54, 60), 1, radius)
        else:
            self.shape(rect, ((38, 44, 58), (22, 26, 35)), (92, 80, 58), 1, radius)
        self.shape(pygame.Rect(rect.x + 3, rect.y + 2, rect.w - 6, max(2, rect.h // 2 - 2)),
                   (255, 255, 255, 16 if lit else 9), None, 0, max(1, radius - 2))

        font = self.small_bold if small else self.body_bold
        label = self.fit_text(label, font, rect.w - (40 if lit else 14))
        color = C_GOLD_LIGHT if lit else ((116, 122, 132) if disabled else INK)
        self.text(label, rect.center, font, color, center=True)
        if lit:
            half = font.size(label)[0] / 2
            cx, cy = rect.centerx, rect.centery
            self.poly(GOLD, [(cx - half - 15, cy - 4), (cx - half - 15, cy + 4), (cx - half - 9, cy)])
            self.poly(GOLD, [(cx + half + 15, cy - 4), (cx + half + 15, cy + 4), (cx + half + 9, cy)])

    def draw_stat_card(self, rect: pygame.Rect, label: str, value: str, color: Color,
                       value_font: Optional[Face] = None) -> None:
        """Label-over-value card used by the statistics and results screens."""
        self.shape(rect, ((30, 36, 48), (21, 26, 35)), (56, 66, 84), 1, 5)
        value_font = value_font or self.small_bold
        self.text(self.fit_text(label, self.tiny, rect.w - 20), (rect.x + 10, rect.y + 9), self.tiny, MUTED)
        self.text(self.fit_text(value, value_font, rect.w - 20),
                  (rect.x + 10, rect.bottom - 9 - value_font.cap_h), value_font, color)

    def draw_bar(self, track: pygame.Rect, fill_w: int, fill_color: Color,
                 track_color: Color = (14, 18, 25)) -> None:
        """Rounded progress bar with a lit leading edge."""
        radius = track.h // 2
        self.shape(track, track_color, (60, 70, 86), 1, radius)
        if fill_w > 0:
            self.shape(pygame.Rect(track.x, track.y, max(track.h, fill_w), track.h), fill_color, None, 0, radius)
