"""Hand-drawn top-down catacombs, pixel character, lights and game interfaces."""
from __future__ import annotations
import math, random
import pygame

WIDTH,HEIGHT,FPS=1100,760,60
IW,IH=640,440
INK=(223,218,196); MUTED=(143,149,151); GOLD=(236,182,90); CYAN=(91,208,218)
DARK=(8,11,17)


class UI:
    MENU_BUTTONS=["ENTER THE DUNGEON","CONTINUE","STATISTICS","QUIT"]
    def __init__(self,screen):
        self.screen=screen
        self.canvas=pygame.Surface((IW,IH)).convert()
        self.large=pygame.font.Font(None,52); self.title=pygame.font.Font(None,31)
        self.body=pygame.font.Font(None,21); self.small=pygame.font.Font(None,16); self.tiny=pygame.font.Font(None,13)
        self.tick=0; self.floor_cache={}; self.light_cache={}; self.hero=self._hero()
        self.hero_walk=self._hero(walk=True)
        self.hero_faces={"up":self.hero,"down":pygame.transform.flip(self.hero,False,True),
                         "left":pygame.transform.rotate(self.hero,90),"right":pygame.transform.rotate(self.hero,-90)}
        self.walk_faces={"up":self.hero_walk,"down":pygame.transform.flip(self.hero_walk,False,True),
                         "left":pygame.transform.rotate(self.hero_walk,90),"right":pygame.transform.rotate(self.hero_walk,-90)}
        self.menu_rects=[]; self.result_rects=[]
        self.hint_rect=pygame.Rect(530,IH-25,50,18); self.pause_rect=pygame.Rect(585,5,42,31)

    def text(self,value,pos,font=None,color=INK,shadow=True):
        font=font or self.body; x,y=map(int,pos); s=font.render(str(value),False,color)
        if shadow:self.canvas.blit(font.render(str(value),False,(3,5,9)),(x+1,y+2))
        self.canvas.blit(s,(x,y))

    def present(self):
        scaled=pygame.transform.scale(self.canvas,self.screen.get_size())
        self.screen.blit(scaled,(0,0)); self.tick+=1

    @staticmethod
    def _hero(walk=False):
        s=pygame.Surface((16,22),pygame.SRCALPHA)
        pygame.draw.ellipse(s,(4,5,8,130),(2,18,13,4))
        pygame.draw.rect(s,(42,29,28),(3,5,10,12)) # dark outline / cloak
        pygame.draw.polygon(s,(45,49,59),[(3,8),(5,3),(11,3),(13,8),(11,10),(4,10)])
        pygame.draw.rect(s,(181,137,100),(6,5,5,6))
        pygame.draw.rect(s,(24,24,29),(5,2,7,4)); pygame.draw.rect(s,(53,65,72),(6,3,5,2))
        pygame.draw.rect(s,(111,67,43),(4,10,8,7)); pygame.draw.rect(s,(68,99,100),(5,10,6,5))
        pygame.draw.rect(s,(203,156,80),(5,11,2,3))
        step=1 if walk else 0
        pygame.draw.rect(s,(53,42,35),(4,16,4,4+step)); pygame.draw.rect(s,(53,42,35),(9,16,4,4-step))
        pygame.draw.rect(s,(22,20,21),(3,19+step,5,2)); pygame.draw.rect(s,(22,20,21),(9,19-step,5,2))
        pygame.draw.line(s,(126,88,55),(13,10),(15,15),1)
        s.set_at((8,7),(25,23,28))
        return s

    def _tile_floor(self,r,c):
        key=(r,c); tile=self.floor_cache.get(key)
        if tile is None:
            tile=pygame.Surface((18,16)); rng=random.Random(r*1181+c*517+77)
            base=[(48,51,52),(53,56,53),(48,55,53),(57,55,49),(48,54,58)][rng.randrange(5)]
            tile.fill(base)
            pygame.draw.rect(tile,(35,39,40),(0,0,18,1)); pygame.draw.line(tile,(73,69,59),(1,14),(16,14))
            # Chipped corner edges and restrained moss in worn floor joints.
            pygame.draw.line(tile,(39,43,41),(0,0),(0,15)); pygame.draw.line(tile,(68,67,58),(17,1),(17,15))
            for _ in range(2):
                x,y=rng.randrange(2,16),rng.randrange(2,14)
                pygame.draw.line(tile,(35,39,39),(x,y),(x+rng.choice((-2,-1,1,2)),y+1))
            if rng.random()<.2:
                x,y=rng.randrange(2,15),rng.randrange(3,13)
                pygame.draw.line(tile,(63,75,53),(x,y),(x+2,y-1))
            if rng.random()<.07:
                pygame.draw.line(tile,(99,83,57),(5,5),(12,5)); pygame.draw.line(tile,(99,83,57),(5,5),(5,10))
            self.floor_cache[key]=tile
        return tile

    def _glow(self,color,radius):
        key=(color,radius); surf=self.light_cache.get(key)
        if surf is None:
            surf=pygame.Surface((radius*2,radius*2),pygame.SRCALPHA)
            for n in range(8,0,-1):
                rad=radius*n//8; alpha=12+(9-n)*7
                light=tuple(channel*alpha//255 for channel in color)
                pygame.draw.ellipse(surf,(*light,alpha),(radius-rad,radius-rad,rad*2,rad*2))
            self.light_cache[key]=surf
        return surf

    def _torch(self,x,y,phase):
        flick=(self.tick//7+phase)%3
        pygame.draw.ellipse(self.canvas,(25,20,18),(x-5,y+5,11,5))
        pygame.draw.rect(self.canvas,(97,60,40),(x-1,y-7,3,13))
        pygame.draw.polygon(self.canvas,(244,99,38),[(x-4,y-5),(x-1,y-13-flick),(x+3,y-9),(x+4,y-4)])
        pygame.draw.polygon(self.canvas,(255,217,126),[(x-1,y-5),(x,y-10-flick),(x+2,y-5)])

    def _wall(self,x,y,r,c):
        shade=(r*7+c*11)%4
        tops=((92,87,75),(84,88,87),(95,89,75),(82,86,81))
        top=tops[shade]
        # Rear wall shadow and a raised, irregular cap over two shaded faces.
        pygame.draw.polygon(self.canvas,(19,22,24),[(x+1,y+2),(x+17,y+2),(x+17,y+13),(x+1,y+13)])
        pygame.draw.polygon(self.canvas,(35,39,43),[(x,y-7),(x+18,y-7),(x+18,y+6),(x+14,y+9),(x,y+8)])
        pygame.draw.polygon(self.canvas,(54,57,57),[(x,y-7),(x+8,y-9),(x+18,y-7),(x+18,y+4),(x+10,y+5),(x,y+3)])
        pygame.draw.line(self.canvas,(135,123,101),(x+1,y-6),(x+8,y-8))
        pygame.draw.line(self.canvas,(117,112,96),(x+8,y-8),(x+17,y-6))
        # Cut joints, chips, and directional highlights on each block.
        pygame.draw.line(self.canvas,(30,34,36),(x+1,y-1),(x+7,y))
        pygame.draw.line(self.canvas,(33,36,37),(x+11,y+1),(x+17,y))
        pygame.draw.line(self.canvas,(67,67,61),(x+4,y+4),(x+9,y+5))
        if (r+c)%5==0: pygame.draw.line(self.canvas,(115,108,87),(x+3,y-5),(x+5,y-3))
        pygame.draw.line(self.canvas,top,(x+3,y-5),(x+7,y-6))

    def _draw_gate(self,x,y,open_gate=False):
        pygame.draw.rect(self.canvas,(25,22,22),(x+1,y-5,16,21))
        pygame.draw.rect(self.canvas,(112,78,47),(x+2,y-4,14,18))
        pygame.draw.rect(self.canvas,(44,35,31),(x+4,y-2,10,15))
        for gx in (6,10,14): pygame.draw.line(self.canvas,(158,119,66),(x+gx,y-1),(x+gx,y+11),1)
        pygame.draw.line(self.canvas,GOLD,(x+4,y+2),(x+14,y+2),1)
        if open_gate:
            pygame.draw.line(self.canvas,(61,192,178),(x+4,y+5),(x+13,y+5),2)

    def _draw_crystal(self,x,y,phase):
        bob=int(math.sin(self.tick/8+phase)*1)
        pygame.draw.polygon(self.canvas,(52,140,194),[(x,y-9+bob),(x+5,y-3+bob),(x+3,y+5+bob),(x,y+8+bob),(x-4,y+3+bob),(x-4,y-4+bob)])
        pygame.draw.polygon(self.canvas,(139,233,246),[(x,y-7+bob),(x+2,y-2+bob),(x,y+4+bob),(x-1,y+1+bob)])

    def _draw_chest(self,x,y,opened=False):
        pygame.draw.ellipse(self.canvas,(24,20,17),(x-8,y+4,16,6))
        pygame.draw.rect(self.canvas,(105,60,34),(x-7,y-3,14,10))
        pygame.draw.rect(self.canvas,(177,119,57),(x-7,y-4,14,3))
        pygame.draw.line(self.canvas,(226,177,82),(x-1,y-3),(x-1,y+6),2)
        pygame.draw.rect(self.canvas,(75,46,29),(x-7,y+3,14,2))
        if opened: pygame.draw.rect(self.canvas,(239,189,83),(x-4,y-2,8,3))

    def dungeon(self,game):
        self.canvas.fill((10,14,20))
        maze=game.maze; tw,th=18,16
        ox=(IW-maze.cols*tw)//2; oy=49+(328-maze.rows*th)//2
        # Rocky cave vignette and sparse masonry beyond playable bounds.
        for y in range(42,IH-43,12):
            pygame.draw.line(self.canvas,(20,25,29),(0,y),(IW,y))
        for r in range(maze.rows):
            for c in range(maze.cols):
                x,y=ox+c*tw,oy+r*th
                if maze.grid[r][c]=='#':
                    pygame.draw.rect(self.canvas,(21,25,28),(x,y,tw,th))
                else:
                    self.canvas.blit(self._tile_floor(r,c),(x,y))
        # Warm torch pools and cool crystal light are cached pixel surfaces.
        for r,c in maze.torches:
            x,y=ox+c*tw+9,oy+r*th+7
            self.canvas.blit(self._glow((245,111,42),25),(x-25,y-25),special_flags=pygame.BLEND_RGBA_ADD)
        for r,c in maze.crystals:
            x,y=ox+c*tw+9,oy+r*th+6
            self.canvas.blit(self._glow((42,142,197),22),(x-22,y-22),special_flags=pygame.BLEND_RGBA_ADD)
        # Depth ordering: each row's raised blocks and props occlude those behind.
        player=game.animated_position
        player_drawn=False
        for r in range(maze.rows):
            for c in range(maze.cols):
                x,y=ox+c*tw,oy+r*th; p=(r,c); code=maze.grid[r][c]
                if p in maze.torches:self._torch(x+9,y+7,r+c)
                if p in maze.runes:
                    pygame.draw.circle(self.canvas,(56,136,145),(x+9,y+8),5,1)
                    pygame.draw.line(self.canvas,(58,172,179),(x+9,y+4),(x+9,y+12),1)
                    pygame.draw.line(self.canvas,(58,172,179),(x+5,y+8),(x+13,y+8),1)
                if p in maze.crystals:self._draw_crystal(x+9,y+6,r+c)
                if p in maze.treasures and p not in game.collected_treasures:
                    self._draw_chest(x+9,y+7,False)
                if p in maze.doors:self._draw_gate(x,y,maze.doors[p] in game.keys)
                if p==maze.goal:
                    self.canvas.blit(self._glow((229,174,79),17),(x-8,y-10),special_flags=pygame.BLEND_RGBA_ADD)
                    self._draw_gate(x,y, bool(game.keys))
                    self.text("EXIT",(x+2,y-17),self.tiny,GOLD)
                if p==maze.entrance:
                    pygame.draw.rect(self.canvas,(107,81,54),(x+3,y+4,12,9))
                    pygame.draw.rect(self.canvas,(34,31,29),(x+5,y+5,8,7))
                if p==game.hint_position:
                    self.canvas.blit(self._glow((75,209,219),15),(x-6,y-6),special_flags=pygame.BLEND_RGBA_ADD)
                    pygame.draw.rect(self.canvas,CYAN,(x+5,y+4,8,8),1)
                # Draw hero at row depth, after world objects at that tile.
                if int(player[0])==r and int(player[1])==c:
                    phase=int(time_value()*9)%2
                    shadow=(x+9,y+13)
                    pygame.draw.ellipse(self.canvas,(17,19,20), (shadow[0]-7,shadow[1]-2,14,5))
                    dr,dc=game.facing
                    direction="up" if dr<0 else "down" if dr>0 else "left" if dc<0 else "right"
                    sprite=(self.walk_faces if phase else self.hero_faces)[direction]
                    self.canvas.blit(sprite,(x+(18-sprite.get_width())//2,y-5))
                    player_drawn=True
                if code=='#':self._wall(x,y,r,c)
        # Slow, sparse ember motes drift through the air without obscuring tiles.
        for i in range(8):
            px=(73*i+(self.tick//3)*(1 if i%2 else -1))%IW
            py=54+(47*i-self.tick//5)%(IH-105)
            if (i+self.tick//12)%3:
                self.canvas.set_at((px,py),(92,66,39))
        if not player_drawn:
            x,y=ox+int(player[1])*tw,oy+int(player[0])*th
            pygame.draw.ellipse(self.canvas,(17,19,20),(x+2,y+11,14,5)); self.canvas.blit(self.hero,(x+1,y-5))
        if game.show_optimal_route or game.show_actual_route:
            route=game.stats.optimal_route if game.show_optimal_route else game.stats.actual_route
            if game.show_optimal_route:
                count=min(len(route),max(1,(self.tick%100)*len(route)//100))
                route=route[:count]
            col=(70,214,223) if game.show_optimal_route else (210,130,204)
            for r,c in route:
                pygame.draw.rect(self.canvas,(*col,110),(ox+c*tw+6,oy+r*th+5,6,6))
        # Header/footer UI bands.
        pygame.draw.rect(self.canvas,(12,16,22),(0,0,IW,43)); pygame.draw.line(self.canvas,(111,86,54),(0,42),(IW,42))
        self.text("THE FORGOTTEN CATACOMBS",(14,8),self.small,GOLD)
        self.text(f"TIME  {int(game.elapsed//60):02d}:{int(game.elapsed%60):02d}",(337,8),self.small)
        self.text(f"MOVES  {game.stats.moves:03d}",(510,8),self.small)
        pygame.draw.rect(self.canvas,(12,16,22),(0,IH-43,IW,43)); pygame.draw.line(self.canvas,(111,86,54),(0,IH-43),(IW,IH-43))
        self._key_icon(17,IH-30,bool(game.keys))
        self.text("KEY FOUND" if game.keys else "KEY: MISSING",(34,IH-36),self.tiny,GOLD if game.keys else MUTED)
        self._coin_icon(180,IH-29)
        self.text(f"RELICS {game.stats.treasures}/2",(197,IH-36),self.tiny)
        msg=game.current_message
        self.text(msg,(316,IH-36),self.tiny,CYAN if "key" in msg.lower() or "gate" in msg.lower() else INK)
        self.text("P / ESC PAUSE    H HINT    T ROUTE",(14,IH-16),self.tiny,MUTED)
        pygame.draw.rect(self.canvas,(76,66,49),self.hint_rect,1)
        self.text("HINT",(539,IH-23),self.tiny,GOLD)
        pygame.draw.rect(self.canvas,(76,66,49),self.pause_rect,1)
        self.text("Ⅱ",(599,11),self.body,GOLD)
        if game.paused:self.panel("EXPEDITION PAUSED",["RESUME","RESTART LEVEL","SAVE & MENU","QUIT"],game.pause_selected)
        self.present()

    def _key_icon(self,x,y,found):
        color=GOLD if found else (105,91,68)
        pygame.draw.circle(self.canvas,color,(x+5,y+5),4,2); pygame.draw.line(self.canvas,color,(x+9,y+5),(x+17,y+5),2)
        pygame.draw.line(self.canvas,color,(x+14,y+5),(x+14,y+8),2)
    def _coin_icon(self,x,y):
        pygame.draw.circle(self.canvas,GOLD,(x+6,y+5),5,1); pygame.draw.line(self.canvas,(255,224,139),(x+6,y+2),(x+6,y+8),1)

    def panel(self,title,options,selected=0):
        pygame.draw.rect(self.canvas,(7,10,16),(166,107,308,230))
        pygame.draw.rect(self.canvas,(160,117,64),(166,107,308,230),2)
        pygame.draw.rect(self.canvas,(69,73,69),(172,113,296,218),1)
        self.text(title,(188,127),self.title,GOLD)
        for i,item in enumerate(options):
            y=174+i*32; active=i==selected
            pygame.draw.rect(self.canvas,(40,39,34) if active else (16,20,25),(190,y-3,258,26))
            pygame.draw.rect(self.canvas,(163,119,62) if active else (49,53,53),(190,y-3,258,26),1)
            self.text(("› " if active else "  ")+item,(202,y+2),self.small,GOLD if active else INK)

    def _frame(self,title,sub=""):
        self.canvas.fill((10,13,19))
        for y in range(0,IH,16):
            for x in range((y//16%2)*18,IW,36):
                pygame.draw.rect(self.canvas,(22,27,30),(x,y,35,15))
                pygame.draw.line(self.canvas,(38,40,39),(x+2,y+2),(x+8,y+2))
        pygame.draw.rect(self.canvas,(12,15,20),(66,38,508,363))
        pygame.draw.rect(self.canvas,(145,106,60),(66,38,508,363),2)
        pygame.draw.rect(self.canvas,(53,60,59),(72,44,496,351),1)
        self.text(title,(92,59),self.title,GOLD)
        if sub:self.text(sub,(94,94),self.small,MUTED)

    def menu(self,selected=0,can_continue=False,mouse=None):
        self.canvas.fill((7,10,16))
        # Recessed crypt arch, torch brackets, and flagstones make a scene behind UI.
        pygame.draw.rect(self.canvas,(24,29,32),(0,185,IW,255))
        pygame.draw.polygon(self.canvas,(39,43,43),[(106,250),(106,170),(143,112),(210,84),(430,84),(495,112),(534,170),(534,250)])
        pygame.draw.polygon(self.canvas,(12,15,20),[(145,250),(145,174),(177,128),(224,108),(416,108),(463,128),(495,174),(495,250)])
        for x in range(0,IW,36):
            pygame.draw.line(self.canvas,(43,45,42),(x,260),(x,IH))
        for y in range(261,IH,20):pygame.draw.line(self.canvas,(38,42,41),(0,y),(IW,y))
        for x,y in ((142,171),(497,171),(270,132),(370,132)):
            self._torch(x,y,x//11)
        self.text("MAZEQUEST",(56,42),self.large,(231,197,133))
        self.text("THE FORGOTTEN CATACOMBS",(60,94),self.small,CYAN)
        labels=self.MENU_BUTTONS[:]
        if not can_continue:labels.remove("CONTINUE")
        self.menu_rects=[]
        for i,label in enumerate(labels):
            rect=pygame.Rect(60,139+i*39,236,32); self.menu_rects.append((label,rect))
            hover=rect.collidepoint(mouse) if mouse else False
            active=i==selected or hover
            pygame.draw.rect(self.canvas,(38,39,35) if active else (17,21,25),rect)
            pygame.draw.rect(self.canvas,(194,145,74) if active else (77,76,66),rect,1)
            pygame.draw.line(self.canvas,(121,94,59),(rect.x+4,rect.y+3),(rect.right-4,rect.y+3))
            self.text(("› " if active else "  ")+label,(rect.x+12,rect.y+7),self.small,GOLD if active else INK)
        self.text("WASD / ARROWS   •   ENTER TO DESCEND",(60,329),self.tiny,MUTED)
        self.present()

    def menu_hit(self,pos):
        return next((label for label,rect in self.menu_rects if rect.collidepoint(pos)),None)

    def game_hit(self,pos):
        if self.hint_rect.collidepoint(pos):return "HINT"
        if self.pause_rect.collidepoint(pos):return "PAUSE"
        return None

    def statistics(self,history,bests):
        self._frame("CATACOMB CHRONICLE",f"Completed expeditions: {len(history)}")
        best=bests.get("1")
        rows=(f"The Forgotten Catacombs",f"BEST TIME   {best['time']:.1f}s" if best else "BEST TIME   —",
              f"BEST MOVES  {best['moves']}" if best else "BEST MOVES  —",
              f"TREASURE RUNS   {sum(1 for run in history if run.get('treasures',0)>0)}")
        for i,row in enumerate(rows):self.text(row,(110,145+i*38),self.body,GOLD if i==0 else INK)
        self.text("ENTER / ESC TO RETURN",(110,330),self.small,MUTED); self.present()

    def results(self,game):
        self._frame("RELIC RECOVERED" if game.won else "THE DUNGEON CLAIMS YOU","The Forgotten Catacombs")
        s=game.stats
        vals=(f"EXPEDITION TIME       {game.elapsed:6.1f} seconds",
              f"SUCCESSFUL MOVES      {s.moves}",f"SHORTEST BFS ROUTE     {s.optimal_moves}",
              f"DETOUR                 {max(0,s.moves-s.optimal_moves)} moves",
              f"INVALID STEPS          {s.invalid_moves}",f"TREASURE               {s.treasures}/2")
        for i,row in enumerate(vals):self.text(row,(98,125+i*31),self.body,CYAN if "BFS" in row else INK)
        pygame.draw.rect(self.canvas,(77,52,94),(98,323,min(210,s.moves*3),7))
        pygame.draw.rect(self.canvas,(39,128,143),(98,334,min(210,s.optimal_moves*3),7))
        self.result_rects=[]
        actions=(("VIEW OPTIMAL PATH",94),("PLAY AGAIN",273),("RETURN TO MENU",416))
        for label,x in actions:
            rect=pygame.Rect(x,358,148 if x!=416 else 128,25)
            self.result_rects.append((label,rect))
            pygame.draw.rect(self.canvas,(42,38,30),(rect.x,rect.y,rect.w,rect.h))
            pygame.draw.rect(self.canvas,(154,116,64),rect,1)
            self.text(label,(rect.x+7,rect.y+7),self.tiny,GOLD)
        self.present()

    def result_hit(self,pos):
        return next((label for label,rect in self.result_rects if rect.collidepoint(pos)),None)


def time_value():
    return pygame.time.get_ticks()/1000
