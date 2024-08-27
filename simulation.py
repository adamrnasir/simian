import pygame
import pymunk
import pymunk.pygame_util
import time
from typing import List, Dict
from particle import Particle
from materials import Rock, Water, Fire, Steam, Material
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
            "Rock": [],
            "Water": [],
            "Fire": [],
            "Steam": [],
        }
        self.material_classes = {
            "Rock": Rock,
            "Water": Water,
            "Fire": Fire,
            "Steam": Steam,
        }
        self.selected_material = "Rock"
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
            Button(20, 20, 100, 40, "Rock", Rock.COLOR),
            Button(20, 70, 100, 40, "Water", Water.COLOR),
            Button(20, 120, 100, 40, "Fire", Fire.COLOR),
            Button(20, 170, 100, 40, "Steam", Steam.COLOR),
        ]

    def setup_collision_handler(self):
        handler = self.space.add_collision_handler(2, 3)  # 2 for water, 3 for fire
        handler.begin = self.handle_water_fire_collision

    def handle_water_fire_collision(self, arbiter, space, data):
        water_shape, fire_shape = arbiter.shapes
        water_body, fire_body = water_shape.body, fire_shape.body

        self.space.remove(water_body, water_shape)
        self.space.remove(fire_body, fire_shape)

        water_pos = water_body.position
        for _ in range(1):
            steam = Steam.create_particle(self.space, water_pos.x, water_pos.y)
            self.particles["Steam"].append(steam)

        self.particles["Water"] = [
            p for p in self.particles["Water"] if p.body not in (water_body, fire_body)
        ]
        self.particles["Fire"] = [
            p for p in self.particles["Fire"] if p.body not in (water_body, fire_body)
        ]

        return False

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

            if self.selected_material == "Rock":
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
        self.window.fill((255, 255, 255))
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
        self.window.blit(text, (10, 10))
