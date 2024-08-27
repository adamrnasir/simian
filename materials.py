import random
import time
from abc import ABC, abstractmethod
from particle import Particle
from pymunk import Vec2d, Space  # Add this import
from typing import Tuple, List


class Material(ABC):
    COLOR = (0, 0, 0)
    MASS = 1.0
    RADIUS = 5
    ELASTICITY = 0.1
    FRICTION = 0.5
    COLLISION_TYPE = 0

    @classmethod
    @abstractmethod
    def create_particle(cls, space, x, y):
        particle = Particle(
            space,
            x,
            y,
            cls.MASS,
            cls.RADIUS,
            cls.COLOR,
            collision_type=cls.COLLISION_TYPE,
            material=cls,  # Add this line
        )
        return particle

    @classmethod
    def create_particles(cls, space, x, y, count=10, spread=5):
        particles = []
        for _ in range(count):
            px = x + random.uniform(-spread, spread)
            py = y + random.uniform(-spread, spread)
            particle = cls.create_particle(space, px, py)
            if particle is not None:
                particle.body.velocity = (
                    random.uniform(-spread, spread),
                    random.uniform(-spread, spread),
                )
                particles.append(particle)
        return particles

    @classmethod
    @abstractmethod
    def update_particle(cls, particle, dt, gravity: Tuple[float, float]):
        pass

    @classmethod
    @abstractmethod
    def handle_collision(
        cls, space: Space, particle: Particle, other_particle: Particle
    ) -> List[Particle]:
        pass


class Fluid(Material):
    @classmethod
    def create_particles(cls, space, x, y):
        particles = []
        for _ in range(10):
            px = x + random.uniform(-5, 5)
            py = y + random.uniform(-5, 5)
            particle = cls.create_particle(space, px, py)
            if particle is not None:  # Add this check
                particle.body.velocity = (
                    random.uniform(-50, 50),
                    random.uniform(-50, 50),
                )
                particles.append(particle)
        return particles


class Rock(Material):
    COLOR = (128, 128, 128)
    MASS = 200
    RADIUS = 30
    COLLISION_TYPE = 4

    @classmethod
    def create_particle(cls, space, x, y):
        particle = super().create_particle(space, x, y)
        # Add any Rock-specific properties here if needed
        return particle

    @classmethod
    def create_particles(cls, space, x, y):
        return super().create_particles(space, x, y, count=1, spread=0)

    @classmethod
    def update_particle(cls, particle, dt, gravity):
        # Rocks are fully affected by gravity
        particle.body.velocity += Vec2d(*gravity) * dt
        return True

    @classmethod
    def handle_collision(
        cls, space: Space, particle: Particle, other_particle: Particle
    ) -> List[Particle]:
        return []  # Rock doesn't react to collisions


class Water(Fluid):
    COLOR = (0, 0, 255)
    COLLISION_TYPE = 2

    @classmethod
    def create_particle(cls, space, x, y):
        particle = super().create_particle(space, x, y)
        particle.shape.elasticity = 0.9999
        particle.shape.friction = 0.0
        return particle

    @classmethod
    def update_particle(cls, particle, dt, gravity):
        # Water is fully affected by gravity
        particle.body.velocity += Vec2d(*gravity) * dt
        return True

    @classmethod
    def handle_collision(
        cls, space: Space, particle: Particle, other_particle: Particle
    ) -> List[Particle]:
        if other_particle.material == Fire:
            particle.to_remove = (
                True  # Flag for removal instead of removing immediately
            )
            return [
                Steam.create_particle(
                    space, particle.body.position.x, particle.body.position.y
                )
            ]

        return []


class Fire(Fluid):
    COLOR = (255, 69, 0)
    COLLISION_TYPE = 3
    MASS = 0.5
    RADIUS = 3
    UPWARD_FORCE = 1100

    @classmethod
    def create_particle(cls, space, x, y):
        particle = super().create_particle(space, x, y)
        particle.lifetime = random.uniform(1, 2)
        particle.body.velocity = Vec2d(
            random.uniform(-50, 50), random.uniform(-100, -50)
        )
        particle.body.velocity_func = cls.update_velocity
        return particle

    @staticmethod
    def update_velocity(body, gravity, damping, dt):
        # Calculate the net force (upward force - gravity)
        net_force = Vec2d(0, -Fire.UPWARD_FORCE) + gravity

        # Apply the net force to the particle
        body.velocity += net_force * dt

        # Add some random horizontal movement
        body.velocity += Vec2d(random.uniform(-10, 10), 0) * dt

    @classmethod
    def update_particle(cls, particle, dt, gravity):
        age = time.time() - particle.creation_time
        if age > particle.lifetime:
            return False  # This signals that the particle should be removed

        # Update color to fade to red
        particle.color = (255, int(255 * (1 - age / particle.lifetime)), 0)
        return True  # This signals that the particle should be kept

    @classmethod
    def handle_collision(
        cls, space: Space, particle: Particle, other_particle: Particle
    ) -> List[Particle]:
        if isinstance(other_particle, Water):
            space.remove(particle.body, particle.shape)
            particle.to_remove = True
        return []


class Steam(Fluid):
    COLOR = (200, 200, 200, 200)
    MASS = 0.1
    RADIUS = 4
    COLLISION_TYPE = 4

    @classmethod
    def create_particle(cls, space, x, y):
        particle = super().create_particle(space, x, y)
        particle.lifetime = random.uniform(1, 3)
        particle.body.velocity = Vec2d(random.uniform(-10, 10), random.uniform(-10, 10))
        particle.body.velocity_func = cls.update_velocity
        return particle

    @staticmethod
    def update_velocity(body, gravity, damping, dt):
        # Add jittery motion to steam
        jitter = Vec2d(random.uniform(-2, 2), random.uniform(-2, 2))
        body.velocity = jitter - gravity * dt  # Counteract gravity

    @classmethod
    def update_particle(cls, particle, dt, gravity):
        age = time.time() - particle.creation_time
        if age > particle.lifetime:
            return False

        # Update color to fade to transparent
        alpha = int(200 * (1 - age / particle.lifetime))
        particle.color = (*particle.color[:3], alpha)
        return True

    @classmethod
    def handle_collision(
        cls, space: Space, particle: Particle, other_particle: Particle
    ) -> List[Particle]:
        return []  # Steam doesn't react to collisions
