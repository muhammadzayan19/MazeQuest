"""Procedural sound synthesizer and sound effect player for MazeQuest."""
from __future__ import annotations
import math
from typing import Optional
import pygame
import numpy as np


class SoundManager:
    """Generates and plays retro dark-fantasy sound effects procedurally."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._available = False
        self.click_snd: Optional[pygame.mixer.Sound] = None
        self.step_snd: Optional[pygame.mixer.Sound] = None
        self.pickup_snd: Optional[pygame.mixer.Sound] = None
        self.key_snd: Optional[pygame.mixer.Sound] = None
        self.unlock_snd: Optional[pygame.mixer.Sound] = None
        self.bump_snd: Optional[pygame.mixer.Sound] = None
        self.win_snd: Optional[pygame.mixer.Sound] = None

        self._init_mixer()

    def _init_mixer(self) -> None:
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            self._available = True
            self._build_sounds()
        except Exception:
            self._available = False

    def _build_sounds(self) -> None:
        if not self._available:
            return
        sample_rate = 44100

        def make_tone(freqs, duration, decay=8.0, wave_type="sine", volume=0.3):
            n_samples = int(sample_rate * duration)
            t = np.linspace(0, duration, n_samples, False)
            signal = np.zeros(n_samples)
            for f in freqs:
                if wave_type == "sine":
                    signal += np.sin(2 * np.pi * f * t)
                elif wave_type == "triangle":
                    signal += 2 * np.abs(2 * (t * f - np.floor(t * f + 0.5))) - 1
            # Apply exponential decay envelope
            envelope = np.exp(-decay * t)
            audio = signal * envelope * volume * 32767
            audio = np.clip(audio, -32767, 32767).astype(np.int16)
            stereo = np.column_stack((audio, audio))
            return pygame.sndarray.make_sound(stereo)

        try:
            # Subtle button click
            self.click_snd = make_tone([880, 1760], 0.05, decay=40.0, volume=0.2)
            # Soft footstep tap
            self.step_snd = make_tone([120, 180], 0.06, decay=35.0, wave_type="triangle", volume=0.15)
            # Wall bump
            self.bump_snd = make_tone([90, 110], 0.08, decay=25.0, wave_type="triangle", volume=0.2)
            # Relic / treasure pickup chime
            self.pickup_snd = make_tone([523.25, 659.25, 783.99, 1046.50], 0.35, decay=6.0, volume=0.25)
            # Key discovery fanfare
            self.key_snd = make_tone([659.25, 830.61, 987.77, 1318.51], 0.45, decay=5.0, volume=0.28)
            # Door unlock
            self.unlock_snd = make_tone([330, 440, 554], 0.4, decay=7.0, wave_type="triangle", volume=0.25)
            # Victory fanfare
            self.win_snd = make_tone([440, 554, 659, 880], 0.6, decay=4.0, volume=0.3)
        except Exception:
            self._available = False

    def play(self, sound_name: str) -> None:
        if not self.enabled or not self._available:
            return
        snd = getattr(self, f"{sound_name}_snd", None)
        if snd:
            try:
                snd.play()
            except Exception:
                pass
