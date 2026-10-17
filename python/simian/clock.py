"""Port of web/clock.mjs: fixed-step scheduling.

At 1x the simulation advances 60 ticks per second. Long frames count as at most
70ms, so catch-up after a stall is bounded, and ticks the CPU cannot fit in one
frame at high speeds are dropped, not queued.
"""
import math

TICK_RATE = 60


class Clock:
    def __init__(self):
        self.accumulator = 0.0


def ticks_due(clock, elapsed, speed):
    interval = 1000 / TICK_RATE / speed
    max_steps = max(4, math.ceil(speed * 2))
    clock.accumulator += min(elapsed, 70)
    steps = min(max_steps, math.floor(clock.accumulator / interval))
    if steps == max_steps:
        clock.accumulator = min(clock.accumulator - steps * interval, interval)
    else:
        clock.accumulator -= steps * interval
    return steps
