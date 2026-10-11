import pygame
from player import Player

class Bullet:
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.color = color
        self.speed = 5
        self.rect = pygame.Rect(self.x, self.y, 5, 10)

    def move(self):
        if self.color == 'white':
            self.y -= self.speed
        else:
            self.y += self.speed
        self.rect.y = self.y

    def draw(self, screen):
        pygame.draw.rect(screen, self.color, self.rect)

    def is_off_screen(self):
        if self.color == 'white':
            return self.y < 0
        else:
            return self.y > 600

    def check_collision(self, other_rect):
        return self.rect.colliderect(other_rect)

    def update(self):
        self.move()
        if self.is_off_screen():
            return False
        return True
