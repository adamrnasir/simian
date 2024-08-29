from abc import ABC, abstractmethod
import random

# Add a global gravity constant
GRAVITY = 1.0


class Material(ABC):
    id = None
    density = None

    @abstractmethod
    async def update(self, grid, x, y, new_grid):
        pass

    @staticmethod
    def react(material1, material2):
        # Default behavior: no reaction
        return None


class Air(Material):
    id = 0
    density = 0.1

    async def update(self, grid, x, y, new_grid):
        pass


class Particle(Material):
    friction = 0.5
    elasticity = 0.5
    mass = 1.0

    async def update(self, grid, x, y, new_grid):
        height, width = grid.shape
        if y < height - 1:
            fall_speed, dx = self.calculate_movement(grid, x, y)
            target_y = min(y + fall_speed, height - 1)
            target_x = max(0, min(x + dx, width - 1))

            if new_grid[target_y, target_x] == Air.id:
                self.move(new_grid, x, y, target_x, target_y)
            else:
                reaction_result = self.react(
                    self, MATERIALS[new_grid[target_y, target_x]]
                )
                if reaction_result:
                    new_grid[target_y, target_x] = reaction_result.id
                    new_grid[y, x] = Air.id
                elif MATERIALS[new_grid[target_y, target_x]].density < self.density:
                    self.displace(new_grid, x, y, target_x, target_y)
                else:
                    self.try_move_diagonally(new_grid, x, y, width, height)

    def calculate_movement(self, grid, x, y):
        surrounding_density = self.get_surrounding_density(grid, x, y)
        # Incorporate global gravity into fall speed calculation
        max_fall_speed = int((self.density / surrounding_density) * GRAVITY) + 1
        fall_speed = random.randint(1, max_fall_speed)

        # Add horizontal movement
        dx = random.randint(-1, 1)
        return fall_speed, dx

    def get_surrounding_density(self, grid, x, y):
        height, width = grid.shape
        surrounding_cells = [
            (y + 1, x),
            (y - 1, x),
            (y, x + 1),
            (y, x - 1),
            (y + 1, x + 1),
            (y + 1, x - 1),
            (y - 1, x + 1),
            (y - 1, x - 1),
        ]
        valid_cells = [
            (ny, nx)
            for ny, nx in surrounding_cells
            if 0 <= ny < height and 0 <= nx < width
        ]

        total_density = sum(MATERIALS[grid[ny, nx]].density for ny, nx in valid_cells)
        return total_density / len(valid_cells) if valid_cells else self.density

    def move(self, new_grid, from_x, from_y, to_x, to_y):
        new_grid[to_y, to_x] = self.id
        new_grid[from_y, from_x] = Air.id

    def displace(self, new_grid, from_x, from_y, to_x, to_y):
        displaced_material = new_grid[to_y, to_x]
        new_grid[to_y, to_x] = self.id
        new_grid[from_y, from_x] = displaced_material

    def try_move_diagonally(self, new_grid, x, y, width, height):
        directions = [(y + 1, x - 1), (y + 1, x + 1)]
        random.shuffle(directions)
        for ny, nx in directions:
            if 0 <= nx < width and 0 <= ny < height:
                target = new_grid[ny, nx]
                if target == Air.id:
                    self.move(new_grid, x, y, nx, ny)
                    break
                elif MATERIALS[target].density < self.density:
                    self.displace(new_grid, x, y, nx, ny)
                    break


class Powder(Particle):
    pass


class Fluid(Particle):
    viscosity = 0.5

    async def update(self, grid, x, y, new_grid):
        await super().update(grid, x, y, new_grid)
        if new_grid[y, x] == self.id:  # If the particle hasn't moved vertically
            self.spread_horizontally(grid, new_grid, x, y)

    def spread_horizontally(self, grid, new_grid, x, y):
        height, width = grid.shape
        surrounding_density = self.get_surrounding_density(grid, x, y)
        # Incorporate global gravity into spread distance calculation
        spread_distance = random.randint(
            1,
            int((self.density / surrounding_density) * (1 - self.viscosity) * GRAVITY)
            + 1,
        )

        directions = [-1, 1]
        random.shuffle(directions)

        for direction in directions:
            target_x = x + direction * spread_distance
            if 0 <= target_x < width:
                if new_grid[y, target_x] == Air.id:
                    self.move(new_grid, x, y, target_x, y)
                    break
                elif MATERIALS[new_grid[y, target_x]].density < self.density:
                    self.displace(new_grid, x, y, target_x, y)
                    break


class Sand(Powder):
    id = 1
    density = 2.0
    friction = 0.7
    elasticity = 0.3
    mass = 1.5


class Water(Fluid):
    id = 2
    density = 1.0
    viscosity = 0.3
    mass = 1.0


class Steam(Fluid):
    id = 3
    density = 0.5
    viscosity = 0.1
    mass = 0.5

    async def update(self, grid, x, y, new_grid):
        # Steam rises
        height, width = grid.shape
        if y > 0:
            fall_speed, dx = self.calculate_movement(grid, x, y)
            target_y = max(y - fall_speed, 0)
            target_x = max(0, min(x + dx, width - 1))

            if new_grid[target_y, target_x] == Air.id:
                self.move(new_grid, x, y, target_x, target_y)
            else:
                reaction_result = self.react(
                    self, MATERIALS[new_grid[target_y, target_x]]
                )
                if reaction_result:
                    new_grid[target_y, target_x] = reaction_result.id
                    new_grid[y, x] = Air.id
                elif MATERIALS[new_grid[target_y, target_x]].density > self.density:
                    self.displace(new_grid, x, y, target_x, target_y)
                else:
                    self.try_move_diagonally(new_grid, x, y, width, height)

    @staticmethod
    def react(material1, material2):
        if isinstance(material2, Water):
            return None  # Steam condenses back to water
        return None


class Lava(Fluid):
    id = 4
    density = 2.5
    viscosity = 0.8
    mass = 2.0

    @staticmethod
    def react(material1, material2):
        if isinstance(material2, Water):
            return Steam()  # Lava turns water into steam
        if isinstance(material2, Sand):
            return Stone()  # Lava turns sand into stone
        return None


class Stone(Powder):
    id = 5
    density = 2.6
    friction = 0.9
    elasticity = 0.1
    mass = 2.5


# Update reaction methods for existing materials
def sand_react(material1, material2):
    if isinstance(material2, Lava):
        return Stone()  # Sand turns into stone when it touches lava
    return None


def water_react(material1, material2):
    if isinstance(material2, Lava):
        return Steam()  # Water turns into steam when it touches lava
    return None


Sand.react = staticmethod(sand_react)
Water.react = staticmethod(water_react)

# Dictionary to map material IDs to their respective classes
MATERIALS = {
    Air.id: Air(),
    Sand.id: Sand(),
    Water.id: Water(),
    Steam.id: Steam(),
    Lava.id: Lava(),
    Stone.id: Stone(),
}
