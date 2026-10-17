// Distance-based angular smoothing rejects pixel-sized axis jitter without
// frame-rate dependence. atan2 handles reversals and crossing ±π continuously.
export function smoothAim(direction, dx, dy) {
  const distance = Math.hypot(dx, dy);
  if (distance < .02) return;
  const current = Math.atan2(direction.y, direction.x);
  const target = Math.atan2(dy, dx);
  const delta = Math.atan2(Math.sin(target - current), Math.cos(target - current));
  const angle = current + delta * (1 - Math.exp(-distance / 3));
  direction.x = Math.cos(angle); direction.y = Math.sin(angle);
}
