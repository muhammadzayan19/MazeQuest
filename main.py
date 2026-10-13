
import pygame

pygame.init()

WIDTH = 900
HEIGHT = 600
FPS = 60

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("MazeQuest")

clock = pygame.time.Clock()

BACKGROUND = (18, 24, 38)
WHITE = (240, 244, 248)
GREEN = (31, 211, 114)

title_font = pygame.font.Font(None, 72)
subtitle_font = pygame.font.Font(None, 30)

running = True

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    screen.fill(BACKGROUND)

    title = title_font.render("MAZEQUEST", True, GREEN)
    subtitle = subtitle_font.render(
        "Your adventure begins here", True, WHITE
    )

    screen.blit(
        title,
        title.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 35))
    )

    screen.blit(
        subtitle,
        subtitle.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 30))
    )

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
