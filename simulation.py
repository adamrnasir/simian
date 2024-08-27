import pygame
import pymunk
import pymunk.pygame_util
import time
from typing import List, Dict
from particle import Particle
from materials import Ball, Water, Fire, Steam, Gravel, Sand, Lava
from ui import Button


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
        }
        self.material_classes = {
            "Ball": Ball,
            "Water": Water,
            "Fire": Fire,
            "Steam": Steam,
            "Gravel": Gravel,  # Add Gravel to material_classes dictionary
            "Sand": Sand,  # Add Sand to material_classes dictionary
            "Lava": Lava,  # Add Lava to material_classes dictionary
        }
        self.selected_material = "Ball"
        self.create_walls()
        self.create_ui()
        self.setup_collision_handler()
        self.stream_active = False
        self.stream_timer = 0
        self.last_update_time = time.time()

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
        self.buttons = [
            Button(20, 20, 100, 40, "Ball", Ball.COLOR),
            Button(20, 70, 100, 40, "Water", Water.COLOR),
            Button(20, 120, 100, 40, "Fire", Fire.COLOR),
            Button(20, 170, 100, 40, "Steam", Steam.COLOR),
            Button(20, 220, 100, 40, "Gravel", Gravel.COLOR),  # Add Gravel button
            Button(20, 270, 100, 40, "Sand", Sand.COLOR),  # Add Sand button
            Button(20, 320, 100, 40, "Lava", Lava.COLOR),  # Add Lava button
        ]

    def setup_collision_handler(self):
        for i in range(2, 6):  # Update range to include Gravel's collision type (5)
            for j in range(i + 1, 6):
                handler = self.space.add_collision_handler(i, j)
                handler.begin = self.handle_collision

    def handle_collision(self, arbiter, space, data):
        shape_a, shape_b = arbiter.shapes
        particle_a = shape_a.body.particle
        particle_b = shape_b.body.particle

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
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self.handle_mouse_down(event)
                elif event.type == pygame.MOUSEBUTTONUP:
                    self.handle_mouse_up(event)

            self.update()
            self.draw()
            pygame.display.flip()
            self.space.step(1 / 60.0)

    def handle_mouse_down(self, event):
        if event.button == 1:  # Left mouse button
            x, y = event.pos
            for button in self.buttons:
                if button.rect.collidepoint(x, y):
                    self.selected_material = button.text
                    return

            if self.selected_material == "Ball":
                self.create_particles(x, y)
            else:
                self.stream_active = True
                self.stream_timer = time.time()

    def handle_mouse_up(self, event):
        if event.button == 1:  # Left mouse button
            self.stream_active = False

    def create_particles(self, x, y):
        material_class = self.material_classes[self.selected_material]
        new_particles = material_class.create_particles(self.space, x, y)
        self.particles[self.selected_material].extend(
            [p for p in new_particles if p is not None]
        )

    def update(self):
        current_time = time.time()
        dt = current_time - self.last_update_time
        self.last_update_time = current_time

        self.remove_out_of_bounds_particles()
        self.remove_flagged_particles()  # Add this line
        self.update_particles(
            dt
        )  # Call this method to update and remove expired particles
        self.limit_particles()

        if self.stream_active and time.time() - self.stream_timer > 0.01:
            x, y = pygame.mouse.get_pos()
            self.create_particles(x, y)
            self.stream_timer = time.time()

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
        for button in self.buttons:
            button.draw(self.window)
        self.draw_selected_material()
        self.draw_particle_count()

    def draw_selected_material(self):
        for button in self.buttons:
            if button.text == self.selected_material:
                pygame.draw.rect(self.window, (255, 255, 0), button.rect, 3)

    def draw_particle_count(self):
        font = pygame.font.Font(None, 36)
        total_particles = sum(len(particles) for particles in self.particles.values())
        text = font.render(f"Particles: {total_particles}", True, (0, 0, 0))
        self.window.blit(text, (256, 10))

    def remove_flagged_particles(self):
        for material, particle_list in self.particles.items():
            particles_to_remove = [p for p in particle_list if p.to_remove]
            for particle in particles_to_remove:
                self.space.remove(particle.body, particle.shape)
                particle_list.remove(particle)
