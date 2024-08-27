import pygame
import pymunk
import time


class Particle:
    def __init__(
        self,
        space,
        x,
        y,
        mass,
        radius,
        color,
        elasticity=0.1,
        friction=0.5,
        collision_type=0,
        lifetime=None,
        gravity_scale=0.0,
    ):
        self.mass = mass
        self.radius = radius
        self.color = color
        self.lifetime = lifetime
        self.creation_time = time.time()

        moment = pymunk.moment_for_circle(mass, 0, radius)
        body = pymunk.Body(mass, moment)

        body.position = x, y
        body.gravity_scale = gravity_scale
        self.body = body
        self.shape = pymunk.Circle(self.body, radius)
        self.shape.elasticity = elasticity
        self.shape.friction = friction
        self.shape.collision_type = collision_type

        space.add(self.body, self.shape)

    def draw(self, window):
        position = self.body.position
        if isinstance(self.color, tuple) and len(self.color) == 4:
            surface = pygame.Surface(
                (int(self.radius * 2), int(self.radius * 2)), pygame.SRCALPHA
            )
            pygame.draw.rect(
                surface,
                self.color,
                (
                    int(self.radius),
                    int(self.radius),
                    int(self.radius),
                    int(self.radius),
                ),
            )
            window.blit(
                surface, (int(position.x - self.radius), int(position.y - self.radius))
            )
        else:
            pygame.draw.rect(
                window,
                self.color,
                (
                    int(position.x - self.radius),
                    int(position.y - self.radius),
                    int(self.radius * 2),
                    int(self.radius * 2),
                ),
            )
