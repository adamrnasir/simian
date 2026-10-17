// Fixed-step scheduling: at 1× the simulation advances 60 ticks per second.
// Long frames count as at most 70ms, so catch-up after a stall is bounded, and
// ticks the CPU cannot fit in one frame at high speeds are dropped, not queued.
export const TICK_RATE = 60;

export function ticksDue(clock, elapsed, speed) {
  const interval = 1000 / TICK_RATE / speed, maxSteps = Math.max(4, Math.ceil(speed * 2));
  clock.accumulator += Math.min(elapsed, 70);
  const steps = Math.min(maxSteps, Math.floor(clock.accumulator / interval));
  clock.accumulator = steps === maxSteps ? Math.min(clock.accumulator - steps * interval, interval) : clock.accumulator - steps * interval;
  return steps;
}
