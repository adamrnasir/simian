import pygame
import pymunk
import pymunk.pygame_util
import time
from typing import List, Dict
from particle import Particle
from materials import (
    Ball,
    Water,
    Fire,
    Steam,
    Gravel,
    Sand,
    Lava,
    Paint,
    Wood,
)  # Add Paint import
from ui import UI
import random


class Simulation:
    def __init__(self, window, width, height):
        self.window = window
        self.width = width
        self.height = height
        self.space = pymunk.Space()
        self.space.gravity = (0, 980)
        self.draw_options = pymunk.pygame_util.DrawOptions(window)
        self.particles: Dict[str, List[Particle]] = {
            "Ball": [],
            "Water": [],
            "Fire": [],
            "Steam": [],
            "Gravel": [],  # Add Gravel to particles dictionary
            "Sand": [],  # Add Sand to particles dictionary
            "Lava": [],  # Add Lava to particles dictionary
            "Paint": [],  # Add Paint to particles dictionary
            "Wood": [],  # Add Wood to particles dictionary
        }
        self.material_classes = {
            "Ball": Ball,
            "Water": Water,
            "Fire": Fire,
            "Steam": Steam,
            "Gravel": Gravel,  # Add Gravel to material_classes dictionary
            "Sand": Sand,  # Add Sand to material_classes dictionary
            "Lava": Lava,  # Add Lava to material_classes dictionary
            "Paint": Paint,  # Add Paint to material_classes dictionary
            "Wood": Wood,  # Add Wood to material_classes dictionary
        }
        self.ui = UI(window, width, height, self.space)
        self.create_ui()
        self.create_walls()
        self.setup_collision_handler()
        self.stream_timer = 0
        self.last_update_time = time.time()
        self.grid_size = 4  # Change grid size to match the smallest particle size
        self.fire_spread_timer = 0
        self.fire_spread_interval = 0.1  # Spread fire every 0.1 seconds
        self.max_paint_distance = 10  # Maximum distance between paint particles

    def create_walls(self):
        wall_thickness = 20
        body = pymunk.Body(body_type=pymunk.Body.STATIC)
        walls = [
            pymunk.Segment(body, (0, 0), (self.width, 0), wall_thickness),
            pymunk.Segment(
                body, (self.width, 0), (self.width, self.height), wall_thickness
            ),
            pymunk.Segment(
                body, (self.width, self.height), (0, self.height), wall_thickness
            ),
            pymunk.Segment(body, (0, self.height), (0, 0), wall_thickness),
        ]
        for wall in walls:
            wall.elasticity = 0.8
            wall.friction = 0.1
            wall.collision_type = 1
        self.space.add(body, *walls)

    def create_ui(self):
        materials = {
            "Ball": Ball.COLOR,
            "Water": Water.COLOR,
            "Fire": Fire.COLOR,
            "Steam": Steam.COLOR,
            "Gravel": Gravel.COLOR,
            "Sand": Sand.COLOR,
            "Lava": Lava.COLOR,
            "Paint": Paint.COLOR,
            "Wood": Wood.COLOR,
        }
        self.ui.create_buttons(materials)

    def setup_collision_handler(self):
        for i in range(2, 8):  # Update range to include Paint's collision type (7)
            for j in range(i + 1, 8):
                handler = self.space.add_collision_handler(i, j)
                handler.begin = self.handle_collision

    def handle_collision(self, arbiter, space, data):
        shape_a, shape_b = arbiter.shapes
        particle_a = shape_a.body.particle
        particle_b = shape_b.body.particle

        # If either particle is Paint, don't process the collision further
        if isinstance(particle_a.material, Paint) or isinstance(
            particle_b.material, Paint
        ):
            return True

        new_particles = []
        particles_to_remove = []

        new_particles.extend(
            particle_a.material.handle_collision(space, particle_a, particle_b)
        )
        new_particles.extend(
            particle_b.material.handle_collision(space, particle_b, particle_a)
        )

        # Check if particles should be removed
        if particle_a.body not in space.bodies:
            particles_to_remove.append(particle_a)
        if particle_b.body not in space.bodies:
            particles_to_remove.append(particle_b)

        # Remove particles from the simulation's particle lists
        for particle in particles_to_remove:
            material_name = particle.material.__name__
            if material_name in self.particles:
                self.particles[material_name] = [
                    p for p in self.particles[material_name] if p != particle
                ]

        # Add new particles to the simulation
        for new_particle in new_particles:
            material_name = new_particle.material.__name__
            if material_name in self.particles:
                self.particles[material_name].append(new_particle)
            else:
                print(f"Warning: Unknown material {material_name}")

        return True

    def run(self):
        running = True
        while running:
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    running = False

            self.ui.handle_events(events)
            self.update()
            self.draw()
            pygame.display.flip()
            self.space.step(1 / 60.0)

    def update(self):
        current_time = time.time()
        dt = current_time - self.last_update_time
        self.last_update_time = current_time

        self.remove_out_of_bounds_particles()
        self.remove_flagged_particles()
        self.update_particles(dt)
        self.limit_particles()

        self.fire_spread_timer += dt
        if self.fire_spread_timer >= self.fire_spread_interval:
            self.spread_fire()
            self.fire_spread_timer = 0

        if self.ui.stream_active:
            x, y = self.ui.get_mouse_position()
            self.create_particles(x, y)

    def remove_out_of_bounds_particles(self):
        for material, particle_list in self.particles.items():
            self.particles[material] = [
                p for p in particle_list if self.is_in_bounds(p)
            ]

    def is_in_bounds(self, particle):
        x, y = particle.body.position
        return 0 <= x <= self.width and 0 <= y <= self.height

    def update_particles(self, dt):
        gravity = self.space.gravity
        for material_name, particle_list in self.particles.items():
            material_class = self.material_classes[material_name]
            updated_particles = []
            for particle in particle_list:
                if material_class.update_particle(particle, dt, gravity):
                    updated_particles.append(particle)
                else:
                    # Remove the particle from the space
                    self.space.remove(particle.body, particle.shape)
            self.particles[material_name] = updated_particles

    def limit_particles(self):
        total_particles = sum(len(particles) for particles in self.particles.values())
        if total_particles > 10000:
            remove_count = total_particles - 10000
            for material, particle_list in self.particles.items():
                if remove_count <= 0:
                    break
                if len(particle_list) > remove_count:
                    for particle in particle_list[:remove_count]:
                        self.space.remove(particle.body, particle.shape)
                    self.particles[material] = particle_list[remove_count:]
                    remove_count = 0
                else:
                    remove_count -= len(particle_list)
                    for particle in particle_list:
                        self.space.remove(particle.body, particle.shape)
                    self.particles[material] = []

    def draw(self):
        self.window.fill((0, 0, 0))
        for particle_list in self.particles.values():
            for particle in particle_list:
                particle.draw(self.window)
        total_particles = sum(len(particles) for particles in self.particles.values())
        self.ui.draw(total_particles)

    def remove_flagged_particles(self):
        for material, particle_list in self.particles.items():
            particles_to_remove = [p for p in particle_list if p.to_remove]
            for particle in particles_to_remove:
                self.space.remove(particle.body, particle.shape)
                particle_list.remove(particle)

    def spread_fire(self):
        new_fire_particles = []
        for fire_particle in self.particles["Fire"]:
            if random.random() < 0.1:  # 10% chance to spread fire
                nearby_particles = self.find_nearby_particles(fire_particle, 20)
                for nearby_particle in nearby_particles:
                    if isinstance(nearby_particle.material, Wood):
                        new_fire = Fire.create_particle(
                            self.space,
                            nearby_particle.body.position.x,
                            nearby_particle.body.position.y,
                        )
                        new_fire_particles.append(new_fire)
                        nearby_particle.to_remove = True

        self.particles["Fire"].extend(new_fire_particles)

    def find_nearby_particles(self, particle, radius):
        nearby = []
        for material, particle_list in self.particles.items():
            for other in particle_list:
                if other != particle:
                    distance = particle.body.position.get_distance(other.body.position)
                    if distance <= radius:
                        nearby.append(other)
        return nearby

    def create_particles(self, x, y):
        material_class = self.material_classes[self.ui.selected_material]
        if issubclass(material_class, Paint):
            self.create_paint_stroke(x, y, material_class)
        else:
            # Quantize the initial position
            qx, qy = self.quantize_position(x, y)
            new_particles = material_class.create_particles(self.space, qx, qy)

            # Quantize the position of each new particle
            for particle in new_particles:
                if particle is not None:
                    px, py = self.quantize_position(
                        particle.body.position.x, particle.body.position.y
                    )
                    particle.body.position = pymunk.Vec2d(px, py)

            self.particles[self.ui.selected_material].extend(
                [p for p in new_particles if p is not None]
            )

    def create_paint_stroke(self, end_x, end_y, material_class):
        if self.ui.last_paint_position is None:
            self.ui.last_paint_position = (float(end_x), float(end_y))
            self.create_paint_particles(end_x, end_y, end_x, end_y, material_class)
        else:
            start_x, start_y = self.ui.last_paint_position
            distance = ((end_x - start_x) ** 2 + (end_y - start_y) ** 2) ** 0.5

            if distance > self.max_paint_distance:
                steps = int(distance / self.max_paint_distance)
                for i in range(1, steps + 1):
                    t = i / steps
                    x = start_x + t * (end_x - start_x)
                    y = start_y + t * (end_y - start_y)
                    self.create_paint_particles(x, y, x, y, material_class)
            else:
                self.create_paint_particles(
                    start_x, start_y, end_x, end_y, material_class
                )

        self.ui.last_paint_position = (float(end_x), float(end_y))

    def create_paint_particles(
        self, start_x, start_y, end_x, end_y, material_class, num_particles=1
    ):
        for i in range(num_particles):
            t = i / num_particles
            x = start_x + t * (end_x - start_x)
            y = start_y + t * (end_y - start_y)
            qx, qy = self.quantize_position(x, y)
            new_particles = material_class.create_particles(self.space, qx, qy, count=1)
            self.particles[self.ui.selected_material].extend(new_particles)

    def quantize_position(self, x, y):
        # Quantize the position to the nearest grid point
        return (
            round(x / self.grid_size) * self.grid_size,
            round(y / self.grid_size) * self.grid_size,
        )
