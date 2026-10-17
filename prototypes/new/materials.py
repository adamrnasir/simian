import copy
import math
from abc import ABC, abstractmethod

import numpy as np

GRAVITY = 1.0


class Material(ABC):
    id = None
    density = 0.1

    @abstractmethod
    def update(self, grid, x, y, new_grid):
        pass

    def react(self, other_material):
        return self

    def end_of_life(self, grid, x, y):
        grid[y, x] = Air.id

    def copy(self):
        return copy.deepcopy(self)


class Air(Material):
    id = 0
    density = 0.1

    def update(self, grid, x, y, new_grid):
        pass


class Particle(Material):
    friction = 0.5
    elasticity = 0.5
    mass = 1.0

    def update(self, grid, x, y, new_grid):
        height, width = grid.shape
        if y < height - 1:
            fall_speed, dx = self.calculate_fall(grid, x, y)
            target_y = min(y + fall_speed, height - 1)
            target_x = max(0, min(x + dx, width - 1))
            if new_grid[target_y, target_x] == Air.id:
                self.move(new_grid, x, y, target_x, target_y)
            else:
                other = get_material(new_grid[target_y, target_x])
                reaction = self.react(other)
                if isinstance(reaction, tuple):
                    new_grid[target_y, target_x] = reaction[0].id
                    new_grid[y, x] = reaction[1].id
                elif reaction.id != self.id:
                    new_grid[target_y, target_x] = reaction.id
                    new_grid[y, x] = Air.id
                elif other.density < self.density and isinstance(other, Fluid):
                    self.displace(new_grid, x, y, target_x, target_y)
                else:
                    self.try_move_diagonally(new_grid, x, y, width, height)

    def calculate_fall(self, grid, x, y):
        dx = np.random.randint(-1, 2)
        below_density = self.get_density_below(grid, x, y)
        if self.density <= below_density:
            return 1, 0
        ratio = self.density / below_density
        fall_speed = int(1 + 2 * math.atan(ratio - 1) / math.pi)
        return fall_speed, dx

    def get_density_below(self, grid, x, y):
        height, _ = grid.shape
        cells = [(y + 1, x), (y + 1, x + 1), (y + 1, x - 1)]
        densities = []
        for ny, nx in cells:
            particle = self._get_valid_particle(grid, ny, nx)
            if particle is not None:
                densities.append(particle.density)
        return sum(densities) / len(densities) if densities else 1000

    def _get_valid_particle(self, grid, ny, nx):
        if 0 <= ny < grid.shape[0] and 0 <= nx < grid.shape[1]:
            return get_material(grid[ny, nx])
        return None

    def get_surrounding_materials(self, grid, x, y):
        height, width = grid.shape
        cells = [
            (y + 1, x),
            (y - 1, x),
            (y, x + 1),
            (y, x - 1),
            (y + 1, x + 1),
            (y + 1, x - 1),
            (y - 1, x + 1),
            (y - 1, x - 1),
        ]
        valid = [(ny, nx) for ny, nx in cells if 0 <= ny < height and 0 <= nx < width]
        return [get_material(grid[ny, nx]) for ny, nx in valid]

    def move(self, new_grid, from_x, from_y, to_x, to_y):
        new_grid[to_y, to_x] = self.id
        new_grid[from_y, from_x] = Air.id

    def displace(self, new_grid, from_x, from_y, to_x, to_y):
        displaced = new_grid[to_y, to_x]
        new_grid[to_y, to_x] = self.id
        new_grid[from_y, from_x] = displaced

    def try_move_diagonally(self, new_grid, x, y, width, height):
        for ny, nx in sorted(
            [(y + 1, x - 1), (y + 1, x + 1)], key=lambda _: np.random.random()
        ):
            if 0 <= nx < width and 0 <= ny < height:
                target = new_grid[ny, nx]
                if target == Air.id:
                    self.move(new_grid, x, y, nx, ny)
                    break
                elif get_material(target).density < self.density and isinstance(
                    get_material(target), Fluid
                ):
                    self.displace(new_grid, x, y, nx, ny)
                    break


class Powder(Particle):
    pass


class Fluid(Particle):
    viscosity = 0.5

    def update(self, grid, x, y, new_grid):
        super().update(grid, x, y, new_grid)
        if new_grid[y, x] == self.id:
            self.spread_horizontally(grid, new_grid, x, y)

    def spread_horizontally(self, grid, new_grid, x, y):
        if np.random.random() > self.viscosity:
            height, width = grid.shape
            below_density = self.get_density_below(grid, x, y)
            spread = np.random.randint(
                1,
                max(
                    1,
                    int(
                        (self.density / below_density) * (1 - self.viscosity) * GRAVITY
                    ),
                )
                + 1,
            )
            for direction in np.random.permutation([-1, 1]):
                target_x = x + direction * spread
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

    def react(self, other):
        from materials import Lava, Mud, Stone, Water

        if isinstance(other, Lava):
            return Stone()
        elif isinstance(other, Water):
            return Mud()
        return self


class Water(Fluid):
    id = 2
    density = 1.0
    viscosity = 0.3
    mass = 1.0

    def react(self, other):
        from materials import Lava, Steam, Stone

        if isinstance(other, Lava):
            return (Stone(), Steam())
        return self


class Steam(Fluid):
    id = 3
    density = 0.5
    viscosity = 0.1
    mass = 0.5

    def update(self, grid, x, y, new_grid):
        height, width = grid.shape
        if y > 0:
            fall_speed, dx = self.calculate_fall(grid, x, y)
            target_y = max(y - fall_speed, 0)
            target_x = max(0, min(x + dx, width - 1))
            if new_grid[target_y, target_x] == Air.id:
                self.move(new_grid, x, y, target_x, target_y)
            else:
                other = get_material(new_grid[target_y, target_x])
                reaction = self.react(other)
                if isinstance(reaction, tuple):
                    new_grid[target_y, target_x] = reaction[0].id
                    new_grid[y, x] = reaction[1].id
                elif reaction.id != self.id:
                    new_grid[target_y, target_x] = reaction.id
                    new_grid[y, x] = Air.id
                elif other.density > self.density:
                    self.displace(new_grid, x, y, target_x, target_y)
                else:
                    self.try_move_diagonally(new_grid, x, y, width, height)
        else:
            if np.random.random() < 0.5:
                self.try_move_diagonally(new_grid, x, y, width, height)
            else:
                self.end_of_life(new_grid, x, y)

    def react(self, other):
        from materials import Water

        if isinstance(other, Water):
            return Water()
        return self

    def end_of_life(self, grid, x, y):
        from materials import Water

        grid[y, x] = Water.id if np.random.random() < 0.2 else Air.id


class Lava(Fluid):
    id = 4
    density = 2.5
    viscosity = 0.5
    mass = 2.0

    def react(self, other):
        from materials import Steam, Stone, Water

        if isinstance(other, Water):
            return (Stone(), Steam())
        elif isinstance(other, Stone):
            return (Lava(), Steam())
        return self


class Stone(Powder):
    id = 5
    density = 100
    friction = 0.9
    elasticity = 0.1
    mass = 2.5

    def react(self, other):
        from materials import Lava

        if isinstance(other, Lava):
            return (Lava(), Stone())
        return self


class Mud(Fluid):
    id = 6
    density = 2.0
    viscosity = 0.9
    mass = 1.0


MATERIALS = {
    Air.id: Air,
    Sand.id: Sand,
    Water.id: Water,
    Steam.id: Steam,
    Lava.id: Lava,
    Stone.id: Stone,
    Mud.id: Mud,
}


def get_material(id):
    return MATERIALS[id]()
