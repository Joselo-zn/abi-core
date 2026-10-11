import sys

import pygame

from assets import Assets
from enemies import EnemyFleet
from game_logic import GameLogic
from player import Player

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

WHITE = (255, 255, 255)


def new_game(assets):
    player = Player(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 20,
                    assets.get_asset("player.png"), assets.get_asset("bullet.png"))
    enemy_fleet = EnemyFleet(assets.get_asset("enemy.png"))
    game_logic = GameLogic(player, enemy_fleet, lives=3)
    return player, enemy_fleet, game_logic


def draw_center(screen, font, text, y_offset=0):
    surface = font.render(text, True, WHITE)
    screen.blit(surface, surface.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + y_offset)))


def main(max_frames=None):
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Space Invaders")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 32)
    big_font = pygame.font.Font(None, 64)

    assets = Assets()
    background_image = assets.get_asset("background.png")
    player, enemy_fleet, game_logic = new_game(assets)

    frame = 0
    while max_frames is None or frame < max_frames:
        frame += 1
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                if event.key == pygame.K_r and (game_logic.game_over or game_logic.victory):
                    player, enemy_fleet, game_logic = new_game(assets)

        playing = not (game_logic.game_over or game_logic.victory)

        if playing:
            keys = pygame.key.get_pressed()
            if keys[pygame.K_LEFT]:
                player.move_left()
            if keys[pygame.K_RIGHT]:
                player.move_right()
            if keys[pygame.K_SPACE]:
                player.shoot()

            player.update()
            enemy_fleet.move_fleet()
            enemy_fleet.shoot()
            enemy_fleet.update_bullets()
            game_logic.update_game_state()

        screen.blit(background_image, (0, 0))
        player.draw(screen)
        enemy_fleet.draw(screen)
        screen.blit(font.render(f"Score: {game_logic.score}", True, WHITE), (10, 10))
        screen.blit(font.render(f"Lives: {game_logic.lives}", True, WHITE), (SCREEN_WIDTH - 110, 10))

        if game_logic.victory:
            draw_center(screen, big_font, "VICTORY!")
            draw_center(screen, font, "R to play again - ESC to quit", 50)
        elif game_logic.game_over:
            draw_center(screen, big_font, "GAME OVER")
            draw_center(screen, font, "R to play again - ESC to quit", 50)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    return game_logic


if __name__ == "__main__":
    main()
