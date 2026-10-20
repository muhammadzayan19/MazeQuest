"""MazeQuest application loop for the single handcrafted catacomb adventure."""
from __future__ import annotations
import time
import pygame
from maze import LEVELS,Maze
from game_logic import Game
from save_data import default_config_path,load_state,save_state
from ui import UI,WIDTH,HEIGHT,FPS,IW,IH


def run():
    pygame.init()
    screen=pygame.display.set_mode((WIDTH,HEIGHT))
    pygame.display.set_caption("MazeQuest — The Forgotten Catacombs")
    ui,clock=UI(screen),pygame.time.Clock()
    path=default_config_path(); state=load_state(path)
    mode="menu"; game=None; selected=0; running=True; last_save=time.monotonic()

    def start():return Game(Maze.handcrafted(),1,LEVELS[0].time_limit)
    def persist():
        if game is not None and not (game.won or game.expired):state["current"]=game.snapshot()
        save_state(path,state)
    def restore():
        current=state.get("current")
        if not current:return start()
        return Game.from_snapshot(Maze.handcrafted(),current,LEVELS[0].time_limit)
    def complete_run():
        nonlocal mode
        if mode!="game" or not (game.won or game.expired):return
        entry=game.snapshot(); state["history"].append(entry); state["current"]=None
        if game.won:
            old=state["personal_bests"].get("1")
            state["personal_bests"]["1"]={
                "time":min(round(game.elapsed,2),old.get("time",float("inf"))) if old else round(game.elapsed,2),
                "moves":min(game.stats.moves,old.get("moves",10**9)) if old else game.stats.moves}
        save_state(path,state); mode="result"

    while running:
        mouse=pygame.mouse.get_pos()
        logical_mouse=(mouse[0]*IW/screen.get_width(),mouse[1]*IH/screen.get_height())
        for event in pygame.event.get():
            if event.type==pygame.QUIT:
                persist(); running=False
            elif mode=="game" and event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
                action=ui.game_hit((event.pos[0]*IW/screen.get_width(),event.pos[1]*IH/screen.get_height()))
                if action=="HINT":game.hint_position=game.request_hint()
                elif action=="PAUSE" and not game.paused:game.toggle_pause()
            elif mode=="result" and event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
                action=ui.result_hit((event.pos[0]*IW/screen.get_width(),event.pos[1]*IH/screen.get_height()))
                if action=="VIEW OPTIMAL PATH":game.show_optimal_route=True;game.result_view=True;mode="game"
                elif action=="PLAY AGAIN":game=start();mode="game";persist()
                elif action=="RETURN TO MENU":game=None;mode="menu";selected=0
            elif mode=="menu" and event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
                label=ui.menu_hit((event.pos[0]*IW/screen.get_width(),event.pos[1]*IH/screen.get_height()))
                if label=="ENTER THE DUNGEON":game=start(); mode="game"; persist()
                elif label=="CONTINUE":game=restore(); mode="game"
                elif label=="STATISTICS":mode="statistics"
                elif label=="QUIT":persist(); running=False
            elif event.type==pygame.KEYDOWN:
                if mode=="menu":
                    entries=["ENTER THE DUNGEON"]+(["CONTINUE"] if state.get("current") else [])+["STATISTICS","QUIT"]
                    if event.key in (pygame.K_DOWN,pygame.K_s):selected=(selected+1)%len(entries)
                    elif event.key in (pygame.K_UP,pygame.K_w):selected=(selected-1)%len(entries)
                    elif event.key in (pygame.K_RETURN,pygame.K_SPACE):
                        action=entries[selected]
                        if action=="ENTER THE DUNGEON":game=start(); mode="game"; persist()
                        elif action=="CONTINUE":game=restore(); mode="game"
                        elif action=="STATISTICS":mode="statistics"
                        else:persist(); running=False
                    elif event.key==pygame.K_ESCAPE:running=False; persist()
                elif mode=="statistics":
                    if event.key in (pygame.K_RETURN,pygame.K_ESCAPE):mode="menu"; selected=0
                elif mode=="game":
                    if game.paused:
                        if event.key in (pygame.K_UP,pygame.K_w):game.pause_selected=(game.pause_selected-1)%4
                        elif event.key in (pygame.K_DOWN,pygame.K_s):game.pause_selected=(game.pause_selected+1)%4
                        elif event.key in (pygame.K_RETURN,pygame.K_SPACE):
                            if game.pause_selected==0:game.toggle_pause()
                            elif game.pause_selected==1:game=start();persist()
                            elif game.pause_selected==2:persist();game=None;mode="menu";selected=0
                            else:persist();running=False
                        elif event.key in (pygame.K_ESCAPE,pygame.K_p):game.toggle_pause()
                    elif event.key in (pygame.K_ESCAPE,pygame.K_p):game.toggle_pause()
                    elif event.key==pygame.K_r:game=start();persist()
                    elif event.key==pygame.K_h:
                        game.hint_position=game.request_hint()
                    elif event.key==pygame.K_t:game.show_actual_route=not game.show_actual_route
                    elif event.key==pygame.K_v:
                        if game.result_view:
                            game.show_optimal_route=False;game.result_view=False;mode="result"
                        else:game.show_optimal_route=not game.show_optimal_route
                    elif event.key==pygame.K_F5:persist()
                    else:
                        moves={pygame.K_UP:(-1,0),pygame.K_w:(-1,0),pygame.K_DOWN:(1,0),pygame.K_s:(1,0),
                               pygame.K_LEFT:(0,-1),pygame.K_a:(0,-1),pygame.K_RIGHT:(0,1),pygame.K_d:(0,1)}
                        if event.key in moves:
                            game.move(*moves[event.key]);persist();last_save=time.monotonic()
                    if not game.result_view:complete_run()
                elif mode=="result":
                    if event.key==pygame.K_v:game.show_optimal_route=True;game.result_view=True;mode="game"
                    elif event.key==pygame.K_r:game=start();mode="game";persist()
                    elif event.key in (pygame.K_RETURN,pygame.K_ESCAPE):mode="menu";selected=0
        if game and mode=="game":
            if time.monotonic()-last_save>8:persist();last_save=time.monotonic()
            if game.expired and not game.result_view:complete_run()
        if mode=="menu":
            ui.menu(selected,bool(state.get("current")),logical_mouse)
        elif mode=="statistics":ui.statistics(state["history"],state["personal_bests"])
        elif mode=="game":ui.dungeon(game)
        else:ui.results(game)
        pygame.display.flip();clock.tick(FPS)
    pygame.quit()


if __name__=="__main__":run()
