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
hint, `T` to show your trail, and `V` to toggle the optimal route. The pause
panel uses arrows and Enter. Progress saves automatically; choose Continue from
the main menu to resume. The completion screen offers route viewing, replay,
and return to the menu.

## Design and algorithms

`maze.py` contains a handcrafted nested-list map for The Forgotten Catacombs,
including its entrance crypt, nave, reliquary, key chamber, sealed passage and
exit. `solver.py` implements key-aware breadth-first search for a verified
shortest route and recursive depth-first search for exploration/backtracking.
`game_logic.py` keeps collision, movement, objective state, timing and run
metrics independent from the renderer. `ui.py` draws the top-down raised-stone
dungeon, deterministic chipped floor tiles, sconces, crystals, the adventurer
and the custom fantasy interface at a low pixel resolution. `save_data.py`
stores runs and personal records in versioned JSON using atomic replacement.

## Tests

```bash
python -m unittest discover -s tests -v
```

The project uses only the Python standard library and `pygame-ce==2.5.8`.
