import pygame
import pymunk
import time
import math


class Particle:
    def __init__(
        self,
        space,
        x,
        y,
        mass,
        size,
        color,
        elasticity=0.5,
        friction=0.5,
        collision_type=0,
        lifetime=None,
        material=None,
    ):
        self.size = size  # Change radius to size
        self.body = pymunk.Body(
            mass=mass, moment=pymunk.moment_for_box(mass, (size, size))
        )
        self.body.position = x, y
        self.shape = pymunk.Poly.create_box(self.body, (size, size))
        self.shape.elasticity = elasticity
        self.shape.friction = friction
        self.shape.collision_type = collision_type
        self.color = color
        self.creation_time = time.time()
        self.lifetime = lifetime
        self.body.particle = self
        self.material = material
        self.to_remove = False
        space.add(self.body, self.shape)

    def draw(self, window):
        position = self.body.position
        angle = -self.body.angle  # Pymunk uses opposite rotation direction to Pygame

        # Create a surface for the particle
        surface = pygame.Surface((int(self.size), int(self.size)), pygame.SRCALPHA)
        
        # Draw the particle on the surface
        if isinstance(self.color, tuple) and len(self.color) == 4:
            pygame.draw.rect(surface, self.color, (0, 0, int(self.size), int(self.size)))
        else:
            pygame.draw.rect(surface, self.color, (0, 0, int(self.size), int(self.size)))

        # Rotate the surface
        rotated_surface = pygame.transform.rotate(surface, math.degrees(angle))
        
        # Get the new rect and calculate the position to blit
        rot_rect = rotated_surface.get_rect()
        blit_pos = (int(position.x - rot_rect.width / 2), int(position.y - rot_rect.height / 2))

        # Draw the rotated surface
        window.blit(rotated_surface, blit_pos)
