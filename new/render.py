import pygame
import numpy as np
import asyncio


class Renderer:
    def __init__(self, window, simulation):
        self.window = window
        self.simulation = simulation
        self.pixel_size = 2
        self.colors = {
            simulation.AIR: (255, 255, 255),
            simulation.SAND: (194, 178, 128),
        }

    async def render(self):
        surface = pygame.Surface(
            (
                self.simulation.width * self.pixel_size,
                self.simulation.height * self.pixel_size,
            )
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
        for x in range(self.simulation.width):
            material = self.simulation.grid[y, x]
            color = self.colors[material]
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
