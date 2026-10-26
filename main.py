"""MazeQuest application loop for the single handcrafted catacomb adventure."""
from __future__ import annotations
import time
import pygame
from maze import LEVELS, Maze
from game_logic import Game
from save_data import default_config_path, load_state, save_state
from display_manager import DisplayManager
from sound import SoundManager
from ui import UI, FPS, HINT_COOLDOWN

SETTINGS_ROWS = ["DISPLAY MODE", "SCALING", "SOUND EFFECTS", "VOLUME", "SHOW HINTS", "FOG OF WAR", "BACK TO MENU"]
MOVE_KEYS = {
    pygame.K_UP: (-1, 0), pygame.K_w: (-1, 0),
    pygame.K_DOWN: (1, 0), pygame.K_s: (1, 0),
    pygame.K_LEFT: (0, -1), pygame.K_a: (0, -1),
    pygame.K_RIGHT: (0, 1), pygame.K_d: (0, 1),
}


def hover_index(rects, pos):
    """Index of the (label, rect) pair under ``pos``, or None."""
    for i, (_, rect) in enumerate(rects):
        if rect.collidepoint(pos):
            return i
    return None


def run() -> None:
    pygame.init()
    path = default_config_path()
    state = load_state(path)
    settings = state["settings"]
    # Pixel theme: crisp integer scaling unless the user explicitly picked SMOOTH.
    if not settings.get("scaling_chosen"):
        settings["scaling"] = "integer"

    display_mgr = DisplayManager(fullscreen=bool(settings.get("fullscreen", False)),
                                 scale_mode=settings.get("scaling", "integer"))
    screen = display_mgr.init_display()
    sound_mgr = SoundManager(enabled=bool(settings.get("sound", True)),
                             volume=float(settings.get("volume", 0.7)))
    ui = UI(screen, sound_mgr=sound_mgr, display_mgr=display_mgr)
    clock = pygame.time.Clock()

    mode = "menu"
    previous_mode = "menu"
    game = None
    menu_selected = 0
    settings_selected = 0
    result_selected = 1
    new_best = False
    hint_ready_at = 0.0
    running = True
    last_save = time.monotonic()
    last_mouse = None
    rendered_mode = None

    # ------------------------------------------------------------ helpers
    def start():
        nonlocal hint_ready_at
        hint_ready_at = 0.0
        return Game(Maze.handcrafted(), 1, LEVELS[0].time_limit)

    def persist():
        if game is not None and not (game.won or game.expired):
            state["current"] = game.snapshot()
        settings["fullscreen"] = display_mgr.is_fullscreen
        settings["sound"] = sound_mgr.enabled
        settings["volume"] = round(sound_mgr.volume, 2)
        settings["scaling"] = display_mgr.scale_mode
        save_state(path, state)

    def restore():
        current = state.get("current")
        if not current:
            return start()
        return Game.from_snapshot(Maze.handcrafted(), current, LEVELS[0].time_limit)

    def toggle_display_mode():
        display_mgr.toggle_fullscreen()
        persist()

    def go(new_mode: str) -> None:
        nonlocal mode, menu_selected, settings_selected
        mode = new_mode
        if new_mode == "menu":
            menu_selected = 0
        elif new_mode == "settings":
            settings_selected = 0

    def begin_run(new_game) -> None:
        nonlocal game, result_selected, new_best
        game = new_game
        result_selected = 1
        new_best = False
        go("game")
        persist()

    def complete_run() -> None:
        nonlocal new_best
        if mode != "game" or not (game.won or game.expired):
            return
        state["history"].append(game.snapshot())
        state["current"] = None
        new_best = False
        if not game.won:
            sound_mgr.play("lose")
        if game.won:
            sound_mgr.play("win")
            old = state["personal_bests"].get("1")
            new_best = old is None or round(game.elapsed, 2) < old.get("time", float("inf"))
            state["personal_bests"]["1"] = {
                "time": min(round(game.elapsed, 2), old.get("time", float("inf"))) if old else round(game.elapsed, 2),
                "moves": min(game.stats.moves, old.get("moves", 10**9)) if old else game.stats.moves,
            }
        save_state(path, state)
        go("result")

    def request_hint() -> None:
        nonlocal hint_ready_at
        now = time.monotonic()
        if not settings.get("show_hints", True) or now < hint_ready_at:
            return
        hint_ready_at = now + HINT_COOLDOWN
        game.hint_position = game.request_hint()
        sound_mgr.play("click")

    def handle_game_move(dr: int, dc: int) -> None:
        nonlocal last_save
        old_pos = game.position
        old_keys = len(game.keys)
        old_treasures = len(game.collected_treasures)
        if game.move(dr, dc):
            sound_mgr.play("step")
            ui.footstep(game.maze, *old_pos)
            if len(game.keys) > old_keys:
                sound_mgr.play("key")
                ui.pickup_burst(game.maze, *game.position, count=22)
            elif len(game.collected_treasures) > old_treasures:
                sound_mgr.play("pickup")
                ui.pickup_burst(game.maze, *game.position, count=18)
            persist()
            last_save = time.monotonic()
        else:
            sound_mgr.play("bump")
            ui.bump(dr, dc)

    # ----------------------------------------------------- action dispatch
    # Mouse clicks and key presses share these so each screen's logic lives once.
    def quit_game() -> None:
        nonlocal running
        persist()
        running = False

    def open_settings(origin: str) -> None:
        nonlocal previous_mode
        previous_mode = origin
        go("settings")

    def menu_action(label: str) -> None:
        nonlocal game
        if label == "ENTER THE DUNGEON":
            begin_run(start())
        elif label == "CONTINUE":
            game = restore()
            go("game")
        elif label == "SETTINGS":
            open_settings("menu")
        elif label == "STATISTICS":
            go("statistics")
        elif label == "QUIT":
            quit_game()

    def settings_action(label: str, direction: int = 0, click_pos=None) -> None:
        if label == "DISPLAY MODE":
            toggle_display_mode()
        elif label == "SCALING":
            display_mgr.set_scale_mode("integer" if display_mgr.scale_mode == "smooth" else "smooth")
            settings["scaling_chosen"] = True
            persist()
        elif label == "SOUND EFFECTS":
            sound_mgr.enabled = not sound_mgr.enabled
            persist()
        elif label == "VOLUME":
            if click_pos is not None:
                vol = ui.volume_from_pos(click_pos)
                if vol is not None:
                    sound_mgr.volume = vol
            elif direction:
                sound_mgr.volume = max(0.0, min(1.0, round((sound_mgr.volume + 0.05 * direction) * 20) / 20))
            else:
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
        nonlocal game
        if label == "RESUME EXPEDITION":
            game.toggle_pause()
        elif label == "RESTART LEVEL":
            begin_run(start())
        elif label == "SETTINGS":
            open_settings("game")
        elif label == "SAVE & MENU":
            persist()
            game = None
            go("menu")
        elif label == "QUIT":
            quit_game()

    def result_action(label: str) -> None:
        nonlocal game
        if label == "VIEW OPTIMAL PATH":
            game.show_optimal_route = True
            game.result_view = True
            go("game")
        elif label == "PLAY AGAIN":
            begin_run(start())
        elif label == "RETURN TO MENU":
            game = None
            go("menu")

    def continue_info() -> str:
        current = state.get("current") or {}
        left = max(0, int(LEVELS[0].time_limit - float(current.get("elapsed", 0))))
        return f"{left // 60:02d}:{left % 60:02d} LEFT"

    def menu_entries():
        return ["ENTER THE DUNGEON"] + (["CONTINUE"] if state.get("current") else []) + ["SETTINGS", "STATISTICS", "QUIT"]

    # ------------------------------------------------------------ main loop
    while running:
        now = time.monotonic()
        raw_mouse = pygame.mouse.get_pos()
        logical_mouse = display_mgr.screen_to_internal(raw_mouse)
        ui.hints_enabled = bool(settings.get("show_hints", True))
        ui.fog_enabled = bool(settings.get("fog", False))
        ui.hint_cooldown = max(0.0, hint_ready_at - now)

        # Mouse movement moves the keyboard selection so only one item is lit.
        if logical_mouse != last_mouse and logical_mouse[0] >= 0:
            if mode == "menu":
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
        last_mouse = logical_mouse

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_game()

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
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                click = display_mgr.screen_to_internal(event.pos)
                if click[0] >= 0:
                    sound_mgr.play("click")

                if mode == "menu":
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
                        label = ui.pause_hit(click)
                        if label:
                            pause_action(label)
                    else:
                        action = ui.game_hit(click)
                        if action == "HINT":
                            request_hint()
                        elif action == "PAUSE":
                            game.toggle_pause()
                        elif action == "SETTINGS":
                            game.toggle_pause()
                            open_settings("game")
                elif mode == "result":
                    label = ui.result_hit(click)
                    if label:
                        result_action(label)

            # Dragging the volume slider
            elif event.type == pygame.MOUSEMOTION and event.buttons[0] and mode == "settings":
                drag = display_mgr.screen_to_internal(event.pos)
                if ui.volume_from_pos(drag) is not None:
                    settings_action("VOLUME", click_pos=drag)

            # --- KEYBOARD ---
            elif event.type == pygame.KEYDOWN:
                key = event.key
                if mode == "menu":
                    entries = menu_entries()
                    if key in (pygame.K_DOWN, pygame.K_s):
                        menu_selected = (menu_selected + 1) % len(entries)
                        sound_mgr.play("click")
                    elif key in (pygame.K_UP, pygame.K_w):
                        menu_selected = (menu_selected - 1) % len(entries)
                        sound_mgr.play("click")
                    elif key in (pygame.K_RETURN, pygame.K_SPACE):
                        sound_mgr.play("click")
                        menu_action(entries[menu_selected % len(entries)])
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
                        direction = -1 if key in (pygame.K_LEFT, pygame.K_a) else 1 if key in (pygame.K_RIGHT, pygame.K_d) else 0
                        sound_mgr.play("click")
                        settings_action(SETTINGS_ROWS[settings_selected], direction=direction)
                    elif key == pygame.K_ESCAPE:
                        sound_mgr.play("click")
                        go(previous_mode)

                elif mode == "statistics":
                    if key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_SPACE):
                        sound_mgr.play("click")
                        go("menu")

                elif mode == "game":
                    if game.paused:
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
                            game.toggle_pause()
                    elif key in (pygame.K_ESCAPE, pygame.K_p):
                        game.toggle_pause()
                    elif key == pygame.K_r:
                        begin_run(start())
                    elif key == pygame.K_h:
                        request_hint()
                    elif key == pygame.K_t:
                        game.show_actual_route = not game.show_actual_route
                        sound_mgr.play("click")
                    elif key == pygame.K_v:
                        sound_mgr.play("click")
                        if game.result_view:
                            game.show_optimal_route = False
                            game.result_view = False
                            go("result")
                        else:
                            game.show_optimal_route = not game.show_optimal_route
                    elif key == pygame.K_F5:
                        persist()
                        sound_mgr.play("click")
                    elif key in MOVE_KEYS:
                        handle_game_move(*MOVE_KEYS[key])
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
            if time.monotonic() - last_save > 8:
                persist()
                last_save = time.monotonic()
            if game.expired and not game.result_view:
                complete_run()

        # Rendering
        if mode != rendered_mode:
            ui.start_fade()
            rendered_mode = mode
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

        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    run()
