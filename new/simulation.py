import numpy as np
from materials import MATERIALS, Air
import asyncio


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


async def async_range(count):
    for i in range(count):
        yield i


async def update_grid(grid, width, height):
    new_grid = grid.copy()
    tasks = []
    async for y in async_range(height):
        actual_y = height - 1 - y  # Process from bottom to top
        async for x in async_range(width):
            material_id = grid[actual_y, x]
            if material_id != Air.id:
                tasks.append(MATERIALS[material_id].update(grid, x, actual_y, new_grid))
    await asyncio.gather(*tasks)
    return new_grid
