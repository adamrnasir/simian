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
    SPREAD = 5
    VELOCITY_SPREAD = 10

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
            elasticity=cls.ELASTICITY,
            friction=cls.FRICTION,
            material=cls,  # Add this line
        )
        return particle

    @classmethod
    def create_particles(cls, space, x, y, count=10):
        particles = []
        for _ in range(count):
            px = x + random.uniform(-cls.SPREAD, cls.SPREAD)
            py = y + random.uniform(-cls.SPREAD, cls.SPREAD)
            particle = cls.create_particle(space, px, py)
            if particle is not None:
                particle.body.velocity = (
                    random.uniform(-cls.VELOCITY_SPREAD, cls.VELOCITY_SPREAD),
                    random.uniform(-cls.VELOCITY_SPREAD, cls.VELOCITY_SPREAD),
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


class Ball(Material):
    COLOR = (128, 128, 128)
    MASS = 200
    RADIUS = 30
    COLLISION_TYPE = 4
    SPREAD = 0
    VELOCITY_SPREAD = 0

    @classmethod
    def create_particle(cls, space, x, y):
        particle = super().create_particle(space, x, y)
        # Add any Ball-specific properties here if needed
        return particle

    @classmethod
    def create_particles(cls, space, x, y):
        return super().create_particles(space, x, y, count=1)

    @classmethod
    def update_particle(cls, particle, dt, gravity):
        # Balls are fully affected by gravity
        particle.body.velocity += Vec2d(*gravity) * dt
        return True

    @classmethod
    def handle_collision(
        cls, space: Space, particle: Particle, other_particle: Particle
    ) -> List[Particle]:
        return []  # Ball doesn't react to collisions


class Water(Fluid):
    COLOR = (0, 0, 255)
    COLLISION_TYPE = 2
    RADIUS = 2
    ELASTICITY = 0.9999
    FRICTION = 0.0

    @classmethod
    def create_particle(cls, space, x, y):
        return super().create_particle(space, x, y)

    @classmethod
    def update_particle(cls, particle, dt, gravity):
        return True

    @classmethod
    def handle_collision(
        cls, space: Space, particle: Particle, other_particle: Particle
    ) -> List[Particle]:
        if other_particle.material == Fire or other_particle.material == Lava:
            particle.to_remove = True
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
        if other_particle.material == Water:
            particle.to_remove = True
        return []


class Steam(Fluid):
    COLOR = (200, 200, 200, 200)
    MASS = 0.1
    RADIUS = 4
    COLLISION_TYPE = 4
    VELOCITY_SPREAD = 100

    @classmethod
    def create_particle(cls, space, x, y):
        particle = super().create_particle(space, x, y)
        particle.lifetime = random.uniform(1, 3)
        particle.body.velocity_func = cls.update_velocity
        return particle

    @staticmethod
    def update_velocity(body, gravity, damping, dt):
        # Add jittery motion to steam
        jitter = Vec2d(body.velocity.x + random.uniform(-2, 2), -10)
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


class Gravel(Material):
    COLOR = (139, 69, 19)  # Brown color
    MASS = 5.0
    RADIUS = 4
    ELASTICITY = 0.2  # Low elasticity
    FRICTION = 0.8  # High friction
    COLLISION_TYPE = 5

    @classmethod
    def create_particle(cls, space, x, y):
        return super().create_particle(space, x, y)

    @classmethod
    def update_particle(cls, particle, dt, gravity):
        # Gravel is fully affected by gravity
        particle.body.velocity += Vec2d(*gravity) * dt
        return True

    @classmethod
    def handle_collision(
        cls, space: Space, particle: Particle, other_particle: Particle
    ) -> List[Particle]:
        return []  # Gravel doesn't react to collisions


class Sand(Material):
    COLOR = (216, 216, 191)
    MASS = 2.0
    RADIUS = 3
    COLLISION_TYPE = 6
    FRICTION = 1.0
    ELASTICITY = 0.1

    @classmethod
    def create_particle(cls, space, x, y):
        particle = super().create_particle(space, x, y)
        return particle

    @classmethod
    def update_particle(cls, particle, dt, gravity):
        # Sand is fully affected by gravity
        particle.body.velocity += Vec2d(*gravity) * dt
        return True

    @classmethod
    def handle_collision(
        cls, space: Space, particle: Particle, other_particle: Particle
    ) -> List[Particle]:
        return []


class Lava(Fluid):
    COLOR = (255, 0, 0)
    MASS = 1.0
    RADIUS = 3
    COLLISION_TYPE = 3
    FRICTION = 0.5
    ELASTICITY = 0.1

    @classmethod
    def create_particle(cls, space, x, y):
        return super().create_particle(space, x, y)

    @classmethod
    def update_particle(cls, particle, dt, gravity):
        return True

    @classmethod
    def handle_collision(
        cls, space: Space, particle: Particle, other_particle: Particle
    ) -> List[Particle]:
        if other_particle.material == Water:
            print("lava and water")
            particle.to_remove = True
            return [
                Gravel.create_particle(
                    space, particle.body.position.x, particle.body.position.y
                )
            ]
        return []
