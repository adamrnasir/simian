import pygame
import pymunk
import pymunk.pygame_util
import random
import time
from pymunk.vec2d import Vec2d
from typing import List, Tuple

# Initialize Pygame and create a window
pygame.init()
width, height = 600, 600
window = pygame.display.set_mode((width, height))
clock = pygame.time.Clock()

# Create a Pymunk space
space = pymunk.Space()
space.gravity = (0, 980)

# Remove the hollow circle creation code
radius = 100


# Create walls for the edges of the screen
def create_walls():
    walls = []
    wall_thickness = 20
    body = pymunk.Body(body_type=pymunk.Body.STATIC)
    walls.append(pymunk.Segment(body, (0, 0), (width, 0), wall_thickness))  # Top
    walls.append(
        pymunk.Segment(body, (width, 0), (width, height), wall_thickness)
    )  # Right
    walls.append(
        pymunk.Segment(body, (width, height), (0, height), wall_thickness)
    )  # Bottom
    walls.append(pymunk.Segment(body, (0, height), (0, 0), wall_thickness))  # Left

    for wall in walls:
        wall.elasticity = 0.8
        wall.friction = 0.1
        wall.collision_type = 1

    space.add(body, *walls)
    return walls


walls = create_walls()

# Add these constants for the material palette
PALETTE_X = 20
PALETTE_Y = 20
PALETTE_WIDTH = 100
PALETTE_HEIGHT = 200  # Increased to accommodate the new button
PALETTE_MARGIN = 10


# Add this function to create a button
def create_button(x, y, width, height, text, color):
    return {
        "rect": pygame.Rect(x, y, width, height),
        "text": text,
        "color": color,
    }


# Create the material palette
water_button = create_button(
    PALETTE_X,
    PALETTE_Y,
    PALETTE_WIDTH,
    PALETTE_HEIGHT // 4 - PALETTE_MARGIN // 2,
    "Water",
    (0, 0, 255),
)
rock_button = create_button(
    PALETTE_X,
    PALETTE_Y + PALETTE_HEIGHT // 4 + PALETTE_MARGIN // 2,
    PALETTE_WIDTH,
    PALETTE_HEIGHT // 4 - PALETTE_MARGIN // 2,
    "Rock",
    (128, 128, 128),
)
fire_button = create_button(
    PALETTE_X,
    PALETTE_Y + 2 * (PALETTE_HEIGHT // 4 + PALETTE_MARGIN // 2),
    PALETTE_WIDTH,
    PALETTE_HEIGHT // 4 - PALETTE_MARGIN // 2,
    "Fire",
    (255, 69, 0),  # Orange-red color for fire
)
steam_button = create_button(
    PALETTE_X,
    PALETTE_Y + 3 * (PALETTE_HEIGHT // 4 + PALETTE_MARGIN // 2),
    PALETTE_WIDTH,
    PALETTE_HEIGHT // 4 - PALETTE_MARGIN // 2,
    "Steam",
    (200, 200, 200),  # Light gray color for steam
)


# Modify the create_balls function to accept a gravity_affected parameter
def create_balls(
    positions,
    mass: float = 1.0,
    radius=5,
    elasticity=0.1,
    friction=0.5,
    velocity=(0, 0),
    color=(128, 128, 128),
    lifetime=None,
    gravity_affected=True,
) -> List[Tuple[pymunk.Body, pymunk.Shape, float, float, float, bool, int]]:
    balls = []
    current_time = time.time()
    for x, y in positions:
        ball_moment = pymunk.moment_for_circle(mass, 0, radius)
        ball_body = pymunk.Body(mass, ball_moment)
        ball_body.position = x, y
        ball_body.velocity = velocity
        ball_shape = pymunk.Circle(ball_body, radius)
        ball_shape.elasticity = elasticity
        ball_shape.friction = friction
        collision_type = (
            2 if color == (0, 0, 255) else 3 if color[0] == 255 else 4
        )  # 2 for water, 3 for fire, 4 for others
        ball_shape.collision_type = collision_type
        ball_shape.color = color
        if not gravity_affected:
            ball_body.gravity_scale = 0
        space.add(ball_body, ball_shape)
        balls.append(
            (
                ball_body,
                ball_shape,
                radius,
                lifetime,
                current_time,
                gravity_affected,
                collision_type,
            )
        )
    return balls


# Add these constants for optimization
MAX_BALLS = 10000
BATCH_SIZE = 10

# Remove the initial ball creation
balls = []

# Add this line after creating the Pygame window and before the main game loop
draw_options = pymunk.pygame_util.DrawOptions(window)


# Add this function to check for collisions between water and fire
def handle_water_fire_collision(arbiter, space, data):
    water_shape, fire_shape = arbiter.shapes
    water_body, fire_body = water_shape.body, fire_shape.body

    # Remove both water and fire particles
    space.remove(water_body, water_shape)
    space.remove(fire_body, fire_shape)

    # Create steam particles at the collision point
    water_pos = water_body.position
    for _ in range(5):  # Create 5 steam particles for each collision
        new_steam = create_balls(
            [
                (
                    water_pos.x + random.uniform(-5, 5),
                    water_pos.y + random.uniform(-5, 5),
                )
            ],
            mass=0.05,
            radius=2,
            elasticity=0.1,
            friction=0.1,
            color=(200, 200, 200, 200),  # Added alpha for transparency
            lifetime=random.uniform(2, 4),
            gravity_affected=False,
        )
        data["balls"].extend(new_steam)

    # Mark both water and fire particles for removal from the balls list
    data["to_remove"].extend([water_body, fire_body])

    return False  # Return False to ensure the collision is processed only once


# Main game loop
running = True
selected_material = "rock"
water_stream = False
fire_stream = False
steam_stream = False
water_timer = 0
fire_timer = 0
steam_timer = 0

# Add collision handler
handler = space.add_collision_handler(2, 3)  # 2 for water, 3 for fire
handler.begin = handle_water_fire_collision
handler.data["balls"] = balls
handler.data["to_remove"] = []


# Modify the drawing code to use squares again
def draw_particle(window, position, size, color):
    rect = pygame.Rect(
        int(position.x - size / 2), int(position.y - size / 2), int(size), int(size)
    )
    if len(color) == 4:  # If the color has an alpha channel (for steam)
        surface = pygame.Surface((int(size), int(size)), pygame.SRCALPHA)
        pygame.draw.rect(surface, color, surface.get_rect())
        window.blit(surface, rect)
    else:
        pygame.draw.rect(window, color, rect)


while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left mouse button
                x, y = event.pos
                if water_button["rect"].collidepoint(x, y):
                    selected_material = "water"
                elif rock_button["rect"].collidepoint(x, y):
                    selected_material = "rock"
                elif fire_button["rect"].collidepoint(x, y):
                    selected_material = "fire"
                elif steam_button["rect"].collidepoint(x, y):
                    selected_material = "steam"
                else:
                    if selected_material == "rock":
                        new_ball = create_balls(
                            [(x, y)], mass=200, radius=30, color=(128, 128, 128)
                        )  # Gray color for rock
                        balls.extend(new_ball)
                    elif selected_material == "water":
                        water_stream = True
                        water_timer = time.time()
                    elif selected_material == "fire":
                        fire_stream = True
                        fire_timer = time.time()
                    elif selected_material == "steam":
                        steam_stream = True
                        steam_timer = time.time()
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:  # Left mouse button
                water_stream = False
                fire_stream = False
                steam_stream = False

    # Clear the screen
    window.fill((255, 255, 255))

    # Remove out-of-bounds balls without replacing them
    for ball in balls[:]:
        if (
            ball[0].position.x < 0
            or ball[0].position.x > width
            or ball[0].position.y < 0
            or ball[0].position.y > height
        ):
            space.remove(ball[0], ball[1])
            balls.remove(ball)

    # Handle water stream
    if water_stream and time.time() - water_timer > 0.01:  # Spawn water every 10ms
        x, y = pygame.mouse.get_pos()
        positions = [
            (x + random.uniform(-5, 5), y + random.uniform(-5, 5))
            for _ in range(BATCH_SIZE)
        ]
        new_water = create_balls(
            positions,
            mass=1,
            radius=5,
            elasticity=0.3,
            friction=0.1,
            color=(0, 0, 255),  # Blue color for water
        )
        for ball in new_water:
            ball[0].velocity = (random.uniform(-50, 50), random.uniform(-50, 50))
        balls.extend(new_water)
        water_timer = time.time()

    # Handle fire stream
    if fire_stream and time.time() - fire_timer > 0.01:
        x, y = pygame.mouse.get_pos()
        positions = [
            (x + random.uniform(-5, 5), y + random.uniform(-5, 5))
            for _ in range(BATCH_SIZE)
        ]
        new_fire = create_balls(
            positions,
            mass=0.5,  # Reduce mass to make it lighter
            radius=3,
            elasticity=0.3,
            friction=0.1,
            color=(255, random.randint(0, 100), 0),  # Random orange-red color
            lifetime=random.uniform(2, 4),  # Increase lifetime for slower rise
        )
        for ball in new_fire:
            ball[0].velocity = (
                random.uniform(-50, 50),
                random.uniform(-100, -50),
            )  # Reduce initial upward velocity
        balls.extend(new_fire)
        fire_timer = time.time()

    # Handle steam stream
    if steam_stream and time.time() - steam_timer > 0.01:
        x, y = pygame.mouse.get_pos()
        positions = [
            (x + random.uniform(-5, 5), y + random.uniform(-5, 5))
            for _ in range(BATCH_SIZE)
        ]
        new_steam = create_balls(
            positions,
            mass=0.1,  # Very light mass
            radius=4,
            elasticity=0.1,
            friction=0.1,
            color=(200, 200, 200),  # Light gray color for steam
            lifetime=random.uniform(3, 6),  # Longer lifetime than fire
            gravity_affected=False,  # Steam is not affected by gravity
        )
        for ball in new_steam:
            ball[0].velocity = (
                random.uniform(-10, 10),
                random.uniform(-10, 10),
            )  # Initial random velocity
        balls.extend(new_steam)
        steam_timer = time.time()

    # Remove particles marked for removal
    for body in handler.data["to_remove"]:
        balls = [ball for ball in balls if ball[0] != body]
    handler.data["to_remove"].clear()

    # Update fire and steam particles
    current_time = time.time()
    for ball in balls[:]:
        if len(ball) >= 7 and ball[3] is not None:
            age = current_time - ball[4]
            if age > ball[3]:  # Remove if lifetime exceeded
                space.remove(ball[0], ball[1])
                balls.remove(ball)
            else:
                if ball[6] == 3:  # It's a fire particle
                    ball[0].velocity += (0, -20)  # Reduce upward force
                    ball[1].color = (
                        255,
                        int(255 * (1 - age / ball[3])),
                        0,
                    )  # Fade to red
                elif ball[6] == 4 and not ball[5]:  # It's a steam particle
                    # Add jittery motion to steam
                    jitter_x = random.uniform(-2, 2)
                    jitter_y = random.uniform(-2, 2)
                    ball[0].velocity = (jitter_x, jitter_y)
                    alpha = int(200 * (1 - age / ball[3]))
                    ball[1].color = (200, 200, 200, alpha)  # Fade to transparent

    # Limit the number of balls
    if len(balls) > MAX_BALLS:
        remove_count = len(balls) - MAX_BALLS
        for ball in balls[:remove_count]:
            space.remove(ball[0], ball[1])
        balls = balls[remove_count:]

    # Update physics
    space.step(1 / 60.0)

    # Draw objects
    for ball in balls:
        position = ball[0].position
        if ball[3] is not None:  # If it's a fire or steam particle
            age = current_time - ball[4]
            size = ball[2] * 2 * (1 - age / ball[3])  # Calculate the visual size
        else:
            size = ball[2] * 2  # Use the original diameter for non-fire particles
        draw_particle(window, position, size, ball[1].color)

    # Draw the ball count
    font = pygame.font.Font(None, 36)
    ball_count_text = font.render(f"Balls: {len(balls)}", True, (0, 0, 0))
    window.blit(ball_count_text, (10, 10))

    # Draw the material palette
    pygame.draw.rect(window, water_button["color"], water_button["rect"])
    pygame.draw.rect(window, rock_button["color"], rock_button["rect"])
    pygame.draw.rect(window, fire_button["color"], fire_button["rect"])
    pygame.draw.rect(window, steam_button["color"], steam_button["rect"])

    font = pygame.font.Font(None, 24)
    water_text = font.render(water_button["text"], True, (255, 255, 255))
    rock_text = font.render(rock_button["text"], True, (255, 255, 255))
    fire_text = font.render(fire_button["text"], True, (255, 255, 255))
    steam_text = font.render(
        steam_button["text"], True, (0, 0, 0)
    )  # Black text for better visibility

    window.blit(water_text, (water_button["rect"].x + 10, water_button["rect"].y + 10))
    window.blit(rock_text, (rock_button["rect"].x + 10, rock_button["rect"].y + 10))
    window.blit(fire_text, (fire_button["rect"].x + 10, fire_button["rect"].y + 10))
    window.blit(steam_text, (steam_button["rect"].x + 10, steam_button["rect"].y + 10))

    # Draw the selected material indicator
    if selected_material == "water":
        pygame.draw.rect(window, (255, 255, 0), water_button["rect"], 3)
    elif selected_material == "rock":
        pygame.draw.rect(window, (255, 255, 0), rock_button["rect"], 3)
    elif selected_material == "fire":
        pygame.draw.rect(window, (255, 255, 0), fire_button["rect"], 3)
    elif selected_material == "steam":
        pygame.draw.rect(window, (255, 255, 0), steam_button["rect"], 3)

    # Update the display
    pygame.display.flip()

    # Control the frame rate
    clock.tick(60)

pygame.quit()
