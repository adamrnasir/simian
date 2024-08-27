import pygame
from simulation import Simulation


def main():
    pygame.init()
    width, height = 600, 600
    window = pygame.display.set_mode((width, height))
    clock = pygame.time.Clock()

    simulation = Simulation(window, width, height)
    simulation.run()

    pygame.quit()


if __name__ == "__main__":
    main()
