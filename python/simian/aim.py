"""Port of web/aim.mjs.

Distance-based angular smoothing rejects pixel-sized axis jitter without
frame-rate dependence. atan2 handles reversals and crossing ±π continuously.
"""
import math


class Direction:
    def __init__(self, x=1.0, y=0.0):
        self.x = x
        self.y = y


def smooth_aim(direction, dx, dy):
    distance = math.hypot(dx, dy)
    if distance < .02:
        return
    current = math.atan2(direction.y, direction.x)
    target = math.atan2(dy, dx)
    delta = math.atan2(math.sin(target - current), math.cos(target - current))
    angle = current + delta * (1 - math.exp(-distance / 3))
    direction.x = math.cos(angle)
    direction.y = math.sin(angle)
