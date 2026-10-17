import numpy as np
import pygame
from materials import Air, Lava, Mud, Sand, Steam, Stone, Water


class Renderer:
    def __init__(self, window, simulation):
        self.window = window
        self.simulation = simulation
        self.pixel_size = min(
            window.get_width() // simulation.width,
            window.get_height() // simulation.height,
        )
        self.colors = {
            Air.id: (0, 0, 0, 0),
            Sand.id: (194, 178, 128),
            Water.id: (64, 164, 223),
            Steam.id: (220, 220, 220),
            Lava.id: (207, 16, 32),
            Stone.id: (120, 120, 120),
            Mud.id: (60, 60, 50),
        }

    def render(self):
        self.window.fill((0, 0, 0))
        surface = pygame.Surface(
            (
                self.simulation.width * self.pixel_size,
                self.simulation.height * self.pixel_size,
            ),
            pygame.SRCALPHA,
        )
        for y in range(self.simulation.height):
            row = self.simulation.grid[y]
            non_air = np.where(row != Air.id)[0]
            for x in non_air:
                color = self.colors[row[x]]
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
        scaled = pygame.transform.scale(surface, self.window.get_size())
        self.window.blit(scaled, (0, 0))
