class GameLogic:
    def __init__(self, player, enemies, lives=3):
        self.player = player
        self.enemies = enemies
        self.score = 0
        self.lives = lives
        self.game_over = False
        self.victory = False

    def check_collisions(self):
        # Player bullets vs enemies
        for bullet in self.player.bullets[:]:
            for enemy in self.enemies:
                if bullet.colliderect(enemy.rect):
                    self.score += 10
                    self.player.bullets.remove(bullet)
                    self.enemies.remove(enemy)
                    break

        # Enemy bullets vs player
        if self.player.is_hit(self.enemies.bullets):
            self.lives -= 1

    def update_game_state(self):
        if self.game_over or self.victory:
            return

        self.check_collisions()

        if len(self.enemies) == 0:
            self.victory = True
        elif self.lives <= 0 or self.enemies.lowest_point() >= self.player.rect.top:
            self.game_over = True
