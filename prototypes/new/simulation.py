import numpy as np
from materials import Air, get_material


class Simulation:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.grid = np.full((height, width), Air.id, dtype=np.int8)

    def add_material(self, x, y, material, radius):
        y_range, x_range = np.ogrid[-radius : radius + 1, -radius : radius + 1]
        mask = x_range * x_range + y_range * y_range <= radius * radius
        x_coords, y_coords = np.where(mask)
        x_coords += x - radius
        y_coords += y - radius
        valid = (
            (x_coords >= 0)
            & (x_coords < self.width)
            & (y_coords >= 0)
            & (y_coords < self.height)
        )
        self.grid[y_coords[valid], x_coords[valid]] = material.id

    def update(self):
        self.grid = update_grid(self.grid, self.width, self.height)


def update_grid(grid, width, height):
    new_grid = grid.copy()
    # Process rows bottom-up so gravity is applied correctly.
    for y in range(height - 1, -1, -1):
        non_air = np.where(grid[y] != Air.id)[0]
        for x in non_air:
            get_material(grid[y, x]).update(grid, x, y, new_grid)
    return new_grid
