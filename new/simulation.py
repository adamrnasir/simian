import numpy as np
from materials import get_material, Air


class Simulation:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.grid = np.full((height, width), Air.id, dtype=np.int8)

    def add_material(self, x, y, material, radius):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if dx * dx + dy * dy <= radius * radius:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < self.width and 0 <= ny < self.height:
                        self.grid[ny, nx] = material.id

    async def update(self):
        self.grid = await update_grid(self.grid, self.width, self.height)


async def async_range(start=0, end=None, step=1):
    if end is None:
        end = start
        start = 0
    for i in range(start, end, step):
        yield i


async def update_grid(grid, width, height):
    new_grid = grid.copy()
    async for y in async_range(height - 1, -1, -1):
        async for x in async_range(width):
            material_id = grid[y, x]
            if material_id != Air.id:
                material = get_material(material_id)
                material.update(grid, x, y, new_grid)
    return new_grid
