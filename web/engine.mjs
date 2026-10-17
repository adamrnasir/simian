import { radialGravity } from './gravity.mjs';

export const ELEMENTS = [
  { name: 'Erase', symbol: '⌁', light: '#666960', dark: '#a4a79d', density: 0, viscosity: 0, thermal: 0, electrical: 0, temperature: 20, state: 'empty', hint: 'Remove particles.' },
  { name: 'Sand', symbol: '·', light: '#886000', dark: '#ffe9a3', density: 1.8, viscosity: 0, thermal: .08, electrical: 0, temperature: 20, state: 'powder', hint: 'Settles through water, mixes into mud, and supports roots. Intense heat fuses it into crystal.' },
  { name: 'Water', symbol: '○', light: '#006cab', dark: '#4ad6ff', density: 1, viscosity: .05, thermal: .5, electrical: .65, temperature: 20, state: 'liquid', hint: 'Supplies roots, carries charge, freezes below zero, and boils above 100°.' },
  { name: 'Oil', symbol: '/', light: '#8919b8', dark: '#da91ff', density: .7, viscosity: .65, thermal: .04, electrical: 0, temperature: 20, state: 'liquid', hint: 'Floats on water. Electrically insulating and combustible.' },
  { name: 'Fire', symbol: ':', light: '#bd3000', dark: '#ff7b4f', density: .12, viscosity: 0, thermal: .5, electrical: 0, temperature: 650, state: 'gas', hint: 'Burns fuel and drives an upward air current. Wind bends the flame; water extinguishes it.' },
  { name: 'Vapor', symbol: '|', light: '#30618c', dark: '#c1e9f3', density: .05, viscosity: .1, thermal: .06, electrical: 0, temperature: 120, state: 'gas', hint: 'Drifts with air currents. Cooler vapor has a shorter condensation half-life.' },
  { name: 'Stone', symbol: '■', light: '#3d434a', dark: '#5b636c', density: 9, viscosity: 1, thermal: .35, electrical: 0, temperature: 20, state: 'solid', hint: 'A fixed, electrically insulating barrier to particles and wind.' },
  { name: 'Seed', symbol: '+', light: '#386e00', dark: '#a5ed60', density: 1.1, viscosity: 0, thermal: .08, electrical: .01, temperature: 20, state: 'powder', hint: 'Roots on sand or mud. Absorbs water to grow upward, branching into thinner shoots.' },
  { name: 'Crystal', symbol: '◇', light: '#007763', dark: '#59f4e1', density: 3, viscosity: 1, thermal: .25, electrical: 1, temperature: 20, state: 'solid', hint: 'A fast electrical conductor. Charge waves reflect at the ends of connected paths.' },
  { name: 'Spark', symbol: '×', light: '#806000', dark: '#ffe56c', density: .02, viscosity: 0, thermal: .4, electrical: 1, temperature: 850, state: 'energy', hint: 'Scatters outward, ignites fuel, and injects a pulse into adjacent conductors.' },
  { name: 'Lava', symbol: '≋', light: '#c02008', dark: '#ff644b', density: 2.8, viscosity: .88, thermal: .85, electrical: .18, temperature: 1100, state: 'liquid', hint: 'Hot, slow, and dense. Cools into stone; contact with water produces vapor.' },
  { name: 'Mud', symbol: '∷', light: '#71430c', dark: '#d0a66d', density: 2.1, viscosity: .92, thermal: .28, electrical: .12, temperature: 20, state: 'liquid', hint: 'Wet soil that holds water for roots. Flows slowly and dries into sand when heated.' },
  { name: 'Ice', symbol: '✧', light: '#2857b8', dark: '#a7d8ff', density: .92, viscosity: 1, thermal: .65, electrical: .01, temperature: -25, state: 'solid', hint: 'Cools its surroundings and melts above zero. Conducts heat much better than charge.' },
  { name: 'Wind', symbol: '~', light: '#147158', dark: '#b0e9ce', density: 0, viscosity: 0, thermal: 0, electrical: 0, temperature: 20, state: 'field', hint: 'Move to aim; hold to blow in that direction. Sends air around obstacles without adding particles.' },
  { name: 'Scramble', symbol: '?', light: '#a12b80', dark: '#ff91dd', density: 1.2, viscosity: 0, thermal: .12, electrical: .05, temperature: 20, state: 'powder', hint: 'Contact changes a neighbor into a random material and consumes the question mark. Phase lock makes it reusable; locked neighbors are protected.' },
  { name: 'Metal', symbol: '□', light: '#4b5663', dark: '#a6b3c1', density: 8, viscosity: 1, thermal: .9, electrical: .95, temperature: 20, state: 'solid', hint: 'Conducts heat and electricity. Hot lava melts it, as does any heat above 800°.' },
  { name: 'Grav', symbol: 'g', light: '#153d87', dark: '#658edc', density: 9, viscosity: 1, thermal: 0, electrical: 0, temperature: 20, state: 'solid', hint: 'A fixed source that attracts nearby moving matter. Antigrav reverses the force for newly placed sources.' },
  { name: 'Bacterium', symbol: '△', light: '#7524a0', dark: '#c38cf4', density: .3, viscosity: 1, thermal: .15, electrical: 0, temperature: 20, state: 'life', hint: 'Life rules: survives with 2–3 neighbors, born with 3. Eats plant matter; heat and cold kill it. Phase lock isolates a colony from other elements.' },
  // U+FE0E requests the text (not emoji) presentation of the warning sign.
  { name: 'Gunpowder', symbol: '\u26A0\uFE0E', light: '#3f3a33', dark: '#d9ccb4', density: 1.5, viscosity: 0, thermal: .1, electrical: 0, temperature: 20, state: 'powder', hint: 'Fire, sparks, lava, or heat above 180° detonate it: a blast of pressure, wind, and fire that chains through connected powder. Cannot be phase locked.' },
  { name: 'Boids', symbol: 'v', light: '#4a3d33', dark: '#e6d3bd', density: 1.05, viscosity: 0, thermal: .1, electrical: 0, temperature: 20, state: 'life', hint: 'Flocking birds: each steers toward its neighbors\u2019 heading and center while keeping its distance, and avoids obstacles. Feesh fall inert until they reach water, then school.' },
  { name: 'Liquid N₂', symbol: '⋄', light: '#126a79', dark: '#9af4ff', density: .81, viscosity: .02, thermal: .3, electrical: 0, temperature: -200, state: 'liquid', hint: 'Liquid nitrogen: an intensely cold liquid. Boils above −196° into nitrogen vapor; phase lock keeps it liquid and cold.' }
];

export const ID = Object.freeze({ EMPTY: 0, SAND: 1, WATER: 2, OIL: 3, FIRE: 4, VAPOR: 5, STONE: 6, SEED: 7, CRYSTAL: 8, SPARK: 9, LAVA: 10, MUD: 11, ICE: 12, WIND: 13, SCRAMBLE: 14, METAL: 15, GRAV: 16, BACTERIUM: 17, GUNPOWDER: 18, BOID: 19, NITROGEN: 20 });

export const PHASE_LOCKABLE = new Set([ID.SAND, ID.WATER, ID.OIL, ID.FIRE, ID.VAPOR, ID.SEED, ID.LAVA, ID.MUD, ID.ICE, ID.SCRAMBLE, ID.METAL, ID.BACTERIUM, ID.NITROGEN]);
export const LOCKED_SYMBOLS = Object.freeze({ [ID.SAND]: '•', [ID.WATER]: '●', [ID.ICE]: '✦', [ID.BACTERIUM]: '▲' });
export const ANTIGRAV_COLOR = Object.freeze({ light: '#8b2533', dark: '#dc727c' });
export const FEESH_COLOR = Object.freeze({ light: '#a64a00', dark: '#ffa45c' });
export const elementSymbol = (id, locked = false) => locked ? LOCKED_SYMBOLS[id] || ELEMENTS[id].symbol : ELEMENTS[id].symbol;
export const MAX_PRESSURE = 60;
export const MAX_AIR_SPEED = 12;
// Ordinary downward acceleration on powders and liquids, per tick.
export const NORMAL_GRAVITY = .045;
// Peak grav acceleration: slightly above ordinary gravity, so a nearby source
// can lift resting matter off the ground.
export const GRAV_STRENGTH = .06;
// Boids: flocking radius (cells) and speed bounds (cells per tick).
const BOID_RADIUS = 6, BOID_MIN_SPEED = .25, BOID_MAX_SPEED = .8, FEESH_MAX_SPEED = .5;
// Per-id lookup avoids reading each element's state string in hot loops.
const SOLID = Uint8Array.from(ELEMENTS, element => Number(element.state === 'solid'));
const GAS = Uint8Array.from(ELEMENTS, element => Number(element.state === 'gas'));
const THERMAL = Float64Array.from(ELEMENTS, element => element.thermal);
const ELECTRICAL = Float64Array.from(ELEMENTS, element => element.electrical);
const SCRAMBLE_RESULTS = ELEMENTS.map((_, id) => id).filter(id => id && id !== ID.WIND && id !== ID.SCRAMBLE);

// Odd diameters center on a cell; even diameters center between cells.
export const brushStart = (position, diameter) => Math.round(position - (diameter - 1) / 2);

export function condensationChance(temperature) {
  if (temperature >= 100) return 0;
  const halfLife = 25 + Math.max(0, temperature - 20) * 3;
  return 1 - Math.exp(-Math.LN2 / halfLife);
}

export class World {
  constructor(size = 112, seed = 731) {
    this.size = size; this.length = size * size; this.seed = seed || 731;
    this.cells = new Uint8Array(this.length);
    this.life = new Uint16Array(this.length);
    this.updated = new Uint32Array(this.length);
    this.moved = new Uint32Array(this.length);
    this.roots = new Int32Array(this.length);
    this.branch = new Int8Array(this.length);
    this.generation = new Uint8Array(this.length);
    this.phaseLocked = new Uint8Array(this.length);
    this.nitrogenVapor = new Uint8Array(this.length);
    this.polarity = new Int8Array(this.length);
    this.gravityX = new Float32Array(this.length); this.gravityY = new Float32Array(this.length);
    this.neighbors = new Uint8Array(this.length); this.lockedNeighbors = new Uint8Array(this.length);
    for (const name of ['heat', 'charge', 'chargeVelocity', 'force', 'vx', 'vy', 'travelX', 'travelY', 'moisture', 'burn', 'pressure', 'nextPressure', 'curl', 'windX', 'windY', 'nextWindX', 'nextWindY']) this[name] = new Float32Array(this.length);
    this.airMask = new Uint8Array(this.length);
    this.supportedMatter = new Uint8Array(this.length);
    this.supportQueue = new Int32Array(this.length);
    this.airHeat = new Float32Array(this.length);
    this.nextAirHeat = new Float32Array(this.length);
    this.particleFields = [this.heat, this.charge, this.chargeVelocity, this.life, this.vx, this.vy, this.travelX, this.travelY, this.moisture, this.burn, this.roots, this.branch, this.generation, this.phaseLocked, this.polarity];
    this.particleFields.push(this.nitrogenVapor);
    this.windStrength = 10;
    this.gravStrength = 1;
    // Zero-g removes gravity-driven effects: weight, settling, buoyancy, and
    // convection. Grav sources, wind, and momentum still act.
    this.zeroGravity = false;
    this.clear();
  }

  random() {
    this.seed ^= this.seed << 13; this.seed ^= this.seed >>> 17; this.seed ^= this.seed << 5;
    return (this.seed >>> 0) / 4294967296;
  }

  clear() {
    this.supportTick = -1;
    this.supportedMatter.fill(0);
    this.gravityDirty = true;
    this.cells.fill(0); this.updated.fill(0); this.moved.fill(0);
    for (const field of this.particleFields) field.fill(0);
    this.heat.fill(20); this.roots.fill(-1);
    this.airHeat.fill(20); this.nextAirHeat.fill(20);
    this.windX.fill(0); this.windY.fill(0); this.nextWindX.fill(0); this.nextWindY.fill(0); this.force.fill(0);
    this.pressure.fill(0); this.nextPressure.fill(0); this.curl.fill(0); this.airMask.fill(0);
    this.tick = 0;
  }

  // `alternate` selects an element's second form: antigrav for Grav, feesh for
  // Boids. Both store it in polarity (1 or -1), which moves with the particle.
  set(i, id, temperature = ELEMENTS[id].temperature, locked = false, alternate = false) {
    if (id === ID.WIND) { this.pressurize(i, .6); return; }
    if (this.cells[i] === ID.GRAV || id === ID.GRAV) this.gravityDirty = true;
    this.cells[i] = id;
    this.polarity[i] = id === ID.GRAV || id === ID.BOID ? (alternate ? -1 : 1) : 0;
    this.phaseLocked[i] = Number(locked && PHASE_LOCKABLE.has(id));
    this.nitrogenVapor[i] = 0;
    this.heat[i] = temperature;
    this.charge[i] = id === ID.SPARK ? 1 : 0;
    this.chargeVelocity[i] = 0;
    // Boids use life as a wingbeat clock; a random start keeps flocks out of phase.
    this.life[i] = id === ID.FIRE ? 300 + (this.random() * 240 | 0) : id === ID.SPARK ? 18 + (this.random() * 18 | 0) : id === ID.BOID ? this.random() * 256 | 0 : 0;
    this.burn[i] = 0;
    this.moisture[i] = id === ID.MUD ? 2 : 0;
    this.roots[i] = -1; this.branch[i] = 0; this.generation[i] = 0;
    const angle = id === ID.SPARK || id === ID.BOID ? this.random() * Math.PI * 2 : 0;
    const speed = id === ID.SPARK ? 1 : id === ID.BOID ? BOID_MIN_SPEED : 0;
    this.vx[i] = speed * Math.cos(angle);
    this.vy[i] = speed * Math.sin(angle);
    this.travelX[i] = this.travelY[i] = 0;
    this.updated[i] = this.tick;
  }

  paint(x, y, id, diameter = 5, strength = 1, locked = false, directionX = 1, directionY = 0, alternate = false) {
    if (id === ID.WIND) { this.blow(x, y, diameter, strength, directionX, directionY); return; }
    const startX = brushStart(x, diameter), startY = brushStart(y, diameter);
    const radius = diameter / 2, center = (diameter - 1) / 2;
    for (let row = 0; row < diameter; row++) for (let col = 0; col < diameter; col++) {
      const dx = col - center, dy = row - center;
      if (dx * dx + dy * dy > radius * radius) continue;
      const px = startX + col, py = startY + row;
      if (px < 0 || py < 0 || px >= this.size || py >= this.size) continue;
      const i = py * this.size + px;
      if (!id) { this.pressure[i] = this.windX[i] = this.windY[i] = 0; }
      if (!id || !this.cells[i]) {
        this.set(i, id, ELEMENTS[id].temperature, locked, alternate);
        if (id === ID.SPARK && (dx || dy)) {
          const length = Math.hypot(dx, dy);
          this.vx[i] = dx / length; this.vy[i] = dy / length;
        }
      }
    }
  }

  blow(x, y, diameter, strength, directionX, directionY) {
    this.windStrength = Math.max(10, Math.min(100, strength));
    const length = Math.hypot(directionX, directionY);
    if (!length) return;
    const ux = directionX / length, uy = directionY / length;
    const startX = brushStart(x, diameter), startY = brushStart(y, diameter);
    const radius = diameter / 2, center = (diameter - 1) / 2;
    for (let row = 0; row < diameter; row++) for (let col = 0; col < diameter; col++) {
      const dx = col - center, dy = row - center, distance = dx * dx + dy * dy;
      const px = startX + col, py = startY + row;
      if (distance > radius * radius || px < 0 || py < 0 || px >= this.size || py >= this.size) continue;
      const i = py * this.size + px;
      if (this.blocked(i)) continue;
      const weight = Math.exp(-distance / (radius * radius * .7));
      // A held nozzle adds momentum, not just pressure in a static balloon.
      // A small balanced pressure dipole helps entrain the surrounding air.
      this.gust(i, ux * strength * .22 * weight, uy * strength * .22 * weight);
      for (let side = -1; side <= 1; side += 2) {
        const tx = px + side * ux, ty = py + side * uy;
        const left = Math.floor(tx), top = Math.floor(ty), fx = tx - left, fy = ty - top;
        // Bilinear deposition preserves the continuous angle of the nozzle.
        for (let row = 0; row < 2; row++) for (let col = 0; col < 2; col++) {
          const nx = left + col, ny = top + row;
          const fraction = (col ? fx : 1 - fx) * (row ? fy : 1 - fy);
          if (!fraction || nx < 0 || ny < 0 || nx >= this.size || ny >= this.size) continue;
          if (nx !== px && ny !== py && (this.blocked(py * this.size + nx) || this.blocked(ny * this.size + px))) continue;
          this.pressurize(ny * this.size + nx, -side * strength * .07 * weight * fraction);
        }
      }
    }
  }

  // Explicit per-array swaps keep each typed-array access monomorphic. A loop
  // over these mixed array types was the engine's single largest cost. Keep
  // this list in sync with particleFields.
  exchange(a, b) {
    let t;
    t = this.cells[a]; this.cells[a] = this.cells[b]; this.cells[b] = t;
    t = this.heat[a]; this.heat[a] = this.heat[b]; this.heat[b] = t;
    t = this.charge[a]; this.charge[a] = this.charge[b]; this.charge[b] = t;
    t = this.chargeVelocity[a]; this.chargeVelocity[a] = this.chargeVelocity[b]; this.chargeVelocity[b] = t;
    t = this.life[a]; this.life[a] = this.life[b]; this.life[b] = t;
    t = this.vx[a]; this.vx[a] = this.vx[b]; this.vx[b] = t;
    t = this.vy[a]; this.vy[a] = this.vy[b]; this.vy[b] = t;
    t = this.travelX[a]; this.travelX[a] = this.travelX[b]; this.travelX[b] = t;
    t = this.travelY[a]; this.travelY[a] = this.travelY[b]; this.travelY[b] = t;
    t = this.moisture[a]; this.moisture[a] = this.moisture[b]; this.moisture[b] = t;
    t = this.burn[a]; this.burn[a] = this.burn[b]; this.burn[b] = t;
    t = this.roots[a]; this.roots[a] = this.roots[b]; this.roots[b] = t;
    t = this.branch[a]; this.branch[a] = this.branch[b]; this.branch[b] = t;
    t = this.generation[a]; this.generation[a] = this.generation[b]; this.generation[b] = t;
    t = this.phaseLocked[a]; this.phaseLocked[a] = this.phaseLocked[b]; this.phaseLocked[b] = t;
    t = this.polarity[a]; this.polarity[a] = this.polarity[b]; this.polarity[b] = t;
    t = this.nitrogenVapor[a]; this.nitrogenVapor[a] = this.nitrogenVapor[b]; this.nitrogenVapor[b] = t;
    this.updated[a] = this.updated[b] = this.moved[a] = this.moved[b] = this.tick;
  }

  move(i, x, y, displace = false) {
    if (x < 0 || y < 0 || x >= this.size || y >= this.size) return false;
    const j = y * this.size + x, target = this.cells[j];
    const other = ELEMENTS[target];
    const dx = x - i % this.size, dy = y - Math.floor(i / this.size);
    const alongGravity = dx * (this.gravityX[i] + this.gravityX[j]) * .5 +
      dy * ((this.gravityY[i] + this.gravityY[j]) * .5 + (this.zeroGravity ? 0 : NORMAL_GRAVITY));
    const displacement = displace && this.moved[j] !== this.tick &&
      (other.state === 'liquid' || other.state === 'gas') &&
      alongGravity * (this.density(i) - this.density(j)) > 1e-9;
    if (!target || displacement) { this.exchange(i, j); return true; }
    return false;
  }

  density(i) {
    const material = ELEMENTS[this.cells[i]];
    const expansion = material.state === 'gas' ? 1 / 293 : material.state === 'liquid' ? .0007 : 0;
    return material.density / Math.max(.25, 1 + expansion * (this.heat[i] - 20));
  }

  airThermal() {
    const n = this.size, air = this.airHeat;
    // Air occupies the flow field, not particle slots: moving/erasing matter
    // must not reset its temperature. Solids exchange through exposed faces.
    const exchange = (particle, cell) => {
      const rate = Math.min(.08, THERMAL[this.cells[particle]]) * .25;
      const transfer = (this.heat[particle] - air[cell]) * rate;
      air[cell] += transfer;
      // Air has one tenth the cell heat capacity of matter.
      if (!this.phaseLocked[particle]) this.heat[particle] -= transfer * .1;
    };
    const pair = (i, j, blocked) => {
      const otherBlocked = this.blocked(j);
      if (!blocked && !otherBlocked) {
        const transfer = (air[i] - air[j]) * .08;
        air[i] -= transfer; air[j] += transfer;
      } else if (blocked !== otherBlocked) exchange(blocked ? i : j, blocked ? j : i);
    };
    for (let y = 0, i = 0; y < n; y++) for (let x = 0; x < n; x++, i++) {
      const blocked = this.blocked(i);
      if (!blocked && this.cells[i]) exchange(i, i);
      if (x + 1 < n) pair(i, i + 1, blocked);
      if (y + 1 < n) pair(i, i + n, blocked);
    }
  }

  thermalPair(a, b) {
    if (!this.cells[b]) return;
    const conductivity = Math.min(THERMAL[this.cells[a]], THERMAL[this.cells[b]]);
    const heat = (this.heat[a] - this.heat[b]) * conductivity * .2;
    // Locked matter is a thermal reservoir: it still heats/cools its neighbors.
    if (!this.phaseLocked[a]) this.heat[a] -= heat;
    if (!this.phaseLocked[b]) this.heat[b] += heat;
  }

  electricalPair(a, b) {
    const conductivity = Math.min(ELECTRICAL[this.cells[a]], ELECTRICAL[this.cells[b]]);
    if (!conductivity) return;
    const force = (this.charge[b] - this.charge[a]) * conductivity * .07;
    this.force[a] += force; this.force[b] -= force;
  }

  electricity() {
    // A damped wave on the conductive adjacency graph, not diffusion. Missing
    // edges have zero flux, so pulses reflect at conductor boundaries. A single
    // substep keeps the front visible; its speed scales with conductivity.
      this.force.fill(0);
      for (let i = 0; i < this.length; i++) {
        if (!ELECTRICAL[this.cells[i]]) continue;
        if (i % this.size < this.size - 1) this.electricalPair(i, i + 1);
        if (i + this.size < this.length) this.electricalPair(i, i + this.size);
      }
      for (let i = 0; i < this.length; i++) {
        if (!ELECTRICAL[this.cells[i]]) { this.charge[i] = this.chargeVelocity[i] = 0; continue; }
        this.chargeVelocity[i] = (this.chargeVelocity[i] + this.force[i]) * .997;
        this.charge[i] = Math.max(-3, Math.min(3, (this.charge[i] + this.chargeVelocity[i]) * .999));
      }
  }

  blocked(i) { const id = this.cells[i]; return SOLID[id] === 1 || (id === ID.SEED && this.roots[i] >= 0); }

  gust(i, x, y) {
    if (this.blocked(i)) return;
    this.windX[i] = Math.max(-MAX_AIR_SPEED, Math.min(MAX_AIR_SPEED, this.windX[i] + x));
    this.windY[i] = Math.max(-MAX_AIR_SPEED, Math.min(MAX_AIR_SPEED, this.windY[i] + y));
  }

  pressurize(i, amount) {
    if (!this.blocked(i)) this.pressure[i] = Math.max(-MAX_PRESSURE, Math.min(MAX_PRESSURE, this.pressure[i] + amount));
  }

  sampleFlow(field, x, y, fallback) {
    const n = this.size;
    x = Math.max(0, Math.min(n - 1.001, x)); y = Math.max(0, Math.min(n - 1.001, y));
    const ix = Math.floor(x), iy = Math.floor(y), i = iy * n + ix, fx = x - ix, fy = y - iy;
    const a = this.airMask[i] ? fallback : field[i], b = this.airMask[i + 1] ? fallback : field[i + 1];
    const c = this.airMask[i + n] ? fallback : field[i + n], d = this.airMask[i + n + 1] ? fallback : field[i + n + 1];
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy;
  }

  airflow() {
    const n = this.size, mask = this.airMask, pressure = this.pressure, windX = this.windX, windY = this.windY;
    const nextX = this.nextWindX, nextY = this.nextWindY, curl = this.curl;
    const persistence = .999 + .00095 * Math.max(0, Math.min(1, (this.windStrength - 10) / 90));
    for (let i = 0; i < this.length; i++) mask[i] = Number(this.blocked(i));
    // Compressible pressure/velocity coupling preserves traveling pressure waves.
    // Semi-Lagrangian velocity transport and weak vorticity confinement retain
    // wakes around obstacles. This is a bounded artistic approximation, not CFD.
    // Row/column loops avoid per-cell division; arithmetic order is unchanged.
    for (let y = 0, i = 0; y < n; y++) for (let x = 0; x < n; x++, i++) {
      if (mask[i]) { nextX[i] = nextY[i] = pressure[i] = 0; this.nextAirHeat[i] = this.airHeat[i]; continue; }
      const p = pressure[i];
      const left = x && !mask[i - 1], right = x < n - 1 && !mask[i + 1];
      const up = y && !mask[i - n], down = y < n - 1 && !mask[i + n];
      // Keep the backtrace inside adjacent cells so fast flow cannot sample
      // through a wall. Momentum magnitude remains independent of transport.
      const transport = Math.min(.3, .9 / Math.max(.001, Math.abs(windX[i]), Math.abs(windY[i])));
      const bx = x - windX[i] * transport, by = y - windY[i] * transport;
      this.nextAirHeat[i] = this.sampleFlow(this.airHeat, bx, by, this.airHeat[i]);
      // Isotropic nine-point gradients reduce the axial cross of a four-neighbor
      // stencil. Diagonal paths are closed when either adjoining face is blocked.
      const nw = left && up && !mask[i - n - 1] ? pressure[i - n - 1] : p;
      const ne = right && up && !mask[i - n + 1] ? pressure[i - n + 1] : p;
      const sw = left && down && !mask[i + n - 1] ? pressure[i + n - 1] : p;
      const se = right && down && !mask[i + n + 1] ? pressure[i + n + 1] : p;
      let vx = this.sampleFlow(windX, bx, by, windX[i]) - (4 * ((right ? pressure[i + 1] : p) - (left ? pressure[i - 1] : p)) + ne + se - nw - sw) * (.28 / 6);
      let vy = this.sampleFlow(windY, bx, by, windY[i]) - (4 * ((down ? pressure[i + n] : p) - (up ? pressure[i - n] : p)) + sw + se - nw - ne) * (.28 / 6);
      const thermalLift = Math.max(-.08, Math.min(.08, (this.airHeat[i] - 20) * .00025)) / NORMAL_GRAVITY;
      vx -= this.gravityX[i] * thermalLift;
      vy -= (this.gravityY[i] + (this.zeroGravity ? 0 : NORMAL_GRAVITY)) * thermalLift;
      if ((!left && vx < 0) || (!right && vx > 0)) vx = 0;
      if ((!up && vy < 0) || (!down && vy > 0)) vy = 0;
      nextX[i] = vx * persistence; nextY[i] = vy * persistence;
    }
    for (let y = 0, i = 0; y < n; y++) for (let x = 0; x < n; x++, i++) {
      curl[i] = mask[i] ? 0 : ((x < n - 1 ? nextY[i + 1] : 0) - (x ? nextY[i - 1] : 0) - (y < n - 1 ? nextX[i + n] : 0) + (y ? nextX[i - n] : 0)) * .5;
    }
    const nextPressure = this.nextPressure;
    for (let y = 0, i = 0; y < n; y++) for (let x = 0; x < n; x++, i++) {
      if (mask[i]) { nextPressure[i] = 0; continue; }
      const left = x && !mask[i - 1], right = x < n - 1 && !mask[i + 1];
      const up = y && !mask[i - n], down = y < n - 1 && !mask[i + n];
      const nw = left && up && !mask[i - n - 1], ne = right && up && !mask[i - n + 1];
      const sw = left && down && !mask[i + n - 1], se = right && down && !mask[i + n + 1];
      const diagonalX = (ne ? nextX[i - n + 1] : -nextX[i]) + (se ? nextX[i + n + 1] : -nextX[i]) - (nw ? nextX[i - n - 1] : -nextX[i]) - (sw ? nextX[i + n - 1] : -nextX[i]);
      const diagonalY = (sw ? nextY[i + n - 1] : -nextY[i]) + (se ? nextY[i + n + 1] : -nextY[i]) - (nw ? nextY[i - n - 1] : -nextY[i]) - (ne ? nextY[i - n + 1] : -nextY[i]);
      const axial = (right ? nextX[i + 1] : -nextX[i]) - (left ? nextX[i - 1] : -nextX[i]) + (down ? nextY[i + n] : -nextY[i]) - (up ? nextY[i - n] : -nextY[i]);
      const divergence = (4 * axial + diagonalX + diagonalY) / 12;
      const p = pressure[i] - divergence * .55;
      nextPressure[i] = Math.max(-MAX_PRESSURE, Math.min(MAX_PRESSURE, p * persistence));
      const gx = (right ? Math.abs(curl[i + 1]) : 0) - (left ? Math.abs(curl[i - 1]) : 0);
      const gy = (down ? Math.abs(curl[i + n]) : 0) - (up ? Math.abs(curl[i - n]) : 0);
      const scale = .035 * curl[i] / (Math.sqrt(gx * gx + gy * gy) + .001);
      let vx = nextX[i] + gy * scale, vy = nextY[i] - gx * scale;
      if ((!left && vx < 0) || (!right && vx > 0)) vx = 0;
      if ((!up && vy < 0) || (!down && vy > 0)) vy = 0;
      nextX[i] = Math.max(-MAX_AIR_SPEED, Math.min(MAX_AIR_SPEED, vx)); nextY[i] = Math.max(-MAX_AIR_SPEED, Math.min(MAX_AIR_SPEED, vy));
    }
    this.windX = nextX; this.nextWindX = windX;
    this.windY = nextY; this.nextWindY = windY;
    this.pressure = nextPressure; this.nextPressure = pressure;
    const previousHeat = this.airHeat;
    this.airHeat = this.nextAirHeat; this.nextAirHeat = previousHeat;
  }

  contact(i, j) {
    const source = this.cells[i], target = this.cells[j];
    if ((source === ID.FIRE || source === ID.SPARK || source === ID.LAVA) && target === ID.GUNPOWDER) this.burn[j] = 1;
    if (!this.phaseLocked[j] && (source === ID.FIRE || source === ID.SPARK || source === ID.LAVA) && (target === ID.OIL || target === ID.SEED)) {
      const thermal = ELEMENTS[target].thermal;
      this.heat[j] += Math.max(0, this.heat[i] - this.heat[j]) * thermal * .08;
      this.burn[j] += thermal * (source === ID.SPARK ? 2 : .4);
      if (source === ID.SPARK) this.heat[j] = Math.max(this.heat[j], 260);
    }
    if (source === ID.FIRE && target === ID.WATER) { this.transform(i, ID.EMPTY); this.transform(j, ID.VAPOR, 105); }
    else if (source === ID.LAVA && (target === ID.WATER || target === ID.ICE)) { this.transform(i, ID.STONE, 400); this.transform(j, ID.VAPOR, 150); }
    // Conduction alone cannot melt metal: it spreads heat faster than lava can
    // supply it. Hot lava instead dissolves touching metal at a bounded rate.
    else if (source === ID.LAVA && target === ID.METAL && this.heat[i] > 800 && this.random() < .03) this.transform(j, ID.LAVA, this.heat[i]);
    else if (source === ID.SAND && target === ID.WATER && !this.phaseLocked[i] && !this.phaseLocked[j] && this.random() < .015) { this.set(i, ID.MUD); this.set(j, ID.EMPTY); }
    else if (source === ID.SPARK && ELEMENTS[target].electrical > .05 && this.life[i] > 10) {
      this.charge[j] = Math.min(.9, this.charge[j] + .65);
      this.charge[i] = 0;
      this.life[i] = 10; // One finite pulse per spark, rather than unbounded pumping.
    }
  }

  transform(i, id, temperature = ELEMENTS[id].temperature) {
    if (this.phaseLocked[i]) return;
    const vx = this.vx[i], vy = this.vy[i];
    const nitrogen = id === ID.VAPOR && (this.cells[i] === ID.NITROGEN || this.nitrogenVapor[i]);
    this.set(i, id, temperature);
    this.nitrogenVapor[i] = Number(nitrogen);
    if (id) { this.vx[i] = vx; this.vy[i] = vy; }
  }

  // Detonation: a flash fire plus a bounded overpressure and radial gust that
  // throws loose matter outward. Adjacent powder ignites at once, so a
  // connected charge goes off within a few ticks.
  explode(i, x, y) {
    const n = this.size, radius = 5;
    this.set(i, ID.FIRE);
    this.life[i] = 60 + (this.random() * 60 | 0);
    for (let dy = -radius; dy <= radius; dy++) for (let dx = -radius; dx <= radius; dx++) {
      const px = x + dx, py = y + dy, distance = Math.hypot(dx, dy);
      if (!distance || distance > radius || px < 0 || py < 0 || px >= n || py >= n) continue;
      const j = py * n + px, id = this.cells[j], falloff = 1 - distance / (radius + 1);
      const ux = dx / distance, uy = dy / distance;
      this.pressurize(j, 18 * falloff);
      this.gust(j, ux * 3 * falloff, uy * 3 * falloff);
      if (id === ID.GUNPOWDER) { if (distance < 2) this.burn[j] = 1; }
      else if (!id && distance < 2.5 && this.random() < .6) { this.set(j, ID.FIRE); this.life[j] = 40 + (this.random() * 60 | 0); }
      else if (id && ELEMENTS[id].state !== 'solid' && id !== ID.BACTERIUM) { this.vx[j] += ux * 2.5 * falloff; this.vy[j] += uy * 2.5 * falloff; }
    }
    this.pressurize(i, 18);
  }

  // Feesh swim only while touching water; otherwise they are inert matter.
  submerged(i, x, y) {
    const n = this.size;
    return (x > 0 && this.cells[i - 1] === ID.WATER) || (x < n - 1 && this.cells[i + 1] === ID.WATER) ||
      (y > 0 && this.cells[i - n] === ID.WATER) || (y < n - 1 && this.cells[i + n] === ID.WATER);
  }

  // Reynolds boids on the grid: alignment, cohesion, and separation among the
  // same form within BOID_RADIUS, plus look-ahead obstacle avoidance and wall
  // repulsion. Birds move through air; feesh swap places with water.
  boid(i, x, y) {
    const n = this.size, fish = this.polarity[i] < 0, medium = fish ? ID.WATER : ID.EMPTY;
    this.life[i] = (this.life[i] + 1) & 0xffff;
    if (fish && !this.submerged(i, x, y)) { this.transportParticle(i, x, y); return; }
    let count = 0, headingX = 0, headingY = 0, centerX = 0, centerY = 0, awayX = 0, awayY = 0;
    for (let dy = -BOID_RADIUS; dy <= BOID_RADIUS; dy++) for (let dx = -BOID_RADIUS; dx <= BOID_RADIUS; dx++) {
      const px = x + dx, py = y + dy, distance = dx * dx + dy * dy;
      if (!distance || distance > BOID_RADIUS * BOID_RADIUS || px < 0 || py < 0 || px >= n || py >= n) continue;
      const j = py * n + px;
      if (this.cells[j] !== ID.BOID || this.polarity[j] !== this.polarity[i]) continue;
      count++; headingX += this.vx[j]; headingY += this.vy[j]; centerX += dx; centerY += dy;
      if (distance <= 2) { awayX -= dx / distance; awayY -= dy / distance; }
    }
    let vx = this.vx[i], vy = this.vy[i];
    if (count) {
      vx += (headingX / count - vx) * .08 + centerX / count * .004 + awayX * .04;
      vy += (headingY / count - vy) * .08 + centerY / count * .004 + awayY * .04;
    }
    // Look ahead along the heading; turn toward whichever side is open.
    const speed = Math.sqrt(vx * vx + vy * vy) || 1;
    const open = (ux, uy) => {
      const ax = Math.round(x + ux * 3), ay = Math.round(y + uy * 3);
      return ax >= 0 && ay >= 0 && ax < n && ay < n && (this.cells[ay * n + ax] === medium || this.cells[ay * n + ax] === ID.BOID);
    };
    const ux = vx / speed, uy = vy / speed;
    if (!open(ux, uy)) {
      const left = open(ux * .5 + uy * .87, uy * .5 - ux * .87), right = open(ux * .5 - uy * .87, uy * .5 + ux * .87);
      const turn = left === right ? (this.random() < .5 ? 1 : -1) : left ? 1 : -1;
      vx += uy * .12 * turn; vy -= ux * .12 * turn;
    }
    const margin = 3;
    // Active flight/swimming counters moderate fields with bounded thrust.
    // Stronger fields still overpower it; stranded feesh use ordinary transport.
    const gravity = Math.hypot(this.gravityX[i], this.gravityY[i]);
    const residual = gravity ? Math.max(0, 1 - .05 / gravity) : 0;
    vx += (x < margin ? .03 : 0) - (x >= n - margin ? .03 : 0) + (this.random() - .5) * .04 + this.windX[i] * .02 + this.gravityX[i] * residual;
    vy += (y < margin ? .03 : 0) - (y >= n - margin ? .03 : 0) + (this.random() - .5) * .04 + this.windY[i] * .02 + this.gravityY[i] * residual;
    // Hold speed within bounds; ease down from bursts (e.g. explosions).
    const maximum = fish ? FEESH_MAX_SPEED : BOID_MAX_SPEED, current = Math.sqrt(vx * vx + vy * vy);
    const scale = !current ? 0 : current > maximum ? Math.max(maximum / current, .9) : current < BOID_MIN_SPEED ? BOID_MIN_SPEED / current : 1;
    this.vx[i] = scale ? vx * scale : BOID_MIN_SPEED; this.vy[i] = scale ? vy * scale : 0;
    // Facing (for the fish glyph) changes only on a clear horizontal heading.
    if (Math.abs(this.vx[i]) > .05) this.branch[i] = this.vx[i] < 0 ? -1 : 1;
    this.travelX[i] += this.vx[i]; this.travelY[i] += this.vy[i];
    const stepX = Math.trunc(this.travelX[i]), stepY = Math.trunc(this.travelY[i]);
    this.travelX[i] -= stepX; this.travelY[i] -= stepY;
    if (stepX) {
      const tx = x + Math.sign(stepX), j = y * n + tx;
      if (tx >= 0 && tx < n && this.cells[j] === medium && this.moved[j] !== this.tick) { this.exchange(i, j); i = j; x = tx; }
      else { this.vx[i] *= -.5; this.travelX[i] = 0; }
    }
    if (stepY) {
      const ty = y + Math.sign(stepY), j = ty * n + x;
      if (ty >= 0 && ty < n && this.cells[j] === medium && this.moved[j] !== this.tick) this.exchange(i, j);
      else { this.vy[i] *= -.5; this.travelY[i] = 0; }
    }
  }

  supported(root) {
    const below = root + this.size;
    return below < this.length && (this.cells[below] === ID.SAND || this.cells[below] === ID.MUD);
  }

  absorb(root) {
    if (this.moisture[root] >= 18) return;
    const x = root % this.size, y = Math.floor(root / this.size);
    for (let dy = -1; dy <= 2; dy++) for (let dx = -2; dx <= 2; dx++) {
      if (x + dx < 0 || x + dx >= this.size || y + dy < 0 || y + dy >= this.size) continue;
      const j = (y + dy) * this.size + x + dx;
      if (this.cells[j] === ID.WATER && !this.phaseLocked[j]) { this.set(j, ID.EMPTY); this.moisture[root] += 6; return; }
      if (this.cells[j] === ID.MUD && this.moisture[j] >= .25) { this.moisture[j] -= .25; this.moisture[root] += 2; return; }
    }
  }

  grow(i, x, y) {
    let root = this.roots[i];
    if (root < 0) {
      if (!this.supported(i)) return false;
      this.absorb(i);
      if (this.moisture[i] < 1) return false;
      root = this.roots[i] = i; this.life[i] = 1;
    }
    if (this.cells[root] !== ID.SEED || this.roots[root] !== root || !this.supported(root)) {
      this.roots[i] = -1; this.life[i] = 0; return false;
    }
    if (root === i && this.tick % 20 === 0) this.absorb(root);
    if (this.life[i] !== 1 || !y || this.moisture[root] < 1 || this.random() > .025) return true;
    let direction = this.branch[i];
    if (!direction && this.random() < .35) direction = this.random() < .5 ? -1 : 1;
    let grown = 0;
    const split = this.generation[i] < 4 && this.random() < .2;
    for (let attempt = 0; attempt < (split ? 2 : 1); attempt++) {
      const dx = split ? (attempt ? 1 : -1) : this.random() < .7 ? direction : 0;
      if (x + dx < 0 || x + dx >= this.size || this.moisture[root] < 1) continue;
      const j = (y - 1) * this.size + x + dx;
      if (this.cells[j]) continue;
      this.set(j, ID.SEED, this.heat[i], this.phaseLocked[i]);
      this.roots[j] = root; this.life[j] = 1;
      this.branch[j] = dx; this.generation[j] = this.generation[i] + Number(split);
      this.moisture[root]--; grown++;
    }
    if (grown) this.life[i] = 2; // Mature stem; only the new tips extend.
    return true;
  }

  drift(i, x, y) {
    let dx = Math.round(this.vx[i] + (this.random() - .5) * .7);
    let dy = Math.round(this.vy[i] + (this.random() - .5) * .7);
    if (!dx && !dy) { dx = this.random() < .5 ? -1 : 1; }
    dx = Math.sign(dx); dy = Math.sign(dy);
    if (!this.move(i, x + dx, y + dy)) {
      this.vx[i] *= -.8; this.vy[i] *= -.8;
    }
  }

  updateSupport() {
    // One linear-time snapshot per tick. Support propagates uphill from fixed
    // obstacles and chamber boundaries, never from an airborne fluid cluster.
    const n = this.size, supported = this.supportedMatter, queue = this.supportQueue;
    const down = this.zeroGravity ? 0 : NORMAL_GRAVITY;
    supported.fill(0);
    let head = 0, tail = 0;
    for (let y = 0, i = 0; y < n; y++) for (let x = 0; x < n; x++, i++) {
      if (!this.cells[i] || GAS[this.cells[i]] || this.cells[i] === ID.SPARK) continue;
      const gx = this.gravityX[i], gy = this.gravityY[i] + down;
      if (this.blocked(i) || (x === 0 && gx < -1e-9) || (x === n - 1 && gx > 1e-9) ||
          (y === 0 && gy < -1e-9) || (y === n - 1 && gy > 1e-9)) {
        supported[i] = 1; queue[tail++] = i;
      }
    }
    const visit = (j, dx, dy) => {
      const id = this.cells[j];
      if (supported[j] || !id || GAS[id] || id === ID.SPARK) return;
      if (dx * this.gravityX[j] + dy * (this.gravityY[j] + down) <= 1e-9) return;
      supported[j] = 1; queue[tail++] = j;
    };
    while (head < tail) {
      const i = queue[head++], x = i % n, y = Math.floor(i / n);
      if (x) visit(i - 1, 1, 0);
      if (x + 1 < n) visit(i + 1, -1, 0);
      if (y) visit(i - n, 0, 1);
      if (y + 1 < n) visit(i + n, 0, -1);
    }
    this.supportTick = this.tick;
  }

  transportParticle(i, x, y) {
    if (this.supportTick !== this.tick) this.updateSupport();
    const material = ELEMENTS[this.cells[i]], gas = GAS[this.cells[i]] === 1;
    const gx = this.gravityX[i], gy = this.gravityY[i] + (this.zeroGravity ? 0 : NORMAL_GRAVITY);
    const magnitude = Math.hypot(gx, gy), ux = magnitude ? gx / magnitude : 0, uy = magnitude ? gy / magnitude : 0;
    const scale = Math.max(Math.abs(gx), Math.abs(gy));
    const downX = scale ? Math.round(gx / scale) : 0, downY = scale ? Math.round(gy / scale) : 0;
    const inBounds = (px, py) => px >= 0 && py >= 0 && px < this.size && py < this.size;
    const above = (y - downY) * this.size + x - downX;
    const exposed = magnitude > 1e-9 && inBounds(x - downX, y - downY) && (!this.cells[above] || GAS[this.cells[above]] === 1);
    // Surface grains feel the faster air just above the bed, not only the
    // stagnant air at their centers. Shear lifts exposed matter into the flow.
    const airX = exposed ? this.windX[i] * .5 + this.windX[above] * .5 : this.windX[i];
    const airY = exposed ? this.windY[i] * .5 + this.windY[above] * .5 : this.windY[i];
    const shear = Math.abs(airX * uy - airY * ux);
    const drag = gas ? .12 : (.08 + .08 * Math.min(1, Math.sqrt(airX * airX + airY * airY))) / (material.density + .25);
    const below = (y + downY) * this.size + x + downX;
    const onSurface = !inBounds(x + downX, y + downY) || (this.cells[below] && GAS[this.cells[below]] === 0);
    let vx = this.vx[i], vy = this.vy[i];
    vx += (airX * .5 - vx) * drag;
    vy += (airY * .5 - vy) * drag;
    if (gas) {
      // Temperature is a proxy for molecular agitation and expansion. Unlike
      // gravity-driven matter, gas diffuses in every direction with mild lift.
      const agitation = Math.max(.3, Math.min(2.5, (this.heat[i] + 273) / 393));
      vx += (this.random() - .5) * .5 * agitation;
      const jitter = (this.random() - .5) * .5 * agitation;
      const lift = Math.max(-.04, Math.min(.04, (this.heat[i] - this.airHeat[i]) * .00012)) / NORMAL_GRAVITY;
      vx -= gx * lift; vy += jitter - gy * lift;
      this.pressurize(i, Math.max(0, this.heat[i] - 20) * .00002);
    } else {
      if (magnitude > 1e-9) {
        // Immersed liquids feel displaced-fluid weight; hot parcels can rise
        // through colder parcels instead of being forced down every tick.
        let surrounding = 0, neighbors = 0;
        if (material.state === 'liquid' && this.supportedMatter[i]) {
          for (const j of [x ? i - 1 : -1, x + 1 < this.size ? i + 1 : -1, y ? i - this.size : -1, y + 1 < this.size ? i + this.size : -1]) {
            if (j >= 0 && this.supportedMatter[j] && ELEMENTS[this.cells[j]].state === 'liquid') { surrounding += this.density(j); neighbors++; }
          }
        }
        const buoyancy = neighbors >= 2 ? 1 - surrounding / neighbors / this.density(i) : 1;
        vx += gx * buoyancy; vy += gy * buoyancy;
      }
      if (exposed && onSurface && shear > .4) {
        const lift = Math.min(.12, (shear - .4) * .045 / (material.density + .25));
        vx -= ux * lift; vy -= uy * lift;
      }
    }
    this.vx[i] = Math.max(-3, Math.min(3, vx));
    this.vy[i] = Math.max(-3, Math.min(3, vy));
    this.travelX[i] += this.vx[i]; this.travelY[i] += this.vy[i];
    const dx = Math.trunc(this.travelX[i]), dy = Math.trunc(this.travelY[i]);
    this.travelX[i] -= dx; this.travelY[i] -= dy;
    const steps = Math.max(Math.abs(dx), Math.abs(dy));
    let previousX = 0, previousY = 0;
    // Sweep at most three cells, checking every crossed cell (no tunneling).
    for (let step = 1; step <= steps; step++) {
      const offsetX = Math.round(dx * step / steps), offsetY = Math.round(dy * step / steps);
      const sx = offsetX - previousX, sy = offsetY - previousY;
      previousX = offsetX; previousY = offsetY;
      if (sx) {
        if (this.move(i, x + sx, y, true)) { x += sx; i = y * this.size + x; }
        else { this.vx[i] *= gas ? -.5 : -.1; this.travelX[i] = 0; }
      }
      if (sy) {
        if (this.move(i, x, y + sy, true)) { y += sy; i = y * this.size + x; }
        else { this.vy[i] *= gas ? -.5 : -.1; this.travelY[i] = 0; }
      }
    }
    if (gas || magnitude < 1e-9 || (material.state === 'liquid' && !this.supportedMatter[i])) return;
    const support = (y + downY) * this.size + x + downX;
    const supported = !inBounds(x + downX, y + downY) || (this.cells[support] && GAS[this.cells[support]] === 0);
    if (!supported) return;
    const tangent = this.vx[i] * uy - this.vy[i] * ux;
    const side = Math.abs(tangent) > .1 ? Math.sign(tangent) : this.random() < .5 ? -1 : 1;
    const mobile = this.random() < (material.state === 'liquid' ? .6 * (1 - material.viscosity) : .35);
    // Neighbor steps on either side of the downhill direction. Clamp diagonal
    // combinations to one cell so settling cannot leap over a thin obstacle.
    const slide = direction => this.move(i, x + Math.sign(downX + direction * downY), y + Math.sign(downY - direction * downX), true);
    if (mobile && (slide(side) || slide(-side))) return;
    if (material.state === 'liquid' && mobile && (this.move(i, x + side * downY, y - side * downX, true) || this.move(i, x - side * downY, y + side * downX, true))) return;
    const friction = shear > .4 ? .985 : material.state === 'liquid' ? .9 - material.viscosity * .3 : .65;
    this.vx[i] -= tangent * uy * (1 - friction);
    this.vy[i] += tangent * ux * (1 - friction);
  }

  scramble(i, x, y) {
    // One conversion per eight ticks for a readable, bounded reaction rate.
    if (this.phaseLocked[i] && (this.tick + i) % 8) return;
    const start = Math.floor(this.random() * 4);
    for (let turn = 0; turn < 4; turn++) {
      const direction = (start + turn) % 4;
      const nx = x + (direction === 0 ? -1 : direction === 1 ? 1 : 0);
      const ny = y + (direction === 2 ? -1 : direction === 3 ? 1 : 0);
      if (nx < 0 || ny < 0 || nx >= this.size || ny >= this.size) continue;
      const j = ny * this.size + nx, target = this.cells[j];
      if (!target || target === ID.SCRAMBLE || this.phaseLocked[j]) continue;
      // Only real materials (not Erase, Wind, or Scramble), always a change.
      const targetIndex = SCRAMBLE_RESULTS.indexOf(target);
      let choice = Math.floor(this.random() * (SCRAMBLE_RESULTS.length - 1));
      if (choice >= targetIndex) choice++;
      const replacement = SCRAMBLE_RESULTS[choice];
      this.set(j, replacement);
      if (!this.phaseLocked[i]) this.set(i, ID.EMPTY);
      return;
    }
  }

  gravity() {
    if (!this.gravityDirty) return;
    this.gravityDirty = false;
    const sources = [];
    for (let i = 0; i < this.length; i++) if (this.cells[i] === ID.GRAV) sources.push({ x: i % this.size, y: Math.floor(i / this.size), sign: this.polarity[i] });
    radialGravity(this.size, sources, this.gravityX, this.gravityY, GRAV_STRENGTH);
    for (let i = 0; i < this.length; i++) { this.gravityX[i] *= this.gravStrength; this.gravityY[i] *= this.gravStrength; }
  }

  setGravStrength(value) {
    if (!Number.isFinite(value)) return;
    const strength = Math.max(0, Math.min(3, value));
    if (strength === this.gravStrength) return;
    this.gravStrength = strength;
    this.gravityDirty = true;
    this.supportTick = -1;
  }

  bacteria() {
    if (this.tick % 12) return;
    const n = this.size;
    this.neighbors.fill(0); this.lockedNeighbors.fill(0);
    for (let i = 0; i < this.length; i++) if (this.cells[i] === ID.BACTERIUM) {
      const x = i % n, y = Math.floor(i / n);
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
        if ((!dx && !dy) || x + dx < 0 || x + dx >= n || y + dy < 0 || y + dy >= n) continue;
        const j = i + dy * n + dx;
        this.neighbors[j]++; this.lockedNeighbors[j] += this.phaseLocked[i];
      }
    }
    // Conway's rules apply to every colony. Phase lock only isolates cells from
    // other elements: locked cells do not eat, overheat, or react.
    for (let i = 0; i < this.length; i++) {
      const id = this.cells[i], neighbors = this.neighbors[i], locked = this.lockedNeighbors[i];
      if (id === ID.BACTERIUM && neighbors !== 2 && neighbors !== 3) this.set(i, ID.EMPTY);
      else if (!id && neighbors === 3) this.set(i, ID.BACTERIUM, 20, locked >= 2);
      else if (id === ID.SEED && !this.phaseLocked[i] && neighbors > locked) this.set(i, ID.BACTERIUM);
    }
  }

  step() {
    if (++this.tick === 0xffffffff) { this.tick = 1; this.updated.fill(0); this.moved.fill(0); }
    const n = this.size;
    this.gravity(); this.electricity(); this.airThermal(); this.airflow();
    for (let y = 0, i = 0; y < n; y++) for (let x = 0; x < n; x++, i++) {
      if (!this.cells[i]) continue;
      if (x < n - 1) this.thermalPair(i, i + 1);
      if (y < n - 1) this.thermalPair(i, i + n);
      if (this.phaseLocked[i]) continue;
      this.heat[i] += this.charge[i] * this.charge[i] * 1.2;
      // Weak radiative loss to the environment, separate from local air exchange.
      this.heat[i] += (20 - this.heat[i]) * (this.cells[i] === ID.VAPOR ? .003 : this.cells[i] === ID.LAVA ? .0004 : .0001);
    }
    for (let y = n - 1; y >= 0; y--) for (let col = 0; col < n; col++) {
      const x = (this.tick + y) % 2 ? n - 1 - col : col, i = y * n + x;
      let id = this.cells[i];
      if (!id || this.updated[i] === this.tick) continue;
      this.updated[i] = this.tick;
      if (id === ID.SCRAMBLE) {
        this.scramble(i, x, y);
        if (!this.cells[i]) continue;
      }
      if (!this.phaseLocked[i]) {
        if ((id === ID.BACTERIUM || id === ID.BOID) && (this.heat[i] > 90 || this.heat[i] < -10)) { this.set(i, ID.EMPTY); continue; }
        if (id === ID.GUNPOWDER && (this.burn[i] >= 1 || this.heat[i] > 180)) { this.explode(i, x, y); continue; }
        if (id === ID.METAL && this.heat[i] > 800) this.transform(i, ID.LAVA, this.heat[i]);
        if (id === ID.WATER && this.heat[i] > 100) this.transform(i, ID.VAPOR, this.heat[i]);
        else if (id === ID.WATER && this.heat[i] < 0) this.transform(i, ID.ICE, this.heat[i]);
        else if (id === ID.ICE && this.heat[i] > 1) this.transform(i, ID.WATER, this.heat[i]);
        else if (id === ID.NITROGEN && this.heat[i] > -196) this.transform(i, ID.VAPOR, this.heat[i]);
        else if (id === ID.VAPOR && this.nitrogenVapor[i]) {
          if (this.heat[i] < -196) this.transform(i, ID.NITROGEN, this.heat[i]);
        }
        else if (id === ID.VAPOR && this.random() < condensationChance(this.heat[i])) this.transform(i, ID.WATER, this.heat[i]);
        else if (id === ID.OIL || id === ID.SEED) {
          this.burn[i] += ELEMENTS[id].thermal * .15 * Math.max(0, Math.min(2, (this.heat[i] - 130) / 120));
          if (this.heat[i] < 100) this.burn[i] *= .99;
          if (this.burn[i] >= 1) {
            const thermal = ELEMENTS[id].thermal;
            this.set(i, ID.FIRE);
            this.life[i] = Math.round(360 + (1 - thermal) * 240 + this.random() * 180);
          }
        }
        else if (id === ID.SAND && this.heat[i] > 300) this.set(i, ID.CRYSTAL, this.heat[i]);
        else if (id === ID.LAVA && this.heat[i] < 650) this.set(i, ID.STONE, this.heat[i]);
        else if (id === ID.MUD && this.heat[i] > 110) this.set(i, ID.SAND, this.heat[i]);
      }
      id = this.cells[i];
      if (id === ID.FIRE || id === ID.SPARK || id === ID.LAVA || id === ID.SAND) {
        if (x > 0) this.contact(i, i - 1);
        if (x < n - 1) this.contact(i, i + 1);
        if (y > 0) this.contact(i, i - n);
        if (y < n - 1) this.contact(i, i + n);
        id = this.cells[i];
        if (!id) continue;
      }
      if (id === ID.BOID) { this.boid(i, x, y); continue; }
      if (id === ID.FIRE || id === ID.SPARK) {
        if (!this.phaseLocked[i] && --this.life[i] === 0) { this.set(i, ID.EMPTY); continue; }
        if (id === ID.FIRE) {
          if (!this.phaseLocked[i]) this.heat[i] = Math.max(this.heat[i], Math.min(650, this.life[i] * 8));
          this.pressurize(i, .08 * this.heat[i] / 650);
          const gx = this.gravityX[i], gy = this.gravityY[i] + (this.zeroGravity ? 0 : NORMAL_GRAVITY);
          this.gust(i, (this.random() - .5) * .035 - gx * (.07 / NORMAL_GRAVITY), -gy * (.07 / NORMAL_GRAVITY));
          const peak = Math.max(Math.abs(gx), Math.abs(gy));
          if (peak > 1e-9) {
            const ax = x - Math.round(gx / peak), ay = y - Math.round(gy / peak);
            if (ax >= 0 && ay >= 0 && ax < n && ay < n) this.gust(ay * n + ax, -gx * (.04 / NORMAL_GRAVITY), -gy * (.04 / NORMAL_GRAVITY));
          }
        } else { this.drift(i, x, y); continue; }
      }
      if (id === ID.SEED && this.grow(i, x, y)) continue;
      if (!SOLID[id] && id !== ID.BACTERIUM) this.transportParticle(i, x, y);
    }
    this.bacteria();
  }

  scene(name = 'estuary') {
    this.clear();
    const n = this.size;
    const margin = Math.max(1, Math.floor(n * .025)), far = n - margin - 1;
    const chamber = () => {
      const inside = (x, y) => x >= margin && x <= far && y >= margin && y <= far &&
        Math.min(x - margin, far - x) + Math.min(y - margin, far - y) >= 2;
      for (let y = margin; y <= far; y++) for (let x = margin; x <= far; x++) {
        if (!inside(x, y)) continue;
        // An eight-neighbor rim seals the stepped corners against diagonal motion.
        if ([-1, 0, 1].some(dy => [-1, 0, 1].some(dx => !inside(x + dx, y + dy)))) this.set(y * n + x, ID.CRYSTAL);
      }
    };
    if (name === 'convection') {
      chamber();
      const width = Math.max(4, Math.floor(n * .28)), depth = Math.max(2, Math.floor(n * .035));
      // Matched glass reservoirs: a low heater and a suspended cooling bath.
      for (const [left, top, id, temperature] of [
        [margin + 3, far - depth - 2, ID.LAVA, 1100],
        [far - width - 2, margin + 2, ID.NITROGEN, -200]
      ]) {
        for (let y = top; y <= top + depth + 1; y++) for (let x = left; x <= left + width; x++) {
          const wall = x === left || x === left + width || y === top + depth + 1;
          this.set(y * n + x, wall ? ID.CRYSTAL : id, wall ? 20 : temperature, !wall);
        }
      }
      for (let y = margin + 3; y < far - 2; y++) for (let x = margin + 2; x < far - 1; x++) {
        const i = y * n + x;
        if (!this.cells[i] && (x + 3 * y) % 9 === 0) this.set(i, ID.VAPOR, 20, true);
      }
      return;
    }
    if (name === 'water-cycle') {
      chamber();
      const left = margin, right = far, floor = Math.floor(n * .78);
      // A melting-point ice ceiling is a permanent cold reservoir without
      // freezing the rain. A compact, enclosed heater balances its heat removal.
      for (let x = left + 3; x <= right - 3; x++) this.set((margin + 1) * n + x, ID.ICE, 0, true);
      // A thin crystal basin conducts heat from an isolated, perpetual lava bath.
      // The cool upper chamber leaves room for clouds and returning rain.
      for (let x = left; x <= right; x++) {
        this.set(floor * n + x, ID.CRYSTAL);
        if (x > left && x < right) for (let y = floor - Math.max(2, Math.floor(n * .04)); y < floor; y++) this.set(y * n + x, ID.WATER);
        const hearthLeft = Math.floor(n * .44), hearthRight = Math.ceil(n * .56);
        const hearthFloor = Math.min(far - 1, floor + 4);
        for (let y = floor + 1; y < far; y++) {
          if ((x === hearthLeft || x === hearthRight) && y <= hearthFloor || y === hearthFloor && x >= hearthLeft && x <= hearthRight) this.set(y * n + x, ID.STONE);
          else if (x > hearthLeft && x < hearthRight && y > floor + 1 && y < hearthFloor) this.set(y * n + x, ID.LAVA, 1100, true);
        }
      }
      return;
    }
    if (name === 'test-tubes') {
      const top = Math.floor(n * .19), bottom = Math.floor(n * .66), half = Math.max(2, Math.floor(n * .055));
      const gap = Math.max(2, Math.floor(n * .05)), potFloor = Math.min(n - 2, bottom + gap + 2);
      [ID.WATER, ID.OIL, ID.ICE].forEach((material, tube) => {
        const center = Math.floor(n * (.2 + tube * .3)), left = center - half, right = center + half;
        const inside = (x, y) => Math.abs(x - center) <= half && y <= bottom &&
          (y <= bottom - half || (x - center) ** 2 + (y - (bottom - half)) ** 2 <= (half + .5) ** 2);
        for (let y = top; y <= bottom; y++) {
          for (let x = left; x <= right; x++) {
            if (!inside(x, y)) continue;
            const rim = [-1, 0, 1].some(dy => [-1, 0, 1].some(dx => !inside(x + dx, y + dy)));
            if (rim) this.set(y * n + x, ID.CRYSTAL);
            else if (y > bottom - n * .18) this.set(y * n + x, material);
          }
        }
        // Open side pockets accept a painted heat source without opening the tube.
        // On the smallest grids the outer holders reach past the chamber walls.
        const holder = (x, y) => { if (x >= 0 && x < n) this.set(y * n + x, ID.STONE); };
        const potHalf = Math.min(half + gap, Math.floor(n * .14));
        for (let y = bottom - half; y <= potFloor; y++) { holder(center - potHalf, y); holder(center + potHalf, y); }
        for (let x = center - potHalf; x <= center + potHalf; x++) holder(x, potFloor);
      });
      return;
    }
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      const px = x / n, py = y / n, floor = .84 + Math.sin(px * 9) * .04;
      if (py > floor) this.set(y * n + x, ID.SAND);
      else if (py > .72 && px < .55) this.set(y * n + x, ID.WATER);
      else if (py > .68 && py < .72 && px < .35) this.set(y * n + x, ID.OIL);
      else if (py > .53 && py < .55 && px > .57 && px < .85) this.set(y * n + x, ID.STONE);
    }
    this.paint(n * .45, n * .69, ID.SEED, 7);
    this.paint(n * .7, n * .45, ID.SAND, 11);
    this.paint(n * .25, n * .25, ID.VAPOR, 11);
  }
}
