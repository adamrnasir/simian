import pygame
from simulation import Simulation


def main():
    pygame.init()
    width, height = 600, 600
    window = pygame.display.set_mode((width, height))

    pygame.display.set_caption("Particle Sim")

    # Set the background color to black
    window.fill((0, 0, 0))
    pygame.display.flip()

    simulation = Simulation(window, width, height)
    simulation.run()

    pygame.quit()


if __name__ == "__main__":
    main()
