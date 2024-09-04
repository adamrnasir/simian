import pygame
import asyncio
import numpy as np
from materials import Air, Sand, Water, Steam, Lava, Stone, Mud


class Renderer:
    def __init__(self, window, simulation):
        self.window = window
        self.simulation = simulation
        # Calculate pixel size based on window and grid sizes
        self.pixel_size = min(
            window.get_width() // simulation.width,
            window.get_height() // simulation.height,
        )
        self.colors = {
            Air.id: (0, 0, 0, 0),  # Changed Air color to transparent black
            Sand.id: (194, 178, 128),
            Water.id: (64, 164, 223),
            Steam.id: (220, 220, 220),
            Lava.id: (207, 16, 32),
            Stone.id: (120, 120, 120),
            Mud.id: (60, 60, 50),
        }

    async def render(self):
        # Fill the window with black
        self.window.fill((0, 0, 0))

        surface = pygame.Surface(
            (
                self.simulation.width * self.pixel_size,
                self.simulation.height * self.pixel_size,
            ),
            pygame.SRCALPHA,  # Add this flag to support transparency
        )

        await self._render_rows(surface)

        self.window.blit(
            pygame.transform.scale(surface, self.window.get_size()), (0, 0)
        )

    async def _render_rows(self, surface):
        tasks = []
        for y in range(self.simulation.height):
            tasks.append(self._render_row(y, surface))
        await asyncio.gather(*tasks)

    async def _render_row(self, y, surface):
        row = self.simulation.grid[y]
        non_air_indices = np.where(row != Air.id)[0]

        async def draw_particle(x):
            material_id = row[x].id
            color = self.colors[material_id]
            pygame.draw.rect(
                surface,
                color,
                (
                    x * self.pixel_size,
                    y * self.pixel_size,
                    self.pixel_size,
                    self.pixel_size,
                ),
            )

        await asyncio.gather(*[draw_particle(x) for x in non_air_indices])
