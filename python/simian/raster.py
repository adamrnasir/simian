"""Qt-independent parts of web/renderer.mjs: tile selection and blitting,
blob contour tracing, and overlay pixels. Kernels follow the engine's
conventions (no reference counting; see engine.kernel)."""
import math

import numpy as np

from .engine import (BOID, ELEMENTS, GRAV, ICE, MAX_PRESSURE, NORMAL_GRAVITY, GRAV_STRENGTH, SEED, SOLID, STATE,
                     VAPOR, hot, kernel, submerged)

# Five weight variants per element, then one extra tile for antigrav sources.
ANTIGRAV_TILE = len(ELEMENTS) * 5
# Boid tiles follow it: bird with wings angled or flattened, then fish facing
# left or right, in water and stranded.
BIRD_TILE, BIRD_FLAT_TILE = ANTIGRAV_TILE + 1, ANTIGRAV_TILE + 2
FISH_LEFT_TILE, FISH_RIGHT_TILE = ANTIGRAV_TILE + 3, ANTIGRAV_TILE + 4
DRY_FISH_LEFT_TILE, DRY_FISH_RIGHT_TILE = ANTIGRAV_TILE + 5, ANTIGRAV_TILE + 6
TILE_COUNT = ANTIGRAV_TILE + 7
# `previous` holds tile indices; this value forces a redraw.
STALE = 255


@hot
def glyph_variant(w, i):
    material = w.cells[i]
    if not material:
        return 1
    if w.phase_locked[i]:
        return 4
    if abs(w.charge[i]) > .06:
        return 3
    if material == SEED and w.roots[i] >= 0:
        return 2 if w.life[i] == 2 else 0
    if material == VAPOR:
        return 0 if w.heat[i] > 85 else 2 if w.heat[i] < 50 else 1
    if w.heat[i] > 350 or (material == ICE and w.heat[i] < -10):
        return 2
    return 1


@hot
def tile_for(w, i, material):
    """Chooses the atlas tile for a cell; most elements use a weight variant."""
    if material == GRAV and w.polarity[i] < 0:
        return ANTIGRAV_TILE
    if material == BOID:
        if w.polarity[i] < 0:
            wet = submerged(w, i, i % w.size, i // w.size); left = w.branch[i] < 0
            if wet:
                return FISH_LEFT_TILE if left else FISH_RIGHT_TILE
            return DRY_FISH_LEFT_TILE if left else DRY_FISH_RIGHT_TILE
        # Wings alternate every 8 ticks of the bird's own clock while it moves.
        moving = abs(w.vx[i]) + abs(w.vy[i]) > .1
        return BIRD_FLAT_TILE if moving and (w.life[i] >> 3) & 1 else BIRD_TILE
    return material + glyph_variant(w, i) * len(ELEMENTS)


@kernel
def blit_tiles(w, atlas, pixels, previous):
    """Copies the tile of every changed cell into `pixels` (rows × columns of
    device pixels) and returns the particle count. `atlas` is (tiles, cell, cell)."""
    n = w.size; cell = atlas.shape[1]; population = 0
    for i in range(w.length):
        material = w.cells[i]
        if material:
            population += 1
        visual = tile_for(w, i, material)
        if previous[i] == visual:
            continue
        previous[i] = visual
        top = (i // n) * cell; left = (i % n) * cell
        for row in range(cell):
            for col in range(cell):
                pixels[top + row, left + col] = atlas[visual, row, col]
    return population


# Marching squares over cell centers, padded by one cell so regions touching
# the walls close. Edges: 0 top, 1 right, 2 bottom, 3 left of a square whose
# corners are cell centers. Segments (from, to pairs, indexed by the corner mask
# TL·8 | TR·4 | BR·2 | BL·1) keep the region on one consistent side, so each
# boundary point has exactly one successor and every contour closes; holes run
# opposite to outer edges and cancel under the nonzero fill rule. Saddles
# (5, 10) join diagonal cells, cutting off only the two outside corners, so
# diagonally touching cells form one continuous blob.
SEGMENTS = np.full((16, 4), -1, np.int64)
for _mask, _pairs in enumerate([[], [3, 2], [2, 1], [3, 1], [1, 0], [3, 0, 1, 2], [2, 0], [3, 0], [0, 3], [0, 2],
                                [0, 1, 2, 3], [0, 1], [1, 3], [1, 2], [2, 3], []]):
    SEGMENTS[_mask, :len(_pairs)] = _pairs


@hot
def _edge_key(width, x, y, edge):
    if edge == 0:
        return ((y + 1) * width + x + 1) * 2
    if edge == 2:
        return ((y + 2) * width + x + 1) * 2
    if edge == 3:
        return ((y + 1) * width + x + 1) * 2 + 1
    return ((y + 1) * width + x + 2) * 2 + 1


@hot
def _inside(groups, n, group, x, y):
    if x < 0 or y < 0 or x >= n or y >= n:
        return 0
    value = groups[y * n + x]
    return int(value == group if group else value != 0)


@kernel
def trace_contours(groups, n, group, min_x, min_y, max_x, max_y, next_key, starts, points, ends):
    """Traces the outlines of cells whose group is `group` (or any nonzero group
    when `group` is 0) within the given bounds. Contours are written to `points`
    as interleaved x, y in cell-center coordinates (on edge midpoints); `ends[k]`
    is the point count after contour k. Returns the number of contours. Buffers
    are sized for (n + 2)² * 2 keys; next_key starts filled with -1 and is
    restored afterward."""
    width = n + 2
    used = 0
    for y in range(min_y - 1, max_y + 1):
        tl = _inside(groups, n, group, min_x - 1, y); bl = _inside(groups, n, group, min_x - 1, y + 1)
        for x in range(min_x - 1, max_x + 1):
            tr = _inside(groups, n, group, x + 1, y); br = _inside(groups, n, group, x + 1, y + 1)
            mask = tl << 3 | tr << 2 | br << 1 | bl
            for s in range(0, 4, 2):
                if SEGMENTS[mask, s] < 0:
                    break
                origin = _edge_key(width, x, y, SEGMENTS[mask, s])
                next_key[origin] = _edge_key(width, x, y, SEGMENTS[mask, s + 1])
                starts[used] = origin; used += 1
            tl = tr; bl = br
    count = 0; contours = 0
    for u in range(used):
        key = starts[u]; first = count
        while next_key[key] >= 0:
            index = key >> 1; x = index % width - 1; y = index // width - 1
            points[count * 2] = x if key & 1 else x + .5
            points[count * 2 + 1] = y + .5 if key & 1 else y
            count += 1
            following = next_key[key]
            next_key[key] = -1
            key = following
        if count > first:
            ends[contours] = count; contours += 1
    return contours


def js_round(values):
    """Math.round for arrays: halves round toward +∞."""
    return np.floor(values + .5)


def blocked_mask(world):
    return (STATE[world.cells] == SOLID) | ((world.cells == SEED) & (world.roots >= 0))


def temperature_pixels(world, dark):
    """RGBA overlay: blue below 20°, clear at 20°, red above, on a fixed
    logarithmic scale so small thermal wakes stay readable without a lava
    reservoir saturating or rescaling the field."""
    temperature = np.where(world.cells != 0, world.heat, world.air_heat)
    delta = temperature - 20
    hot_color = (255, 117, 65) if dark else (190, 49, 12)
    cold_color = (90, 163, 255) if dark else (25, 80, 190)
    pixels = np.empty((world.length, 4), np.uint8)
    pixels[:, :3] = np.where((delta >= 0)[:, None], hot_color, cold_color)
    intensity = np.minimum(1, np.log1p(np.abs(delta) / 10) / math.log1p(108))
    pixels[:, 3] = np.where(np.isfinite(temperature), js_round(110 * np.nan_to_num(intensity)), 0)
    return pixels


def pressure_pixels(world, dark):
    """Warm overpressure and cool rarefaction on a gentle logarithmic ramp that
    keeps weak ripples without saturating modest gusts."""
    pressure = world.pressure
    intensity = np.log1p(np.abs(pressure) * 2) / math.log1p(MAX_PRESSURE * 2)
    positive = (205, 185, 157) if dark else (135, 104, 70)
    negative = (129, 190, 202) if dark else (54, 112, 130)
    pixels = np.empty((world.length, 4), np.uint8)
    pixels[:, :3] = np.where((pressure > 0)[:, None], positive, negative)
    pixels[:, 3] = np.where(blocked_mask(world), 0, js_round(68 * intensity))
    return pixels


# Grav field hues by net pull direction, blended by angle.
PULL_COLORS = {
    'light': {'up': (139, 37, 51), 'down': (21, 61, 135), 'left': (46, 125, 50), 'right': (176, 140, 0)},
    'dark': {'up': (220, 114, 124), 'down': (101, 142, 220), 'left': (120, 200, 120), 'right': (230, 205, 90)},
}


def net_gravity(world):
    """The net pull on powders and liquids: grav sources plus ordinary gravity
    (absent in zero-g), and the magnitude that maps to full intensity."""
    world.gravity()
    down = 0 if world.zero_gravity else NORMAL_GRAVITY
    peak = NORMAL_GRAVITY + GRAV_STRENGTH * max(1, world.grav_strength)
    return world.gravity_x, world.gravity_y + down, peak


def gravity_pixels(world, net_x, net_y, peak, dark):
    """Vertical (up red, down blue) and horizontal (left green, right yellow)
    hues weighted by each component's share of the pull."""
    hues = PULL_COLORS['dark' if dark else 'light']
    total = np.abs(net_x) + np.abs(net_y)
    share = np.divide(np.abs(net_y), total, out=np.zeros_like(total), where=total > 0)[:, None]
    vertical = np.where((net_y < 0)[:, None], hues['up'], hues['down'])
    horizontal = np.where((net_x < 0)[:, None], hues['left'], hues['right'])
    pixels = np.empty((world.length, 4), np.uint8)
    pixels[:, :3] = js_round(vertical * share + horizontal * (1 - share))
    alpha = js_round(68 * np.minimum(1, np.hypot(net_x, net_y) / peak))
    pixels[:, 3] = np.where((total == 0) | (world.cells == GRAV), 0, alpha)
    return pixels
