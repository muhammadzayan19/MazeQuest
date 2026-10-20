"""Display, scaling, viewport and fullscreen management for MazeQuest."""
from __future__ import annotations
from typing import Optional, Tuple
import pygame

IW: int = 640
IH: int = 440
DEFAULT_WINDOW_WIDTH: int = 1280
DEFAULT_WINDOW_HEIGHT: int = 880


class DisplayManager:
    """Manages the window, fullscreen transitions, and aspect-correct letterboxing."""

    def __init__(self, fullscreen: bool = False, window_size: Tuple[int, int] = (DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)) -> None:
        self.is_fullscreen = fullscreen
        self.window_size = window_size
        self.screen: Optional[pygame.Surface] = None
        self.viewport_rect = pygame.Rect(0, 0, IW, IH)
        self.scale: float = 1.0
        self.desktop_size = self._detect_desktop_size()

    def _detect_desktop_size(self) -> Tuple[int, int]:
        try:
            sizes = pygame.display.get_desktop_sizes()
            if sizes:
                return sizes[0]
        except Exception:
            pass
        try:
            info = pygame.display.Info()
            if info.current_w > 0 and info.current_h > 0:
                return (info.current_w, info.current_h)
        except Exception:
            pass
        return (DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)

    def init_display(self) -> pygame.Surface:
        pygame.display.set_caption("MazeQuest — The Forgotten Catacombs")
        if self.is_fullscreen:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode(self.window_size, pygame.RESIZABLE)
        self.update_viewport()
        return self.screen

    def toggle_fullscreen(self) -> bool:
        if self.is_fullscreen:
            self.is_fullscreen = False
            self.screen = pygame.display.set_mode(self.window_size, pygame.RESIZABLE)
        else:
            # Store current windowed dimensions before switching
            if self.screen:
                cur_w, cur_h = self.screen.get_size()
                if cur_w > 0 and cur_h > 0 and not (self.screen.get_flags() & pygame.FULLSCREEN):
                    self.window_size = (cur_w, cur_h)
            self.is_fullscreen = True
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        self.update_viewport()
        return self.is_fullscreen

    def set_fullscreen(self, enable: bool) -> bool:
        if self.is_fullscreen != enable:
            return self.toggle_fullscreen()
        return self.is_fullscreen

    def handle_resize(self, new_size: Tuple[int, int]) -> None:
        if not self.is_fullscreen:
            w = max(IW // 2, new_size[0])
            h = max(IH // 2, new_size[1])
            self.window_size = (w, h)
            self.screen = pygame.display.set_mode((w, h), pygame.RESIZABLE)
            self.update_viewport()

    def update_viewport(self) -> None:
        if not self.screen:
            return
        w, h = self.screen.get_size()
        # Pixel art must be enlarged by whole pixels. Fractional scaling makes
        # adjacent source pixels have different widths and reads as blur.
        scale = max(1, int(min(w / IW, h / IH)))
        vw = IW * scale
        vh = IH * scale
        vx = (w - vw) // 2
        vy = (h - vh) // 2
        self.viewport_rect = pygame.Rect(vx, vy, vw, vh)
        self.scale = float(scale)

    def screen_to_internal(self, pos: Tuple[int, int]) -> Tuple[int, int]:
        """Convert window screen coordinates to internal canvas (IW, IH) coordinates."""
        if not self.viewport_rect.collidepoint(pos):
            return (-1, -1)
        vx, vy, vw, vh = self.viewport_rect
        if vw <= 0 or vh <= 0:
            return (-1, -1)
        ix = int((pos[0] - vx) * IW / vw)
        iy = int((pos[1] - vy) * IH / vh)
        return (max(0, min(IW - 1, ix)), max(0, min(IH - 1, iy)))

    def present(self, canvas: pygame.Surface) -> None:
        """Scale and blit the internal pixel canvas to the display with aspect-correct letterboxing."""
        if not self.screen:
            return
        w, h = self.screen.get_size()
        vx, vy, vw, vh = self.viewport_rect

        # Clear letterbox / pillarbox margins with clean dark charcoal
        if vx > 0 or vy > 0 or vw < w or vh < h:
            self.screen.fill((7, 9, 13))

        scaled = pygame.transform.scale(canvas, (vw, vh))
        self.screen.blit(scaled, (vx, vy))

        # Delicate bezel rim around game frame if letterboxed
        if vx > 0 or vy > 0:
            pygame.draw.rect(self.screen, (26, 32, 42), self.viewport_rect, 1)

        pygame.display.flip()
