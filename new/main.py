import pygame
from simulation import Simulation
from render import Renderer
from materials import Sand, Water, Lava, Steam, Stone
import cProfile
import pstats
import asyncio

# Add this constant at the top of the file
GRID_SIZE = 100  # Increase this value for a larger grid


def main():
    pygame.init()
    # Increase the window size and use GRID_SIZE
    width, height = GRID_SIZE, GRID_SIZE
    window = pygame.display.set_mode((800, 800))  # Larger window size

    pygame.display.set_caption("Quantized Particle Physics Simulation")

    simulation = Simulation(width, height)
    renderer = Renderer(window, simulation)

    clock = pygame.time.Clock()
    running = True

    # Create a Profile object
    pr = cProfile.Profile()

    # Update material selector
    selected_material = Sand()
    font = pygame.font.Font(None, 36)

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                # Save profiling results to a file
                # with open("profiling_results.txt", "w") as file:
                #     ps = pstats.Stats(pr, stream=file).sort_stats("cumulative")
                #     ps.print_stats()
            elif pygame.mouse.get_pressed()[0]:
                x, y = pygame.mouse.get_pos()
                grid_x = x * simulation.width // window.get_width()
                grid_y = y * simulation.height // window.get_height()
                simulation.add_material(grid_x, grid_y, selected_material, 5)
            elif event.type == pygame.KEYDOWN:
                # Update material selection
                if event.key == pygame.K_s:
                    selected_material = Sand()
                elif event.key == pygame.K_w:
                    selected_material = Water()
                elif event.key == pygame.K_l:
                    selected_material = Lava()
                elif event.key == pygame.K_t:
                    selected_material = Steam()
                elif event.key == pygame.K_r:
                    selected_material = Stone()

        # Start profiling
        # pr.enable()

        asyncio.run(simulation.update())
        asyncio.run(renderer.render())

        # Render material selector
        selector_text = f"Selected: {selected_material.__class__.__name__}"
        text_surface = font.render(selector_text, True, (255, 255, 255))
        window.blit(text_surface, (10, 10))

        # Stop profiling
        # pr.disable()

        pygame.display.flip()
        clock.tick(120)

    pygame.quit()


if __name__ == "__main__":
    main()
