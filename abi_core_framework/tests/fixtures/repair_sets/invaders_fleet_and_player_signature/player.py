import pygame

SCREEN_WIDTH = 800


class Player:
    def __init__(self, x, y, image):
        self.image = image
        self.bullet_image = bullet_image
        self.rect = self.image.get_rect(midbottom=(x, y))
        self.speed = 5
        self.bullet_speed = 10
        self.bullets = []
        self.bullet_cooldown = 0

    def move_left(self):
        self.rect.x = max(0, self.rect.x - self.speed)

    def move_right(self):
        self.rect.x = min(SCREEN_WIDTH - self.rect.width, self.rect.x + self.speed)

    def shoot(self):
        if self.bullet_cooldown <= 0:
            bullet = self.bullet_image.get_rect(midbottom=self.rect.midtop)
            self.bullets.append(bullet)
            self.bullet_cooldown = 15

    def update(self):
        if self.bullet_cooldown > 0:
            self.bullet_cooldown -= 1

        for bullet in self.bullets[:]:
            bullet.y -= self.bullet_speed
            if bullet.bottom < 0:
                self.bullets.remove(bullet)

    def draw(self, screen):
        screen.blit(self.image, self.rect)
        for bullet in self.bullets:
            screen.blit(self.bullet_image, bullet)

    def is_hit(self, enemy_bullets):
        for bullet in enemy_bullets[:]:
            if self.rect.colliderect(bullet):
                enemy_bullets.remove(bullet)
                return True
        return False
