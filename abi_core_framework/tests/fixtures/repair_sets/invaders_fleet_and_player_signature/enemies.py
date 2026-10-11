import random

import pygame

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600


class Enemy:
    def __init__(self, x, y, image):
        self.image = image
        self.rect = self.image.get_rect(topleft=(x, y))

    def draw(self, screen):
        screen.blit(self.image, self.rect)


class EnemyFleet:
    """The whole fleet moves as one block: sideways until an edge, then
    down a step and reverse. Shots come from random enemies."""

    def __init__(self, image, rows=4, columns=8):
        self.image = image
        self.rows = rows
        self.columns = columns
        self.spacing_x = 60
        self.spacing_y = 45
        self.speed = 1.0
        self.direction = 1
        self.drop = 20
        self.bullet_speed = 5
        self.shoot_chance = 0.02
        self.bullets = []
        self.enemies = []
        self._offset = 0.0
        self.create_fleet()

    def create_fleet(self):
        self.enemies = []
        for row in range(self.rows):
            for col in range(self.columns):
                x = col * self.spacing_x + 100
                y = row * self.spacing_y + 60
                self.enemies.append(Enemy(x, y, self.image))

    def __len__(self):
        return len(self.enemies)

    def __iter__(self):
        return iter(list(self.enemies))

    def remove(self, enemy):
        self.enemies.remove(enemy)
        # Fewer enemies left → faster fleet, like the original
        self.speed += 0.05

    def advance(self):
        if not self.enemies:
            return
        # Sub-pixel accumulation so fractional speeds still move
        self._offset += self.speed * self.direction
        step = int(self._offset)
        self._offset -= step
        for enemy in self.enemies:
            enemy.rect.x += step

        left = min(e.rect.left for e in self.enemies)
        right = max(e.rect.right for e in self.enemies)
        # Only bounce when moving INTO the edge: with fractional speeds the
        # next frame may not move at all, and re-checking a bare "touching
        # the edge" would flip and drop the fleet again every frame.
        hit_right = self.direction > 0 and right >= SCREEN_WIDTH
        hit_left = self.direction < 0 and left <= 0
        if hit_left or hit_right:
            self.direction *= -1
            shift = -left if left < 0 else (SCREEN_WIDTH - right if right > SCREEN_WIDTH else 0)
            for enemy in self.enemies:
                enemy.rect.x += shift
                enemy.rect.y += self.drop

    def shoot(self):
        if self.enemies and random.random() < self.shoot_chance:
            shooter = random.choice(self.enemies)
            self.bullets.append(pygame.Rect(shooter.rect.centerx - 2, shooter.rect.bottom, 4, 10))

    def update_bullets(self):
        for bullet in self.bullets[:]:
            bullet.y += self.bullet_speed
            if bullet.top > SCREEN_HEIGHT:
                self.bullets.remove(bullet)

    def lowest_point(self):
        return max((e.rect.bottom for e in self.enemies), default=0)

    def draw(self, screen):
        for enemy in self.enemies:
            enemy.draw(screen)
        for bullet in self.bullets:
            pygame.draw.rect(screen, (255, 255, 0), bullet)
