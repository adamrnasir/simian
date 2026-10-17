import { ANTIGRAV_COLOR, ELEMENTS, FEESH_COLOR, GRAV_STRENGTH, ID, MAX_PRESSURE, MAX_AIR_SPEED, NORMAL_GRAVITY, brushStart, elementSymbol } from './engine.mjs';

// Five weight variants per element, then one extra tile for antigrav sources.
const ANTIGRAV_TILE = ELEMENTS.length * 5;
// Boid tiles follow it: bird with wings angled or flattened, then fish facing
// left or right, in water and stranded.
const BIRD_TILE = ANTIGRAV_TILE + 1, BIRD_FLAT_TILE = ANTIGRAV_TILE + 2, FISH_LEFT_TILE = ANTIGRAV_TILE + 3, FISH_RIGHT_TILE = ANTIGRAV_TILE + 4;
const DRY_FISH_LEFT_TILE = ANTIGRAV_TILE + 5, DRY_FISH_RIGHT_TILE = ANTIGRAV_TILE + 6;

// Boid glyphs are paths, not text: exact shapes that can never render as emoji.
const bird = flat => (ctx, left, top, size) => {
  ctx.lineWidth = Math.max(1.2, size * .12); ctx.lineCap = ctx.lineJoin = 'round';
  ctx.beginPath();
  ctx.moveTo(left + size * .14, top + size * (flat ? .48 : .3));
  ctx.lineTo(left + size * .5, top + size * (flat ? .6 : .68));
  ctx.lineTo(left + size * .86, top + size * (flat ? .48 : .3));
  ctx.stroke();
};
const fish = facing => (ctx, left, top, size) => {
  const x = left + size * (.5 + facing * .08), y = top + size * .5, tail = x - facing * size * .24;
  ctx.beginPath(); ctx.ellipse(x, y, size * .25, size * .15, 0, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.moveTo(tail, y); ctx.lineTo(tail - facing * size * .2, y - size * .16); ctx.lineTo(tail - facing * size * .2, y + size * .16); ctx.closePath(); ctx.fill();
};

// Marching squares over cell centers, padded by one cell so regions touching
// the walls close. Edges: 0 top, 1 right, 2 bottom, 3 left of a square whose
// corners are cell centers. Segments (from, to pairs, indexed by the corner mask
// TL·8 | TR·4 | BR·2 | BL·1) keep the region on one consistent side, so each
// boundary point has exactly one successor and every contour closes; holes run
// opposite to outer edges and cancel under the nonzero fill rule. Saddles
// (5, 10) join diagonal cells, cutting off only the two outside corners, so
// diagonally touching cells form one continuous blob.
const SEGMENTS = [[], [3, 2], [2, 1], [3, 1], [1, 0], [3, 0, 1, 2], [2, 0], [3, 0], [0, 3], [0, 2], [0, 1, 2, 3], [0, 1], [1, 3], [1, 2], [2, 3], []];
// Over visible symbols, blobs are translucent so the glyphs stay legible.
const BLOB_OVER_SYMBOLS = .4;
const edgeKey = (width, x, y, edge) => edge === 0 ? ((y + 1) * width + x + 1) * 2 : edge === 2 ? ((y + 2) * width + x + 1) * 2
  : edge === 3 ? ((y + 1) * width + x + 1) * 2 + 1 : ((y + 1) * width + x + 2) * 2 + 1;

// Traces region outlines within bounds [minX, minY, maxX, maxY]. `inside(x, y)`
// returns 0 or 1. `emit(points, count)` receives each closed contour as
// interleaved x, y in cell-center coordinates (points lie on edge midpoints).
// Buffers are reused: next (filled with -1), starts, and points, each sized
// for (n + 2)² * 2 keys; next is restored to -1 afterward.
export function traceContours(n, inside, [minX, minY, maxX, maxY], { next, starts, points }, emit) {
  const width = n + 2;
  let used = 0;
  for (let y = minY - 1; y <= maxY; y++) {
    let tl = inside(minX - 1, y), bl = inside(minX - 1, y + 1);
    for (let x = minX - 1; x <= maxX; x++) {
      const tr = inside(x + 1, y), br = inside(x + 1, y + 1), segments = SEGMENTS[tl << 3 | tr << 2 | br << 1 | bl];
      for (let s = 0; s < segments.length; s += 2) {
        const from = edgeKey(width, x, y, segments[s]);
        next[from] = edgeKey(width, x, y, segments[s + 1]);
        starts[used++] = from;
      }
      tl = tr; bl = br;
    }
  }
  for (let u = 0; u < used; u++) {
    let key = starts[u], count = 0;
    while (next[key] >= 0) {
      const index = key >> 1, x = index % width - 1, y = (index / width | 0) - 1;
      points[count * 2] = key & 1 ? x : x + .5;
      points[count * 2 + 1] = key & 1 ? y + .5 : y;
      count++;
      const following = next[key];
      next[key] = -1;
      key = following;
    }
    if (count) emit(points, count);
  }
}

// Chooses the atlas tile for a cell; most elements use a weight variant.
function tileFor(world, i, id) {
  if (id === ID.GRAV && world.polarity[i] < 0) return ANTIGRAV_TILE;
  if (id === ID.BOID) {
    if (world.polarity[i] < 0) {
      const wet = world.submerged(i, i % world.size, Math.floor(i / world.size)), left = world.branch[i] < 0;
      return wet ? (left ? FISH_LEFT_TILE : FISH_RIGHT_TILE) : (left ? DRY_FISH_LEFT_TILE : DRY_FISH_RIGHT_TILE);
    }
    // Wings alternate every 8 ticks of the bird's own clock while it moves.
    const moving = Math.abs(world.vx[i]) + Math.abs(world.vy[i]) > .1;
    return moving && (world.life[i] >> 3) & 1 ? BIRD_FLAT_TILE : BIRD_TILE;
  }
  return id + glyphVariant(world, i) * ELEMENTS.length;
}
export const pixelRatio = () => Math.min(devicePixelRatio || 1, 3);

// Device pixels available to the field (its frame's width).
export const fieldPixels = canvas => Math.floor(canvas.parentElement.getBoundingClientRect().width * pixelRatio());

// Grav field hues by net pull direction, blended by angle.
const PULL_COLORS = {
  light: { up: [139, 37, 51], down: [21, 61, 135], left: [46, 125, 50], right: [176, 140, 0] },
  dark: { up: [220, 114, 124], down: [101, 142, 220], left: [120, 200, 120], right: [230, 205, 90] }
};

export function glyphVariant(world, i) {
  const id = world.cells[i];
  if (!id) return 1;
  if (world.phaseLocked[i]) return 4;
  if (Math.abs(world.charge[i]) > .06) return 3;
  if (id === ID.SEED && world.roots[i] >= 0) return world.life[i] === 2 ? 2 : 0;
  if (id === ID.VAPOR) return world.heat[i] > 85 ? 0 : world.heat[i] < 50 ? 2 : 1;
  if (world.heat[i] > 350 || (id === ID.ICE && world.heat[i] < -10)) return 2;
  return 1;
}

// Glyphs are rasterized once per theme/size, never typeset per particle per frame.
export class Renderer {
  constructor(canvas, world) {
    this.canvas = canvas;
    this.world = world;
    this.showSymbols = true;
    this.context = canvas.getContext('2d');
    if (!this.context) throw new Error('Canvas is unavailable in this browser.');
    this.resize();
  }

  resize() {
    // Cells are whole device pixels so the canvas is shown 1:1; CSS scaling
    // would resample and blur every glyph. The frame keeps its size: the canvas
    // is centered in it on a device-pixel boundary, and empty cells are
    // transparent, so the sub-cell remainder is invisible at any density.
    const ratio = pixelRatio(), available = fieldPixels(this.canvas);
    this.cell = Math.max(3, Math.floor(available / this.world.size));
    const size = this.cell * this.world.size, offset = Math.floor((available - size) / 2) / ratio;
    Object.assign(this.canvas.style, { width: `${size / ratio}px`, height: `${size / ratio}px`, left: `${offset}px`, top: `${offset}px` });
    this.canvas.width = this.canvas.height = this.cell * this.world.size;
    this.buffer = this.context.createImageData(this.canvas.width, this.canvas.height);
    this.pixels = new Uint32Array(this.buffer.data.buffer);
    this.previous = new Uint8Array(this.world.length);
    // One cell-resolution buffer, scaled up smoothly, serves every field overlay.
    this.fieldCanvas = document.createElement('canvas');
    this.fieldCanvas.width = this.fieldCanvas.height = this.world.size;
    this.fieldContext = this.fieldCanvas.getContext('2d');
    this.fieldPixels = this.fieldContext.createImageData(this.world.size, this.world.size);
    this.palette();
  }

  setWorld(world) {
    this.world = world;
    this.netX = this.netY = null;
    this.resize();
  }

  // Without symbols, each cell is a solid block of its glyph color.
  setShowSymbols(show) {
    this.showSymbols = show;
    this.palette();
  }

  // Blob mode draws smooth regions: translucent over the symbol tiles when
  // symbols are shown, or solid in their place. Leaving it forces every tile
  // to be redrawn into the pixel buffer.
  setBlobs(on) {
    this.blobs = on;
    if (!on) this.previous.fill(255);
  }

  palette() {
    const dark = document.documentElement.dataset.theme === 'dark';
    this.cursorColor = dark ? '#e2e3dc' : '#30322f';
    this.atlas = document.createElement('canvas');
    this.atlas.width = ELEMENTS.length * this.cell;
    this.atlas.height = this.cell * 6;
    const ctx = this.atlas.getContext('2d');
    ctx.textAlign = 'center'; ctx.textBaseline = 'alphabetic';
    // `backing` tints the cell (null for none); it defaults to the glyph color.
    const tile = (id, column, row, variant, color, shape = null, backing = color) => {
      // Bake a faint material-colored backing into every glyph variant. Cached
      // cell replacement moves/removes the tint along with the particle.
      ctx.fillStyle = backing || 'transparent';
      // Sand's tiny dot leaves mostly backing visible: give it a lighter bed
      // so a settled dune reads as pale sand rather than dark soil.
      ctx.globalAlpha = dark ? (id === ID.SAND ? .30 : .14) : (id === ID.SAND ? .10 : .16);
      ctx.fillRect(column * this.cell, row * this.cell, this.cell, this.cell);
      ctx.globalAlpha = 1;
      const glyphColor = variant === 3 ? (dark ? '#fff2cf' : '#b84931') : color;
      if (!this.showSymbols) {
        ctx.fillStyle = glyphColor;
        ctx.fillRect(column * this.cell, row * this.cell, this.cell, this.cell);
        return;
      }
      ctx.save();
      ctx.beginPath(); ctx.rect(column * this.cell, row * this.cell, this.cell, this.cell); ctx.clip();
      if (shape) {
        ctx.fillStyle = ctx.strokeStyle = glyphColor;
        shape(ctx, column * this.cell, row * this.cell, this.cell);
        ctx.restore();
        return;
      }
      const weight = (dark ? [400, 500, 800, 800, 1000] : [500, 600, 900, 900, 1000])[variant];
      ctx.font = `${weight} ${this.cell * 1.5}px monospace`;
      const symbol = elementSymbol(id, variant === 4);
      let metrics = ctx.measureText(symbol);
      const fit = Math.min(1, this.cell * .96 / Math.max(metrics.width, metrics.actualBoundingBoxAscent + metrics.actualBoundingBoxDescent));
      if (fit < 1) { ctx.font = `${weight} ${this.cell * 1.5 * fit}px monospace`; metrics = ctx.measureText(symbol); }
      const baseline = this.cell * (row + .5) + (metrics.actualBoundingBoxAscent - metrics.actualBoundingBoxDescent) / 2;
      ctx.fillStyle = glyphColor;
      ctx.fillText(symbol, (column + .5) * this.cell, baseline, this.cell * .96);
      if ((!dark && variant < 2) || variant === 4) {
        ctx.strokeStyle = ctx.fillStyle; ctx.lineWidth = variant === 4 ? Math.max(1, this.cell * .18) : .45;
        ctx.strokeText(symbol, (column + .5) * this.cell, baseline, this.cell * .96);
      }
      ctx.restore();
    };
    for (let variant = 0; variant < 5; variant++) ELEMENTS.forEach((element, id) => { if (id) tile(id, id, variant, variant, dark ? element.dark : element.light); });
    // Row 5 holds alternate forms: antigrav in Grav's column, boids in the unused columns 0–5.
    const boid = dark ? ELEMENTS[ID.BOID].dark : ELEMENTS[ID.BOID].light, feesh = dark ? FEESH_COLOR.dark : FEESH_COLOR.light;
    tile(ID.GRAV, ID.GRAV, 5, 1, dark ? ANTIGRAV_COLOR.dark : ANTIGRAV_COLOR.light);
    // Birds and stranded feesh are bare glyphs; swimming feesh sit on water's tint.
    const water = dark ? ELEMENTS[ID.WATER].dark : ELEMENTS[ID.WATER].light;
    tile(ID.BOID, 0, 5, 1, boid, bird(false), null);
    tile(ID.BOID, 1, 5, 1, boid, bird(true), null);
    tile(ID.BOID, 2, 5, 1, feesh, fish(-1), water);
    tile(ID.BOID, 3, 5, 1, feesh, fish(1), water);
    tile(ID.BOID, 4, 5, 1, feesh, fish(-1), null);
    tile(ID.BOID, 5, 5, 1, feesh, fish(1), null);
    // Precompute row views once. Updating cells uses typed-array copies rather
    // than thousands of drawImage calls or temporary arrays each frame.
    const rows = (column, atlasRow) => {
      const pixels = new Uint32Array(ctx.getImageData(column * this.cell, atlasRow * this.cell, this.cell, this.cell).data.buffer);
      return Array.from({ length: this.cell }, (_, row) => pixels.subarray(row * this.cell, (row + 1) * this.cell));
    };
    this.tiles = [];
    for (let variant = 0; variant < 5; variant++) for (let id = 0; id < ELEMENTS.length; id++) this.tiles.push(rows(id, variant));
    this.tiles[ANTIGRAV_TILE] = rows(ID.GRAV, 5);
    [BIRD_TILE, BIRD_FLAT_TILE, FISH_LEFT_TILE, FISH_RIGHT_TILE, DRY_FISH_LEFT_TILE, DRY_FISH_RIGHT_TILE].forEach((index, column) => { this.tiles[index] = rows(column, 5); });
    this.previous.fill(255);
  }

  draw(cursor, diameter, overlays = {}, direction = null) {
    const ctx = this.context, unit = this.cell, world = this.world;
    let population = 0;
    const tiles = !this.blobs || this.showSymbols;
    if (tiles) {
      for (let i = 0; i < world.length; i++) {
        const id = world.cells[i];
        if (id) population++;
        const visual = tileFor(world, i, id);
        if (this.previous[i] === visual) continue;
        this.previous[i] = visual;
        const offset = Math.floor(i / world.size) * unit * this.canvas.width + i % world.size * unit;
        const rows = this.tiles[visual];
        for (let row = 0; row < unit; row++) this.pixels.set(rows[row], offset + row * this.canvas.width);
      }
      ctx.putImageData(this.buffer, 0, 0);
    }
    if (this.blobs) {
      const count = this.drawBlobs(tiles ? BLOB_OVER_SYMBOLS : 1, !tiles);
      if (!tiles) population = count;
    }
    if (overlays.temperature) this.drawTemperature();
    if (overlays.wind || overlays.windArrows) this.drawWind(overlays.wind, overlays.windArrows);
    if (overlays.grav || overlays.gravArrows) this.drawGrav(overlays.grav, overlays.gravArrows);
    if (cursor.visible) {
      ctx.strokeStyle = this.cursorColor;
      ctx.globalAlpha = .55;
      ctx.lineWidth = 1;
      ctx.beginPath();
      const cx = (brushStart(cursor.x, diameter) + diameter / 2) * unit;
      const cy = (brushStart(cursor.y, diameter) + diameter / 2) * unit;
      ctx.arc(cx, cy, diameter / 2 * unit, 0, Math.PI * 2);
      if (direction) {
        const length = (diameter / 2 + 3) * unit;
        const ex = cx + direction.x * length, ey = cy + direction.y * length;
        ctx.moveTo(cx, cy); ctx.lineTo(ex, ey);
        ctx.moveTo(ex - direction.x * unit - direction.y * unit * .5, ey - direction.y * unit + direction.x * unit * .5);
        ctx.lineTo(ex, ey); ctx.lineTo(ex - direction.x * unit + direction.y * unit * .5, ey - direction.y * unit - direction.x * unit * .5);
      }
      ctx.stroke(); ctx.globalAlpha = 1;
    }
    return population;
  }

  // Groups cells by element (antigrav and feesh apart) and draws each group's
  // contours as closed quadratic B-splines through the edge midpoints.
  // Independently smoothed neighbors would leave slivers at corners and
  // junctions, so each group is first stroked wide in its own color, clipped
  // to the smoothed outline of all matter: gaps between blobs fill in, but no
  // blob grows into empty space. Fills then go on top, keeping the shared
  // boundaries where they were. The layer is composited once at `alpha`.
  drawBlobs(alpha, clear) {
    const world = this.world, n = world.size, unit = this.cell;
    const dark = document.documentElement.dataset.theme === 'dark', groupCount = ELEMENTS.length * 2;
    const keys = (n + 2) * (n + 2) * 2;
    if (!this.blobBuffers || this.blobBuffers.next.length !== keys) {
      this.blobGroups = new Uint8Array(world.length);
      this.blobBounds = new Int32Array(groupCount * 4);
      this.blobBuffers = { next: new Int32Array(keys).fill(-1), starts: new Int32Array(keys), points: new Float64Array(keys * 2) };
    }
    if (!this.blobLayer || this.blobLayer.width !== this.canvas.width || this.blobLayer.height !== this.canvas.height) {
      this.blobLayer = document.createElement('canvas');
      this.blobLayer.width = this.canvas.width; this.blobLayer.height = this.canvas.height;
    }
    const groups = this.blobGroups, bounds = this.blobBounds, layer = this.blobLayer.getContext('2d');
    // Group 0 (empty cells) is never drawn, so its bounds hold the union of all matter.
    for (let g = 0; g < groupCount; g++) { bounds[g * 4] = bounds[g * 4 + 1] = n; bounds[g * 4 + 2] = bounds[g * 4 + 3] = -1; }
    const grow = (b, x, y) => {
      if (x < bounds[b]) bounds[b] = x;
      if (y < bounds[b + 1]) bounds[b + 1] = y;
      if (x > bounds[b + 2]) bounds[b + 2] = x;
      if (y > bounds[b + 3]) bounds[b + 3] = y;
    };
    let population = 0;
    for (let y = 0, i = 0; y < n; y++) for (let x = 0; x < n; x++, i++) {
      const id = world.cells[i];
      const g = groups[i] = id ? id * 2 + Number((id === ID.GRAV || id === ID.BOID) && world.polarity[i] < 0) : 0;
      if (!g) continue;
      population++;
      grow(g * 4, x, y); grow(0, x, y);
    }
    const px = value => (value + .5) * unit;
    const outline = (inside, b) => {
      const path = new Path2D();
      traceContours(n, inside, [bounds[b], bounds[b + 1], bounds[b + 2], bounds[b + 3]], this.blobBuffers, (points, count) => {
        const last = (count - 1) * 2;
        path.moveTo(px((points[last] + points[0]) / 2), px((points[last + 1] + points[1]) / 2));
        for (let k = 0; k < count; k++) {
          const next = (k + 1) % count;
          path.quadraticCurveTo(px(points[k * 2]), px(points[k * 2 + 1]), px((points[k * 2] + points[next * 2]) / 2), px((points[k * 2 + 1] + points[next * 2 + 1]) / 2));
        }
        path.closePath();
      });
      return path;
    };
    const shapes = [];
    for (let g = 2; g < groupCount; g++) {
      if (bounds[g * 4 + 2] < 0) continue;
      const id = g >> 1, colors = g & 1 ? (id === ID.GRAV ? ANTIGRAV_COLOR : FEESH_COLOR) : ELEMENTS[id];
      shapes.push({ color: dark ? colors.dark : colors.light, path: outline((x, y) => x >= 0 && y >= 0 && x < n && y < n && groups[y * n + x] === g ? 1 : 0, g * 4) });
    }
    layer.clearRect(0, 0, this.blobLayer.width, this.blobLayer.height);
    if (shapes.length) {
      layer.save();
      layer.clip(outline((x, y) => x >= 0 && y >= 0 && x < n && y < n && groups[y * n + x] ? 1 : 0, 0));
      layer.lineWidth = unit; layer.lineJoin = 'round';
      for (const shape of shapes) { layer.strokeStyle = shape.color; layer.stroke(shape.path); }
      layer.restore();
      for (const shape of shapes) { layer.fillStyle = shape.color; layer.fill(shape.path); }
    }
    const ctx = this.context;
    if (clear) ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    ctx.globalAlpha = alpha;
    ctx.drawImage(this.blobLayer, 0, 0);
    ctx.globalAlpha = 1;
    return population;
  }

  drawTemperature() {
    const world = this.world, pixels = this.fieldPixels.data;
    const dark = document.documentElement.dataset.theme === 'dark';
    const hot = dark ? [255, 117, 65] : [190, 49, 12];
    const cold = dark ? [90, 163, 255] : [25, 80, 190];
    for (let i = 0; i < world.length; i++) {
      const temperature = world.cells[i] ? world.heat[i] : world.airHeat[i];
      const delta = temperature - 20, color = delta >= 0 ? hot : cold, offset = i * 4;
      // A fixed logarithmic scale makes small thermal wakes readable without
      // letting a lava reservoir saturate the entire field or rescale it.
      const intensity = Math.min(1, Math.log1p(Math.abs(delta) / 10) / Math.log1p(108));
      pixels[offset] = color[0]; pixels[offset + 1] = color[1]; pixels[offset + 2] = color[2];
      pixels[offset + 3] = Number.isFinite(temperature) ? Math.round(110 * intensity) : 0;
    }
    this.presentField();
  }

  drawWind(showPressure, showArrows) {
    const world = this.world;
    const dark = document.documentElement.dataset.theme === 'dark';
    if (showPressure) {
      const pixels = this.fieldPixels.data;
      for (let i = 0; i < world.length; i++) {
        const p = world.pressure[i], offset = i * 4;
        // Use the full pressure range without saturating modest gusts. A gentle
        // logarithmic ramp retains weak ripples while keeping the field quiet.
        const intensity = Math.log1p(Math.abs(p) * 2) / Math.log1p(MAX_PRESSURE * 2);
        pixels[offset] = p > 0 ? (dark ? 205 : 135) : (dark ? 129 : 54);
        pixels[offset + 1] = p > 0 ? (dark ? 185 : 104) : (dark ? 190 : 112);
        pixels[offset + 2] = p > 0 ? (dark ? 157 : 70) : (dark ? 202 : 130);
        pixels[offset + 3] = world.blocked(i) ? 0 : Math.round(68 * intensity);
      }
      this.presentField();
    }
    if (showArrows) this.drawArrows(world.windX, world.windY, dark ? '#a8e8d9' : '#32746b', speed => speed < .025 ? 0 : Math.log1p(speed * 4) / Math.log1p(Math.SQRT2 * MAX_AIR_SPEED * 4), i => world.blocked(i));
  }

  // Shows the net pull on powders and liquids: grav sources plus ordinary
  // gravity (absent in zero-g). Gas feels buoyancy instead and is not shown.
  drawGrav(showField, showArrows) {
    const world = this.world, dark = document.documentElement.dataset.theme === 'dark';
    // The overlay may be shown while paused, before the next tick refreshes the
    // field. Recomputing is idempotent and skipped when no source changed.
    world.gravity();
    const down = world.zeroGravity ? 0 : NORMAL_GRAVITY, peak = NORMAL_GRAVITY + GRAV_STRENGTH * Math.max(1, world.gravStrength);
    const netX = this.netX ||= new Float32Array(world.length), netY = this.netY ||= new Float32Array(world.length);
    for (let i = 0; i < world.length; i++) { netX[i] = world.gravityX[i]; netY[i] = world.gravityY[i] + down; }
    if (showField) {
      const pixels = this.fieldPixels.data, hues = PULL_COLORS[dark ? 'dark' : 'light'];
      for (let i = 0; i < world.length; i++) {
        const x = netX[i], y = netY[i], sum = Math.abs(x) + Math.abs(y), offset = i * 4;
        if (!sum || world.cells[i] === ID.GRAV) { pixels[offset + 3] = 0; continue; }
        // Vertical (up red, down blue) and horizontal (left green, right yellow)
        // hues are weighted by each component's share of the pull.
        const vertical = y < 0 ? hues.up : hues.down, horizontal = x < 0 ? hues.left : hues.right, share = Math.abs(y) / sum;
        for (let channel = 0; channel < 3; channel++) pixels[offset + channel] = Math.round(vertical[channel] * share + horizontal[channel] * (1 - share));
        pixels[offset + 3] = Math.round(68 * Math.min(1, Math.hypot(x, y) / peak));
      }
      this.presentField();
    }
    if (showArrows) this.drawArrows(netX, netY, dark ? ANTIGRAV_COLOR.dark : ANTIGRAV_COLOR.light, speed => speed < .004 ? 0 : Math.min(1, speed / peak), i => world.cells[i] === ID.GRAV);
  }

  presentField() {
    this.fieldContext.putImageData(this.fieldPixels, 0, 0);
    this.context.imageSmoothingEnabled = true;
    this.context.drawImage(this.fieldCanvas, 0, 0, this.canvas.width, this.canvas.height);
  }

  // Draws a sparse arrow grid; scale maps a vector's magnitude to 0–1 length.
  drawArrows(fieldX, fieldY, color, scale, skip) {
    const ctx = this.context, world = this.world, unit = this.cell, stride = 4;
    ctx.beginPath(); ctx.strokeStyle = color; ctx.lineWidth = Math.max(1, unit / 8);
    for (let y = 1; y < world.size; y += stride) for (let x = 1; x < world.size; x += stride) {
      const i = y * world.size + x;
      if (skip(i)) continue;
      const vx = fieldX[i], vy = fieldY[i], speed = Math.hypot(vx, vy), amount = scale(speed);
      if (!amount) continue;
      const cx = (x + .5) * unit, cy = (y + .5) * unit;
      const length = unit * 3 * amount, dx = vx / speed, dy = vy / speed;
      const head = Math.min(unit * .5, length * .4);
      const ex = cx + dx * length, ey = cy + dy * length;
      ctx.moveTo(cx, cy); ctx.lineTo(ex, ey);
      ctx.moveTo(ex - dx * head - dy * head * .8, ey - dy * head + dx * head * .8);
      ctx.lineTo(ex, ey); ctx.lineTo(ex - dx * head + dy * head * .8, ey - dy * head - dx * head * .8);
    }
    ctx.globalAlpha = .45; ctx.stroke(); ctx.globalAlpha = 1;
  }
}
