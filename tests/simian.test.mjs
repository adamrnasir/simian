import test from 'node:test';
import assert from 'node:assert/strict';
import { World, ID, ELEMENTS, ANTIGRAV_COLOR, FEESH_COLOR, GRAV_STRENGTH, NORMAL_GRAVITY, MAX_PRESSURE, MAX_AIR_SPEED, condensationChance, elementSymbol } from '../web/engine.mjs';
import { smoothAim } from '../web/aim.mjs';
import { radialGravity } from '../web/gravity.mjs';
import { Renderer, glyphVariant, traceContours } from '../web/renderer.mjs';
import { TICK_RATE, ticksDue } from '../web/clock.mjs';

const count = (world, id) => world.cells.reduce((sum, cell) => sum + Number(cell === id), 0);

test('gravity strength rescales existing sources and survives clearing', () => {
  const w = new World(24); w.set(12 * 24 + 12, ID.GRAV); w.gravity();
  const initial = w.gravityX.slice();
  w.setGravStrength(.5); w.gravity();
  for (let i = 0; i < w.length; i++) assert(Math.abs(w.gravityX[i] - initial[i] * .5) < 1e-8);
  w.setGravStrength(3); w.gravity();
  for (let i = 0; i < w.length; i++) assert(Math.abs(w.gravityX[i] - initial[i] * 3) < 1e-7);
  w.clear(); assert.equal(w.gravStrength, 3);
  w.set(100, ID.GRAV, 20, false, true); w.setGravStrength(0); w.gravity();
  assert(w.gravityX.every(v => v === 0) && w.gravityY.every(v => v === 0));
});

test('birds and swimming feesh counter moderate gravity but strong fields overpower them', () => {
  for (const fish of [false, true]) {
    const accelerate = force => {
      const w = new World(24), i = 12 * 24 + 12;
      if (fish) for (let y = 8; y <= 16; y++) for (let x = 8; x <= 16; x++) w.set(y * 24 + x, ID.WATER, 20, true);
      w.set(i, ID.BOID, 20, false, fish); w.random = () => .5;
      w.vx[i] = .3; w.vy[i] = 0; w.gravityY[i] = force;
      w.boid(i, 12, 12);
      return w.vy[i];
    };
    assert(Math.abs(accelerate(.04)) < 1e-8);
    assert(Math.abs(accelerate(.06) - .01) < 1e-7);
    assert(accelerate(.18) > .12);
    assert(accelerate(-.18) < -.12);
  }
});

test('airborne liquid rows and blobs accelerate together in every gravity direction', () => {
  const n = 32;
  for (const [dx, dy] of [[0, 1], [1, 0], [0, -1], [-1, 0], [Math.SQRT1_2, Math.SQRT1_2]]) {
    for (const depth of [0, 2]) {
      const w = new World(n); w.zeroGravity = true;
      w.gravityX.fill(dx * NORMAL_GRAVITY); w.gravityY.fill(dy * NORMAL_GRAVITY);
      const cells = [];
      for (let y = 16 - depth; y <= 16 + depth; y++) for (let x = 13; x <= 19; x++) {
        const i = y * n + x; w.set(i, ID.WATER, 20, true); cells.push(i);
      }
      w.updateSupport();
      assert(cells.every(i => !w.supportedMatter[i]), 'no airborne parcel has hydrostatic support');
      for (const i of cells) w.transportParticle(i, i % n, Math.floor(i / n));
      for (const i of cells) {
        assert(Math.abs(w.vx[i] - dx * NORMAL_GRAVITY) < 1e-7);
        assert(Math.abs(w.vy[i] - dy * NORMAL_GRAVITY) < 1e-7);
      }
    }
  }
});

test('fluid support reaches through a resting column and disappears when its floor is removed', () => {
  const w = new World(24);
  for (let y = 8; y <= 16; y++) w.set(y * 24 + 12, ID.WATER, 20, true);
  w.set(17 * 24 + 12, ID.STONE); w.updateSupport();
  assert(w.supportedMatter[8 * 24 + 12]);
  w.set(17 * 24 + 12, ID.EMPTY); w.tick++;
  w.transportParticle(8 * 24 + 12, 12, 8);
  assert(!w.supportedMatter[8 * 24 + 12]);
  assert(w.vy[8 * 24 + 12] > 0, 'the top falls immediately, not only when neighbors peel away');
});

test('density sorting, liquid buoyancy, and settling rotate with net gravity', () => {
  const n = 16, i = 8 * n + 8;
  for (const [dx, dy] of [[0, 1], [1, 0], [0, -1], [-1, 0]]) {
    const w = new World(n); w.zeroGravity = true; w.tick = 1;
    w.gravityX.fill(dx * NORMAL_GRAVITY); w.gravityY.fill(dy * NORMAL_GRAVITY);
    w.set(i, ID.WATER, 20, true); w.set(i + dx + dy * n, ID.OIL, 20, true);
    assert(w.move(i, 8 + dx, 8 + dy, true), 'dense liquid sinks along gravity');
    w.tick++;
    assert(!w.move(i + dx + dy * n, 8, 8, true), 'dense liquid cannot rise through lighter liquid');
    w.set(i, ID.WATER, 90, true);
    for (const j of [i - 1, i + 1, i - n, i + n]) w.set(j, ID.WATER, 10, true);
    for (let side = -1; side <= 1; side++) w.set(i + 2 * (dx + dy * n) + side * (dy - dx * n), ID.STONE);
    // Give the side parcels a continuous supported column as well.
    for (const side of [-1, 1]) w.set(i + dx + dy * n + side * (dy - dx * n), ID.WATER, 10, true);
    w.transportParticle(i, 8, 8);
    const warm = w.heat.indexOf(90);
    assert(w.vx[warm] * dx + w.vy[warm] * dy < 0, 'warm parcel rises opposite gravity');
    w.cells.fill(0); w.set(i, ID.SAND); w.set(i + dx + dy * n, ID.STONE);
    w.updateSupport();
    w.random = () => 0;
    w.transportParticle(i, 8, 8);
    const sand = w.cells.indexOf(ID.SAND);
    assert((sand % n - 8) * dx + (Math.floor(sand / n) - 8) * dy > 0, 'supported grains settle downhill even in zero-g with custom gravity');
  }
});

test('density displacement uses combined gravity and vanishes when gravity cancels', () => {
  const w = new World(16), i = 8 * 16 + 8;
  w.tick = 1; w.gravityY.fill(-.06);
  w.set(i, ID.WATER); w.set(i - 16, ID.OIL);
  assert(w.move(i, 8, 7, true), 'custom upward gravity overcomes ordinary gravity');
  w.tick++; w.gravityY.fill(-NORMAL_GRAVITY);
  w.set(i, ID.WATER); w.set(i + 16, ID.OIL);
  assert(!w.move(i, 8, 9, true), 'no density sorting without net gravity');
});

test('thermal air and gas buoyancy follow sideways custom gravity', () => {
  const w = new World(16), i = 8 * 16 + 8;
  w.zeroGravity = true; w.gravityX.fill(NORMAL_GRAVITY);
  w.airHeat.fill(120); w.airflow();
  assert(w.windX[i] < 0 && w.windY[i] === 0, 'hot air rises against sideways gravity');
  w.windX.fill(0); w.windY.fill(0); w.airHeat.fill(20);
  w.set(i, ID.VAPOR, 120, true); w.random = () => .5;
  w.transportParticle(i, 8, 8);
  assert(w.vx[i] < 0 && w.vy[i] === 0, 'gas has no hardcoded upward bias');
});

test('gravity is radial, symmetric, softened, reversible, and cached', () => {
  const w = new World(65), center = 32 * 65 + 32;
  w.set(center, ID.GRAV); w.gravity();
  const axial = center + 25, diagonal = center + 15 + 20 * 65;
  const strength = i => Math.hypot(w.gravityX[i], w.gravityY[i]);
  assert(Math.abs(strength(axial) - strength(diagonal)) < 1e-8, 'equal Euclidean distances have equal strength');
  assert(Math.abs(w.gravityX[diagonal] / w.gravityY[diagonal] - 15 / 20) < 1e-6, 'force points directly at source');
  assert.equal(strength(center), 0, 'no singularity or self-force');
  assert.equal(w.gravityX[center - 25], -w.gravityX[axial]);
  assert(strength(center + 20) > strength(center + 30), 'strength decays radially');
  const original = w.gravityX.slice();
  w.gravity(); assert.deepEqual(w.gravityX, original);
  w.set(center, ID.GRAV, 20, false, true); w.gravity();
  for (let i = 0; i < w.length; i++) assert(Math.abs(w.gravityX[i] + original[i]) < 1e-8);
  w.set(center, ID.EMPTY); w.gravity();
  assert(w.gravityX.every(v => v === 0) && w.gravityY.every(v => v === 0));
});

test('many-source gravity closely matches direct radial forces, including mixed polarities', () => {
  const n = 32, sources = Array.from({ length: 80 }, (_, i) => ({ x: (i * 79 % (n * n)) % n, y: Math.floor((i * 79 % (n * n)) / n), sign: i % 3 ? 1 : -1 }));
  const xs = new Float32Array(n * n), ys = new Float32Array(n * n);
  radialGravity(n, sources, xs, ys, GRAV_STRENGTH);
  let error = 0;
  for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
    let fx = 0, fy = 0;
    for (const p of sources) {
      const dx = p.x - x, dy = p.y - y, r2 = dx * dx + dy * dy + 9, factor = 5 * p.sign / (r2 * Math.sqrt(r2));
      fx += dx * factor; fy += dy * factor;
    }
    const scale = Math.min(1, GRAV_STRENGTH / (Math.hypot(fx, fy) || 1)), i = y * n + x;
    error += (xs[i] - fx * scale) ** 2 + (ys[i] - fy * scale) ** 2;
    assert(Math.hypot(xs[i], ys[i]) <= GRAV_STRENGTH + 1e-8);
  }
  assert(Math.sqrt(error / (n * n)) < GRAV_STRENGTH * .03, 'RMS error below 3% of the acceleration cap');
});

test('liquid nitrogen cools air, boils into vapor, and respects phase lock', () => {
  const w = new World(24);
  w.set(200, ID.NITROGEN);
  for (let t = 0; t < 120; t++) w.step();
  assert.equal(count(w, ID.NITROGEN), 0);
  assert.equal(count(w, ID.VAPOR), 1);
  assert.equal(count(w, ID.WATER), 0, 'nitrogen vapor does not condense into water');
  assert.equal(w.nitrogenVapor[w.cells.indexOf(ID.VAPOR)], 1);
  w.clear(); w.set(200, ID.NITROGEN, -200, true);
  for (let t = 0; t < 120; t++) w.step();
  const i = w.cells.indexOf(ID.NITROGEN);
  assert(i >= 0); assert.equal(w.heat[i], -200); assert.equal(w.phaseLocked[i], 1);
  assert(w.airHeat.some(t => t < 10), 'moving nitrogen significantly cools the air along its path');
  w.clear(); w.set(200, ID.NITROGEN); w.transform(200, ID.VAPOR, -210);
  w.step(); assert.equal(count(w, ID.NITROGEN), 1);
  w.clear(); assert(w.nitrogenVapor.every(v => v === 0));
});

test('temperature overlay maps air and matter, with neutral ambient and bounded opacity', () => {
  const previous = globalThis.document;
  try {
    const world = new World(4);
    world.airHeat[0] = -25; world.airHeat[1] = 200;
    world.set(2, ID.LAVA, 1100, true);
    for (const theme of ['light', 'dark']) {
      globalThis.document = { documentElement: { dataset: { theme } } };
      const data = new Uint8ClampedArray(world.length * 4);
      let presented = false;
      Renderer.prototype.drawTemperature.call({ world, fieldPixels: { data }, presentField() { presented = true; } });
      assert(presented);
      assert(data[2] > data[0], 'cold air is blue');
      assert(data[4] > data[6], 'hot air is red');
      assert(data[11] > data[7], 'lava is more intense than warm air');
      assert.equal(data[15], 0, 'ambient air stays transparent');
      assert(data.every((v, i) => i % 4 !== 3 || v <= 110));
    }
  } finally {
    if (previous === undefined) delete globalThis.document; else globalThis.document = previous;
  }
});

test('aim filters pixel staircase jitter and turns continuously through reversals', () => {
  const direction = { x: 1, y: 0 };
  for (let i = 0; i < 80; i++) smoothAim(direction, i % 2 ? .15 : 0, i % 2 ? 0 : .15);
  assert(direction.x > .6 && direction.x < .8);
  assert(direction.y > .6 && direction.y < .8);
  const before = Math.atan2(direction.y, direction.x);
  smoothAim(direction, -.1, 0);
  assert(Math.abs(Math.atan2(direction.y, direction.x) - before) < .1);
  for (let i = 0; i < 50; i++) smoothAim(direction, -1, 0);
  assert(direction.x < -.99);
  assert(Math.abs(Math.hypot(direction.x, direction.y) - 1) < 1e-10);
});

test('Scramble persists alone, converts a neighbor, and respects locks', () => {
  const world = new World(20), i = 210, j = 211;
  world.set(i, ID.SCRAMBLE);
  world.scramble(i, 10, 10);
  assert.equal(world.cells[i], ID.SCRAMBLE);
  world.set(j, ID.STONE); world.scramble(i, 10, 10);
  assert.equal(world.cells[i], ID.EMPTY);
  assert(world.cells[j] >= ID.SAND && world.cells[j] <= ID.ICE && world.cells[j] !== ID.STONE);
  world.set(i, ID.SCRAMBLE, 20, true); world.tick = 6;
  world.set(j, ID.WATER, 20, true); world.scramble(i, 10, 10);
  assert.equal(world.cells[j], ID.WATER); assert.equal(world.phaseLocked[j], 1);
  world.set(j, ID.STONE);
  for (let t = 0; t < 20; t++) {
    const previous = world.cells[j]; world.tick = 6 + t * 8; world.scramble(i, 10, 10);
    assert.notEqual(world.cells[j], previous);
    assert.equal(world.cells[i], ID.SCRAMBLE); assert.equal(world.phaseLocked[i], 1);
  }
  assert.equal(elementSymbol(ID.WATER, true), '●');
  assert.equal(elementSymbol(ID.ICE, true), '✦');
  assert.equal(elementSymbol(ID.SCRAMBLE, true), '?');
});

test('brush diameter is its exact cell footprint for every supported size', () => {
  for (let diameter = 1; diameter <= 15; diameter++) {
    const world = new World(40);
    world.paint(20, 20, ID.STONE, diameter);
    const xs = [], ys = [];
    world.cells.forEach((id, i) => { if (id) { xs.push(i % 40); ys.push(Math.floor(i / 40)); } });
    assert.equal(Math.max(...xs) - Math.min(...xs) + 1, diameter);
    assert.equal(Math.max(...ys) - Math.min(...ys) + 1, diameter);
    if (diameter === 1) assert.equal(xs.length, 1);
    world.paint(20, 20, ID.EMPTY, diameter);
    assert.equal(count(world, ID.STONE), 0);
  }
});

test('a held wind nozzle propagates forward and stops at a solid wall', () => {
  const open = new World(48), wall = new World(48);
  for (let y = 0; y < 48; y++) wall.set(y * 48 + 20, ID.STONE);
  for (let t = 0; t < 120; t++) for (const world of [open, wall]) {
    world.paint(12, 24, ID.WIND, 5, 1, false, 1, 0); world.airflow();
  }
  assert(open.windX[24 * 48 + 24] > .5, 'Held nozzle reaches particles twelve cells ahead');
  assert.equal(wall.windX[24 * 48 + 24], 0);
  for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1], [.6, .8]]) {
    const world = new World(20); world.paint(10, 10, ID.WIND, 1, 1, false, dx, dy);
    assert(Math.abs(world.windX[210] - .22 * dx) < .00001);
    assert(Math.abs(world.windY[210] - .22 * dy) < .00001);
  }
});

test('holding wind moves a sand pile before releasing the brush', () => {
  const means = [];
  for (const blowing of [false, true]) {
    const world = new World(48);
    for (let x = 0; x < 48; x++) world.set(28 * 48 + x, ID.STONE);
    world.paint(22, 25, ID.SAND, 5);
    const initialCount = count(world, ID.SAND);
    for (let t = 0; t < 150; t++) {
      if (blowing) world.paint(12, 26, ID.WIND, 5, 10, false, 1, 0);
      world.step();
    }
    assert.equal(count(world, ID.SAND), initialCount);
    means.push(world.cells.reduce((sum, id, i) => sum + (id === ID.SAND ? i % 48 : 0), 0) / initialCount);
  }
  assert(means[1] > means[0] + 3);
});

test('minimum wind with a small nozzle moves already-settled powders and liquids', () => {
  for (const material of [ID.SAND, ID.WATER, ID.MUD]) {
    const means = [];
    for (const blowing of [false, true]) {
      const world = new World(64);
      for (let x = 0; x < 64; x++) world.set(45 * 64 + x, ID.STONE);
      world.paint(24, 43, material, 3);
      for (let t = 0; t < 120; t++) world.step();
      for (let t = 0; t < 150; t++) {
        if (blowing) world.paint(18, 43, ID.WIND, 3, 10, false, 1, 0);
        world.step();
      }
      assert.equal(count(world, material), 9);
      means.push(world.cells.reduce((sum, id, i) => sum + (id === material ? i % 64 : 0), 0) / 9);
    }
    assert(means[1] > means[0] + 8, ELEMENTS[material].name);
  }
});

test('upper wind strengths retain distinct pressure above the old ceiling and stay bounded', () => {
  const weak = new World(24), strong = new World(24);
  for (let t = 0; t < 30; t++) {
    weak.paint(12, 12, ID.WIND, 1, 5);
    strong.paint(12, 12, ID.WIND, 1, 10);
  }
  const center = 12 * 24 + 11;
  assert(weak.pressure[center] > 6);
  assert.equal(strong.pressure[center], weak.pressure[center] * 2);
  strong.pressurize(center, 1000);
  assert.equal(strong.pressure[center], MAX_PRESSURE);
  for (let t = 0; t < 100; t++) strong.airflow();
  assert(strong.pressure.every(value => Number.isFinite(value) && Math.abs(value) <= MAX_PRESSURE));
  assert(strong.windX.every(value => Number.isFinite(value) && Math.abs(value) <= MAX_AIR_SPEED));
});

test('phase lock preserves material and temperature through heat, reactions, and movement', () => {
  for (const [id, temperature] of [[ID.WATER, 200], [ID.VAPOR, 0], [ID.ICE, 80], [ID.LAVA, 400], [ID.OIL, 600], [ID.FIRE, 650], [ID.MUD, 200], [ID.SAND, 600]]) {
    const world = new World(12);
    world.set(65, id, temperature, true);
    world.charge[65] = 2;
    for (let t = 0; t < 650; t++) world.step();
    const index = world.cells.indexOf(id);
    assert(index >= 0, ELEMENTS[id].name);
    assert.equal(world.phaseLocked[index], 1);
    assert.equal(world.heat[index], temperature);
    assert.equal(glyphVariant(world, index), 4);
  }
  const world = new World(12);
  world.set(65, ID.LAVA, 1100, true); world.set(66, ID.WATER, 20, true);
  world.thermalPair(65, 66); world.contact(65, 66);
  assert.equal(world.heat[65], 1100); assert.equal(world.heat[66], 20);
  assert.equal(world.cells[65], ID.LAVA); assert.equal(world.cells[66], ID.WATER);
  world.set(66, ID.CRYSTAL); world.thermalPair(65, 66);
  assert(world.heat[66] > 20); assert.equal(world.heat[65], 1100);
  world.paint(5, 5, ID.EMPTY, 3);
  assert.equal(world.phaseLocked[65], 0);
});

test('water cycle repeatedly evaporates and rains without consuming its heater or water', () => {
  const world = new World(64); world.scene('water-cycle');
  const water = count(world, ID.WATER), lava = count(world, ID.LAVA);
  let boiled = 0, condensed = 0;
  const set = world.set.bind(world);
  world.set = (i, id, ...args) => {
    if (world.cells[i] === ID.WATER && id === ID.VAPOR) boiled++;
    if (world.cells[i] === ID.VAPOR && id === ID.WATER) condensed++;
    set(i, id, ...args);
  };
  for (let t = 0; t < 1800; t++) world.step();
  assert(boiled > water && condensed > water);
  assert.equal(count(world, ID.WATER) + count(world, ID.VAPOR), water);
  assert.equal(count(world, ID.LAVA), lava);
  assert(world.heat.some((heat, i) => world.cells[i] === ID.CRYSTAL && heat > 100));
  for (let i = 0; i < world.length; i++) if (world.cells[i] === ID.LAVA) assert.equal(world.heat[i], 1100);
  const margin = Math.max(1, Math.floor(world.size * .025));
  for (let i = 0; i < world.length; i++) if ([ID.WATER, ID.VAPOR].includes(world.cells[i])) {
    const x = i % world.size, y = Math.floor(i / world.size);
    assert(x > margin && x < world.size - margin - 1 && y > margin && y < Math.floor(world.size * .8), 'water and vapor remain inside the basin chamber');
  }
});

test('scene chambers seal diagonal corners at every supported scale', () => {
  for (const n of [24, 32, 64, 208]) for (const scene of ['water-cycle', 'convection']) {
    const w = new World(n); w.scene(scene);
    const seen = new Uint8Array(w.length), queue = [0]; seen[0] = 1;
    for (let head = 0; head < queue.length; head++) {
      const i = queue[head], x = i % n, y = Math.floor(i / n);
      assert(![ID.WATER, ID.VAPOR, ID.LAVA, ID.NITROGEN].includes(w.cells[i]), `${scene} reservoir is sealed at ${n}`);
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
        const px = x + dx, py = y + dy, j = py * n + px;
        if (px < 0 || py < 0 || px >= n || py >= n || seen[j] || w.blocked(j)) continue;
        seen[j] = 1; queue.push(j);
      }
    }
    assert(count(w, ID.LAVA) > 0);
    if (scene === 'convection') { assert(count(w, ID.NITROGEN) > 0); assert.equal(count(w, ID.ICE), 0); }
  }
});

test('test tube holders admit lava and conduct heat through intact crystal', () => {
  for (const size of [64, 96]) {
    const world = new World(size); world.scene('test-tubes');
    const center = Math.floor(size * .2), bottom = Math.floor(size * .66);
    assert.equal(world.cells[(bottom + 1) * size + center], ID.EMPTY);
    const crystal = count(world, ID.CRYSTAL);
    const half = Math.max(2, Math.floor(size * .055)), gap = Math.max(2, Math.floor(size * .05));
    for (let y = bottom - half; y < bottom + gap + 2; y++) for (let x = center - half - gap + 1; x < center + half + gap; x++) {
      if (!world.cells[y * size + x]) world.set(y * size + x, ID.LAVA, 1100, true);
    }
    for (let t = 0; t < 350; t++) world.step();
    assert.equal(count(world, ID.CRYSTAL), crystal);
    assert(world.heat[bottom * size + center] > 100);
    assert(count(world, ID.VAPOR) > 0);
  }
});

test('bounded brush, non-overwriting paint, and complete metadata cleanup', () => {
  const world = new World(20);
  world.paint(0, 0, ID.SPARK, 3);
  const initial = count(world, ID.SPARK);
  world.paint(0, 0, ID.STONE, 3);
  assert.equal(count(world, ID.SPARK), initial);
  world.paint(0, 0, ID.EMPTY, 3);
  assert.equal(count(world, ID.SPARK), 0);
  assert(world.charge.every(value => value === 0));
  assert(world.life.every(value => value === 0));
  assert(world.roots.every(value => value === -1));
});

test('gravity accelerates gradually; scaffold stays fixed', () => {
  const world = new World(20);
  world.set(50, ID.SAND); world.set(310, ID.STONE); world.set(210, ID.VAPOR);
  world.step();
  assert.equal(world.cells[50], ID.SAND);
  assert(Math.abs(world.vy[50] - .045) < .00001);
  assert.equal(world.cells[310], ID.STONE);
  assert.equal(world.cells[210], ID.VAPOR);
  for (let t = 0; t < 15; t++) world.step();
  assert(world.cells.indexOf(ID.SAND) > 50);
  assert.equal(world.cells[310], ID.STONE);
});

test('airborne matter retains sideways momentum and cannot tunnel through walls', () => {
  for (const id of [ID.SAND, ID.WATER, ID.OIL]) {
    const world = new World(32);
    world.set(10 * 32 + 10, id); world.vx[330] = 2;
    for (let t = 0; t < 8; t++) world.step();
    const i = world.cells.indexOf(id);
    assert(i % 32 > 17, ELEMENTS[id].name);
    assert(world.vx[i] > .5);
    world.clear(); world.set(10 * 32 + 10, id); world.vx[330] = 3;
    for (let y = 0; y < 32; y++) world.set(y * 32 + 11, ID.STONE);
    for (let t = 0; t < 30; t++) world.step();
    assert(world.cells.indexOf(id) % 32 < 11);
  }
});

test('vapor diffuses sideways and hot gas expands more strongly without racing upward', () => {
  const spreads = [];
  for (const temperature of [40, 400]) {
    const world = new World(64); world.paint(32, 32, ID.VAPOR, 7, 1, true);
    for (let i = 0; i < world.length; i++) if (world.cells[i]) world.heat[i] = temperature;
    const population = count(world, ID.VAPOR);
    for (let t = 0; t < 90; t++) world.step();
    let variance = 0, height = 0;
    world.cells.forEach((id, i) => { if (id === ID.VAPOR) { variance += (i % 64 - 32) ** 2; height += Math.floor(i / 64); } });
    assert.equal(count(world, ID.VAPOR), population);
    assert(variance / population > 20);
    assert(height / population > 8, 'Gas should diffuse, not instantly collect at the roof');
    spreads.push(variance / population);
  }
  assert(spreads[1] > spreads[0]);
});

test('phase changes preserve momentum and replacement clears fractional travel', () => {
  const world = new World(16); world.set(40, ID.WATER, 120);
  world.vx[40] = 1.5; world.vy[40] = -.5; world.travelX[40] = .4;
  world.transform(40, ID.VAPOR, 120);
  assert.equal(world.vx[40], 1.5); assert.equal(world.vy[40], -.5);
  world.set(40, ID.EMPTY);
  assert.equal(world.vx[40], 0); assert.equal(world.travelX[40], 0);
});

test('sand sinks through oil without losing particles', () => {
  const world = new World(16);
  for (let i = 0; i < world.length; i++) world.set(i, ID.OIL);
  world.set(24, ID.SAND);
  for (let i = 0; i < 32; i++) world.step();
  assert.equal(count(world, ID.SAND), 1);
  assert.equal(count(world, ID.OIL), 255);
  assert(world.cells.indexOf(ID.SAND) >= 224);
});

test('condensation is probabilistic, with a shorter half-life at lower temperatures', () => {
  assert(condensationChance(20) > condensationChance(60));
  assert(condensationChance(60) > condensationChance(90));
  assert.equal(condensationChance(110), 0);
  const world = new World(24);
  for (let i = 0; i < 200; i++) world.set(i, ID.VAPOR, 20);
  for (let i = 0; i < 20; i++) world.step();
  assert(count(world, ID.WATER) > 10);
  assert(count(world, ID.VAPOR) > 10);
  assert.equal(count(world, ID.VAPOR) + count(world, ID.WATER), 200);
});

test('water boils, freezes, and ice melts according to temperature', () => {
  const world = new World(20);
  world.set(100, ID.WATER, 130); world.set(200, ID.WATER, -10); world.set(300, ID.ICE, 10);
  world.step();
  assert.equal(count(world, ID.VAPOR), 1);
  assert.equal(count(world, ID.ICE), 1);
  assert.equal(count(world, ID.WATER), 1);
});

test('fuel ignites gradually, sand fuses, and sparks expire', () => {
  const world = new World(20);
  world.set(10, ID.OIL, 250); world.set(100, ID.SAND, 500); world.set(300, ID.SPARK);
  world.step();
  assert.equal(count(world, ID.FIRE), 0);
  assert.equal(count(world, ID.CRYSTAL), 1);
  for (let i = 0; i < 40; i++) world.step();
  assert.equal(count(world, ID.SPARK), 0);
  for (let i = 0; i < 240; i++) world.step();
  assert(count(world, ID.FIRE) > 0);
});

test('thermal and electrical conductivity are independent', () => {
  const world = new World(20);
  world.set(200, ID.STONE, 100); world.set(201, ID.STONE, 20);
  world.charge[200] = 1;
  world.step();
  assert(world.heat[201] > 20);
  assert.equal(world.charge[201], 0);
  assert(ELEMENTS[ID.ICE].thermal > ELEMENTS[ID.ICE].electrical * 10);
});

test('visible charge front reverses and cannot cross an insulating gap', () => {
  const world = new World(32);
  const start = 16 * 32 + 5;
  for (let j = 0; j < 20; j++) world.set(start + j, ID.CRYSTAL);
  world.set(start + 21, ID.CRYSTAL);
  world.charge[start] = 1;
  let farPeak = 0, negative = false, returnPeak = 0;
  for (let tick = 0; tick < 240; tick++) {
    world.electricity();
    farPeak = Math.max(farPeak, Math.abs(world.charge[start + 18]));
    if (tick > 20) returnPeak = Math.max(returnPeak, Math.abs(world.charge[start]));
    negative ||= world.charge.some(value => value < -.02);
    assert.equal(world.charge[start + 21], 0);
  }
  assert(farPeak > .08, `front peak ${farPeak}`);
  assert(returnPeak > .05, `reflected peak ${returnPeak}`);
  assert(negative);
});

test('spark contact injects one bounded pulse and heats fuel without instant ignition', () => {
  const world = new World(20);
  world.set(180, ID.SPARK); world.set(181, ID.CRYSTAL);
  world.contact(180, 181);
  const firstPulse = world.charge[181];
  world.contact(180, 181);
  assert.equal(world.charge[181], firstPulse);
  assert(firstPulse > 0);
  world.clear();
  for (let y = 10; y < 20; y++) for (let x = 0; x < 20; x++) world.set(y * 20 + x, ID.OIL);
  world.set(190, ID.SPARK); world.step();
  assert.equal(count(world, ID.FIRE), 0);
  assert(world.burn.some(value => value > 0));
});

test('lava quenches in water and solidifies on cooling; sand mixes into mud', () => {
  const world = new World(20);
  world.set(200, ID.LAVA); world.set(201, ID.WATER); world.contact(200, 201);
  assert.equal(world.cells[200], ID.STONE);
  assert.equal(world.cells[201], ID.VAPOR);
  world.set(300, ID.LAVA, 400); world.set(350, ID.MUD, 150); world.step();
  assert.equal(count(world, ID.LAVA), 0); assert.equal(count(world, ID.MUD), 0);
  world.set(100, ID.SAND); world.set(101, ID.WATER);
  world.random = () => 0; world.contact(100, 101);
  assert.equal(world.cells[100], ID.MUD); assert.equal(world.cells[101], ID.EMPTY);
});

test('fire emits rising wind; currents push vapor and decay behind solid barriers', () => {
  const world = new World(24);
  world.set(300, ID.FIRE); world.step();
  assert(world.windY.some(value => value < -.03));
  assert(world.pressure.some(value => value > 0));
  assert.equal(count(world, ID.WIND), 0);
  world.clear(); world.set(300, ID.VAPOR); world.gust(300, 12, 0);
  world.random = () => .5; world.step();
  assert(world.vx[300] > .02, 'Airflow accelerates vapor rather than teleporting it');
  world.clear();
  for (let y = 0; y < 24; y++) world.set(y * 24 + 12, ID.STONE);
  world.gust(12 * 24 + 11, 3, 0);
  for (let tick = 0; tick < 20; tick++) world.airflow();
  for (let y = 0; y < 24; y++) assert.equal(world.windX[y * 24 + 13], 0);
});

test('spark brush emits radially rather than rising as a gas', () => {
  const world = new World(32);
  world.paint(16, 16, ID.SPARK, 7);
  assert(world.vx[16 * 32 + 13] < 0); assert(world.vx[16 * 32 + 19] > 0);
  assert(world.vy[13 * 32 + 16] < 0); assert(world.vy[19 * 32 + 16] > 0);
  for (let tick = 0; tick < 5; tick++) world.step();
  assert(world.cells.some((id, i) => id === ID.SPARK && Math.floor(i / 32) > 20));
  assert(world.cells.some((id, i) => id === ID.SPARK && Math.floor(i / 32) < 12));
});

test('wind brush adds a directional jet and balanced pressure without replacing particles', () => {
  const world = new World(32);
  world.set(16 * 32 + 16, ID.WATER);
  world.paint(16, 16, ID.WIND, 3);
  assert.equal(world.cells.filter(Boolean).length, 1);
  assert.equal(world.cells[16 * 32 + 16], ID.WATER);
  assert(world.pressure.some(value => value > 0));
  assert(world.pressure.some(value => value < 0));
  assert(Math.abs(world.pressure.reduce((a, b) => a + b, 0)) < .00001);
  assert(world.windX[16 * 32 + 16] > .2);
  assert(world.windY.every(value => value === 0));
  for (let t = 0; t < 8; t++) world.airflow();
  assert(world.pressure.some(value => value < -.001), 'Pressure pulse must also produce rarefaction');
});

test('wind remains after release and higher settings reduce damping', () => {
  const weak = new World(24), strong = new World(24);
  weak.windStrength = 10; strong.windStrength = 100;
  for (let y = 10; y < 14; y++) for (let x = 10; x < 14; x++) {
    weak.pressurize(y * 24 + x, 4); strong.pressurize(y * 24 + x, 4);
  }
  const energy = world => world.pressure.reduce((sum, p, i) => sum + p * p + world.windX[i] ** 2 + world.windY[i] ** 2, 0);
  const initialWeak = energy(weak), initialStrong = energy(strong);
  for (let t = 0; t < 40; t++) { weak.airflow(); strong.airflow(); }
  assert(energy(strong) / initialStrong > energy(weak) / initialWeak);
  assert(energy(strong) < initialStrong);
  for (let t = 0; t < 600; t++) { weak.airflow(); strong.airflow(); }
  assert(energy(strong) > .1, 'Circulation must not vanish within seconds');
  assert(energy(strong) > energy(weak));
});

test('wind strength scales momentum; unforced pressure waves remain approximately radial', () => {
  const weak = new World(64), strong = new World(64);
  weak.paint(32, 32, ID.WIND, 3, .2); strong.paint(32, 32, ID.WIND, 3, 2);
  const center = 32 * 64 + 32;
  assert(Math.abs(strong.windX[center] / weak.windX[center] - 10) < .001);
  const radial = new World(64);
  for (let dy = -6; dy <= 6; dy++) for (let dx = -6; dx <= 6; dx++) {
    if (dx * dx + dy * dy <= 36) radial.pressurize((32 + dy) * 64 + 32 + dx, .6 * Math.exp(-(dx * dx + dy * dy) / (36 * .3)));
  }
  for (let t = 0; t < 8; t++) radial.airflow();
  // (5,0) and (3,4) are the same radius but different orientations.
  const axial = radial.pressure[32 * 64 + 37], diagonal = radial.pressure[36 * 64 + 35];
  assert(axial > .01 && diagonal > .01);
  assert(Math.abs(axial - diagonal) / Math.max(axial, diagonal) < .12);
});

test('all material palette colors have strong contrast against both field backgrounds', () => {
  const luminance = hex => {
    const channels = hex.slice(1).match(/../g).map(value => parseInt(value, 16) / 255)
      .map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4);
    return channels[0] * .2126 + channels[1] * .7152 + channels[2] * .0722;
  };
  // Stone's glyph is a solid block, a graphical object rather than text, so it
  // needs WCAG's 3:1 non-text contrast; every other glyph needs 4.5:1.
  for (const element of [...ELEMENTS, { name: 'Antigrav', ...ANTIGRAV_COLOR }, { name: 'Feesh', ...FEESH_COLOR }]) {
    const minimum = element.name === 'Stone' ? 3 : 4.5;
    assert((luminance('#f5f4f0') + .05) / (luminance(element.light) + .05) >= minimum, `${element.name} light`);
    assert((luminance(element.dark) + .05) / (luminance('#080909') + .05) >= minimum, `${element.name} dark`);
  }
});

test('pressure deflects around a finite obstacle and develops a rotating wake', () => {
  const world = new World(32);
  for (let y = 10; y < 22; y++) world.set(y * 32 + 16, ID.STONE);
  for (let y = 8; y < 24; y++) for (let x = 8; x < 12; x++) world.pressurize(y * 32 + x, 4);
  let transverse = 0, curl = 0, behind = 0;
  for (let t = 0; t < 80; t++) {
    world.airflow();
    transverse = Math.max(transverse, Math.abs(world.windY[10 * 32 + 15]));
    curl = Math.max(curl, ...world.curl.map(Math.abs));
    behind = Math.max(behind, Math.abs(world.pressure[9 * 32 + 18]));
  }
  assert(transverse > .01); assert(curl > .01); assert(behind > .01);
});

test('conductivity changes wave travel time and does not instantly saturate a conductor', () => {
  const arrival = id => {
    const world = new World(32), start = 16 * 32 + 5;
    for (let j = 0; j < 20; j++) world.set(start + j, id);
    world.charge[start] = 1;
    for (let t = 0; t < 400; t++) {
      world.electricity();
      if (Math.abs(world.charge[start + 18]) > .08) return t;
    }
    return Infinity;
  };
  const fast = arrival(ID.CRYSTAL), slow = arrival(ID.MUD);
  assert(fast > 40 && fast < 120); assert(slow > fast * 2 && slow < 350);
});

test('thermal conductivity controls fuel ignition time', () => {
  const ignition = id => {
    const world = new World(20);
    world.set(210, id, 250);
    for (let t = 0; t < 600; t++) { world.step(); if (world.cells.includes(ID.FIRE)) return t; }
    return Infinity;
  };
  const seedTime = ignition(ID.SEED), oilTime = ignition(ID.OIL);
  assert(seedTime > 30 && oilTime > seedTime && oilTime < 600);
});

test('seeds require sand or mud plus water before rooting', () => {
  const world = new World(20);
  world.set(210, ID.SEED); world.set(230, ID.STONE); world.set(209, ID.WATER);
  assert.equal(world.grow(210, 10, 10), false);
  assert.equal(world.cells[209], ID.WATER);
  world.set(230, ID.SAND); world.set(209, ID.EMPTY);
  assert.equal(world.grow(210, 10, 10), false);
  world.set(209, ID.WATER);
  assert.equal(world.grow(210, 10, 10), true);
  assert.equal(world.roots[210], 210); assert.equal(world.cells[209], ID.EMPTY);
});

test('watered roots produce upward branches and stop extending when the supply is exhausted', () => {
  const world = new World(32);
  for (let y = 26; y < 32; y++) for (let x = 0; x < 32; x++) world.set(y * 32 + x, ID.SAND);
  const root = 25 * 32 + 16;
  world.set(root, ID.SEED);
  world.set(root - 1, ID.WATER); world.set(root + 1, ID.WATER);
  for (let tick = 0; tick < 1200; tick++) world.step();
  assert(count(world, ID.SEED) > 4);
  assert(world.cells.some((id, i) => id === ID.SEED && Math.floor(i / 32) < 23));
  assert(world.branch.some(direction => direction !== 0));
  const before = count(world, ID.SEED);
  world.moisture.fill(0);
  for (let i = 0; i < world.length; i++) if (world.cells[i] === ID.WATER || world.cells[i] === ID.MUD) world.set(i, ID.SAND);
  for (let tick = 0; tick < 100; tick++) world.step();
  assert.equal(count(world, ID.SEED), before);
});

test('glyph weight distinguishes vapor temperature, stem maturity, and charge', () => {
  const world = new World(20);
  world.set(0, ID.VAPOR, 120); assert.equal(glyphVariant(world, 0), 0);
  world.heat[0] = 40; assert.equal(glyphVariant(world, 0), 2);
  world.set(1, ID.SEED); world.roots[1] = 1; world.life[1] = 2;
  assert.equal(glyphVariant(world, 1), 2);
  world.set(2, ID.CRYSTAL); world.charge[2] = -.4;
  assert.equal(glyphVariant(world, 2), 3);
});

test('deterministic scenes and finite bounded fields under dense mixed load', () => {
  const first = new World(32), second = new World(32);
  first.scene(); second.scene();
  for (let i = 0; i < 100; i++) { first.step(); second.step(); }
  assert.deepEqual(first.cells, second.cells);
  for (let i = 0; i < first.length; i++) first.set(i, i % ELEMENTS.length);
  for (let i = 0; i < 300; i++) first.step();
  assert(first.cells.every(id => id < ELEMENTS.length));
  assert(first.heat.every(Number.isFinite));
  assert(first.charge.every(value => Number.isFinite(value) && Math.abs(value) <= 3));
  assert(first.windX.every(value => Number.isFinite(value) && Math.abs(value) <= MAX_AIR_SPEED));
  assert.equal(new Set(ELEMENTS.map(element => element.symbol)).size, ELEMENTS.length);
});

test('hot lava melts metal that conduction alone would keep solid; stone and locked metal are distinct', () => {
  const n = 32, world = new World(n, 5);
  for (let x = 8; x < 24; x++) world.set(28 * n + x, ID.METAL);
  world.paint(16, 24, ID.LAVA, 7);
  for (let t = 0; t < 600; t++) world.step();
  assert.ok(count(world, ID.METAL) < 16);
  const locked = new World(8, 5);
  locked.set(0, ID.METAL, 20, true); locked.set(1, ID.LAVA, 1100, true);
  for (let t = 0; t < 200; t++) locked.step();
  assert.equal(locked.cells[0], ID.METAL);
  assert.notEqual(elementSymbol(ID.METAL, true), elementSymbol(ID.STONE));
  assert.ok(ELEMENTS[ID.METAL].thermal > ELEMENTS[ID.STONE].thermal && ELEMENTS[ID.METAL].electrical > .5);
});

test('grav lifts resting sand slightly above ordinary gravity; antigrav repels', () => {
  const n = 32;
  for (const antigrav of [false, true]) {
    const world = new World(n, 5);
    for (let x = 0; x < n; x++) for (let y = 29; y < n; y++) world.set(y * n + x, ID.SAND);
    world.set(20 * n + 16, ID.GRAV, 20, false, antigrav);
    for (let t = 0; t < 300; t++) world.step();
    let lifted = 0;
    for (let i = 0; i < 29 * n; i++) lifted += Number(world.cells[i] === ID.SAND);
    assert.ok(Math.abs(world.gravityY[26 * n + 16] - (antigrav ? GRAV_STRENGTH : -GRAV_STRENGTH)) < 1e-6);
    if (antigrav) assert.equal(lifted, 0); else assert.ok(lifted > 0);
  }
  assert.ok(GRAV_STRENGTH > .045 && GRAV_STRENGTH < .09);
  const world = new World(8, 5);
  world.set(10, ID.GRAV); world.step();
  world.set(10, ID.EMPTY); world.step();
  assert.ok(world.gravityX.every(value => value === 0) && world.gravityY.every(value => value === 0));
});

test('bacteria follow Life rules whether or not locked, eat plants, and locks isolate them', () => {
  const n = 16, generation = world => { for (let t = 0; t < 12; t++) world.step(); };
  const cells = world => [...world.cells.keys()].filter(i => world.cells[i] === ID.BACTERIUM).join();
  for (const locked of [false, true]) {
    const world = new World(n, 5);
    for (const x of [5, 6, 7]) world.set(5 * n + x, ID.BACTERIUM, 20, locked);
    const start = cells(world);
    generation(world); const middle = cells(world);
    generation(world);
    assert.notEqual(middle, start);
    assert.equal(cells(world), start);
    assert.ok([...world.cells.keys()].every(i => world.cells[i] !== ID.BACTERIUM || world.phaseLocked[i] === Number(locked)));
  }
  const eating = new World(n, 5);
  for (const x of [5, 6, 7]) eating.set(5 * n + x, ID.BACTERIUM);
  eating.set(5 * n + 8, ID.SEED); for (const x of [7, 8, 9]) eating.set(6 * n + x, ID.STONE);
  generation(eating);
  assert.equal(eating.cells[5 * n + 8], ID.BACTERIUM);
  const guarded = new World(n, 5);
  for (const x of [5, 6, 7]) guarded.set(5 * n + x, ID.BACTERIUM, 20, true);
  guarded.set(5 * n + 8, ID.SEED); for (const x of [7, 8, 9]) guarded.set(6 * n + x, ID.STONE);
  generation(guarded);
  assert.equal(guarded.cells[5 * n + 8], ID.SEED);
  const heat = new World(n, 5);
  for (const locked of [false, true]) {
    const y = locked ? 10 : 4;
    // A stable block isolates thermal immunity from oscillator births being
    // obstructed by lava whose movement depends on buoyancy.
    for (const x of [5, 6]) for (const row of [y - 1, y]) heat.set(row * n + x, ID.BACTERIUM, 20, locked);
    for (const x of [5, 6, 7]) heat.set((y + 1) * n + x, ID.LAVA, 1100, true);
  }
  generation(heat); generation(heat);
  assert.ok([...heat.cells.keys()].every(i => heat.cells[i] !== ID.BACTERIUM || heat.phaseLocked[i]));
  assert.ok(count(heat, ID.BACTERIUM) > 0);
});

test('air carries heat, exchanges with reservoirs, and resets independently of particles', () => {
  const w = new World(24), i = 12 * 24 + 12;
  w.set(i, ID.ICE, -25, true);
  for (let t = 0; t < 80; t++) w.step();
  assert(w.airHeat[i - 1] < 15, 'ice chills adjacent air');
  assert.equal(w.heat[i], -25);
  w.set(i, ID.EMPTY);
  assert(w.airHeat[i - 1] < 15, 'erasing does not erase the thermal field');
  w.clear(); w.set(i, ID.LAVA, 1100, true); w.airThermal();
  assert(w.airHeat[i] > 20);
  assert.equal(w.heat[i], 1100);
  w.clear(); w.zeroGravity = true;
  w.airHeat[i] = 200; w.windX.fill(1); w.airflow();
  assert(w.airHeat[i + 1] > 20, 'flow advects heat');
  w.clear(); w.airHeat.fill(0); w.airflow();
  assert(w.windY.every(v => v === 0), 'zero-g disables thermal lift');
  w.zeroGravity = false; w.airflow();
  assert(w.windY[i] > 0, 'cold air sinks');
  w.clear(); w.airHeat.fill(100); w.airflow();
  assert(w.windY[i] < 0, 'hot air rises');
  w.clear(); assert(w.airHeat.every(v => v === 20));
});

test('warm liquid rises through cold liquid, with direction-aware density displacement', () => {
  const w = new World(16), i = 8 * 16 + 8;
  w.tick = 1;
  w.set(i, ID.WATER, 90, true); w.set(i - 16, ID.WATER, 10, true);
  assert(w.density(i) < w.density(i - 16));
  assert(w.move(i, 8, 7, true));
  assert.equal(w.heat[i - 16], 90);
  w.tick++;
  assert.equal(w.move(i - 16, 8, 8, true), false, 'warm water cannot sink through cold water');
  for (const j of [i - 1, i + 1, i - 16, i + 16]) w.set(j, ID.WATER, 10, true);
  for (let x = 7; x <= 9; x++) { w.set(10 * 16 + x, ID.STONE); w.set(9 * 16 + x, ID.WATER, 10, true); }
  w.set(i, ID.WATER, 90, true); w.transportParticle(i, 8, 8);
  assert(w.vy[w.heat.indexOf(90)] < 0, 'immersed warm water accelerates upward');
});

test('convection scene circulates locked vapor without consuming reservoirs', () => {
  const w = new World(32); w.scene('convection');
  const initial = [ID.VAPOR, ID.LAVA, ID.NITROGEN].map(id => count(w, id));
  let rising = 0, falling = 0;
  for (let t = 0; t < 1600; t++) {
    w.step();
    if (t > 800) for (let i = 0; i < w.length; i++) if (w.cells[i] === ID.VAPOR) {
      if (i % 32 < 16) rising += w.vy[i]; else falling += w.vy[i];
    }
  }
  assert(rising < 0 && falling > 0, 'vapor traces a rising hot limb and descending cool limb');
  assert.deepEqual([ID.VAPOR, ID.LAVA, ID.NITROGEN].map(id => count(w, id)), initial);
  for (let i = 0; i < w.length; i++) {
    const id = w.cells[i];
    if ([ID.VAPOR, ID.LAVA, ID.NITROGEN].includes(id)) {
      assert(w.phaseLocked[i]);
      assert.equal(w.heat[i], id === ID.VAPOR ? 20 : id === ID.LAVA ? 1100 : -200);
    }
    assert(Number.isFinite(w.airHeat[i]));
  }
});

test('ignited gunpowder chain-detonates into a bounded blast of pressure, wind, fire, and debris', () => {
  const n = 48, world = new World(n, 5);
  for (let x = 0; x < n; x++) for (let y = 44; y < n; y++) world.set(y * n + x, ID.SAND);
  for (let x = 18; x < 30; x++) for (let y = 40; y < 44; y++) world.set(y * n + x, ID.GUNPOWDER, 20, true);
  assert.ok(world.phaseLocked.every(value => !value));
  for (let t = 0; t < 30; t++) world.step();
  assert.equal(count(world, ID.GUNPOWDER), 48);
  world.set(39 * n + 24, ID.SPARK);
  world.vx[39 * n + 24] = 0; world.vy[39 * n + 24] = 1;
  let peakPressure = 0, peakWind = 0, sawFire = false;
  for (let t = 0; t < 20; t++) {
    world.step();
    peakPressure = Math.max(peakPressure, ...world.pressure);
    peakWind = Math.max(peakWind, ...world.windX.map(Math.abs));
    sawFire ||= count(world, ID.FIRE) > 10;
  }
  assert.equal(count(world, ID.GUNPOWDER), 0);
  assert.ok(sawFire && peakPressure > 40 && peakPressure <= MAX_PRESSURE && peakWind > 4 && peakWind <= MAX_AIR_SPEED);
  let thrown = 0;
  for (let i = 0; i < 40 * n; i++) thrown += Number(world.cells[i] === ID.SAND);
  assert.ok(thrown > 0);
  const heated = new World(16, 5);
  heated.set(8 * 16 + 8, ID.GUNPOWDER, 250);
  heated.step();
  assert.equal(heated.cells[8 * 16 + 8], ID.FIRE);
});

test('zero-g removes weight, settling, buoyancy, and convection but keeps grav sources', () => {
  const n = 32, draft = zeroGravity => {
    const world = new World(n, 5);
    world.zeroGravity = zeroGravity;
    world.set(10 * n + 8, ID.SAND);
    world.set(16 * n + 24, ID.FIRE, 650, true);
    // Sum vertical airflow in the column above the fire once the flow develops.
    let lift = 0;
    for (let t = 0; t < 120; t++) { world.step(); if (t >= 60) for (let y = 11; y < 16; y++) lift += world.windY[y * n + 24]; }
    return { world, lift };
  };
  const weightless = draft(true), normal = draft(false);
  assert.equal(weightless.world.cells[10 * n + 8], ID.SAND, 'sand floats in place');
  assert.notEqual(normal.world.cells[10 * n + 8], ID.SAND, 'sand falls with gravity');
  assert.ok(normal.lift < -5 && weightless.lift > normal.lift / 4, `fire draft ${normal.lift.toFixed(2)} vs ${weightless.lift.toFixed(2)}`);
  // Gas agitation is random, so compare net lift over several seeds.
  const lift = zeroGravity => [9, 10, 11].reduce((total, seed) => {
    const gas = new World(n, seed);
    gas.zeroGravity = zeroGravity;
    for (let x = 12; x < 20; x++) gas.set(16 * n + x, ID.VAPOR, 90);
    for (let t = 0; t < 60; t++) { gas.step(); for (let i = 0; i < gas.length; i++) if (gas.cells[i] === ID.VAPOR) total += gas.vy[i]; }
    return total;
  }, 0);
  const buoyant = lift(false), drifting = lift(true);
  assert.ok(buoyant < -40 && drifting > buoyant / 4, `vapor lift ${buoyant.toFixed(2)} vs ${drifting.toFixed(2)}`);
  const pulled = new World(n, 5);
  pulled.zeroGravity = true;
  pulled.set(16 * n + 16, ID.GRAV); pulled.set(16 * n + 10, ID.SAND);
  for (let t = 0; t < 80; t++) pulled.step();
  assert.equal(pulled.cells[16 * n + 10], ID.EMPTY, 'grav still attracts');
  assert.ok(NORMAL_GRAVITY < GRAV_STRENGTH);
});

test('boids flock in air; feesh fall inert until water, then school; heat kills both', () => {
  const n = 64, count = (world, id) => world.cells.reduce((sum, cell) => sum + Number(cell === id), 0);
  // Mean cosine between each boid's heading and its neighbors' within 6 cells.
  const alignment = world => {
    const boids = [];
    for (let i = 0; i < world.length; i++) if (world.cells[i] === ID.BOID) boids.push({ x: i % n, y: Math.floor(i / n), vx: world.vx[i], vy: world.vy[i] });
    let total = 0, pairs = 0;
    for (const a of boids) for (const b of boids) {
      if (a === b || Math.hypot(a.x - b.x, a.y - b.y) > 6) continue;
      total += (a.vx * b.vx + a.vy * b.vy) / (Math.hypot(a.vx, a.vy) * Math.hypot(b.vx, b.vy)); pairs++;
    }
    return total / pairs;
  };
  const birds = new World(n, 5);
  for (let k = 0; k < 40; k++) birds.set(((k * 37) % 40 + 10) * n + (k * 23) % 44 + 10, ID.BOID);
  const initial = alignment(birds);
  let aligned = 0;
  for (let t = 1; t <= 600; t++) { birds.step(); if (t > 300 && t % 30 === 0) aligned += alignment(birds) / 10; }
  assert.equal(count(birds, ID.BOID), 40);
  assert.ok(aligned > .55 && aligned > initial + .3, `local alignment ${initial.toFixed(2)} -> ${aligned.toFixed(2)}`);

  const pond = new World(n, 4);
  for (let x = 8; x < 56; x++) { pond.set(60 * n + x, ID.STONE); for (let y = 44; y < 60; y++) pond.set(y * n + x, ID.WATER); }
  for (let y = 30; y < 61; y++) { pond.set(y * n + 7, ID.STONE); pond.set(y * n + 56, ID.STONE); }
  for (let k = 0; k < 24; k++) pond.set((20 + k % 4) * n + 20 + k, ID.BOID, 20, false, true);
  const water = count(pond, ID.WATER);
  for (let t = 0; t < 300; t++) pond.step();
  const fish = [...pond.cells.keys()].filter(i => pond.cells[i] === ID.BOID);
  assert.equal(fish.length, 24);
  assert.ok(fish.every(i => pond.polarity[i] < 0 && pond.submerged(i, i % n, Math.floor(i / n))), 'every feesh is in the pond');
  assert.equal(count(pond, ID.WATER), water, 'swimming exchanges places with water');
  assert.ok(fish.some(i => Math.abs(pond.vx[i]) + Math.abs(pond.vy[i]) > .2), 'feesh swim');

  const beach = new World(16, 4);
  for (let x = 0; x < 16; x++) beach.set(15 * 16 + x, ID.SAND);
  beach.set(5 * 16 + 8, ID.BOID, 20, false, true);
  for (let t = 0; t < 120; t++) beach.step();
  const stranded = beach.cells.indexOf(ID.BOID);
  for (let t = 0; t < 60; t++) beach.step();
  assert.equal(Math.floor(stranded / 16), 14, 'a feesh out of water falls to the ground');
  assert.equal(beach.cells.indexOf(ID.BOID), stranded, 'and stays inert there');

  const hot = new World(16, 4);
  hot.set(8 * 16 + 8, ID.BOID, 120);
  hot.step();
  assert.equal(count(hot, ID.BOID), 0);
});

test('tick speed scales the tick rate, holds it at lower frame rates, and drops stalls', () => {
  const rate = (speed, frameMs, seconds = 2) => {
    const clock = { accumulator: 0 };
    let ticks = 0;
    const frames = Math.round(seconds * 1000 / frameMs);
    for (let frame = 0; frame < frames; frame++) ticks += ticksDue(clock, frameMs, speed);
    return ticks / seconds;
  };
  for (const speed of [.5, .75, 1, 1.5, 2, 3, 4, 6, 8]) {
    assert.ok(Math.abs(rate(speed, 1000 / 60) - TICK_RATE * speed) <= 1, `${speed}x at 60 fps`);
    assert.ok(Math.abs(rate(speed, 1000 / 30) - TICK_RATE * speed) <= 1, `${speed}x at 30 fps`);
  }
  const clock = { accumulator: 0 };
  assert.ok(ticksDue(clock, 1000, 8) <= 16, 'a one-second stall is bounded');
  assert.ok(clock.accumulator <= 1000 / TICK_RATE / 8, 'and leaves no backlog');
});

test('blob contours close around regions, join diagonals, and reverse around holes', () => {
  const n = 8, keys = (n + 2) ** 2 * 2;
  const buffers = { next: new Int32Array(keys).fill(-1), starts: new Int32Array(keys), points: new Float64Array(keys * 2) };
  const trace = cells => {
    const set = new Set(cells.map(([x, y]) => y * n + x)), areas = [];
    const inside = (x, y) => x >= 0 && y >= 0 && x < n && y < n && set.has(y * n + x) ? 1 : 0;
    const xs = cells.map(cell => cell[0]), ys = cells.map(cell => cell[1]);
    traceContours(n, inside, [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)], buffers, (points, count) => {
      let area = 0;
      for (let k = 0; k < count; k++) { const j = (k + 1) % count; area += points[k * 2] * points[j * 2 + 1] - points[j * 2] * points[k * 2 + 1]; }
      areas.push(area / 2);
    });
    assert.ok(buffers.next.every(value => value === -1), 'buffers are restored');
    return areas;
  };
  assert.deepEqual(trace([[3, 3]]), [.5]);
  assert.deepEqual(trace([[3, 3], [4, 3], [3, 4], [4, 4]]), [3.5]);
  assert.deepEqual(trace([[3, 3], [4, 4]]), [1.5], 'diagonal neighbors form one blob');
  assert.equal(trace([[1, 1], [2, 2], [3, 3], [4, 4], [5, 5]]).length, 1, 'a diagonal staircase is one blob');
  assert.deepEqual(trace([[0, 0], [1, 0], [0, 1]]), [2.5]);
  const ring = [];
  for (let y = 2; y <= 5; y++) for (let x = 2; x <= 5; x++) if (x === 2 || x === 5 || y === 2 || y === 5) ring.push([x, y]);
  assert.deepEqual(trace(ring), [15.5, -3.5]);
});
