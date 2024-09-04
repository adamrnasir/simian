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
        grid[y, x] = Air()

    def copy(self):
        return deepcopy(self)


class Air(Material):
    id = 0
    density = 0.1

    async def update(self, grid, x, y, new_grid):
        pass


class Particle(Material):
    friction = 0.5
    elasticity = 0.5
    fall_speed = 1.0

    async def calculate_reaction(self, grid, x, y, new_grid):
        other_material = grid[y, x]
        react1 = self.react(other_material)
        react2 = other_material.react(self)

        if react1.id != self.id and react2.id != other_material.id:
            # Both materials want to change, randomly choose one
            new_material = react1 if np.random.random() < 0.5 else react2
        elif react1.id != self.id:
            new_material = react1
        elif react2.id != other_material.id:
            new_material = react2
        else:
            return None

        new_grid[y, x] = new_material
        return new_grid

    async def calculate_reaction_static(self, grid, x, y, new_grid):
        valid_cells = [
            (y + 1, x),
            (y - 1, x),
            (y, x + 1),
            (y, x - 1),
            (y + 1, x + 1),
            (y + 1, x - 1),
            (y - 1, x + 1),
            (y - 1, x - 1),
        ]

        np.random.shuffle(valid_cells)
        for ny, nx in valid_cells:
            if 0 <= ny < grid.shape[0] and 0 <= nx < grid.shape[1]:
                reaction_result = await self.calculate_reaction(grid, nx, ny, new_grid)
                if reaction_result is not None:
                    return reaction_result

        return None

    def calculate_move_reaction(self, reactant):
        return 0, 0

    async def calculate_move_gravity(
        self, grid=None, x=None, y=None, surrounding_materials=None
    ):
        dx = 0
        if not surrounding_materials:
            dy = -self.fall_speed * GRAVITY
        else:
            if surrounding_materials[0].id == Air.id:
                dy = 0
            else:
                below_density = await self.get_density_below(grid, x, y)
                if below_density > self.density:
                    dy = 0
                else:
                    dy = await self._buoy(below_density)

        return dx, dy

    async def _buoy(self, surrounding_density):
        density_ratio = self.density / surrounding_density

        # Use arctangent function to map density ratio to fall speed
        dy = 1 + 2 * math.atan(density_ratio - 1) / math.pi

        return dy

    async def calculate_move_buoyant(self, grid, x, y):
        surrounding_density = await self.get_density_surrounding(grid, x, y)
        return 0, await self._buoy(surrounding_density)

    async def calculate_move_random(self, grid, x, y):
        dx = np.random.randint(-1, 1)
        dy = 0
        return dx, dy

    async def update(self, grid, x, y, new_grid):
        if new_grid is None:
            print(f"new_grid is None in Particle.update at x={x}, y={y}")  # Debug print
            return

        height, width = grid.shape
        dx, dy = await self.calculate_move(grid, x, y)
        target_x = max(0, min(x + int(dx), width - 1))
        target_y = max(0, min(y + int(dy), height - 1))

        if target_y == y and target_x == x:
            reaction_result = await self.calculate_reaction_static(grid, x, y, new_grid)
            if reaction_result is not None:
                new_grid[y, x] = reaction_result[y, x]
        elif isinstance(new_grid[target_y, target_x], Air):
            self.move(new_grid, x, y, target_x, target_y)
        else:
            reaction_result = await self.calculate_reaction(
                grid, target_x, target_y, new_grid
            )
            if reaction_result is not None:
                new_grid[target_y, target_x] = reaction_result[target_y, target_x]
                if new_grid[y, x] == self:  # If the original particle hasn't moved
                    new_grid[y, x] = Air()
            else:
                # If no reaction, try to displace
                self.displace(new_grid, x, y, target_x, target_y)

    async def calculate_move(self, grid, x, y):
        height, width = grid.shape
        surrounding_materials = self.get_surrounding_materials(grid, x, y)
        surrounding_materials_set = list(set(surrounding_materials))
        reactant = surrounding_materials_set[0]

        dx_reactant, dy_reactant = self.calculate_move_reaction(reactant)

        dx_grav, dy_grav = await self.calculate_move_gravity(
            grid, x, y, surrounding_materials
        )

        dx_buoy, dy_buoy = await self.calculate_move_buoyant(grid, x, y)

        dx_rand, dy_rand = await self.calculate_move_random(grid, x, y)

        dx = int(dx_reactant + dx_grav + dx_buoy + dx_rand)
        dy = int(dy_reactant + dy_grav + dy_buoy + dy_rand)

        # Ensure dx and dy don't cause out-of-bounds access
        dx = max(-x, min(dx, width - 1 - x))
        dy = max(-y, min(dy, height - 1 - y))

        # Check if the particle is below a fluid and try to displace it
        if y < height - 1:
            material_below = grid[y + 1, x]
            if dy > 0 and material_below.id != Air.id:
                if material_below.density < self.density and issubclass(
                    material_below.__class__, Fluid
                ):
                    self.displace(grid, x, y, x, y + 1)
                else:
                    self.try_move_diagonally(grid, x, y, width, height)

        return dx, dy

    async def _get_particle_density(self, grid, ny, nx):
        particle = await self._get_valid_particle(grid, ny, nx)
        return particle.density if particle else None

    async def get_density_below(self, grid, x, y):
        height, width = grid.shape

        valid_cells = [(y + 1, x)]

        densities = await asyncio.gather(
            *[self._get_particle_density(grid, ny, nx) for ny, nx in valid_cells]
        )
        valid_densities = [d for d in densities if d is not None]

        if not valid_densities:
            return 1000  # Floor

        return sum(valid_densities) / len(valid_densities)

    async def get_density_surrounding(self, grid, x, y):
        height, width = grid.shape

        valid_cells = [
            (y + 1, x),
            (y - 1, x),
            (y, x + 1),
            (y, x - 1),
            (y + 1, x + 1),
            (y + 1, x - 1),
            (y - 1, x + 1),
            (y - 1, x - 1),
        ]

        densities = await asyncio.gather(
            *[self._get_particle_density(grid, ny, nx) for ny, nx in valid_cells]
        )
        valid_densities = [d for d in densities if d is not None]

        return sum(valid_densities) / len(valid_densities)

    async def _get_valid_particle(self, grid, ny, nx):
        if ny >= 0 and ny < grid.shape[0] and nx >= 0 and nx < grid.shape[1]:
            return grid[ny, nx]
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
        return [grid[ny, nx] for ny, nx in valid_cells]

    def move(self, new_grid, from_x, from_y, to_x, to_y):
        # Only move if the destination is Air
        if isinstance(new_grid[to_y, to_x], Air):
            new_grid[to_y, to_x] = self
            new_grid[from_y, from_x] = Air()
        else:
            # If destination is not Air, try to displace
            self.displace(new_grid, from_x, from_y, to_x, to_y)

    def displace(self, new_grid, from_x, from_y, to_x, to_y):
        displaced_material = new_grid[to_y, to_x]
        if self.density > displaced_material.density:
            new_grid[to_y, to_x] = self
            new_grid[from_y, from_x] = displaced_material

    def try_move_diagonally(self, new_grid, x, y, width, height):
        directions = np.array([(y + 1, x - 1), (y + 1, x + 1)])
        np.random.shuffle(directions)
        for ny, nx in directions:
            if 0 <= nx < width and 0 <= ny < height:
                target = new_grid[ny, nx]
                if target.id == Air.id:
                    self.move(new_grid, x, y, nx, ny)
                    break
                elif target.density < self.density and issubclass(
                    target.__class__, Fluid
                ):
                    self.displace(new_grid, x, y, nx, ny)
                    break


class Powder(Particle):
    pass


class Fluid(Particle):
    viscosity = 0.5

    async def update(self, grid, x, y, new_grid):
        await super().update(grid, x, y, new_grid)
        if new_grid[y, x] == self:  # If the particle hasn't moved vertically
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
                    if new_grid[y, target_x].id == Air.id:
                        self.move(new_grid, x, y, target_x, y)
                        break
                    elif new_grid[y, target_x].density < self.density:
                        self.displace(new_grid, x, y, target_x, y)
                    break


class Sand(Powder):
    id = 1
    density = 1.5
    friction = 0.7
    elasticity = 0.3
    fall_speed = 1.5

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
    fall_speed = 1.0

    def react(self, other_material):
        if isinstance(other_material, Lava):
            return Steam()
        return self


class Steam(Fluid):
    id = 3
    density = 0.5
    viscosity = 0.1
    fall_speed = 0.5

    async def update(self, grid, x, y, new_grid):
        height, width = grid.shape
        fall_speed, dx = await self.calculate_move(grid, x, y)
        target_y = max(0, min(y - int(fall_speed), height - 1))
        target_x = max(0, min(x + dx, width - 1))

        if new_grid[target_y, target_x].id == Air.id:
            self.move(new_grid, x, y, target_x, target_y)
        else:
            other_material = new_grid[target_y, target_x]
            reaction_result = self.react(other_material)
            if reaction_result.id != self.id:
                new_grid[target_y, target_x] = reaction_result
                new_grid[y, x] = Air()
            elif other_material.density > self.density:
                self.displace(new_grid, x, y, target_x, target_y)
            else:
                self.try_move_diagonally(new_grid, x, y, width, height)

        if y == 0 and np.random.random() < 0.1:  # Chance to disappear at the top
            self.end_of_life(new_grid, x, y)

    def react(self, other_material):
        if isinstance(other_material, Water):
            return Water()  # Steam condenses back to water
        return self

    def end_of_life(self, grid, x, y):
        # 20% chance to turn into Water, 80% chance to disappear
        if np.random.random() < 0.2:
            grid[y, x] = Water()
        else:
            grid[y, x] = Air()


class Lava(Fluid):
    id = 4
    density = 2.5
    viscosity = 0.5
    fall_speed = 2.0

    def react(self, other_material):
        if isinstance(other_material, Water):
            return Stone()
        return self


class Stone(Powder):
    id = 5
    density = 100
    friction = 0.9
    elasticity = 0.1
    fall_speed = 2.5

    def react(self, other_material):
        if isinstance(other_material, Lava):
            return Lava()
        return self


class Mud(Fluid):
    id = 6
    density = 2.0
    viscosity = 0.9
    fall_speed = 1.0


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
