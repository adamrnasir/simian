import pygame
import numpy as np
from simulation import Simulation
from render import Renderer
import cProfile
import pstats
import io
import asyncio


def main():
    pygame.init()
    width, height = 100, 100
    window = pygame.display.set_mode((width, height))
    pygame.display.set_caption("Quantized Particle Physics Simulation")

    simulation = Simulation(width, height)
    renderer = Renderer(window, simulation)

    clock = pygame.time.Clock()
    running = True

    # Create a Profile object
    pr = cProfile.Profile()

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                # Save profiling results to a file
                with open("profiling_results.txt", "w") as file:
                    ps = pstats.Stats(pr, stream=file).sort_stats("cumulative")
                    ps.print_stats()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                x, y = pygame.mouse.get_pos()
                simulation.add_material(x, y, simulation.SAND, 10)

        # Start profiling
        pr.enable()

        simulation.update()
        asyncio.run(renderer.render())

        # Stop profiling
        pr.disable()

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    main()
