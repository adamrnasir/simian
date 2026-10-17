import cProfile

import pygame
from materials import Lava, Mud, Sand, Steam, Stone, Water
from render import Renderer
from simulation import Simulation

GRID_SIZE = 100  # Adjust as needed


class MaterialButton:
    def __init__(self, x, y, width, height, material, color):
        self.rect = pygame.Rect(x, y, width, height)
        self.material = material
        self.color = color

    def draw(self, window):
        pygame.draw.rect(window, self.color, self.rect)
        font = pygame.font.Font(None, 24)
        text = font.render(self.material.__name__, True, (255, 255, 255))
        text_rect = text.get_rect(center=self.rect.center)
        window.blit(text, text_rect)


def main():
    pygame.init()
    width, height = GRID_SIZE, GRID_SIZE
    window = pygame.display.set_mode((800, 800))
    pygame.display.set_caption("Powder Sim")
    simulation = Simulation(width, height)
    renderer = Renderer(window, simulation)
    clock = pygame.time.Clock()
    running = True
    brush_size = 1
    materials = [Sand, Water, Lava, Steam, Stone, Mud]
    buttons = [
        MaterialButton(10, 10 + i * 50, 100, 40, m, renderer.colors[m.id])
        for i, m in enumerate(materials)
    ]
    selected_material = Sand()
    font = pygame.font.Font(None, 36)
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
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_DOWN:
                    brush_size = max(1, brush_size - 1)
                elif event.key == pygame.K_UP:
                    brush_size = min(10, brush_size + 1)
        if pygame.mouse.get_pressed()[0]:
            mx, my = pygame.mouse.get_pos()
            grid_x = int(mx * simulation.width // window.get_width())
            grid_y = int(my * simulation.height // window.get_height())
            simulation.add_material(grid_x, grid_y, selected_material, brush_size)
        simulation.update()
        renderer.render()
        for button in buttons:
            button.draw(window)
        # Highlight selected material
        for button in buttons:
            if isinstance(selected_material, button.material):
                pygame.draw.rect(window, (255, 255, 0), button.rect, 3)
        selector_text = f"Selected: {selected_material.__class__.__name__}"
        text = font.render(selector_text, True, (255, 255, 255))
        window.blit(text, (120, 10))
        pygame.display.flip()
        clock.tick(60)
    pygame.quit()


if __name__ == "__main__":
    main()
