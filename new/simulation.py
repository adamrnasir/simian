import numpy as np
from materials import get_material, Air
import asyncio


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

        valid_coords = (
            (x_coords >= 0)
            & (x_coords < self.width)
            & (y_coords >= 0)
            & (y_coords < self.height)
        )
        self.grid[y_coords[valid_coords], x_coords[valid_coords]] = material.id

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

    async def process_row(y):
        # Get non-Air material indices in the row
        non_air_indices = np.where(grid[y] != Air.id)[0]

        # Create tasks for non-Air materials
        row_tasks = [
            get_material(grid[y, x]).update(grid, x, y, new_grid)
            for x in non_air_indices
        ]

        # Execute all tasks for the row concurrently
        await asyncio.gather(*row_tasks)

    row_tasks = [process_row(y) async for y in async_range(height - 1, -1, -1)]
    await asyncio.gather(*row_tasks)

    return new_grid
