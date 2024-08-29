import pygame
import asyncio
from materials import Air, Sand, Water, Steam, Lava, Stone


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

    @staticmethod
    async def async_range(count):
        for i in range(count):
            yield (i)

    async def _render_row(self, y, surface):
        async for x in self.async_range(self.simulation.width):
            material_id = self.simulation.grid[y, x]
            if material_id != Air.id:  # Only draw non-Air particles
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
