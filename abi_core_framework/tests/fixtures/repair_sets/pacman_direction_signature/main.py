"""
main.py
Main entry point and game loop driver for Pac-Man.
Manages game initialization, state machine (Menu, Playing, Paused, Game Over, Victory),
event handling, collision detection, score and life systems, and rendering.
"""

import math
import os
import sys
import pygame
from entities import Pellet, Maze, PacMan, Ghost

# Game States
STATE_MENU = 0
STATE_PLAYING = 1
STATE_PAUSED = 2
STATE_GAME_OVER = 3
STATE_VICTORY = 4

# UI Configuration
HUD_HEIGHT = 60
CELL_SIZE = 28
FPS = 60

# Colors
COLOR_BLACK = (0, 0, 0)
COLOR_WHITE = (255, 255, 255)
COLOR_YELLOW = (255, 255, 0)
COLOR_RED = (255, 0, 0)
COLOR_BLUE = (33, 33, 222)
COLOR_CYAN = (0, 255, 255)
COLOR_GREEN = (0, 255, 0)


def create_ghosts(maze, cell_size):
    """Instantiates the 4 ghosts with specific movement patterns and colors."""
    starts = maze.ghost_starts
    g_coords = []
    for i in range(4):
        g_coords.append(starts[i % len(starts)])

    ghost_configs = [
        ("Blinky", (255, 0, 0), "chase"),
        ("Pinky", (255, 182, 193), "ambush"),
        ("Inky", (0, 255, 255), "patrol"),
        ("Clyde", (255, 165, 0), "random")
    ]

    ghosts = []
    for i, (name, color, pattern) in enumerate(ghost_configs):
        sx, sy = g_coords[i]
        ghosts.append(Ghost(name, color, sx, sy, pattern=pattern, cell_size=cell_size))
    return ghosts


class Game:
    """Core game manager handling loop execution, user input, updates, and rendering."""
    def __init__(self):
        pygame.init()
        pygame.font.init()

        self.maze = Maze(cell_size=CELL_SIZE)
        self.screen_width = self.maze.width
        self.screen_height = self.maze.height + HUD_HEIGHT

        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("Pac-Man Classic")

        self.clock = pygame.time.Clock()

        # Surface dedicated to rendering the maze grid
        self.game_surface = pygame.Surface((self.maze.width, self.maze.height))

        # Fonts using Pygame default font (cross-platform fallback)
        self.font_large = pygame.font.Font(None, 42)
        self.font_medium = pygame.font.Font(None, 28)
        self.font_small = pygame.font.Font(None, 22)

        self.state = STATE_MENU
        self.high_score = 0
        self.ghost_combo = 200

        self.pacman = None
        self.ghosts = []

        self.reset_game()

    def reset_game(self):
        """Resets maze, PacMan, and ghosts for a new game session."""
        self.maze = Maze(cell_size=CELL_SIZE)
        self.pacman = PacMan(self.maze.pacman_start[0], self.maze.pacman_start[1], cell_size=CELL_SIZE)
        self.ghosts = create_ghosts(self.maze, CELL_SIZE)
        self.ghost_combo = 200

    def handle_events(self):
        """Processes keyboard and system events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            elif event.type == pygame.KEYDOWN:
                if self.state == STATE_MENU:
                    if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                        self.reset_game()
                        self.state = STATE_PLAYING

                elif self.state == STATE_PLAYING:
                    if event.key in (pygame.K_UP, pygame.K_w):
                        self.pacman.set_direction(0, -1)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        self.pacman.set_direction(0, 1)
                    elif event.key in (pygame.K_LEFT, pygame.K_a):
                        self.pacman.set_direction(-1, 0)
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        self.pacman.set_direction(1, 0)
                    elif event.key in (pygame.K_p, pygame.K_ESCAPE):
                        self.state = STATE_PAUSED

                elif self.state == STATE_PAUSED:
                    if event.key in (pygame.K_p, pygame.K_ESCAPE, pygame.K_SPACE):
                        self.state = STATE_PLAYING
                    elif event.key == pygame.K_m:
                        self.state = STATE_MENU

                elif self.state in (STATE_GAME_OVER, STATE_VICTORY):
                    if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                        self.reset_game()
                        self.state = STATE_PLAYING
                    elif event.key == pygame.K_m:
                        self.state = STATE_MENU

    def update(self):
        """Updates entity positions and resolves game logic and collisions."""
        if self.state != STATE_PLAYING:
            return

        # Update PacMan position
        self.pacman.update(self.maze)

        # Handle pellet consumption
        points_earned, power_eaten = self.pacman.eat_pellets(self.maze)
        if power_eaten:
            self.ghost_combo = 200
            for ghost in self.ghosts:
                ghost.set_frightened(300)

        # Update High Score
        if self.pacman.score > self.high_score:
            self.high_score = self.pacman.score

        # Check level completion
        if len(self.maze.pellets) == 0:
            self.state = STATE_VICTORY
            return

        # Update Ghosts & check collisions
        for ghost in self.ghosts:
            ghost.update(self.maze, self.pacman)

            # Distance-based collision detection
            dist = math.hypot(self.pacman.x - ghost.x, self.pacman.y - ghost.y)
            if dist < CELL_SIZE * 0.7:
                if ghost.frightened:
                    # Eat frightened ghost
                    self.pacman.score += self.ghost_combo
                    self.ghost_combo = min(self.ghost_combo * 2, 1600)
                    ghost.reset_position()
                else:
                    # PacMan caught by ghost
                    self.pacman.lives -= 1
                    pygame.time.delay(500)  # Brief pause on hit
                    if self.pacman.lives <= 0:
                        self.state = STATE_GAME_OVER
                    else:
                        self.pacman.reset_position()
                        for g in self.ghosts:
                            g.reset_position()

    def draw_hud(self):
        """Renders header HUD containing score, high score, and remaining lives."""
        hud_rect = pygame.Rect(0, 0, self.screen_width, HUD_HEIGHT)
        pygame.draw.rect(self.screen, COLOR_BLACK, hud_rect)
        pygame.draw.line(self.screen, COLOR_BLUE, (0, HUD_HEIGHT - 2), (self.screen_width, HUD_HEIGHT - 2), 2)

        # Draw Score
        score_text = self.font_medium.render(f"SCORE: {self.pacman.score}", True, COLOR_WHITE)
        self.screen.blit(score_text, (15, 18))

        # Draw High Score
        high_text = self.font_medium.render(f"HIGH: {self.high_score}", True, COLOR_YELLOW)
        self.screen.blit(high_text, (self.screen_width // 2 - high_text.get_width() // 2, 18))

        # Draw Lives (as mini PacMan icons)
        lives_label = self.font_small.render("LIVES:", True, COLOR_WHITE)
        lives_x = self.screen_width - 120
        self.screen.blit(lives_label, (lives_x, 22))

        for i in range(self.pacman.lives):
            lx = lives_x + 65 + i * 18
            ly = 30
            pygame.draw.circle(self.screen, COLOR_YELLOW, (lx, ly), 7)

    def draw_menu(self):
        """Renders title screen with controls and start instructions."""
        self.screen.fill(COLOR_BLACK)

        title = self.font_large.render("PAC-MAN", True, COLOR_YELLOW)
        self.screen.blit(title, (self.screen_width // 2 - title.get_width() // 2, 100))

        sub = self.font_medium.render("Press SPACE to Start Game", True, COLOR_WHITE)
        self.screen.blit(sub, (self.screen_width // 2 - sub.get_width() // 2, 220))

        controls_title = self.font_medium.render("CONTROLS:", True, COLOR_CYAN)
        self.screen.blit(controls_title, (self.screen_width // 2 - controls_title.get_width() // 2, 320))

        ctrl1 = self.font_small.render("Arrow Keys / WASD : Move", True, COLOR_WHITE)
        ctrl2 = self.font_small.render("P / ESC : Pause Game", True, COLOR_WHITE)
        ctrl3 = self.font_small.render("M : Main Menu", True, COLOR_WHITE)

        self.screen.blit(ctrl1, (self.screen_width // 2 - ctrl1.get_width() // 2, 360))
        self.screen.blit(ctrl2, (self.screen_width // 2 - ctrl2.get_width() // 2, 390))
        self.screen.blit(ctrl3, (self.screen_width // 2 - ctrl3.get_width() // 2, 420))

    def draw_pause_overlay(self):
        """Renders semi-transparent pause overlay."""
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        txt = self.font_large.render("PAUSED", True, COLOR_YELLOW)
        sub = self.font_medium.render("Press P to Resume | M for Menu", True, COLOR_WHITE)

        self.screen.blit(txt, (self.screen_width // 2 - txt.get_width() // 2, self.screen_height // 2 - 40))
        self.screen.blit(sub, (self.screen_width // 2 - sub.get_width() // 2, self.screen_height // 2 + 10))

    def draw_game_over(self):
        """Renders Game Over overlay."""
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        self.screen.blit(overlay, (0, 0))

        txt = self.font_large.render("GAME OVER", True, COLOR_RED)
        score_txt = self.font_medium.render(f"Final Score: {self.pacman.score}", True, COLOR_WHITE)
        restart_txt = self.font_small.render("Press SPACE to Restart | M for Menu", True, COLOR_YELLOW)

        self.screen.blit(txt, (self.screen_width // 2 - txt.get_width() // 2, self.screen_height // 2 - 60))
        self.screen.blit(score_txt, (self.screen_width // 2 - score_txt.get_width() // 2, self.screen_height // 2 - 10))
        self.screen.blit(restart_txt, (self.screen_width // 2 - restart_txt.get_width() // 2, self.screen_height // 2 + 40))

    def draw_victory(self):
        """Renders Victory overlay on level completion."""
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        self.screen.blit(overlay, (0, 0))

        txt = self.font_large.render("YOU WIN!", True, COLOR_GREEN)
        score_txt = self.font_medium.render(f"Final Score: {self.pacman.score}", True, COLOR_WHITE)
        restart_txt = self.font_small.render("Press SPACE to Play Again | M for Menu", True, COLOR_YELLOW)

        self.screen.blit(txt, (self.screen_width // 2 - txt.get_width() // 2, self.screen_height // 2 - 60))
        self.screen.blit(score_txt, (self.screen_width // 2 - score_txt.get_width() // 2, self.screen_height // 2 - 10))
        self.screen.blit(restart_txt, (self.screen_width // 2 - restart_txt.get_width() // 2, self.screen_height // 2 + 40))

    def render(self):
        """Renders all game components depending on current state."""
        if self.state == STATE_MENU:
            self.draw_menu()
        else:
            # Render HUD at top
            self.draw_hud()

            # Render Game World
            self.game_surface.fill(COLOR_BLACK)
            self.maze.draw(self.game_surface)
            self.pacman.draw(self.game_surface)
            for ghost in self.ghosts:
                ghost.draw(self.game_surface)

            # Blit game_surface onto screen below HUD
            self.screen.blit(self.game_surface, (0, HUD_HEIGHT))

            # State overlays
            if self.state == STATE_PAUSED:
                self.draw_pause_overlay()
            elif self.state == STATE_GAME_OVER:
                self.draw_game_over()
            elif self.state == STATE_VICTORY:
                self.draw_victory()

        pygame.display.flip()

    def run(self):
        """Main execution loop."""
        while True:
            self.handle_events()
            self.update()
            self.render()
            self.clock.tick(FPS)


if __name__ == "__main__":
    game = Game()
    game.run()
