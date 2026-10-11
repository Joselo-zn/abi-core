"""
entities.py
Defines entity classes for Pac-Man game: PacMan, Ghost, Pellet, and Maze.
Includes predefined movement patterns, grid configuration, and game logic.
No local plan dependencies; runs nothing on import.
"""

import math
import random
import pygame

# Default Classic-style Pac-Man Grid Layout (19 cols x 21 rows)
# '#' = Wall, '.' = Pellet, 'o' = Power Pellet, ' ' = Empty, 'P' = PacMan Start, 'G' = Ghost Start, '-' = Ghost Door, 'T' = Tunnel
DEFAULT_MAP = [
    "###################",
    "#........#........#",
    "#o##.###.#.###.##o#",
    "#.................#",
    "#.##.#.#####.#.##.#",
    "#....#...#...#....#",
    "####.### # ###.####",
    "   #.#   G   #.#   ",
    "####.# ##-## #.####",
    "T    . #GGG# .    T",
    "####.# ##### #.####",
    "   #.#       #.#   ",
    "####.# ##### #.####",
    "#........#........#",
    "#.##.###.#.###.##.#",
    "#o.#.....P.....#.o#",
    "##.#.#.#####.#.#.##",
    "#....#...#...#....#",
    "#.######.#.######.#",
    "#..........................#"[0:19],  # Ensure exact string length safety
    "###################"
]

# Standard fixed map cleaner
DEFAULT_MAP = [
    "###################",
    "#........#........#",
    "#o##.###.#.###.##o#",
    "#.................#",
    "#.##.#.#####.#.##.#",
    "#....#...#...#....#",
    "####.### # ###.####",
    "   #.#   G   #.#   ",
    "####.# ##-## #.####",
    "T    . #GGG# .    T",
    "####.# ##### #.####",
    "   #.#       #.#   ",
    "####.# ##### #.####",
    "#........#........#",
    "#.##.###.#.###.##.#",
    "#o.#.....P.....#.o#",
    "##.#.#.#####.#.#.##",
    "#....#...#...#....#",
    "#.######.#.######.#",
    "#.................#",
    "###################"
]

# Colors
COLOR_BLACK = (0, 0, 0)
COLOR_WALL = (33, 33, 222)
COLOR_WALL_DOOR = (255, 184, 222)
COLOR_PELLET = (255, 184, 174)
COLOR_PACMAN = (255, 255, 0)
COLOR_GHOST_BLUE = (33, 33, 255)
COLOR_GHOST_WHITE = (255, 255, 255)


class Pellet:
    """Represents a standard pellet or power pellet in the maze."""
    def __init__(self, grid_x, grid_y, cell_size, is_power=False):
        self.grid_x = grid_x
        self.grid_y = grid_y
        self.cell_size = cell_size
        self.x = grid_x * cell_size + cell_size // 2
        self.y = grid_y * cell_size + cell_size // 2
        self.is_power = is_power
        self.points = 50 if is_power else 10
        self.radius = cell_size // 4 if is_power else cell_size // 8
        self.flash_timer = 0

    def draw(self, surface):
        """Draws the pellet on the Pygame surface."""
        if self.is_power:
            self.flash_timer = (self.flash_timer + 1) % 30
            if self.flash_timer < 15:
                pygame.draw.circle(surface, COLOR_PELLET, (int(self.x), int(self.y)), self.radius)
        else:
            pygame.draw.circle(surface, COLOR_PELLET, (int(self.x), int(self.y)), self.radius)


class Maze:
    """Manages the grid configuration, walls, pellets, and spawn locations."""
    def __init__(self, cell_size=28, map_data=None):
        self.cell_size = cell_size
        self.grid = map_data if map_data else DEFAULT_MAP
        self.rows = len(self.grid)
        self.cols = len(self.grid[0])
        self.width = self.cols * self.cell_size
        self.height = self.rows * self.cell_size

        self.pellets = []
        self.pacman_start = (self.width // 2, self.height // 2)
        self.ghost_starts = []

        self._parse_map()

    def _parse_map(self):
        """Parses the ASCII map to extract pellets and entity spawn points."""
        self.pellets = []
        self.ghost_starts = []

        for row in range(self.rows):
            for col in range(self.cols):
                char = self.grid[row][col]
                cx = col * self.cell_size + self.cell_size // 2
                cy = row * self.cell_size + self.cell_size // 2

                if char == '.':
                    self.pellets.append(Pellet(col, row, self.cell_size, is_power=False))
                elif char == 'o':
                    self.pellets.append(Pellet(col, row, self.cell_size, is_power=True))
                elif char == 'P':
                    self.pacman_start = (cx, cy)
                elif char == 'G':
                    self.ghost_starts.append((cx, cy))

        # Fallback if no ghost starts found in map
        if not self.ghost_starts:
            self.ghost_starts = [(self.width // 2, self.height // 2)]

    def is_wall(self, grid_x, grid_y, is_ghost=False):
        """Checks if a grid coordinate is a wall."""
        # Handle wrap-around tunnel rows
        if grid_y >= 0 and grid_y < self.rows:
            if grid_x < 0 or grid_x >= self.cols:
                return False  # Tunnel wrap area is open

        if grid_x < 0 or grid_x >= self.cols or grid_y < 0 or grid_y >= self.rows:
            return True

        char = self.grid[grid_y][grid_x]
        if char == '#':
            return True
        if char == '-' and not is_ghost:
            return True  # Ghost door acts as wall for PacMan
        return False

    def get_valid_directions(self, grid_x, grid_y, is_ghost=False):
        """Returns a list of valid direction tuples (dx, dy) from a given grid cell."""
        valid = []
        directions = [(0, -1), (0, 1), (-1, 0), (1, 0)]  # UP, DOWN, LEFT, RIGHT
        for dx, dy in directions:
            nx, ny = grid_x + dx, grid_y + dy
            if not self.is_wall(nx, ny, is_ghost=is_ghost):
                valid.append((dx, dy))
        return valid

    def draw(self, surface):
        """Draws the maze walls and ghost house door."""
        for row in range(self.rows):
            for col in range(self.cols):
                char = self.grid[row][col]
                rect = pygame.Rect(col * self.cell_size, row * self.cell_size, self.cell_size, self.cell_size)

                if char == '#':
                    pygame.draw.rect(surface, COLOR_WALL, rect, border_radius=4)
                elif char == '-':
                    door_rect = pygame.Rect(
                        col * self.cell_size,
                        row * self.cell_size + self.cell_size // 3,
                        self.cell_size,
                        self.cell_size // 3
                    )
                    pygame.draw.rect(surface, COLOR_WALL_DOOR, door_rect)

        # Draw all remaining pellets
        for pellet in self.pellets:
            pellet.draw(surface)


class PacMan:
    """Pac-Man player entity with direction control, movement logic, score and lives."""
    def __init__(self, start_x, start_y, cell_size=28):
        self.start_x = start_x
        self.start_y = start_y
        self.cell_size = cell_size
        self.x = float(start_x)
        self.y = float(start_y)
        self.speed = 2.5
        self.direction = (0, 0)
        self.next_direction = (0, 0)
        self.lives = 3
        self.score = 0

        # Animation parameters
        self.mouth_angle = 45.0
        self.mouth_speed = 3.0
        self.mouth_opening = True

    def reset_position(self):
        """Resets PacMan to starting location and stops movement."""
        self.x = float(self.start_x)
        self.y = float(self.start_y)
        self.direction = (0, 0)
        self.next_direction = (0, 0)

    def set_direction(self, direction):
        """Sets the requested next direction."""
        self.next_direction = (dx, dy)

    def get_grid_pos(self):
        """Returns the current grid coordinates (grid_x, grid_y)."""
        return int(self.x // self.cell_size), int(self.y // self.cell_size)

    def is_centered(self):
        """Checks if PacMan is aligned near the center of the current tile."""
        cx = (self.x // self.cell_size) * self.cell_size + self.cell_size / 2.0
        cy = (self.y // self.cell_size) * self.cell_size + self.cell_size / 2.0
        return abs(self.x - cx) < self.speed and abs(self.y - cy) < self.speed

    def update(self, maze):
        """Updates position, handles direction changes at tile intersections, and mouth animation."""
        grid_x, grid_y = self.get_grid_pos()

        # Try changing to next_direction if possible
        if self.next_direction != (0, 0):
            next_gx = grid_x + self.next_direction[0]
            next_gy = grid_y + self.next_direction[1]

            # Reversing direction can happen immediately
            if (self.next_direction[0] == -self.direction[0] and self.next_direction[1] == -self.direction[1]):
                self.direction = self.next_direction
            elif self.is_centered():
                if not maze.is_wall(next_gx, next_gy, is_ghost=False):
                    self.direction = self.next_direction
                    # Snap to tile center along axis perpendicular to new direction
                    if self.direction[0] != 0:
                        self.y = grid_y * self.cell_size + self.cell_size / 2.0
                    else:
                        self.x = grid_x * self.cell_size + self.cell_size / 2.0

        # Move if target tile in current direction is not a wall
        if self.direction != (0, 0):
            target_gx = grid_x + self.direction[0]
            target_gy = grid_y + self.direction[1]

            if not maze.is_wall(target_gx, target_gy, is_ghost=False) or not self.is_centered():
                self.x += self.direction[0] * self.speed
                self.y += self.direction[1] * self.speed
            else:
                # Snap to tile center and halt
                self.x = grid_x * self.cell_size + self.cell_size / 2.0
                self.y = grid_y * self.cell_size + self.cell_size / 2.0

        # Handle wrap-around tunnel
        if self.x < 0:
            self.x = maze.width - 1
        elif self.x >= maze.width:
            self.x = 0

        # Mouth animation logic
        if self.direction != (0, 0):
            if self.mouth_opening:
                self.mouth_angle += self.mouth_speed
                if self.mouth_angle >= 45.0:
                    self.mouth_opening = False
            else:
                self.mouth_angle -= self.mouth_speed
                if self.mouth_angle <= 5.0:
                    self.mouth_opening = True

    def eat_pellets(self, maze):
        """Checks collision with pellets. Returns (points_earned, was_power_pellet)."""
        points = 0
        power_eaten = False
        remaining_pellets = []

        for pellet in maze.pellets:
            dist = math.hypot(self.x - pellet.x, self.y - pellet.y)
            if dist < self.cell_size / 2.0:
                points += pellet.points
                if pellet.is_power:
                    power_eaten = True
            else:
                remaining_pellets.append(pellet)

        maze.pellets = remaining_pellets
        self.score += points
        return points, power_eaten

    def draw(self, surface):
        """Draws PacMan with mouth animation oriented according to current direction."""
        radius = self.cell_size // 2 - 2
        px, py = int(self.x), int(self.y)

        # Base angle depending on direction
        if self.direction == (1, 0):
            base_angle = 0
        elif self.direction == (-1, 0):
            base_angle = 180
        elif self.direction == (0, -1):
            base_angle = 90
        elif self.direction == (0, 1):
            base_angle = 270
        else:
            base_angle = 0

        start_angle = math.radians(base_angle + self.mouth_angle)
        end_angle = math.radians(base_angle + 360 - self.mouth_angle)

        points = [(px, py)]
        num_steps = 20
        angle_step = (end_angle - start_angle) / num_steps

        for i in range(num_steps + 1):
            angle = start_angle + i * angle_step
            x = px + radius * math.cos(angle)
            y = py - radius * math.sin(angle)  # Pygame Y axis inverted
            points.append((x, y))

        if len(points) > 2:
            pygame.draw.polygon(surface, COLOR_PACMAN, points)
        else:
            pygame.draw.circle(surface, COLOR_PACMAN, (px, py), radius)


class Ghost:
    """Ghost entity with predefined movement patterns (Chase, Ambush, Patrol, Random, Frightened)."""
    def __init__(self, name, color, start_x, start_y, pattern="chase", cell_size=28):
        self.name = name
        self.color = color
        self.start_x = start_x
        self.start_y = start_y
        self.cell_size = cell_size

        self.x = float(start_x)
        self.y = float(start_y)
        self.speed = 2.0
        self.direction = (0, -1)
        self.pattern = pattern  # "chase", "ambush", "patrol", "random"

        self.frightened = False
        self.frightened_timer = 0

        # Predefined patrol sequence for 'patrol' pattern
        self.patrol_index = 0
        self.patrol_targets = [(1, 1), (17, 1), (17, 19), (1, 19)]

    def reset_position(self):
        """Resets Ghost to spawn coordinates and clears frightened state."""
        self.x = float(self.start_x)
        self.y = float(self.start_y)
        self.direction = (0, -1)
        self.frightened = False
        self.frightened_timer = 0

    def set_frightened(self, duration_frames=300):
        """Triggers frightened mode for specified frame duration."""
        self.frightened = True
        self.frightened_timer = duration_frames

    def get_grid_pos(self):
        """Returns ghost grid coordinates."""
        return int(self.x // self.cell_size), int(self.y // self.cell_size)

    def is_centered(self):
        """Checks if ghost is near the center of its current cell."""
        cx = (self.x // self.cell_size) * self.cell_size + self.cell_size / 2.0
        cy = (self.y // self.cell_size) * self.cell_size + self.cell_size / 2.0
        return abs(self.x - cx) < self.speed and abs(self.y - cy) < self.speed

    def _choose_direction(self, maze, pacman):
        """Determines the next move direction based on state and predefined movement pattern."""
        grid_x, grid_y = self.get_grid_pos()
        valid_dirs = maze.get_valid_directions(grid_x, grid_y, is_ghost=True)

        if not valid_dirs:
            return (0, 0)

        # Do not allow immediate 180-degree turn unless no other choice
        opposite = (-self.direction[0], -self.direction[1])
        non_opposite = [d for d in valid_dirs if d != opposite]
        choices = non_opposite if non_opposite else valid_dirs

        # Frightened pattern: random choice
        if self.frightened:
            return random.choice(choices)

        # Target tile selection based on predefined AI patterns
        pac_gx, pac_gy = pacman.get_grid_pos()

        if self.pattern == "chase":
            # Direct target to PacMan position (Blinky strategy)
            target = (pac_gx, pac_gy)

        elif self.pattern == "ambush":
            # Target 4 steps ahead of PacMan position (Pinky strategy)
            p_dx, p_dy = pacman.direction
            target = (pac_gx + p_dx * 4, pac_gy + p_dy * 4)

        elif self.pattern == "patrol":
            # Predefined patrol waypoint pattern (Inky/Patrol strategy)
            target = self.patrol_targets[self.patrol_index]
            if (grid_x, grid_y) == target:
                self.patrol_index = (self.patrol_index + 1) % len(self.patrol_targets)
                target = self.patrol_targets[self.patrol_index]

        else:  # "random" or Clyde pattern
            # Pick a random path or move towards corner if too close to PacMan
            dist_to_pacman = math.hypot(grid_x - pac_gx, grid_y - pac_gy)
            if dist_to_pacman < 5:
                target = (0, maze.rows - 1)  # Bottom left corner scatter
            else:
                return random.choice(choices)

        # Select choice direction that minimizes distance to target
        best_dir = choices[0]
        best_dist = float('inf')

        for dx, dy in choices:
            nx, ny = grid_x + dx, grid_y + dy
            dist = math.hypot(nx - target[0], ny - target[1])
            if dist < best_dist:
                best_dist = dist
                best_dir = (dx, dy)

        return best_dir

    def update(self, maze, pacman):
        """Updates ghost state, frightened timer, and position."""
        # Handle frightened state countdown
        if self.frightened:
            self.frightened_timer -= 1
            if self.frightened_timer <= 0:
                self.frightened = False

        grid_x, grid_y = self.get_grid_pos()

        # Make movement decision at tile center
        if self.is_centered():
            # Align position to exact tile center
            self.x = grid_x * self.cell_size + self.cell_size / 2.0
            self.y = grid_y * self.cell_size + self.cell_size / 2.0
            self.direction = self._choose_direction(maze, pacman)

        # Move ghost
        current_speed = self.speed * 0.6 if self.frightened else self.speed
        self.x += self.direction[0] * current_speed
        self.y += self.direction[1] * current_speed

        # Handle wrap-around tunnel
        if self.x < 0:
            self.x = maze.width - 1
        elif self.x >= maze.width:
            self.x = 0

    def draw(self, surface):
        """Draws ghost sprite with body, wavy skirt, and eye details."""
        radius = self.cell_size // 2 - 2
        px, py = int(self.x), int(self.y)

        # Color selection
        if self.frightened:
            color = COLOR_GHOST_WHITE if (self.frightened_timer < 60 and (self.frightened_timer // 10) % 2 == 0) else COLOR_GHOST_BLUE
        else:
            color = self.color

        # Ghost head (arc / semicircle top)
        head_rect = pygame.Rect(px - radius, py - radius, radius * 2, radius * 2)
        pygame.draw.circle(surface, color, (px, py - 2), radius)

        # Ghost lower body
        body_rect = pygame.Rect(px - radius, py - 2, radius * 2, radius)
        pygame.draw.rect(surface, color, body_rect)

        # Wavy bottom skirt
        wave_width = (radius * 2) // 3
        for i in range(3):
            wx = px - radius + i * wave_width + wave_width // 2
            wy = py + radius
            pygame.draw.circle(surface, color, (wx, wy), wave_width // 2)

        # Eyes (if not frightened, look in current direction)
        if not self.frightened:
            eye_offset_x = self.direction[0] * 3
            eye_offset_y = self.direction[1] * 3

            # Left eye & Right eye
            pygame.draw.circle(surface, (255, 255, 255), (px - 5 + eye_offset_x, py - 4 + eye_offset_y), 4)
            pygame.draw.circle(surface, (255, 255, 255), (px + 5 + eye_offset_x, py - 4 + eye_offset_y), 4)

            # Pupils
            pygame.draw.circle(surface, (0, 0, 255), (px - 5 + eye_offset_x * 1.5, py - 4 + eye_offset_y * 1.5), 2)
            pygame.draw.circle(surface, (0, 0, 255), (px + 5 + eye_offset_x * 1.5, py - 4 + eye_offset_y * 1.5), 2)
