"""Particle effects engine for torch embers, magical crystals, pickups, and dust."""
from __future__ import annotations
import math
import random
from typing import List, Tuple
import pygame

class Particle:
    __slots__ = ('x', 'y', 'vx', 'vy', 'color', 'life', 'max_life', 'size', 'fade')

    def __init__(self, x: float, y: float, vx: float, vy: float, color: Tuple[int, int, int], life: float, size: int = 1, fade: bool = True):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color
        self.life = life
        self.max_life = life
        self.size = size
        self.fade = fade

    def update(self, dt: float) -> bool:
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt
        return self.life > 0

    def draw(self, surface: pygame.Surface) -> None:
        if self.life <= 0:
            return
        ratio = max(0.0, min(1.0, self.life / self.max_life))
        alpha = int(ratio * 255) if self.fade else 255
        c = self.color
        ix, iy = int(self.x), int(self.y)
        if 0 <= ix < surface.get_width() and 0 <= iy < surface.get_height():
            if self.size == 1:
                # Direct pixel set
                surface.set_at((ix, iy), c)
            else:
                pygame.draw.rect(surface, c, (ix, iy, self.size, self.size))


class ParticleSystem:
    def __init__(self, max_particles: int = 150):
        self.particles: List[Particle] = []
        self.max_particles = max_particles
        self._spawn_timer = 0.0

    def clear(self) -> None:
        self.particles.clear()

    def add(self, particle: Particle) -> None:
        if len(self.particles) < self.max_particles:
            self.particles.append(particle)

    def emit_torch_embers(self, x: float, y: float, count: int = 1) -> None:
        for _ in range(count):
            vx = random.uniform(-6, 6)
            vy = random.uniform(-22, -10)
            life = random.uniform(0.6, 1.4)
            color = random.choice([
                (255, 230, 140),
                (245, 160, 45),
                (230, 95, 25),
                (190, 50, 15)
            ])
            self.add(Particle(x + random.uniform(-2, 2), y - 2, vx, vy, color, life, size=1))

    def emit_crystal_dust(self, x: float, y: float, count: int = 1) -> None:
        for _ in range(count):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(3, 10)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed - 4
            life = random.uniform(0.7, 1.5)
            color = random.choice([
                (220, 255, 255),
                (95, 235, 250),
                (45, 175, 220),
                (30, 110, 160)
            ])
            self.add(Particle(x + random.uniform(-3, 3), y + random.uniform(-3, 3), vx, vy, color, life, size=1))

    def emit_pickup_burst(self, x: float, y: float, count: int = 16) -> None:
        """Explosion of golden glint stars when collecting treasure or keys."""
        for _ in range(count):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(25, 65)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            life = random.uniform(0.35, 0.75)
            color = random.choice([
                (255, 255, 220),
                (255, 220, 100),
                (240, 180, 50),
                (210, 130, 30)
            ])
            size = 2 if random.random() < 0.4 else 1
            self.add(Particle(x, y, vx, vy, color, life, size=size))

    def emit_unlock_flash(self, x: float, y: float, count: int = 14) -> None:
        """Burst of cyan/ethereal sparks when a passage gate is unlocked."""
        for _ in range(count):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(20, 50)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed - 10
            life = random.uniform(0.4, 0.8)
            color = random.choice([
                (230, 255, 255),
                (110, 240, 255),
                (50, 190, 220),
                (240, 200, 80)
            ])
            self.add(Particle(x + random.uniform(-6, 6), y + random.uniform(-4, 4), vx, vy, color, life, size=1))

    def emit_footstep(self, x: float, y: float) -> None:
        """Subtle dust puff under player boots."""
        for _ in range(3):
            vx = random.uniform(-10, 10)
            vy = random.uniform(-4, 2)
            life = random.uniform(0.18, 0.35)
            color = random.choice([(60, 68, 76), (46, 52, 60), (36, 40, 48)])
            self.add(Particle(x + random.uniform(-3, 3), y, vx, vy, color, life, size=1))

    def update(self, dt: float) -> None:
        if dt <= 0:
            return
        self.particles = [p for p in self.particles if p.update(dt)]

    def draw(self, surface: pygame.Surface) -> None:
        for p in self.particles:
            p.draw(surface)
