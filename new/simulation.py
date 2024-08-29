import numpy as np
from numba import jit, prange

# Material constants
AIR = 0
SAND = 1


class Simulation:
    AIR = AIR
    SAND = SAND

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.grid = np.zeros((height, width), dtype=np.int8)

    def add_material(self, x, y, material, radius):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if dx * dx + dy * dy <= radius * radius:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < self.width and 0 <= ny < self.height:
                        self.grid[ny, nx] = material

    def update(self):
        self.grid = update_grid(self.grid, self.width, self.height)


@jit(nopython=True, parallel=True)
def update_grid(grid, width, height):
    new_grid = grid.copy()
    for y in prange(height):
        actual_y = height - 1 - y  # Process from bottom to top
        for x in prange(width):
            material = grid[actual_y, x]
            if material == AIR:
                continue

            if material == SAND:
                if actual_y < height - 1:
                    if new_grid[actual_y + 1, x] == AIR:
                        new_grid[actual_y + 1, x] = SAND
                        new_grid[actual_y, x] = AIR
                    elif x > 0 and new_grid[actual_y + 1, x - 1] == AIR:
                        new_grid[actual_y + 1, x - 1] = SAND
                        new_grid[actual_y, x] = AIR
                    elif x < width - 1 and new_grid[actual_y + 1, x + 1] == AIR:
                        new_grid[actual_y + 1, x + 1] = SAND
                        new_grid[actual_y, x] = AIR
    return new_grid
