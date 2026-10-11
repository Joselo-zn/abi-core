import pygame

class Score:
    def __init__(self):
        self.score = 0
        self.lives = 3
        self.font = pygame.font.SysFont("Arial", 32)

    def add_points(self, points=10):
        self.score += points

    def remove_life(self):
        self.lives -= 1

    def draw(self, screen):
        score_text = self.font.render(f"Score: {self.score}", True, (255, 255, 255))
        lives_text = self.font.render(f"Lives: {self.lives}", True, (255, 255, 255))
        screen.blit(score_text, (10, 10))
        screen.blit(lives_text, (600, 10))

    def is_game_over(self):
        return self.lives <= 0
