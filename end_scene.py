"""Pixel-art backdrops for the end screen: a golden dawn for victory, a blood-red night for defeat."""
from __future__ import annotations
import math
import random
from typing import Dict, List, Tuple
import pygame

from display_manager import IW, IH
from menu_scene import draw_banded_sky, gradient_color

Color = Tuple[int, int, int]
HORIZON = 250
CONFETTI_COLORS: List[Color] = [(255, 206, 76), (255, 120, 90), (110, 230, 250), (130, 240, 160), (255, 255, 230), (220, 130, 255)]


def _mix(a: Color, b: Color, t: float) -> Color:
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


class EndScene:
    """Animated backdrop for the results screen; ``draw`` picks the victory or defeat variant."""

    def __init__(self) -> None:
        self._scenes: Dict[bool, dict] = {}
        self._mode = None
        self.confetti: List[list] = []
        self.ash: List[list] = []
        self._rng = random.Random(5)

    # ------------------------------------------------------------------ build
    def _scene(self, won: bool) -> dict:
        scene = self._scenes.get(won)
        if scene is None:
            scene = self._scenes[won] = self._build_victory() if won else self._build_defeat()
        return scene

    @staticmethod
    def _convert(surf: pygame.Surface, alpha: bool = False) -> pygame.Surface:
        if not pygame.display.get_surface():
            return surf
        return surf.convert_alpha() if alpha else surf.convert()

    def _build_fog(self, rng: random.Random, height: int, count: int, color: Color) -> pygame.Surface:
        surf = pygame.Surface((IW, height), pygame.SRCALPHA)
        for _ in range(count):
            w, h = rng.randint(30, 90), rng.choice([4, 6, 8])
            x, y = rng.randint(0, IW), rng.randint(0, height - h)
            a = rng.randint(14, 28)
            for off in (-IW, 0, IW):
                pygame.draw.rect(surf, (*color, a), (x + off, y, w, h))
        return surf

    def _towers(self, front: pygame.Surface, rng: random.Random, color: Color, ruined: bool, flags: bool) -> None:
        pts = [(0, HORIZON)]
        x = 0
        while x <= IW:
            pts.append((x, HORIZON - 12 - int(9 * math.sin(x / 57.0) + 5 * math.sin(x / 21.0))))
            x += 16
        pts.append((IW, HORIZON))
        pygame.draw.polygon(front, color, pts)
        for x in list(range(-6, 150, 36)) + list(range(470, IW + 20, 36)):
            w = rng.choice([22, 26, 30])
            h = rng.randint(50, 120)
            top = HORIZON - h
            pygame.draw.rect(front, color, (x, top, w, h + 4))
            if ruined:
                cut = rng.randint(6, 16)
                pygame.draw.polygon(front, (0, 0, 0, 0), [(x - 1, top - 1), (x + w // 2, top - 1), (x + w + 1, top + cut)])
                for _ in range(rng.randint(2, 4)):          # broken crenellations
                    pygame.draw.rect(front, color, (x + rng.randint(0, w - 4), top - rng.randint(2, 7), 4, 6))
            else:
                for cx in range(x, x + w - 2, 8):
                    pygame.draw.rect(front, color, (cx, top - 5, 4, 5))
                if flags and rng.random() < 0.7:
                    px = x + w // 2
                    pygame.draw.line(front, color, (px, top - 5), (px, top - 20))
                    pygame.draw.polygon(front, (236, 76, 76), [(px + 1, top - 20), (px + 11, top - 16), (px + 1, top - 12)])
            for _ in range(rng.randint(1, 3)):
                wx, wy = x + rng.randint(4, w - 7), top + rng.randint(10, max(11, h - 16))
                pygame.draw.rect(front, (255, 196, 90) if flags else (120, 36, 44), (wx, wy, 3, 5))

    def _ground(self, front: pygame.Surface, base: Color, line: Color, light: Color) -> None:
        pygame.draw.rect(front, base, (0, HORIZON, IW, IH - HORIZON))
        ys = [HORIZON]
        k = 1
        while ys[-1] < IH:
            ys.append(int(HORIZON + 5 * k * k * 0.5 + 6 * k))
            k += 1
        for i in range(len(ys) - 1):
            if i % 2:
                pygame.draw.rect(front, light, (0, ys[i], IW, ys[i + 1] - ys[i]))
            pygame.draw.line(front, line, (0, ys[i]), (IW, ys[i]))
        for x in range(-480, IW + 480, 64):
            pygame.draw.line(front, line, (IW // 2 + (x - IW // 2) * 0.06, HORIZON), (x, IH))

    def _stars(self, rng: random.Random, count: int, limit: int) -> List[Tuple[int, int, float, float]]:
        return [(rng.randint(4, IW - 4), rng.randint(4, limit), rng.uniform(0, 6.28), rng.uniform(1.0, 3.0))
                for _ in range(count)]

    def _build_victory(self) -> dict:
        rng = random.Random(21)
        back = pygame.Surface((IW, IH))
        stops = [(0.0, (14, 18, 56)), (0.5, (112, 58, 120)), (1.0, (255, 170, 90))]
        draw_banded_sky(back, stops, HORIZON)
        horizon_col = gradient_color(stops, 1.0)
        cx = IW // 2
        for r, t in ((96, 0.10), (80, 0.18), (66, 0.30)):
            pygame.draw.circle(back, _mix(horizon_col, (255, 232, 160), t), (cx, HORIZON), r)
        pygame.draw.circle(back, (255, 226, 140), (cx, HORIZON), 46)
        pygame.draw.circle(back, (255, 244, 190), (cx, HORIZON), 38)
        pygame.draw.circle(back, (255, 252, 226), (cx - 10, HORIZON - 8), 16)

        front = pygame.Surface((IW, IH), pygame.SRCALPHA)
        self._towers(front, rng, (38, 22, 58), ruined=False, flags=True)
        self._ground(front, (34, 22, 48), (20, 12, 32), (40, 27, 56))
        for i in range(12):                                # golden road of light from the sun
            y0 = HORIZON + int(5 * i * i * 0.5 + 6 * i)
            y1 = HORIZON + int(5 * (i + 1) ** 2 * 0.5 + 6 * (i + 1))
            half = 14 + i * 20
            col = (255, 196, 96, max(14, 70 - i * 5))
            pygame.draw.polygon(front, col, [(cx - half, y0), (cx + half, y0), (cx + half + 20, y1), (cx - half - 20, y1)])

        rays = []
        for parity in (0, 1):
            surf = pygame.Surface((IW, HORIZON + 4), pygame.SRCALPHA)
            n = 18
            for k in range(parity, n, 2):
                a0 = math.pi + k * math.pi / n
                a1 = a0 + math.pi / n
                R = 520
                pygame.draw.polygon(surf, (255, 214, 130, 36),
                                    [(cx, HORIZON), (cx + R * math.cos(a0), HORIZON + R * math.sin(a0)),
                                     (cx + R * math.cos(a1), HORIZON + R * math.sin(a1))])
            rays.append(surf)
        return {"back": self._convert(back), "front": self._convert(front, True), "rays": rays,
                "stars": self._stars(rng, 36, 120), "fog": [self._build_fog(rng, 110, 28, (255, 214, 170)),
                                                          self._build_fog(rng, 80, 24, (255, 190, 150))]}

    def _build_defeat(self) -> dict:
        rng = random.Random(33)
        back = pygame.Surface((IW, IH))
        stops = [(0.0, (8, 4, 16)), (0.65, (54, 12, 38)), (1.0, (130, 34, 44))]
        draw_banded_sky(back, stops, HORIZON)
        cx, cy = 566, 74
        for r, t in ((52, 0.10), (44, 0.18)):
            pygame.draw.circle(back, _mix(gradient_color(stops, cy / HORIZON), (230, 90, 90), t), (cx, cy), r)
        pygame.draw.circle(back, (214, 86, 86), (cx, cy), 32)
        pygame.draw.circle(back, (170, 58, 66), (cx - 10, cy + 8), 6)
        pygame.draw.circle(back, (170, 58, 66), (cx + 11, cy - 10), 4)
        pygame.draw.circle(back, (236, 120, 112), (cx - 8, cy - 12), 10)
        crack = [(cx + 4, cy - 32), (cx - 3, cy - 18), (cx + 6, cy - 6), (cx - 2, cy + 8), (cx + 8, cy + 20), (cx + 2, cy + 32)]
        pygame.draw.lines(back, (70, 16, 30), False, crack, 2)

        front = pygame.Surface((IW, IH), pygame.SRCALPHA)
        self._towers(front, rng, (18, 7, 24), ruined=True, flags=False)
        self._ground(front, (24, 11, 28), (14, 6, 18), (30, 14, 34))
        return {"back": self._convert(back), "front": self._convert(front, True), "rays": None,
                "stars": self._stars(rng, 50, 130), "fog": [self._build_fog(rng, 110, 30, (210, 80, 96)),
                                                          self._build_fog(rng, 80, 26, (180, 60, 84))]}

    # ------------------------------------------------------------------ draw
    def _reset_particles(self, won: bool) -> None:
        rng = self._rng
        self.confetti, self.ash = [], []
        if won:
            for _ in range(70):
                self.confetti.append(self._new_confetti(rng, rng.uniform(0, IH)))
        else:
            for _ in range(50):
                self.ash.append([rng.uniform(0, IW), rng.uniform(0, IH), rng.uniform(-6, 6), rng.uniform(10, 26),
                                 rng.choice((1, 1, 2)), rng.uniform(0, 6.28)])

    @staticmethod
    def _new_confetti(rng: random.Random, y: float) -> list:
        return [rng.uniform(0, IW), y, rng.uniform(-10, 10), rng.uniform(34, 80), rng.choice(CONFETTI_COLORS),
                rng.uniform(0, 6.28), rng.choice((2, 3))]

    def draw(self, canvas: pygame.Surface, t: float, dt: float, won: bool) -> None:
        if self._mode != won:
            self._mode = won
            self._reset_particles(won)
        sc = self._scene(won)
        canvas.blit(sc["back"], (0, 0))
        for x, y, phase, speed in sc["stars"]:
            v = math.sin(t * speed + phase)
            if v > 0.1:
                canvas.set_at((x, y), (255, 255, 255) if won else (255, 205, 205))
            elif v > -0.4:
                canvas.set_at((x, y), (160, 150, 190))
        if sc["rays"]:
            canvas.blit(sc["rays"][int(t * 1.6) % 2], (0, 0))
        canvas.blit(sc["front"], (0, 0))
        for fog, y, speed in ((sc["fog"][0], 238, 6.0), (sc["fog"][1], 330, 13.0)):
            off = int(t * speed) % IW
            canvas.blit(fog, (off, y))
            canvas.blit(fog, (off - IW, y))

        rng = self._rng
        for c in self.confetti:
            c[1] += c[3] * dt
            c[0] += (c[2] + math.sin(t * 3 + c[5]) * 16) * dt
            if c[1] > IH:
                c[:] = self._new_confetti(rng, -4)
            tall = 3 if int(t * 6 + c[5]) % 2 else 2
            pygame.draw.rect(canvas, c[4], (int(c[0]), int(c[1]), c[6], tall))
        for a in self.ash:
            a[1] += a[3] * dt
            a[0] += (a[2] + math.sin(t + a[5]) * 6) * dt
            if a[1] > IH:
                a[0], a[1] = rng.uniform(0, IW), -3
            canvas.fill((150, 128, 146), (int(a[0]), int(a[1]), a[4], a[4]))
