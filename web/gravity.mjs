// Softened inverse-square gravity. Nearby sources are exact; distant groups
// use Barnes–Hut aggregation so dense brushes don't require all-pairs work.
// Positive and negative sources have separate centers, preserving dipoles.
export function radialGravity(size, sources, fieldX, fieldY, limit) {
  fieldX.fill(0); fieldY.fill(0);
  if (!sources.length) return;
  const build = (points, x, y, width) => {
    const node = { x, y, width, positive: 0, negative: 0, px: 0, py: 0, nx: 0, ny: 0, children: null };
    for (const p of points) {
      if (p.sign > 0) { node.positive++; node.px += p.x; node.py += p.y; }
      else { node.negative++; node.nx += p.x; node.ny += p.y; }
    }
    if (node.positive) { node.px /= node.positive; node.py /= node.positive; }
    if (node.negative) { node.nx /= node.negative; node.ny /= node.negative; }
    if (points.length > 1) {
      const half = width / 2, groups = [[], [], [], []];
      for (const p of points) groups[Number(p.x >= x + half) + 2 * Number(p.y >= y + half)].push(p);
      node.children = groups.flatMap((group, q) => group.length ? [build(group, x + (q % 2) * half, y + (q >> 1) * half, half)] : []);
    }
    return node;
  };
  const root = sources.length > 32 ? build(sources, -.5, -.5, size) : null;
  let fx = 0, fy = 0;
  const add = (dx, dy, mass) => {
    const r2 = dx * dx + dy * dy + 9;
    const strength = 5 * mass / (r2 * Math.sqrt(r2));
    fx += dx * strength; fy += dy * strength;
  };
  const visit = (node, x, y) => {
    const dx = x - (node.x + node.width / 2), dy = y - (node.y + node.width / 2);
    // Opening angle 0.5: never approximate a node containing the target.
    if (!node.children || node.width * node.width < .25 * (dx * dx + dy * dy)) {
      if (node.positive) add(node.px - x, node.py - y, node.positive);
      if (node.negative) add(node.nx - x, node.ny - y, -node.negative);
    } else for (const child of node.children) visit(child, x, y);
  };
  for (let y = 0, i = 0; y < size; y++) for (let x = 0; x < size; x++, i++) {
    fx = fy = 0;
    if (root) visit(root, x, y);
    else for (const p of sources) add(p.x - x, p.y - y, p.sign);
    const scale = Math.min(1, limit / (Math.hypot(fx, fy) || 1));
    fieldX[i] = fx * scale; fieldY[i] = fy * scale;
  }
}
