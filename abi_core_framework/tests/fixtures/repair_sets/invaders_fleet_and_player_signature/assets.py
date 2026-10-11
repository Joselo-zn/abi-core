import os

import pygame

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


class Assets:
    """Loads images from ./assets when present; otherwise draws simple
    placeholder sprites, so the game runs without any image files."""

    def __init__(self):
        self.assets = {}
        self._build_defaults()
        self.load_assets(["background.png", "player.png", "enemy.png", "bullet.png"], [])

    def _build_defaults(self):
        background = pygame.Surface((800, 600))
        background.fill((0, 0, 0))
        for i in range(80):
            x = (i * 97) % 800
            y = (i * 53) % 600
            background.set_at((x, y), (200, 200, 200))
        self.assets["background.png"] = background

        player = pygame.Surface((50, 30), pygame.SRCALPHA)
        pygame.draw.rect(player, (0, 255, 0), (0, 12, 50, 18))
        pygame.draw.rect(player, (0, 255, 0), (20, 0, 10, 14))
        self.assets["player.png"] = player

        enemy = pygame.Surface((40, 30), pygame.SRCALPHA)
        pygame.draw.rect(enemy, (255, 60, 60), (4, 6, 32, 18))
        pygame.draw.rect(enemy, (255, 60, 60), (0, 18, 8, 12))
        pygame.draw.rect(enemy, (255, 60, 60), (32, 18, 8, 12))
        pygame.draw.rect(enemy, (0, 0, 0), (12, 10, 5, 5))
        pygame.draw.rect(enemy, (0, 0, 0), (23, 10, 5, 5))
        self.assets["enemy.png"] = enemy

        bullet = pygame.Surface((4, 12))
        bullet.fill((255, 255, 255))
        self.assets["bullet.png"] = bullet

    def load_assets(self, image_paths, sound_paths):
        for name in image_paths:
            path = os.path.join(ASSETS_DIR, name)
            if os.path.exists(path):
                self.assets[name] = pygame.image.load(path).convert_alpha()

        for name in sound_paths:
            path = os.path.join(ASSETS_DIR, name)
            if os.path.exists(path) and pygame.mixer.get_init():
                self.assets[name] = pygame.mixer.Sound(path)

    def get_asset(self, name):
        return self.assets.get(name)
