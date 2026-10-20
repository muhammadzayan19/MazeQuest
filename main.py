"""MazeQuest application loop for the single handcrafted catacomb adventure."""
from __future__ import annotations
import time
import pygame
from maze import LEVELS, Maze
from game_logic import Game
from save_data import default_config_path, load_state, save_state
from display_manager import DisplayManager, IW, IH, DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT
from sound import SoundManager
from ui import UI, WIDTH, HEIGHT, FPS


def run() -> None:
    pygame.init()
    path = default_config_path()
    state = load_state(path)

    # Display and audio managers
    is_fullscreen_pref = bool(state["settings"].get("fullscreen", False))
    sound_enabled_pref = bool(state["settings"].get("sound", True))

    display_mgr = DisplayManager(fullscreen=is_fullscreen_pref)
    screen = display_mgr.init_display()
    sound_mgr = SoundManager(enabled=sound_enabled_pref)
    ui = UI(screen, sound_mgr=sound_mgr, display_mgr=display_mgr)
    clock = pygame.time.Clock()

    mode = "menu"
    previous_mode = "menu"
    game = None
    menu_selected = 0
    settings_selected = 0
    running = True
    last_save = time.monotonic()

    def start():
        return Game(Maze.handcrafted(), 1, LEVELS[0].time_limit)

    def persist():
        if game is not None and not (game.won or game.expired):
            state["current"] = game.snapshot()
        state["settings"]["fullscreen"] = display_mgr.is_fullscreen
        state["settings"]["sound"] = sound_mgr.enabled
        save_state(path, state)

    def restore():
        current = state.get("current")
        if not current:
            return start()
        return Game.from_snapshot(Maze.handcrafted(), current, LEVELS[0].time_limit)

    def toggle_display_mode():
        is_full = display_mgr.toggle_fullscreen()
        state["settings"]["fullscreen"] = is_full
        persist()
        return is_full

    def complete_run():
        nonlocal mode
        if mode != "game" or not (game.won or game.expired):
            return
        entry = game.snapshot()
        state["history"].append(entry)
        state["current"] = None
        if game.won:
            sound_mgr.play("win")
            old = state["personal_bests"].get("1")
            state["personal_bests"]["1"] = {
                "time": min(round(game.elapsed, 2), old.get("time", float("inf"))) if old else round(game.elapsed, 2),
                "moves": min(game.stats.moves, old.get("moves", 10**9)) if old else game.stats.moves
            }
        save_state(path, state)
        mode = "result"

    def handle_game_move(dr: int, dc: int):
        nonlocal last_save
        old_keys = len(game.keys)
        old_treasures = len(game.collected_treasures)
        moved = game.move(dr, dc)
        if moved:
            # Check for key discovery
            if len(game.keys) > old_keys:
                sound_mgr.play("key")
                ox = (IW - game.maze.cols * 18) // 2
                oy = 44 + (IH - 88 - game.maze.rows * 16) // 2
                px = ox + game.position[1] * 18 + 9
                py = oy + game.position[0] * 16 + 8
                ui.particles.emit_pickup_burst(px, py, count=22)
            # Check for relic discovery
            elif len(game.collected_treasures) > old_treasures:
                sound_mgr.play("pickup")
                ox = (IW - game.maze.cols * 18) // 2
                oy = 44 + (IH - 88 - game.maze.rows * 16) // 2
                px = ox + game.position[1] * 18 + 9
                py = oy + game.position[0] * 16 + 8
                ui.particles.emit_pickup_burst(px, py, count=18)
            persist()
            last_save = time.monotonic()
        else:
            sound_mgr.play("bump")

    while running:
        raw_mouse = pygame.mouse.get_pos()
        logical_mouse = display_mgr.screen_to_internal(raw_mouse)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                persist()
                running = False

            elif event.type == pygame.VIDEORESIZE:
                display_mgr.handle_resize(event.size)

            # Global display shortcuts (F11 and Alt+Enter)
            elif event.type == pygame.KEYDOWN and (
                event.key == pygame.K_F11 or
                (event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and (event.mod & pygame.KMOD_ALT))
            ):
                toggle_display_mode()
                sound_mgr.play("click")
                continue

            # --- MOUSE INTERACTIONS ---
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                logical_click = display_mgr.screen_to_internal(event.pos)
                if logical_click[0] >= 0:
                    sound_mgr.play("click")

                if mode == "menu":
                    label = ui.menu_hit(logical_click)
                    if label == "ENTER THE DUNGEON":
                        game = start()
                        mode = "game"
                        persist()
                    elif label == "CONTINUE":
                        game = restore()
                        mode = "game"
                    elif label == "SETTINGS":
                        previous_mode = "menu"
                        mode = "settings"
                        settings_selected = 0
                    elif label == "STATISTICS":
                        mode = "statistics"
                    elif label == "QUIT":
                        persist()
                        running = False

                elif mode == "settings":
                    label = ui.settings_hit(logical_click)
                    if label == "DISPLAY MODE":
                        toggle_display_mode()
                    elif label == "SOUND EFFECTS":
                        sound_mgr.enabled = not sound_mgr.enabled
                        state["settings"]["sound"] = sound_mgr.enabled
                        persist()
                    elif label == "SHOW HINTS":
                        state["settings"]["show_hints"] = not state["settings"].get("show_hints", True)
                        persist()
                    elif label == "BACK TO MENU":
                        mode = previous_mode

                elif mode == "statistics":
                    label = ui.statistics_hit(logical_click)
                    if label == "RETURN TO MENU":
                        mode = "menu"
                        menu_selected = 0

                elif mode == "game":
                    if game.paused:
                        opt = ui.pause_hit(logical_click)
                        if opt == "RESUME EXPEDITION":
                            game.toggle_pause()
                        elif opt == "RESTART LEVEL":
                            game = start()
                            persist()
                        elif opt == "SETTINGS":
                            previous_mode = "game"
                            mode = "settings"
                            settings_selected = 0
                        elif opt == "SAVE & MENU":
                            persist()
                            game = None
                            mode = "menu"
                            menu_selected = 0
                        elif opt == "QUIT":
                            persist()
                            running = False
                    else:
                        action = ui.game_hit(logical_click)
                        if action == "HINT":
                            game.hint_position = game.request_hint()
                        elif action == "PAUSE":
                            game.toggle_pause()
                        elif action == "SETTINGS":
                            if not game.paused:
                                game.toggle_pause()
                            previous_mode = "game"
                            mode = "settings"
                            settings_selected = 0

                elif mode == "result":
                    action = ui.result_hit(logical_click)
                    if action == "VIEW OPTIMAL PATH":
                        game.show_optimal_route = True
                        game.result_view = True
                        mode = "game"
                    elif action == "PLAY AGAIN":
                        game = start()
                        mode = "game"
                        persist()
                    elif action == "RETURN TO MENU":
                        game = None
                        mode = "menu"
                        menu_selected = 0

            # --- KEYBOARD INTERACTIONS ---
            elif event.type == pygame.KEYDOWN:
                if mode == "menu":
                    entries = ["ENTER THE DUNGEON"] + (["CONTINUE"] if state.get("current") else []) + ["SETTINGS", "STATISTICS", "QUIT"]
                    if event.key in (pygame.K_DOWN, pygame.K_s):
                        menu_selected = (menu_selected + 1) % len(entries)
                        sound_mgr.play("click")
                    elif event.key in (pygame.K_UP, pygame.K_w):
                        menu_selected = (menu_selected - 1) % len(entries)
                        sound_mgr.play("click")
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        action = entries[menu_selected]
                        sound_mgr.play("click")
                        if action == "ENTER THE DUNGEON":
                            game = start()
                            mode = "game"
                            persist()
                        elif action == "CONTINUE":
                            game = restore()
                            mode = "game"
                        elif action == "SETTINGS":
                            previous_mode = "menu"
                            mode = "settings"
                            settings_selected = 0
                        elif action == "STATISTICS":
                            mode = "statistics"
                        else:
                            persist()
                            running = False
                    elif event.key == pygame.K_ESCAPE:
                        running = False
                        persist()

                elif mode == "settings":
                    settings_count = 5
                    if event.key in (pygame.K_DOWN, pygame.K_s):
                        settings_selected = (settings_selected + 1) % settings_count
                        sound_mgr.play("click")
                    elif event.key in (pygame.K_UP, pygame.K_w):
                        settings_selected = (settings_selected - 1) % settings_count
                        sound_mgr.play("click")
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_a, pygame.K_d):
                        sound_mgr.play("click")
                        if settings_selected == 0:
                            toggle_display_mode()
                        elif settings_selected == 2:
                            sound_mgr.enabled = not sound_mgr.enabled
                            state["settings"]["sound"] = sound_mgr.enabled
                            persist()
                        elif settings_selected == 3:
                            state["settings"]["show_hints"] = not state["settings"].get("show_hints", True)
                            persist()
                        elif settings_selected == 4:
                            mode = previous_mode
                    elif event.key == pygame.K_ESCAPE:
                        sound_mgr.play("click")
                        mode = previous_mode

                elif mode == "statistics":
                    if event.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_SPACE):
                        sound_mgr.play("click")
                        mode = "menu"
                        menu_selected = 0

                elif mode == "game":
                    if game.paused:
                        if event.key in (pygame.K_UP, pygame.K_w):
                            game.pause_selected = (game.pause_selected - 1) % len(UI.PAUSE_OPTIONS)
                            sound_mgr.play("click")
                        elif event.key in (pygame.K_DOWN, pygame.K_s):
                            game.pause_selected = (game.pause_selected + 1) % len(UI.PAUSE_OPTIONS)
                            sound_mgr.play("click")
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            sound_mgr.play("click")
                            if game.pause_selected == 0:
                                game.toggle_pause()
                            elif game.pause_selected == 1:
                                game = start()
                                persist()
                            elif game.pause_selected == 2:
                                previous_mode = "game"
                                mode = "settings"
                                settings_selected = 0
                            elif game.pause_selected == 3:
                                persist()
                                game = None
                                mode = "menu"
                                menu_selected = 0
                            else:
                                persist()
                                running = False
                        elif event.key in (pygame.K_ESCAPE, pygame.K_p):
                            game.toggle_pause()
                    elif event.key in (pygame.K_ESCAPE, pygame.K_p):
                        game.toggle_pause()
                    elif event.key == pygame.K_r:
                        game = start()
                        persist()
                    elif event.key == pygame.K_h:
                        game.hint_position = game.request_hint()
                        sound_mgr.play("click")
                    elif event.key == pygame.K_t:
                        game.show_actual_route = not game.show_actual_route
                        sound_mgr.play("click")
                    elif event.key == pygame.K_v:
                        sound_mgr.play("click")
                        if game.result_view:
                            game.show_optimal_route = False
                            game.result_view = False
                            mode = "result"
                        else:
                            game.show_optimal_route = not game.show_optimal_route
                    elif event.key == pygame.K_F5:
                        persist()
                        sound_mgr.play("click")
                    else:
                        moves = {
                            pygame.K_UP: (-1, 0), pygame.K_w: (-1, 0),
                            pygame.K_DOWN: (1, 0), pygame.K_s: (1, 0),
                            pygame.K_LEFT: (0, -1), pygame.K_a: (0, -1),
                            pygame.K_RIGHT: (0, 1), pygame.K_d: (0, 1)
                        }
                        if event.key in moves:
                            handle_game_move(*moves[event.key])
                    if not game.result_view:
                        complete_run()

                elif mode == "result":
                    if event.key == pygame.K_v:
                        sound_mgr.play("click")
                        game.show_optimal_route = True
                        game.result_view = True
                        mode = "game"
                    elif event.key == pygame.K_r:
                        sound_mgr.play("click")
                        game = start()
                        mode = "game"
                        persist()
                    elif event.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_SPACE):
                        sound_mgr.play("click")
                        game = None
                        mode = "menu"
                        menu_selected = 0

        # Autosave during active exploration
        if game and mode == "game":
            if time.monotonic() - last_save > 8:
                persist()
                last_save = time.monotonic()
            if game.expired and not game.result_view:
                complete_run()

        # Rendering
        if mode == "menu":
            ui.menu(menu_selected, bool(state.get("current")), logical_mouse)
        elif mode == "settings":
            ui.settings(state["settings"], settings_selected, logical_mouse)
        elif mode == "statistics":
            ui.statistics(state["history"], state["personal_bests"], logical_mouse)
        elif mode == "game":
            ui.dungeon(game, logical_mouse)
        elif mode == "result":
            ui.results(game, logical_mouse)

        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    run()
