# MazeQuest: The Forgotten Catacombs

A single-level, handcrafted dark-fantasy dungeon adventure made with Python
3.14 and Pygame CE. Explore an old fortress, recover its key and optional
treasures, pass the sealed door, and reach the relic gate.

## Run

```bash
python -m pip install -r requirements.txt
python main.py
```

Move with WASD or the arrow keys. Press `P` or `Esc` to pause, `H` for a BFS
hint, `T` to show your trail, and `V` to toggle the optimal route. Press `F11`
or `Alt+Enter` to toggle fullscreen. Window resizing is fully supported with
aspect-correct letterboxing. The pause panel and Settings menu use arrows, Enter,
or direct mouse clicks. Progress saves automatically; choose Continue from
the main menu to resume. The completion screen offers route viewing, replay,
and return to the menu.

## Design and algorithms

`maze.py` contains a handcrafted nested-list map for The Forgotten Catacombs,
including its entrance crypt, nave, reliquary, key chamber, sealed passage and
exit. `solver.py` implements key-aware breadth-first search for a verified
shortest route and recursive depth-first search for exploration/backtracking.
`game_logic.py` keeps collision, movement, objective state, timing and run
metrics independent from the renderer. `display_manager.py` maintains an internal
640x440 pixel-art canvas, calculates aspect-correct letterboxed viewports, and
handles seamless fullscreen and resize transitions. `sprites.py` provides
pre-rendered procedural stone masonry with 2.5D perspective, 4-directional
animated hero sprites, smooth radial lighting, and props. `particles.py` powers
delta-time torch embers, crystal sparkles, and pickup bursts. `sound.py` provides
crash-proof procedural audio feedback. `ui.py` orchestrates rendering, fonts,
and retro RPG interfaces. `save_data.py` stores runs, settings, and personal
records in versioned JSON using atomic replacement.

## Tests

```bash
python -m unittest discover -s tests -v
```

The project uses only the Python standard library and `pygame-ce==2.5.8`.
