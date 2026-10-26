# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
python -m pip install -r requirements.txt   # only dependency: pygame-ce==2.5.8
python main.py                              # run the game
python -m unittest discover -s tests -v     # all tests
python -m unittest tests.test_ui_improvements.TestUIImprovements.test_fit_text_never_exceeds_width   # single test
```

No linter or build step is configured. Tests use `unittest` (a `.pytest_cache` exists, so `pytest` also works) and create real pygame surfaces, so they need `pygame.init()` to succeed.

## Architecture

Single-level pygame-ce dungeon game (flat module layout, no package). The key design rule is that **game state is independent of rendering**:

- `maze.py` — handcrafted nested-list map (`Maze.handcrafted()`, `LEVELS`).
- `game_logic.py` — `Game`: collision, movement, key/door/objective state, timing and run metrics. No pygame rendering.
- `solver.py` — key-aware BFS (shortest route, used for the `H` hint and `V` optimal-route overlay) and recursive DFS.
- `main.py` — `run()` loop: input handling, scene/state transitions (menu, pause, settings, dungeon, completion), wiring `Game`, `UI`, `DisplayManager`, `SoundManager`, and save data together.
- `ui.py` — `UI` class renders every screen and also owns hit-testing (e.g. `game_hit`, `hint_btn_rect`, `fit_text`). Rect-based mouse hit areas are computed during draw, so draw before querying them (tests call `ui.dungeon(game)` first).
- `widgets.py` — shared `Painter` and UI widget helpers used by `ui.py`. UI is queued as commands in logical 640x440 coordinates and rendered at native resolution with a pixel look (Silkscreen / Press Start 2P from `assets/fonts`, snapped to an 8px grid, no anti-aliasing, stepped corners).
- `menu_scene.py` — pixel-art start-screen backdrop (sky, moon, skyline, stone gate, fog, torches).
- `end_scene.py` — pixel-art end-screen backdrops (golden dawn + confetti for victory, red night + ash for defeat).
- `decor.py` / `decor_art.py` — deterministic dungeon dressing derived from the maze (zones, carpet, floor decals, wall overlays, candles, drip points) and its pixel art. Rendering only: decals are flat and wall decor only replaces wall faces, so nothing blocks a route.
- Dungeon view (`ui.py`): static layer (zone floors, decals, walls) is cached per maze; each frame draws props, a wall-aware banded lightmap (line-of-sight masked glows), emissive props, hero, particles, optional fog of war (Settings > FOG OF WAR), and reaction effects (chest/door animation, pickup popups, bump, footprints) detected from game state.
- `sprites.py` — procedural pre-rendered tiles, hero animation, lighting, props (no image assets besides fonts).
- `particles.py` — delta-time particle effects. `sound.py` — procedural audio, written to never crash if audio is unavailable.
- `display_manager.py` — renders into a fixed internal 640x440 canvas (`IW`, `IH`) and scales with aspect-correct letterboxing; handles resize and fullscreen (F11 / Alt+Enter). Mouse coordinates must be mapped from window space back to canvas space through it.
- `save_data.py` — versioned JSON for runs, settings, and records; atomic replace on write. Stored under `%APPDATA%` on Windows, otherwise `XDG_CONFIG_HOME` (see `default_config_path`). `savegame.json`/`highscores.json` are gitignored.

Tests in `tests/` cover logic (`test_mazequest.py`), display/UI (`test_display_and_ui.py`, `test_ui_improvements.py`), and end-to-end gameplay (`test_e2e_gameplay.py`).

## Git

Never add a Claude `Co-Authored-By` line (or any other Claude attribution) to commit messages or PR descriptions. Commits that get pushed must not credit Claude as a co-author.
