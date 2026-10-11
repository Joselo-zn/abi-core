import pygame
from bullets import Bullet

class Player:
    def __init__(self):
        self.rect = pygame.Rect(375, 550, 50, 20)
        self.bullets = []

    def go_left(self):
        self.rect.x -= 5
        if self.rect.left < 0:
            self.rect.left = 0

    def go_right(self):
        self.rect.x += 5
        if self.rect.right > 800:
            self.rect.right = 800

    def shoot(self):
        bullet = Bullet(self.rect.centerx, self.rect.top, 'white')
        self.bullets.append(bullet)

    def draw(self, screen):
        pygame.draw.rect(screen, (255, 255, 255), self.rect)
        for bullet in self.bullets:
            bullet.draw(screen)

    def update(self):
        for bullet in self.bullets[:]:
            if not bullet.update():
                self.bullets.remove(bullet)
