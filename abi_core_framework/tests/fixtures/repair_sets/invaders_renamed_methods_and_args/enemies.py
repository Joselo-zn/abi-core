import pygame
from bullets import Bullet

class Enemy:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 50, 50)
        self.direction = 1
        self.shoot_timer = 0

    def move(self):
        self.rect.x += 1 * self.direction
        if self.rect.left <= 0 or self.rect.right >= 800:
            self.rect.y += 10
            self.direction *= -1

    def shoot(self):
        self.shoot_timer += 1
        if self.shoot_timer >= 60:
            self.shoot_timer = 0
            return Bullet(self.rect.centerx, self.rect.bottom, 'red')
        return None

    def draw(self, screen):
        pygame.draw.rect(screen, (255, 0, 0), self.rect)

class EnemyGrid:
    def __init__(self):
        self.enemies = []
        self.create_grid()

    def create_grid(self):
        for row in range(2):
            for col in range(4):
                x = 100 + col * 60
                y = 50 + row * 60
                self.enemies.append(Enemy(x, y))

    def update(self):
        for enemy in self.enemies:
            enemy.move()

    def draw(self, screen):
        for enemy in self.enemies:
            enemy.draw(screen)

    def remove_enemy(self, enemy):
        if enemy in self.enemies:
            self.enemies.remove(enemy)
    
    def get_enemies(self):
        return self.enemies
