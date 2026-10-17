import pygame
from typing import List, Tuple, Optional


class Button:
    def __init__(self, x, y, width, height, text, color):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color = color

    def draw(self, window):
        pygame.draw.rect(window, self.color, self.rect)
        font = pygame.font.Font(None, 24)
        text_surface = font.render(self.text, True, (255, 255, 255))
        text_rect = text_surface.get_rect(center=self.rect.center)
        window.blit(text_surface, text_rect)


class UI:
    def __init__(self, window, width, height, space):
        self.window = window
        self.width = width
        self.height = height
        self.buttons: List[Button] = []
        self.selected_material = "Ball"
        self.stream_active = False
        self.last_paint_position: Optional[Tuple[float, float]] = None
        self.space = space

    def create_buttons(self, materials):
        y_offset = 20
        for material, color in materials.items():
            self.buttons.append(Button(20, y_offset, 100, 40, material, color))
            y_offset += 50

    def handle_events(self, events: List[pygame.event.Event]) -> None:
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN:
                self.handle_mouse_down(event)
            elif event.type == pygame.MOUSEBUTTONUP:
                self.handle_mouse_up(event)

    def handle_mouse_down(self, event: pygame.event.Event) -> None:
        if event.button == 1:  # Left mouse button
            x, y = event.pos
            for button in self.buttons:
                if button.rect.collidepoint(x, y):
                    self.selected_material = button.text
                    return

            self.stream_active = True
            self.last_paint_position = None

    def handle_mouse_up(self, event: pygame.event.Event) -> None:
        if event.button == 1:  # Left mouse button
            self.stream_active = False
            self.last_paint_position = None

    def draw(self, total_particles: int) -> None:
        for button in self.buttons:
            button.draw(self.window)
        self.draw_selected_material()
        self.draw_particle_count(total_particles)

    def draw_selected_material(self) -> None:
        for button in self.buttons:
            if button.text == self.selected_material:
                pygame.draw.rect(self.window, (255, 255, 0), button.rect, 3)

    def draw_particle_count(self, total_particles: int) -> None:
        font = pygame.font.Font(None, 36)
        text = font.render(f"Particles: {total_particles}", True, (0, 0, 0))
        self.window.blit(text, (256, 10))

    def get_mouse_position(self) -> tuple[int, int]:
        return pygame.mouse.get_pos()
