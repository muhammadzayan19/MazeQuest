"""MazeQuest application loop for the single handcrafted catacomb adventure."""
# =============================================================================
# WHAT THIS FILE IS
# -----------------------------------------------------------------------------
# The entry point and the "conductor" of the whole game. Run `python main.py`
# and the function run() below starts everything and then loops forever:
#
#       read input  ->  change the game's state  ->  draw a frame  ->  repeat
#
# That repeat is the GAME LOOP, and it runs about 60 times per second.
#
# The game is always in exactly one MODE (a text label stored in `mode`):
#       "menu"        the start screen
#       "game"        playing the dungeon (also shows the pause menu on top)
#       "settings"    the settings screen
#       "statistics"  past-runs screen
#       "result"      the end screen after winning or losing
# Input is interpreted differently depending on the current mode, and the
# matching screen is drawn at the bottom of the loop.
#
# This file wires the other pieces together:
#   game_logic.Game      the rules (it knows nothing about screens)
#   ui.UI                draws screens and says which button a click hit
#   display_manager      window / fullscreen / scaling
#   sound.SoundManager   sound effects
#   save_data            loading and saving the progress file
# =============================================================================

# Lets type hints refer to names defined later in the file.
from __future__ import annotations

# time gives us the clock (used for autosave timing and the hint cooldown).
import time

# pygame is the library that opens the window, reads keyboard/mouse input and
# plays sound. We use it here for input events and key constants.
import pygame

# The level list and map class.
from maze import LEVELS, Maze

# The game rules class.
from game_logic import Game

# Functions for finding, reading and writing the save file.
from save_data import default_config_path, load_state, save_state

# Window and scaling manager.
from display_manager import DisplayManager

# Sound effects.
from sound import SoundManager

# The screen painter, the target frame rate (60), and the hint cooldown (seconds).
from ui import UI, FPS, HINT_COOLDOWN

# The rows of the settings screen, in the order they appear. The keyboard code
# uses this list to know which setting the highlighted row refers to.
SETTINGS_ROWS = ["DISPLAY MODE", "SCALING", "SOUND EFFECTS", "VOLUME", "SHOW HINTS", "FOG OF WAR", "BACK TO MENU"]

# Which keys move the hero, and in which direction. Each direction is
# (row change, column change): (-1, 0) = up one row, (1, 0) = down one row,
# (0, -1) = left one column, (0, 1) = right one column. Arrow keys and WASD both work.
MOVE_KEYS = {
    pygame.K_UP: (-1, 0), pygame.K_w: (-1, 0),
    pygame.K_DOWN: (1, 0), pygame.K_s: (1, 0),
    pygame.K_LEFT: (0, -1), pygame.K_a: (0, -1),
    pygame.K_RIGHT: (0, 1), pygame.K_d: (0, 1),
}


def hover_index(rects, pos):
    """Index of the (label, rect) pair under ``pos``, or None."""
    # `rects` is a list of (label, rectangle) pairs for the buttons on screen.
    # enumerate() gives each item together with its position number i.
    # The `_` means "I don't need the label here, only the rectangle".
    for i, (_, rect) in enumerate(rects):
        # collidepoint is True when the mouse point lies inside the rectangle.
        if rect.collidepoint(pos):
            return i
    # The mouse is not over any button.
    return None


def run() -> None:
    """Set everything up, then run the game loop until the player quits."""
    # Start up all of pygame's internal modules (display, sound, fonts, ...).
    pygame.init()
    # Where the save file lives, and what it currently contains (or a fresh default).
    path = default_config_path()
    state = load_state(path)
    # A shortcut name for the settings part of the saved data. Both names refer to
    # the SAME dictionary, so changing `settings` also changes `state["settings"]`.
    settings = state["settings"]
    # Pixel theme: crisp integer scaling unless the user explicitly picked SMOOTH.
    # (The flag "scaling_chosen" is only set when the player changes it in Settings.)
    if not settings.get("scaling_chosen"):
        settings["scaling"] = "integer"

    # Create the window manager using the saved fullscreen/scaling preferences.
    display_mgr = DisplayManager(fullscreen=bool(settings.get("fullscreen", False)),
                                 scale_mode=settings.get("scaling", "integer"))
    # Open the window; `screen` is the surface everything is finally drawn onto.
    screen = display_mgr.init_display()
    # Create the sound player with the saved on/off and volume settings.
    sound_mgr = SoundManager(enabled=bool(settings.get("sound", True)),
                             volume=float(settings.get("volume", 0.7)))
    # Create the object that paints every screen.
    ui = UI(screen, sound_mgr=sound_mgr, display_mgr=display_mgr)
    # A clock used at the end of each loop to hold the game to 60 frames per second.
    clock = pygame.time.Clock()

    # ------------------------------------------------------------------------
    # The game's changing values live here as ordinary variables. The small
    # helper functions below change them using `nonlocal` (explained there).
    # ------------------------------------------------------------------------
    # Current screen, and which screen to return to from Settings.
    mode = "menu"
    previous_mode = "menu"
    # The Game object of the run in progress (None when there is none).
    game = None
    # Which button is highlighted on the menu / settings / end screen.
    menu_selected = 0
    settings_selected = 0
    result_selected = 1
    # True if the run just finished set a new best time (shown as a badge).
    new_best = False
    # The clock time at which the hint button works again (0 = ready now).
    hint_ready_at = 0.0
    # The loop keeps running while this is True; quitting sets it to False.
    running = True
    # The clock time of the last save (used for the 8-second autosave).
    last_save = time.monotonic()
    # The mouse position in the previous frame (to notice when the mouse moves).
    last_mouse = None
    # The mode that was drawn last frame (to notice when the screen changes).
    rendered_mode = None

    # ------------------------------------------------------------ helpers
    # The functions below are defined INSIDE run() so they can see its variables.
    # To CHANGE (re-assign) such a variable they must declare it `nonlocal`;
    # without that, Python would create a new local variable of the same name.
    def start():
        """Create a brand-new game and reset the hint cooldown."""
        nonlocal hint_ready_at
        hint_ready_at = 0.0
        return Game(Maze.handcrafted(), 1, LEVELS[0].time_limit)

    def persist():
        """Write the settings (and the game in progress) to the save file."""
        # Save the game in progress, but not a finished one (win/lose are recorded
        # separately in the history instead).
        if game is not None and not (game.won or game.expired):
            state["current"] = game.snapshot()
        # Copy the live setting values into the saved settings.
        settings["fullscreen"] = display_mgr.is_fullscreen
        settings["sound"] = sound_mgr.enabled
        settings["volume"] = round(sound_mgr.volume, 2)
        settings["scaling"] = display_mgr.scale_mode
        # Write the file to disk.
        save_state(path, state)

    def restore():
        """Rebuild the saved game for the "Continue" button (or a new one if none)."""
        current = state.get("current")
        if not current:
            return start()
        return Game.from_snapshot(Maze.handcrafted(), current, LEVELS[0].time_limit)

    def toggle_display_mode():
        """Switch between windowed and fullscreen, and remember the choice."""
        display_mgr.toggle_fullscreen()
        persist()

    def go(new_mode: str) -> None:
        """Switch to another screen, resetting the highlighted row where it makes sense."""
        nonlocal mode, menu_selected, settings_selected
        mode = new_mode
        # Entering the menu or settings always starts with the first row highlighted.
        if new_mode == "menu":
            menu_selected = 0
        elif new_mode == "settings":
            settings_selected = 0

    def begin_run(new_game) -> None:
        """Make `new_game` the active game and switch to the dungeon screen."""
        nonlocal game, result_selected, new_best
        game = new_game
        # Reset the end-screen state for the new run.
        result_selected = 1
        new_best = False
        go("game")
        # Save immediately so "Continue" works even if the game is closed right away.
        persist()

    def complete_run() -> None:
        """Called when a run might have ended: record the result and show the end screen."""
        nonlocal new_best
        # Only act while playing, and only if the player has won or time ran out.
        if mode != "game" or not (game.won or game.expired):
            return
        # Add this run to the history and clear the "game in progress" slot.
        state["history"].append(game.snapshot())
        state["current"] = None
        new_best = False
        # Play the matching jingle: a low tone for a loss.
        if not game.won:
            sound_mgr.play("lose")
        if game.won:
            sound_mgr.play("win")
            # The stored best result for level 1 (None if this is the first win).
            old = state["personal_bests"].get("1")
            # It is a new best if there is no old record or this time is faster.
            new_best = old is None or round(game.elapsed, 2) < old.get("time", float("inf"))
            # Store the better of the old and new time, and the better of the old and
            # new move count (min = the smaller number = better).
            state["personal_bests"]["1"] = {
                "time": min(round(game.elapsed, 2), old.get("time", float("inf"))) if old else round(game.elapsed, 2),
                "moves": min(game.stats.moves, old.get("moves", 10**9)) if old else game.stats.moves,
            }
        # Write everything to disk and show the end screen.
        save_state(path, state)
        go("result")

    def request_hint() -> None:
        """Show a hint, unless hints are disabled or still cooling down."""
        nonlocal hint_ready_at
        now = time.monotonic()
        # Refuse if the setting is off or the cooldown has not finished.
        if not settings.get("show_hints", True) or now < hint_ready_at:
            return
        # Start a new cooldown, then ask the game for the next tile to point at.
        hint_ready_at = now + HINT_COOLDOWN
        game.hint_position = game.request_hint()
        sound_mgr.play("click")

    def handle_game_move(dr: int, dc: int) -> None:
        """Try to move the hero by (dr, dc) and trigger the matching sounds and effects."""
        nonlocal last_save
        # Remember the situation BEFORE the move so we can tell what changed.
        old_pos = game.position
        old_keys = len(game.keys)
        old_treasures = len(game.collected_treasures)
        # game.move returns True if the hero really moved.
        if game.move(dr, dc):
            sound_mgr.play("step")
            # Dust puff and footprint on the tile the hero just left.
            ui.footstep(game.maze, *old_pos)
            # More keys than before -> a key was just picked up.
            if len(game.keys) > old_keys:
                sound_mgr.play("key")
                ui.pickup_burst(game.maze, *game.position, count=22)
            # More chests than before -> a treasure was just collected.
            elif len(game.collected_treasures) > old_treasures:
                sound_mgr.play("pickup")
                ui.pickup_burst(game.maze, *game.position, count=18)
            # Save progress after every successful step and reset the autosave timer.
            persist()
            last_save = time.monotonic()
        else:
            # The move was blocked (wall or locked gate): thud sound and a nudge animation.
            sound_mgr.play("bump")
            ui.bump(dr, dc)

    # ----------------------------------------------------- action dispatch
    # Mouse clicks and key presses share these so each screen's logic lives once.
    # (A "dispatch" function takes a button's label and runs what that button does.)
    def quit_game() -> None:
        """Save, then tell the main loop to stop."""
        nonlocal running
        persist()
        running = False

    def open_settings(origin: str) -> None:
        """Open Settings, remembering which screen to return to ("menu" or "game")."""
        nonlocal previous_mode
        previous_mode = origin
        go("settings")

    def menu_action(label: str) -> None:
        """Do what the clicked/selected menu button says."""
        nonlocal game
        if label == "ENTER THE DUNGEON":
            begin_run(start())
        elif label == "CONTINUE":
            # Load the saved game and jump straight into it.
            game = restore()
            go("game")
        elif label == "SETTINGS":
            open_settings("menu")
        elif label == "STATISTICS":
            go("statistics")
        elif label == "QUIT":
            quit_game()

    def settings_action(label: str, direction: int = 0, click_pos=None) -> None:
        """Change the setting named `label`.

        direction: -1 / +1 for a left/right key press, 0 for Enter/Space.
        click_pos: where the mouse clicked (used by the volume slider).
        """
        if label == "DISPLAY MODE":
            toggle_display_mode()
        elif label == "SCALING":
            # Flip between smooth and sharp scaling, and remember the player CHOSE it.
            display_mgr.set_scale_mode("integer" if display_mgr.scale_mode == "smooth" else "smooth")
            settings["scaling_chosen"] = True
            persist()
        elif label == "SOUND EFFECTS":
            sound_mgr.enabled = not sound_mgr.enabled
            persist()
        elif label == "VOLUME":
            if click_pos is not None:
                # A click or drag on the slider: convert its position to a 0..1 volume.
                vol = ui.volume_from_pos(click_pos)
                if vol is not None:
                    sound_mgr.volume = vol
            elif direction:
                # Left/right keys change the volume in 5% steps, kept between 0 and 1.
                # round(x * 20) / 20 snaps to the nearest 0.05.
                sound_mgr.volume = max(0.0, min(1.0, round((sound_mgr.volume + 0.05 * direction) * 20) / 20))
            else:
                # Enter on the volume row does nothing.
                return
            persist()
        elif label == "SHOW HINTS":
            settings["show_hints"] = not settings.get("show_hints", True)
            persist()
        elif label == "FOG OF WAR":
            settings["fog"] = not settings.get("fog", False)
            persist()
        elif label == "BACK TO MENU":
            go(previous_mode)

    def pause_action(label: str) -> None:
        """Do what the chosen pause-menu option says."""
        nonlocal game
        if label == "RESUME EXPEDITION":
            game.toggle_pause()
        elif label == "RESTART LEVEL":
            begin_run(start())
        elif label == "SETTINGS":
            open_settings("game")
        elif label == "SAVE & MENU":
            # Save, throw away the live game object and return to the start screen.
            persist()
            game = None
            go("menu")
        elif label == "QUIT":
            quit_game()

    def result_action(label: str) -> None:
        """Do what the chosen end-screen button says."""
        nonlocal game
        if label == "VIEW OPTIMAL PATH":
            # Go back into the dungeon view with the shortest route drawn.
            game.show_optimal_route = True
            game.result_view = True
            go("game")
        elif label == "PLAY AGAIN":
            begin_run(start())
        elif label == "RETURN TO MENU":
            game = None
            go("menu")

    def continue_info() -> str:
        """Text like '12:40 LEFT' shown on the CONTINUE button."""
        current = state.get("current") or {}
        # Seconds remaining = the time limit minus the time already used in the save.
        left = max(0, int(LEVELS[0].time_limit - float(current.get("elapsed", 0))))
        # `//` is whole-number division, `%` is the remainder: minutes and seconds.
        return f"{left // 60:02d}:{left % 60:02d} LEFT"

    def menu_entries():
        """The menu button labels in order (CONTINUE only appears if a save exists)."""
        return ["ENTER THE DUNGEON"] + (["CONTINUE"] if state.get("current") else []) + ["SETTINGS", "STATISTICS", "QUIT"]

    # ------------------------------------------------------------ main loop
    # Everything from here runs once per frame until `running` becomes False.
    while running:
        # The current clock time and the mouse position (converted from window
        # pixels to the game's own internal 640x440 coordinates).
        now = time.monotonic()
        raw_mouse = pygame.mouse.get_pos()
        logical_mouse = display_mgr.screen_to_internal(raw_mouse)
        # Pass the latest settings and the hint cooldown to the screen painter.
        ui.hints_enabled = bool(settings.get("show_hints", True))
        ui.fog_enabled = bool(settings.get("fog", False))
        ui.hint_cooldown = max(0.0, hint_ready_at - now)

        # Mouse movement moves the keyboard selection so only one item is lit.
        # (Only react when the mouse actually moved and is inside the game area.)
        if logical_mouse != last_mouse and logical_mouse[0] >= 0:
            if mode == "menu":
                # Highlight the menu button under the mouse (keep the old one if none).
                idx = hover_index(ui.menu_rects, logical_mouse)
                menu_selected = menu_selected if idx is None else idx
            elif mode == "settings":
                idx = hover_index(ui.settings_rects, logical_mouse)
                settings_selected = settings_selected if idx is None else idx
            elif mode == "result":
                idx = hover_index(ui.result_rects, logical_mouse)
                result_selected = result_selected if idx is None else idx
            elif mode == "game" and game is not None and game.paused:
                idx = hover_index(ui.pause_rects, logical_mouse)
                if idx is not None:
                    game.pause_selected = idx
        # Remember this position to compare against next frame.
        last_mouse = logical_mouse

        # pygame collects everything that happened (key presses, clicks, window
        # events) in a queue; this loop handles each waiting event in order.
        for event in pygame.event.get():
            # The window's close button was pressed.
            if event.type == pygame.QUIT:
                quit_game()

            # The player resized the window.
            elif event.type == pygame.VIDEORESIZE:
                display_mgr.handle_resize(event.size)

            # Global display shortcuts (F11 and Alt+Enter)
            elif event.type == pygame.KEYDOWN and (
                event.key == pygame.K_F11 or
                (event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and (event.mod & pygame.KMOD_ALT))
            ):
                toggle_display_mode()
                sound_mgr.play("click")

            # --- MOUSE ---
            # A left-button (button 1) click.
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Convert the click position to the game's internal coordinates
                # (x is negative if the click was outside the game area).
                click = display_mgr.screen_to_internal(event.pos)
                if click[0] >= 0:
                    sound_mgr.play("click")

                # Which screen are we on decides what a click means.
                if mode == "menu":
                    # ui.menu_hit tells us which button (if any) was under the click.
                    label = ui.menu_hit(click)
                    if label:
                        menu_action(label)
                elif mode == "settings":
                    label = ui.settings_hit(click)
                    if label:
                        settings_action(label, click_pos=click)
                elif mode == "statistics":
                    if ui.statistics_hit(click):
                        go("menu")
                elif mode == "game":
                    if game.paused:
                        # Pause menu is open: clicks go to its buttons.
                        label = ui.pause_hit(click)
                        if label:
                            pause_action(label)
                    else:
                        # Otherwise clicks go to the on-screen HUD buttons.
                        action = ui.game_hit(click)
                        if action == "HINT":
                            request_hint()
                        elif action == "PAUSE":
                            game.toggle_pause()
                        elif action == "SETTINGS":
                            # Pause first so the clock stops while in settings.
                            game.toggle_pause()
                            open_settings("game")
                elif mode == "result":
                    label = ui.result_hit(click)
                    if label:
                        result_action(label)

            # Dragging the volume slider
            # The mouse moved while the left button (buttons[0]) is held in Settings.
            elif event.type == pygame.MOUSEMOTION and event.buttons[0] and mode == "settings":
                drag = display_mgr.screen_to_internal(event.pos)
                if ui.volume_from_pos(drag) is not None:
                    settings_action("VOLUME", click_pos=drag)

            # --- KEYBOARD ---
            # Any key press that was not already handled by the shortcuts above.
            elif event.type == pygame.KEYDOWN:
                key = event.key
                if mode == "menu":
                    entries = menu_entries()
                    if key in (pygame.K_DOWN, pygame.K_s):
                        # `% len(entries)` wraps around: after the last entry comes the first.
                        menu_selected = (menu_selected + 1) % len(entries)
                        sound_mgr.play("click")
                    elif key in (pygame.K_UP, pygame.K_w):
                        menu_selected = (menu_selected - 1) % len(entries)
                        sound_mgr.play("click")
                    elif key in (pygame.K_RETURN, pygame.K_SPACE):
                        sound_mgr.play("click")
                        menu_action(entries[menu_selected % len(entries)])
                    # Number keys 1..9 pick the matching menu entry directly.
                    elif pygame.K_1 <= key <= pygame.K_9 and key - pygame.K_1 < len(entries):
                        menu_selected = key - pygame.K_1
                        sound_mgr.play("click")
                        menu_action(entries[menu_selected])
                    elif key == pygame.K_ESCAPE:
                        quit_game()

                elif mode == "settings":
                    if key in (pygame.K_DOWN, pygame.K_s):
                        settings_selected = (settings_selected + 1) % len(SETTINGS_ROWS)
                        sound_mgr.play("click")
                    elif key in (pygame.K_UP, pygame.K_w):
                        settings_selected = (settings_selected - 1) % len(SETTINGS_ROWS)
                        sound_mgr.play("click")
                    elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_a, pygame.K_d):
                        # Left keys mean -1, right keys +1, Enter/Space 0 (just toggle).
                        direction = -1 if key in (pygame.K_LEFT, pygame.K_a) else 1 if key in (pygame.K_RIGHT, pygame.K_d) else 0
                        sound_mgr.play("click")
                        settings_action(SETTINGS_ROWS[settings_selected], direction=direction)
                    elif key == pygame.K_ESCAPE:
                        sound_mgr.play("click")
                        go(previous_mode)

                elif mode == "statistics":
                    # Enter, Escape or Space returns to the menu.
                    if key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_SPACE):
                        sound_mgr.play("click")
                        go("menu")

                elif mode == "game":
                    if game.paused:
                        # The pause menu is open: arrows move the highlight.
                        count = len(UI.PAUSE_OPTIONS)
                        if key in (pygame.K_UP, pygame.K_w):
                            game.pause_selected = (game.pause_selected - 1) % count
                            sound_mgr.play("click")
                        elif key in (pygame.K_DOWN, pygame.K_s):
                            game.pause_selected = (game.pause_selected + 1) % count
                            sound_mgr.play("click")
                        elif key in (pygame.K_RETURN, pygame.K_SPACE):
                            sound_mgr.play("click")
                            pause_action(UI.PAUSE_OPTIONS[game.pause_selected])
                        elif key in (pygame.K_ESCAPE, pygame.K_p):
                            # Escape or P closes the pause menu.
                            game.toggle_pause()
                    # The pause menu is NOT open, so these are the gameplay keys:
                    elif key in (pygame.K_ESCAPE, pygame.K_p):
                        # Open the pause menu.
                        game.toggle_pause()
                    elif key == pygame.K_r:
                        # R restarts the level.
                        begin_run(start())
                    elif key == pygame.K_h:
                        request_hint()
                    elif key == pygame.K_t:
                        # T shows/hides the trail of tiles the player has walked.
                        game.show_actual_route = not game.show_actual_route
                        sound_mgr.play("click")
                    elif key == pygame.K_v:
                        # V shows/hides the optimal route. When viewing it from the end
                        # screen, V goes back to the end screen instead.
                        sound_mgr.play("click")
                        if game.result_view:
                            game.show_optimal_route = False
                            game.result_view = False
                            go("result")
                        else:
                            game.show_optimal_route = not game.show_optimal_route
                    elif key == pygame.K_F5:
                        # F5 saves on demand.
                        persist()
                        sound_mgr.play("click")
                    elif key in MOVE_KEYS:
                        # `*` unpacks the (row change, column change) pair into two arguments.
                        handle_game_move(*MOVE_KEYS[key])
                    # After any key press, check whether the run just ended (unless the
                    # player is only looking at the route from the end screen).
                    if game is not None and not game.result_view:
                        complete_run()

                elif mode == "result":
                    count = len(UI.RESULT_ACTIONS)
                    if key in (pygame.K_LEFT, pygame.K_a):
                        result_selected = (result_selected - 1) % count
                        sound_mgr.play("click")
                    elif key in (pygame.K_RIGHT, pygame.K_d):
                        result_selected = (result_selected + 1) % count
                        sound_mgr.play("click")
                    elif key == pygame.K_v:
                        sound_mgr.play("click")
                        result_action("VIEW OPTIMAL PATH")
                    elif key == pygame.K_r:
                        sound_mgr.play("click")
                        result_action("PLAY AGAIN")
                    elif key in (pygame.K_RETURN, pygame.K_SPACE):
                        sound_mgr.play("click")
                        result_action(UI.RESULT_ACTIONS[result_selected][0])
                    elif key == pygame.K_ESCAPE:
                        sound_mgr.play("click")
                        result_action("RETURN TO MENU")

        # Autosave during active exploration
        if game and mode == "game":
            # Save every 8 seconds so the timer in the save stays reasonably fresh.
            if time.monotonic() - last_save > 8:
                persist()
                last_save = time.monotonic()
            # Time may run out even when the player presses no key, so check every frame.
            if game.expired and not game.result_view:
                complete_run()

        # Rendering
        # When the screen changes, start a short fade-in transition.
        if mode != rendered_mode:
            ui.start_fade()
            rendered_mode = mode
        # Draw the screen that matches the current mode (each call also shows the frame).
        if mode == "menu":
            ui.menu(menu_selected, bool(state.get("current")), logical_mouse,
                    state["personal_bests"], state["history"],
                    continue_info() if state.get("current") else "")
        elif mode == "settings":
            ui.settings(settings, settings_selected, logical_mouse)
        elif mode == "statistics":
            ui.statistics(state["history"], state["personal_bests"], logical_mouse)
        elif mode == "game":
            ui.dungeon(game, logical_mouse)
        elif mode == "result":
            ui.results(game, logical_mouse, result_selected, new_best)

        # Wait just long enough to cap the loop at FPS (60) frames per second.
        clock.tick(FPS)

    # The loop ended: shut pygame down cleanly.
    pygame.quit()


# This runs only when the file is started directly (`python main.py`), not when
# another file imports it. It starts the game.
if __name__ == "__main__":
    run()
