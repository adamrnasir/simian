import pygame
from simulation import Simulation
from render import Renderer
from materials import Sand, Water, Lava, Steam, Stone, Mud
import asyncio
import cProfile

# Add this constant at the top of the file
GRID_SIZE = 100  # Increase this value for a larger grid


# Add this new class for the GUI
class MaterialButton:
    def __init__(self, x, y, width, height, material, color):
        self.rect = pygame.Rect(x, y, width, height)
        self.material = material
        self.color = color

    def draw(self, window):
        pygame.draw.rect(window, self.color, self.rect)
        font = pygame.font.Font(None, 24)
        text_surface = font.render(self.material.__name__, True, (255, 255, 255))
        text_rect = text_surface.get_rect(center=self.rect.center)
        window.blit(text_surface, text_rect)


def main():
    pygame.init()
    # Increase the window size and use GRID_SIZE
    width, height = GRID_SIZE, GRID_SIZE
    window = pygame.display.set_mode((800, 800))  # Larger window size

    pygame.display.set_caption("Powder Sim")

    simulation = Simulation(width, height)
    renderer = Renderer(window, simulation)

    clock = pygame.time.Clock()
    running = True

    brush_size = 1

    # Create material buttons using colors from the renderer
    materials = [Sand, Water, Lava, Steam, Stone, Mud]
    buttons = []
    for i, material in enumerate(materials):
        color = renderer.colors[material.id]
        buttons.append(MaterialButton(10, 10 + i * 50, 100, 40, material, color))

    selected_material = Sand()
    font = pygame.font.Font(None, 36)

    # Set up profiler
    profiler = cProfile.Profile()
    profiler.enable()

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                profiler.disable()
                profiler.print_stats(sort="time")
                profiler.dump_stats("profile.pstats")
            elif event.type == pygame.MOUSEBUTTONDOWN:
                x, y = pygame.mouse.get_pos()
                for button in buttons:
                    if button.rect.collidepoint(x, y):
                        selected_material = button.material()
                        break
            # If the left bracket is pressed, decrease brush size
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_DOWN:
                    print(brush_size)
                    brush_size = max(1, brush_size - 1)
                elif event.key == pygame.K_UP:
                    print(brush_size)
                    brush_size = min(10, brush_size + 1)
            elif pygame.mouse.get_pressed()[0]:
                x, y = pygame.mouse.get_pos()
                grid_x = int(x * simulation.width // window.get_width())
                grid_y = int(y * simulation.height // window.get_height())
                simulation.add_material(grid_x, grid_y, selected_material, brush_size)

        asyncio.run(simulation.update())
        asyncio.run(renderer.render())

        # Draw material buttons
        for button in buttons:
            button.draw(window)

        # Highlight selected material
        for button in buttons:
            if isinstance(selected_material, button.material):
                pygame.draw.rect(window, (255, 255, 0), button.rect, 3)

        # Render material selector text
        selector_text = f"Selected: {selected_material.__class__.__name__}"
        text_surface = font.render(selector_text, True, (255, 255, 255))
        window.blit(text_surface, (120, 10))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    main()
