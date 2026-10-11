import pygame
import sys
from player import Player
from enemies import EnemyGrid
from bullets import Bullet
from score import Score

# Initialize Pygame
pygame.init()

# Set up the game window
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Space Invaders")

# Clock for controlling the frame rate
clock = pygame.time.Clock()

# Game variables
player = Player()
enemy_grid = EnemyGrid()
score = Score()
player_bullets = []
enemy_bullets = []

# Game loop
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # Handle player input
    keys = pygame.key.get_pressed()
    if keys[pygame.K_LEFT]:
        player.move_left()
    if keys[pygame.K_RIGHT]:
        player.move_right()
    if keys[pygame.K_SPACE]:
        player.shoot()

    # Update game objects
    player.update()
    enemy_grid.update()
    
    # Check for collisions
    for bullet in player.bullets[:]:
        if bullet.is_off_screen():
            player.bullets.remove(bullet)
        else:
            for enemy in enemy_grid.get_enemies()[:]:
                if bullet.check_collision(enemy.rect):
                    player.bullets.remove(bullet)
                    enemy_grid.remove_enemy(enemy)
                    score.update_score()
                    break

    # Draw everything
    screen.fill((0, 0, 0))
    player.draw(screen)
    enemy_grid.draw(screen)
    score.draw(screen)

    # Update the display
    pygame.display.flip()
    clock.tick(60)

# Quit Pygame
pygame.quit()
sys.exit()
