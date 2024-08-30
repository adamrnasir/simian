from abc import ABC, abstractmethod
import numpy as np
from copy import deepcopy
import math
import asyncio

GRAVITY = 1.0


class Material(ABC):
    id = None
    density = 0.1

    @abstractmethod
    async def update(self, grid, x, y, new_grid):
        pass

    def react(self, other_material):
        # Default behavior: no reaction
        return self

    def end_of_life(self, grid, x, y):
        # Default behavior: turn into Air
        grid[y, x] = Air.id

    def copy(self):
        return deepcopy(self)


class Air(Material):
    id = 0
    density = 0.1

    def update(self, grid, x, y, new_grid):
        pass


class Particle(Material):
    friction = 0.5
    elasticity = 0.5
    mass = 1.0

    async def update(self, grid, x, y, new_grid):
        height, width = grid.shape
        if y < height - 1:
            fall_speed, dx = await self.calculate_fall(grid, x, y)
            target_y = min(y + fall_speed, height - 1)
            target_x = max(0, min(x + dx, width - 1))

            if new_grid[target_y, target_x] == Air.id:
                self.move(new_grid, x, y, target_x, target_y)
            else:
                other_material = get_material(new_grid[target_y, target_x])
                reaction_result = self.react(other_material)
                if isinstance(reaction_result, tuple):
                    # Handle the case where two materials are produced
                    new_grid[target_y, target_x] = reaction_result[0].id
                    new_grid[y, x] = reaction_result[1].id
                elif reaction_result.id != self.id:
                    new_grid[target_y, target_x] = reaction_result.id
                    new_grid[y, x] = Air.id
                elif other_material.density < self.density and issubclass(
                    other_material.__class__, Fluid
                ):
                    self.displace(new_grid, x, y, target_x, target_y)
                else:
                    self.try_move_diagonally(new_grid, x, y, width, height)

    async def calculate_fall(self, grid, x, y):
        dx = np.random.randint(-1, 2)
        surrounding_density = await self.get_density_below(grid, x, y)

        if self.density <= surrounding_density:
            return 1, 0  # Particle floats or sits on top

        density_ratio = self.density / surrounding_density

        # Use arctangent function to map density ratio to fall speed
        fall_speed = int(1 + 2 * math.atan(density_ratio - 1) / math.pi)

        return fall_speed, dx

    async def get_density_below(self, grid, x, y):
        height, width = grid.shape

        valid_cells = [
            (y + 1, x),
            (y + 1, x + 1),
            (y + 1, x - 1),
        ]

        async def get_particle_density(ny, nx):
            particle = await self._get_valid_particle(grid, ny, nx)
            return particle.density if particle else None

        densities = await asyncio.gather(
            *[get_particle_density(ny, nx) for ny, nx in valid_cells]
        )
        valid_densities = [d for d in densities if d is not None]

        if not valid_densities:
            return 1000  # Floor

        return sum(valid_densities) / len(valid_densities)

    async def _get_valid_particle(self, grid, ny, nx):
        if ny >= 0 and ny < grid.shape[0] and nx >= 0 and nx < grid.shape[1]:
            return get_material(grid[ny, nx])
        return None

    def get_surrounding_materials(self, grid, x, y):
        height, width = grid.shape
        surrounding_cells = np.array(
            [
                [y + 1, x],
                [y - 1, x],
                [y, x + 1],
                [y, x - 1],
                [y + 1, x + 1],
                [y + 1, x - 1],
                [y - 1, x + 1],
                [y - 1, x - 1],
            ]
        )
        valid_cells = surrounding_cells[
            (surrounding_cells[:, 0] >= 0)
            & (surrounding_cells[:, 0] < height)
            & (surrounding_cells[:, 1] >= 0)
            & (surrounding_cells[:, 1] < width)
        ]
        return [get_material(grid[ny, nx]) for ny, nx in valid_cells]

    def move(self, new_grid, from_x, from_y, to_x, to_y):
        new_grid[to_y, to_x] = self.id
        new_grid[from_y, from_x] = Air.id

    def displace(self, new_grid, from_x, from_y, to_x, to_y):
        displaced_material = new_grid[to_y, to_x]
        new_grid[to_y, to_x] = self.id
        new_grid[from_y, from_x] = displaced_material

    def try_move_diagonally(self, new_grid, x, y, width, height):
        directions = np.array([(y + 1, x - 1), (y + 1, x + 1)])
        np.random.shuffle(directions)
        for ny, nx in directions:
            if 0 <= nx < width and 0 <= ny < height:
                target = new_grid[ny, nx]
                if target == Air.id:
                    self.move(new_grid, x, y, nx, ny)
                    break
                elif get_material(target).density < self.density and issubclass(
                    get_material(target).__class__, Fluid
                ):
                    self.displace(new_grid, x, y, nx, ny)
                    break


class Powder(Particle):
    pass


class Fluid(Particle):
    viscosity = 0.5

    async def update(self, grid, x, y, new_grid):
        await super().update(grid, x, y, new_grid)
        if new_grid[y, x] == self.id:  # If the particle hasn't moved vertically
            await self.spread_horizontally(grid, new_grid, x, y)

    async def spread_horizontally(self, grid, new_grid, x, y):
        if np.random.random() > self.viscosity:
            height, width = grid.shape
            surrounding_density = await self.get_density_below(grid, x, y)
            spread_distance = np.random.randint(
                1,
                max(
                    1,
                    int(
                        (self.density / surrounding_density)
                        * (1 - self.viscosity)
                        * GRAVITY
                    ),
                )
                + 1,
            )

            directions = np.array([-1, 1])
            np.random.shuffle(directions)

            for direction in directions:
                target_x = x + direction * spread_distance
                if 0 <= target_x < width:
                    if new_grid[y, target_x] == Air.id:
                        self.move(new_grid, x, y, target_x, y)
                        break
                    elif get_material(new_grid[y, target_x]).density < self.density:
                        self.displace(new_grid, x, y, target_x, y)
                    break


class Sand(Powder):
    id = 1
    density = 1.5
    friction = 0.7
    elasticity = 0.3
    mass = 1.5

    def react(self, other_material):
        if isinstance(other_material, Lava):
            return Stone()
        elif isinstance(other_material, Water):
            return Mud()
        return self


class Water(Fluid):
    id = 2
    density = 1.0
    viscosity = 0.3
    mass = 1.0

    def react(self, other_material):
        if isinstance(other_material, Lava):
            return (Stone(), Steam())
        return self


class Steam(Fluid):
    id = 3
    density = 0.5
    viscosity = 0.1
    mass = 0.5

    async def update(self, grid, x, y, new_grid):
        # Steam rises
        height, width = grid.shape
        if y > 0:
            fall_speed, dx = await self.calculate_fall(grid, x, y)
            target_y = max(y - fall_speed, 0)
            target_x = max(0, min(x + dx, width - 1))

            if new_grid[target_y, target_x] == Air.id:
                self.move(new_grid, x, y, target_x, target_y)
            else:
                other_material = get_material(new_grid[target_y, target_x])
                reaction_result = self.react(other_material)
                if isinstance(reaction_result, tuple):
                    # Handle the case where two materials are produced
                    new_grid[target_y, target_x] = reaction_result[0].id
                    new_grid[y, x] = reaction_result[1].id
                elif reaction_result.id != self.id:
                    new_grid[target_y, target_x] = reaction_result.id
                    new_grid[y, x] = Air.id
                elif other_material.density > self.density:
                    self.displace(new_grid, x, y, target_x, target_y)
                else:
                    self.try_move_diagonally(new_grid, x, y, width, height)
        else:
            if np.random.random() < 0.5:
                self.try_move_diagonally(new_grid, x, y, width, height)
            else:
                self.end_of_life(new_grid, x, y)

    def react(self, other_material):
        if isinstance(other_material, Water):
            return Water()  # Steam condenses back to water
        return self

    def end_of_life(self, grid, x, y):
        # 20% chance to turn into Water, 80% chance to disappear
        if np.random.random() < 0.2:
            grid[y, x] = Water.id
        else:
            grid[y, x] = Air.id


class Lava(Fluid):
    id = 4
    density = 2.5
    viscosity = 0.5
    mass = 2.0

    def react(self, other_material):
        if isinstance(other_material, Water):
            return (Stone(), Steam())
        elif isinstance(other_material, Stone):
            return (Lava(), Steam())
        return self


class Stone(Powder):
    id = 5
    density = 100
    friction = 0.9
    elasticity = 0.1
    mass = 2.5

    def react(self, other_material):
        if isinstance(other_material, Lava):
            return (Lava(), Stone())
        return self


class Mud(Fluid):
    id = 6
    density = 2.0
    viscosity = 0.9
    mass = 1.0


# Dictionary to map material IDs to their respective classes
MATERIALS = {
    Air.id: Air,
    Sand.id: Sand,
    Water.id: Water,
    Steam.id: Steam,
    Lava.id: Lava,
    Stone.id: Stone,
    Mud.id: Mud,
}


# Function to get a new instance of a material
def get_material(id):
    return MATERIALS[id]()
